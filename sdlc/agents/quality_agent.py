import os
import re
from concurrent.futures import ThreadPoolExecutor
from xml.sax.saxutils import escape as xml_escape

from sdlc.agents.common import MARKDOWN_RULES, system_prompt
from sdlc.config import ensure_generated_code_dir
from sdlc.llm import call_llm
from sdlc.state import SdlcState, traced

ROLE = "a Principal Engineer acting as delivery quality gate"

DOCS_SUBDIR = "docs"
DOCUMENTATION_FILE_NAMES = (
    "README.md",
    "user-guide.md",
    "api-documentation.md",
    "data-model-documentation.md",
    "release-notes.md",
)

SECURITY_PROMPT = """
Review the implementation pack below for security.

REQUIREMENT
===========
{requirement}

ARCHITECTURE
============
{architecture}

API DESIGN
==========
{api_design}

DATA MODEL
==========
{data_model}

Produce exactly this section:

## 10. SECURITY CONSIDERATIONS

Authentication, authorization, input validation, injection risks,
sensitive data exposure, API abuse, logging and error response safety.
Give a concrete control for each item.

{rules}
"""

CHECKLIST_PROMPT = """
Produce the developer checklist for the implementation pack below.

REQUIREMENT
===========
{requirement}

TEST STRATEGY
=============
{test_strategy}

SECURITY CONSIDERATIONS
========================
{security_considerations}

Produce exactly this section:

## 11. DEVELOPER CHECKLIST AND DEFINITION OF DONE

An ordered checklist covering requirements, architecture, database,
backend, API, validation, security, testing, documentation and
deployment, in the recommended implementation order.

Format every item on a single line exactly like this, with no other
text before, between or after the items:
- [ ] <concise actionable task> Definition of Done: <one sentence, measurable completion criteria>

{rules}
"""

DOCUMENTATION_PLAN_PROMPT = """
Produce comprehensive, project-grounded documentation planning for the
implementation pack below.

REQUIREMENT
===========
{requirement}

ARCHITECTURE
============
{architecture}

API DESIGN
==========
{api_design}

DATA MODEL
==========
{data_model}

SECURITY CONSIDERATIONS
========================
{security_considerations}

TEST STRATEGY
=============
{test_strategy}

DEVELOPER CHECKLIST
====================
{developer_checklist}

Produce exactly this section:

## 12. DOCUMENTATION

List the documentation to create or maintain as the final delivery
section. You must produce EXACTLY 5 blocks, no more and no fewer, one for
each of these documents in this exact order: README/Setup Guide, User
Guide, API Documentation, Data Model Documentation, Release Notes. Do not
add a separate block for any individual endpoint, entity, table, query,
stored procedure, trigger, view, or example — those all belong inside the
relevant document's content, never as their own block in this list.

Format every item exactly like this, with one block per document and a
blank line between blocks. Do not use a markdown table.

### <document name>
**Audience:** <who reads this>
**Key Content:**
- <specific, non-empty topic covered by this document>
- <specific, non-empty topic covered by this document>

Never use placeholders such as `-`, `--`, `TBD`, `N/A`, or generic
phrases such as "details to be added". Every bullet must be specific
to the supplied requirement.

{rules}
"""

# Each document is generated in its own LLM call so it gets a dedicated
# output-token budget instead of competing with four other files for a
# single response - this is what actually gives each file room to be
# detailed instead of getting cut short.
DOCUMENT_FILE_CONTEXT = """
Produce ONE complete, detailed, project-grounded Markdown document for the
implementation pack below.

CRITICAL RULE: every <angle-bracket> segment in the template below is an
instruction describing what to write, never literal text. Replace each one
with real, specific content derived from the REQUIREMENT, ARCHITECTURE, API
DESIGN, DATA MODEL, SECURITY, TEST STRATEGY and CHECKLIST supplied here. Your
final answer must never contain the characters "<" or ">" used as a
placeholder. If a detail is not explicit in the input, infer a concrete,
reasonable value consistent with the requirement instead of leaving a
placeholder or generic filler. Expand every section with concrete,
specific, multi-paragraph content - do not compress sections into
one-liners. The document must contain at least 600 words.

REQUIREMENT
===========
{requirement}

ARCHITECTURE
============
{architecture}

API DESIGN
==========
{api_design}

DATA MODEL
==========
{data_model}

SECURITY CONSIDERATIONS
========================
{security_considerations}

TEST STRATEGY
=============
{test_strategy}

DEVELOPER CHECKLIST
====================
{developer_checklist}

Produce the document below, starting directly with its "# " title line.
You may use normal fenced code blocks (```bash, ```json, etc.) for
examples inside the content. Do not add any other commentary, preamble or
closing remarks before or after the document.

TEMPLATE TO FOLLOW
===================
{template}

Final check before you answer: re-read the document and confirm it does
not still contain literal "<" or ">" placeholder markers. Rewrite any that
do before returning your answer.

{rules}
"""

