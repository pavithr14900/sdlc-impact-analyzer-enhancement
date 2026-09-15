from sdlc.agents.common import (
    MARKDOWN_RULES, TECH_BASELINE, coding_standards_context, system_prompt
)
from sdlc.drawio import build_drawio_xml, fallback_spec
from sdlc.llm import call_llm, call_llm_json
from sdlc.state import SdlcState, traced

ROLE = "a Solution Architect"

PROMPT = """
Design the application architecture for the requirement below.

REQUIREMENT
===========
{requirement}

REQUIREMENT ANALYSIS
====================
{analysis}

{tech}
{coding_standards}

Produce exactly these sections:

## 4. ARCHITECTURE DESIGN

### Architecture and Diagram Summary

Describe the layers and key boundaries that the generated architecture
diagram represents. Mention the frontend, API, application services,
persistence, security and external systems.

Write exactly one self-contained bullet per layer, in this exact order:
Frontend Layer, API Layer, Application Services Layer, Persistence Layer,
Security Layer, External Systems. Each bullet must be a single line with
this exact format and nothing else on the line:
`- **Layer Name**: one sentence description.`
Never split a layer name and its description across two lines, never
use a colon on its own line, and never let one bullet run into the
next layer name.

### Code Design

Recommend the Java package structure and the key classes with their
responsibilities. Do not include a full code sample. List 4 to 6
packages as single-line bullets in this exact format:
`- \`com.example.<domain>.<package>\`: responsibility in a few words.`

### Implementation Plan

Phased delivery plan (setup, database, domain, business logic, APIs,
validation, testing, integration, security, deployment).
Use exactly 5 to 6 practical phases, with no more than 4 concise tasks
per phase. Keep the plan realistic for a small-to-medium application,
avoid inflated task counts, and combine related delivery work into one
phase where appropriate.

Format every phase exactly like this, with a blank line between phases.
Do not add any other headings, labels or commentary inside a phase:

#### Phase <n>: <phase title>
**Tasks:**
- <concise task>
- <concise task>
**Dependencies:** <what this phase depends on, or "None">
**Expected Outcome:** <one sentence outcome>

{rules}
"""


def architecture_agent(state: SdlcState) -> dict:

    content = call_llm(
        PROMPT.format(
            requirement=state["requirement"],
            analysis=state.get("requirement_analysis", ""),
            tech=TECH_BASELINE,
            coding_standards=coding_standards_context(state["requirement"]),
            rules=MARKDOWN_RULES
        ),
        system=system_prompt(ROLE)
    )

    try:
        diagram_spec = call_llm_json(
            f"""Create a draw.io architecture model as JSON for this requirement.

REQUIREMENT:
{state["requirement"]}

ARCHITECTURE DESIGN:
{content}

Return only JSON with title, layers, and connections. Use 4 to 6 layers,
2 to 4 nodes per layer, unique lowercase snake_case node ids, and valid
connections. Node types: client, gateway, security, api, service,
repository, database, messaging, external, observability.""",
            system=system_prompt(ROLE)
        )
        diagram_xml = build_drawio_xml(diagram_spec)
    except Exception as exc:
        print(f"      \u26a0 Architecture diagram unusable: {exc}")
        diagram_xml = build_drawio_xml(fallback_spec())

    return {
        "architecture": content,
        "diagram_xml": diagram_xml,
        "trace": traced(
            "Architecture Design Agent",
            "Architecture design and solution diagram"
        )
    }
