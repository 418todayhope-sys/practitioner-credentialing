import unittest
from unittest.mock import patch

from credentialing.readiness import _admit_decision, _decision_conditions, process_recorded_decisions


def ledger_with_decision(fields, app_date="2026-01-01"):
    content = "# Decision\n" + "\n".join(f"**{k}:** {v}  " for k, v in fields.items())
    return {"ledger_version": "credentialing-evidence-ledger/1", "batches": [{
        "batch_id": "batch-0", "export_date": "2026-05-01", "records": [
            {"filename": "applications.csv", "row_number": 2, "values": {"application_id": "APP-1", "revision": "1", "received_date": app_date, "first_received_date": app_date}}
        ], "documents": []
    }, {"batch_id": "batch-1", "export_date": "2026-05-18", "records": [], "documents": [{"path": "decisions/decision.md", "content": content, "sha256": "abc"}]}]}


def decision(**kw):
    d = {"Decision ID": "GBD-1", "Body": "Governing Body", "Signatory": "Ms. Corinne Batiste",
         "Role": "Chair, Governing Body", "Application": "APP-1", "Revision": "1",
         "Decision date": "2026-05-12", "Outcome": "approved", "Privileges": "PRIV-HOSP",
         "Reason": "", "Effective date": "2026-06-01", "Supersedes": ""}
    d.update({k.replace("_", " ").title(): v for k, v in kw.items()})
    return d


