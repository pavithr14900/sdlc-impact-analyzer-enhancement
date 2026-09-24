"""Builds a bounded LLM context from Legacy Code Intelligence discovery
output and runs the multi-agent insight synthesis graph (mirrors the
evidence-budget discipline in `sdlc.services.change_impact_service`)."""
from __future__ import annotations

import json

from sdlc.integrations.mcp_client import error_message

_PRIORITY_KINDS = ["service", "api", "databaseTable", "externalIntegration", "scheduledJob", "class"]


def build_legacy_context(analysis: dict, limit: int = 65000) -> str:
    """Bounded, evidence-cited JSON-lines context for the insight agents."""
    blocks, used = [], 0

    header = {
        "repositories": [repo.get("name") for repo in analysis.get("repositories", [])],
        "overview": analysis.get("overview"),
        "limitations": (analysis.get("limitations") or [])[:10],
    }
    header_block = json.dumps(header, ensure_ascii=False, default=str)
    blocks.append(header_block)
    used += len(header_block)

    facts = sorted(
        analysis.get("facts") or [],
        key=lambda item: _PRIORITY_KINDS.index(item["kind"]) if item.get("kind") in _PRIORITY_KINDS else len(_PRIORITY_KINDS),
    )
    for fact in facts:
        block = json.dumps(fact, ensure_ascii=False, default=str)
        if used + len(block) > limit:
            break
        blocks.append(block)
        used += len(block)

    for rule in analysis.get("businessRules") or []:
        block = json.dumps(rule, ensure_ascii=False, default=str)
        if used + len(block) > limit:
            break
        blocks.append(block)
        used += len(block)

    for graph_fact in analysis.get("graphFacts") or []:
        block = json.dumps(graph_fact, ensure_ascii=False, default=str)[:4000]
        if used + len(block) > limit:
            break
        blocks.append(block)
        used += len(block)

    return "\n".join(blocks)


def run_ai_insights(analysis: dict) -> dict:
    """Run the legacy intelligence multi-agent graph and return the fields
    to merge into the analysis snapshot. Raises on failure; callers should
    catch and degrade gracefully (analysis stays useful without narratives)."""
    from sdlc.graphs.legacy_intelligence_graph import run_legacy_intelligence_workflow

    context = build_legacy_context(analysis)

    try:
        state = run_legacy_intelligence_workflow(context)
    except Exception as exc:
        raise RuntimeError(f"AI insight synthesis failed: {error_message(exc)}") from exc

    narratives = {
        "architecture": state.get("architecture_narrative", ""),
        "businessRules": state.get("business_rules_narrative", ""),
        "flows": state.get("flows_narrative", ""),
        "dependencies": state.get("dependencies_narrative", ""),
        "security": state.get("security_narrative", ""),
        "technicalDebt": state.get("tech_debt_narrative", ""),
    }
    return {
        "narratives": narratives,
        "insights": state.get("report"),
        "insightsDocument": state.get("document", ""),
    }
