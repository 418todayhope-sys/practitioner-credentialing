# Three-batch execution record

This records the official run of `scripts/generate_snapshots.py` against the original exports. Batch calculations used each export's own date. The execution date and wall-clock time were not captured in the recorded run, so this log does not assign one.

## Inputs and independent source counts

Command used to generate the official outputs:

```sh
python3 scripts/generate_snapshots.py
```

The generator processed the numbered batch directories in chronological order:

| Batch | Input directory | Export date | CSV records | Indexed documents |
|---|---|---:|---:|---:|
| 1 | `inputs/Batch 1 export — 2026-03-16/` | 2026-03-16 | 1,631 | 15 (9 letters, 0 dispositions, 6 decisions) |
| 2 | `inputs/Batch 2 export — 2026-04-20/` | 2026-04-20 | 214 | 41 (8 letters, 4 dispositions, 29 decisions) |
| 3 | `inputs/Batch 3 export — 2026-05-18/` | 2026-05-18 | 100 | 26 (4 letters, 1 disposition, 21 decisions) |

Record totals count CSV data rows, excluding header rows. Document totals count source Markdown files in the letters, dispositions, and decisions folders. These totals were independently compared with the batch READMEs and cumulative ledgers; all matched, with zero reported integrity issues.

## Generated files and application totals

The official output directory contains:

- `deliverables/snapshots/batch-01.json`
- `deliverables/snapshots/batch-02.json`
- `deliverables/snapshots/batch-03.json`
- `deliverables/snapshots/evidence-ledger-batch-01.json`
- `deliverables/snapshots/evidence-ledger-batch-02.json`
- `deliverables/snapshots/evidence-ledger-batch-03.json`

Each ledger is cumulative through its named batch. The cumulative ledgers retain **40 applications** and **41 / 45 / 46 unique application-revision pairs** at checkpoints 1 / 2 / 3. Each corresponding snapshot has 40 application entries using the latest revision available as of its batch date.

| Snapshot as of | Final snapshot status counts | Recorded decisions | Admitted | Activations |
|---|---|---:|---:|---:|
| 2026-03-16 | 6 decision-inadmissible; 34 in-verification | 6 | 0 | 0 |
| 2026-04-20 | 25 decision-inadmissible; 13 in-verification; 1 withdrawn; 1 discontinued | 35 | 0 | 0 |
| 2026-05-18 | 27 decision-inadmissible; 11 in-verification; 1 withdrawn; 1 discontinued | 56 | 0 | 0 |

Decision counts are cumulative and therefore include earlier recorded decisions. In the final snapshot, 55 decisions were not admitted because the evaluator could not establish packet presentability from the supplied record; one (`MEC-2026-036`) was refused because the Executive Committee recorded an approval, an outcome reserved to the Governing Body. All 56 are **unadmitted under the evidence-based evaluator**. This does **not** establish that the hospital's recorded human decisions were invalid. Zero activations were produced because no approval was admitted; no privilege activation was inferred.

## Schema and predecessor checks

Each validation command exited successfully and printed `Valid snapshot: ...`:

```sh
python3 scripts/validate_snapshot.py deliverables/snapshots/batch-01.json
python3 scripts/validate_snapshot.py deliverables/snapshots/batch-02.json
python3 scripts/validate_snapshot.py deliverables/snapshots/batch-03.json
```

The unchanged `snapshot.schema.json` therefore accepted all three files. Independent SHA-256 recomputation over the predecessor files matched the paths and digests stored in snapshots 2 and 3:

| Snapshot | Expected predecessor path | Stored and independently computed predecessor SHA-256 | Result |
|---|---|---|---|
| Batch 1 | none | none | PASS |
| Batch 2 | `deliverables/snapshots/batch-01.json` | `77dd5dcdcca8257a76c5cb67ac840384902fbea1593044c783644d740ede924d` | PASS |
| Batch 3 | `deliverables/snapshots/batch-02.json` | `49b1ec31ad32fddb5260e0405c743750e71b34620b57b6b555639b191cc4f248` | PASS |

The current snapshot hashes, independently recomputed from file bytes, are:

| Snapshot | SHA-256 |
|---|---|
| `batch-01.json` | `77dd5dcdcca8257a76c5cb67ac840384902fbea1593044c783644d740ede924d` |
| `batch-02.json` | `49b1ec31ad32fddb5260e0405c743750e71b34620b57b6b555639b191cc4f248` |
| `batch-03.json` | `47df46b5ac05dce6ce8ed11c325baf931d4048ac25e2fd275db9221ecc8d898d` |

## No-change rerun and tests

The generator was run unchanged after the official files existed:

```sh
python3 scripts/generate_snapshots.py
```

Observed output: `No changes: all snapshots and ledger checkpoints already match the exports.` Exit status was 0. A before/after comparison found the same six files with identical SHA-256 hashes and modification times.

The full automated test suite was run with:

```sh
python3 -m unittest discover -s tests -v
```

Result: **35 tests passed**, 0 failures, 0 errors (`Ran 35 tests in 9.989s`, `OK`).

## Evidence limitations

Missing or unassessable evidence remains unresolved in application action queues. The supplied exports lack structured accreditation proof for some education/training entries and do not expose the peer-reference delivery channel; some verification-reply end dates are blank. These are not treated as positive proof. The logs and snapshots do not invent missing evidence or human dispositions. For per-check detail and independent audit method, see [`verification.md`](verification.md).
