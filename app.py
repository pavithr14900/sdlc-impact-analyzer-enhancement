"""Flask API for the LangGraph multi-agent SDLC assistant."""

import os

from flask import Flask, Response, jsonify, request, send_file
import re
from flask_cors import CORS

from sdlc.agents.diagram_agent import diagram_agent
from sdlc.agents.quality_agent import (
    _export_documentation_pdfs,
    _write_documentation_fallback,
    regenerate_documentation_from_pack,
)
from sdlc.config import (
    ARCHITECTURE_DIAGRAM_FILE,
    GENERATED_CODE_DIR,
    MODEL_ID,
    REGION,
    REQUIREMENT_OUTPUT_FILE,
    ensure_output_dir,
)
from sdlc.config import get_model_id, set_model_id
from sdlc.graphs import (
    WORKFLOWS,
    run_change_impact_workflow,
    run_sdlc_workflow,
)
from sdlc.services import repo_store
from sdlc.services.change_impact_service import start_job_async, validate_local_path
from sdlc.legacy_intelligence.routes import legacy_intelligence_bp
from sdlc.integrations.confluence_client import publish_documentation_to_confluence
from sdlc.integrations.github_client import commit_generated_code_to_github
from sdlc.integrations.jira_client import push_user_stories_to_jira
from sdlc.rag import add_document, clear as clear_knowledge_base, get_status
from sdlc.agents import (
    api_design_agent,
    architecture_agent,
    assembler_agent,
    code_generation_agent,
    data_model_agent,
    developer_checklist_agent,
    documentation_agent,
    infrastructure_agent,
    prototype_agent,
    requirement_agent,
    security_considerations_agent,
    test_strategy_agent,
    user_story_agent,
)

app = Flask(__name__)
app.register_blueprint(legacy_intelligence_bp)

CORS(
    app,
    resources={
        r"/api/*": {
            "origins": "*"
        }
    }
)


# ============================================================
# HELPERS
# ============================================================

def _read_field(field: str, label: str):

    data = request.get_json(silent=True)

    if not data:
        return None, (
            jsonify({
                "success": False,
                "error": "Request body is required."
            }),
            400
        )

    value = str(data.get(field, "")).strip()

    if not value:
        return None, (
            jsonify({
                "success": False,
                "error": f"{label} is required."
            }),
            400
        )

    return value, None


def _banner(title: str) -> None:

    print()
    print("=" * 70)
    print(f"  {title}")
    print("=" * 70)


def _agent_names(graph) -> list[str]:

    return [
        node
        for node in graph.get_graph().nodes
        if node not in ("__start__", "__end__")
    ]


def _stages(state: dict) -> list[dict]:

    stage_order = {
        "Requirement Agent": 0,
        "Architecture Design Agent": 1,
        "API Design Agent": 2,
        "Data Model Agent": 3,
        "Test Strategy Agent": 4,
        "Security Considerations Agent": 5,
        "Developer Checklist Agent": 6,
        "Documentation Agent": 7,
        "Assembler Agent": 8,
    }
    entries = list(state.get("trace", []))
    ordered_entries = sorted(
        enumerate(entries),
        key=lambda item: (stage_order.get(item[1]["name"], 100), item[0])
    )

    seen_names = set()
    unique_entries = []
    for _, entry in ordered_entries:
        if entry["name"] in seen_names:
            continue
        seen_names.add(entry["name"])
        unique_entries.append(entry)

    return [
        {
            "name": entry["name"],
            "role": entry.get("role", ""),
            "status": entry.get("status", "completed")
        }
        for entry in unique_entries
    ]


def _failure(message: str, exc: Exception):

    print(f"\u274c {message}: {exc}")

    return jsonify({
        "success": False,
        "error": str(exc)
    }), 500


# ============================================================
# KNOWLEDGE BASE (OPTIONAL RAG STEP - CODING STANDARDS UPLOAD)
# ============================================================

ALLOWED_KNOWLEDGE_BASE_EXTENSIONS = {".txt", ".md", ".pdf"}

ALLOWED_BUILD_SETTINGS_EXTENSIONS = {".txt", ".md", ".pdf", ".docx", ".doc", ".png", ".jpg", ".jpeg"}


