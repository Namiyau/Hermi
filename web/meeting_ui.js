(function () {
  function runStatus(run, steps) {
    const labels = { running: "会议进行中", paused: "会议已停止，可恢复", completed: "会议已完成", failed: "会议运行失败", cancelled: "会议已取消" };
    const usage = (steps || []).reduce((total, step) => {
      try {
        const item = JSON.parse(step.usage_json || "{}");
        total.input += Number(item.input_tokens || 0);
        total.output += Number(item.output_tokens || 0);
        total.all += Number(item.total_tokens || 0);
      } catch {}
      return total;
    }, { input: 0, output: 0, all: 0 });
    const base = labels[run.status] || run.status;
    if (!usage.all) return base;
    const warning = usage.input >= 50000 ? " · 上下文偏高" : "";
    return `${base} · Token ${usage.all.toLocaleString()}（输入 ${usage.input.toLocaleString()} / 输出 ${usage.output.toLocaleString()}）${warning}`;
  }
  function syncRunButtons(run, controls) {
    controls.stop.hidden = run.status !== "running";
    controls.resume.hidden = run.status !== "paused";
    controls.cancel.hidden = !["running", "paused"].includes(run.status);
  }
  window.HermiMeetingUI = { runStatus, syncRunButtons };
})();
