// Tooltips (data-tip), placed by Floating UI: faster than native ones, themed, and on
// keyboard focus too. Without Floating UI: the browser's own.
const FUI = globalThis.FloatingUIDOM;
const tipEl = Object.assign(document.createElement("div"), {
  className: "tip",
  id: "tip",
  role: "tooltip",
  hidden: true,
});
let tipAnchor = null,
  tipTimer = 0,
  stopTip = null,
  lastTip = 0;
const tipTarget = (node) => (node instanceof Element ? node.closest("[data-tip]") : null);
function showTip(el) {
  if (!el.isConnected || !el.dataset.tip) return;
  tipEl.textContent = el.dataset.tip;
  (el.closest("dialog[open]") || document.body).append(tipEl); // modal dialogs sit above the page
  tipEl.hidden = false;
  el.setAttribute("aria-describedby", "tip");
  const place = () =>
    FUI.computePosition(el, tipEl, {
      placement: "top",
      strategy: "fixed",
      middleware: [FUI.offset(8), FUI.flip(), FUI.shift({ padding: 8 })],
    }).then(({ x, y }) => Object.assign(tipEl.style, { left: x + "px", top: y + "px" }));
  stopTip = FUI.autoUpdate(el, tipEl, place);
}
function hideTip() {
  clearTimeout(tipTimer);
  if (!tipEl.hidden) lastTip = Date.now();
  tipAnchor?.removeAttribute("aria-describedby");
  tipAnchor = null;
  tipEl.hidden = true;
  stopTip?.();
  stopTip = null;
}
function queueTip(el, delay) {
  if (el === tipAnchor) return;
  hideTip();
  if (!el) return;
  tipAnchor = el;
  tipTimer = setTimeout(() => showTip(el), Date.now() - lastTip < 400 ? 0 : delay);
}

export function initTooltips() {
  if (!FUI) {
    document.addEventListener("pointerover", (e) => {
      const el = tipTarget(e.target);
      if (el && !el.title) el.title = el.dataset.tip;
    });
    return;
  }
  document.addEventListener("pointerover", (e) =>
    queueTip(e.pointerType === "touch" ? null : tipTarget(e.target), 150),
  );
  document.addEventListener("pointerout", (e) => {
    if (!e.relatedTarget) hideTip();
  }); // left the window
  document.addEventListener("focusin", (e) => {
    const el = tipTarget(e.target);
    if (el?.matches(":focus-visible")) queueTip(el, 0);
  });
  document.addEventListener("focusout", hideTip);
  document.addEventListener("pointerdown", hideTip);
  document.addEventListener("keydown", (e) => {
    if (e.key === "Escape") hideTip();
  });
}
