from sdlc.agents.common import MARKDOWN_RULES, system_prompt
from sdlc.llm import call_llm
from sdlc.state import SdlcState, traced

ROLE = "a Senior Business Analyst and Requirements Engineer"

PROMPT = """
Analyze the software requirement below and produce the requirement
foundation of a developer implementation pack.

REQUIREMENT
===========
{requirement}

Produce only this section:

## 1. REQUIREMENT SUMMARY

- Business objective
- Problem being solved
- Key users and actors
- Core capabilities
- In scope (as a separate row)
- Out of scope (as a separate row)

Return the summary as a markdown table with exactly these columns:
Category | Details. Use separate rows named exactly "In scope" and
"Out of scope". Keep scope items as short bullet-separated details.

{rules}
"""

STORY_PROMPT = """
Create the user stories and acceptance criteria for this requirement.

REQUIREMENT
===========
{requirement}

REQUIREMENT SUMMARY
===================
{summary}

USER CORRECTION TO APPLY
========================
{correction}

Produce only this section:

## 2. USER STORIES AND ACCEPTANCE CRITERIA

Create exactly 4 to 5 distinct stories for the main user journeys.
Use this structure for each story:

### Story 1: <short title>
**As a:** <role>
**I want:** <capability>
**So that:** <business value>

**Acceptance criteria**
Return plain Markdown only. Do not use code fences for the stories or
acceptance criteria. Start every story with a heading exactly like
`### Story 1: Apply for leave`.

Every acceptance criterion must start with **Given**, followed by
**When**, and end with **Then**. Never place **Given** after **Then** or
repeat any of these keywords at the end of a sentence.

Do not duplicate stories and ensure every major capability is covered.

{rules}
"""


def requirement_agent(state: SdlcState) -> dict:

    content = call_llm(
        PROMPT.format(
            requirement=state["requirement"],
            rules=MARKDOWN_RULES
        ),
        system=system_prompt(ROLE)
    )

    return {
        "requirement_analysis": content,
        "trace": traced(
            "Requirement Agent",
            "Business analysis, user stories, acceptance criteria"
        )
    }


def user_story_agent(state: SdlcState) -> dict:

    content = call_llm(
        STORY_PROMPT.format(
            requirement=state["requirement"],
            summary=state.get("requirement_analysis", ""),
            correction=state.get("correction", "No correction provided."),
            rules=MARKDOWN_RULES
        ),
        system=system_prompt(ROLE)
    )

    return {
        "user_stories": content,
        "trace": traced(
            "Requirement Agent",
            "User stories and acceptance criteria"
        )
    }
