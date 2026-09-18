from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_frontend_enter_send_typewriter_panels_and_modals_present():
    html = (ROOT / "web" / "index.html").read_text(encoding="utf-8")
    script = (ROOT / "web" / "app.js").read_text(encoding="utf-8")
    admin_tools = (ROOT / "web" / "admin_tools.js").read_text(encoding="utf-8")
    permissions_panel = (ROOT / "web" / "permissions_panel.js").read_text(encoding="utf-8")
    scheduled_jobs = (ROOT / "web" / "scheduled_jobs.js").read_text(encoding="utf-8")
    styles = (ROOT / "web" / "styles.css").read_text(encoding="utf-8")

    assert 'id="token-form"' in html
    assert 'id="token-submit"' in html
    assert 'id="scroll-bottom"' in html
    assert 'id="left-panel-toggle"' in html
    assert 'id="right-panel-toggle"' in html
    assert 'id="display-mode-toggle"' in html
    assert 'id="file-form"' in html
    assert 'id="file-input"' in html
    assert 'id="upload-trigger"' in html
    assert 'id="send-button"' in html
    assert 'class="panel-footer"' in html
    assert html.index('id="file-form"') > html.index('id="message-form"')
    assert 'id="hermi-conversation-list"' in html
    assert 'id="api-conversation-list"' in html
    assert 'id="other-conversation-list"' in html
    assert 'id="scheduled-job-list"' in html
    assert "Hermi会话" in html
    assert "他人会话" in html
    assert "API会话" in html
    assert "定时任务" in html
    assert 'id="temporary-tools-button"' in html
    assert 'id="settings-tools-button"' in html
    assert 'id="temporary-tools-modal"' in html
    assert 'id="settings-tools-modal"' in html
    assert 'id="scheduled-job-detail-modal"' in html
    assert 'id="confirm-modal"' in html
    assert 'id="confirm-ok"' in html
    assert html.index('id="approval-list"') < html.index('id="temporary-tools-modal"')
    assert 'id="admin-user-form"' in html
    assert 'id="admin-role-label"' in html
    assert 'id="admin-quota-policy-label"' not in html
    assert 'id="admin-quota-policy"' not in html
    assert 'id="admin-user-list"' in html
    assert 'id="perm-detail-modal"' in html
    assert 'id="perm-detail-save"' in html
    assert 'id="usage-list"' in html
    assert 'id="task-list"' in html
    assert 'id="context-summary"' in html
    assert 'id="profile-list"' in html
    assert 'id="meeting-preset-list"' in html
    assert 'id="brain-status-list"' in html
    assert 'id="prompt-binding-list"' in html
    assert 'id="capability-list"' in html
    assert 'id="action-validate-form"' in html
    assert 'id="action-validate-input"' in html
    assert 'id="usage-guide-modal"' in html
    assert 'id="usage-guide-confirm"' in html
    assert 'id="usage-guide-dismiss"' in html
    assert '<script src="/admin_tools.js"></script>' in html
    assert '<script src="/permissions_panel.js"></script>' in html
    assert '<script src="/scheduled_jobs.js"></script>' in html

    assert 'event.key === "Enter" && !event.shiftKey && !isMobileComposer()' in script
    assert "requestSubmit()" in script
    assert "AbortController" in script
    assert "cancelActiveSend" in script
    assert "setSendingState" in script
    assert "recoverBackgroundSend" in script
    assert "refreshVisibleState" in script
    assert 'document.addEventListener("visibilitychange"' in script
    assert "setConnectionState(true);" in script
    assert 'tokenForm.addEventListener("submit"' in script
    assert 'leftPanelToggle.addEventListener("click"' in script
    assert 'rightPanelToggle.addEventListener("click"' in script
    assert "togglePanel" in script
    assert "data-left-open" in script
    assert "data-right-open" in script
    assert "sendMessageStream" in script
    assert "capability_id: capabilityId" in script
    assert "showUsageGuideIfNeeded" in script
    assert "hermi_usage_guide_dismissed" in script
    assert "sendMessageStream(sendConversationId" in script
    assert "inflightByConversation" in script
    assert "loadActiveRun" in script
    assert "/runs/active" in script
    assert "runTrace" in script
    assert "state.activeRunPoll" in script
    assert "renderInflightForCurrentConversation" in script
    assert "Hermi 正在思考" not in script
    assert "inflight-assistant" not in script
    assert "data-inflight-id" not in script
    assert "data-pending-id" in script
    assert "createNewConversation" in script
    assert 'newConversationButton.addEventListener("click", openNewConversationPicker)' in script
    assert "setDisplayMode" in script
    assert "initializePanels()" in script
    assert "confirmAction" in script
    assert "resolveConfirm" in script
    assert "window.confirm" not in script
    assert "messageTime" in script
    assert "formatClock" in script
    assert "getFullYear()" in script
    assert "pad(date.getMonth() + 1)" in script
    assert "message-meta-time" in script
    assert "message-time-divider" in script
    assert "bubble.append(time, line)" in script
    assert "bubble.append(body, messageTime(createdAt))" not in script
    assert "parseSse" in script
    assert "renderThoughtPanel" in script
    assert "translateThoughtContent" in script
    assert "isMessageListNearBottom" in script
    assert "if (wasNearBottom) scrollMessages(true)" in script
    assert "messageTrace(message)" in script
    assert "renderTracePanel" in script
    assert "line.innerHTML = renderMarkdown(translateThoughtContent" in script
    assert "collapseThoughtPanel" in script
    assert "stageSelectedFiles" in script
    assert "uploadPendingFiles" in script
    assert "dropZone" in script
    assert "formatScheduledJobDetail" in scheduled_jobs
    assert "await loadConversations()" in script
    assert "parsed.event === \"thought\" || parsed.event === \"tool\"" in script
    assert "trace_started_at" in script
    assert "async function downloadFileAttachment" in script
    assert "file-card-download" in script
    assert "Forwarding to Hermes" not in script
    assert "animateAssistant" in script
    assert "body.innerHTML = renderMarkdown(text.slice(0, index))" in script
    assert "renderMarkdown" in script
    assert "escapeHtml" in script
    assert "markdown-body" in script
    assert "pending-user" in script
    assert "openDrawer" in script
    assert "selectConversation" in script
    assert "if (isCompactViewport()) closeDrawers()" in script
    assert "conversation-delete" in script
    assert 'method: "DELETE"' in script
    assert "updateScrollButton" in script
    assert "else updateScrollButton()" in script
    assert "uploadSelectedFile" in script
    assert 'fileInput.addEventListener("change"' in script
    assert "uploadTrigger" in script
    assert "deleteFile" in script
    assert "deleteApproval" in script
    assert "showScheduledJobDetail" in scheduled_jobs
    assert "deleteScheduledJob" in scheduled_jobs
    assert "deleteAdminUser" in script
    assert "openTemporaryTools" in script
    assert "openSettingsTools" in script
    assert "syncAdminQuotaPolicy" not in script
    assert "window.HermiAdminTools" in script
    assert "FormData" in script
    assert "loadFiles" in script
    assert "renderConversationSection" in script
    assert "isHermiConversation" in script
    assert "async function loadScheduledJobs" not in script
    assert "function renderScheduledJobItem" not in script
    assert "window.HermiScheduledJobs.load" in script
    assert "scheduled-job-delete-inline" in scheduled_jobs
    assert "otherConversationList" in script
    assert "isOtherConversation" in script
    assert "conversationDisplayTitle" in script
    assert "async function openPermDetailModal" not in script
    assert "window.HermiPermissionsPanel.open" in script
    assert "encodeURIComponent(userId)" in admin_tools
    assert "loadUsers" in script
    assert "loadUsage" in script
    assert "total_tokens" in script
    assert "loadTasks" in script
    assert "createAdminUser" in script
    assert "loadConversationContext" in script
    assert "loadProfiles" in script
    assert "loadMeetingPresets" in script
    assert "loadBrainStatus" in script
    assert "loadPromptBindings" in script
    assert "statusCard" in script
    assert "loadCapabilities" in script
    assert "validateActionDraft" in script
    assert "const current = data.conversations.find" in script
    assert "if (current && !state.symbiosisOpen) title.textContent = conversationDisplayTitle(current)" in script
    assert "/capabilities" in script
    assert "/profiles" in script
    assert "/meeting-presets" in script
    assert "/brain/status" in script
    assert "/prompt-bindings" in script
    assert "/actions/validate" in script
    assert "/context" in script
    assert "/usage/" in script
    assert "/admin/users" in script
    assert "admin-user-delete" in script
    assert "/scheduled-jobs" in script
    assert "/tasks" in script

    assert "@keyframes sentPulse" in styles
    assert "flex: 0 0 auto" in styles
    assert "-webkit-overflow-scrolling: touch" in styles
    assert "touch-action: pan-y" in styles
    assert ".panel.open" in styles
    assert "--left-panel-width" in styles
    assert "--right-panel-width" in styles
    assert "grid-template-columns: var(--left-panel-width) minmax(0, 1fr) var(--right-panel-width)" in styles
    assert 'body[data-left-open="true"]' in styles
    assert 'body[data-right-open="true"]' in styles
    assert ".confirm-panel" in styles
    assert ".confirm-actions" in styles
    assert "height: 100dvh" in styles
    assert ".upload-trigger" in styles
    assert "grid-template-columns: 42px minmax(0, 1fr) 76px" in styles
    assert ".modal-backdrop" in styles
    assert ".modal-panel" in styles
    assert "--color-surface" in styles
    assert ".right-panel-view" in styles
    assert ".right-panel-tab.active" in styles
    assert "#temporary-tools-modal .modal-panel" not in styles
    assert "rgba(24, 25, 28, 0.55)" not in styles
    assert ".scheduled-job-item" in styles
    assert ".drop-active" in styles
    assert ".detail-grid" in styles
    assert ".thought-panel" in styles
    assert ".file-card-download" in styles
    assert ".thought-line.tool" in styles
    assert ".thought-line.thought" in styles
    assert "font-family: Consolas" in styles
    assert 'body[data-chat-mode="professional"]' in styles
    assert ".message-meta-time" in styles
    assert ".message-time-outside" in styles
    assert ".markdown-body" in styles
    assert ".markdown-body pre" in styles
    assert ".admin-section" in styles
    assert ".settings-tools-modal" not in styles
    assert ".usage-list" in styles
    assert ".task-list" in styles
    assert ".status-card-list" in styles
    assert ".status-card-title" in styles
    assert ".context-summary" in styles
    assert ".capability-list" in styles
    assert ".action-validate-form" in styles
    assert ".action-validate-result" in styles
    assert ".nav-section-title" in styles
    assert "min-height: 28px" in styles

    assert "adminUserPath" in admin_tools
    assert "window.HermiPermissionsPanel" in permissions_panel
    assert "collectPermissionForm" in permissions_panel
    assert "renderPermDetailBody" in permissions_panel
    assert "permissions: changes" in permissions_panel
    assert "window.HermiScheduledJobs" in scheduled_jobs


