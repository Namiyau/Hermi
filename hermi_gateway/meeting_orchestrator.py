from __future__ import annotations

import re


def discussion_control(content: str) -> tuple[str, str]:
    text = str(content or "").strip()
    match = re.search(r"(?:^|\n)\s*NEXT\s*:\s*([A-Za-z0-9_-]+)\s*$", text, re.IGNORECASE)
    if not match:
        return text, ""
    visible = text[: match.start()].strip()
    return visible or "（本轮无补充）", match.group(1).strip().lower()