DOCUMENT_FILE_TEMPLATES = {
    "README.md": """# README / Setup Guide

## Overview
<what the application does, its core benefits, and target users, grounded in the requirement>

## Key Features
- <specific, high-value feature from the requirement with concrete outcome>
- <specific, high-value feature from the requirement with concrete outcome>
- <specific, high-value feature from the requirement with concrete outcome>

## Prerequisites
- <specific runtime with version, e.g., Python 3.9+, Node.js 16+>
- <specific tool or account needed with version if relevant>
- <hardware/resource requirements if applicable>
- <required system dependencies or OS versions>

## Project Structure
<describe the repository layout; reference the architecture>
- backend/: <backend responsibility and key frameworks>
- frontend/: <frontend responsibility and key frameworks>
- shared/: <shared utilities if any>
- docs/: <documentation location>

## Installation & Setup

### Backend Setup
<numbered, concrete steps to install backend dependencies>
1. Clone the repository: `git clone <url>`
2. Navigate to the project: `cd project-name`
3. Create virtual environment: `python -m venv venv`
4. Activate: `source venv/bin/activate` (Linux/Mac) or `venv\\Scripts\\activate` (Windows)
5. Install dependencies: `pip install -r requirements.txt`

### Frontend Setup
<numbered, concrete steps to install frontend dependencies>
1. Navigate to frontend: `cd frontend`
2. Install dependencies: `npm install`
3. Build/prepare assets: `npm run build`

## Configuration
<describe all required and optional environment variables>

### Required Environment Variables
- `<VAR_NAME>`: <what it controls, format, example value>
- `<VAR_NAME>`: <what it controls, format, example value>

### Optional Environment Variables
- `<VAR_NAME>` (default: `<value>`): <what it controls, effect if changed>

## Running the Application

### Starting the Backend
<numbered steps to start the backend server>
1. Ensure virtual environment is activated
2. Set environment variables: `export VAR=value`
3. Start server: `python app.py`
4. Verify: Backend is running on http://localhost:5000

### Starting the Frontend
<numbered steps to start the frontend>
1. Navigate to frontend directory: `cd frontend`
2. Start dev server: `npm run dev`
3. Open browser: http://localhost:5173 (or displayed URL)
4. Verify: UI loads and connects to backend

## Verification Checklist
- [ ] Backend health check responds at GET /api/health with 200 OK
- [ ] Frontend loads without console errors
- [ ] Basic workflow completes end-to-end (e.g., <workflow from requirement>)
- [ ] API endpoints respond with expected data format

## Troubleshooting

### Backend Issues
- **Port already in use**: Change PORT env var or kill process on port 5000
- **Module not found**: Run `pip install -r requirements.txt` again
- **Database connection error**: Verify connection string in config, check service is running
- **Authentication error**: Verify API keys/tokens in .env are correct and not expired

### Frontend Issues
- **Blank page or won't load**: Check browser console for errors, ensure backend is running
- **API connection error**: Verify backend URL in config, check CORS settings
- **Module resolution error**: Delete node_modules and run `npm install` again
- **Build fails**: Ensure Node.js version matches requirements, clear cache: `npm cache clean --force`

## Common Workflows

### <Workflow 1 Title>
<numbered steps with expected outcomes>

### <Workflow 2 Title>
<numbered steps with expected outcomes>

## Deployment Notes
<any special considerations for moving to production, e.g., secrets management, scaling>

## Getting Help
- Check logs: Backend logs in console, frontend logs in browser DevTools
- Review error message and stack trace for clues
- Check environment variables are set correctly
- Refer to the API Documentation and User Guide for more details""",

    "user-guide.md": """# User Guide

## Overview
<who uses this application, what problems it solves, and what they accomplish with it>

## Getting Started
<quick introduction for a new user>
1. <first action to take>
2. <second action to take>
3. <verify success: what should they see?>

## User Roles and Permissions

### <Role 1 Name>
- **Capabilities**: <what this role can do>
- **Typical workflows**: <2-3 examples of what they do>
- **Restrictions**: <what they cannot do>

### <Role 2 Name>
- **Capabilities**: <what this role can do>
- **Typical workflows**: <2-3 examples of what they do>
- **Restrictions**: <what they cannot do>

## Core Workflows

### <Workflow 1 Title>
<what this workflow accomplishes and when you'd use it>

**Steps:**
1. Navigate to <location> by <action>
2. Click <button> to open <dialog/page>
3. Enter <field names> with values like:
   - `<example 1>`
   - `<example 2>`
4. Click <button> to submit
5. **Expected outcome**: <what you should see, e.g., success message, record created>

**Common mistakes:**
- <mistake 1>: <how to avoid or fix it>
- <mistake 2>: <how to avoid or fix it>

### <Workflow 2 Title>
<what this workflow accomplishes and when you'd use it>

**Steps:**
1. Navigate to <location> by <action>
2. <2-4 additional numbered steps with specific UI references>
3. Click <button> to submit
4. **Expected outcome**: <success state>

**Tips:**
- <tip or shortcut>
- <tip or shortcut>

### <Workflow 3 Title>
<similar detailed steps>

## Data Management

### Creating Records
<how to create a new record, validation rules, required fields>

### Editing Records
<how to modify existing records, who can edit what>

### Deleting Records
<deletion process, any cascading effects, recovery options>

### Filtering and Search
<how to find records using filters and search>

## Reports and Exports
<what reports are available, how to generate them, export formats>

## Frequently Asked Questions

**Q: <Realistic question from requirement>**
A: <Concrete, specific answer with steps if applicable>

**Q: <Another realistic question>**
A: <Concrete answer>

**Q: Can I <feature question>?**
A: <Yes/No with context>

## Troubleshooting

### Common Issues
- **<Issue 1>**: <How to diagnose>, <how to fix>
- **<Issue 2>**: <How to diagnose>, <how to fix>
- **<Issue 3>**: <How to diagnose>, <how to fix>

### Performance Tips
- <tip 1>
- <tip 2>

## Best Practices
- <best practice 1 from the requirement>
- <best practice 2>
- <best practice 3>

## Getting Help
- **In-app help**: Click the ? icon for contextual help
- **Documentation**: See the API Documentation and README for technical details
- **Contact support**: Email support@example.com with:
  - What you were trying to do
  - Error message (if any)
  - Screenshots or logs
  - Your role and username""",

    "api-documentation.md": """# API Documentation

## Overview
**Base URL**: `http://localhost:5000` (development) | `https://api.example.com` (production)
**Response Format**: JSON
**Authentication**: <Bearer token, API key, OAuth, etc. - reference security considerations>
**Rate Limits**: <requests per minute or unlimited>

## Authentication

### Bearer Token
1. Obtain a token by <method, e.g., login endpoint>
2. Include in request headers: `Authorization: Bearer <token>`
3. Token expires in <duration>; refresh using <refresh endpoint or mechanism>

### Example Request with Auth
```bash
curl -X GET http://localhost:5000/api/endpoint \\
  -H "Authorization: Bearer your_token_here" \\
  -H "Content-Type: application/json"
```

## Endpoints

Document every endpoint from the API design above using this structure:

### <HTTP Method and Path from API Design>
<what this endpoint does, when to use it>

**Request:**
- **Method**: <GET|POST|PUT|DELETE>
- **Path**: `/api/...`
- **Headers**: `Authorization: Bearer <token>`, `Content-Type: application/json`
- **Query Parameters** (if any):
  - `param1` (required|optional): <description, type, example>
  - `param2` (required|optional): <description, type, example>
- **Request Body** (if POST/PUT):
  ```json
  {{
    "field1": "type, description, e.g. string, user ID",
    "field2": "type, description"
  }}
  ```

**Response:**
- **Status 200 (Success)**:
  ```json
  {{
    "success": true,
    "data": {{ "...": "response fields" }},
    "message": "descriptive message"
  }}
  ```
- **Status 400 (Bad Request)**: Missing or invalid required field
- **Status 401 (Unauthorized)**: Invalid or expired token
- **Status 403 (Forbidden)**: Insufficient permissions
- **Status 500 (Server Error)**: Unexpected error

**Example:**
```bash
curl -X POST http://localhost:5000/api/endpoint \\
  -H "Authorization: Bearer token" \\
  -H "Content-Type: application/json" \\
  -d '{{"field1":"value1","field2":"value2"}}'
```

Repeat this structure for every remaining endpoint from the API design.

## Error Codes and Meanings

| Status | Code | Meaning | When It Occurs |
|--------|------|---------|----------------|
| 400 | BAD_REQUEST | Invalid input | <specific example from API design> |
| 401 | UNAUTHORIZED | Invalid credentials | Token missing or expired |
| 403 | FORBIDDEN | Access denied | User lacks required role |
| 404 | NOT_FOUND | Resource not found | Record doesn't exist |
| 409 | CONFLICT | Duplicate or state conflict | Record already exists |
| 429 | RATE_LIMIT | Too many requests | Exceeded rate limit |
| 500 | INTERNAL_ERROR | Server error | Unexpected error, check logs |

## Rate Limits and Quotas
<from security considerations>
- <limit 1>: <threshold, window, consequence>
- <limit 2>: <threshold, window, consequence>

## Data Types and Formats
- **Timestamps**: ISO 8601 format (e.g., `2026-01-15T10:30:00Z`)
- **Booleans**: `true` or `false`
- **IDs**: UUID v4 or numeric, as documented per entity
- **Enums**: Specific values listed in request/response examples

## Pagination (if applicable)
<if the API supports pagination>
- Use `?page=1&limit=20` query parameters
- Response includes `total`, `page`, `limit`, `data` array
- Default page size: 20, max: 100

## SDK Examples
<if SDKs are provided, link or examples here>""",

    "data-model-documentation.md": """# Data Model Documentation

## Overview
<what data the application manages and why, grounded in the requirement>

The system manages the following core domains:
- <Domain 1>: <responsibility, cardinality>
- <Domain 2>: <responsibility, cardinality>

## Entity Relationship Diagram
<ASCII diagram or reference to visual diagram of entities and relationships>

```
[Entity1]
    |
    | 1:N
    |
[Entity2] ---- N:1 ---- [Entity3]
    |
    | 1:1
    |
[Entity4]
```

## Entities

Document every entity from the data model above using this structure:

### <Entity Name>
**Purpose**: <what this entity represents, why it exists>
**Table/Collection Name**: `<table_name>`

**Fields:**
| Field Name | Type | Required | Constraints | Description |
|------------|------|----------|-------------|-------------|
| `id` | UUID | Yes | Primary key, auto-generated | Unique identifier |
| `field1` | String | Yes | Max 255 chars, unique | <specific purpose> |
| `field2` | Integer | No | Min 0, Max 1000 | <specific purpose> |
| `created_at` | Timestamp | Yes | Auto-set on create | Record creation time |
| `updated_at` | Timestamp | Yes | Auto-set on create/update | Last modification time |

**Relationships:**
- Belongs to `<Entity2>` (N:1): Foreign key `entity2_id` references `Entity2.id`
- Has many `<Entity3>` (1:N): Inverse via `Entity3.entity1_id`

**Validation Rules:**
- `field1` must be non-empty and unique across all records
- `field2` must be between 0 and 1000 if provided

Repeat this structure for every remaining entity in the data model.

## Relationships and Constraints

### Foreign Keys
| From Entity | Field | To Entity | Field | Cardinality | Delete Behavior |
|-------------|-------|-----------|-------|-------------|-----------------|
| `Entity1` | `entity2_id` | `Entity2` | `id` | N:1 | CASCADE |
| `Entity2` | `entity3_id` | `Entity3` | `id` | N:1 | SET NULL |

### Unique Constraints
- `Entity1(field1)`: Ensures no duplicate <specific value>
- `Entity2(field1, field2)`: Composite unique key across these fields

## Data Validation Rules

**Business Rules:**
- <Rule 1>: <which entity/field, validation logic, error if violated>
- <Rule 2>: <which entity/field, validation logic, error if violated>
- <Rule 3>: <which entity/field, validation logic, error if violated>

**Format Rules:**
- <Format 1>: <which field, regex or description>
- <Format 2>: <which field, regex or description>

## Data Lifecycle

### Creation
<how records are created, default values, triggers>
- A new `Entity1` is created when <trigger>
- Default `status` is `<status>`
- `created_by` is automatically set to current user

### Updates
<when and how records are modified, audit trail>
- `Entity1.field1` can only be updated by <role>
- `updated_at` is automatically updated on any modification

### Archival / Soft Delete
<if records are archived instead of deleted>
- Records are marked with `deleted_at` timestamp
- Soft-deleted records are excluded from normal queries

## Indexes
<which fields are indexed for query performance>
- Primary key: `id`
- Foreign keys: `entity2_id`, `entity3_id`
- Search fields: `field1`, `email` (for common queries)

## Example Records
<sample data showing valid record structure for the primary entity>

```json
{{
  "id": "550e8400-e29b-41d4-a716-446655440000",
  "field1": "example value",
  "field2": 42,
  "created_at": "2026-01-15T10:30:00Z",
  "updated_at": "2026-01-15T10:30:00Z"
}}
```""",

    "release-notes.md": """# Release Notes

## Version 1.0.0 - Initial Release
**Release Date**: <date>
**Status**: <Alpha|Beta|Stable>

### Summary
<executive summary of what ships in this version, grounded in the requirement>

### New Features
- <Feature 1 from requirement>: <what it enables, concrete benefit>
- <Feature 2 from requirement>: <what it enables, concrete benefit>
- <Feature 3 from requirement>: <what it enables, concrete benefit>

### Core Capabilities Delivered
- <Capability 1 from requirement>
- <Capability 2 from requirement>
- <Capability 3 from requirement>

### Improvements & Polish
- <Improvement from test strategy, security, or checklist>
- <Improvement from test strategy, security, or checklist>
- UI refinement: <specific improvement>

### Known Issues & Limitations
- <Limitation 1 from requirement, not yet implemented>: Will be addressed in <version>
- <Limitation 2>: <workaround if any>
- Performance: <specific performance characteristic, e.g., "handles up to 1000 records">

### Breaking Changes
- <If any, describe old vs. new behavior>

### Compatibility
- Requires: <Node.js version>, <Python version>, <databases>, <browsers>
- Tested on: <specific OS/browser combinations>

### Upgrade Notes
To deploy this release:
1. Back up the database
2. Pull the latest code: `git pull origin main`
3. Install/update dependencies: `pip install -r requirements.txt && npm install`
4. Run migrations if any: `python migrate.py`
5. Restart services
6. Verify health: `curl http://localhost:5000/api/health`

### Contributors
- <Team/person 1>: <contribution>
- <Team/person 2>: <contribution>

### What's Next

#### Planned for Version 1.1
- <Feature 1 from requirement not yet done>
- <Feature 2>
- <Performance improvement>

#### Future Roadmap
- <Major feature or refactor>
- <Major feature or refactor>

### Feedback & Support
- Report issues: <GitHub, Jira, email>
- Request features: <GitHub, Jira, email>
- Documentation: See README.md, User Guide, and API Documentation""",
}

