(function () {
  let api = null;
  let confirmAction = null;
  let getUser = () => null;
  let afterChange = async () => {};
  let activeJobId = null;
  let list = null;
  let modal = null;
  let detail = null;

  function init(options) {
    api = options.api;
    confirmAction = options.confirmAction;
    getUser = options.getUser;
    afterChange = options.afterChange || afterChange;
    list = document.querySelector("#scheduled-job-list");
    modal = document.querySelector("#scheduled-job-detail-modal");
    detail = document.querySelector("#scheduled-job-detail");
    document.querySelector("#scheduled-job-detail-close").addEventListener("click", close);
    document.querySelector("#scheduled-job-delete").addEventListener("click", deleteActiveScheduledJob);
    modal.addEventListener("click", (event) => {
      if (event.target === modal) close();
    });
  }

  async function load() {
    if (!getUser()) {
      list.innerHTML = '<p class="nav-empty">登录后显示</p>';
      return;
    }
    let data;
    try {
      data = await api("/scheduled-jobs");
    } catch {
      list.innerHTML = '<p class="nav-empty">无权限</p>';
      return;
    }
    list.innerHTML = "";
    const jobs = data.scheduled_jobs.slice(0, 10);
    if (!jobs.length) {
      list.innerHTML = '<p class="nav-empty">暂无</p>';
      return;
    }
    for (const job of jobs) list.append(renderScheduledJobItem(job));
  }

  function renderScheduledJobItem(job) {
    const item = document.createElement("article");
    item.className = "scheduled-job-item";
    const open = document.createElement("button");
    open.type = "button";
    open.className = "scheduled-job-open";
    const creator = job.created_by_display_name || job.created_by || "未知用户";
    const completion = job.status === "completed" ? "已完成" : job.status === "failed" ? "执行失败" : "未完成";
    const taskName = job.summary || "未命名任务";
    open.textContent = getUser()?.can_approve
      ? `（${creator}）+${completion}+${taskName}`
      : `${completion}+${taskName}`;
    open.addEventListener("click", () => showScheduledJobDetail(job.job_id));
    const remove = document.createElement("button");
    remove.type = "button";
    remove.className = "scheduled-job-delete scheduled-job-delete-inline";
    remove.textContent = "×";
    remove.setAttribute("aria-label", `删除定时任务 ${job.summary || job.job_id}`);
    remove.addEventListener("click", async (event) => {
      event.stopPropagation();
      await deleteScheduledJob(job.job_id);
    });
    item.append(open);
    if (canDeleteScheduledJob(job)) item.append(remove);
    return item;
  }

  function canDeleteScheduledJob(job) {
    const user = getUser() || {};
    if (user.can_approve || user.role === "owner") return true;
    return Boolean(user.user_id && job.created_by === user.user_id);
  }

  async function showScheduledJobDetail(jobId) {
    const job = await api(`/scheduled-jobs/${jobId}`);
    activeJobId = jobId;
    detail.innerHTML = formatScheduledJobDetail(job);
    modal.hidden = false;
  }

  function close() {
    modal.hidden = true;
    activeJobId = null;
    detail.innerHTML = "";
  }

  function formatScheduledJobDetail(job) {
    const target = safeJson(job.target_json);
    const payload = safeJson(job.payload_json);
    const rows = [
      ["任务", job.summary || "未命名"],
      ["状态", job.status || "未知"],
      ["类型", job.kind || "未知"],
      ["计划", job.schedule || "未设置"],
      ["创建者", job.created_by_display_name || job.created_by || "未知"],
      ["任务 ID", job.task_id || "无"],
      ["上次运行", job.last_run_at ? new Date(job.last_run_at * 1000).toLocaleString() : "尚未运行"],
      ["投递", Array.isArray(target.delivery) ? target.delivery.join("、") : target.delivery || "Hermi"],
      ["QQ 目标", target.qq ? JSON.stringify(target.qq) : "无"],
      ["执行内容", payload.content || payload.prompt || "无"],
    ];
    return rows.map(([label, value]) => `<div class="detail-label">${escapeHtml(label)}</div><div class="detail-value">${escapeHtml(value)}</div>`).join("");
  }

  function safeJson(value) {
    try {
      const parsed = JSON.parse(value || "{}");
      return parsed && typeof parsed === "object" ? parsed : {};
    } catch {
      return {};
    }
  }

  function escapeHtml(value) {
    return String(value || "").replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;").replace(/'/g, "&#39;");
  }

  async function deleteActiveScheduledJob() {
    if (!activeJobId) return;
    await deleteScheduledJob(activeJobId);
    close();
  }

  async function deleteScheduledJob(jobId) {
    if (!(await confirmAction({ title: "删除定时任务", message: "删除这个定时任务记录？" }))) return;
    await api(`/scheduled-jobs/${jobId}`, { method: "DELETE" });
    if (activeJobId === jobId) close();
    await Promise.all([load(), afterChange()]);
  }

  window.HermiScheduledJobs = { init, load };
})();
