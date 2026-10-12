"""Packet readiness, recorded-decision admission, and activation.

This layer consumes the Stage 3 evaluator and recorded source documents. It
never creates a human disposition or committee outcome.
"""
from __future__ import annotations

import calendar
import re
from datetime import date, timedelta
from typing import Any

from .evaluation import evaluate_application, _parse_date, _row_records, _source_ref


POLICY = {
    "readiness": ["office/procedure-extract.txt § 8 — Packet readiness", "office/procedure-extract.txt § 4 — High-risk findings"],
    "decisions": ["office/procedure-extract.txt § 9 — The committee protocol", "office/authority-roster.txt — Who may record what; Individual authority"],
    "activation": ["office/procedure-extract.txt § 10 — Activation and the appointment cycle", "office/procedure-extract.txt § 11 — Re-entry"],
}

LIMITATIONS = [
    "Stage 3 evidence limitations remain: reference delivery channel is absent from exports; accreditation status is not supplied; acceptable verifiers for teaching and military history are undefined.",
    "This implementation does not determine intake completeness, clinical competency, whether a finding is disqualifying, whether a gap explanation is satisfactory, or whether appointment should be recommended or granted.",
    "Condition completion is recognized only when a recorded source explicitly names the condition; no completion is inferred from unrelated evidence.",
    "Conditional-approval condition extraction recognizes explicit '... due YYYY-MM-DD' phrases in the recorded reason. Other condition wording is retained in decision details but cannot be converted to the schema's condition-and-date pair without an explicit structured source field.",
]

_ROLES = {
    "Chair, Governing Body": ("Ms. Corinne Batiste", date(2025, 1, 1), date(2027, 12, 31)),
    "Vice-Chair, Governing Body": ("Mr. Desmond Ihejirika", date(2026, 1, 1), date(2026, 12, 31)),
    "Chair, Executive Committee of the Medical Staff": ("Dr. Peter Vandermolen, MD", date(2026, 1, 1), date(2027, 12, 31)),
    "Chair, Credentials Committee": ("Dr. Anneke Thorvald, MD", date(2025, 7, 1), date(2027, 6, 30)),
}
_BODY_OUTCOMES = {
    "Credentials Committee": {"recommended", "not recommended", "deferred-pending-information"},
    "Executive Committee of the Medical Staff": {"recommended", "not recommended", "deferred-pending-information"},
    "Governing Body": {"approved", "approved-with-conditions", "deferred-pending-information", "denied"},
}
_NONBLOCKING_OBSERVATIONS = {
    # These describe evidence already established or a certification finding
    # limited to an unsupported subset. The procedure permits such a finding
    # to travel with a presentable packet; it is not an open verification hold.
    "gap_explained",
    "privilege_support_map",
    "two_qualifying_current_references",
    "unsupported_requested_privilege",
}


def _fields(markdown: str) -> dict[str, str]:
    return {k.strip().casefold(): v.strip() for k, v in re.findall(r"^\*\*([^*]+):\*\*[ \t]*(.*?)[ \t]*$", markdown, re.M)}


def _document_ref(batch: dict[str, Any], doc: dict[str, Any]) -> dict[str, Any]:
    return {"batch_id": batch.get("batch_id"), "document_path": doc.get("path"), "sha256": doc.get("sha256")}


def _app_revision_exists(ledger: dict[str, Any], app_id: str, revision: str, on: date) -> bool:
    # A later closed export can carry an application/revision that was already
    # on file on the decision date. Use its source received_date, not the date
    # the batch was published.
    for batch in ledger.get("batches", []):
        for record in batch.get("records", []):
            values = record.get("values", {})
            received = _parse_date(values.get("received_date"))
            if (record.get("filename") == "applications.csv"
                    and str(values.get("application_id")) == app_id
                    and str(values.get("revision")) == revision
                    and received is not None and received <= on):
                return True
    return False


def _historical_evidence_view(ledger: dict[str, Any], as_of: date) -> dict[str, Any]:
    """Expose later-exported rows to date-aware evaluators for historical checks.

    The evaluator still applies each source's event dates and document dates;
    lowering only the enclosing batch cutoff avoids confusing publication date
    with when a row or document took effect.
    """
    view = dict(ledger)
    view["batches"] = []
    for batch in ledger.get("batches", []):
        copy = dict(batch)
        if (_parse_date(copy.get("export_date")) or date.max) > as_of:
            copy["export_date"] = as_of.isoformat()
        view["batches"].append(copy)
    return view


