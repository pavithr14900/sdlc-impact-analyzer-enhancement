# Change impact analysis with codebase memory

Enter a change description and paste an absolute local repository folder path in **Change Impact**. Click **Analyze impact**. The backend starts the installed [codebase-memory-mcp](https://github.com/DeusData/codebase-memory-mcp) process over MCP stdio, indexes that folder, retrieves relevant code, and traces callers and callees before the existing Bedrock agents generate the report.

The report explains current versus intended behavior, who is affected, why each component matters, and the edit or review it needs. It also includes data/API/access findings, risks and mitigations, ordered implementation steps with completion checks, and proposed test scenarios with observable expected results. Tests in the report are recommendations and have not been executed by the analysis.

Use the section links to navigate, filter components by direct edits/downstream checks/scope confirmation, and open individual source references to inspect code excerpts. Coverage gaps appear near the summary; detailed evidence remains expandable. Export includes the report, original request, repository paths, source references and retrieval limits. Missing MCP setup or indexing failures appear as failed jobs. Run a new analysis to generate the additional content; previously saved reports still display.

## Run locally (PowerShell)

From the repository root (Python 3.11+):

```powershell
.venv\Scripts\python.exe -m pip install -r requirements.txt
# Only needed if codebase-memory-mcp is not already installed:
npm install -g codebase-memory-mcp
.venv\Scripts\python.exe app.py
```

If `python app.py` reports `ModuleNotFoundError: No module named 'mcp'`, that `python` may be a different interpreter from the repository's `.venv`. Use the `.venv` commands above, or install dependencies with the same interpreter you use to start the app:

```powershell
python -m pip install -r requirements.txt
python app.py
```

In another terminal:

```powershell
cd frontend
npm install
npm run dev
```

Use the Vite URL printed in that terminal. Keep the existing AWS/Bedrock configuration in `.env`; it is still required for narrative and risk generation. MCP indexes locally; retrieved evidence is sent to the configured Bedrock model for assessment, and existing LangSmith tracing settings still apply.

The folder path must exist on the **backend machine**. It can be a source directory without `.git`. Pasted paths support spaces, surrounding double quotes, and environment variables. Git URLs remain supported; an empty branch uses the remote default branch. Reused cloned checkouts are not automatically pulled.

## Optional configuration

Add these only if needed to the backend `.env`, then restart the backend:

```dotenv
# Absolute native executable path. Normally detected automatically, including Windows npm installs.
# CODEBASE_MEMORY_COMMAND=C:/path/to/codebase-memory-mcp.exe
CODEBASE_MEMORY_TIMEOUT=60
CODEBASE_MEMORY_INDEX_TIMEOUT=600
```

Do not set `MCP_BASE_URL`: this integration uses the server's native MCP stdio transport, not HTTP `/index`, `/search` or `/trace` endpoints. `CODEBASE_MEMORY_COMMAND` accepts an executable path, not a shell command with arguments. Existing `CBM_*` environment settings are inherited. The application requests `persistence=false`, keeping graph artifacts out of the selected source directory. Index storage follows the server's own cache configuration.

Requires a server exposing `index_repository` with `name` and `persistence`, JSON `search_graph`, `get_code_snippet`, and `trace_path` (or `trace_call_path`). Verified against installed codebase-memory-mcp **0.10.8**. The Python MCP client dependency is in `requirements.txt`.

Optional frontend API override: `VITE_API_BASE_URL=http://localhost:5000/api` in `frontend/.env.local`.

## API

`POST /api/change-impact/start-simple`:

```json
{
  "change": "Allow discounts when calculating an order total",
  "repo": { "local_path": "C:/work/my-repository" }
}
```

The response contains `job_id`. Poll `/api/change-impact/status?job_id=...` for `pending`, `preparing`, `indexing`, `searching`, `analyzing`, `completed`, or `failed`. Failed status includes the actual error. Fetch `/api/change-impact/result?job_id=...` for the Markdown document, indexed repositories, dependency traces, risks, agent stages, source evidence and retrieval limits.

## Verification

```powershell
# Offline regression tests; model calls are mocked.
.venv\Scripts\python.exe -m unittest discover -s tests -p test_change_impact_memory.py -v
.venv\Scripts\python.exe -m unittest discover -s tests -p test_impact_report.py -v
# Installed server schemas, without indexing:
.venv\Scripts\python.exe scripts/inspect_memory.py
# Real MCP indexing/search/tracing on the tiny test fixture, without model calls:
.venv\Scripts\python.exe scripts/inspect_memory.py --collect
cd frontend
npm run build
```

Retrieval is bounded to eight extracted search terms, up to six candidate functions per repository and dependency paths up to three hops. It is an assessment of retrieved evidence, not proof that every affected file was found. Search limits, missing matches, partial indexing and truncated model context are reported explicitly. Risk severity is assessed by the model; call distance alone is not treated as a risk score.
