---
name: project-e-initial-credentialing
description: Process Project E initial practitioner appointment exports into traceable, schema-valid snapshots while leaving reserved decisions to authorized hospital personnel.
---

# Project E initial credentialing

## Purpose and boundaries

Use this skill to process **initial practitioner appointments only**, from the supplied closed exports through evidence review, recorded-decision admission, and any supported privilege activation. Reappointment, temporary or emergency privileges, and other appointment types are outside scope.

The software organizes evidence and applies the written criteria. It does not make clinical judgments or create hospital decisions. See [deliverables/rules.md](deliverables/rules.md) for the detailed policy register, exact document citations, and implementation choices.

## Required inputs

The repository must contain the seven official documents in `office/`:

- `procedure-extract.txt`
- `privilege-criteria.txt`
- `attester-table.txt`
- `authority-roster.txt`
- `application-form.txt`
- `peer-reference-form.txt`
- `export-notes.txt`

It must also contain the three original chronological export directories under `inputs/`:

- `Batch 1 export — 2026-03-16/`
- `Batch 2 export — 2026-04-20/`
- `Batch 3 export — 2026-05-18/`

Each export includes its README, CSV files, and any correspondence-indexed letters, dispositions, and decisions. Read the README and export notes; the README states the batch's export date and coverage. Do not edit closed exports.

## Environment setup

Use Python 3.10 or newer and install the repository dependency:

```sh
python3 -m venv .venv
. .venv/bin/activate
python3 -m pip install -r requirements.txt
```

`requirements.txt` specifies `jsonschema>=4.18,<5`. Run commands from the repository root.

## Run the workflow

Generate the three snapshots and their cumulative evidence-ledger checkpoints in the default location, `deliverables/snapshots/`:

```sh
python3 scripts/generate_snapshots.py
```

The generator discovers `Batch N` directories in `inputs/`, orders them by batch number, ingests them sequentially, and uses each batch's own export date. It refuses integrity issues and will not overwrite a differing existing output. An identical rerun reports that there are no changes and leaves files untouched.

Validate each snapshot against the repository's unchanged `snapshot.schema.json`:

```sh
python3 scripts/validate_snapshot.py deliverables/snapshots/batch-01.json
python3 scripts/validate_snapshot.py deliverables/snapshots/batch-02.json
python3 scripts/validate_snapshot.py deliverables/snapshots/batch-03.json
```

Each successful validation prints `Valid snapshot: ...`; a validation error exits nonzero.

## Processing and decision boundaries

1. **Ingest evidence.** Read each batch README, all CSV files, and the documents referenced through correspondence. The companion ledger retains original observations, source batch, file, row or stable key, and indexed documents. Later batches append observations and revisions; they do not erase earlier evidence.
2. **Evaluate verification.** Evaluate licensure, experience, time gaps, education, certification, and references against the accepted-source rules, the application revision, and the batch export date. Results retain evidence references. Do not turn an applicant-carried item or an unlisted source into verification.
3. **Assess readiness and recorded decisions.** The evaluator checks packet readiness and recorded decisions against prerequisites, revision, date, authority roster, and sequence. It records whether each provided decision can be admitted. It never invents, repairs, or substitutes a human decision.
4. **Activate only when supported.** Activation requires an admitted, current-revision Governing Body approval and applicable effective-date conditions. An unadmitted approval never activates privileges. Clinical findings and committee decisions stay with authorized humans.
5. **Write and chain snapshots.** Each batch snapshot contains the current application state as of that batch's date. Its predecessor stores the prior snapshot's repository-relative path and SHA-256 hash. The cumulative ledger checkpoint preserves the underlying evidence history.

## Missing evidence, dispositions, and follow-up

Blank fields follow the meanings in `office/export-notes.txt`; do not infer a positive verification from an absent value. Preserve missing or unassessable conditions as unresolved and retain actionable items in each application's `action_queue`. In particular, the exports do not establish some accreditation and peer-reference return-channel facts; these remain limitations with follow-up, not verified facts.

Preserve adverse findings and discrepancies. Only a disposition recorded by a person authorized for that finding can clear a hold when policy permits. A valid disposition does not erase the historical finding. Packet readiness considers unresolved work, discrepancies, and findings without required dispositions; a cleared historical finding is not automatically a permanent blocker.

Some export conditions cannot be assessed from the supplied fields. Keep those conditions explicitly unresolved. Do not relax a written requirement to admit a recorded decision. An unadmitted decision means the supplied record does not independently establish admissibility; it is **not proof that the hospital's human decision was invalid**.

## Reruns and genuine corrections

To check a no-change rerun, run the generator again:

```sh
python3 scripts/generate_snapshots.py
```

Expected output is `No changes: all snapshots and ledger checkpoints already match the exports.` Existing files remain byte-for-byte unchanged.

For a genuine correction, preserve the original outputs and give the generator a new correction ID and an explanation. The implemented options are `--correction-id` and `--correction-note`; both are required together. For example:

```sh
python3 scripts/generate_snapshots.py --correction-id correction-2026-10-12-a --correction-note "Describe the verified source correction"
```

This writes a distinct chain under `deliverables/snapshots/corrections/<correction-id>/` with a `correction.json` manifest and corrected predecessor links. A correction output is itself not overwritten; choose a new ID for another correction. Never edit or replace a sealed snapshot in place.

## Read the official outputs

`deliverables/snapshots/` contains six JSON files:

- `batch-01.json`, `batch-02.json`, `batch-03.json`: schema-constrained per-export snapshots, each with application revision, element states, decision admission results, activation state, monitored conditions, and follow-up queue.
- `evidence-ledger-batch-01.json`, `evidence-ledger-batch-02.json`, `evidence-ledger-batch-03.json`: cumulative, append-only checkpoints holding source observations and document provenance through the corresponding export.

For an independent audit of source counts, revision preservation, schema, chaining, decision authority, activation safety, follow-up evidence, and deterministic reruns, read [deliverables/verification.md](deliverables/verification.md). It records the checks and their observed results. Rerun the validators above when checking the current snapshots.

## Known limitations and safety

- Some requirements cannot be independently established from fields in the supplied exports. Follow-up queues preserve these limitations; missing evidence is never clearance.
- A recorded approval may remain unadmitted when packet prerequisites or required authority cannot be established from the supplied evidence. Treat that as an evidence-based evaluator result, not a judgment that the hospital's decision was invalid.
- The evaluator cannot make reserved clinical judgments, determine the adequacy of a gap explanation, or create a committee action or disposition.
- Never invent verification evidence, human dispositions, committee decisions, approvals, or privilege activations. Never silently overwrite a completed snapshot. Keep source exports, schema, and detailed written rules authoritative.
