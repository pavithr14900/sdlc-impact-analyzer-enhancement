"""Exercise a running Legacy Intelligence API with the bundled source fixture.

Uses real repository analysis, including the backend's configured AI insight
synthesis. Does not execute fixture code or change existing capability jobs.
"""
from __future__ import annotations

import argparse
import asyncio
import json
from pathlib import Path
import sys
import time
from urllib.error import HTTPError
from urllib.request import Request, urlopen


def request(base: str, path: str, body: dict | None = None) -> dict:
    data = json.dumps(body).encode() if body is not None else None
    req = Request(base.rstrip("/") + path, data=data,
                  headers={"Content-Type": "application/json"})
    try:
        with urlopen(req, timeout=30) as response:
            result = json.load(response)
    except HTTPError as exc:
        raise RuntimeError(f"{path}: HTTP {exc.code}: {exc.read().decode()}") from exc
    if result.get("success") is not True:
        raise RuntimeError(f"{path}: {result}")
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", default="http://127.0.0.1:5000/api")
    parser.add_argument("--timeout", type=float, default=240)
    parser.add_argument("--adapter-only", action="store_true", help="Verify real MCP call flows on a tiny fixture without HTTP or model calls")
    args = parser.parse_args()
    if args.adapter_only:
        root = Path(__file__).resolve().parents[1]
        sys.path.insert(0, str(root))
        from sdlc.legacy_intelligence.codebase_memory import CodebaseMemoryAdapter
        source = root / "tests/fixtures/memory_repo"
        result = asyncio.run(CodebaseMemoryAdapter().analyze(
            [{"type": "local", "name": "pricing", "path": str(source), "resolvedPath": str(source)}],
            lambda status, step, message: print(message, flush=True),
        ))
        assert result["engine"] == "codebase-memory-mcp"
        assert result["flows"], "Expected the fixture's checkout -> calculate_total call flow"
        assert any("calculate_total" in edge["target"] for flow in result["flows"] for edge in flow["edges"])
        print(json.dumps({"engine": result["engine"], "flows": result["flows"], "limitations": result["limitations"]}, indent=2))
        return
    fixture = Path(__file__).resolve().parents[1] / "tests/fixtures/legacy_repo"
    endpoint = "/legacy-intelligence"
    started = request(args.base_url, endpoint + "/analyze", {
        "repositories": [{"type": "local", "path": str(fixture)}],
    })["analysis"]
    analysis_id = started["analysisId"]
    detail = endpoint + "/" + analysis_id
    deadline = time.monotonic() + args.timeout
    previous = None
    while time.monotonic() < deadline:
        analysis = request(args.base_url, detail)["analysis"]
        progress = (analysis["status"], analysis.get("progress", {}).get("message"))
        if progress != previous:
            print(json.dumps({"analysisId": analysis_id, "status": progress[0],
                              "message": progress[1]}), flush=True)
            previous = progress
        if analysis["status"] == "FAILED":
            raise RuntimeError(analysis.get("error") or "Analysis failed")
        if analysis["status"] == "COMPLETED":
            break
        time.sleep(1)
    else:
        raise TimeoutError(f"Analysis {analysis_id} did not finish within {args.timeout} seconds")

    if analysis.get("overview", {}).get("repositories") != 1:
        raise AssertionError("Expected one analyzed repository")
    if not analysis.get("architecture", {}).get("nodes"):
        raise AssertionError("The fixture should have discovered architecture nodes")
    for view in ("overview", "architecture", "business-rules", "flows"):
        request(args.base_url, detail + "/" + view)
    recent = request(args.base_url, endpoint + "/recent")["analyses"]
    if analysis_id not in {item["analysisId"] for item in recent}:
        raise AssertionError("Completed analysis is missing from saved history")
    reopened = request(args.base_url, detail)["analysis"]
    if reopened["updatedAt"] != analysis["updatedAt"]:
        raise AssertionError("Loading a saved analysis should not start another scan")
    print(json.dumps({"success": True, "analysisId": analysis_id,
                      "engine": analysis.get("engine"),
                      "overview": analysis.get("overview"),
                      "rules": len(analysis.get("businessRules", [])),
                      "flows": len(analysis.get("flows", [])),
                      "limitations": analysis.get("limitations", [])}, indent=2))


if __name__ == "__main__":
    main()