PLACEHOLDER_PATTERN = re.compile(r"<[A-Za-z][^<>\n]*\s[^<>\n]*>")

PLACEHOLDER_FIX_PROMPT = """
The document below still contains unresolved angle-bracket placeholders
(instructional text left in place of real content).

REQUIREMENT
===========
{requirement}

ARCHITECTURE
============
{architecture}

API DESIGN
==========
{api_design}

DATA MODEL
==========
{data_model}

DOCUMENTATION WITH REMAINING PLACEHOLDERS
==========================================
{content}

Rewrite the ENTIRE document above verbatim, keeping the exact same
structure and headings, but replace every single <angle-bracket>
placeholder with real, specific content grounded in the requirement,
architecture, API design and data model above. Do not output any literal
"<" or ">" placeholder markers. Return the complete corrected document
and nothing else.
"""


def _filter_documentation_plan(plan: str) -> str:
    """Keep only the 5 canonical document blocks; drop any extra blocks the
    model may add for individual endpoints, entities, queries, etc."""

    categories = [
        ("readme", re.compile(r"readme|setup guide", re.I)),
        ("user_guide", re.compile(r"user guide", re.I)),
        ("api", re.compile(r"api documentation|\bapi\b", re.I)),
        ("data_model", re.compile(r"data model", re.I)),
        ("release_notes", re.compile(r"release notes", re.I)),
    ]

    blocks = re.split(r"(?=^#{2,4}\s+.+$)", plan, flags=re.MULTILINE)
    kept = {}

    for block in blocks:
        stripped = block.strip()
        if not stripped:
            continue
        heading_match = re.match(r"^#{2,4}\s+(.+)$", stripped)
        heading = heading_match.group(1) if heading_match else ""
        for key, pattern in categories:
            if key not in kept and pattern.search(heading):
                kept[key] = stripped
                break

    if not kept:
        return plan.strip()

    return "\n\n".join(kept[key] for key, _ in categories if key in kept)


