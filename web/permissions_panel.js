(function () {
  const PERMISSION_DEFS = {
    chat: { label: "对话权限", desc: "能否发送消息对话", type: "tristate" },
    external_tools: { label: "外部工具", desc: "只读联网检索与在线研究；不包含本机、QQ 或定时任务", type: "tristate" },
    cron: { label: "创建定时任务", desc: "能否创建 cron/reminder", type: "tristate" },
    approve: { label: "审批权限", desc: "审批他人操作", type: "owner_only" },
    remote_control: { label: "远程控制", desc: "操控系统功能", type: "owner_only" },
    view_all_conversations: { label: "查看所有会话", desc: "看到所有用户的对话", type: "owner_only" },
    admin_users: { label: "管理用户", desc: "增删改账号", type: "owner_only" },
    manage_scheduled: { label: "管理定时任务", desc: "编辑/删除定时任务", type: "tristate" },
    prompt_cards: { label: "管理提示卡片", desc: "暂缓，仅 Owner 可用", type: "owner_only" },
    media: { label: "媒体文件", desc: "是否允许接收或上传媒体文件", type: "tristate" },
    admin_config: { label: "系统配置", desc: "改系统设置", type: "owner_only" },
    high_risk: { label: "高风险操作", desc: "rm -rf/格式化/修改系统等", type: "owner_only" },
    quota_token_limit: { label: "Token 额度", desc: "每个额度窗口最多可使用的总 Token；-1 表示不限", type: "number" },
    file_size_limit_mb: { label: "文件大小上限(MB)", desc: "单个上传文件大小", type: "number" },
    media_max_size_mb: { label: "媒体单文件上限(MB)", desc: "QLOS-Lite 附件限制；0 表示不限", type: "media_number", subkey: "max_size_mb" },
    media_daily_vision_count: { label: "每日识图上限（预留）", desc: "识图能力接入后按此额度限制；-1 表示不限", type: "media_number", subkey: "daily_vision_count" },
    quota_window_minutes: { label: "额度时间窗口(分钟)", desc: "默认 1440=24 小时，可手动填写", type: "number" },
  };

  const TRISTATE_OPTIONS = [
    { value: "allow", label: "允许" },
    { value: "deny", label: "禁止" },
    { value: "approval", label: "实时审批" },
  ];

  let api = null;
  let afterSave = async () => {};
  let currentUserId = null;
  let modal = null;
  let title = null;
  let body = null;

  function init(options) {
    api = options.api;
    afterSave = options.afterSave || afterSave;
    modal = document.querySelector("#perm-detail-modal");
    title = document.querySelector("#perm-detail-title");
    body = document.querySelector("#perm-detail-body");
    document.querySelector("#perm-detail-close").addEventListener("click", close);
    document.querySelector("#perm-detail-cancel").addEventListener("click", close);
    document.querySelector("#perm-detail-save").addEventListener("click", save);
    modal.addEventListener("click", (event) => {
      if (event.target === modal) close();
    });
  }

  async function open(userId) {
    currentUserId = userId;
    try {
      const userData = await api(window.HermiAdminTools.adminUserPath(userId));
      title.textContent = `权限配置：${userData.display_name || userId}`;
      renderPermDetailBody(userData);
      modal.hidden = false;
    } catch (error) {
      console.error(error);
      alert(`加载用户权限失败：${error.message}`);
    }
  }

  function close() {
    modal.hidden = true;
    currentUserId = null;
  }

  async function save() {
    if (!currentUserId) return;
    const changes = collectPermissionForm();
    try {
      await api(window.HermiAdminTools.adminUserPath(currentUserId), {
        method: "PATCH",
        body: JSON.stringify({ permissions: changes }),
      });
      close();
      await afterSave();
    } catch (error) {
      alert(`保存失败：${error.message}`);
    }
  }

  function renderPermDetailBody(userData) {
    const permissions = permissionMap(userData.effective_permissions || userData.permissions);
    const categories = [
      { label: "基础类", keys: ["chat", "external_tools", "cron", "approve", "remote_control"] },
      { label: "管理类", keys: ["view_all_conversations", "admin_users", "manage_scheduled", "prompt_cards", "media", "admin_config"] },
      { label: "QQ侧", keys: ["high_risk"] },
      { label: "额度类（Owner 手动填写）", keys: ["quota_token_limit", "file_size_limit_mb", "media_max_size_mb", "media_daily_vision_count", "quota_window_minutes"] },
    ];
    body.innerHTML = categories.map((category) => {
      const items = category.keys.map((key) => {
        const definition = PERMISSION_DEFS[key];
        const current = definition?.type === "media_number" ? permissions.media : permissions[key];
        return renderPermItem(key, definition, current);
      }).join("");
      return `<div class="perm-category"><h3>${category.label}</h3><div class="perm-items">${items}</div></div>`;
    }).join("");
  }

  function renderPermItem(key, definition, current) {
    let control = "";
    if (definition.type === "tristate") {
      control = renderModeSelect(key, current || "deny");
    } else if (definition.type === "owner_only") {
      control = '<span class="perm-badge owner-only">仅 Owner</span>';
    } else if (definition.type === "media_number") {
      const media = current && typeof current === "object" ? current : {};
      const value = media[definition.subkey] ?? (definition.subkey === "daily_vision_count" ? -1 : 0);
      control = `<input type="number" class="perm-number" data-key="media" data-subkey="${definition.subkey}" value="${value}" min="-1" />`;
    } else if (definition.type === "number") {
      const value = current !== undefined ? current : 0;
      const minimum = key === "quota_token_limit" ? "-1" : "0";
      control = `<input type="number" class="perm-number" data-key="${key}" value="${value}" min="${minimum}" />`;
    }
    return `<div class="perm-item" data-perm-key="${key}"><label>${definition.label}</label><span class="perm-desc">${definition.desc}</span>${control}</div>`;
  }

  function renderModeSelect(key, value) {
    const options = TRISTATE_OPTIONS.map((option) => {
      const selected = option.value === value ? "selected" : "";
      return `<option value="${option.value}" ${selected}>${option.label}</option>`;
    }).join("");
    return `<select class="perm-select" data-key="${key}">${options}</select>`;
  }

  function permissionMap(value) {
    if (!value) return {};
    if (typeof value === "object") return value;
    try {
      const parsed = JSON.parse(value);
      return parsed && typeof parsed === "object" ? parsed : {};
    } catch {
      return {};
    }
  }

  function collectPermissionForm() {
    const permissions = {};
    body.querySelectorAll(".perm-item[data-perm-key]").forEach((item) => {
      const key = item.dataset.permKey;
      const definition = PERMISSION_DEFS[key];
      if (!definition || definition.type === "owner_only") return;
      if (definition.type === "number" || definition.type === "media_number") {
        if (definition.type === "media_number") return;
        const value = parseInt(item.querySelector("input.perm-number")?.value || "0", 10);
        permissions[key] = key === "quota_token_limit"
          ? (Number.isFinite(value) ? Math.max(-1, value) : 0)
          : Math.max(0, value || 0);
        return;
      }
      const select = item.querySelector("select.perm-select");
      if (definition.type === "tristate") {
        permissions[key] = select?.value || "deny";
        return;
      }
      permissions[key] = select?.value || "deny";
    });
    const mediaSelect = body.querySelector('select.perm-select[data-key="media"]');
    if (mediaSelect) {
      const maxSize = parseInt(body.querySelector('input[data-key="media"][data-subkey="max_size_mb"]')?.value || "0", 10) || 0;
      const visionCount = parseInt(body.querySelector('input[data-key="media"][data-subkey="daily_vision_count"]')?.value || "-1", 10);
      permissions.media = {
        mode: mediaSelect.value || "deny",
        max_size_mb: Math.max(0, maxSize),
        daily_vision_count: Number.isFinite(visionCount) ? Math.max(-1, visionCount) : -1,
      };
    }
    return permissions;
  }

  window.HermiPermissionsPanel = { init, open };
})();
