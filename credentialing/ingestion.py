"""Lossless, append-only ingestion of closed Project E export batches.

This module records source data and structural integrity findings only. It does
not apply credentialing rules or make clinical/committee decisions.
"""

from __future__ import annotations

import csv
import hashlib
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any


LEDGER_VERSION = "credentialing-evidence-ledger/1"

CSV_FILES = (
    "applications.csv",
    "application-disclosures.csv",
    "declared-history.csv",
    "declared-credentials.csv",
    "privilege-requests.csv",
    "licence-lookup-wa.csv",
    "licence-lookup-other-states.csv",
    "certification-replies.csv",
    "verification-replies.csv",
    "verification-attempts.csv",
    "peer-referees.csv",
    "peer-reference-replies.csv",
    "correspondence.csv",
)

DOCUMENT_FOLDERS = ("letters", "dispositions", "decisions")

# Keys identify source-record occurrences, not credentialing conclusions.
STABLE_KEYS: dict[str, tuple[str, ...]] = {
    "applications.csv": ("application_id", "revision"),
    "application-disclosures.csv": ("application_id", "revision", "question_code"),
    "declared-history.csv": ("application_id", "revision", "entry_id"),
    "declared-credentials.csv": ("application_id", "revision", "declaration_id"),
    "privilege-requests.csv": ("application_id", "revision", "request_id"),
    # These exports are re-run. Include lookup_date so a later observation of
    # the same practitioner/credential remains a distinct source observation.
    "licence-lookup-wa.csv": (
        "lastname", "firstname", "middlename", "birthyear", "credentialnumber", "lookup_date"
    ),
    "licence-lookup-other-states.csv": ("board_state", "licence_number", "lookup_date"),
    "certification-replies.csv": ("reply_id",),
    "verification-replies.csv": ("reply_id",),
    "verification-attempts.csv": ("attempt_id",),
    "peer-referees.csv": ("referee_id",),
    "peer-reference-replies.csv": ("reply_id",),
    "correspondence.csv": ("letter_id",),
}

REVISION_SCOPED_FILES = {
    "application-disclosures.csv",
    "declared-history.csv",
    "declared-credentials.csv",
    "privilege-requests.csv",
    "peer-referees.csv",
}


@dataclass(frozen=True)
class IngestionIssue:
    code: str
    message: str
    filename: str | None = None
    row_number: int | None = None

    def as_dict(self) -> dict[str, Any]:
        return {
            "code": self.code,
            "message": self.message,
            "filename": self.filename,
            "row_number": self.row_number,
        }


@dataclass
class IngestionResult:
    ledger: dict[str, Any]
    issues: list[IngestionIssue]
    changed: bool
    batch_id: str | None


def empty_ledger() -> dict[str, Any]:
    return {"ledger_version": LEDGER_VERSION, "batches": []}


def load_ledger(path: str | Path) -> dict[str, Any]:
    with Path(path).open(encoding="utf-8") as source:
        ledger = json.load(source)
    if not isinstance(ledger, dict) or ledger.get("ledger_version") != LEDGER_VERSION:
        raise ValueError(f"Unsupported or malformed evidence ledger: {path}")
    if not isinstance(ledger.get("batches"), list):
        raise ValueError(f"Evidence ledger has no batches list: {path}")
    return ledger


def stable_key(filename: str, values: dict[str, Any]) -> str | None:
    fields = STABLE_KEYS[filename]
    optional_blank = {"middlename"} if filename == "licence-lookup-wa.csv" else set()
    if any(values.get(field) in (None, "") for field in fields if field not in optional_blank):
        return None
    return json.dumps({field: values[field] for field in fields}, ensure_ascii=False, sort_keys=True)


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _readme_metadata(content: str) -> tuple[int | None, str | None, str | None]:
    title = re.search(r"^# Batch\s+(\d+)\b", content, flags=re.MULTILINE)
    export_date = re.search(r"^\*\*Export date:\s*(\d{4}-\d{2}-\d{2})\*\*", content, flags=re.MULTILINE)
    window = re.search(r"^\*\*Window covered:\s*(.*?)\*\*", content, flags=re.MULTILINE)
    return (
        int(title.group(1)) if title else None,
        export_date.group(1) if export_date else None,
        window.group(1).strip() if window else None,
    )