def _write_single_doc(filename: str, content: str) -> str:

    docs_dir = os.path.join(ensure_generated_code_dir(), DOCS_SUBDIR)
    os.makedirs(docs_dir, exist_ok=True)

    with open(os.path.join(docs_dir, filename), "w", encoding="utf-8") as file:
        file.write(content.strip() + "\n")

    return f"{DOCS_SUBDIR}/{filename}"


_UNICODE_REPLACEMENTS = {
    "\u2018": "'", "\u2019": "'", "\u201c": '"', "\u201d": '"',
    "\u2013": "-", "\u2014": "-", "\u2026": "...", "\u00a0": " ",
}


def _sanitize_pdf_text(text: str) -> str:
    for target, replacement in _UNICODE_REPLACEMENTS.items():
        text = text.replace(target, replacement)
    return text


def _inline_markdown_to_reportlab(text: str) -> str:
    """Convert simple inline Markdown (bold/italic/code) into ReportLab's
    mini-XML markup, after escaping and normalising problem Unicode chars."""

    text = xml_escape(_sanitize_pdf_text(text))
    text = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", text)
    text = re.sub(r"(?<!\*)\*([^*\n]+?)\*(?!\*)", r"<i>\1</i>", text)
    text = re.sub(r"`([^`\n]+?)`", r'<font face="Courier">\1</font>', text)
    return text


