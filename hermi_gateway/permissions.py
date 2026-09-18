"""
Hermi 权限模块 (Phase 1 基础设施)

职责：
- 定义所有权限项的 key、类型、默认值
- PermissionChecker：根据用户 JSON 权限配置检查操作是否允许
- 迁移函数：将旧版 quota_policy 字符串转为新版 JSON 格式
- 此阶段只建模块，不改现有业务逻辑
"""

from __future__ import annotations

import json
import os
import time
from typing import Any

# ── 环境熔断开关 ──────────────────────────────────────────
PERMISSIONS_ENABLED = os.environ.get("HERMI_PERMISSIONS_ENABLED", "1").lower() in (
    "1",
    "true",
    "yes",
    "on",
)


# ── 权限定义 ──────────────────────────────────────────────
# type: tristate = allow/deny/approval
#       owner_only = 仅 owner 可用
#       composite = 复合值 (dict)
#       number = 数值

PERMISSION_DEFS: dict[str, dict[str, Any]] = {
    "chat": {
        "type": "tristate",
        "default": "allow",
        "label": "对话权限",
        "desc": "能否发送消息对话",
    },
    "external_tools": {
        "type": "tristate",
        "default": "approval",
        "label": "外部工具",
        "desc": "只读联网检索与在线研究技能；不包含本机、QQ 或定时任务",
    },
    "cron": {
        "type": "tristate",
        "default": "deny",
        "label": "创建定时任务",
        "desc": "能否创建 cron / reminder",
    },
    "approve": {
        "type": "owner_only",
        "default": "owner_only",
        "label": "审批权限",
        "desc": "审批他人操作",
    },
    "remote_control": {
        "type": "owner_only",
        "default": "owner_only",
        "label": "远程控制",
        "desc": "操控系统功能",
    },
    "view_all_conversations": {
        "type": "owner_only",
        "default": "owner_only",
        "label": "查看所有会话",
        "desc": "看到所有用户的对话",
    },
    "admin_users": {
        "type": "owner_only",
        "default": "owner_only",
        "label": "管理用户",
        "desc": "增删改账号",
    },
    "manage_scheduled": {
        "type": "tristate",
        "default": "allow",
        "label": "管理定时任务",
        "desc": "编辑/删除定时任务",
    },
    "prompt_cards": {
        "type": "composite",
        "default": {"mode": "allow", "max_count": 5},
        "label": "管理提示卡片",
        "desc": "prompt card 可用数量和模式",
    },
    "media": {
        "type": "composite",
        "default": {"mode": "allow", "max_size_mb": 5, "daily_vision_count": 5},
        "label": "媒体文件管理",
        "desc": "上传文件大小和识图次数",
    },
    "admin_config": {
        "type": "owner_only",
        "default": "owner_only",
        "label": "系统配置",
        "desc": "改系统设置",
    },
    "view_stats": {
        "type": "tristate",
        "default": "allow",
        "label": "查看统计",
        "desc": "查看用量数据",
    },
    "high_risk": {
        "type": "owner_only",
        "default": "owner_only",
        "label": "高风险操作",
        "desc": "rm -rf / 格式化 / 改系统等",
    },
    "medium_risk": {
        "type": "composite",
        "default": {"mode": "allow", "daily_count": 5},
        "label": "中风险操作",
        "desc": "写脚本 / 跑代码等",
    },
    "quota_token_limit": {
        "type": "number",
        "default": 50_000,
        "label": "额度 Token 上限",
        "desc": "每个额度时间窗口可使用的总 Token；-1 表示不限",
    },
    "file_size_limit_mb": {
        "type": "number",
        "default": 5,
        "label": "文件大小上限(MB)",
        "desc": "单个上传文件大小",
    },
    "quota_window_minutes": {
        "type": "number",
        "default": 1440,
        "label": "额度时间窗口(分钟)",
        "desc": "默认 1440 = 24 小时",
    },
}

# ── 角色默认权限 ──────────────────────────────────────────

