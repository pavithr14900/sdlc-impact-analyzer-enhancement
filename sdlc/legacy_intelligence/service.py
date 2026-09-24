"""Asynchronous analysis orchestration with durable progress and evidence snapshots."""
from __future__ import annotations

import asyncio
from copy import deepcopy
from queue import Queue, Empty
from pathlib import Path
import threading
from urllib.parse import urlsplit
import uuid

from sdlc.integrations.mcp_client import error_message
from sdlc.services.change_impact_service import _ensure_local_checkout

from . import repository
from .codebase_memory import get_adapter
from .models import progress, validate_repositories


class AnalysisDeleted(Exception):
    """The user removed this analysis while a background operation was running."""


AI_INSIGHTS_TIMEOUT_SECONDS = 120


def _bounded_ai_insights(analysis: dict) -> dict:
    """Keep optional AI enrichment from blocking access to source findings.

    A detached worker receives its own snapshot; late results cannot overwrite
    the completed analysis. Transport timeouts also bound outstanding requests.
    """
    from sdlc.services.legacy_intelligence_service import run_ai_insights

    results = Queue(maxsize=1)
    snapshot = deepcopy(analysis)

    def synthesize():
        try:
            results.put((run_ai_insights(snapshot), None))
        except Exception as exc:
            results.put((None, exc))

    threading.Thread(target=synthesize, name="legacy-ai-insights", daemon=True).start()
    try:
        result, error = results.get(timeout=AI_INSIGHTS_TIMEOUT_SECONDS)
    except Empty:
        raise TimeoutError(
            "The AI insight time limit was reached. Source findings are available; "
            "AI narratives could not be completed."
        ) from None
    if error is not None:
        raise error
    return result


def start_analysis(payload: dict) -> dict:
    sources = validate_repositories(payload)
    for index, source in enumerate(sources):
        original = source.get("path") or urlsplit(source["url"]).path.rstrip("/")
        source["name"] = Path(original).name.removesuffix(".git") or f"Repository {index + 1}"
    # Distinct roots can have the same basename; keep evidence repository identities unique.
    names: dict[str, int] = {}
    for source in sources:
        name = source["name"]
        names[name] = names.get(name, 0) + 1
        if names[name] > 1:
            source["name"] = f"{name} ({names[name]})"
    created = repository.now()
    analysis = {"analysisId": uuid.uuid4().hex, "name": sources[0]["name"] + (f" + {len(sources) - 1}" if len(sources) > 1 else ""), "repositories": sources, "status": "NOT_STARTED", "progress": progress(0, "Queued for analysis"), "createdAt": created, "updatedAt": created, "overview": {key: None for key in ("repositories", "services", "classes", "apis", "databaseTables", "externalIntegrations", "scheduledJobs")}, "architecture": {"nodes": [], "edges": []}, "businessRules": [], "flows": [], "relationships": [], "evidence": [], "facts": [], "limitations": [], "narratives": {}, "insights": None, "insightsDocument": "", "engine": None, "error": None}
    repository.save(analysis)

    def update(status, step, message):
        analysis.update(status=status, progress=progress(step, message))
        if repository.save(analysis) is None:
            raise AnalysisDeleted()

    def run():
        try:
            update("SCANNING", 1, "Scanning repositories")
            for source in sources:
                source["resolvedPath"] = _ensure_local_checkout(source.get("url"), source.get("path"), None)
            update("SCANNING", 2, "Discovering source files")
            result = asyncio.run(get_adapter().analyze(sources, update))
            analysis.update(result)
            update("ANALYZING", 7, "Synthesizing AI insights (up to 2 minutes); source scanning is complete")
            try:
                analysis.update(_bounded_ai_insights(analysis))
            except Exception as exc:
                analysis.setdefault("limitations", []).append(f"AI insight synthesis was skipped: {error_message(exc)}")
            update("COMPLETED", 8, "Analysis complete")
        except AnalysisDeleted:
            return
        except Exception as exc:
            analysis.update(status="FAILED", error=error_message(exc))
            repository.save(analysis)

    thread = threading.Thread(target=run, name=f"legacy-{analysis['analysisId'][:8]}", daemon=True)
    thread.start()
    # Fetch a separate snapshot so worker mutations cannot race the JSON response.
    return repository.get(analysis["analysisId"])


def require_completed(analysis_id: str) -> dict:
    analysis = repository.get(analysis_id)
    if analysis is None:
        raise LookupError("Analysis not found.")
    if analysis["status"] != "COMPLETED":
        raise RuntimeError("Complete a repository analysis before using this action.")
    return analysis
