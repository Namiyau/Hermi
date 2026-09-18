from __future__ import annotations





import json
import math


import base64


import hashlib


import mimetypes


import os


import re


import shutil


import subprocess


import sys


import threading


import time


import uuid
from datetime import date, timedelta


from pathlib import Path


from typing import Any, Literal


from urllib.parse import unquote, urlparse





from fastapi import Body, Depends, FastAPI, File, Form, Header, HTTPException, Request, UploadFile


from fastapi.responses import FileResponse, Response, StreamingResponse



from .admin_routes import register_admin_routes
from .admin_users import mark_user_profile_context_injected, pending_user_profile_context

from .symbiosis_routes import register_symbiosis_routes

from .config import HermiConfig

from .db import create_seed_users, init_db, upsert_user, verify_token


from .hermes import HermesAdapter

from .meeting_context import compact_meeting_context as _compact_meeting_context

from .meeting_events import trace_event as _meeting_trace_event

from .meeting_modes import (

    HOST_ROLES,

    MEETING_MODE_IDS,

    MEETING_MODE_PRESETS,

    MEETING_ROLE_PRESETS,

    meeting_mode_label as _meeting_mode_label,

    normalize_meeting_mode as _normalize_meeting_mode,

)

from .meeting_orchestrator import discussion_control as _meeting_discussion_control

from .meeting_permissions import meeting_permission_prompt as _meeting_permission_prompt

from .meeting_repository import room_by_id as _room_by_id, room_members as _room_members, room_runs

from .meeting_routes import register_meeting_web_routes

from .meeting_service import can_delete_room, next_run_status

from .permissions import (
    PERMISSIONS_ENABLED,
    PermissionChecker,
    grant_existing_users_external_tool_access,
    migrate_quota_to_permissions,
)


from .prompting import build_hermi_messages, extract_hermi_action, public_owner_identity_reply


from .qq_context import load_recent_qq_context


from .qq_adapter import CHANNEL_ENVELOPE_FIELDS, normalize_channel_envelope


from .qlos_client import QlosClient

from .trusted_context import (
    build_hermi_web_context,
    ensure_hermi_subject_page,
    verify_qq_context,
    write_trusted_session_context,
)

from .scheduler import (

    apply_job_delivery_policy as _apply_job_delivery_policy,

    cron_due as _cron_due,

    cron_field_values as _cron_field_values,

    delivery_list as _delivery_list,

    duration_seconds as _duration_seconds,

    retry_backoff_seconds as _retry_backoff_seconds,

    scheduled_job_due as _scheduled_job_due,

    scheduled_job_messages as _scheduled_job_messages,

    simple_cron_interval_seconds as _simple_cron_interval_seconds,

)

from .models import (


    AgentCreate,


    ApprovalDecision,


    ApprovalReminderRequest,


    CodeAdapterRunCreate,


    ConversationCreate,

    ConversationPatch,

    DeploymentJobCreate,


    MessageCreate,


    NodeJobCreate,


    NodeJobArtifactMeta,


    NodeJobLogCreate,


    NodeJobResultCreate,


    NodeRegister,


    ChannelEventCreate,


    ChannelEnvelopeCreate,


    PromptCardCreate,


    PromptBindingCreate,

    PromptRenderPreview,

    ProfileDisplayNamePatch,

    SelfDisplayNamePatch,
    UserLocalePatch,

    OperationAction,


    OperationZoneCreate,


    ProactiveDraftCreate,


    QQEventIn,

    RoomCreate,

    RoomPatch,

    RoomMemberCreate,

    ScheduledJobCreate,


    TaskCreate,


    TaskEventCreate,


    WorkflowRunCreate,


)








TEMPORARY_QUOTA_TOKENS = 100_000


