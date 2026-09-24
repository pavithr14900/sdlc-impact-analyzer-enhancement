"""Code intelligence boundary. Controllers do not know MCP commands or schemas."""
from __future__ import annotations

import hashlib
import os
from pathlib import Path
from typing import Protocol

from sdlc.integrations import mcp_client
from sdlc.services.change_impact_service import graph_rows

from .source_analysis import discover
from .flow_analysis import build_call_flow


class CodebaseIntelligenceService(Protocol):
    async def analyze(self, repositories: list[dict], progress) -> dict: ...


def _snapshot(repositories: list[dict], findings: dict, engine: str) -> dict:
    facts = findings["facts"]
    overview = {"repositories": len(repositories)}
    metric_kinds = {"services": "service", "classes": "class", "apis": "api", "databaseTables": "databaseTable", "externalIntegrations": "externalIntegration", "scheduledJobs": "scheduledJob"}
    for metric, kind in metric_kinds.items():
        matches = [fact for fact in facts if fact["kind"] == kind]
        # Null means not discovered/verified, rather than implying an absent capability.
        overview[metric] = len({(fact["repository"], fact["name"], fact["evidence"][0]["file"]) for fact in matches}) or None
    nodes, edges = [], []
    for index, repository in enumerate(repositories):
        repo_id = f"repo-{index}"
        name = repository["name"]
        repo_evidence = [item for item in findings["evidence"] if item["repository"] == name][:1]
        nodes.append({"id": repo_id, "name": name, "type": "repository", "repository": name, "evidence": repo_evidence})
        component_types = {"api": "api", "service": "service", "databaseTable": "database", "externalIntegration": "external", "scheduledJob": "job"}
        # Reserve space for every discovered category, independent of scan order.
        selected = []
        for kind in component_types:
            matches = [item for item in facts if item["repository"] == name and item["kind"] == kind]
            selected.extend(matches[:6])
            if len(matches) > 6:
                findings["limitations"].append(f"{name}: architecture shows 6 of {len(matches)} discovered {kind} declarations; full findings remain available in documentation.")
        for fact in selected:
            node_id = f"node-{len(nodes)}"
            nodes.append({"id": node_id, "name": fact["name"], "type": component_types[fact["kind"]], "repository": name, "evidence": fact["evidence"]})
            edges.append({"source": repo_id, "target": node_id, "relationship": "references" if fact["kind"] == "externalIntegration" else "contains declaration", "evidence": fact["evidence"]})
    return {**findings, "overview": overview, "architecture": {"nodes": nodes, "edges": edges}, "flows": [], "relationships": [], "engine": engine}


class DevelopmentCodebaseIntelligence:
    """Explicit offline development engine; never chosen after an MCP failure."""
    async def analyze(self, repositories, progress):
        progress("INDEXING", 3, "Discovering source declarations (development engine)")
        findings = discover(repositories)
        findings["limitations"].insert(0, "Development source scanner selected explicitly. Codebase Memory MCP is not connected; call hierarchy and cross-repository relationships are unavailable.")
        progress("ANALYZING", 6, "Preparing source-backed insights")
        return _snapshot(repositories, findings, "development-source-scanner")


