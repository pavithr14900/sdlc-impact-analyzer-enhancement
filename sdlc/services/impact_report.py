"""Validate a compact impact report and render a readable Markdown export.

Model output is advisory data. Invalid fields and citations must not turn into
UI errors or appear to be verified repository evidence.
"""
from __future__ import annotations

import json
import re
from typing import Any


RISK_LEVELS = {level.casefold(): level for level in ("High", "Medium", "Low", "Unknown")}
IMPACT_LEVELS = {level.casefold(): level for level in ("Direct", "Indirect", "Review")}
CONTRACT_STATUS = {value.casefold(): value for value in ("Change needed", "Review needed", "No change identified")}
SOURCE_TOOLS = {"get_code_snippet", "trace_path", "trace_call_path", "search_graph", "search_code"}


def _evidence(context: str) -> dict[str, dict]:
    """Only accept IDs from outer evidence records, never IDs in source text."""
    records = {}
    for line in context.splitlines():
        try:
            record = json.loads(line)
        except (ValueError, TypeError):
            continue
        if isinstance(record, dict) and isinstance(record.get("id"), str) and re.fullmatch(r"E[1-9]\d*", record["id"]):
            records[record["id"]] = record
    return records


def _text(value: Any, limit: int, evidence: dict | None = None) -> str:
    if not isinstance(value, str):
        return ""
    if evidence is not None:
        value = re.sub(r"\bE[1-9]\d*\b", lambda match: match[0] if match[0] in evidence else "", value)
        value = re.sub(r"\[\s*\]|\(\s*\)", "", value)
    value = " ".join(value.split()).strip()
    if len(value) > limit:
        value = value[:limit - 1].rsplit(" ", 1)[0].rstrip(" ,;:") + "…"
    return value


def _enum(value: Any, values: dict[str, str], fallback: str) -> str:
    return values.get(value.strip().casefold(), fallback) if isinstance(value, str) else fallback


def _citations(value: Any, evidence: dict[str, dict]) -> list[str]:
    if not isinstance(value, list):
        return []
    return list(dict.fromkeys(item.strip() for item in value if isinstance(item, str) and item.strip() in evidence))[:6]


def _items(value: Any, fields: dict[str, int], required: tuple[str, ...], cap: int,
           evidence: dict[str, dict], key_fields: tuple[str, ...]) -> list[dict]:
    if not isinstance(value, list):
        return []
    items, seen = [], set()
    for candidate in value:
        if not isinstance(candidate, dict):
            continue
        item = {field: _text(candidate.get(field), limit, evidence) for field, limit in fields.items()}
        if any(not item[field] for field in required):
            continue
        key = tuple(item[field].casefold().strip(" .,:;") for field in key_fields)
        if key in seen:
            continue
        seen.add(key)
        if "evidence_ids" in candidate:
            item["evidence_ids"] = _citations(candidate["evidence_ids"], evidence)
        items.append(item)
        if len(items) >= cap:
            break
    return items


def _source_backed(ids: list[str], evidence: dict[str, dict]) -> bool:
    return any(evidence[item].get("tool") in SOURCE_TOOLS for item in ids)


def _known_file(path: str, ids: list[str], evidence: dict[str, dict]) -> bool:
    """Do not present a model-supplied file path without supporting source data."""
    def strings(value):
        if isinstance(value, str):
            yield value
        elif isinstance(value, dict):
            for child in value.values():
                yield from strings(child)
        elif isinstance(value, list):
            for child in value:
                yield from strings(child)

    normal = path.replace("\\", "/").casefold()
    pattern = re.compile(r"(?<![\w./-])" + re.escape(normal) + r"(?![\w./-])")
    for item in ids:
        for value in strings(evidence[item].get("result")):
            candidate = value.replace("\\", "/").casefold()
            if candidate == normal or candidate.endswith("/" + normal) or pattern.search(candidate):
                return True
    return False


