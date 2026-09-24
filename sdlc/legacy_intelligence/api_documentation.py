"""Consistent API reference tables for model-authored and source-only documents."""
import re

COLUMNS = ("Method", "Path", "Purpose", "Request Body", "Response Body", "Success Status", "Error Statuses")
API_WRITING_RULES = """API DOCUMENTATION FORMAT (takes precedence over the general four-column limit):
Match the SDLC API Design presentation. Include ## Endpoints with a Markdown table using EXACTLY these seven columns:
| Method | Path | Purpose | Request Body | Response Body | Success Status | Error Statuses |
Include the discovered endpoints, using GET, POST, PUT, PATCH, DELETE etc. only when supported by source evidence.
Preserve declared paths; do not redesign them or invent mounted prefixes. Put short, single-line minified JSON examples
inside inline backticks in payload cells ONLY when the supplied source establishes their fields and values.
Never put fenced code blocks or line breaks inside table cells. Escape literal pipes as &#124;.
Use 'Not verified from source' for any missing method, request schema, response schema, status, or purpose.
Do not assume GET means no request body, POST means 201, or add generic 400/401/500 responses without evidence.
Then include ## Endpoint Details, with a ### METHOD /path heading and detailed explanation for each documented endpoint:
purpose and when used; source handler/repository; path/query/header parameters and validation; request fields, types and
requiredness; response fields and success/error behavior; authentication only where supported. Clearly state missing contracts.
Use small parameter tables (Field, Type, Required, Description) where evidence warrants them. JSON code examples may appear
outside the inventory table and must be labeled as examples derived from source; never invent fields or values.
Include ## Validation and Error Handling with an evidence-backed status/condition/response table or an explicit gap statement.
Cite each table row and endpoint explanation with supplied source IDs. Do not claim complete endpoint coverage when the context
is bounded. Keep the Executive Summary, Scope and Context, Engineering Considerations, and Open Questions sections."""


def _cell(value):
    return str(value or "Not verified from source").replace("|", "&#124;").replace("\r", " ").replace("\n", " ").replace("`", "")


def declared_method(fact):
    """Read explicit method declarations on the same line as this path only."""
    methods = set()
    for evidence in fact.get("evidence", []):
        for line in evidence.get("snippet", "").splitlines():
            path = str(fact.get("name", ""))
            quoted_paths = re.findall(r"[\"']([^\"']+)[\"']", line)
            if not path or path not in quoted_paths or line.lstrip().startswith(("#", "//", "*")):
                continue
            for match in re.finditer(r"(?:[.@](get|post|put|patch|delete|head|options)\s*\(|@(Get|Post|Put|Patch|Delete|Head|Options)Mapping\s*\(|\[Http(Get|Post|Put|Patch|Delete|Head|Options)\s*\()", line, re.I):
                methods.add(next(group for group in match.groups() if group).upper())
            if re.search(r"(?:\.route|@RequestMapping)\s*\(", line):
                specification = re.search(r"\bmethods?\s*=\s*(.+)", line)
                if specification:
                    methods.update(re.findall(r"\b(GET|POST|PUT|PATCH|DELETE|HEAD|OPTIONS)\b", specification.group(1)))
    return ", ".join(sorted(methods)) or "Not verified from source"


def render_api_inventory(facts):
    apis = [fact for fact in facts if fact.get("kind") == "api"]
    lines = ["## Executive Summary", "", f"The saved analysis contains {len(apis)} API route declarations. This reference distinguishes discovered routes from request and response contracts that still need verification.",
             "", "## Scope and Context", "", "Paths are source declarations. Mounted prefixes, runtime configuration and complete request/response schemas are not established by the route inventory alone.",
             "", "## Endpoints", "", "| " + " | ".join(COLUMNS) + " |", "| " + " | ".join(["---"] * len(COLUMNS)) + " |"]
    for fact in apis:
        refs = " ".join(f"[{e['id']}]" for e in fact.get("evidence", []) if e.get("id"))
        lines.append("| " + " | ".join([declared_method(fact), _cell(fact.get("name")) + " " + refs,
            "Route declared in " + _cell(fact.get("repository")) + "; business purpose not verified",
            "Not verified from source", "Not verified from source", "Not verified from source", "Not verified from source"]) + " |")
    if not apis:
        lines += ["", "No API route declarations were discovered in the saved analysis."]
    lines += ["", "## Endpoint Details", ""]
    for fact in apis:
        lines += [f"### {declared_method(fact)} {_cell(fact.get('name'))}", "", f"**Repository:** {_cell(fact.get('repository'))}", "",
                  str(fact.get("description") or "A route declaration was discovered. Its full handler behavior has not been established."), "",
                  "| Contract area | Findings |", "| --- | --- |",
                  "| Parameters and headers | Not verified from source |",
                  "| Request body and validation | Not verified from source |",
                  "| Response body and status codes | Not verified from source |",
                  "| Authentication and authorization | Not verified from source |", ""]
        for ev in fact.get("evidence", []):
            lines.append(f"Source: [{ev.get('id') or 'source'}] {_cell(ev.get('repository'))}: {_cell(ev.get('file'))}:{ev.get('lineStart', '?')}")
        lines.append("")
    lines += ["## Validation and Error Handling", "", "The declaration inventory does not establish field validation, exception mappings or response envelopes. Review handler implementations and shared middleware before relying on a contract.",
              "", "## Engineering Considerations", "", "Confirm the deployed route prefix and the handler's request and response contract before integration. Unknown fields in this reference indicate missing evidence, not an absent capability.",
              "", "## Open Questions", "", "- Which request fields and parameters are required?", "- Which response schemas and status codes are guaranteed?", "- Which authentication and validation rules apply to each route?"]
    return "\n".join(lines)


def has_api_reference_format(content):
    expected = [column.lower() for column in COLUMNS]
    table = any([cell.strip().lower() for cell in line.strip().strip("|").split("|")] == expected for line in content.splitlines() if line.strip().startswith("|"))
    return table and "## Endpoint Details" in content and "## Validation and Error Handling" in content
