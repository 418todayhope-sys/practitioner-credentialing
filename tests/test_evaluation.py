from datetime import date
import unittest

from credentialing.evaluation import (
    _Element,
    _gaps_element,
    _reference_element,
    evaluate_application,
)


def record(filename, values, row=2):
    return {"filename": filename, "row_number": row, "stable_key": f"{filename}:{row}", "values": values}


def ledger(records, export_date="2026-05-18"):
    return {
        "ledger_version": "credentialing-evidence-ledger/1",
        "batches": [{
            "batch_id": "batch-01-2026-05-18", "batch_number": 1,
            "export_date": export_date, "records": records, "documents": [],
        }],
    }


def app_record():
    return record("applications.csv", {
        "application_id": "APP-1", "revision": "1", "first_received_date": "2026-01-01",
        "last_name": "Example", "first_name": "Alex", "middle_name": "Q", "birth_year": "1980",
        "discipline": "Internal Medicine",
    })


class EvaluationTests(unittest.TestCase):
  def test_licensure_restriction_maps_to_persistent_finding(self):
    element = _Element("licensure")
    element.note("licensure_finding", "Board evidence records a restriction.")
    self.assertEqual(element.finish()["state"], "finding")

  def test_certification_disagreement_remains_a_discrepancy(self):
    element = _Element("certification")
    element.note("declared_certification_not_confirmed", "The declaration and board reply disagree.")
    self.assertEqual(element.finish()["state"], "discrepancy")

  def test_missing_evidence_returns_schema_states_and_citations(self):
    result = evaluate_application(ledger([app_record()]), "APP-1", 1, "2026-05-18")
    self.assertEqual(set(result["elements"]), {"licensure", "experience", "gaps", "education", "certification", "references"})
    allowed = {"resolved", "outstanding", "finding", "discrepancy", "return-incomplete", "routed-to-clinical-director", "eligibility-question"}
    self.assertLessEqual(set(result["elements"].values()), allowed)
    self.assertTrue(all(detail["evidence"] for detail in result["element_details"].values()))
    self.assertEqual(result["elements"]["licensure"], "finding")
    self.assertEqual(result["elements"]["experience"], "outstanding")

  def test_washington_expiry_day_is_valid_and_action_yes_is_not_a_finding(self):
    app = app_record()
    declaration = record("declared-credentials.csv", {
        "application_id": "APP-1", "revision": "1", "declaration_id": "L1",
        "credential_class": "licence", "jurisdiction_or_board": "WA", "number_declared": "WA123",
    })
    lookup = record("licence-lookup-wa.csv", {
        "lastname": "Example", "firstname": "Alex", "middlename": "Q", "birthyear": "1980",
        "credentialnumber": "WA123", "status": "Active", "expirationdate": "2026-05-18",
        "actiontaken": "Yes", "lookup_date": "2026-05-18",
    })
    result = evaluate_application(ledger([app, declaration, lookup]), "APP-1", 1, "2026-05-18")
    detail = result["element_details"]["licensure"]
    self.assertEqual(detail["state"], "outstanding")
    self.assertTrue(any(o["code"] == "board_action_requires_detail" for o in detail["observations"]))
    self.assertFalse(any(o["code"] == "licensure_finding" for o in detail["observations"]))

  def test_authoritative_board_action_detail_replaces_missing_detail_hold(self):
    app = app_record()
    declaration = record("declared-credentials.csv", {
        "application_id": "APP-1", "revision": "1", "declaration_id": "L1",
        "credential_class": "licence", "jurisdiction_or_board": "WA", "number_declared": "WA123",
    })
    lookup = record("licence-lookup-wa.csv", {
        "lastname": "Example", "firstname": "Alex", "middlename": "Q", "birthyear": "1980",
        "credentialnumber": "WA123", "status": "Active", "expirationdate": "2027-05-18",
        "actiontaken": "Yes", "lookup_date": "2026-05-18",
    })
    correspondence = record("correspondence.csv", {
        "application_id": "APP-1", "letter_id": "L-1", "document_path": "letters/board-action.md",
    })
    data = ledger([app, declaration, lookup, correspondence])
    data["batches"][0]["documents"] = [{"path": "letters/board-action.md", "content":
        "**Date:** 2026-05-01\n**From:** Washington State Department of Health\n**Application:** APP-1\n\nCredential WA123 is under a stipulated agreement and monitoring programme."}]
    result = evaluate_application(data, "APP-1", 1, "2026-05-18")
    codes = {o["code"] for o in result["element_details"]["licensure"]["observations"]}
    self.assertIn("licensure_finding", codes)
    self.assertNotIn("board_action_requires_detail", codes)

  def test_washington_expired_day_before_export_is_not_current(self):
    app = app_record()
    declaration = record("declared-credentials.csv", {
        "application_id": "APP-1", "revision": "1", "declaration_id": "L1",
        "credential_class": "licence", "jurisdiction_or_board": "WA", "number_declared": "WA123",
    })
    lookup = record("licence-lookup-wa.csv", {
        "lastname": "Example", "firstname": "Alex", "middlename": "Q", "birthyear": "1980",
        "credentialnumber": "WA123", "status": "Active", "expirationdate": "2026-05-17",
        "actiontaken": "No", "lookup_date": "2026-05-18",
    })
    result = evaluate_application(ledger([app, declaration, lookup]), "APP-1", 1, "2026-05-18")
    self.assertEqual(result["elements"]["licensure"], "finding")


  def test_inadmissible_applicant_carried_education_does_not_verify_entry(self):
    rows = [app_record(), record("declared-history.csv", {
        "application_id": "APP-1", "revision": "1", "entry_id": "ED1", "entry_type": "medical-school",
        "organization": "Example University", "from_date": "2000-08-01", "to_date": "2004-05-31",
    }), record("verification-replies.csv", {
        "application_id": "APP-1", "entry_id": "ED1", "element": "education-and-training",
        "received_from": "Applicant — hand-delivered", "received_date": "2026-02-01",
        "verified_credential": "MD", "verified_from": "2000-08-01", "verified_to": "2004-05-31", "outcome": "confirmed",
    })]
    result = evaluate_application(ledger(rows), "APP-1", 1, "2026-05-18")
    detail = result["element_details"]["education"]
    self.assertEqual(detail["state"], "outstanding")
    self.assertTrue(any(o["code"] == "inadmissible_source" for o in detail["observations"]))
    self.assertTrue(any(ref["filename"] == "verification-replies.csv" and ref["row_number"] == 2 for ref in detail["evidence"]))


  def test_conflicting_admissible_verification_is_preserved_as_discrepancy(self):
    base = {
        "application_id": "APP-1", "entry_id": "ED1", "element": "education-and-training",
        "received_from": "Registrar's office — Example University", "received_date": "2026-02-01",
        "verified_credential": "MD", "verified_from": "2000-08-01", "verified_to": "2004-05-31", "outcome": "confirmed",
    }
    rows = [app_record(), record("declared-history.csv", {
        "application_id": "APP-1", "revision": "1", "entry_id": "ED1", "entry_type": "medical-school",
        "organization": "Example University", "from_date": "2000-08-01", "to_date": "2004-05-31",
    }), record("verification-replies.csv", dict(base, reply_id="VR1"), 2),
        record("verification-replies.csv", dict(base, reply_id="VR2", verified_to="2004-06-01"), 3)]
    result = evaluate_application(ledger(rows), "APP-1", 1, "2026-05-18")
    detail = result["element_details"]["education"]
    self.assertEqual(detail["state"], "discrepancy")
    self.assertTrue(any(o["code"] == "conflicting_source_responses" for o in detail["observations"]))
    self.assertEqual({ref["row_number"] for ref in detail["evidence"] if ref["filename"] == "verification-replies.csv"}, {2, 3})

  def test_blank_source_reply_end_date_is_not_inferred_to_mean_current(self):
    rows = [app_record(), record("declared-history.csv", {
        "application_id": "APP-1", "revision": "1", "entry_id": "JOB", "entry_type": "employment",
        "organization": "Example Clinic", "role": "Staff Physician", "from_date": "2020-01-01", "to_date": "",
    }), record("verification-replies.csv", {
        "application_id": "APP-1", "entry_id": "JOB", "element": "affiliation-and-employment",
        "received_from": "Medical staff office — Example Clinic", "received_date": "2026-02-01",
        "verified_credential": "Employment — Staff Physician", "verified_from": "2020-01-01", "verified_to": "", "outcome": "confirmed",
    })]
    result = evaluate_application(ledger(rows), "APP-1", 1, "2026-05-18")
    detail = result["element_details"]["experience"]
    self.assertEqual(detail["state"], "outstanding")
    self.assertTrue(any(o["code"] == "incomplete_verification_content" for o in detail["observations"]))


  def test_gap_boundary_is_29_vs_30_inclusive_days(self):
    batch = {"batch_id": "b", "export_date": "2026-05-18"}

    def state_for(employment_start):
        school = record("declared-history.csv", {"entry_type": "medical-school", "to_date": "2025-01-31"}, 2)
        employment = record("declared-history.csv", {
            "entry_type": "employment", "from_date": employment_start, "to_date": "2026-05-18",
        }, 3)
        element = _Element("gaps")
        _gaps_element(element, [(batch, school), (batch, employment)], [], date(2026, 5, 18))
        return element.finish()

    self.assertEqual(state_for("2025-03-01")["state"], "resolved")  # Feb 1–28 = 28 uncovered days
    self.assertEqual(state_for("2025-03-02")["state"], "resolved")  # Feb 1–Mar 1 = 29 uncovered days
    self.assertEqual(state_for("2025-03-03")["state"], "return-incomplete")  # Feb 1–Mar 2 = 30 days

  def test_180_day_gap_routes_but_179_day_gap_does_not(self):
    batch = {"batch_id": "b", "export_date": "2025-07-30"}
    school = record("declared-history.csv", {"entry_type": "medical-school", "to_date": "2025-01-31"}, 2)
    at_179 = _Element("gaps")
    _gaps_element(at_179, [(batch, school)], [], date(2025, 7, 29))
    self.assertFalse(any(o["code"] == "gap_disposition_pending" for o in at_179.finish()["observations"]))
    at_180 = _Element("gaps")
    _gaps_element(at_180, [(batch, school)], [], date(2025, 7, 30))
    self.assertTrue(any(o["code"] == "gap_disposition_pending" for o in at_180.finish()["observations"]))


  def test_reference_two_year_boundaries_are_inclusive(self):
    batch = {"batch_id": "b", "export_date": "2026-05-18"}
    referees = []
    replies = []
    for i, last_worked in enumerate(("2024-05-18", "2024-05-17"), 1):
        referees.append((batch, record("peer-referees.csv", {"application_id": "APP-1", "revision": "1", "referee_id": f"R{i}"}, i + 1)))
        replies.append((batch, record("peer-reference-replies.csv", {
            "application_id": "APP-1", "referee_id": f"R{i}", "signature_date": "2026-05-18",
            "received_date": "2026-05-18", "last_worked_together_end": last_worked,
            "referee_specialty_stated": "Internal Medicine", "related_or_partner": "No",
        }, i + 5)))
    element = _Element("references")
    _reference_element(element, referees + replies, {"discipline": "Internal Medicine"}, "APP-1", "1", date(2026, 5, 18))
    detail = element.finish()
    self.assertEqual(detail["state"], "outstanding")  # only one reference meets direct-work cutoff
    self.assertTrue(any(o["code"] == "reference_not_countable" for o in detail["observations"]))


  def test_reference_signature_current_through_anniversary(self):
    batch = {"batch_id": "b", "export_date": "2026-05-18"}
    rows = []
    for i in range(2):
        rows.append((batch, record("peer-referees.csv", {
            "application_id": "APP-1", "revision": "1", "referee_id": f"R{i}"
        }, i + 2)))
        rows.append((batch, record("peer-reference-replies.csv", {
            "application_id": "APP-1", "referee_id": f"R{i}", "signature_date": "2024-05-18",
            "received_date": "2026-05-18", "last_worked_together_end": "2023-05-18",
            "referee_specialty_stated": "Internal Medicine", "related_or_partner": "No",
        }, i + 5)))
    element = _Element("references")
    _reference_element(element, rows, {"discipline": "Internal Medicine"}, "APP-1", "1", date(2026, 5, 18))
    detail = element.finish()
    self.assertEqual(detail["state"], "outstanding")
    self.assertTrue(any(o["code"] == "two_qualifying_current_references" for o in detail["observations"]))
    self.assertTrue(any(o["code"] == "reference_channel_unverified" for o in detail["observations"]))

  def test_unaffected_reference_nominations_carry_forward_to_later_revision(self):
    batch = {"batch_id": "b", "export_date": "2026-05-18"}
    rows = []
    for i in range(2):
        rows.append((batch, record("peer-referees.csv", {
            "application_id": "APP-1", "revision": "1", "referee_id": f"R{i}"
        }, i + 2)))
        rows.append((batch, record("peer-reference-replies.csv", {
            "application_id": "APP-1", "referee_id": f"R{i}", "signature_date": "2026-02-01",
            "received_date": "2026-02-02", "last_worked_together_end": "2025-01-01",
            "referee_specialty_stated": "Internal Medicine", "related_or_partner": "No",
        }, i + 5)))
    element = _Element("references")
    _reference_element(element, rows, {"discipline": "Internal Medicine"}, "APP-1", "2", date(2026, 5, 18))
    detail = element.finish()
    self.assertEqual(detail["state"], "outstanding")  # channel remains an explicit limitation
    self.assertTrue(any(o["code"] == "two_qualifying_current_references" for o in detail["observations"]))
    self.assertFalse(any(o["code"] == "two_references_not_established" for o in detail["observations"]))

  def test_hospital_privilege_accepts_either_qualifying_residency_and_requires_accreditation(self):
    rows = [app_record(),
        record("declared-history.csv", {
            "application_id": "APP-1", "revision": "1", "entry_id": "MED", "entry_type": "medical-school",
            "organization": "Example University", "role": "Doctor of Medicine", "from_date": "2006-08-01", "to_date": "2010-06-30",
        }, 2),
        record("declared-history.csv", {
            "application_id": "APP-1", "revision": "1", "entry_id": "RES", "entry_type": "residency",
            "organization": "Example Hospital", "role": "Family Medicine Residency", "from_date": "2010-07-01", "to_date": "2013-06-30",
        }, 3),
        record("verification-replies.csv", {
            "application_id": "APP-1", "entry_id": "MED", "element": "education-and-training",
            "received_from": "Registrar's office — Example University", "received_date": "2026-02-01",
            "verified_credential": "Degree — Doctor of Medicine — not accredited", "verified_from": "2006-08-01", "verified_to": "2010-06-30", "outcome": "confirmed",
        }, 2),
        record("verification-replies.csv", {
            "application_id": "APP-1", "entry_id": "RES", "element": "education-and-training",
            "received_from": "Graduate medical education office — Example Hospital", "received_date": "2026-02-02",
            "verified_credential": "Residency — Family Medicine — not accredited", "verified_from": "2010-07-01", "verified_to": "2013-06-30", "outcome": "confirmed",
        }, 3),
        record("declared-credentials.csv", {
            "application_id": "APP-1", "revision": "1", "declaration_id": "CERT", "credential_class": "certification",
            "jurisdiction_or_board": "ABFM", "number_declared": "", "issuer": "American Board of Family Medicine",
        }, 2),
        record("certification-replies.csv", {
            "application_id": "APP-1", "declaration_id": "CERT", "board_code": "ABFM", "board_name": "American Board of Family Medicine",
            "received_from": "Certifying board — American Board of Family Medicine", "certificate_specialty": "Family Medicine",
            "certification_status": "Active", "received_date": "2026-02-03", "expiry_date": "2030-12-31",
        }, 2),
        record("privilege-requests.csv", {
            "application_id": "APP-1", "revision": "1", "request_id": "REQ", "privilege_code": "PRIV-HOSP",
        }, 2)]

    without_accreditation = evaluate_application(ledger(rows), "APP-1", 1, "2026-05-18")
    cert_detail = without_accreditation["element_details"]["certification"]
    support = next(o["support_by_privilege"] for o in cert_detail["observations"] if o["code"] == "privilege_support_map")
    self.assertEqual(support["PRIV-HOSP"], "not-established")
    self.assertEqual(cert_detail["state"], "outstanding")
    self.assertEqual(without_accreditation["elements"]["education"], "outstanding")
    self.assertTrue(any(o["code"] == "accreditation_not_recorded" for o in without_accreditation["element_details"]["education"]["observations"]))

    for reply in rows:
        if reply["filename"] == "verification-replies.csv":
            reply["values"]["verified_credential"] = reply["values"]["verified_credential"].replace(" — not accredited", "") + " — accredited"
    with_accreditation = evaluate_application(ledger(rows), "APP-1", 1, "2026-05-18")
    cert_detail = with_accreditation["element_details"]["certification"]
    support = next(o["support_by_privilege"] for o in cert_detail["observations"] if o["code"] == "privilege_support_map")
    self.assertEqual(support["PRIV-HOSP"], "supported")
    self.assertEqual(cert_detail["state"], "resolved")
    self.assertEqual(with_accreditation["elements"]["education"], "resolved")

    for reply in rows:
        if reply["filename"] == "certification-replies.csv":
            reply["values"]["board_code"] = "ABIM"
    conflicting = evaluate_application(ledger(rows), "APP-1", 1, "2026-05-18")
    cert_detail = conflicting["element_details"]["certification"]
    self.assertEqual(cert_detail["state"], "discrepancy")
    self.assertTrue(any(o["code"] == "certification_identity_mismatch" for o in cert_detail["observations"]))

    for reply in rows:
        if reply["filename"] == "certification-replies.csv":
            reply["values"]["board_code"] = "ABFM"
            reply["values"]["expiry_date"] = "2020-12-31"
    expired = evaluate_application(ledger(rows), "APP-1", 1, "2026-05-18")
    cert_detail = expired["element_details"]["certification"]
    support = next(o["support_by_privilege"] for o in cert_detail["observations"] if o["code"] == "privilege_support_map")
    self.assertEqual(support["PRIV-HOSP"], "unsupported-on-verified-evidence")
    self.assertNotEqual(cert_detail["state"], "resolved")