class CodebaseMemoryAdapter:
    """Reuse the existing native stdio client and only advertised MCP capabilities."""
    async def analyze(self, repositories, progress):
        graph_results, warnings, flows, relationships = [], [], [], []
        for number, repository in enumerate(repositories, 1):
            path = repository["resolvedPath"]
            project = "legacy-" + hashlib.sha256(os.path.normcase(path).encode()).hexdigest()[:16]
            progress("INDEXING", 3, f"Building code knowledge graph ({number}/{len(repositories)})")
            async with mcp_client.connect(path) as memory:
                if not memory.supports("index_repository", "name") or not memory.supports("index_repository", "persistence"):
                    raise mcp_client.McpError("The installed Codebase Memory server must support named indexes and persistence=false.")
                index = await memory.call("index_repository", repo_path=path, name=project, persistence=False)
                if not isinstance(index, dict) or index.get("status") not in {"indexed", "up_to_date", "unchanged"}:
                    raise mcp_client.McpError("Codebase Memory indexing did not complete successfully.")
                project = index.get("project") or project
                repository["project"] = project
                result = {"repository": repository["name"], "project": project, "index": index}
                for counter in ("not_indexed_files_count", "skipped_count", "parse_partial_count"):
                    if index.get(counter):
                        warnings.append(f"{repository['name']}: MCP reported {counter}={index[counter]}; graph coverage is incomplete.")
                progress("ANALYZING", 4, f"Analyzing architecture ({number}/{len(repositories)})")
                if memory.supports("get_architecture"):
                    arguments = {"project": project}
                    if memory.supports("get_architecture", "aspects"):
                        arguments["aspects"] = ["overview"]
                    try:
                        result["architecture"] = await memory.call("get_architecture", **arguments)
                    except mcp_client.McpError as exc:
                        warnings.append(str(exc))
                if memory.supports("check_index_coverage"):
                    try:
                        result["coverage"] = await memory.call("check_index_coverage", project=project, scopes=["."], scope_limit=30)
                    except mcp_client.McpError as exc:
                        warnings.append(str(exc))
                # Trace a bounded set of real graph symbols. Never guess call relationships.
                progress("ANALYZING", 5, "Finding dependencies and application flows")
                candidates = []
                if memory.supports("search_graph", "query"):
                    try:
                        search = await memory.call("search_graph", project=project, query="service controller handler", format="json", limit=5)
                        result["symbols"] = search
                        candidates = [row for row in graph_rows(search) if row.get("label") in {"Function", "Method"}][:3]
                        if not candidates and memory.supports("search_graph", "label"):
                            search = await memory.call("search_graph", project=project, label="Function", format="json", limit=5)
                            candidates = graph_rows(search)[:3]
                    except mcp_client.McpError as exc:
                        warnings.append(str(exc))
                for candidate in candidates:
                    symbol = candidate.get("qn") or candidate.get("qualified_name")
                    tool = "trace_path" if memory.supports("trace_path") else "trace_call_path"
                    if not symbol or not memory.supports(tool):
                        continue
                    args = {"project": project, "function_name": symbol, "direction": "outbound", "depth": 2}
                    # Existing server calls accept both/inbound/outbound; use its advertised enum.
                    direction = memory.schemas.get(tool, {}).get("properties", {}).get("direction", {}).get("enum", [])
                    args["direction"] = "outbound" if "outbound" in direction else "outgoing" if "outgoing" in direction else "both"
                    for key, value in {"format": "json", "limit": 20, "include_evidence": True}.items():
                        if memory.supports(tool, key):
                            args[key] = value
                    try:
                        trace = await memory.call(tool, **args)
                        result.setdefault("traces", []).append({"symbol": symbol, "trace": trace})
                        flow = await build_call_flow(memory, repository, symbol, trace)
                        if flow:
                            flows.append(flow)
                            relationships.extend(flow["edges"])
                    except mcp_client.McpError as exc:
                        warnings.append(str(exc))
                graph_results.append(result)
        progress("ANALYZING", 6, "Discovering APIs, database objects and candidate business rules")
        findings = discover(repositories)
        findings["limitations"].extend(warnings)
        findings["limitations"].append("Architecture edges show source containment/references. Flow graphs show up to eight direct, source-resolved calls for up to three discovered functions per repository; they do not establish execution order or complete runtime workflows. Cross-repository HTTP/event relationships are not inferred from matching names.")
        for flow in flows:
            for item in flow["evidence"]:
                item["id"] = f"E{len(findings['evidence']) + 1}"
                findings["evidence"].append(item)
        findings["graphFacts"] = graph_results
        snapshot = _snapshot(repositories, findings, "codebase-memory-mcp")
        snapshot["flows"], snapshot["relationships"] = flows, relationships
        return snapshot


def get_adapter() -> CodebaseIntelligenceService:
    engine = os.getenv("LEGACY_INTELLIGENCE_ENGINE", "mcp").strip().lower()
    if engine == "development":
        return DevelopmentCodebaseIntelligence()
    if engine != "mcp":
        raise ValueError("LEGACY_INTELLIGENCE_ENGINE must be mcp or development.")
    return CodebaseMemoryAdapter()
