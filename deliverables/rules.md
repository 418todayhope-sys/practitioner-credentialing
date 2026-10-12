# Project E rules register

This register records the written hospital rules to implement and separates them from project implementation choices. The seven files under `office/` are the supplied written hospital reference set. When the interview differs from these documents, use the written rule and retain the difference as an unresolved interview conflict; the interview is operational context, not a rule source.

No batch has been processed and no snapshot has been created as part of this stage.

## Source key

| Key | Official document | Version / identifying text |
|---|---|---|
| PROC | `office/procedure-extract.txt` — **Initial appointment — Medical Staff Office procedure** | LARK-MSO-2026.1 |
| PRIV | `office/privilege-criteria.txt` — **Privilege criteria — initial appointment** | LARK-PRIV-2026.1 |
| ATT | `office/attester-table.txt` — **Accepted sources by element — who may attest** | LARK-ATT-2026.1 |
| AUTH | `office/authority-roster.txt` — **Reserved authority — who holds what** | LARK-AUTH-2026.1 |
| APP | `office/application-form.txt` — **Application for initial appointment and clinical privileges — blank form** | LARK-APP-2026.1 |
| REF | `office/peer-reference-form.txt` — **Professional peer reference — blank request and return form** | LARK-REF-2026.1 |
| EXP | `office/export-notes.txt` — **How this office exports its credentialing records** | Note written 2026-03-16; no version identifier stated |

Section references below use the section numbers and exact headings printed in those files. Where a source has no numbered section, its printed heading, form part, or table name is cited.

## 1. Scope, source authority, and date basis

| Rule | Classification | Authority |
|---|---|---|
| This workflow covers initial appointment only. Reappointment, additional privileges between appointments, credentialing by proxy, temporary privileges, and emergency or disaster privileges are outside scope. | Written hospital policy | PROC, opening scope paragraph before **“Where our rules come from, and how to tell them apart”** |
| The hospital is non-federal. Implement the Larkhollow rules in the procedure where they tailor or replace federal-facility rules; do not import additional rules from the adopted manual when the procedure does not state them. | Written hospital policy | PROC, **“Where our rules come from, and how to tell them apart”** |
| The export date is the clock for all calculations from a batch. Do not use the machine's current date for a batch calculation. | Written hospital policy | EXP, **“The export date is the clock”** |
| Batch 1 is cumulative through 2026-03-15; batches 2 and 3 contain changes since the previous export. The caseload accumulates and retains withdrawn or discontinued files. | Written hospital policy | EXP, **“The export date is the clock”**; **“The caseload at an export date…”** |
| An export is closed and immutable. Later information appears as new rows or documents; do not infer changes by expecting edits to earlier batch records. | Written hospital policy | EXP, **“A batch is closed. It never changes.”** |
| Treat `office/*.txt` as the local source paths. Some source prose names `.md` paths, but the supplied authoritative files have `.txt` extensions; do not create duplicate documents to satisfy those stale path references. | Project implementation choice | Repository inventory and user instruction; not hospital policy |
| Keep this register aligned to written documents. Record interview disagreements separately; do not promote interview-only claims into policy. | Project implementation choice | User instruction; not hospital policy |

## 2. Export ingestion and evidence retention

