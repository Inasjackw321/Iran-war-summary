"use strict";

// ---------------------------------------------------------------------------
// Boot
// ---------------------------------------------------------------------------
document.addEventListener("DOMContentLoaded", async () => {
  const { authorized } = await api("GET", "/api/status");
  authorized ? showApp() : showModal("auth-modal");

  el("ch-input").addEventListener("keydown", e => {
    if (e.key === "Enter") addChannel();
  });
});

// ---------------------------------------------------------------------------
// Auth modal
// ---------------------------------------------------------------------------
async function sendCode() {
  const phone = el("auth-phone").value.trim();
  setErr("err-phone", "");
  if (!phone) return setErr("err-phone", "Enter your phone number.");
  const res = await api("POST", "/api/auth/send-code", { phone });
  if (res.ok) {
    hide("step-phone"); show("step-code");
  } else {
    setErr("err-phone", res.error || "Failed to send code.");
  }
}

async function verifyCode() {
  const code     = el("auth-code").value.trim();
  const password = el("auth-2fa").value || null;
  setErr("err-code", "");
  if (!code) return setErr("err-code", "Enter the code.");
  const res = await api("POST", "/api/auth/verify", { code, password });
  if (res.ok) {
    hide("auth-modal"); showApp();
  } else if ((res.error || "").toLowerCase().includes("2fa") ||
             (res.error || "").toLowerCase().includes("password")) {
    show("step-2fa");
    setErr("err-code", "2FA password required — enter it above.");
  } else {
    setErr("err-code", res.error || "Verification failed.");
  }
}

function resetAuth() {
  hide("step-code"); show("step-phone");
  setErr("err-phone", ""); setErr("err-code", "");
  el("auth-code").value = ""; el("auth-2fa").value = "";
}

// ---------------------------------------------------------------------------
// Main app
// ---------------------------------------------------------------------------
function showApp() {
  show("app");
  loadAll();
  setInterval(loadAll, 30_000);   // poll for new summaries every 30 s
}

async function loadAll() {
  const [channels, summaries] = await Promise.all([
    api("GET", "/api/channels"),
    api("GET", "/api/summaries"),
  ]);
  renderSidebar(channels);
  renderGrid(summaries);
}

// ---------------------------------------------------------------------------
// Sidebar
// ---------------------------------------------------------------------------
function renderSidebar(channels) {
  const list = el("ch-list");
  if (!channels.length) {
    list.innerHTML = "";
    show("ch-empty");
    return;
  }
  hide("ch-empty");
  list.innerHTML = channels.map(ch => `
    <li class="ch-item">
      <div class="ch-item-text">
        <div class="ch-name">${esc(ch.display_name || ch.username)}</div>
        <div class="ch-user">@${esc(ch.username)}</div>
      </div>
      <button class="btn-del" onclick="removeChannel(${ch.id})" title="Remove">✕</button>
    </li>
  `).join("");
}

async function addChannel() {
  const input   = el("ch-input");
  const btn     = el("btn-add");
  const channel = input.value.trim();
  setErr("err-add", "");
  if (!channel) return;
  btn.disabled = true; btn.textContent = "…";
  const res = await api("POST", "/api/channels", { channel });
  btn.disabled = false; btn.textContent = "Add";
  if (res.ok) { input.value = ""; loadAll(); }
  else setErr("err-add", res.error || "Could not add channel.");
}

async function removeChannel(id) {
  if (!confirm("Remove this channel?")) return;
  await api("DELETE", `/api/channels/${id}`);
  loadAll();
}

// ---------------------------------------------------------------------------
// Summary grid
// ---------------------------------------------------------------------------
function renderGrid(summaries) {
  const grid = el("grid");
  if (!summaries.length) {
    grid.innerHTML = "";
    show("main-empty");
    return;
  }
  hide("main-empty");

  const scrollY = window.scrollY;
  grid.innerHTML = summaries.map(ch => `
    <div class="card">
      <div>
        <div class="card-name">${esc(ch.display_name || ch.username)}</div>
        <div class="card-user">@${esc(ch.username)}</div>
      </div>
      <div class="card-meta">
        <span>${ch.message_count != null ? ch.message_count + " messages" : "—"}</span>
        <span>${ch.generated_at ? "Updated " + ago(ch.generated_at) : "Not summarised yet"}</span>
      </div>
      <div class="card-body${ch.summary ? "" : " pending"}">
        ${ch.summary ? esc(ch.summary) : "Awaiting first refresh…"}
      </div>
    </div>
  `).join("");

  // Update header timestamp
  const times = summaries.filter(s => s.generated_at).map(s => +new Date(s.generated_at + "Z"));
  if (times.length) {
    el("last-updated").textContent = "Last updated " + ago(
      new Date(Math.max(...times)).toISOString().replace("Z", "")
    );
  }
  window.scrollTo(0, scrollY);
}

// ---------------------------------------------------------------------------
// Refresh button
// ---------------------------------------------------------------------------
async function triggerRefresh() {
  const btn = el("btn-refresh");
  btn.disabled = true; btn.classList.add("spinning"); btn.textContent = "Refreshing";
  try {
    await api("POST", "/api/refresh");
    await loadAll();
  } finally {
    btn.disabled = false; btn.classList.remove("spinning"); btn.textContent = "Refresh Now";
  }
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------
async function api(method, url, body) {
  const opts = { method, headers: {} };
  if (body) { opts.headers["Content-Type"] = "application/json"; opts.body = JSON.stringify(body); }
  const r = await fetch(url, opts);
  return r.json();
}

const el  = id => document.getElementById(id);
const show = id => el(id)?.classList.remove("hidden");
const hide = id => el(id)?.classList.add("hidden");
const showModal = id => { show(id); };

function setErr(id, msg) { const e = el(id); if (e) e.textContent = msg; }

function esc(s) {
  return String(s ?? "")
    .replace(/&/g,"&amp;").replace(/</g,"&lt;")
    .replace(/>/g,"&gt;").replace(/"/g,"&quot;");
}

function ago(iso) {
  const s = Math.floor((Date.now() - new Date(iso.endsWith("Z") ? iso : iso + "Z")) / 1000);
  if (s < 60)    return "just now";
  if (s < 3600)  return `${Math.floor(s/60)}m ago`;
  if (s < 86400) return `${Math.floor(s/3600)}h ago`;
  return `${Math.floor(s/86400)}d ago`;
}
