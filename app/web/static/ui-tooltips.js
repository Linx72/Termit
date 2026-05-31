window.TermitTooltips = (function () {
  let tipEl = null;
  let activeTarget = null;

  function tTip(key) {
    const lang = window.getTermitLang ? window.getTermitLang() : "ru";
    const pack = (window.TERMIT_I18N && window.TERMIT_I18N[lang]) || {};
    if (pack.tips && pack.tips[key]) return pack.tips[key];
    const en = window.TERMIT_I18N && window.TERMIT_I18N.en;
    return (en && en.tips && en.tips[key]) || "";
  }

  function ensureTipElement() {
    if (tipEl) return tipEl;
    tipEl = document.createElement("div");
    tipEl.id = "termitTooltip";
    tipEl.className = "termit-tooltip";
    tipEl.setAttribute("role", "tooltip");
    tipEl.hidden = true;
    document.body.appendChild(tipEl);
    return tipEl;
  }

  function positionTip(target) {
    const el = ensureTipElement();
    const rect = target.getBoundingClientRect();
    const tipRect = el.getBoundingClientRect();
    let left = rect.left + rect.width / 2 - tipRect.width / 2;
    let top = rect.top - tipRect.height - 10;
    left = Math.max(8, Math.min(left, window.innerWidth - tipRect.width - 8));
    if (top < 8) top = rect.bottom + 10;
    el.style.left = `${left + window.scrollX}px`;
    el.style.top = `${top + window.scrollY}px`;
  }

  function showTip(target) {
    const key = target.getAttribute("data-tip");
    if (!key) return;
    const text = tTip(key);
    if (!text) return;
    activeTarget = target;
    const el = ensureTipElement();
    el.textContent = text;
    el.hidden = false;
    requestAnimationFrame(() => positionTip(target));
  }

  function hideTip() {
    activeTarget = null;
    if (tipEl) tipEl.hidden = true;
  }

  function bind() {
    document.addEventListener(
      "mouseover",
      (event) => {
        const target = event.target.closest("[data-tip]");
        if (target) showTip(target);
      },
      true
    );
    document.addEventListener(
      "mouseout",
      (event) => {
        const target = event.target.closest("[data-tip]");
        if (!target) return;
        const related = event.relatedTarget;
        if (related && target.contains(related)) return;
        if (activeTarget === target) hideTip();
      },
      true
    );
    document.addEventListener("focusin", (event) => {
      const target = event.target.closest("[data-tip]");
      if (target) showTip(target);
    });
    document.addEventListener("focusout", () => hideTip());
    window.addEventListener(
      "scroll",
      () => {
        if (activeTarget) positionTip(activeTarget);
      },
      true
    );
    window.addEventListener("resize", () => {
      if (activeTarget) positionTip(activeTarget);
    });
  }

  function applyTipsToDom() {
    document.querySelectorAll("[data-tip]").forEach((el) => {
      const key = el.getAttribute("data-tip");
      const text = tTip(key);
      if (text) el.setAttribute("title", "");
      if (text) el.setAttribute("aria-label", text.slice(0, 160));
    });
  }

  function init() {
    ensureTipElement();
    bind();
    applyTipsToDom();
  }

  return { init, applyTipsToDom, hideTip };
})();
