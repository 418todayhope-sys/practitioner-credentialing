import csv
import tempfile
import unittest
from pathlib import Path

from credentialing.ingestion import CSV_FILES, empty_ledger, ingest_batch


HEADERS = {
    "applications.csv": ["application_id", "revision", "applicant_id", "last_name", "first_name", "middle_name", "birth_year"],
    "application-disclosures.csv": ["application_id", "revision", "question_code"],
    "declared-history.csv": ["application_id", "revision", "entry_id", "to_date"],
    "declared-credentials.csv": ["application_id", "revision", "declaration_id"],
    "privilege-requests.csv": ["application_id", "revision", "request_id"],
    "licence-lookup-wa.csv": ["lastname", "firstname", "middlename", "birthyear", "credentialnumber", "lookup_date"],
    "licence-lookup-other-states.csv": ["board_state", "licence_number", "lookup_date"],
    "certification-replies.csv": ["reply_id", "application_id", "declaration_id", "expiry_date"],
    "verification-replies.csv": ["reply_id", "application_id", "entry_id"],
    "verification-attempts.csv": ["attempt_id", "application_id"],
    "peer-referees.csv": ["referee_id", "application_id", "revision"],
    "peer-reference-replies.csv": ["reply_id", "application_id", "referee_id"],
    "correspondence.csv": ["letter_id", "application_id", "document_path"],
}


def make_batch(root: Path, number: int, export_date: str, rows: dict[str, list[dict]] | None = None, docs: dict[str, str] | None = None) -> Path:
    rows = rows or {}
    docs = docs or {}
    directory = root / f"Batch {number} export — {export_date}"
    directory.mkdir(parents=True)
    for folder in ("letters", "dispositions", "decisions"):
        (directory / folder).mkdir()
    for path, content in docs.items():
        target = directory / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")

    for filename in CSV_FILES:
        with (directory / filename).open("w", encoding="utf-8", newline="") as stream:
            writer = csv.DictWriter(stream, fieldnames=HEADERS[filename])
            writer.writeheader()
            writer.writerows(rows.get(filename, []))

    folder_counts = {folder: len(list((directory / folder).glob("*.md"))) for folder in ("letters", "dispositions", "decisions")}
    readme = [
        f"# Batch {number} export — test hospital",
        f"**Export date: {export_date}**",
        "**Window covered: fixture window**",
        "",
        "## What is here",
        "| File | Rows |",
        "|---|---|",
    ]
    readme.extend(f"| `{name}` | {len(rows.get(name, []))} |" for name in CSV_FILES)
    readme.extend(["", "| Folder | Documents |", "|---|---|"])
    readme.extend(f"| `{folder}/` | {count} |" for folder, count in folder_counts.items())
    (directory / "README.md").write_text("\n".join(readme) + "\n", encoding="utf-8")
    return directory


