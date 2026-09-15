from langgraph.graph import END, START, StateGraph

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
from sdlc.state import SdlcState


def build_sdlc_graph():
    """
    requirement
        |-- architecture design --|
        |-- API design ------------|-- generate code -- test strategy --|
        |-- data model ------------|                                    |-- quality gate -- assemble
        |--------------------------|------------------------------------|
    """

    graph = StateGraph(SdlcState)

    graph.add_node("requirement", requirement_agent)
    graph.add_node("user_stories", user_story_agent)
    graph.add_node("prototype", prototype_agent)
    graph.add_node("architecture", architecture_agent)
    graph.add_node("api_design", api_design_agent)
    graph.add_node("data_model", data_model_agent)
    graph.add_node("generate_code", code_generation_agent)
    graph.add_node("test_strategy", test_strategy_agent)
    graph.add_node("infrastructure", infrastructure_agent)
    graph.add_node("security", security_considerations_agent)
    graph.add_node("checklist", developer_checklist_agent)
    graph.add_node("documentation", documentation_agent)
    graph.add_node("assemble", assembler_agent)

    graph.add_edge(START, "requirement")

    graph.add_edge("requirement", "architecture")
    graph.add_edge("requirement", "user_stories")
    graph.add_edge("user_stories", "architecture")
    graph.add_edge("user_stories", "api_design")
    graph.add_edge("user_stories", "data_model")
    graph.add_edge("user_stories", "prototype")
    graph.add_edge("api_design", "generate_code")
    graph.add_edge("data_model", "generate_code")
    graph.add_edge("generate_code", "test_strategy")
    graph.add_edge("test_strategy", "infrastructure")
    graph.add_edge("architecture", "security")
    graph.add_edge("infrastructure", "security")
    graph.add_edge("prototype", "security")
    graph.add_edge("security", "checklist")
    graph.add_edge("checklist", "documentation")

    graph.add_edge("documentation", "assemble")
    graph.add_edge("assemble", END)

    return graph.compile()


sdlc_graph = build_sdlc_graph()


def run_sdlc_workflow(requirement: str, context: dict | None = None) -> SdlcState:

    # Run the full workflow sequentially: initial stages up to Data Model,
    # then the remaining generators in order (generate_code -> test_strategy ->
    # infrastructure -> security -> checklist -> documentation), and finally
    # assemble.

    state: SdlcState = {
        **{key: value for key, value in (context or {}).items() if key in {"design_standards", "development_standards"}},
        "requirement": requirement,
        "trace": []
    }

    # Initial sequential agents
    sequential_initial = [
        ("requirement", requirement_agent, "requirement_analysis"),
        ("user_stories", user_story_agent, "user_stories"),
        ("prototype", prototype_agent, "ui_prototype"),
        ("architecture", architecture_agent, "architecture"),
        ("api_design", api_design_agent, "api_design"),
        ("data_model", data_model_agent, "data_model"),
    ]

    for name, agent, key in sequential_initial:
        try:
            result = agent(state)
            for k, v in result.items():
                if k == "trace":
                    state.setdefault("trace", []).extend(v)
                else:
                    state[k] = v
        except Exception:
            state.setdefault("trace", []).append({"name": f"{name} (failed)", "role": "agent", "status": "failed"})

    # Remaining generators run sequentially in the explicit order desired
    remaining = [
        ("generate_code", code_generation_agent, "generated_code"),
        ("test_strategy", test_strategy_agent, "test_strategy"),
        ("infrastructure", infrastructure_agent, "infrastructure"),
        ("security", security_considerations_agent, "security_considerations"),
        ("checklist", developer_checklist_agent, "developer_checklist"),
        ("documentation", documentation_agent, "documentation"),
    ]

    for name, agent, key in remaining:
        try:
            result = agent(state)
            for k, v in result.items():
                if k == "trace":
                    state.setdefault("trace", []).extend(v)
                else:
                    state[k] = v
        except Exception:
            state.setdefault("trace", []).append({"name": f"{name} (failed)", "role": "agent", "status": "failed"})

    # Final assembly
    try:
        from sdlc.agents.assembler_agent import assembler_agent
        assembler_agent(state)
    except Exception:
        state.setdefault("trace", []).append({"name": "assembler (failed)", "role": "agent", "status": "failed"})

    return state
