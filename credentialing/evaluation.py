"""Evaluate six verification elements from an evidence ledger.

The evaluator reports rule-mapped evidence states only. It does not admit
committee decisions, make clinical judgments, activate privileges, or create
snapshots.
"""

from __future__ import annotations

import calendar
import re
from datetime import date, timedelta
from typing import Any, Iterable


ELEMENT_STATES = {
    "resolved",
    "outstanding",
    "finding",
    "discrepancy",
    "return-incomplete",
    "routed-to-clinical-director",
    "eligibility-question",
}

POLICY = {
    "licensure": [
        "office/procedure-extract.txt § Check 1 — Licensure",
        "office/attester-table.txt — Licensure",
        "office/export-notes.txt — The three joins that matter, rule 2",
        "office/export-notes.txt — The Washington export's own columns",
    ],
    "experience": [
        "office/procedure-extract.txt § Check 2 — Experience and time gaps",
        "office/attester-table.txt — Affiliations and employment",
        "office/export-notes.txt — The three joins that matter, rule 1",
    ],
    "gaps": [
        "office/procedure-extract.txt § Check 2 — Experience and time gaps",
        "office/application-form.txt § Section F — Explanation of periods not covered",
    ],
    "education": [
        "office/procedure-extract.txt § Check 3 — Professional education and post-graduate training",
        "office/attester-table.txt — Education and training",
        "office/application-form.txt § Section D — Education and post-graduate training",
        "office/privilege-criteria.txt — The twelve privilege groups, universal education requirement",
    ],
    "certification": [
        "office/procedure-extract.txt § Check 5 — Board certification and the privileges requested",
        "office/attester-table.txt — Board certification",
        "office/privilege-criteria.txt — The twelve privilege groups",
        "office/privilege-criteria.txt — How the office applies the table, rules 1–7",
    ],
    "references": [
        "office/procedure-extract.txt § Check 4 — Professional peer references",
        "office/peer-reference-form.txt — Part 2, Who may give a peer reference",
        "office/peer-reference-form.txt — Currency",
        "office/peer-reference-form.txt — Part 1, completed by the Medical Staff Office before sending",
    ],
}

SOURCE_LIMITATIONS = [
    "The export has no field for peer-reference return channel; direct return cannot be independently verified from the ledger.",
    "The written criteria require accredited schools/programmes, but the declared and verification CSV fields do not identify accreditation status. Privilege support is not established without explicit accreditation evidence.",
    "The accepted-source table has no row defining acceptable verifiers for teaching or military history entries; those experience entries cannot be resolved from source type alone.",
]


def _parse_date(value: Any) -> date | None:
    if not isinstance(value, str) or not value:
        return None
    try:
        return date.fromisoformat(value)
    except ValueError:
        return None


def _has_positive_accreditation(text: Any) -> bool:
    normalized = str(text or "").casefold().replace("–", "-").replace("—", "-")
    if re.search(r"\b(?:not|non|un)\s*-?\s*accredited\b", normalized):
        return False
    if re.search(r"\baccreditation\s+(?:not verified|unknown|unverified|not established)\b", normalized):
        return False
    return "accredited" in normalized or "accreditation confirmed" in normalized


def _anniversary(day: date, years: int) -> date:
    year = day.year + years
    return day.replace(year=year, day=min(day.day, calendar.monthrange(year, day.month)[1]))


def _subtract_years(day: date, years: int) -> date:
    year = day.year - years
    return day.replace(year=year, day=min(day.day, calendar.monthrange(year, day.month)[1]))


def _row_records(ledger: dict[str, Any], as_of: date) -> list[tuple[dict[str, Any], dict[str, Any]]]:
    result = []
    for batch in ledger.get("batches", []):
        batch_date = _parse_date(batch.get("export_date"))
        if batch_date is None or batch_date > as_of:
            continue
        for record in batch.get("records", []):
            result.append((batch, record))
    return result


def _source_ref(batch: dict[str, Any], record: dict[str, Any], document_path: str | None = None) -> dict[str, Any]:
    ref = {
        "batch_id": batch.get("batch_id"),
        "filename": record.get("filename"),
        "row_number": record.get("row_number"),
        "stable_key": record.get("stable_key"),
    }
    if document_path:
        ref["document_path"] = document_path
    return ref


class _Element:
    def __init__(self, name: str):
        self.name = name
        self.evidence: list[dict[str, Any]] = []
        self.observations: list[dict[str, Any]] = []
        self.problems: set[str] = set()

    def cite(self, batch: dict[str, Any], record: dict[str, Any], document_path: str | None = None) -> None:
        ref = _source_ref(batch, record, document_path)
        if ref not in self.evidence:
            self.evidence.append(ref)

    def note(self, code: str, message: str, evidence: Iterable[dict[str, Any]] = ()) -> None:
        self.problems.add(code)
        entry = {"code": code, "message": message}
        cited = list(evidence)
        if cited:
            entry["evidence"] = cited
        if entry not in self.observations:
            self.observations.append(entry)

    def finish(self, forced_state: str | None = None) -> dict[str, Any]:
        if forced_state:
            state = forced_state
        else:
            # Observation codes remain detailed in the companion result; this
            # table maps them to the schema's coarser state vocabulary.
            state_codes = {
                "return-incomplete": {"unexplained_gap"},
                "discrepancy": {
                    "conflicting_source_responses", "unresolved_discrepancy",
                    "conflicting_certification_replies", "certification_identity_mismatch",
                    "undeclared_washington_license", "declared_certification_not_confirmed",
                },
                "routed-to-clinical-director": {"gap_disposition_pending"},
                "eligibility-question": {"threshold_eligibility_question"},
                "finding": {
                    "licensure_finding", "washington_license_not_current",
                    "washington_practice_license_missing",
                    "unsupported_requested_privilege",
                },
                "outstanding": {
                    "no_entries_to_verify", "missing_history_date", "missing_entry_id",
                    "professional_school_end_missing", "inadmissible_source",
                    "unusable_verification_date", "verification_outstanding", "unresolved_verification_outcome",
                    "incomplete_verification_content",
                    "accreditation_not_recorded", "gap_disposition_pending",
                    "licence_verification_outstanding", "inadmissible_license_source", "invalid_license_lookup_date",
                    "inadmissible_certification_source", "unusable_certification_date", "certification_verification_outstanding",
                    "no_privilege_request", "unknown_privilege_code", "board_action_requires_detail",
                    "privilege_support_not_established", "reference_outstanding", "reference_date_unusable",
                    "reference_not_countable", "two_references_not_established", "reference_channel_unverified",
                },
            }
            for state_name, codes in state_codes.items():
                if self.problems.intersection(codes):
                    self.problems.add(state_name)
            for candidate in (
                "return-incomplete",
                "discrepancy",
                "routed-to-clinical-director",
                "finding",
                "outstanding",
                "eligibility-question",
            ):
                if candidate in self.problems:
                    state = candidate
                    break
            else:
                state = "resolved"
        assert state in ELEMENT_STATES
        return {
            "state": state,
            "evidence": self.evidence,
            "rule_refs": POLICY[self.name],
            "observations": self.observations,
        }