def _render_documentation_pdf(markdown_text: str, pdf_path: str) -> None:
    """Render a Markdown document to a properly formatted PDF using
    ReportLab, with real headings, bullets, tables and code blocks instead
    of a hand-rolled byte-level PDF writer."""

    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
    from reportlab.lib.units import mm
    from reportlab.platypus import (
        Paragraph, XPreformatted, SimpleDocTemplate, Spacer, Table, TableStyle
    )

    styles = getSampleStyleSheet()
    h1_style = ParagraphStyle(
        name="DocH1", parent=styles["Heading1"], spaceBefore=4, spaceAfter=12,
        textColor=colors.HexColor("#1a2b3c")
    )
    h2_style = ParagraphStyle(
        name="DocH2", parent=styles["Heading2"], spaceBefore=14, spaceAfter=8,
        textColor=colors.HexColor("#1f3a5f")
    )
    h3_style = ParagraphStyle(
        name="DocH3", parent=styles["Heading3"], spaceBefore=10, spaceAfter=6,
        textColor=colors.HexColor("#33495e")
    )
    h4_style = ParagraphStyle(
        name="DocH4", parent=styles["Heading4"], spaceBefore=8, spaceAfter=4
    )
    body_style = ParagraphStyle(
        name="DocBody", parent=styles["BodyText"], fontSize=10.5, leading=15, spaceAfter=6
    )
    bullet_style = ParagraphStyle(name="DocBullet", parent=body_style, leftIndent=14)
    quote_style = ParagraphStyle(
        name="DocQuote", parent=body_style, leftIndent=16, textColor=colors.HexColor("#555555")
    )
    code_style = ParagraphStyle(
        name="DocCode", parent=styles["Code"], fontName="Courier", fontSize=9, leading=12
    )

    story = []
    lines = markdown_text.splitlines()
    index = 0
    in_code = False
    code_lines: list[str] = []
    table_rows: list[list] = []

    def flush_table():
        if not table_rows:
            return
        table = Table(table_rows, hAlign="LEFT", repeatRows=1)
        table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#2c3e50")),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTSIZE", (0, 0), (-1, -1), 8.5),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#cccccc")),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f7f9fb")]),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("LEFTPADDING", (0, 0), (-1, -1), 5),
            ("RIGHTPADDING", (0, 0), (-1, -1), 5),
            ("TOPPADDING", (0, 0), (-1, -1), 4),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ]))
        story.append(table)
        story.append(Spacer(1, 10))
        table_rows.clear()

    def flush_code():
        if not code_lines:
            return
        box = Table([[XPreformatted(_sanitize_pdf_text("\n".join(code_lines)), code_style)]], colWidths=[460])
        box.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#f4f4f4")),
            ("BOX", (0, 0), (-1, -1), 0.75, colors.HexColor("#cccccc")),
            ("LEFTPADDING", (0, 0), (-1, -1), 8),
            ("RIGHTPADDING", (0, 0), (-1, -1), 8),
            ("TOPPADDING", (0, 0), (-1, -1), 6),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ]))
        story.append(box)
        story.append(Spacer(1, 10))
        code_lines.clear()

    separator_pattern = re.compile(r"^:?-{2,}:?$")

    while index < len(lines):
        raw_line = lines[index]
        stripped = raw_line.strip()

        if stripped.startswith("```"):
            flush_table()
            in_code = not in_code
            if not in_code:
                flush_code()
            index += 1
            continue

        if in_code:
            code_lines.append(raw_line)
            index += 1
            continue

        if not stripped:
            flush_table()
            story.append(Spacer(1, 6))
            index += 1
            continue

        if stripped.startswith("|") and stripped.endswith("|"):
            cells = [cell.strip() for cell in stripped.strip("|").split("|")]
            if all(separator_pattern.match(cell.replace(" ", "") or "--") for cell in cells):
                index += 1
                continue
            table_rows.append([Paragraph(_inline_markdown_to_reportlab(cell), body_style) for cell in cells])
            index += 1
            continue

        flush_table()

        checkbox_match = re.match(r"^[-*]\s+\[([ xX])\]\s+(.*)$", stripped)
        bullet_match = re.match(r"^[-*]\s+(.*)$", stripped)
        numbered_match = re.match(r"^\d+[.)]\s+(.*)$", stripped)

        if stripped.startswith("#### "):
            story.append(Paragraph(_inline_markdown_to_reportlab(stripped[5:]), h4_style))
        elif stripped.startswith("### "):
            story.append(Paragraph(_inline_markdown_to_reportlab(stripped[4:]), h3_style))
        elif stripped.startswith("## "):
            story.append(Paragraph(_inline_markdown_to_reportlab(stripped[3:]), h2_style))
        elif stripped.startswith("# "):
            story.append(Paragraph(_inline_markdown_to_reportlab(stripped[2:]), h1_style))
        elif checkbox_match:
            box = "[x]" if checkbox_match.group(1).lower() == "x" else "[ ]"
            story.append(Paragraph(f"{box} {_inline_markdown_to_reportlab(checkbox_match.group(2))}", bullet_style))
        elif bullet_match:
            story.append(Paragraph(f"\u2022 {_inline_markdown_to_reportlab(bullet_match.group(1))}", bullet_style))
        elif numbered_match:
            story.append(Paragraph(_inline_markdown_to_reportlab(stripped), bullet_style))
        elif stripped.startswith(">"):
            story.append(Paragraph(_inline_markdown_to_reportlab(stripped.lstrip("> ").strip()), quote_style))
        else:
            story.append(Paragraph(_inline_markdown_to_reportlab(stripped), body_style))

        index += 1

    flush_table()
    flush_code()

    document = SimpleDocTemplate(
        pdf_path, pagesize=A4,
        leftMargin=20 * mm, rightMargin=20 * mm, topMargin=18 * mm, bottomMargin=18 * mm,
        title=os.path.basename(pdf_path)
    )
    document.build(story or [Paragraph("(empty document)", body_style)])


