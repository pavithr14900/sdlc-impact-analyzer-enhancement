import threading
from concurrent.futures import ThreadPoolExecutor
from typing import Dict

from sdlc.agents import (
    code_generation_agent,
    test_strategy_agent,
    infrastructure_agent,
    security_considerations_agent,
    developer_checklist_agent,
    documentation_agent,
)
from sdlc.agents.assembler_agent import assembler_agent
from sdlc.state import SdlcState, traced

# Shared executor and status tracking for background generations
_executor = ThreadPoolExecutor(max_workers=6)
_lock = threading.Lock()
# status map: agent_key -> { status: 'pending'|'generating'|'ready'|'failed', error: str|None }
_statuses: Dict[str, Dict] = {}
_global_state: SdlcState | None = None


def _run_agent(name: str, agent_func, output_key: str, state: SdlcState):
    with _lock:
        _statuses[name] = {"status": "generating", "error": None}

    try:
        result = agent_func(state)

        # Merge outputs into shared global state
        with _lock:
            global _global_state
            if _global_state is None:
                _global_state = state

            if output_key in result and result[output_key]:
                _global_state[output_key] = result[output_key]

            # Append trace info if provided
            if "trace" in result:
                _global_state.setdefault("trace", []).extend(result["trace"])

            _statuses[name]["status"] = "ready"

        # Update the assembled document so the UI can preview partial results
        try:
            assembler_agent(state)
        except Exception:
            # Assembler is best-effort here; do not propagate
            pass

    except Exception as exc:
        with _lock:
            _statuses[name]["status"] = "failed"
            _statuses[name]["error"] = str(exc)


def get_state():
    with _lock:
        return dict(_global_state) if _global_state is not None else None


def start_parallel_generations(state: SdlcState):
    """Start background generations for multiple agents. Returns immediately.

    The agents run in separate threads and update `state` in-place when they
    complete. Statuses may be queried with `get_statuses()`.
    """

    jobs = [
        ("generate_code", code_generation_agent, "generated_code"),
        ("test_strategy", test_strategy_agent, "test_strategy"),
        ("infrastructure", infrastructure_agent, "infrastructure"),
        ("security", security_considerations_agent, "security_considerations"),
        ("checklist", developer_checklist_agent, "developer_checklist"),
        ("documentation", documentation_agent, "documentation"),
    ]

    global _global_state
    with _lock:
        _global_state = state
        for name, _, _ in jobs:
            _statuses[name] = {"status": "pending", "error": None}

    for name, func, key in jobs:
        _executor.submit(_run_agent, name, func, key, state)


def get_statuses():
    with _lock:
        return {k: dict(v) for k, v in _statuses.items()}
