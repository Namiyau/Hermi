from __future__ import annotations

import sqlite3
import time
from pathlib import Path
from typing import Any


def init_db(path: str | Path) -> sqlite3.Connection:
    db_path = Path(path)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.executescript(
        """
        create table if not exists users (
          user_id text primary key,
          display_name text not null,
          role text not null,
          token text unique not null,
          can_approve integer not null default 0,
          can_remote_control integer not null default 0,
          quota_policy text not null default 'owner',
          created_at real not null
        );

        create table if not exists user_profiles (
          user_id text primary key,
          relationship text not null default '',
          preferences text not null default '',
          recent_focus text not null default '',
          revision integer not null default 0,
          updated_at real not null default 0
        );

        create table if not exists user_profile_injections (
          conversation_id text not null,
          user_id text not null,
          revision integer not null,
          injected_at real not null,
          primary key (conversation_id, user_id)
        );

        create table if not exists devices (
          device_id text primary key,
          user_id text not null,
          token text unique not null,
          name text not null,
          created_at real not null
        );

        create table if not exists conversations (
          conversation_id text primary key,
          channel text not null,
          source_id text not null,
          title text not null,
          session_id text not null,
          session_key text not null,
          profile_id text not null default '',
          owner_user_id text not null,
          visibility text not null default 'private',
          quota_policy text not null default 'owner',
          created_at real not null,
          updated_at real not null,
          unique(channel, source_id)
        );

        create table if not exists messages (
          message_id text primary key,
          conversation_id text not null,
          role text not null,
          content text not null,
          source_channel text not null,
          metadata_json text not null default '{}',
          created_at real not null
        );

        create table if not exists qq_inbound_events (
          source_id text not null,
          message_id text not null,
          conversation_id text not null,
          created_at real not null,
          primary key (source_id, message_id)
        );

        create table if not exists hermes_session_sync (
          conversation_id text not null,
          remote_message_id text not null,
          disposition text not null,
          created_at real not null,
          primary key(conversation_id, remote_message_id)
        );

        create table if not exists message_runs (
          run_id text primary key,
          conversation_id text not null,
          user_id text not null,
          status text not null,
          events_json text not null default '[]',
          final_json text not null default '{}',
          error text not null default '',
          created_at real not null,
          updated_at real not null
        );

        create table if not exists media_files (
          file_id text primary key,
          conversation_id text,
          source_channel text not null,
          source_message_id text,
          original_name text not null,
          mime text not null,
          size_bytes integer not null,
          sha256 text not null,
          storage_path text not null,
          visibility text not null default 'private',
          created_by text not null,
          expires_at real,
          created_at real not null,
          metadata_json text not null default '{}'
        );

        create table if not exists approvals (
          approval_id text primary key,
          conversation_id text not null,
          action_type text not null default '',
          payload_json text not null default '{}',
          status text not null,
          source text not null,
          summary text not null,
          risk_level text not null,
          expires_at real not null,
          decision text,
          decided_by text,
          decided_at real,
          created_at real not null default 0,
          updated_at real not null default 0
        );

        create table if not exists usage_daily (
          usage_key text primary key,
          user_id text not null,
          day text not null,
          text_messages integer not null default 0,
          image_messages integer not null default 0,
          file_uploads integer not null default 0,
          prompt_tokens integer not null default 0,
          completion_tokens integer not null default 0,
          total_tokens integer not null default 0
        );

        create table if not exists conversation_usage (
          conversation_id text primary key,
          user_id text not null,
          prompt_tokens integer not null default 0,
          completion_tokens integer not null default 0,
          total_tokens integer not null default 0,
          updated_at real not null
        );

        create table if not exists usage_windows (
          window_key text primary key,
          user_id text not null,
          window_start_at real not null,
          window_end_at real not null,
          text_messages integer not null default 0,
          file_uploads integer not null default 0,
          total_tokens integer not null default 0
        );

        create table if not exists temporary_quota_grants (
          grant_id text primary key,
          user_id text not null,
          approval_id text not null unique,
          token_amount integer not null,
          window_start_at real not null,
          window_end_at real not null,
          created_at real not null
        );

        create table if not exists user_notices (
          notice_id text primary key,
          user_id text not null,
          kind text not null,
          title text not null,
          message text not null,
          created_at real not null,
          read_at real
        );

        create table if not exists audit_log (
          audit_id integer primary key autoincrement,
          event text not null,
          actor_user_id text,
          detail_json text not null,
          created_at real not null
        );

        create table if not exists evolution_notes (
          note_id text primary key,
          content text not null,
          created_by text not null,
          created_at real not null,
          updated_at real not null,
          pinned_at real
        );

        create table if not exists evolution_blueprints (
          note_id text primary key,
          content text not null,
          created_by text not null,
          created_at real not null,
          updated_at real not null,
          pinned_at real
        );

        create table if not exists feature_proposals (
          proposal_id text primary key,
          title text not null,
          content text not null,
          proposal_type text not null default 'support',
          options_json text not null default '[]',
          status text not null default 'open',
          created_by text not null,
          created_at real not null,
          updated_at real not null
        );

        create table if not exists feature_votes (
          proposal_id text not null,
          user_id text not null,
          choice text not null,
          created_at real not null,
          updated_at real not null,
          primary key (proposal_id, user_id)
        );

        create table if not exists feature_proposal_vote_confirms (
          proposal_id text not null,
          user_id text not null,
          confirmed_at real not null,
          primary key (proposal_id, user_id)
        );

        create table if not exists feature_proposal_comments (
          proposal_id text not null,
          user_id text not null,
          content text not null,
          created_at real not null,
          updated_at real not null,
          primary key (proposal_id, user_id)
        );

        create table if not exists feature_proposal_opinion_reveals (
          proposal_id text not null,
          user_id text not null,
          revealed_at real not null,
          primary key (proposal_id, user_id)
        );

        create table if not exists tasks (
          task_id text primary key,
          title text not null,
          status text not null,
          task_type text not null default 'general',
          conversation_id text,
          source text not null default 'manual',
          created_by text not null,
          created_at real not null,
          updated_at real not null,
          metadata_json text not null default '{}'
        );

        create table if not exists task_events (
          event_id text primary key,
          task_id text not null,
          event_type text not null,
          content text not null,
          created_at real not null,
          metadata_json text not null default '{}'
        );

        create table if not exists task_artifacts (
          artifact_id text primary key,
          task_id text not null,
          file_id text not null,
          created_at real not null
        );

        create table if not exists scheduled_jobs (
          job_id text primary key,
          task_id text,
          kind text not null,
          schedule text not null,
          summary text not null,
          status text not null default 'pending',
          target_json text not null default '{}',
          payload_json text not null default '{}',
          created_by text not null,
          created_at real not null,
          updated_at real not null,
          last_run_at real
        );

        create table if not exists prompt_cards (
          card_id text primary key,
          name text not null,
          card_type text not null,
          content text not null,
          enabled integer not null default 1,
          created_at real not null,
          updated_at real not null,
          metadata_json text not null default '{}'
        );

        create table if not exists prompt_bindings (
          binding_id text primary key,
          card_id text not null,
          scope_type text not null,
          scope_id text not null,
          priority integer not null default 100,
          enabled integer not null default 1,
          created_at real not null,
          updated_at real not null,
          metadata_json text not null default '{}'
        );

        create table if not exists prompt_renders (
          render_id text primary key,
          conversation_id text,
          task_id text,
          render_type text not null,
          content text not null,
          created_at real not null,
          metadata_json text not null default '{}'
        );

        create table if not exists channel_events (
          event_id text primary key,
          channel text not null,
          source_id text not null,
          direction text not null,
          envelope_json text not null default '{}',
          task_id text,
          created_at real not null,
          metadata_json text not null default '{}'
        );

        create table if not exists agents (
          agent_id text primary key,
          name text not null,
          agent_type text not null,
          description text not null default '',
          config_json text not null default '{}',
          created_at real not null,
          updated_at real not null
        );

        create table if not exists profile_settings (
          profile_id text primary key,
          display_name text not null,
          customized integer not null default 0,
          updated_at real not null
        );

        create table if not exists rooms (
          room_id text primary key,
          name text not null,
          room_type text not null,
          mode text not null,
          created_at real not null,
          updated_at real not null
        );

        create table if not exists room_members (
          room_id text not null,
          agent_id text not null,
          role text not null,
          joined_at real not null,
          primary key(room_id, agent_id)
        );

        create table if not exists workflow_runs (
          run_id text primary key,
          room_id text,
          mode text not null,
          status text not null,
          max_turns integer not null default 1,
          topic text not null default '',
          state_json text not null default '{}',
          created_at real not null,
          updated_at real not null
        );

        create table if not exists workflow_steps (
          step_id text primary key,
          run_id text not null,
          step_index integer not null,
          agent_id text,
          role text not null,
          content text not null,
          created_at real not null
        );

        create table if not exists nodes (
          node_id text primary key,
          name text not null,
          status text not null,
          endpoint text not null default '',
          last_seen_at real,
          metadata_json text not null default '{}',
          created_at real not null,
          updated_at real not null
        );

        create table if not exists deployment_jobs (
          job_id text primary key,
          target_node text not null,
          summary text not null,
          status text not null,
          payload_json text not null default '{}',
          created_at real not null,
          updated_at real not null
        );

        create table if not exists node_jobs (
          job_id text primary key,
          node_id text not null,
          summary text not null,
          status text not null,
          payload_json text not null default '{}',
          result_json text not null default '{}',
          created_by text not null,
          claimed_at real,
          completed_at real,
          created_at real not null,
          updated_at real not null
        );

        create table if not exists node_job_logs (
          log_id text primary key,
          job_id text not null,
          node_id text not null,
          event_type text not null,
          content text not null,
          created_at real not null,
          metadata_json text not null default '{}'
        );

        create table if not exists node_job_artifacts (
          artifact_id text primary key,
          job_id text not null,
          node_id text not null,
          artifact_type text not null,
          original_name text not null,
          mime text not null,
          size_bytes integer not null,
          sha256 text not null,
          storage_path text not null,
          metadata_json text not null default '{}',
          created_at real not null
        );

        create table if not exists scheduled_job_runs (
          run_id text primary key,
          job_id text not null,
          status text not null,
          started_at real not null,
          finished_at real,
          duration_ms integer not null default 0,
          result_json text not null default '{}',
          error text not null default '',
          token_json text not null default '{}'
        );

        create table if not exists operation_zones (
          zone_id text primary key,
          node_id text not null,
          workspace_path text not null,
          allowed_tools_json text not null default '[]',
          denied_paths_json text not null default '[]',
          permission_level text not null default 'readonly',
          requires_approval integer not null default 1,
          created_by text not null,
          created_at real not null,
          updated_at real not null
        );

        create table if not exists operation_logs (
          log_id text primary key,
          zone_id text not null,
          action text not null,
          status text not null,
          detail_json text not null default '{}',
          created_at real not null
        );

        create table if not exists capability_registry (
          capability_id text primary key,
          title text not null,
          description text not null default '',
          risk_level text not null default 'medium',
          schema_json text not null default '{}',
          approval_policy text not null default 'owner',
          enabled integer not null default 1,
          created_at real not null,
          updated_at real not null
        );

        create table if not exists approval_callbacks (
          callback_id text primary key,
          approval_id text not null,
          external_run_id text not null default '',
          external_request_id text not null default '',
          status text not null,
          payload_json text not null default '{}',
          created_at real not null,
          updated_at real not null
        );
        """
    )
    _ensure_columns(
        conn,
        "users",
        {
            "locale": "text not null default 'auto'",
        },
    )
    _ensure_columns(
        conn,
        "conversations",
        {
            "profile_id": "text not null default ''",
        },
    )
    _ensure_columns(
        conn,
        "usage_daily",
        {
            "prompt_tokens": "integer not null default 0",
            "completion_tokens": "integer not null default 0",
            "total_tokens": "integer not null default 0",
        },
    )
    _ensure_columns(
        conn,
        "usage_windows",
        {
            "total_tokens": "integer not null default 0",
        },
    )
    _ensure_columns(
        conn,
        "conversation_usage",
        {
            "cache_read_tokens": "integer not null default 0",
            "cache_reported": "integer not null default 0",
        },
    )
    _ensure_columns(
        conn,
        "approvals",
        {
            "action_type": "text not null default ''",
            "payload_json": "text not null default '{}'",
            "decided_by": "text",
            "created_at": "real not null default 0",
            "updated_at": "real not null default 0",
        },
    )
    _ensure_columns(
        conn,
        "media_files",
        {
            "conversation_id": "text",
            "source_message_id": "text",
            "visibility": "text not null default 'private'",
            "expires_at": "real",
            "metadata_json": "text not null default '{}'",
        },
    )
    _ensure_columns(
        conn,
        "nodes",
        {
            "token": "text",
            "capabilities_json": "text not null default '[]'",
            "created_by": "text not null default 'owner'",
            "policy_json": "text not null default '{}'",
        },
    )
    _ensure_columns(
        conn,
        "scheduled_jobs",
        {
            "policy_json": "text not null default '{}'",
            "retry_count": "integer not null default 0",
            "max_retries": "integer not null default 0",
            "next_run_after": "real",
        },
    )
    _ensure_columns(
        conn,
        "feature_proposals",
        {
            "proposal_type": "text not null default 'support'",
            "options_json": "text not null default '[]'",
        },
    )
    _ensure_columns(
        conn,
        "evolution_notes",
        {
            "pinned_at": "real",
        },
    )
    _ensure_columns(
        conn,
        "users",
        {
            "permissions": "text",
        },
    )
    _ensure_columns(
        conn,
        "rooms",
        {
            "host_agent_id": "text",
            "permission_level": "text not null default 'general'",
            "history_policy": "text not null default 'adaptive'",
            "max_turns": "integer not null default 3",
            "settings_json": "text not null default '{}'",
        },
    )
    _ensure_columns(
        conn,
        "workflow_runs",
        {
            "state_json": "text not null default '{}'",
        },
    )
    _ensure_columns(
        conn,
        "workflow_steps",
        {
            "session_id": "text not null default ''",
            "usage_json": "text not null default '{}'",
            "error": "text not null default ''",
            "metadata_json": "text not null default '{}'",
        },
    )
    conn.commit()
    return conn


