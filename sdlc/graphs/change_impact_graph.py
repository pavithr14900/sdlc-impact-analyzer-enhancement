from langgraph.graph import END, START, StateGraph

from sdlc.agents import (
    code_impact_agent,
    data_impact_agent,
    risk_agent,
    scope_agent,
    test_impact_agent,
)
from sdlc.state import ChangeImpactState


def build_change_impact_graph():
    """
    scope --|-- code_impact --|
            |-- data_impact --|-- risk
            |-- test_impact --|
    """

    graph = StateGraph(ChangeImpactState)

    graph.add_node("scope", scope_agent)
    graph.add_node("code_impact", code_impact_agent)
    graph.add_node("data_impact", data_impact_agent)
    graph.add_node("test_impact", test_impact_agent)
    graph.add_node("risk", risk_agent)

    graph.add_edge(START, "scope")

    graph.add_edge("scope", "code_impact")
    graph.add_edge("scope", "data_impact")
    graph.add_edge("scope", "test_impact")

    graph.add_edge(["code_impact", "data_impact", "test_impact"], "risk")

    graph.add_edge("risk", END)

    return graph.compile()


change_impact_graph = build_change_impact_graph()


def run_change_impact_workflow(change: str, repository_context: str = "") -> ChangeImpactState:

    return change_impact_graph.invoke({
        "change": change,
        "repository_context": repository_context,
        "trace": []
    })