| Rule | Classification | Authority |
|---|---|---|
| Read the batch README and use its export date and coverage window. Nothing after that export date belongs to the batch's state. | Written hospital policy | EXP, **“The export date is the clock”**; each batch `README.md`, opening export-date and window statements |
| Read `correspondence.csv` as an index only. Open the referenced letters, dispositions, and decisions to establish what they say. | Written hospital policy | EXP, **“The files”**, `correspondence.csv` and document-folder descriptions |
| Empty cells mean no value is held; they do not mean zero, “no,” or presumed compliance. An empty `declared-history.to_date` means current through the export date; an empty certification reply `expiry_date` means non-expiring. | Written hospital policy | EXP, **“Dates, blanks and columns”** |
| Join applicant-side records by `application_id`, and by `revision` when the fact belongs to a revision. Use the current revision's repeated entries, credentials, privilege requests, and disclosures for current-revision statements. | Written hospital policy | EXP, **“The three joins that matter”**, rule 1 |
| Join the Washington lookup by last name, first name, middle name, and birth year. No matching row means no Washington credential in that export, not a malformed/missing-data exception. | Written hospital policy | EXP, **“The three joins that matter”**, rule 2 |
| A missing peer-reference reply is silence, not a reply. Establish unanswered attempts from `verification-attempts.csv`; do not treat absence from the replies file as completion. | Written hospital policy | EXP, **“The three joins that matter”**, rule 3 |
| Keep each source observation and each earlier revision. Corrected replies, later revisions, and repeated decisions are new events; none erases the earlier record. | Written hospital policy | EXP, **“A batch is closed. It never changes.”**; PROC, **2. Reconciliation** and **11. Re-entry: when something lands on work already done** |
| Maintain an evidence ledger that identifies the source batch, file, row/key, document path, and any rule citation behind each derived statement. This companion record supplies traceability the snapshot structure does not carry. | Project implementation choice | Schema contract has no per-element evidence citation properties; this ledger is an implementation artifact, not hospital policy |

## 3. Intake, completeness, and revisions

| Rule | Classification | Authority |
|---|---|---|
| Do not send verification requests before the Larkhollow Authorization and Release is signed and dated. A file without it cannot advance. | Written hospital policy | PROC, **1. Intake and completeness**; APP, **Section B — Authorization and release** |
| Apply all nine completeness conditions: signed/dated application; signed/dated release; at least one current privilege group; current CV; all professional-practice answers Yes/No with explanations for every Yes; continuous declared history from professional school with written explanations for uncovered periods of at least 30 days; two referees with working addresses; verification contacts for declared employers/affiliations; and declaration of every held licence and certification, active or inactive. | Written hospital policy | PROC, **1. Intake and completeness**, numbered Larkhollow completeness list; APP, **Sections A–J** |
| Missing completeness items are requested from the applicant in writing. The 30-calendar-day response period starts on the date of that written request; the deadline day is included and a reply on day 30 is in time. | Written hospital policy | PROC, **1. Intake and completeness**; APP, **“What the office does with a completed form”** |
| Do not start a discrepancy-notice deadline unless a written hospital rule or a dated written request in the record establishes it. The materials do not establish that every discrepancy notice has a 30-day deadline. | Unresolved limitation / conservative implementation boundary | PROC, **1. Intake and completeness** establishes the clock for missing-item requests; PROC, **2. Reconciliation** describes discrepancy resolution but sets no separate deadline. No deadline is inferred. |
| A response that adds or changes application information is a new revision. Preserve every prior revision; never replace it. | Written hospital policy | PROC, **1. Intake and completeness**; APP, opening paragraph |
| On a new revision, repeat intake/completeness screening and reconcile the changed entry against the CV and completed verifications. A change to dates, organization, role, supervisor, or verification contact changes the entry. Reopen affected work per section 11. | Written hospital policy | PROC, **2. Reconciliation**; **11. Re-entry**; APP, **Sections D–G** |
| The export omits referee working addresses. Mark completeness condition 7's address check as not assessable from the export, neither met nor failed; do not fabricate an address or infer a pass. | Written hospital policy | EXP, **“What I do not export”** |
| Store revision history and evidence append-only in the companion ledger. A no-change rerun preserves the existing sealed snapshot and creates no duplicate. For a genuine correction, retain the original, create a corrected snapshot in a distinct file with a distinct `snapshot_id`, document what was corrected and why, and repair downstream predecessor path/hash links as needed. Never silently overwrite a sealed snapshot. | Project implementation choice / schema contract | User instruction; `snapshot.schema.json`, `snapshot_id` description, `predecessor` description, and top-level snapshot description |

## 4. Reconciliation, source admissibility, and attempts

