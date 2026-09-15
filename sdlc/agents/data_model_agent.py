from sdlc.agents.common import MARKDOWN_RULES, coding_standards_context, system_prompt
from sdlc.llm import call_llm
from sdlc.state import SdlcState, traced

ROLE = "a Database Architect"

PROMPT = """
Design the relational data model for the requirement below.

REQUIREMENT
===========
{requirement}

REQUIREMENT ANALYSIS
====================
{analysis}

Target database: PostgreSQL, accessed through Spring Data JPA.
{coding_standards}

Produce exactly these sections:

## 6. DATA MODEL

### Model

For every table give a column table with: column, data type, nullable,
key, default and description. Include audit fields where appropriate.

### ER Diagram

Return ONLY a fenced json code block, no other text in this
subsection, with this exact schema:

```json
{{
  "entities": [
    {{ "name": "Employee", "fields": ["id", "name", "email"] }}
  ],
  "relationships": [
    {{ "from": "Employee", "to": "LeaveRequest", "label": "1:N" }}
  ]
}}
```

Include every table from the Model subsection above as an entity with
its 3 to 6 most relevant fields, and every real relationship between
them with its cardinality label (for example "1:N", "N:N", "1:1").

### Schema Script

A PostgreSQL DDL script in a fenced sql code block that creates the
tables described above, including their constraints and indexes.

### Constraints and Indexes

Primary keys, foreign keys, unique constraints, check constraints,
referential integrity rules and index recommendations with the reason
for each index.

{rules}
"""


def data_model_agent(state: SdlcState) -> dict:

    content = call_llm(
        PROMPT.format(
            requirement=state["requirement"],
            analysis=state.get("requirement_analysis", ""),
            coding_standards=coding_standards_context(state["requirement"]),
            rules=MARKDOWN_RULES
        ),
        system=system_prompt(ROLE)
    )

    return {
        "data_model": content,
        "trace": traced(
            "Data Model Agent",
            "Entities, relationships, constraints, DDL"
        )
    }
