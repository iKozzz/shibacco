(() => {
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
            <div class="comp-l">${esc(it.flavor)}${it.price ? ` · от ${it.price} ₽` : ""}${it.strength ? ` · ${esc(it.strength)}` : ""}</div>
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
    const txt = `Микс Shibaco: ${m.line}\n${mixText(m)}`;
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
      $("#results").innerHTML = '<div class="empty">Запускаю генератор в браузере — первый раз это занимает несколько секунд.</div>';
      const [pyo, src, bridge, db] = await Promise.all([
        loadPyodide(),
        fetch("mixgen.py").then((r) => r.text()),
        fetch("bridge.py").then((r) => r.text()),
        fetch("tobacco_flavors.json").then((r) => r.text()),
      ]);
      pyo.FS.writeFile("/home/pyodide/mixgen.py", src);
      pyo.FS.writeFile("/home/pyodide/bridge.py", bridge);
      pyo.FS.writeFile("/home/pyodide/tobacco_flavors.json", db);
      await pyo.runPythonAsync("import sys; sys.path.insert(0, '/home/pyodide'); import bridge");
      const meta = JSON.parse(pyo.runPython("bridge.meta()"));
      py = pyo;
      $("#dbinfo").textContent = `${meta.total.toLocaleString("ru-RU")} вкусов · ${meta.brands.length} брендов`;
      buildChips(meta);
      $("#results").innerHTML = '<div class="empty">Выберите параметры и нажмите «Собрать микс».</div>';
      setReady("Собрать микс", true);
    } catch (err) {
      console.error(err);
      $("#dbinfo").textContent = "Не удалось загрузить генератор";
      $("#results").innerHTML = `<div class="err">Не удалось запустить генератор: ${esc(err.message || err)}. Обновите страницу.</div>`;
    }
  }
  boot();
})();