class IngestionTests(unittest.TestCase):
    def test_preserves_provenance_raw_blanks_and_indexed_document(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            batch = make_batch(
                root,
                1,
                "2026-03-16",
                rows={
                    "applications.csv": [{
                        "application_id": "APP-TEST-1", "revision": "1", "applicant_id": "LP-1",
                        "last_name": "Ng", "first_name": "Ari", "middle_name": "", "birth_year": "1980",
                    }],
                    "licence-lookup-wa.csv": [{
                        "lastname": "Ng", "firstname": "Ari", "middlename": "", "birthyear": "1980",
                        "credentialnumber": "WA-1", "lookup_date": "2026-03-15",
                    }],
                    "declared-history.csv": [{
                        "application_id": "APP-TEST-1", "revision": "1", "entry_id": "ENT-1", "to_date": "",
                    }],
                    "correspondence.csv": [{
                        "letter_id": "LTR-1", "application_id": "APP-TEST-1", "document_path": "letters/note.md",
                    }],
                },
                docs={"letters/note.md": "Source note text\n"},
            )

            result = ingest_batch(batch)
            self.assertEqual([], result.issues)
            ingested = result.ledger["batches"][0]
            self.assertEqual(13, len(ingested["record_files"]))
            history = next(record for record in ingested["records"] if record["filename"] == "declared-history.csv")
            self.assertEqual(2, history["row_number"])
            self.assertEqual("", history["values"]["to_date"])
            self.assertEqual("ENT-1", history["values"]["entry_id"])
            lookup = next(record for record in ingested["records"] if record["filename"] == "licence-lookup-wa.csv")
            self.assertIsNotNone(lookup["stable_key"])
            self.assertEqual("", lookup["values"]["middlename"])
            self.assertIn("current through this batch's export date", ingested["blank_cell_handling"]["declared-history.csv.to_date"])
            self.assertEqual("Source note text\n", ingested["documents"][0]["content"])
            self.assertEqual("letters/note.md", ingested["documents"][0]["path"])
            self.assertEqual(64, len(ingested["documents"][0]["sha256"]))
            self.assertNotIn("status", ingested["records"][0]["values"])

    def test_reports_missing_record_file_and_broken_correspondence_reference(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            batch = make_batch(
                root,
                1,
                "2026-03-16",
                rows={"correspondence.csv": [{
                    "letter_id": "LTR-1", "application_id": "APP-TEST-1", "document_path": "letters/missing.md",
                }]},
            )
            (batch / "certification-replies.csv").unlink()
            # Keep the README count accurate for the deliberate missing file.
            readme = (batch / "README.md").read_text(encoding="utf-8")
            readme = readme.replace("| `certification-replies.csv` | 0 |\n", "")
            (batch / "README.md").write_text(readme, encoding="utf-8")

            result = ingest_batch(batch)
            codes = {issue.code for issue in result.issues}
            self.assertIn("missing_record_file", codes)
            self.assertIn("broken_document_reference", codes)
            self.assertIn("unknown_application_id", codes)
            self.assertEqual(1, len(result.ledger["batches"]))

    def test_incremental_merge_is_append_only_and_reingestion_is_idempotent(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            first = make_batch(root, 1, "2026-03-16", rows={
                "applications.csv": [{
                    "application_id": "APP-TEST-1", "revision": "1", "applicant_id": "LP-1",
                    "last_name": "Ng", "first_name": "Ari", "middle_name": "", "birth_year": "1980",
                }],
            })
            second = make_batch(root, 2, "2026-04-20", rows={
                "verification-attempts.csv": [{"attempt_id": "ATT-1", "application_id": "APP-TEST-1"}],
            })
            first_result = ingest_batch(first)
            second_result = ingest_batch(second, first_result.ledger)

            self.assertTrue(second_result.changed)
            self.assertEqual(["batch-01-2026-03-16", "batch-02-2026-04-20"], [b["batch_id"] for b in second_result.ledger["batches"]])
            application = next(r for r in second_result.ledger["batches"][0]["records"] if r["filename"] == "applications.csv")
            self.assertEqual("LP-1", application["values"]["applicant_id"])
            replay = ingest_batch(second, second_result.ledger)
            self.assertFalse(replay.changed)
            self.assertEqual(2, len(replay.ledger["batches"]))

    def test_reports_duplicate_source_rows_and_unknown_revision(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            app = {
                "application_id": "APP-TEST-1", "revision": "1", "applicant_id": "LP-1",
                "last_name": "Ng", "first_name": "Ari", "middle_name": "", "birth_year": "1980",
            }
            batch = make_batch(root, 1, "2026-03-16", rows={
                "applications.csv": [app, dict(app), {**app, "applicant_id": "LP-2"}],
                "declared-history.csv": [{"application_id": "APP-TEST-1", "revision": "9", "entry_id": "ENT-9", "to_date": ""}],
            })
            result = ingest_batch(batch, empty_ledger())
            codes = {issue.code for issue in result.issues}
            self.assertIn("duplicate_source_record", codes)
            self.assertIn("identifier_reused_with_different_values", codes)
            self.assertIn("application_person_identifier_conflict", codes)
            self.assertIn("unknown_application_revision", codes)
            stored_apps = [r for r in result.ledger["batches"][0]["records"] if r["filename"] == "applications.csv"]
            self.assertEqual(3, len(stored_apps))

    def test_changed_closed_batch_is_reported_without_replacing_retained_observations(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            batch = make_batch(root, 1, "2026-03-16")
            original = ingest_batch(batch)
            original_digest = original.ledger["batches"][0]["source_digest"]
            (batch / "README.md").write_text(
                (batch / "README.md").read_text(encoding="utf-8") + "\nChanged after sealing.\n",
                encoding="utf-8",
            )

            replay = ingest_batch(batch, original.ledger)
            self.assertFalse(replay.changed)
            self.assertIn("immutable_batch_changed", {issue.code for issue in replay.issues})
            self.assertEqual(original_digest, replay.ledger["batches"][0]["source_digest"])
            self.assertEqual(1, len(replay.ledger["batches"]))


if __name__ == "__main__":
    unittest.main()