def test_message_ui_has_identity_avatar_centered_time_and_incremental_meeting_updates():
    script = (ROOT / "web" / "app.js").read_text(encoding="utf-8")
    styles = (ROOT / "web" / "styles.css").read_text(encoding="utf-8")
    scheduled_jobs = (ROOT / "web" / "scheduled_jobs.js").read_text(encoding="utf-8")

    assert "message-avatar" in script
    assert "message-identity" in script
    assert "message-display-name" in script
    assert "message-time-divider" in script
    assert "actorForMessage" in script
    assert "step.actor" in script
    assert "syncMeetingMessages" in script
    assert "syncMeetingModeOptions" in script
    assert "step.trace" in script
    assert "formatMeetingRunStatus" in script
    assert "Token" in script
    assert "requestAnimationFrame" in script

    assert ".message-avatar" in styles
    assert ".message-identity" in styles
    assert ".message-time-divider" in styles
    assert "text-align: center" in styles
    assert 'if (!role.includes("user")) line.append(avatar)' in script
    assert 'newMeetingButton.disabled = false' in script
    assert "~会议功能测试中~" in script
    assert 'newMeetingButton.hidden = !show' not in script
    assert 'body[data-chat-mode="professional"] .message-avatar' in styles

    sync_start = script.index("function syncMeetingMessages")
    sync_end = script.index("async function pollMeetingRun", sync_start)
    sync_body = script[sync_start:sync_end]
    assert sync_body.index("renderTracePanel") < sync_body.index("appendMessageOnce(", sync_body.index("for (const step"))

    render_start = script.index("async function renderMeetingRun")
    render_end = script.index("async function pollMeetingRun", render_start)
    render_body = script[render_start:render_end]
    assert 'messageList.innerHTML = ""' not in render_body
    assert "`${label}\\n\\n${step.content}`" not in render_body
    assert "renderScheduledJobItem" in scheduled_jobs
    assert "formatScheduledJobDetail" in scheduled_jobs
    assert "deleteScheduledJob" in scheduled_jobs
    assert "adminUserList.querySelectorAll" in script
    assert "row.dataset.userId = user.user_id" in script
    assert '["friend", "guest"].includes(user.role)' in script
    assert "permission-summary" in script
    assert "quota_window" in script
    assert "permission-state-allow" in styles
    assert "permission-state-deny" in styles
    assert "permission-state-approval" in styles
    assert "max-height: 400px" not in styles
    admin_list_css = styles[styles.index("/* admin user list */"):]
    assert "overflow-y: auto" not in admin_list_css