@app.route("/api/knowledge-base", methods=["GET"])
def api_knowledge_base_status():

    return jsonify({"success": True, **get_status()})


@app.route("/api/knowledge-base/upload", methods=["POST"])
def api_knowledge_base_upload():

    files = request.files.getlist("files")

    if not files:
        return jsonify({"success": False, "error": "Select at least one file to upload."}), 400

    added_chunks = 0
    skipped = []

    for file in files:
        filename = os.path.basename(file.filename or "")
        extension = os.path.splitext(filename)[1].lower()

        if not filename or extension not in ALLOWED_KNOWLEDGE_BASE_EXTENSIONS:
            skipped.append(filename or "unnamed file")
            continue

        try:
            # Legacy knowledge base uploads are treated as engineering docs
            added_chunks += add_document(filename, file.read(), category="engineering")
        except Exception as exc:
            return _failure(f"Could not process '{filename}'", exc)

    status = get_status()

    return jsonify({
        "success": True,
        "addedChunks": added_chunks,
        "skipped": skipped,
        **status
    })



@app.route('/api/build-settings/upload', methods=['POST'])
def api_build_settings_upload():
    """Upload files for build settings (engineering or design)."""
    files = request.files.getlist('files')
    category = str(request.form.get('category', 'engineering')).strip().lower()

    if not files:
        return jsonify({"success": False, "error": "Select at least one file to upload."}), 400

    added_chunks = 0
    skipped = []

    for file in files:
        filename = os.path.basename(file.filename or "")
        extension = os.path.splitext(filename)[1].lower()

        if not filename or extension not in ALLOWED_BUILD_SETTINGS_EXTENSIONS:
            skipped.append(filename or "unnamed file")
            continue

        try:
            added_chunks += add_document(filename, file.read(), category=category)
        except Exception as exc:
            return _failure(f"Could not process '{filename}'", exc)

    # Provide a small cached summary of the uploaded guidance to send back
    from sdlc.rag.knowledge_base import category_summary, get_status as _kb_status
    status = _kb_status()
    summary = category_summary(category)

    return jsonify({"success": True, "addedChunks": added_chunks, "skipped": skipped, "summary": summary, **status})


@app.route('/api/build-settings/fetch-url', methods=['POST'])
def api_build_settings_fetch_url():
    data = request.get_json(silent=True) or {}
    url = str(data.get('url', '')).strip()
    category = str(data.get('category', 'engineering')).strip().lower()

    if not url:
        return jsonify({"success": False, "error": "url is required."}), 400

    try:
        from sdlc.rag.design_url import fetch_guidance
        from sdlc.rag.knowledge_base import replace_category, category_summary
        documents, warnings = fetch_guidance(url, max_pages=12 if category == "design" else 1)
        added = replace_category(category, documents)
        return jsonify({
            "success": True, "addedChunks": added,
            "summary": category_summary(category),
            "sources": [source for source, _ in documents],
            "warning": " ".join(warnings), **get_status(),
        })
    except Exception as exc:
        return _failure("Failed to fetch and process URL", exc)


@app.route('/api/build-settings/status', methods=['GET'])
def api_build_settings_status():
    category = str(request.args.get('category', '')).strip().lower() or None
    from sdlc.rag.knowledge_base import category_summary, get_status as _kb_status
    status = _kb_status()
    summary = category_summary(category) if category else ""
    return jsonify({"success": True, "status": status, "summary": summary})


@app.route("/api/knowledge-base", methods=["DELETE"])
def api_knowledge_base_clear():

    clear_knowledge_base()

    return jsonify({"success": True, **get_status()})


REQUIREMENT_STAGES = [
    ("requirement", requirement_agent, "requirement_analysis"),
    ("user_stories", user_story_agent, "user_stories"),
    ("prototype", prototype_agent, "ui_prototype"),
    ("architecture", architecture_agent, "architecture"),
    ("api_design", api_design_agent, "api_design"),
    ("data_model", data_model_agent, "data_model"),
    ("generate_code", code_generation_agent, "generated_code"),
    ("test_strategy", test_strategy_agent, "test_strategy"),
    ("infrastructure", infrastructure_agent, "infrastructure"),
    ("security", security_considerations_agent, "security_considerations"),
    ("checklist", developer_checklist_agent, "developer_checklist"),
    ("documentation", documentation_agent, "documentation"),
    ("assemble", assembler_agent, "document"),
]


