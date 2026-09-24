"""Bounded source discovery. All heuristics retain code locations and explicit limits."""
from __future__ import annotations

import ast
from pathlib import Path
import re
from urllib.parse import urlsplit

from .models import Evidence

EXCLUDED = {".git", ".venv", "venv", "node_modules", "dist", "build", "target", "generated", "vendor", "__pycache__", ".idea", ".codex", ".agents"}
SUFFIXES = {".py", ".java", ".ts", ".tsx", ".js", ".jsx", ".cs", ".go", ".rb", ".php", ".sql"}
CLASS = re.compile(r"\b(?:class|interface|struct)\s+(\w+)")
API = re.compile(r'''(?:@(?:\w+\.)?(?:route|get|post|put|patch|delete|GetMapping|PostMapping|PutMapping|DeleteMapping|RequestMapping)|\b(?:app|router)\.(?:get|post|put|delete|patch)|\[(?:HttpGet|HttpPost|HttpPut|HttpDelete|Route))\s*\(\s*(?:value\s*=\s*)?["']([^"']+)["']''', re.I)
TABLE = re.compile(r'''(?:\bCREATE\s+TABLE\s+(?:IF\s+NOT\s+EXISTS\s+)?["`\[]?([\w.]+)|@Table\s*\(\s*name\s*=\s*["']([^"']+)|\b__tablename__\s*=\s*["']([^"']+))''', re.I)
SCHEDULE = re.compile(r"@(?:Scheduled|scheduler\.(?:task|scheduled_job)|\w+\.scheduled_job)|\b(?:add_job|scheduleJob|RecurringJob\.AddOrUpdate|cron\.schedule)\s*\(", re.I)
URL = re.compile(r'''https?://[^\s"'<>`]+''')