def _ensure_columns(conn: sqlite3.Connection, table: str, columns: dict[str, str]) -> None:
    existing = {
        row["name"]
        for row in conn.execute(f"pragma table_info({table})").fetchall()
    }
    for name, definition in columns.items():
        if name not in existing:
            conn.execute(f"alter table {table} add column {name} {definition}")


def upsert_user(
    conn: sqlite3.Connection,
    *,
    user_id: str,
    display_name: str,
    role: str,
    token: str,
    can_approve: bool,
    can_remote_control: bool,
    quota_policy: str,
    permissions: str = "",
) -> None:
    now = time.time()
    conn.execute(
        """
        insert into users (
          user_id, display_name, role, token, can_approve, can_remote_control, quota_policy, permissions, created_at
        ) values (?, ?, ?, ?, ?, ?, ?, ?, ?)
        on conflict(user_id) do update set
          display_name = excluded.display_name,
          role = excluded.role,
          token = excluded.token,
          can_approve = excluded.can_approve,
          can_remote_control = excluded.can_remote_control,
          quota_policy = excluded.quota_policy,
          permissions = excluded.permissions
        """,
        (
            user_id,
            display_name,
            role,
            token,
            1 if can_approve else 0,
            1 if can_remote_control else 0,
            quota_policy,
            permissions or "",
            now,
        ),
    )
    conn.commit()


