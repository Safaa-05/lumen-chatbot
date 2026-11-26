(function () {
  "use strict";

  const $ = (id) => document.getElementById(id);
  const csrf = document.querySelector('meta[name="csrf-token"]').content;
  const range = $("range");
  const SVG = "http://www.w3.org/2000/svg";
  const POSITIVE = new Set(["joy", "love"]);

  // ---------- date helpers (the server groups by day using our timezone offset) ----------
  const pad = (n) => String(n).padStart(2, "0");
  const ymd = (d) => d.getFullYear() + "-" + pad(d.getMonth() + 1) + "-" + pad(d.getDate());
  const shortDate = (d) => d.toLocaleDateString(undefined, { day: "numeric", month: "short" });
  const tzOffset = () => -new Date().getTimezoneOffset();  // minutes ahead of UTC (India: 330)

  function node(tag, attrs, parent) {
    const n = document.createElementNS(SVG, tag);
    Object.keys(attrs || {}).forEach((k) => n.setAttribute(k, attrs[k]));
    if (parent) parent.appendChild(n);
    return n;
  }

  // ---------- mood-over-time line chart, drawn as SVG ----------
  function drawTrend(daily, days) {
    const box = $("trend");
    box.replaceChildren();

    // Draw at the real pixel width so the text stays readable on phones
    const W = Math.max(280, Math.round(box.clientWidth)), H = W < 520 ? 220 : 260;
    const L = 62, R = 14, T = 14, B = 30;
    const plotW = W - L - R, plotH = H - T - B;
    const svg = node("svg", { viewBox: "0 0 " + W + " " + H, width: W, height: H, role: "img",
      "aria-label": "Line chart of your average mood per day" }, box);

    // list every calendar day in the range so gaps show up as gaps
    const today = new Date();
    const list = [];
    for (let i = days - 1; i >= 0; i--) {
      const d = new Date(today.getFullYear(), today.getMonth(), today.getDate() - i);
      list.push({ key: ymd(d), date: d });
    }
    const x = (i) => L + (days === 1 ? plotW / 2 : (i * plotW) / (days - 1));
    const y = (v) => T + (1 - (v + 1) / 2) * plotH;

    // horizontal guides: positive, neutral, low
    [[1, "Positive"], [0, "Neutral"], [-1, "Low"]].forEach(([v, label]) => {
      node("line", { x1: L, x2: W - R, y1: y(v), y2: y(v), class: v === 0 ? "zero" : "grid" }, svg);
      const t = node("text", { x: L - 10, y: y(v) + 4, "text-anchor": "end" }, svg);
      t.textContent = label;
    });

    // a few date labels along the bottom
    [0, Math.floor((days - 1) / 2), days - 1].filter((v, i, a) => a.indexOf(v) === i).forEach((i, n, arr) => {
      const anchor = i === 0 ? "start" : i === days - 1 ? "end" : "middle";
      const t = node("text", { x: x(i), y: H - 8, "text-anchor": anchor }, svg);
      t.textContent = shortDate(list[i].date);
    });

    // the line and the dots
    const byDay = {};
    daily.forEach((d) => { byDay[d.day] = d; });
    const points = [];
    list.forEach((item, i) => {
      const d = byDay[item.key];
      if (d) points.push({ px: x(i), py: y(Math.max(-1, Math.min(1, d.mood))), d, item });
    });
    if (points.length > 1) {
      node("polyline", { class: "line", points: points.map((p) => p.px + "," + p.py).join(" ") }, svg);
    }
    points.forEach((p) => {
      const c = node("circle", { class: "dot", cx: p.px, cy: p.py, r: 5 }, svg);
      const tip = node("title", {}, c);
      const sign = p.d.mood > 0 ? "+" : "";
      tip.textContent = shortDate(p.item.date) + ": mood " + sign + p.d.mood.toFixed(2) +
        " (" + p.d.n + (p.d.n === 1 ? " check-in)" : " check-ins)");
    });
  }

  // ---------- emotion bars ----------
  function drawBars(counts) {
    const box = $("bars");
    box.replaceChildren();
    const entries = Object.entries(counts).sort((a, b) => b[1] - a[1]);
    const max = entries.length ? entries[0][1] : 1;
    entries.forEach(([emotion, count]) => {
      const row = document.createElement("div");
      row.className = "bar-row";
      const name = document.createElement("span");
      name.className = "bar-name";
      name.textContent = emotion;
      const track = document.createElement("div");
      track.className = "bar-track";
      const fill = document.createElement("div");
      const kind = emotion === "distress" ? "distress" : POSITIVE.has(emotion) ? "" :
                   emotion === "surprise" ? "neutral" : "low";
      fill.className = "bar-fill " + kind;
      fill.style.width = Math.max(4, (count / max) * 100) + "%";
      track.appendChild(fill);
      const num = document.createElement("span");
      num.className = "bar-count";
      num.textContent = count;
      row.append(name, track, num);
      box.appendChild(row);
    });
  }

  // ---------- load and show ----------
  let last = null;  // remembered so the chart can be redrawn when the window is resized

  async function load() {
    const days = Number(range.value);
    const res = await fetch("/api/mood?days=" + days + "&tz=" + tzOffset());
    if (res.status === 401) { window.location.href = "/login"; return; }
    const data = await res.json();

    const has = data.total > 0;
    $("empty").hidden = has;
    $("results").hidden = !has;
    if (!has) return;

    $("statTotal").textContent = data.total;
    $("statTop").textContent = data.top;
    $("statLast").textContent = new Date(data.last.replace(" ", "T") + "Z")
      .toLocaleString(undefined, { day: "numeric", month: "short", hour: "numeric", minute: "2-digit" });
    last = { daily: data.daily, days: days };
    drawTrend(data.daily, days);
    drawBars(data.counts);
  }

  let resizeTimer;
  window.addEventListener("resize", () => {
    clearTimeout(resizeTimer);
    resizeTimer = setTimeout(() => { if (last) drawTrend(last.daily, last.days); }, 150);
  });

  range.addEventListener("change", load);

  $("wipe").addEventListener("click", async () => {
    if (!window.confirm("Delete all saved mood history? This cannot be undone.")) return;
    await fetch("/api/mood", { method: "DELETE", headers: { "X-CSRF-Token": csrf } });
    load();
  });

  load();
})();