def _doc_index(ledger: dict[str, Any], as_of: date, application_id: str) -> list[tuple[dict[str, Any], dict[str, Any], dict[str, Any]]]:
    output = []
    for batch, record in _row_records(ledger, as_of):
        values = record.get("values", {})
        if record.get("filename") != "correspondence.csv" or values.get("application_id") != application_id:
            continue
        path = values.get("document_path")
        for source_batch in ledger.get("batches", []):
            if source_batch.get("batch_id") != batch.get("batch_id"):
                continue
            document = next((d for d in source_batch.get("documents", []) if d.get("path") == path), None)
            if document is not None:
                doc_date_match = re.search(r"^\*\*Date:\*\*\s*(\d{4}-\d{2}-\d{2})", document.get("content", ""), re.MULTILINE)
                doc_date = _parse_date(doc_date_match.group(1)) if doc_date_match else None
                if doc_date is None or doc_date <= as_of:
                    output.append((batch, record, document))
    return output


def _entry_replies(
    rows: list[tuple[dict[str, Any], dict[str, Any]]], application_id: str, entry_id: str, element: str
) -> list[tuple[dict[str, Any], dict[str, Any]]]:
    return [
        (batch, record)
        for batch, record in rows
        if record.get("filename") == "verification-replies.csv"
        and record.get("values", {}).get("application_id") == application_id
        and record.get("values", {}).get("entry_id") == entry_id
        and record.get("values", {}).get("element") == element
    ]


def _source_class(element: str, values: dict[str, Any], docs: list[tuple[dict[str, Any], dict[str, Any], dict[str, Any]]]) -> tuple[str, str]:
    received = str(values.get("received_from") or "").strip().casefold()
    organization = str(values.get("attester_organization") or "").strip().casefold()
    context = str(values.get("notes") or "").casefold()
    doc_text = "\n".join(d.get("content", "") for _, _, d in docs).casefold()

    if "applicant" in received:
        return "inadmissible", "Applicant-delivered primary-source material is not an acceptable verification source."

    if element == "education-and-training":
        if received.startswith(("registrar's office", "dean's office", "graduate medical education office", "programme director")):
            return "primary", "Listed primary education/training source."
        if any(term in received or term in organization for term in (
            "ecfmg", "federation credentials verification service", "fcvs",
            "american medical association physician profile", "ama physician profile",
            "american osteopathic association physician profile", "aoa physician profile",
            "national student clearinghouse",
        )):
            return "designated-equivalent", "Listed designated equivalent education/training source."
        if received.startswith("medical staff office") and any(term in (context + "\n" + doc_text) for term in ("school closed", "programme closed", "program closed", "school has closed")):
            reason_present = any(term in (context + "\n" + doc_text) for term in ("no designated equivalent", "no equivalent source", "does not exist", "closed and no"))
            if reason_present:
                return "secondary-impossibility", "Closed school/programme exception is documented in the source notes or indexed record."
        return "inadmissible", "Source is not identified in the closed education/training source table."

    if element == "affiliation-and-employment":
        if received.startswith(("medical staff office", "human resources", "authorized administrator", "employer's human resources")):
            return "primary", "Listed primary affiliation/employment source."
        if any(term in received for term in ("credentials verification organization", "credentials verification organisation", "cvo")):
            if organization and (organization in received or organization in context):
                return "designated-equivalent", "CVO is identified as acting for the affiliation/employer."
            return "inadmissible", "CVO response does not identify the affiliation/employer it acted for."
        if received.startswith("medical staff office") and any(term in (context + "\n" + doc_text) for term in ("employer dissolved", "employer has dissolved", "no successor")):
            return "secondary-impossibility", "Dissolved-employer exception is documented."
        return "inadmissible", "Source is not identified in the closed affiliation/employment source table."

    return "inadmissible", "No source rule is defined for this element."


def _reply_is_usable(values: dict[str, Any], first_received: date, as_of: date) -> tuple[bool, str]:
    received = _parse_date(values.get("received_date"))
    if received is None:
        return False, "Verification has no valid received_date."
    if received > as_of:
        return False, "Verification was received after the requested export date."
    if received < first_received:
        return False, "Verification predates the application's first-received date and is outside the usability window."
    return True, ""


def _add_related_documents(element: _Element, docs: list[tuple[dict[str, Any], dict[str, Any], dict[str, Any]]], terms: tuple[str, ...] = ()) -> list[tuple[dict[str, Any], dict[str, Any], dict[str, Any]]]:
    matched = []
    for batch, index_record, document in docs:
        if not terms or any(term.casefold() in document.get("content", "").casefold() for term in terms):
            element.cite(batch, index_record, document.get("path"))
            matched.append((batch, index_record, document))
    return matched


