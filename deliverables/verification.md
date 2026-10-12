# Independent verification record

**Scope:** official Project E snapshots for batches 1–3, their cumulative evidence-ledger checkpoints, original batch exports, and `snapshot.schema.json`.

**Interpretation of decision results:** “Not admitted” means the evaluator could not independently establish, from the evidence present in these exports, that the recorded decision met the documented admission prerequisites. It does **not** prove that the hospital’s human decision was invalid. In particular, unavailable export fields remain evidence limitations; they are not findings about what hospital personnel did outside the supplied record.

## Verification results

Commands below were run from the repository root. “PASS” means the independent check matched the stated expectation; it is not a certification of source facts outside the supplied files.

| Check | Command / method | Expected | Observed | Result |
|---|---|---|---|---|
| Source record and document counts | Independently count data rows (excluding CSV headers) in each original `inputs/Batch * export */*.csv`; independently count Markdown files in `letters/`, `dispositions/`, and `decisions/`; compare with the corresponding batch entry in each cumulative ledger. | Original export counts equal ledger observations and indexed documents, with no missing or extra source files. | Batch 1: **1,631 records, 15 documents** (9 letters, 0 dispositions, 6 decisions). Batch 2: **214 records, 41 documents** (8 letters, 4 dispositions, 29 decisions). Batch 3: **100 records, 26 documents** (4 letters, 1 disposition, 21 decisions). Counts match the ledger and README file inventories. | PASS |
| Application and revision preservation | Read `applications.csv` observations from the three cumulative ledgers; compare unique `(application_id, revision)` keys and the latest revision with each corresponding snapshot. | Cumulative unique applications/revisions are monotonic; no earlier revision disappears; snapshot contains one current evaluated entry per application at its latest known revision. | Cumulative ledger application rows: **41 / 45 / 46**. Unique applications: **40** at all three checkpoints. Unique application/revision pairs: **41 / 45 / 46**. Every earlier pair is retained at later checkpoints. Each snapshot has 40 application entries and uses the latest available revision. | PASS |
| Snapshot schema and required fields | `python3 scripts/validate_snapshot.py deliverables/snapshots/batch-01.json` (repeat for `batch-02.json` and `batch-03.json`); validator uses the unchanged `snapshot.schema.json`. | Each official snapshot validates and includes all schema-required fields. | All three commands printed `Valid snapshot: ...` and exited 0. Independent schema validation also completed without errors. | PASS |
| Predecessor paths and hashes | Independently hash snapshot file bytes with SHA-256 and compare the digest and path stored in the next snapshot’s `predecessor`. | Batch 1 has no predecessor; batch 2 points to batch 1 and batch 3 points to batch 2; both digests match exact predecessor bytes. | Batch 1 predecessor is `null`. Batch 2 path is `deliverables/snapshots/batch-01.json`, SHA-256 `77dd5dcdcca8257a76c5cb67ac840384902fbea1593044c783644d740ede924d`. Batch 3 path is `deliverables/snapshots/batch-02.json`, SHA-256 `49b1ec31ad32fddb5260e0405c743750e71b34620b57b6b555639b191cc4f248`. Both hashes match independently computed hashes. | PASS |
| Decision count and admission results | Count decisions in each snapshot; deduplicate indexed decision documents across the cumulative ledger; parse the decision records and compare the body, outcome, signatory, and role with `office/authority-roster.txt`. | Snapshot decision IDs match the original decision documents. No unauthorized body/outcome or roster role/signatory is admitted. | Cumulative snapshot decision counts: **6 / 35 / 56**; all are recorded as not admitted. The 56 unique indexed decision documents were all parseable. Independent roster comparison found **one** body/outcome violation: `MEC-2026-036` records `approved` for the Executive Committee, which the roster says may make recommendations but not approvals. The snapshot rejects it with `body-or-outcome-not-authorized`. Signatory and role comparisons found no other discrepancy. | PASS |
| Activation safety | Inspect every application’s `activation` and `approval_decision_id` in each snapshot; compare with each decision’s admission result, application revision, and Governing Body authority. | No activation exists without an admitted approval for the current revision from an authorized Governing Body decision. | **0 activations** in all three snapshots (6, 35, and 56 decisions respectively; 0 admitted). Therefore no activation lacks an admitted current-revision Governing Body approval. | PASS |
| Missing and unassessable evidence in follow-up queues | Inspect `elements`, `action_queue`, and cited source references for every application in each snapshot; spot-check explicit accreditation, reference-delivery-channel, and verification-date limitations against original exports. | Unresolved or unassessable requirements remain visible with follow-up; absent fields are not treated as verified. | All **120** application entries (40 per snapshot) have a nonempty action queue. Each snapshot has explicit missing/unassessable evidence in follow-up items. Spot checks preserve accreditation gaps, the lack of an exported peer-reference delivery channel, and blank verification-reply end dates as unresolved limitations. | PASS |
| Deterministic no-change rerun | Capture SHA-256 and `st_mtime_ns` for all six JSON files in `deliverables/snapshots/`; run `python3 scripts/generate_snapshots.py`; capture both again and compare. | Generator reports no changes; file set, hashes, and modification times remain identical. | Output: `No changes: all snapshots and ledger checkpoints already match the exports.` Exit 0. Six files before and after; all hashes and modification times unchanged. | PASS |

### Snapshot and ledger file digests

These SHA-256 values were independently computed from the files currently present. The three snapshot hashes also serve as the exact predecessor-chain inputs above.

| File | SHA-256 |
|---|---|
| `batch-01.json` | `77dd5dcdcca8257a76c5cb67ac840384902fbea1593044c783644d740ede924d` |
| `batch-02.json` | `49b1ec31ad32fddb5260e0405c743750e71b34620b57b6b555639b191cc4f248` |
| `batch-03.json` | `47df46b5ac05dce6ce8ed11c325baf931d4048ac25e2fd275db9221ecc8d898d` |
| `evidence-ledger-batch-01.json` | `54b4feba9710d17d5ae86f1e1ebb0313c83a6058769bdfd59359634e645c9878` |
| `evidence-ledger-batch-02.json` | `059a920c5a52bb60bbe52dc2b8da07fb317d75539ec85df5208998cf97737996` |
| `evidence-ledger-batch-03.json` | `ec1ad60588f5c0ddedd006ebd7b87e2ca6fa5d66c241a31e6334818d5abadab1` |

## Full automated test suite

Command: `python3 -m unittest discover -s tests -v`

Expected: all automated tests pass.

Observed: **35 tests passed**, 0 failures, 0 errors (`Ran 35 tests in 10.481s`, `OK`).

## Audit harness note

An initial ad hoc follow-up selector produced false alarms because it matched wording that was not used in the action queue and counted cumulative decision records once per checkpoint. The selector was corrected to match the actual queue language and to deduplicate source decision documents. The corrected checks above passed. This was a verification-script query issue, not a change to or correction of any source, ledger, snapshot, schema, or evaluation rule.

No snapshot, evidence ledger, source export, schema, or evaluation rule was changed during this verification. The only file created for this step is this report.
