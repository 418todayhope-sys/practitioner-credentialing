# Project E practitioner credentialing

This repository contains a reusable Agent Skill and Python workflow for processing closed medical staff office exports for **initial practitioner appointments**. It preserves source evidence and application revisions, evaluates six verification elements, assesses packet readiness and recorded decisions, and produces schema-valid, hash-chained snapshots. It does not make clinical judgments or create human decisions.

## Repository map

| Path | Contents |
|---|---|
| `SKILL.md` | Operator instructions for running the reusable skill. |
| `credentialing/` | Evidence ingestion, six-element evaluation, readiness, decision admission, and activation code. |
| `scripts/generate_snapshots.py` | Sequential three-batch snapshot generator. |
| `scripts/validate_snapshot.py` | Validator for one snapshot against `snapshot.schema.json`. |
| `snapshot.schema.json` | Required snapshot contract; treat as authoritative and unchanged. |
| `requirements.txt` | Python dependency declaration (`jsonschema`). |
| `office/` | Seven official hospital reference documents in `.txt` format. |
| `inputs/` | Three chronological batch exports, each with a README, CSVs, and indexed documents. |
| `interviews/` | Completed stakeholder interview transcript: [`project-e-practitioner-credentialing-20261012-1308.md`](interviews/project-e-practitioner-credentialing-20261012-1308.md). |
| `deliverables/rules.md` | Policy register with exact official document and section citations; separates written policy from implementation choices. |
| `deliverables/snapshots/` | Three official snapshots and three cumulative evidence-ledger checkpoints. |
| `deliverables/verification.md` | Independent checks of official outputs, their source exports, schema, hashes, and rerun behavior. |
| `deliverables/run-log.md` | Record of the actual three-batch execution and its results. |
| `tests/` | Automated ingestion, evaluation, readiness, and snapshot-generator tests. |

The interview provides operational context. The written hospital documents govern credentialing rules; see `deliverables/rules.md` for how conflicts and limitations are handled.

## Prerequisites and setup

Use Python 3.10 or newer. From the repository root, create and activate a virtual environment and install the declared dependency:

```sh
python3 -m venv .venv
. .venv/bin/activate
python3 -m pip install -r requirements.txt
```

The dependency is `jsonschema>=4.18,<5`.

## Run and validate

The generator discovers the three `Batch N` directories in `inputs/`, sorts them chronologically by batch number, reads each batch README and source files, and processes each at its stated export date. From the repository root, run:

```sh
python3 scripts/generate_snapshots.py
```

For a fresh output directory, it creates these six files under `deliverables/snapshots/`:

- `batch-01.json`, `batch-02.json`, `batch-03.json`
- `evidence-ledger-batch-01.json`, `evidence-ledger-batch-02.json`, `evidence-ledger-batch-03.json`

For the already generated official files in this repository, an unchanged rerun prints `No changes: all snapshots and ledger checkpoints already match the exports.` It will not silently overwrite a differing snapshot; see the correction procedure in [SKILL.md](SKILL.md).

Validate each official snapshot against `snapshot.schema.json`:

```sh
python3 scripts/validate_snapshot.py deliverables/snapshots/batch-01.json
python3 scripts/validate_snapshot.py deliverables/snapshots/batch-02.json
python3 scripts/validate_snapshot.py deliverables/snapshots/batch-03.json
```

Success prints `Valid snapshot: <path>` for each file. A validation failure prints an error and returns a nonzero exit status. Run the automated test suite with:

```sh
python3 -m unittest discover -s tests -v
```

The generator also supports `--batches-dir`, `--output-dir`, `--correction-id`, and `--correction-note`; confirm their exact behavior with `python3 scripts/generate_snapshots.py --help`. Both correction flags are required together. A corrected chain is retained separately under `deliverables/snapshots/corrections/<correction-id>/`.

## Project and assignment references

- [Full Project E assignment instructions](https://docs.google.com/document/d/1HhmU8Jay09XHDci38hl9ZOX_dMryaSv4aFLCPu1Nk-E/edit)
- [Starter repository](https://github.com/GitRollTraining/practitioner-credentialing)

## Review the work

Start with [SKILL.md](SKILL.md) for the operator workflow. Use [deliverables/rules.md](deliverables/rules.md) for policy citations, [the stakeholder interview](interviews/project-e-practitioner-credentialing-20261012-1308.md) for operational context, and [deliverables/verification.md](deliverables/verification.md) for independent output checks. The [execution record](deliverables/run-log.md) summarizes the commands and results for the official three-batch run.