def _education_experience_elements(
    elements: dict[str, _Element], rows: list[tuple[dict[str, Any], dict[str, Any]]],
    app: dict[str, Any], application_id: str, revision: str, as_of: date,
    first_received: date, docs: list[tuple[dict[str, Any], dict[str, Any], dict[str, Any]]],
) -> None:
    current_history = [
        (batch, record) for batch, record in rows
        if record.get("filename") == "declared-history.csv"
        and record.get("values", {}).get("application_id") == application_id
        and record.get("values", {}).get("revision") == revision
    ]
    categories = {
        "education": {"medical-school", "residency", "fellowship", "other"},
        "experience": {"employment", "affiliation", "teaching", "military", "other"},
    }
    for element_name, required_element in (("education", "education-and-training"), ("experience", "affiliation-and-employment")):
        element = elements[element_name]
        relevant = []
        for batch, record in current_history:
            values = record.get("values", {})
            entry_type = str(values.get("entry_type") or "").casefold()
            if entry_type not in categories[element_name]:
                continue
            if element_name == "experience":
                start, end = _parse_date(values.get("from_date")), _parse_date(values.get("to_date")) or as_of
                anchor_window = _subtract_years(first_received, 5)
                if start is None:
                    element.cite(batch, record)
                    element.note("missing_history_date", "History entry lacks a valid from_date.", [element.evidence[-1]])
                    continue
                if end < anchor_window or start > first_received:
                    continue
            relevant.append((batch, record))
            element.cite(batch, record)

        if not relevant:
            # Cite the revision record that establishes the scope of this empty
            # result. Absence of rows is not evidence that the check is complete.
            app_batch = next((b for b, r in rows if r.get("filename") == "applications.csv"
                              and r.get("values", {}).get("application_id") == application_id
                              and str(r.get("values", {}).get("revision")) == revision), None)
            if app_batch is not None:
                app_record = next(r for b, r in rows if b is app_batch and r.get("filename") == "applications.csv"
                                  and r.get("values", {}).get("application_id") == application_id
                                  and str(r.get("values", {}).get("revision")) == revision)
                element.cite(app_batch, app_record)
            element.note("no_entries_to_verify", "No applicable history entries were found for this element; evidence is still required.", element.evidence)
            element.problems.add("outstanding")
            continue

        for entry_batch, entry_record in relevant:
            entry = entry_record["values"]
            entry_id = entry.get("entry_id")
            if not entry_id:
                element.note("missing_entry_id", "History entry has no entry_id for linking its verification.", [_source_ref(entry_batch, entry_record)])
                continue
            replies = _entry_replies(rows, application_id, entry_id, required_element)
            accepted: list[tuple[dict[str, Any], dict[str, Any]]] = []
            for reply_batch, reply_record in replies:
                reply = reply_record["values"]
                element.cite(reply_batch, reply_record)
                source_class, source_explanation = _source_class(required_element, reply, docs)
                usable, date_explanation = _reply_is_usable(reply, first_received, as_of)
                if source_class in ("inadmissible",) or not usable:
                    element.note(
                        "inadmissible_source" if source_class == "inadmissible" else "unusable_verification_date",
                        source_explanation if source_class == "inadmissible" else date_explanation,
                        [_source_ref(reply_batch, reply_record)],
                    )
                    continue
                outcome = str(reply.get("outcome") or "").casefold()
                if outcome not in {"confirmed", "confirmed-with-discrepancy"}:
                    element.note("unresolved_verification_outcome", f"Verification reply for entry {entry_id} has no recognized confirmation outcome.", [_source_ref(reply_batch, reply_record)])
                    continue
                if not str(reply.get("verified_credential") or "").strip() or not _parse_date(reply.get("verified_from")) or not _parse_date(reply.get("verified_to")):
                    # Export notes define blank declared-history.to_date but do
                    # not define blank source-reply verified_to as current.
                    element.note("incomplete_verification_content", f"Verification reply for entry {entry_id} lacks a verified credential or complete source date range; blank reply dates are not inferred as current.", [_source_ref(reply_batch, reply_record)])
                    continue
                accepted.append((reply_batch, reply_record))

            if not accepted:
                element.note("verification_outstanding", f"No admissible, usable verification is on file for entry {entry_id}.", [_source_ref(entry_batch, entry_record)])
                continue

            # Conflicting source responses are retained as a discrepancy; row order
            # alone is not an authorization to discard or supersede one.
            signatures = set()
            for _, reply_record in accepted:
                rv = reply_record["values"]
                signatures.add((rv.get("verified_credential"), rv.get("verified_from"), rv.get("verified_to")))
            if len(signatures) > 1:
                element.note("conflicting_source_responses", f"Multiple admissible replies conflict for entry {entry_id}.", [
                    _source_ref(b, r) for b, r in accepted
                ])

            declared_from, declared_to = entry.get("from_date"), entry.get("to_date")
            for reply_batch, reply_record in accepted:
                reply = reply_record["values"]
                mismatch = False
                for declared_field, verified_field in (("from_date", "verified_from"), ("to_date", "verified_to")):
                    declared_value = entry.get(declared_field) or (as_of.isoformat() if declared_field == "to_date" else "")
                    verified_value = reply.get(verified_field) or ""
                    if declared_value and verified_value and declared_value != verified_value:
                        mismatch = True
                outcome_discrepancy = str(reply.get("outcome") or "").casefold() == "confirmed-with-discrepancy"
                if mismatch or outcome_discrepancy:
                    element.note("unresolved_discrepancy", f"Applicant and verification records disagree for entry {entry_id}; retain both values for reconciliation.", [
                        _source_ref(entry_batch, entry_record), _source_ref(reply_batch, reply_record)
                    ])
                elif reply.get("outcome") not in (None, "", "confirmed"):
                    element.note("unresolved_verification_outcome", f"Verification outcome {reply.get('outcome')!r} is not a plain confirmation for entry {entry_id}.", [_source_ref(reply_batch, reply_record)])

            if element_name == "education" and entry.get("entry_type") in {"medical-school", "residency", "fellowship"}:
                if not any(
                    _has_positive_accreditation(str(r["values"].get("verified_credential") or "") + " " + str(r["values"].get("notes") or ""))
                    for _, r in accepted
                ):
                    element.note("accreditation_not_recorded", f"Accreditation is not established for the {entry.get('entry_type')} entry {entry_id}; the published privilege criteria require accredited schools and programmes.", [
                        _source_ref(entry_batch, entry_record), *[_source_ref(b, r) for b, r in accepted]
                    ])

    # ``app`` is retained in the signature because revision identity is part of
    # the caller contract; this function evaluates only scoped history rows.
    _ = app


def _parse_explanations(docs: list[tuple[dict[str, Any], dict[str, Any], dict[str, Any]]], as_of: date) -> list[tuple[date, date, dict[str, Any], dict[str, Any], dict[str, Any]]]:
    parsed = []
    for batch, index_record, document in docs:
        content = document.get("content", "")
        match = re.search(r"^\*\*Period explained:\*\*\s*(\d{4}-\d{2}-\d{2})\s+to\s+(\d{4}-\d{2}-\d{2})", content, re.MULTILINE)
        if not match:
            match = re.search(r"^Period explained:\s*(\d{4}-\d{2}-\d{2})\s+to\s+(\d{4}-\d{2}-\d{2})", content, re.MULTILINE)
        if match:
            start, end = _parse_date(match.group(1)), _parse_date(match.group(2))
            if start and end and end <= as_of and start <= end:
                parsed.append((start, end, batch, index_record, document))
    return parsed