def _predecision_readiness(ledger: dict[str, Any], app_id: str, revision: str, decision_date: date) -> dict[str, Any]:
    """Apply the ordinary before-decision window plus the WA lookup exception."""
    prior_date = decision_date - timedelta(days=1)
    prior = assess_packet_readiness(_historical_evidence_view(ledger, prior_date), app_id, revision, prior_date.isoformat())
    day_rows = _historical_evidence_view(ledger, decision_date)
    same_day_wa_lookup = any(
        record.get("filename") == "licence-lookup-wa.csv"
        and _parse_date(record.get("values", {}).get("lookup_date")) == decision_date
        and str(record.get("values", {}).get("lastname", "")).casefold()
        for batch in day_rows.get("batches", []) for record in batch.get("records", [])
    )
    if not same_day_wa_lookup:
        return prior
    on_day = assess_packet_readiness(day_rows, app_id, revision, decision_date.isoformat())
    # Only the licensure component may use decision-day evidence. All other
    # elements remain fixed to the end of the preceding day.
    prior["blockers"] = [b for b in prior.get("blockers", []) if b.get("element") != "licensure"] + [
        b for b in on_day.get("blockers", []) if b.get("element") == "licensure"
    ]
    prior["cleared_holds"] = [h for h in prior.get("cleared_holds", []) if h.get("element") != "licensure"] + [
        h for h in on_day.get("cleared_holds", []) if h.get("element") == "licensure"
    ]
    prior["elements"]["licensure"] = on_day.get("elements", {}).get("licensure", prior["elements"].get("licensure"))
    prior["presentable"] = not prior["blockers"]
    return prior


def _dispositions(ledger: dict[str, Any], app_id: str, revision: str, as_of: date) -> list[dict[str, Any]]:
    found = []
    for batch in ledger.get("batches", []):
        if (_parse_date(batch.get("export_date")) or date.max) > as_of:
            continue
        for doc in batch.get("documents", []):
            path, content = doc.get("path", ""), doc.get("content", "")
            if "/dispositions/" not in f"/{path}" or not content:
                continue
            f = _fields(content)
            aid = f.get("application", "")
            rev = f.get("revision", revision)
            actor = f.get("recorded by", "")
            if aid == app_id and str(rev) == str(revision) and actor.startswith("Dr. Marguerite Oyelaran") and "Clinical Director" in actor:
                date_match = _parse_date(f.get("date"))
                if date_match and date_match <= as_of:
                    found.append({"fields": f, "content": content, "ref": _document_ref(batch, doc), "date": date_match})
    return found


