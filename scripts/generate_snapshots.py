#!/usr/bin/env python3
"""Generate validated, append-only Project E snapshots for closed batches."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
import tempfile
import os
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator, FormatChecker

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from credentialing.ingestion import empty_ledger, ingest_batch
from credentialing.readiness import process_recorded_decisions


def _json_bytes(value: Any) -> bytes:
    return (json.dumps(value, ensure_ascii=False, indent=2, sort_keys=False) + "\n").encode("utf-8")


def _relative(path: Path, root: Path) -> str:
    try:
        return path.resolve().relative_to(root.resolve()).as_posix()
    except ValueError as exc:
        raise ValueError(f"Output path must be inside repository root to keep snapshot links repository-relative: {path}") from exc


def _source_label(ref: dict[str, Any]) -> str:
    batch = ref.get("batch_id", "unknown-batch")
    if ref.get("filename"):
        location = str(ref["filename"])
        if ref.get("row_number") is not None:
            location += f":{ref['row_number']}"
    else:
        location = str(ref.get("document_path", "source document"))
    return f"{batch}/{location}"


def _application_entries(ledger: dict[str, Any], as_of: str) -> list[dict[str, Any]]:
    revisions: dict[str, list[dict[str, Any]]] = {}
    for batch in ledger["batches"]:
        if batch["export_date"] > as_of:
            continue
        for record in batch["records"]:
            if record["filename"] != "applications.csv":
                continue
            values = record["values"]
            if values.get("application_id") and values.get("revision"):
                revisions.setdefault(str(values["application_id"]), []).append(values)

    entries = []
    for application_id in sorted(revisions):
        app_rows = revisions[application_id]
        latest_by_revision: dict[int, dict[str, Any]] = {}
        for values in app_rows:
            try:
                number = int(values["revision"])
            except (KeyError, ValueError):
                continue
            latest_by_revision[number] = values
        if not latest_by_revision:
            continue
        revision = max(latest_by_revision)
        result = process_recorded_decisions(ledger, application_id, revision, as_of)
        fragment = result["schema_compatible"]
        readiness = result["readiness"]
        actions = list(fragment["action_queue"])
        for blocker in readiness.get("blockers", []):
            refs = blocker.get("evidence", [])
            suffix = "" if not refs else " Evidence: " + ", ".join(_source_label(ref) for ref in refs) + "."
            if not refs:
                suffix = " Evidence source is not identifiable in this export."
            actions.append({
                "item": f"{blocker.get('element', 'packet')} — {blocker.get('message', blocker.get('code', 'unresolved'))}.{suffix}",
                "owner": "Medical Staff Office",
                "due": None,
            })
        for detail in result["decision_details"]:
            if detail["admitted"]:
                continue
            source = detail.get("source", {})
            actions.append({
                "item": (f"Record decision {detail['decision_id']} against revision {detail.get('revision')} was not admitted: "
                         f"{detail.get('admission_reason')}. Source: {_source_label(source)}."),
                "owner": "Medical Services Professional",
                "due": None,
            })
        for limitation in result.get("limitations", []):
            actions.append({
                "item": f"Unresolved export limitation: {limitation}",
                "owner": "Medical Services Professional",
                "due": None,
            })

        # Stable de-duplication keeps repeated blockers from producing noisy queues.
        unique_actions = []
        seen = set()
        for action in actions:
            marker = (action["item"], action["owner"], action["due"])
            if marker not in seen:
                seen.add(marker)
                unique_actions.append(action)
        entries.append({
            "application_id": application_id,
            "revision": revision,
            "status": fragment["status"],
            "elements": fragment["elements"],
            "packet_presentable": fragment["packet_presentable"],
            "decisions": fragment["decisions"],
            "approval_decision_id": fragment["approval_decision_id"],
            "activation": fragment["activation"],
            "monitored_conditions": fragment["monitored_conditions"],
            "action_queue": unique_actions,
        })
    return entries


def _validate(snapshot: dict[str, Any], schema: dict[str, Any]) -> None:
    validator = Draft202012Validator(schema, format_checker=FormatChecker())
    errors = sorted(validator.iter_errors(snapshot), key=lambda e: list(map(str, e.absolute_path)))
    if errors:
        descriptions = []
        for error in errors:
            location = ".".join(str(part) for part in error.absolute_path) or "$"
            descriptions.append(f"{location}: {error.message}")
        raise ValueError("Generated snapshot failed schema validation:\n  " + "\n  ".join(descriptions))


def _atomic_create(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temp_name = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        os.link(temp_name, path)
    except FileExistsError:
        raise
    finally:
        try:
            os.unlink(temp_name)
        except OSError:
            pass


def generate_snapshots(
    batch_dirs: list[Path], output_dir: Path, *, repo_root: Path = ROOT,
    correction_id: str | None = None, correction_note: str | None = None,
) -> list[Path]:
    """Ingest batches sequentially and create immutable, schema-valid snapshots.

    Existing byte-identical output is a no-change rerun. Conflicting output is
    never overwritten; callers must choose a correction ID and explanation,
    which writes a separate retained chain under ``corrections/<id>/``.
    """
    if bool(correction_id) != bool(correction_note):
        raise ValueError("A correction requires both --correction-id and --correction-note.")
    if correction_id and not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]*", correction_id):
        raise ValueError("Correction IDs may contain only letters, numbers, dots, underscores, and hyphens.")
    schema_path = repo_root / "snapshot.schema.json"
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    ordered_dirs = sorted(batch_dirs, key=lambda p: int(re.search(r"Batch\s+(\d+)", p.name).group(1)))
    if not ordered_dirs:
        raise ValueError("No batch export directories were provided.")

    target_dir = output_dir / "corrections" / correction_id if correction_id else output_dir
    suffix = f"-correction-{correction_id}" if correction_id else ""
    manifest_path = target_dir / "correction.json" if correction_id else None
    ledger = empty_ledger()
    artifacts: list[tuple[Path, bytes]] = []
    previous_snapshot: tuple[Path, bytes] | None = None
    correction_manifest: dict[str, Any] | None = None

    for batch_number, batch_dir in enumerate(ordered_dirs, start=1):
        ingested = ingest_batch(batch_dir, ledger)
        if ingested.issues:
            issue_text = "; ".join(f"{i.code} [{i.filename}:{i.row_number}]: {i.message}" for i in ingested.issues)
            raise ValueError(f"Batch integrity issues prevent snapshot generation: {issue_text}")
        ledger = ingested.ledger
        batch = ledger["batches"][-1]
        # Keep checkpoint bytes stable across clones and invocation locations.
        batch["source_directory"] = _relative(batch_dir, repo_root)
        if batch["batch_number"] != batch_number:
            raise ValueError(f"Expected Batch {batch_number}, found {batch['batch_number']} in {batch_dir}.")
        as_of = batch["export_date"]

        ledger_path = target_dir / f"evidence-ledger-batch-{batch_number:02d}.json"
        ledger_rel = _relative(ledger_path, repo_root)
        ledger_data = _json_bytes(ledger)
        snapshot_path = target_dir / f"batch-{batch_number:02d}.json"
        snapshot_rel = _relative(snapshot_path, repo_root)
        produced = [ledger_rel, snapshot_rel]
        if manifest_path:
            produced.append(_relative(manifest_path, repo_root))
        predecessor = None
        if previous_snapshot:
            predecessor = {
                "path": _relative(previous_snapshot[0], repo_root),
                "sha256": hashlib.sha256(previous_snapshot[1]).hexdigest(),
            }
        snapshot = {
            "schema_version": "credentialing-snapshot/1",
            "snapshot_id": f"project-e-batch-{batch_number:02d}-{as_of.replace('-', '')}-{batch['source_digest'][:12]}{suffix}",
            "predecessor": predecessor,
            "batch": batch_number,
            "as_of": as_of,
            "consumed": {
                "record_files": sorted(batch["record_files"]),
                "documents": sorted(doc["path"] for doc in batch["documents"]),
            },
            "produced": produced,
            "rules_file": "deliverables/rules.md",
            "applications": _application_entries(ledger, as_of),
        }
        _validate(snapshot, schema)
        snapshot_data = _json_bytes(snapshot)
        artifacts.extend([(ledger_path, ledger_data), (snapshot_path, snapshot_data)])
        previous_snapshot = (snapshot_path, snapshot_data)

    if correction_id:
        correction_manifest = {
            "correction_id": correction_id,
            "reason": correction_note,
            "preserves_originals": True,
            "corrected_chain": [_relative(path, repo_root) for path, data in artifacts if re.fullmatch(r"batch-\d{2}\.json", path.name)],
        }
        manifest_data = _json_bytes(correction_manifest)
        artifacts.append((manifest_path, manifest_data))

    # Preflight all destinations before creating any of the requested files.
    for path, data in artifacts:
        if path.exists():
            if path.read_bytes() != data:
                if not correction_id:
                    raise FileExistsError(
                        f"Refusing to overwrite changed output {path}; supply --correction-id and --correction-note."
                    )
                raise FileExistsError(f"Correction output already exists with different content: {path}")
    created = []
    for path, data in artifacts:
        if not path.exists():
            _atomic_create(path, data)
            created.append(path)
    return created


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Generate and validate append-only snapshots for sequential Project E exports.")
    parser.add_argument("--batches-dir", type=Path, default=ROOT / "inputs", help="directory containing the three Batch N export folders")
    parser.add_argument("--output-dir", type=Path, default=ROOT / "deliverables" / "snapshots", help="snapshot output directory inside the repository")
    parser.add_argument("--correction-id", help="distinct identifier for a separately retained correction chain")
    parser.add_argument("--correction-note", help="why this corrected chain differs from the original")
    args = parser.parse_args(argv)
    try:
        batch_dirs = [p for p in args.batches_dir.iterdir() if p.is_dir() and re.search(r"Batch\s+\d+", p.name)]
        created = generate_snapshots(batch_dirs, args.output_dir, correction_id=args.correction_id, correction_note=args.correction_note)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"Snapshot generation failed: {exc}", file=sys.stderr)
        return 1
    if created:
        for path in created:
            print(f"Created: {_relative(path, ROOT)}")
    else:
        print("No changes: all snapshots and ledger checkpoints already match the exports.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