def _gaps_element(
    element: _Element, history: list[tuple[dict[str, Any], dict[str, Any]]],
    docs: list[tuple[dict[str, Any], dict[str, Any], dict[str, Any]]], as_of: date,
) -> None:
    entries = [record for _, record in history]
    for batch, record in history:
        element.cite(batch, record)
    school_ends = [
        _parse_date(record["values"].get("to_date"))
        for record in entries if record["values"].get("entry_type") == "medical-school"
    ]
    school_ends = [day for day in school_ends if day]
    if not school_ends:
        element.note("professional_school_end_missing", "Cannot calculate the gap timeline without a medical-school completion date.", element.evidence)
        return
    first_uncovered_day = max(school_ends) + timedelta(days=1)
    if first_uncovered_day > as_of:
        return

    intervals = []
    for batch, record in history:
        values = record["values"]
        start, end = _parse_date(values.get("from_date")), _parse_date(values.get("to_date")) or as_of
        if start and end >= first_uncovered_day and start <= as_of:
            intervals.append((max(start, first_uncovered_day), min(end, as_of), batch, record))
            element.cite(batch, record)
    intervals.sort(key=lambda item: item[0])
    uncovered = []
    cursor = first_uncovered_day
    for start, end, _, _ in intervals:
        if end < start:
            continue
        if start > cursor:
            gap_end = start - timedelta(days=1)
            if (gap_end - cursor).days + 1 >= 30:
                uncovered.append((cursor, gap_end))
        if end >= cursor:
            cursor = end + timedelta(days=1)
    if cursor <= as_of and (as_of - cursor).days + 1 >= 30:
        uncovered.append((cursor, as_of))

    explanations = _parse_explanations(docs, as_of)
    dispositions = [
        (batch, index_record, document)
        for batch, index_record, document in docs
        if "/dispositions/" in f"/{document.get('path', '')}"
    ]
    for start, end in uncovered:
        covering = [(s, e, b, r, d) for s, e, b, r, d in explanations if s <= start and e >= end]
        if covering:
            for _, _, batch, record, document in covering:
                element.cite(batch, record, document.get("path"))
            element.observations.append({
                "code": "gap_explained",
                "message": f"Uncovered period {start.isoformat()} to {end.isoformat()} has a written explanation covering the whole period; adequacy is not evaluated here.",
                "evidence": [_source_ref(b, r, d.get("path")) for _, _, b, r, d in covering],
            })
        else:
            element.note("unexplained_gap", f"Uncovered period {start.isoformat()} to {end.isoformat()} has no covering written explanation.", [
                _source_ref(batch, record) for batch, record in history
            ])

        if (end - start).days + 1 >= 180:
            matching_dispositions = []
            for batch, index_record, document in dispositions:
                text = document.get("content", "")
                if start.isoformat() in text and end.isoformat() in text:
                    matching_dispositions.append((batch, index_record, document))
            if matching_dispositions:
                for batch, record, document in matching_dispositions:
                    element.cite(batch, record, document.get("path"))
                element.observations.append({
                    "code": "clinical_director_disposition_recorded",
                    "message": f"A disposition record names the long gap {start.isoformat()} to {end.isoformat()}; its human judgment is retained, not re-evaluated.",
                    "evidence": [_source_ref(b, r, d.get("path")) for b, r, d in matching_dispositions],
                })
            else:
                element.note("gap_disposition_pending", f"Gap of at least 180 days ({start.isoformat()} to {end.isoformat()}) awaits a Clinical Director disposition.", [
                    *[_source_ref(b, r) for b, r in history],
                    *[_source_ref(b, r, d.get("path")) for _, _, b, r, d in covering],
                ])

    if "unexplained_gap" in element.problems:
        element.problems.discard("outstanding")
        element.problems.add("return-incomplete")
    if "gap_disposition_pending" in element.problems:
        element.problems.add("routed-to-clinical-director")


