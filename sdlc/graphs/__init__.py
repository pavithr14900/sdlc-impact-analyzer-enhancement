from sdlc.graphs.change_impact_graph import (
    change_impact_graph,
    run_change_impact_workflow,
)
from sdlc.graphs.sdlc_graph import sdlc_graph, run_sdlc_workflow

WORKFLOWS = {
    "requirement": sdlc_graph,
    "change-impact": change_impact_graph,
}

__all__ = [
    "WORKFLOWS",
    "change_impact_graph",
    "run_change_impact_workflow",
    "run_sdlc_workflow",
    "sdlc_graph",
]
