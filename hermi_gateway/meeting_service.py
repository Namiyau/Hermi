from __future__ import annotations

from typing import Any

ACTIVE_RUN_STATUSES = {"running", "paused"}


def can_delete_room(runs: list[dict[str, Any]]) -> bool:
    return not any(str(run.get("status") or "") in ACTIVE_RUN_STATUSES for run in runs)


def next_run_status(current: str, action: str) -> str:
    transitions = {
        ("running", "stop"): "paused",
        ("paused", "resume"): "running",
        ("running", "cancel"): "cancelled",
        ("paused", "cancel"): "cancelled",
    }
    return transitions.get((str(current), str(action)), str(current))