ROLE_DEFAULTS: dict[str, dict[str, Any]] = {
    "owner": {
        "chat": "allow",
        "external_tools": "allow",
        "cron": "allow",
        "approve": "owner_only",
        "remote_control": "owner_only",
        "view_all_conversations": "owner_only",
        "admin_users": "owner_only",
        "manage_scheduled": "allow",
        "prompt_cards": {"mode": "allow", "max_count": -1},
        "media": {"mode": "allow", "max_size_mb": 0, "daily_vision_count": -1},
        "admin_config": "owner_only",
        "view_stats": "allow",
        "high_risk": "owner_only",
        "medium_risk": {"mode": "allow", "daily_count": -1},
        "quota_token_limit": -1,
        "file_size_limit_mb": 0,
        "quota_window_minutes": 1440,
    },
    "channel": {
        "chat": "allow",
        "external_tools": "allow",
        "cron": "allow",
        "approve": "owner_only",
        "remote_control": "owner_only",
        "view_all_conversations": "owner_only",
        "admin_users": "owner_only",
        "manage_scheduled": "allow",
        "prompt_cards": {"mode": "allow", "max_count": -1},
        "media": {"mode": "allow", "max_size_mb": 0, "daily_vision_count": -1},
        "admin_config": "owner_only",
        "view_stats": "allow",
        "high_risk": "owner_only",
        "medium_risk": {"mode": "allow", "daily_count": -1},
        "quota_token_limit": -1,
        "file_size_limit_mb": 0,
        "quota_window_minutes": 1440,
    },
    "friend": {
        "chat": "allow",
        "external_tools": "approval",
        "cron": "deny",
        "approve": "owner_only",
        "remote_control": "owner_only",
        "view_all_conversations": "owner_only",
        "admin_users": "owner_only",
        "manage_scheduled": "allow",
        "prompt_cards": {"mode": "allow", "max_count": 5},
        "media": {"mode": "allow", "max_size_mb": 5, "daily_vision_count": 5},
        "admin_config": "owner_only",
        "view_stats": "allow",
        "high_risk": "owner_only",
        "medium_risk": {"mode": "allow", "daily_count": 5},
        "quota_token_limit": 50_000,
        "file_size_limit_mb": 5,
        "quota_window_minutes": 1440,
    },
    "guest": {
        "chat": "allow",
        "external_tools": "approval",
        "cron": "deny",
        "approve": "owner_only",
        "remote_control": "owner_only",
        "view_all_conversations": "owner_only",
        "admin_users": "owner_only",
        "manage_scheduled": "deny",
        "prompt_cards": {"mode": "deny"},
        "media": {"mode": "deny"},
        "admin_config": "owner_only",
        "view_stats": "allow",
        "high_risk": "owner_only",
        "medium_risk": {"mode": "deny"},
        "quota_token_limit": 25_000,
        "file_size_limit_mb": 2,
        "quota_window_minutes": 1440,
    },
}


# ── 迁移函数 ──────────────────────────────────────────────


def migrate_quota_to_permissions(quota_policy: str) -> dict[str, Any]:
    """将旧版 quota_policy 字符串转为新版 permissions JSON dict."""
    policy = str(quota_policy or "").strip().lower()
    defaults: dict[str, Any] = {}

    if policy == "owner":
        defaults.update(ROLE_DEFAULTS.get("owner", {}))
    elif policy == "channel":
        defaults.update(ROLE_DEFAULTS.get("channel", {}))
    elif policy == "friend_trusted":
        defaults.update(ROLE_DEFAULTS.get("friend", {}))
        defaults["quota_token_limit"] = 250_000
        defaults["file_size_limit_mb"] = 25
        defaults["media"] = {"mode": "allow", "max_size_mb": 25, "daily_vision_count": 10}
        defaults["medium_risk"] = {"mode": "allow", "daily_count": 10}
    elif policy == "friend_free":
        defaults.update(ROLE_DEFAULTS.get("friend", {}))
    elif policy == "guest":
        defaults.update(ROLE_DEFAULTS.get("guest", {}))
    else:
        # fallback: treat as friend_free
        defaults.update(ROLE_DEFAULTS.get("friend", {}))

    return defaults


def _upgrade_legacy_quota_permissions(permissions: dict[str, Any]) -> dict[str, Any]:
    upgraded = dict(permissions)
    legacy_limit = upgraded.pop("daily_text_limit", None)
    if "quota_token_limit" not in upgraded and isinstance(legacy_limit, (int, float)):
        upgraded["quota_token_limit"] = -1 if legacy_limit < 0 else int(legacy_limit) * 2_500
    return upgraded


def get_default_permissions(role: str) -> dict[str, Any]:
    """获取指定角色的默认权限."""
    return dict(ROLE_DEFAULTS.get(role, ROLE_DEFAULTS["friend"]))


