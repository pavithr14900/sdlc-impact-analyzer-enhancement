"""Offline regressions for focused chat retrieval and answer validation."""
import json
import unittest
from unittest.mock import patch

from sdlc.legacy_intelligence import agents


def evidence(number, symbol):
    return {"id": f"E{number}", "repository": "sample", "file": f"{symbol}.py",
            "lineStart": 1, "symbol": symbol, "snippet": f"def {symbol}(): pass"}


class ChatTests(unittest.TestCase):
    def test_business_rules_are_retrievable_without_keyword_in_source(self):
        ev = evidence(1, "discount")
        value = {"evidence": [ev], "businessRules": [{"title": "Senior discount", "evidence": [ev]}]}
        with patch.object(agents, "call_llm_json", return_value={"answer": "See discount [E1].", "evidenceIds": ["E1"]}) as llm:
            agents.answer_question(value, "Explain the business rules")
        context = json.loads(llm.call_args.args[0])
        self.assertEqual(context["findings"][0]["title"], "Senior discount")
        self.assertEqual(llm.call_args.kwargs["max_tokens"], 2600)
        self.assertEqual(llm.call_args.kwargs["timeout_seconds"], 60)

    def test_dependencies_include_confirmed_edges(self):
        caller, callee = evidence(1, "submit"), evidence(2, "save")
        value = {"evidence": [caller, callee], "relationships": [{"source": "submit", "target": "save", "relationship": "calls", "evidence": [caller, callee]}]}
        selected = agents._pick_evidence(value, "Which dependencies exist?")
        self.assertEqual(len(selected), 2)
        self.assertEqual(agents._context_findings(value, selected)[0]["target"], "save")
        self.assertEqual(agents._context_findings(value, [caller]), [])

    def test_specific_symbol_outranks_generic_category_and_deduplicates(self):
        generic = [evidence(i, f"generic{i}") for i in range(1, 12)]
        target = evidence(12, "PayrollService")
        value = {"evidence": generic + [target, {**target, "id": "E13"}], "facts": [
            {"kind": "service", "name": ev["symbol"], "evidence": [ev]} for ev in generic + [target]]}
        selected = agents._pick_evidence(value, "Explain PayrollService")
        self.assertEqual(selected[0]["id"], "E12")
        self.assertEqual(sum(ev["file"] == target["file"] for ev in selected), 1)

    def test_unknown_inline_citation_is_rejected(self):
        ev = evidence(1, "discount")
        with patch.object(agents, "call_llm_json", return_value={"answer": "Invented claim [E999].", "evidenceIds": ["E1"]}):
            answer = agents.answer_question({"evidence": [ev]}, "Explain discount")
        self.assertNotIn("Invented claim", answer["answer"])

    def test_provider_denial_is_actionable_not_a_source_fallback(self):
        from sdlc import llm
        from botocore.exceptions import ClientError
        ev = evidence(1, "discount")
        denied = ClientError({"Error": {"Code": "ValidationException", "Message": "Operation not allowed"}}, "Converse")
        with patch.object(llm, "_bedrock_for_timeout") as client:
            client.return_value.converse.side_effect = denied
            with self.assertRaisesRegex(llm.AIProviderError, "Select an enabled model"):
                agents.answer_question({"evidence": [ev]}, "Explain discount")

    def test_llm_reads_text_after_non_text_content_blocks(self):
        from sdlc import llm
        with patch.object(llm, "_bedrock") as client:
            client.converse.return_value = {"output": {"message": {"content": [
                {"reasoningContent": {}}, {"text": "First."}, {"text": "Second."}
            ]}}}
            self.assertEqual(llm.call_llm("question"), "First.\nSecond.")

    def test_json_helper_forwards_token_budget(self):
        from sdlc import llm
        with patch.object(llm, "call_llm", return_value='{"answer": "ok"}') as call:
            self.assertEqual(llm.call_llm_json("question", max_tokens=1000), {"answer": "ok"})
        self.assertEqual(call.call_args.kwargs["max_tokens"], 1000)