def discover(repositories: list[dict]) -> dict:
    facts, evidence, rules, limitations = [], [], [], []
    files_read = 0
    seen = set()

    def record(repository, file, lines, line_number, symbol, kind="CODE"):
        start, end = max(1, line_number - 2), min(len(lines), line_number + 3)
        item = Evidence(f"E{len(evidence) + 1}", repository, file, symbol, start, end, kind, "\n".join(lines[start - 1:end])).to_dict()
        evidence.append(item)
        return item

    def fact(kind, name, repository, file, lines, line_number, symbol="", description="", evidence_type="CODE"):
        key = (kind, repository, file, name, line_number)
        if key in seen:
            return
        seen.add(key)
        item = record(repository, file, lines, line_number, symbol or name, evidence_type)
        facts.append({"kind": kind, "name": name, "repository": repository, "description": description, "evidence": [item]})

    for repository in repositories:
        root = Path(repository["resolvedPath"]).resolve()
        repo_name = repository["name"]
        eligible, scanned = 0, 0
        # os.walk prunes dependencies before traversing them; symlinked source is excluded.
        import os
        for directory, subdirs, filenames in os.walk(root, followlinks=False):
            subdirs[:] = sorted(name for name in subdirs if name not in EXCLUDED and not name.startswith(".") and not (Path(directory) / name).is_symlink())
            for filename in sorted(filenames):
                path = Path(directory) / filename
                if path.suffix.lower() not in SUFFIXES or path.is_symlink():
                    continue
                eligible += 1
                if scanned >= 1500:
                    continue
                try:
                    if path.stat().st_size > 300_000:
                        limitations.append(f"{repo_name}/{path.relative_to(root).as_posix()}: source file exceeds the 300 KB excerpt scan limit.")
                        continue
                    text = path.read_text(encoding="utf-8", errors="replace")
                except OSError:
                    limitations.append(f"{repo_name}/{path.relative_to(root).as_posix()}: source could not be read.")
                    continue
                scanned += 1
                files_read += 1
                file = path.relative_to(root).as_posix()
                lines = text.splitlines()
                is_test = any(part.lower() in {"test", "tests", "__tests__"} for part in path.parts) or filename.startswith("test_") or ".test." in filename or ".spec." in filename
                if is_test:
                    continue
                current_symbol = path.stem
                if path.suffix == ".py":
                    try:
                        tree = ast.parse(text)
                        for node in ast.walk(tree):
                            if isinstance(node, ast.ClassDef):
                                fact("class", node.name, repo_name, file, lines, node.lineno)
                                if node.name.endswith(("Service", "Controller", "Repository", "Handler")):
                                    fact("service", node.name, repo_name, file, lines, node.lineno, description="Named source component; deployability has not been verified.")
                            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                                for condition in ast.walk(node):
                                    if isinstance(condition, ast.If) and isinstance(condition.test, ast.Compare) and len(rules) < 60:
                                        condition_text = ast.get_source_segment(text, condition.test) or "comparison"
                                        ev = record(repo_name, file, lines, condition.lineno, node.name)
                                        rules.append({"id": f"BR-{len(rules) + 1:03}", "title": f"Condition in {node.name}", "description": f"Candidate code condition: {condition_text}. Its business meaning requires review.", "confidence": "LOW", "evidence": [ev]})
                    except SyntaxError:
                        limitations.append(f"{repo_name}/{file}: Python source could not be parsed; only line-based discovery was available.")
                for line_number, line in enumerate(lines, 1):
                    if line.lstrip().startswith(("//", "#", "*", "--")):
                        continue
                    if path.suffix != ".py":
                        match = CLASS.search(line)
                        if match:
                            current_symbol = match.group(1)
                            fact("class", current_symbol, repo_name, file, lines, line_number)
                            if current_symbol.endswith(("Service", "Controller", "Repository", "Handler")):
                                fact("service", current_symbol, repo_name, file, lines, line_number, description="Named source component; deployability has not been verified.")
                    api = API.search(line)
                    if api:
                        fact("api", api.group(1), repo_name, file, lines, line_number, current_symbol, "Route declaration found in source; mounted prefixes and dynamic routes may require review.", "API")
                    table = TABLE.search(line)
                    if table:
                        name = next(group for group in table.groups() if group)
                        fact("databaseTable", name, repo_name, file, lines, line_number, current_symbol, evidence_type="DATABASE")
                    if SCHEDULE.search(line):
                        fact("scheduledJob", f"{current_symbol}:{line_number}", repo_name, file, lines, line_number, current_symbol, "Scheduling declaration; runtime activation has not been verified.")
                    for match in URL.finditer(line):
                        parsed = urlsplit(match.group())
                        if parsed.hostname and parsed.hostname not in {"localhost", "127.0.0.1", "example.com"}:
                            fact("externalIntegration", parsed.hostname, repo_name, file, lines, line_number, current_symbol, "URL reference found in source; an active integration is not verified.")
                    if path.suffix != ".py" and len(rules) < 60 and re.search(r"\bif\s*\([^)]*(?:>=|<=|==|!=|>|<)[^)]*\)", line):
                        condition = re.search(r"\bif\s*\(([^)]*)\)", line)
                        ev = record(repo_name, file, lines, line_number, current_symbol)
                        rules.append({"id": f"BR-{len(rules) + 1:03}", "title": f"Condition in {current_symbol}", "description": f"Candidate code condition: {condition.group(1)}. Its business meaning requires review.", "confidence": "LOW", "evidence": [ev]})
        if eligible > scanned:
            limitations.append(f"{repo_name}: source excerpt scan read {scanned} of {eligible} eligible files; metrics are bounded discoveries.")
    limitations.append("Source metrics describe discovered declarations in supported Python, Java, JavaScript/TypeScript, C#, Go, Ruby, PHP and SQL files, excluding tests, dependencies, generated files and files over 300 KB. Pattern matching can miss dynamic or multiline constructs and is not a complete inventory.")
    limitations.append("Services are named code components; external integrations are URL references. Business rules are candidate conditions requiring human review. These categories are not deployment or business validation.")
    return {"facts": facts, "evidence": evidence, "businessRules": rules, "limitations": limitations, "filesRead": files_read}
