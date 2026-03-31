// ---------------------------------------------------------------------------
// Boot
// ---------------------------------------------------------------------------
document.addEventListener("DOMContentLoaded", async () => {
  let authorized = false;
  try {
    const res = await get("/api/status");
    authorized = res.authorized;
  } catch (_) {}

  if (!authorized) {
    show("session-error");
  } else {
    showApp();
  }

  document.getElementById("channel-input")
    .addEventListener("keydown", e => { if (e.key === "Enter") addChannel(); });
});

// ---------------------------------------------------------------------------
// Main app
// ---------------------------------------------------------------------------
const THREE_HOURS_MS = 3 * 60 * 60 * 1000;

function showApp() {
  show("app");
  loadAll();

  let nextRefresh = Date.now() + THREE_HOURS_MS;

  setInterval(() => {
    loadAll();
    nextRefresh = Date.now() + THREE_HOURS_MS;
  }, THREE_HOURS_MS);

  setInterval(() => {
    const remaining = Math.max(0, nextRefresh - Date.now());
    const h = Math.floor(remaining / 3_600_000);
    const m = Math.floor((remaining % 3_600_000) / 60_000);
    const s = Math.floor((remaining % 60_000) / 1_000);
    const el = document.getElementById("next-refresh");
    if (el) el.textContent =
      `Next refresh in ${h}:${String(m).padStart(2, "0")}:${String(s).padStart(2, "0")}`;
  }, 1_000);
}

async function loadAll() {
  const [channels, summaries] = await Promise.all([
    get("/api/channels"),
    get("/api/summaries"),
  ]);
  renderChannelList(channels);
  renderSummaries(summaries);
}

// ---------------------------------------------------------------------------
// Sidebar channel list
// ---------------------------------------------------------------------------
function renderChannelList(channels) {
  const list  = document.getElementById("channel-list");
  const empty = document.getElementById("channel-empty");

  if (!channels.length) {
    list.innerHTML = "";
    show("channel-empty");
    return;
  }

  hide("channel-empty");
  list.innerHTML = channels.map(ch => `
    <li class="channel-item">
      <div class="channel-item-name">
        <span class="channel-item-title">${esc(ch.display_name || ch.username)}</span>
        <span class="channel-item-user">@${esc(ch.username)}</span>
      </div>
      <button class="btn-remove" onclick="removeChannel(${ch.id})" title="Remove">✕</button>
    </li>
  `).join("");
}

async function addChannel() {
  const input = document.getElementById("channel-input");
  const btn   = document.getElementById("add-btn");
  const channel = input.value.trim();
  setError("add-error", "");
  if (!channel) return;

  btn.disabled = true;
  btn.textContent = "…";

  const res = await post("/api/channels", { channel });

  btn.disabled = false;
  btn.textContent = "Add";

  if (res.ok) {
    input.value = "";
    loadAll();
  } else {
    setError("add-error", res.error || "Could not add channel.");
  }
}

async function removeChannel(id) {
  if (!confirm("Remove this channel and its summaries?")) return;
  await fetch("/api/channels", {
    method: "DELETE",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ id }),
  });
  loadAll();
}

// ---------------------------------------------------------------------------
// Summaries grid
// ---------------------------------------------------------------------------
function renderSummaries(summaries) {
  const grid  = document.getElementById("summaries-grid");
  const empty = document.getElementById("empty-state");

  if (!summaries.length) {
    grid.innerHTML = "";
    show("empty-state");
    return;
  }

  hide("empty-state");

  const scrollY = window.scrollY;
  grid.innerHTML = summaries.map(ch => `
    <div class="channel-card">
      <div>
        <div class="card-title">${esc(ch.display_name || ch.username)}</div>
        <div class="card-username">@${esc(ch.username)}</div>
      </div>
      <div class="card-meta">
        <span>${ch.message_count != null ? ch.message_count + " messages" : "—"}</span>
        <span>${ch.generated_at ? "Updated " + relativeTime(ch.generated_at) : "Not yet summarised"}</span>
      </div>
      <div class="card-summary ${ch.summary ? "" : "loading"}">
        ${ch.summary ? esc(ch.summary) : "Awaiting first refresh…"}
      </div>
    </div>
  `).join("");

  const times = summaries.filter(s => s.generated_at).map(s => new Date(s.generated_at));
  if (times.length) {
    const latest = new Date(Math.max(...times));
    document.getElementById("last-updated").textContent =
      "Last updated " + relativeTime(latest.toISOString());
  }

  window.scrollTo(0, scrollY);
}

// ---------------------------------------------------------------------------
// Manual refresh
// ---------------------------------------------------------------------------
async function triggerRefresh() {
  const btn = document.getElementById("refresh-btn");
  btn.disabled = true;
  btn.classList.add("spinning");
  btn.textContent = "Refreshing";
  try {
    await post("/api/refresh", {});
    await loadAll();
  } finally {
    btn.disabled = false;
    btn.classList.remove("spinning");
    btn.textContent = "Refresh Now";
  }
}

// ---------------------------------------------------------------------------
// Utilities
// ---------------------------------------------------------------------------
async function get(url) {
  const r = await fetch(url);
  return r.json();
}

async function post(url, body) {
  const r = await fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  return r.json();
}

function show(id) { document.getElementById(id)?.classList.remove("hidden"); }
function hide(id) { document.getElementById(id)?.classList.add("hidden"); }

function setError(id, msg) {
  const el = document.getElementById(id);
  if (el) el.textContent = msg;
}

function esc(str) {
  if (str == null) return "";
  return String(str)
    .replace(/&/g, "&amp;").replace(/</g, "&lt;")
    .replace(/>/g, "&gt;").replace(/"/g, "&quot;");
}

function relativeTime(isoStr) {
  const ms = Date.now() - new Date(isoStr).getTime();
  const s  = Math.floor(ms / 1000);
  if (s < 60)    return "just now";
  if (s < 3600)  return `${Math.floor(s / 60)}m ago`;
  if (s < 86400) return `${Math.floor(s / 3600)}h ago`;
  return `${Math.floor(s / 86400)}d ago`;
}
