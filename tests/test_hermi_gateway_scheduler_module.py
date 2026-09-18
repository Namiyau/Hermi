import time

from hermi_gateway import scheduler


def test_scheduler_module_owns_due_and_delivery_policy():
    now = time.time()
    job = {
        "kind": "interval",
        "schedule": "interval:5m",
        "created_at": now - 301,
        "last_run_at": 0,
    }

    assert scheduler.scheduled_job_due(job, now) is True
    assert scheduler.delivery_list({"delivery": ["hermi", "qq"]}) == ["hermi", "qq"]
    assert scheduler.apply_job_delivery_policy(["hermi", "qq"], {"allowed_delivery": ["hermi"]}) == ["hermi"]
    assert scheduler.retry_backoff_seconds({"retry_mode": "exponential", "retry_backoff_seconds": 30}, 3) == 120


def test_scheduler_module_builds_execution_messages():
    messages = scheduler.scheduled_job_messages(
        {"job_id": "job-1", "summary": "汇报", "schedule": "once:+5m"},
        {"delivery": ["hermi"]},
        {"content": "检查项目"},
    )

    assert messages[0]["role"] == "system"
    assert "job_id=job-1" in messages[1]["content"]
    assert "检查项目" in messages[1]["content"]
