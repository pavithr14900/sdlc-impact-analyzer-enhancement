"""Document authoring, stable exports and Confluence publishing contracts (offline)."""
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch, Mock

from flask import Flask
from pypdf import PdfReader
from sdlc.legacy_intelligence import document_pack as pack, documentation, confluence
from sdlc.legacy_intelligence.routes import legacy_intelligence_bp

DRAFT = """## Executive Summary
The customer endpoint is declared by the sample application [E9]. It provides a source-backed entry point for reviewing customer behavior; its complete response schema has not been established.

## Scope and Context
This document covers the discovered endpoint only. Deployment settings and authentication policy are not included in the supplied evidence.

## Endpoints
| Method | Path | Purpose | Request Body | Response Body | Success Status | Error Statuses |
| --- | --- | --- | --- | --- | --- | --- |
| GET | /customers | Customer route [E9] | Not verified from source | Not verified from source | Not verified from source | Not verified from source |

## Endpoint Details
### GET /customers
The endpoint is declared in the sample application [E9]. Its full request and response contract is not established by the supplied source.

## Validation and Error Handling
Validation and error envelopes are not verified from source.

## Engineering Considerations
Confirm request validation with the owning team before changing the route.

## Open Questions
What response schema is guaranteed to consumers?
"""

class DocumentPackTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        for module in (pack, documentation):
            patcher = patch.object(module, "ensure_generated_code_dir", return_value=str(self.root))
            patcher.start(); self.addCleanup(patcher.stop)
        evidence = {"id": "E9", "repository": "sample", "file": "api.py", "lineStart": 10, "lineEnd": 12, "snippet": "@app.get('/customers')"}
        self.analysis = {"analysisId": "docs-test", "name": "Sample", "status": "COMPLETED", "facts": [{"kind": "api", "name": "/customers", "repository": "sample", "evidence": [evidence]}], "evidence": [evidence], "limitations": ["Dynamic routes are unverified."]}
        for key, value in {"CONFLUENCE_BASE_URL": "https://team.atlassian.net/wiki", "CONFLUENCE_EMAIL": "author@example.com", "CONFLUENCE_API_TOKEN": "secret-test-token", "CONFLUENCE_SPACE_KEY": "ENG", "CONFLUENCE_PARENT_PAGE_ID": ""}.items():
            patcher = patch.object(confluence.config, key, value)
            patcher.start(); self.addCleanup(patcher.stop)
        self.app = Flask(__name__)
        self.app.register_blueprint(legacy_intelligence_bp)
        self.client = self.app.test_client()

    def author(self, draft=DRAFT):
        with patch.object(pack, "call_llm", return_value=draft), patch.object(documentation, "_render_pdf"):
            return pack.author_documentation(self.analysis, ["api_documentation"])[0]

    def test_authored_snapshot_reopens_and_exports_exact_content_without_model(self):
        doc = self.author()
        self.assertEqual(doc["generationMode"], "ai-authored")
        self.assertIn("## Contents", doc["content"])
        self.assertIn("api.py:10-12", doc["content"])
        with patch.object(pack, "call_llm", side_effect=AssertionError("Export must not call LLM")):
            loaded = pack.load_documents("docs-test")[0]
            self.assertEqual(doc["revision"], loaded["revision"])
            output = pack.render_saved_pdf("docs-test", loaded)
            reader = PdfReader(output)
            self.assertGreaterEqual(len(reader.pages), 2)
            self.assertGreater(reader.pages[1].mediabox.width, reader.pages[1].mediabox.height)
            text = "\n".join(page.extract_text() for page in reader.pages)
            self.assertIn("API", text.upper())
            self.assertIn("/customers", text)
            self.assertIn("ENGINEERING", text.upper())

    def test_api_format_is_required_and_fallback_remains_tabular(self):
        doc = self.author(DRAFT.replace("| Method | Path |", "| Verb | Route |"))
        self.assertEqual(doc["generationMode"], "source-summary")
        self.assertIn("| Method | Path | Purpose | Request Body | Response Body | Success Status | Error Statuses |", doc["content"])
        self.assertIn("| GET | /customers", doc["content"])
        self.assertIn("## Endpoint Details", doc["content"])
        self.assertIn("Not verified from source", doc["content"])

    def test_api_methods_only_use_explicit_matching_route_declarations(self):
        from sdlc.legacy_intelligence.api_documentation import declared_method, render_api_inventory
        def route(snippet):
            return {"kind": "api", "name": "/customers", "repository": "sample", "evidence": [{"id": "E9", "snippet": snippet}]}
        for snippet, expected in [("@app.post('/customers')", "POST"), ('@GetMapping("/customers")', "GET"), ("@app.route('/customers', methods=['GET', 'POST'])", "GET, POST"), ("@app.route('/customers')", "Not verified from source"), ("@app.delete('/other')", "Not verified from source"), ("@app.delete('/customers/archive')", "Not verified from source")]:
            self.assertEqual(declared_method(route(snippet)), expected)
        self.assertIn("Not verified from source", render_api_inventory([route("@app.post('/customers')")]))

    def test_invalid_citations_fall_back_and_report_reason(self):
        doc = self.author(DRAFT.replace("E9", "E999"))
        self.assertEqual(doc["generationMode"], "source-summary")
        self.assertTrue(doc["warning"])
        self.assertNotIn("[E999]", doc["content"])

    def test_no_evidence_does_not_call_model(self):
        self.analysis.update(facts=[], evidence=[])
        with patch.object(pack, "call_llm") as llm, patch.object(documentation, "_render_pdf"):
            docs = pack.author_documentation(self.analysis, ["security_overview"])
        llm.assert_not_called()
        self.assertEqual(docs[0]["generationMode"], "source-summary")

    def test_stale_revision_and_missing_document_rejected_before_network(self):
        self.author()
        with patch.object(confluence, "_request") as request:
            with self.assertRaisesRegex(ValueError, "changed"):
                confluence.publish_documents(self.analysis, [{"type": "api_documentation", "revision": "stale"}])
            request.assert_not_called()
        with self.assertRaises(ValueError): pack.load_documents("docs-test", ["../secrets"])
        with self.assertRaises(ValueError): pack.pack_directory("../../outside")

    def test_publish_create_update_and_partial_failure(self):
        doc = self.author()
        selections = [{"type": doc["type"], "revision": doc["revision"]}]
        with patch.object(confluence, "_request", side_effect=[{"results": [{"id": "7"}]}, {"results": []}, {"id": "101"}]) as request:
            result = confluence.publish_documents(self.analysis, selections)
            self.assertEqual(result["pages"][0]["action"], "created")
            payload = request.call_args.kwargs["json"]
            self.assertEqual(payload["spaceId"], "7")
            self.assertIn("<table>", payload["body"]["value"])
            self.assertIn("[docs-test]", payload["title"])
        with patch.object(confluence, "_request", side_effect=[{"results": [{"id": "7"}]}, {"results": [{"id": "101"}]}, {"id": "101", "version": {"number": 2}}, {"id": "101"}]) as request:
            result = confluence.publish_documents(self.analysis, selections)
            self.assertEqual(result["pages"][0]["action"], "updated")
            self.assertEqual(request.call_args.kwargs["json"]["version"]["number"], 3)
        with patch.object(confluence, "_request", side_effect=[{"results": [{"id": "7"}]}, RuntimeError("Permission denied")]):
            result = confluence.publish_documents(self.analysis, selections)
            self.assertFalse(result["pages"])
            self.assertEqual(len(result["errors"]), 1)

    def test_storage_removes_active_html_and_connection_hides_secrets(self):
        html = confluence.storage_body('<script>alert(1)</script><img src="https://bad" onerror="alert(1)"><a href="javascript:alert(1)">x</a>')
        self.assertNotIn("<script", html)
        self.assertNotIn("<img", html)
        self.assertNotIn("javascript:", html)
        response = self.client.get('/api/legacy-intelligence/confluence/status')
        self.assertTrue(response.json["configured"])
        self.assertNotIn("secret-test-token", response.get_data(as_text=True))

    def test_routes_reject_bad_selection_and_download_only_requested_snapshots(self):
        self.author()
        response = self.client.post('/api/legacy-intelligence/docs-test/confluence/publish', json={"documents": []})
        self.assertEqual(response.status_code, 400)
        with patch('sdlc.legacy_intelligence.service.require_completed', return_value=self.analysis), patch.object(pack, "call_llm", side_effect=AssertionError("No fresh authoring on download")):
            response = self.client.get('/api/legacy-intelligence/docs-test/documentation')
            self.assertEqual(len(response.json["documents"]), 1)
            response = self.client.get('/api/legacy-intelligence/docs-test/documentation/pdf?type=all&types=api_documentation')
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.mimetype, "application/pdf")
            response.close()

    def test_remote_errors_do_not_expose_response_body_or_credentials(self):
        with patch.object(confluence.requests, "request", return_value=Mock(status_code=401, text="secret-test-token")):
            with self.assertRaisesRegex(RuntimeError, "Authentication failed") as error:
                confluence._request("GET", "/spaces")
            self.assertNotIn("secret-test-token", str(error.exception))

if __name__ == "__main__":
    unittest.main()
