"""Offline contract and evidence regression checks for Legacy Code Intelligence."""
import asyncio
from contextlib import asynccontextmanager
from pathlib import Path
import tempfile
import time
import threading
import unittest
from unittest.mock import patch

from flask import Flask

from sdlc.integrations import mcp_client
from sdlc.legacy_intelligence import repository, service
from sdlc.legacy_intelligence.codebase_memory import CodebaseMemoryAdapter, DevelopmentCodebaseIntelligence
from sdlc.legacy_intelligence.models import validate_repositories
from sdlc.legacy_intelligence.routes import legacy_intelligence_bp
from sdlc.legacy_intelligence.source_analysis import discover

FIXTURE = '''from flask import Flask
app = Flask(__name__)

class CustomerService:
    def discount(self, age):
        if age >= 60:
            return 0.15
        return 0

@app.route('/customers')
def customers():
    return []
'''


class LegacyTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.repo = self.root / 'sample'
        self.repo.mkdir()
        (self.repo / 'app.py').write_text(FIXTURE)
        self.db_patch = patch.object(repository, 'DB_PATH', str(self.root / 'analyses.db'))
        self.db_patch.start()
        self.addCleanup(self.db_patch.stop)
        self.addCleanup(self.temp.cleanup)
        app = Flask(__name__)
        app.register_blueprint(legacy_intelligence_bp)
        self.client = app.test_client()
        self.ai_patch = patch('sdlc.services.legacy_intelligence_service.run_ai_insights', return_value={})
        self.ai_patch.start()
        self.addCleanup(self.ai_patch.stop)

    def sources(self):
        return [{'name': 'sample', 'type': 'local', 'path': str(self.repo), 'resolvedPath': str(self.repo)}]

    def wait(self, analysis_id):
        deadline = time.monotonic() + 5
        while time.monotonic() < deadline:
            value = repository.get(analysis_id)
            if value['status'] in {'COMPLETED', 'FAILED'}:
                return value
            time.sleep(0.01)
        self.fail('Analysis worker did not complete')

    def test_inputs_reject_invalid_shapes_and_credential_urls(self):
        for payload in (None, [], {}, {'repositories': []}, {'repositories': ['bad']}, {'repositories': [{'type': 'local', 'path': 'relative'}]}, {'repositories': [{'type': 'git', 'url': 'file:///tmp/repo'}]}, {'repositories': [{'type': 'git', 'url': 'https://token@example.com/org/repo.git'}]}, {'repositories': [{'type': 'git', 'url': 'https://example.com/org/repo.git?token=secret'}]}):
            response = self.client.post('/api/legacy-intelligence/analyze', json=payload)
            self.assertEqual(response.status_code, 400, payload)

    def test_deduplicates_same_local_repository(self):
        repo = {'type': 'local', 'path': str(self.repo)}
        self.assertEqual(len(validate_repositories({'repositories': [repo, repo]})), 1)

    def test_discovered_facts_have_real_source_evidence(self):
        result = discover(self.sources())
        self.assertTrue(any(fact['kind'] == 'class' and fact['name'] == 'CustomerService' for fact in result['facts']))
        self.assertTrue(any(fact['kind'] == 'api' and fact['name'] == '/customers' for fact in result['facts']))
        self.assertEqual(result['businessRules'][0]['confidence'], 'LOW')
        for evidence in result['evidence']:
            lines = (self.repo / evidence['file']).read_text().splitlines()
            self.assertEqual(evidence['snippet'], '\n'.join(lines[evidence['lineStart'] - 1:evidence['lineEnd']]))

    def test_excludes_dependency_trees_and_symlinks_from_source_scan(self):
        excluded = self.repo / 'node_modules'
        excluded.mkdir()
        (excluded / 'noise.py').write_text('class FakeService: pass')
        self.assertFalse(any(fact['name'] == 'FakeService' for fact in discover(self.sources())['facts']))

    def test_slow_ai_completes_with_source_findings_and_ignores_late_result(self):
        release, finished = threading.Event(), threading.Event()

        def slow_ai(snapshot):
            release.wait(3)
            snapshot["overview"]["classes"] = 999
            finished.set()
            return {"insights": {"summary": "Late result"}}

        try:
            with patch.object(service, 'get_adapter', return_value=DevelopmentCodebaseIntelligence()), \
                 patch.object(service, 'AI_INSIGHTS_TIMEOUT_SECONDS', 0.02), \
                 patch('sdlc.services.legacy_intelligence_service.run_ai_insights', side_effect=slow_ai):
                initial = service.start_analysis({'repositories': [{'type': 'local', 'path': str(self.repo)}]})
                value = self.wait(initial['analysisId'])
                self.assertEqual(value['status'], 'COMPLETED')
                self.assertEqual(value['overview']['classes'], 1)
                self.assertTrue(any('time limit' in item for item in value['limitations']))
                self.assertTrue(value['evidence'])
                release.set()
                self.assertTrue(finished.wait(1))
                saved = repository.get(initial['analysisId'])
                self.assertIsNone(saved['insights'])
                self.assertEqual(saved['overview']['classes'], 1)
        finally:
            release.set()

    def test_async_analysis_persists_and_reopens_without_scanning(self):
        with patch.object(service, 'get_adapter', return_value=DevelopmentCodebaseIntelligence()):
            response = self.client.post('/api/legacy-intelligence/analyze', json={'repositories': [{'type': 'local', 'path': str(self.repo)}]})
            self.assertEqual(response.status_code, 202)
            analysis_id = response.json['analysis']['analysisId']
            value = self.wait(analysis_id)
        self.assertEqual(value['status'], 'COMPLETED', value.get('error'))
        self.assertEqual(value['overview']['classes'], 1)
        self.assertIsNone(value['overview']['scheduledJobs'])
        self.assertEqual(value['engine'], 'development-source-scanner')
        with patch.object(service, 'start_analysis') as start:
            reopened = self.client.get('/api/legacy-intelligence/' + analysis_id)
            start.assert_not_called()
        self.assertEqual(reopened.json['analysis']['evidence'], value['evidence'])
        recent = self.client.get('/api/legacy-intelligence/recent').json['analyses']
        self.assertEqual(recent[0]['analysisId'], analysis_id)
        self.assertNotIn('evidence', recent[0])

    def test_mcp_failure_is_failed_job_never_silent_development_fallback(self):
        class FailedAdapter:
            async def analyze(self, repositories, progress):
                raise mcp_client.McpError('MCP fixture unavailable')
        with patch.object(service, 'get_adapter', return_value=FailedAdapter()):
            value = service.start_analysis({'repositories': [{'type': 'local', 'path': str(self.repo)}]})
            result = self.wait(value['analysisId'])
        self.assertEqual(result['status'], 'FAILED')
        self.assertIn('MCP fixture unavailable', result['error'])
        self.assertEqual(result['evidence'], [])

    def test_graph_adapter_names_projects_and_does_not_write_index_to_source(self):
        calls = []
        class Memory:
            schemas = {}
            def supports(self, tool, parameter=None):
                return tool in {'index_repository', 'get_architecture'}
            async def call(self, tool, **args):
                calls.append((tool, args))
                return {'status': 'indexed', 'project': args['name']} if tool == 'index_repository' else {'overview': 'source facts'}
        @asynccontextmanager
        async def connect(path):
            yield Memory()
        with patch.object(mcp_client, 'connect', connect):
            result = asyncio.run(CodebaseMemoryAdapter().analyze(self.sources(), lambda *args: None))
        self.assertEqual(result['engine'], 'codebase-memory-mcp')
        self.assertFalse(calls[0][1]['persistence'])
        self.assertTrue(calls[0][1]['name'].startswith('legacy-'))
        self.assertEqual(calls[1][1]['project'], calls[0][1]['name'])
        self.assertEqual(result['overview']['classes'], 1)
        self.assertTrue(result['graphFacts'])

    def test_api_missing_analysis_and_invalid_chat_are_actionable(self):
        self.assertEqual(self.client.get('/api/legacy-intelligence/missing').status_code, 404)
        for payload in ({}, [], {'analysisId': 'missing', 'question': ''}):
            self.assertEqual(self.client.post('/api/legacy-intelligence/chat', json=payload).status_code, 400)
        self.assertEqual(self.client.post('/api/legacy-intelligence/chat', json={'analysisId': 'missing', 'question': 'Where is validation?'}).status_code, 404)

    def test_restart_marks_interrupted_job_failed_and_preserves_evidence(self):
        record = {'analysisId': 'interrupted', 'status': 'INDEXING', 'evidence': [{'id': 'E1'}]}
        repository.save(record)
        repository._initialized.discard(str(Path(repository.DB_PATH).resolve()))
        with patch.object(repository, 'SESSION', 'new-backend-process'):
            reopened = repository.get('interrupted')
        self.assertEqual(reopened['status'], 'FAILED')
        self.assertIn('restarted', reopened['error'])
        self.assertEqual(reopened['evidence'], [{'id': 'E1'}])

    def test_delete_removes_selected_snapshot_and_does_not_resurrect_running_work(self):
        for status in ('COMPLETED', 'INDEXING', 'FAILED'):
            record = {'analysisId': status, 'status': status, 'name': status, 'evidence': [{'id': 'E1'}]}
            repository.save(record)
            response = self.client.delete('/api/legacy-intelligence/' + status)
            self.assertEqual(response.status_code, 200)
            self.assertEqual(self.client.get('/api/legacy-intelligence/' + status).status_code, 404)
            # A late worker update must not undo deletion.
            record['status'] = 'COMPLETED'
            self.assertIsNone(repository.save(record))
            self.assertIsNone(repository.get(status))
        self.assertEqual(repository.recent(), [])
        self.assertEqual(self.client.delete('/api/legacy-intelligence/missing').status_code, 404)

    def test_chat_provider_failure_returns_actionable_502(self):
        from sdlc.llm import AIProviderError
        with patch.object(service, 'require_completed', return_value={}), \
             patch('sdlc.legacy_intelligence.agents.answer_question', side_effect=AIProviderError("Select an enabled model.")):
            response = self.client.post('/api/legacy-intelligence/chat', json={
                'analysisId': 'saved', 'question': 'Explain the services'
            })
        self.assertEqual(response.status_code, 502)
        self.assertFalse(response.json['success'])
        self.assertEqual(response.json['error'], 'Select an enabled model.')

    def test_chat_requires_relevant_evidence_and_valid_citations(self):
        from sdlc.legacy_intelligence import agents
        unrelated = {'id': 'E1', 'repository': 'sample', 'file': 'customers.py', 'symbol': 'Customer', 'snippet': 'class Customer: pass', 'lineStart': 1}
        job = {'id': 'E8', 'repository': 'sample', 'file': 'jobs.py', 'symbol': 'reconcile', 'snippet': '@scheduler.scheduled_job("cron")', 'lineStart': 8}
        value = {'evidence': [unrelated, job], 'facts': [{'kind': 'scheduledJob', 'name': 'reconcile', 'evidence': [job]}]}
        with patch.object(agents, 'call_llm_json', return_value={'answer': 'Reconcile is scheduled [E8].', 'evidenceIds': ['E8']}) as llm:
            result = agents.answer_question(value, 'What scheduled jobs exist?')
            self.assertEqual([ev['id'] for ev in result['evidence']], ['E8'])
            self.assertNotIn('customers.py', llm.call_args.args[0])
        with patch.object(agents, 'call_llm_json') as llm:
            self.assertEqual(agents.answer_question(value, 'Where is payroll calculated?')['evidence'], [])
            llm.assert_not_called()
        with patch.object(agents, 'call_llm_json', return_value={'answer': 'Invented finding', 'evidenceIds': ['E999']}):
            result = agents.answer_question(value, 'What scheduled jobs exist?')
            self.assertNotIn('Invented finding', result['answer'])

    def test_flow_only_connects_direct_source_resolved_calls(self):
        from sdlc.legacy_intelligence.flow_analysis import build_call_flow
        class Memory:
            def supports(self, *args):
                return True
            async def call(self, tool, **args):
                return {'file_path': 'app.py', 'start_line': 1, 'source': 'def call():\n    return 1'}
        trace = {'callees': {'cols': ['name', 'hop', 'strategy'], 'groups': [{'qn_prefix': 'sample.app', 'rows': [['save', 1, 'lsp'], ['indirect', 2, 'lsp'], ['guess', 1, 'heuristic']]}]}}
        source = {**self.sources()[0], 'project': 'sample'}
        flow = asyncio.run(build_call_flow(Memory(), source, 'sample.app.submit', trace))
        self.assertEqual(len(flow['edges']), 1)
        self.assertEqual(flow['edges'][0]['target'], 'sample.app.save')
        self.assertTrue(all(node['evidence'] for node in flow['nodes']))

    def test_document_exports_include_relevant_source_references(self):
        from sdlc.legacy_intelligence import documentation
        api = {'id': 'E9', 'repository': 'sample', 'file': 'api.py', 'symbol': 'customers', 'lineStart': 10, 'lineEnd': 12}
        unrelated = {'id': 'E1', 'repository': 'sample', 'file': 'unrelated.py', 'lineStart': 1, 'lineEnd': 2}
        value = {'analysisId': 'docs-test', 'facts': [{'kind': 'api', 'name': '/customers', 'repository': 'sample', 'evidence': [api]}], 'evidence': [unrelated, api], 'limitations': ['Dynamic routes are unverified.']}
        with patch.object(documentation, 'ensure_generated_code_dir', return_value=str(self.root / 'output')), patch.object(documentation, '_render_pdf') as render:
            docs = documentation.generate_documentation(value, ['api_documentation', 'security_overview', 'technical_debt'])
        self.assertEqual([item['id'] for item in docs[0]['evidence']], ['E9'])
        self.assertIn('api.py:10-12', docs[0]['content'])
        self.assertIn('api.py:10-12', render.call_args_list[0].args[0])
        self.assertNotIn('unrelated.py', docs[0]['content'])
        self.assertIn('Dynamic routes are unverified', docs[0]['content'])
        self.assertNotIn('low test coverage', docs[2]['content'])


if __name__ == '__main__':
    unittest.main()