@app.route("/api/analyze/step", methods=["POST"])
def api_analyze_step():
    data = request.get_json(silent=True) or {}
    requirement = str(data.get("requirement", "")).strip()
    stage_name = str(data.get("stage", "")).strip()
    context = data.get("context") or {}
    correction = str(data.get("correction", "")).strip()
    selected_sections = data.get("selected_sections")
    if selected_sections is None:
        selected_sections = context.get("selected_sections")
    if selected_sections is not None:
        selected_sections = [str(section).strip() for section in selected_sections if str(section).strip()]

    if not requirement or not stage_name:
        return jsonify({"success": False, "error": "Requirement and stage are required."}), 400

    stage = next((item for item in REQUIREMENT_STAGES if item[0] == stage_name), None)
    if stage is None:
        return jsonify({"success": False, "error": "Unknown requirement stage."}), 400

    if selected_sections is not None and stage_name not in selected_sections:
        return jsonify({
            "success": False,
            "error": f"Stage '{stage_name}' was not selected for this build."
        }), 400

    try:
        stage_key, agent, output_key = stage
        request_text = requirement
        if correction:
            request_text += f"\n\nUser correction for the previous output:\n{correction}"
        state = {
            **context,
            "requirement": request_text,
            "correction": correction,
            "trace": []
        }
        if selected_sections is not None:
            state["selected_sections"] = selected_sections

        # Run the requested agent synchronously and return its immediate output.
        result = agent(state)
        next_context = {**context, **{key: value for key, value in result.items() if key != "trace"}}
        if selected_sections is not None:
            next_context["selected_sections"] = selected_sections

        return jsonify({
            "success": True,
            "stage": stage_key,
            "content": result.get(output_key, ""),
            "context": next_context,
            "diagram": result.get("diagram_xml", context.get("diagram_xml", "")),
            "stages": [{"name": getattr(agent, "__name__", stage_key), "status": "Completed"}],
            "complete": stage_key == "assemble",
        })
    except Exception as exc:
        return _failure("Requirement stage failed", exc)


# ============================================================
# REQUIREMENT ANALYSIS WORKFLOW
# ============================================================

@app.route("/api/analyze", methods=["POST"])
def api_analyze():

    requirement, error = _read_field("requirement", "Requirement")

    if error:
        return error

    try:

        _banner("SDLC AGENT GRAPH \u2014 REQUIREMENT ANALYSIS")

        state = run_sdlc_workflow(requirement, (request.get_json(silent=True) or {}).get("context"))

        _banner("WORKFLOW COMPLETED")

        print(f"\u2713 Developer pack: {REQUIREMENT_OUTPUT_FILE}")
        print(f"\u2713 draw.io diagram: {ARCHITECTURE_DIAGRAM_FILE}")

        return jsonify({
            "success": True,
            "result": state.get("document", ""),
            "file": REQUIREMENT_OUTPUT_FILE,
            "diagram": state.get("diagram_xml", ""),
            "diagramFile": ARCHITECTURE_DIAGRAM_FILE,
            "stages": _stages(state)
        })

    except Exception as exc:

        return _failure("SDLC analysis failed", exc)


# ============================================================
# CHANGE IMPACT WORKFLOW
# ============================================================

@app.route("/api/change-impact", methods=["POST"])
def api_change_impact():
    # Backwards-compatible single-call analysis is still supported, but the
    # preferred route is to start an asynchronous job via /api/change-impact/start
    data = request.get_json(silent=True) or {}
    change = str(data.get("change", "")).strip()

    if not change:
        return jsonify({"success": False, "error": "Change request is required."}), 400

    try:
        _banner("CHANGE IMPACT (synchronous fallback)")
        state = run_change_impact_workflow(change)
        document = state.get("document", "") or ""
        return jsonify({"success": True, "result": document, "stages": _stages(state)})
    except Exception as exc:
        return _failure("Change impact analysis failed", exc)


