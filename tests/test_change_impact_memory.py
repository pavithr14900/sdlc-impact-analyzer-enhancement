"""Offline regression tests for MCP retrieval and change-impact jobs."""
import asyncio
from contextlib import asynccontextmanager
import json
import importlib
from langsmith import tracing_context
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from sdlc.integrations import mcp_client
from sdlc.services import change_impact_service as service, repo_store


class FakeMemory:
    def __init__(self, fail=None, empty=False):
        self.calls = []
        self.fail = fail
        self.empty = empty

    def supports(self, *args):
        return True

    async def call(self, tool, **args):
        self.calls.append((tool, args))
        if tool == self.fail:
            raise mcp_client.McpError('server unavailable')
        if tool == 'index_repository':
            return {'status': 'indexed', 'project': args['name']}
        if tool == 'search_graph':
            return {'cols': ['qn', 'label', 'file', 'lines'], 'rows': [] if self.empty else [[args['project'] + '.pricing.calculate_total', 'Function', 'pricing.py', '1-3']]}
        if tool == 'trace_path':
            return {'callers_total': 1, 'callers': {'cols': ['name', 'hop'], 'groups': [{'qn_prefix': args['project'] + '.orders', 'rows': [['checkout', 1]]}]}}
        if tool == 'get_code_snippet':
            return {'file_path': 'pricing.py', 'start_line': 1, 'source': 'def calculate_total(price, quantity): return price * quantity'}
        return {'text': 'Python repository evidence'}


def connection(memory):
    @asynccontextmanager
    async def connect(path):
        yield memory
    return connect


