import json
import os
import re
from functools import lru_cache

import boto3
from botocore.config import Config
from langsmith import traceable
from langsmith.run_helpers import get_current_run_tree

from sdlc.config import get_model_id, REGION

# Optional: set these in .env to send exact cost with every trace instead of
# relying on LangSmith's model pricing table (which has no built-in entry
# for Bedrock/Nova models). Values are $ per 1,000 tokens; leave at 0 to
# skip cost reporting (token counts are still sent either way).
BEDROCK_INPUT_PRICE_PER_1K = float(
    os.getenv("BEDROCK_INPUT_PRICE_PER_1K") or "0"
)
BEDROCK_OUTPUT_PRICE_PER_1K = float(
    os.getenv("BEDROCK_OUTPUT_PRICE_PER_1K") or "0"
)
# Larger prompts (code generation, documentation) can take longer than the
# default 60s read timeout, and Bedrock occasionally throttles, so allow
# more time and let botocore retry transient failures automatically.
_bedrock = boto3.client(
    "bedrock-runtime",
    region_name=REGION,
    config=Config(
        connect_timeout=10,
        read_timeout=180,
        retries={"mode": "standard", "max_attempts": 4}
    )
)


class AIProviderError(Exception):
    """Actionable provider failure safe to display without exposing credentials."""


def _provider_error(exc: Exception) -> AIProviderError:
    code = getattr(exc, "response", {}).get("Error", {}).get("Code", "")
    if code in {"AccessDeniedException", "ValidationException", "UnauthorizedException"}:
        return AIProviderError(
            f"Bedrock rejected model '{get_model_id()}' in {REGION} ({code}). "
            "Select an enabled model in the MODEL selector, or ask your AWS administrator "
            "to verify model access and inference-profile permissions."
        )
    if code in {"ExpiredTokenException", "UnrecognizedClientException", "InvalidSignatureException"} or type(exc).__name__ in {"NoCredentialsError", "PartialCredentialsError"}:
        return AIProviderError("AWS credentials are missing, invalid, or expired. Refresh the backend AWS credentials and retry.")
    if code in {"ThrottlingException", "ServiceUnavailableException", "ModelNotReadyException"}:
        return AIProviderError("The AI provider is temporarily busy. Retry shortly or select another enabled model.")
    return AIProviderError(
        f"The AI request failed ({code or type(exc).__name__}). "
        "Check the backend network connection and AI provider configuration, then retry."
    )


@lru_cache(maxsize=4)
def _bedrock_for_timeout(seconds: int):
    return boto3.client(
        "bedrock-runtime", region_name=REGION,
        config=Config(connect_timeout=5, read_timeout=seconds,
                      retries={"mode": "standard", "total_max_attempts": 1}),
    )


@traceable(run_type="llm", name="bedrock_converse")
def call_llm(
    prompt: str,
    system: str = "",
    temperature: float = 0.2,
    max_tokens: int = 4096,
    timeout_seconds: int | None = None,
) -> str:

    request = {
        "modelId": get_model_id(),
        "messages": [
            {
                "role": "user",
                "content": [
                    {
                        "text": prompt
                    }
                ]
            }
        ],
        "inferenceConfig": {
            "temperature": temperature,
            "maxTokens": max_tokens
        }
    }

    if system:
        request["system"] = [
            {
                "text": system
            }
        ]

    # Optional short, single-attempt calls for interactive discovery workflows.
    client = _bedrock if timeout_seconds is None else _bedrock_for_timeout(timeout_seconds)
    try:
        response = client.converse(**request)
    except Exception as exc:
        raise _provider_error(exc) from exc

    usage = response.get("usage") or {}
    run_tree = get_current_run_tree()
    if run_tree and usage:
        input_tokens = usage.get("inputTokens", 0)
        output_tokens = usage.get("outputTokens", 0)
        usage_metadata = {
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "total_tokens": usage.get("totalTokens", 0),
        }
        if BEDROCK_INPUT_PRICE_PER_1K or BEDROCK_OUTPUT_PRICE_PER_1K:
            # Send cost directly so it doesn't depend on LangSmith having a
            # matching entry in its model pricing table for this model.
            # total_cost is sent explicitly too - the Runs table's cost
            # column reads it directly rather than summing input/output.
            input_cost = input_tokens / 1000 * BEDROCK_INPUT_PRICE_PER_1K
            output_cost = output_tokens / 1000 * BEDROCK_OUTPUT_PRICE_PER_1K
            usage_metadata["input_cost"] = input_cost
            usage_metadata["output_cost"] = output_cost
            usage_metadata["total_cost"] = input_cost + output_cost

        # LangSmith reads this shape to render token counts (and cost, if
        # it has pricing for the model) on the trace.
        run_tree.add_metadata({
            "usage_metadata": usage_metadata,
            "ls_provider": "bedrock",
            "ls_model_name": get_model_id(),
        })

    content = response.get("output", {}).get("message", {}).get("content", [])
    text = "\n".join(block["text"] for block in content if isinstance(block.get("text"), str)).strip()
    if not text:
        raise AIProviderError("The AI model returned no text. Retry or select another enabled model.")
    if response.get("stopReason") == "max_tokens":
        raise AIProviderError("The AI response exceeded its output limit. Ask a more focused question and retry.")
    return text


def call_llm_json(
    prompt: str,
    system: str = "",
    temperature: float = 0.1,
    max_tokens: int = 4096,
    timeout_seconds: int | None = None,
) -> dict:

    options = {} if timeout_seconds is None else {"timeout_seconds": timeout_seconds}
    raw = call_llm(
        prompt,
        system=system,
        temperature=temperature,
        max_tokens=max_tokens,
        **options,
    )

    cleaned = re.sub(
        r"^```(?:json)?|```$",
        "",
        raw.strip(),
        flags=re.MULTILINE
    ).strip()

    start = cleaned.find("{")
    end = cleaned.rfind("}")

    if start == -1 or end == -1:
        raise ValueError("No JSON object found in model response.")

    return json.loads(cleaned[start:end + 1])
