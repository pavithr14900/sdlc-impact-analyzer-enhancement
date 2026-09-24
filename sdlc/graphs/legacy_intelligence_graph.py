from langgraph.graph import END, START, StateGraph

from sdlc.agents.legacy_intelligence_agents import (
    architecture_narrative_agent,
    business_rules_agent,
    dependencies_agent,
    flows_agent,
    security_agent,
    synthesis_agent,
    tech_debt_agent,
)
from sdlc.state import LegacyIntelligenceState


def build_legacy_intelligence_graph():
    """
    START --|-- architecture   --|
            |-- business_rules --|
            |-- flows          --|-- synthesis -- END
            |-- dependencies   --|
            |-- security       --|
            |-- tech_debt      --|
    """

    graph = StateGraph(LegacyIntelligenceState)

    graph.add_node("architecture", architecture_narrative_agent)
    graph.add_node("business_rules", business_rules_agent)
    graph.add_node("flows", flows_agent)
    graph.add_node("dependencies", dependencies_agent)
    graph.add_node("security", security_agent)
    graph.add_node("tech_debt", tech_debt_agent)
    graph.add_node("synthesis", synthesis_agent)

    for node in ("architecture", "business_rules", "flows", "dependencies", "security", "tech_debt"):
        graph.add_edge(START, node)

    graph.add_edge(["architecture", "business_rules", "flows", "dependencies", "security", "tech_debt"], "synthesis")

    graph.add_edge("synthesis", END)

    return graph.compile()


legacy_intelligence_graph = build_legacy_intelligence_graph()


def run_legacy_intelligence_workflow(context: str) -> LegacyIntelligenceState:

    return legacy_intelligence_graph.invoke({
        "context": context,
        "trace": []
    })
