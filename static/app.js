(function () {
  "use strict";

  const $ = (id) => document.getElementById(id);
  const scroller = $("scroller");
  const thread = $("thread");
  const empty = $("empty");
  const form = $("composer");
  const input = $("input");
  const sendBtn = $("send");
  const announce = $("announce");
  const analysisToggle = $("analysisToggle");
  const reduceMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  let busy = false;

  // ---------- small helpers ----------
  function save(key, value) { try { localStorage.setItem(key, value); } catch (e) {} }
  function load(key) { try { return localStorage.getItem(key); } catch (e) { return null; } }
  function pct(x) { return Math.round(x * 100) + "%"; }

  function scrollDown() {
    scroller.scrollTo({ top: scroller.scrollHeight, behavior: reduceMotion ? "auto" : "smooth" });
  }

  function autosize() {
    input.style.height = "auto";
    input.style.height = Math.min(input.scrollHeight, 160) + "px";
  }

  function updateSend() {
    sendBtn.disabled = busy || !input.value.trim();
  }

  // ---------- building messages (textContent only, so user text can never inject HTML) ----------
  function el(tag, className, text) {
    const node = document.createElement(tag);
    if (className) node.className = className;
    if (text !== undefined) node.textContent = text;
    return node;
  }

  function addUser(text) {
    const m = el("div", "msg user", text);
    thread.appendChild(m);
    scrollDown();
  }

  function showTyping() {
    const m = el("div", "msg bot");
    const dots = el("div", "typing");
    dots.setAttribute("aria-label", "Lumen is typing");
    for (let i = 0; i < 3; i++) dots.appendChild(el("span"));
    m.appendChild(dots);
    thread.appendChild(m);
    scrollDown();
    return m;
  }

  function reveal(node, text) {
    return new Promise((resolve) => {
      if (reduceMotion) { node.textContent = text; resolve(); return; }
      const words = text.split(" ");
      const delay = Math.max(12, Math.min(35, 2200 / words.length));
      let i = 0;
      const tick = () => {
        i += 1;
        node.textContent = words.slice(0, i).join(" ");
        scrollDown();
        if (i < words.length) setTimeout(tick, delay); else resolve();
      };
      tick();
    });
  }

  function metaText(d) {
    if (d.risk === "high") return "Safety check triggered";
    if (d.emotion) {
      const extra = d.risk === "moderate" ? " · safety note added" : "";
      return "Detected: " + d.emotion + " · " + pct(d.confidence) + " confident · " +
             d.intensity_label + " intensity" + extra;
    }
    if (d.confidence !== null && d.confidence !== undefined) {
      return "Unclear · model confidence " + pct(d.confidence);
    }
    return null;
  }

  function helplineLinks(list) {
    const wrap = el("div", "help");
    list.forEach((h) => {
      const a = el("a");
      a.href = "tel:" + h.contact.replace(/[^0-9+]/g, "");
      a.appendChild(el("strong", "", h.contact));
      a.appendChild(el("span", "", h.name));
      wrap.appendChild(a);
    });
    return wrap;
  }

  async function botMessage(d) {
    const m = el("div", "msg bot");
    if (d.risk === "high") m.classList.add("crisis");
    if (d.error) m.classList.add("error");
    const body = el("div", "bot-text");
    m.appendChild(body);
    thread.appendChild(m);

    await reveal(body, d.reply);

    const info = d.error ? null : metaText(d);
    if (info) m.appendChild(el("div", "meta", info));
    if (d.helplines) m.appendChild(helplineLinks(d.helplines));
    announce.textContent = d.reply;
    scrollDown();
  }

  // ---------- sending ----------
  async function send(raw) {
    const text = raw.trim();
    if (!text || busy) return;
    busy = true;
    empty.hidden = true;
    addUser(text);
    input.value = "";
    autosize();
    updateSend();
    const typing = showTyping();

    try {
      const res = await fetch("/api/chat", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ message: text }),
      });
      const data = await res.json().catch(() => ({}));
      typing.remove();
      if (res.ok) {
        await botMessage(data);
      } else {
        await botMessage({ reply: data.error || "Something went wrong. Please try again.", error: true });
      }
    } catch (err) {
      typing.remove();
      await botMessage({ reply: "I couldn't reach the server. Check your connection and try again.", error: true });
    } finally {
      busy = false;
      updateSend();
      input.focus();
    }
  }

  // ---------- events ----------
  form.addEventListener("submit", (e) => { e.preventDefault(); send(input.value); });

  input.addEventListener("input", () => { autosize(); updateSend(); });
  input.addEventListener("keydown", (e) => {
    // Enter sends, Shift+Enter makes a new line (and don't interfere with IME typing)
    if (e.key === "Enter" && !e.shiftKey && !e.isComposing) {
      e.preventDefault();
      form.requestSubmit();
    }
  });

  document.querySelectorAll(".chip").forEach((chip) => {
    chip.addEventListener("click", () => send(chip.textContent));
  });

  $("newChat").addEventListener("click", async () => {
    try { await fetch("/api/reset", { method: "POST" }); } catch (e) {}
    Array.from(thread.children).forEach((c) => { if (c !== empty) c.remove(); });
    empty.hidden = false;
    announce.textContent = "";
    input.focus();
  });

  // ---------- theme and analysis toggle ----------
  $("themeBtn").addEventListener("click", () => {
    const root = document.documentElement;
    const current = root.getAttribute("data-theme") ||
      (window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light");
    const next = current === "dark" ? "light" : "dark";
    root.setAttribute("data-theme", next);
    save("theme", next);
  });

  function applyAnalysis() {
    document.body.classList.toggle("hide-analysis", !analysisToggle.checked);
  }
  analysisToggle.checked = load("analysis") !== "off";
  analysisToggle.addEventListener("change", () => {
    save("analysis", analysisToggle.checked ? "on" : "off");
    applyAnalysis();
  });
  applyAnalysis();

  input.focus();
})();