def test_professional_user_layout_hides_user_name_and_keeps_message_centered():
    styles = (ROOT / "web" / "styles.css").read_text(encoding="utf-8")

    assert 'body[data-chat-mode="professional"] .message.user .message-content {\n  text-align: center;\n  width: 100%;' in styles
    assert 'body[data-chat-mode="professional"] .message.user .message-identity {\n  display: none;' in styles
    assert 'body[data-chat-mode="professional"] .message.user .message-time-divider {\n  border-top: 1px solid var(--line);\n  margin-top: 8px;\n  padding-top: 7px;\n  text-align: center;' in styles


def test_sidebar_uses_inline_rename_login_hiding_and_custom_placeholder_notices():
    script = (ROOT / "web" / "app.js").read_text(encoding="utf-8")
    styles = (ROOT / "web" / "styles.css").read_text(encoding="utf-8")
    html = (ROOT / "web" / "index.html").read_text(encoding="utf-8")

    assert 'id="efficiency-organization-list"' in html
    assert "共生网络" in html
    assert "演化观测站" in html
    assert "异常处理中心" in html
    assert "深空通讯舱" in html
    assert "startInlineConversationRename(conversation, item, button, actions)" in script
    assert "button.hidden = true;" in script
    assert "tokenForm.hidden = true;" in script
    assert "tokenForm.hidden = false;" in script
    assert "function showInfoNotice" in script
    assert "~会议功能测试中~" in script
    assert "~施工中ing~" in script
    assert 'body[data-role="owner"] .status[data-state="ok"]' in styles
    assert '.status[data-state="warn"]' in styles


def test_sidebar_polling_preserves_active_inline_rename_and_efficiency_items_match_conversations():
    script = (ROOT / "web" / "app.js").read_text(encoding="utf-8")
    styles = (ROOT / "web" / "styles.css").read_text(encoding="utf-8")
    html = (ROOT / "web" / "index.html").read_text(encoding="utf-8")

    assert "function hasActiveInlineConversationRename" in script
    assert "if (hasActiveInlineConversationRename()) return;" in script
    assert 'class="nav-section efficiency-section"' in html
    assert 'class="conversation-open efficiency-placeholder"' in html
    assert ".efficiency-section .nav-section-title" in styles


def test_gateway_start_script_strips_utf8_bom_from_env_keys():
    start_script = (ROOT / "scripts" / "start_hermi_gateway.ps1").read_text(encoding="utf-8-sig")
    all_script = (ROOT / "scripts" / "start_hermi_all.ps1").read_text(encoding="utf-8-sig")

    assert "TrimStart([char]0xFEFF)" in start_script
    assert "TrimStart([char]0xFEFF)" in all_script


def test_conversation_rename_restores_edit_state_before_refreshing_sidebar():
    script = (ROOT / "web" / "app.js").read_text(encoding="utf-8")

    rename_start = script.index("function startInlineConversationRename")
    rename_end = script.index("function startInlineRoomRename", rename_start)
    rename_body = script[rename_start:rename_end]
    assert rename_body.index("restore();") < rename_body.index("await loadConversations();")


def test_new_conversation_profile_picker_supports_all_local_profiles_and_locks_unavailable_ones():
    script = (ROOT / "web" / "app.js").read_text(encoding="utf-8")
    styles = (ROOT / "web" / "styles.css").read_text(encoding="utf-8")
    html = (ROOT / "web" / "index.html").read_text(encoding="utf-8")

    assert 'id="new-conversation-modal"' in html
    assert 'data-profile-id="maid"' in html
    assert 'data-profile-id="trainee"' in html
    assert 'data-profile-id="imouto"' in html
    assert "薇拉(Vera)" in html
    assert "薇达(Veda)" in html
    assert "小墨(Ember)" in html
    assert "能力六维" not in html
    assert "负责 Hermi 对话" not in html
    assert 'class="profile-portrait profile-portrait-vera"' in html
    assert 'class="profile-radar"' in html
    assert 'class="profile-brief"' in html
    assert "function openNewConversationPicker" in script
    assert "isConversationProfileAvailable" in script
    assert "newConversationConfirm.disabled = !available" in script
    assert "createNewConversation(selectedConversationProfileId)" in script
    assert "profile_id: profileId" in script
    assert ".profile-picker-panel" in styles
    assert "overflow-x: hidden;" in styles
    assert "grid-template-columns: minmax(150px, 0.62fr) minmax(0, 0.96fr) minmax(150px, 0.6fr);" in styles
    assert ".modal-panel.profile-picker-panel" in styles


def test_successful_token_login_opens_sidebar_on_desktop():
    script = (ROOT / "web" / "app.js").read_text(encoding="utf-8")

    refresh_start = script.index("async function refresh()")
    refresh_end = script.index("async function loadConversations()", refresh_start)
    refresh_body = script[refresh_start:refresh_end]
    assert 'setPanelOpen("conversations", true);' in refresh_body


def test_login_renders_conversations_before_loading_initial_messages():
    script = (ROOT / "web" / "app.js").read_text(encoding="utf-8")

    load_start = script.index("async function loadConversations()")
    load_end = script.index("function hasActiveInlineConversationRename()", load_start)
    load_body = script[load_start:load_end]
    assert load_body.index("renderProfileConversationGroups") < load_body.index("await loadMessages();")

    logout_start = script.index("function logout()")
    logout_end = script.index("meetingMode.addEventListener", logout_start)
    logout_body = script[logout_start:logout_end]
    assert 'conversationList.innerHTML = "";' not in logout_body


