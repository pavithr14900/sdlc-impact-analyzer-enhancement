from sdlc.agents.common import MARKDOWN_RULES, system_prompt
from sdlc.llm import call_llm
from sdlc.state import SdlcState, traced

ROLE = "a Senior Product Designer and UX Engineer"

PROMPT = """
Design the interactive application prototype for the requirement below.
This is NOT a generated image or mockup - it is a structured UI
specification that a React renderer will use to build the actual
prototype screens, so every field must be concrete and renderable.

REQUIREMENT
===========
{requirement}

REQUIREMENT ANALYSIS
====================
{analysis}

USER STORIES AND ACCEPTANCE CRITERIA
=====================================
{user_stories}

Produce exactly these sections:

## 3. INTERACTIVE APPLICATION PROTOTYPE

### Prototype Overview

One short paragraph describing the overall application experience and
how the screens below cover the user stories above.

### UI Specification

Return ONLY a fenced json code block, no other text in this subsection,
with this exact schema:

```json
{{
  "appName": "Application name grounded in the requirement",
  "layout": "sidebar",
  "theme": {{
    "primary": "#2563eb", "background": "#ffffff", "surface": "#ffffff",
    "text": "#172b4d", "muted": "#505a5f", "border": "#b1b4b6",
    "headerBackground": "#172b4d", "headerText": "#ffffff",
    "primaryText": "#ffffff", "focus": "#ffdd00",
    "fontFamily": "Arial, sans-serif", "fontSize": "16px",
    "headingSize": "28px", "spacing": "16px", "radius": "4px",
    "borderWidth": "1px", "contentWidth": "1200px"
  }},
  "designNotes": ["Explain applied guidance and any unsupported rules, citing source URLs"],
  "screens": [
    {{
      "name": "Screen name shown in the mock browser bar",
      "description": "One sentence describing what this screen is for",
      "components": [
        {{ "type": "heading", "text": "Page title" }},
        {{ "type": "nav", "items": ["Dashboard", "Customers", "Settings"] }},
        {{ "type": "field", "label": "Search customers", "inputType": "text" }},
        {{ "type": "table", "columns": ["Name", "Email", "Status"] }},
        {{ "type": "button", "label": "Add Customer", "variant": "primary" }},
        {{ "type": "list", "items": ["Bullet point one", "Bullet point two"] }},
        {{ "type": "card", "text": "Short summary or stat shown in a card" }},
        {{ "type": "text", "text": "Supporting paragraph or helper text" }}
      ]
    }}
  ]
}}
```

DESIGN CONTRACT:
Use the organization guidance below as the source of truth for theme values and
layout. The sample values above illustrate syntax, NOT prescribed styling.
All colours must be hex values. Sizes must be px or rem. Font families must
include a fallback. Layout must be sidebar, topnav, or stacked. Choose the page
structure specified by the guidance; do not default to a dashboard sidebar.
Use designNotes to cite source URLs and disclose missing or unsupported guidance.
Do not claim exact compliance where guidance is incomplete. Do not invent fonts
being loaded: only system fonts are available; document required font assets.
Components render in array order. Fields may have items for select choices.
Button variant must be primary or secondary. Include text components for help
and validation guidance. Every field is rendered, including standalone fields.

Cover every major user journey from the user stories above with its own
screen (typically 3 to 6 screens: for example a dashboard/list screen,
a create/edit form screen, a detail screen, and any confirmation or
empty-state screen implied by the acceptance criteria). Component
`type` must be one of: heading, text, nav, field, button, table, list,
card. Use fields and table columns that are grounded in the requirement
and data being managed, never generic placeholders. Keep each screen to
4 to 8 components.

{rules}
{design_standards}
"""


def prototype_agent(state: SdlcState) -> dict:

    from sdlc.rag.knowledge_base import category_summary
    # A build snapshot takes precedence over mutable global reference documents.
    design_ctx = state.get("design_standards") or category_summary("design")

    content = call_llm(
      PROMPT.format(
        requirement=state["requirement"],
        analysis=state.get("requirement_analysis", ""),
        user_stories=state.get("user_stories", ""),
        rules=MARKDOWN_RULES,
        design_standards=design_ctx
      ),
      system=system_prompt(ROLE)
    )

    return {
        "ui_prototype": content,
        "trace": traced(
            "Prototype Agent",
            "Structured UI specification rendered as an interactive prototype"
        )
    }
