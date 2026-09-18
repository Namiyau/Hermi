from __future__ import annotations

import json
import re
import time
from typing import Any


def scheduled_job_due(job: dict[str, Any], now: float) -> bool:
    next_run_after = float(job.get("next_run_after") or 0)
    if next_run_after:
        return now >= next_run_after
    kind = str(job.get("kind") or "")
    schedule = str(job.get("schedule") or "").strip()
    created_at = float(job.get("created_at") or now)
    last_run_at = float(job.get("last_run_at") or 0)
    baseline = last_run_at or created_at
    if kind == "interval":
        return baseline + duration_seconds(schedule.removeprefix("interval:")) <= now
    if kind == "cron":
        return cron_due(schedule, baseline, now)
    if kind != "once":
        return False
    if schedule.startswith("once:+"):
        return created_at + duration_seconds(schedule[6:]) <= now
    if schedule.startswith("once:"):
        schedule = schedule[5:]
    try:
        return time.mktime(time.strptime(schedule[:19], "%Y-%m-%dT%H:%M:%S")) <= now
    except ValueError:
        return False


def simple_cron_interval_seconds(schedule: str) -> int:
    match = re.fullmatch(r"\*/(\d+) \* \* \* \*", schedule.strip())
    return int(match.group(1)) * 60 if match else 0


def cron_due(schedule: str, baseline: float, now: float) -> bool:
    fields = schedule.strip().split()
    if len(fields) != 5 or now <= baseline:
        return False
    try:
        parsed = [
            cron_field_values(fields[0], 0, 59),
            cron_field_values(fields[1], 0, 23),
            cron_field_values(fields[2], 1, 31),
            cron_field_values(fields[3], 1, 12),
            cron_field_values(fields[4], 0, 7),
        ]
    except ValueError:
        return False
    start_minute = int(baseline // 60) * 60 + 60
    end_minute = int(now // 60) * 60
    if start_minute > end_minute:
        return False
    max_minutes = 366 * 24 * 60
    if (end_minute - start_minute) // 60 > max_minutes:
        start_minute = end_minute - max_minutes * 60
    for timestamp in range(start_minute, end_minute + 1, 60):
        local = time.localtime(timestamp)
        cron_dow = (local.tm_wday + 1) % 7
        dow_values = parsed[4]
        if 7 in dow_values:
            dow_values = set(dow_values)
            dow_values.add(0)
        if (
            local.tm_min in parsed[0]
            and local.tm_hour in parsed[1]
            and local.tm_mday in parsed[2]
            and local.tm_mon in parsed[3]
            and cron_dow in dow_values
        ):
            return True
    return False


def cron_field_values(field: str, minimum: int, maximum: int) -> set[int]:
    values: set[int] = set()
    for part in field.split(","):
        part = part.strip()
        if not part:
            raise ValueError("empty cron field")
        step = 1
        if "/" in part:
            part, step_text = part.split("/", 1)
            step = int(step_text)
            if step <= 0:
                raise ValueError("invalid cron step")
        if part == "*":
            start, end = minimum, maximum
        elif "-" in part:
            start_text, end_text = part.split("-", 1)
            start, end = int(start_text), int(end_text)
        else:
            start = end = int(part)
        if start < minimum or end > maximum or start > end:
            raise ValueError("cron value out of range")
        values.update(range(start, end + 1, step))
    return values


def delivery_list(target: dict[str, Any]) -> list[str]:
    delivery = target.get("delivery") or ["hermi"]
    if isinstance(delivery, str):
        delivery = [delivery]
    if not isinstance(delivery, list):
        return ["hermi"]
    normalized = []
    for item in delivery:
        value = str(item).strip().lower()
        if value in {"hermi", "qq"} and value not in normalized:
            normalized.append(value)
    return normalized or ["hermi"]


def apply_job_delivery_policy(delivery: list[str], policy: dict[str, Any]) -> list[str]:
    allowed = policy.get("allowed_delivery")
    if not isinstance(allowed, list) or not allowed:
        return delivery
    allowed_set = {str(item).strip().lower() for item in allowed}
    filtered = [item for item in delivery if item in allowed_set]
    if "qq" in delivery and "qq" not in allowed_set and policy.get("notify_policy_block", True):
        return [item for item in filtered if item != "qq"] or ["hermi"]
    return filtered or ["hermi"]


def retry_backoff_seconds(policy: dict[str, Any], retry_count: int) -> int:
    retry = policy.get("retry") if isinstance(policy.get("retry"), dict) else {}
    base = int(retry.get("backoff_seconds") or policy.get("retry_backoff_seconds") or 60)
    mode = str(retry.get("mode") or policy.get("retry_mode") or "linear")
    if mode == "exponential":
        return min(base * (2 ** max(0, retry_count - 1)), 3600)
    return min(base * max(1, retry_count), 3600)


def scheduled_job_messages(
    job: dict[str, Any],
    target: dict[str, Any],
    payload: dict[str, Any],
) -> list[dict[str, str]]:
    content = str(payload.get("content") or payload.get("prompt") or job.get("summary") or "").strip()
    return [
        {
            "role": "system",
            "content": (
                "You are continuing a Hermi conversation because its scheduled time has arrived. "
                "Reply in the selected profile's natural personality and conversational style. "
                "For a reminder, be concise, warm, and useful; do not write a mechanical operational report. "
                "Perform only the requested work that is safe to complete now. "
                "Hermi owns delivery to Hermi/QQ according to the configured target. "
                "If you need any additional dangerous action beyond the configured delivery, return a HERMI_ACTION block for approval."
            ),
        },
        {
            "role": "user",
            "content": (
                "[Hermi scheduled job]\n"
                + f"job_id={job.get('job_id')}\n"
                + f"summary={job.get('summary')}\n"
                + f"schedule={job.get('schedule')}\n"
                + f"target={json.dumps(target, ensure_ascii=False)}\n"
                + f"payload={json.dumps(payload, ensure_ascii=False)}\n\n"
                + "[job_content]\n"
                + content
            ),
        },
    ]


def duration_seconds(value: str) -> int:
    match = re.fullmatch(r"(\d+)([smhd])", value.strip())
    if not match:
        return 0
    amount = int(match.group(1))
    return amount * {"s": 1, "m": 60, "h": 3600, "d": 86400}[match.group(2)]