| Rule | Classification | Authority |
|---|---|---|
| Compare the CV, application, and completed verifications. When a source and applicant disagree, record both values and ask the applicant to resolve in writing or amend the application; the office does not choose, average, or silently substitute a value. | Written hospital policy | PROC, **2. Reconciliation** |
| A discrepancy holds the affected entry, not unrelated entries. Continue other verification work, but do not present the file while any discrepancy remains open. | Written hospital policy | PROC, **2. Reconciliation**; **8. Packet readiness** |
| Work on other elements may continue while one is outstanding. Hold the entire file only for a reason recorded in its action list. Never present with an element outstanding. | Written hospital policy | PROC, **2. Reconciliation** |
| A verification is a response from an admissible source, not a document carried by the applicant. Applicant-delivered primary-source responses and copies of diplomas, licences, or registrations cannot substitute for verification. | Written hospital policy | PROC, **3. The six checks — “What counts as a verification at all”**; ATT, cross-cutting rules before element tables |
| Use the source classes in the element-specific closed table: **Education and training**, **Licensure**, **Board certification**, and **Affiliations and employment**. Each row distinguishes primary, designated equivalent, secondary-on-impossibility, and not-accepted sources where applicable. Accept only listed sources. | Written hospital policy | ATT, tables **Education and training**, **Licensure**, **Board certification**, and **Affiliations and employment** |
| Preserve an unlisted reply, leave the element outstanding, continue an admissible request, log attempts, and raise the source question to the Medical Services Professional. | Written hospital policy | ATT, **“What to do with a reply that is not on this table”**; PROC, **3. The six checks** |
| Secondary-source verification is available only when the primary/designated equivalent source no longer exists (such as a closed school/programme or dissolved employer), and the reason must be recorded. Non-response is not impossibility. | Written hospital policy | ATT, element tables and **“What to do with a reply that is not on this table”**; PROC, **3. The six checks** |
| Keep every attempt permanently. At least three attempts are required under the cited manual rule; silence remains outstanding and may be a red flag. A later reply does not erase earlier attempts. | Written hospital policy | PROC, **3. The six checks — “How often we ask, and what silence means”** |

## 5. Six verification elements

### 5.1 Licensure

| Rule | Classification | Authority |
|---|---|---|
| Verify every active and inactive medical licence held. Require one current, active, full, unrestricted Washington licence for practice at this hospital. | Written hospital policy | PROC, **Check 1 — Licensure**; APP, **Section G — Licences and certifications** |
| Treat probation, supervision, a monitoring agreement, practice limitation, suspension, stipulated condition, or surrender as a licensure finding. Route the evidence to the Clinical Director; do not judge whether the restriction matters. A disposition ends the hold but does not make the finding disappear. | Written hospital policy | PROC, **Check 1 — Licensure**; AUTH, **Individual authority** |
| A National Provider Identifier is not a licence. | Written hospital policy | PROC, **Check 1 — Licensure**; APP, **Section A — Identity and contact** |
| Initial appointment cycle is one year from effective date through the day before its first anniversary. Licence validity is required on decision date. If Washington licence expiry falls inside the cycle, track re-verification; it does not block initial activation. Record the condition due date as the expiry date. | Written hospital policy | PROC, **Check 1 — Licensure**, **“The cycle”** |
| Board lookup `lookup_date` is the office's own observation, not an external source reply; do not apply the verification usability window to it. A lookup on decision date is usable for that decision. | Written hospital policy | EXP, **“The Washington export's own columns”**; PROC, **8. Packet readiness**, **“The board lookup and the window”** |

### 5.2 Experience

| Rule | Classification | Authority |
|---|---|---|
| Verify relevant work and affiliation history for at least the most recent five years, measured back from first application receipt; go further back for conflicts or suspicious indicators. A later revision does not move that anchor. | Written hospital policy | PROC, **Check 2 — Experience and time gaps** |
| Do not make a current-competency judgment from experience evidence. The procedure assigns current competency to clinical leadership; privilege criteria say current experience travels with the packet and does not make a group unsupported. | Written hospital policy | PROC, **Check 2 — Experience and time gaps**, current-competency boundary; PRIV, **How the office applies the table**, rule 7 |

### 5.3 Time gaps