# ============================================================
# ARCHITECTURE DIAGRAM
# ============================================================

@app.route("/api/architecture-diagram", methods=["POST"])
def api_architecture_diagram():

    requirement, error = _read_field("requirement", "Requirement")

    if error:
        return error

    try:

        _banner("DIAGRAM AGENT")

        state = diagram_agent({
            "requirement": requirement,
            "architecture": ""
        })

        ensure_output_dir()

        with open(
            ARCHITECTURE_DIAGRAM_FILE,
            "w",
            encoding="utf-8"
        ) as file:
            file.write(state["diagram_xml"])

        return jsonify({
            "success": True,
            "diagram": state["diagram_xml"],
            "diagramFile": ARCHITECTURE_DIAGRAM_FILE
        })

    except Exception as exc:

        return _failure("Diagram generation failed", exc)


@app.route("/api/architecture-diagram/download", methods=["GET"])
def api_architecture_diagram_download():

    if not os.path.exists(ARCHITECTURE_DIAGRAM_FILE):

        return jsonify({
            "success": False,
            "error": "No architecture diagram has been generated yet."
        }), 404

    with open(
        ARCHITECTURE_DIAGRAM_FILE,
        "r",
        encoding="utf-8"
    ) as file:
        xml = file.read()

    return Response(
        xml,
        mimetype="application/xml",
        headers={
            "Content-Disposition":
                "attachment; filename=architecture.drawio"
        }
    )


@app.route("/api/requirement-analysis/download", methods=["GET"])
def api_requirement_analysis_download():

    if not os.path.exists(REQUIREMENT_OUTPUT_FILE):
        return jsonify({
            "success": False,
            "error": "No requirement analysis has been generated yet."
        }), 404

    return send_file(
        REQUIREMENT_OUTPUT_FILE,
        as_attachment=True,
        download_name="requirement-analysis.md",
        mimetype="text/markdown"
    )


@app.route("/api/requirement-analysis/preview", methods=["GET"])
def api_requirement_analysis_preview():

    if not os.path.exists(REQUIREMENT_OUTPUT_FILE):
        return jsonify({
            "success": False,
            "error": "No requirement analysis has been generated yet."
        }), 404

    with open(REQUIREMENT_OUTPUT_FILE, "r", encoding="utf-8") as file:
        content = file.read()

    return Response(content, mimetype="text/plain; charset=utf-8")


FILE_LANGUAGE_MAP = {
    ".java": "java",
    ".ts": "typescript",
    ".tsx": "tsx",
    ".js": "javascript",
    ".jsx": "jsx",
    ".sql": "sql",
    ".json": "json",
    ".yml": "yaml",
    ".yaml": "yaml",
    ".md": "markdown",
    ".xml": "xml",
    ".properties": "properties",
}


def _build_code_tree(root: str, current: str) -> list[dict]:

    entries = []

    for name in sorted(os.listdir(current)):
        full_path = os.path.join(current, name)
        rel_path = os.path.relpath(full_path, root).replace("\\", "/")

        if os.path.isdir(full_path):
            entries.append({
                "name": name,
                "path": rel_path,
                "type": "folder",
                "children": _build_code_tree(root, full_path)
            })
        else:
            entries.append({
                "name": name,
                "path": rel_path,
                "type": "file"
            })

    return entries


@app.route("/api/generated-code/tree", methods=["GET"])
def api_generated_code_tree():

    prefix = str(request.args.get("prefix", "")).strip()
    safe_prefix = os.path.normpath(prefix).replace("\\", "/").lstrip("/") if prefix else ""

    if safe_prefix.startswith(".."):
        return jsonify({"success": False, "error": "Invalid prefix."}), 400

    root = os.path.join(GENERATED_CODE_DIR, safe_prefix) if safe_prefix else GENERATED_CODE_DIR

    if not os.path.abspath(root).startswith(os.path.abspath(GENERATED_CODE_DIR)):
        return jsonify({"success": False, "error": "Invalid prefix."}), 400

    if not os.path.isdir(root):
        return jsonify({"success": True, "tree": []})

    tree = _build_code_tree(GENERATED_CODE_DIR, root)

    return jsonify({"success": True, "tree": tree})


