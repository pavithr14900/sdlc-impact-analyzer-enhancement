"""Local codebase-memory-mcp connection using the official MCP stdio client."""
from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from datetime import timedelta
import json
import os
from pathlib import Path
import shutil
import sys

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


class McpError(RuntimeError):
    pass


def server_command() -> str:
    """Resolve a native binary, including Windows npm installs, without a shell."""
    configured = os.getenv("CODEBASE_MEMORY_COMMAND", "").strip().strip('"')
    command = configured or shutil.which("codebase-memory-mcp")
    candidates = []
    if command:
        path = Path(command)
        if path.suffix.lower() in {".cmd", ".ps1"}:
            candidates.append(path.parent / "node_modules/codebase-memory-mcp/bin/codebase-memory-mcp.exe")
        else:
            candidates.append(Path(shutil.which(command) or command))
    if not configured:
        candidates.extend([
            Path(sys.executable).parent / "codebase-memory-mcp.exe",
            Path.home() / ".local/bin/codebase-memory-mcp.exe",
            Path.home() / ".local/bin/codebase-memory-mcp",
        ])
        if os.getenv("APPDATA"):
            candidates.append(Path(os.environ["APPDATA"]) / "npm/node_modules/codebase-memory-mcp/bin/codebase-memory-mcp.exe")
    for candidate in candidates:
        if candidate.is_file():
            return str(candidate.resolve())
    raise McpError(
        "codebase-memory-mcp executable not found. Install it with npm install -g "
        "codebase-memory-mcp, or set CODEBASE_MEMORY_COMMAND to its executable path "
        "in the backend .env and restart the backend."
    )


def error_message(exc: BaseException) -> str:
    if isinstance(exc, BaseExceptionGroup):
        return "; ".join(dict.fromkeys(error_message(child) for child in exc.exceptions))
    return str(exc) or type(exc).__name__


def decode_result(result):
    text = "\n".join(block.text for block in result.content if block.type == "text")
    if result.isError:
        raise McpError(text or "MCP tool returned an error")
    if result.structuredContent is not None:
        data = result.structuredContent
    else:
        try:
            data = json.loads(text)
        except (ValueError, TypeError):
            return {"text": text}
    if isinstance(data, dict) and data.get("error"):
        raise McpError(str(data["error"]))
    return data


class MemorySession:
    def __init__(self, session: ClientSession, schemas: dict):
        self.session = session
        self.schemas = schemas

    def supports(self, tool: str, parameter: str | None = None) -> bool:
        return tool in self.schemas and (
            parameter is None or parameter in self.schemas[tool].get("properties", {})
        )

    async def call(self, tool: str, **arguments):
        if not self.supports(tool):
            raise McpError(f"Installed codebase-memory-mcp does not expose {tool}. Update the server.")
        timeout = float(os.getenv("CODEBASE_MEMORY_INDEX_TIMEOUT" if tool == "index_repository" else "CODEBASE_MEMORY_TIMEOUT", "600" if tool == "index_repository" else "60"))
        try:
            result = await self.session.call_tool(tool, arguments, read_timeout_seconds=timedelta(seconds=timeout))
            return decode_result(result)
        except Exception as exc:
            raise McpError(f"{tool}: {error_message(exc)}") from exc


@asynccontextmanager
async def connect(repo_path: str):
    parameters = StdioServerParameters(command=server_command(), cwd=repo_path, env=dict(os.environ))
    try:
        async with stdio_client(parameters) as (read, write):
            async with ClientSession(read, write) as session:
                await asyncio.wait_for(session.initialize(), timeout=60)
                schemas = {}
                cursor = None
                while True:
                    page = await asyncio.wait_for(session.list_tools(cursor=cursor), timeout=60)
                    schemas.update({tool.name: tool.inputSchema for tool in page.tools})
                    cursor = page.nextCursor
                    if not cursor:
                        break
                yield MemorySession(session, schemas)
    except Exception as exc:
        raise McpError(f"Codebase memory MCP connection failed: {error_message(exc)}") from exc


def discover() -> dict:
    """Check whether a local codebase-memory-mcp executable is available and return basic info.

    The UI uses this to show MCP availability. This is intentionally lightweight
    (does not start the server) to avoid blocking on environments where a
    desktop/server process is unavailable.
    """
    try:
        cmd = server_command()
        return {"available": True, "command": cmd}
    except McpError as exc:
        return {"available": False, "error": str(exc)}