def test_professional_mode_uses_symmetric_full_width_message_layout():
    styles = (ROOT / "web" / "styles.css").read_text(encoding="utf-8")

    assert 'body[data-chat-mode="professional"] .message-list' in styles
    assert "padding-inline: max(22px, calc((100% - 880px) / 2));" in styles
    assert "scrollbar-gutter: stable both-edges;" in styles
    assert 'body[data-chat-mode="professional"] .thought-panel' in styles
    assert "max-width: none;" in styles


def test_profile_picker_keeps_avatar_slot_only_in_profile_choices():
    styles = (ROOT / "web" / "styles.css").read_text(encoding="utf-8")
    html = (ROOT / "web" / "index.html").read_text(encoding="utf-8")

    assert 'class="profile-portrait profile-portrait-vera"' in html
    assert "profile-avatar-slot" not in html
    assert ".profile-portrait" in styles
    assert "border-radius: 8px;" in styles


def test_stream_final_reconciles_polling_race_without_duplicate_messages_or_trace():
    script = (ROOT / "web" / "app.js").read_text(encoding="utf-8")
    message_ui = (ROOT / "web" / "message_ui.js").read_text(encoding="utf-8")
    trace_ui = (ROOT / "web" / "trace_ui.js").read_text(encoding="utf-8")
    html = (ROOT / "web" / "index.html").read_text(encoding="utf-8")

    assert 'src="/message_ui.js"' in html
    assert 'src="/trace_ui.js"' in html
    assert "reconcilePendingMessage" in message_ui
    assert "pending.remove()" in message_ui
    assert "reconcileLiveTrace" in trace_ui
    assert "live.remove()" in trace_ui
    assert "window.HermiMessageUI.reconcilePendingMessage" in script
    assert "window.HermiTraceUI.reconcileLiveTrace" in script
    assert "hasMessage" in message_ui
    assert "if (!window.HermiMessageUI.hasMessage" in script
    assert "reconcilePersistedUserMessage" in script
    assert "Number(message.created_at || 0) * 1000 < Number(inflight.startedAt || 0) - 5000" in script
    assert "appendTraceTime" in trace_ui
    assert "data-trace-time-for" in trace_ui
    assert "bindLiveTrace" in trace_ui
    assert "[data-live-trace-time]" in trace_ui
    load_start = script.index("async function loadMessages")
    load_end = script.index("async function loadActiveRun", load_start)
    load_body = script[load_start:load_end]
    assert load_body.index("reconcilePersistedUserMessage") < load_body.index("appendMessageOnce(")
    assert load_body.index("appendTraceTime") < load_body.index("renderTracePanel")
    assert "window.HermiTraceUI.reconcileLiveTrace(messageList, message.message_id)" in load_body
    final_start = script.index("const tracePanel = window.HermiTraceUI.reconcileLiveTrace")
    final_end = script.index("delete state.inflightByConversation[sendConversationId]", final_start)
    final_body = script[final_start:final_end]
    assert "appendTraceTime(messageList, assistantId" in final_body


def test_terminal_stream_state_blocks_late_trace_events_and_stale_live_panels():
    script = (ROOT / "web" / "app.js").read_text(encoding="utf-8")
    stream_start = script.index("async function sendMessageStream")
    stream_end = script.index("function renderInflightForCurrentConversation", stream_start)
    stream_body = script[stream_start:stream_end]
    inflight_start = script.index("function renderInflightForCurrentConversation")
    inflight_end = script.index("function runTrace", inflight_start)
    inflight_body = script[inflight_start:inflight_end]
    thought_start = script.index("function renderThoughtPanel")
    thought_end = script.index("function collapseThoughtPanel", thought_start)
    thought_body = script[thought_start:thought_end]

    assert "function markConversationFinalized" in script
    assert "function isConversationFinalized" in script
    assert "&& !isConversationFinalized(conversationId)" in stream_body
    assert "markConversationFinalized(conversationId);" in stream_body
    assert "if (isConversationFinalized(state.conversationId)) return;" in inflight_body
    assert "!isConversationFinalized(item.conversationId)" in thought_body
    clear_start = script.index("function clearThoughtPanel")
    clear_end = script.index("function createTracePanel", clear_start)
    assert "[data-live-trace-time]" in script[clear_start:clear_end]


def test_login_token_is_not_prefilled_and_file_denial_is_explained_before_upload():
    html = (ROOT / "web" / "index.html").read_text(encoding="utf-8")
    script = (ROOT / "web" / "app.js").read_text(encoding="utf-8")

    assert "默认 replace-with-owner-token" not in html
    assert "tokenInput.value = state.token" not in script
    assert "文件上传已被 Owner 禁止" in script
    assert "function canUploadFiles" in script


def test_gateway_startup_does_not_write_owner_token_to_console_or_runtime_info():
    script = (ROOT / "scripts" / "start_hermi_gateway.ps1").read_text(encoding="utf-8")

    assert "OWNER_TOKEN=$env:HERMI_OWNER_TOKEN" not in script
    assert "QLOS_CHANNEL_TOKEN=$env:HERMI_CHANNEL_TOKEN" not in script
    assert "QLOS_ENV=QLOS_HERMI_GATEWAY_TOKEN=$env:HERMI_CHANNEL_TOKEN" not in script
    assert 'Write-Host "Owner token: $env:HERMI_OWNER_TOKEN"' not in script
    assert 'Write-Host "Channel token for QLOS: $env:HERMI_CHANNEL_TOKEN"' not in script
    assert 'Write-Host "Owner token: configured"' in script
    assert 'Write-Host "Channel token for QLOS: configured"' in script


def test_local_secrets_are_ignored_by_version_control():
    gitignore = (ROOT / ".gitignore").read_text(encoding="utf-8")

    assert "secrets.local.env" in gitignore


def test_mobile_conversation_delete_keeps_sidebar_open():
    script = (ROOT / "web" / "app.js").read_text(encoding="utf-8")

    delete_start = script.index('remove.addEventListener("click", async (event) =>')
    delete_end = script.index("const actions = document.createElement", delete_start)
    assert "if (isCompactViewport()) closeDrawers();" not in script[delete_start:delete_end]


