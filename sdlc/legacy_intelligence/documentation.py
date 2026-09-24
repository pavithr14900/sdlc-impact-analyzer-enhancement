"""Generate simple, evidence-backed documentation from an analysis snapshot.

This module provides a conservative, deterministic document generator used
by the frontend DocumentationGenerator. It intentionally produces plain
markdown-like content assembled from discovered facts and evidence. The
implementation is lightweight and safe to run without calling external
services.
"""
from __future__ import annotations

from typing import List
import os
import json
import re
from datetime import datetime
from pathlib import Path

from sdlc.config import ensure_generated_code_dir
from sdlc.agents.quality_agent import _render_documentation_pdf as _render_pdf

DOC_TYPES = [
    "application_overview",
    "system_architecture",
    "component_documentation",
    "api_documentation",
    "database_documentation",
    "service_dependencies",
    "external_integrations",
    "scheduled_jobs",
    "business_rules",
    "application_flows",
    "security_overview",
    "technical_debt",
]


def _evidence_list(evidence: list) -> list[dict]:
    if not evidence:
        return []
    out = []
    for item in evidence:
        out.append({
            "id": item.get("id"),
            "repository": item.get("repository"),
            "file": item.get("file"),
            "symbol": item.get("symbol"),
            "lineStart": item.get("lineStart"),
            "lineEnd": item.get("lineEnd"),
        })
    return out


def _section_evidence(analysis: dict, kind: str) -> list[dict]:
    kinds = {"component_documentation": {"service", "class"}, "api_documentation": {"api"}, "database_documentation": {"databaseTable"}, "external_integrations": {"externalIntegration"}, "scheduled_jobs": {"scheduledJob"}, "service_dependencies": {"dependency"}}
    evidence = []
    if kind == "application_overview":
        evidence.extend(analysis.get("evidence", []))
    for fact in analysis.get("facts", []):
        if fact.get("kind") in kinds.get(kind, set()):
            evidence.extend(fact.get("evidence", []))
    collections = {"business_rules": analysis.get("businessRules", []), "application_flows": analysis.get("flows", []), "system_architecture": (analysis.get("architecture") or {}).get("nodes", []) + (analysis.get("architecture") or {}).get("edges", []), "service_dependencies": analysis.get("relationships", [])}
    for item in collections.get(kind, []):
        evidence.extend(item.get("evidence", []))
    narrative_key = {"system_architecture": "architecture", "business_rules": "businessRules", "application_flows": "flows", "service_dependencies": "dependencies", "external_integrations": "dependencies", "scheduled_jobs": "dependencies", "security_overview": "security", "technical_debt": "technicalDebt"}.get(kind)
    cited = set(re.findall(r"\bE\d+\b", (analysis.get("narratives") or {}).get(narrative_key, "")))
    evidence.extend(item for item in analysis.get("evidence", []) if item.get("id") in cited)
    return list({(item.get("repository"), item.get("file"), item.get("lineStart")): item for item in evidence}.values())


def _safe_filename(name: str) -> str:
    return "".join(c if c.isalnum() or c in "-_ ." else "-" for c in name).strip().replace(" ", "_")


_FRONT_MATTER = re.compile(r"^---\n.*?\n---\n\n?", re.DOTALL)


def _strip_front_matter(content: str) -> str:
    """Drop the YAML-style front matter block used for the exported .md/.pdf
    files; the API response should show clean Markdown, not the raw
    delimiters and metadata lines."""
    return _FRONT_MATTER.sub("", content, count=1)