@app.route("/api/generated-code/file", methods=["GET"])
def api_generated_code_file():

    raw_path = str(request.args.get("path", "")).strip()

    if not raw_path:
        return jsonify({"success": False, "error": "path is required."}), 400

    safe_path = os.path.normpath(raw_path).replace("\\", "/").lstrip("/")

    if safe_path.startswith("..") or not safe_path:
        return jsonify({"success": False, "error": "Invalid path."}), 400

    full_path = os.path.join(GENERATED_CODE_DIR, safe_path)

    if not os.path.abspath(full_path).startswith(os.path.abspath(GENERATED_CODE_DIR)):
        return jsonify({"success": False, "error": "Invalid path."}), 400

    if not os.path.isfile(full_path):
        return jsonify({"success": False, "error": "File not found."}), 404

    with open(full_path, "r", encoding="utf-8") as file:
        content = file.read()

    extension = os.path.splitext(full_path)[1].lower()

    return jsonify({
        "success": True,
        "path": safe_path,
        "content": content,
        "language": FILE_LANGUAGE_MAP.get(extension, "text")
    })





@app.route("/api/documentation/pdf", methods=["GET", "POST"])
def api_documentation_pdf():

    payload = request.get_json(silent=True) or {}
    raw_path = str(payload.get("path", request.args.get("path", ""))).strip()
    download = str(request.args.get("download", "")).lower() == "true"
    safe_path = os.path.normpath(raw_path).replace("\\", "/").lstrip("/")

    if (
        safe_path.startswith("..")
        or not safe_path.startswith("docs/")
        or not safe_path.lower().endswith(".pdf")
    ):
        return jsonify({"success": False, "error": "Invalid documentation path."}), 400

    full_path = os.path.join(GENERATED_CODE_DIR, safe_path)
    docs_dir = os.path.join(GENERATED_CODE_DIR, "docs")

    if not os.path.abspath(full_path).startswith(os.path.abspath(docs_dir)):
        return jsonify({"success": False, "error": "Invalid documentation path."}), 400

    if request.method == "POST" and not os.path.isfile(full_path):
        plan = str(payload.get("plan", "")).strip()
        full_document = str(payload.get("fullDocument", "")).strip()
        if not plan and not full_document:
            return jsonify({"success": False, "error": "Documentation content is required."}), 400
        try:
            written_files = []
            if full_document:
                # Prefer regenerating the full detailed documents (same
                # quality as the real pipeline run) from the complete
                # assembled pack, instead of the short plan-only summary.
                written_files = regenerate_documentation_from_pack(full_document)
            if not written_files and plan:
                written_files = _write_documentation_fallback(plan)
            _export_documentation_pdfs(written_files)
        except Exception as exc:
            return _failure("Documentation PDF generation failed", exc)

    if not os.path.isfile(full_path):
        legacy_path = os.path.join(docs_dir, safe_path)
        if os.path.abspath(legacy_path).startswith(os.path.abspath(docs_dir)):
            full_path = legacy_path

    if request.method == "POST":
        if os.path.isfile(full_path):
            return jsonify({"success": True})
        return jsonify({
            "success": False,
            "error": f"'{safe_path}' does not match a generated document."
        }), 404

    if not os.path.isfile(full_path):
        return jsonify({"success": False, "error": "Documentation PDF not found."}), 404

    return send_file(
        full_path,
        mimetype="application/pdf",
        as_attachment=download,
        download_name=os.path.basename(full_path),
    )


# ============================================================
# THIRD-PARTY INTEGRATIONS
# ============================================================

@app.route("/api/integrations/jira/push-stories", methods=["POST"])
def api_jira_push_stories():

    data = request.get_json(silent=True) or {}
    user_stories = str(data.get("user_stories", "")).strip()

    if not user_stories:
        return jsonify({"success": False, "error": "User stories content is required."}), 400

    try:
        return jsonify({"success": True, "issues": push_user_stories_to_jira(user_stories)})
    except Exception as exc:
        return _failure("Jira push failed", exc)


