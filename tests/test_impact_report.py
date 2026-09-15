"""Offline checks for the user-facing report contract and Markdown fallback."""
import copy
import json
import unittest

from sdlc.services.impact_report import fallback_document, parse_report, render_report, render_analysis_appendix


CONTEXT = "\n".join(json.dumps(item) for item in [
    {"repositories": [], "limitations": ["Retrieval is bounded."]},
    {"id": "E1", "tool": "index_repository", "result": {"status": "indexed"}},
    {"id": "E2", "tool": "get_code_snippet", "result": {
        "file_path": "pricing.py", "source": "def calculate_total(price, quantity): return price * quantity"}},
    {"id": "E3", "tool": "trace_path", "result": {
        "function": "calculate_total", "callers": [{"name": "checkout", "file": "orders.py"}]}},
])


def example_report():
    return {
        "title": "Apply an order discount",
        "summary": "Apply a 10% discount to the total. Review checkout because it consumes that value.",
        "overall_risk": "Medium",
        "risk_reason": "The calculation changes the amount returned by checkout.",
        "behavior_changes": [{"area": "Order checkout", "before": "Checkout returns price multiplied by quantity.",
            "after": "Checkout returns the total with a 10% discount applied once.",
            "user_impact": "Customers pay 180 instead of 200 for two items priced at 100.", "evidence_ids": ["E2", "E3"]}],
        "affected_components": [
            {"name": "calculate_total", "file": "pricing.py", "impact": "Direct",
             "reason": "Calculates the total before the discount.", "action": "Apply the discount once.", "evidence_ids": ["E2"]},
            {"name": "checkout", "file": "orders.py", "impact": "Indirect",
             "reason": "Returns the calculated amount.", "action": "Check the returned total.", "evidence_ids": ["E3"]},
        ],
        "dependencies": [{"source": "checkout", "target": "calculate_total", "relationship": "Calls",
            "impact": "Checkout will return the discounted amount.", "evidence_ids": ["E3"]}],
        "risks": [{"title": "Incorrect payable total", "severity": "Medium", "detail": "A second discount could undercharge an order.",
            "mitigation": "Apply the discount once and check checkout output.", "evidence_ids": ["E2", "E3"]}],
        "contract_impacts": [{"area": "API", "status": "Review needed", "detail": "Checkout consumes the total; external API response fields are not shown.",
            "action": "Check whether an external endpoint exposes this amount.", "evidence_ids": ["E3"]}],
        "actions": [{"title": "Update the calculation", "detail": "Apply the 10% discount after multiplying price and quantity.",
            "validation": "The calculation and checkout both return 180 for a subtotal of 200."}],
        "tests": [{"scenario": "Price 100 and quantity 2", "expected_result": "The returned total is 180.",
            "purpose": "Verify the discount is applied exactly once through checkout."}],
        "open_questions": [],
    }