def create_seed_users(conn: sqlite3.Connection, owner_token: str, channel_token: str) -> None:
    _seed_system_user(
        conn,
        user_id="owner",
        display_name="Owner",
        role="owner",
        token=owner_token,
        can_approve=True,
        can_remote_control=True,
        quota_policy="owner",
    )
    _seed_system_user(
        conn,
        user_id="channel:qlos",
        display_name="QLOS-Lite",
        role="channel",
        token=channel_token,
        can_approve=False,
        can_remote_control=False,
        quota_policy="channel",
    )


def _seed_system_user(
    conn: sqlite3.Connection,
    *,
    user_id: str,
    display_name: str,
    role: str,
    token: str,
    can_approve: bool,
    can_remote_control: bool,
    quota_policy: str,
) -> None:
    existing = conn.execute("select 1 from users where user_id = ?", (user_id,)).fetchone()
    if existing:
        # Keep owner-managed labels and permissions across service restarts.
        conn.execute(
            """
            update users set token = ?, role = ?, can_approve = ?, can_remote_control = ?
            where user_id = ?
            """,
            (token, role, 1 if can_approve else 0, 1 if can_remote_control else 0, user_id),
        )
        conn.commit()
        return
    upsert_user(
        conn,
        user_id=user_id,
        display_name=display_name,
        role=role,
        token=token,
        can_approve=can_approve,
        can_remote_control=can_remote_control,
        quota_policy=quota_policy,
        permissions="",
    )


def verify_token(conn: sqlite3.Connection, token: str) -> dict[str, Any] | None:
    token = str(token or "").strip()
    if not token:
        return None
    row = conn.execute("select * from users where token = ?", (token,)).fetchone()
    return dict(row) if row else None