def test_friend_errors_other_conversation_and_job_creator_are_explicit():
    script = (ROOT / "web" / "app.js").read_text(encoding="utf-8")
    scheduled_jobs = (ROOT / "web" / "scheduled_jobs.js").read_text(encoding="utf-8")

    assert "responseErrorMessage" in script
    assert "消息额度已用完" in script
    assert "消息权限已被禁止" in script
    assert "owner_display_name" in script
    assert "window.setInterval" in script
    assert "created_by_display_name" in scheduled_jobs


def test_friend_approval_refresh_and_long_conversation_titles_keep_actions_available():
    script = (ROOT / "web" / "app.js").read_text(encoding="utf-8")
    styles = (ROOT / "web" / "styles.css").read_text(encoding="utf-8")

    refresh_start = script.index("async function refreshVisibleState")
    refresh_end = script.index("async function sendMessageStream", refresh_start)
    refresh_body = script[refresh_start:refresh_end]
    assert "await loadApprovals();" in refresh_body
    assert 'uiText("approvals",' in script
    assert "grid-template-columns: minmax(0, 1fr) auto;" in styles
    assert "position: static;" in styles


def test_account_menu_uses_basic_information_and_live_summary_data():
    html = (ROOT / "web" / "index.html").read_text(encoding="utf-8")
    script = (ROOT / "web" / "app.js").read_text(encoding="utf-8")

    assert 'id="account-settings-summary"' in html
    assert "账户设置" in html
    assert 'id="my-tools-view"' not in html
    assert 'api("/my/summary")' in script
    assert "loadMySummary" in script


def test_chat_bubbles_account_quota_menu_and_temporary_quota_request_are_explicitly_wired():
    html = (ROOT / "web" / "index.html").read_text(encoding="utf-8")
    script = (ROOT / "web" / "app.js").read_text(encoding="utf-8")
    styles = (ROOT / "web" / "styles.css").read_text(encoding="utf-8")

    assert 'id="account-quota-reset"' in html
    assert 'id="account-request-quota-button"' in html
    assert "account-quota-policy-row" in script
    assert "max-inline-size: min(680px, calc(100vw - 120px));" in styles
    assert 'padding-inline: max(22px, calc((100% - 880px) / 2));' in styles
    assert "/my/quota-requests" in script
    assert "requestTemporaryQuota" in script


def test_quota_rejection_shows_a_notice_and_account_notices_are_separate_from_guides():
    html = (ROOT / "web" / "index.html").read_text(encoding="utf-8")
    script = (ROOT / "web" / "app.js").read_text(encoding="utf-8")
    styles = (ROOT / "web" / "styles.css").read_text(encoding="utf-8")

    assert 'id="account-notice-modal"' in html
    assert "额度已用尽" in script
    assert "isQuotaSendError(error)" in script
    assert "loadAccountNotices" in script
    assert "#confirm-modal {\n  z-index: 1100;" in styles


def test_sidebar_groups_hermi_conversations_by_role_and_keeps_focus_during_approval_refresh():
    html = (ROOT / "web" / "index.html").read_text(encoding="utf-8")
    script = (ROOT / "web" / "app.js").read_text(encoding="utf-8")
    styles = (ROOT / "web" / "styles.css").read_text(encoding="utf-8")

    assert 'id="hermi-conversation-groups"' in html
    assert "initialConversationSelectionDone" in script
    assert "renderProfileConversationGroups" in script
    assert "conversationTitleWithoutProfile" in script
    assert "conversation-item-actions" in script
    assert ".conversation-item-actions" in styles
    assert ".conversation-list .conversation-open" in styles
    assert ".conversation-list .scheduled-job-open" in styles


def test_sidebar_and_trace_ui_keep_role_sections_and_stable_trace_order():
    html = (ROOT / "web" / "index.html").read_text(encoding="utf-8")
    script = (ROOT / "web" / "app.js").read_text(encoding="utf-8")
    trace_ui = (ROOT / "web" / "trace_ui.js").read_text(encoding="utf-8")
    styles = (ROOT / "web" / "styles.css").read_text(encoding="utf-8")

    assert 'id="other-conversation-section"' in html
    assert "conversationSidebarTitle" in script
    assert "otherConversationSection.hidden = !show" in script
    assert "traceDurationText" in script
    assert "reconcileLiveTrace" in script
    assert "traceStartedAt" in script
    assert "traceTimeFor" in trace_ui
    assert "margin-top" in styles[styles.index(".conversation-list"):styles.index(".nav-section")]


def test_friend_sidebar_settings_and_inline_rename_are_explicitly_supported():
    html = (ROOT / "web" / "index.html").read_text(encoding="utf-8")
    script = (ROOT / "web" / "app.js").read_text(encoding="utf-8")
    styles = (ROOT / "web" / "styles.css").read_text(encoding="utf-8")

    assert 'id="api-conversation-section"' in html
    assert "apiConversationSection.hidden = !show" in script
    assert 'uiText("professional", "Professional")' in script
    assert 'uiText("chat", "Chat")' in script
    assert "settingsToolsButton.hidden = false" in script
    assert "actionValidateForm.hidden = !show" in script
    assert "startInlineConversationRename" in script
    assert "window.prompt" not in script
    assert ".conversation-rename-input" in styles
    assert "[hidden]" in styles


def test_professional_message_layout_and_trace_reconciliation_are_race_safe():
    script = (ROOT / "web" / "app.js").read_text(encoding="utf-8")
    styles = (ROOT / "web" / "styles.css").read_text(encoding="utf-8")
    trace_ui = (ROOT / "web" / "trace_ui.js").read_text(encoding="utf-8")

    assert "messageLoadSequence" in script
    assert "if (requestSequence !== state.messageLoadSequence) return;" in script
    assert "function arrangeTraceForAssistant" in script
    trace_start = script.index("function arrangeTraceForAssistant")
    trace_end = script.index("function messageTrace", trace_start)
    trace_body = script[trace_start:trace_end]
    assert "trace-actor-label" not in trace_body
    assert "return conversationTitleWithoutProfile(conversation);" in script
    assert "data-trace-time-for" in trace_ui
    assert "querySelectorAll(\".thought-panel.live-thought-panel\")" in trace_ui
    assert "reconcileLiveTrace(messageList, message.message_id)" in script
    assert "normalizeLiveTrace" in trace_ui
    assert "function traceCompletesInflightRun" in script
    load_messages = script[script.index("async function loadMessages"):script.index("async function loadActiveRun")]
    assert "traceCompletesInflightRun(message, conversationId)" in load_messages
    assert "markConversationFinalized(conversationId);" in load_messages
    assert ".message-list" in styles
    assert "padding-inline: max(22px, calc((100% - 880px) / 2));" in styles
    assert ".message.user .message-time-divider" in styles
    assert "border-top: 1px solid var(--line)" in styles
    assert "bubble.before(time, panel);" in trace_body
    assert "messageList.append(time, panel);" in trace_body
    assert "(?:tool\\.)?(running|started|completed|failed|progress)" in script