class ImpactReportTests(unittest.TestCase):
    def test_source_backed_report_preserves_direction_and_generates_readable_export(self):
        report = parse_report(json.dumps(example_report()), CONTEXT)
        self.assertEqual(report, example_report())
        document = render_report(report)
        self.assertIn("checkout → calculate\\_total", document)
        self.assertIn("Overall risk: Medium", document)
        self.assertIn("The returned total is 180.", document)
        self.assertNotIn("## Decisions needed", document)
        self.assertNotIn('"affected_components"', document)
        self.assertIn("## What changes for users", document)
        self.assertIn("## Data, API and access impact", document)
        self.assertIn("Done when:", document)
        self.assertIn("these tests have not been run", document)
        self.assertIn("Verify the discount is applied exactly once", document)

    def test_missing_evidence_does_not_establish_current_behavior_or_unchanged_contracts(self):
        raw = example_report()
        raw["behavior_changes"][0]["evidence_ids"] = ["E999"]
        raw["contract_impacts"][0].update(status="No change identified", evidence_ids=["E1"])
        report = parse_report(json.dumps(raw), CONTEXT)
        self.assertIn("not established", report["behavior_changes"][0]["before"])
        self.assertEqual(report["behavior_changes"][0]["evidence_ids"], [])
        self.assertEqual(report["contract_impacts"][0]["status"], "Review needed")
        self.assertTrue(report["contract_impacts"][0]["detail"].startswith("Unverified assessment:"))

    def test_old_reports_and_malformed_new_sections_are_safe(self):
        raw = example_report()
        raw.pop("behavior_changes")
        raw["contract_impacts"] = [None, {"area": [], "detail": True}]
        raw["actions"][0].pop("validation")
        raw["tests"][0]["purpose"] = {"wrong": "type"}
        report = parse_report(json.dumps(raw), CONTEXT)
        self.assertEqual(report["behavior_changes"], [])
        self.assertEqual(report["contract_impacts"], [])
        self.assertEqual(report["actions"][0]["validation"], "")
        self.assertEqual(report["tests"][0]["purpose"], "")
        self.assertIn("The returned total is 180.", render_report(report))

    def test_new_sections_are_bounded_and_invalid_status_needs_review(self):
        raw = example_report()
        for field in ("behavior_changes", "contract_impacts"):
            item = raw[field][0]
            raw[field] = [item, item] + [{**item, "area": f"Area {i}"} for i in range(5)]
        raw["contract_impacts"][0]["status"] = "Definitely safe"
        report = parse_report(json.dumps(raw), CONTEXT)
        self.assertEqual(len(report["behavior_changes"]), 3)
        self.assertEqual(len(report["contract_impacts"]), 3)
        self.assertEqual(report["contract_impacts"][0]["status"], "Review needed")

    def test_export_keeps_source_locations_and_coverage_without_dumping_source_code(self):
        evidence = [json.loads(line) for line in CONTEXT.splitlines()][1:]
        evidence[1]["result"]["start_line"] = 12
        findings = {"indexed": [{"path": "C:/work/orders"}], "evidence": evidence,
            "warnings": ["One caller could not be traced."]}
        document = render_analysis_appendix("Apply a 10% discount.", findings)
        self.assertIn("Requested change:", document)
        self.assertIn("C:/work/orders", document)
        self.assertIn("**E2**", document)
        self.assertIn("pricing.py:12", document)
        self.assertIn("One caller could not be traced.", document)
        self.assertNotIn("return price * quantity", document)

    def test_accepts_fenced_json_without_another_model_call(self):
        report = parse_report("```json\n" + json.dumps(example_report()) + "\n```", CONTEXT)
        self.assertEqual(report["title"], "Apply an order discount")

    def test_bad_types_do_not_leak_into_the_display_contract(self):
        raw = example_report()
        raw.update(title=["wrong"], overall_risk="catastrophic", risk_reason={}, actions="do things", tests=[None, {"scenario": {}, "expected_result": 2}])
        raw["affected_components"] += [None, "invalid", {"name": True, "reason": "invalid"}]
        raw["risks"][0]["severity"] = "certain"
        report = parse_report(json.dumps(raw), CONTEXT)
        self.assertEqual(report["title"], "Change impact assessment")
        self.assertEqual(report["overall_risk"], "Unknown")
        self.assertEqual(report["risks"][0]["severity"], "Unknown")
        self.assertEqual(report["actions"], [])
        self.assertEqual(report["tests"], [])
        self.assertEqual(len(report["affected_components"]), 2)
        self.assertIsInstance(report["risk_reason"], str)

    def test_deduplicates_and_caps_each_section(self):
        raw = example_report()
        for field, key in (("affected_components", "name"), ("dependencies", "source"),
                           ("risks", "title"), ("actions", "title"), ("tests", "scenario")):
            base = raw[field][0]
            raw[field] = [copy.deepcopy(base), copy.deepcopy(base)]
            raw[field] += [{**base, key: f"Item {i}"} for i in range(12)]
        raw["open_questions"] = ["Which rounding rule?", "which rounding rule?", None] + [f"Decision {i}?" for i in range(5)]
        report = parse_report(json.dumps(raw), CONTEXT)
        for field, limit in (("affected_components", 8), ("dependencies", 6), ("risks", 5), ("actions", 5), ("tests", 5), ("open_questions", 3)):
            self.assertEqual(len(report[field]), limit, field)
        self.assertEqual(len({item["name"] for item in report["affected_components"]}), 8)

    def test_unknown_citations_and_invented_files_are_not_source_evidence(self):
        raw = example_report()
        raw["summary"] += " See [E999]."
        raw["affected_components"][0].update(file="invented.py", evidence_ids=["E2", "E999", "E2", 7])
        raw["dependencies"][0]["evidence_ids"] = ["E999"]
        # A source string mentioning an ID cannot grant that ID a citation.
        context = CONTEXT + "\n" + json.dumps({"id": "E4", "tool": "get_code_snippet", "result": {"source": "The string E999 is in source code."}})
        report = parse_report(json.dumps(raw), context)
        self.assertNotIn("E999", json.dumps(report))
        self.assertEqual(report["affected_components"][0]["evidence_ids"], ["E2"])
        self.assertEqual(report["affected_components"][0]["file"], "")
        self.assertEqual(report["affected_components"][0]["impact"], "Review")
        self.assertEqual(report["dependencies"], [])

    def test_missing_source_evidence_cannot_establish_low_risk(self):
        for context, evidence_id in (("", "E2"), (CONTEXT, "E1")):
            with self.subTest(context=context):
                raw = example_report()
                raw["overall_risk"] = "low"
                raw["risks"][0]["severity"] = "low"
                for field in ("affected_components", "dependencies", "risks"):
                    for item in raw[field]:
                        item["evidence_ids"] = [evidence_id]
                report = parse_report(json.dumps(raw), context)
                self.assertEqual(report["overall_risk"], "Unknown")
                self.assertEqual(report["risks"][0]["severity"], "Unknown")
                self.assertEqual(report["dependencies"], [])
                self.assertTrue(all(item["impact"] == "Review" for item in report["affected_components"]))

    def test_wrong_shapes_and_malformed_json_choose_fallback(self):
        for value in ("", "Not JSON", '{"summary": "unfinished', "[]", "null", '{"summary": []}', "{}"):
            with self.subTest(value=value):
                self.assertIsNone(parse_report(value, CONTEXT))

    def test_fallback_preserves_stage_markdown_without_dumping_broken_json(self):
        state = {"scope": "## Change summary\n\nApply a 10% discount.",
                 "code_impact": "## Affected components\n\nReview calculate_total and checkout.",
                 "test_impact": "Verify that 200 becomes 180."}
        document = fallback_document(state, '{"summary": "unfinished')
        self.assertIn("Apply a 10% discount.", document)
        self.assertIn("Review calculate_total and checkout.", document)
        self.assertIn("Verify that 200 becomes 180.", document)
        self.assertNotIn('"summary"', document)
        self.assertTrue(fallback_document({}, ""))

    def test_export_escapes_markup_from_model_fields(self):
        raw = example_report()
        raw["summary"] = "<script>alert(1)</script> [click](https://example.test)"
        document = render_report(parse_report(json.dumps(raw), CONTEXT))
        self.assertNotIn("<script>", document)
        self.assertNotIn("[click]", document)


if __name__ == "__main__":
    unittest.main()