def _license_element(
    element: _Element, rows: list[tuple[dict[str, Any], dict[str, Any]]], app: dict[str, Any],
    application_id: str, revision: str, as_of: date,
    docs: list[tuple[dict[str, Any], dict[str, Any], dict[str, Any]]],
) -> None:
    identity = tuple(str(app.get(field) or "") for field in ("last_name", "first_name", "middle_name", "birth_year"))
    declared = [
        (batch, record) for batch, record in rows
        if record.get("filename") == "declared-credentials.csv"
        and record.get("values", {}).get("application_id") == application_id
        and record.get("values", {}).get("revision") == revision
        and str(record.get("values", {}).get("credential_class") or "").casefold() in {"licence", "license"}
    ]
    for batch, record in declared:
        element.cite(batch, record)
    wa_rows = [
        (batch, record) for batch, record in rows
        if record.get("filename") == "licence-lookup-wa.csv"
        and tuple(str(record.get("values", {}).get(field) or "") for field in ("lastname", "firstname", "middlename", "birthyear")) == identity
    ]
    other_rows = [
        (batch, record) for batch, record in rows
        if record.get("filename") == "licence-lookup-other-states.csv"
    ]
    matched: dict[str, list[tuple[dict[str, Any], dict[str, Any]]]] = {}
    for item in wa_rows:
        number = item[1]["values"].get("credentialnumber")
        if number:
            matched.setdefault(str(number), []).append(item)
    for declared_batch, declared_record in declared:
        dv = declared_record["values"]
        number = str(dv.get("number_declared") or "")
        jurisdiction = str(dv.get("jurisdiction_or_board") or "").upper()
        candidates = matched.get(number, []) if jurisdiction == "WA" else []
        if jurisdiction != "WA":
            candidates = [
                (b, r) for b, r in other_rows
                if str(r.get("values", {}).get("licence_number") or "") == number
                and str(r.get("values", {}).get("board_state") or "").upper() == jurisdiction
            ]
        if not candidates:
            element.note("licence_verification_outstanding", f"No board lookup row is linked to declared licence {number!r} ({jurisdiction}).", [_source_ref(declared_batch, declared_record)])
            continue
        for lookup_batch, lookup_record in candidates:
            lv = lookup_record["values"]
            element.cite(lookup_batch, lookup_record)
            if jurisdiction != "WA":
                verified_by = str(lv.get("verified_by") or "").casefold()
                accepted = ("board" in verified_by and "online verification" in verified_by) or "physician data center" in verified_by
                if not accepted:
                    element.note("inadmissible_license_source", f"Out-of-state licence source {lv.get('verified_by')!r} is not established as a listed board/FSMB source.", [_source_ref(lookup_batch, lookup_record)])
                    continue
            lookup_date = _parse_date(lv.get("lookup_date"))
            if lookup_date is None or lookup_date > as_of:
                element.note("invalid_license_lookup_date", f"Licence lookup date {lv.get('lookup_date')!r} is missing, invalid, or after the export date.", [_source_ref(lookup_batch, lookup_record)])
                continue
            state = str(lv.get("status") or lv.get("license_status") or "").casefold()
            action = str(lv.get("actiontaken") or lv.get("disciplinary_action") or "").casefold()
            action_detail_classified = False
            if action not in {"", "no", "none", "none reported", "false"}:
                if action not in {"yes", "pending", "true"} and any(term in action for term in ("probation", "supervision", "monitoring agreement", "practice limitation", "suspend", "stipulated condition", "surrender", "restriction")):
                    element.note("licensure_finding", f"Board record states an adverse licence condition for {number!r}; preserve and route to the Clinical Director.", [_source_ref(lookup_batch, lookup_record)])
            expiration = _parse_date(lv.get("expirationdate") or lv.get("expiry_date"))
            if jurisdiction == "WA" and (state != "active" or expiration is None or expiration < as_of):
                element.note("washington_license_not_current", f"Washington lookup does not show licence {number!r} as active and unexpired on {as_of.isoformat()}.", [_source_ref(lookup_batch, lookup_record)])
            if jurisdiction == "WA" and any(term in action for term in ("yes", "pending", "stipulated", "probation", "supervision", "restriction")):
                for doc_batch, index_record, document in docs:
                    content = document.get("content", "")
                    if number in content:
                        detail = content.casefold()
                        fields = {k.strip().casefold(): v.strip() for k, v in re.findall(r"^\*\*([^*]+):\*\*[ \t]*(.*?)[ \t]*$", content, re.M)}
                        source_name = fields.get("from", "").casefold()
                        if not any(term in source_name for term in ("washington state department of health", "washington medical commission", "state licensing board")):
                            continue
                        element.cite(doc_batch, index_record, document.get("path"))
                        restrictive = any(term in detail for term in (
                            "stipulated agreement", "under supervision", "monitoring programme", "monitoring program",
                            "practice limitation", "on probation", "suspended", "surrendered", "practice restriction",
                        ))
                        negated = any(phrase in detail for phrase in (
                            "no practice restriction", "no restriction is in force", "not restricted", "no monitoring agreement",
                        ))
                        if restrictive and not negated:
                            action_detail_classified = True
                            element.note("licensure_finding", f"Indexed board document describes a restriction for licence {number!r}; preserve it without judging its significance.", [
                                _source_ref(lookup_batch, lookup_record), _source_ref(doc_batch, index_record, document.get("path"))
                            ])
                        elif negated:
                            action_detail_classified = True
            if action in {"yes", "pending", "true"} and not action_detail_classified:
                element.note("board_action_requires_detail", f"Board lookup indicates action ({action}); an authoritative written board detail classifying the action is not on file.", [_source_ref(lookup_batch, lookup_record)])

    declared_numbers = {str(r[1]["values"].get("number_declared") or "") for r in declared}
    for batch, record in wa_rows:
        number = str(record["values"].get("credentialnumber") or "")
        if number and number not in declared_numbers:
            element.cite(batch, record)
            declared_sources = [_source_ref(b, r) for b, r in declared]
            element.note("undeclared_washington_license", f"Washington lookup contains credential {number!r}, absent from this revision's declared licences.", [_source_ref(batch, record), *declared_sources])

    active_wa = []
    for batch, record in wa_rows:
        values = record["values"]
        expiration = _parse_date(values.get("expirationdate"))
        if str(values.get("status") or "").casefold() == "active" and expiration is not None and expiration >= as_of:
            active_wa.append((batch, record))
    if not active_wa:
        application_sources = [
            _source_ref(batch, record) for batch, record in rows
            if record.get("filename") == "applications.csv"
            and record.get("values", {}).get("application_id") == application_id
            and str(record.get("values", {}).get("revision")) == revision
        ]
        element.note("washington_practice_license_missing", "No current active Washington licence is present in the joined board lookup on the export date.", [
            *[_source_ref(batch, record) for batch, record in wa_rows], *application_sources,
        ])
        element.problems.add("finding")


PRIVILEGES: dict[str, dict[str, Any]] = {
    "PRIV-FM": {"boards": {"ABFM": {"Family Medicine"}, "AOBFP": {"Family Practice"}}, "training": [("residency", "family medicine", 36)]},
    "PRIV-IM": {"boards": {"ABIM": {"Internal Medicine"}, "AOBIM": {"Internal Medicine"}}, "training": [("residency", "internal medicine", 36)]},
    "PRIV-HOSP": {"boards": {"ABIM": {"Internal Medicine", "Internal Medicine with Focused Practice in Hospital Medicine"}, "ABFM": {"Family Medicine"}, "AOBIM": {"Internal Medicine"}}, "training": [("residency", "internal medicine", 36), ("residency", "family medicine", 36)]},
    "PRIV-CARD": {"boards": {"ABIM": {"Cardiovascular Disease"}, "AOBIM": {"Cardiology"}}, "training": [("residency", "internal medicine", 36), ("fellowship", "cardiovascular disease", 36)]},
    "PRIV-EM": {"boards": {"ABEM": {"Emergency Medicine"}, "AOBEM": {"Emergency Medicine"}}, "training": [("residency", "emergency medicine", 36)]},
    "PRIV-GS": {"boards": {"ABS": {"Surgery"}, "AOBS": {"General Surgery"}}, "training": [("residency", "general surgery", 60)]},
    "PRIV-OBG": {"boards": {"ABOG": {"Obstetrics and Gynecology"}, "AOBOG": {"Obstetrics and Gynecology"}}, "training": [("residency", "obstetrics and gynecology", 48)]},
    "PRIV-PED": {"boards": {"ABP": {"Pediatrics"}, "AOBP": {"Pediatrics"}}, "training": [("residency", "pediatrics", 36)]},
    "PRIV-ANES": {"boards": {"ABA": {"Anesthesiology"}, "AOBA": {"Anesthesiology"}}, "training": [("residency", "anesthesiology", 48)]},
    "PRIV-RAD": {"boards": {"ABR": {"Diagnostic Radiology"}, "AOBR": {"Diagnostic Radiology"}}, "training": [("residency", "diagnostic radiology", 48)]},
    "PRIV-PSY": {"boards": {"ABPN": {"Psychiatry"}, "AOBNP": {"Psychiatry"}}, "training": [("residency", "psychiatry", 48)]},
    "PRIV-ORTHO": {"boards": {"ABOS": {"Orthopaedic Surgery"}, "AOBOS": {"Orthopedic Surgery"}}, "training": [("residency", "orthopaedic surgery", 60)]},
}