def grant_existing_users_external_tool_access(conn: Any) -> int:
    """兼容旧账号：缺少新权限时保留此前可用的联网研究能力。"""
    changed = 0
    rows = conn.execute("select user_id, permissions from users").fetchall()
    for row in rows:
        raw = row["permissions"]
        if not raw:
            permissions: dict[str, Any] = {}
        elif isinstance(raw, str):
            try:
                parsed = json.loads(raw)
            except json.JSONDecodeError:
                parsed = {}
            permissions = parsed if isinstance(parsed, dict) else {}
        elif isinstance(raw, dict):
            permissions = dict(raw)
        else:
            permissions = {}
        if "external_tools" in permissions:
            continue
        permissions["external_tools"] = "allow"
        conn.execute(
            "update users set permissions = ? where user_id = ?",
            (json.dumps(permissions, ensure_ascii=False), row["user_id"]),
        )
        changed += 1
    if changed:
        conn.commit()
    return changed


# ── PermissionChecker ─────────────────────────────────────


class PermissionChecker:
    """权限检查器。

    用法：
        checker = PermissionChecker(user)
        result = checker.check("cron")
        # 返回 "allow" / "deny" / "approval"
        limit = checker.get_number("quota_token_limit")
    """

    def __init__(self, user: dict[str, Any]) -> None:
        self.user = user
        self.role = str(user.get("role") or "friend")
        self._perms: dict[str, Any] = {}
        self._parse()

    def _parse(self) -> None:
        """解析用户权限配置：优先用 permissions JSON，没有则从 quota_policy 迁移。"""
        raw = self.user.get("permissions")
        if raw and PERMISSIONS_ENABLED:
            if isinstance(raw, str):
                try:
                    parsed = json.loads(raw)
                except (json.JSONDecodeError, TypeError):
                    parsed = None
                if isinstance(parsed, dict):
                    self._perms = _upgrade_legacy_quota_permissions(parsed)
                    return
            elif isinstance(raw, dict):
                self._perms = _upgrade_legacy_quota_permissions(raw)
                return
        # fallback：从旧版 quota_policy 迁移
        quota = str(self.user.get("quota_policy") or "friend_free")
        self._perms = _upgrade_legacy_quota_permissions(migrate_quota_to_permissions(quota))

    def check(self, perm_name: str) -> str:
        """检查权限，返回 'allow' / 'deny' / 'approval'。"""
        if not PERMISSIONS_ENABLED:
            return "allow"

        value = self._perms.get(perm_name)
        if value is None:
            # 没有配置则用角色默认
            role_defaults = ROLE_DEFAULTS.get(self.role, ROLE_DEFAULTS["friend"])
            value = role_defaults.get(perm_name)
            if value is None:
                # 连角色默认都没有则看全局定义
                definition = PERMISSION_DEFS.get(perm_name)
                if definition:
                    value = definition["default"]
                else:
                    return "deny"

        if isinstance(value, str):
            return value  # "allow" / "deny" / "approval" / "owner_only"

        if isinstance(value, dict):
            mode = str(value.get("mode") or "allow")
            if mode == "deny":
                return "deny"
            return mode  # "allow" / "approval"

        return "allow"

    def get_number(self, perm_name: str) -> int:
        """获取数值型权限的值（如每日消息上限）。"""
        value = self._perms.get(perm_name)
        if value is None:
            role_defaults = ROLE_DEFAULTS.get(self.role, ROLE_DEFAULTS["friend"])
            value = role_defaults.get(perm_name)
            if value is None:
                definition = PERMISSION_DEFS.get(perm_name)
                if definition:
                    value = definition["default"]
                else:
                    return 0

        if isinstance(value, (int, float)):
            return int(value)

        if isinstance(value, dict):
            for key in ("max_count", "max_size_mb", "daily_count", "daily_vision_count"):
                if key in value:
                    v = value[key]
                    if isinstance(v, (int, float)):
                        return int(v)

        return 0

    def get_composite(self, perm_name: str) -> dict[str, Any]:
        """获取复合型权限的完整配置 dict。"""
        value = self._perms.get(perm_name)
        if isinstance(value, dict):
            return dict(value)
        return {}

    @property
    def is_owner(self) -> bool:
        """快捷判断是否为 owner。"""
        return self.role == "owner" or self.user.get("can_approve", False)

    def to_dict(self) -> dict[str, Any]:
        """返回完整的权限配置 dict（用于前端展示）。"""
        return dict(self._perms)
