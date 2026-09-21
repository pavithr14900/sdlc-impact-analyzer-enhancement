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

STYLE GUIDANCE:
Do NOT use any stored organizational design guidance or external design
documents when producing the UI. Instead, generate a rich, modern, self-
contained theme: choose concrete hex colours, sensible spacing (px or rem),
and a system font-family fallback. Aim for a polished enterprise product,
not a wireframe: use a restrained 2-colour accent system, generous whitespace,
clear hierarchy, responsive stat cards, realistic labels and data, and accessible
contrast. Prefer this composition where the requirement supports it: page heading
with supporting description, 3-5 summary cards, a primary data table or form,
and one action area. Use concise, domain-specific copy instead of placeholder
phrases such as "Item 1 detail". Include a dashboard/overview screen when useful,
and make primary actions explicit. Keep each screen to 5 to 9 components and
ground fields/tables in the requirement data.

{rules}
"""



def prototype_agent(state: SdlcState) -> dict:

    # Do not consult stored organizational design guidance when generating
    # the prototype; the prompt explicitly instructs the model to create a
    # self-contained, rich UI theme.
    content = call_llm(
      PROMPT.format(
        requirement=state["requirement"],
        analysis=state.get("requirement_analysis", ""),
        user_stories=state.get("user_stories", ""),
        rules=MARKDOWN_RULES,
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
