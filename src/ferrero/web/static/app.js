"use strict";

const $ = (sel) => document.querySelector(sel);
const params = new URLSearchParams(location.search);
const state = { conversationId: null, caseId: params.get("case"), busy: false, users: [], msgSeq: 0 };

function store(key, value) {
  try { if (value === undefined) return localStorage.getItem(key); localStorage.setItem(key, value); } catch { return null; }
  return null;
}

async function api(path, options = {}) {
  const res = await fetch(path, { headers: { "Content-Type": "application/json" }, ...options });
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    const err = new Error(typeof body.detail === "string" ? body.detail : res.statusText);
    err.status = res.status;
    throw err;
  }
  return res;
}

const escapeHtml = (s) => String(s).replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
const fmtDate = (iso) => new Date(iso + "T00:00:00").toLocaleDateString("en-GB", { day: "numeric", month: "short", year: "numeric" });

// ---------- minimal, safe Markdown (input is escaped first) ----------
function inline(s) {
  return s.replace(/`([^`]+)`/g, "<code>$1</code>").replace(/\*\*([^*]+)\*\*/g, "<strong>$1</strong>");
}
function renderMarkdown(escaped) {
  const lines = escaped.split(/\n/);
  const out = [];
  let list = null, para = [];
  const flushPara = () => { if (para.length) { out.push(`<p dir="auto">${inline(para.join("<br>"))}</p>`); para = []; } };
  const flushList = () => { if (list) { out.push(`<${list.tag}>${list.items.map((i) => `<li dir="auto">${inline(i)}</li>`).join("")}</${list.tag}>`); list = null; } };
  for (let i = 0; i < lines.length; i++) {
    const line = lines[i];
    if (/^\s*\|.*\|\s*$/.test(line) && i + 1 < lines.length && /^\s*\|[\s:|-]+\|\s*$/.test(lines[i + 1])) {
      flushPara(); flushList();
      const cells = (l) => l.trim().replace(/^\||\|$/g, "").split("|").map((c) => inline(c.trim()));
      const head = cells(line);
      const rows = [];
      i += 2;
      while (i < lines.length && /^\s*\|.*\|\s*$/.test(lines[i])) rows.push(cells(lines[i++]));
      i--;
      out.push(`<table dir="auto"><thead><tr>${head.map((h) => `<th>${h}</th>`).join("")}</tr></thead><tbody>` +
        rows.map((r) => `<tr>${r.map((c) => `<td>${c}</td>`).join("")}</tr>`).join("") + "</tbody></table>");
      continue;
    }
    const bullet = line.match(/^\s*(?:[-*•])\s+(.*)$/);
    const numbered = line.match(/^\s*\d+[.)]\s+(.*)$/);
    const heading = line.match(/^\s*#{1,6}\s+(.*)$/);
    if (bullet || numbered) {
      flushPara();
      const tag = bullet ? "ul" : "ol";
      if (!list || list.tag !== tag) { flushList(); list = { tag, items: [] }; }
      list.items.push((bullet || numbered)[1]);
    } else if (heading) {
      flushPara(); flushList();
      out.push(`<p dir="auto"><strong>${inline(heading[1])}</strong></p>`);
    } else if (!line.trim()) {
      flushPara(); flushList();
    } else {
      flushList();
      para.push(line);
    }
  }
  flushPara(); flushList();
  return out.join("");
}

// ---------- thread ----------
function scrollDown() { const t = $("#thread"); t.scrollTop = t.scrollHeight; }
function note(text) {
  const el = document.createElement("div");
  el.className = "note";
  el.textContent = text;
  $("#thread").append(el);
  scrollDown();
}
function addUserMessage(text) {
  const el = document.createElement("div");
  el.className = "msg user";
  el.dir = "auto";
  el.textContent = text;
  $("#thread").append(el);
  scrollDown();
}
function addPending() {
  const el = document.createElement("div");
  el.className = "msg assistant";
  el.innerHTML = '<div class="bubble"><ol class="live-steps"></ol><span class="muted thinking">Ferrero is checking the case files</span></div>';
  $("#thread").append(el);
  scrollDown();
  return el;
}
function describeTool(ev) {
  const i = ev.input || {};
  switch (ev.name) {
    case "search_case_documents": return `Searching documents for “${i.query || ""}”${i.case_id ? ` in ${i.case_id}` : ""}`;
    case "read_case_document": return `Reading ${i.file_name || "a document"}`;
    case "get_case": return `Looking up case ${i.case_id || ""}`;
    case "query_case_data": return "Querying the case tracker";
    default: return ev.name;
  }
}
function addStep(pending, ev) {
  const li = document.createElement("li");
  li.textContent = describeTool(ev);
  pending.querySelector(".live-steps").append(li);
  scrollDown();
}
function showError(pending, message) {
  pending.querySelector(".bubble").innerHTML = `<p class="error">${escapeHtml(message)}</p>`;
}
function renderAnswer(pending, a) {
  const id = ++state.msgSeq;
  let marked = "";
  for (const seg of a.segments || []) {
    marked += seg.text + seg.citations.map((n) => `\u0001${n}\u0002`).join("");
  }
  if (!marked) marked = a.text || "";
  const body = renderMarkdown(escapeHtml(marked))
    .replace(/\u0001(\d+)\u0002/g, (_, n) => `<sup class="cite"><a href="#src-${id}-${n}" title="Source ${n}">${n}</a></sup>`);

  const badges = [];
  if ((a.route || []).includes("documents")) badges.push('<span class="badge">Documents</span>');
  if ((a.route || []).includes("case_data")) badges.push('<span class="badge">Case tracker</span>');

  let sources = "";
  if ((a.citations || []).length) {
    sources = '<div class="sources"><h3>Sources</h3><ol>' + a.citations.map((c) => `
      <li id="src-${id}-${c.n}"><span class="n">${c.n}</span><strong>${escapeHtml(c.file_name || c.title || c.source)}</strong>
        ${c.section ? ` · ${escapeHtml(c.section)}` : ""}${c.doc_type ? ` <span class="badge plain">${escapeHtml(c.doc_type)}</span>` : ""}
        <blockquote dir="auto">${escapeHtml(c.cited_text || "")}</blockquote>
        ${c.library_path ? `<div class="path">${escapeHtml(c.library_path)}</div>` : ""}</li>`).join("") + "</ol></div>";
  }
  const steps = (a.tools || []).length ? `<details class="steps"><summary>How Ferrero answered: ${a.tools.length} step${a.tools.length > 1 ? "s" : ""} · ${a.latency_s}s</summary><ol>${
    a.tools.map((t) => `<li${t.is_error ? ' class="error"' : ""}>${escapeHtml(describeTool(t))} – ${escapeHtml(t.summary || "")}</li>`).join("")}</ol></details>` : "";

  pending.querySelector(".bubble").innerHTML =
    (badges.length ? `<div class="badges">${badges.join("")}</div>` : "") + body + sources + steps;
  scrollDown();
}

// ---------- conversation ----------
async function newConversation() {
  const userId = $("#user").value;
  let data;
  try {
    data = await (await api("/api/conversations", { method: "POST", body: JSON.stringify({ user_id: userId, case_id: state.caseId }) })).json();
  } catch (e) {
    note(`Could not start a conversation: ${e.message}`);
    return;
  }
  state.conversationId = data.conversation_id;
  $("#thread").innerHTML = "";
  $("#access").textContent = `Can see ${data.user.access}.`;
  const card = $("#case-card");
  if (data.case) {
    const c = data.case;
    $("#case-body").innerHTML = [
      `<div class="case-line"><b>${escapeHtml(c.case_id)}</b> · ${escapeHtml(c.title)}</div>`,
      `<div class="case-line">${escapeHtml(c.status)} · ${escapeHtml(c.stage)}${c.outcome && c.outcome !== "Pending" ? ` · ${escapeHtml(c.outcome)}` : ""}</div>`,
      `<div class="case-line">${escapeHtml(c.court_name)}</div>`,
      c.next_hearing_date ? `<div class="case-line">Next hearing ${fmtDate(c.next_hearing_date)}</div>` : "",
      c.next_action ? `<div class="case-line">Next: ${escapeHtml(c.next_action)}${c.next_action_due ? ` (due ${fmtDate(c.next_action_due)})` : ""}</div>` : "",
    ].join("");
    card.hidden = false;
  } else if (data.case_requested) {
    $("#case-body").innerHTML = `<div class="case-line">${escapeHtml(data.case_requested)} is not available to ${escapeHtml(data.user.full_name)}.</div>`;
    card.hidden = false;
  } else {
    card.hidden = true;
  }
  note(`New conversation as ${data.user.full_name} (${data.user.entra_group}).`);
  $("#input").focus();
}

async function send(text) {
  text = text.trim();
  if (state.busy || !text || !state.conversationId) return;
  state.busy = true;
  $("#send").disabled = true;
  $("#input").value = "";
  addUserMessage(text);
  const pending = addPending();
  try {
    const res = await fetch(`/api/conversations/${state.conversationId}/messages`, {
      method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ text }),
    });
    if (!res.ok) {
      const body = await res.json().catch(() => ({}));
      showError(pending, typeof body.detail === "string" ? body.detail : res.statusText);
      if (res.status === 404) await newConversation();
      return;
    }
    const reader = res.body.getReader();
    const decoder = new TextDecoder();
    let buffer = "";
    for (;;) {
      const { value, done } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });
      let cut;
      while ((cut = buffer.indexOf("\n\n")) >= 0) {
        const chunk = buffer.slice(0, cut);
        buffer = buffer.slice(cut + 2);
        if (!chunk.startsWith("data: ")) continue;
        const ev = JSON.parse(chunk.slice(6));
        if (ev.type === "tool") addStep(pending, ev);
        else if (ev.type === "answer") renderAnswer(pending, ev);
        else if (ev.type === "error") showError(pending, ev.message);
      }
    }
  } catch (e) {
    showError(pending, `Connection problem: ${e.message}`);
  } finally {
    state.busy = false;
    $("#send").disabled = false;
  }
}

async function init() {
  try {
    const meta = await (await api("/api/meta")).json();
    state.model = meta.model;
    $("#meta").textContent = `Reporting date ${fmtDate(meta.demo_today)} · ${meta.index.indexed} documents searchable`;
    for (const q of meta.examples) {
      const li = document.createElement("li");
      const b = document.createElement("button");
      b.type = "button";
      b.dir = "auto";
      b.textContent = q;
      b.addEventListener("click", () => send(q));
      li.append(b);
      $("#examples").append(li);
    }
    state.users = await (await api("/api/users")).json();
  } catch (e) {
    $("#meta").textContent = `Server not reachable: ${e.message}`;
    return;
  }
  const select = $("#user");
  for (const u of state.users) {
    const opt = document.createElement("option");
    opt.value = u.user_id;
    opt.textContent = `${u.full_name} – ${u.job_title} (${u.entra_group})`;
    select.append(opt);
  }
  select.value = store("ferrero.user") || "U-08";
  if (!select.value) select.selectedIndex = 0;
  select.addEventListener("change", () => { store("ferrero.user", select.value); newConversation(); });
  $("#new").addEventListener("click", newConversation);
  $("#composer").addEventListener("submit", (e) => { e.preventDefault(); send($("#input").value); });
  $("#input").addEventListener("keydown", (e) => {
    if (e.key === "Enter" && !e.shiftKey && !e.isComposing) { e.preventDefault(); send($("#input").value); }
  });
  await newConversation();
}

init();
