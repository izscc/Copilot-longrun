let currentDraft = null;
let currentRunId = null;
let currentAppendRequest = null;
let currentDetail = null;
let currentWorkspace = null;
let currentTab = "home";
let eventSource = null;

const TAB_META = {
  home: { title: "任务编排", subtitle: "先优化任务，再启动 LongRun 长跑。" },
  runs: { title: "运行监控", subtitle: "查看状态、日志、计划和收敛动作。" },
  operator: { title: "追加任务", subtitle: "在检查点插入新的任务请求并追踪状态。" },
  ai: { title: "AI 配置", subtitle: "仅用于 Web Prompt Compiler 的优化助手。" },
  doctor: { title: "环境检测", subtitle: "检查 Copilot CLI、helper 与工作区环境。" },
};

function pretty(value) {
  return typeof value === "string" ? value : JSON.stringify(value, null, 2);
}

async function api(url, options = {}) {
  const response = await fetch(url, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });
  const text = await response.text();
  const data = text ? JSON.parse(text) : {};
  if (!response.ok) {
    throw new Error(data.detail || data.error || `HTTP ${response.status}`);
  }
  return data;
}

function setText(id, value) {
  const node = document.getElementById(id);
  if (node) node.textContent = typeof value === "string" ? value : pretty(value);
}

function setValue(id, value) {
  const node = document.getElementById(id);
  if (node) node.value = value || "";
}

function safeMessage(error) {
  return error && error.message ? error.message : String(error || "unknown error");
}

async function wrap(targetId, fn) {
  try {
    const result = await fn();
    if (targetId && result !== undefined) setText(targetId, result);
    return result;
  } catch (error) {
    if (targetId) setText(targetId, { ok: false, error: safeMessage(error) });
    console.error(error);
    return null;
  }
}

function switchTab(tabName) {
  currentTab = tabName;
  for (const [key, meta] of Object.entries(TAB_META)) {
    const panel = document.getElementById(`tab-${key}`);
    const nav = document.getElementById(`nav-${key}`);
    if (panel) panel.classList.toggle("active", key === tabName);
    if (nav) nav.classList.toggle("active", key === tabName);
    if (key === tabName) {
      setText("tabTitle", meta.title);
      setText("tabSubtitle", meta.subtitle);
    }
  }
}

function resetCurrentRunView() {
  currentRunId = null;
  currentDetail = null;
  if (eventSource) {
    eventSource.close();
    eventSource = null;
  }
  setText("runSummaryBox", "请选择左侧一个 run");
  setText("planBox", "暂无计划");
  setText("logBox", "暂无日志");
  setText("missionBox", "暂无内容");
  renderOperatorTasks();
}

function updateWorkspaceUi(data) {
  currentWorkspace = data.activeWorkspace;
  setValue("workspaceInput", data.activeWorkspace);
  setText("workspaceBadge", data.activeWorkspace || "未设置工作区");
  setText("workspaceHint", `当前工作区：${data.activeWorkspace}`);

  const list = document.getElementById("workspaceSuggestions");
  if (list) {
    list.innerHTML = "";
    for (const item of data.recentWorkspaces || []) {
      const option = document.createElement("option");
      option.value = item;
      list.appendChild(option);
    }
  }
}

async function loadWorkspaceInfo() {
  const data = await wrap(null, async () => await api("/api/workspace"));
  if (data) updateWorkspaceUi(data);
}

async function applyWorkspace() {
  const workspace = document.getElementById("workspaceInput").value.trim();
  if (!workspace) {
    alert("请先输入工作区路径");
    return;
  }
  const data = await wrap("doctorBox", async () =>
    await api("/api/workspace", {
      method: "POST",
      body: JSON.stringify({ workspace }),
    })
  );
  if (!data) return;
  updateWorkspaceUi(data);
  resetCurrentRunView();
  await refreshDoctor();
  await refreshRuns();
  switchTab("home");
}

async function refreshDoctor() {
  await wrap("doctorBox", async () => await api("/api/doctor"));
}