def parse_report(content: str, repository_context: str) -> dict | None:
    """Return a safe display contract, or None so existing analysis can be shown."""
    if not isinstance(content, str):
        return None
    cleaned = content.strip()
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```(?:json)?\s*|\s*```$", "", cleaned, flags=re.IGNORECASE).strip()
    try:
        raw = json.loads(cleaned)
    except (ValueError, TypeError):
        return None
    if not isinstance(raw, dict):
        return None
    evidence = _evidence(repository_context)
    summary = _text(raw.get("summary"), 500, evidence)
    if not summary:
        return None
    report = {
        "title": _text(raw.get("title"), 100, evidence) or "Change impact assessment",
        "summary": summary,
        "overall_risk": _enum(raw.get("overall_risk"), RISK_LEVELS, "Unknown"),
        "risk_reason": _text(raw.get("risk_reason"), 280, evidence),
        "behavior_changes": _items(raw.get("behavior_changes"),
            {"area": 100, "before": 300, "after": 300, "user_impact": 300},
            ("area", "after", "user_impact"), 3, evidence, ("area",)),
        "affected_components": _items(raw.get("affected_components"),
            {"name": 120, "file": 260, "impact": 20, "reason": 280, "action": 240},
            ("name", "reason"), 8, evidence, ("name", "file")),
        "dependencies": _items(raw.get("dependencies"),
            {"source": 120, "target": 120, "relationship": 140, "impact": 260},
            ("source", "target", "relationship", "impact"), 6, evidence, ("source", "target")),
        "risks": _items(raw.get("risks"),
            {"title": 120, "severity": 20, "detail": 300, "mitigation": 260},
            ("title", "detail", "mitigation"), 5, evidence, ("title",)),
        "contract_impacts": _items(raw.get("contract_impacts"),
            {"area": 60, "status": 40, "detail": 350, "action": 280},
            ("area", "detail"), 3, evidence, ("area",)),
        "actions": _items(raw.get("actions"), {"title": 100, "detail": 350, "validation": 280},
            ("title", "detail"), 5, evidence, ("title",)),
        "tests": _items(raw.get("tests"), {"scenario": 280, "expected_result": 350, "purpose": 240},
            ("scenario", "expected_result"), 5, evidence, ("scenario",)),
        "open_questions": [],
    }
    # Actions and tests contain no citation fields in the public contract.
    for item in report["actions"] + report["tests"]:
        item.pop("evidence_ids", None)
    for item in report["behavior_changes"]:
        item.setdefault("evidence_ids", [])
        if not item["before"] or not _source_backed(item["evidence_ids"], evidence):
            item["before"] = "Current behaviour was not established from the retrieved source."
    for item in report["contract_impacts"]:
        item.setdefault("evidence_ids", [])
        item["status"] = _enum(item["status"], CONTRACT_STATUS, "Review needed")
        if not _source_backed(item["evidence_ids"], evidence):
            item["status"] = "Review needed"
            item["detail"] = "Unverified assessment: " + item["detail"]
    for component in report["affected_components"]:
        component.setdefault("evidence_ids", [])
        component["impact"] = _enum(component["impact"], IMPACT_LEVELS, "Review")
        if not _source_backed(component["evidence_ids"], evidence):
            component["impact"] = "Review"
        if component["file"] and not _known_file(component["file"], component["evidence_ids"], evidence):
            component["file"] = ""
            component["impact"] = "Review"
    # A dependency relationship is an existing-code claim: require source proof.
    report["dependencies"] = [item for item in report["dependencies"]
        if _source_backed(item.setdefault("evidence_ids", []), evidence)]
    for risk in report["risks"]:
        risk.setdefault("evidence_ids", [])
        risk["severity"] = _enum(risk["severity"], RISK_LEVELS, "Unknown")
        if risk["severity"] == "Low" and not _source_backed(risk["evidence_ids"], evidence):
            risk["severity"] = "Unknown"
    questions = raw.get("open_questions")
    if isinstance(questions, list):
        seen = set()
        for value in questions:
            question = _text(value, 240, evidence)
            if question and question.casefold() not in seen:
                report["open_questions"].append(question)
                seen.add(question.casefold())
            if len(report["open_questions"]) >= 3:
                break
    supported = any(_source_backed(item["evidence_ids"], evidence)
        for field in ("affected_components", "dependencies", "risks") for item in report[field])
    if report["overall_risk"] == "Low" and not supported:
        report["overall_risk"] = "Unknown"
        report["risk_reason"] = "The retrieved source evidence is insufficient to establish the level of risk."
    if not report["risk_reason"]:
        report["risk_reason"] = "Review the affected components and risks below; retrieval covers only part of the repository."
    return report


def _md(value: str) -> str:
    # Keep model text as text, including in the downloadable report.
    return re.sub(r"([\\`*_{}\[\]<>|])", r"\\\1", value)


def _refs(item: dict) -> str:
    ids = item.get("evidence_ids", [])
    return " (" + ", ".join(ids) + ")" if ids else ""


