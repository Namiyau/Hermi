from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


class ConversationCreate(BaseModel):
    title: str = "New conversation"
    channel: str = "hermi-native"
    profile_id: str = ""


class ConversationPatch(BaseModel):
    title: str = Field(min_length=1, max_length=120)


class SelfDisplayNamePatch(BaseModel):
    display_name: str = Field(min_length=1, max_length=40)


class UserLocalePatch(BaseModel):
    locale: Literal["auto", "zh-CN", "ja-JP", "en-US"] = "auto"


class MessageCreate(BaseModel):
    content: str
    attachments: list[dict[str, Any] | str] = Field(default_factory=list)
    capability_id: str = Field(default="", max_length=80)


class ApprovalDecision(BaseModel):
    decision: Literal["once", "deny"]


class ApprovalReminderRequest(BaseModel):
    max_age_seconds: int = 600
    user_id: str = "1000000001"


class AdminUserCreate(BaseModel):
    user_id: str
    display_name: str
    role: Literal["friend", "guest", "owner"] = "friend"
    token: str = ""
    can_approve: bool = False
    can_remote_control: bool = False
    quota_policy: str = "friend_free"
    permissions: dict[str, Any] | str = Field(default_factory=dict)


class AdminUserPatch(BaseModel):
    display_name: str | None = None
    role: Literal["friend", "guest", "owner"] | None = None
    token: str | None = None
    can_approve: bool | None = None
    can_remote_control: bool | None = None
    quota_policy: str | None = None
    permissions: dict[str, Any] | str | None = None


class UserProfileFieldPatch(BaseModel):
    value: str = Field(default="", max_length=240)


class ProactiveDraftCreate(BaseModel):
    conversation_id: str | None = None
    kind: Literal["reminder", "summary", "qq.send", "task_suggestion", "alert"] = "summary"
    summary: str
    content: str = ""
    action: dict[str, Any] = Field(default_factory=dict)
    target: dict[str, Any] = Field(default_factory=dict)
    risk_level: str = "medium"


class TaskCreate(BaseModel):
    title: str
    task_type: str = "general"
    conversation_id: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class TaskEventCreate(BaseModel):
    event_type: str = "log"
    content: str
    metadata: dict[str, Any] = Field(default_factory=dict)


class ScheduledJobCreate(BaseModel):
    kind: Literal["cron", "interval", "once"] = "cron"
    schedule: str
    summary: str
    task_id: str | None = None
    target: dict[str, Any] = Field(default_factory=dict)
    payload: dict[str, Any] = Field(default_factory=dict)
    policy: dict[str, Any] = Field(default_factory=dict)
    max_retries: int = 0


class PromptCardCreate(BaseModel):
    name: str
    card_type: str = "style"
    content: str
    enabled: bool = True
    metadata: dict[str, Any] = Field(default_factory=dict)


class PromptBindingCreate(BaseModel):
    card_id: str
    scope_type: str = "channel"
    scope_id: str
    priority: int = 100
    enabled: bool = True
    metadata: dict[str, Any] = Field(default_factory=dict)


class ChannelEventCreate(BaseModel):
    channel: str
    source_id: str
    direction: Literal["inbound", "outbound", "internal"] = "inbound"
    envelope: dict[str, Any] = Field(default_factory=dict)
    task_id: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class ChannelEnvelopeCreate(BaseModel):
    channel: str = ""
    source: str = "qq"
    transport: str = ""
    chat_type: str = "private"
    user_id: str = ""
    group_id: str = ""
    message_id: str = ""
    sender_role: str = "friend"
    permissions: list[str] = Field(default_factory=list)
    target_profile: str = ""
    attachments: list[dict[str, Any] | str] = Field(default_factory=list)
    trace_id: str = ""


class AgentCreate(BaseModel):
    name: str
    agent_type: str = "mock"
    description: str = ""
    config: dict[str, Any] = Field(default_factory=dict)


class RoomCreate(BaseModel):
    name: str
    room_type: str = "project"
    mode: str = "auto_single"
    host_agent_id: str | None = None
    permission_level: Literal["general", "smart", "full"] = "smart"
    history_policy: Literal["adaptive", "summary", "full"] = "adaptive"
    max_turns: int = Field(default=2, ge=1, le=50)
    settings: dict[str, Any] = Field(default_factory=dict)


class RoomPatch(BaseModel):
    name: str | None = None
    mode: str | None = None
    host_agent_id: str | None = None
    permission_level: Literal["general", "smart", "full"] | None = None
    history_policy: Literal["adaptive", "summary", "full"] | None = None
    max_turns: int | None = Field(default=None, ge=1, le=50)
    settings: dict[str, Any] | None = None


class RoomMemberCreate(BaseModel):
    agent_id: str
    role: str = "participant"


class WorkflowRunCreate(BaseModel):
    mode: str = ""
    topic: str
    max_turns: int = Field(default=2, ge=1, le=50)
    background: bool = False


class PromptRenderPreview(BaseModel):
    channel: str = "hermi"
    room_id: str | None = None
    agent_id: str | None = None
    agent_name: str | None = None


class ProfileDisplayNamePatch(BaseModel):
    display_name: str = Field(min_length=1, max_length=40)


class OperationZoneCreate(BaseModel):
    node_id: str = "local"
    workspace_path: str
    allowed_tools: list[str] = Field(default_factory=lambda: ["list", "read", "git_status"])
    denied_paths: list[str] = Field(default_factory=list)
    permission_level: str = "readonly"
    requires_approval: bool = True


class OperationAction(BaseModel):
    action: str
    path: str = "."


class CodeAdapterRunCreate(BaseModel):
    adapter: Literal["codex", "opencode"]
    operation_zone_id: str
    summary: str
    mode: Literal["plan", "review", "repair"] = "plan"
    instructions: str = ""
    requires_approval: bool = True


class NodeRegister(BaseModel):
    node_id: str
    name: str
    capabilities: list[str] = Field(default_factory=list)
    policy: dict[str, Any] = Field(default_factory=dict)


class NodeJobCreate(BaseModel):
    summary: str
    payload: dict[str, Any] = Field(default_factory=dict)


class NodeJobLogCreate(BaseModel):
    content: str
    metadata: dict[str, Any] = Field(default_factory=dict)


class NodeJobResultCreate(BaseModel):
    status: Literal["completed", "failed"]
    result: dict[str, Any] = Field(default_factory=dict)


class NodeJobArtifactMeta(BaseModel):
    artifact_type: Literal["file", "log", "screenshot", "diff", "test_report"] = "file"
    metadata: dict[str, Any] = Field(default_factory=dict)


class DeploymentJobCreate(BaseModel):
    target_node: str
    summary: str
    payload: dict[str, Any] = Field(default_factory=dict)


class QQEventIn(BaseModel):
    message_id: str
    chat_type: Literal["private", "group"]
    user_id: str
    text: str
    nickname: str | None = None
    group_id: str | None = None
    attachments: list[str] = Field(default_factory=list)
    sender_role: str = "friend"
    risk: dict[str, Any] = Field(default_factory=dict)
    session_id: str
    session_key: str
    qlos_prompt: str = Field(default="", max_length=2000)
    trusted_context: dict[str, Any] | None = None