@app.route("/api/integrations/confluence/publish-docs", methods=["POST"])
def api_confluence_publish_docs():

    try:
        docs_dir = os.path.join(GENERATED_CODE_DIR, "docs")
        return jsonify({"success": True, "pages": publish_documentation_to_confluence(docs_dir)})
    except Exception as exc:
        return _failure("Confluence publish failed", exc)


@app.route("/api/integrations/github/commit-code", methods=["POST"])
def api_github_commit_code():

    data = request.get_json(silent=True) or {}
    message = str(data.get("message", "")).strip() or "Add generated application code"

    try:
        return jsonify({"success": True, "commit": commit_generated_code_to_github(GENERATED_CODE_DIR, message)})
    except Exception as exc:
        return _failure("GitHub commit failed", exc)


# ============================================================
# WORKFLOW INTROSPECTION
# ============================================================

@app.route("/api/workflows", methods=["GET"])
def api_workflows():

    return jsonify({
        "success": True,
        "workflows": {
            name: {
                "agents": _agent_names(graph),
                "mermaid": graph.get_graph().draw_mermaid()
            }
            for name, graph in WORKFLOWS.items()
        }
    })


@app.route("/api/models", methods=["GET"])
def api_models():
    """List available model options for the UI selector."""
    models = [
        {"id": "amazon.nova-lite-v1:0", "label": "Amazon Nova Lite v1"},
        {"id": "eu.anthropic.claude-haiku-4-5-20251001-v1:0", "label": "Claude Haiku 4.5"},
    ]
    return jsonify({"success": True, "models": models})


@app.route("/api/model", methods=["GET", "POST"])
def api_model():
    """Get or set the active model id used for LLM calls at runtime.

    GET returns the current model id. POST accepts JSON {"model_id": "..."}
    and updates the runtime model.
    """
    if request.method == "GET":
        return jsonify({"success": True, "model_id": get_model_id()})

    data = request.get_json(silent=True) or {}
    model_id = str(data.get("model_id", "")).strip()
    if not model_id:
        return jsonify({"success": False, "error": "model_id is required."}), 400

    try:
        set_model_id(model_id)
        return jsonify({"success": True, "model_id": get_model_id()})
    except Exception as exc:
        return _failure("Failed to set model", exc)


@app.route("/api/mcp/discover", methods=["GET"])
def api_mcp_discover():
    """Attempt to discover an MCP server and return capabilities or an error."""
    try:
        info = mcp_client.discover()
        return jsonify({"success": True, "mcp": info})
    except Exception as exc:
        return jsonify({"success": False, "error": str(exc)}), 502


# ------------------------------------------------------------
# Workspaces, repositories and change-impact job APIs
# ------------------------------------------------------------


@app.route("/api/workspaces", methods=["GET", "POST"])
def api_workspaces():
    if request.method == "GET":
        return jsonify({"success": True, "workspaces": repo_store.list_workspaces()})

    data = request.get_json(silent=True) or {}
    name = str(data.get("name", "")).strip() or "default"
    ws = repo_store.create_workspace(name)
    return jsonify({"success": True, "workspace": ws})


@app.route("/api/workspaces/<int:workspace_id>/repos", methods=["GET", "POST"])
def api_workspace_repos(workspace_id: int):
    if request.method == "GET":
        return jsonify({"success": True, "repositories": repo_store.list_repositories(workspace_id)})

    data = request.get_json(silent=True) or {}
    name = str(data.get("name", "")).strip() or "repo"
    git_url = str(data.get("git_url", "")).strip() or None
    local_path = str(data.get("local_path", "")).strip() or None
    branch = str(data.get("branch", "")).strip() or None
    repo = repo_store.add_repository(workspace_id, name, git_url, local_path, branch)
    return jsonify({"success": True, "repository": repo})


