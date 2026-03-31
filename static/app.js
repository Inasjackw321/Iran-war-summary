// ---------------------------------------------------------------------------
// State
// ---------------------------------------------------------------------------
let pollTimer = null;

// ---------------------------------------------------------------------------
// Boot
// ---------------------------------------------------------------------------
document.addEventListener("DOMContentLoaded", async () => {
  const { authorized } = await get("/api/status");
  if (authorized) {
    showApp();
  } else {
    showAuthModal();
  }
});

// ---------------------------------------------------------------------------
// Auth flow
// ---------------------------------------------------------------------------
function showAuthModal() {
  show("auth-modal");
  // Pre-fill phone from a meta tag if present (we won't expose the real number)
  const phoneInput = document.getElementById("auth-phone");
  if (phoneInput && !phoneInput.value) phoneInput.value = "";
}

async function sendCode() {
  const phone = document.getElementById("auth-phone").value.trim();
  setError("auth-phone-error", "");
  const res = await post("/api/auth/send-code", { phone });
  if (res.ok) {
    hide("auth-step-phone");
    show("auth-step-code");
  } else {
    setError("auth-phone-error", res.error || "Failed to send code.");
  }
}

async function verifyCode() {
  const code     = document.getElementById("auth-code").value.trim();
  const password = document.getElementById("auth-password").value || null;
  setError("auth-code-error", "");
  const res = await post("/api/auth/verify", { code, password });
  if (res.ok) {
    hide("auth-modal");
    showApp();
  } else if (res.error && res.error.toLowerCase().includes("password")) {
    // 2FA needed
    show("auth-2fa-row");
    setError("auth-code-error", "2FA password required — enter it above.");
  } else {
    setError("auth-code-error", res.error || "Verification failed.");
  }
}

// ---------------------------------------------------------------------------
// Main app
// ---------------------------------------------------------------------------
function showApp() {
  show("app");
  loadSummaries();
  // Auto-poll every 30 seconds to pick up background refresh results
  pollTimer = setInterval(loadSummaries, 30_000);
}

async function loadSummaries() {
  const summaries = await get("/api/summaries");
  renderSummaries(summaries);
}

function renderSummaries(summaries) {
  const grid  = document.getElementById("summaries-grid");
  const empty = document.getElementById("empty-state");

  if (!summaries.length) {
    grid.innerHTML = "";
    show("empty-state");
    return;
  }

  hide("empty-state");

  // Preserve scroll position
  const scrollY = window.scrollY;

  grid.innerHTML = summaries.map(ch => `
    <div class="channel-card" id="card-${ch.id}">
      <div class="card-header">
        <div>
          <div class="card-title">${esc(ch.display_name || ch.username)}</div>
          <div class="card-username">@${esc(ch.username)}</div>
        </div>
        <button class="card-remove" onclick="removeChannel(${ch.id})">Remove</button>
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

  // Update last-updated label
  const times = summaries.filter(s => s.generated_at).map(s => new Date(s.generated_at + "Z"));
  if (times.length) {
    const latest = new Date(Math.max(...times));
    document.getElementById("last-updated").textContent =
      "Last updated " + relativeTime(latest.toISOString().replace("Z", ""));
  }

  window.scrollTo(0, scrollY);
}

// ---------------------------------------------------------------------------
// Channel management
// ---------------------------------------------------------------------------
function toggleAddChannel() {
  const panel = document.getElementById("add-channel-panel");
  panel.classList.toggle("hidden");
  if (!panel.classList.contains("hidden")) {
    document.getElementById("channel-input").focus();
  }
}

async function addChannel() {
  const input = document.getElementById("channel-input");
  const channel = input.value.trim();
  setError("add-error", "");
  if (!channel) return;

  const res = await post("/api/channels", { channel });
  if (res.ok) {
    input.value = "";
    hide("add-channel-panel");
    loadSummaries();
  } else {
    setError("add-error", res.error || "Could not add channel.");
  }
}

// Allow Enter key in channel input
document.addEventListener("DOMContentLoaded", () => {
  const input = document.getElementById("channel-input");
  if (input) input.addEventListener("keydown", e => { if (e.key === "Enter") addChannel(); });
});

async function removeChannel(id) {
  if (!confirm("Remove this channel and its summaries?")) return;
  await del(`/api/channels/${id}`);
  loadSummaries();
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
    await loadSummaries();
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

async function del(url) {
  return fetch(url, { method: "DELETE" });
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
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

function relativeTime(isoStr) {
  const ms = Date.now() - new Date(isoStr + (isoStr.endsWith("Z") ? "" : "Z")).getTime();
  const s  = Math.floor(ms / 1000);
  if (s < 60)  return "just now";
  if (s < 3600) return `${Math.floor(s / 60)}m ago`;
  if (s < 86400) return `${Math.floor(s / 3600)}h ago`;
  return `${Math.floor(s / 86400)}d ago`;
}