def render_report(report: dict) -> str:
    """Use one concise report for both the application and its export."""
    lines = ["# " + _md(report["title"]), "", _md(report["summary"]), "",
        "**Overall risk: " + report["overall_risk"] + ".** " + _md(report["risk_reason"])]
    if report.get("behavior_changes"):
        lines += ["", "## What changes for users"]
        for item in report["behavior_changes"]:
            lines += ["", "### " + _md(item["area"]), "",
                "- **Today:** " + _md(item["before"]) + _refs(item),
                "- **After this change:** " + _md(item["after"]),
                "- **User impact:** " + _md(item["user_impact"])]
    if report["affected_components"]:
        lines += ["", "## Affected components"]
        for item in report["affected_components"]:
            location = " — " + _md(item["file"]) if item["file"] else ""
            lines += ["", "- **" + _md(item["name"]) + "**" + location + " (" + item["impact"] + "): "
                + _md(item["reason"]) + _refs(item)]
            if item["action"]:
                lines.append("  Recommended change: " + _md(item["action"]))
    if report["dependencies"]:
        lines += ["", "## Dependencies"]
        for item in report["dependencies"]:
            lines += ["", "- **" + _md(item["source"]) + " → " + _md(item["target"]) + "**: "
                + _md(item["relationship"]) + ". " + _md(item["impact"]) + _refs(item)]
    if report["risks"]:
        lines += ["", "## Key risks"]
        for item in report["risks"]:
            lines += ["", "- **" + _md(item["title"]) + " (" + item["severity"] + "):** "
                + _md(item["detail"]) + _refs(item), "  Mitigation: " + _md(item["mitigation"])]
    if report.get("contract_impacts"):
        lines += ["", "## Data, API and access impact"]
        for item in report["contract_impacts"]:
            lines += ["", "- **" + _md(item["area"]) + " — " + item["status"] + ":** "
                + _md(item["detail"]) + _refs(item)]
            if item["action"]:
                lines.append("  Next step: " + _md(item["action"]))
    if report["actions"]:
        lines += ["", "## Recommended actions", ""]
        for i, item in enumerate(report["actions"], start=1):
            lines.append(f"{i}. **{_md(item['title'])}:** {_md(item['detail'])}")
            if item.get("validation"):
                lines.append("   Done when: " + _md(item["validation"]))
    if report["tests"]:
        lines += ["", "## Verification plan", "", "Proposed checks; these tests have not been run by this analysis.", ""]
        for i, item in enumerate(report["tests"], start=1):
            lines += [f"{i}. **{_md(item['scenario'])}**", "   Expected result: " + _md(item["expected_result"])]
            if item.get("purpose"):
                lines.append("   Why: " + _md(item["purpose"]))
    if report["open_questions"]:
        lines += ["", "## Decisions needed", ""]
        lines += ["- " + _md(question) for question in report["open_questions"]]
    return "\n".join(lines)


def render_analysis_appendix(change: str, findings: dict) -> str:
    """Keep request, source references and retrieval limits with a shared export."""
    lines = ["", "## Analysis context", "", "**Requested change:** " + _md(change), ""]
    for repo in findings.get("indexed", []):
        lines.append("- **Repository:** " + _md(repo["path"]))
    lines += ["", "## Sources", "", "Source IDs refer to the evidence retrieved for this analysis.", ""]
    for item in findings.get("evidence", []):
        result = item.get("result")
        location = (result.get("file_path") or result.get("file") or "") if isinstance(result, dict) else ""
        if not isinstance(location, str):
            location = ""
        if location and isinstance(result.get("start_line"), int):
            location += ":" + str(result["start_line"])
        args = item.get("arguments", {})
        subject = location or next((args[key] for key in ("qualified_name", "function_name", "query", "pattern", "repo_path") if isinstance(args.get(key), str)), "")
        lines.append("- **" + _md(item["id"]) + "** · " + _md(item.get("project", "")) + " · "
            + _md(item.get("tool", "")) + (" · " + _md(subject) if subject else ""))
    if findings.get("warnings"):
        lines += ["", "## Analysis limits", ""]
        lines += ["- " + _md(warning) for warning in findings["warnings"]]
    return "\n".join(lines)


def fallback_document(state: dict, final_content: str) -> str:
    """Preserve readable stage analysis if the model misses the output format."""
    parts = []
    seen = set()
    sections = [("scope", "Change summary"), ("code_impact", "Affected components and dependencies"),
        ("data_impact", "Data and API impact"), ("test_impact", "Tests to run")]
    for field, heading in sections:
        value = state.get(field)
        if not isinstance(value, str) or not value.strip() or value.strip() in seen:
            continue
        value = value.strip()
        seen.add(value)
        # Existing drafts remain Markdown; cap runaway output without inventing a summary.
        if len(value) > 4000:
            value = value[:4000].rsplit("\n", 1)[0] + "\n\nFurther details omitted from this preview."
        parts.append(value if value.startswith("#") else "## " + heading + "\n\n" + value)
    final_content = final_content.strip() if isinstance(final_content, str) else ""
    if final_content and not re.match(r"^(?:```|\{|\[)", final_content) and final_content not in seen:
        parts.append("## Key risks\n\n" + final_content[:4000])
    if not parts:
        return "# Change impact assessment\n\nThe analysis could not be formatted. Review the retrieved source evidence and run the analysis again."
    return "\n\n".join(parts)