def create_app(


    config: HermiConfig | None = None,


    hermes_adapter: Any | None = None,


    qlos_client: Any | None = None,


) -> FastAPI:


    config = config or HermiConfig.from_env()


    conn = init_db(config.db_path)

    create_seed_users(conn, config.owner_token, config.channel_token)

    grant_existing_users_external_tool_access(conn)

    _ensure_default_capabilities(conn)

    _ensure_default_prompt_bindings(conn)

    _sync_profile_agents(conn, config)

    _mark_orphaned_workflow_runs_recoverable(conn)

    app = FastAPI(title="Hermi Gateway", version="0.1.0")

    register_meeting_web_routes(app, _web_path)

    app.state.config = config


    app.state.db = conn


    app.state.hermes_adapter = hermes_adapter or HermesAdapter(config)


    app.state.qlos_client = qlos_client or QlosClient(config)


    app.state.scheduler_lock = threading.Lock()

    app.state.run_lock = threading.RLock()

    app.state.approval_lock = threading.Lock()

    app.state.workflow_threads = {}




    if config.scheduler_enabled:


        @app.on_event("startup")


        def start_scheduler_loop() -> None:


            if getattr(app.state, "scheduler_thread_started", False):


                return


            app.state.scheduler_thread_started = True


            thread = threading.Thread(


                target=_scheduler_loop,


                args=(app,),


                name="hermi-scheduler",


                daemon=True,


            )


            thread.start()





    def current_user(authorization: str | None = Header(default=None)) -> dict[str, Any]:


        token = _bearer_token(authorization)


        user = verify_token(conn, token)


        if not user:


            raise HTTPException(status_code=401, detail="unauthorized")


        # Phase 1: attach parsed permissions info to user dict


        try:


            checker = PermissionChecker(user)


            user["_permissions"] = checker.to_dict()


        except Exception:


            user["_permissions"] = None


        return user





    def owner_user(user: dict[str, Any] = Depends(current_user)) -> dict[str, Any]:


        if not user.get("can_approve"):


            raise HTTPException(status_code=403, detail="owner_required")


        return user





    def channel_user(user: dict[str, Any] = Depends(current_user)) -> dict[str, Any]:


        if user.get("role") != "channel":


            raise HTTPException(status_code=403, detail="channel_required")


        return user





    def _require_perm(perm_name: str, user: dict[str, Any]) -> None:

        """Phase 2: permission check helper. Raises 403 if denied, returns None if allowed."""

        result = _permission_result(perm_name, user)

        if result in ("deny", "owner_only"):

            raise HTTPException(status_code=403, detail=f"permission_denied:{perm_name}")

        if result == "approval":

            raise HTTPException(status_code=403, detail=f"permission_approval_required:{perm_name}")



    def _permission_result(perm_name: str, user: dict[str, Any]) -> str:

        if user.get("role") == "owner":

            return "allow"

        checker = PermissionChecker(user)

        return checker.check(perm_name)



    def _require_owner_or_perm(perm_name: str, user: dict[str, Any]) -> None:


        """Check: owner passes automatically; others need specific permission."""


        if user.get("role") == "owner":


            return


        _require_perm(perm_name, user)





    def _has_perm_allow(user: dict[str, Any], perm_name: str) -> bool:


        """Check whether user has 'allow' for a permission (returns False for deny/approval/owner_only)."""


        if user.get("role") == "owner":


            return True


        checker = PermissionChecker(user)


        return checker.check(perm_name) == "allow"





    def node_auth(authorization: str | None = Header(default=None)) -> dict[str, Any]:


        token = _bearer_token(authorization)


        row = conn.execute("select * from nodes where token = ?", (token,)).fetchone() if token else None


        if not row:


            raise HTTPException(status_code=401, detail="node_unauthorized")


        return dict(row)





    @app.get("/health")

    async def health() -> dict[str, str]:

        return {"status": "ok", "service": "hermi-gateway"}




    def frontend_file(filename: str) -> FileResponse:

        return FileResponse(

            _web_path(filename),

            headers={"Cache-Control": "no-store, max-age=0, must-revalidate"},

        )


    @app.get("/")


    def index() -> FileResponse:


        return frontend_file("index.html")





    @app.get("/app.js")

    def app_js() -> FileResponse:

        return frontend_file("app.js")



    @app.get("/admin_tools.js")

    def admin_tools_js() -> FileResponse:

        return frontend_file("admin_tools.js")



    @app.get("/permissions_panel.js")

    def permissions_panel_js() -> FileResponse:

        return frontend_file("permissions_panel.js")



    @app.get("/scheduled_jobs.js")

    def scheduled_jobs_js() -> FileResponse:

        return frontend_file("scheduled_jobs.js")

    @app.get("/i18n.js")

    def i18n_js() -> FileResponse:

        return frontend_file("i18n.js")



    @app.get("/message_ui.js")

    def message_ui_js() -> FileResponse:

        return frontend_file("message_ui.js")



    @app.get("/trace_ui.js")

    def trace_ui_js() -> FileResponse:

        return frontend_file("trace_ui.js")



    @app.get("/styles.css")


    def styles_css() -> FileResponse:


        return frontend_file("styles.css")





    @app.get("/manifest.webmanifest")


    def manifest() -> FileResponse:


        return frontend_file("manifest.webmanifest")





    @app.get("/favicon.ico")


    def favicon() -> Response:


        return Response(status_code=204)





    @app.get("/me")

    def me(user: dict[str, Any] = Depends(current_user)) -> dict[str, Any]:

        return _public_user(user)


    @app.get("/my/summary")

    def my_summary(user: dict[str, Any] = Depends(current_user)) -> dict[str, Any]:

        user_id = str(user["user_id"])

        conversation_count = conn.execute(

            "select count(*) as count from conversations where owner_user_id = ?",

            (user_id,),

        ).fetchone()["count"]

        message_count = conn.execute(

            """

            select count(*) as count

            from messages m join conversations c on c.conversation_id = m.conversation_id

            where c.owner_user_id = ?

            """,

            (user_id,),

        ).fetchone()["count"]

        attachment_count = conn.execute(

            "select count(*) as count from media_files where created_by = ?",

            (user_id,),

        ).fetchone()["count"]

        total_tokens = conn.execute(

            "select coalesce(sum(total_tokens), 0) as total from usage_daily where user_id = ?",

            (user_id,),

        ).fetchone()["total"]

        seven_day_start = (date.today() - timedelta(days=6)).isoformat()

        last_7_day_tokens = conn.execute(

            "select coalesce(sum(total_tokens), 0) as total from usage_daily where user_id = ? and day >= ?",

            (user_id, seven_day_start),

        ).fetchone()["total"]

        scheduled_job_count = conn.execute(

            "select count(*) as count from scheduled_jobs where created_by = ?",

            (user_id,),

        ).fetchone()["count"]

        pending_approval_count = conn.execute(

            """

            select count(*) as count

            from approvals a join conversations c on c.conversation_id = a.conversation_id

            where c.owner_user_id = ? and a.status = 'pending'

            """,

            (user_id,),

        ).fetchone()["count"]

        quota_window = _quota_window_summary(conn, user, config)

        return {

            "user_id": user_id,

            "display_name": str(user.get("display_name") or user_id),

            "role": str(user.get("role") or "friend"),

            "quota_policy": str(user.get("quota_policy") or ""),

            "conversation_count": int(conversation_count or 0),

            "message_count": int(message_count or 0),

            "attachment_count": int(attachment_count or 0),

            "total_tokens": int(total_tokens or 0),

            "last_7_day_tokens": int(last_7_day_tokens or 0),

            "quota_window": quota_window,

            "scheduled_job_count": int(scheduled_job_count or 0),

            "pending_approval_count": int(pending_approval_count or 0),

        }


    @app.patch("/my/display-name")

    def update_my_display_name(

        body: SelfDisplayNamePatch,

        user: dict[str, Any] = Depends(current_user),

    ) -> dict[str, Any]:

        display_name = body.display_name.strip()

        conn.execute("update users set display_name = ? where user_id = ?", (display_name, user["user_id"]))

        _audit(conn, "user_display_name_updated", user["user_id"], {"display_name": display_name})

        conn.commit()

        return {"user_id": user["user_id"], "display_name": display_name}

    @app.post("/my/quota-requests", status_code=201)
    def request_temporary_quota(user: dict[str, Any] = Depends(current_user)) -> dict[str, Any]:
        if user.get("role") in {"owner", "channel"} or _token_limit_for_user(user, config) is None:
            raise HTTPException(status_code=403, detail="temporary_quota_not_available")

        _expire_pending_approvals(conn)
        pending = conn.execute(
            """
            select 1
            from approvals a
            join conversations c on c.conversation_id = a.conversation_id
            where c.owner_user_id = ? and a.action_type = ? and a.status = 'pending'
            limit 1
            """,
            (user["user_id"], "quota.temporary.grant"),
        ).fetchone()
        if pending:
            raise HTTPException(status_code=409, detail="temporary_quota_request_pending")

        conversation_id = _get_or_create_user_system_conversation(conn, user)
        approval = _create_action_approval(
            conn,
            conversation_id,
            {
                "type": "quota.temporary.grant",
                "user_id": user["user_id"],
                "token_amount": TEMPORARY_QUOTA_TOKENS,
                "summary": "申请临时额度 100,000 Token",
            },
            source="self_service",
            summary="申请临时额度 100,000 Token",
            risk_level="medium",
        )
        conn.commit()
        return approval

    @app.get("/my/notices")
    def list_my_notices(user: dict[str, Any] = Depends(current_user)) -> dict[str, Any]:
        rows = conn.execute(
            """
            select notice_id, kind, title, message, created_at
            from user_notices
            where user_id = ? and read_at is null
            order by created_at asc
            limit 20
            """,
            (user["user_id"],),
        ).fetchall()
        return {"notices": [dict(row) for row in rows]}

    @app.post("/my/notices/{notice_id}/read")
    def mark_my_notice_read(notice_id: str, user: dict[str, Any] = Depends(current_user)) -> dict[str, Any]:
        updated = conn.execute(
            "update user_notices set read_at = ? where notice_id = ? and user_id = ? and read_at is null",
            (time.time(), notice_id, user["user_id"]),
        )
        conn.commit()
        if updated.rowcount != 1:
            raise HTTPException(status_code=404, detail="notice_not_found")
        return {"ok": True, "notice_id": notice_id}

    @app.patch("/my/locale")
    def update_my_locale(
        body: UserLocalePatch,
        user: dict[str, Any] = Depends(current_user),
    ) -> dict[str, Any]:
        conn.execute("update users set locale = ? where user_id = ?", (body.locale, user["user_id"]))
        _audit(conn, "user_locale_updated", user["user_id"], {"locale": body.locale})
        conn.commit()
        return {"user_id": user["user_id"], "locale": body.locale}




    @app.get("/conversations")


    def list_conversations(user: dict[str, Any] = Depends(current_user)) -> dict[str, Any]:

        if user.get("can_approve") or _has_perm_allow(user, "view_all_conversations"):

            rows = conn.execute(

                """

                select c.*, coalesce(u.display_name, c.owner_user_id) as owner_display_name,

                       coalesce(u.role, '') as owner_role

                from conversations c left join users u on u.user_id = c.owner_user_id

                order by c.updated_at desc, c.created_at desc

                """

            ).fetchall()

        else:


            rows = conn.execute(


                """


                select c.*, coalesce(u.display_name, c.owner_user_id) as owner_display_name,

                       coalesce(u.role, '') as owner_role

                from conversations c left join users u on u.user_id = c.owner_user_id

                where c.owner_user_id = ?

                order by c.updated_at desc, c.created_at desc

                """,


                (user["user_id"],),


            ).fetchall()


        return {

            "conversations": [

                {
                    **dict(row),
                    "profile_id": _conversation_profile_id(conn, config, dict(row)),
                    "target_profile": _conversation_profile_name(conn, config, dict(row)),
                }

                for row in rows

            ]

        }




    @app.post("/conversations")


    def create_conversation(

        body: ConversationCreate,

        user: dict[str, Any] = Depends(current_user),

    ) -> dict[str, Any]:

        if _permission_result("chat", user) in {"deny", "owner_only"}:

            raise HTTPException(status_code=403, detail="permission_denied:chat")

        now = time.time()


        conversation_id = f"conv-{uuid.uuid4().hex[:12]}"


        session_id = f"hermi-{conversation_id}"


        session_key = f"hermi:{conversation_id}"

        channel = str(body.channel).lower()
        profile_id = config.qq_profile_id if channel == "qq" else str(body.profile_id or "").strip() or config.hermi_profile_id
        if channel != "qq" and profile_id != config.hermi_profile_id:
            raise HTTPException(status_code=422, detail="profile_not_available")


        conn.execute(


            """


            insert into conversations (


              conversation_id, channel, source_id, title, session_id, session_key, profile_id,


              owner_user_id, visibility, quota_policy, created_at, updated_at


            ) values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)


            """,


            (


                conversation_id,


                body.channel,


                conversation_id,


                body.title,


                session_id,


                session_key,


                profile_id,


                user["user_id"],


                "private",


                user["quota_policy"],


                now,


                now,


            ),


        )


        conn.commit()


        return _conversation_by_id(conn, conversation_id)





    @app.delete("/conversations/{conversation_id}")

    def delete_conversation(

        conversation_id: str,

        user: dict[str, Any] = Depends(current_user),

    ) -> dict[str, Any]:

        conversation = _require_conversation(conn, conversation_id)

        if not user.get("can_approve") and conversation.get("owner_user_id") != user.get("user_id"):

            raise HTTPException(status_code=403, detail="conversation_forbidden")

        hermes_delete = {}


        profile_id = _conversation_profile_id(conn, config, conversation)


        if hasattr(app.state.hermes_adapter, "delete_profile_session"):


            hermes_delete = app.state.hermes_adapter.delete_profile_session(


                profile_id,


                str(conversation.get("session_id") or ""),


                str(conversation.get("session_key") or ""),


            )


        elif hasattr(app.state.hermes_adapter, "delete_session"):


            hermes_delete = app.state.hermes_adapter.delete_session(


                str(conversation.get("session_id") or ""),


                str(conversation.get("session_key") or ""),


            )


        conn.execute("delete from messages where conversation_id = ?", (conversation_id,))


        conn.execute("delete from approvals where conversation_id = ?", (conversation_id,))


        conn.execute("delete from message_runs where conversation_id = ?", (conversation_id,))


        conn.execute("delete from user_profile_injections where conversation_id = ?", (conversation_id,))


        conn.execute("delete from conversations where conversation_id = ?", (conversation_id,))


        _audit(


            conn,


            "conversation_deleted",


            user["user_id"],


            {"conversation_id": conversation_id, "hermes_session_delete": hermes_delete},


        )


        conn.commit()


        return {"ok": True, "conversation_id": conversation_id, "hermes_session_delete": hermes_delete}



    @app.patch("/conversations/{conversation_id}")

    def rename_conversation(conversation_id: str, body: ConversationPatch, user: dict[str, Any] = Depends(current_user)) -> dict[str, Any]:

        conversation = _require_conversation(conn, conversation_id)

        if conversation.get("owner_user_id") != user.get("user_id"):

            raise HTTPException(status_code=403, detail="conversation_forbidden")

        title = body.title.strip()

        conn.execute("update conversations set title = ?, updated_at = ? where conversation_id = ?", (title, time.time(), conversation_id))

        _audit(conn, "conversation_renamed", user["user_id"], {"conversation_id": conversation_id, "title": title})

        conn.commit()

        return _conversation_by_id(conn, conversation_id)




    @app.get("/conversations/{conversation_id}/messages")


    def list_messages(

        conversation_id: str,

        user: dict[str, Any] = Depends(current_user),

    ) -> dict[str, Any]:

        conversation = _require_conversation_for_user(conn, conversation_id, user)

        # Create the hash-only, session-bound subject context as soon as a user
        # message is accepted.  This intentionally precedes local/attachment
        # shortcuts so the first Hermi-visible utterance can create its subject
        # page even when no LLM request follows.
        _record_hermi_tool_identity(config, conversation, user)


        _sync_hermes_session_messages(conn, app.state.hermes_adapter, config, conversation)

        _backfill_message_authors_from_runs(conn, conversation_id)

        rows = conn.execute(

            "select * from messages where conversation_id = ? order by created_at asc",

            (conversation_id,),

        ).fetchall()

        return {

            "messages": [

                {**dict(row), "actor": _message_actor(conn, config, conversation, dict(row))}

                for row in rows

            ]

        }




    @app.get("/conversations/{conversation_id}/context")


    def conversation_context(


        conversation_id: str,


        user: dict[str, Any] = Depends(current_user),


    ) -> dict[str, Any]:


        conversation = _require_conversation_for_user(conn, conversation_id, user)


        messages = conn.execute(


            "select * from messages where conversation_id = ? order by created_at asc",


            (conversation_id,),


        ).fetchall()


        attachments = 0


        traces = 0


        for row in messages:


            metadata = _safe_json_dict(row["metadata_json"])


            attachments += len(metadata.get("attachments") or [])


            traces += len(metadata.get("trace") or [])


        tasks = conn.execute(


            "select task_id, title, status, task_type, updated_at from tasks where conversation_id = ? order by updated_at desc limit 8",


            (conversation_id,),


        ).fetchall()


        usage_rows = conn.execute(


            "select * from usage_daily where user_id = ? order by day desc limit 7",


            (conversation["owner_user_id"],),


        ).fetchall()


        usage = _usage_totals([dict(row) for row in usage_rows])

        conversation_usage_row = conn.execute(
            "select prompt_tokens, completion_tokens, total_tokens, cache_read_tokens, cache_reported from conversation_usage where conversation_id = ?",
            (conversation_id,),
        ).fetchone()
        conversation_usage = _usage_totals([dict(conversation_usage_row)]) if conversation_usage_row else _usage_totals([])
        if conversation_usage_row:
            cache_read_tokens = int(conversation_usage_row["cache_read_tokens"] or 0)
            cache_reported = bool(conversation_usage_row["cache_reported"])
            prompt_tokens = int(conversation_usage_row["prompt_tokens"] or 0)
            conversation_usage["cache_read_tokens"] = cache_read_tokens
            conversation_usage["cache_hit_rate"] = round(cache_read_tokens * 100 / prompt_tokens) if cache_reported and prompt_tokens else None
        else:
            conversation_usage["cache_read_tokens"] = 0
            conversation_usage["cache_hit_rate"] = None


        return {


            "conversation_id": conversation_id,


            "title": conversation["title"],


            "channel": conversation["channel"],


            "owner_user_id": conversation["owner_user_id"],


            "target_profile": _conversation_profile_name(conn, config, conversation),

            "message_count": len(messages),


            "attachment_count": attachments,


            "trace_event_count": traces,


            "tasks": [dict(row) for row in tasks],


            "usage": usage,

            "conversation_usage": conversation_usage,


            "usage_scope": "user_last_7_days",

            "context_window": _context_window_summary(len(messages), conversation_usage),


        }





    @app.post("/conversations/{conversation_id}/messages")


    def post_message(

        conversation_id: str,


        body: MessageCreate,


        user: dict[str, Any] = Depends(current_user),


    ) -> dict[str, Any]:

        conversation = _require_conversation_for_user(conn, conversation_id, user)

        _record_hermi_tool_identity(config, conversation, user)

        chat_permission = _permission_result("chat", user)

        if chat_permission in {"deny", "owner_only"}:

            raise HTTPException(status_code=403, detail="permission_denied:chat")

        _require_token_quota(conn, user, config)

        attachment_refs = _resolve_message_attachments(conn, body.attachments, user)


        user_message_metadata = {"author_user_id": str(user["user_id"])}
        if attachment_refs:
            user_message_metadata["attachments"] = _public_attachment_refs(attachment_refs)

        user_message = _insert_message(


            conn,


            conversation_id,


            "user",


            body.content,


            "hermi",


            metadata=user_message_metadata,


        )

        _increment_usage(conn, user["user_id"], text_messages=1)

        _increment_quota_window_usage(conn, user, text_messages=1, config=config)

        conn.execute(

            "update conversations set updated_at = ? where conversation_id = ?",


            (time.time(), conversation_id),

        )

        if _is_attachment_only_message(body.content, attachment_refs):

            assistant_message = _insert_message(

                conn,

                conversation_id,

                "assistant",

                _attachment_waiting_reply(attachment_refs),

                "hermi",

            )

            conn.commit()

            return {"user": user_message, "assistant": assistant_message}

        if _needs_image_vision(body.content, attachment_refs) and not _image_vision_enabled():

            assistant_message = _insert_message(

                conn,

                conversation_id,

                "assistant",

                _image_vision_unavailable_reply(),

                "hermi",

            )

            conn.commit()

            return {"user": user_message, "assistant": assistant_message}

        if chat_permission == "approval":

            approval_reply = _create_chat_message_approval(conn, conversation, body.content, user)

            assistant_message = _insert_message(conn, conversation_id, "assistant", approval_reply, "hermi")

            conn.commit()

            return {"user": user_message, "assistant": assistant_message}

        local_reply = _local_hermi_command_reply(conn, config, conversation, body.content, user)

        if local_reply is not None:

            assistant_message = _insert_message(conn, conversation_id, "assistant", local_reply, "hermi")

            _auto_name_conversation(conn, conversation, body.content, _active_profile_name(conn, config))

            conn.commit()


            return {"user": user_message, "assistant": assistant_message}

        identity_reply = public_owner_identity_reply(
            user,
            body.content,
            owner_display_name=_owner_display_name(conn),
            profile_name=_profile_display_name(conn, _conversation_profile_id(conn, config, conversation)),
        )
        if identity_reply is not None:
            assistant_message = _insert_message(conn, conversation_id, "assistant", identity_reply, "hermi")
            conn.commit()
            return {"user": user_message, "assistant": assistant_message}

        if user.get("role") == "owner":

            owner_schedule = _owner_scheduled_request_reply(conn, conversation, body.content)

            if owner_schedule is not None:

                schedule_reply, job = owner_schedule

                assistant_message = _insert_message(

                    conn,

                    conversation_id,

                    "assistant",

                    schedule_reply,

                    "hermi",

                    metadata={"action_type": "scheduled.create", "job_id": job["job_id"], "task_id": job.get("task_id")},

                )

                _auto_name_conversation(conn, conversation, body.content, _active_profile_name(conn, config))

                conn.commit()

                return {"user": user_message, "assistant": assistant_message}

        mixed_scheduled_request = _is_mixed_scheduled_request(body.content)

        scheduled_reply = _scheduled_chat_permission_reply(

            conn, conversation, body.content, user, continue_chat=mixed_scheduled_request

        )

        if scheduled_reply is not None and not mixed_scheduled_request:

            assistant_message = _insert_message(conn, conversation_id, "assistant", scheduled_reply, "hermi")

            conn.commit()

            return {"user": user_message, "assistant": assistant_message}

        scheduled_instruction = scheduled_reply if mixed_scheduled_request else ""

        profile_id = _conversation_profile_id(conn, config, conversation)
        profile_name = _profile_display_name(conn, profile_id)
        user_profile_context, user_profile_revision = pending_user_profile_context(
            conn, str(user["user_id"]), conversation_id
        )
        history = build_hermi_messages(

            _history_with_attachment_context(_conversation_history(conn, conversation_id), attachment_refs),

            user=user,

            conversation=conversation,

            recent_qq_context=_recent_qq_context_for_request(config, user, body.content),

            soul_text=_load_soul_text(config),

            profile_name=profile_name,
            profile_id=profile_id,
            qq_profile_name=_profile_display_name(conn, config.qq_profile_id),
            media_dir=str(_media_dir(config)),
            user_profile_context=user_profile_context,
            owner_display_name=_owner_display_name(conn),

        )

        if scheduled_instruction:

            history.insert(1, {"role": "system", "content": scheduled_instruction})

        skill_instruction = _skill_capability_instruction(body.capability_id)

        if skill_instruction:

            history.insert(1, {"role": "system", "content": skill_instruction})

        profile_context_delivered = False
        try:

            reply = _chat_profile(

                app.state.hermes_adapter,

                profile_id,

                history,

                conversation["session_id"],

                conversation["session_key"],


            ).strip()

            profile_context_delivered = True


            _increment_usage_from_hermes(
                conn,
                user["user_id"],
                app.state.hermes_adapter,
                conversation_id=conversation_id,
                config=config,
            )


        except Exception:


            reply = "我这边调用 Hermes 出错了，稍后再试。"


        if profile_context_delivered:
            mark_user_profile_context_injected(conn, str(user["user_id"]), conversation_id, user_profile_revision)

        reply, action = extract_hermi_action(reply)


        reply = _friendly_hermes_failure_reply(reply)

        if scheduled_instruction and str((action or {}).get("type") or "") in {"scheduled.create", "cron.create"}:

            action = None


        if not action and not scheduled_instruction:


            action = _infer_hermes_permission_action(reply, body.content)


        if not action and user.get("role") != "owner" and not scheduled_instruction:


            native_cron_reply = _maybe_create_native_hermes_cron(config, conversation, body.content, reply)


            if native_cron_reply:


                reply = native_cron_reply


        _repair_recent_native_cron_origin(conversation, body.content)


        media_refs = _ingest_local_media_paths(conn, config, conversation_id, reply, user["user_id"]) if user.get("role") == "owner" else []


        reply = _strip_media_markers(reply, strip_local_paths=bool(media_refs))


        action, denied_action_reply = _filter_action_for_user(action, user)

        if denied_action_reply:

            reply = (reply + "\n\n" + denied_action_reply).strip()

        _augment_qq_action_with_media(action, media_refs)


        if action and user.get("role") == "owner" and str(action.get("type") or "") in {"scheduled.create", "cron.create"}:

            try:

                _, job = _create_owner_scheduled_job(conn, conversation_id, action)

                reply = (reply + "\n\n" + f"我已经把“{job['summary']}”安排好了，到时间会在这里提醒你。").strip()

                action = None

            except ValueError as exc:

                reply = (reply + "\n\n" + f"这个提醒还差一点信息：{exc}").strip()

                action = None

        if action:

            approval = _create_action_approval(conn, conversation_id, action)

            reply = (reply + "\n\n" + f"已创建审批：{approval['summary']}").strip()


        assistant_metadata = {"attachments": _public_attachment_refs(media_refs)} if media_refs else None

        assistant_message = _insert_message(conn, conversation_id, "assistant", reply, "hermes", metadata=assistant_metadata)

        _auto_name_conversation(conn, conversation, body.content, profile_name)

        conn.commit()


        return {"user": user_message, "assistant": assistant_message}





    @app.post("/conversations/{conversation_id}/messages/stream")


    def post_message_stream(

        conversation_id: str,


        body: MessageCreate,


        user: dict[str, Any] = Depends(current_user),


    ) -> StreamingResponse:

        _require_conversation_for_user(conn, conversation_id, user)

        if _permission_result("chat", user) in {"deny", "owner_only"}:

            raise HTTPException(status_code=403, detail="permission_denied:chat")

        run = _create_message_run(conn, conversation_id, user["user_id"], app.state.run_lock)


        thread = threading.Thread(


            target=_message_run_worker,


            args=(conn, app, config, run["run_id"], conversation_id, body, user, post_message),


            name=f"hermi-message-{run['run_id']}",


            daemon=True,


        )


        thread.start()





        def stream():


            yield from _stream_message_run(conn, run["run_id"], app.state.run_lock)





        return StreamingResponse(stream(), media_type="text/event-stream")



    @app.post("/conversations/{conversation_id}/runs/cancel")

    def cancel_message_run(

        conversation_id: str,

        user: dict[str, Any] = Depends(current_user),

    ) -> dict[str, Any]:

        _require_conversation_for_user(conn, conversation_id, user)

        with app.state.run_lock:

            row = conn.execute(

                """

                select * from message_runs

                where conversation_id = ? and user_id = ? and status in ('queued', 'running')

                order by created_at desc limit 1

                """,

                (conversation_id, user["user_id"]),

            ).fetchone()

            if not row:

                return {"status": "idle", "run_id": ""}

            conn.execute(

                "update message_runs set status = 'cancelled', error = 'cancelled_by_user', updated_at = ? where run_id = ?",

                (time.time(), row["run_id"]),

            )

            conn.commit()

        return {"status": "cancelled", "run_id": row["run_id"]}




    @app.get("/conversations/{conversation_id}/runs/active")


    def active_message_run(


        conversation_id: str,


        user: dict[str, Any] = Depends(current_user),


    ) -> dict[str, Any]:


        _require_conversation_for_user(conn, conversation_id, user)


        row = conn.execute(


            """


            select * from message_runs


            where conversation_id = ? and status in ('queued', 'running')


            order by created_at desc


            limit 1


            """,


            (conversation_id,),


        ).fetchone()


        if not row:


            return {"run": None}


        return {"run": _public_message_run(dict(row))}





    @app.get("/events/stream")


    def events_stream(user: dict[str, Any] = Depends(current_user)) -> StreamingResponse:


        def stream():


            yield "event: status\n"


            yield 'data: {"status":"connected"}\n\n'





        return StreamingResponse(stream(), media_type="text/event-stream")





    @app.get("/approvals")


    def list_approvals(user: dict[str, Any] = Depends(current_user)) -> dict[str, Any]:
        _expire_pending_approvals(conn)

        if user.get("can_approve"):
            rows = conn.execute("select * from approvals order by expires_at asc").fetchall()
        else:
            rows = conn.execute(
                """
                select approvals.*
                from approvals
                join conversations on conversations.conversation_id = approvals.conversation_id
                where conversations.owner_user_id = ?
                order by approvals.expires_at asc
                """,
                (user["user_id"],),
            ).fetchall()

        return {"approvals": [dict(row) for row in rows]}





    @app.post("/approvals/native")


    def create_native_approval(


        body: dict[str, Any] = Body(...),


        user: dict[str, Any] = Depends(owner_user),


    ) -> dict[str, Any]:


        conversation_id = str(body.get("conversation_id") or "").strip()


        _require_conversation_for_user(conn, conversation_id, user)


        action = {


            "type": str(body.get("capability_id") or body.get("action_type") or "hermes.native.approval"),


            "summary": str(body.get("summary") or "Hermes native approval request"),


            "payload": body.get("payload") or {},


            "run_id": body.get("run_id") or "",


            "request_id": body.get("request_id") or "",


        }


        _validate_action_payload(action)


        approval = _create_action_approval(


            conn,


            conversation_id,


            action,


            source="hermes.native",


            summary=action["summary"],


            risk_level=_capability_risk(conn, action["type"]),


        )


        _create_approval_callback(


            conn,


            approval["approval_id"],


            external_run_id=str(body.get("run_id") or ""),


            external_request_id=str(body.get("request_id") or ""),


            payload=body,


        )


        conn.commit()


        return approval





    @app.get("/approvals/{approval_id}/callbacks")


    def approval_callbacks(


        approval_id: str,


        user: dict[str, Any] = Depends(owner_user),


    ) -> dict[str, Any]:


        _require_approval(conn, approval_id)


        rows = conn.execute(


            "select * from approval_callbacks where approval_id = ? order by created_at asc",


            (approval_id,),


        ).fetchall()


        return {"approval_id": approval_id, "callbacks": [dict(row) for row in rows]}





    @app.get("/proactive/drafts")


    def list_proactive_drafts(user: dict[str, Any] = Depends(owner_user)) -> dict[str, Any]:


        rows = conn.execute(


            "select * from approvals where source = ? order by created_at desc",


            ("proactive",),


        ).fetchall()


        return {"drafts": [dict(row) for row in rows]}





    @app.post("/proactive/drafts")


    def create_proactive_draft(


        body: ProactiveDraftCreate,


        user: dict[str, Any] = Depends(owner_user),


    ) -> dict[str, Any]:


        conversation_id = body.conversation_id or _get_or_create_proactive_conversation(conn, user)


        _require_conversation(conn, conversation_id)


        action = _proactive_action_from_body(body)


        approval = _create_action_approval(


            conn,


            conversation_id,


            action,


            source="proactive",


            summary=body.summary,


            risk_level=body.risk_level,


        )


        conn.commit()


        return approval





    @app.post("/approvals/{approval_id}/decision")


    def decide_approval(

        approval_id: str,


        body: ApprovalDecision,


        user: dict[str, Any] = Depends(owner_user),


    ) -> dict[str, Any]:

        with app.state.approval_lock:

            _expire_pending_approvals(conn)

            row = conn.execute("select * from approvals where approval_id = ?", (approval_id,)).fetchone()

            if not row:

                raise HTTPException(status_code=404, detail="approval_not_found")

            if row["status"] != "pending":

                raise HTTPException(status_code=409, detail="approval_already_decided")

            claim_time = time.time()

            claimed = conn.execute(

                """

                update approvals

                set status = 'executing', decision = ?, decided_by = ?, updated_at = ?

                where approval_id = ? and status = 'pending'

                """,

                (body.decision, user["user_id"], claim_time, approval_id),

            )

            conn.commit()

            if claimed.rowcount != 1:

                raise HTTPException(status_code=409, detail="approval_already_decided")

        execution_note = ""
        action = _safe_json_dict(row["payload_json"])

        if body.decision == "once":
            try:

                execution_note = _execute_approved_action(conn, app, config, dict(row), action)

                status = "approved"

            except Exception as exc:

                status = "failed"

                execution_note = f"{type(exc).__name__}: {exc}"

                _insert_message(

                    conn,

                    str(row["conversation_id"]),

                    "assistant",

                    f"本次审批已通过，但执行失败：{row['summary']}。请稍后重试。",

                    "hermi",

                    metadata={"approval_id": approval_id, "approval_status": "failed"},

                )

        else:

            status = "denied"

            if str(action.get("type") or "") == "quota.temporary.grant":
                conversation = _require_conversation(conn, str(row["conversation_id"]))
                _create_user_notice(
                    conn,
                    str(action.get("user_id") or conversation.get("owner_user_id") or ""),
                    kind="quota.temporary.grant.denied",
                    title="临时额度申请未通过",
                    message="Owner 未批准本次 100,000 Token 临时额度申请。你可以等待额度重置后再试，或稍后重新申请。",
                )
            else:
                _insert_message(
                    conn,
                    str(row["conversation_id"]),
                    "assistant",
                    f"Owner 已拒绝本次请求：{row['summary']}",
                    "hermi",
                    metadata={"approval_id": approval_id, "approval_status": "denied"},
                )

            conn.execute(

                "update conversations set updated_at = ? where conversation_id = ?",

                (time.time(), row["conversation_id"]),

            )

        now = time.time()


        conn.execute(


            """


            update approvals


            set status = ?, decision = ?, decided_by = ?, decided_at = ?, updated_at = ?


            where approval_id = ?


            """,


            (status, body.decision, user["user_id"], now, now, approval_id),


        )


        _audit(


            conn,


            "approval_decided",


            user["user_id"],


            {


                "approval_id": approval_id,


                "decision": body.decision,


                "status": status,


                "execution_note": execution_note,


            },


        )


        _update_approval_callbacks(conn, approval_id, status, body.decision, execution_note)


        conn.commit()


        return dict(conn.execute("select * from approvals where approval_id = ?", (approval_id,)).fetchone())





    @app.delete("/approvals/{approval_id}")


    def delete_approval(


        approval_id: str,


        user: dict[str, Any] = Depends(owner_user),


    ) -> dict[str, Any]:


        row = conn.execute("select * from approvals where approval_id = ?", (approval_id,)).fetchone()


        if not row:


            raise HTTPException(status_code=404, detail="approval_not_found")


        if row["status"] == "pending":


            raise HTTPException(status_code=409, detail="approval_pending")


        conn.execute("delete from approvals where approval_id = ?", (approval_id,))


        _audit(conn, "approval_deleted", user["user_id"], {"approval_id": approval_id})


        conn.commit()


        return {"ok": True, "approval_id": approval_id}





    @app.post("/approvals/notify-overdue")


    def notify_overdue_approvals(


        body: ApprovalReminderRequest,


        user: dict[str, Any] = Depends(owner_user),


    ) -> dict[str, Any]:


        cutoff = time.time() - max(0, body.max_age_seconds)


        rows = conn.execute(


            """


            select * from approvals


            where status = ? and created_at <= ?


            order by created_at asc


            """,


            ("pending", cutoff),


        ).fetchall()


        approvals = [dict(row) for row in rows]


        if not approvals:


            return {"ok": True, "notified": 0}


        lines = [f"Hermi 有 {len(approvals)} 个审批待处理："]


        for row in approvals[:5]:


            lines.append(f"- {row['summary']}")


        if len(approvals) > 5:


            lines.append(f"- 另有 {len(approvals) - 5} 个")


        app.state.qlos_client.send_qq(


            chat_type="private",


            user_id=body.user_id,


            message="\n".join(lines),


        )


        _audit(


            conn,


            "approval_overdue_notified",


            user["user_id"],


            {"count": len(approvals), "user_id": body.user_id, "max_age_seconds": body.max_age_seconds},


        )


        conn.commit()


        return {"ok": True, "notified": len(approvals)}





    @app.get("/audit-log")


    def audit_log(user: dict[str, Any] = Depends(owner_user)) -> dict[str, Any]:


        rows = conn.execute("select * from audit_log order by created_at desc limit 200").fetchall()


        return {"events": [dict(row) for row in rows]}





    @app.get("/tasks")


    def list_tasks(user: dict[str, Any] = Depends(owner_user)) -> dict[str, Any]:


        rows = conn.execute("select * from tasks order by updated_at desc, created_at desc").fetchall()


        return {"tasks": [dict(row) for row in rows]}





    @app.post("/tasks")


    def create_task(body: TaskCreate, user: dict[str, Any] = Depends(owner_user)) -> dict[str, Any]:


        if body.conversation_id:


            _require_conversation(conn, body.conversation_id)


        task = _create_task(


            conn,


            title=body.title,


            task_type=body.task_type,


            conversation_id=body.conversation_id,


            source="manual",


            created_by=user["user_id"],


            metadata=body.metadata,


        )


        _audit(conn, "task_created", user["user_id"], {"task_id": task["task_id"], "task_type": body.task_type})


        conn.commit()


        return task





    @app.get("/tasks/{task_id}/events")


    def list_task_events(task_id: str, user: dict[str, Any] = Depends(owner_user)) -> dict[str, Any]:


        _task_by_id(conn, task_id)


        rows = conn.execute(


            "select * from task_events where task_id = ? order by created_at asc",


            (task_id,),


        ).fetchall()


        return {"task_id": task_id, "events": [dict(row) for row in rows]}





    @app.post("/tasks/{task_id}/events")


    def create_task_event(


        task_id: str,


        body: TaskEventCreate,


        user: dict[str, Any] = Depends(owner_user),


    ) -> dict[str, Any]:


        _task_by_id(conn, task_id)


        event = _create_task_event(


            conn,


            task_id=task_id,


            event_type=body.event_type,


            content=body.content,


            metadata=body.metadata,


        )


        conn.execute("update tasks set updated_at = ? where task_id = ?", (time.time(), task_id))


        _audit(conn, "task_event_created", user["user_id"], {"task_id": task_id, "event_type": body.event_type})


        conn.commit()


        return event





    @app.post("/code-adapter-runs")


    def create_code_adapter_run(


        body: CodeAdapterRunCreate,


        user: dict[str, Any] = Depends(owner_user),


    ) -> dict[str, Any]:


        zone = _operation_zone_by_id(conn, body.operation_zone_id)


        metadata = {


            "adapter": body.adapter,


            "operation_zone_id": body.operation_zone_id,


            "workspace_path": zone["workspace_path"],


            "mode": body.mode,


            "requires_approval": body.requires_approval,


            "instructions": body.instructions,


        }


        task = _create_task(


            conn,


            title=body.summary,


            task_type="code_adapter",


            conversation_id=None,


            source="code_adapter",


            created_by=user["user_id"],


            metadata=metadata,


            status="pending_approval" if body.requires_approval else "draft",


        )


        _create_task_event(


            conn,


            task_id=task["task_id"],


            event_type="code_adapter.draft",


            content=(


                f"{body.adapter} {body.mode} 草稿已创建，绑定 Operation Zone {body.operation_zone_id}。"


                "默认不执行写入；写文件、执行命令或修改项目必须先经过 owner 审批。"


            ),


            metadata=metadata,


        )


        _audit(


            conn,


            "code_adapter_run_drafted",


            user["user_id"],


            {"task_id": task["task_id"], "adapter": body.adapter, "operation_zone_id": body.operation_zone_id},


        )


        conn.commit()


        return _task_by_id(conn, task["task_id"])





    @app.get("/scheduled-jobs")

    def list_scheduled_jobs(user: dict[str, Any] = Depends(current_user)) -> dict[str, Any]:

        if user.get("can_approve"):

            rows = conn.execute(

                """

                select j.*, coalesce(u.display_name, j.created_by) as created_by_display_name,

                       coalesce(u.role, '') as created_by_role

                from scheduled_jobs j left join users u on u.user_id = j.created_by

                order by j.created_at desc

                """

            ).fetchall()

        else:

            rows = conn.execute(

                """

                select j.*, coalesce(u.display_name, j.created_by) as created_by_display_name,

                       coalesce(u.role, '') as created_by_role

                from scheduled_jobs j left join users u on u.user_id = j.created_by

                where j.created_by = ? order by j.created_at desc

                """,

                (user["user_id"],),

            ).fetchall()

        return {"scheduled_jobs": [dict(row) for row in rows]}





    @app.get("/scheduled-jobs/{job_id}")

    def scheduled_job_detail(job_id: str, user: dict[str, Any] = Depends(current_user)) -> dict[str, Any]:

        job = _scheduled_job_for_user(conn, job_id, user)

        creator = conn.execute("select display_name, role from users where user_id = ?", (job["created_by"],)).fetchone()

        job["created_by_display_name"] = creator["display_name"] if creator else job["created_by"]

        job["created_by_role"] = creator["role"] if creator else ""

        return job




    @app.delete("/scheduled-jobs/{job_id}")

    def delete_scheduled_job(job_id: str, user: dict[str, Any] = Depends(current_user)) -> dict[str, Any]:

        job = _scheduled_job_for_user(conn, job_id, user)

        conn.execute("delete from scheduled_jobs where job_id = ?", (job_id,))

        _audit(conn, "scheduled_job_deleted", user["user_id"], {"job_id": job_id, "task_id": job.get("task_id")})


        conn.commit()


        return {"ok": True, "job_id": job_id}





    @app.post("/scheduled-jobs/{job_id}/pause")


    def pause_scheduled_job(job_id: str, user: dict[str, Any] = Depends(current_user)) -> dict[str, Any]:

        _require_perm("manage_scheduled", user)

        _scheduled_job_for_user(conn, job_id, user)

        conn.execute(


            "update scheduled_jobs set status = ?, updated_at = ? where job_id = ?",


            ("paused", time.time(), job_id),


        )


        _audit(conn, "scheduled_job_paused", user["user_id"], {"job_id": job_id})


        conn.commit()


        return _scheduled_job_by_id(conn, job_id)





    @app.post("/scheduled-jobs/{job_id}/resume")


    def resume_scheduled_job(job_id: str, user: dict[str, Any] = Depends(current_user)) -> dict[str, Any]:

        _require_perm("manage_scheduled", user)

        _scheduled_job_for_user(conn, job_id, user)

        conn.execute(


            "update scheduled_jobs set status = ?, updated_at = ? where job_id = ?",


            ("active", time.time(), job_id),


        )


        _audit(conn, "scheduled_job_resumed", user["user_id"], {"job_id": job_id})


        conn.commit()


        return _scheduled_job_by_id(conn, job_id)





    @app.post("/scheduled-jobs/{job_id}/run-now")


    def run_scheduled_job_now(job_id: str, user: dict[str, Any] = Depends(current_user)) -> dict[str, Any]:

        _require_perm("manage_scheduled", user)

        job = _scheduled_job_for_user(conn, job_id, user)

        result = _execute_due_scheduled_job(conn, app, config, job, time.time(), force=True)


        _audit(conn, "scheduled_job_run_now", user["user_id"], {"job_id": job_id, "status": result.get("status")})


        conn.commit()


        return result





    @app.get("/scheduled-jobs/{job_id}/runs")


    def scheduled_job_runs(job_id: str, user: dict[str, Any] = Depends(current_user)) -> dict[str, Any]:

        _require_perm("manage_scheduled", user)

        job = _scheduled_job_for_user(conn, job_id, user)

        rows = conn.execute(


            "select * from scheduled_job_runs where job_id = ? order by started_at desc limit 100",


            (job_id,),


        ).fetchall()


        return {"job": job, "runs": [dict(row) for row in rows]}





    @app.post("/scheduled-jobs")

    def create_scheduled_job(

        body: ScheduledJobCreate,

        user: dict[str, Any] = Depends(current_user),

    ) -> dict[str, Any]:

        permission = _permission_result("cron", user)

        if permission in {"deny", "owner_only"}:

            raise HTTPException(status_code=403, detail="permission_denied:cron")

        if permission == "approval":

            action = {

                "type": "scheduled.create",

                "kind": body.kind,

                "schedule": body.schedule,

                "summary": body.summary,

                "content": str(body.payload.get("content") or body.payload.get("prompt") or body.summary),

                "target": body.target,

                "payload": body.payload,

                "policy": body.policy,

                "max_retries": body.max_retries,

                "created_by": user["user_id"],

            }

            conversation_id = str(body.target.get("conversation_id") or "").strip()

            if conversation_id:

                _require_conversation_for_user(conn, conversation_id, user)

            else:

                conversation_id = _get_or_create_user_system_conversation(conn, user)

            approval = _create_action_approval(

                conn,

                conversation_id,

                action,

                source="permission",

                summary=f"权限审批：创建定时任务 {body.summary}",

                risk_level="medium",

            )

            _audit(

                conn,

                "permission_approval_created",

                user["user_id"],

                {"approval_id": approval["approval_id"], "permission": "cron", "action_type": "scheduled.create"},

            )

            conn.commit()

            return {"status": "pending_approval", "approval": approval}

        if body.task_id:

            _task_by_id(conn, body.task_id)

            task_id = body.task_id

        else:


            task = _create_task(


                conn,


                title=body.summary,


                task_type="scheduled",


                conversation_id=None,


                source="manual",


                created_by=user["user_id"],


                metadata={"kind": body.kind, "schedule": body.schedule},


            )


            task_id = task["task_id"]


        job = _create_scheduled_job(


            conn,


            task_id=task_id,


            kind=body.kind,


            schedule=body.schedule,


            summary=body.summary,


            target=body.target,


            payload=body.payload,


            created_by=user["user_id"],


            status="active",


            policy=body.policy,


            max_retries=body.max_retries,


        )


        _create_task_event(


            conn,


            task_id=task_id,


            event_type="scheduled_job_created",


            content=f"已创建定时任务：{body.summary} ({body.schedule})",


            metadata={"job_id": job["job_id"]},


        )


        _audit(conn, "scheduled_job_created", user["user_id"], {"job_id": job["job_id"], "task_id": task_id})


        conn.commit()


        return job





    @app.post("/scheduler/run-once")

    def scheduler_run_once(user: dict[str, Any] = Depends(owner_user)) -> dict[str, Any]:

        return _run_due_scheduled_jobs(conn, app, config, actor_user_id=user["user_id"])




    @app.get("/prompt-cards")


    def list_prompt_cards(user: dict[str, Any] = Depends(owner_user)) -> dict[str, Any]:


        rows = conn.execute("select * from prompt_cards order by created_at desc").fetchall()


        return {"prompt_cards": [dict(row) for row in rows]}





    @app.post("/prompt-cards")


    def create_prompt_card(body: PromptCardCreate, user: dict[str, Any] = Depends(owner_user)) -> dict[str, Any]:


        now = time.time()


        card_id = f"pcard-{uuid.uuid4().hex[:12]}"


        conn.execute(


            """


            insert into prompt_cards (


              card_id, name, card_type, content, enabled, created_at, updated_at, metadata_json


            ) values (?, ?, ?, ?, ?, ?, ?, ?)


            """,


            (


                card_id,


                body.name,


                body.card_type,


                body.content,


                1 if body.enabled else 0,


                now,


                now,


                json.dumps(body.metadata, ensure_ascii=False),


            ),


        )


        _audit(conn, "prompt_card_created", user["user_id"], {"card_id": card_id, "card_type": body.card_type})


        conn.commit()


        return dict(conn.execute("select * from prompt_cards where card_id = ?", (card_id,)).fetchone())





    @app.get("/prompt-bindings")


    def list_prompt_bindings(user: dict[str, Any] = Depends(owner_user)) -> dict[str, Any]:


        rows = conn.execute(


            """


            select b.*, c.name as card_name, c.card_type as card_type


            from prompt_bindings b


            left join prompt_cards c on c.card_id = b.card_id


            order by b.priority asc, b.created_at desc


            """


        ).fetchall()


        return {"prompt_bindings": [dict(row) for row in rows]}





    @app.post("/prompt-bindings")


    def create_prompt_binding(body: PromptBindingCreate, user: dict[str, Any] = Depends(owner_user)) -> dict[str, Any]:


        row = conn.execute("select * from prompt_cards where card_id = ?", (body.card_id,)).fetchone()


        if not row:


            raise HTTPException(status_code=404, detail="prompt_card_not_found")


        now = time.time()


        binding_id = f"pbind-{uuid.uuid4().hex[:12]}"


        conn.execute(


            """


            insert into prompt_bindings (


              binding_id, card_id, scope_type, scope_id, priority, enabled,


              created_at, updated_at, metadata_json


            ) values (?, ?, ?, ?, ?, ?, ?, ?, ?)


            """,


            (


                binding_id,


                body.card_id,


                body.scope_type,


                body.scope_id,


                body.priority,


                1 if body.enabled else 0,


                now,


                now,


                json.dumps(body.metadata, ensure_ascii=False),


            ),


        )


        _audit(conn, "prompt_binding_created", user["user_id"], {"binding_id": binding_id, "scope_id": body.scope_id})


        conn.commit()


        return dict(conn.execute("select * from prompt_bindings where binding_id = ?", (binding_id,)).fetchone())





    @app.post("/prompt-renders/preview")


    def prompt_render_preview(body: PromptRenderPreview, user: dict[str, Any] = Depends(owner_user)) -> dict[str, Any]:


        rows = conn.execute(


            "select * from prompt_cards where enabled = 1 order by created_at asc",


        ).fetchall()


        agent_name = body.agent_name or _active_profile_name(conn, config)

        prompt = _render_prompt_preview([dict(row) for row in rows], channel=body.channel, room_id=body.room_id, agent_name=agent_name)


        render_id = f"prender-{uuid.uuid4().hex[:12]}"


        conn.execute(


            """


            insert into prompt_renders (render_id, conversation_id, task_id, render_type, content, created_at, metadata_json)


            values (?, ?, ?, ?, ?, ?, ?)


            """,


            (


                render_id,


                None,


                None,


                "preview",


                prompt,


                time.time(),


                json.dumps(body.model_dump(), ensure_ascii=False),


            ),


        )


        conn.commit()


        return {"render_id": render_id, "mode": "supplemental", "prompt": prompt}





    @app.get("/capabilities")


    def list_capabilities(user: dict[str, Any] = Depends(current_user)) -> dict[str, Any]:
        rows = conn.execute(


            "select * from capability_registry order by risk_level desc, capability_id asc"


        ).fetchall()


        return {
            "capabilities": [_public_capability(dict(row)) for row in rows],
            "reserved_capabilities": RESERVED_CAPABILITIES,
            "skill_capabilities": SKILL_CAPABILITIES,
        }





    @app.post("/actions/validate")


    def validate_action(


        body: dict[str, Any] = Body(...),


        user: dict[str, Any] = Depends(owner_user),


    ) -> dict[str, Any]:


        validated = _validate_action_payload(body)


        return {"ok": True, "capability_id": validated["capability_id"], "normalized": validated["action"]}





    @app.get("/channel-events")


    def list_channel_events(user: dict[str, Any] = Depends(owner_user)) -> dict[str, Any]:


        rows = conn.execute("select * from channel_events order by created_at desc limit 200").fetchall()


        return {"channel_events": [dict(row) for row in rows]}





    @app.post("/channel-events")


    def create_channel_event(body: ChannelEventCreate, user: dict[str, Any] = Depends(owner_user)) -> dict[str, Any]:


        if body.task_id:


            _task_by_id(conn, body.task_id)


        event_id = f"chan-{uuid.uuid4().hex[:12]}"


        conn.execute(


            """


            insert into channel_events (


              event_id, channel, source_id, direction, envelope_json, task_id, created_at, metadata_json


            ) values (?, ?, ?, ?, ?, ?, ?, ?)


            """,


            (


                event_id,


                body.channel,


                body.source_id,


                body.direction,


                json.dumps(body.envelope, ensure_ascii=False),


                body.task_id,


                time.time(),


                json.dumps(body.metadata, ensure_ascii=False),


            ),


        )


        _audit(conn, "channel_event_created", user["user_id"], {"event_id": event_id, "channel": body.channel})


        conn.commit()


        return dict(conn.execute("select * from channel_events where event_id = ?", (event_id,)).fetchone())





    @app.get("/qq-adapter/envelope/schema")


    def qq_adapter_envelope_schema(user: dict[str, Any] = Depends(current_user)) -> dict[str, Any]:


        _require_perm("admin_config", user)


        return {


            "fields": CHANNEL_ENVELOPE_FIELDS,


            "sources": ["qq", "hermi_web", "hermi_pwa", "api", "remote_agent"],


            "transports": ["napcat_onebot", "web", "pwa", "http_api", "remote_agent"],


            "default_profile": _active_profile_name(conn, config),

        }





    @app.post("/qq-adapter/envelope/normalize")


    def qq_adapter_envelope_normalize(


        body: ChannelEnvelopeCreate,


        user: dict[str, Any] = Depends(owner_user),


    ) -> dict[str, Any]:


        payload = body.model_dump() if hasattr(body, "model_dump") else body.dict()


        envelope = normalize_channel_envelope(

            payload, default_profile=_profile_display_name(conn, config.qq_profile_id)

        )

        return {"ok": True, "envelope": envelope}





    def _usage_rows_for_period(user_id: str | None, period: Literal["7d", "30d", "all"]) -> list[dict[str, Any]]:

        clauses: list[str] = []
        params: list[Any] = []
        if user_id:
            clauses.append("user_id = ?")
            params.append(user_id)
        if period != "all":
            days = 7 if period == "7d" else 30
            clauses.append("day >= ?")
            params.append((date.today() - timedelta(days=days - 1)).isoformat())
        where = f" where {' and '.join(clauses)}" if clauses else ""
        rows = conn.execute(f"select * from usage_daily{where} order by day desc", params).fetchall()
        return [dict(row) for row in rows]


    @app.get("/usage")

    def usage(
        period: Literal["7d", "30d", "all"] = "7d",
        user: dict[str, Any] = Depends(current_user),
    ) -> dict[str, Any]:

        _require_perm("view_all_conversations", user)

        return {"period": period, "usage": _usage_rows_for_period(None, period)}



    @app.get("/usage/{user_id}")

    def usage_for_user(
        user_id: str,
        period: Literal["7d", "30d", "all"] = "7d",
        user: dict[str, Any] = Depends(current_user),
    ) -> dict[str, Any]:

        if user_id != user["user_id"]:

            _require_perm("view_all_conversations", user)

        target = conn.execute("select * from users where user_id = ?", (user_id,)).fetchone()

        if not target:

            raise HTTPException(status_code=404, detail="user_not_found")

        return {

            "user_id": user_id,

            "period": period,

            "usage": _usage_rows_for_period(user_id, period),

            "quota_window": _quota_window_summary(conn, dict(target), config),

        }




    register_admin_routes(

        app,

        conn=conn,

        current_user=current_user,

        owner_user=owner_user,

        require_perm=_require_perm,

        audit=_audit,

    )

    register_symbiosis_routes(
        app,
        conn=conn,
        current_user=current_user,
        owner_user=owner_user,
        audit=_audit,
    )




    @app.get("/qq/recent")


    def recent_qq(user: dict[str, Any] = Depends(owner_user)) -> dict[str, Any]:


        return {"context": load_recent_qq_context(config.qlos_log_dir, limit=50)}





    @app.get("/files")

    def list_files(user: dict[str, Any] = Depends(current_user)) -> dict[str, Any]:

        _require_perm("media", user)

        if user.get("can_approve"):

            rows = conn.execute("select * from media_files order by created_at desc").fetchall()


        else:


            rows = conn.execute(


                """


                select * from media_files


                where created_by = ? or visibility = ?


                order by created_at desc


                """,


                (user["user_id"], "shared"),


            ).fetchall()


        return {"files": [_public_file(dict(row)) for row in rows]}





    @app.post("/files")


    async def upload_file(


        upload: UploadFile = File(...),


        conversation_id: str | None = Form(default=None),


        source_channel: str = Form(default="hermi"),


        visibility: str = Form(default="private"),


        user: dict[str, Any] = Depends(current_user),


    ) -> dict[str, Any]:


        _require_perm("media", user)


        if visibility not in {"private", "shared"}:


            raise HTTPException(status_code=400, detail="invalid_visibility")


        if conversation_id:


            _require_conversation_for_user(conn, conversation_id, user)


        file_bytes = await upload.read()


        if not file_bytes:


            raise HTTPException(status_code=400, detail="empty_file")


        if len(file_bytes) > 25 * 1024 * 1024:


            raise HTTPException(status_code=413, detail="file_too_large")


        file_limit = _file_limit_for_user(user, config)


        if file_limit is not None and len(file_bytes) > file_limit:


            raise HTTPException(status_code=413, detail="file_quota_exceeded")


        now = time.time()


        file_id = f"file-{uuid.uuid4().hex[:12]}"


        original_name = _safe_filename(upload.filename or "upload.bin")


        digest = hashlib.sha256(file_bytes).hexdigest()


        suffix = Path(original_name).suffix[:20]


        storage_path = _media_dir(config) / f"{file_id}{suffix}"


        storage_path.write_bytes(file_bytes)


        conn.execute(


            """


            insert into media_files (


              file_id, conversation_id, source_channel, source_message_id, original_name,


              mime, size_bytes, sha256, storage_path, visibility, created_by,


              expires_at, created_at, metadata_json


            ) values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)


            """,


            (


                file_id,


                conversation_id,


                source_channel,


                None,


                original_name,


                upload.content_type or "application/octet-stream",


                len(file_bytes),


                digest,


                str(storage_path),


                visibility,


                user["user_id"],


                None,


                now,


                json.dumps({"safe_name": original_name}, ensure_ascii=False),


            ),


        )

        _increment_usage(conn, user["user_id"], file_uploads=1)

        _increment_quota_window_usage(conn, user, file_uploads=1, config=config)

        if conversation_id:


            _insert_message(


                conn,


                conversation_id,


                "system",


                f"已上传文件：{original_name} ({file_id})",


                "hermi",


                metadata={"file_id": file_id},


            )


            conn.execute(


                "update conversations set updated_at = ? where conversation_id = ?",


                (now, conversation_id),


            )


        _audit(conn, "file_uploaded", user["user_id"], {"file_id": file_id, "size_bytes": len(file_bytes)})


        conn.commit()


        return _public_file(_file_by_id(conn, file_id))





    @app.get("/files/{file_id}")


    def get_file(file_id: str, user: dict[str, Any] = Depends(current_user)) -> dict[str, Any]:


        _require_perm("media", user)


        return _public_file(_file_for_user(conn, file_id, user))





    @app.get("/files/{file_id}/content")


    def download_file(file_id: str, user: dict[str, Any] = Depends(current_user)) -> FileResponse:


        _require_perm("media", user)


        row = _file_for_user(conn, file_id, user)


        if not row["storage_path"]:


            raise HTTPException(status_code=404, detail="file_blob_not_found")


        path = Path(row["storage_path"])


        if not path.exists():


            raise HTTPException(status_code=404, detail="file_blob_not_found")


        return FileResponse(path, media_type=row["mime"], filename=row["original_name"])





    @app.get("/files/node-artifacts/{artifact_id}/content")

    def download_node_artifact(artifact_id: str, user: dict[str, Any] = Depends(owner_user)) -> FileResponse:

        row = conn.execute("select * from node_job_artifacts where artifact_id = ?", (artifact_id,)).fetchone()


        if not row:


            raise HTTPException(status_code=404, detail="artifact_not_found")


        artifact = dict(row)


        path = Path(str(artifact.get("storage_path") or ""))


        if not path.exists() or not path.is_file():


            raise HTTPException(status_code=404, detail="artifact_blob_not_found")


        return FileResponse(path, media_type=artifact["mime"], filename=artifact["original_name"])





    @app.delete("/files/{file_id}")


    def delete_file(file_id: str, user: dict[str, Any] = Depends(current_user)) -> dict[str, Any]:

        _require_perm("media", user)

        row = _owned_file_for_user(conn, file_id, user)

        path = Path(row["storage_path"]) if row["storage_path"] else None


        if path and path.exists() and path.is_file():


            path.unlink()


        conn.execute("delete from media_files where file_id = ?", (file_id,))


        _audit(conn, "file_deleted", user["user_id"], {"file_id": file_id})


        conn.commit()


        return {"ok": True, "file_id": file_id}





    @app.post("/ops/services/{service}/action")


    async def service_action(


        service: str,


        request: Request,


        user: dict[str, Any] = Depends(owner_user),


    ) -> dict[str, Any]:


        payload = await request.json()


        action = str(payload.get("action") or "")


        if action not in {"status", "start", "stop", "restart"}:


            raise HTTPException(status_code=400, detail="invalid_action")


        return {"ok": True, "service": service, "action": action, "mode": "audit-only"}





    @app.get("/operation-zones")


    def list_operation_zones(user: dict[str, Any] = Depends(owner_user)) -> dict[str, Any]:


        rows = conn.execute("select * from operation_zones order by created_at desc").fetchall()


        return {"operation_zones": [dict(row) for row in rows]}





    @app.post("/operation-zones")


    def create_operation_zone(body: OperationZoneCreate, user: dict[str, Any] = Depends(owner_user)) -> dict[str, Any]:


        workspace = _resolve_operation_workspace(config, body.workspace_path)


        now = time.time()


        zone_id = f"zone-{uuid.uuid4().hex[:12]}"


        conn.execute(


            """


            insert into operation_zones (


              zone_id, node_id, workspace_path, allowed_tools_json, denied_paths_json,


              permission_level, requires_approval, created_by, created_at, updated_at


            ) values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)


            """,


            (


                zone_id,


                body.node_id,


                str(workspace),


                json.dumps(body.allowed_tools, ensure_ascii=False),


                json.dumps(body.denied_paths, ensure_ascii=False),


                body.permission_level,


                1 if body.requires_approval else 0,


                user["user_id"],


                now,


                now,


            ),


        )


        _audit(conn, "operation_zone_created", user["user_id"], {"zone_id": zone_id, "workspace_path": str(workspace)})


        conn.commit()


        return dict(conn.execute("select * from operation_zones where zone_id = ?", (zone_id,)).fetchone())





    @app.post("/operation-zones/{zone_id}/actions")


    def operation_zone_action(


        zone_id: str,


        body: OperationAction,


        user: dict[str, Any] = Depends(owner_user),


    ) -> dict[str, Any]:


        zone = _operation_zone_by_id(conn, zone_id)


        allowed = set(_json_list(zone.get("allowed_tools_json")))


        if body.action not in allowed:


            raise HTTPException(status_code=403, detail="operation_tool_not_allowed")


        workspace = Path(zone["workspace_path"]).resolve()


        target = _resolve_inside_workspace(workspace, body.path)


        if body.action == "list":


            if not target.is_dir():


                raise HTTPException(status_code=400, detail="not_a_directory")


            output = "\n".join(sorted(item.name for item in target.iterdir()))


        elif body.action == "read":


            if not target.is_file():


                raise HTTPException(status_code=400, detail="not_a_file")


            output = target.read_text(encoding="utf-8", errors="replace")[:20000]


        elif body.action == "git_status":


            output = _run_whitelisted_command(["git", "status", "--short"], workspace)


        else:


            raise HTTPException(status_code=403, detail="operation_tool_not_allowed")


        _operation_log(conn, zone_id, body.action, "ok", {"path": body.path, "output_preview": output[:1000]})


        conn.commit()


        return {"zone_id": zone_id, "action": body.action, "output": output}





    @app.get("/agents")


    def list_agents(user: dict[str, Any] = Depends(owner_user)) -> dict[str, Any]:


        rows = conn.execute("select * from agents order by created_at asc").fetchall()


        return {"agents": [dict(row) for row in rows]}





    @app.post("/agents")


    def create_agent(body: AgentCreate, user: dict[str, Any] = Depends(owner_user)) -> dict[str, Any]:


        now = time.time()


        agent_id = f"agent-{uuid.uuid4().hex[:12]}"


        conn.execute(


            """


            insert into agents (


              agent_id, name, agent_type, description, config_json, created_at, updated_at


            ) values (?, ?, ?, ?, ?, ?, ?)


            """,


            (


                agent_id,


                body.name,


                body.agent_type,


                body.description,


                json.dumps(body.config, ensure_ascii=False),


                now,


                now,


            ),


        )


        _audit(conn, "agent_created", user["user_id"], {"agent_id": agent_id, "agent_type": body.agent_type})


        conn.commit()


        return dict(conn.execute("select * from agents where agent_id = ?", (agent_id,)).fetchone())





    @app.get("/rooms")

    def list_rooms(user: dict[str, Any] = Depends(owner_user)) -> dict[str, Any]:

        rows = conn.execute("select * from rooms order by created_at asc").fetchall()

        return {"rooms": [dict(row) for row in rows]}



    @app.get("/rooms/{room_id}")

    def get_room(room_id: str, user: dict[str, Any] = Depends(owner_user)) -> dict[str, Any]:

        room = _room_by_id(conn, room_id)

        room["members"] = _room_members(conn, room_id)

        latest = conn.execute(

            "select * from workflow_runs where room_id = ? order by created_at desc limit 1",

            (room_id,),

        ).fetchone()

        room["latest_run"] = _public_workflow_run(conn, dict(latest)) if latest else None

        return room



    @app.get("/rooms/{room_id}/export")

    def export_room(room_id: str, user: dict[str, Any] = Depends(owner_user)) -> dict[str, Any]:

        room = _room_by_id(conn, room_id)

        members = _room_members(conn, room_id)

        runs = []

        for row in conn.execute(

            "select * from workflow_runs where room_id = ? order by created_at asc", (room_id,)

        ).fetchall():

            public_run = _public_workflow_run(conn, dict(row))

            public_run["steps"] = [

                _public_workflow_step(conn, dict(step))

                for step in conn.execute(

                    "select * from workflow_steps where run_id = ? order by step_index asc",

                    (row["run_id"],),

                ).fetchall()

            ]

            runs.append(public_run)

        safe_room = {key: room.get(key) for key in (

            "room_id", "name", "room_type", "mode", "host_agent_id", "permission_level",

            "history_policy", "max_turns", "created_at", "updated_at",

        )}

        _audit(conn, "room_exported", user["user_id"], {"room_id": room_id, "run_count": len(runs)})

        conn.commit()

        return {"schema_version": 1, "room": safe_room, "members": members, "runs": runs}




    @app.get("/meeting-presets")


    def meeting_presets(user: dict[str, Any] = Depends(current_user)) -> dict[str, Any]:


        _require_perm("admin_config", user)


        return {"roles": MEETING_ROLE_PRESETS, "modes": MEETING_MODE_PRESETS}





    @app.get("/profiles")

    def list_profiles(user: dict[str, Any] = Depends(current_user)) -> dict[str, Any]:

        _require_perm("admin_config", user)

        return {"profiles": _profile_registry_with_settings(conn, config)}



    @app.patch("/profiles/{profile_id}")

    def update_profile_display_name(

        profile_id: str,

        body: ProfileDisplayNamePatch,

        user: dict[str, Any] = Depends(owner_user),

    ) -> dict[str, Any]:

        profiles = _profile_registry(config)

        profile = next((item for item in profiles if item["profile_id"] == profile_id), None)

        if not profile:

            raise HTTPException(status_code=404, detail="profile_not_found")

        display_name = body.display_name.strip()

        conn.execute(

            """

            insert into profile_settings (profile_id, display_name, customized, updated_at)

            values (?, ?, 1, ?)

            on conflict(profile_id) do update set

              display_name = excluded.display_name, customized = 1, updated_at = excluded.updated_at

            """,

            (profile_id, display_name, time.time()),

        )

        _sync_profile_agents(conn, config)

        _audit(conn, "profile_display_name_updated", user["user_id"], {"profile_id": profile_id, "display_name": display_name})

        conn.commit()

        return next(item for item in _profile_registry_with_settings(conn, config) if item["profile_id"] == profile_id)




    @app.get("/brain/status")


    def brain_status(user: dict[str, Any] = Depends(owner_user)) -> dict[str, Any]:

        return {

            "active_brain": "hermes_api" if config.hermes_api_url else "none",

            "default_profile": _profile_display_name(conn, config.hermi_profile_id),

            "channel_profiles": {

                "qq": config.qq_profile_id,

                "hermi": config.hermi_profile_id,

                "meeting_host": config.meeting_host_profile_id,

            },

            "profiles": _profile_registry_with_settings(conn, config),

            "adapters": _brain_adapter_status(config),


        }





    @app.post("/rooms")

    def create_room(body: RoomCreate, user: dict[str, Any] = Depends(owner_user)) -> dict[str, Any]:

        host_agent_id = body.host_agent_id

        if not host_agent_id:

            candidate = f"profile:{config.meeting_host_profile_id}"

            if conn.execute("select 1 from agents where agent_id = ?", (candidate,)).fetchone():

                host_agent_id = candidate

        if host_agent_id:

            _agent_by_id(conn, host_agent_id)

        now = time.time()

        room_id = f"room-{uuid.uuid4().hex[:12]}"


        conn.execute(


            """

            insert into rooms (

              room_id, name, room_type, mode, host_agent_id, permission_level,

              history_policy, max_turns, settings_json, created_at, updated_at

            ) values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)

            """,

            (

                room_id, body.name, body.room_type, body.mode,

                host_agent_id, body.permission_level, body.history_policy,

                1 if _normalize_meeting_mode(body.mode) == "auto_single" else body.max_turns,

                json.dumps(body.settings, ensure_ascii=False), now, now,

            ),

        )

        if host_agent_id:

            conn.execute(

                "insert into room_members (room_id, agent_id, role, joined_at) values (?, ?, 'host', ?)",

                (room_id, host_agent_id, now),

            )

        _audit(conn, "room_created", user["user_id"], {"room_id": room_id, "mode": body.mode})

        conn.commit()


        return dict(conn.execute("select * from rooms where room_id = ?", (room_id,)).fetchone())



    @app.patch("/rooms/{room_id}")

    def update_room(

        room_id: str,

        body: RoomPatch,

        user: dict[str, Any] = Depends(owner_user),

    ) -> dict[str, Any]:

        current = _room_by_id(conn, room_id)

        values = body.model_dump(exclude_none=True) if hasattr(body, "model_dump") else body.dict(exclude_none=True)

        if values.get("host_agent_id"):

            _agent_by_id(conn, values["host_agent_id"])

        if "mode" in values:

            values["mode"] = _normalize_meeting_mode(values["mode"])

        if "settings" in values:

            values["settings_json"] = json.dumps(values.pop("settings"), ensure_ascii=False)

        allowed = {"name", "mode", "host_agent_id", "permission_level", "history_policy", "max_turns", "settings_json"}

        updates = {key: value for key, value in values.items() if key in allowed}

        if updates:

            assignments = ", ".join(f"{key} = ?" for key in updates)

            conn.execute(

                f"update rooms set {assignments}, updated_at = ? where room_id = ?",

                (*updates.values(), time.time(), room_id),

            )

            _audit(conn, "room_updated", user["user_id"], {"room_id": room_id, "fields": list(updates)})

            conn.commit()

        return _room_by_id(conn, room_id)



    @app.delete("/rooms/{room_id}")

    def delete_room(room_id: str, user: dict[str, Any] = Depends(owner_user)) -> dict[str, Any]:

        _room_by_id(conn, room_id)

        runs = room_runs(conn, room_id)

        if not can_delete_room(runs):

            raise HTTPException(status_code=409, detail="cancel_meeting_before_delete")

        run_ids = [row["run_id"] for row in runs]

        for run_id in run_ids:

            conn.execute("delete from workflow_steps where run_id = ?", (run_id,))

        conn.execute("delete from workflow_runs where room_id = ?", (room_id,))

        conn.execute("delete from room_members where room_id = ?", (room_id,))

        conn.execute("delete from rooms where room_id = ?", (room_id,))

        _audit(conn, "room_deleted", user["user_id"], {"room_id": room_id, "run_count": len(run_ids)})

        conn.commit()

        return {"ok": True, "room_id": room_id}




    @app.post("/rooms/{room_id}/members")


    def add_room_member(

        room_id: str,


        body: RoomMemberCreate,


        user: dict[str, Any] = Depends(owner_user),


    ) -> dict[str, Any]:


        _room_by_id(conn, room_id)


        _agent_by_id(conn, body.agent_id)


        now = time.time()


        conn.execute(


            """


            insert into room_members (room_id, agent_id, role, joined_at)


            values (?, ?, ?, ?)


            on conflict(room_id, agent_id) do update set role = excluded.role


            """,


            (room_id, body.agent_id, body.role, now),


        )


        _audit(conn, "room_member_added", user["user_id"], {"room_id": room_id, "agent_id": body.agent_id})


        conn.commit()


        return dict(

            conn.execute(

                "select * from room_members where room_id = ? and agent_id = ?",

                (room_id, body.agent_id),

            ).fetchone()

        )



    @app.delete("/rooms/{room_id}/members/{agent_id}")

    def remove_room_member(

        room_id: str,

        agent_id: str,

        user: dict[str, Any] = Depends(owner_user),

    ) -> dict[str, Any]:

        room = _room_by_id(conn, room_id)

        if room.get("host_agent_id") == agent_id:

            raise HTTPException(status_code=409, detail="cannot_remove_room_host")

        deleted = conn.execute(

            "delete from room_members where room_id = ? and agent_id = ?",

            (room_id, agent_id),

        )

        if deleted.rowcount != 1:

            raise HTTPException(status_code=404, detail="room_member_not_found")

        _audit(conn, "room_member_removed", user["user_id"], {"room_id": room_id, "agent_id": agent_id})

        conn.commit()

        return {"ok": True, "room_id": room_id, "agent_id": agent_id}



    @app.post("/rooms/{room_id}/workflows")

    def run_room_workflow(

        room_id: str,


        body: WorkflowRunCreate,


        user: dict[str, Any] = Depends(owner_user),


    ) -> dict[str, Any]:


        room = _room_by_id(conn, room_id)

        mode = _normalize_meeting_mode(body.mode or room.get("mode"))

        members = _room_members(conn, room_id)

        participants = [item for item in members if item["agent_id"] != room.get("host_agent_id")]

        if mode == "pair_review" and len(participants) != 2:

            raise HTTPException(status_code=400, detail="pair_review_requires_two_participants")

        if mode == "project_meeting" and len(members) < 2:

            raise HTTPException(status_code=400, detail="project_meeting_requires_two_members")

        run = _create_workflow_run(conn, room_id=room_id, mode=mode, topic=body.topic, max_turns=body.max_turns)

        conn.commit()

        if mode in MEETING_MODE_IDS:

            real_profiles = all(

                item.get("agent_type") == "hermes_profile"

                and str(item.get("agent_id") or "").startswith("profile:")

                for item in members

            )

            if real_profiles and body.background:

                _start_workflow_thread(

                    app,

                    config,

                    run,

                    room,

                )

            elif real_profiles:

                _run_room_workflow(

                    conn, app.state.hermes_adapter, run["run_id"], room, body.topic,

                    mode, 1 if mode == "auto_single" else max(1, body.max_turns),

                )

            else:

                _run_room_workflow_skeleton(

                    conn, run["run_id"], room_id, body.topic, mode, max(1, body.max_turns)

                )

            if not body.background:

                conn.execute(

                    "update workflow_runs set status = ?, updated_at = ? where run_id = ?",

                    ("completed", time.time(), run["run_id"]),

                )

        _audit(conn, "workflow_run_created", user["user_id"], {"run_id": run["run_id"], "mode": body.mode})


        conn.commit()


        return dict(conn.execute("select * from workflow_runs where run_id = ?", (run["run_id"],)).fetchone())



    @app.get("/rooms/{room_id}/workflows")

    def list_room_workflows(room_id: str, user: dict[str, Any] = Depends(owner_user)) -> dict[str, Any]:

        _room_by_id(conn, room_id)

        rows = conn.execute(

            "select * from workflow_runs where room_id = ? order by created_at desc",

            (room_id,),

        ).fetchall()

        return {"room_id": room_id, "runs": [_public_workflow_run(conn, dict(row)) for row in rows]}



    @app.get("/workflow-runs/{run_id}")

    def get_workflow_run(run_id: str, user: dict[str, Any] = Depends(owner_user)) -> dict[str, Any]:

        row = conn.execute("select * from workflow_runs where run_id = ?", (run_id,)).fetchone()

        if not row:

            raise HTTPException(status_code=404, detail="workflow_run_not_found")

        return _public_workflow_run(conn, dict(row))



    @app.post("/workflow-runs/{run_id}/stop")

    def stop_workflow_run(run_id: str, user: dict[str, Any] = Depends(owner_user)) -> dict[str, Any]:

        row = conn.execute("select * from workflow_runs where run_id = ?", (run_id,)).fetchone()

        if not row:

            raise HTTPException(status_code=404, detail="workflow_run_not_found")

        if row["status"] == "running":

            status = next_run_status(str(row["status"]), "stop")

            conn.execute(

                "update workflow_runs set status = ?, updated_at = ? where run_id = ?",

                (status, time.time(), run_id),

            )

            conn.commit()

        return dict(conn.execute("select * from workflow_runs where run_id = ?", (run_id,)).fetchone())



    @app.post("/workflow-runs/{run_id}/resume")

    def resume_workflow_run(run_id: str, user: dict[str, Any] = Depends(owner_user)) -> dict[str, Any]:

        row = conn.execute("select * from workflow_runs where run_id = ?", (run_id,)).fetchone()

        if not row:

            raise HTTPException(status_code=404, detail="workflow_run_not_found")

        if row["status"] == "paused":

            state = _safe_json_dict(str(row["state_json"] or "{}"))

            state.update(

                {

                    "recoverable": False,

                    "reason": "",

                    "recovery_count": int(state.get("recovery_count") or 0) + 1,

                }

            )

            conn.execute(

                "update workflow_runs set status = 'running', state_json = ?, updated_at = ? where run_id = ?",

                (json.dumps(state, ensure_ascii=False), time.time(), run_id),

            )

            conn.commit()

            thread = app.state.workflow_threads.get(run_id)

            if not thread or not thread.is_alive():

                room = _room_by_id(conn, str(row["room_id"]))

                _start_workflow_thread(app, config, dict(row), room)

        return dict(conn.execute("select * from workflow_runs where run_id = ?", (run_id,)).fetchone())



    @app.post("/workflow-runs/{run_id}/cancel")

    def cancel_workflow_run(run_id: str, user: dict[str, Any] = Depends(owner_user)) -> dict[str, Any]:

        row = conn.execute("select * from workflow_runs where run_id = ?", (run_id,)).fetchone()

        if not row:

            raise HTTPException(status_code=404, detail="workflow_run_not_found")

        if row["status"] in {"running", "paused"}:

            status = next_run_status(str(row["status"]), "cancel")

            conn.execute(

                "update workflow_runs set status = ?, updated_at = ? where run_id = ?",

                (status, time.time(), run_id),

            )

            _audit(conn, "workflow_run_cancelled", user["user_id"], {"run_id": run_id, "room_id": row["room_id"]})

            conn.commit()

        return _public_workflow_run(conn, dict(conn.execute("select * from workflow_runs where run_id = ?", (run_id,)).fetchone()))




    @app.get("/workflow-runs/{run_id}/steps")


    def list_workflow_steps(run_id: str, user: dict[str, Any] = Depends(owner_user)) -> dict[str, Any]:

        row = conn.execute("select * from workflow_runs where run_id = ?", (run_id,)).fetchone()


        if not row:


            raise HTTPException(status_code=404, detail="workflow_run_not_found")


        rows = conn.execute(


            "select * from workflow_steps where run_id = ? order by step_index asc",


            (run_id,),


        ).fetchall()


        return {

            "run_id": run_id,

            "steps": [_public_workflow_step(conn, dict(item)) for item in rows],

        }




    @app.get("/nodes")


    def list_nodes(user: dict[str, Any] = Depends(owner_user)) -> dict[str, Any]:


        rows = conn.execute("select * from nodes order by updated_at desc, created_at desc").fetchall()


        return {"nodes": [_public_node(dict(row)) for row in rows]}





    @app.post("/nodes/register")


    def register_node(body: NodeRegister, user: dict[str, Any] = Depends(owner_user)) -> dict[str, Any]:


        node_id = _safe_node_id(body.node_id)


        if not node_id:


            raise HTTPException(status_code=400, detail="node_id_required")


        now = time.time()


        node_token = f"node-{uuid.uuid4().hex}"


        conn.execute(


            """


            insert into nodes (


              node_id, name, status, endpoint, last_seen_at, metadata_json,


              token, capabilities_json, policy_json, created_by, created_at, updated_at


            ) values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)


            on conflict(node_id) do update set


              name = excluded.name,


              status = excluded.status,


              token = excluded.token,


              capabilities_json = excluded.capabilities_json,


              policy_json = excluded.policy_json,


              updated_at = excluded.updated_at


            """,


            (


                node_id,


                body.name.strip() or node_id,


                "registered",


                "",


                None,


                "{}",


                node_token,


                json.dumps(body.capabilities, ensure_ascii=False),


                json.dumps(body.policy, ensure_ascii=False),


                user["user_id"],


                now,


                now,


            ),


        )


        _audit(conn, "node_registered", user["user_id"], {"node_id": node_id})


        conn.commit()


        node = dict(conn.execute("select * from nodes where node_id = ?", (node_id,)).fetchone())


        return {**_public_node(node), "node_token": node_token}





    @app.post("/nodes/{node_id}/heartbeat")


    def node_heartbeat(node_id: str, node: dict[str, Any] = Depends(node_auth)) -> dict[str, Any]:


        if node["node_id"] != node_id:


            raise HTTPException(status_code=403, detail="node_mismatch")


        now = time.time()


        conn.execute(


            "update nodes set status = ?, last_seen_at = ?, updated_at = ? where node_id = ?",


            ("online", now, now, node_id),


        )


        conn.commit()


        return {"ok": True, "node_id": node_id, "status": "online", "last_seen_at": now}





    @app.post("/nodes/{node_id}/jobs")


    def create_node_job(


        node_id: str,


        body: NodeJobCreate,


        user: dict[str, Any] = Depends(owner_user),


    ) -> dict[str, Any]:


        _node_by_id(conn, node_id)


        now = time.time()


        job_id = f"nodejob-{uuid.uuid4().hex[:12]}"


        conn.execute(


            """


            insert into node_jobs (


              job_id, node_id, summary, status, payload_json, result_json,


              created_by, claimed_at, completed_at, created_at, updated_at


            ) values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)


            """,


            (


                job_id,


                node_id,


                body.summary.strip() or "未命名节点任务",


                "queued",


                json.dumps(body.payload, ensure_ascii=False),


                "{}",


                user["user_id"],


                None,


                None,


                now,


                now,


            ),


        )


        _audit(conn, "node_job_created", user["user_id"], {"job_id": job_id, "node_id": node_id})


        conn.commit()


        return _node_job_by_id(conn, job_id)





    @app.get("/nodes/{node_id}/jobs/next")


    def next_node_job(node_id: str, node: dict[str, Any] = Depends(node_auth)) -> dict[str, Any]:


        if node["node_id"] != node_id:


            raise HTTPException(status_code=403, detail="node_mismatch")


        row = conn.execute(


            "select * from node_jobs where node_id = ? and status = ? order by created_at asc limit 1",


            (node_id, "queued"),


        ).fetchone()


        if not row:


            return {"job": None}


        now = time.time()


        conn.execute(


            "update node_jobs set status = ?, claimed_at = ?, updated_at = ? where job_id = ?",


            ("claimed", now, now, row["job_id"]),


        )


        conn.commit()


        return {"job": _node_job_by_id(conn, row["job_id"])}





    @app.post("/jobs/{job_id}/logs")


    def append_node_job_log(


        job_id: str,


        body: NodeJobLogCreate,


        node: dict[str, Any] = Depends(node_auth),


    ) -> dict[str, Any]:


        job = _node_job_by_id(conn, job_id)


        if job["node_id"] != node["node_id"]:


            raise HTTPException(status_code=403, detail="node_job_mismatch")


        log = _create_node_job_log(


            conn,


            job_id=job_id,


            node_id=node["node_id"],


            event_type="node.log",


            content=body.content,


            metadata=body.metadata,


        )


        conn.execute("update node_jobs set updated_at = ? where job_id = ?", (time.time(), job_id))


        conn.commit()


        return log





    @app.get("/jobs/{job_id}/logs")


    def list_node_job_logs(job_id: str, user: dict[str, Any] = Depends(owner_user)) -> dict[str, Any]:


        job = _node_job_by_id(conn, job_id)


        rows = conn.execute(


            "select * from node_job_logs where job_id = ? order by created_at asc",


            (job_id,),


        ).fetchall()


        return {"job": job, "logs": [dict(row) for row in rows]}





    @app.post("/jobs/{job_id}/artifacts")


    def upload_node_job_artifact(


        job_id: str,


        upload: UploadFile = File(...),


        artifact_type: str = Form(default="file"),


        metadata_json: str = Form(default="{}"),


        node: dict[str, Any] = Depends(node_auth),


    ) -> dict[str, Any]:


        job = _node_job_by_id(conn, job_id)


        if job["node_id"] != node["node_id"]:


            raise HTTPException(status_code=403, detail="node_job_mismatch")


        metadata = _safe_json_dict(metadata_json)


        artifact = _store_node_job_artifact(conn, config, job, node, upload, artifact_type, metadata)


        _create_node_job_log(


            conn,


            job_id=job_id,


            node_id=node["node_id"],


            event_type="node.artifact",


            content=f"节点上传 artifact：{artifact['original_name']}",


            metadata={"artifact_id": artifact["artifact_id"], "artifact_type": artifact["artifact_type"]},


        )


        conn.commit()


        return artifact





    @app.get("/jobs/{job_id}/artifacts")


    def list_node_job_artifacts(job_id: str, user: dict[str, Any] = Depends(owner_user)) -> dict[str, Any]:


        job = _node_job_by_id(conn, job_id)


        rows = conn.execute(


            "select * from node_job_artifacts where job_id = ? order by created_at asc",


            (job_id,),


        ).fetchall()


        return {"job": job, "artifacts": [_public_node_artifact(dict(row)) for row in rows]}





    @app.post("/jobs/{job_id}/result")


    def complete_node_job(


        job_id: str,


        body: NodeJobResultCreate,


        node: dict[str, Any] = Depends(node_auth),


    ) -> dict[str, Any]:


        job = _node_job_by_id(conn, job_id)


        if job["node_id"] != node["node_id"]:


            raise HTTPException(status_code=403, detail="node_job_mismatch")


        now = time.time()


        conn.execute(


            """


            update node_jobs


            set status = ?, result_json = ?, completed_at = ?, updated_at = ?


            where job_id = ?


            """,


            (body.status, json.dumps(body.result, ensure_ascii=False), now, now, job_id),


        )


        _create_node_job_log(


            conn,


            job_id=job_id,


            node_id=node["node_id"],


            event_type="node.result",


            content=f"节点任务结束：{body.status}",


            metadata=body.result,


        )


        conn.commit()


        return _node_job_by_id(conn, job_id)





    @app.get("/deployment-jobs")


    def list_deployment_jobs(user: dict[str, Any] = Depends(owner_user)) -> dict[str, Any]:


        rows = conn.execute("select * from deployment_jobs order by created_at desc").fetchall()


        return {"deployment_jobs": [dict(row) for row in rows]}





    @app.post("/deployment-jobs")


    def create_deployment_job(


        body: DeploymentJobCreate,


        user: dict[str, Any] = Depends(owner_user),


    ) -> dict[str, Any]:


        now = time.time()


        job_id = f"deploy-{uuid.uuid4().hex[:12]}"


        conn.execute(


            """


            insert into deployment_jobs (


              job_id, target_node, summary, status, payload_json, created_at, updated_at


            ) values (?, ?, ?, ?, ?, ?, ?)


            """,


            (


                job_id,


                body.target_node,


                body.summary,


                "pending",


                json.dumps(body.payload, ensure_ascii=False),


                now,


                now,


            ),


        )


        _audit(conn, "deployment_job_created", user["user_id"], {"job_id": job_id, "target_node": body.target_node})


        conn.commit()


        return dict(conn.execute("select * from deployment_jobs where job_id = ?", (job_id,)).fetchone())





    @app.post("/channels/qq/events")


    def qq_event(


        body: QQEventIn,


        user: dict[str, Any] = Depends(channel_user),


    ) -> dict[str, Any]:

        _require_perm("chat", user)
        if body.attachments:
            _require_perm("media", user)

        verified_memory_context = verify_qq_context(
            body.trusted_context,
            config.channel_token,
            session_id=body.session_id,
            session_key=body.session_key,
            user_id=body.user_id,
            group_id=body.group_id,
            chat_type=body.chat_type,
            sender_role=body.sender_role,
        )
        if verified_memory_context is not None:
            write_trusted_session_context(config.memory_context_dir, body.session_id, verified_memory_context)


        conversation = _get_or_create_qq_conversation(conn, body)

        if body.message_id:
            source_id = _qq_source_id(body)
            claimed = conn.execute(
                """
                insert into qq_inbound_events (source_id, message_id, conversation_id, created_at)
                values (?, ?, ?, ?)
                on conflict(source_id, message_id) do nothing
                """,
                (source_id, body.message_id, conversation["conversation_id"], time.time()),
            )
            if claimed.rowcount != 1:
                conn.commit()
                return {
                    "ok": True,
                    "duplicate": True,
                    "reply": "",
                    "conversation_id": conversation["conversation_id"],
                }


        attachment_refs = _ingest_qq_attachments(conn, config, body, user, conversation["conversation_id"])


        metadata = {


            "message_id": body.message_id,


            "chat_type": body.chat_type,


            "user_id": body.user_id,


            "group_id": body.group_id,


            "sender_role": body.sender_role,


            "risk": body.risk,


            "raw_attachments": body.attachments,


            "auto_vision": False,


        }


        if attachment_refs:


            metadata["attachments"] = _public_attachment_refs(attachment_refs)


        user_message = _insert_message(


            conn,


            conversation["conversation_id"],


            "user",


            body.text,


            "qq",


            metadata=metadata,


        )

        _increment_usage(
            conn,
            user["user_id"],
            text_messages=1,
            file_uploads=len(attachment_refs),
        )

        if body.sender_role == "owner":

            owner_schedule = _owner_scheduled_request_reply(

                conn,

                conversation,

                body.text,

                qq_target={

                    "chat_type": body.chat_type,

                    "user_id": body.user_id,

                    "group_id": body.group_id,

                },

            )

            if owner_schedule is not None:

                reply, job = owner_schedule

                _insert_message(

                    conn,

                    conversation["conversation_id"],

                    "assistant",

                    reply,

                    "hermi",

                    metadata={

                        "action_type": "scheduled.create",

                        "job_id": job["job_id"],

                        "task_id": job.get("task_id"),

                    },

                )

                conn.execute(

                    "update conversations set updated_at = ? where conversation_id = ?",

                    (time.time(), conversation["conversation_id"]),

                )

                conn.commit()

                return {

                    "ok": True,

                    "conversation_id": conversation["conversation_id"],

                    "reply": reply,

                    "session_id": body.session_id,

                    "session_key": body.session_key,

                }

        if _is_attachment_only_message(body.text, attachment_refs):

            reply = _attachment_waiting_reply(attachment_refs)

            _insert_message(conn, conversation["conversation_id"], "assistant", reply, "hermi")

            conn.execute(

                "update conversations set updated_at = ? where conversation_id = ?",

                (time.time(), conversation["conversation_id"]),

            )

            conn.commit()

            return {

                "ok": True,

                "conversation_id": conversation["conversation_id"],

                "reply": reply,

                "session_id": body.session_id,

                "session_key": body.session_key,

            }

        history = _conversation_history(conn, conversation["conversation_id"])


        if not history or history[-1]["content"] != user_message["content"]:


            history.append({"role": "user", "content": body.text})


        messages = _build_qq_channel_messages(

            conn,

            history,

            body,

            conversation["conversation_id"],

            profile_name=_profile_display_name(conn, config.qq_profile_id),

            attachment_refs=attachment_refs,

        )

        try:


            reply = _chat_profile(app.state.hermes_adapter, config.qq_profile_id, messages, body.session_id, body.session_key).strip()


            _increment_usage_from_hermes(
                conn,
                user["user_id"],
                app.state.hermes_adapter,
                conversation_id=conversation["conversation_id"],
                config=config,
            )

        except Exception:


            reply = "我这边调用 Hermes 出错了，稍后再试。"

        split_parts = _split_qlos_reply_parts(reply)


        display_reply = "\n\n".join(split_parts).strip() if split_parts else reply.strip()


        assistant_metadata = {"split_parts": split_parts} if len(split_parts) > 1 else None


        _insert_message(conn, conversation["conversation_id"], "assistant", display_reply, "hermes", metadata=assistant_metadata)


        conn.execute(


            "update conversations set updated_at = ? where conversation_id = ?",


            (time.time(), conversation["conversation_id"]),


        )


        conn.commit()


        return {


            "ok": True,


            "conversation_id": conversation["conversation_id"],


            "reply": reply,


            "session_id": body.session_id,


            "session_key": body.session_key,


        }





    @app.post("/hermes-cron/deliver")


    def hermes_cron_deliver(


        body: dict[str, Any] = Body(default_factory=dict),


        authorization: str | None = Header(default=None),


        x_hermi_token: str | None = Header(default=None),


        x_qlos_token: str | None = Header(default=None),


    ) -> dict[str, Any]:


        token = _bearer_token(authorization) or str(x_hermi_token or "").strip() or str(x_qlos_token or "").strip()


        allowed = {config.channel_token, config.owner_token, *(config.qlos_send_tokens or [])}


        allowed = {item for item in allowed if item}


        if allowed and token not in allowed:


            raise HTTPException(status_code=401, detail="unauthorized")





        content = str(body.get("content") or body.get("message") or "").strip()


        if not content:


            raise HTTPException(status_code=400, detail="missing_content")





        target = str(


            body.get("conversation_id")


            or body.get("session_id")


            or body.get("chat_id")


            or body.get("target")


            or ""


        ).strip()


        conversation = _conversation_by_identifier(conn, target) if target else None


        if not conversation:


            conversation = _conversation_by_id(conn, _get_or_create_system_conversation(conn))





        metadata = {


            "source": "hermes_native_cron",


            "job_id": body.get("job_id") or "",


            "job_name": body.get("job_name") or body.get("name") or "",


            "deliver_target": target,


        }


        message = _insert_message(


            conn,


            str(conversation["conversation_id"]),


            "assistant",


            content,


            "hermes-cron",


            metadata=metadata,


        )


        conn.execute(


            "update conversations set updated_at = ? where conversation_id = ?",


            (time.time(), conversation["conversation_id"]),


        )


        conn.commit()


        return {"ok": True, "conversation_id": conversation["conversation_id"], "message": message}





    return app