| Rule | Classification | Authority |
|---|---|---|
| Compute gaps from the day after professional school ends. Treat declared entries as inclusive date ranges; an open end runs through the export date. Overlaps, part-time work, and training cover time. A gap is at least 30 consecutive uncovered days. Recompute the gap set when dates change. | Written hospital policy | PROC, **Check 2 — Experience and time gaps**; APP, **Sections D–F** |
| Record an explanation as covering a gap only if its explicit `Period explained` date range covers the entire computed gap. The office records presence/coverage, not adequacy. An unexplained gap returns the application incomplete. | Written hospital policy | PROC, **Check 2 — Experience and time gaps**; APP, **Section F — Explanation of periods not covered** |
| Route every gap of 180 days or more to the Clinical Director for disposition, whether explained or not. | Written hospital policy | PROC, **Check 2 — Experience and time gaps**; AUTH, **Individual authority** |

### 5.4 Professional education and post-graduate training

| Rule | Classification | Authority |
|---|---|---|
| Verify the qualifying degree and each post-graduate training entry using an admissible source. A degree or training completion is not a licence. | Written hospital policy | PROC, **Check 3 — Professional education and post-graduate training**; APP, **Section D**; ATT, **Education and training** |

### 5.5 Peer references

| Rule | Classification | Authority |
|---|---|---|
| The office sends the form directly to the named referee, who returns it directly. Applicant-carried references cannot be used. | Written hospital policy | REF, opening paragraph; PROC, **Check 4 — Professional peer references** |
| A referee qualifies only if all hold: direct work together within two years ending on signature date; same clinical discipline as applicant; and not a relative, spouse, or partner. Record an ineligible reply but do not count it. | Written hospital policy | REF, **Part 2 — completed by the referee**, **“Who may give a peer reference”**; PROC, **Check 4** |
| Reference currency is measured from signature date, not receipt date. It is current through the second anniversary of signature (presentation on or before that date); it can become stale while waiting. | Written hospital policy | REF, **“Currency”**; PROC, **Check 4 — Professional peer references**, **“when currency is measured”** |
| Ask up to three times, 21 calendar days apart. Beginning day 64 after first request, notify the applicant and request an additional referee. The original request remains open/outstanding and never counts. | Written hospital policy | REF, **Part 1 — completed by the Medical Staff Office before sending**; PROC, **Check 4** |
| Two qualifying, current references satisfy the element. An otherwise open request does not hold a met element; retain its action until presentation, then close it as no longer needed. | Written hospital policy | PROC, **Check 4 — Professional peer references** |

### 5.6 Board certification and requested privileges

| Rule | Classification | Authority |
|---|---|---|
| Verify all active and inactive board certifications. Use the closed source list in ATT. A lapsed certificate remains a verified historical fact but supports no privilege group. | Written hospital policy | PROC, **Check 5 — Board certification and the privileges requested**; ATT, **Board certification** |
| Apply the versioned privilege table as written. A group is supported only by qualifying verified certification (or the narrow permitted board-eligible route) and minimum training. Name unsupported groups individually; do not reject supported groups by association. | Written hospital policy | PRIV, **The twelve privilege groups** and **How the office applies the table**, rules 1–5 |
| Board eligibility substitutes for active certification only for PRIV-FM, PRIV-IM, PRIV-HOSP, and PRIV-PED, with written board confirmation of good standing and a future eligibility end date. It is unavailable for the other listed groups. | Written hospital policy | PRIV, **How the office applies the table**, rule 4 |
| PRIV-CARD requires both the specified cardiology fellowship and preceding internal medicine residency. | Written hospital policy | PRIV, **How the office applies the table**, rule 5 |
| If nothing verified supports any requested group, raise an eligibility question. The Clinical Director alone decides discontinuance. If later evidence supports a requested group, withdraw the question without disposition. | Written hospital policy | PRIV, **How the office applies the table**, rule 6; AUTH, **Individual authority** |
| Do not apply the criteria's current-experience column as an office eligibility test. Current competency is clinical leadership's judgment and travels with the packet. | Written hospital policy | PRIV, **How the office applies the table**, rule 7; PROC, **Reserved judgments** |