@app.route("/api/change-impact/start", methods=["POST"])
def api_change_impact_start():
    data = request.get_json(silent=True) or {}
    change = str(data.get("change", "")).strip()
    workspace_id = data.get("workspace_id")
    repository_ids = data.get("repository_ids", [])
    options = data.get("options", {}) or {}

    if not change:
        return jsonify({"success": False, "error": "Change request is required."}), 400

    # resolve repositories by ids
    selected = []
    if repository_ids:
        all_repos = repo_store.list_repositories()
        id_map = {r["id"]: r for r in all_repos}
        for rid in repository_ids:
            r = id_map.get(rid)
            if r:
                selected.append(r)

    # create job id and start async worker
    import uuid
    job_id = str(uuid.uuid4())
    try:
        start_job_async(job_id, change, workspace_id, selected, options)
        return jsonify({"success": True, "job_id": job_id})
    except ValueError as exc:
        return jsonify({"success": False, "error": str(exc)}), 400
    except Exception as exc:
        return _failure("Failed to start change impact job", exc)



@app.route("/api/change-impact/start-simple", methods=["POST"])
def api_change_impact_start_simple():
    """Start a change-impact job with a single repository spec provided inline.

    JSON body: { change: string, repo: { git_url?: str, branch?: str, local_path?: str }, options?: {} }
    """
    data = request.get_json(silent=True) or {}
    if not isinstance(data, dict) or not isinstance(data.get("change", ""), str):
        return jsonify({"success": False, "error": "Provide a JSON object with a text change description."}), 400
    change = data.get("change", "").strip()
    repo = data.get("repo") or {}
    options = data.get("options", {}) or {}

    if not change:
        return jsonify({"success": False, "error": "Change request is required."}), 400

    if not isinstance(repo, dict) or not (repo.get("local_path") or repo.get("git_url")):
        return jsonify({"success": False, "error": "Provide a local repository path or Git URL."}), 400
    for field in ("local_path", "git_url", "branch"):
        if repo.get(field) is not None and not isinstance(repo[field], str):
            return jsonify({"success": False, "error": f"{field} must be a string."}), 400
    for field in ("git_url", "branch"):
        if repo.get(field):
            repo[field] = repo[field].strip()
    if not (repo.get("local_path") or repo.get("git_url")):
        return jsonify({"success": False, "error": "Provide a local repository path or Git URL."}), 400
    if repo.get("local_path"):
        try:
            repo["local_path"] = validate_local_path(repo["local_path"])
        except ValueError as exc:
            return jsonify({"success": False, "error": str(exc)}), 400

    selected = []
    # repo may be a dict with git_url or local_path
    if repo:
        selected.append({
            "git_url": repo.get("git_url"),
            "local_path": repo.get("local_path"),
            "branch": repo.get("branch")
        })

    import uuid
    job_id = str(uuid.uuid4())
    try:
        start_job_async(job_id, change, None, selected, options)
        return jsonify({"success": True, "job_id": job_id})
    except ValueError as exc:
        return jsonify({"success": False, "error": str(exc)}), 400
    except Exception as exc:
        return _failure("Failed to start change impact job", exc)


@app.route("/api/pick-folder", methods=["POST"])
def api_pick_folder():
    """Open a native folder picker on the backend host and return the chosen path.

    NOTE: This only works when the backend is running on a machine with a
    desktop session. If unavailable, the endpoint returns an error explaining
    alternatives.
    """
    try:
        # Import lazily to avoid requiring tkinter in headless environments
        import tkinter as tk
        from tkinter import filedialog

        root = tk.Tk()
        root.withdraw()
        root.attributes("-topmost", True)
        path = filedialog.askdirectory()
        root.destroy()

        if not path:
            return jsonify({"success": False, "error": "No folder selected."}), 400

        return jsonify({"success": True, "path": path})
    except Exception as exc:
        return jsonify({"success": False, "error": f"Folder picker unavailable: {exc}"}), 500