def _bearer_token(header: Any | None) -> str:


    if not header:


        return ""


    try:


        value = str(header).strip()


    except Exception:


        return ""


    if value.lower().startswith("bearer "):


        return value[7:].strip()


    return value








def _public_user(user: dict[str, Any]) -> dict[str, Any]:

    public = {key: value for key, value in user.items() if key != "token"}

    public["permissions"] = _permissions_dict(public.get("permissions"))

    return public





def _permissions_dict(value: Any) -> dict[str, Any]:

    if isinstance(value, dict):

        return dict(value)

    if not value:

        return {}

    if isinstance(value, str):

        try:

            parsed = json.loads(value)

        except json.JSONDecodeError:

            return {}

        return parsed if isinstance(parsed, dict) else {}

    return {}





def _permissions_to_db(value: Any) -> str:

    permissions = _permissions_dict(value)

    return json.dumps(permissions, ensure_ascii=False) if permissions else ""





def _merge_permission_patch(current: Any, patch: Any) -> str:

    if patch is None:

        return _permissions_to_db(current)

    merged = _permissions_dict(current)

    incoming = _permissions_dict(patch)

    if not incoming and patch in ("", {}):

        return ""

    for key, value in incoming.items():

        if isinstance(value, dict) and isinstance(merged.get(key), dict):

            nested = dict(merged[key])

            nested.update(value)

            merged[key] = nested

        else:

            merged[key] = value

    return _permissions_to_db(merged)







DEFAULT_CAPABILITIES: list[dict[str, Any]] = [


    {


        "capability_id": "qq.send",


        "title": "发送 QQ 消息",


        "description": "经 QLOS/NapCat 向私聊或群聊发送文本消息。",


        "risk_level": "medium",


        "approval_policy": "owner",


        "schema": {


            "required": ["type", "message", "target"],


            "properties": {


                "type": {"type": "string"},


                "message": {"type": "string"},


                "target": {"type": "object", "required": ["chat_type"]},


            },


        },


    },


    {


        "capability_id": "scheduled.create",


        "title": "创建定时任务",


        "description": "创建 once/interval/cron 主动任务。",


        "risk_level": "medium",


        "approval_policy": "owner",


        "schema": {


            "required": ["type", "kind", "schedule", "summary", "content"],


            "properties": {


                "type": {"type": "string"},


                "kind": {"type": "string"},


                "schedule": {"type": "string"},


                "summary": {"type": "string"},


                "content": {"type": "string"},


            },


        },


    },


    {


        "capability_id": "service.action",


        "title": "服务控制",


        "description": "重启或管理 Hermi/QLOS/Hermes/NapCat 等本机服务。",


        "risk_level": "high",


        "approval_policy": "owner",


        "schema": {


            "required": ["type", "payload"],


            "properties": {


                "type": {"type": "string"},


                "payload": {"type": "object"},


            },


        },


    },


    {


        "capability_id": "operation.request",


        "title": "本机操作区请求",


        "description": "请求读取日志、运行白名单测试、生成 diff 或执行受控修复。",


        "risk_level": "high",


        "approval_policy": "owner",


        "schema": {


            "required": ["type", "summary"],


            "properties": {


                "type": {"type": "string"},


                "summary": {"type": "string"},


                "operation_zone_id": {"type": "string"},


            },


        },


    },


    {


        "capability_id": "hermes.permission.request",


        "title": "Hermes 权限请求",


        "description": "Hermes 原生运行或文本 fallback 提出的权限请求。",


        "risk_level": "high",


        "approval_policy": "owner",


        "schema": {


            "required": ["type", "summary"],


            "properties": {


                "type": {"type": "string"},


                "summary": {"type": "string"},


                "requested_capability": {"type": "string"},


            },


        },


    },


]





SKILL_CAPABILITIES: list[dict[str, Any]] = [
    {
        "capability_id": "scheduled.create",
        "title": "定时任务",
        "description": "创建、查看或调整 Hermi 定时任务；会保留原有审批与提醒投递规则。",
        "skills": ["hermi-scheduler"],
        "kind": "hermi_feature",
        "risk_level": "medium",
    },
    {
        "capability_id": "qq.send",
        "title": "QQ 消息",
        "description": "按对话要求准备 QQ 消息；发送前仍会执行既有权限、审批和 QLOS 投递流程。",
        "skills": ["qlos", "napcat"],
        "kind": "hermi_feature",
        "risk_level": "high",
    },
    {
        "capability_id": "presentation.create",
        "title": "PPT 制作",
        "description": "根据目标、受众和材料规划内容并制作演示文稿。",
        "skills": ["powerpoint"],
        "risk_level": "medium",
    },
    {
        "capability_id": "document.read",
        "title": "文档识读",
        "description": "从 PDF、扫描件或文档中提取、核对和整理信息。",
        "skills": ["ocr-and-documents"],
        "risk_level": "low",
    },
    {
        "capability_id": "knowledge.record",
        "title": "知识库记录",
        "description": "整理内容并按需写入或检索 Obsidian 知识库。",
        "skills": ["obsidian"],
        "risk_level": "medium",
    },
    {
        "capability_id": "research.search",
        "title": "资料调研",
        "description": "联网检索资料、比较来源并整理可核对的结论。",
        "skills": ["agent-reach"],
        "risk_level": "medium",
    },
    {
        "capability_id": "diagram.create",
        "title": "流程图",
        "description": "把流程、架构或时序关系整理成可编辑图示。",
        "skills": ["excalidraw"],
        "risk_level": "low",
    },
    {
        "capability_id": "project.inspect",
        "title": "项目检查",
        "description": "检查代码结构、变更风险和可审查的问题。",
        "skills": ["codebase-inspection", "github-code-review"],
        "risk_level": "medium",
    },
    {
        "capability_id": "memory.organize",
        "title": "长期记忆整理",
        "description": "搜索、归纳、修正或归档长期记忆。",
        "skills": ["knowledge-memory"],
        "risk_level": "medium",
    },
]