class MemoryTests(unittest.TestCase):
    def test_text_and_structured_mcp_errors(self):
        for structured in (None, {'error': 'bad project'}):
            with self.assertRaises(mcp_client.McpError):
                mcp_client.decode_result(SimpleNamespace(content=[SimpleNamespace(type='text', text='bad project')], isError=structured is None, structuredContent=structured))

    def test_json_and_text_results(self):
        for value in ('{"nodes": 2}', 'source evidence'):
            result = mcp_client.decode_result(SimpleNamespace(content=[SimpleNamespace(type='text', text=value)], isError=False, structuredContent=None))
            self.assertIsInstance(result, dict)

    def test_plain_language_queries(self):
        terms = service._search_terms('Allow discounts when calculating an order total')
        self.assertIn('discounts', terms)
        self.assertIn('total', terms)
        self.assertNotIn('when', terms)

    def test_prefix_grouped_trace(self):
        rows = service.graph_rows({'callers': {'cols': ['name', 'hop'], 'groups': [{'qn_prefix': 'repo.orders', 'rows': [['checkout', 1]]}]}})
        self.assertEqual(rows[0]['qn'], 'repo.orders.checkout')

    def test_local_path_validation(self):
        with tempfile.TemporaryDirectory() as directory:
            self.assertEqual(service.validate_local_path('"' + directory + '"'), str(Path(directory).resolve()))
            file = Path(directory) / 'file.txt'
            file.write_text('example')
            for invalid in (str(file), str(Path(directory) / 'missing'), 'relative/path'):
                with self.assertRaises(ValueError):
                    service.validate_local_path(invalid)

    def test_retrieval_scopes_queries_and_fetches_callers(self):
        memory = FakeMemory()
        with patch.object(mcp_client, 'connect', connection(memory)):
            result = asyncio.run(service.collect_repository_evidence('Allow discounts on order total', ['/repo/a', '/repo/b']))
        self.assertEqual(len(result['indexed']), 2)
        projects = {item['project'] for item in result['indexed']}
        self.assertEqual(len(projects), 2)
        for tool, args in memory.calls:
            if tool != 'index_repository':
                self.assertIn(args['project'], projects)
        self.assertTrue(any(args.get('qualified_name', '').endswith('.orders.checkout') for _, args in memory.calls))
        self.assertEqual(len(result['dependencies']), 2)
        self.assertTrue(all(not args['persistence'] for tool, args in memory.calls if tool == 'index_repository'))

    def test_index_failure_stops_analysis(self):
        memory = FakeMemory(fail='index_repository')
        with patch.object(mcp_client, 'connect', connection(memory)), self.assertRaises(mcp_client.McpError):
            asyncio.run(service.collect_repository_evidence('Change totals', ['/repo']))
        self.assertEqual([tool for tool, _ in memory.calls], ['index_repository'])

    def test_search_failure_does_not_become_empty_success(self):
        with patch.object(mcp_client, 'connect', connection(FakeMemory(fail='search_graph'))), self.assertRaises(mcp_client.McpError):
            asyncio.run(service.collect_repository_evidence('Change totals', ['/repo']))

    def test_no_matches_are_reported_as_unknown(self):
        with patch.object(mcp_client, 'connect', connection(FakeMemory(empty=True))):
            result = asyncio.run(service.collect_repository_evidence('Change totals', ['/repo']))
        self.assertEqual(result['dependencies'], [])
        self.assertTrue(any('unverified' in warning for warning in result['warnings']))

    def test_context_truncation_is_explicit(self):
        result = {'indexed': [], 'warnings': [], 'evidence': [{'id': 'E1', 'result': {'text': 'x' * 10000}}]}
        context = service.build_repository_context(result)
        self.assertIn('truncated', context)
        self.assertTrue(result['warnings'])
        self.assertLess(len(context), 8000)

    def test_job_stores_evidence_before_model_runs(self):
        change_impact_graph = importlib.import_module('sdlc.graphs.change_impact_graph')
        with tempfile.TemporaryDirectory() as directory, patch.object(repo_store, 'DB_PATH', str(Path(directory) / 'jobs.db')):
            repo_store.init_db()
            with patch.object(mcp_client, 'connect', connection(FakeMemory())), patch.object(change_impact_graph, 'run_change_impact_workflow', return_value={'document': 'Report', 'risks': 'Risks', 'report': {'title': 'Order discount'}}) as workflow:
                thread = service.start_job_async('success', 'Allow discounts on order total', None, [{'local_path': directory}], {})
                thread.join(10)
                job = repo_store.get_job('success')
            self.assertEqual(job['status'], 'completed')
            self.assertIn('calculate_total', workflow.call_args.kwargs['repository_context'])
            self.assertTrue(job['result']['dependencies'])
            self.assertEqual(job['result']['report'], {'title': 'Order discount'})
            self.assertTrue(job['result']['document'].startswith('Report\n'))
            self.assertIn('## Analysis context', job['result']['document'])
            self.assertIn('## Analysis limits', job['result']['document'])
            self.assertIn('Allow discounts on order total', job['result']['document'])
            self.assertTrue(job['result']['findings']['warnings'])
            with patch.object(mcp_client, 'connect', connection(FakeMemory(fail='index_repository'))), patch.object(change_impact_graph, 'run_change_impact_workflow') as workflow:
                service.start_job_async('failure', 'Change total', None, [{'local_path': directory}], {}).join(10)
            self.assertEqual(repo_store.get_job('failure')['status'], 'failed')
            workflow.assert_not_called()

    def test_every_agent_receives_evidence_and_risk_runs_once(self):
        from sdlc.agents import change_impact_agents
        from sdlc.graphs.change_impact_graph import run_change_impact_workflow
        with tracing_context(enabled=False), patch.object(change_impact_agents, 'call_llm', return_value='Assessed evidence') as llm:
            result = run_change_impact_workflow('Change total', repository_context='E1 pricing.py:1 calculate_total')
        self.assertEqual(llm.call_count, 5)
        for call in llm.call_args_list:
            self.assertIn('E1 pricing.py:1 calculate_total', call.args[0])
        self.assertEqual(sum('This is the final report synthesis.' in call.args[0] for call in llm.call_args_list), 1)
        self.assertTrue(result['document'])
        self.assertIsNone(result['report'])

    def test_five_agent_workflow_returns_structured_report_without_concatenating_drafts(self):
        from sdlc.agents import change_impact_agents
        from sdlc.graphs.change_impact_graph import run_change_impact_workflow
        final = {'title': 'Discount order totals', 'summary': 'Apply a 10% discount and review checkout.',
                 'overall_risk': 'Unknown', 'risk_reason': 'Coverage requires review.',
                 'tests': [{'scenario': 'Subtotal 200', 'expected_result': 'Total 180'}]}

        def model(prompt, **kwargs):
            return json.dumps(final) if 'This is the final report synthesis.' in prompt else 'Internal draft notes'

        with tracing_context(enabled=False), patch.object(change_impact_agents, 'call_llm', side_effect=model) as llm:
            result = run_change_impact_workflow('Discount totals', repository_context='No source evidence available.')
        self.assertEqual(llm.call_count, 5)
        self.assertEqual(result['report']['title'], 'Discount order totals')
        self.assertIn('Total 180', result['document'])
        self.assertNotIn('Internal draft notes', result['document'])
        self.assertEqual(len(result['trace']), 5)


    def test_api_rejects_missing_or_invalid_inputs(self):
        import app as api
        client = api.app.test_client()
        for payload in ({'change': 'Change totals'}, {'change': None}, ['invalid'], {'change': 'Change totals', 'repo': {'local_path': 'relative/path'}}, {'change': 'Change totals', 'repo': {'git_url': '   '}}):
            response = client.post('/api/change-impact/start-simple', json=payload)
            self.assertEqual(response.status_code, 400, payload)
        with tempfile.TemporaryDirectory() as directory, patch.object(api, 'start_job_async') as start:
            response = client.post('/api/change-impact/start-simple', json={'change': 'Change totals', 'repo': {'local_path': directory}})
            self.assertEqual(response.status_code, 200)
            self.assertEqual(start.call_args.args[3][0]['local_path'], str(Path(directory).resolve()))

    def test_status_exposes_actionable_failure(self):
        import app as api
        with patch.object(repo_store, 'get_job', return_value={'status': 'failed', 'result': {'error': 'MCP executable missing'}}):
            response = api.app.test_client().get('/api/change-impact/status?job_id=failed')
        self.assertEqual(response.json['job']['error'], 'MCP executable missing')


if __name__ == '__main__':
    unittest.main()
