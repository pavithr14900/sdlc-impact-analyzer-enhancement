import os
import re

from sdlc.agents.common import MARKDOWN_RULES, coding_standards_context, system_prompt
from sdlc.config import ensure_generated_code_dir
from sdlc.llm import call_llm
from sdlc.state import SdlcState, traced

ROLE = "a QA Architect"

FILE_MARKER = re.compile(
    r"^####\s*FILE:\s*(\S+)\s*\n```[^\n]*\n(.*?)```",
    re.MULTILINE | re.DOTALL
)

PROMPT = """
Define the test strategy for the requirement below.

REQUIREMENT
===========
{requirement}

ACCEPTANCE CRITERIA AND SCOPE
=============================
{analysis}

API DESIGN
==========
{api_design}

DATA MODEL
==========
{data_model}

Produce exactly these sections:

## 8. TEST STRATEGY

### Overview

Test levels (unit, integration, API, regression), what is mocked,
what uses a real database, tooling (JUnit 5, Mockito, Spring Boot Test,
MockMvc, Testcontainers, Selenium) and the test data strategy.

### Test Scenarios

A table of scenario id, test level, scenario, test data, expected
result and the acceptance criterion it covers.
Every acceptance criterion must be covered.

### Edge Cases

At least 8 edge cases. For each give scenario, risk, expected behaviour
and the recommended automated test.

{rules}
"""

TEST_CODE_PROMPT = """
Generate compilable automated test code for the requirement below, for
the same primary entity and business operation already implemented in
the generated application code.

REQUIREMENT
===========
{requirement}

TEST STRATEGY
=============
{test_strategy}

API DESIGN
==========
{api_design}

DATA MODEL
==========
{data_model}

Target stack: Java 21, JUnit 5, Mockito, Spring Boot Test, MockMvc for
unit/integration tests; Selenium WebDriver (Java) with JUnit 5 for
end-to-end UI tests against the generated React frontend.
{coding_standards}

Produce exactly these two files:

- backend/src/test/java/.../service/<Entity>ServiceTest.java
  Unit tests for the service layer using JUnit 5 and Mockito, covering
  the happy path and at least 2 edge cases from the test strategy.

- selenium-tests/src/test/java/.../<Entity>E2ETest.java
  A Selenium WebDriver end-to-end test class that drives the primary
  user journey through the browser (locate elements, submit the form,
  assert the result), using JUnit 5 and the Page Object pattern.

Return each file as a fenced code block, immediately preceded on its
own line by "#### FILE: <path>" using the exact relative paths above
(replace ".../" with the real Java package path). Do not add any other
text, headings or commentary before, between or after the files.
"""


def _write_test_files(content: str) -> list[str]:

    output_dir = ensure_generated_code_dir()
    written = []

    for match in FILE_MARKER.finditer(content):

        raw_path = match.group(1).strip()
        file_content = match.group(2)

        safe_path = os.path.normpath(raw_path).replace("\\", "/").lstrip("/")

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


def test_strategy_agent(state: SdlcState) -> dict:

    content = call_llm(
        PROMPT.format(
            requirement=state["requirement"],
            analysis=state.get("requirement_analysis", ""),
            api_design=state.get("api_design", ""),
            data_model=state.get("data_model", ""),
            rules=MARKDOWN_RULES
        ),
        system=system_prompt(ROLE)
    )

    try:
        # If code was generated earlier, attempt to discover backend Java classes
        # and ask the LLM to produce unit tests for each class. This ensures a
        # test file per Java class rather than a single hand-crafted file.
        output_dir = ensure_generated_code_dir()
        backend_src = os.path.join(output_dir, "backend", "src", "main", "java")
        java_classes = []
        if os.path.isdir(backend_src):
            for root, _, files in os.walk(backend_src):
                for f in files:
                    if f.endswith(".java"):
                        rel = os.path.relpath(os.path.join(root, f), backend_src).replace("\\", "/")
                        java_classes.append(rel)

        if java_classes:
            # Build a tailored prompt listing classes and requesting one unit test
            # per class under backend/src/test/java with matching package paths.
            classes_list_text = "\n".join(f"- {c}" for c in java_classes)
            dynamic_prompt = """
Generate compilable JUnit 5 unit test classes for the Java source files listed below. For each
backend source file under `backend/src/main/java/<package>/.../<Name>.java` produce a corresponding
unit test file at `backend/src/test/java/<package>/.../<Name>Test.java` that uses JUnit 5 and Mockito
to test the class's public behavior. Where classes are Spring components (Service, Controller, Repository),
write focused unit tests using Mockito to mock collaborators; for simple POJOs generate basic tests that
verify constructors, getters/setters, and equals/hashCode where applicable.

Produce each test file as a fenced code block preceded by a line: `#### FILE: <path>` (relative to
the generated/code folder). Do not include any other narrative text.

Files to cover:
{classes}

Additionally, produce a Selenium end-to-end test as before for the primary user journey at
`selenium-tests/src/test/java/.../<Entity>E2ETest.java`.
""".format(classes=classes_list_text)

            test_code = call_llm(
                dynamic_prompt + "\n\n" + TEST_CODE_PROMPT,  # append original guidance for e2e test
                system=system_prompt(ROLE),
                max_tokens=9000
            )
        else:
            test_code = call_llm(
                TEST_CODE_PROMPT.format(
                    requirement=state["requirement"],
                    test_strategy=content,
                    api_design=state.get("api_design", ""),
                    data_model=state.get("data_model", ""),
                    coding_standards=coding_standards_context(state["requirement"])
                ),
                system=system_prompt(ROLE),
                max_tokens=6000
            )

        written_files = _write_test_files(test_code)
    except OSError:
        written_files = []

    if written_files:
        file_list = "\n".join(f"- `{path}`" for path in written_files)
        content += (
            "\n\n### Generated Test Code\n\n"
            f"Generated {len(written_files)} test file(s) (JUnit unit tests and a "
            f"Selenium end-to-end test) in the local `generated/code` folder.\n\n"
            f"{file_list}\n"
        )

    return {
        "test_strategy": content,
        "trace": traced(
            "Test Strategy Agent",
            "Test levels, scenarios, edge cases, JUnit and Selenium test code"
        )
    }
