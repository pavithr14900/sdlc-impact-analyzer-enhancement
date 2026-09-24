"""Convert direct MCP call edges into source-backed flow graphs."""
from pathlib import Path

from sdlc.integrations.mcp_client import McpError
from sdlc.services.change_impact_service import graph_rows


async def build_call_flow(memory, repository: dict, symbol: str, trace: dict) -> dict | None:
    if not memory.supports("get_code_snippet"):
        return None
    # Hop distance alone cannot tell us the parent of a transitive callee.
    # Draw only direct, resolved edges rather than inventing a sequence.
    callees = [row for row in graph_rows(trace.get("callees", {}))
               if row.get("hop") == 1 and row.get("strategy") in {"lsp", "language_rule"}][:8]
    if not callees:
        return None
    symbols = [symbol] + [row.get("qn") or row.get("qualified_name") for row in callees]
    nodes, evidence = [], []
    for qualified_name in dict.fromkeys(item for item in symbols if item):
        try:
            snippet = await memory.call("get_code_snippet", project=repository["project"], qualified_name=qualified_name)
        except McpError:
            continue
        if not isinstance(snippet, dict) or not isinstance(snippet.get("source"), str):
            continue
        file = snippet.get("file_path")
        start = snippet.get("start_line")
        if not isinstance(file, str) or not isinstance(start, int) or start < 1:
            continue
        root = Path(repository["resolvedPath"]).resolve()
        try:
            file = (root / file).resolve().relative_to(root).as_posix()
        except ValueError:
            continue
        source = "\n".join(snippet["source"].splitlines()[:40])
        reference = {"repository": repository["name"], "file": file, "symbol": qualified_name,
                     "lineStart": start, "lineEnd": start + max(0, len(source.splitlines()) - 1),
                     "evidenceType": "CODE", "snippet": source}
        evidence.append(reference)
        nodes.append({"id": qualified_name, "name": qualified_name.split(".")[-1], "type": "function",
                      "repository": repository["name"], "evidence": [reference]})
    if not nodes or nodes[0]["id"] != symbol:
        return None
    edges = [{"source": symbol, "target": node["id"], "relationship": "calls",
              "sourceRepository": repository["name"], "targetRepository": repository["name"],
              "sourceSymbol": symbol, "targetSymbol": node["id"], "relationshipType": "CALLS",
              "evidence": [nodes[0]["evidence"][0], node["evidence"][0]]} for node in nodes[1:]]
    if not edges:
        return None
    return {"id": symbol, "title": f"Calls from {symbol.split('.')[-1]}",
            "description": "Direct source-resolved calls from the indexed function. Branch order and a complete runtime workflow are not established.",
            "nodes": nodes, "edges": edges, "evidence": evidence}