@app.route("/api/upload-repo", methods=["POST"])
def api_upload_repo():
    """Accept a zip file upload of a repository, extract it into the repos root and return the local path.

    Form field: 'file' (zip archive)
    """
    file = request.files.get("file")
    if not file:
        return jsonify({"success": False, "error": "No file uploaded."}), 400

    filename = file.filename or "repo.zip"
    if not filename.lower().endswith(".zip"):
        return jsonify({"success": False, "error": "Only .zip uploads are supported."}), 400

    import zipfile
    import uuid
    import shutil

    repo_root = os.environ.get("CHANGE_IMPACT_REPOS", "data/repos")
    os.makedirs(repo_root, exist_ok=True)

    uid = uuid.uuid4().hex[:10]
    target_dir = os.path.join(repo_root, f"uploaded-{uid}")
    os.makedirs(target_dir, exist_ok=True)

    temp_zip = os.path.join(target_dir, "upload.zip")
    file.save(temp_zip)

    try:
        with zipfile.ZipFile(temp_zip, 'r') as z:
            # safe extraction: prevent path traversal
            for member in z.namelist():
                member_path = os.path.normpath(member)
                if member_path.startswith('..'):
                    return jsonify({"success": False, "error": "Invalid archive (path traversal)."}), 400
            z.extractall(target_dir)

        # If archive contains a single top-level folder, use that
        entries = [e for e in os.listdir(target_dir) if e != 'upload.zip']
        if len(entries) == 1 and os.path.isdir(os.path.join(target_dir, entries[0])):
            extracted = os.path.join(target_dir, entries[0])
        else:
            extracted = target_dir

        return jsonify({"success": True, "path": os.path.abspath(extracted)})
    except zipfile.BadZipFile:
        shutil.rmtree(target_dir, ignore_errors=True)
        return jsonify({"success": False, "error": "Uploaded file is not a valid zip archive."}), 400
    except Exception as exc:
        shutil.rmtree(target_dir, ignore_errors=True)
        return jsonify({"success": False, "error": str(exc)}), 500


@app.route("/api/change-impact/status", methods=["GET"])
def api_change_impact_status():
    job_id = str(request.args.get("job_id", "")).strip()
    if not job_id:
        return jsonify({"success": False, "error": "job_id is required."}), 400
    job = repo_store.get_job(job_id)
    if not job:
        return jsonify({"success": False, "error": "job not found."}), 404
    return jsonify({"success": True, "job": {"id": job_id, "status": job.get("status"), "error": (job.get("result") or {}).get("error"), "created_at": job.get("created_at"), "updated_at": job.get("updated_at")}})


@app.route("/api/change-impact/result", methods=["GET"])
def api_change_impact_result():
    job_id = str(request.args.get("job_id", "")).strip()
    if not job_id:
        return jsonify({"success": False, "error": "job_id is required."}), 400
    job = repo_store.get_job(job_id)
    if not job:
        return jsonify({"success": False, "error": "job not found."}), 404
    return jsonify({"success": True, "job": job})


# ============================================================
# HEALTH CHECK
# ============================================================

@app.route("/api/health", methods=["GET"])
def health():

    return jsonify({
        "status": "UP",
        "service": "AI SDLC Multi-Agent Assistant",
        "orchestrator": "LangGraph",
        "model": MODEL_ID,
        "region": REGION
    })


# ============================================================
# APPLICATION START
# ============================================================

if __name__ == "__main__":

    _banner("AI SDLC MULTI-AGENT ASSISTANT")

    # initialize DB for repo/job storage
    try:
        repo_store.init_db()
    except Exception as exc:
        print(f"Warning: could not initialize DB: {exc}")

    print()
    print("\u2713 LangGraph workflows compiled")
    print(f"\u2713 AWS Region: {REGION}")
    print(f"\u2713 Bedrock Model: {MODEL_ID}")

    print()
    print("Agent graphs:")

    for workflow_name, workflow in WORKFLOWS.items():
        print(
            f"  {workflow_name:<16} "
            f"{' \u2192 '.join(_agent_names(workflow))}"
        )

    print()
    print("Available endpoints:")
    print("  POST  /api/analyze")
    print("  POST  /api/knowledge-base/upload")
    print("  GET   /api/knowledge-base")
    print("  DELETE /api/knowledge-base")
    print("  POST  /api/change-impact")
    print("  POST  /api/architecture-diagram")
    print("  GET   /api/architecture-diagram/download")
    print("  GET   /api/workflows")
    print("  GET   /api/health")
    print()

    app.run(
        host="0.0.0.0",
        port=5000,
        debug=True
    )