def _skill_capability_instruction(capability_id: str) -> str:
    capability = next(
        (item for item in SKILL_CAPABILITIES if item["capability_id"] == str(capability_id or "").strip()),
        None,
    )
    if capability is None:
        return ""
    skills = ", ".join(capability["skills"])
    if capability.get("kind") == "hermi_feature":
        return (
            f"Selected Hermi feature capability: {capability['capability_id']} ({capability['title']}).\n"
            f"Use the relevant built-in Hermi workflow when it fits: {skills}.\n"
            "This is a scoped workflow hint, not proof that an external action has completed. Keep all existing "
            "permission and approval rules in force, explain any required approval naturally, and do not claim "
            "a task or QQ message was created or sent until the Hermi action result confirms it."
        )
    return (
        f"Selected Hermi skill capability: {capability['capability_id']} ({capability['title']}).\n"
        f"Prefer these Hermes skills when they fit the latest request: {skills}.\n"
        "This is a scoped workflow hint, not a command to force the skill. If the latest request does not fit, "
        "continue as a normal conversation and briefly say which capability would fit better when useful. "
        "Keep all existing Hermi permission, approval, file, network, and external-action rules in force."
    )


RESERVED_CAPABILITIES: list[dict[str, str]] = [
    {
        "capability_id": "file.analysis",
        "title": "文件分析",
        "description": "进入文件专用会话，明确读取、总结、提取或改写目标。",
        "risk_level": "low",
    },
    {
        "capability_id": "project.diagnose",
        "title": "项目诊断",
        "description": "进入诊断流程：读取日志、运行测试并整理问题报告。",
        "risk_level": "medium",
    },
    {
        "capability_id": "meeting.create",
        "title": "会议发起",
        "description": "进入会议配置流程，选择成员、模式和权限后再创建。",
        "risk_level": "low",
    },
    {
        "capability_id": "code.repair",
        "title": "代码修复",
        "description": "进入修复任务流程，先形成 diff 与测试结果，再等待 Owner 审批。",
        "risk_level": "high",
    },
    {
        "capability_id": "research.search",
        "title": "信息检索",
        "description": "进入检索流程，未来会展示来源、范围和引用结果。",
        "risk_level": "low",
    },
]


PROFILE_DISPLAY_DEFAULTS = {

    "trainee": "薇达(Veda)",

    "imouto": "小墨(Ember)",

    "maid": "薇拉(Vera)",

}







def _profile_registry(config: HermiConfig) -> list[dict[str, Any]]:

    names = [


        name.strip()


        for name in str(os.environ.get("HERMI_PROFILE_NAMES", "")).split(",")


        if name.strip()


    ]


    if names:

        if config.default_profile_name and config.default_profile_name not in names:

            names.insert(0, config.default_profile_name)

        return [

            {

                "profile_id": _safe_node_id(name) or f"profile-{index + 1}",

                "name": name,

                "adapter": "hermes_profile",

                "is_default": name == config.default_profile_name,

                "status": "reserved",

                "model": "",

                "provider": "",

                "path": "",

            }

            for index, name in enumerate(names)

        ]



    local_app_data = Path(os.environ.get("LOCALAPPDATA") or Path.home() / "AppData" / "Local")

    hermes_root = local_app_data / "hermes"

    profiles_root = hermes_root / "profiles"

    candidates: list[tuple[str, Path]] = []

    if profiles_root.exists():

        profile_paths = {path.name: path for path in profiles_root.iterdir() if path.is_dir()}

        primary_path = profile_paths.pop(config.qq_profile_id, None)

        if primary_path is not None:

            candidates.append((config.qq_profile_id, primary_path))

        candidates.extend(sorted(profile_paths.items()))

    if not candidates and ((hermes_root / "config.yaml").exists() or (hermes_root / "SOUL.md").exists()):

        candidates.append(("default", hermes_root))

    if not candidates:

        return [{

            "profile_id": config.qq_profile_id,

            "name": config.default_profile_name or config.qq_profile_id,

            "adapter": "hermes_profile",

            "is_default": True,

            "status": "setup_required",

            "model": "",

            "provider": "",

            "path": str(hermes_root),

        }]



    configured_gateway_profiles = {

        item.partition("=")[0].strip()

        for item in str(config.profile_api_urls).split(",")

        if "=" in item

    }

    profiles = []

    for profile_id, path in candidates:

        model, provider = _hermes_profile_model(path)

        profiles.append({

            "profile_id": profile_id,

            "name": profile_id,

            "adapter": "hermes_profile",

            "is_default": profile_id == config.qq_profile_id,

            "status": "ready" if model else "setup_required",

            "gateway_status": "running" if profile_id in configured_gateway_profiles else "stopped",

            "model": model,

            "provider": provider,

            "path": str(path),

        })

    return profiles





def _hermes_profile_model(path: Path) -> tuple[str, str]:

    config_path = path / "config.yaml"

    if not config_path.exists():

        return "", ""

    try:

        import yaml



        payload = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}

        model = payload.get("model") if isinstance(payload, dict) else {}

        if not isinstance(model, dict):

            return "", ""

        return str(model.get("default") or "").strip(), str(model.get("provider") or "").strip()

    except Exception:

        return "", ""





def _sync_profile_agents(conn, config: HermiConfig) -> None:

    _migrate_primary_profile_records(conn, "default", config.qq_profile_id)

    now = time.time()

    profiles = _profile_registry(config)

    active_agent_ids = {f"profile:{profile['profile_id']}" for profile in profiles}

    stale_agents = conn.execute(

        "select agent_id from agents where agent_type = 'hermes_profile'"

    ).fetchall()

    for row in stale_agents:

        if row["agent_id"] not in active_agent_ids:

            conn.execute("delete from agents where agent_id = ?", (row["agent_id"],))

    for profile in profiles:

        conn.execute(

            """

            insert into profile_settings (profile_id, display_name, customized, updated_at)

            values (?, ?, 0, ?)

            on conflict(profile_id) do nothing

            """,

            (profile["profile_id"], profile["name"], now),

        )

        setting = conn.execute(

            "select display_name, customized from profile_settings where profile_id = ?",

            (profile["profile_id"],),

        ).fetchone()

        display_name = str(

            setting["display_name"]

            if setting and setting["customized"]

            else PROFILE_DISPLAY_DEFAULTS.get(profile["profile_id"], profile["name"])

        )

        agent_id = f"profile:{profile['profile_id']}"

        conn.execute(

            """

            insert into agents (agent_id, name, agent_type, description, config_json, created_at, updated_at)

            values (?, ?, 'hermes_profile', ?, ?, ?, ?)

            on conflict(agent_id) do update set

              name = excluded.name, agent_type = excluded.agent_type,

              description = excluded.description, config_json = excluded.config_json,

              updated_at = excluded.updated_at

            """,

            (

                agent_id,

                display_name,

                f"Local Hermes profile ({profile['status']})",

                json.dumps(profile, ensure_ascii=False),

                now,

                now,

            ),

        )



    conn.commit()




def _migrate_primary_profile_records(conn, old_profile_id: str, new_profile_id: str) -> None:

    if not new_profile_id or new_profile_id == old_profile_id:

        return

    old_setting = conn.execute(

        "select * from profile_settings where profile_id = ?", (old_profile_id,)

    ).fetchone()

    new_setting = conn.execute(

        "select * from profile_settings where profile_id = ?", (new_profile_id,)

    ).fetchone()

    if old_setting and not new_setting:

        conn.execute(

            "update profile_settings set profile_id = ? where profile_id = ?",

            (new_profile_id, old_profile_id),

        )

    elif old_setting and new_setting:

        if old_setting["customized"] and not new_setting["customized"]:

            conn.execute(

                "update profile_settings set display_name = ?, customized = 1, updated_at = ? where profile_id = ?",

                (old_setting["display_name"], old_setting["updated_at"], new_profile_id),

            )

        conn.execute("delete from profile_settings where profile_id = ?", (old_profile_id,))

    old_agent_id = f"profile:{old_profile_id}"

    new_agent_id = f"profile:{new_profile_id}"

    conn.execute(

        "insert or ignore into room_members (room_id, agent_id, role, joined_at) "

        "select room_id, ?, role, joined_at from room_members where agent_id = ?",

        (new_agent_id, old_agent_id),

    )

    conn.execute("delete from room_members where agent_id = ?", (old_agent_id,))

    conn.execute("update rooms set host_agent_id = ? where host_agent_id = ?", (new_agent_id, old_agent_id))

    conn.execute("update workflow_steps set agent_id = ? where agent_id = ?", (new_agent_id, old_agent_id))

    conn.execute("delete from agents where agent_id = ?", (old_agent_id,))





def _profile_registry_with_settings(conn, config: HermiConfig) -> list[dict[str, Any]]:

    profiles = _profile_registry(config)

    rows = conn.execute("select * from profile_settings").fetchall()

    settings = {str(row["profile_id"]): dict(row) for row in rows}

    for profile in profiles:

        setting = settings.get(str(profile["profile_id"]))

        profile["technical_name"] = profile["name"]

        profile["customized"] = bool(setting and setting.get("customized"))

        profile["display_name"] = str(

            setting["display_name"]

            if profile["customized"]

            else PROFILE_DISPLAY_DEFAULTS.get(profile["profile_id"], profile["name"])

        )

        profile["name"] = profile["display_name"] if profile["customized"] else profile["name"]

    return profiles





def _active_profile_name(conn, config: HermiConfig) -> str:

    return _profile_display_name(conn, config.hermi_profile_id)





def _conversation_profile_name(conn, config: HermiConfig, conversation: dict[str, Any]) -> str:
    return _profile_display_name(conn, _conversation_profile_id(conn, config, conversation))


def _conversation_profile_id(conn, config: HermiConfig, conversation: dict[str, Any]) -> str:
    stored = str(conversation.get("profile_id") or "").strip()
    if stored:
        return stored
    if str(conversation.get("channel") or "").lower() == "qq":
        return config.qq_profile_id
    title = str(conversation.get("title") or "")
    settings = {
        str(row["profile_id"]): str(row["display_name"])
        for row in conn.execute("select profile_id, display_name from profile_settings where customized = 1")
    }
    for profile_id, display_name in PROFILE_DISPLAY_DEFAULTS.items():
        candidate = settings.get(profile_id, display_name)
        if title.startswith(f"{candidate} · ") or title.startswith(f"{candidate} "):
            return profile_id
    return config.hermi_profile_id





def _actor_payload(actor_id: str, display_name: str, actor_type: str, avatar: str = "") -> dict[str, str]:

    return {

        "actor_id": actor_id,

        "display_name": display_name,

        "actor_type": actor_type,

        "avatar": avatar,

    }





def _message_actor(

    conn,

    config: HermiConfig,

    conversation: dict[str, Any],

    message: dict[str, Any],

) -> dict[str, str]:

    role = str(message.get("role") or "")

    metadata = _safe_json_dict(str(message.get("metadata_json") or "{}"))

    if role == "user":

        actor_id = str(
            metadata.get("author_user_id")
            or ("owner" if metadata.get("external_author") == "owner" else "")
            or conversation.get("owner_user_id")
            or "user"
        )

        row = conn.execute("select display_name from users where user_id = ?", (actor_id,)).fetchone()

        display_name = str(row["display_name"] if row else actor_id)

        return _actor_payload(actor_id, display_name, "user")

    if role == "assistant":

        profile_id = _conversation_profile_id(conn, config, conversation)

        return _actor_payload(f"profile:{profile_id}", _profile_display_name(conn, profile_id), "ai")

    return _actor_payload("system", "Hermi", "system")


def _backfill_message_authors_from_runs(conn, conversation_id: str) -> None:
    """Restore authors for older streamed messages created before author metadata."""
    changed = False
    rows = conn.execute(
        "select user_id, final_json from message_runs where conversation_id = ? and final_json != '{}'",
        (conversation_id,),
    ).fetchall()
    for row in rows:
        final = _safe_json_dict(str(row["final_json"] or "{}"))
        user_message = final.get("user") if isinstance(final.get("user"), dict) else {}
        message_id = str(user_message.get("message_id") or "")
        if not message_id:
            continue
        message_row = conn.execute(
            "select metadata_json from messages where message_id = ? and conversation_id = ?",
            (message_id, conversation_id),
        ).fetchone()
        if not message_row:
            continue
        metadata = _safe_json_dict(str(message_row["metadata_json"] or "{}"))
        if metadata.get("author_user_id"):
            continue
        metadata["author_user_id"] = str(row["user_id"])
        conn.execute(
            "update messages set metadata_json = ? where message_id = ?",
            (json.dumps(metadata, ensure_ascii=False), message_id),
        )
        changed = True
    if changed:
        conn.commit()





def _workflow_step_actor(conn, step: dict[str, Any]) -> dict[str, str]:

    actor_id = str(step.get("agent_id") or "system")

    if actor_id == "system":

        return _actor_payload("system", "会议系统", "system")

    row = conn.execute("select name from agents where agent_id = ?", (actor_id,)).fetchone()

    return _actor_payload(actor_id, str(row["name"] if row else actor_id), "ai")





def _public_workflow_step(conn, step: dict[str, Any]) -> dict[str, Any]:

    metadata = _safe_json_dict(str(step.get("metadata_json") or "{}"))

    trace = metadata.get("trace") if isinstance(metadata.get("trace"), list) else []

    return {**step, "actor": _workflow_step_actor(conn, step), "trace": trace}





def _recent_qq_context_for_request(

    config: HermiConfig,

    user: dict[str, Any],

    content: str,

) -> str:

    if str(user.get("role") or "") != "owner":

        return ""

    text = str(content or "")

    asks_about_history = bool(

        re.search(r"(?:QQ|qq|群).{0,20}(?:最近|刚刚|消息|记录|历史|聊|说了|发生|有什么)", text)

        or re.search(r"(?:最近|刚刚|看看|消息|记录|历史).{0,20}(?:QQ|qq|群)", text)

    )

    if not asks_about_history:

        return ""

    return load_recent_qq_context(config.qlos_log_dir, limit=20)





def _profile_display_name(conn, profile_id: str) -> str:

    row = conn.execute(

        "select display_name, customized from profile_settings where profile_id = ?", (profile_id,)

    ).fetchone()

    if row and row["customized"]:

        return str(row["display_name"])

    return PROFILE_DISPLAY_DEFAULTS.get(profile_id, profile_id)


def _owner_display_name(conn) -> str:
    row = conn.execute("select display_name from users where user_id = 'owner'").fetchone()
    return str(row["display_name"] if row and row["display_name"] else "Owner")





def _chat_profile(adapter: Any, profile_id: str, messages, session_id: str, session_key: str) -> str:

    if hasattr(adapter, "chat_profile"):

        return adapter.chat_profile(profile_id, messages, session_id, session_key)

    return adapter.chat(messages, session_id, session_key)


_hermi_tool_identity_lock = threading.Lock()


def _record_hermi_tool_identity(config: HermiConfig, conversation: dict[str, Any], user: dict[str, Any]) -> None:
    """Give Hermes' pre-tool hook a short-lived, server-issued Hermi role record."""

    session_id = str(conversation.get("session_id") or "").strip()
    session_key = str(conversation.get("session_key") or "").strip()
    if not session_id:
        return
    if session_key and str(user.get("user_id") or "").strip():
        context = build_hermi_web_context(
            config.channel_token,
            user_id=str(user.get("user_id") or ""),
            session_id=session_id,
            session_key=session_key,
            role="owner" if bool(user.get("can_approve") or user.get("role") == "owner") else str(user.get("role") or "friend"),
        )
        write_trusted_session_context(config.memory_context_dir, session_id, context)
        ensure_hermi_subject_page(
            config.memory_context_dir,
            str(conversation.get("profile_id") or config.hermi_profile_id),
            context,
        )
    configured = os.getenv("HERMI_TOOL_GUARD_IDENTITY_FILE", "").strip()
    path = Path(configured) if configured else config.db_path.parent / "hermi_tool_identity.jsonl"
    now = time.time()
    record = {
        "session_id": session_id,
        "user_id": str(user.get("user_id") or ""),
        "role": str(user.get("role") or "friend"),
        "is_owner": bool(user.get("can_approve") or user.get("role") == "owner"),
        "ts": now,
        "expires_at": now + 900,
    }
    with _hermi_tool_identity_lock:
        retained: list[str] = []
        if path.exists():
            try:
                for line in path.read_text(encoding="utf-8").splitlines():
                    try:
                        previous = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    if (
                        str(previous.get("session_id") or "") != session_id
                        and float(previous.get("expires_at") or 0) > now
                    ):
                        retained.append(json.dumps(previous, ensure_ascii=False))
            except OSError:
                retained = []
        path.parent.mkdir(parents=True, exist_ok=True)
        retained.append(json.dumps(record, ensure_ascii=False))
        path.write_text("\n".join(retained[-256:]) + "\n", encoding="utf-8")





def _stream_profile_events(adapter: Any, profile_id: str, messages, session_id: str, session_key: str):

    if hasattr(adapter, "stream_profile_events"):

        yield from adapter.stream_profile_events(profile_id, messages, session_id, session_key)

        return

    yield from adapter.stream_events(messages, session_id, session_key)







def _brain_adapter_status(config: HermiConfig) -> list[dict[str, Any]]:


    return [


        {


            "adapter_id": "hermes_api",


            "label": "Hermes API",


            "available": bool(config.hermes_api_url),


            "requires_setup": not bool(config.hermes_api_key),


            "endpoint": config.hermes_api_url,


            "notes": "当前默认主脑；无 API key 时 Hermi 仍可启动，真实对话取决于 Hermes 侧是否允许。",


        },


        {


            "adapter_id": "local_profiles",


            "label": "本机多 Profile",


            "available": True,


            "requires_setup": False,


            "endpoint": "HERMI_PROFILE_NAMES",


            "notes": "阶段15预留：多个 profile 先登记，真实并行发言后续接入。",


        },


        {


            "adapter_id": "opencode",


            "label": "OpenCode",


            "available": False,


            "requires_setup": True,


            "endpoint": "",


            "notes": "阶段16/后续预留：还未接真实执行器。",


        },


        {


            "adapter_id": "openai_compatible",


            "label": "OpenAI-compatible",


            "available": False,


            "requires_setup": True,


            "endpoint": "",


            "notes": "阶段16预留：用于未来无 API 启动后的主脑选择。",


        },


    ]








def _ensure_default_capabilities(conn) -> None:


    now = time.time()


    for capability in DEFAULT_CAPABILITIES:


        conn.execute(


            """


            insert into capability_registry (


              capability_id, title, description, risk_level, schema_json,


              approval_policy, enabled, created_at, updated_at


            ) values (?, ?, ?, ?, ?, ?, ?, ?, ?)


            on conflict(capability_id) do update set


              title = excluded.title,


              description = excluded.description,


              risk_level = excluded.risk_level,


              schema_json = excluded.schema_json,


              approval_policy = excluded.approval_policy,


              enabled = excluded.enabled,


              updated_at = excluded.updated_at


            """,


            (


                capability["capability_id"],


                capability["title"],


                capability["description"],


                capability["risk_level"],


                json.dumps(capability["schema"], ensure_ascii=False),


                capability["approval_policy"],


                1,


                now,


                now,


            ),


        )


    conn.commit()








QQ_SPLIT_PROMPT = (


    "QQ channel prompt: 回复 QQ 时用轻松简短、清楚明了的语言。"


    "如一条回复适合拆成几条 QQ 消息，可在段落之间插入内部拆分标记 <<<QLOS_SPLIT>>>；"


    "推荐 1~3 个。这个标记不是给用户看的分隔线，不要解释给用户，"


    "不要用 --- 代替。代码、命令、表格、严肃结构化内容不要拆。"


)








def _ensure_default_prompt_bindings(conn) -> None:


    now = time.time()


    card_id = "pcard-qq-split-v1"


    conn.execute(


        """


        insert into prompt_cards (


          card_id, name, card_type, content, enabled, created_at, updated_at, metadata_json


        ) values (?, ?, ?, ?, ?, ?, ?, ?)


        on conflict(card_id) do update set


          content = excluded.content,


          enabled = excluded.enabled,


          updated_at = excluded.updated_at


        """,


        (


            card_id,


            "QQ channel split style",


            "channel",


            QQ_SPLIT_PROMPT,


            1,


            now,


            now,


            json.dumps({"channel": "qq", "system": True, "version": "v1"}, ensure_ascii=False),


        ),


    )


    conn.execute(


        """


        insert into prompt_bindings (


          binding_id, card_id, scope_type, scope_id, priority, enabled,


          created_at, updated_at, metadata_json


        ) values (?, ?, ?, ?, ?, ?, ?, ?, ?)


        on conflict(binding_id) do update set


          priority = excluded.priority,


          enabled = excluded.enabled,


          updated_at = excluded.updated_at


        """,


        (


            "pbind-qq-channel-split-v1",


            card_id,


            "channel",


            "qq",


            10,


            1,


            now,


            now,


            json.dumps({"system": True}, ensure_ascii=False),


        ),


    )


    conn.commit()








def _public_capability(row: dict[str, Any]) -> dict[str, Any]:


    return {


        "capability_id": row["capability_id"],


        "title": row["title"],


        "description": row["description"],


        "risk_level": row["risk_level"],


        "schema": _safe_json_dict(row["schema_json"]),


        "approval_policy": row["approval_policy"],


        "enabled": bool(row["enabled"]),


        "updated_at": row["updated_at"],


    }








def _validate_action_payload(action: dict[str, Any]) -> dict[str, Any]:


    action_type = str(action.get("type") or "").strip()


    if not action_type:


        raise HTTPException(status_code=422, detail={"error": "missing_type", "missing": ["type"]})


    schema = next((item["schema"] for item in DEFAULT_CAPABILITIES if item["capability_id"] == action_type), None)


    if schema is None and action_type == "cron.create":


        schema = next(item["schema"] for item in DEFAULT_CAPABILITIES if item["capability_id"] == "scheduled.create")


    if schema is None:


        raise HTTPException(status_code=422, detail={"error": "unknown_capability", "capability_id": action_type})


    missing = _missing_required_fields(action, schema)


    if missing:


        raise HTTPException(status_code=422, detail={"error": "missing_required", "missing": missing})


    wrong_type = _wrong_type_fields(action, schema)


    if wrong_type:


        raise HTTPException(status_code=422, detail={"error": "invalid_type", "fields": wrong_type})


    return {"capability_id": action_type, "action": action}








def _missing_required_fields(payload: dict[str, Any], schema: dict[str, Any], prefix: str = "") -> list[str]:


    missing: list[str] = []


    for field in schema.get("required") or []:


        if field not in payload or payload.get(field) in (None, ""):


            missing.append(f"{prefix}{field}")


    for field, field_schema in (schema.get("properties") or {}).items():


        if field_schema.get("type") == "object" and isinstance(payload.get(field), dict):


            missing.extend(_missing_required_fields(payload[field], field_schema, prefix=f"{prefix}{field}."))


    return missing








def _wrong_type_fields(payload: dict[str, Any], schema: dict[str, Any], prefix: str = "") -> list[str]:


    wrong: list[str] = []


    for field, field_schema in (schema.get("properties") or {}).items():


        if field not in payload or payload.get(field) is None:


            continue


        expected = field_schema.get("type")


        value = payload[field]


        if expected == "string" and not isinstance(value, str):


            wrong.append(f"{prefix}{field}")


        elif expected == "object" and not isinstance(value, dict):


            wrong.append(f"{prefix}{field}")


        elif expected == "array" and not isinstance(value, list):


            wrong.append(f"{prefix}{field}")


        elif expected == "object":


            wrong.extend(_wrong_type_fields(value, field_schema, prefix=f"{prefix}{field}."))


    return wrong








def _capability_risk(conn, capability_id: str) -> str:


    row = conn.execute("select risk_level from capability_registry where capability_id = ?", (capability_id,)).fetchone()


    return str(row["risk_level"]) if row else "high"








def _require_approval(conn, approval_id: str) -> dict[str, Any]:

    row = conn.execute("select * from approvals where approval_id = ?", (approval_id,)).fetchone()


    if not row:


        raise HTTPException(status_code=404, detail="approval_not_found")


    return dict(row)





def _expire_pending_approvals(conn, now: float | None = None) -> int:

    current = float(now if now is not None else time.time())

    rows = conn.execute(

        "select approval_id from approvals where status = 'pending' and expires_at <= ?",

        (current,),

    ).fetchall()

    cursor = conn.execute(

        """

        update approvals

        set status = 'denied', decision = 'expired', decided_by = 'system:expiry',

            decided_at = ?, updated_at = ?

        where status = 'pending' and expires_at <= ?

        """,

        (current, current, current),

    )

    for row in rows:

        _update_approval_callbacks(

            conn,

            str(row["approval_id"]),

            "denied",

            "expired",

            "approval_expired",

        )

    conn.commit()

    return int(cursor.rowcount or 0)







def _create_approval_callback(


    conn,


    approval_id: str,


    *,


    external_run_id: str,


    external_request_id: str,


    payload: dict[str, Any],


) -> None:


    now = time.time()


    conn.execute(


        """


        insert into approval_callbacks (


          callback_id, approval_id, external_run_id, external_request_id,


          status, payload_json, created_at, updated_at


        ) values (?, ?, ?, ?, ?, ?, ?, ?)


        """,


        (


            f"acb-{uuid.uuid4().hex[:12]}",


            approval_id,


            external_run_id,


            external_request_id,


            "pending",


            json.dumps(payload, ensure_ascii=False),


            now,


            now,


        ),


    )








def _update_approval_callbacks(conn, approval_id: str, status: str, decision: str, execution_note: str) -> None:


    now = time.time()


    rows = conn.execute("select * from approval_callbacks where approval_id = ?", (approval_id,)).fetchall()


    for row in rows:


        payload = _safe_json_dict(row["payload_json"])


        payload["decision"] = decision


        payload["execution_note"] = execution_note


        conn.execute(


            """


            update approval_callbacks


            set status = ?, payload_json = ?, updated_at = ?


            where callback_id = ?


            """,


            (status, json.dumps(payload, ensure_ascii=False), now, row["callback_id"]),


        )








def _safe_json_dict(value: str | bytes | None) -> dict[str, Any]:


    try:


        parsed = json.loads(value or "{}")


        return parsed if isinstance(parsed, dict) else {}


    except (TypeError, json.JSONDecodeError):


        return {}








def _safe_json_list(value: str | bytes | None) -> list[dict[str, Any]]:


    try:


        parsed = json.loads(value or "[]")


    except (TypeError, json.JSONDecodeError):


        return []


    return [item for item in parsed if isinstance(item, dict)] if isinstance(parsed, list) else []








def _usage_totals(rows: list[dict[str, Any]]) -> dict[str, int]:


    totals = {


        "text_messages": 0,


        "image_messages": 0,


        "file_uploads": 0,


        "prompt_tokens": 0,


        "completion_tokens": 0,


        "total_tokens": 0,


    }


    for row in rows:


        for key in totals:


            totals[key] += int(row.get(key) or 0)


    return totals








def _context_window_summary(message_count: int, usage: dict[str, int]) -> dict[str, Any]:


    total_tokens = int(usage.get("total_tokens") or 0)


    if total_tokens <= 0:


        status = "unknown"


    elif total_tokens < 80_000:


        status = "ok"


    else:


        status = "needs_trim"


    return {


        "status": status,


        "message_count": message_count,


        "total_tokens": total_tokens,


        "trim_strategy": "not_configured" if status != "needs_trim" else "summarize_old_messages",


    }








def _local_hermi_command_reply(


    conn,


    config: HermiConfig,


    conversation: dict[str, Any],


    content: str,


    user: dict[str, Any],


) -> str | None:


    command = str(content or "").strip().lower()


    if command not in {"/capabilities", "/context", "/help"}:


        return None


    if not user.get("can_approve"):


        return "这个 Hermi 本地管理命令只给 owner 使用。"


    if command == "/help":


        return (


            "Hermi 本地命令：\n"


            "- `/context`：查看当前会话的消息、附件、trace、token 汇总。\n"


            "- `/capabilities`：查看 Hermi 当前登记的能力和审批策略。\n\n"


            "更推荐在界面右侧点“临时”，里面有“当前会话”和“能力”两个区。"


        )


    if command == "/capabilities":


        rows = conn.execute("select * from capability_registry order by risk_level desc, capability_id asc").fetchall()


        lines = ["Hermi 当前能力："]


        for row in rows:


            cap = _public_capability(dict(row))


            required = "、".join(cap["schema"].get("required") or []) or "无"


            lines.append(


                f"- {cap['capability_id']}：{cap['title']}；风险 {cap['risk_level']}；审批 {cap['approval_policy']}；必填 {required}"


            )


        return "\n".join(lines)


    usage_rows = conn.execute(


        "select * from usage_daily where user_id = ? order by day desc limit 7",


        (conversation["owner_user_id"],),


    ).fetchall()


    message_count = conn.execute(


        "select count(*) as count from messages where conversation_id = ?",


        (conversation["conversation_id"],),


    ).fetchone()["count"]


    attachment_count = 0


    trace_count = 0


    for row in conn.execute("select metadata_json from messages where conversation_id = ?", (conversation["conversation_id"],)):


        metadata = _safe_json_dict(row["metadata_json"])


        attachment_count += len(metadata.get("attachments") or [])


        trace_count += len(metadata.get("trace") or [])


    usage = _usage_totals([dict(row) for row in usage_rows])


    return (


        "当前 Hermi 会话上下文：\n"


        f"- 标题：{conversation['title']}\n"


        f"- 来源：{conversation['channel']}\n"


        f"- 目标人格：{_active_profile_name(conn, config)}\n"

        f"- 消息数：{message_count}\n"


        f"- 附件数：{attachment_count}\n"


        f"- 思考/工具事件：{trace_count}\n"


        f"- 近 7 日 total token：{usage['total_tokens']}\n"


        f"- 上下文状态：{_context_window_summary(message_count, usage)['status']}\n\n"


        "界面入口：右侧点“✓”打开审批面板，再点“临时”，看“当前会话”。"


    )








def _load_soul_text(config: HermiConfig) -> str:


    path = Path(config.soul_path)


    if not path.is_absolute():


        path = Path.cwd() / path


    if not path.exists() or not path.is_file():


        return ""


    try:


        return path.read_text(encoding="utf-8").strip()[:20000]


    except OSError:


        return ""








def _sse(event: str, data: dict[str, Any]) -> str:


    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"








def _create_message_run(conn, conversation_id: str, user_id: str, lock: threading.RLock) -> dict[str, Any]:


    now = time.time()


    run_id = f"run-{uuid.uuid4().hex[:12]}"


    with lock:


        conn.execute(


            """


            insert into message_runs (


              run_id, conversation_id, user_id, status, events_json, final_json, error, created_at, updated_at


            ) values (?, ?, ?, 'queued', '[]', '{}', '', ?, ?)


            """,


            (run_id, conversation_id, user_id, now, now),


        )


        conn.commit()


    return _message_run_by_id(conn, run_id)








def _message_run_worker(


    conn,


    app: FastAPI,


    config: HermiConfig,


    run_id: str,


    conversation_id: str,


    body: MessageCreate,


    user: dict[str, Any],


    post_message,


) -> None:


    _mark_message_run_status(conn, run_id, "running", app.state.run_lock)


    try:


        if hasattr(app.state.hermes_adapter, "stream_events"):


            for chunk in _stream_hermi_message(

                conn, app, config, conversation_id, body.content, body.attachments, user,
                capability_id=body.capability_id, run_id=run_id

            ):

                parsed = _parse_sse_chunk(chunk)


                if parsed:


                    _append_message_run_event(conn, run_id, parsed["event"], parsed["data"], app.state.run_lock)


                    if parsed["event"] == "final":


                        _finish_message_run(conn, run_id, parsed["data"], app.state.run_lock)


            return


        if _message_run_cancelled(conn, run_id):

            return

        result = post_message(conversation_id, body, user)

        if _message_run_cancelled(conn, run_id):

            return

        _append_message_run_event(conn, run_id, "final", result, app.state.run_lock)


        _finish_message_run(conn, run_id, result, app.state.run_lock)


    except Exception as exc:


        _fail_message_run(conn, run_id, f"{type(exc).__name__}: {exc}", app.state.run_lock)








def _stream_message_run(conn, run_id: str, lock: threading.RLock):


    sent = 0


    deadline = time.time() + 1800


    last_heartbeat = 0.0


    yield _sse("status", {"status": "queued", "run_id": run_id})


    while time.time() < deadline:


        row = _message_run_by_id(conn, run_id)


        events = _safe_json_list(row.get("events_json"))


        while sent < len(events):


            event = events[sent]


            sent += 1


            yield _sse(str(event.get("event") or "status"), dict(event.get("data") or {}))


        if row.get("status") in {"done", "failed", "cancelled"}:

            if row.get("status") == "failed":


                yield _sse("error", {"error": row.get("error") or "message_run_failed"})


            return


        if time.time() - last_heartbeat >= 10:


            last_heartbeat = time.time()


            yield _sse("status", {"status": row.get("status") or "running"})


        time.sleep(0.25)


    yield _sse("status", {"status": "still_running", "run_id": run_id})








def _append_message_run_event(conn, run_id: str, event: str, data: dict[str, Any], lock: threading.RLock) -> None:


    with lock:


        row = _message_run_by_id(conn, run_id)


        events = _safe_json_list(row.get("events_json"))


        events.append({"event": event, "data": data, "created_at": time.time()})


        conn.execute(


            "update message_runs set events_json = ?, updated_at = ? where run_id = ?",


            (json.dumps(events, ensure_ascii=False), time.time(), run_id),


        )


        conn.commit()








def _mark_message_run_status(conn, run_id: str, status: str, lock: threading.RLock) -> None:

    with lock:


        conn.execute(


            "update message_runs set status = ?, updated_at = ? where run_id = ?",


            (status, time.time(), run_id),


        )


        conn.commit()





def _message_run_cancelled(conn, run_id: str) -> bool:

    row = conn.execute("select status from message_runs where run_id = ?", (run_id,)).fetchone()

    return bool(row and row["status"] == "cancelled")







