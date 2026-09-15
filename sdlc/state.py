import operator
from typing import Annotated, TypedDict


class AgentTrace(TypedDict):
    name: str
    role: str
    status: str


class SdlcState(TypedDict, total=False):
    """Shared state for the requirement analysis agent graph."""

    requirement: str
    design_standards: str
    development_standards: str

    requirement_analysis: str
    user_stories: str
    ui_prototype: str
    architecture: str
    api_design: str
    data_model: str
    generated_code: str
    test_strategy: str
    infrastructure: str
    security_considerations: str
    developer_checklist: str
    documentation: str

    diagram_xml: str

    document: str

    trace: Annotated[list[AgentTrace], operator.add]


class ChangeImpactState(TypedDict, total=False):
    """Shared state for the change impact agent graph."""

    change: str
    repository_context: str

    scope: str
    code_impact: str
    data_impact: str
    test_impact: str
    risks: str

    report: dict | None
    document: str

    trace: Annotated[list[AgentTrace], operator.add]


def traced(
    name: str,
    role: str,
    status: str = "completed"
) -> list[AgentTrace]:

    print(f"      [OK] {name} - {status}")

    return [
        {
            "name": name,
            "role": role,
            "status": status
        }
    ]