def test_trace_order_is_mode_aware_without_a_second_actor_label():
    script = (ROOT / "web" / "app.js").read_text(encoding="utf-8")

    trace_start = script.index("function arrangeTraceForAssistant")
    trace_end = script.index("function messageTrace", trace_start)
    trace_body = script[trace_start:trace_end]

    assert "trace-actor-label" not in trace_body
    assert "bubble.before(time, panel);" in trace_body
    assert "body.before(panel);" in trace_body
    assert 'state.chatMode === "chat"' in trace_body
    assert "messageList.append(time, panel);" in trace_body

def test_profile_aware_assistant_identity_privacy_notice_and_picker_layout_are_explicit():
    script = (ROOT / "web" / "app.js").read_text(encoding="utf-8")
    html = (ROOT / "web" / "index.html").read_text(encoding="utf-8")
    styles = (ROOT / "web" / "styles.css").read_text(encoding="utf-8")

    assert "assistantActorsByConversation" in script
    assert "assistantActorForConversation" in script
    assert "state.assistantActorsByConversation[created.conversation_id]" in script
    assert "function defaultAssistantActor(conversationId = state.conversationId)" in script
    assert "body[data-chat-mode=\"professional\"] .message.user .message-identity" in styles
    professional_user_name = styles[styles.index('body[data-chat-mode="professional"] .message.user .message-identity'):]
    assert "display: none;" in professional_user_name[:220]
    assert "您的隐私已被保护，上传文件最多在服务器保存30天" in html
    assert "composer-privacy-note" in styles
    assert html.index('class="profile-brief"') < html.index('class="profile-stage"')
    assert "grid-template-columns: minmax(150px, 0.62fr) minmax(0, 0.96fr) minmax(150px, 0.6fr);" in styles
    assert ".profile-stage {\n  min-height: 250px;" in styles


def test_usage_selection_privacy_note_and_context_estimate_are_explicit():
    script = (ROOT / "web" / "app.js").read_text(encoding="utf-8")
    html = (ROOT / "web" / "index.html").read_text(encoding="utf-8")
    styles = (ROOT / "web" / "styles.css").read_text(encoding="utf-8")

    refresh_start = script.index("async function refreshVisibleState()")
    refresh_end = script.index("async function sendMessageStream", refresh_start)
    refresh_body = script[refresh_start:refresh_end]

    assert "usageLoadSequence: 0," in script
    assert "async function loadUsage(userId = state.usageUserId)" in script
    assert "const requestId = ++state.usageLoadSequence;" in script
    assert "if (requestId !== state.usageLoadSequence) return;" in script
    assert "loadUsage(state.usageUserId)" in refresh_body
    assert "function contextWindowStatus" in script
    assert "contextWindowStatus(data.context_window)" in script
    assert "未统计实时 Token" not in script

    assert 'class="composer-privacy-note"' in html
    assert 'id="composer-privacy-info"' in html
    assert 'aria-describedby="composer-privacy-tooltip"' in html
    assert 'id="composer-privacy-tooltip"' in html
    assert 'role="tooltip"' in html
    assert ".composer-privacy-note {\n  align-items: center;" in styles
    assert "justify-content: center;" in styles
    assert ".composer-privacy-info" in styles
    assert ".composer-privacy-info-wrap.is-open .composer-privacy-tooltip" in styles
    assert "function toggleComposerPrivacyTooltip" in script


def test_symbiosis_network_workspace_is_explicit_in_the_frontend():
    html = (ROOT / "web" / "index.html").read_text(encoding="utf-8")
    script = (ROOT / "web" / "app.js").read_text(encoding="utf-8")
    styles = (ROOT / "web" / "styles.css").read_text(encoding="utf-8")

    assert "共生网络" in html
    assert "演化观测站" in html
    assert "异常处理中心" in html
    assert "深空通讯舱" in html
    assert 'id="symbiosis-workspace"' in html
    assert 'id="evolution-notes-tab"' in html
    assert 'id="feature-proposals-tab"' in html
    assert 'id="evolution-note-form"' in html
    assert 'id="symbiosis-top-title"' in html
    assert 'id="feature-proposal-type"' in html
    assert 'id="feature-proposal-options"' in html
    assert 'data-note-format="bold"' in html
    assert 'id="feature-proposal-add-option"' in html
    assert "openSymbiosisWorkspace" in script
    assert "syncSymbiosisHeader" in script
    assert "proposal_type" in script
    assert "addFeatureProposalOption" in script
    assert "removeFeatureProposalOption" in script
    assert "formatEvolutionNoteSelection" in script
    assert "/symbiosis/notes" in script
    assert "/symbiosis/proposals" in script
    assert "renderMarkdown" in script
    assert ".symbiosis-workspace" in styles
    assert ".symbiosis-note-composer" in styles


def test_usage_total_reserved_capabilities_and_permission_modal_layout_are_explicit():
    html = (ROOT / "web" / "index.html").read_text(encoding="utf-8")
    script = (ROOT / "web" / "app.js").read_text(encoding="utf-8")
    permissions = (ROOT / "web" / "permissions_panel.js").read_text(encoding="utf-8")

    assert 'id="usage-total-tokens"' in html
    assert "预留能力" in script
    assert "reserved_capabilities" in script
    assert "媒体文件" in permissions
    assert "媒体单文件上限(MB)" in permissions
    assert "每日识图上限（预留）" in permissions