def _readme_counts(content: str, filenames: tuple[str, ...]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for name, count in re.findall(r"^\|\s*`([^`]+)`\s*\|\s*(\d+)\s*\|\s*$", content, re.MULTILINE):
        name = name.removesuffix("/")
        if name in filenames:
            counts[name] = int(count)
    return counts


def _batch_files_digest(batch_dir: Path) -> str:
    digest = hashlib.sha256()
    for path in sorted(p for p in batch_dir.rglob("*") if p.is_file()):
        relative = path.relative_to(batch_dir).as_posix().encode("utf-8")
        data = path.read_bytes()
        digest.update(len(relative).to_bytes(8, "big"))
        digest.update(relative)
        digest.update(len(data).to_bytes(8, "big"))
        digest.update(data)
    return digest.hexdigest()


def _read_csv(path: Path, filename: str, issues: list[IngestionIssue]) -> list[dict[str, Any]]:
    try:
        with path.open(encoding="utf-8-sig", newline="") as stream:
            reader = csv.DictReader(stream)
            if reader.fieldnames is None:
                issues.append(IngestionIssue("missing_csv_header", "CSV has no header row.", filename))
                return []
            if len(reader.fieldnames) != len(set(reader.fieldnames)):
                issues.append(IngestionIssue("duplicate_csv_header", "CSV contains duplicate column names.", filename))
            rows: list[dict[str, Any]] = []
            for values in reader:
                row_number = reader.line_num
                row = dict(values)
                extras = row.pop(None, None)
                if extras is not None:
                    row["__extra_values__"] = extras
                    issues.append(IngestionIssue(
                        "csv_row_has_extra_values",
                        "Row has more values than the header; extra values were retained.",
                        filename,
                        row_number,
                    ))
                if any(value is None for value in row.values()):
                    issues.append(IngestionIssue(
                        "csv_row_has_missing_cells",
                        "Row has fewer values than the header; missing cells were retained as null.",
                        filename,
                        row_number,
                    ))
                rows.append({
                    "filename": filename,
                    "row_number": row_number,
                    "stable_key": stable_key(filename, row),
                    "values": row,
                })
            return rows
    except (OSError, UnicodeError, csv.Error) as exc:
        issues.append(IngestionIssue("csv_read_error", str(exc), filename))
        return []


def _issue(code: str, message: str, record: dict[str, Any] | None = None) -> IngestionIssue:
    return IngestionIssue(
        code,
        message,
        record.get("filename") if record else None,
        record.get("row_number") if record else None,
    )


def _all_records(batches: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [record for batch in batches for record in batch.get("records", [])]


def _find_integrity_issues(
    batch: dict[str, Any], previous_batches: list[dict[str, Any]], issues: list[IngestionIssue]
) -> None:
    previous_records = _all_records(previous_batches)
    current_records = batch["records"]

    # Stable keys and exact source rows are checked separately: changed source
    # values under an existing key are an identifier conflict, not a correction.
    seen_keys: dict[tuple[str, str], dict[str, Any]] = {}
    seen_rows: set[tuple[str, str]] = set()
    for record in previous_records:
        filename = record["filename"]
        key = record.get("stable_key")
        serialized = json.dumps(record["values"], ensure_ascii=False, sort_keys=True)
        seen_rows.add((filename, _sha256(serialized.encode("utf-8"))))
        if key is not None:
            seen_keys.setdefault((filename, key), record)
    for record in current_records:
        filename = record["filename"]
        key = record.get("stable_key")
        serialized = json.dumps(record["values"], ensure_ascii=False, sort_keys=True)
        row_hash = _sha256(serialized.encode("utf-8"))
        row_identity = (filename, row_hash)
        if row_identity in seen_rows:
            issues.append(_issue("duplicate_source_record", "Exact source row is repeated in the ledger or batch.", record))
        else:
            seen_rows.add(row_identity)
        if key is None:
            issues.append(_issue("missing_stable_identifier", "Stable-key columns are empty; row number is retained as provenance.", record))
            continue
        key_identity = (filename, key)
        prior = seen_keys.get(key_identity)
        if prior is not None:
            prior_serialized = json.dumps(prior["values"], ensure_ascii=False, sort_keys=True)
            if prior_serialized == serialized:
                # Exact repeats are already reported as duplicate source rows.
                pass
            else:
                issues.append(_issue(
                    "identifier_reused_with_different_values",
                    f"Stable key {key} appears with different source values; both observations are retained.",
                    record,
                ))
        else:
            seen_keys[key_identity] = record

    all_records = previous_records + current_records
    applications = [r for r in all_records if r["filename"] == "applications.csv"]
    known_app_ids = {r["values"].get("application_id") for r in applications}
    known_revisions = {
        (r["values"].get("application_id"), r["values"].get("revision")) for r in applications
    }

    applicant_ids_by_file: dict[str, set[str]] = {}
    app_person_ids: dict[str, str] = {}
    app_identity: dict[tuple[str, str, str, str], set[str]] = {}
    for record in applications:
        values = record["values"]
        app_id = values.get("application_id")
        person_id = values.get("applicant_id")
        if app_id in (None, "") or values.get("revision") in (None, ""):
            issues.append(_issue("incomplete_application_identifier", "Application row lacks application_id or revision.", record))
        if app_id and person_id:
            previous_person = app_person_ids.setdefault(app_id, person_id)
            if previous_person != person_id:
                issues.append(_issue("application_person_identifier_conflict", f"{app_id} maps to multiple applicant_id values.", record))
        identity = tuple(values.get(field) or "" for field in ("last_name", "first_name", "middle_name", "birth_year"))
        if identity[0] and identity[1] and identity[3]:
            app_identity.setdefault(identity, set()).add(app_id)

    for identity, app_ids in app_identity.items():
        if len(app_ids) > 1:
            issues.append(IngestionIssue(
                "ambiguous_washington_join_identity",
                f"Washington name/birth-year join key maps to multiple application IDs: {identity!r}.",
                "applications.csv",
            ))

    for record in all_records:
        values = record["values"]
        filename = record["filename"]
        app_id = values.get("application_id")
        if app_id and filename != "applications.csv" and app_id not in known_app_ids:
            issues.append(_issue("unknown_application_id", f"application_id {app_id!r} has no application record in the ledger.", record))
        if filename in REVISION_SCOPED_FILES and app_id and values.get("revision") not in (None, ""):
            if (app_id, values["revision"]) not in known_revisions:
                issues.append(_issue(
                    "unknown_application_revision",
                    f"Application revision ({app_id!r}, {values['revision']!r}) is not present in the ledger.",
                    record,
                ))

    # The Washington export's documented join is the exact four-part identity.
    current_wa = [r for r in current_records if r["filename"] == "licence-lookup-wa.csv"]
    wa_seen: dict[tuple[str, str, str, str], dict[str, Any]] = {}
    for record in current_wa:
        values = record["values"]
        identity = tuple(values.get(field) or "" for field in ("lastname", "firstname", "middlename", "birthyear"))
        previous = wa_seen.get(identity)
        if previous is not None:
            issues.append(_issue(
                "duplicate_washington_join_identity",
                f"Washington export join identity {identity!r} occurs more than once in this batch.",
                record,
            ))
        else:
            wa_seen[identity] = record
        matching_apps = app_identity.get(identity, set())
        if len(matching_apps) > 1:
            issues.append(_issue("ambiguous_washington_join_identity", f"Washington row maps to multiple application IDs: {identity!r}.", record))

    # Validate declared foreign-key relationships without interpreting their meaning.
    history_keys = {
        (r["values"].get("application_id"), r["values"].get("entry_id"))
        for r in all_records if r["filename"] == "declared-history.csv"
    }
    declaration_keys = {
        (r["values"].get("application_id"), r["values"].get("declaration_id"))
        for r in all_records if r["filename"] == "declared-credentials.csv"
    }
    referee_keys = {
        (r["values"].get("application_id"), r["values"].get("referee_id"))
        for r in all_records if r["filename"] == "peer-referees.csv"
    }
    for record in all_records:
        values = record["values"]
        filename = record["filename"]
        app_id = values.get("application_id")
        if filename == "verification-replies.csv" and values.get("entry_id"):
            if (app_id, values["entry_id"]) not in history_keys:
                issues.append(_issue("unknown_history_entry_reference", "Verification reply references no declared-history entry for this application.", record))
        if filename == "certification-replies.csv" and values.get("declaration_id"):
            if (app_id, values["declaration_id"]) not in declaration_keys:
                issues.append(_issue("unknown_credential_declaration_reference", "Certification reply references no declared credential for this application.", record))
        if filename == "peer-reference-replies.csv" and values.get("referee_id"):
            if (app_id, values["referee_id"]) not in referee_keys:
                issues.append(_issue("unknown_referee_reference", "Peer-reference reply references no referee record for this application.", record))


def ingest_batch(batch_dir: str | Path, ledger: dict[str, Any] | None = None) -> IngestionResult:
    """Read one closed export directory and append its raw observations to a ledger."""
    directory = Path(batch_dir)
    prior_ledger = ledger if ledger is not None else empty_ledger()
    if prior_ledger.get("ledger_version") != LEDGER_VERSION or not isinstance(prior_ledger.get("batches"), list):
        raise ValueError("Unsupported or malformed evidence ledger")

    issues: list[IngestionIssue] = []
    readme_path = directory / "README.md"
    if not readme_path.is_file():
        return IngestionResult(prior_ledger, [IngestionIssue("missing_batch_readme", f"Required README not found: {readme_path}", "README.md")], False, None)
    try:
        readme_bytes = readme_path.read_bytes()
        readme_text = readme_bytes.decode("utf-8-sig")
    except (OSError, UnicodeError) as exc:
        return IngestionResult(prior_ledger, [IngestionIssue("readme_read_error", str(exc), "README.md")], False, None)

    batch_number, export_date, window = _readme_metadata(readme_text)
    if batch_number is None or export_date is None:
        return IngestionResult(prior_ledger, [IngestionIssue(
            "invalid_batch_readme", "README must state '# Batch N' and '**Export date: YYYY-MM-DD**'.", "README.md"
        )], False, None)
    batch_id = f"batch-{batch_number:02d}-{export_date}"
    input_digest = _batch_files_digest(directory)
    existing = next((b for b in prior_ledger["batches"] if b.get("batch_id") == batch_id), None)
    if existing is not None:
        if existing.get("source_digest") == input_digest:
            retained_issues = [IngestionIssue(**issue) for issue in existing.get("issues", [])]
            return IngestionResult(prior_ledger, retained_issues, False, batch_id)
        return IngestionResult(prior_ledger, [IngestionIssue(
            "immutable_batch_changed",
            f"{batch_id} is already recorded with a different source digest; prior observations were preserved and no replacement was made.",
            "README.md",
        )], False, batch_id)

    if prior_ledger["batches"]:
        prior_numbers = [b.get("batch_number", 0) for b in prior_ledger["batches"]]
        if batch_number <= max(prior_numbers):
            issues.append(IngestionIssue(
                "batch_out_of_order",
                f"Batch {batch_number} is not later than the highest batch already in the ledger.",
                "README.md",
            ))

    expected_record_counts = _readme_counts(readme_text, CSV_FILES)
    batch: dict[str, Any] = {
        "batch_id": batch_id,
        "batch_number": batch_number,
        "export_date": export_date,
        "window_covered": window,
        "source_directory": str(directory),
        "source_digest": input_digest,
        "readme": {
            "filename": "README.md",
            "content": readme_text,
            "sha256": _sha256(readme_bytes),
        },
        "record_files": [],
        "records": [],
        "documents": [],
        "join_rules": [
            {
                "source": "office/export-notes.txt — The three joins that matter, rule 1",
                "keys": ["application_id", "revision where revision-specific"],
                "revision_scoped_files": sorted(REVISION_SCOPED_FILES),
            },
            {
                "source": "office/export-notes.txt — The three joins that matter, rule 2",
                "file": "licence-lookup-wa.csv",
                "keys": ["lastname", "firstname", "middlename", "birthyear"],
                "unmatched_lookup_rows": "Retained without an ingestion error; the join's absence meaning is not inferred here.",
            },
            {
                "source": "office/export-notes.txt — The three joins that matter, rule 3",
                "file": "peer-reference-replies.csv",
                "reply_key": ["application_id", "referee_id"],
                "no_reply": "No reply row remains an absence in the raw ledger; attempt interpretation is deferred.",
            },
        ],
        "blank_cell_handling": {
            "raw_empty_cells": "Preserved as empty strings without coercion.",
            "declared-history.csv.to_date": "An empty source value is defined by the export note as current through this batch's export date; the raw value remains empty.",
            "certification-replies.csv.expiry_date": "An empty source value is defined by the export note as non-expiring; the raw value remains empty.",
        },
        "issues": [],
    }

    actual_csvs = {path.name for path in directory.glob("*.csv") if path.is_file()}
    for missing in sorted(set(CSV_FILES) - actual_csvs):
        issues.append(IngestionIssue("missing_record_file", f"Required CSV not found: {missing}.", missing))
    for unexpected in sorted(actual_csvs - set(CSV_FILES)):
        issues.append(IngestionIssue("unexpected_record_file", f"Unexpected CSV was not parsed: {unexpected}.", unexpected))

    for filename in CSV_FILES:
        path = directory / filename
        if not path.is_file():
            continue
        batch["record_files"].append(filename)
        file_records = _read_csv(path, filename, issues)
        batch["records"].extend(file_records)
        expected = expected_record_counts.get(filename)
        if expected is None:
            issues.append(IngestionIssue("missing_readme_record_count", f"README does not list row count for {filename}.", "README.md"))
        elif expected != len(file_records):
            issues.append(IngestionIssue(
                "record_count_mismatch",
                f"README declares {expected} data rows; CSV contains {len(file_records)}.",
                filename,
            ))

    expected_doc_counts = _readme_counts(readme_text, DOCUMENT_FOLDERS)
    for folder in DOCUMENT_FOLDERS:
        expected = expected_doc_counts.get(folder)
        actual_paths = sorted((directory / folder).glob("*.md")) if (directory / folder).is_dir() else []
        if expected is None:
            issues.append(IngestionIssue("missing_readme_document_count", f"README does not list document count for {folder}/.", "README.md"))
        elif len(actual_paths) != expected:
            issues.append(IngestionIssue(
                "document_count_mismatch",
                f"README declares {expected} documents in {folder}/; found {len(actual_paths)}.",
                "README.md",
            ))

    correspondence = [r for r in batch["records"] if r["filename"] == "correspondence.csv"]
    seen_document_paths: set[str] = set()
    for index_record in correspondence:
        document_path = index_record["values"].get("document_path")
        if not document_path:
            issues.append(_issue("missing_document_reference", "Correspondence row has no document_path.", index_record))
            continue
        relative = Path(document_path)
        resolved = (directory / relative).resolve()
        try:
            resolved.relative_to(directory.resolve())
        except ValueError:
            issues.append(_issue("unsafe_document_reference", f"Document reference escapes the batch directory: {document_path!r}.", index_record))
            continue
        if not resolved.is_file():
            issues.append(_issue("broken_document_reference", f"Indexed document does not exist: {document_path!r}.", index_record))
            continue
        if document_path in seen_document_paths:
            # Keep one content copy and all the source index rows that name it.
            existing_doc = next(d for d in batch["documents"] if d["path"] == document_path)
            existing_doc["indexed_by"].append({
                "filename": index_record["filename"],
                "row_number": index_record["row_number"],
                "stable_key": index_record["stable_key"],
            })
            continue
        seen_document_paths.add(document_path)
        try:
            document_bytes = resolved.read_bytes()
            document_text = document_bytes.decode("utf-8-sig")
        except (OSError, UnicodeError) as exc:
            issues.append(_issue("document_read_error", f"Could not read {document_path!r}: {exc}", index_record))
            continue
        batch["documents"].append({
            "path": document_path,
            "content": document_text,
            "sha256": _sha256(document_bytes),
            "indexed_by": [{
                "filename": index_record["filename"],
                "row_number": index_record["row_number"],
                "stable_key": index_record["stable_key"],
            }],
        })

    _find_integrity_issues(batch, prior_ledger["batches"], issues)
    batch["issues"] = [issue.as_dict() for issue in issues]
    next_ledger = {
        "ledger_version": LEDGER_VERSION,
        "batches": [*prior_ledger["batches"], batch],
    }
    return IngestionResult(next_ledger, issues, True, batch_id)