def assess_packet_readiness(ledger: dict[str, Any], application_id: str, revision: int | str, as_of: str) -> dict[str, Any]:
    """Assess six-element readiness as of a date, with authorized dispositions."""
    day = _parse_date(as_of)
    if day is None:
        raise ValueError("as_of must be an ISO calendar date")
    ev = evaluate_application(ledger, application_id, revision, as_of)
    dispositions = _dispositions(ledger, application_id, str(revision), day)
    cleared: list[dict[str, Any]] = []
    blockers: list[dict[str, Any]] = []
    nonblocking_findings: list[dict[str, Any]] = []
    for name, detail in ev["element_details"].items():
        state = detail["state"]
        obs = detail.get("observations", [])
        for finding in obs:
            code = finding.get("code", "")
            if code in _NONBLOCKING_OBSERVATIONS:
                nonblocking_findings.append({"element": name, **finding, "rule_refs": POLICY["readiness"]})
                continue
            if code in {"licensure_finding", "gap_disposition_pending", "high_risk_finding"}:
                matching = [d for d in dispositions if
                            (code != "gap_disposition_pending" or "gap" in d["content"].casefold()) and
                            (code != "licensure_finding" or "licens" in d["content"].casefold())]
                if matching:
                    cleared.append({"element": name, "finding_code": code, "disposition": matching[-1]["ref"], "rule_refs": POLICY["readiness"]})
                    continue
                blockers.append({"element": name, "code": code, "message": finding.get("message", "Required disposition is missing."), "evidence": finding.get("evidence", detail.get("evidence", [])), "rule_refs": POLICY["readiness"]})
            elif state != "resolved":
                blockers.append({"element": name, "code": code or state, "message": finding.get("message", f"Element state is {state}."), "evidence": finding.get("evidence", detail.get("evidence", [])), "rule_refs": POLICY["readiness"]})
        # No observations for a non-resolved state still constitutes blocking work.
        if state != "resolved" and not obs:
            blockers.append({"element": name, "code": state, "message": f"Element state is {state}.", "evidence": detail.get("evidence", []), "rule_refs": POLICY["readiness"]})
    # High-risk disclosure evidence is outside the six element states.
    for batch, record in _row_records(ledger, day):
        v = record.get("values", {})
        if record.get("filename") == "application-disclosures.csv" and v.get("application_id") == application_id and str(v.get("revision")) == str(revision) and str(v.get("answer", "")).casefold() == "yes":
            refs = [_source_ref(batch, record)]
            matching = [d for d in dispositions if "high-risk" in d["content"].casefold()]
            if not matching:
                blockers.append({"element": "high-risk", "code": "high_risk_disposition_pending", "message": "High-risk disclosure awaits a Clinical Director disposition.", "evidence": refs, "rule_refs": POLICY["readiness"]})
            else:
                cleared.append({"element": "high-risk", "finding_code": "high_risk_finding", "disposition": matching[-1]["ref"], "evidence": refs, "rule_refs": POLICY["readiness"]})
    return {"application_id": application_id, "revision": int(revision), "as_of": as_of,
            "presentable": not blockers, "elements": ev["elements"], "blockers": blockers,
            "cleared_holds": cleared, "nonblocking_findings": nonblocking_findings,
            "evaluation": ev, "rule_refs": POLICY["readiness"],
            "limitations": LIMITATIONS}


def _parse_decisions(ledger: dict[str, Any], as_of: date) -> list[dict[str, Any]]:
    out = []
    for batch in ledger.get("batches", []):
        if (_parse_date(batch.get("export_date")) or date.max) > as_of:
            continue
        for doc in batch.get("documents", []):
            path, content = doc.get("path", ""), doc.get("content", "")
            if "/decisions/" not in f"/{path}" or not content:
                continue
            f = _fields(content)
            if not f.get("decision id"):
                continue
            f["__ref"] = _document_ref(batch, doc)
            f["__content"] = content
            out.append(f)
    return out


def _decision_conditions(d: dict[str, Any]) -> list[dict[str, str]]:
    """Read explicitly listed condition/due pairs from a decision record."""
    content = d.get("__content", "")
    section = re.search(r"^\*\*Conditions:\*\*[ \t]*\r?\n(.*?)(?=^##\s|\Z)", content, re.M | re.S)
    lines = section.group(1).splitlines() if section else []
    result = []
    for line in lines:
        item = re.match(r"\s*[-*]\s+(.+?)\s+[—–-]\s+due\s+(\d{4}-\d{2}-\d{2})\s*$", line, re.I)
        if item and _parse_date(item.group(2)):
            result.append({"condition": item.group(1).strip(), "due": item.group(2)})
    # Older records may place a single explicit due-dated condition in Reason.
    if not result:
        for item in (d.get("reason") or "").split(";"):
            match = re.match(r"\s*(.*?)\s+due\s+(\d{4}-\d{2}-\d{2})\s*$", item, re.I)
            if match and _parse_date(match.group(2)):
                result.append({"condition": match.group(1).strip(), "due": match.group(2)})
    return result


def _terminal_status(ledger: dict[str, Any], app_id: str, as_of: date) -> tuple[str | None, dict[str, Any] | None]:
    """Find explicit applicant withdrawal or roster-authorized discontinuance."""
    for batch in ledger.get("batches", []):
        if (_parse_date(batch.get("export_date")) or date.max) > as_of:
            continue
        for doc in batch.get("documents", []):
            path, content = doc.get("path", ""), doc.get("content", "")
            if not content:
                continue
            fields = _fields(content)
            if fields.get("application") != app_id:
                continue
            if "/letters/" in f"/{path}" and re.search(r"\bI am withdrawing my application\b", content, re.I):
                when = _parse_date(fields.get("date"))
                if when and when <= as_of:
                    return "withdrawn", _document_ref(batch, doc)
    for disposition in _dispositions(ledger, app_id, "1", as_of):
        content = disposition["content"]
        if re.search(r"\bDiscontinue the application\b", content, re.I) and not re.search(r"\bDo not discontinue the application\b", content, re.I):
            return "discontinued", disposition["ref"]
    return None, None


