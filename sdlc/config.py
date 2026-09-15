import os
from pathlib import Path

from dotenv import load_dotenv

# Resolve .env relative to the project root (not the process cwd) so the
# key/config values always load no matter where the server was started
# from. override=True ensures .env wins over any stale/blank values already
# present in the shell's environment (e.g. an empty LANGCHAIN_API_KEY).
load_dotenv(Path(__file__).resolve().parent.parent / ".env", override=True)


REGION = os.getenv("AWS_REGION", "eu-west-2")

MODEL_ID = os.getenv("BEDROCK_MODEL_ID", "amazon.nova-lite-v1:0")

OUTPUT_DIR = os.getenv("SDLC_OUTPUT_DIR", "generated")

# LangSmith reads these from the environment itself, so just make sure
# they're set (with sane defaults) whenever an API key is provided. Both
# the legacy LANGCHAIN_* and current LANGSMITH_* names are set since the
# SDK version in use determines which one it actually reads.
if os.getenv("LANGCHAIN_API_KEY"):
    _project = os.getenv("LANGSMITH_PROJECT", "sdlc-demo")
    os.environ.setdefault("LANGCHAIN_TRACING_V2", "true")
    os.environ.setdefault("LANGCHAIN_PROJECT", _project)
    os.environ.setdefault("LANGSMITH_TRACING", "true")
    os.environ.setdefault("LANGSMITH_API_KEY", os.environ["LANGCHAIN_API_KEY"])
    os.environ.setdefault("LANGSMITH_PROJECT", _project)

JIRA_BASE_URL = os.getenv("JIRA_BASE_URL", "")
JIRA_EMAIL = os.getenv("JIRA_EMAIL", "")
JIRA_API_TOKEN = os.getenv("JIRA_API_TOKEN", "")
JIRA_PROJECT_KEY = os.getenv("JIRA_PROJECT_KEY", "")
JIRA_ISSUE_TYPE = os.getenv("JIRA_ISSUE_TYPE", "Story")

CONFLUENCE_BASE_URL = os.getenv("CONFLUENCE_BASE_URL", "")
CONFLUENCE_EMAIL = os.getenv("CONFLUENCE_EMAIL", "")
CONFLUENCE_API_TOKEN = os.getenv("CONFLUENCE_API_TOKEN", "")
CONFLUENCE_SPACE_KEY = os.getenv("CONFLUENCE_SPACE_KEY", "")
CONFLUENCE_PARENT_PAGE_ID = os.getenv("CONFLUENCE_PARENT_PAGE_ID", "")

GITHUB_TOKEN = os.getenv("GITHUB_TOKEN", "")
GITHUB_REPO = os.getenv("GITHUB_REPO", "")
GITHUB_BRANCH = os.getenv("GITHUB_BRANCH", "main")

REQUIREMENT_OUTPUT_FILE = os.path.join(
    OUTPUT_DIR,
    "requirement-analysis.md"
)

ARCHITECTURE_DIAGRAM_FILE = os.path.join(
    OUTPUT_DIR,
    "architecture.drawio"
)

GENERATED_CODE_DIR = os.path.join(
    OUTPUT_DIR,
    "code"
)

KNOWLEDGE_BASE_FILE = os.path.join(
    OUTPUT_DIR,
    "knowledge_base.json"
)


def ensure_output_dir() -> str:

    os.makedirs(OUTPUT_DIR, exist_ok=True)

    return OUTPUT_DIR


def ensure_generated_code_dir() -> str:

    os.makedirs(GENERATED_CODE_DIR, exist_ok=True)

    return GENERATED_CODE_DIR