def generate_documentation(analysis: dict, types: List[str]) -> List[dict]:
    """Generate structured documentation files (markdown + optional PDFs).

    Writes per-analysis documentation into `generated/docs/legacy-intelligence/<analysisId>/`.
    Returns a list of document metadata objects including an optional `pdf` relative path
    (e.g. `docs/legacy-intelligence/<id>/application_overview.pdf`) which the frontend
    can download via the existing `/api/documentation/pdf` endpoint.
    """
    analysis_id = analysis.get("analysisId") or "analysis"
    overview = analysis.get("overview") or {}
    architecture = analysis.get("architecture") or {}
    facts = analysis.get("facts") or []
    evidence = analysis.get("evidence") or []
    business_rules = analysis.get("businessRules") or []
    narratives = analysis.get("narratives") or {}
    insights = analysis.get("insights") or {}

    base = Path(ensure_generated_code_dir()) / "docs" / "legacy-intelligence" / analysis_id
    base.mkdir(parents=True, exist_ok=True)

    documents = []

    def with_references(content: str) -> str:
        references = [f"- [{ev.get('id') or 'source'}] {ev.get('repository')}: {ev.get('file')}:{ev.get('lineStart')}-{ev.get('lineEnd')} ({ev.get('symbol') or 'declaration'})" for ev in evidence]
        if references:
            content += "\n\n## Source Evidence\n\n" + "\n".join(references)
        if analysis.get("limitations"):
            content += "\n\n## Coverage Limitations\n\n" + "\n".join(f"- {item}" for item in analysis["limitations"])
        return content

    def _render_documentation_pdf(content: str, destination: str):
        _render_pdf(with_references(content), destination)

    def write_md(filename: str, content: str) -> str:
        path = base / filename
        if path.stem in DOC_TYPES:
            content = with_references(content)
        path.write_text(content, encoding="utf-8")
        # Return path relative to GENERATED_CODE_DIR
        rel = Path("docs") / "legacy-intelligence" / analysis_id / filename
        return str(rel).replace("\\", "/")

    # Index / front-matter
    index_lines = ["---", f"analysisId: {analysis_id}", f"generatedAt: {datetime.utcnow().isoformat()}Z", "---", "", f"# Analysis: {analysis.get('name', analysis_id)}", ""]

    # Per-requested document types
    for kind in types:
        if kind not in DOC_TYPES:
            continue
        evidence = _section_evidence(analysis, kind)
        title = kind.replace("_", " ").title()
        if kind == "application_overview":
            lines = ["---", f"title: {title}", "type: application_overview", "---", "", f"# {title}", ""]
            if insights.get("summary"):
                lines += ["## Executive Summary", "", insights["summary"], ""]
            lines.append("## Discovered Metrics")
            for key in ("repositories", "services", "classes", "apis", "databaseTables", "externalIntegrations", "scheduledJobs"):
                lines.append(f"- {key}: {overview.get(key) if overview.get(key) is not None else '—'}")
            if insights.get("key_risks"):
                lines += ["", "## Key Risks"] + [f"- {item}" for item in insights["key_risks"]]
            if insights.get("modernization_priorities"):
                lines += ["", "## Modernization Priorities"] + [f"- {item}" for item in insights["modernization_priorities"]]
            if insights.get("open_questions"):
                lines += ["", "## Open Questions"] + [f"- {item}" for item in insights["open_questions"]]
            content = "\n".join(lines)
            md_rel = write_md(f"{kind}.md", content)
            pdf_rel = str(Path(md_rel).with_suffix('.pdf'))
            try:
                _render_documentation_pdf(content, str((base / f"{kind}.pdf")))
            except Exception:
                pdf_rel = ""
            documents.append({"type": kind, "title": title, "content": _strip_front_matter(content), "evidence": _evidence_list(evidence), "pdf": pdf_rel})

        elif kind == "system_architecture":
            lines = ["---", f"title: {title}", "type: system_architecture", "---", "", f"# {title}", ""]
            if narratives.get("architecture"):
                lines += [narratives["architecture"], ""]
            lines.append("## Components")
            for n in architecture.get("nodes", [])[:200]:
                lines.append(f"- {n.get('name')} ({n.get('type')}) — repo: {n.get('repository')}")
            lines += ["", "## Relationships"]
            for e in architecture.get("edges", [])[:400]:
                lines.append(f"- {e.get('source')} -> {e.get('target')} — {e.get('relationship')}")
            content = "\n".join(lines)
            md_rel = write_md(f"{kind}.md", content)
            pdf_rel = str(Path(md_rel).with_suffix('.pdf'))
            try:
                _render_documentation_pdf(content, str((base / f"{kind}.pdf")))
            except Exception:
                pdf_rel = ""
            documents.append({"type": kind, "title": title, "content": _strip_front_matter(content), "evidence": _evidence_list(evidence), "pdf": pdf_rel})

        elif kind == "component_documentation":
            lines = ["---", f"title: {title}", "type: component_documentation", "---", "", f"# {title}", ""]
            for fact in facts:
                if fact.get("kind") in {"service", "class"}:
                    fname = _safe_filename(f"component_{fact.get('repository')}_{fact.get('name')}.md")
                    fm = ["---", f"title: {fact.get('name')}", f"repository: {fact.get('repository')}", f"kind: {fact.get('kind')}", f"evidence_count: {len(fact.get('evidence', []))}", "---", "", f"# {fact.get('name')}", ""]
                    fm.append(fact.get('description', ''))
                    fm.append("\n## Evidence\n")
                    for ev in fact.get('evidence', [])[:8]:
                        fm.append(f"- {ev.get('repository')}: {ev.get('file')}{(':' + str(ev.get('lineStart'))) if ev.get('lineStart') else ''}")
                    write_md(fname, "\n".join(fm))
                    lines.extend([f"## {fact.get('name')}", "", f"Repository: {fact.get('repository')}", fact.get('description', ''), ""])
            content = "\n".join(lines)
            md_rel = write_md(f"{kind}.md", content)
            pdf_rel = str(Path(md_rel).with_suffix('.pdf'))
            try:
                _render_documentation_pdf(content, str((base / f"{kind}.pdf")))
            except Exception:
                pdf_rel = ""
            documents.append({"type": kind, "title": title, "content": _strip_front_matter(content), "evidence": _evidence_list(evidence), "pdf": pdf_rel})

        elif kind == "api_documentation":
            from .api_documentation import render_api_inventory
            title = "API Documentation"
            content = f"# {title}\n\n" + render_api_inventory(facts)
            md_rel = write_md(f"{kind}.md", content)
            pdf_rel = str(Path(md_rel).with_suffix('.pdf'))
            try:
                _render_documentation_pdf(content, str((base / f"{kind}.pdf")))
            except Exception:
                pdf_rel = ""
            documents.append({"type": kind, "title": title, "content": _strip_front_matter(content), "evidence": _evidence_list(evidence), "pdf": pdf_rel})

        elif kind == "database_documentation":
            tables = [f for f in facts if f.get('kind') == 'databaseTable']
            content = "---\n" + f"title: {title}\ntype: database_documentation\n---\n\n# {title}\n\n" + ("\n".join(f"- {t.get('name')} — {t.get('repository')}" for t in tables) if tables else "No database tables discovered.")
            md_rel = write_md(f"{kind}.md", content)
            pdf_rel = str(Path(md_rel).with_suffix('.pdf'))
            try:
                _render_documentation_pdf(content, str((base / f"{kind}.pdf")))
            except Exception:
                pdf_rel = ""
            documents.append({"type": kind, "title": title, "content": _strip_front_matter(content), "evidence": _evidence_list(evidence), "pdf": pdf_rel})

        elif kind == "service_dependencies":
            graph = analysis.get("graphFacts") or []
            lines = ["---", f"title: {title}", "type: service_dependencies", "---", "", f"# {title}", ""]
            if narratives.get("dependencies"):
                lines += [narratives["dependencies"], ""]
            lines.append("## Indexed Repository Summaries")
            if graph:
                for g in graph[:10]:
                    lines.append(f"- Repository: {g.get('repository')} — index summary: {g.get('index', {}).get('summary', {})}")
            else:
                lines.append("No graph index summaries available (development engine or MCP not connected).")
            content = "\n".join(lines)
            md_rel = write_md(f"{kind}.md", content)
            pdf_rel = str(Path(md_rel).with_suffix('.pdf'))
            try:
                _render_documentation_pdf(content, str((base / f"{kind}.pdf")))
            except Exception:
                pdf_rel = ""
            documents.append({"type": kind, "title": title, "content": _strip_front_matter(content), "evidence": _evidence_list(evidence), "pdf": pdf_rel})

        elif kind == "external_integrations":
            ext = [f for f in facts if f.get('kind') == 'externalIntegration']
            lines = ["---", f"title: {title}", "type: external_integrations", "---", "", f"# {title}", ""]
            if narratives.get("dependencies"):
                lines += [narratives["dependencies"], ""]
            lines.append("## Referenced Hosts")
            lines += [f"- {e.get('name')} — {e.get('repository')}" for e in ext] if ext else ["No external URLs discovered."]
            content = "\n".join(lines)
            md_rel = write_md(f"{kind}.md", content)
            pdf_rel = str(Path(md_rel).with_suffix('.pdf'))
            try:
                _render_documentation_pdf(content, str((base / f"{kind}.pdf")))
            except Exception:
                pdf_rel = ""
            documents.append({"type": kind, "title": title, "content": _strip_front_matter(content), "evidence": _evidence_list(evidence), "pdf": pdf_rel})

        elif kind == "scheduled_jobs":
            jobs = [f for f in facts if f.get('kind') == 'scheduledJob']
            lines = ["---", f"title: {title}", "type: scheduled_jobs", "---", "", f"# {title}", ""]
            if narratives.get("dependencies"):
                lines += [narratives["dependencies"], ""]
            lines.append("## Discovered Scheduling Declarations")
            lines += [f"- {j.get('name')} — {j.get('repository')}" for j in jobs] if jobs else ["No scheduling declarations discovered."]
            content = "\n".join(lines)
            md_rel = write_md(f"{kind}.md", content)
            pdf_rel = str(Path(md_rel).with_suffix('.pdf'))
            try:
                _render_documentation_pdf(content, str((base / f"{kind}.pdf")))
            except Exception:
                pdf_rel = ""
            documents.append({"type": kind, "title": title, "content": _strip_front_matter(content), "evidence": _evidence_list(evidence), "pdf": pdf_rel})

        elif kind == "business_rules":
            lines = ["---", f"title: {title}", "type: business_rules", "---", "", f"# {title}", ""]
            if narratives.get("businessRules"):
                lines += [narratives["businessRules"], ""]
            lines.append("## Candidate Rules (Raw Discovery)")
            if business_rules:
                for rule in business_rules[:60]:
                    lines.append(f"- {rule.get('id')}: {rule.get('title')} — {rule.get('description')} (confidence: {rule.get('confidence')})")
            else:
                lines.append("No candidate business rules discovered.")
            content = "\n".join(lines)
            md_rel = write_md(f"{kind}.md", content)
            pdf_rel = str(Path(md_rel).with_suffix('.pdf'))
            try:
                _render_documentation_pdf(content, str((base / f"{kind}.pdf")))
            except Exception:
                pdf_rel = ""
            documents.append({"type": kind, "title": title, "content": _strip_front_matter(content), "evidence": _evidence_list(evidence), "pdf": pdf_rel})

        elif kind == "application_flows":
            flows = analysis.get("flows") or []
            lines = ["---", f"title: {title}", "type: application_flows", "---", "", f"# {title}", ""]
            if narratives.get("flows"):
                lines += [narratives["flows"], ""]
            if flows:
                lines.append("## Indexed Flows")
                lines += [f"- {f.get('title') or f.get('name') or f.get('id')}" for f in flows]
            content = "\n".join(lines)
            md_rel = write_md(f"{kind}.md", content)
            pdf_rel = str(Path(md_rel).with_suffix('.pdf'))
            try:
                _render_documentation_pdf(content, str((base / f"{kind}.pdf")))
            except Exception:
                pdf_rel = ""
            documents.append({"type": kind, "title": title, "content": _strip_front_matter(content), "evidence": _evidence_list(evidence), "pdf": pdf_rel})

        elif kind == "security_overview":
            lines = ["---", f"title: {title}", "type: security_overview", "---", "", f"# {title}", ""]
            lines.append(narratives.get("security") or "No evidence-backed security assessment was generated. The current source inventory cannot establish security controls or vulnerabilities.")
            content = "\n".join(lines)
            md_rel = write_md(f"{kind}.md", content)
            pdf_rel = str(Path(md_rel).with_suffix('.pdf'))
            try:
                _render_documentation_pdf(content, str((base / f"{kind}.pdf")))
            except Exception:
                pdf_rel = ""
            documents.append({"type": kind, "title": title, "content": _strip_front_matter(content), "evidence": _evidence_list(evidence), "pdf": pdf_rel})

        elif kind == "technical_debt":
            lines = ["---", f"title: {title}", "type: technical_debt", "---", "", f"# {title}", ""]
            lines.append(narratives.get("technicalDebt") or "No evidence-backed technical debt assessment was generated. Code complexity and test coverage have not been established by this analysis.")
            content = "\n".join(lines)
            md_rel = write_md(f"{kind}.md", content)
            pdf_rel = str(Path(md_rel).with_suffix('.pdf'))
            try:
                _render_documentation_pdf(content, str((base / f"{kind}.pdf")))
            except Exception:
                pdf_rel = ""
            documents.append({"type": kind, "title": title, "content": _strip_front_matter(content), "evidence": _evidence_list(evidence), "pdf": pdf_rel})

        else:
            # Generic fallback: include a header and minimal content
            content = "---\n" + f"title: {title}\ntype: {kind}\n---\n\n# {title}\n\nNo detailed content available."
            md_rel = write_md(f"{kind}.md", content)
            pdf_rel = ""
            documents.append({"type": kind, "title": title, "content": _strip_front_matter(content), "evidence": _evidence_list(evidence), "pdf": pdf_rel})

    # Write index file
    index_lines.append("## Documents")
    for doc in documents:
        doc["content"] = _strip_front_matter((base / f"{doc['type']}.md").read_text(encoding="utf-8"))
        index_lines.append(f"- {doc['title']}: {doc.get('pdf') or ''}")
    write_md("index.md", "\n".join(index_lines))

    return documents
