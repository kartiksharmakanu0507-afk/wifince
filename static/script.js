/**
 * script.js — WIFINCE Teacher Dashboard
 * Handles: live clock, session start, ARP polling, present/absent DOM updates,
 *          disconnect, export, copy link.
 */

"use strict";

// ─── STATE ────────────────────────────────────────────────────────────────────
let sessionId     = null;
let pollInterval  = null;
let prevPresentIds = new Set();   // track which students were already in present list

// ─── CLOCK ────────────────────────────────────────────────────────────────────
const DAYS   = ["SUN","MON","TUE","WED","THU","FRI","SAT"];
const MONTHS = ["JAN","FEB","MAR","APR","MAY","JUN","JUL","AUG","SEP","OCT","NOV","DEC"];

function updateClock() {
  const now = new Date();
  const d   = `${DAYS[now.getDay()]} ${String(now.getDate()).padStart(2,"0")} ${MONTHS[now.getMonth()]} ${now.getFullYear()}`;
  const t   = `${pad(now.getHours())}:${pad(now.getMinutes())}:${pad(now.getSeconds())}`;
  setText("clock-date", d);
  setText("clock-time", t);
}
setInterval(updateClock, 1000);
updateClock();

// ─── HELPERS ──────────────────────────────────────────────────────────────────
function pad(n)          { return String(n).padStart(2, "0"); }
function setText(id, v)  { const el = document.getElementById(id); if (el) el.textContent = v; }
function show(id)        { const el = document.getElementById(id); if (el) el.style.display = ""; }
function showFlex(id)    { const el = document.getElementById(id); if (el) el.style.display = "flex"; }
function showGrid(id)    { const el = document.getElementById(id); if (el) el.style.display = "grid"; }
function hide(id)        { const el = document.getElementById(id); if (el) el.style.display = "none"; }

function showToast(msg, type = "") {
  const t = document.getElementById("toast");
  t.textContent = msg;
  t.className   = `toast show ${type ? "t" + type : ""}`;
  setTimeout(() => { t.className = "toast"; }, 3200);
}

// ─── STOP SESSION ─────────────────────────────────────────────────────────────
async function stopSession() {
  if (!sessionId) return;
  const res = await fetch("/api/session/stop", { method: "POST" });
  if (res.ok) {
    clearInterval(pollInterval);
    sessionId = null;
    document.getElementById("start-btn").textContent = "▶ START SESSION";
    document.getElementById("start-btn").style.borderColor = "";
    document.getElementById("start-btn").style.color = "";
    document.getElementById("start-btn").disabled = false;
    document.getElementById("stop-btn").style.display = "none";
    document.getElementById("start-btn").style.display = "";
    showToast("Session stopped", "");
  }
}

// ─── START SESSION ────────────────────────────────────────────────────────────
async function startSession() {
  const branch   = document.getElementById("branch").value;
  const semester = parseInt(document.getElementById("semester").value);
  const section  = document.getElementById("section").value;

  const btn    = document.getElementById("start-btn");
  btn.textContent = "INITIALIZING...";
  btn.disabled    = true;

  try {
    const res  = await fetch("/api/session/start", {
      method:  "POST",
      headers: { "Content-Type": "application/json" },
      body:    JSON.stringify({ branch, section, semester }),
    });
    if (!res.ok) throw new Error("Server error");
    const data = await res.json();

    sessionId = data.session_id;

    // Show session info badge
    setText("active-session-id", sessionId);
    setText("session-datetime", `${data.date}  ·  ${data.time}`);
    show("session-info");

    // Show all live sections
    showFlex("stats-bar");
    show("prog-wrap");
    showGrid("main-panel");
    showFlex("bbar");

    // Build student link
    const host = window.location.hostname;
    const port = window.location.port ? ":" + window.location.port : "";
    setText("student-link", `http://${host}${port}/student?session=${sessionId}`);

    // Update button to active state
    btn.textContent       = "✓  SESSION ACTIVE";
    btn.style.borderColor = "#34d399";
    btn.style.color       = "#34d399";
    btn.style.display     = "none";
    document.getElementById("stop-btn").style.display = "";

    // Begin polling
    if (pollInterval) clearInterval(pollInterval);
    pollInterval = setInterval(fetchLiveData, 3000);
    fetchLiveData();

    showToast(`Session ${sessionId} started!`, "suc");

  } catch (err) {
    console.error(err);
    btn.textContent = "START SESSION";
    btn.disabled    = false;
    showToast("Failed to start session", "err");
  }
}

