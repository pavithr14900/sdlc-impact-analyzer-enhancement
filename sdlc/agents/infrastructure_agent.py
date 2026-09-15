import os
import re

from sdlc.agents.common import coding_standards_context, system_prompt
from sdlc.config import ensure_generated_code_dir
from sdlc.llm import call_llm
from sdlc.state import SdlcState, traced

ROLE = "a Cloud/DevOps Engineer"

FILE_MARKER = re.compile(
    r"^####\s*FILE:\s*(\S+)\s*\n```[^\n]*\n(.*?)```",
    re.MULTILINE | re.DOTALL
)

PROMPT = """
Generate Terraform infrastructure-as-code for the requirement below,
provisioning the AWS resources implied by the approved architecture.

REQUIREMENT
===========
{requirement}

ARCHITECTURE
============
{architecture}

DATA MODEL
==========
{data_model}

Target stack: the architecture's Spring Boot backend runs on AWS ECS
Fargate behind an Application Load Balancer, the React frontend is
served from S3 + CloudFront, and the database is Amazon RDS for
PostgreSQL sized for the data model above.
{coding_standards}

Produce exactly these files:

- infrastructure/main.tf
  VPC (or reference to default VPC for simplicity), ECS cluster and
  Fargate service/task definition for the backend, an Application Load
  Balancer, an S3 bucket + CloudFront distribution for the frontend,
  and an RDS PostgreSQL instance sized appropriately for the data model.

- infrastructure/variables.tf
  Input variables for region, environment name, instance sizes,
  database credentials (as sensitive variables) and container image.

- infrastructure/outputs.tf
  Outputs for the load balancer DNS name, CloudFront domain name and
  the RDS endpoint.

Use the AWS provider, pin realistic provider/resource versions, and
keep resource names grounded in the requirement (not generic
placeholders). Return each file as a fenced code block, immediately
preceded on its own line by "#### FILE: <path>" using the exact
relative paths above. Do not add any other text, headings or
commentary before, between or after the files.
"""

SUMMARY_PROMPT = """
Write a short paragraph (3 to 5 sentences) summarising the
infrastructure provisioned by the Terraform below for the requirement,
in plain language for a delivery team audience.

REQUIREMENT
===========
{requirement}

TERRAFORM FILES
===============
{terraform}
"""


def _write_infrastructure_files(content: str) -> list[str]:

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


def infrastructure_agent(state: SdlcState) -> dict:

    terraform = call_llm(
        PROMPT.format(
            requirement=state["requirement"],
            architecture=state.get("architecture", ""),
            data_model=state.get("data_model", ""),
            coding_standards=coding_standards_context(state["requirement"])
        ),
        system=system_prompt(ROLE),
        max_tokens=6000
    )

    try:
        written_files = _write_infrastructure_files(terraform)
    except OSError:
        written_files = []

    overview = ""
    if written_files:
        try:
            overview = call_llm(
                SUMMARY_PROMPT.format(
                    requirement=state["requirement"],
                    terraform=terraform
                ),
                system=system_prompt(ROLE),
                max_tokens=400
            )
        except Exception:
            overview = ""

    file_list = "\n".join(f"- `{path}`" for path in written_files)
    content = "## 9. TERRAFORM / INFRASTRUCTURE AS CODE\n\n"
    content += f"{overview.strip()}\n\n" if overview.strip() else ""
    if written_files:
        content += (
            f"### Generated Infrastructure Files\n\n"
            f"Generated {len(written_files)} Terraform file(s) in the local "
            f"`generated/code/infrastructure` folder.\n\n"
            f"{file_list}\n"
        )
    else:
        content += (
            "### Generated Infrastructure Files\n\n"
            "No Terraform files could be parsed from the generated response."
        )

    return {
        "infrastructure": content,
        "trace": traced(
            "Infrastructure Agent",
            "Terraform provisioning for the generated application"
        )
    }
