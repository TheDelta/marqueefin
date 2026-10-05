// The state menu of a title on your list: one, placed next to whichever button opened
// it (card corner, list dialog)
import { t } from "./i18n.js";
import { markIcon } from "./icons.js";
import { esc } from "./lib.js";
import { setMark } from "./list.js";
import { MARK_LABEL, marks } from "./marks.js";

const markMenu = Object.assign(document.createElement("div"), {
  className: "markmenu",
  role: "menu",
  hidden: true,
});
let menuFor = null,
  menuAnchor = null,
  stopMenu = null;
function placeMenu() {
  const FUIx = globalThis.FloatingUIDOM;
  if (!FUIx) {
    const r = menuAnchor.getBoundingClientRect();
    Object.assign(markMenu.style, {
      left: `${Math.max(8, r.right - 190)}px`,
      top: `${r.bottom + 6}px`,
    });
    return;
  }
  FUIx.computePosition(menuAnchor, markMenu, {
    placement: "bottom-end",
    strategy: "fixed",
    middleware: [FUIx.offset(6), FUIx.flip(), FUIx.shift({ padding: 8 })],
  }).then(({ x, y }) => Object.assign(markMenu.style, { left: `${x}px`, top: `${y}px` }));
}
export function openMarkMenu(it, anchor) {
  const again = menuAnchor === anchor && !markMenu.hidden;
  closeMarkMenu(false);
  if (again) return; // a second click on the same button closes it
  menuFor = it;
  menuAnchor = anchor;
  const st = marks.get(it.id) || "";
  markMenu.innerHTML =
    Object.entries(MARK_LABEL)
      .map(
        ([k, label]) =>
          `<button type="button" role="menuitemradio" aria-checked="${k === st}" data-set="${k}">${markIcon(k)}${esc(label)}</button>`,
      )
      .join("") +
    `<button type="button" role="menuitem" class="rm" data-set="">${esc(t("mark.removeFromList"))}</button>`;
  (anchor.closest("dialog[open]") || document.body).append(markMenu);
  markMenu.hidden = false;
  anchor.setAttribute("aria-expanded", "true");
  const FUIx = globalThis.FloatingUIDOM;
  stopMenu = FUIx ? FUIx.autoUpdate(anchor, markMenu, placeMenu) : (placeMenu(), null);
  markMenu.querySelector('[aria-checked="true"]')?.focus();
}
function closeMarkMenu(focusBack = true) {
  if (markMenu.hidden) return;
  markMenu.hidden = true;
  stopMenu?.();
  stopMenu = null;
  menuAnchor?.setAttribute("aria-expanded", "false");
  if (focusBack && menuAnchor?.isConnected) menuAnchor.focus();
  menuAnchor = menuFor = null;
}

export function initMenu() {
  markMenu.addEventListener("click", (e) => {
    const b = e.target.closest("[data-set]");
    if (!b) return;
    const it = menuFor;
    closeMarkMenu();
    setMark(it, b.dataset.set);
  });
  markMenu.addEventListener("keydown", (e) => {
    if (!["ArrowDown", "ArrowUp"].includes(e.key)) return;
    e.preventDefault();
    const items = [...markMenu.querySelectorAll("button")];
    const i = items.indexOf(document.activeElement);
    items[(i + (e.key === "ArrowDown" ? 1 : items.length - 1)) % items.length].focus();
  });
  // Escape closes the menu only (not the dialog around it); a click elsewhere too
  document.addEventListener(
    "keydown",
    (e) => {
      if (e.key === "Escape" && !markMenu.hidden) {
        e.preventDefault();
        e.stopPropagation();
        closeMarkMenu();
      }
    },
    true,
  );
  document.addEventListener("pointerdown", (e) => {
    if (!markMenu.hidden && !markMenu.contains(e.target) && !menuAnchor?.contains(e.target))
      closeMarkMenu(false);
  });
}