def _finish_message_run(conn, run_id: str, final: dict[str, Any], lock: threading.RLock) -> None:


    with lock:


        conn.execute(


            "update message_runs set status = 'done', final_json = ?, error = '', updated_at = ? where run_id = ?",


            (json.dumps(final, ensure_ascii=False), time.time(), run_id),


        )


        conn.commit()








def _fail_message_run(conn, run_id: str, error: str, lock: threading.RLock) -> None:


    with lock:


        conn.execute(


            "update message_runs set status = 'failed', error = ?, updated_at = ? where run_id = ?",


            (error, time.time(), run_id),


        )


        conn.commit()








def _message_run_by_id(conn, run_id: str) -> dict[str, Any]:


    row = conn.execute("select * from message_runs where run_id = ?", (run_id,)).fetchone()


    if not row:


        raise HTTPException(status_code=404, detail="message_run_not_found")


    return dict(row)








def _public_message_run(row: dict[str, Any]) -> dict[str, Any]:


    return {


        "run_id": row["run_id"],


        "conversation_id": row["conversation_id"],


        "status": row["status"],


        "events": _safe_json_list(row.get("events_json")),


        "final": _safe_json_dict(row.get("final_json")),


        "error": row.get("error") or "",


        "created_at": row["created_at"],


        "updated_at": row["updated_at"],


    }








def _parse_sse_chunk(chunk: str) -> dict[str, Any] | None:


    event = ""


    data = ""


    for line in str(chunk or "").splitlines():


        if line.startswith("event:"):


            event = line[6:].strip()


        elif line.startswith("data:"):


            data = line[5:].strip()


    if not event or not data:


        return None


    try:


        parsed = json.loads(data)


    except json.JSONDecodeError:


        parsed = {"content": data}


    return {"event": event, "data": parsed if isinstance(parsed, dict) else {"content": parsed}}








def _today_key() -> str:


    return time.strftime("%Y-%m-%d", time.localtime())








def _usage_row(conn, user_id: str, day: str | None = None) -> dict[str, Any] | None:

    day = day or _today_key()


    row = conn.execute(


        "select * from usage_daily where usage_key = ?",


        (f"{user_id}:{day}",),


    ).fetchone()


    return dict(row) if row else None





def _quota_window_minutes(user: dict[str, Any]) -> int:

    if user.get("role") in {"owner", "channel"}:

        return 1440

    minutes = PermissionChecker(user).get_number("quota_window_minutes")

    return max(1, minutes or 1440)