async function saveAiProfile() {
  const payload = {
    name: document.getElementById("aiName").value,
    baseUrl: document.getElementById("aiBaseUrl").value,
    apiKey: document.getElementById("aiKey").value,
    model: document.getElementById("aiModel").value,
    setDefault: document.getElementById("aiDefault").checked,
  };
  await wrap("aiBox", async () => await api("/api/ai/profiles", { method: "POST", body: JSON.stringify(payload) }));
}

async function testAiProfile() {
  const payload = {
    name: document.getElementById("aiName").value,
    baseUrl: document.getElementById("aiBaseUrl").value,
    apiKey: document.getElementById("aiKey").value,
    model: document.getElementById("aiModel").value,
    setDefault: document.getElementById("aiDefault").checked,
  };
  await wrap("aiBox", async () => await api("/api/ai/test", { method: "POST", body: JSON.stringify(payload) }));
}

async function loadModels() {
  const name = document.getElementById("aiName").value || "default";
  const data = await wrap("aiBox", async () => await api(`/api/ai/models?profile=${encodeURIComponent(name)}`));
  if (data && data.models && data.models[0] && !document.getElementById("aiModel").value) {
    document.getElementById("aiModel").value = data.models[0];
  }
}

function draftPayload(interaction) {
  return {
    text: document.getElementById("taskInput").value,
    previousDraft: currentDraft,
    interaction,
    aiProfile: document.getElementById("aiName").value || "default",
    packVersion: document.getElementById("packVersion").value,
  };
}

async function buildDraft(interaction) {
  const data = await wrap("draftBox", async () =>
    await api("/api/compiler/draft", { method: "POST", body: JSON.stringify(draftPayload(interaction)) })
  );
  if (!data) return;
  currentDraft = data.missionDraft;
  setText("draftBox", currentDraft);
}

async function refineDraft(interaction) {
  const data = await wrap("draftBox", async () =>
    await api("/api/compiler/refine", { method: "POST", body: JSON.stringify(draftPayload(interaction)) })
  );
  if (!data) return;
  currentDraft = data.missionDraft;
  setText("draftBox", data);
  setValue("compiledPromptBox", data.compiledPrompt || "");
}

async function finalizePrompt() {
  if (!currentDraft) await buildDraft("initial_compile");
  if (!currentDraft) return;
  const data = await wrap("draftBox", async () =>
    await api("/api/compiler/finalize-prompt", {
      method: "POST",
      body: JSON.stringify({ draft: currentDraft, packVersion: document.getElementById("packVersion").value }),
    })
  );
  if (data) setValue("compiledPromptBox", data.compiledPrompt || "");
}

async function launchRun() {
  const prompt = document.getElementById("compiledPromptBox").value || document.getElementById("taskInput").value;
  const data = await wrap("runSummaryBox", async () =>
    await api("/api/runs", { method: "POST", body: JSON.stringify({ prompt }) })
  );
  await refreshRuns();
  if (data && data.runId) {
    switchTab("runs");
    await selectRun(data.runId);
  }
}

async function refreshRuns() {
  const data = await wrap(null, async () => await api("/api/runs"));
  const box = document.getElementById("runsList");
  if (!box) return;
  box.innerHTML = "";
  for (const item of (data && data.runs) || []) {
    const li = document.createElement("li");
    li.className = "run-item";
    if (item.runId === currentRunId) li.classList.add("active");
    li.innerHTML = `
      <div><strong>${item.runId}</strong></div>
      <div>${item.state} · ${item.phase}</div>
      <div>${item.summary || "无摘要"}</div>
      <div>待处理追加：${item.operatorPendingCount || 0}</div>
    `;
    li.onclick = () => {
      switchTab("runs");
      selectRun(item.runId);
    };
    box.appendChild(li);
  }
}

async function selectRun(runId) {
  currentRunId = runId;
  if (eventSource) eventSource.close();
  await refreshCurrentRun();
  await refreshRuns();
  eventSource = new EventSource(`/api/runs/${encodeURIComponent(runId)}/stream`);
  eventSource.onmessage = (event) => {
    const data = JSON.parse(event.data);
    renderRunDetail(data);
  };
}