// ─── FETCH LIVE DATA ──────────────────────────────────────────────────────────
async function fetchLiveData() {
  if (!sessionId) return;
  try {
    const res  = await fetch(`/api/session/${sessionId}/live`);
    if (!res.ok) throw new Error("Poll failed");
    const data = await res.json();

    updateStats(data);
    updatePresentList(data.present);
    updateAbsentList(data.absent);
  } catch (err) {
    console.error("Poll error:", err);
  }
}

// ─── UPDATE STATS ─────────────────────────────────────────────────────────────
function updateStats(data) {
  const total   = data.total;
  const present = data.present.length;
  const absent  = data.absent.length;
  const pct     = total > 0 ? Math.round((present / total) * 100) : 0;

  animNum("stat-total",   total);
  animNum("stat-present", present);
  animNum("stat-absent",  absent);
  setText("stat-pct", pct + "%");
  setText("ph-present-count", present);
  setText("ph-absent-count",  absent);

  const bar = document.getElementById("prog-fill");
  if (bar) bar.style.width = pct + "%";
  const lbl = document.getElementById("prog-pct-lbl");
  if (lbl) lbl.textContent = `${pct}% ATTENDANCE RATE`;
}

function animNum(id, target) {
  const el = document.getElementById(id);
  if (!el) return;
  const cur = parseInt(el.textContent) || 0;
  if (cur !== target) {
    el.textContent = target;
    el.classList.add("new-row");
    setTimeout(() => el.classList.remove("new-row"), 1400);
  }
}

// ─── UPDATE PRESENT LIST ──────────────────────────────────────────────────────
function updatePresentList(students) {
  const list = document.getElementById("present-list");
  if (!list) return;

  if (students.length === 0) {
    list.innerHTML = `<div class="empty-msg">Waiting for WiFi connections…</div>`;
    prevPresentIds = new Set();
    return;
  }

  const currentIds = new Set(students.map(s => s.id));
  const newIds     = [...currentIds].filter(id => !prevPresentIds.has(id));

  list.innerHTML = students.map(s => `
    <div class="srow grow ${newIds.includes(s.id) ? "new-row" : ""}" data-id="${s.id}">
      <span class="roll">${s.roll}</span>
      <span class="sname">${s.name}</span>
      <span class="stime">${s.marked_at || "--:--"}</span>
      <button class="btn-disc" onclick="disconnectStudent(${s.id})" title="Mark Absent">✕</button>
    </div>
  `).join("");

  prevPresentIds = currentIds;
}

// ─── UPDATE ABSENT LIST ───────────────────────────────────────────────────────
function updateAbsentList(students) {
  const list = document.getElementById("absent-list");
  if (!list) return;

  if (students.length === 0) {
    list.innerHTML = `<div class="empty-msg">All students present ✓</div>`;
    return;
  }

  list.innerHTML = students.map(s => `
    <div class="srow arow">
      <span class="roll">${s.roll}</span>
      <span class="sname">${s.name}</span>
    </div>
  `).join("");
}

// ─── DISCONNECT STUDENT ───────────────────────────────────────────────────────
async function disconnectStudent(studentId) {
  if (!sessionId) return;
  try {
    const res = await fetch(`/api/disconnect/${studentId}`, {
      method:  "POST",
      headers: { "Content-Type": "application/json" },
      body:    JSON.stringify({ session_id: sessionId }),
    });
    if (res.ok) {
      showToast("Marked absent", "");
      fetchLiveData();
    }
  } catch (err) {
    showToast("Failed to disconnect", "err");
  }
}

// ─── COPY STUDENT LINK ────────────────────────────────────────────────────────
function copyLink() {
  const url = document.getElementById("student-link")?.textContent;
  if (!url) return;
  navigator.clipboard.writeText(url)
    .then(()  => showToast("Link copied!", "suc"))
    .catch(()  => showToast("Copy manually from the URL bar", ""));
}

// ─── EXPORT ───────────────────────────────────────────────────────────────────
function exportCSV() {
  if (!sessionId) { showToast("No active session", "err"); return; }
  window.open(`/api/session/${sessionId}/export/csv`, "_blank");
}

function exportTXT() {
  if (!sessionId) { showToast("No active session", "err"); return; }
  window.open(`/api/session/${sessionId}/export/txt`, "_blank");
}