def _export_documentation_pdfs(paths: list[str]) -> None:

    for relative_path in paths:
        markdown_path = os.path.join(ensure_generated_code_dir(), relative_path)

        if not os.path.isfile(markdown_path):
            continue

        with open(markdown_path, "r", encoding="utf-8") as file:
            markdown_text = file.read()

        pdf_path = os.path.splitext(markdown_path)[0] + ".pdf"

        try:
            _render_documentation_pdf(markdown_text, pdf_path)
        except ModuleNotFoundError:
            raise
        except Exception:
            # Don't let one malformed document block the rest; the .md
            # source is still available for Confluence publishing.
            continue
        # Keep the source .md alongside the .pdf - Confluence publishing
        # needs the real Markdown content, not just the rendered PDF.


def _fallback_doc_body(filename: str) -> str:

    title = {
        "README.md": "README/Setup Guide",
        "user-guide.md": "User Guide",
        "api-documentation.md": "API Documentation",
        "data-model-documentation.md": "Data Model Documentation",
        "release-notes.md": "Release Notes",
    }[filename]

    return (
        f"# {title}\n\n"
        "## Purpose and Audience\n"
        "This document supports the delivery team for the generated application.\n\n"
        "## Detailed Guidance\n"
        "Refer to the Application Builder output for the relevant requirements, "
        "architecture, API design, test strategy, and security controls.\n\n"
        "## Operational Checks\n"
        "- Review this document before release.\n"
        "- Keep it updated as implementation decisions change."
    )


