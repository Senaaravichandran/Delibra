"use strict";

const state = { models: [], currentDebateId: null, polling: false };
const terminalStatuses = new Set(["completed", "partial", "failed"]);
const $ = (selector) => document.querySelector(selector);

document.addEventListener("DOMContentLoaded", () => {
  bindEvents();
  void Promise.allSettled([loadHealth(), loadModels(), loadStats(), loadHistory()]);
});

function bindEvents() {
  $("#question").addEventListener("input", updateCharacterCount);
  $("#debate-form").addEventListener("submit", startDebate);
  $("#refresh-history").addEventListener("click", loadHistory);
  document.querySelectorAll("[data-prompt]").forEach((button) => {
    button.addEventListener("click", () => {
      $("#question").value = button.dataset.prompt;
      updateCharacterCount();
      $("#question").focus();
    });
  });
  $("#export-markdown").addEventListener("click", () => exportCurrent("markdown"));
  $("#export-json").addEventListener("click", () => exportCurrent("json"));
}

async function api(path, options = {}) {
  const accessKey = sessionStorage.getItem("verdictforge-api-key");
  const response = await fetch(`/api/v1${path}`, {
    headers: { "Content-Type": "application/json", ...(accessKey ? { "X-API-Key": accessKey } : {}), ...options.headers },
    ...options,
  });
  if (!response.ok) {
    let message = `Request failed (${response.status})`;
    try {
      const payload = await response.json();
      message = typeof payload.detail === "string" ? payload.detail : message;
    } catch { /* The fallback already explains the failure. */ }
    throw new Error(message);
  }
  return response.json();
}

async function loadHealth() {
  const badge = $("#system-status");
  try {
    const health = await api("/health");
    badge.className = `status-pill ${health.status === "ok" ? "online" : "degraded"}`;
    badge.lastElementChild.textContent = health.status === "ok" ? "Systems ready" : "Needs configuration";
    $("#stat-models").textContent = health.available_models;
    $("#api-key-field").hidden = !health.api_key_required;
  } catch {
    badge.className = "status-pill degraded";
    badge.lastElementChild.textContent = "Offline";
  }
}

async function loadModels() {
  try {
    state.models = await api("/models");
    const picker = $("#model-picker");
    picker.replaceChildren(...state.models.map(modelOption));
  } catch (error) {
    showFormError(error.message);
  }
}

function modelOption(model, index) {
  const label = document.createElement("label");
  label.className = "model-option";
  label.style.setProperty("--model-color", model.accent);
  const checkbox = document.createElement("input");
  checkbox.type = "checkbox";
  checkbox.name = "models";
  checkbox.value = model.id;
  checkbox.checked = model.available;
  checkbox.disabled = !model.available;
  const glyph = document.createElement("span");
  glyph.className = "model-glyph";
  glyph.textContent = String(index + 1).padStart(2, "0");
  const copy = document.createElement("span");
  copy.className = "model-copy";
  const name = document.createElement("b");
  name.textContent = model.display_name;
  const description = document.createElement("small");
  description.textContent = model.available ? model.description : "Provider key not configured";
  copy.append(name, description);
  const provider = document.createElement("span");
  provider.className = "provider-tag";
  provider.textContent = model.provider;
  label.append(checkbox, glyph, copy, provider);
  return label;
}

async function loadStats() {
  try {
    const stats = await api("/stats");
    $("#stat-debates").textContent = compactNumber(stats.total_debates);
    $("#stat-completed").textContent = compactNumber(stats.completed_debates);
    $("#stat-duration").textContent = formatDuration(stats.average_duration_ms);
    renderLeaderboard(stats.ratings);
  } catch { /* Stats remain as graceful placeholders. */ }
}