class ReadinessDecisionTests(unittest.TestCase):
    @patch("credentialing.readiness.evaluate_application")
    def test_positive_evidence_notes_and_subset_certification_finding_are_not_readiness_blockers(self, evaluate):
        states = {"licensure": "resolved", "experience": "resolved", "gaps": "resolved",
                  "education": "resolved", "certification": "finding", "references": "outstanding"}
        details = {
            name: {"state": state, "evidence": [], "observations": []}
            for name, state in states.items()
        }
        details["certification"]["observations"] = [{"code": "unsupported_requested_privilege", "message": "One requested group is unsupported."}]
        details["references"]["observations"] = [
            {"code": "two_qualifying_current_references", "message": "Two qualify."},
            {"code": "reference_channel_unverified", "message": "Return channel is not exported."},
        ]
        evaluate.return_value = {"elements": states, "element_details": details}
        from credentialing.readiness import assess_packet_readiness
        result = assess_packet_readiness({"batches": []}, "APP-1", 1, "2026-05-18")
        self.assertFalse(result["presentable"])
        self.assertEqual([b["code"] for b in result["blockers"]], ["reference_channel_unverified"])
        self.assertEqual({f["code"] for f in result["nonblocking_findings"]}, {
            "unsupported_requested_privilege", "two_qualifying_current_references"})

    @patch("credentialing.readiness.evaluate_application")
    def test_non_discontinuance_disposition_does_not_clear_unsupported_privilege_question(self, evaluate):
        states = {"licensure": "resolved", "experience": "resolved", "gaps": "resolved",
                  "education": "resolved", "certification": "eligibility-question", "references": "resolved"}
        details = {name: {"state": state, "evidence": [], "observations": []} for name, state in states.items()}
        details["certification"]["observations"] = [{"code": "threshold_eligibility_question", "message": "No requested group is supported."}]
        evaluate.return_value = {"elements": states, "element_details": details}
        ledger = {"batches": [{"batch_id": "b1", "export_date": "2026-05-18", "records": [], "documents": [{
            "path": "dispositions/no-discontinue.md", "content": "**Date:** 2026-05-01\n**Application:** APP-1\n**Recorded by:** Dr. Marguerite Oyelaran, MD, Clinical Director\n\nOffer the applicant an opportunity to amend. Do not discontinue the application."}]}]}
        from credentialing.readiness import assess_packet_readiness
        result = assess_packet_readiness(ledger, "APP-1", 1, "2026-05-18")
        self.assertFalse(result["presentable"])
        self.assertIn("threshold_eligibility_question", [b["code"] for b in result["blockers"]])

    @patch("credentialing.readiness.assess_packet_readiness")
    def test_authorized_approval_before_effective_date_is_not_active(self, ready):
        ready.return_value = {"presentable": True, "elements": {}}
        result = process_recorded_decisions(ledger_with_decision(decision()), "APP-1", 1, "2026-05-18")
        fragment = result["schema_compatible"]
        self.assertTrue(fragment["decisions"][0]["admitted"])
        self.assertEqual(fragment["status"], "approved-not-yet-effective")
        self.assertFalse(fragment["activation"]["active_at_export"])
        self.assertEqual(fragment["activation"]["effective_date"], "2026-06-01")

    @patch("credentialing.readiness.assess_packet_readiness")
    def test_admitted_approval_for_prior_revision_does_not_activate_current_revision(self, ready):
        ready.return_value = {"presentable": True, "elements": {}, "blockers": [], "cleared_holds": []}
        ledger = ledger_with_decision(decision())
        ledger["batches"][1]["records"] = [{"filename": "applications.csv", "row_number": 3, "values": {
            "application_id": "APP-1", "revision": "2", "received_date": "2026-05-13", "first_received_date": "2026-01-01"
        }}]
        result = process_recorded_decisions(ledger, "APP-1", 2, "2026-05-18")
        fragment = result["schema_compatible"]
        self.assertTrue(fragment["decisions"][0]["admitted"])  # retained as history for revision 1
        self.assertEqual(fragment["status"], "packet-presentable")
        self.assertIsNone(fragment["approval_decision_id"])
        self.assertIsNone(fragment["activation"])

    @patch("credentialing.readiness.assess_packet_readiness")
    def test_application_received_before_decision_is_not_rejected_due_to_later_export_date(self, ready):
        ready.return_value = {"presentable": True, "elements": {}}
        ledger = ledger_with_decision(decision())
        ledger["batches"][1]["records"] = ledger["batches"][0]["records"]
        ledger["batches"][0]["records"] = []
        result = process_recorded_decisions(ledger, "APP-1", 1, "2026-05-18")
        self.assertTrue(result["schema_compatible"]["decisions"][0]["admitted"])

    @patch("credentialing.readiness.assess_packet_readiness")
    def test_decision_day_washington_lookup_exception_does_not_use_other_same_day_elements(self, ready):
        ledger = ledger_with_decision(decision())
        ledger["batches"][1]["records"].append({"filename": "licence-lookup-wa.csv", "row_number": 2,
            "values": {"lastname": "Example", "lookup_date": "2026-05-12"}})
        prior = {"presentable": False, "elements": {"licensure": "outstanding", "experience": "resolved"},
                 "blockers": [{"element": "licensure", "code": "invalid_license_lookup_date"},
                              {"element": "experience", "code": "verification_outstanding"}], "cleared_holds": []}
        same_day = {"presentable": True, "elements": {"licensure": "resolved", "experience": "resolved"},
                    "blockers": [], "cleared_holds": []}
        ready.side_effect = [prior, same_day, same_day]
        result = process_recorded_decisions(ledger, "APP-1", 1, "2026-05-18")
        # Decision date is May 12, so the synthetic lookup must also be on that date.
        # The no-same-day non-licensure evidence remains a blocker.
        self.assertEqual(result["schema_compatible"]["decisions"][0]["reason"], "packet-not-presentable-before-decision-date")

    @patch("credentialing.readiness.assess_packet_readiness")
    def test_decision_day_washington_lookup_can_complete_licensure(self, ready):
        ledger = ledger_with_decision(decision())
        ledger["batches"][1]["records"].append({"filename": "licence-lookup-wa.csv", "row_number": 2,
            "values": {"lastname": "Example", "lookup_date": "2026-05-12"}})
        prior = {"presentable": False, "elements": {"licensure": "outstanding"},
                 "blockers": [{"element": "licensure", "code": "invalid_license_lookup_date"}], "cleared_holds": []}
        same_day = {"presentable": True, "elements": {"licensure": "resolved"}, "blockers": [], "cleared_holds": []}
        ready.side_effect = [prior, same_day, same_day]
        result = process_recorded_decisions(ledger, "APP-1", 1, "2026-05-18")
        self.assertTrue(result["schema_compatible"]["decisions"][0]["admitted"])

    @patch("credentialing.readiness.assess_packet_readiness")
    def test_decision_day_activation_boundary_and_one_year_cycle(self, ready):
        ready.return_value = {"presentable": True, "elements": {}}
        result = process_recorded_decisions(ledger_with_decision(decision(Effective_date="2026-05-12")), "APP-1", 1, "2026-05-18")
        self.assertTrue(result["schema_compatible"]["activation"]["active_at_export"])
        self.assertEqual(result["schema_compatible"]["activation"]["cycle_end"], "2027-05-11")

    @patch("credentialing.readiness.assess_packet_readiness")
    def test_unauthorized_signatory_and_premature_decision_are_refused(self, ready):
        ready.return_value = {"presentable": False, "elements": {}}
        bad = decision(Signatory="Not On Roster")
        result = process_recorded_decisions(ledger_with_decision(bad), "APP-1", 1, "2026-05-18")
        self.assertEqual(result["schema_compatible"]["decisions"][0]["reason"], "signatory-not-authorized-on-decision-date")
        early = process_recorded_decisions(ledger_with_decision(decision()), "APP-1", 1, "2026-05-18")
        self.assertEqual(early["schema_compatible"]["decisions"][0]["reason"], "packet-not-presentable-before-decision-date")
        self.assertIsNone(early["schema_compatible"]["activation"])

    @patch("credentialing.readiness.assess_packet_readiness")
    def test_committee_approval_claim_is_never_authorized(self, ready):
        ready.return_value = {"presentable": True, "elements": {}}
        fields = decision(Body="Credentials Committee", Signatory="Dr. Anneke Thorvald, MD", Role="Chair, Credentials Committee")
        result = process_recorded_decisions(ledger_with_decision(fields), "APP-1", 1, "2026-05-18")
        self.assertEqual(result["schema_compatible"]["decisions"][0]["reason"], "body-or-outcome-not-authorized")

    @patch("credentialing.readiness.assess_packet_readiness")
    def test_deferral_blocks_advancement_and_conditional_approval_activates(self, ready):
        ready.return_value = {"presentable": True, "elements": {}}
        deferred = process_recorded_decisions(ledger_with_decision(
            decision(Outcome="deferred-pending-information", Reason="Await board response")), "APP-1", 1, "2026-05-18")
        self.assertEqual(deferred["schema_compatible"]["status"], "deferred")
        self.assertIsNone(deferred["schema_compatible"]["activation"])
        conditional = process_recorded_decisions(ledger_with_decision(
            decision(Outcome="approved-with-conditions", Reason="Complete training due 2026-07-01")), "APP-1", 1, "2026-06-02")
        self.assertEqual(conditional["schema_compatible"]["status"], "active-with-conditions")
        self.assertEqual(conditional["schema_compatible"]["monitored_conditions"], [
            {"condition": "Complete training", "due": "2026-07-01"}])

    def test_conditions_section_parses_batch_two_document_shape(self):
        d = {"__content": "**Outcome:** approved-with-conditions\n**Reason:** subject to conditions\n**Conditions:**  \n- Re-verification of the Washington licence before its expiry on 2026-12-31 — due 2026-11-30\n- The Clinical Director's written concurrence on the 2021 practice gap explanation — due 2026-06-30\n\n## Minute\n"}
        self.assertEqual(_decision_conditions(d), [
            {"condition": "Re-verification of the Washington licence before its expiry on 2026-12-31", "due": "2026-11-30"},
            {"condition": "The Clinical Director's written concurrence on the 2021 practice gap explanation", "due": "2026-06-30"},
        ])

    @patch("credentialing.readiness.assess_packet_readiness")
    def test_explicit_withdrawal_is_terminal_and_refused_decision_status_precedence(self, ready):
        ready.return_value = {"presentable": False, "elements": {}, "blockers": [], "cleared_holds": []}
        ledger = ledger_with_decision(decision(Signatory="Not On Roster"))
        ledger["batches"][1]["documents"] = [{"path": "letters/withdrawal.md", "content":
            "**Date:** 2026-05-15\n**Application:** APP-1\nI am withdrawing my application for initial appointment."}]
        result = process_recorded_decisions(ledger, "APP-1", 1, "2026-05-18")
        self.assertEqual(result["schema_compatible"]["status"], "withdrawn")
        ledger["batches"][1]["documents"] = [{"path": "decisions/decision.md", "content":
            "**Decision ID:** GBD-1\n**Body:** Governing Body\n**Signatory:** Nobody\n**Role:** Chair, Governing Body\n**Application:** APP-1\n**Revision:** 1\n**Decision date:** 2026-05-12\n**Outcome:** approved\n**Privileges:** PRIV-HOSP\n**Reason:**\n**Effective date:**\n**Supersedes:**"}]
        result = process_recorded_decisions(ledger, "APP-1", 1, "2026-05-18")
        self.assertEqual(result["schema_compatible"]["status"], "decision-inadmissible")


if __name__ == "__main__":
    unittest.main()