def _add_months(day: date, months: int) -> date:
    month_index = day.month - 1 + months
    year = day.year + month_index // 12
    month = month_index % 12 + 1
    return date(year, month, min(day.day, calendar.monthrange(year, month)[1]))


def _training_support(
    requirements: list[tuple[str, str, int]],
    history: list[tuple[dict[str, Any], dict[str, Any]]],
    rows: list[tuple[dict[str, Any], dict[str, Any]]],
    application_id: str,
    first_received: date,
    as_of: date,
    docs: list[tuple[dict[str, Any], dict[str, Any], dict[str, Any]]],
) -> tuple[bool, list[dict[str, Any]], bool]:
    evidence = []
    accredited_missing = False

    # Every privilege group also requires a verified MD/DO from an accredited
    # school. The export has no accreditation column, so accreditation must be
    # stated in the accepted registrar reply itself; it is never presumed.
    degree_verified = False
    degree_entries = [
        (b, r) for b, r in history
        if str(r.get("values", {}).get("entry_type") or "").casefold() == "medical-school"
    ]
    for entry_batch, entry_record in degree_entries:
        ev = entry_record["values"]
        evidence.append(_source_ref(entry_batch, entry_record))
        replies = _entry_replies(rows, application_id, str(ev.get("entry_id") or ""), "education-and-training")
        for reply_batch, reply_record in replies:
            rv = reply_record["values"]
            source_class, _ = _source_class("education-and-training", rv, docs)
            usable, _ = _reply_is_usable(rv, first_received, as_of)
            if source_class == "inadmissible" or not usable or str(rv.get("outcome") or "").casefold() != "confirmed":
                continue
            if not _parse_date(rv.get("verified_from")) or not _parse_date(rv.get("verified_to")):
                continue
            text = (str(rv.get("verified_credential") or "") + " " + str(rv.get("notes") or "")).casefold()
            if not any(term in text for term in ("doctor of medicine", "doctor of osteopathic medicine")):
                continue
            evidence.append(_source_ref(reply_batch, reply_record))
            if _has_positive_accreditation(text):
                degree_verified = True
                break
            accredited_missing = True
        if degree_verified:
            break
    if not degree_verified:
        # No medical-school response or no explicit accreditation proof is not
        # evidence of an unqualified school; it is an unresolved requirement.
        return False, evidence, True

    for entry_type, specialty, minimum_months in requirements:
        matched = False
        for entry_batch, entry_record in history:
            ev = entry_record["values"]
            if str(ev.get("entry_type") or "").casefold() != entry_type:
                continue
            desc = (str(ev.get("role") or "") + " " + str(ev.get("organization") or "")).casefold()
            if specialty not in desc:
                continue
            replies = _entry_replies(rows, application_id, str(ev.get("entry_id") or ""), "education-and-training")
            for reply_batch, reply_record in replies:
                rv = reply_record["values"]
                source_class, _ = _source_class("education-and-training", rv, docs)
                usable, _ = _reply_is_usable(rv, first_received, as_of)
                if source_class == "inadmissible" or not usable or str(rv.get("outcome") or "").casefold() != "confirmed":
                    continue
                if not _parse_date(rv.get("verified_from")) or not _parse_date(rv.get("verified_to")):
                    continue
                verified_text = str(rv.get("verified_credential") or "").casefold()
                if entry_type not in verified_text or specialty not in verified_text:
                    continue
                start = _parse_date(rv.get("verified_from"))
                end = _parse_date(rv.get("verified_to"))
                if not start or not end or end < start:
                    continue
                completed_months = 0
                for months in range(1, 121):
                    if end >= _add_months(start, months) - timedelta(days=1):
                        completed_months = months
                    else:
                        break
                if completed_months < minimum_months:
                    continue
                if not _has_positive_accreditation(verified_text + " " + str(rv.get("notes") or "")):
                    accredited_missing = True
                    continue
                evidence.extend([_source_ref(entry_batch, entry_record), _source_ref(reply_batch, reply_record)])
                matched = True
                break
            if matched:
                break
        if not matched:
            return False, evidence, True
    return True, evidence, accredited_missing


