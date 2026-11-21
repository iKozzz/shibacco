(() => {
  const BUILD = "4"; // версия локальных ассетов (синхронно с ?v= в index.html)
  window.__shibaccoBuild = BUILD;
  const tg = window.Telegram && window.Telegram.WebApp;
  const inTG = !!(tg && tg.initData);
  const $ = (s) => document.querySelector(s);
  const state = { size: "", style: "", strength: "", tag: "", brands: new Set() };
  const COLORS = ["#ff7a3d", "#ffb067", "#c58cff", "#7fd1a3"];
  let py = null, busy = false, last = [];

  if (inTG) {
    document.body.classList.add("tg");
    tg.ready(); tg.expand();
    try { tg.setHeaderColor("#141012"); tg.setBackgroundColor("#141012"); } catch (e) {}
    tg.MainButton.setParams({ text: "Подготовка…", color: "#ff7a3d", text_color: "#1a0f0a" });
    tg.MainButton.show(); tg.MainButton.disable();
    tg.MainButton.onClick(generate);
  }

  const haptic = (t) => { try { inTG && tg.HapticFeedback.impactOccurred(t || "light"); } catch (e) {} };
  const toast = (m) => { const t = $("#toast"); t.textContent = m; t.classList.add("show"); clearTimeout(t._h); t._h = setTimeout(() => t.classList.remove("show"), 1800); };
  const esc = (s) => String(s ?? "").replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));

  // оверлей загрузки: спиннер + прогресс, UI показываем только после готовности
  const PHRASES = [
    "Фаннел или турка — вот в чём вопрос",
    "Уголь дышит, табак молчит",
    "Где-то томится идеальный микс",
    "Калауд греется, судьба решается",
    "Дым знает больше, чем мы",
    "Шахта помнит каждый затяг",
    "Мята шепчет, цитрус спорит",
    "Табак ещё не решил, кем станет",
    "Жар угля — дело тонкое",
    "Вкус собирается по крупицам",
    "Пока грузится — раскуривай терпение",
    "Дым рассеется, микс останется",
    "Совместимость вкусов — как химия людей",
    "Не торопи уголь, не торопи микс",
    "Где-то между ягодой и холодом",
    "Пропорции важнее слов",
    "Нет дыма без угля",
    "Уголь лёг — мысли потянулись",
    "Дым не врёт, он намекает",
    "Турка молчит, но всё понимает",
    "Фаннел выбирает тебя, не ты его",
    "Калауд — маленький костёр судьбы",
    "Затяг длиннее, чем разговор",
    "Вкус приходит к тем, кто ждёт",
    "Ягода спорит с холодом, судья — дым",
    "Табак любит терпеливых",
    "Жар углей — характер микса",
    "Дым пишет письма без чернил",
    "Мята остывает, цитрус зажигает",
    "В каждом угле — чья-то история",
    "Микс как погода: непредсказуем, но приятен",
    "Шахта — портал в настроение",
    "Уголь краснеет, вкус раскрывается",
    "Дым знает дорогу к дому",
    "Табак шепчет рецептами",
    "Совместимость — это когда дым не спорит",
    "Пока угли греются, душа отдыхает",
    "Вкус — это дым, ставший словом",
    "Не считай затяги, считай моменты",
    "Дым рассеивает сомнения",
    "Уголь и табак — старый добрый союз",
    "В миксе, как в жизни: баланс решает",
  ];
  const loader = {
    box: $("#loader"), bar: $("#loadBar"), pct: $("#loadPct"), stage: $("#loadStage"),
    err: $("#loadError"), errText: $("#loadErrorText"), value: 0, _pt: null, _pi: -1,
    set(v, text) {
      this.value = Math.max(this.value, Math.min(100, v));
      this.bar.style.width = this.value + "%";
      this.pct.textContent = Math.round(this.value) + "%";
      if (text) this.stage.textContent = text;
    },
    startPhrases() {
      this.stopPhrases();
      const pick = () => {
        let i;
        do { i = Math.floor(Math.random() * PHRASES.length); } while (PHRASES.length > 1 && i === this._pi);
        this._pi = i;
        this.stage.textContent = PHRASES[i];
      };
      pick();
      this._pt = setInterval(pick, 2600);
    },
    stopPhrases() { if (this._pt) { clearInterval(this._pt); this._pt = null; } },
    fail(msg) {
      this.stopPhrases();
      this.box.classList.add("is-error");
      this.stage.textContent = "Не удалось загрузить генератор";
      this.errText.textContent = msg;
      this.err.hidden = false;
    },
    done() {
      this.stopPhrases();
      this.set(100, "Готово");
      document.body.classList.remove("is-loading");
      setTimeout(() => this.box.remove(), 400);
    },
  };
  $("#loadRetry").addEventListener("click", () => location.reload());

  // Кэш базы вкусов: маркер = ETag/Last-Modified, перезагрузка только при изменении файла.
  // Кэшируем и сырую базу, и обработанную (чтобы не повторять тяжёлый препроцессинг).
  const DB_URL = "tobacco_flavors.json";
  const RAW_CACHE = "shibacco-db-v1";
  const PROC_CACHE = "shibacco-proc-v1";
  async function dbMarker() {
    try {
      const head = await fetch(DB_URL, { method: "HEAD", cache: "no-store" });
      return head.headers.get("etag") || head.headers.get("last-modified");
    } catch (e) { return null; }
  }
  async function cacheRead(name, key) {
    if (!window.caches) return null;
    try {
      const c = await caches.open(name);
      const hit = await c.match(key);
      return hit ? await hit.text() : null;
    } catch (e) { return null; }
  }
  async function cacheWrite(name, key, text) {
    if (!window.caches) return;
    try {
      const c = await caches.open(name);
      for (const k of await c.keys()) await c.delete(k); // держим только актуальную версию
      await c.put(key, new Response(text, { headers: { "Content-Type": "application/json" } }));
    } catch (e) {}
  }
  async function loadDbRaw(marker) {
    if (marker) {
      const key = DB_URL + "?v=" + encodeURIComponent(marker);
      const hit = await cacheRead(RAW_CACHE, key);
      if (hit) return hit;
      const res = await fetch(DB_URL, { cache: "no-store" });
      if (!res.ok) throw new Error("HTTP " + res.status);
      const text = await res.text();
      await cacheWrite(RAW_CACHE, key, text);
      return text;
    }
    const res = await fetch(DB_URL, { cache: "no-store" });
    if (!res.ok) throw new Error("HTTP " + res.status);
    return await res.text();
  }

  function setReady(text, enabled) {
    $(".cta-text").textContent = text; $("#go").disabled = !enabled;
    if (inTG) { tg.MainButton.setText(text); enabled ? tg.MainButton.enable() : tg.MainButton.disable(); }
  }

  // segmented controls
  document.querySelectorAll(".seg").forEach((seg) => {
    seg.addEventListener("click", (e) => {
      const b = e.target.closest("button"); if (!b) return;
      seg.querySelectorAll("button").forEach((x) => x.classList.toggle("on", x === b));
      state[seg.dataset.key] = b.dataset.v; haptic("soft");
    });
  });

  function updateBadge() {
    const n = (state.tag ? 1 : 0) + state.brands.size;
    const b = $("#filtersBadge"); b.hidden = !n; b.textContent = n;
    $("#clearBrands").hidden = !state.brands.size;
  }

  function buildChips(meta) {
    const tags = $("#tags");
    tags.innerHTML = ['<button class="chip on" data-v="">любая</button>', ...meta.tags.map((t) => `<button class="chip" data-v="${esc(t)}">${esc(t)}</button>`)].join("");
    tags.addEventListener("click", (e) => {
      const b = e.target.closest(".chip"); if (!b) return;
      tags.querySelectorAll(".chip").forEach((x) => x.classList.toggle("on", x === b));
      state.tag = b.dataset.v; updateBadge(); haptic("soft");
    });
    const br = $("#brands");
    br.innerHTML = meta.brands.map((t) => `<button class="chip" data-v="${esc(t)}">${esc(t)}</button>`).join("");
    br.addEventListener("click", (e) => {
      const b = e.target.closest(".chip"); if (!b) return;
      const v = b.dataset.v;
      state.brands.has(v) ? state.brands.delete(v) : state.brands.add(v);
      b.classList.toggle("on", state.brands.has(v)); updateBadge(); haptic("soft");
    });
    $("#clearBrands").addEventListener("click", (e) => {
      e.preventDefault(); state.brands.clear();
      br.querySelectorAll(".chip").forEach((x) => x.classList.remove("on")); updateBadge();
    });
  }

  function render(res) {
    const box = $("#results");
    if (res.error) { box.innerHTML = `<div class="err">${esc(res.error)}</div>`; return; }
    if (!res.mixes.length) { box.innerHTML = `<div class="empty">Не удалось собрать микс с такими условиями. Попробуйте убрать часть фильтров.</div>`; return; }
    last = res.mixes;
    box.innerHTML = res.mixes.map((m, idx) => {
      const name = m.items.map((it) => esc(it.display)).join('<span class="sep">\\</span>');
      const bar = m.items.map((it, i) => `<span style="width:${it.percent}%;background:${COLORS[i]}"></span>`).join("");
      const comps = m.items.map((it, i) => `
        <div class="comp">
          <div class="pct" style="color:${COLORS[i]}">${it.percent}%</div>
          <div>
            <div class="comp-t">${it.url ? `<a href="${esc(it.url)}" target="_blank" rel="noopener">${esc(it.label)}</a>` : esc(it.label)}</div>
            <div class="comp-l">${esc(it.flavor)}${it.strength ? ` · ${esc(it.strength)}` : ""}</div>
            ${it.description ? `<div class="comp-d">${esc(it.description)}</div>` : ""}
          </div>
        </div>`).join("");
      const pills = [m.items.length === 1 ? '<span class="pill solo">соло</span>' : "", m.bold ? '<span class="pill bold">смелый</span>' : "", m.score != null ? `<span class="pill" title="Совместимость">${m.score}</span>` : ""].join("");
      const notes = m.notes.length ? `<span class="notes">${esc(m.notes.join(" · "))}</span>` : `<span>${esc(m.groups.slice(0, 4).join(", "))}</span>`;
      return `<article class="card${m.bold ? " isbold" : ""}">
        <div class="card-h"><h2 class="mixname">${name}</h2><div class="tags">${pills}</div></div>
        <div class="bar">${bar}</div>
        ${comps}
        <div class="card-f">${notes}<button class="copy" data-i="${idx}">${inTG ? "Поделиться" : "Скопировать"}</button></div>
      </article>`;
    }).join("");
  }

  function mixText(m) {
    return m.items.map((it) => `${it.percent}% ${it.label} — ${it.flavor}`).join("\n");
  }

  $("#results").addEventListener("click", async (e) => {
    const b = e.target.closest(".copy"); if (!b) return;
    const m = last[+b.dataset.i]; if (!m) return;
    const txt = `Микс Shibacco: ${m.line}\n${mixText(m)}`;
    if (inTG) { tg.openTelegramLink("https://t.me/share/url?url=" + encodeURIComponent(" ") + "&text=" + encodeURIComponent(txt)); return; }
    try { await navigator.clipboard.writeText(txt); toast("Микс скопирован"); }
    catch (err) {
      const ta = document.createElement("textarea"); ta.value = txt; document.body.appendChild(ta); ta.select();
      try { document.execCommand("copy"); toast("Микс скопирован"); } catch (e2) { toast("Не удалось скопировать"); }
      ta.remove();
    }
  });

  async function generate() {
    if (!py || busy) return;
    busy = true; haptic("medium");
    setReady("Подбираю…", false);
    $("#results").innerHTML = '<div class="skel"></div><div class="skel"></div>';
    await new Promise((r) => setTimeout(r, 30));
    try {
      const opts = { size: state.size ? +state.size : null, style: state.style, strength: state.strength, tag: state.tag, brands: [...state.brands], count: 5 };
      py.globals.set("_opts", JSON.stringify(opts));
      const out = await py.runPythonAsync("bridge.run(_opts)");
      render(JSON.parse(out));
      try { inTG && tg.HapticFeedback.notificationOccurred("success"); } catch (e) {}
    } catch (err) {
      console.error(err);
      $("#results").innerHTML = `<div class="err">Ошибка генерации: ${esc(err.message || err)}</div>`;
    }
    busy = false; setReady("Ещё миксы", true);
  }
  $("#go").addEventListener("click", generate);

  async function boot() {
    try {
      loader.startPhrases();
      loader.set(3);
      const marker = await dbMarker();
      const procKey = marker ? "processed.json?v=" + encodeURIComponent(marker) : null;
      const proc = procKey ? await cacheRead(PROC_CACHE, procKey) : null;
      loader.set(10);
      const srcP = fetch("mixgen.py?v=" + BUILD).then((r) => r.text()).then((t) => { loader.set(14); return t; });
      const bridgeP = fetch("bridge.py?v=" + BUILD).then((r) => r.text()).then((t) => { loader.set(18); return t; });
      const pyoP = loadPyodide().then((p) => { loader.set(60); return p; });
      const dbP = proc ? Promise.resolve(null) : loadDbRaw(marker).then((t) => { loader.set(30); return t; });
      const [pyo, src, bridge, db] = await Promise.all([pyoP, srcP, bridgeP, dbP]);
      pyo.FS.writeFile("/home/pyodide/mixgen.py", src);
      pyo.FS.writeFile("/home/pyodide/bridge.py", bridge);
      if (proc) pyo.FS.writeFile("/home/pyodide/processed.json", proc);
      else pyo.FS.writeFile("/home/pyodide/tobacco_flavors.json", db);
      loader.set(70);
      await pyo.runPythonAsync("import sys; sys.path.insert(0, '/home/pyodide'); import bridge");
      loader.set(85);
      if (!proc && procKey) {
        try { await cacheWrite(PROC_CACHE, procKey, pyo.runPython("bridge.processed_json()")); } catch (e) {}
      }
      loader.set(92);
      const meta = JSON.parse(pyo.runPython("bridge.meta()"));
      py = pyo;
      $("#dbinfo").textContent = `${meta.total.toLocaleString("ru-RU")} вкусов · ${meta.brands.length} брендов`;
      buildChips(meta);
      $("#results").innerHTML = '<div class="empty">Выберите параметры и нажмите «Собрать микс».</div>';
      setReady("Собрать микс", true);
      loader.done();
    } catch (err) {
      console.error(err);
      loader.fail(err.message || String(err));
    }
  }
  boot();
})();
