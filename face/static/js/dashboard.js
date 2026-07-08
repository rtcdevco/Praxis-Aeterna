const POLL_INTERVAL_MS = 5000;

function setText(id, text) {
  const el = document.getElementById(id);
  if (el) el.textContent = text;
}

function updateClock() {
  setText("clock", new Date().toLocaleTimeString());
}

async function fetchJSON(url) {
  const response = await fetch(url);
  if (!response.ok) throw new Error(`${url} -> ${response.status}`);
  return response.json();
}

async function refreshMetrics() {
  const metrics = await fetchJSON("/api/metrics");
  setText("metric-vault-nodes", `Vault Nodes: ${metrics.vault_nodes}`);
  setText("metric-graph-links", `Graph Links: ${metrics.graph_links}`);
  setText("metric-daily-notes", `Daily Notes: ${metrics.daily_notes}`);
  const usage = metrics.context_usage;
  setText(
    "metric-context-usage",
    `Context Usage: ${usage.used_tokens}/${usage.budget_tokens} (${Math.round(usage.ratio * 100)}%)`
  );
  setText("metric-active-skill", `Active Skill: ${metrics.active_skill ?? "none"}`);
  return metrics.active_skill;
}

async function refreshSkills(activeSkill) {
  const data = await fetchJSON("/api/skills");
  const list = document.getElementById("skills-list");
  if (!list) return;
  list.innerHTML = "";
  for (const name of data.skills) {
    const item = document.createElement("li");
    item.textContent = name;
    if (name === activeSkill) item.classList.add("active");
    list.appendChild(item);
  }
}

async function refreshVoice() {
  const status = await fetchJSON("/api/voice/status");
  setText("voice-state", `state: ${status.state}`);
  setText("voice-stt", `STT: ${status.stt}`);
  setText("voice-tts", `TTS: ${status.tts}`);
}

async function refreshGraph() {
  const data = await fetchJSON("/api/graph");
  if (window.renderGraph) window.renderGraph(data);
}

async function refreshAll() {
  try {
    const activeSkill = await refreshMetrics();
    await Promise.all([refreshSkills(activeSkill), refreshVoice(), refreshGraph()]);
  } catch (err) {
    console.error("dashboard refresh failed", err);
  }
}

updateClock();
setInterval(updateClock, 1000);
refreshAll();
setInterval(refreshAll, POLL_INTERVAL_MS);