def _write_documentation_fallback(plan: str) -> list[str]:
    """Used by the on-demand PDF regeneration endpoint when a document's
    .md/.pdf is missing entirely and only the plan text is available."""

    blocks = {}
    for match in re.finditer(r"^###\s+(.+?)\s*\n([\s\S]*?)(?=^###\s+|\Z)", plan, re.MULTILINE):
        title = match.group(1).strip()
        body = match.group(2).strip()
        normalized_title = title.lower().replace("/", " ").replace("-", " ").strip()
        blocks[normalized_title] = body

    document_titles = {
        "README.md": "README/Setup Guide",
        "user-guide.md": "User Guide",
        "api-documentation.md": "API Documentation",
        "data-model-documentation.md": "Data Model Documentation",
        "release-notes.md": "Release Notes",
    }

    written = []
    for filename in DOCUMENTATION_FILE_NAMES:
        title = document_titles[filename]
        normalized_title = title.lower().replace("/", " ").replace("-", " ").strip()
        body = blocks.get(normalized_title, "")
        content = f"# {title}\n\n{body}" if body else _fallback_doc_body(filename)
        written.append(_write_single_doc(filename, content))

    return written


def _extract_pack_section(full_document: str, title_pattern: str) -> str:
    """Pulls one "## N. TITLE" section's body out of the assembled
    implementation pack, matched by a case-insensitive title fragment."""

    match = re.search(
        rf"^##\s*\d+\.\s*{title_pattern}.*?\n(.*?)(?=^##\s*\d+\.|\Z)",
        full_document, re.MULTILINE | re.DOTALL | re.IGNORECASE
    )
    return match.group(1).strip() if match else ""


def regenerate_documentation_from_pack(full_document: str) -> list[str]:
    """Used by the on-demand PDF regeneration endpoint when a document's
    .md/.pdf is missing but the full assembled pack is available (from the
    frontend's in-memory result) - regenerates the same detailed per-file
    documentation that documentation_agent produces, instead of the short
    plan-only fallback."""

    state: SdlcState = {
        "requirement": (
            _extract_pack_section(full_document, "REQUIREMENT SUMMARY") + "\n\n" +
            _extract_pack_section(full_document, "USER STORIES")
        ),
        "architecture": _extract_pack_section(full_document, "ARCHITECTURE DESIGN"),
        "api_design": _extract_pack_section(full_document, "API DESIGN"),
        "data_model": _extract_pack_section(full_document, "DATA MODEL"),
        "test_strategy": _extract_pack_section(full_document, "TEST STRATEGY"),
        "security_considerations": _extract_pack_section(full_document, "SECURITY CONSIDERATIONS"),
        "developer_checklist": _extract_pack_section(full_document, "DEVELOPER CHECKLIST"),
    }

    if not state["architecture"] and not state["api_design"]:
        # The pack doesn't look usable (e.g. too early in the flow) - let
        # the caller fall back to the short plan-only generator instead.
        return []

    with ThreadPoolExecutor(max_workers=len(DOCUMENTATION_FILE_NAMES)) as executor:
        contents = list(executor.map(
            lambda filename: _generate_document_file(filename, state),
            DOCUMENTATION_FILE_NAMES
        ))

    return [
        _write_single_doc(filename, content)
        for filename, content in zip(DOCUMENTATION_FILE_NAMES, contents)
    ]


def _truncate_after_first_section(content: str) -> str:
    """Defensive safety net: some prompts still continue into an
    unrequested extra section despite the stop instruction; cut anything
    after the first heading's content once another heading line appears."""

    lines = content.splitlines()
    heading_indexes = [i for i, line in enumerate(lines) if re.match(r"^#{1,4}\s+\S", line.strip())]

    if len(heading_indexes) <= 1:
        return content

    return "\n".join(lines[:heading_indexes[1]]).rstrip()


def security_considerations_agent(state: SdlcState) -> dict:

    content = call_llm(
        SECURITY_PROMPT.format(
            requirement=state["requirement"],
            architecture=state.get("architecture", ""),
            api_design=state.get("api_design", ""),
            data_model=state.get("data_model", ""),
            rules=MARKDOWN_RULES
        ),
        system=system_prompt(ROLE)
    )
    content = _truncate_after_first_section(content)

    return {
        "security_considerations": content,
        "trace": traced(
            "Security Considerations Agent",
            "Security controls for the implementation pack"
        )
    }