def _certification_element(
    element: _Element, rows: list[tuple[dict[str, Any], dict[str, Any]]], app: dict[str, Any],
    application_id: str, revision: str, first_received: date, as_of: date,
    docs: list[tuple[dict[str, Any], dict[str, Any], dict[str, Any]]],
) -> None:
    declarations = [
        (b, r) for b, r in rows
        if r.get("filename") == "declared-credentials.csv"
        and r.get("values", {}).get("application_id") == application_id
        and r.get("values", {}).get("revision") == revision
        and str(r.get("values", {}).get("credential_class") or "").casefold() in {"certification", "certificate"}
    ]
    history = [
        (b, r) for b, r in rows
        if r.get("filename") == "declared-history.csv"
        and r.get("values", {}).get("application_id") == application_id
        and r.get("values", {}).get("revision") == revision
    ]
    for b, r in declarations:
        element.cite(b, r)
    replies_by_declaration: dict[str, list[tuple[dict[str, Any], dict[str, Any]]]] = {}
    for b, r in rows:
        if r.get("filename") == "certification-replies.csv" and r.get("values", {}).get("application_id") == application_id:
            replies_by_declaration.setdefault(str(r["values"].get("declaration_id") or ""), []).append((b, r))

    verified: list[tuple[dict[str, Any], dict[str, Any], dict[str, Any]]] = []
    for decl_batch, decl_record in declarations:
        dv = decl_record["values"]
        declaration_id = str(dv.get("declaration_id") or "")
        replies = replies_by_declaration.get(declaration_id, [])
        accepted = []
        for rb, rr in replies:
            rv = rr["values"]
            element.cite(rb, rr)
            received = str(rv.get("received_from") or "").casefold()
            board_code = str(rv.get("board_code") or "").upper()
            accepted_source = received.startswith("certifying board") or any(name in received for name in (
                "abms", "certifacts", "american medical association physician profile",
                "american osteopathic association physician profile", "abps", "ancc", "nccpa",
            ))
            usable, date_reason = _reply_is_usable(rv, first_received, as_of)
            if not accepted_source:
                element.note("inadmissible_certification_source", f"Certification reply source {rv.get('received_from')!r} is not listed in the accepted-source table.", [_source_ref(rb, rr)])
            elif not usable:
                element.note("unusable_certification_date", date_reason, [_source_ref(rb, rr)])
            else:
                declared_code = str(dv.get("jurisdiction_or_board") or "").strip().casefold()
                declared_issuer = str(dv.get("issuer") or "").strip().casefold()
                reply_code = str(rv.get("board_code") or "").strip().casefold()
                reply_board = str(rv.get("board_name") or "").strip().casefold()
                if (declared_code and reply_code != declared_code) or (declared_issuer and reply_board != declared_issuer):
                    element.note("certification_identity_mismatch", f"Board reply identity does not match declaration {declaration_id!r}; preserve both and do not use the reply for privilege support.", [
                        _source_ref(decl_batch, decl_record), _source_ref(rb, rr),
                    ])
                    continue
                accepted.append((rb, rr))
        if not accepted:
            element.note("certification_verification_outstanding", f"No admissible, usable certification reply is on file for declaration {declaration_id!r}.", [_source_ref(decl_batch, decl_record)])
            continue
        responses = {(r["values"].get("certification_status"), r["values"].get("certificate_specialty"), r["values"].get("board_code")) for _, r in accepted}
        if len(responses) > 1:
            element.note("conflicting_certification_replies", f"Admissible replies conflict for declaration {declaration_id!r}; both are retained.", [_source_ref(b, r) for b, r in accepted])
        for rb, rr in accepted:
            rv = rr["values"]
            if str(rv.get("certification_status") or "").casefold() == "not certified":
                element.note("declared_certification_not_confirmed", f"Board reply does not confirm declared certification {declaration_id!r}.", [_source_ref(decl_batch, decl_record), _source_ref(rb, rr)])
            verified.append((rb, rr, dv))

    requests = [
        (b, r) for b, r in rows
        if r.get("filename") == "privilege-requests.csv"
        and r.get("values", {}).get("application_id") == application_id
        and r.get("values", {}).get("revision") == revision
    ]
    requested_codes = []
    for b, r in requests:
        element.cite(b, r)
        requested_codes.append(str(r["values"].get("privilege_code") or ""))
    if not requested_codes:
        element.note("no_privilege_request", "No privilege group is recorded for this revision; support cannot be evaluated.", element.evidence)
        return

    support: dict[str, str] = {}
    for code in requested_codes:
        criteria = PRIVILEGES.get(code)
        if not criteria:
            support[code] = "unknown"
            element.note("unknown_privilege_code", f"Privilege code {code!r} is absent from the published criteria table.", [_source_ref(b, r) for b, r in requests])
            continue
        code_supported = False
        accreditation_missing = False
        for rb, rr, declaration in verified:
            cert = rr["values"]
            board = str(cert.get("board_code") or "").upper()
            specialty = str(cert.get("certificate_specialty") or "")
            allowed_specialties = criteria["boards"].get(board, set())
            status = str(cert.get("certification_status") or "").casefold()
            cert_expiry = _parse_date(cert.get("expiry_date"))
            active = status == "active" and (cert_expiry is None or cert_expiry >= as_of)
            if status == "active" and cert_expiry is not None and cert_expiry < as_of:
                element.note("certificate_expired_no_support", f"Certification {declaration.get('declaration_id')!r} has an expiry date before the export date and supports no requested group.", [
                    _source_ref(rb, rr),
                ])
            eligible = status in {"board eligible", "eligible"}
            if specialty not in allowed_specialties:
                continue
            if not active:
                eligible_allowed = code in {"PRIV-FM", "PRIV-IM", "PRIV-HOSP", "PRIV-PED"}
                expiry = cert_expiry
                notes = str(cert.get("notes") or "").casefold()
                if not (eligible and eligible_allowed and "good standing" in notes and expiry is not None and expiry > as_of):
                    continue
            # PRIV-HOSP accepts either a qualifying internal-medicine or
            # family-medicine residency. Other groups list cumulative training
            # requirements (not alternatives), notably PRIV-CARD.
            if code == "PRIV-HOSP":
                alternatives = [
                    _training_support([requirement], history, rows, application_id, first_received, as_of, docs)
                    for requirement in criteria["training"]
                ]
                training_ok = any(result[0] for result in alternatives)
                training_evidence = [ref for result in alternatives for ref in result[1]]
                training_accreditation_missing = any(result[2] for result in alternatives) and not training_ok
            else:
                training_ok, training_evidence, training_accreditation_missing = _training_support(
                    criteria["training"], history, rows, application_id, first_received, as_of, docs
                )
            accreditation_missing = accreditation_missing or training_accreditation_missing
            if training_ok:
                code_supported = True
                element.cite(rb, rr)
                for ref in training_evidence:
                    if ref not in element.evidence:
                        element.evidence.append(ref)
                break
        if code_supported:
            support[code] = "supported"
        elif accreditation_missing:
            support[code] = "not-established"
        else:
            support[code] = "unsupported-on-verified-evidence"

    element.observations.append({
        "code": "privilege_support_map",
        "message": "Group support is mapped from verified certification, published board/specialty criteria, and verified training only; current competency is not evaluated.",
        "support_by_privilege": support,
        "evidence": element.evidence.copy(),
    })
    supported = [code for code, value in support.items() if value == "supported"]
    unresolved_verification = bool(element.problems.intersection({
        "certification_verification_outstanding", "inadmissible_certification_source", "unusable_certification_date"
    }))
    if not supported and (any(value == "not-established" for value in support.values()) or unresolved_verification):
        element.note("privilege_support_not_established", "Required degree accreditation, training verification, or programme accreditation is not established by the available source fields.", element.evidence)
        element.problems.add("outstanding")
    elif not supported:
        element.note("threshold_eligibility_question", "No requested group is established as supported by verified evidence at this export date; this raises the documented eligibility question and does not decide it.", element.evidence)
        element.problems.add("eligibility-question")
    elif any(value == "unsupported-on-verified-evidence" for value in support.values()):
        element.note("unsupported_requested_privilege", "One or more requested privilege groups are unsupported on verified evidence; retain the named subset.", element.evidence)
    elif any(value == "not-established" for value in support.values()):
        element.note("privilege_support_not_established", "Required degree accreditation, training verification, or programme accreditation is not established by the available source fields.", element.evidence)
        element.problems.add("outstanding")


