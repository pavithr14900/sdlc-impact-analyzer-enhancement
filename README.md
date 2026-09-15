# SDLC Application Builder and Change Impact Analyzer

This application supports two workflows through a React frontend and Flask backend, with Amazon Bedrock generating the analysis and implementation content:

- **Application Builder** turns a business requirement into Software Development Life Cycle (SDLC) deliverables, from requirement analysis through code, tests, infrastructure and documentation.
- **Change Impact** analyzes an existing repository using codebase memory to identify affected components and recommend implementation and testing work.

## SDLC Application Builder

### Using the workflow

1. Open **Application Builder** and describe the application, users, business workflows and expected outcomes in **Business Requirement**.
2. Optionally open **Build Settings** to upload development and design guidelines or import them from a URL. Click **Done** to process and save the guidance before starting the build. Development guidance informs generation; design guidance informs the prototype's colours, typography, components and accessibility rules.
3. Click **Build Application** and select the sections to generate. Selected stages run in the order below; skipped stages do not supply their outputs to later stages.
4. Review each generated section. Use the correction action to regenerate the current stage with feedback, or approve/continue to the next selected stage. The returned context carries earlier outputs into subsequent stages.
5. Inspect the prototype, architecture and data-model views, browse generated code, and preview or download available documents. Include **Final Assembly** to save the combined developer implementation pack.

### Stages and deliverables

| Stage | API stage name | Deliverable |
| --- | --- | --- |
| Requirement Summary | `requirement` | Analysis of the business requirement and scope. |
| User Stories & Acceptance Criteria | `user_stories` | User stories with acceptance criteria. |
| Interactive Application Prototype | `prototype` | A UI prototype based on the requirement, stories and design guidance. |
| Architecture Design | `architecture` | Proposed application architecture and component responsibilities. |
| API Design | `api_design` | API contracts and request/response details. |
| Data Model | `data_model` | Entities, relationships and database design. |
| Generated Code | `generate_code` | Application source files written to the backend output directory. |
| Test Strategy | `test_strategy` | Testing approach and generated test files. |
| Terraform / Infrastructure as Code | `infrastructure` | Infrastructure plan and generated Terraform files. |
| Security Considerations | `security` | Security controls and recommendations. |
| Developer Checklist | `checklist` | Implementation and review tasks. |
| Documentation | `documentation` | Setup guide, user guide, API documentation, data-model documentation and release notes. |
| Final Assembly | `assemble` | Combined SDLC Developer Implementation Pack. |

Generated code, tests and Terraform are saved as artifacts; this workflow does not execute the generated tests or deploy the generated application.

### Generated files

The default output directory is `generated/` on the backend machine. Set `SDLC_OUTPUT_DIR` to change it.

| Location | Contents |
| --- | --- |
| `generated/requirement-analysis.md` | Combined developer pack written by Final Assembly. |
| `generated/architecture.drawio` | Architecture diagram when diagram XML is available. |
| `generated/code/` | Generated application source, test and infrastructure files. |
| `generated/code/docs/` | `README.md`, `user-guide.md`, `api-documentation.md`, `data-model-documentation.md`, `release-notes.md`, and PDF exports when conversion succeeds. |
| `generated/knowledge_base.json` | Stored guidance used for retrieval during generation. |

Outputs use a shared directory rather than a separate folder per build, so later runs can replace earlier artifacts. Uploaded guidance is stored locally and relevant excerpts are included in Bedrock prompts.

### Optional delivery integrations

Generated sections expose **Push to Jira**, **Publish to Confluence**, and **Commit to GitHub** actions. Configure the corresponding backend environment variables before using them:

| Integration | Configuration |
| --- | --- |
| Jira user stories | `JIRA_BASE_URL`, `JIRA_EMAIL`, `JIRA_API_TOKEN`, `JIRA_PROJECT_KEY`; optional `JIRA_ISSUE_TYPE` (default: `Story`). |
| Confluence documentation | `CONFLUENCE_BASE_URL`, `CONFLUENCE_EMAIL`, `CONFLUENCE_API_TOKEN`, `CONFLUENCE_SPACE_KEY`; optional `CONFLUENCE_PARENT_PAGE_ID`. |
| GitHub generated code | `GITHUB_TOKEN`, `GITHUB_REPO` (`owner/repository`); optional `GITHUB_BRANCH` (default: `main`). |

