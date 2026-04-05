let currentDraft = null;
let currentRunId = null;
let currentAppendRequest = null;
let eventSource = null;
let currentDetail = null;

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
  document.getElementById(id).textContent = typeof value === "string" ? value : pretty(value);
}

function setValue(id, value) {
  document.getElementById(id).value = value || "";
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
  const data = await wrap("draftBox", async () => await api("/api/compiler/draft", { method: "POST", body: JSON.stringify(draftPayload(interaction)) }));
  if (!data) return;
  currentDraft = data.missionDraft;
  setText("draftBox", currentDraft);
}

async function refineDraft(interaction) {
  const data = await wrap("draftBox", async () => await api("/api/compiler/refine", { method: "POST", body: JSON.stringify(draftPayload(interaction)) }));
  if (!data) return;
  currentDraft = data.missionDraft;
  setText("draftBox", data);
  setValue("compiledPromptBox", data.compiledPrompt || "");
}

async function finalizePrompt() {
  if (!currentDraft) await buildDraft("initial_compile");
  if (!currentDraft) return;
  const data = await wrap("draftBox", async () => await api("/api/compiler/finalize-prompt", {
    method: "POST",
    body: JSON.stringify({ draft: currentDraft, packVersion: document.getElementById("packVersion").value }),
  }));
  if (data) setValue("compiledPromptBox", data.compiledPrompt || "");
}

async function launchRun() {
  const prompt = document.getElementById("compiledPromptBox").value || document.getElementById("taskInput").value;
  const data = await wrap("runSummaryBox", async () => await api("/api/runs", { method: "POST", body: JSON.stringify({ prompt }) }));
  await refreshRuns();
  if (data && data.runId) await selectRun(data.runId);
}

async function refreshRuns() {
  const data = await wrap(null, async () => await api("/api/runs"));
  const box = document.getElementById("runsList");
  box.innerHTML = "";
  for (const item of (data && data.runs) || []) {
    const li = document.createElement("li");
    li.className = "run-item";
    li.textContent = `${item.runId} | ${item.state} | ${item.phase} | pending:${item.operatorPendingCount || 0}`;
    li.onclick = () => selectRun(item.runId);
    box.appendChild(li);
  }
}

async function selectRun(runId) {
  currentRunId = runId;
  if (eventSource) eventSource.close();
  await refreshCurrentRun();
  eventSource = new EventSource(`/api/runs/${encodeURIComponent(runId)}/stream`);
  eventSource.onmessage = (event) => renderRunDetail(JSON.parse(event.data));
}

function renderRunDetail(data) {
  currentDetail = data;
  setText("runSummaryBox", data.status || {});
  setText("planBox", data.plan || "");
  setText("logBox", (data.logTail || []).join("\n"));
  renderOperatorTasks();
}

function renderOperatorTasks() {
  const tbody = document.getElementById("operatorTasksBody");
  tbody.innerHTML = "";
  const filter = document.getElementById("taskFilter").value;
  const tasks = (currentDetail && currentDetail.operatorTasks) || [];
  for (const task of tasks) {
    if (filter !== "all" && task.status !== filter) continue;
    const tr = document.createElement("tr");
    tr.innerHTML = `<td>${task.title || ""}</td><td>${task.type || ""}</td><td>${task.status || ""}</td><td>${task.priority || ""}</td><td>${task.resultSummary || task.statusReason || ""}</td>`;
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
  await wrap("runSummaryBox", async () => await api(`/api/runs/${encodeURIComponent(currentRunId)}/actions/reconcile`, { method: "POST", body: "{}" }));
  await refreshCurrentRun();
}

async function verifyCurrent() {
  if (!currentRunId) return;
  await wrap("runSummaryBox", async () => await api(`/api/runs/${encodeURIComponent(currentRunId)}/actions/verify`, { method: "POST", body: "{}" }));
  await refreshCurrentRun();
}

async function resumeCurrent() {
  if (!currentRunId) return;
  await wrap("runSummaryBox", async () => await api(`/api/runs/${encodeURIComponent(currentRunId)}/actions/resume`, { method: "POST", body: "{}" }));
  await refreshCurrentRun();
}

async function finalizeCurrent(status) {
  if (!currentRunId) return;
  const headline = prompt(`请输入 ${status} 的 headline`, `${status} via web beta`);
  if (!headline) return;
  await wrap("runSummaryBox", async () => await api(`/api/runs/${encodeURIComponent(currentRunId)}/actions/finalize`, {
    method: "POST",
    body: JSON.stringify({ status, headline }),
  }));
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
  const data = await wrap("appendBox", async () => await api("/api/compiler/refine", { method: "POST", body: JSON.stringify(payload) }));
  if (!data) return;
  currentAppendRequest = data.operatorRequest;
  setText("appendBox", data);
}

async function submitAppendTask() {
  if (!currentRunId) {
    alert("请先选择 run");
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
  await wrap("appendBox", async () => await api(`/api/runs/${encodeURIComponent(currentRunId)}/inbox`, { method: "POST", body: JSON.stringify(payload) }));
  currentAppendRequest = null;
  await refreshCurrentRun();
}

refreshDoctor();
refreshRuns();