### Professional practice / high-risk findings (outside the six verification-element keys)

| Rule | Classification | Authority |
|---|---|---|
| Every professional-practice question must have Yes/No; every Yes requires an explanation. A Yes is a high-risk finding, not an automatic bar. If evidence suggests an applicant answered No when Yes was owed, contact the applicant to confirm. | Written hospital policy | APP, **Section I — Professional practice questions**; PROC, **4. High-risk findings** |
| Route high-risk findings to the Clinical Director and present evidence to the Executive Committee and Governing Body. Do not make a disqualification judgment. | Written hospital policy | PROC, **4. High-risk findings** and **6. Reserved judgments**; AUTH, **Individual authority** |

**Project implementation mapping (not an additional hospital rule):** map licensure → `licensure`; work/affiliation history verification → `experience`; uncovered periods and their explanations → `gaps`; professional education/training → `education`; board certification and privilege support → `certification`; peer references → `references`. Keep professional-practice/high-risk findings in the companion ledger/action reporting; they are not a seventh schema element. This maps PROC, **3. The six checks** and **4. High-risk findings** to `snapshot.schema.json`, `applications[].elements`.

## 6. Readiness, decisions, and activation

| Rule | Classification | Authority |
|---|---|---|
| General verification usability window: completed on or after first application receipt and before decision date; no fixed day count. A later revision does not automatically invalidate all evidence. Reassess only entries affected by revision changes. | Written hospital policy | PROC, **8. Packet readiness**, **“The usability window”**; **2. Reconciliation** |
| A packet is presentable only when all six elements are resolved, no item is outstanding, no discrepancy is open, required verifications are usable, and readiness is tied to one named revision. An adverse finding remains in the record after its required authorized disposition clears its hold; do not treat every historical finding as a permanent blocker. A finding without its required disposition, an outstanding item, or an unresolved discrepancy still prevents presentation. | Written hospital policy | PROC, **8. Packet readiness**, **“What makes a packet presentable”**; AUTH, **Individual authority** |
| Readiness is not undone by a refused decision, withdrawal, or discontinuance. It is lost when an element reopens or a new revision arrives; preserve earlier readiness as history. | Written hospital policy | PROC, **8. Packet readiness**; **11. Re-entry** |
| The Credentials Committee and Executive Committee may recommend, not recommend, or defer pending information; neither may approve. The Governing Body may approve, approve with conditions, defer pending information, or deny. | Written hospital policy | AUTH, **Who may record what** |
| Validate a decision using all five written conditions: authorized body/outcome; signatory held role on decision date; correct applicant and revision; presentable packet existed before decision date; valid outcome and required reason. Valid outcomes are approved, approved-with-conditions, deferred-pending-information, denied, recommended, and not-recommended. Plain approval and positive recommendation carry no reason; approval-with-conditions, deferral, denial, and not-recommended require one. Do not accept a decision's own assertion of authority as proof. | Written hospital policy | PROC, **9. The committee protocol**, **“what makes a decision admissible”** and **“which outcomes carry a reason”**; AUTH, **Who may record what** and opening authority statement |
| A decision against a superseded revision remains history and cannot authorize the current revision. A second Governing Body decision for the same revision must identify the earlier decision it supersedes; otherwise it is inadmissible. Keep refused records and reasons. | Written hospital policy | PROC, **9. The committee protocol**, rules on superseded revisions and two decisions; AUTH, **Who may record what** |
| A deferral identifies the information awaited; chase that information and do not advance while it is outstanding. | Written hospital policy | PROC, **9. The committee protocol**, **“deferral”** |
| Only an admitted Governing Body approval activates privileges. Activate exactly the privileges named in that approval, on its effective date or decision date if no separate effective date is given. Never activate before then. | Written hospital policy | PROC, **10. Activation and the appointment cycle**; AUTH, **Who may record what** |
| Approval with conditions activates approved groups normally and creates monitored conditions with due dates. A condition is satisfied only by a record naming it; one unmet on its due date becomes a finding. Monitored conditions do not block initial activation. | Written hospital policy | PROC, **10. Activation and the appointment cycle**, **“approve with conditions”** |
| Re-enter work for a new revision, new evidence/reclassification/corrected date, credential expiry/renewal, inadmissible or superseded decision, withdrawal, or discontinuance. Reopen only the affected work as specified and retain every prior occurrence. | Written hospital policy | PROC, **11. Re-entry: when something lands on work already done** |