def test_evolution_note_editor_supports_distinct_markdown_edit_time_and_common_formats():
    html = (ROOT / "web" / "index.html").read_text(encoding="utf-8")
    script = (ROOT / "web" / "app.js").read_text(encoding="utf-8")
    styles = (ROOT / "web" / "styles.css").read_text(encoding="utf-8")

    assert 'data-note-format="ordered-list"' in html
    assert 'data-note-format="strike"' in html
    assert 'data-note-format="divider"' in html
    assert "function evolutionNoteTimestamp" in script
    assert "分钟前编辑" in script
    assert "小时前编辑" in script
    assert "天前编辑" in script
    assert ".replace(/\\*(.+?)\\*/g, \"<em>$1</em>\")" in script
    assert ".replace(/^>\\s+(.+)$/gm, \"<blockquote>$1</blockquote>\")" in script
    assert "<ol>" in script
    assert ".symbiosis-markdown h2" in styles
    assert "font-size: 21px;" in styles


def test_generated_message_attachments_refresh_in_place_and_other_conversations_cannot_rename():
    script = (ROOT / "web" / "app.js").read_text(encoding="utf-8")

    assert "function refreshMessageBubble" in script
    assert "refreshMessageBubble(existing, role, content, createdAt, attachments, actor);" in script
    assert "if (!isOtherConversation(conversation)) actions.append(rename);" in script


def test_right_panel_removes_my_tab_after_moving_account_controls_to_the_sidebar():
    html = (ROOT / "web" / "index.html").read_text(encoding="utf-8")
    script = (ROOT / "web" / "app.js").read_text(encoding="utf-8")
    styles = (ROOT / "web" / "styles.css").read_text(encoding="utf-8")

    assert 'id="my-tools-button"' not in html
    assert 'id="my-tools-view"' not in html
    assert 'id="right-panel-tab-prev"' in html
    assert 'id="right-panel-tab-next"' in html
    assert "switchRightPanelView(\"my\")" not in script
    assert ".right-panel-tab-nav" in styles
    assert ".right-panel-tab-arrow" in styles


def test_my_display_name_and_proposal_opinion_locking_are_explicit_in_the_frontend():
    html = (ROOT / "web" / "index.html").read_text(encoding="utf-8")
    script = (ROOT / "web" / "app.js").read_text(encoding="utf-8")

    assert 'api("/my/display-name"' in script
    assert "last_7_day_tokens" in script
    assert "/comment" in script
    assert "/reveal-opinions" in script
    assert "/opinions" in script
    assert "查看其他人的意见后，将不能修改本次支持、投票或评论。" in script
    context_function = script[script.index("async function loadConversationContext"):script.index("async function loadProfiles")]
    assert "data.usage?.total_tokens" not in context_function
    assert 'id="account-settings-summary"' in html
    assert 'id="account-menu-button"' in html


def test_sidebar_connection_is_status_only_and_account_menu_owns_account_actions():
    script = (ROOT / "web" / "app.js").read_text(encoding="utf-8")
    html = (ROOT / "web" / "index.html").read_text(encoding="utf-8")
    styles = (ROOT / "web" / "styles.css").read_text(encoding="utf-8")

    assert "function showConnectionNotice" not in script
    assert 'id="account-menu"' in html
    assert 'id="account-quota-button"' in html
    assert 'id="account-settings-button"' in html
    assert 'id="account-logout-button"' in html
    assert 'id="app-download-button"' in html
    assert "function renderAccountSettings" in script
    assert "function toggleAccountMenu" in script
    assert "下载 Hermi APP" in script
    assert ".account-menu" in styles
    assert 'conversation-item${conversation.conversation_id === state.conversationId ? " active" : ""}' in script
    assert ".conversation-item.active" in styles


def test_account_menu_dismisses_outside_click_and_owner_can_edit_structured_user_info():
    html = (ROOT / "web" / "index.html").read_text(encoding="utf-8")
    script = (ROOT / "web" / "app.js").read_text(encoding="utf-8")

    assert 'id="user-info-modal"' in html
    assert 'id="user-info-relationship"' in html
    assert 'id="user-info-preferences"' in html
    assert 'id="user-info-recent-focus"' in html
    assert "closeAccountMenuOnOutsideClick" in script
    assert "openUserInfoModal" in script
    assert "/profile/${encodeURIComponent(field)}" in script
    assert 'id="user-info-close"' not in html
    assert "userInfoTitle.textContent = `${user.display_name || userId}的信息`;" in script
    assert "input.value = profile[field] || \"\";" in script


def test_evolution_blueprints_and_interface_locale_are_explicitly_wired():
    html = (ROOT / "web" / "index.html").read_text(encoding="utf-8")
    script = (ROOT / "web" / "app.js").read_text(encoding="utf-8")
    styles = (ROOT / "web" / "styles.css").read_text(encoding="utf-8")

    assert 'id="evolution-blueprints-tab"' in html
    assert 'id="evolution-blueprints-view"' in html
    assert "/symbiosis/blueprints" in script
    assert 'id="account-language-button"' in html
    assert 'id="account-language-options"' in html
    assert 'src="/i18n.js"' in html
    assert 'api("/my/locale"' in script
    assert "positionAccountLanguageOptions" in script
    assert "setAccountLanguageOptionsOpen" in script
    assert "ACCOUNT_LANGUAGE_OPTIONS_CLOSE_DELAY_MS" in script
    assert "handleAccountLanguagePointerMove" in script
    assert "position: fixed;" in styles
    assert "--account-language-popover-x" in styles


def test_stream_finalization_reconciles_live_thoughts_with_the_persisted_trace():
    script = (ROOT / "web" / "app.js").read_text(encoding="utf-8")

    assert "finalizeTraceForAssistant" in script
    assert "messageCompletesInflightRun" in script
    assert "if (!panel && trace.length)" in script
    trace_complete_start = script.index("function traceCompletesInflightRun")
    trace_complete_end = script.index("function messageCompletesInflightRun", trace_complete_start)
    trace_complete_body = script[trace_complete_start:trace_complete_end]
    assert 'message?.source_channel === "hermes-api"' in trace_complete_body


def test_message_polling_does_not_replace_unchanged_message_nodes():
    script = (ROOT / "web" / "app.js").read_text(encoding="utf-8")

    assert "function messageRenderSignature" in script
    assert "existing.dataset.renderSignature === signature" in script
    assert "bubble.dataset.renderSignature = signature" in script
    assert "function traceRenderSignature" in script
    assert "panel.dataset.traceRenderSignature === signature" in script