function renderLeaderboard(ratings) {
  const list = $("#leaderboard-list");
  if (!ratings.length) {
    list.innerHTML = '<div class="history-empty">No ratings yet.</div>';
    return;
  }
  list.replaceChildren(...ratings.map((rating, index) => {
    const model = modelById(rating.model_id);
    const row = document.createElement("div");
    row.className = "rank-row";
    row.innerHTML = `<span class="rank-number">${String(index + 1).padStart(2, "0")}</span>
      <span class="rank-model"><b>${escapeHtml(model.display_name)}</b><small>${rating.wins} wins · ${rating.debates} debates</small></span>
      <span class="rank-score">${Math.round(rating.rating)} <small>ELO</small></span>`;
    return row;
  }));
}

async function startDebate(event) {
  event.preventDefault();
  if (state.polling) return;
  const question = $("#question").value.trim();
  const modelIds = [...document.querySelectorAll('input[name="models"]:checked')].map(input => input.value);
  if (question.length < 1) return showFormError("Enter a question for the council.");
  if (modelIds.length < 2) return showFormError("Select at least two available models.");
  if (!$("#api-key-field").hidden) {
    const accessKey = $("#api-key").value.trim();
    if (!accessKey) return showFormError("Enter the server access key for this deployment.");
    sessionStorage.setItem("verdictforge-api-key", accessKey);
  }
  hideFormError();
  setBusy(true);
  showProgress("queued");
  try {
    const debate = await api("/debates", {
      method: "POST",
      body: JSON.stringify({
        question,
        model_ids: modelIds,
        mode: document.querySelector('input[name="mode"]:checked').value,
      }),
    });
    state.currentDebateId = debate.id;
    await pollDebate(debate.id);
  } catch (error) {
    renderFailure(error.message);
  } finally {
    state.polling = false;
    setBusy(false);
  }
}

async function pollDebate(id) {
  state.polling = true;
  const deadline = Date.now() + 12 * 60 * 1000;
  while (Date.now() < deadline) {
    const debate = await api(`/debates/${id}`);
    if (terminalStatuses.has(debate.status)) {
      renderDebate(debate);
      await Promise.allSettled([loadStats(), loadHistory()]);
      return;
    }
    showProgress(debate.status);
    await delay(document.hidden ? 2500 : 1300);
  }
  throw new Error("The debate is still running. Find it in the archive and open it later.");
}

function showProgress(status) {
  const section = $("#results");
  section.hidden = false;
  const active = status === "running" ? 2 : 1;
  $("#result-content").innerHTML = `<div class="progress-card"><i class="progress-line"></i>
    <h3>${status === "running" ? "The council is deliberating…" : "Preparing the arena…"}</h3>
    <p>Parallel answers, blind synthesis, and structured evaluation may take a minute.</p>
    <div class="progress-steps">${[1,2,3].map(step => `<span class="${step <= active ? "active" : ""}"></span>`).join("")}</div></div>`;
  section.scrollIntoView({ behavior: "smooth", block: "start" });
}

function renderDebate(debate) {
  state.currentDebateId = debate.id;
  const container = $("#result-content");
  if (debate.status === "failed" || !debate.judgment) {
    renderFailure(debate.error || "The debate did not reach a verdict.");
    return;
  }
  const cards = debate.judgment.rankings.map((entry, index) => {
    const model = modelById(entry.model_id);
    return `<article class="verdict-card ${index === 0 ? "winner" : ""}">
      <span class="verdict-rank">${index === 0 ? "WINNER" : `RANK ${entry.rank}`}</span>
      <h3>${escapeHtml(model.display_name)}</h3><div class="verdict-score">${formatScore(entry.score)} <small>/ 100</small></div>
      <p>${escapeHtml(entry.verdict)}</p><div class="evidence">
      <div><b>Strength</b>${escapeHtml(entry.strengths[0] || "—")}</div>
      <div><b>Watch</b>${escapeHtml(entry.weaknesses[0] || "—")}</div></div></article>`;
  }).join("");
  const answers = debate.answers.map(answer => {
    const model = modelById(answer.model_id);
    return `<details class="answer-card"><summary><b>${escapeHtml(model.display_name)}</b>
      <span class="answer-meta">${formatDuration(answer.latency_ms)} · ${answer.usage.output_tokens ?? "—"} tokens</span></summary>
      <div class="answer-body">${escapeHtml(answer.content || answer.error || "No response")}</div></details>`;
  }).join("");
  container.innerHTML = `<div class="verdict-grid">${cards}</div>
    <div class="judge-reasoning"><b>Judge's reasoning</b><br>${escapeHtml(debate.judgment.reasoning)}</div>
    <h3 class="answers-heading">Inspect every answer</h3>${answers}`;
  $("#results").hidden = false;
  $("#results").scrollIntoView({ behavior: "smooth", block: "start" });
}