These actions create issues, publish documentation or commit generated files to the configured service when invoked.

## Change impact analysis with codebase memory

Enter a change description and paste an absolute local repository folder path in **Change Impact**. Click **Analyze impact**. The backend starts the installed [codebase-memory-mcp](https://github.com/DeusData/codebase-memory-mcp) process over MCP stdio, indexes that folder, retrieves relevant code, and traces callers and callees before the existing Bedrock agents generate the report.

The report explains current versus intended behavior, who is affected, why each component matters, and the edit or review it needs. It also includes data/API/access findings, risks and mitigations, ordered implementation steps with completion checks, and proposed test scenarios with observable expected results. Tests in the report are recommendations and have not been executed by the analysis.

Use the section links to navigate, filter components by direct edits/downstream checks/scope confirmation, and open individual source references to inspect code excerpts. Coverage gaps appear near the summary; detailed evidence remains expandable. Export includes the report, original request, repository paths, source references and retrieval limits. Missing MCP setup or indexing failures appear as failed jobs. Run a new analysis to generate the additional content; previously saved reports still display.

## Run locally (PowerShell)

From the repository root (Python 3.11+):

```powershell
# First-time setup, if .venv does not exist:
python -m venv .venv
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

Both workflows use the backend at `http://localhost:5000`. Configure AWS credentials for the backend with access to the selected Bedrock model. The backend loads `.env` from the repository root. These are the application defaults:

```dotenv
AWS_REGION=eu-west-2
BEDROCK_MODEL_ID=amazon.nova-lite-v1:0
SDLC_OUTPUT_DIR=generated
```

Optional tracing uses `LANGCHAIN_API_KEY` and `LANGSMITH_PROJECT`. The codebase-memory-mcp server is required for repository-based Change Impact analysis; the SDLC Application Builder uses Bedrock without invoking that server.

For Change Impact, the folder path must exist on the **backend machine**. It can be a source directory without `.git`. Pasted paths support spaces, surrounding double quotes, and environment variables. Git URLs remain supported; an empty branch uses the remote default branch. Reused cloned checkouts are not automatically pulled.

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

### SDLC generation

`POST /api/analyze/step` generates one stage at a time, as used by Application Builder:

```json
{
  "requirement": "Build a leave management application with employee requests and manager approvals.",
  "stage": "requirement",
  "context": {},
  "selected_sections": ["requirement", "user_stories", "architecture", "assemble"]
}
```

The response includes `success`, `stage`, `content`, `context`, `diagram`, `stages` and `complete`. Pass the returned `context` into the next stage request and update `stage` using the names in the stages table. To revise the current stage, send it again with a `correction` string. If `selected_sections` is supplied, the requested stage must be included. `complete` is true for `assemble`.

`POST /api/analyze` runs the full SDLC sequence synchronously without interactive review:

```json
{
  "requirement": "Build a leave management application with employee requests and manager approvals.",
  "context": {
    "development_standards": "Use layered services and provide unit tests.",
    "design_standards": "Use accessible forms with clear validation messages."
  }
}
```

The response includes `success`, `result`, `file`, `diagram`, `diagramFile` and `stages`. Check stage statuses and the saved developer pack for completeness: the full workflow can continue after an individual agent fails.

Supporting endpoints:

| Endpoint | Purpose |
| --- | --- |
| `POST /api/build-settings/upload` | Upload guidance as multipart `files` with `category` set to `engineering` or `design`. |
| `POST /api/build-settings/fetch-url` | Import guidance using JSON `url` and `category`. |
| `GET /api/build-settings/status` | Inspect imported guidance; accepts an optional `category`. |
| `GET /api/requirement-analysis/preview` | Preview the saved developer pack. |
| `GET /api/requirement-analysis/download` | Download the saved developer pack. |
| `GET /api/generated-code/tree` | List generated files. |
| `GET /api/generated-code/file?path=...` | Read a file relative to the generated code directory. |
| `GET /api/documentation/pdf?path=docs/README.pdf` | Preview a generated PDF; add `&download=true` to download. |
| `GET /api/health` | Check backend health. |

### Change Impact analysis

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