## 7. Snapshot contract and implementation boundaries

The following are output-contract or implementation choices, not additional hospital credentialing rules.

| Constraint / choice | Classification | Authority |
|---|---|---|
| Produce one snapshot per consumed batch, including unfinished work. A later snapshot does not rewrite an earlier one. | Required output contract | `snapshot.schema.json`, top-level description |
| Use the exact schema version, required properties, enums, date formats, and closed-object shapes in the existing schema. Do not add properties or modify the schema. | Required output contract | `snapshot.schema.json`, `$schema`, `required`, `additionalProperties`, property definitions, and `$defs` |
| Include predecessor path and SHA-256 for later retained snapshots; the first predecessor is null. A snapshot does not hash itself. | Required output contract | `snapshot.schema.json`, `predecessor` description |
| `consumed.record_files` names the batch record files read; `consumed.documents` names batch documents opened. `produced` lists every created/refreshed file including that snapshot. `rules_file` points to this register or its maintained successor. | Required output contract | `snapshot.schema.json`, `consumed`, `produced`, and `rules_file` descriptions |
| Preserve detailed per-entry evidence and decision-to-revision linkage in a companion ledger because the schema's decision objects do not include revision, actor, body, date, outcome, or evidence fields. Do not squeeze unsupported fields into the schema. | Project implementation choice | `snapshot.schema.json`, `applications[].decisions[]` and `applications[].elements` definitions |
| Keep snapshots append-only. A no-change rerun leaves the existing sealed snapshot in place and creates no duplicate. For a genuine correction, retain the original and create a corrected snapshot with a distinct ID and file; document the correction and repair downstream predecessor links when the corrected snapshot changes a predecessor path or hash. Never silently replace a sealed snapshot. | Project implementation choice constrained by schema | User instruction; `snapshot.schema.json`, `snapshot_id` and `predecessor` descriptions |
| Use schema validation plus separate semantic checks for cross-record joins, date arithmetic, status precedence, decision authority, and evidence consistency. Schema validation alone does not establish these business facts. | Project implementation choice | Existing `scripts/validate_snapshot.py` validates JSON Schema structure/formats; schema property definitions |

## 8. Interview conflicts and unresolved limitations

| Topic | Written rule to follow | Interview statement / limitation | Authority |
|---|---|---|---|
| Discrepancy deadline | No separate deadline is stated for a discrepancy notice. The written 30-day clock is for a written request for missing completeness items. Do not assign a discrepancy deadline without further written authority. | Interview describes a 30-day response to discrepancy notices. This conflicts with the narrower written rule and is not adopted. | PROC, **1. Intake and completeness** and **2. Reconciliation** |
| Experience and competency | Verify relevant history; current competency is not determined by the office and does not make a privilege group unsupported. | Interview says experience may be “resolved after up to three attempts.” Do not implement this as a competency decision or an automatic resolution rule. | PROC, **Check 2 — Experience and time gaps**; PRIV, **How the office applies the table**, rule 7 |
| Referral/address completeness | Address condition is not assessable from this export. | Interview-level operational statements cannot supply missing addresses absent from the export. | EXP, **“What I do not export”** |
| Evidence schema detail | The schema is authoritative and unchanged; retain additional audit detail in the companion ledger. | Schema cannot encode all per-revision decision facts or source citations. | `snapshot.schema.json`, application and decision definitions |

No other interview-only requirement is adopted as a credentialing rule by this register. Any additional mismatch discovered during implementation must be recorded here with its written authority and left unresolved where the documents do not settle it.