def developer_checklist_agent(state: SdlcState) -> dict:

    content = call_llm(
        CHECKLIST_PROMPT.format(
            requirement=state["requirement"],
            test_strategy=state.get("test_strategy", ""),
            security_considerations=state.get("security_considerations", ""),
            rules=MARKDOWN_RULES
        ),
        system=system_prompt(ROLE)
    )
    content = _truncate_after_first_section(content)

    return {
        "developer_checklist": content,
        "trace": traced(
            "Developer Checklist Agent",
            "Definition of done and implementation order"
        )
    }


def _looks_like_context_echo(text: str) -> bool:
    """True when the model echoed one of the supplied context section
    headers back verbatim instead of writing the requested document."""

    return bool(re.match(
        r"^\s*(REQUIREMENT|ARCHITECTURE|API DESIGN|DATA MODEL)\b",
        text, re.IGNORECASE
    ))


def _generate_document_file(filename: str, state: SdlcState) -> str:

    def _generate() -> str:
        return call_llm(
            DOCUMENT_FILE_CONTEXT.format(
                requirement=state["requirement"],
                architecture=state.get("architecture", ""),
                api_design=state.get("api_design", ""),
                data_model=state.get("data_model", ""),
                security_considerations=state.get("security_considerations", ""),
                test_strategy=state.get("test_strategy", ""),
                developer_checklist=state.get("developer_checklist", ""),
                template=DOCUMENT_FILE_TEMPLATES[filename],
                rules=MARKDOWN_RULES
            ),
            system=system_prompt(ROLE),
            max_tokens=3000
        )

    doc_content = _generate()

    # Lite models occasionally echo the supplied context (REQUIREMENT /
    # ARCHITECTURE / etc. section headers) back verbatim instead of writing
    # the document; that's a different failure mode than the placeholder
    # case below, so it gets its own retry with a fresh generation call.
    for _ in range(2):
        if not _looks_like_context_echo(doc_content):
            break
        doc_content = _generate()

    if _looks_like_context_echo(doc_content):
        # Retries exhausted and it's still an echo - a fallback body beats
        # shipping the raw input context as the "document".
        return _fallback_doc_body(filename)

    # Lite models sometimes echo the <angle-bracket> instructions
    # verbatim; give it up to two corrective passes per file.
    for _ in range(2):
        if not PLACEHOLDER_PATTERN.search(doc_content):
            break
        doc_content = call_llm(
            PLACEHOLDER_FIX_PROMPT.format(
                requirement=state["requirement"],
                architecture=state.get("architecture", ""),
                api_design=state.get("api_design", ""),
                data_model=state.get("data_model", ""),
                content=doc_content
            ),
            system=system_prompt(ROLE),
            max_tokens=3000
        )

    return doc_content.strip() or _fallback_doc_body(filename)


def documentation_agent(state: SdlcState) -> dict:

    plan = call_llm(
        DOCUMENTATION_PLAN_PROMPT.format(
            requirement=state["requirement"],
            architecture=state.get("architecture", ""),
            api_design=state.get("api_design", ""),
            data_model=state.get("data_model", ""),
            security_considerations=state.get("security_considerations", ""),
            test_strategy=state.get("test_strategy", ""),
            developer_checklist=state.get("developer_checklist", ""),
            rules=MARKDOWN_RULES
        ),
        system=system_prompt(ROLE),
        max_tokens=1500
    )
    plan = plan.strip()
    # The model isn't reliable about including the numbered heading itself
    # (it sometimes jumps straight to the "### <document name>" blocks);
    # strip whatever heading it did produce and force the canonical one so
    # the frontend can always find this as its own numbered section instead
    # of it being absorbed into the previous section's content.
    plan = re.sub(r"^#{1,4}\s*\d+\.\s*[^\n]*\n?", "", plan, count=1).strip()
    plan = _filter_documentation_plan(plan)
    plan = f"## 12. DOCUMENTATION\n\n{plan}"

    docs_dir = os.path.join(ensure_generated_code_dir(), DOCS_SUBDIR)
    if os.path.isdir(docs_dir):
        for entry in os.listdir(docs_dir):
            entry_path = os.path.join(docs_dir, entry)
            if os.path.isfile(entry_path):
                os.remove(entry_path)

    written_files = []

    try:
        # Each file is an independent LLM call (and possible corrective
        # retries), so run all 5 concurrently instead of one after another -
        # this is what actually keeps the documentation stage from being the
        # slowest step in the pipeline.
        with ThreadPoolExecutor(max_workers=len(DOCUMENTATION_FILE_NAMES)) as executor:
            contents = list(executor.map(
                lambda filename: _generate_document_file(filename, state),
                DOCUMENTATION_FILE_NAMES
            ))

        for filename, doc_content in zip(DOCUMENTATION_FILE_NAMES, contents):
            written_files.append(_write_single_doc(filename, doc_content))

        _export_documentation_pdfs(written_files)
    except OSError:
        pass

    return {
        "documentation": plan.strip(),
        "trace": traced(
            "Documentation Agent",
            "Documentation plan prioritised by value"
        )
    }
