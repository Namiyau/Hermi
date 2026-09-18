from __future__ import annotations


def trace_event(event: str, content: str) -> dict[str, str]:
    return {"event": str(event or "thought"), "content": str(content or "")}
