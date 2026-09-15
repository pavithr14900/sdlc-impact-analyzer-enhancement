from sdlc.agents.common import (
    MARKDOWN_RULES, TECH_BASELINE, coding_standards_context, system_prompt
)
from sdlc.llm import call_llm
from sdlc.state import SdlcState, traced

ROLE = "an API Architect"

PROMPT = """
Design the REST API for the requirement below.

REQUIREMENT
===========
{requirement}

REQUIREMENT ANALYSIS
====================
{analysis}

{tech}
{coding_standards}

Produce exactly these sections:

## 5. API DESIGN

### Endpoints

A table of every endpoint with: method, path, purpose, request body,
response body, success status and error statuses.
Use resource-oriented, plural, kebab-case paths.
The request body and response body columns are Markdown table cells, so
they cannot contain triple-backtick code fences. Put each payload as a
single-line minified JSON example wrapped in one pair of backticks, for
example `{{"employeeId":1,"leaveType":"SICK"}}`.

### Validation and Error Handling

Field level validation rules, the standard error response envelope,
and a table mapping business failures to HTTP status codes.

{rules}
"""


def api_design_agent(state: SdlcState) -> dict:

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

    return {
        "api_design": content,
        "trace": traced(
            "API Design Agent",
            "REST endpoints, contracts, error handling"
        )
    }