def _cycle_end(effective: date) -> date:
    year = effective.year + 1
    anniversary = effective.replace(year=year, day=min(effective.day, calendar.monthrange(year, effective.month)[1]))
    return anniversary - timedelta(days=1)


def _admit_decision(ledger: dict[str, Any], d: dict[str, Any], target_app: str, target_rev: str, readiness_cache: dict[tuple[str, str, str], dict[str, Any]]) -> tuple[bool, str | None]:
    decision_date = _parse_date(d.get("decision date"))
    app_id, rev, body = d.get("application", ""), d.get("revision", ""), d.get("body", "")
    outcome = d.get("outcome", "").casefold()
    role, signatory = d.get("role", ""), d.get("signatory", "")
    if body not in _BODY_OUTCOMES or outcome not in _BODY_OUTCOMES.get(body, set()): return False, "body-or-outcome-not-authorized"
    if decision_date is None: return False, "invalid-decision-date"
    if body == "Governing Body":
        authorized = signatory == "Ms. Corinne Batiste" and role == "Chair, Governing Body"
        authorized |= (signatory == "Mr. Desmond Ihejirika" and role == "Vice-Chair, Governing Body" and date(2026,1,5) <= decision_date <= date(2026,12,31))
    else:
        expected = _ROLES.get(role)
        authorized = bool(expected and expected[0] == signatory and expected[1] <= decision_date <= expected[2] and
                          ((body == "Executive Committee of the Medical Staff" and role == "Chair, Executive Committee of the Medical Staff") or (body == "Credentials Committee" and role == "Chair, Credentials Committee")))
    if not authorized: return False, "signatory-not-authorized-on-decision-date"
    if not app_id or not rev or not _app_revision_exists(ledger, app_id, rev, decision_date): return False, "application-revision-not-on-file"
    if app_id != target_app: return False, "decision-names-different-application"
    # The record must have a presentable packet before its decision date.
    prior_day = decision_date - timedelta(days=1)
    key = (app_id, str(rev), decision_date.isoformat())
    if key not in readiness_cache:
        readiness_cache[key] = _predecision_readiness(ledger, app_id, rev, decision_date)
    if not readiness_cache[key]["presentable"]: return False, "packet-not-presentable-before-decision-date"
    if outcome not in {"approved", "approved-with-conditions", "deferred-pending-information", "denied", "recommended", "not recommended"}: return False, "invalid-outcome"
    reason_required = outcome in {"approved-with-conditions", "deferred-pending-information", "denied", "not recommended"}
    if reason_required and not d.get("reason"): return False, "required-reason-missing"
    if outcome == "deferred-pending-information" and not d.get("reason"): return False, "deferral-information-not-named"
    if body == "Governing Body" and outcome in {"approved", "approved-with-conditions", "denied", "deferred-pending-information"}:
        received = _parse_decisions(ledger, decision_date)
        earlier = []
        for item in received:
            if item.get("decision id") == d.get("decision id"):
                break
            if item.get("application") == app_id and item.get("revision") == rev and item.get("body") == "Governing Body":
                earlier.append(item)
        if earlier and d.get("supersedes") != earlier[-1].get("decision id"): return False, "second-governing-body-decision-must-supersede-earlier"
    return True, None


