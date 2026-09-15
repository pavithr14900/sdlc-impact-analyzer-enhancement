"""Retrieve repository evidence before generating a change impact assessment."""
from __future__ import annotations

import asyncio
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import threading
from typing import Any

from sdlc.integrations import mcp_client
from sdlc.services import repo_store
from sdlc.services.impact_report import render_analysis_appendix

REPOS_ROOT = os.environ.get("CHANGE_IMPACT_REPOS", "data/repos")


def validate_local_path(value: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError("Enter a local repository folder path.")
    path = Path(os.path.expandvars(value.strip().strip('"'))).expanduser()
    if not path.is_absolute():
        raise ValueError("Local repository path must be absolute and accessible on the backend machine.")
    if not path.is_dir():
        raise ValueError(f"Repository folder not found on the backend machine: {path}")
    return str(path.resolve())


def _ensure_local_checkout(git_url, local_path, branch) -> str:
    if local_path:
        return validate_local_path(local_path)
    if not isinstance(git_url, str) or not git_url.strip() or git_url.startswith("-"):
        raise ValueError("Provide a local repository path or a Git URL.")
    repo_id = hashlib.sha256((git_url + (branch or "")).encode()).hexdigest()[:16]
    dest = Path(REPOS_ROOT).resolve() / repo_id
    if (dest / ".git").exists():
        return str(dest)
    dest.parent.mkdir(parents=True, exist_ok=True)
    command = ["git", "clone", "--no-tags", "--depth", "1"]
    if branch:
        command += ["--branch", branch]
    command += ["--", git_url, str(dest)]
    subprocess.run(command, check=True, capture_output=True, text=True, timeout=300,
                   creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0)
    return str(dest)


def _search_terms(change: str) -> list[str]:
    """Include plain-language terms as well as explicit paths and identifiers."""
    explicit = re.findall(r"/[-A-Za-z0-9_/{}]+|[A-Za-z_][\w.]*\(\)|[A-Za-z_]\w*(?:\.[A-Za-z_]\w*)+", change)
    words = re.findall(r"[A-Za-z_][A-Za-z0-9_]{2,}", change)
    stop = set("the and for with from this that should would could change update add allow need want when then into using must will have has are was were can not new existing support please implement make give enable able include instead after before without behavior behaviour requested request application system code repository".split())
    identifiers = [word for word in words if "_" in word or re.search(r"[a-z][A-Z]", word)]
    candidates = explicit + identifiers + [word for word in words if word.lower() not in stop]
    return list(dict.fromkeys(word.removesuffix("()") for word in candidates))[:8]


def graph_rows(value: Any) -> list[dict]:
    """Decode CBM's JSON column/row format, including prefix-grouped traces."""
    rows = []
    if isinstance(value, dict):
        columns = value.get("cols", [])
        for row in value.get("rows", []):
            if isinstance(row, dict):
                rows.append(row)
            elif isinstance(row, list):
                rows.append(dict(zip(columns, row)))
        for group in value.get("groups", []):
            for row in graph_rows({"cols": columns, **group}):
                prefix = group.get("qn_prefix", "")
                if prefix:
                    key = "qn" if "qn" in row else "name"
                    if row.get(key):
                        row["qn"] = prefix + "." + str(row[key])
                rows.append(row)
        for key in ("results", "semantic_results", "callers", "callees"):
            child = value.get(key)
            if isinstance(child, (dict, list)):
                rows.extend(graph_rows(child))
        if value.get("qualified_name"):
            rows.append(value)
    elif isinstance(value, list):
        for item in value:
            rows.extend(graph_rows(item))
    return rows


async def collect_repository_evidence(change: str, repo_paths: list[str], progress=lambda stage: None) -> dict:
    evidence, indexed, dependencies, warnings = [], [], [], []
    symbols = []

    def record(project, tool, arguments, result):
        item = {"id": f"E{len(evidence) + 1}", "project": project, "tool": tool, "arguments": arguments, "result": result}
        evidence.append(item)
        return item["id"]

    for path in repo_paths:
        project = "impact-" + hashlib.sha256(os.path.normcase(path).encode()).hexdigest()[:16]
        progress("indexing")
        async with mcp_client.connect(path) as memory:
            args = {"repo_path": path, "name": project, "persistence": False}
            if not memory.supports("index_repository", "name"):
                raise mcp_client.McpError("Update codebase-memory-mcp: this integration requires named repository indexes.")
            index = await memory.call("index_repository", **args)
            if not isinstance(index, dict) or index.get("status") not in {"indexed", "up_to_date", "unchanged"}:
                raise mcp_client.McpError(f"Repository indexing did not complete successfully: {index}")
            project = index.get("project") or project
            indexed.append({"path": path, "project": project, "index": index})
            record(project, "index_repository", args, index)
            for counter in ("not_indexed_files_count", "skipped_count", "parse_partial_count"):
                if index.get(counter):
                    warnings.append(f"{project}: {counter} = {index[counter]}; coverage is incomplete.")
            progress("searching")

            async def query(tool, **kwargs):
                args = {"project": project, **kwargs}
                try:
                    result = await memory.call(tool, **args)
                    return result, record(project, tool, args, result)
                except mcp_client.McpError as exc:
                    warnings.append(str(exc))
                    return None, None

            await query("get_architecture", aspects=["overview"])
            if memory.supports("check_index_coverage"):
                await query("check_index_coverage", scopes=["."], scope_limit=100)
            else:
                warnings.append(f"{project}: installed server cannot report detailed index coverage.")
            terms = _search_terms(change)
            searches = [change[:1000], *terms]
            candidates = {}
            successful_searches = 0
            for term in dict.fromkeys(searches):
                result, _ = await query("search_graph", query=term, format="json", limit=8)
                if result is not None:
                    successful_searches += 1
                    for row in graph_rows(result):
                        name = row.get("qn") or row.get("qualified_name")
                        if name and row.get("label") in {"Function", "Method"}:
                            candidates.setdefault(name, row)
                    if isinstance(result, dict) and result.get("has_more"):
                        warnings.append(f"{project}: search for {term!r} was limited to 8 results.")
            for term in terms[:4]:
                await query("search_code", pattern=term, limit=8)
            if not successful_searches:
                raise mcp_client.McpError("All repository symbol searches failed; cannot generate an evidence-based assessment.")
            if not candidates:
                warnings.append(f"{project}: no matching functions were found. Dependency impact is unverified; describe specific features, APIs or symbols to refine retrieval.")
            if len(candidates) > 6:
                warnings.append(f"{project}: tracing the first 6 of {len(candidates)} candidate functions.")
            neighbors = set()
            selected = list(candidates)[:6]
            for name in selected:
                symbols.append(name)
                await query("get_code_snippet", qualified_name=name)
                trace_tool = "trace_path" if memory.supports("trace_path") else "trace_call_path"
                trace_args = {"function_name": name, "direction": "both", "depth": 3}
                for key, value in {"format": "json", "limit": 40, "include_tests": True, "include_evidence": True}.items():
                    if memory.supports(trace_tool, key):
                        trace_args[key] = value
                trace, evidence_id = await query(trace_tool, **trace_args)
                if trace is not None:
                    dependencies.append({"project": project, "symbol": name, "evidence_id": evidence_id, "trace": trace})
                    for row in graph_rows(trace):
                        neighbor = row.get("qn") or row.get("qualified_name")
                        if neighbor and neighbor not in selected:
                            neighbors.add(neighbor)
                    if isinstance(trace, dict) and trace.get("next"):
                        warnings.append(f"{name}: dependency trace was limited to 40 rows.")
            for neighbor in sorted(neighbors)[:4]:
                await query("get_code_snippet", qualified_name=neighbor)
            if len(neighbors) > 4:
                warnings.append(f"{project}: source snippets include only 4 of {len(neighbors)} traced neighbors.")

    warnings.append("Retrieval is bounded: keyword searches, up to 6 candidate functions per repository, and call paths up to 3 hops. Dynamic calls and unindexed code may be missing. Trace proximity is not a business risk score.")
    return {"indexed": indexed, "symbols": symbols, "dependencies": dependencies, "evidence": evidence, "warnings": list(dict.fromkeys(warnings))}


def build_repository_context(findings: dict) -> str:
    """Keep valid, cited evidence blocks within a bounded model prompt."""
    blocks, used = [], 0
    priority = {"get_code_snippet": 0, "trace_path": 1, "trace_call_path": 1, "get_architecture": 2, "check_index_coverage": 3}
    for item in sorted(findings["evidence"], key=lambda item: priority.get(item.get("tool"), 4)):
        block = json.dumps(item, ensure_ascii=False, default=str)
        if len(block) > 7000:
            block = json.dumps({**item, "result": {"excerpt": json.dumps(item["result"], ensure_ascii=False)[:6500], "truncated": True}}, ensure_ascii=False)
            findings["warnings"].append(f"{item['id']}: model context contains an excerpt; full result is available under Source evidence.")
        if used + len(block) > 65000:
            findings["warnings"].append(f"Model context budget reached at {item['id']}; remaining evidence is available in the report data but was not assessed by the model.")
            break
        blocks.append(block)
        used += len(block)
    return json.dumps({"repositories": findings["indexed"], "limitations": findings["warnings"]}, ensure_ascii=False) + "\n" + "\n".join(blocks)


def start_job_async(job_id: str, change: str, workspace_id, selected_repos: list[dict], options: dict):
    if not selected_repos:
        raise ValueError("Select at least one repository.")
    if len(selected_repos) > 5:
        raise ValueError("Analyze at most five repositories per job.")
    if not change.strip() or len(change) > 12000:
        raise ValueError("Change description must contain between 1 and 12000 characters.")
    repo_store.create_job(job_id, change, workspace_id)

    def run():
        try:
            repo_store.update_job_status(job_id, "preparing")
            paths = list(dict.fromkeys(_ensure_local_checkout(repo.get("git_url"), repo.get("local_path"), repo.get("branch")) for repo in selected_repos))
            findings = asyncio.run(collect_repository_evidence(change, paths, lambda stage: repo_store.update_job_status(job_id, stage)))
            context = build_repository_context(findings)
            repo_store.update_job_status(job_id, "analyzing")
            from sdlc.graphs.change_impact_graph import run_change_impact_workflow

            state = run_change_impact_workflow(change, repository_context=context)
            document = state.get("document", "")
            if not document.strip():
                raise RuntimeError("The analysis model returned an empty report.")
            document += "\n" + render_analysis_appendix(change, findings)
            result = {
                "success": True, "change": change, "document": document,
                "report": state.get("report"),
                "indexed": findings["indexed"], "symbols": findings["symbols"],
                "dependencies": findings["dependencies"], "risks": state.get("risks", ""),
                "stages": state.get("trace", []),
                "findings": {"evidence": findings["evidence"], "warnings": findings["warnings"]},
            }
            repo_store.update_job_status(job_id, "completed", result)
        except Exception as exc:
            repo_store.update_job_status(job_id, "failed", {"error": mcp_client.error_message(exc)})

    thread = threading.Thread(target=run, daemon=True)
    thread.start()
    return thread
