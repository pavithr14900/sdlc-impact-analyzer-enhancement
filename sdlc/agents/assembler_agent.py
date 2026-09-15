from datetime import datetime

from sdlc.config import (
    ARCHITECTURE_DIAGRAM_FILE,
    REQUIREMENT_OUTPUT_FILE,
    ensure_output_dir,
)
from sdlc.state import SdlcState, traced


def _save(path: str, content: str) -> str:

    ensure_output_dir()

    with open(path, "w", encoding="utf-8") as file:
        file.write(content)

    return path


def assembler_agent(state: SdlcState) -> dict:
    """Deterministically merges every agent output into one pack."""

    parts = [
        state.get("requirement_analysis", ""),
        state.get("user_stories", ""),
        state.get("ui_prototype", ""),
        state.get("architecture", ""),
        state.get("api_design", ""),
        state.get("data_model", ""),
        state.get("generated_code", ""),
        state.get("test_strategy", ""),
        state.get("infrastructure", ""),
        state.get("security_considerations", ""),
        state.get("developer_checklist", ""),
        state.get("documentation", ""),
    ]

    document = "\n\n---\n\n".join(
        part.strip()
        for part in parts
        if part and part.strip()
    )

    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    _save(
        REQUIREMENT_OUTPUT_FILE,
        f"# SDLC Developer Implementation Pack\n\n"
        f"Generated: {timestamp}\n\n---\n\n{document}\n"
    )

    if state.get("diagram_xml"):
        _save(
            ARCHITECTURE_DIAGRAM_FILE,
            state["diagram_xml"]
        )

    return {
        "document": document,
        "trace": traced(
            "Assembler Agent",
            "Merges agent outputs and writes developer pack"
        )
    }
