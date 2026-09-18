from __future__ import annotations


def meeting_permission_prompt(level: str) -> str:
    if level == "full":
        return "完整权限：仅可在 Operation Zone 和工具白名单内操作；删除、凭据、系统控制等高风险动作仍必须审批。"
    if level == "smart":
        return "智能权限：低风险只读工具可直接使用；写入、命令、外部发送必须审批；高风险动作禁止或仅 Owner 可做。"
    return "一般权限：只能分析、讨论、总结和提出行动建议；禁止调用文件、命令、网络写入或外部发送工具。"