def test_non_owner_views_place_owner_insertions_on_the_assistant_side():
    script = (ROOT / "web" / "app.js").read_text(encoding="utf-8")

    assert "function presentationRoleForMessage" in script
    assert "!state.user?.can_approve" in script
    assert "actorId !== String(state.user?.user_id || \"\")" in script
    assert "const presentationRole = presentationRoleForMessage(message);" in script


def test_professional_mode_keeps_centered_attachments_and_respects_manual_scroll():
    script = (ROOT / "web" / "app.js").read_text(encoding="utf-8")
    styles = (ROOT / "web" / "styles.css").read_text(encoding="utf-8")

    assert "max(22px, calc((100% - 880px) / 2))" in styles
    assert 'body[data-chat-mode="professional"] .message.user .attachment-grid' in styles
    assert "const followAssistant = isMessageListNearBottom();" in script
    assert "if (followAssistant) scrollMessages(true);" in script


def test_mobile_professional_messages_override_the_chat_bubble_width_limit():
    styles = (ROOT / "web" / "styles.css").read_text(encoding="utf-8")

    assert 'body[data-chat-mode="professional"] .message {\n    max-width: 100%;\n  }' in styles


def test_feature_proposals_show_author_and_allow_vote_withdrawal_before_reveal():
    script = (ROOT / "web" / "app.js").read_text(encoding="utf-8")

    assert "作者：${proposal.author_display_name" in script
    assert "作者：${note.author_display_name" in script
    assert 'method: "DELETE"' in script
    assert "/vote`, { method: \"DELETE\" }" in script


def test_polling_preserves_active_name_and_proposal_comment_edits():
    script = (ROOT / "web" / "app.js").read_text(encoding="utf-8")

    assert "mySummaryLoadSequence: 0," in script
    assert "state.mySummaryDirty" in script
    assert "if (!force && state.mySummaryDirty) return;" in script
    assert "featureProposalsList.contains(document.activeElement)" in script
    assert "profileNameList.contains(document.activeElement)" in script


def test_symbiosis_updates_and_confirmed_vote_ui_are_explicit_and_polling_safe():
    html = (ROOT / "web" / "index.html").read_text(encoding="utf-8")
    script = (ROOT / "web" / "app.js").read_text(encoding="utf-8")
    styles = (ROOT / "web" / "styles.css").read_text(encoding="utf-8")

    assert 'id="evolution-update-modal"' in html
    assert "checkEvolutionUpdates" in script
    assert "evolutionUpdateDismissedForUser" in script
    assert "showPendingEvolutionUpdateNotice" in script
    assert "hasBlockingCenterModal" in script
    assert "proposalOpinionViews" in script
    assert "/confirm-vote" in script
    assert "/comment`, { method: \"DELETE\" }" in script
    assert ".symbiosis-markdown h1 { font-size: 21px; }" in styles


def test_proposal_vote_summary_and_personal_opinion_editor_have_separate_areas():
    script = (ROOT / "web" / "app.js").read_text(encoding="utf-8")
    styles = (ROOT / "web" / "styles.css").read_text(encoding="utf-8")

    assert "article.append(meta, content, controls, summary, participation, commentEditor);" in script
    assert 'participationLabel.textContent = "查看大家的意见";' in script
    assert 'commentLabel.textContent = "我的建议";' in script
    assert ".proposal-opinion-controls" in styles
    assert ".proposal-comment-editor {" in styles
    assert ".proposal-section-label" in styles


def test_evolution_notes_expose_an_owner_pin_control():
    script = (ROOT / "web" / "app.js").read_text(encoding="utf-8")

    assert "toggleEvolutionNotePin" in script
    assert "/pin`, {" in script
    assert 'pin.textContent = note.is_pinned ? "取消置顶" : "置顶";' in script


def test_owner_management_label_and_exception_center_workspace_are_explicit():
    html = (ROOT / "web" / "index.html").read_text(encoding="utf-8")
    script = (ROOT / "web" / "app.js").read_text(encoding="utf-8")
    styles = (ROOT / "web" / "styles.css").read_text(encoding="utf-8")

    assert 'id="temporary-tools-button" class="right-panel-tab" type="button" data-i18n="management">管理</button>' in html
    assert 'id="exception-workspace"' in html
    assert 'id="exception-monitor-tab"' in html
    assert 'id="exception-archive-tab"' in html
    assert "openExceptionWorkspace" in script
    assert "setExceptionTab" in script
    assert ".exception-status-grid" in styles


def test_personal_quota_summary_shows_remaining_token_ratio_and_reset_time():
    script = (ROOT / "web" / "app.js").read_text(encoding="utf-8")

    assert "formatQuotaReset" in script
    assert "remaining_percent" in script
    assert "剩余额度" in script


def test_usage_guide_explains_both_chat_modes_and_single_capability_selection():
    html = (ROOT / "web" / "index.html").read_text(encoding="utf-8")

    assert "聊天模式" in html
    assert "专业模式" in html
    assert "能力一次只选择一项" in html


def test_japanese_catalog_covers_the_core_navigation_and_composer_controls():
    html = (ROOT / "web" / "index.html").read_text(encoding="utf-8")
    catalog = (ROOT / "web" / "i18n.js").read_text(encoding="utf-8")

    for key in (
        "new_conversation",
        "new_meeting",
        "meeting_rooms",
        "other_conversations",
        "scheduled_jobs",
        "symbiosis_network",
        "send_message",
        "send",
        "approvals",
        "settings",
        "management",
        "meeting",
    ):
        assert f"{key}:" in catalog
    assert 'data-i18n="new_conversation"' in html
    assert 'data-i18n="send"' in html
    assert 'data-i18n-placeholder="send_message"' in html


def test_japanese_catalog_covers_symbiosis_workspace_and_common_dialogs():
    html = (ROOT / "web" / "index.html").read_text(encoding="utf-8")
    catalog = (ROOT / "web" / "i18n.js").read_text(encoding="utf-8")

    for key in (
        "return_to_chat",
        "notes_format",
        "record_evolution",
        "publish",
        "support_proposal",
        "poll_proposal",
        "exception_monitor",
        "exception_archive",
        "scheduled_job",
        "usage_guide",
        "select_conversation_role",
        "permission_configuration",
    ):
        assert f"{key}:" in catalog
    assert 'data-i18n="exception_monitor"' in html
    assert 'data-i18n="usage_guide"' in html
    assert 'data-i18n="select_conversation_role"' in html