def _reference_element(
    element: _Element, rows: list[tuple[dict[str, Any], dict[str, Any]]], app: dict[str, Any],
    application_id: str, revision: str, as_of: date,
) -> None:
    try:
        current_revision = int(revision)
    except (TypeError, ValueError):
        current_revision = None
    referees = [
        (b, r) for b, r in rows
        if r.get("filename") == "peer-referees.csv"
        and r.get("values", {}).get("application_id") == application_id
        # Referee nominations are event records, not repeated revision data.
        # Keep earlier nominations available to later revisions; the procedure
        # permits unaffected verifications to carry forward, subject to the
        # reference currency and eligibility checks below.
        and (
            str(r.get("values", {}).get("revision")) == str(revision)
            if current_revision is None
            else (str(r.get("values", {}).get("revision", "")).isdigit()
                  and int(r["values"]["revision"]) <= current_revision)
        )
    ]
    replies = [
        (b, r) for b, r in rows
        if r.get("filename") == "peer-reference-replies.csv"
        and r.get("values", {}).get("application_id") == application_id
    ]
    for b, r in referees:
        element.cite(b, r)
    discipline = str(app.get("discipline") or "").strip().casefold()
    cutoff = _subtract_years(as_of, 2)
    valid_count = 0
    for referee_batch, referee_record in referees:
        referee = referee_record["values"]
        referee_id = str(referee.get("referee_id") or "")
        matching = [(b, r) for b, r in replies if r["values"].get("referee_id") == referee_id]
        if not matching:
            element.note("reference_outstanding", f"No returned reference is recorded for referee {referee_id!r}.", [_source_ref(referee_batch, referee_record)])
            continue
        for reply_batch, reply_record in matching:
            reply = reply_record["values"]
            element.cite(reply_batch, reply_record)
            signature = _parse_date(reply.get("signature_date"))
            received = _parse_date(reply.get("received_date"))
            if not signature or not received or received > as_of or signature > as_of:
                element.note("reference_date_unusable", f"Reference {referee_id!r} has missing or future signature/received date.", [_source_ref(reply_batch, reply_record)])
                continue
            reasons = []
            last_work = _parse_date(reply.get("last_worked_together_end"))
            if last_work is not None and last_work < _subtract_years(signature, 2):
                reasons.append("direct work ended more than two years before signature")
            stated_discipline = str(reply.get("referee_specialty_stated") or "").strip().casefold()
            if not stated_discipline or stated_discipline != discipline:
                reasons.append("referee discipline does not match the applicant's declared discipline")
            related = str(reply.get("related_or_partner") or "").strip().casefold()
            if related not in {"no", "false"}:
                reasons.append("relationship exclusion is not affirmatively cleared")
            if signature < cutoff:
                reasons.append("signature is older than two years at this export date")
            if reasons:
                element.note("reference_not_countable", f"Reference {referee_id!r} is not countable: " + "; ".join(reasons) + ".", [
                    _source_ref(referee_batch, referee_record), _source_ref(reply_batch, reply_record)
                ])
                continue
            valid_count += 1
    if valid_count >= 2:
        element.observations.append({
            "code": "two_qualifying_current_references",
            "message": f"{valid_count} references satisfy the recorded date, discipline, and relationship checks as of {as_of.isoformat()}.",
            "evidence": element.evidence.copy(),
        })
        element.observations.append({
            "code": "reference_channel_unverified",
            "message": SOURCE_LIMITATIONS[0],
            "evidence": element.evidence.copy(),
        })
        # The written form requires direct return. Since the export has no
        # channel field, qualifying dates/content alone cannot clear the check.
        element.problems.add("reference_channel_unverified")
    else:
        element.note("two_references_not_established", f"Only {valid_count} references are established as qualifying and current; at least two are required.", element.evidence)
        element.problems.add("outstanding")


def evaluate_application(
    ledger: dict[str, Any], application_id: str, revision: str | int, export_date: str | date
) -> dict[str, Any]:
    """Evaluate the six element states for a specific revision as of an export date."""
    as_of = export_date if isinstance(export_date, date) else _parse_date(export_date)
    if as_of is None:
        raise ValueError("export_date must be a valid YYYY-MM-DD date")
    revision = str(revision)
    rows = _row_records(ledger, as_of)
    app_rows = [
        (b, r) for b, r in rows
        if r.get("filename") == "applications.csv"
        and r.get("values", {}).get("application_id") == application_id
        and str(r.get("values", {}).get("revision")) == revision
    ]
    if not app_rows:
        raise ValueError(f"Application revision {application_id}/{revision} is not present on or before {as_of.isoformat()}")
    app = app_rows[-1][1]["values"]
    first_received_rows = [
        (b, r) for b, r in rows
        if r.get("filename") == "applications.csv"
        and r.get("values", {}).get("application_id") == application_id
        and str(r.get("values", {}).get("revision")) == "1"
    ]
    first_received = _parse_date(first_received_rows[0][1]["values"].get("first_received_date")) if first_received_rows else None
    first_received = first_received or _parse_date(app.get("first_received_date"))
    if first_received is None:
        raise ValueError(f"First-received date is unavailable for {application_id}")

    docs = _doc_index(ledger, as_of, application_id)
    elements = {name: _Element(name) for name in ("licensure", "experience", "gaps", "education", "certification", "references")}
    for batch, record in app_rows:
        for name in elements:
            elements[name].cite(batch, record)

    _license_element(elements["licensure"], rows, app, application_id, revision, as_of, docs)
    _education_experience_elements(elements, rows, app, application_id, revision, as_of, first_received, docs)
    history = [
        (b, r) for b, r in rows
        if r.get("filename") == "declared-history.csv"
        and r.get("values", {}).get("application_id") == application_id
        and r.get("values", {}).get("revision") == revision
    ]
    _gaps_element(elements["gaps"], history, docs, as_of)
    _certification_element(elements["certification"], rows, app, application_id, revision, first_received, as_of, docs)
    _reference_element(elements["references"], rows, app, application_id, revision, as_of)

    details = {name: element.finish() for name, element in elements.items()}
    return {
        "application_id": application_id,
        "revision": int(revision) if revision.isdigit() else revision,
        "as_of": as_of.isoformat(),
        "elements": {name: details[name]["state"] for name in details},
        "element_details": details,
        "assumptions": [
            "For an undecided file, export_date is used as the reference date for evidence known/current at that export; this is not a committee decision date.",
            "A peer-reference row in peer-reference-replies.csv is treated as a returned office record for eligibility calculations, but the unexported return channel is reported as a limitation.",
        ],
        "unresolved_policy_questions": SOURCE_LIMITATIONS,
    }
