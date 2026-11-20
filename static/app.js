"use strict";

// ---------------------------------------------------------------- config
const CATEGORY_COLORS = {
  "Models & Research": "var(--c-models)",
  "Business": "var(--c-business)",
  "Policy & Society": "var(--c-policy)",
  "Products": "var(--c-products)",
  "Health & Science": "var(--c-health)",
  "Chips & Hardware": "var(--c-chips)",
  "Thailand": "var(--c-thailand)",
  "General": "var(--c-general)",
};
const PAGE_SIZE = 30;
// build_static.py adds this tag for the GitHub Pages copy, which reads JSON files instead of the Flask API.
const STATIC_META = document.querySelector('meta[name="static-build"]');
const IS_STATIC = !!STATIC_META;
const REPO = STATIC_META?.content || "";
const store = {
  get: (k, d) => { try { return JSON.parse(localStorage.getItem("aidaily." + k)) ?? d; } catch { return d; } },
  set: (k, v) => localStorage.setItem("aidaily." + k, JSON.stringify(v)),
};

const state = {
  days: store.get("days", 1),
  category: "All",
  query: "",
  sort: "new",
  limit: PAGE_SIZE,
  data: null,
  saved: store.get("saved", {}),      // url -> {title, url, source, published}
  read: new Set(store.get("read", [])),
};

const $ = (sel) => document.querySelector(sel);