def _quota_window_bounds(user: dict[str, Any], now: float | None = None) -> tuple[float, float, int]:

    current = float(now if now is not None else time.time())

    minutes = _quota_window_minutes(user)

    seconds = minutes * 60

    origin = float(user.get("created_at") or current)

    elapsed = max(0.0, current - origin)

    start = origin + int(elapsed // seconds) * seconds

    return start, start + seconds, minutes





def _quota_window_row(conn, user: dict[str, Any], now: float | None = None) -> dict[str, Any] | None:

    start, _, _ = _quota_window_bounds(user, now)

    key = f"{user['user_id']}:{int(start)}"

    row = conn.execute("select * from usage_windows where window_key = ?", (key,)).fetchone()

    return dict(row) if row else None





def _ensure_quota_window(
    conn,
    user: dict[str, Any],
    config: HermiConfig,
    *,
    now: float | None = None,
) -> dict[str, Any]:
    """Create a window and carry only an immediately preceding token overage."""
    if user.get("role") in {"owner", "channel"}:
        return {}

    current = float(now if now is not None else time.time())
    start, end, _ = _quota_window_bounds(user, current)
    key = f"{user['user_id']}:{int(start)}"
    existing = conn.execute("select * from usage_windows where window_key = ?", (key,)).fetchone()
    if existing:
        return dict(existing)

    debt_tokens = 0
    previous = conn.execute(
        """
        select total_tokens, window_end_at
        from usage_windows
        where user_id = ? and window_end_at <= ?
        order by window_end_at desc
        limit 1
        """,
        (user["user_id"], start),
    ).fetchone()
    token_limit = _token_limit_for_user(user, config)
    if previous and abs(float(previous["window_end_at"]) - start) < 0.001 and token_limit is not None:
        debt_tokens = max(0, int(previous["total_tokens"] or 0) - int(token_limit))

    conn.execute(
        """
        insert or ignore into usage_windows (
          window_key, user_id, window_start_at, window_end_at, text_messages, file_uploads, total_tokens
        ) values (?, ?, ?, ?, 0, 0, ?)
        """,
        (key, user["user_id"], start, end, debt_tokens),
    )
    row = conn.execute("select * from usage_windows where window_key = ?", (key,)).fetchone()
    return dict(row) if row else {}


def _increment_quota_window_usage(

    conn,

    user: dict[str, Any],

    *,

    text_messages: int = 0,

    file_uploads: int = 0,

    total_tokens: int = 0,

    config: HermiConfig | None = None,

) -> None:

    if user.get("role") in {"owner", "channel"}:

        return

    start, end, _ = _quota_window_bounds(user)

    if config is not None:

        _ensure_quota_window(conn, user, config)

    key = f"{user['user_id']}:{int(start)}"

    conn.execute(

        """

        insert into usage_windows (

          window_key, user_id, window_start_at, window_end_at, text_messages, file_uploads, total_tokens

        ) values (?, ?, ?, ?, ?, ?, ?)

        on conflict(window_key) do update set

          text_messages = text_messages + excluded.text_messages,

          file_uploads = file_uploads + excluded.file_uploads,

          total_tokens = total_tokens + excluded.total_tokens

        """,

        (key, user["user_id"], start, end, text_messages, file_uploads, total_tokens),

    )





def _quota_window_summary(conn, user: dict[str, Any], config: HermiConfig) -> dict[str, Any]:

    now = time.time()

    start, end, minutes = _quota_window_bounds(user, now)

    row = _ensure_quota_window(conn, user, config, now=now)

    base_token_limit = _token_limit_for_user(user, config)
    temporary_granted_tokens = _temporary_quota_tokens(conn, user, now=now)
    token_limit = None if base_token_limit is None else base_token_limit + temporary_granted_tokens

    file_limit = _file_limit_for_user(user, config)

    return {

        "window_minutes": minutes,

        "window_start_at": start,

        "window_end_at": end,

        "remaining_seconds": max(0, int(end - now)),

        "text_messages": int(row.get("text_messages") or 0),

        "total_tokens": int(row.get("total_tokens") or 0),

        "token_limit": token_limit,

        "temporary_granted_tokens": temporary_granted_tokens,

        "remaining_tokens": None if token_limit is None else int(token_limit) - int(row.get("total_tokens") or 0),

        "usage_percent": None if token_limit is None or token_limit <= 0 else min(100, round(int(row.get("total_tokens") or 0) * 100 / token_limit)),

        "remaining_percent": None if token_limit is None or token_limit <= 0 else min(100, round((int(token_limit) - int(row.get("total_tokens") or 0)) * 100 / token_limit)),

        "file_uploads": int(row.get("file_uploads") or 0),

        "file_size_limit_mb": None if file_limit is None else int(file_limit / 1024 / 1024),

    }







def _increment_usage(


    conn,


    user_id: str,


    *,


    text_messages: int = 0,


    image_messages: int = 0,


    file_uploads: int = 0,


    prompt_tokens: int = 0,


    completion_tokens: int = 0,


    total_tokens: int = 0,


) -> None:


    day = _today_key()


    usage_key = f"{user_id}:{day}"


    conn.execute(


        """


        insert into usage_daily (


          usage_key, user_id, day, text_messages, image_messages, file_uploads,


          prompt_tokens, completion_tokens, total_tokens


        )


        values (?, ?, ?, ?, ?, ?, ?, ?, ?)


        on conflict(usage_key) do update set


          text_messages = text_messages + excluded.text_messages,


          image_messages = image_messages + excluded.image_messages,


          file_uploads = file_uploads + excluded.file_uploads,


          prompt_tokens = prompt_tokens + excluded.prompt_tokens,


          completion_tokens = completion_tokens + excluded.completion_tokens,


          total_tokens = total_tokens + excluded.total_tokens


        """,


        (


            usage_key,


            user_id,


            day,


            text_messages,


            image_messages,


            file_uploads,


            prompt_tokens,


            completion_tokens,


            total_tokens,


        ),


    )








def _increment_conversation_usage(
    conn,
    conversation_id: str,
    user_id: str,
    *,
    prompt_tokens: int = 0,
    completion_tokens: int = 0,
    total_tokens: int = 0,
    cache_read_tokens: int = 0,
    cache_reported: bool = False,
) -> None:
    conn.execute(
        """
        insert into conversation_usage (
          conversation_id, user_id, prompt_tokens, completion_tokens, total_tokens, cache_read_tokens, cache_reported, updated_at
        ) values (?, ?, ?, ?, ?, ?, ?, ?)
        on conflict(conversation_id) do update set
          user_id = excluded.user_id,
          prompt_tokens = prompt_tokens + excluded.prompt_tokens,
          completion_tokens = completion_tokens + excluded.completion_tokens,
          total_tokens = total_tokens + excluded.total_tokens,
          cache_read_tokens = cache_read_tokens + excluded.cache_read_tokens,
          cache_reported = max(cache_reported, excluded.cache_reported),
          updated_at = excluded.updated_at
        """,
        (conversation_id, user_id, prompt_tokens, completion_tokens, total_tokens, cache_read_tokens, 1 if cache_reported else 0, time.time()),
    )


def _increment_usage_from_hermes(
    conn,
    user_id: str,
    hermes_adapter: Any,
    *,
    conversation_id: str | None = None,
    config: HermiConfig | None = None,
) -> int:


    usage = getattr(hermes_adapter, "last_usage", {}) or {}


    if not isinstance(usage, dict):


        return 0


    prompt_tokens = int(usage.get("prompt_tokens") or usage.get("input_tokens") or 0)


    completion_tokens = int(usage.get("completion_tokens") or usage.get("output_tokens") or 0)


    total_tokens = int(usage.get("total_tokens") or (prompt_tokens + completion_tokens))

    cache_read_tokens, cache_reported = _cache_usage_values(usage)


    if prompt_tokens or completion_tokens or total_tokens:


        _increment_usage(


            conn,


            user_id,


            prompt_tokens=prompt_tokens,


            completion_tokens=completion_tokens,


            total_tokens=total_tokens,


        )


        if conversation_id:


            _increment_conversation_usage(


                conn,


                conversation_id,


                user_id,


                prompt_tokens=prompt_tokens,


                completion_tokens=completion_tokens,


                total_tokens=total_tokens,


                cache_read_tokens=cache_read_tokens,


                cache_reported=cache_reported,


            )

        quota_user = conn.execute("select * from users where user_id = ?", (user_id,)).fetchone()

        if quota_user:

            _increment_quota_window_usage(conn, dict(quota_user), total_tokens=total_tokens, config=config)

    return total_tokens


def _cache_usage_values(usage: dict[str, Any]) -> tuple[int, bool]:
    """Normalize provider-specific read-cache fields without treating absence as zero."""
    candidates: list[Any] = [
        usage.get("cache_read_tokens"),
        usage.get("cached_tokens"),
        usage.get("cache_read_input_tokens"),
    ]
    details = usage.get("prompt_tokens_details")
    if isinstance(details, dict):
        candidates.extend((details.get("cached_tokens"), details.get("cache_read_tokens")))
    for value in candidates:
        if value is None:
            continue
        try:
            return max(0, int(value)), True
        except (TypeError, ValueError):
            return 0, True
    return 0, False








def _token_limit_for_user(user: dict[str, Any], config: HermiConfig) -> int | None:

    if user.get("role") in {"owner", "channel"}:

        return None

    explicit = _explicit_permission_number(user, "quota_token_limit")

    if explicit is not None:

        return None if explicit < 0 else explicit

    if user.get("quota_policy") == "friend_trusted":

        return config.friend_trusted_token_limit

    return config.friend_token_limit





def _temporary_quota_tokens(conn, user: dict[str, Any], *, now: float | None = None) -> int:
    if user.get("role") in {"owner", "channel"}:
        return 0
    current = float(now if now is not None else time.time())
    row = conn.execute(
        """
        select coalesce(sum(token_amount), 0) as total
        from temporary_quota_grants
        where user_id = ? and window_start_at <= ? and window_end_at > ?
        """,
        (user["user_id"], current, current),
    ).fetchone()
    return max(0, int(row["total"] or 0)) if row else 0


def _file_limit_for_user(user: dict[str, Any], config: HermiConfig) -> int | None:

    if user.get("role") in {"owner", "channel"}:

        return None

    explicit = _explicit_permission_number(user, "file_size_limit_mb")

    if explicit is not None:

        return None if explicit <= 0 else explicit * 1024 * 1024

    if user.get("quota_policy") == "friend_trusted":

        return config.friend_trusted_file_size_limit

    return config.friend_file_size_limit


def _explicit_permission_number(user: dict[str, Any], key: str) -> int | None:
    """Return a numeric permission only when the user explicitly saved it."""
    permissions = _permissions_dict(user.get("permissions"))
    value = permissions.get(key)
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    return int(value)







def _require_token_quota(conn, user: dict[str, Any], config: HermiConfig) -> None:

    base_limit = _token_limit_for_user(user, config)
    limit = None if base_limit is None else base_limit + _temporary_quota_tokens(conn, user)


    if limit is None:


        return


    row = _ensure_quota_window(conn, user, config)

    used = int((row or {}).get("total_tokens") or 0)


    if used >= limit:


        _, end, _ = _quota_window_bounds(user)

        raise HTTPException(
            status_code=429,
            detail="token_quota_exceeded",
            headers={"Retry-After": str(max(1, math.ceil(end - time.time())))},
        )








def _safe_filename(name: str) -> str:
    # Strip only truly dangerous characters; preserve CJK punctuation, parens, etc.
    cleaned = re.sub(r'[<>:"/\\|?*\x00-\x1f]+', "_", str(name or "upload.bin")).strip(" .")
    return cleaned[:250] or "upload.bin"






def _media_dir(config: HermiConfig) -> Path:


    media_dir = Path(config.media_dir)


    if not media_dir.is_absolute():


        media_dir = Path.cwd() / media_dir


    media_dir.mkdir(parents=True, exist_ok=True)


    return media_dir








def _file_by_id(conn, file_id: str) -> dict[str, Any]:


    row = conn.execute("select * from media_files where file_id = ?", (file_id,)).fetchone()


    if not row:


        raise HTTPException(status_code=404, detail="file_not_found")


    return dict(row)








def _file_for_user(conn, file_id: str, user: dict[str, Any]) -> dict[str, Any]:

    row = _file_by_id(conn, file_id)


    if user.get("can_approve") or row.get("created_by") == user.get("user_id") or row.get("visibility") == "shared":


        return row


    raise HTTPException(status_code=404, detail="file_not_found")





def _owned_file_for_user(conn, file_id: str, user: dict[str, Any]) -> dict[str, Any]:

    row = _file_by_id(conn, file_id)

    if user.get("can_approve") or row.get("created_by") == user.get("user_id"):

        return row

    raise HTTPException(status_code=403, detail="file_forbidden")







def _resolve_message_attachments(


    conn,


    attachments: list[dict[str, Any] | str],


    user: dict[str, Any],


) -> list[dict[str, Any]]:


    refs: list[dict[str, Any]] = []


    for item in attachments or []:


        file_id = str(item.get("file_id") if isinstance(item, dict) else item).strip()


        if not file_id:


            continue


        row = _file_for_user(conn, file_id, user)


        refs.append(


            {


                "file_id": row["file_id"],


                "original_name": row["original_name"],


                "mime": row["mime"],


                "size_bytes": row["size_bytes"],


                "sha256": row["sha256"],


                "server_path": row["storage_path"],


                "download_url": f"/files/{row['file_id']}/content",


            }


        )


    return refs








def _parse_qq_attachment_ref(item: str) -> tuple[str, str]:


    kind, sep, value = str(item or "").partition(":")


    if not sep:


        return "file", str(item or "").strip()


    # QLOS appends display metadata after the actual local file reference.
    return kind.strip().lower() or "file", value.split(" | ", 1)[0].strip()








def _attachment_original_name(kind: str, value: str) -> str:


    if value.startswith(("http://", "https://", "data:")):


        parsed = urlparse(value)


        name = Path(unquote(parsed.path)).name


    else:


        name = Path(value).name


    if not name:


        name = "qq-image" if kind == "image" else "qq-file"


    return _safe_filename(name)








def _attachment_mime(kind: str, original_name: str) -> str:


    guessed, _ = mimetypes.guess_type(original_name)


    if guessed:


        return guessed


    if kind == "image":


        return "image/unknown"


    return "application/octet-stream"


def _sniff_attachment_mime(file_bytes: bytes, fallback: str) -> str:

    if file_bytes.startswith(b"\x89PNG\r\n\x1a\n"):

        return "image/png"

    if file_bytes.startswith(b"\xff\xd8\xff"):

        return "image/jpeg"

    if file_bytes.startswith((b"GIF87a", b"GIF89a")):

        return "image/gif"

    if len(file_bytes) >= 12 and file_bytes.startswith(b"RIFF") and file_bytes[8:12] == b"WEBP":

        return "image/webp"

    return fallback


def _image_suffix_for_mime(mime: str) -> str:

    return {

        "image/png": ".png",

        "image/jpeg": ".jpg",

        "image/gif": ".gif",

        "image/webp": ".webp",

    }.get(mime, "")








def _ingest_qq_attachments(


    conn,


    config: HermiConfig,


    body: QQEventIn,


    user: dict[str, Any],


    conversation_id: str,


) -> list[dict[str, Any]]:


    refs: list[dict[str, Any]] = []


    media_permissions = PermissionChecker(user).get_composite("media")


    max_size_mb = int(media_permissions.get("max_size_mb") or 0)


    max_size_bytes = max_size_mb * 1024 * 1024 if max_size_mb > 0 else 0


    for raw in body.attachments or []:


        kind, value = _parse_qq_attachment_ref(str(raw))


        if not value:


            continue


        now = time.time()


        file_id = f"file-{uuid.uuid4().hex[:12]}"


        original_name = _attachment_original_name(kind, value)


        mime = _attachment_mime(kind, original_name)


        digest = hashlib.sha256(f"{kind}:{value}".encode("utf-8")).hexdigest()


        size_bytes = 0


        storage_path = ""


        ingestion = "reference"


        local_path = Path(value) if not value.startswith(("http://", "https://", "data:")) else None


        if local_path and local_path.exists() and local_path.is_file():


            file_bytes = local_path.read_bytes()


            if max_size_bytes and len(file_bytes) > max_size_bytes:


                raise HTTPException(status_code=413, detail="media_file_too_large")


            digest = hashlib.sha256(file_bytes).hexdigest()


            size_bytes = len(file_bytes)


            mime = _sniff_attachment_mime(file_bytes, mime)


            if kind == "image" and not Path(original_name).suffix:


                original_name = f"qq-image{_image_suffix_for_mime(mime) or '.bin'}"


            suffix = Path(original_name).suffix[:20]


            destination = _media_dir(config) / f"{file_id}{suffix}"


            shutil.copyfile(local_path, destination)


            storage_path = str(destination)


            ingestion = "copied"


        conn.execute(


            """


            insert into media_files (


              file_id, conversation_id, source_channel, source_message_id, original_name,


              mime, size_bytes, sha256, storage_path, visibility, created_by,


              expires_at, created_at, metadata_json


            ) values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)


            """,


            (


                file_id,


                conversation_id,


                "qq",


                body.message_id,


                original_name,


                mime,


                size_bytes,


                digest,


                storage_path,


                "shared",


                user["user_id"],


                None,


                now,


                json.dumps(


                    {


                        "kind": kind,


                        "raw_ref": str(raw),


                        "remote_url": value if value.startswith(("http://", "https://", "data:")) else "",


                        "auto_vision": False,


                        "ingestion": ingestion,


                    },


                    ensure_ascii=False,


                ),


            ),


        )


        refs.append(


            {


                "file_id": file_id,


                "original_name": original_name,


                "mime": mime,


                "size_bytes": size_bytes,


                "sha256": digest,


                "server_path": storage_path,


                "download_url": f"/files/{file_id}/content" if storage_path else "",


            }


        )


    return refs








def _public_attachment_refs(attachment_refs: list[dict[str, Any]]) -> list[dict[str, Any]]:


    return [


        {


            "file_id": item["file_id"],


            "original_name": item["original_name"],


            "mime": item["mime"],


            "size_bytes": item["size_bytes"],


            "download_url": item["download_url"],


        }


        for item in attachment_refs


    ]








MEDIA_PATH_RE = re.compile(


    r"(?:MEDIA:)?(?P<path>[A-Za-z]:\\[^\r\n`\"<>|]+?\.(?:png|jpg|jpeg|gif|webp|bmp|pdf|docx|doc|xlsx|xls|pptx|ppt|tar\.gz|tar|gz|zip|rar|7z|txt|py|js|ts|json|yaml|yml|md|csv|xml|html|htm|css|sql|sh|bat|ps1|ini|cfg|conf|toml))",


    re.IGNORECASE,


)


LOCAL_MEDIA_PATH_LINE_RE = re.compile(


    r"(?im)^\s*(?:截图路径|图片路径|文件路径|路径|path|media|image path|file path)?\s*[:：-]?\s*"


    r"(?:MEDIA:)?[A-Za-z]:\\[^\r\n`\"<>|]+?\.(?:png|jpg|jpeg|gif|webp|bmp|pdf|docx|doc|xlsx|xls|pptx|ppt|tar\.gz|tar|gz|zip|rar|7z|txt|py|js|ts|json|yaml|yml|md|csv|xml|html|htm|css|sql|sh|bat|ps1|ini|cfg|conf|toml)\s*$"


)








def _extract_local_media_paths(text: str) -> list[Path]:


    paths: list[Path] = []


    seen: set[str] = set()


    for match in MEDIA_PATH_RE.finditer(str(text or "")):


        raw = match.group("path").strip().rstrip(").,，。")


        path = Path(raw)


        key = str(path).lower()


        if key in seen or not path.exists() or not path.is_file():


            continue


        seen.add(key)


        paths.append(path)


    return paths[:8]








def _strip_local_media_path_text(text: str) -> str:


    cleaned = LOCAL_MEDIA_PATH_LINE_RE.sub("", str(text or ""))


    cleaned = MEDIA_PATH_RE.sub("图片已附上", cleaned)


    return re.sub(r"\n{3,}", "\n\n", cleaned).strip()








def _strip_media_markers(text: str, *, strip_local_paths: bool = False) -> str:


    cleaned = re.sub(r"(?m)^\s*MEDIA:[^\r\n]+(?:\r?\n)?", "", str(text or ""))


    if strip_local_paths:


        cleaned = _strip_local_media_path_text(cleaned)


    return re.sub(r"\n{3,}", "\n\n", cleaned).strip()








def _ingest_local_media_paths(


    conn,


    config: HermiConfig,


    conversation_id: str,


    text: str,


    created_by: str,


) -> list[dict[str, Any]]:


    refs: list[dict[str, Any]] = []


    for source_path in _extract_local_media_paths(text):


        file_bytes = source_path.read_bytes()


        if not file_bytes:


            continue


        now = time.time()


        file_id = f"file-{uuid.uuid4().hex[:12]}"


        original_name = _safe_filename(source_path.name or "media.png")


        suffix = source_path.suffix[:20]


        media_root = _media_dir(config).resolve()

        try:
            source_path.resolve().relative_to(media_root)
            destination = source_path.resolve()
        except ValueError:
            destination = media_root / f"{file_id}{suffix}"


        if destination != source_path.resolve():
            shutil.copyfile(source_path, destination)


        mime = mimetypes.guess_type(original_name)[0] or "application/octet-stream"


        digest = hashlib.sha256(file_bytes).hexdigest()


        conn.execute(


            """


            insert into media_files (


              file_id, conversation_id, source_channel, source_message_id, original_name,


              mime, size_bytes, sha256, storage_path, visibility, created_by,


              expires_at, created_at, metadata_json


            ) values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)


            """,


            (


                file_id,


                conversation_id,


                "hermes",


                None,


                original_name,


                mime,


                len(file_bytes),


                digest,


                str(destination),


                "private",


                created_by,


                None,


                now,


                json.dumps({"source_path": str(source_path)}, ensure_ascii=False),


            ),


        )


        _audit(conn, "file_imported_from_hermes", created_by, {"file_id": file_id, "source_path": str(source_path)})


        refs.append(


            {


                "file_id": file_id,


                "original_name": original_name,


                "mime": mime,


                "size_bytes": len(file_bytes),


                "sha256": digest,


                "server_path": str(destination),


                "download_url": f"/files/{file_id}/content",


            }


        )


    return refs








def _filter_action_for_user(action: dict[str, Any] | None, user: dict[str, Any]) -> tuple[dict[str, Any] | None, str]:


    if action and action.get("type") == "qq.send" and user.get("role") != "owner":


        return None, "QQ 外联仅由 Owner 通过薇达处理；这里不会发送消息，也不会提供 Owner 的 QQ 联系方式。"


    return action, ""




def _augment_qq_action_with_media(action: dict[str, Any] | None, media_refs: list[dict[str, Any]]) -> None:


    if not action or action.get("type") != "qq.send" or not media_refs:


        return


    images = action.get("images") if isinstance(action.get("images"), list) else []


    attachments = action.get("attachments") if isinstance(action.get("attachments"), list) else []


    for item in media_refs:


        payload = {


            "file_id": item["file_id"],


            "path": item["server_path"],


            "original_name": item["original_name"],


            "mime": item["mime"],


        }


        if str(item.get("mime") or "").startswith("image/"):


            images.append(payload)


        else:


            attachments.append({"type": "file", **payload})


    action["images"] = images


    action["attachments"] = attachments


    message = _strip_local_media_path_text(str(action.get("message") or ""))


    action["message"] = message or "图片已附上。"








def _is_attachment_only_message(content: str, attachment_refs: list[dict[str, Any]]) -> bool:


    if not attachment_refs:


        return False


    text = str(content or "").strip().lower()


    return not text or text in {"[image]", "[file]", "[video]", "[record]", "[图片]", "[文件]", "请查看我上传的文件。"}


def _attachment_waiting_reply(attachment_refs: list[dict[str, Any]]) -> str:


    count = len(attachment_refs)


    noun = "图片" if count == 1 and str(attachment_refs[0].get("mime") or "").startswith("image/") else "文件"


    return f"已收到{noun}。请告诉我希望我做什么；在你明确要求前，我不会读取、识别或分析其中内容。"


def _is_internal_action_trace(content: str) -> bool:


    return "<<<HERMI_ACTION" in str(content or "")


def _trace_repeats_final_reply(trace_content: str, final_content: str) -> bool:
    """Some Hermes streams label the completed answer as a thought event."""
    trace_text = re.sub(r"\s+", " ", str(trace_content or "").strip())
    final_text = re.sub(r"\s+", " ", str(final_content or "").strip())
    return bool(trace_text and final_text and trace_text == final_text)


def _needs_image_vision(content: str, attachment_refs: list[dict[str, Any]]) -> bool:


    if not any(str(item.get("mime") or "").startswith("image/") for item in attachment_refs):


        return False


    text = str(content or "").lower()


    return bool(re.search(r"识图|识别|ocr|图片.*(?:内容|文字|是什么)|截图.*(?:内容|文字|是什么)|(?:看看|描述).*(?:图片|截图|图)", text))


def _image_vision_enabled() -> bool:


    return os.environ.get("HERMI_IMAGE_VISION_ENABLED", "").strip().lower() in {"1", "true", "yes", "on"}


def _image_vision_unavailable_reply() -> str:


    return "图片已保存，但当前识图服务不可用，所以我不会猜测图片内容。请稍后重试，或先让 Owner 配置可用的视觉服务后再识别。"


def _history_with_attachment_context(


    history: list[dict[str, str]],


    attachment_refs: list[dict[str, Any]],


) -> list[dict[str, str]]:


    if not history or not attachment_refs:


        return history


    enriched = [dict(item) for item in history]


    for index in range(len(enriched) - 1, -1, -1):


        if enriched[index].get("role") == "user":


            enriched[index]["content"] = (


                str(enriched[index].get("content") or "").rstrip()


                + "\n\n"


                + _attachment_context_for_hermes(attachment_refs)


            )


            break


    return enriched








def _attachment_context_for_hermes(attachment_refs: list[dict[str, Any]]) -> str:


    lines = [


        "[Hermi server attachments]",


        "These files were uploaded through Hermi and are stored on the Hermi/Hermes host. Use server_path or file_id; ignore any client/browser local paths.",


        "Do not open, read, OCR, identify, or analyze an attachment automatically. Only access a file when the latest user instruction explicitly requires it. For an explicit image request, inspect the relevant stored image before answering; never guess what an unseen image contains.",


    ]


    for item in attachment_refs:


        lines.append(


            "- "


            + f"file_id={item['file_id']} "


            + f"original_name={item['original_name']} "


            + f"mime={item['mime']} "


            + f"size_bytes={item['size_bytes']} "


            + f"sha256={item['sha256']} "


            + f"server_path={item['server_path']} "


            + f"download_url={item['download_url']}"


        )


    return "\n".join(lines)








def _stream_hermi_message(

    conn,


    app: FastAPI,


    config: HermiConfig,


    conversation_id: str,


    content: str,


    attachments: list[dict[str, Any] | str],


    user: dict[str, Any],


    capability_id: str = "",

    run_id: str = "",

):

    conversation = _require_conversation_for_user(conn, conversation_id, user)

    # Match the non-streaming endpoint: issue the server-side subject context
    # before any early reply path can return.
    _record_hermi_tool_identity(config, conversation, user)


    _require_token_quota(conn, user, config)


    attachment_refs = _resolve_message_attachments(conn, attachments, user)


    user_message = _insert_message(


        conn,


        conversation_id,


        "user",


        content,


        "hermi",


        metadata={"attachments": _public_attachment_refs(attachment_refs)} if attachment_refs else None,


    )

    _increment_usage(conn, user["user_id"], text_messages=1)

    _increment_quota_window_usage(conn, user, text_messages=1, config=config)

    conn.execute(

        "update conversations set updated_at = ? where conversation_id = ?",

        (time.time(), conversation_id),

    )

    if _is_attachment_only_message(content, attachment_refs):

        assistant_message = _insert_message(

            conn,

            conversation_id,

            "assistant",

            _attachment_waiting_reply(attachment_refs),

            "hermi",

        )

        conn.commit()

        yield _sse("final", {"user": user_message, "assistant": assistant_message})

        return

    if _needs_image_vision(content, attachment_refs) and not _image_vision_enabled():

        assistant_message = _insert_message(

            conn,

            conversation_id,

            "assistant",

            _image_vision_unavailable_reply(),

            "hermi",

        )

        conn.commit()

        yield _sse("final", {"user": user_message, "assistant": assistant_message})

        return

    if _permission_result_for_user(user, "chat") == "approval":

        approval_reply = _create_chat_message_approval(conn, conversation, content, user)

        assistant_message = _insert_message(conn, conversation_id, "assistant", approval_reply, "hermi")

        conn.commit()

        yield _sse("final", {"user": user_message, "assistant": assistant_message})

        return

    local_reply = _local_hermi_command_reply(conn, config, conversation, content, user)

    if local_reply is not None:

        assistant_message = _insert_message(conn, conversation_id, "assistant", local_reply, "hermi")

        _auto_name_conversation(conn, conversation, content, _active_profile_name(conn, config))

        conn.commit()


        yield _sse("final", {"user": user_message, "assistant": assistant_message})

        return

    if user.get("role") == "owner":

        owner_schedule = _owner_scheduled_request_reply(conn, conversation, content)

        if owner_schedule is not None:

            schedule_reply, job = owner_schedule

            assistant_message = _insert_message(

                conn,

                conversation_id,

                "assistant",

                schedule_reply,

                "hermi",

                metadata={"action_type": "scheduled.create", "job_id": job["job_id"], "task_id": job.get("task_id")},

            )

            _auto_name_conversation(conn, conversation, content, _active_profile_name(conn, config))

            conn.commit()

            yield _sse("final", {"user": user_message, "assistant": assistant_message})

            return

    mixed_scheduled_request = _is_mixed_scheduled_request(content)

    scheduled_reply = _scheduled_chat_permission_reply(

        conn, conversation, content, user, continue_chat=mixed_scheduled_request

    )

    if scheduled_reply is not None and not mixed_scheduled_request:

        assistant_message = _insert_message(conn, conversation_id, "assistant", scheduled_reply, "hermi")

        conn.commit()

        yield _sse("final", {"user": user_message, "assistant": assistant_message})

        return

    scheduled_instruction = scheduled_reply if mixed_scheduled_request else ""

    profile_id = _conversation_profile_id(conn, config, conversation)
    profile_name = _profile_display_name(conn, profile_id)
    user_profile_context, user_profile_revision = pending_user_profile_context(
        conn, str(user["user_id"]), conversation_id
    )
    history = build_hermi_messages(


        _history_with_attachment_context(_conversation_history(conn, conversation_id), attachment_refs),


        user=user,


        conversation=conversation,


        recent_qq_context=_recent_qq_context_for_request(config, user, content),

        soul_text=_load_soul_text(config),

        profile_name=profile_name,
        profile_id=profile_id,
        qq_profile_name=_profile_display_name(conn, config.qq_profile_id),
        media_dir=str(_media_dir(config)),
        user_profile_context=user_profile_context,
        owner_display_name=_owner_display_name(conn),

    )

    if scheduled_instruction:

        history.insert(1, {"role": "system", "content": scheduled_instruction})

    skill_instruction = _skill_capability_instruction(capability_id)

    if skill_instruction:

        history.insert(1, {"role": "system", "content": skill_instruction})

    final_text = ""


    trace_events: list[dict[str, str]] = []


    # The browser needs an immediate clock, while persisted timing must use the
    # gateway's start point rather than the first delayed Hermes trace event.
    trace_started_at = time.time()
    yield _sse("status", {"run_id": run_id, "trace_started_at": trace_started_at})
    profile_context_delivered = False


    try:


        for event in _stream_profile_events(

            app.state.hermes_adapter,

            profile_id,

            history,

            conversation["session_id"],


            conversation["session_key"],


        ):


            event_type = str(event.get("event") or event.get("type") or "")


            event_content = str(event.get("content") or event.get("text") or "")


            if event_type in {"thought", "tool"} and event_content and not _is_internal_action_trace(event_content):


                trace_events.append({"event": event_type, "content": event_content})


                yield _sse(event_type, {"content": event_content})


            if event_type == "final":


                final_text = event_content


        # A provider can close a streaming request after tool calls without a
        # usable final event. Treat that as a failed stream instead of storing
        # an invisible assistant message and leaving the user waiting.
        if not final_text.strip():


            raise RuntimeError("Hermes stream ended without a final reply")


        _increment_usage_from_hermes(
            conn,
            user["user_id"],
            app.state.hermes_adapter,
            conversation_id=conversation_id,
            config=config,
        )
        profile_context_delivered = True


    except Exception:


        try:


            final_text = _chat_profile(

                app.state.hermes_adapter,

                profile_id,

                history,

                conversation["session_id"],


                conversation["session_key"],


            ).strip()


            _increment_usage_from_hermes(
                conn,
                user["user_id"],
                app.state.hermes_adapter,
                conversation_id=conversation_id,
                config=config,
            )
            profile_context_delivered = True


        except Exception:

            final_text = "我这边调用 Hermes 出错了，稍后再试。"

    if not final_text.strip():


        final_text = "这次工具执行已结束，但模型没有返回正文。请稍后重试。"

    if run_id and _message_run_cancelled(conn, run_id):

        return

    if profile_context_delivered:
        mark_user_profile_context_injected(conn, str(user["user_id"]), conversation_id, user_profile_revision)

    reply, action = extract_hermi_action(final_text)

    reply = _friendly_hermes_failure_reply(reply)

    if scheduled_instruction and str((action or {}).get("type") or "") in {"scheduled.create", "cron.create"}:

        action = None

    # Hermes can emit its completed answer once as ``thought`` and once as
    # ``final``. Keep the live stream responsive, but never persist that echo.
    trace_events = [
        event for event in trace_events
        if not _trace_repeats_final_reply(event.get("content", ""), final_text)
    ]


    if not action and not scheduled_instruction:


        action = _infer_hermes_permission_action(reply, content)


    if not action and user.get("role") != "owner" and not scheduled_instruction:


        native_cron_reply = _maybe_create_native_hermes_cron(config, conversation, content, reply)


        if native_cron_reply:


            reply = native_cron_reply


    _repair_recent_native_cron_origin(conversation, content)


    media_refs = _ingest_local_media_paths(conn, config, conversation_id, reply, user["user_id"]) if user.get("role") == "owner" else []


    reply = _strip_media_markers(reply, strip_local_paths=bool(media_refs))


    action, denied_action_reply = _filter_action_for_user(action, user)

    if denied_action_reply:

        reply = (reply + "\n\n" + denied_action_reply).strip()

    _augment_qq_action_with_media(action, media_refs)


    if action and user.get("role") == "owner" and str(action.get("type") or "") in {"scheduled.create", "cron.create"}:

        try:

            _, job = _create_owner_scheduled_job(conn, conversation_id, action)

            reply = (reply + "\n\n" + f"我已经把“{job['summary']}”安排好了，到时间会在这里提醒你。").strip()

            action = None

        except ValueError as exc:

            reply = (reply + "\n\n" + f"这个提醒还差一点信息：{exc}").strip()

            action = None

    if action:

        approval = _create_action_approval(conn, conversation_id, action)

        reply = (reply + "\n\n" + f"已创建审批：{approval['summary']}").strip()


    assistant_metadata = {}


    if trace_events:


        assistant_metadata["trace"] = trace_events


        assistant_metadata["trace_started_at"] = trace_started_at


        assistant_metadata["trace_finished_at"] = time.time()


    if media_refs:


        assistant_metadata["attachments"] = _public_attachment_refs(media_refs)


    if not assistant_metadata:


        assistant_metadata = None


    assistant_message = _insert_message(conn, conversation_id, "assistant", reply, "hermes", metadata=assistant_metadata)

    _auto_name_conversation(conn, conversation, content, profile_name)

    conn.commit()


    yield _sse("final", {"user": user_message, "assistant": assistant_message})








def _public_file(row: dict[str, Any]) -> dict[str, Any]:


    data = dict(row)


    storage_path = str(data.pop("storage_path", "") or "")


    data["download_url"] = f"/files/{data['file_id']}/content" if storage_path else ""


    return data








def _task_by_id(conn, task_id: str) -> dict[str, Any]:


    row = conn.execute("select * from tasks where task_id = ?", (task_id,)).fetchone()


    if not row:


        raise HTTPException(status_code=404, detail="task_not_found")


    return dict(row)








def _safe_node_id(value: str) -> str:


    return re.sub(r"[^A-Za-z0-9_.:-]+", "-", str(value or "").strip())[:80].strip("-")








def _node_by_id(conn, node_id: str) -> dict[str, Any]:


    row = conn.execute("select * from nodes where node_id = ?", (node_id,)).fetchone()


    if not row:


        raise HTTPException(status_code=404, detail="node_not_found")


    return dict(row)








def _public_node(row: dict[str, Any]) -> dict[str, Any]:


    data = dict(row)


    data.pop("token", None)


    try:


        data["capabilities"] = json.loads(str(data.get("capabilities_json") or "[]"))


    except json.JSONDecodeError:


        data["capabilities"] = []


    data["policy"] = _json_object(data.get("policy_json"))


    return data








def _node_job_by_id(conn, job_id: str) -> dict[str, Any]:


    row = conn.execute("select * from node_jobs where job_id = ?", (job_id,)).fetchone()


    if not row:


        raise HTTPException(status_code=404, detail="node_job_not_found")


    return dict(row)








def _create_node_job_log(


    conn,


    *,


    job_id: str,


    node_id: str,


    event_type: str,


    content: str,


    metadata: dict[str, Any] | None = None,


) -> dict[str, Any]:


    log_id = f"nodelog-{uuid.uuid4().hex[:12]}"


    conn.execute(


        """


        insert into node_job_logs (log_id, job_id, node_id, event_type, content, created_at, metadata_json)


        values (?, ?, ?, ?, ?, ?, ?)


        """,


        (


            log_id,


            job_id,


            node_id,


            event_type,


            content,


            time.time(),


            json.dumps(metadata or {}, ensure_ascii=False),


        ),


    )


    return dict(conn.execute("select * from node_job_logs where log_id = ?", (log_id,)).fetchone())








def _store_node_job_artifact(


    conn,


    config: HermiConfig,


    job: dict[str, Any],


    node: dict[str, Any],


    upload: UploadFile,


    artifact_type: str,


    metadata: dict[str, Any],


) -> dict[str, Any]:


    allowed_types = {"file", "log", "screenshot", "diff", "test_report"}


    normalized_type = artifact_type if artifact_type in allowed_types else "file"


    content = upload.file.read()


    policy = _json_object(node.get("policy_json"))


    max_bytes = int(policy.get("max_artifact_bytes") or 25 * 1024 * 1024)


    if len(content) > max_bytes:


        raise HTTPException(status_code=413, detail="artifact_too_large")


    allowed_artifacts = policy.get("allowed_artifact_types")


    if isinstance(allowed_artifacts, list) and allowed_artifacts and normalized_type not in {str(item) for item in allowed_artifacts}:


        raise HTTPException(status_code=403, detail="artifact_type_denied")


    artifact_id = f"artifact-{uuid.uuid4().hex[:12]}"


    original_name = _safe_filename(upload.filename or f"{artifact_id}.bin")


    digest = hashlib.sha256(content).hexdigest()


    destination_dir = config.media_dir / "node-artifacts" / str(job["job_id"])


    destination_dir.mkdir(parents=True, exist_ok=True)


    destination = destination_dir / f"{artifact_id}-{original_name}"


    destination.write_bytes(content)


    conn.execute(


        """


        insert into node_job_artifacts (


          artifact_id, job_id, node_id, artifact_type, original_name, mime,


          size_bytes, sha256, storage_path, metadata_json, created_at


        ) values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)


        """,


        (


            artifact_id,


            job["job_id"],


            node["node_id"],


            normalized_type,


            original_name,


            upload.content_type or mimetypes.guess_type(original_name)[0] or "application/octet-stream",


            len(content),


            digest,


            str(destination),


            json.dumps(metadata, ensure_ascii=False),


            time.time(),


        ),


    )


    return _public_node_artifact(dict(conn.execute("select * from node_job_artifacts where artifact_id = ?", (artifact_id,)).fetchone()))








def _public_node_artifact(row: dict[str, Any]) -> dict[str, Any]:


    data = dict(row)


    storage_path = data.pop("storage_path", "")


    data["download_url"] = f"/files/node-artifacts/{data['artifact_id']}/content" if storage_path else ""


    data["metadata"] = _json_object(data.get("metadata_json"))


    return data








def _scheduled_job_by_id(conn, job_id: str) -> dict[str, Any]:

    row = conn.execute("select * from scheduled_jobs where job_id = ?", (job_id,)).fetchone()


    if not row:


        raise HTTPException(status_code=404, detail="scheduled_job_not_found")


    return dict(row)





def _scheduled_job_for_user(conn, job_id: str, user: dict[str, Any]) -> dict[str, Any]:

    job = _scheduled_job_by_id(conn, job_id)

    if user.get("can_approve") or job.get("created_by") == user.get("user_id"):

        return job

    raise HTTPException(status_code=403, detail="scheduled_job_forbidden")







def _scheduler_loop(app: FastAPI) -> None:


    while True:


        time.sleep(max(5, int(app.state.config.scheduler_interval_seconds)))


        try:


            _run_due_scheduled_jobs(


                app.state.db,


                app,


                app.state.config,


                actor_user_id="system:scheduler",


                commit=True,


            )


        except Exception:


            continue








def _run_due_scheduled_jobs(


    conn,


    app: FastAPI,


    config: HermiConfig,


    *,


    actor_user_id: str,


    commit: bool = True,


) -> dict[str, Any]:


    lock = getattr(app.state, "scheduler_lock", None)


    if lock and not lock.acquire(blocking=False):


        return {"processed": 0, "jobs": [], "busy": True}


    try:


        now = time.time()


        rows = conn.execute(


            "select * from scheduled_jobs where status = ? order by created_at asc",


            ("active",),


        ).fetchall()


        processed: list[dict[str, Any]] = []


        for row in rows:


            job = dict(row)


            if not _scheduled_job_due(job, now):


                continue


            processed.append(_execute_due_scheduled_job(conn, app, config, job, now))


        _audit(conn, "scheduler_run_once", actor_user_id, {"processed": len(processed)})


        if commit:


            conn.commit()


        return {"processed": len(processed), "jobs": processed}


    finally:


        if lock:


            lock.release()








def _execute_due_scheduled_job(


    conn,


    app: FastAPI,


    config: HermiConfig,


    job: dict[str, Any],


    now: float,


    *,


    force: bool = False,


) -> dict[str, Any]:


    run_id = _start_scheduled_job_run(conn, job["job_id"], now)


    task_id = str(job.get("task_id") or "")


    target = _json_object(job.get("target_json"))


    payload = _json_object(job.get("payload_json"))


    policy = _json_object(job.get("policy_json"))


    delivery = _delivery_list(target)


    if not force:


        delivery = _apply_job_delivery_policy(delivery, policy)


    result: dict[str, Any] = {"job_id": job["job_id"], "delivery": {"hermi": False, "qq": False}}


    if task_id:


        _create_task_event(


            conn,


            task_id=task_id,


            event_type="scheduled_job_due",


            content=f"定时任务到期：{job.get('summary') or job.get('job_id')}",


            metadata={"job_id": job["job_id"], "schedule": job.get("schedule")},


        )


    try:


        profile_id = _scheduled_job_profile_id(conn, config, target, task_id)


        reply = _chat_profile(


            app.state.hermes_adapter,


            profile_id,


            _scheduled_job_messages(job, target, payload),


            f"hermi-scheduled-{job['job_id']}",


            f"hermi:scheduled:{job['job_id']}",


        ).strip()


        _increment_usage_from_hermes(
            conn,
            str(job.get("created_by") or "system:scheduler"),
            app.state.hermes_adapter,
            config=config,
        )


        token_usage = dict(getattr(app.state.hermes_adapter, "last_usage", {}) or {})


        visible_reply, action = extract_hermi_action(reply)


        if action:


            approval = _create_action_approval(conn, task_id and _task_by_id(conn, task_id).get("conversation_id") or _get_or_create_system_conversation(conn), action)


            visible_reply = (


                visible_reply


                + "\n\n"


                + f"主动任务需要额外审批：{approval['summary']}"


            ).strip()


        if not visible_reply:


            visible_reply = "主动任务已执行，但 Hermes 没有返回可展示内容。"


        if "hermi" in delivery:


            result["delivery"]["hermi"] = _deliver_scheduled_result_to_hermi(conn, job, task_id, target, visible_reply)


        if "qq" in delivery:


            result["delivery"]["qq"] = _deliver_scheduled_result_to_qq(app.state.qlos_client, target, visible_reply)


        if task_id:


            _create_task_event(


                conn,


                task_id=task_id,


                event_type="scheduled_job_completed",


                content=visible_reply,


                metadata={"job_id": job["job_id"], "delivery": result["delivery"]},


            )


        status = "completed" if job.get("kind") == "once" else "active"


        result["status"] = status


        result["run_id"] = run_id


        conn.execute(


            """


            update scheduled_jobs


            set status = ?, last_run_at = ?, retry_count = 0, next_run_after = null, updated_at = ?


            where job_id = ?


            """,


            (status, now, now, job["job_id"]),


        )


        if task_id:


            conn.execute(


                "update tasks set status = ?, updated_at = ? where task_id = ?",


                ("completed" if status == "completed" else "running", now, task_id),


            )


        _finish_scheduled_job_run(conn, run_id, status, result, "", token_usage)


        return result


    except Exception as exc:


        error = f"{type(exc).__name__}: {exc}"


        retry_count = int(job.get("retry_count") or 0) + 1


        max_retries = int(job.get("max_retries") or 0)


        should_retry = retry_count <= max_retries


        next_run_after = now + _retry_backoff_seconds(policy, retry_count) if should_retry else None


        if task_id:


            _create_task_event(


                conn,


                task_id=task_id,


                event_type="scheduled_job_failed",


                content=f"主动任务执行失败：{error}",


                metadata={"job_id": job["job_id"], "retry_count": retry_count, "will_retry": should_retry},


            )


        conn.execute(


            """


            update scheduled_jobs


            set status = ?, last_run_at = ?, retry_count = ?, next_run_after = ?, updated_at = ?


            where job_id = ?


            """,


            (


                "active" if should_retry else ("failed" if job.get("kind") == "once" else "active"),


                now,


                retry_count,


                next_run_after,


                now,


                job["job_id"],


            ),


        )


        if task_id:


            conn.execute(


                "update tasks set status = ?, updated_at = ? where task_id = ?",


                ("running" if should_retry or job.get("kind") != "once" else "failed", now, task_id),


            )


        failed = {"job_id": job["job_id"], "status": "failed", "error": error, "delivery": result["delivery"], "retry_count": retry_count, "will_retry": should_retry, "run_id": run_id}


        _finish_scheduled_job_run(conn, run_id, "failed", failed, error, {})


        return failed








def _scheduled_job_profile_id(


    conn,


    config: HermiConfig,


    target: dict[str, Any],


    task_id: str,


) -> str:


    conversation_id = str(target.get("conversation_id") or "").strip()


    if not conversation_id and task_id:


        conversation_id = str(_task_by_id(conn, task_id).get("conversation_id") or "").strip()


    if conversation_id:


        row = conn.execute("select * from conversations where conversation_id = ?", (conversation_id,)).fetchone()


        if row:


            return _conversation_profile_id(conn, config, dict(row))


    return config.hermi_profile_id






def _start_scheduled_job_run(conn, job_id: str, started_at: float) -> str:

    run_id = f"jobrun-{uuid.uuid4().hex[:12]}"


    conn.execute(


        """


        insert into scheduled_job_runs (


          run_id, job_id, status, started_at, finished_at, duration_ms, result_json, error, token_json


        ) values (?, ?, 'running', ?, null, 0, '{}', '', '{}')


        """,


        (run_id, job_id, started_at),


    )


    return run_id








def _finish_scheduled_job_run(


    conn,


    run_id: str,


    status: str,


    result: dict[str, Any],


    error: str,


    token_usage: dict[str, Any],


) -> None:


    row = conn.execute("select started_at from scheduled_job_runs where run_id = ?", (run_id,)).fetchone()


    started_at = float(row["started_at"] if row else time.time())


    finished_at = time.time()


    conn.execute(


        """


        update scheduled_job_runs


        set status = ?, finished_at = ?, duration_ms = ?, result_json = ?, error = ?, token_json = ?


        where run_id = ?


        """,


        (


            status,


            finished_at,


            int((finished_at - started_at) * 1000),


            json.dumps(result, ensure_ascii=False),


            error,


            json.dumps(token_usage or {}, ensure_ascii=False),


            run_id,


        ),


    )








def _deliver_scheduled_result_to_hermi(

    conn,


    job: dict[str, Any],


    task_id: str,


    target: dict[str, Any],


    reply: str,


) -> bool:


    conversation_id = str(target.get("conversation_id") or "").strip()


    if not conversation_id and task_id:


        task = _task_by_id(conn, task_id)


        conversation_id = str(task.get("conversation_id") or "")


    if not conversation_id:


        conversation_id = _get_or_create_system_conversation(conn)


    _insert_message(


        conn,


        conversation_id,


        "assistant",


        reply,


        "hermi",


        metadata={"job_id": job["job_id"], "task_id": task_id, "delivery": "hermi"},


    )


    conn.execute(


        "update conversations set updated_at = ? where conversation_id = ?",


        (time.time(), conversation_id),


    )


    return True








def _deliver_scheduled_result_to_qq(qlos_client: Any, target: dict[str, Any], reply: str) -> bool:


    qq = target.get("qq") if isinstance(target.get("qq"), dict) else {}


    chat_type = str(qq.get("chat_type") or target.get("chat_type") or "private")


    user_id = str(qq.get("user_id") or target.get("user_id") or "").strip() or None


    group_id = str(qq.get("group_id") or target.get("group_id") or "").strip() or None


    if chat_type == "private" and not user_id:


        return False


    if chat_type == "group" and not group_id:


        return False


    response = qlos_client.send_qq(chat_type=chat_type, user_id=user_id, group_id=group_id, message=reply)


    if isinstance(response, dict) and not response.get("ok", False):


        raise RuntimeError("scheduled_qq_delivery_failed")


    return True








def _get_or_create_system_conversation(conn) -> str:


    row = conn.execute(


        "select * from conversations where channel = ? and source_id = ?",


        ("hermi-native", "hermi:system"),


    ).fetchone()


    if row:


        return str(row["conversation_id"])


    now = time.time()


    conversation_id = f"conv-{uuid.uuid4().hex[:12]}"


    conn.execute(


        """


        insert into conversations (


          conversation_id, channel, source_id, title, session_id, session_key,


          owner_user_id, visibility, quota_policy, created_at, updated_at


        ) values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)


        """,


        (


            conversation_id,


            "hermi-native",


            "hermi:system",


            "Hermi 系统",


            f"hermi-{conversation_id}",


            f"hermi:{conversation_id}",


            "owner",


            "private",


            "owner",


            now,


            now,


        ),


    )


    return conversation_id


def _get_or_create_user_system_conversation(conn, user: dict[str, Any]) -> str:

    user_id = str(user.get("user_id") or "").strip()
    if not user_id or user_id == "owner":
        return _get_or_create_system_conversation(conn)

    source_id = f"hermi:system:{user_id}"
    row = conn.execute(
        "select * from conversations where channel = ? and source_id = ?",
        ("hermi-native", source_id),
    ).fetchone()
    if row:
        return str(row["conversation_id"])

    now = time.time()
    conversation_id = f"conv-{uuid.uuid4().hex[:12]}"
    conn.execute(
        """
        insert into conversations (
          conversation_id, channel, source_id, title, session_id, session_key,
          owner_user_id, visibility, quota_policy, created_at, updated_at
        ) values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            conversation_id,
            "hermi-native",
            source_id,
            "Hermi 系统任务",
            f"hermi-{conversation_id}",
            f"hermi:{conversation_id}",
            user_id,
            "private",
            str(user.get("quota_policy") or "friend_free"),
            now,
            now,
        ),
    )
    return conversation_id








def _json_object(value: str | None) -> dict[str, Any]:

    try:


        parsed = json.loads(value or "{}")


    except json.JSONDecodeError:


        return {}


    return parsed if isinstance(parsed, dict) else {}








def _json_list(value: str | None) -> list[str]:


    try:


        parsed = json.loads(value or "[]")


    except json.JSONDecodeError:


        return []


    return [str(item) for item in parsed] if isinstance(parsed, list) else []








def _split_qlos_reply_parts(text: str) -> list[str]:


    parts = [part.strip() for part in str(text or "").split("<<<QLOS_SPLIT>>>")]


    return [part for part in parts if part]








def _render_prompt_preview(cards: list[dict[str, Any]], *, channel: str, room_id: str | None, agent_name: str) -> str:


    lines = [


        "Prompt Tavern 预览：只做补充，不覆盖 Hermes 原生 profile/soul。",


        f"目标对象：{agent_name}",


        f"通道：{channel}",


    ]


    if room_id:


        lines.append(f"会议室：{room_id}")


    for card in cards:


        lines.append(f"[{card.get('card_type')}] {card.get('name')}: {card.get('content')}")


    return "\n".join(lines)








def _prompt_cards_for_scope(conn, *, scope_type: str, scope_id: str) -> list[dict[str, Any]]:


    rows = conn.execute(


        """


        select c.*, b.binding_id, b.scope_type, b.scope_id, b.priority


        from prompt_bindings b


        join prompt_cards c on c.card_id = b.card_id


        where b.enabled = 1 and c.enabled = 1 and b.scope_type = ? and b.scope_id = ?


        order by b.priority asc, b.created_at asc


        """,


        (scope_type, scope_id),


    ).fetchall()


    return [dict(row) for row in rows]








def _render_channel_prompt(conn, *, channel: str, conversation_id: str | None = None) -> str:


    cards = _prompt_cards_for_scope(conn, scope_type="channel", scope_id=channel)


    if not cards:


        return ""


    prompt = "\n".join(str(card.get("content") or "").strip() for card in cards if str(card.get("content") or "").strip())


    render_id = f"prender-{uuid.uuid4().hex[:12]}"


    conn.execute(


        """


        insert into prompt_renders (render_id, conversation_id, task_id, render_type, content, created_at, metadata_json)


        values (?, ?, ?, ?, ?, ?, ?)


        """,


        (


            render_id,


            conversation_id,


            None,


            f"channel:{channel}",


            prompt,


            time.time(),


            json.dumps({"channel": channel, "cards": [card["card_id"] for card in cards]}, ensure_ascii=False),


        ),


    )


    return prompt








def _build_qq_channel_messages(

    conn,

    history: list[dict[str, str]],

    body: QQEventIn,

    conversation_id: str,

    *,

    profile_name: str = "",

    attachment_refs: list[dict[str, Any]] | None = None,

) -> list[dict[str, str]]:

    channel_prompt = str(body.qlos_prompt or "").strip()
    if not channel_prompt:
        channel_prompt = _render_channel_prompt(conn, channel="qq", conversation_id=conversation_id)


    system = (

        "Use the default Hermes personality, skills, memory, and tool policy.\n"

        f"当前启用人格：{profile_name}。身份必须以当前 profile 的 SOUL.md 为准；"

        "不得根据旧会话、长期记忆中的旧人格偏好或用户称呼改写身份。\n"

        "This message comes from QQ through QLOS/Hermi. Keep source identity and permissions in mind.\n"

        "Answer the current [user_message]. Rely on Hermes native session context instead of manually injected recent QQ history.\n"


        f"{channel_prompt}"


    ).strip()


    messages = [{"role": "system", "content": system}]


    latest = dict(history[-1]) if history else {"role": "user", "content": body.text}


    latest["role"] = "user"


    latest["content"] = (


        "[QQ ChannelEnvelope]\n"


        "source=qq\n"


        "transport=napcat_onebot\n"


        f"chat_type={body.chat_type}\n"


        f"user_id={body.user_id}\n"


        f"group_id={body.group_id or ''}\n"


        f"message_id={body.message_id}\n"


        f"sender_role={body.sender_role}\n"

        f"target_profile={profile_name}\n"

        f"risk={json.dumps(body.risk, ensure_ascii=False)}\n\n"

        f"[user_message]\n{body.text}"
        + ("\n\n" + _attachment_context_for_hermes(attachment_refs) if attachment_refs else "")


    )


    messages.append(latest)


    return messages








def _resolve_operation_workspace(config: HermiConfig, workspace_path: str) -> Path:


    root = Path(config.default_operation_root).resolve()


    path = Path(workspace_path).resolve()


    try:


        path.relative_to(root)


    except ValueError:


        if root != path:


            raise HTTPException(status_code=403, detail="workspace_outside_operation_root")


    if not path.exists() or not path.is_dir():


        raise HTTPException(status_code=400, detail="workspace_not_found")


    return path








def _operation_zone_by_id(conn, zone_id: str) -> dict[str, Any]:


    row = conn.execute("select * from operation_zones where zone_id = ?", (zone_id,)).fetchone()


    if not row:


        raise HTTPException(status_code=404, detail="operation_zone_not_found")


    return dict(row)








def _resolve_inside_workspace(workspace: Path, relative_path: str) -> Path:


    target = (workspace / relative_path).resolve()


    try:


        target.relative_to(workspace)


    except ValueError:


        raise HTTPException(status_code=403, detail="path_outside_operation_zone")


    return target








def _run_whitelisted_command(command: list[str], cwd: Path) -> str:


    completed = subprocess.run(command, cwd=cwd, text=True, capture_output=True, timeout=30)


    return (completed.stdout + completed.stderr).strip()








def _operation_log(conn, zone_id: str, action: str, status: str, detail: dict[str, Any]) -> None:


    conn.execute(


        """


        insert into operation_logs (log_id, zone_id, action, status, detail_json, created_at)


        values (?, ?, ?, ?, ?, ?)


        """,


        (


            f"oplog-{uuid.uuid4().hex[:12]}",


            zone_id,


            action,


            status,


            json.dumps(detail, ensure_ascii=False),


            time.time(),


        ),


    )








def _create_task(


    conn,


    *,


    title: str,


    task_type: str,


    conversation_id: str | None,


    source: str,


    created_by: str,


    metadata: dict[str, Any] | None = None,


    status: str = "pending",


) -> dict[str, Any]:


    now = time.time()


    task_id = f"task-{uuid.uuid4().hex[:12]}"


    conn.execute(


        """


        insert into tasks (


          task_id, title, status, task_type, conversation_id, source, created_by,


          created_at, updated_at, metadata_json


        ) values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)


        """,


        (


            task_id,


            title.strip() or "未命名任务",


            status,


            task_type.strip() or "general",


            conversation_id,


            source,


            created_by,


            now,


            now,


            json.dumps(metadata or {}, ensure_ascii=False),


        ),


    )


    return _task_by_id(conn, task_id)








def _create_task_event(


    conn,


    *,


    task_id: str,


    event_type: str,


    content: str,


    metadata: dict[str, Any] | None = None,


) -> dict[str, Any]:


    event_id = f"event-{uuid.uuid4().hex[:12]}"


    conn.execute(


        """


        insert into task_events (event_id, task_id, event_type, content, created_at, metadata_json)


        values (?, ?, ?, ?, ?, ?)


        """,


        (


            event_id,


            task_id,


            event_type.strip() or "log",


            content,


            time.time(),


            json.dumps(metadata or {}, ensure_ascii=False),


        ),


    )


    return dict(conn.execute("select * from task_events where event_id = ?", (event_id,)).fetchone())








def _create_scheduled_job(


    conn,


    *,


    task_id: str | None,


    kind: str,


    schedule: str,


    summary: str,


    target: dict[str, Any] | None,


    payload: dict[str, Any] | None,


    created_by: str,


    status: str,


    policy: dict[str, Any] | None = None,


    max_retries: int = 0,


) -> dict[str, Any]:


    now = time.time()


    job_id = f"job-{uuid.uuid4().hex[:12]}"


    conn.execute(


        """


        insert into scheduled_jobs (


          job_id, task_id, kind, schedule, summary, status, target_json,


          payload_json, policy_json, retry_count, max_retries, created_by, created_at, updated_at


        ) values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)


        """,


        (


            job_id,


            task_id,


            kind or "cron",


            schedule.strip(),


            summary.strip() or "定时任务",


            status,


            json.dumps(target or {}, ensure_ascii=False),


            json.dumps(payload or {}, ensure_ascii=False),


            json.dumps(policy or {}, ensure_ascii=False),


            0,


            max(0, int(max_retries or 0)),


            created_by,


            now,


            now,


        ),


    )


    return dict(conn.execute("select * from scheduled_jobs where job_id = ?", (job_id,)).fetchone())








def _conversation_by_id(conn, conversation_id: str) -> dict[str, Any]:


    row = conn.execute("select * from conversations where conversation_id = ?", (conversation_id,)).fetchone()


    if not row:


        raise HTTPException(status_code=404, detail="conversation_not_found")


    return dict(row)








def _conversation_by_identifier(conn, value: str) -> dict[str, Any] | None:


    text = str(value or "").strip()


    if not text:


        return None


    row = conn.execute(


        """


        select * from conversations


        where conversation_id = ? or session_id = ? or session_key = ?


        limit 1


        """,


        (text, text, text),


    ).fetchone()


    return dict(row) if row else None








def _agent_by_id(conn, agent_id: str) -> dict[str, Any]:


    row = conn.execute("select * from agents where agent_id = ?", (agent_id,)).fetchone()


    if not row:


        raise HTTPException(status_code=404, detail="agent_not_found")


    return dict(row)








def _mark_orphaned_workflow_runs_recoverable(conn) -> None:

    rows = conn.execute(

        "select run_id, state_json from workflow_runs where status = 'running'"

    ).fetchall()

    now = time.time()

    for row in rows:

        state = _safe_json_dict(str(row["state_json"] or "{}"))

        state.update({"recoverable": True, "reason": "service_restart"})

        conn.execute(

            "update workflow_runs set status = 'paused', state_json = ?, updated_at = ? where run_id = ?",

            (json.dumps(state, ensure_ascii=False), now, row["run_id"]),

        )

    if rows:

        conn.commit()





def _public_workflow_run(conn, run: dict[str, Any]) -> dict[str, Any]:

    rows = conn.execute(

        "select usage_json from workflow_steps where run_id = ?", (run["run_id"],)

    ).fetchall()

    usage = {"input_tokens": 0, "output_tokens": 0, "total_tokens": 0}

    for row in rows:

        item = _safe_json_dict(str(row["usage_json"] or "{}"))

        for key in usage:

            usage[key] += int(item.get(key) or 0)

    return {**run, "usage": usage}





def _create_workflow_run(conn, *, room_id: str, mode: str, topic: str, max_turns: int) -> dict[str, Any]:

    now = time.time()


    run_id = f"run-{uuid.uuid4().hex[:12]}"


    conn.execute(


        """


        insert into workflow_runs (

          run_id, room_id, mode, status, max_turns, topic, state_json, created_at, updated_at

        ) values (?, ?, ?, ?, ?, ?, ?, ?, ?)

        """,

        (

            run_id, room_id, mode, "running", max(1, max_turns), topic,

            json.dumps({"last_step_index": -1, "recoverable": False}, ensure_ascii=False),

            now, now,

        ),

    )


    return dict(conn.execute("select * from workflow_runs where run_id = ?", (run_id,)).fetchone())








def _insert_workflow_step(

    conn,


    *,


    run_id: str,


    step_index: int,


    agent_id: str | None,


    role: str,

    content: str,

    session_id: str = "",

    usage: dict[str, Any] | None = None,

    error: str = "",

    metadata: dict[str, Any] | None = None,

) -> None:

    conn.execute(

        """

        insert into workflow_steps (

          step_id, run_id, step_index, agent_id, role, content, created_at,

          session_id, usage_json, error, metadata_json

        ) values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)

        """,

        (

            f"step-{uuid.uuid4().hex[:12]}", run_id, step_index, agent_id, role,

            content, time.time(), session_id, json.dumps(usage or {}, ensure_ascii=False),

            error, json.dumps(metadata or {}, ensure_ascii=False),

        ),

    )

    row = conn.execute(

        "select state_json from workflow_runs where run_id = ?", (run_id,)

    ).fetchone()

    if row:

        state = _safe_json_dict(str(row["state_json"] or "{}"))

        state.update(

            {

                "last_step_index": step_index,

                "last_agent_id": agent_id or "",

                "recoverable": False,

            }

        )

        conn.execute(

            "update workflow_runs set state_json = ?, updated_at = ? where run_id = ?",

            (json.dumps(state, ensure_ascii=False), time.time(), run_id),

        )







def _meeting_profile_id(member: dict[str, Any]) -> str:

    agent_id = str(member.get("agent_id") or "")

    if member.get("agent_type") != "hermes_profile" or not agent_id.startswith("profile:"):

        raise RuntimeError(f"meeting_member_not_hermes_profile:{agent_id}")

    return agent_id.split(":", 1)[1]





def _wait_for_workflow_running(conn, run_id: str) -> bool:

    while True:

        row = conn.execute("select status from workflow_runs where run_id = ?", (run_id,)).fetchone()

        if not row:

            return False

        status = str(row["status"])

        if status == "running":

            return True

        if status != "paused":

            return False

        time.sleep(0.05)





def _call_meeting_member(

    conn,

    adapter: Any,

    *,

    run_id: str,

    step_index: int,

    member: dict[str, Any],

    topic: str,

    mode: str,

    round_number: int,

    permission_level: str,

    previous: list[str],

    instruction: str,

    persist: bool = True,

) -> str:

    if not _wait_for_workflow_running(conn, run_id):

        return ""

    existing = conn.execute(

        "select content from workflow_steps where run_id = ? and step_index = ?",

        (run_id, step_index),

    ).fetchone() if persist else None

    if existing:

        return str(existing["content"] or "")

    profile_id = _meeting_profile_id(member)

    session_id = f"meeting:{run_id}:{profile_id}:{step_index}"

    context = _compact_meeting_context(previous)

    system = (

        f"你正在参加 Hermi 本机会议。模式：{_meeting_mode_label(mode)}。"

        f"你是 {member['name']}，当前第 {round_number} 轮。\n"

        f"{_meeting_permission_prompt(permission_level)}\n"

        "只在用户明确要求执行、测试、审查等动作时提出或执行对应动作；否则只讨论。"

    )

    messages = [

        {"role": "system", "content": system},

        {"role": "user", "content": f"议题：{topic}\n任务：{instruction}\n相关前序发言：\n{context}"},

    ]

    error = ""

    content = ""

    trace: list[dict[str, str]] = []

    try:

        if hasattr(adapter, "stream_profile_events"):

            for event in adapter.stream_profile_events(profile_id, messages, session_id, session_id):

                event_type = str(event.get("event") or event.get("type") or "")

                event_content = str(event.get("content") or event.get("text") or "")

                if event_type in {"thought", "tool", "progress"} and event_content:

                    trace.append(_meeting_trace_event(event_type, event_content))

                elif event_type == "final":

                    content = event_content.strip()

        elif hasattr(adapter, "chat_profile"):

            content = str(adapter.chat_profile(profile_id, messages, session_id, session_id)).strip()

        else:

            content = str(adapter.chat(messages, session_id, session_id)).strip()

    except Exception as exc:

        error = f"{type(exc).__name__}: {exc}"

        content = f"[{member['name']} 调用失败，会议继续]"

    if not _wait_for_workflow_running(conn, run_id):

        return ""

    if not persist:

        return content

    usage = dict(getattr(adapter, "last_usage", {}) or {})

    _insert_workflow_step(

        conn,

        run_id=run_id,

        step_index=step_index,

        agent_id=member["agent_id"],

        role=str(member["member_role"]),

        content=content,

        session_id=session_id,

        usage=usage,

        error=error,

        metadata={"profile_id": profile_id, "round": round_number, "mode": mode, "trace": trace},

    )

    conn.commit()

    return content





def _start_workflow_thread(

    app: FastAPI,

    config: HermiConfig,

    run: dict[str, Any],

    room: dict[str, Any],

) -> threading.Thread:

    run_id = str(run["run_id"])

    existing = app.state.workflow_threads.get(run_id)

    if existing and existing.is_alive():

        return existing

    mode = _normalize_meeting_mode(str(run.get("mode") or room.get("mode") or ""))

    max_turns = 1 if mode == "auto_single" else max(1, int(run.get("max_turns") or 1))

    thread = threading.Thread(

        target=_run_room_workflow_background,

        args=(

            config.db_path,

            app.state.hermes_adapter,

            app.state.workflow_threads,

            run_id,

            room,

            str(run.get("topic") or ""),

            mode,

            max_turns,

        ),

        name=f"hermi-meeting-{run_id}",

        daemon=True,

    )

    app.state.workflow_threads[run_id] = thread

    thread.start()

    return thread





def _run_room_workflow_background(

    db_path: Path,

    adapter: Any,

    workflow_threads: dict[str, threading.Thread],

    run_id: str,

    room: dict[str, Any],

    topic: str,

    mode: str,

    max_turns: int,

) -> None:

    worker_conn = init_db(db_path)

    try:

        _run_room_workflow(worker_conn, adapter, run_id, room, topic, mode, max_turns)

        row = worker_conn.execute(

            "select status from workflow_runs where run_id = ?", (run_id,)

        ).fetchone()

        if row and row["status"] == "running":

            worker_conn.execute(

                "update workflow_runs set status = 'completed', updated_at = ? where run_id = ?",

                (time.time(), run_id),

            )

    except Exception as exc:

        worker_conn.execute(

            "update workflow_runs set status = 'failed', updated_at = ? where run_id = ?",

            (time.time(), run_id),

        )

        _insert_workflow_step(

            worker_conn,

            run_id=run_id,

            step_index=999999,

            agent_id=None,

            role="error",

            content="会议运行失败。",

            error=f"{type(exc).__name__}: {exc}",

        )

    finally:

        worker_conn.commit()

        worker_conn.close()

        workflow_threads.pop(run_id, None)





def _update_workflow_step_after_control(

    conn,

    run_id: str,

    step_index: int,

    content: str,

    metadata_updates: dict[str, Any],

) -> None:

    row = conn.execute(

        "select metadata_json from workflow_steps where run_id = ? and step_index = ?",

        (run_id, step_index),

    ).fetchone()

    if not row:

        return

    metadata = _safe_json_dict(str(row["metadata_json"] or "{}"))

    metadata.update(metadata_updates)

    conn.execute(

        "update workflow_steps set content = ?, metadata_json = ? where run_id = ? and step_index = ?",

        (content, json.dumps(metadata, ensure_ascii=False), run_id, step_index),

    )

    conn.commit()





def _saved_workflow_step_control(conn, run_id: str, step_index: int) -> str:

    row = conn.execute(

        "select metadata_json from workflow_steps where run_id = ? and step_index = ?",

        (run_id, step_index),

    ).fetchone()

    if not row:

        return ""

    metadata = _safe_json_dict(str(row["metadata_json"] or "{}"))

    if metadata.get("discussion_end"):

        return "end"

    if metadata.get("awaiting_user"):

        return "user"

    return str(metadata.get("next_speaker") or "")





def _run_room_workflow(

    conn,

    adapter: Any,

    run_id: str,

    room: dict[str, Any],

    topic: str,

    mode: str,

    max_turns: int,

) -> None:

    members = _room_members(conn, room["room_id"])

    host = next((item for item in members if item["agent_id"] == room.get("host_agent_id")), None)

    if host is None:

        host = next((item for item in members if item["member_role"] in HOST_ROLES), None)

    participants = [item for item in members if item is not host]

    permission_level = str(room.get("permission_level") or "general")

    previous: list[str] = []

    step_index = 0



    if mode == "auto_single":

        chosen = participants[0] if participants else host

        if host and participants:

            candidates = ", ".join(

                f"{_meeting_profile_id(item)}={item['name']}" for item in participants

            )

            selection = _call_meeting_member(

                conn, adapter, run_id=run_id, step_index=step_index, member=host,

                topic=topic, mode=mode, round_number=1, permission_level=permission_level,

                previous=[],

                instruction=(

                    f"从候选成员中选最适合回答者：{candidates}。"

                    "只返回一个技术 profile_id，不回答议题。"

                ),

                persist=False,

            )

            chosen = next(

                (item for item in participants if _meeting_profile_id(item) in selection),

                chosen,

            )

        if chosen is None:

            raise HTTPException(status_code=400, detail="meeting_has_no_members")

        _call_meeting_member(

            conn, adapter, run_id=run_id, step_index=step_index, member=chosen,

            topic=topic, mode=mode, round_number=1, permission_level=permission_level,

            previous=[], instruction="主持人已按成员职责选择你。请对问题单次作答或提出动作建议。",

        )

        return



    if mode == "pair_review":

        for round_number in range(1, max_turns + 1):

            for member in participants:

                content = _call_meeting_member(

                    conn, adapter, run_id=run_id, step_index=step_index, member=member,

                    topic=topic, mode=mode, round_number=round_number,

                    permission_level=permission_level, previous=previous,

                    instruction="回答、挑错或修正前序观点。可向提问者提出必要问题；不要生成会议纪要。",

                )

                previous.append(f"{member['name']}：{content}")

                step_index += 1

        return



    if mode == "project_meeting":

        speakers = participants or members

        speaker_index = 0

        call_limit = max(1, max_turns) * max(1, len(speakers))

        for call_number in range(call_limit):

            member = speakers[speaker_index]

            content = _call_meeting_member(

                conn, adapter, run_id=run_id, step_index=step_index, member=member,

                topic=topic, mode=mode,

                round_number=(call_number // max(1, len(speakers))) + 1,

                permission_level=permission_level, previous=previous,

                instruction=(

                    "自然讨论问题，可补充、质疑、提问或简短回应，不必套固定格式。"

                    "如希望指定下一位，在末行写 NEXT: profile_id；需要用户回答写 NEXT: USER；"

                    "认为可以结束写 NEXT: END。控制行不会展示给用户。"

                ),

            )

            visible, directive = _meeting_discussion_control(content)

            if not directive:

                directive = _saved_workflow_step_control(conn, run_id, step_index)

            metadata_updates: dict[str, Any] = {}

            if directive == "end":

                metadata_updates["discussion_end"] = True

            elif directive == "user":

                metadata_updates["awaiting_user"] = True

            elif directive:

                metadata_updates["next_speaker"] = directive

            _update_workflow_step_after_control(

                conn, run_id, step_index, visible, metadata_updates

            )

            previous.append(f"{member['name']}：{visible}")

            step_index += 1

            if directive in {"end", "user"}:

                break

            requested_index = next(

                (

                    index

                    for index, item in enumerate(speakers)

                    if _meeting_profile_id(item) == directive

                ),

                None,

            )

            speaker_index = (

                requested_index

                if requested_index is not None

                else (speaker_index + 1) % len(speakers)

            )

        if host:

            _call_meeting_member(

                conn, adapter, run_id=run_id, step_index=step_index, member=host,

                topic=topic, mode=mode, round_number=max_turns,

                permission_level=permission_level, previous=previous,

                instruction="整理会议纪要：结论、分歧、行动项；没有明确执行要求时不要执行。",

            )

        return



    stages = ("需求", "设计", "计划", "执行", "测试", "审查")

    for stage in stages:

        for round_number in range(1, max_turns + 1):

            for member in members:

                content = _call_meeting_member(

                    conn, adapter, run_id=run_id, step_index=step_index, member=member,

                    topic=topic, mode=mode, round_number=round_number,

                    permission_level=permission_level, previous=previous,

                    instruction=f"当前阶段：{stage}。完成本阶段职责并给出阶段结果；不得越过权限边界。",

                )

                previous.append(f"[{stage}] {member['name']}：{content}")

                step_index += 1





def _run_room_workflow_skeleton(conn, run_id: str, room_id: str, topic: str, mode: str, max_turns: int) -> None:

    members = _room_members(conn, room_id)


    host = next((member for member in members if member["member_role"] in HOST_ROLES), None)


    host_role = str(host["member_role"] if host else "host")


    host_name = str(host["name"] if host else "主持人")


    label = _meeting_mode_label(mode)


    _insert_workflow_step(


        conn,


        run_id=run_id,


        step_index=0,


        agent_id=host["agent_id"] if host else None,


        role=host_role,


        content=f"{label}启动：{topic}\n主持：{host_name}\n边界：当前只生成会议骨架和行动项，不执行危险操作。",


    )


    if mode == "auto_single":


        chosen = next((member for member in members if member is not host), host)


        _insert_workflow_step(


            conn,


            run_id=run_id,


            step_index=1,


            agent_id=chosen["agent_id"] if chosen else None,


            role=str(chosen["member_role"] if chosen else "participant"),


            content=f"自动单次模式：主持人根据议题挑选 {chosen['name'] if chosen else '成员'} 单次回答「{topic}」。",


        )


        index = 2


    elif mode == "pair_review":


        pair = [member for member in members if member is not host][:2] or members[:2]


        index = 1


        for turn in range(max(1, max_turns)):


            for member in pair:


                _insert_workflow_step(


                    conn,


                    run_id=run_id,


                    step_index=index,


                    agent_id=member["agent_id"],


                    role=str(member["member_role"]),


                    content=f"双人挑错模式 第 {turn + 1} 轮：{member['name']} 围绕「{topic}」回答、挑错或修正上一轮观点。",


                )


                index += 1


    elif mode == "engineering_pipeline":


        pipeline = ["需求整理", "方案设计", "实现计划", "执行草稿", "测试策略", "审查修复", "总结交付"]


        index = 1


        for stage in pipeline:


            _insert_workflow_step(


                conn,


                run_id=run_id,


                step_index=index,


                agent_id=host["agent_id"] if host else None,


                role=host_role,


                content=f"工程流水线模式：{stage} - 围绕「{topic}」生成该步骤产物；危险操作需另走审批。",


            )


            index += 1


    else:


        index = 1


        for member in members:


            name = member["name"]


            member_role = member["member_role"]


            _insert_workflow_step(


                conn,


                run_id=run_id,


                step_index=index,


                agent_id=member["agent_id"],


                role=member_role,


                content=f"项目会议模式：{name} 围绕「{topic}」给出观点、风险和下一步建议。",


            )


            index += 1


    _insert_workflow_step(


        conn,


        run_id=run_id,


        step_index=index,


        agent_id=host["agent_id"] if host else None,


        role="summary",


        content=f"会议纪要：{topic}\n- 模式：{label}。\n- 当前是开放式骨架，角色/名称/流程可后续调整。\n- 不执行文件、命令或外部发送。",


    )








def _run_project_meeting(conn, run_id: str, room_id: str, topic: str) -> None:


    _run_room_workflow_skeleton(conn, run_id, room_id, topic, "project_meeting", 1)








def _require_conversation(conn, conversation_id: str) -> dict[str, Any]:


    return _conversation_by_id(conn, conversation_id)








def _require_conversation_for_user(


    conn,


    conversation_id: str,


    user: dict[str, Any],


) -> dict[str, Any]:


    conversation = _conversation_by_id(conn, conversation_id)


    if user.get("can_approve") or conversation.get("owner_user_id") == user.get("user_id"):


        return conversation


    raise HTTPException(status_code=404, detail="conversation_not_found")








def _insert_message(


    conn,


    conversation_id: str,


    role: str,


    content: str,


    source_channel: str,


    metadata: dict[str, Any] | None = None,


    created_at: float | None = None,


) -> dict[str, Any]:


    message_id = f"msg-{uuid.uuid4().hex[:12]}"


    conn.execute(


        """


        insert into messages (


          message_id, conversation_id, role, content, source_channel, metadata_json, created_at


        ) values (?, ?, ?, ?, ?, ?, ?)


        """,


        (


            message_id,


            conversation_id,


            role,


            content,


            source_channel,


            json.dumps(metadata or {}, ensure_ascii=False),


            created_at if created_at is not None else time.time(),


        ),


    )


    return dict(conn.execute("select * from messages where message_id = ?", (message_id,)).fetchone())


def _create_user_notice(conn, user_id: str, *, kind: str, title: str, message: str) -> dict[str, Any]:
    notice_id = f"notice-{uuid.uuid4().hex[:12]}"
    now = time.time()
    conn.execute(
        """
        insert into user_notices (notice_id, user_id, kind, title, message, created_at, read_at)
        values (?, ?, ?, ?, ?, ?, null)
        """,
        (notice_id, user_id, kind, title, message, now),
    )
    return {
        "notice_id": notice_id,
        "user_id": user_id,
        "kind": kind,
        "title": title,
        "message": message,
        "created_at": now,
    }


def _hermes_session_message_text(item: dict[str, Any]) -> str:
    content = item.get("content")
    if isinstance(content, list):
        content = "".join(
            str(part.get("text") or part.get("content") or "")
            for part in content
            if isinstance(part, dict)
        )
    return str(content or "").strip()


def _sync_hermes_session_messages(conn, adapter: Any, config: HermiConfig, conversation: dict[str, Any]) -> None:
    if str(conversation.get("channel") or "").lower() != "hermi-native":
        return
    profile_id = _conversation_profile_id(conn, config, conversation)
    try:
        if hasattr(adapter, "session_messages_profile"):
            raw_messages = adapter.session_messages_profile(
                profile_id,
                str(conversation.get("session_id") or ""),
                str(conversation.get("session_key") or ""),
            )
        elif hasattr(adapter, "session_messages"):
            raw_messages = adapter.session_messages(
                str(conversation.get("session_id") or ""),
                str(conversation.get("session_key") or ""),
            )
        else:
            return
    except Exception:
        return
    if not isinstance(raw_messages, list):
        return

    conversation_id = str(conversation["conversation_id"])
    local_messages = [
        dict(row)
        for row in conn.execute(
            "select * from messages where conversation_id = ? order by created_at asc",
            (conversation_id,),
        ).fetchall()
    ]
    legacy_messages = {
        str(_safe_json_dict(row.get("metadata_json")).get("hermes_session_message_id") or ""): row
        for row in local_messages
    }
    synced = {
        str(row["remote_message_id"]): str(row["disposition"])
        for row in conn.execute(
            "select remote_message_id, disposition from hermes_session_sync where conversation_id = ?",
            (conversation_id,),
        ).fetchall()
    }
    changed = False
    suppress_internal_assistant_messages = False
    for item in raw_messages:
        if not isinstance(item, dict):
            continue
        remote_id = str(item.get("id") or item.get("message_id") or "").strip()
        role = str(item.get("role") or item.get("author") or "").strip().lower()
        content = _hermes_session_message_text(item)
        if not remote_id or role not in {"user", "assistant", "system"} or not content:
            continue
        is_internal_user = role == "user" and _is_hermi_session_envelope(content)
        if is_internal_user:
            removed = _remove_legacy_hermes_message(conn, legacy_messages.get(remote_id))
            recorded = _record_hermes_session_sync(conn, conversation_id, remote_id, "internal_user")
            synced[remote_id] = "internal_user"
            # Hermes can emit several assistant records while handling one Hermi
            # envelope (tool progress, intermediate wording, then the answer).
            # Hermi's own stream is authoritative for that whole turn.
            suppress_internal_assistant_messages = True
            changed = changed or removed or recorded
            continue
        if role == "assistant" and suppress_internal_assistant_messages:
            removed = _remove_legacy_hermes_message(conn, legacy_messages.get(remote_id))
            recorded = _record_hermes_session_sync(conn, conversation_id, remote_id, "internal_assistant")
            synced[remote_id] = "internal_assistant"
            changed = changed or removed or recorded
            continue
        if role == "user":
            # A normal user entry starts a genuine Hermes-direct turn, which
            # remains eligible for the owner-to-Hermi history synchronisation.
            suppress_internal_assistant_messages = False
        if role == "system":
            recorded = _record_hermes_session_sync(conn, conversation_id, remote_id, "system")
            synced[remote_id] = "system"
            changed = changed or recorded
            continue
        if remote_id in synced:
            continue
        try:
            created_at = float(item.get("timestamp") or item.get("created_at") or time.time())
        except (TypeError, ValueError):
            created_at = time.time()
        equivalent = legacy_messages.get(remote_id) or next(
            (
                row
                for row in local_messages
                if row["role"] == role
                and row["content"] == content
                and abs(float(row["created_at"]) - created_at) <= 120
            ),
            None,
        )
        metadata = {"hermes_session_message_id": remote_id}
        if equivalent:
            existing_metadata = _safe_json_dict(equivalent.get("metadata_json"))
            existing_metadata.update(metadata)
            conn.execute(
                "update messages set metadata_json = ? where message_id = ?",
                (json.dumps(existing_metadata, ensure_ascii=False), equivalent["message_id"]),
            )
        else:
            if role == "user":
                metadata["external_author"] = "owner"
            reasoning = str(item.get("reasoning_content") or item.get("reasoning") or "").strip()
            if role == "assistant" and reasoning:
                metadata["trace"] = [{"event": "thought", "content": reasoning}]
            inserted = _insert_message(
                conn,
                conversation_id,
                role,
                content,
                "hermes-api",
                metadata=metadata,
                created_at=created_at,
            )
            local_messages.append(inserted)
            legacy_messages[remote_id] = inserted
        _record_hermes_session_sync(conn, conversation_id, remote_id, "visible")
        synced[remote_id] = "visible"
        changed = True
    if changed:
        conn.execute(
            "update conversations set updated_at = ? where conversation_id = ?",
            (time.time(), conversation_id),
        )
        conn.commit()


def _is_hermi_session_envelope(content: str) -> bool:
    normalized = str(content or "")
    return "[user_message]" in normalized and "user_id=" in normalized and "permission=" in normalized


def _record_hermes_session_sync(conn, conversation_id: str, remote_id: str, disposition: str) -> bool:
    row = conn.execute(
        "select disposition from hermes_session_sync where conversation_id = ? and remote_message_id = ?",
        (conversation_id, remote_id),
    ).fetchone()
    if row and str(row["disposition"]) == disposition:
        return False
    conn.execute(
        """
        insert into hermes_session_sync (conversation_id, remote_message_id, disposition, created_at)
        values (?, ?, ?, ?)
        on conflict(conversation_id, remote_message_id) do update set disposition = excluded.disposition
        """,
        (conversation_id, remote_id, disposition, time.time()),
    )
    return True


def _remove_legacy_hermes_message(conn, message: dict[str, Any] | None) -> bool:
    if message and str(message.get("source_channel") or "") == "hermes-api":
        conn.execute("delete from messages where message_id = ?", (message["message_id"],))
        return True
    return False








def _conversation_history(conn, conversation_id: str) -> list[dict[str, str]]:


    rows = conn.execute(


        """


        select role, content from messages


        where conversation_id = ?


        order by created_at desc


        limit 1


        """,


        (conversation_id,),


    ).fetchall()


    return [


        {"role": row["role"], "content": row["content"]}


        for row in reversed(rows)


        if row["role"] in {"user", "assistant", "system"}


    ]








def _auto_name_conversation(conn, conversation: dict[str, Any], content: str, profile_name: str = "") -> None:


    title = str(conversation.get("title") or "").strip()


    if title not in {"", "New conversation", "新会话", "鏂颁細璇?", "???"}:


        return


    new_title = _conversation_title_from_content(content)


    if not new_title:


        return


    profile = str(profile_name or "").strip()


    if profile and not new_title.startswith(f"{profile} · "):


        new_title = f"{profile} · {new_title}"


    conn.execute(


        "update conversations set title = ?, updated_at = ? where conversation_id = ?",


        (new_title, time.time(), conversation["conversation_id"]),


    )








def _conversation_title_from_content(content: str) -> str:


    text = re.sub(r"\s+", " ", str(content or "")).strip()


    text = re.split(r"[。！？!?，,\n]", text, maxsplit=1)[0].strip()


    return text[:11] or "新会话"








def _get_or_create_qq_conversation(conn, event: QQEventIn) -> dict[str, Any]:


    source_id = _qq_source_id(event)


    row = conn.execute(


        "select * from conversations where channel = ? and source_id = ?",


        ("qq", source_id),


    ).fetchone()


    if row:


        return dict(row)


    now = time.time()


    conversation_id = f"conv-{uuid.uuid4().hex[:12]}"


    title = f"QQ {event.user_id}" if event.chat_type == "private" else f"QQ group {event.group_id} / {event.user_id}"


    conn.execute(


        """


        insert into conversations (


          conversation_id, channel, source_id, title, session_id, session_key,


          owner_user_id, visibility, quota_policy, created_at, updated_at


        ) values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)


        """,


        (


            conversation_id,


            "qq",


            source_id,


            title,


            event.session_id,


            event.session_key,


            "owner",


            "private",


            "owner" if event.sender_role == "owner" else "friend_free",


            now,


            now,


        ),


    )


    conn.commit()


    return _conversation_by_id(conn, conversation_id)








def _qq_source_id(event: QQEventIn) -> str:


    if event.chat_type == "private":


        return f"qq:dm:{event.user_id}"


    return f"qq:group:{event.group_id}:user:{event.user_id}"








def _get_or_create_proactive_conversation(conn, user: dict[str, Any]) -> str:


    row = conn.execute(


        "select conversation_id from conversations where channel = ? and source_id = ?",


        ("hermi-native", "hermi:proactive"),


    ).fetchone()


    if row:


        return str(row["conversation_id"])


    now = time.time()


    conversation_id = f"conv-{uuid.uuid4().hex[:12]}"


    conn.execute(


        """


        insert into conversations (


          conversation_id, channel, source_id, title, session_id, session_key,


          owner_user_id, visibility, quota_policy, created_at, updated_at


        ) values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)


        """,


        (


            conversation_id,


            "hermi-native",


            "hermi:proactive",


            "主动草稿",


            f"hermi-{conversation_id}",


            f"hermi:{conversation_id}",


            user["user_id"],


            "private",


            user["quota_policy"],


            now,


            now,


        ),


    )


    return conversation_id








def _proactive_action_from_body(body: ProactiveDraftCreate) -> dict[str, Any]:


    if body.kind == "qq.send":


        action = dict(body.action or {})


        action["type"] = "qq.send"


        if body.content and not action.get("message"):


            action["message"] = body.content


        if body.target:


            action.setdefault("chat_type", body.target.get("chat_type"))


            action.setdefault("user_id", body.target.get("user_id"))


            action.setdefault("group_id", body.target.get("group_id"))


        return action


    return {


        "type": f"draft.{body.kind}",


        "summary": body.summary,


        "content": body.content,


        "target": body.target,


    }








def _create_action_approval(


    conn,


    conversation_id: str,


    action: dict[str, Any],


    *,


    source: str = "hermes",


    summary: str | None = None,


    risk_level: str | None = None,


) -> dict[str, Any]:


    now = time.time()


    approval_id = f"app-{uuid.uuid4().hex[:12]}"


    action_type = str(action.get("type") or "unknown")


    approval_summary = summary or _action_summary(action)


    approval_risk = risk_level or ("medium" if action_type == "qq.send" else "high")


    conn.execute(


        """


        insert into approvals (


          approval_id, conversation_id, action_type, payload_json, status, source,


          summary, risk_level, expires_at, created_at, updated_at


        ) values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)


        """,


        (


            approval_id,


            conversation_id,


            action_type,


            json.dumps(action, ensure_ascii=False),


            "pending",


            source,


            approval_summary,


            approval_risk,


            now + 3600,


            now,


            now,


        ),


    )


    _audit(conn, "approval_created", source, {"approval_id": approval_id, "action_type": action_type})


    return dict(conn.execute("select * from approvals where approval_id = ?", (approval_id,)).fetchone())








def _action_summary(action: dict[str, Any]) -> str:


    if action.get("type") == "qq.send":


        chat_type = str(action.get("chat_type") or "")


        target = str(action.get("group_id") or action.get("user_id") or "")


        message = str(action.get("message") or "").strip().replace("\n", " ")


        if len(message) > 60:


            message = message[:57] + "..."


        return f"发送 QQ {chat_type} 消息到 {target}: {message}"


    if action.get("type") in {"scheduled.create", "cron.create"}:


        schedule = str(action.get("schedule") or "")


        summary = str(action.get("summary") or action.get("content") or "定时任务").strip()


        if len(summary) > 60:


            summary = summary[:57] + "..."


        return f"创建定时任务 {schedule}: {summary}"


    if action.get("type") == "hermes.permission.request":


        summary = str(action.get("summary") or action.get("requested_capability") or "Hermes 权限请求").strip()


        return summary[:80]


    return f"执行动作：{action.get('type') or 'unknown'}"








def _infer_hermes_permission_action(reply: str, user_request: str) -> dict[str, Any] | None:


    text = str(reply or "")


    request = str(user_request or "")


    if not re.search(r"(需要|请求|缺少|没有|无).{0,12}(权限|审批|批准|授权)", text):


        return None


    capability = "unknown"


    if re.search(r"(重启|restart)", text + request, re.IGNORECASE):


        capability = "service.restart"


    elif re.search(r"(删除|delete|remove)", text + request, re.IGNORECASE):


        capability = "file.delete"


    elif re.search(r"(创建|写入|保存|create|write)", text + request, re.IGNORECASE):


        capability = "file.write"


    elif re.search(r"(执行|运行|命令|shell|run)", text + request, re.IGNORECASE):


        capability = "command.run"


    summary_base = _conversation_title_from_content(request) or _conversation_title_from_content(text)


    return {


        "type": "hermes.permission.request",


        "requested_capability": capability,


        "summary": f"Hermes 请求权限：{summary_base}",


        "user_request": request,


        "hermes_reply": text,


    }








def _recover_missing_scheduled_action(

    hermes_adapter: Any,


    config: HermiConfig,


    conversation: dict[str, Any],


    user_request: str,


    first_reply: str,


) -> tuple[str, dict[str, Any]] | None:


    if not _looks_like_scheduled_request(user_request):


        return None


    if "HERMI_ACTION" in str(first_reply or ""):


        return None


    repair_messages = [


        {


            "role": "system",


            "content": (


                "You repair Hermi Action Contract misses. "


                "Convert the owner's latest natural-language scheduling request into exactly one "


                "HERMI_ACTION scheduled.create block for Hermi approval. "


                "Do not call tools. Do not use native Hermes cronjob. "


                "Do not claim the task is already created. "


                "For one-shot relative delays, use kind=once and schedule like once:+5m. "


                "For recurring jobs, use kind=interval with every 30m or kind=cron with a 5-field cron. "


                "If the owner asks to report to QQ, include target.delivery=[\"hermi\",\"qq\"], "


                "target.qq={\"chat_type\":\"private\",\"user_id\":\"1000000001\"}, and payload.report_to_qq=true. "


                "If the owner says current conversation, include target.delivery=[\"hermi\"] and "


                f"target.conversation_id=\"{conversation['conversation_id']}\". "


                "If required timing or target is genuinely unclear, ask one short Chinese question and return no action."


            ),


        },


        {


            "role": "user",


            "content": (


                f"[Hermi contract repair]\n"


                f"target_profile={config.default_profile_name}\n"


                f"conversation_id={conversation['conversation_id']}\n"


                f"session_id={conversation['session_id']}\n\n"


                f"Owner request:\n{user_request}\n\n"


                f"Previous Hermes reply without Hermi action:\n{first_reply}"


            ),


        },


    ]


    try:


        raw = hermes_adapter.chat(


            repair_messages,


            f"{conversation['session_id']}:contract-repair",


            f"{conversation['session_key']}:contract-repair",


        )


    except Exception:


        return None


    visible, action = extract_hermi_action(raw)


    if not action or str(action.get("type") or "") not in {"scheduled.create", "cron.create"}:


        return None


    if not str(action.get("schedule") or "").strip():


        return None


    if not str(action.get("summary") or action.get("content") or "").strip():


        return None


    return visible, action





def _scheduled_chat_permission_reply(

    conn,

    conversation: dict[str, Any],

    request: str,

    user: dict[str, Any],

    *,

    continue_chat: bool = False,

) -> str | None:

    if user.get("role") == "owner" or not _looks_like_native_cron_request(request):

        return None

    permission = _permission_result_for_user(user, "cron")

    if permission == "allow":

        return None

    if permission in {"deny", "owner_only"}:

        if continue_chat:

            return (

                "[Hermi scheduling status]\n"

                "The scheduling part of this mixed request is not permitted and was not created. "

                "Answer the normal conversational part naturally, then briefly explain that the reminder cannot be arranged."

            )

        return "你的定时任务权限已被禁止，本次没有创建或执行任务。"



    parsed = _parse_native_cron_request(request, conversation) or {}

    schedule = str(parsed.get("schedule") or "").strip()

    kind = "cron"

    if re.fullmatch(r"\d+[mh]", schedule, re.IGNORECASE):

        kind = "once"

        schedule = f"once:+{schedule}"

    elif schedule.startswith("once:"):

        kind = "once"

    elif schedule.startswith("every "):

        kind = "interval"

    if not schedule:

        if continue_chat:

            return (

                "[Hermi scheduling status]\n"

                "The scheduling part of this mixed request has no clear time and was not created. "

                "Answer the normal conversational part naturally, then ask for a clear reminder time."

            )

        return "我识别到你想设置定时任务，但没能确定具体时间。请写成“5 分钟后”或“每天 8 点”。本次没有创建任务。"

    request_parts = [part.strip() for part in re.split(r"[。！？!?；;\n]+", request) if part.strip()]

    scheduled_part = next((part for part in request_parts if _looks_like_native_cron_request(part)), request)

    summary = (_conversation_title_from_content(scheduled_part) or "朋友请求创建定时任务")[:80]

    action = {

        "type": "scheduled.create",

        "kind": kind,

        "schedule": schedule,

        "summary": summary,

        "content": str(parsed.get("prompt") or request),

        "target": {"delivery": ["hermi"], "conversation_id": conversation["conversation_id"]},

        "payload": {"content": str(parsed.get("prompt") or request)},

        "created_by": user["user_id"],

    }

    approval = _create_action_approval(

        conn,

        conversation["conversation_id"],

        action,

        source="permission",

        summary=f"权限审批：{summary}",

        risk_level="medium",

    )

    _audit(

        conn,

        "permission_approval_created",

        user["user_id"],

        {"approval_id": approval["approval_id"], "permission": "cron", "action_type": "scheduled.create"},

    )

    if continue_chat:

        return (

            "[Hermi scheduling status]\n"

            "The scheduling part of this mixed request is already pending Owner approval. "

            "Do not call tools and do not return HERMI_ACTION for it. Answer the normal conversational part naturally, "

            "then briefly say the reminder will be created only after Owner approval."

        )

    return f"这个定时任务需要 Owner 审批。我已提交审批，批准后才会创建和执行。\n\n审批号：{approval['approval_id']}"





def _create_chat_message_approval(

    conn,

    conversation: dict[str, Any],

    content: str,

    user: dict[str, Any],

) -> str:

    summary = (_conversation_title_from_content(content) or "朋友消息")[:80]

    action = {

        "type": "chat.message",

        "content": content,

        "created_by": user["user_id"],

    }

    approval = _create_action_approval(

        conn,

        conversation["conversation_id"],

        action,

        source="permission",

        summary=f"消息审批：{summary}",

        risk_level="low",

    )

    _audit(

        conn,

        "permission_approval_created",

        user["user_id"],

        {"approval_id": approval["approval_id"], "permission": "chat", "action_type": "chat.message"},

    )

    return f"这条消息需要 Owner 审批，批准后才会发送给 Hermes。\n\n审批号：{approval['approval_id']}"





def _owner_scheduled_request_reply(

    conn,

    conversation: dict[str, Any],

    request: str,

    *,

    qq_target: dict[str, Any] | None = None,

) -> tuple[str, dict[str, Any]] | None:

    if not _looks_like_native_cron_request(request):

        return None

    parsed = _parse_native_cron_request(request, conversation)

    if not parsed:

        return None

    raw_schedule = str(parsed.get("schedule") or "").strip()

    if not raw_schedule:

        return None

    repeating = bool(re.search(r"(?:每|每隔|每天|每周|每月|every|repeat|recurring|periodic)", request, re.IGNORECASE))

    kind = "cron"

    schedule = raw_schedule

    if re.fullmatch(r"\d+[mh]", raw_schedule, re.IGNORECASE):

        kind = "interval" if repeating else "once"

        schedule = f"interval:{raw_schedule}" if repeating else f"once:+{raw_schedule}"

    elif raw_schedule.startswith("every "):

        kind = "interval"

        schedule = f"interval:{raw_schedule.removeprefix('every ').strip()}"

    elif raw_schedule.startswith("once:"):

        kind = "once"

    request_parts = [part.strip() for part in re.split(r"[。！？!?；;\n]+", request) if part.strip()]

    scheduled_part = next((part for part in request_parts if _looks_like_native_cron_request(part)), request)

    summary = str(parsed.get("name") or _conversation_title_from_content(scheduled_part) or "定时提醒")[:80]

    target: dict[str, Any] = {"delivery": ["hermi"], "conversation_id": conversation["conversation_id"]}

    deliver = str(parsed.get("deliver") or "")

    qq_match = re.search(r"qq:(\d+)", deliver, re.IGNORECASE)

    if qq_match:

        target["delivery"].append("qq")

        target["qq"] = {"chat_type": "private", "user_id": qq_match.group(1)}


    if qq_target:

        if "qq" not in target["delivery"]:

            target["delivery"].append("qq")


        target["qq"] = {


            key: value


            for key, value in qq_target.items()


            if value


        }

    _, job = _create_owner_scheduled_job(

        conn,

        conversation["conversation_id"],

        {

            "type": "scheduled.create",

            "kind": kind,

            "schedule": schedule,

            "summary": summary,

            "content": str(parsed.get("prompt") or request),

            "target": target,

        },

    )

    destination = "QQ 里" if qq_target else "这里"


    return f"好的主人，我已经把“{job['summary']}”安排好了。到时间我会在{destination}提醒你。", job


def _permission_result_for_user(user: dict[str, Any], permission: str) -> str:

    if user.get("role") == "owner":

        return "allow"

    return PermissionChecker(user).check(permission)







def _scheduled_request_missing_action_reply(user_request: str, reply: str) -> str:


    request = str(user_request or "")


    text = str(reply or "")


    if not _looks_like_scheduled_request(request):


        return ""


    if "HERMI_ACTION" in text or "已创建审批" in text:


        return ""


    if not re.search(r"(设好|设置好|创建|已创建|成功|提醒你|会提醒|到时|定时|cron|corn)", text, re.IGNORECASE):


        return ""


    return (


        "我没有真正创建定时任务。\n\n"


        "原因：Hermes 这轮回复没有返回 `HERMI_ACTION scheduled.create`，所以 Hermi 没有创建审批，也没有写入定时任务。\n\n"


        "请重新发起这个定时请求；如果 Hermes 正确返回动作，Hermi 会先在审批中心显示，批准后才会创建任务。"


    )








def _friendly_hermes_failure_reply(reply: str) -> str:


    text = str(reply or "").strip()


    if text.startswith("Traceback (most recent call last):"):


        first_error = text.splitlines()[-1].strip() if text.splitlines() else "unknown error"


        return f"Hermes 工具执行报错，没有完成本轮操作。\n\n错误：`{first_error}`"


    return str(reply or "")








def _maybe_create_native_hermes_cron(


    config: HermiConfig,


    conversation: dict[str, Any],


    user_request: str,


    hermes_reply: str,


) -> str:


    request = str(user_request or "")


    if not _looks_like_native_cron_request(request):


        return ""


    if _looks_like_native_cron_success(str(hermes_reply or "")):


        return ""


    parsed = _parse_native_cron_request(request, conversation)


    if not parsed:


        return ""


    adopted = _adopt_recent_native_hermes_cron_job(parsed, conversation)


    if adopted:


        return (


            "已接管 Hermes 刚创建的原生定时任务。\n\n"


            f"- job_id: `{adopted.get('id')}`\n"


            f"- schedule: `{adopted.get('schedule_display') or parsed['schedule']}`\n"


            f"- deliver: `{adopted.get('deliver') or parsed['deliver']}`\n"


            f"- next_run_at: `{adopted.get('next_run_at') or ''}`"


        )


    try:


        _ensure_hermes_agent_path()


        from cron.jobs import create_job





        job = create_job(


            prompt=parsed["prompt"],


            schedule=parsed["schedule"],


            name=parsed["name"],


            deliver=parsed["deliver"],


            origin=parsed["origin"],


        )


    except Exception as exc:


        return f"Hermes 原生 cron 创建失败：{type(exc).__name__}: {exc}"


    return (


        "已创建 Hermes 原生定时任务。\n\n"


        f"- job_id: `{job.get('id')}`\n"


        f"- schedule: `{job.get('schedule_display') or parsed['schedule']}`\n"


        f"- deliver: `{job.get('deliver') or parsed['deliver']}`\n"


        f"- next_run_at: `{job.get('next_run_at') or ''}`"


    )








def _adopt_recent_native_hermes_cron_job(parsed: dict[str, Any], conversation: dict[str, Any]) -> dict[str, Any] | None:


    try:


        _ensure_hermes_agent_path()


        from cron.jobs import load_jobs, save_jobs


    except Exception:


        return None


    try:


        jobs = load_jobs()


    except Exception:


        return None


    origin = {


        "platform": "api_server",


        "chat_id": str(conversation.get("session_id") or conversation.get("conversation_id") or ""),


        "session_id": str(conversation.get("session_id") or ""),


        "conversation_id": str(conversation.get("conversation_id") or ""),


    }


    now = time.time()


    candidates: list[tuple[float, dict[str, Any]]] = []


    for job in jobs:


        created_at = _parse_iso_epoch(str(job.get("created_at") or ""))


        if not created_at or abs(now - created_at) > 240:


            continue


        if not _native_cron_schedule_matches(str(parsed.get("schedule") or ""), job):


            continue


        deliver = str(job.get("deliver") or "")


        parsed_deliver = str(parsed.get("deliver") or "")


        if not (


            _native_cron_deliver_has_external_chat(deliver)


            or _native_cron_deliver_has_external_chat(parsed_deliver)


            or "origin" in {part.strip().lower() for part in deliver.split(",")}


        ):


            continue


        candidates.append((created_at, job))


    if not candidates:


        return None


    _, job = max(candidates, key=lambda item: item[0])


    changed = False


    merged_deliver = _merge_native_cron_deliver(str(job.get("deliver") or ""), str(parsed.get("deliver") or ""))


    if merged_deliver and merged_deliver != str(job.get("deliver") or ""):


        job["deliver"] = merged_deliver


        changed = True


    if "origin" in {part.strip().lower() for part in str(job.get("deliver") or "").split(",")} and not job.get("origin"):


        job["origin"] = dict(origin)


        changed = True


    old_prompt = str(job.get("prompt") or "")


    parsed_prompt = str(parsed.get("prompt") or "")


    source_prompt = parsed_prompt if _native_cron_prompt_should_prefer_parsed(old_prompt, parsed_prompt) else old_prompt


    new_prompt = _sanitize_native_cron_delivery_prompt(source_prompt, str(job.get("deliver") or ""))


    if new_prompt and new_prompt != old_prompt:


        job["prompt"] = new_prompt


        if not job.get("name") or str(job.get("name") or "").strip() == old_prompt[:50].strip():


            job["name"] = (_conversation_title_from_content(new_prompt) or "Hermi native cron")[:50]


        changed = True


    if changed:


        try:


            save_jobs(jobs)


        except Exception:


            return job


    return job








def _native_cron_prompt_should_prefer_parsed(job_prompt: str, parsed_prompt: str) -> bool:


    if not parsed_prompt:


        return False


    current = str(job_prompt or "").strip()


    parsed_text = str(parsed_prompt or "").strip()


    if not current:


        return True


    scaffold_markers = [


        "\u6700\u7ec8\u8981\u6295\u9012\u7ed9\u7528\u6237\u7684\u5185\u5bb9",


        "\u4e0d\u8981\u8c03\u7528\u4efb\u4f55\u6295\u9012\u5de5\u5177",


        "final message",


        "delivery layer",


    ]


    if any(marker.lower() in current.lower() for marker in scaffold_markers):


        return True


    return len(parsed_text) > len(current) * 2








def _native_cron_schedule_matches(parsed_schedule: str, job: dict[str, Any]) -> bool:


    wanted = str(parsed_schedule or "").strip().lower().replace(" ", "")


    if not wanted:


        return True


    display = str(job.get("schedule_display") or "").lower().replace(" ", "")


    raw_schedule = json.dumps(job.get("schedule") or {}, ensure_ascii=False).lower().replace(" ", "")


    if wanted in display or wanted in raw_schedule:


        return True


    if re.fullmatch(r"\d+m", wanted) and f"oncein{wanted}" in display:


        return True


    if re.fullmatch(r"\d+h", wanted) and f"oncein{wanted}" in display:


        return True


    return False








def _merge_native_cron_deliver(current: str, desired: str) -> str:


    parts: list[str] = []


    seen: set[str] = set()


    for item in [*str(current or "").split(","), *str(desired or "").split(",")]:


        value = item.strip()


        key = value.lower()


        if value and key not in seen:


            parts.append(value)


            seen.add(key)


    return ",".join(parts)








def _ensure_hermes_agent_path() -> None:


    base = Path(os.environ.get("LOCALAPPDATA", str(Path.home() / "AppData" / "Local")))


    hermes_agent = base / "hermes" / "hermes-agent"


    path = str(hermes_agent)


    if path not in sys.path:


        sys.path.insert(0, path)








def _repair_recent_native_cron_origin(conversation: dict[str, Any], user_request: str) -> int:


    if not _looks_like_native_cron_request(user_request):


        return 0


    try:


        _ensure_hermes_agent_path()


        from cron.jobs import load_jobs, save_jobs


    except Exception:


        return 0


    origin = {


        "platform": "api_server",


        "chat_id": str(conversation.get("session_id") or conversation.get("conversation_id") or ""),


        "session_id": str(conversation.get("session_id") or ""),


        "conversation_id": str(conversation.get("conversation_id") or ""),


    }


    changed = 0


    try:


        jobs = load_jobs()


        now = time.time()


        for job in jobs:


            deliver = str(job.get("deliver") or "")


            old_prompt = str(job.get("prompt") or "")


            new_prompt = _sanitize_native_cron_delivery_prompt(old_prompt, deliver)


            if new_prompt and new_prompt != old_prompt:


                job["prompt"] = new_prompt


                if not job.get("name") or str(job.get("name") or "").strip() == old_prompt[:50].strip():


                    job["name"] = (_conversation_title_from_content(new_prompt) or "Hermi native cron")[:50]


                changed += 1


            if "origin" not in {part.strip().lower() for part in deliver.split(",")}:


                continue


            if job.get("origin"):


                continue


            created_at = _parse_iso_epoch(str(job.get("created_at") or ""))


            if created_at and abs(now - created_at) > 180:


                continue


            job["origin"] = dict(origin)


            changed += 1


        if changed:


            save_jobs(jobs)


    except Exception:


        return changed


    return changed








def _parse_iso_epoch(value: str) -> float | None:


    try:


        from datetime import datetime





        return datetime.fromisoformat(value.replace("Z", "+00:00")).timestamp()


    except Exception:


        return None








def _looks_like_native_cron_request(text: str) -> bool:

    raw = str(text or "")

    return bool(

        re.search(r"\b(cronjob|cron|schedule|timer)\b|定时|闹钟", raw, re.IGNORECASE)

        or re.search(

            r"(?:\d+|[一二两三四五六七八九十百]+)\s*(?:秒|分钟|分|小时|天|seconds?|minutes?|hours?|days?)\s*(?:后|以后|later|from now)",

            raw,

            re.IGNORECASE,

        )

        or re.search(r"每隔\s*(?:\d+|[一二两三四五六七八九十百]+)?\s*(?:秒|分钟|分|小时|天)", raw)

        or re.search(r"(?:每天|每周|每月).{0,12}(?:\d{1,2}|[一二两三四五六七八九十]+)\s*(?:点|时)", raw)

        or re.search(r"remind\s+me\s+(?:in|at)\s+\d+", raw, re.IGNORECASE)

    )







def _looks_like_native_cron_success(text: str) -> bool:


    return bool(


        re.search(


            r"(job_id|next_run_at|已创建|创建成功|scheduled|created).{0,120}(cron|任务|job)",


            str(text or ""),


            re.IGNORECASE | re.DOTALL,


        )


    )








def _parse_native_cron_request(text: str, conversation: dict[str, Any]) -> dict[str, Any] | None:


    schedule = _parse_native_cron_schedule(text)


    if not schedule:


        return None


    prompt = _parse_native_cron_prompt(text)


    if not prompt:


        return None


    deliver = _parse_native_cron_deliver(text)


    prompt = _sanitize_native_cron_delivery_prompt(prompt, deliver)


    name = (_conversation_title_from_content(prompt) or "Hermi native cron")[:50]


    return {


        "schedule": schedule,


        "prompt": prompt,


        "deliver": deliver,


        "name": name,


        "origin": {


            "platform": "api_server",


            "chat_id": str(conversation.get("session_id") or conversation.get("conversation_id") or ""),


            "session_id": str(conversation.get("session_id") or ""),


            "conversation_id": str(conversation.get("conversation_id") or ""),


        },


    }








def _parse_native_cron_schedule(text: str) -> str:

    raw = str(text or "")


    match = re.search(r"schedule\s*=\s*([A-Za-z0-9*/:,\- ]+?)(?=\s*(?:[,，。；;]|deliver\s*=|prompt\s*=|$))", raw, re.IGNORECASE)


    if match:


        value = match.group(1).strip().strip("`'\"")


        if value:


            return value


    match = re.search(r"(\d+)\s*(?:分钟|分|minute|minutes|min|m)\s*(?:后|later)?", raw, re.IGNORECASE)


    if match:


        return f"{int(match.group(1))}m"


    match = re.search(r"(\d+)\s*(?:小时|hour|hours|h)\s*(?:后|later)?", raw, re.IGNORECASE)

    if match:

        return f"{int(match.group(1))}h"

    match = re.search(r"([一二两三四五六七八九十百]+)\s*(?:分钟|分)\s*(?:后|以后)", raw)

    if match:

        value = _chinese_small_number(match.group(1))

        if value is not None:

            return f"{value}m"

    match = re.search(r"([一二两三四五六七八九十百]+)\s*小时\s*(?:后|以后)", raw)

    if match:

        value = _chinese_small_number(match.group(1))

        if value is not None:

            return f"{value}h"

    return ""





def _chinese_small_number(value: str) -> int | None:

    digits = {"一": 1, "二": 2, "两": 2, "三": 3, "四": 4, "五": 5, "六": 6, "七": 7, "八": 8, "九": 9}

    text = str(value or "").strip()

    if text in digits:

        return digits[text]

    if text == "十":

        return 10

    if "十" in text:

        left, right = text.split("十", 1)

        tens = digits.get(left, 1) if left else 1

        ones = digits.get(right, 0) if right else 0

        return tens * 10 + ones

    return None







def _parse_native_cron_prompt(text: str) -> str:


    raw = str(text or "").strip()


    patterns = [


        r"prompt\s*=\s*(?:只输出(?:这一?句话)?[:：])?(.*?)(?:不要解释|不要\s*list|不要\s*shell|不要\s*curl|$)",


        r"只输出(?:这一?句话)?[:：]\s*(.*?)(?:不要解释|不要\s*list|不要\s*shell|不要\s*curl|$)",


        r"(?:内容|提醒内容|消息)\s*(?:是|为|:|：)\s*(.*?)(?:不要解释|不要\s*list|不要\s*shell|不要\s*curl|$)",


    ]


    for pattern in patterns:


        match = re.search(pattern, raw, re.IGNORECASE | re.DOTALL)


        if match:


            value = match.group(1).strip().strip("。；; \n\t`'\"")


            if value:


                return value


    return raw








def _sanitize_native_cron_delivery_prompt(prompt: str, deliver: str) -> str:


    text = str(prompt or "").strip()


    if not text:


        return ""


    if not _native_cron_deliver_has_external_chat(deliver):


        return text





    text = re.sub(r"^\s*prompt\s*=\s*", "", text, flags=re.IGNORECASE)


    text = _strip_native_cron_meta_instructions(text)





    for pattern in (


        r"\u7ed9.*?\u53d1.*?(?:QQ|qq)?.*?(?:\u79c1\u804a)?\u6d88\u606f\s*[:\uff1a]\s*(.+)$",


        r"(?:QQ|qq)?(?:\u79c1\u804a)?\u6d88\u606f\s*[:\uff1a]\s*(.+)$",


        r"(?:\u6d88\u606f|\u5185\u5bb9|\u63d0\u9192\u5185\u5bb9)\s*(?:\u662f\s*[:\uff1a]?|[:\uff1a])\s*(.+)$",


    ):


        match = re.search(pattern, text, re.IGNORECASE | re.DOTALL)


        if match:


            value = _clean_native_cron_delivery_text(match.group(1))


            if value:


                return _exact_native_cron_output_prompt(value)





    match = re.search(


        r"(?:\u63d0\u9192|\u53eb|\u901a\u77e5)\s*(?:QQ|qq)?\s*(?:\u8ba9\u6211|\u6211)\s*([^,，。！？!\n\r]+)",


        text,


        re.IGNORECASE,


    )


    if match:


        body = _clean_native_cron_delivery_text(match.group(1))


        if body:


            return _exact_native_cron_output_prompt(f"\u63d0\u9192\u6211{body}\u3002")





    cleaned = _clean_native_cron_delivery_text(text)


    if not cleaned:


        return "\u8bf7\u8f93\u51fa\u672c\u6b21\u63d0\u9192\u5185\u5bb9\u3002"


    if _looks_like_plain_reminder_delivery_text(cleaned):


        return _exact_native_cron_output_prompt(cleaned)


    return (


        "\u5b8c\u6210\u4efb\u52a1\u540e\u53ea\u8f93\u51fa\u6700\u7ec8\u8981\u6295\u9012\u7ed9\u7528\u6237\u7684\u5185\u5bb9\uff1b"


        "\u4e0d\u8981\u89e3\u91ca\uff0c\u4e0d\u8981\u8c03\u7528\u4efb\u4f55\u6295\u9012\u5de5\u5177\u3002\n"


        f"{cleaned}"


    )








def _looks_like_plain_reminder_delivery_text(text: str) -> bool:


    value = str(text or "").strip()


    if not value:


        return False


    task_words = (


        "\u67e5",


        "\u641c",


        "\u4e0a\u7f51",


        "\u603b\u7ed3",


        "\u68c0\u67e5",


        "\u76d1\u63a7",


        "\u8bfb\u53d6",


        "\u5206\u6790",


        "\u6267\u884c",


        "\u8fd0\u884c",


        "\u521b\u5efa",


        "\u5220\u9664",


    )


    return len(value) <= 120 and not any(word in value for word in task_words)








def _exact_native_cron_output_prompt(text: str) -> str:


    return (


        "\u8bf7\u53ea\u539f\u6837\u8f93\u51fa\u4ee5\u4e0b\u63d0\u9192\u6587\u672c\uff0c"


        "\u4e0d\u8981\u89e3\u91ca\uff0c\u4e0d\u8981\u6539\u5199\uff0c\u4e0d\u8981\u8c03\u7528\u4efb\u4f55\u5de5\u5177\uff1a\n"


        f"{text}"


    )








def _native_cron_deliver_has_external_chat(deliver: str) -> bool:


    parts = [part.strip().lower() for part in str(deliver or "").split(",") if part.strip()]


    return any(part == "qq" or part.startswith("qq:") or part == "qlos" or part.startswith("qlos:") for part in parts)








def _strip_native_cron_meta_instructions(text: str) -> str:


    value = str(text or "").strip()


    stop_patterns = [


        "\u4e0d\u8981\u89e3\u91ca",


        "\u4e0d\u8981\\s*list",


        "\u4e0d\u8981\\s*shell",


        "\u4e0d\u8981\\s*curl",


        "do\\s+not\\s+explain",


        "do\\s+not\\s+use\\s+shell",


        "do\\s+not\\s+use\\s+curl",


    ]


    value = re.split("|".join(stop_patterns), value, maxsplit=1, flags=re.IGNORECASE)[0].strip()


    value = re.sub(r"^\s*(?:\u53ea\u8f93\u51fa(?:\u8fd9\u4e00?\u53e5\u8bdd)?|output only)\s*[:\uff1a]?\s*", "", value, flags=re.IGNORECASE)


    return value.strip()








def _clean_native_cron_delivery_text(text: str) -> str:


    value = str(text or "").strip().strip("`'\" \n\r\t;；。")


    replacements = [


        (r"\d+\s*(?:\u5206\u949f|minute|minutes|min|m)\s*(?:\u540e|later)?", ""),


        (r"\d+\s*(?:\u5c0f\u65f6|hour|hours|h)\s*(?:\u540e|later)?", ""),


        (r"(?:\u518d\u8bd5\u8bd5|try again)[?\uff1f]?", ""),


        (r"(?:\u53d1\u5230|\u53d1\u7ed9|\u53d1\u5f80|\u53d1\u4e00\u6761|\u53d1\u6761|\u53d1|\u53d1\u9001\u5230|\u53d1\u9001\u7ed9|\u53d1\u9001)\s*(?:QQ|qq|QLOS|qlos)(?:\u79c1\u804a)?", ""),


        (r"(?:QQ|qq|QLOS|qlos)(?:\u79c1\u804a)?", ""),


        (r"(?:shell|curl|endpoint|/hermi/qq/send)", ""),


    ]


    for pattern, replacement in replacements:


        value = re.sub(pattern, replacement, value, flags=re.IGNORECASE)


    value = re.sub(r"\s+", " ", value).strip(" ,，。！？!：:")


    return value








def _parse_native_cron_deliver(text: str) -> str:


    raw = str(text or "")


    match = re.search(r"deliver\s*=\s*([^\s，。；;]+)", raw, re.IGNORECASE)


    if match:


        return match.group(1).strip().strip("`'\"")


    targets = ["origin"]


    if re.search(r"(QQ|qq|1000000001)", raw):


        targets.append("qq:1000000001")


    return ",".join(dict.fromkeys(targets))








def _looks_like_scheduled_request(text: str) -> bool:


    return bool(


        re.search(


            r"(定时|提醒|闹钟|稍后|之后|分钟后|小时后|天后|到点|每天|每周|每月|每隔|cron|corn|schedule|timer|remind|after|later|in \d+)",


            str(text or ""),


            re.IGNORECASE,


        )


    )








def _audit(conn, event: str, actor_user_id: str | None, detail: dict[str, Any]) -> None:


    conn.execute(


        """


        insert into audit_log (event, actor_user_id, detail_json, created_at)


        values (?, ?, ?, ?)


        """,


        (event, actor_user_id, json.dumps(detail, ensure_ascii=False), time.time()),


    )








def _insert_approved_qq_followup(
    conn,
    app: FastAPI,
    config: HermiConfig,
    approval: dict[str, Any],
) -> None:
    conversation = _require_conversation(conn, str(approval["conversation_id"]))
    actor_id = str(conversation.get("owner_user_id") or "")
    actor_row = conn.execute("select * from users where user_id = ?", (actor_id,)).fetchone()
    actor = dict(actor_row) if actor_row else {"user_id": actor_id, "role": "owner", "quota_policy": "owner"}
    profile_id = _conversation_profile_id(conn, config, conversation)
    profile_name = _profile_display_name(conn, profile_id)
    qq_profile_name = _profile_display_name(conn, config.qq_profile_id)
    history = build_hermi_messages(
        _conversation_history(conn, conversation["conversation_id"]),
        user=actor,
        conversation=conversation,
        soul_text=_load_soul_text(config),
        profile_name=profile_name,
        profile_id=profile_id,
        qq_profile_name=qq_profile_name,
    )
    history.append(
        {
            "role": "user",
            "content": (
                "[Hermi QQ delivery completed]\n"
                f"The approved QQ delivery has succeeded. You are {profile_name}; {qq_profile_name} handled QQ transport. "
                "Reply naturally in your current personality to the original user. Do not use generic system wording, "
                "do not explain implementation details, and do not return HERMI_ACTION."
            ),
        }
    )
    try:
        reply = _chat_profile(
            app.state.hermes_adapter,
            profile_id,
            history,
            conversation["session_id"],
            conversation["session_key"],
        ).strip()
        _increment_usage_from_hermes(
            conn,
            actor_id,
            app.state.hermes_adapter,
            conversation_id=conversation["conversation_id"],
            config=config,
        )
        reply, _ = extract_hermi_action(reply)
    except Exception:
        reply = ""
    if not reply:
        reply = f"{qq_profile_name} 已经替我把消息带去 QQ 了。"
    _insert_message(
        conn,
        conversation["conversation_id"],
        "assistant",
        reply,
        "hermes",
        metadata={
            "approval_id": approval["approval_id"],
            "approval_status": "approved",
            "action_type": "qq.send",
            "qq_delivery": "succeeded",
        },
    )
    conn.execute(
        "update conversations set updated_at = ? where conversation_id = ?",
        (time.time(), conversation["conversation_id"]),
    )


def _is_mixed_scheduled_request(text: str) -> bool:

    parts = [part.strip() for part in re.split(r"[。！？!?；;\n]+", str(text or "")) if part.strip()]

    return len(parts) > 1 and any(_looks_like_native_cron_request(part) for part in parts) and any(
        not _looks_like_native_cron_request(part) for part in parts
    )


def _create_owner_scheduled_job(

    conn,

    conversation_id: str,

    action: dict[str, Any],

) -> tuple[dict[str, Any], dict[str, Any]]:

    schedule = str(action.get("schedule") or "").strip()

    if not schedule:

        raise ValueError("定时任务缺少 schedule")

    kind = str(action.get("kind") or "cron")

    if kind not in {"cron", "interval", "once"}:

        kind = "cron"

    summary = str(action.get("summary") or "定时提醒").strip()

    content = str(action.get("content") or summary).strip()

    target = dict(action.get("target") or {})

    target.setdefault("delivery", ["hermi"])

    target.setdefault("conversation_id", conversation_id)

    task = _create_task(

        conn,

        title=summary,

        task_type="scheduled",

        conversation_id=conversation_id,

        source="owner",

        created_by="owner",

        metadata={"action_type": "scheduled.create", "schedule": schedule},

        status="running",

    )

    job = _create_scheduled_job(

        conn,

        task_id=task["task_id"],

        kind=kind,

        schedule=schedule,

        summary=summary,

        target=target,

        payload={"content": content, **(action.get("payload") or {})},

        created_by="owner",

        status="active",

        policy=action.get("policy") or {},

        max_retries=int(action.get("max_retries") or 0),

    )

    _create_task_event(

        conn,

        task_id=task["task_id"],

        event_type="scheduled_job_created",

        content=f"Owner 已安排定时任务：{summary}",

        metadata={"job_id": job["job_id"], "schedule": schedule},

    )

    return task, job


def _execute_approved_action(

    conn,

    app: FastAPI,

    config: HermiConfig,

    approval: dict[str, Any],

    action: dict[str, Any] | None,

) -> str:

    action_type = str((action or {}).get("type") or "")

    if action_type == "quota.temporary.grant":
        conversation = _require_conversation(conn, str(approval["conversation_id"]))
        user_id = str((action or {}).get("user_id") or conversation.get("owner_user_id") or "")
        target = conn.execute("select * from users where user_id = ?", (user_id,)).fetchone()
        token_amount = int((action or {}).get("token_amount") or 0)
        if not target or dict(target).get("role") in {"owner", "channel"} or token_amount != TEMPORARY_QUOTA_TOKENS:
            raise ValueError("invalid_temporary_quota_request")
        start, end, _ = _quota_window_bounds(dict(target))
        conn.execute(
            """
            insert or ignore into temporary_quota_grants (
              grant_id, user_id, approval_id, token_amount, window_start_at, window_end_at, created_at
            ) values (?, ?, ?, ?, ?, ?, ?)
            """,
            (f"quota-{uuid.uuid4().hex[:12]}", user_id, approval["approval_id"], token_amount, start, end, time.time()),
        )
        _create_user_notice(
            conn,
            user_id,
            kind="quota.temporary.grant.approved",
            title="临时额度申请已通过",
            message="Owner 已批准本次申请，当前额度窗口已增加 100,000 Token。",
        )
        return "已批准临时额度申请。"

    if action_type == "qq.send":
        succeeded, execution_note = _execute_qq_send_action(app.state.qlos_client, action)
        if succeeded:
            _insert_approved_qq_followup(conn, app, config, approval)
        return execution_note

    if action_type == "chat.message":

        conversation = _require_conversation(conn, str(approval["conversation_id"]))

        actor_id = str((action or {}).get("created_by") or conversation.get("owner_user_id") or "")

        actor_row = conn.execute("select * from users where user_id = ?", (actor_id,)).fetchone()

        actor = dict(actor_row) if actor_row else {"user_id": actor_id, "role": "friend", "quota_policy": "friend_free"}

        history = build_hermi_messages(

            _conversation_history(conn, conversation["conversation_id"]),

            user=actor,

            conversation=conversation,

            recent_qq_context="",

            soul_text=_load_soul_text(config),

            profile_name=_active_profile_name(conn, config),

        )

        history.append(

            {

                "role": "user",

                "content": (

                    "[Hermi approval completed]\n"

                    "Owner approved the following original user message. Reply to this message directly; "

                    "do not discuss the approval process.\n\n"

                    + str((action or {}).get("content") or "")

                ),

            }

        )

        try:

            reply = _chat_profile(

                app.state.hermes_adapter, config.hermi_profile_id, history,

                conversation["session_id"], conversation["session_key"],

            ).strip()

            _increment_usage_from_hermes(
                conn,
                actor_id,
                app.state.hermes_adapter,
                conversation_id=conversation["conversation_id"],
                config=config,
            )

        except Exception:

            reply = "Owner 已批准消息，但调用 Hermes 失败，请稍后重试。"

        _insert_message(

            conn,

            conversation["conversation_id"],

            "assistant",

            reply or "Owner 已批准消息，但 Hermes 没有返回内容。",

            "hermes",

            metadata={"approval_id": approval["approval_id"], "approval_status": "approved"},

        )

        conn.execute(

            "update conversations set updated_at = ? where conversation_id = ?",

            (time.time(), conversation["conversation_id"]),

        )

        return "消息已获批准并发送给 Hermes。"

    if action_type.startswith("draft."):


        content = str((action or {}).get("content") or "").strip()


        summary = str(approval.get("summary") or (action or {}).get("summary") or "主动草稿")


        message = f"主动草稿已确认：{summary}"


        if content:


            message = f"{message}\n\n{content}"


        _insert_message(


            conn,


            str(approval["conversation_id"]),


            "assistant",


            message,


            "hermi",


            metadata={"approval_id": approval["approval_id"], "action_type": action_type},


        )


        conn.execute(


            "update conversations set updated_at = ? where conversation_id = ?",


            (time.time(), approval["conversation_id"]),


        )


        return "已确认主动草稿。"


    if action_type == "hermes.permission.request":


        capability = str((action or {}).get("requested_capability") or "unknown")


        summary = str((action or {}).get("summary") or approval.get("summary") or "Hermes 权限请求")


        restart_scheduled = capability == "service.restart" and _schedule_hermi_gateway_restart()


        next_step = (


            "Hermi Gateway 已安排后台重启。"


            if restart_scheduled


            else "下一步需要 Hermes 或对应执行器继续发起具体动作。"


        )


        _insert_message(


            conn,


            str(approval["conversation_id"]),


            "assistant",


            f"已批准 Hermes 权限请求：{summary}\n\n能力：{capability}\n\n{next_step}",


            "hermi",


            metadata={"approval_id": approval["approval_id"], "action_type": action_type, "capability": capability},


        )


        conn.execute(


            "update conversations set updated_at = ? where conversation_id = ?",


            (time.time(), approval["conversation_id"]),


        )


        if restart_scheduled:


            return "已批准 Hermes 权限请求，并安排 Hermi Gateway 后台重启。"


        return "已批准 Hermes 权限请求。"


    if action_type in {"scheduled.create", "cron.create"}:

        schedule = str((action or {}).get("schedule") or "").strip()

        if not schedule:

            return "Hermi 动作未执行：定时任务缺少 schedule。"

        kind = str((action or {}).get("kind") or "cron")


        if kind not in {"cron", "interval", "once"}:

            kind = "cron"

        summary = str((action or {}).get("summary") or approval.get("summary") or "定时任务").strip()

        content = str((action or {}).get("content") or "").strip()

        created_by = str((action or {}).get("created_by") or "hermes")

        task = _create_task(

            conn,

            title=summary,

            task_type="scheduled",

            conversation_id=str(approval["conversation_id"]),

            source="approval",

            created_by=created_by,

            metadata={

                "approval_id": approval["approval_id"],

                "action_type": action_type,

                "schedule": schedule,

            },

            status="running",


        )


        job = _create_scheduled_job(


            conn,


            task_id=task["task_id"],


            kind=kind,


            schedule=schedule,


            summary=summary,


            target=(action or {}).get("target") or {},

            payload={"content": content, **((action or {}).get("payload") or {})},

            created_by=created_by,

            status="active",

            policy=(action or {}).get("policy") or {},

            max_retries=int((action or {}).get("max_retries") or 0),

        )

        _create_task_event(


            conn,


            task_id=task["task_id"],


            event_type="scheduled_job_created",


            content=f"已创建定时任务：{summary} ({schedule})",


            metadata={"job_id": job["job_id"], "approval_id": approval["approval_id"]},


        )


        _insert_message(


            conn,


            str(approval["conversation_id"]),


            "assistant",


            f"Owner 已批准啦，“{summary}”已经排进提醒列表。到时间后我会在这里叫你。",


            "hermi",


            metadata={


                "approval_id": approval["approval_id"],


                "action_type": action_type,


                "task_id": task["task_id"],


                "job_id": job["job_id"],


            },


        )


        conn.execute(


            "update conversations set updated_at = ? where conversation_id = ?",


            (time.time(), approval["conversation_id"]),


        )


        return "已创建定时任务。"


    return _execute_hermi_action(app.state.qlos_client, action)







def _schedule_hermi_gateway_restart() -> bool:


    root = Path(__file__).resolve().parents[1]


    script = root / "scripts" / "start_hermi_gateway.ps1"


    if not script.exists():


        return False


    ps_script = str(script).replace("'", "''")


    command = f"Start-Sleep -Seconds 2; & '{ps_script}' -NoOpen"


    encoded_command = base64.b64encode(command.encode("utf-16le")).decode("ascii")


    creationflags = 0


    env = dict(os.environ)


    env["HERMI_RESTART_PARENT_PID"] = str(os.getpid())


    state_dir = root / "state"


    state_dir.mkdir(parents=True, exist_ok=True)


    try:


        stdout = (state_dir / "hermi_restart.out.log").open("ab")


        stderr = (state_dir / "hermi_restart.err.log").open("ab")


        subprocess.Popen(


            ["powershell.exe", "-NoProfile", "-ExecutionPolicy", "Bypass", "-EncodedCommand", encoded_command],


            cwd=root,


            env=env,


            stdout=stdout,


            stderr=stderr,


            stdin=subprocess.DEVNULL,


            creationflags=creationflags,


        )


    except OSError:


        return False


    return True








def _execute_qq_send_action(qlos_client: Any, action: dict[str, Any] | None) -> tuple[bool, str]:
    if not action or action.get("type") != "qq.send":
        return False, "Hermi 动作未执行：未知动作类型。"


    chat_type = str(action.get("chat_type") or "")


    message = str(action.get("message") or "").strip()


    user_id = str(action.get("user_id") or "").strip() or None


    group_id = str(action.get("group_id") or "").strip() or None


    images = action.get("images") if isinstance(action.get("images"), list) else []


    attachments = action.get("attachments") if isinstance(action.get("attachments"), list) else []


    if images or attachments:


        message = _strip_local_media_path_text(message) or "图片已附上。"


    if chat_type not in {"private", "group"} or not message:


        return False, "Hermi 动作未执行：QQ 发送参数不完整。"


    try:


        try:


            qlos_client.send_qq(


                chat_type=chat_type,


                user_id=user_id,


                group_id=group_id,


                message=message,


                images=images,


                attachments=attachments,


            )


        except TypeError:


            qlos_client.send_qq(chat_type=chat_type, user_id=user_id, group_id=group_id, message=message)


    except Exception as exc:


        return False, f"Hermi 动作执行失败：{type(exc).__name__}: {exc}"

    return True, "已执行 QQ 发送动作。"


def _execute_hermi_action(qlos_client: Any, action: dict[str, Any] | None) -> str:
    if not action:
        return ""
    _, execution_note = _execute_qq_send_action(qlos_client, action)
    return execution_note








def _web_path(name: str) -> Path:


    return Path(__file__).resolve().parents[1] / "web" / name








app = create_app()