function renderRunDetail(data) {
  currentDetail = data;
  setText("runSummaryBox", data.status || {});
  setText("planBox", data.plan || "暂无计划");
  setText("logBox", (data.logTail || []).join("\n") || "暂无日志");
  const missionText = [data.mission || "", "", data.completion || ""].join("\n").trim();
  setText("missionBox", missionText || "暂无内容");
  renderOperatorTasks();
}

function renderOperatorTasks() {
  const tbody = document.getElementById("operatorTasksBody");
  if (!tbody) return;
  tbody.innerHTML = "";
  const filter = document.getElementById("taskFilter").value;
  const tasks = (currentDetail && currentDetail.operatorTasks) || [];
  for (const task of tasks) {
    if (filter !== "all" && task.status !== filter) continue;
    const tr = document.createElement("tr");
    tr.innerHTML = `
      <td>${task.title || ""}</td>
      <td>${task.type || ""}</td>
      <td>${task.status || ""}</td>
      <td>${task.priority || ""}</td>
      <td>${task.resultSummary || task.statusReason || ""}</td>
    `;
    tbody.appendChild(tr);
  }
}

async function refreshCurrentRun() {
  if (!currentRunId) return;
  const data = await wrap("runSummaryBox", async () => await api(`/api/runs/${encodeURIComponent(currentRunId)}`));
  if (data) renderRunDetail(data);
}

async function reconcileCurrent() {
  if (!currentRunId) return;
  await wrap("runSummaryBox", async () =>
    await api(`/api/runs/${encodeURIComponent(currentRunId)}/actions/reconcile`, { method: "POST", body: "{}" })
  );
  await refreshCurrentRun();
}

async function verifyCurrent() {
  if (!currentRunId) return;
  await wrap("runSummaryBox", async () =>
    await api(`/api/runs/${encodeURIComponent(currentRunId)}/actions/verify`, { method: "POST", body: "{}" })
  );
  await refreshCurrentRun();
}

async function resumeCurrent() {
  if (!currentRunId) return;
  await wrap("runSummaryBox", async () =>
    await api(`/api/runs/${encodeURIComponent(currentRunId)}/actions/resume`, { method: "POST", body: "{}" })
  );
  await refreshCurrentRun();
}

async function finalizeCurrent(status) {
  if (!currentRunId) return;
  const headline = prompt(`请输入 ${status} 的 headline`, `${status} via web beta`);
  if (!headline) return;
  await wrap("runSummaryBox", async () =>
    await api(`/api/runs/${encodeURIComponent(currentRunId)}/actions/finalize`, {
      method: "POST",
      body: JSON.stringify({ status, headline }),
    })
  );
  await refreshCurrentRun();
}

async function refineAppendTask() {
  const payload = {
    text: document.getElementById("appendInput").value,
    previousDraft: currentDraft,
    interaction: "append_task",
    aiProfile: document.getElementById("aiName").value || "default",
    packVersion: document.getElementById("packVersion").value,
  };
  const data = await wrap("appendBox", async () =>
    await api("/api/compiler/refine", { method: "POST", body: JSON.stringify(payload) })
  );
  if (!data) return;
  currentAppendRequest = data.operatorRequest;
  setText("appendBox", data);
}

async function submitAppendTask() {
  if (!currentRunId) {
    alert("请先在左侧选择一个 run");
    return;
  }
  if (!currentAppendRequest) await refineAppendTask();
  const payload = currentAppendRequest || {
    type: "append_task",
    title: "追加任务",
    rawText: document.getElementById("appendInput").value,
    normalizedText: document.getElementById("appendInput").value,
    priority: "normal",
    linkedDeliverables: [],
    linkedArtifacts: [],
    linkedWorkstream: null,
  };
  await wrap("appendBox", async () =>
    await api(`/api/runs/${encodeURIComponent(currentRunId)}/inbox`, { method: "POST", body: JSON.stringify(payload) })
  );
  currentAppendRequest = null;
  await refreshCurrentRun();
  switchTab("operator");
}

async function initPage() {
  await loadWorkspaceInfo();
  await refreshDoctor();
  await refreshRuns();
  switchTab("home");
}

initPage();
