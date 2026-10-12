import json
import shutil
import tempfile
import unittest
from hashlib import sha256
from pathlib import Path

from jsonschema import Draft202012Validator, FormatChecker

from scripts.generate_snapshots import ROOT, generate_snapshots


def source_batches(base=ROOT / "inputs"):
    return sorted((p for p in base.iterdir() if p.is_dir() and p.name.startswith("Batch ")), key=lambda p: int(p.name.split()[1]))


class SnapshotGeneratorTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix=".snapshot-generator-test-", dir=ROOT)
        self.work = Path(self.temp.name)

    def tearDown(self):
        self.temp.cleanup()

    def test_schema_chain_rerun_and_revision_history(self):
        output = self.work / "snapshots"
        created = generate_snapshots(source_batches(), output)
        snapshots = sorted(output.glob("batch-*.json"))
        self.assertEqual(len(snapshots), 3)
        self.assertEqual(len([p for p in created if p.name.startswith("batch-")]), 3)

        schema = json.loads((ROOT / "snapshot.schema.json").read_text(encoding="utf-8"))
        validator = Draft202012Validator(schema, format_checker=FormatChecker())
        contents = [p.read_bytes() for p in snapshots]
        decoded = [json.loads(data) for data in contents]
        for snapshot in decoded:
            validator.validate(snapshot)
        self.assertIsNone(decoded[0]["predecessor"])
        for index in (1, 2):
            predecessor = decoded[index]["predecessor"]
            self.assertEqual(predecessor["path"], snapshots[index - 1].relative_to(ROOT).as_posix())
            self.assertEqual(predecessor["sha256"], sha256(contents[index - 1]).hexdigest())

        app1 = next(a for a in decoded[0]["applications"] if a["application_id"] == "APP-2026-036")
        app2 = next(a for a in decoded[1]["applications"] if a["application_id"] == "APP-2026-036")
        self.assertEqual(app1["revision"], 1)
        self.assertEqual(app2["revision"], 2)
        ledger2 = json.loads((output / "evidence-ledger-batch-02.json").read_text(encoding="utf-8"))
        app_revisions = {
            r["values"]["revision"] for b in ledger2["batches"] for r in b["records"]
            if r["filename"] == "applications.csv" and r["values"].get("application_id") == "APP-2026-036"
        }
        self.assertEqual(app_revisions, {"1", "2"})

        mtimes = {p: p.stat().st_mtime_ns for p in output.rglob("*") if p.is_file()}
        self.assertEqual(generate_snapshots(source_batches(), output), [])
        self.assertEqual(mtimes, {p: p.stat().st_mtime_ns for p in output.rglob("*") if p.is_file()})

        for snapshot in decoded:
            for app in snapshot["applications"]:
                admitted = {d["decision_id"] for d in app["decisions"] if d["admitted"]}
                if app["approval_decision_id"] is None:
                    self.assertIsNone(app["activation"])
                else:
                    self.assertIn(app["approval_decision_id"], admitted)

    def test_changed_batch_creates_separate_corrected_chain_and_keeps_originals(self):
        copied_inputs = self.work / "inputs"
        shutil.copytree(ROOT / "inputs", copied_inputs)
        batches = source_batches(copied_inputs)
        output = self.work / "snapshots"
        originals = generate_snapshots(batches, output)
        original_bytes = {p: p.read_bytes() for p in output.rglob("batch-*.json")}

        readme = batches[0] / "README.md"
        readme.write_text(readme.read_text(encoding="utf-8") + "\nCorrection note for test fixture.\n", encoding="utf-8")
        with self.assertRaises(FileExistsError):
            generate_snapshots(batches, output)

        corrected = generate_snapshots(
            batches, output, correction_id="fixture-correction-1", correction_note="Test corrected source digest handling."
        )
        corrected_snapshots = sorted((output / "corrections" / "fixture-correction-1").glob("batch-*.json"))
        self.assertEqual(len(corrected_snapshots), 3)
        self.assertTrue(all(path.read_bytes() == data for path, data in original_bytes.items()))
        self.assertTrue(all("fixture-correction-1" in json.loads(p.read_text(encoding="utf-8"))["snapshot_id"] for p in corrected_snapshots))
        manifest = json.loads((output / "corrections" / "fixture-correction-1" / "correction.json").read_text(encoding="utf-8"))
        self.assertEqual(manifest["reason"], "Test corrected source digest handling.")
        corrected_data = [p.read_bytes() for p in corrected_snapshots]
        corrected_json = [json.loads(b) for b in corrected_data]
        for i in (1, 2):
            predecessor = corrected_json[i]["predecessor"]
            self.assertEqual(predecessor["path"], corrected_snapshots[i - 1].relative_to(ROOT).as_posix())
            self.assertEqual(predecessor["sha256"], sha256(corrected_data[i - 1]).hexdigest())
        self.assertEqual(generate_snapshots(
            batches, output, correction_id="fixture-correction-1", correction_note="Test corrected source digest handling."
        ), [])


if __name__ == "__main__":
    unittest.main()
