from __future__ import annotations


def compact_meeting_context(previous: list[str], max_chars: int = 6000) -> str:
    if not previous:
        return "（尚无前序发言）"
    recent = previous[-6:]
    joined = "\n\n".join(recent)
    if len(joined) <= max_chars:
        return joined
    kept: list[str] = []
    remaining = max_chars - len("[会议上下文已压缩]\n")
    for item in reversed(recent):
        if remaining <= 0:
            break
        chunk = str(item)[-remaining:]
        kept.append(chunk)
        remaining -= len(chunk) + 2
    return "[会议上下文已压缩]\n" + "\n\n".join(reversed(kept))