// ---------------------------------------------------------------- helpers
const escapeHtml = (s) => String(s ?? "").replace(/[&<>"']/g, (c) =>
  ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
const safeUrl = (u) => /^https?:\/\//i.test(u || "") ? escapeHtml(u) : "#";
const colorOf = (cat) => CATEGORY_COLORS[cat] || CATEGORY_COLORS.General;

function timeAgo(iso) {
  const mins = Math.round((Date.now() - new Date(iso)) / 60000);
  if (mins < 1) return "just now";
  if (mins < 60) return `${mins}m ago`;
  const hrs = Math.round(mins / 60);
  if (hrs < 24) return `${hrs}h ago`;
  const days = Math.round(hrs / 24);
  return days === 1 ? "yesterday" : `${days}d ago`;
}

function dayLabel(iso) {
  const d = new Date(iso), today = new Date();
  const start = (x) => new Date(x.getFullYear(), x.getMonth(), x.getDate()).getTime();
  const diff = Math.round((start(today) - start(d)) / 86400000);
  if (diff === 0) return "Today";
  if (diff === 1) return "Yesterday";
  return d.toLocaleDateString(undefined, { weekday: "long", day: "numeric", month: "short" });
}

const fmtTime = (iso) => new Date(iso).toLocaleTimeString(undefined, { hour: "numeric", minute: "2-digit" });

function toast(msg) {
  const el = $("#toast");
  el.textContent = msg;
  el.hidden = false;
  clearTimeout(toast.t);
  toast.t = setTimeout(() => (el.hidden = true), 3200);
}

// ---------------------------------------------------------------- filtering
function filtered() {
  if (!state.data) return [];
  const q = state.query.trim().toLowerCase();
  let list = state.data.articles.filter((a) =>
    (state.category === "All" || a.category === state.category) &&
    (!q || `${a.title} ${a.summary} ${a.source}`.toLowerCase().includes(q)));
  if (state.sort === "coverage") {
    list = [...list].sort((a, b) => b.coverage - a.coverage || b.published.localeCompare(a.published));
  }
  return list;
}

function countBy(list, key) {
  const m = new Map();
  list.forEach((a) => m.set(a[key], (m.get(a[key]) || 0) + 1));
  return [...m.entries()].sort((a, b) => b[1] - a[1]);
}

// ---------------------------------------------------------------- render: pieces
const thumbHtml = (a) => `
  <div class="thumb" style="--cat:${colorOf(a.category)}">
    <span aria-hidden="true">${escapeHtml((a.source || "?").trim().charAt(0).toUpperCase())}</span>
    ${a.image ? `<img src="${safeUrl(a.image)}" alt="" loading="lazy" referrerpolicy="no-referrer" onerror="this.remove()">` : ""}
  </div>`;

const coverageBadge = (a) => a.coverage >= 3
  ? `<span class="badge" title="Similar headlines from ${a.coverage} outlets"><svg class="icon"><use href="#i-flame"/></svg>${a.coverage} outlets</span>` : "";

const metaHtml = (a) => `
  <span class="meta">
    <span class="source">${escapeHtml(a.source)}</span><span aria-hidden="true">·</span>
    <time datetime="${escapeHtml(a.published)}" title="${escapeHtml(new Date(a.published).toLocaleString())}">${timeAgo(a.published)}</time>
    ${coverageBadge(a)}
  </span>`;

function cardHtml(a, i) {
  const saved = !!state.saved[a.url];
  return `
  <article class="card ${state.read.has(a.url) ? "is-read" : ""}" style="--cat:${colorOf(a.category)};animation-delay:${Math.min(i, 10) * 25}ms">
    <a href="${safeUrl(a.url)}" target="_blank" rel="noopener noreferrer" data-read="${escapeHtml(a.url)}" tabindex="-1" aria-hidden="true">${thumbHtml(a)}</a>
    <div class="card-body">
      <div class="card-top"><span class="tag">${escapeHtml(a.category)}</span></div>
      <h3><a href="${safeUrl(a.url)}" target="_blank" rel="noopener noreferrer" data-read="${escapeHtml(a.url)}">${escapeHtml(a.title)}</a></h3>
      ${a.summary ? `<p>${escapeHtml(a.summary)}</p>` : ""}
      <div class="card-foot">
        ${metaHtml(a)}
        <button class="save-btn" data-save="${escapeHtml(a.url)}" aria-pressed="${saved}" aria-label="${saved ? "Remove from saved" : "Save for later"}" title="${saved ? "Remove from saved" : "Save for later"}">
          <svg class="icon"><use href="#i-bookmark"/></svg>
        </button>
      </div>
    </div>
  </article>`;
}

function featureHtml(a) {
  return `
  <a class="feature" href="${safeUrl(a.url)}" target="_blank" rel="noopener noreferrer" data-read="${escapeHtml(a.url)}"
     style="--cat:${colorOf(a.category)};--feature-bg:linear-gradient(135deg, color-mix(in srgb, ${colorOf(a.category)} 70%, #0b0d1a), #0b0d1a)">
    ${a.image ? `<img src="${safeUrl(a.image)}" alt="" referrerpolicy="no-referrer" onerror="this.remove()">` : ""}
    <span class="tag">${escapeHtml(a.category)}</span>
    <h3>${escapeHtml(a.title)}</h3>
    ${a.summary ? `<p>${escapeHtml(a.summary)}</p>` : ""}
    ${metaHtml(a)}
  </a>`;
}

// ---------------------------------------------------------------- render: sections
function renderHeader() {
  const now = new Date(), h = now.getHours();
  $("#greeting").textContent = h < 12 ? "Good morning" : h < 18 ? "Good afternoon" : "Good evening";
  $("#today-date").textContent = now.toLocaleDateString(undefined, { weekday: "long", day: "numeric", month: "long", year: "numeric" });
}

function renderStatus() {
  const d = state.data;
  if (!d) return;
  const status = $("#status-text");
  if (d.refreshing) { status.textContent = "Fetching the latest stories…"; return; }
  const next = new Date(d.next_update);
  const nextDay = next.toDateString() === new Date().toDateString() ? "today" : "tomorrow";
  status.innerHTML = d.last_updated
    ? `<span class="dot" aria-hidden="true"></span> Updated ${escapeHtml(timeAgo(d.last_updated))} · next update ${nextDay} at ${escapeHtml(fmtTime(d.next_update))}`
    : "Not fetched yet — click refresh";
}

function renderStats() {
  const all = state.data.articles;
  const range = { 1: "in the last 24 hours", 3: "in the last 3 days", 7: "this week" }[state.days];
  $("#stat-stories").textContent = all.length;
  $("#stat-stories-sub").textContent = range;
  const outlets = countBy(all, "source");
  $("#stat-outlets").textContent = outlets.length;
  $("#stat-outlets-sub").textContent = outlets[0] ? `most from ${outlets[0][0]}` : " ";
  const topics = countBy(all.filter((a) => !["General", "Thailand"].includes(a.category)), "category");
  $("#stat-topic").textContent = topics[0] ? topics[0][0] : "—";
  $("#stat-topic").style.color = topics[0] ? colorOf(topics[0][0]) : "";
  $("#stat-topic-sub").textContent = topics[0] ? `${topics[0][1]} stories` : " ";
  $("#stat-saved").textContent = Object.keys(state.saved).length;
}

function renderBrief() {
  const brief = state.data.summary;
  $("#brief").hidden = !brief?.items?.length;
  if (!brief?.items?.length) return;
  $("#brief-list").innerHTML = brief.items.map((it) => `
    <li>
      <div class="brief-th" lang="th">
        <a href="${safeUrl(it.url)}" target="_blank" rel="noopener noreferrer" data-read="${escapeHtml(it.url)}">${escapeHtml(it.title_th)}</a>
        <p>${escapeHtml(it.summary_th)}</p>
      </div>
      <div class="brief-en" lang="en">
        <strong>${escapeHtml(it.title_en)}</strong>
        <p>${escapeHtml(it.summary_en)}</p>
      </div>
      <span class="brief-source">${escapeHtml(it.source)}</span>
    </li>`).join("");
  $("#brief-meta").textContent = `${brief.model} · ${timeAgo(brief.generated)}`;
}

function renderFeatured() {
  const byId = new Map(state.data.articles.map((a) => [a.id, a]));
  const items = state.data.featured.map((id) => byId.get(id)).filter(Boolean);
  $("#featured").innerHTML = items.length
    ? items.map(featureHtml).join("")
    : `<div class="empty" style="grid-column:1/-1"><strong>No top stories yet</strong>Check back after the next update.</div>`;
}

function renderChips() {
  const all = state.data.articles;
  const counts = new Map(countBy(all, "category"));
  const cats = ["All", ...Object.keys(CATEGORY_COLORS).filter((c) => counts.has(c))];
  if (state.category !== "All" && !counts.has(state.category)) state.category = "All";
  $("#chips").innerHTML = cats.map((c) => `
    <button class="chip" data-cat="${escapeHtml(c)}" aria-pressed="${state.category === c}" style="--cat:${c === "All" ? "var(--accent)" : colorOf(c)}">
      ${c === "All" ? "" : '<span class="dot" aria-hidden="true"></span>'}${escapeHtml(c)}
      <span class="count">${c === "All" ? all.length : counts.get(c)}</span>
    </button>`).join("");
}

function renderFeed() {
  const list = filtered();
  const feed = $("#feed");
  const af = $("#active-filter");
  if (state.query) {
    af.hidden = false;
    af.innerHTML = `${list.length} result${list.length === 1 ? "" : "s"} for “${escapeHtml(state.query)}”
      <button data-clear-search><svg class="icon"><use href="#i-x"/></svg>Clear</button>`;
  } else af.hidden = true;

  if (!list.length) {
    feed.innerHTML = `<div class="empty"><strong>Nothing matches</strong>Try another topic, a wider time range, or a different search.</div>`;
    $("#more-btn").hidden = true;
    return;
  }
  const shown = list.slice(0, state.limit);
  let html = "", lastDay = null;
  shown.forEach((a, i) => {
    if (state.sort === "new") {
      const label = dayLabel(a.published);
      if (label !== lastDay) { html += `<div class="day-label">${escapeHtml(label)}</div>`; lastDay = label; }
    }
    html += cardHtml(a, i);
  });
  feed.innerHTML = html;
  const more = $("#more-btn");
  more.hidden = list.length <= state.limit;
  more.textContent = `Show more stories (${list.length - state.limit} left)`;
}

function renderSidebar() {
  const all = state.data.articles;
  const trending = state.data.trending;
  $("#trending").innerHTML = trending.length
    ? trending.map(([w, c]) => `<button data-term="${escapeHtml(w)}">${escapeHtml(w)}<small>${c}</small></button>`).join("")
    : `<p class="panel-empty">Not enough headlines yet.</p>`;

  const bars = (rows, attr, colored) => {
    const max = rows[0]?.[1] || 1;
    return rows.map(([name, n]) => `
      <li><button ${attr}="${escapeHtml(name)}" style="--cat:${colored ? colorOf(name) : "var(--accent)"}">
        <div class="bar-row"><span>${escapeHtml(name)}</span><b>${n}</b></div>
        <div class="bar"><i style="width:${(n / max) * 100}%"></i></div>
      </button></li>`).join("");
  };
  $("#topic-bars").innerHTML = bars(countBy(all, "category"), "data-cat", true);
  $("#source-bars").innerHTML = bars(countBy(all, "source").slice(0, 7), "data-term", false);
  renderSaved();
}

function renderSaved() {
  const items = Object.values(state.saved).sort((a, b) => b.savedAt - a.savedAt);
  $("#saved-list").innerHTML = items.length
    ? items.slice(0, 8).map((a) => `
      <li>
        <a href="${safeUrl(a.url)}" target="_blank" rel="noopener noreferrer">${escapeHtml(a.title)}<small>${escapeHtml(a.source)} · ${timeAgo(a.published)}</small></a>
        <button data-save="${escapeHtml(a.url)}" aria-label="Remove from saved" title="Remove"><svg class="icon"><use href="#i-x"/></svg></button>
      </li>`).join("")
    : `<p class="panel-empty">Click the bookmark on any story to keep it here.</p>`;
  $("#stat-saved").textContent = items.length;
}

function renderAll() {
  renderStatus();
  renderStats();
  renderBrief();
  renderFeatured();
  renderChips();
  renderFeed();
  renderSidebar();
}

function renderLoading() {
  $("#featured").innerHTML = `<div class="skeleton" style="grid-row:span 2"></div><div class="skeleton"></div><div class="skeleton"></div>`;
  $("#feed").innerHTML = Array.from({ length: 5 }, () => `<div class="skeleton skeleton-card"></div>`).join("");
}

// ---------------------------------------------------------------- data
async function load({ quiet = false } = {}) {
  if (!quiet && !state.data) renderLoading();
  try {
    const url = IS_STATIC ? `data/news-${state.days}.json` : `api/news?days=${state.days}`;
    const res = await fetch(url, { cache: "no-cache" });
    if (!res.ok) throw new Error(res.status);
    state.data = await res.json();
    renderAll();
    if (!IS_STATIC && state.data.refreshing) setTimeout(() => load({ quiet: true }), 4000);
  } catch (err) {
    if (IS_STATIC) {
      $("#status-text").textContent = "Couldn't load the news data file.";
      if (!state.data) $("#feed").innerHTML = `<div class="empty"><strong>Can't load news</strong>The data file couldn't be loaded. Try reloading in a few minutes.</div>`;
    } else {
      $("#status-text").textContent = "Couldn't reach the news server. Is app.py running?";
      if (!state.data) $("#feed").innerHTML = `<div class="empty"><strong>Can't load news</strong>Start the server with <code>python app.py</code> and reload.</div>`;
    }
  }
}

async function refreshNow() {
  const btn = $("#refresh-btn");
  if (btn.classList.contains("spinning")) return;
  btn.classList.add("spinning");
  $("#status-text").textContent = "Fetching the latest stories…";
  try {
    const res = await fetch("api/refresh", { method: "POST" });
    const r = await res.json();
    if (r.status === "busy") toast("Already updating — hang on a moment");
    else {
      const failed = Object.keys(r.errors || {});
      toast(`${r.new} new ${r.new === 1 ? "story" : "stories"}` + (failed.length ? ` · ${failed.length} source${failed.length > 1 ? "s" : ""} unavailable` : ""));
    }
    await load({ quiet: true });
  } catch {
    toast("Refresh failed — check your connection");
  } finally {
    btn.classList.remove("spinning");
  }
}

// ---------------------------------------------------------------- actions
function toggleSave(url) {
  if (state.saved[url]) delete state.saved[url];
  else {
    const a = state.data?.articles.find((x) => x.url === url);
    if (!a) return;
    state.saved[url] = { url: a.url, title: a.title, source: a.source, published: a.published, savedAt: Date.now() };
    toast("Saved for later");
  }
  store.set("saved", state.saved);
  document.querySelectorAll(`.save-btn[data-save="${CSS.escape(url)}"]`).forEach((b) => {
    const on = !!state.saved[url];
    b.setAttribute("aria-pressed", on);
    b.setAttribute("aria-label", on ? "Remove from saved" : "Save for later");
    b.title = on ? "Remove from saved" : "Save for later";
  });
  renderSaved();
}

function markRead(url) {
  if (state.read.has(url)) return;
  state.read.add(url);
  store.set("read", [...state.read].slice(-1500));
  document.querySelectorAll(`[data-read="${CSS.escape(url)}"]`).forEach((el) => el.closest(".card")?.classList.add("is-read"));
}

function setSearch(term) {
  state.query = term;
  state.limit = PAGE_SIZE;
  $("#search").value = term;
  renderFeed();
  $("#feed-title").scrollIntoView({ behavior: "smooth", block: "start" });
}

function setCategory(cat) {
  state.category = cat;
  state.limit = PAGE_SIZE;
  renderChips();
  renderFeed();
}

// ---------------------------------------------------------------- events
document.addEventListener("click", (e) => {
  const t = e.target.closest("[data-save],[data-cat],[data-term],[data-days],[data-clear-search],[data-read]");
  if (!t) return;
  if (t.dataset.save !== undefined) { e.preventDefault(); toggleSave(t.dataset.save); }
  else if (t.dataset.cat !== undefined) {
    setCategory(t.dataset.cat === state.category && t.closest(".bars") ? "All" : t.dataset.cat);
    if (t.closest(".sidebar")) $("#feed-title").scrollIntoView({ behavior: "smooth" });
  }
  else if (t.dataset.term !== undefined) setSearch(t.dataset.term);
  else if (t.dataset.clearSearch !== undefined) setSearch("");
  else if (t.dataset.days !== undefined) {
    state.days = Number(t.dataset.days);
    store.set("days", state.days);
    state.limit = PAGE_SIZE;
    document.querySelectorAll(".segmented button").forEach((b) => b.setAttribute("aria-pressed", b === t));
    load({ quiet: true });
  }
  else if (t.dataset.read !== undefined) markRead(t.dataset.read);
});
// Middle-click opens in a new tab too; count it as read.
document.addEventListener("auxclick", (e) => {
  const t = e.target.closest("[data-read]");
  if (t) markRead(t.dataset.read);
});

let searchTimer;
$("#search").addEventListener("input", (e) => {
  clearTimeout(searchTimer);
  searchTimer = setTimeout(() => { state.query = e.target.value; state.limit = PAGE_SIZE; renderFeed(); }, 120);
});
$("#search").addEventListener("keydown", (e) => { if (e.key === "Escape") { setSearch(""); e.target.blur(); } });
document.addEventListener("keydown", (e) => {
  if (e.key === "/" && !["INPUT", "TEXTAREA", "SELECT"].includes(document.activeElement.tagName)) {
    e.preventDefault();
    $("#search").focus();
  }
});
$("#sort").addEventListener("change", (e) => { state.sort = e.target.value; renderFeed(); });
$("#more-btn").addEventListener("click", () => { state.limit += PAGE_SIZE; renderFeed(); });
const refreshBtn = $("#refresh-btn");
if (!IS_STATIC) refreshBtn.addEventListener("click", refreshNow);
else if (REPO) {
  refreshBtn.title = "Run the update on GitHub";
  refreshBtn.setAttribute("aria-label", "Run the update on GitHub");
  refreshBtn.addEventListener("click", () =>
    window.open(`https://github.com/${REPO}/actions/workflows/daily.yml`, "_blank", "noopener"));
}
else refreshBtn.hidden = true;
$("#theme-btn").addEventListener("click", () => {
  const next = document.documentElement.dataset.theme === "dark" ? "light" : "dark";
  document.documentElement.dataset.theme = next;
  localStorage.setItem("aidaily.theme", next);
});

// When the tab has been open overnight, pick up the morning update automatically.
document.addEventListener("visibilitychange", () => { if (!document.hidden) { renderHeader(); load({ quiet: true }); } });
setInterval(() => { renderHeader(); load({ quiet: true }); }, 15 * 60 * 1000);

// ---------------------------------------------------------------- start
document.querySelectorAll(".segmented button").forEach((b) => b.setAttribute("aria-pressed", Number(b.dataset.days) === state.days));
renderHeader();
load();
