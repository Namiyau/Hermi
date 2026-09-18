(function () {
  function traceKey(event, content) {
    return `${event || "thought"}\u0000${String(content || "").trim()}`;
  }

  function appendUniqueLine(panel, event, content, createLine) {
    const key = traceKey(event, content);
    const duplicate = Array.from(panel.querySelectorAll("[data-trace-key]"))
      .some((line) => line.dataset.traceKey === key);
    if (!content || duplicate) return false;
    const line = createLine();
    line.dataset.traceKey = key;
    panel.querySelector(".thought-lines").append(line);
    return true;
  }

  function normalizeLiveTrace(messageList) {
    const livePanels = Array.from(messageList.querySelectorAll(".thought-panel.live-thought-panel"));
    const preferred = livePanels.find((panel) => panel.dataset.traceFor) || livePanels[0] || null;
    for (const panel of livePanels) {
      if (panel !== preferred) panel.remove();
    }
    const liveTimes = Array.from(messageList.querySelectorAll("[data-live-trace-time]"));
    for (const time of liveTimes.slice(1)) time.remove();
    const liveActors = Array.from(messageList.querySelectorAll("[data-live-trace-actor]"));
    for (const actor of liveActors.slice(1)) actor.remove();
    return preferred;
  }

  function reconcileLiveTrace(messageList, messageId) {
    const live = normalizeLiveTrace(messageList);
    const historicalPanels = messageId
      ? Array.from(messageList.querySelectorAll(`[data-trace-for="${messageId}"]`))
      : [];
    const historical = historicalPanels[0] || null;
    for (const duplicate of historicalPanels.slice(1)) duplicate.remove();
    if (historical && live && historical !== live) {
      live.remove();
      return historical;
    }
    if (!live) return historical;
    live.classList.add("collapsed");
    live.classList.remove("live-thought-panel");
    if (messageId) live.dataset.traceFor = messageId;
    return live;
  }

  function bindLiveTrace(messageList, messageId) {
    const live = normalizeLiveTrace(messageList);
    const historical = messageId
      ? messageList.querySelector(`[data-trace-for="${messageId}"]`)
      : null;
    if (live && messageId) live.dataset.traceFor = messageId;
    return live || historical;
  }

  function appendTraceTime(messageList, messageId, createdAt, createTime, live = false) {
    normalizeLiveTrace(messageList);
    const selector = messageId ? `[data-trace-time-for="${messageId}"]` : "[data-live-trace-time]";
    const matching = Array.from(messageList.querySelectorAll(selector));
    const existing = matching.shift();
    for (const duplicate of matching) duplicate.remove();
    if (existing) return existing;
    const liveTime = messageId ? messageList.querySelector("[data-live-trace-time]") : null;
    if (liveTime) {
      liveTime.removeAttribute("data-live-trace-time");
      liveTime.dataset.traceTimeFor = messageId;
      return liveTime;
    }
    const time = createTime(createdAt);
    if (live) time.dataset.liveTraceTime = "true";
    else time.dataset.traceTimeFor = messageId;
    messageList.append(time);
    return time;
  }

  function syncLiveTrace(messageList, messageId) {
    return bindLiveTrace(messageList, messageId);
  }

  window.HermiTraceUI = { appendTraceTime, appendUniqueLine, bindLiveTrace, normalizeLiveTrace, reconcileLiveTrace, syncLiveTrace, traceKey };
})();
