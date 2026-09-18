from __future__ import annotations

MEETING_ROLE_PRESETS: list[dict[str, str]] = [
    {"role": "总理", "label": "总理", "description": "暂定主持人/调度者，可后续改名。"},
    {"role": "host", "label": "主持人", "description": "主持会议、分配发言、总结行动项。"},
    {"role": "participant", "label": "成员", "description": "普通发言成员。"},
    {"role": "reviewer", "label": "挑错者", "description": "负责审查、挑错、提出反例。"},
    {"role": "executor", "label": "执行者", "description": "工程流水线中负责执行步骤。"},
]

MEETING_MODE_PRESETS: list[dict[str, str]] = [
    {"mode": "auto_single", "label": "自动单次模式", "description": "主持人根据问题自动挑选合适成员单次回答。", "rule_version": "1", "orchestration": "host_select"},
    {"mode": "pair_review", "label": "双人挑错模式", "description": "选中两个 AI 自然讨论、挑错和修正。", "rule_version": "2", "orchestration": "bounded_pair"},
    {"mode": "project_meeting", "label": "项目会议模式", "description": "成员自由讨论，最后形成纪要和行动项。", "rule_version": "2", "orchestration": "directed_free"},
    {"mode": "engineering_pipeline", "label": "工程流水线模式", "description": "按需求、设计、计划、执行、测试、审查推进，阶段内允许动态协作。", "rule_version": "2", "orchestration": "staged_dynamic"},
]
MEETING_MODE_IDS = {item["mode"] for item in MEETING_MODE_PRESETS}
MEETING_MODE_ALIASES = {
    "single": "auto_single", "auto": "auto_single", "自动单次模式": "auto_single",
    "双人挑错模式": "pair_review", "项目会议模式": "project_meeting", "工程流水线模式": "engineering_pipeline",
}
HOST_ROLES = {"总理", "host", "主持人", "premier", "moderator"}


def normalize_meeting_mode(mode: str) -> str:
    value = str(mode or "").strip()
    return MEETING_MODE_ALIASES.get(value, value if value in MEETING_MODE_IDS else "project_meeting")


def meeting_mode_label(mode: str) -> str:
    return next((item["label"] for item in MEETING_MODE_PRESETS if item["mode"] == mode), mode)