def process_recorded_decisions(ledger: dict[str, Any], application_id: str, revision: int | str, as_of: str) -> dict[str, Any]:
    """Return the schema-compatible decision/activation fragment and audit detail."""
    day = _parse_date(as_of)
    if day is None: raise ValueError("as_of must be an ISO calendar date")
    rev = str(revision)
    docs = [d for d in _parse_decisions(ledger, day) if d.get("application") == application_id]
    cache: dict[tuple[str, str, str], dict[str, Any]] = {}
    records, details = [], []
    admitted = []
    for d in docs:
        ok, reason = _admit_decision(ledger, d, application_id, rev, cache)
        records.append({"decision_id": d["decision id"], "admitted": ok, "reason": None if ok else reason})
        details.append({"decision_id": d["decision id"], "application_id": d.get("application"), "revision": d.get("revision"), "body": d.get("body"), "signatory": d.get("signatory"), "role": d.get("role"), "decision_date": d.get("decision date"), "outcome": d.get("outcome"), "reason": d.get("reason") or None, "conditions": _decision_conditions(d), "supersedes": d.get("supersedes") or None, "source": d["__ref"], "admitted": ok, "admission_reason": reason, "rule_refs": POLICY["decisions"]})
        if ok and str(d.get("revision")) == rev: admitted.append(d)
    # An admitted decision remains valid history for the revision it names,
    # but it cannot authorize a later application revision.
    governing = [d for d in admitted if d.get("body") == "Governing Body" and str(d.get("revision")) == rev]
    governing.sort(key=lambda d: (_parse_date(d.get("decision date")) or date.min, d["decision id"]))
    final = governing[-1] if governing else None
    approval_id = None
    activation = None
    conditions = []
    condition_details = []
    readiness = assess_packet_readiness(ledger, application_id, revision, as_of)
    status = "decision-inadmissible" if any(not r["admitted"] for r in records) else ("packet-presentable" if readiness["presentable"] else "in-verification")
    if final:
        out = final.get("outcome", "").casefold()
        if out == "deferred-pending-information": status = "deferred"
        elif out == "denied": status = "denied"
        elif out in {"approved", "approved-with-conditions"}:
            approval_id = final["decision id"]
            effective = _parse_date(final.get("effective date")) or _parse_date(final.get("decision date"))
            cycle_end = _cycle_end(effective)
            privileges = sorted({p.strip() for p in final.get("privileges", "").split(";") if p.strip()})
            active = effective <= day and day <= cycle_end and bool(privileges)
            activation = {"active_at_export": active, "effective_date": effective.isoformat(), "cycle_end": cycle_end.isoformat(), "privileges": privileges}
            if not active: status = "approved-not-yet-effective" if day < effective else "in-verification"
            elif out == "approved-with-conditions": status = "active-with-conditions"
            else: status = "active"
            if out == "approved-with-conditions":
                for condition in _decision_conditions(final):
                    conditions.append(condition)
                    condition_details.append({**condition, "source": final["__ref"], "rule_refs": POLICY["activation"]})
            # Licensure expiring within this cycle is monitored independently
            # of any conditions attached by the Governing Body.
            license_detail = readiness.get("evaluation", {}).get("element_details", {}).get("licensure", {})
            refs = license_detail.get("evidence", [])
            ref_keys = {(r.get("batch_id"), r.get("filename"), r.get("row_number")) for r in refs}
            for batch in ledger.get("batches", []):
                for record in batch.get("records", []):
                    ident = (batch.get("batch_id"), record.get("filename"), record.get("row_number"))
                    if ident not in ref_keys or record.get("filename") != "licence-lookup-wa.csv":
                        continue
                    expiry = _parse_date(record.get("values", {}).get("expirationdate"))
                    if expiry and effective <= expiry <= cycle_end:
                        condition = {"condition": "Re-verify Washington licence before expiry; due date records the licence expiry.", "due": expiry.isoformat()}
                        if condition not in conditions:
                            conditions.append(condition)
                            condition_details.append({**condition, "source": _source_ref(batch, record), "rule_refs": POLICY["activation"]})
    terminal, terminal_source = _terminal_status(ledger, application_id, day)
    if terminal:
        status = terminal
    action_queue = [
        {"item": f"Resolve {b['element']} readiness blocker: {b['message']}", "owner": "Medical Staff Office", "due": None}
        for b in readiness.get("blockers", [])
    ]
    if final and final.get("outcome", "").casefold() == "deferred-pending-information":
        action_queue.append({"item": f"Obtain information named in deferral: {final.get('reason', '')}", "owner": "Medical Staff Office", "due": None})
    return {"application_id": application_id, "revision": int(revision), "as_of": as_of,
            "schema_compatible": {"status": status, "elements": readiness["elements"], "packet_presentable": readiness["presentable"], "decisions": records, "approval_decision_id": approval_id, "activation": activation, "monitored_conditions": conditions, "action_queue": action_queue},
            "readiness": readiness, "decision_details": details,
            "terminal_source": terminal_source,
            "condition_sources": condition_details,
            "rule_refs": {**POLICY}, "limitations": LIMITATIONS}