function renderFailure(message) {
  $("#results").hidden = false;
  $("#result-content").innerHTML = `<div class="error-card"><b>No verdict was forged.</b><br>${escapeHtml(message)}</div>`;
}

async function loadHistory() {
  const list = $("#history-list");
  try {
    const page = await api("/debates?limit=12");
    if (!page.items.length) {
      list.innerHTML = '<div class="history-empty">Your first forged verdict will appear here.</div>';
      return;
    }
    list.replaceChildren(...page.items.map(historyRow));
  } catch {
    list.innerHTML = '<div class="history-empty">The archive is unavailable.</div>';
  }
}

function historyRow(item) {
  const button = document.createElement("button");
  button.type = "button";
  button.className = "history-row";
  const winner = item.winner_model_id ? modelById(item.winner_model_id).display_name : "Pending";
  button.innerHTML = `<span class="history-status ${item.status === "failed" ? "failed" : ""}">${escapeHtml(item.status)}</span>
    <span class="history-question">${escapeHtml(item.question)}</span>
    <span class="history-winner">Winner · <b>${escapeHtml(winner)}</b></span>
    <span class="history-time">${relativeTime(item.created_at)}</span>`;
  button.addEventListener("click", async () => {
    try {
      const debate = await api(`/debates/${item.id}`);
      if (terminalStatuses.has(debate.status)) renderDebate(debate);
      else { state.currentDebateId = item.id; showProgress(debate.status); await pollDebate(item.id); }
    } catch (error) { renderFailure(error.message); }
  });
  return button;
}

function exportCurrent(format) {
  if (state.currentDebateId) window.location.assign(`/api/v1/debates/${state.currentDebateId}/export?format=${format}`);
}

function setBusy(busy) {
  const button = $("#forge-button");
  button.disabled = busy;
  button.querySelector("span").textContent = busy ? "Forging…" : "Forge the verdict";
}
function showFormError(message) { const node = $("#form-error"); node.textContent = message; node.hidden = false; }
function hideFormError() { $("#form-error").hidden = true; }
function updateCharacterCount() { $("#character-count").textContent = `${$("#question").value.length.toLocaleString()} / 12,000`; }
function modelById(id) { return state.models.find(model => model.id === id) || { id, display_name: id, provider: "model", accent: "#9298a8" }; }
function compactNumber(value) { return Intl.NumberFormat("en", { notation: value > 999 ? "compact" : "standard" }).format(value); }
function formatDuration(ms) { if (!ms) return "0s"; return ms < 1000 ? `${ms}ms` : `${(ms / 1000).toFixed(ms < 10000 ? 1 : 0)}s`; }
function formatScore(value) { return Number(value).toFixed(Number(value) % 1 ? 1 : 0); }
function delay(ms) { return new Promise(resolve => setTimeout(resolve, ms)); }
function relativeTime(iso) { const seconds = Math.round((new Date(iso).getTime() - Date.now()) / 1000); const abs = Math.abs(seconds); const [amount, unit] = abs < 60 ? [seconds, "second"] : abs < 3600 ? [Math.round(seconds / 60), "minute"] : abs < 86400 ? [Math.round(seconds / 3600), "hour"] : [Math.round(seconds / 86400), "day"]; return new Intl.RelativeTimeFormat("en", { numeric: "auto" }).format(amount, unit); }
function escapeHtml(value) { const node = document.createElement("div"); node.textContent = String(value ?? ""); return node.innerHTML; }
