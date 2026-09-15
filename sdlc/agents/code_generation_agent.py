import os
import re
import shutil

from sdlc.agents.common import coding_standards_context, system_prompt
from sdlc.config import ensure_generated_code_dir
from sdlc.llm import call_llm
from sdlc.state import SdlcState, traced

ROLE = "a Senior Full-Stack Engineer"
DOCS_SUBDIR = "docs"

FILE_MARKER = re.compile(
    r"^####\s*FILE:\s*(\S+)\s*\n```[^\n]*\n(.*?)```",
    re.MULTILINE | re.DOTALL
)

PROMPT = """
Generate representative, compilable code for the requirement below,
based on the interactive prototype, architecture, API design and data
model already produced and approved.

REQUIREMENT
===========
{requirement}

INTERACTIVE APPLICATION PROTOTYPE (approved UI specification)
===============================================================
{ui_prototype}

ARCHITECTURE
============
{architecture}

API DESIGN
==========
{api_design}

DATA MODEL
==========
{data_model}

Target stack: Java 21, Spring Boot 3.x, Spring Data JPA, PostgreSQL,
deployed on AWS. Frontend: React 18 with TypeScript.
{coding_standards}

For the single most important entity and business operation, produce
these files, matching the endpoints and fields already defined in the
API design and data model:

- backend/src/main/java/.../model/<Entity>.java
- backend/src/main/java/.../repository/<Entity>Repository.java
- backend/src/main/java/.../service/<Entity>Service.java
- backend/src/main/java/.../controller/<Entity>Controller.java
- frontend/src/components/<Entity>Panel.tsx
- database/schema.sql

Additionally, produce minimal build and run manifests and entrypoints
so the generated project is runnable out-of-the-box. Include these
exact files (use the real Java package path in place of ".../"):

- backend/pom.xml
- backend/src/main/java/.../Application.java
- backend/src/main/resources/application.properties
- frontend/package.json
- frontend/index.html
- frontend/src/main.tsx

The `pom.xml` should be a minimal Spring Boot Maven POM with web,
JPA and H2 (or PostgreSQL) dependencies and the spring-boot-maven-plugin.
`application.properties` should configure an in-memory H2 datasource and
server port 8080. The frontend `package.json` should contain `dev` and
`build` scripts for Vite and the necessary React/TypeScript deps. The
React entry `src/main.tsx` should mount the generated component.

The React component must implement the screen, fields, form controls,
table columns and actions defined for the corresponding screen in the
UI specification above - do not invent unrelated fields or layouts.

Use constructor injection, DTOs, Jakarta Validation and proper
exception handling in the Java code. Use TypeScript interfaces for the
request/response shapes in the React component. Reuse the schema from
the data model in schema.sql, do not invent new tables.

Return each file as a fenced code block, immediately preceded on its
own line by "#### FILE: <path>" using the exact relative paths above
(replace ".../" with the real Java package path). Do not add any other
text, headings or commentary before, between or after the files. Ensure
the `pom.xml` and `package.json` are valid minimal manifests so the
generated backend and frontend can be started with `mvn spring-boot:run`
and `npm run dev` respectively.
"""


def _write_files(content: str) -> list[str]:

    output_dir = ensure_generated_code_dir()

    if os.path.isdir(output_dir):
        for entry in os.listdir(output_dir):
            if entry == DOCS_SUBDIR:
                continue
            path = os.path.join(output_dir, entry)
            if os.path.isdir(path):
                shutil.rmtree(path)
            else:
                os.remove(path)

    os.makedirs(output_dir, exist_ok=True)

    written = []

    for match in FILE_MARKER.finditer(content):

        raw_path = match.group(1).strip()
        file_content = match.group(2)

        safe_path = os.path.normpath(raw_path).replace("\\", "/")
        safe_path = safe_path.lstrip("/")

        if safe_path.startswith("..") or not safe_path:
            continue

        full_path = os.path.join(output_dir, safe_path)

        if not os.path.abspath(full_path).startswith(os.path.abspath(output_dir)):
            continue

        try:
            os.makedirs(os.path.dirname(full_path), exist_ok=True)

            with open(full_path, "w", encoding="utf-8") as file:
                file.write(file_content.strip() + "\n")
        except OSError:
            continue

        written.append(safe_path)

    return written


def code_generation_agent(state: SdlcState) -> dict:

    content = call_llm(
        PROMPT.format(
            requirement=state["requirement"],
            ui_prototype=state.get("ui_prototype", ""),
            architecture=state.get("architecture", ""),
            api_design=state.get("api_design", ""),
            data_model=state.get("data_model", ""),
            coding_standards=(coding_standards_context(state["requirement"]) + "\n\n" + state.get("development_standards", "")).strip()
        ),
        system=system_prompt(ROLE),
        max_tokens=6000
    )

    written_files = []
    write_failed = False

    try:
        written_files = _write_files(content)
    except OSError:
        write_failed = True

    if written_files:
        file_list = "\n".join(f"- `{path}`" for path in written_files)
        summary = (
            "## 7. GENERATED CODE\n\n"
            f"Generated {len(written_files)} file(s) in the local `generated/code` "
            f"folder. Use the file explorer below to preview each one.\n\n"
            f"{file_list}\n"
        )
    elif write_failed:
        summary = (
            "## 7. GENERATED CODE\n\n"
            "The generated files could not be written to the local `generated/code` "
            "folder. Check disk space and folder permissions, then try again."
        )
    else:
        summary = (
            "## 7. GENERATED CODE\n\n"
            "No files could be parsed from the generated response."
        )

    return {
        "generated_code": summary,
        "trace": traced(
            "Code Generation Agent",
            "Backend, frontend and database code written to the local repo"
        )
    }

