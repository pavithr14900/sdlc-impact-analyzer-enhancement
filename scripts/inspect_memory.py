"""Print the installed codebase-memory MCP tool schemas (no indexing)."""
import asyncio
import json
import os
import sys
from pathlib import Path

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from sdlc.integrations.mcp_client import connect, server_command


async def main():
    if '--collect' in sys.argv:
        from sdlc.services.change_impact_service import collect_repository_evidence, build_repository_context
        repo = Path(__file__).resolve().parents[1] / 'tests/fixtures/memory_repo'
        result = await collect_repository_evidence('Allow discounts when calculating an order total', [str(repo)], lambda stage: print(stage, flush=True))
        context = build_repository_context(result)
        assert result['dependencies'], 'No dependencies retrieved'
        assert 'checkout' in json.dumps(result['dependencies']), 'Known caller was not found'
        assert 'calculate_total' in context, 'Model did not receive relevant source evidence'
        print(json.dumps({'indexed': result['indexed'], 'dependency_count': len(result['dependencies']), 'evidence_count': len(result['evidence']), 'warnings': result['warnings']}), flush=True)
        return
    if '--smoke' in sys.argv:
        repo = Path(__file__).resolve().parents[1] / 'tests/fixtures/memory_repo'
        async with connect(str(repo)) as memory:
            for name, args in [
                ('index_repository', {'repo_path': str(repo), 'name': 'sdlc-impact-smoke', 'persistence': False}),
                ('search_graph', {'project': 'sdlc-impact-smoke', 'query': 'calculate total', 'format': 'json', 'limit': 5}),
                ('trace_path', {'project': 'sdlc-impact-smoke', 'function_name': 'calculate_total', 'format': 'json', 'direction': 'both', 'depth': 2, 'include_tests': True, 'include_evidence': True}),
                ('search_code', {'project': 'sdlc-impact-smoke', 'pattern': 'calculate_total', 'limit': 5}),
            ]:
                print(json.dumps({'tool': name, 'result': await memory.call(name, **args)}), flush=True)
        return
    command = server_command()
    async with stdio_client(StdioServerParameters(command=command)) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            result = await session.list_tools()
            for tool in result.tools:
                if '--all' in sys.argv or tool.name in {'index_repository', 'list_projects', 'search_graph', 'search_code', 'trace_call_path', 'trace_path', 'get_architecture', 'get_code_snippet', 'check_index_coverage'}:
                    print(json.dumps({'name': tool.name, 'schema': tool.inputSchema}))


if __name__ == '__main__':
    asyncio.run(main())
