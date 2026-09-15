from sdlc.agents.common import system_prompt
from sdlc.drawio import build_drawio_xml, fallback_spec
from sdlc.llm import call_llm_json
from sdlc.state import SdlcState, traced

ROLE = "a Solution Architect producing machine readable diagram models"

PROMPT = """
Produce the architecture diagram model for the requirement below.

REQUIREMENT
===========
{requirement}

ARCHITECTURE DESCRIPTION
========================
{architecture}

Return ONLY valid JSON. No markdown, no commentary.

Schema:

{{
  "title": "<short system name> - Solution Architecture",
  "layers": [
    {{
      "name": "Client Layer",
      "nodes": [
        {{
          "id": "web_app",
          "label": "Web Application",
          "tech": "React 18 / TypeScript",
          "type": "client"
        }}
      ]
    }}
  ],
  "connections": [
    {{
      "from": "web_app",
      "to": "api_gateway",
      "label": "HTTPS / REST"
    }}
  ]
}}

Rules:

- 4 to 6 layers, ordered top to bottom
  (client, edge/security, application, domain, persistence, external).
- 2 to 4 nodes per layer. Never more than 4.
- "id" is lowercase snake_case and unique.
- "label" max 28 characters and specific to the business domain.
- "tech" max 30 characters.
- "type" is one of: client, gateway, security, api, service,
  repository, database, messaging, external, observability.
- Every connection references existing node ids.
- Connection "label" max 22 characters.
- Do not invent unrelated components.
"""


def diagram_agent(state: SdlcState) -> dict:

    try:

        spec = call_llm_json(
            PROMPT.format(
                requirement=state["requirement"],
                architecture=state.get("architecture", "")
            ),
            system=system_prompt(ROLE)
        )

        xml = build_drawio_xml(spec)

        status = "completed"

    except Exception as exc:

        print(f"      \u26a0 Diagram model unusable: {exc}")

        xml = build_drawio_xml(fallback_spec())

        status = "completed (fallback layout)"

    return {
        "diagram_xml": xml,
        "trace": traced(
            "Diagram Agent",
            "draw.io solution architecture diagram",
            status
        )
    }
