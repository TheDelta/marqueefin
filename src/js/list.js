// Putting titles on your list: the detail view's switch, your rating, the list bar
import { paintMark } from "./cards.js";
import { $, byId, xdlg } from "./dom.js";
import { nameOf } from "./format.js";
import { apply } from "./grid.js";
import { t } from "./i18n.js";
import { STAR, markIcon } from "./icons.js";
import { syncMarkFilter } from "./filters.js";
import { esc } from "./lib.js";
import { fillExport } from "./list-dialog.js";
import {
  MARK_LABEL,
  markTimes,
  markWhenHtml,
  markedItems,
  marks,
  myRating,
  myRatings,
  saveMarks,
  saveRatings,
  touchMark,
} from "./marks.js";
import { state } from "./state.js";

// The detail view's switch: Wanted | Owned | Watched, and "Remove"
export const markSeg = (it) =>
  `<div class="markseg" data-id="${esc(it.id)}" role="group" aria-label="${esc(t("mark.yourList"))}">` +
  Object.entries(MARK_LABEL)
    .map(
      ([st, label]) =>
        `<button type="button" data-set="${st}" aria-pressed="false">${markIcon(st)}${esc(label)}</button>`,
    )
    .join("") +
  `<button type="button" class="linkbtn unmark" data-set="" hidden>${esc(t("mark.remove"))}</button></div>` +
  `<div class="myratewrap" hidden></div>`;
// Your rating: five stars (row-reverse in CSS, so hovering lights up the ones before)
export const rateHtml = (it) => {
  const r = myRating(it);
  return (
    `<span class="myrate" data-id="${esc(it.id)}" role="radiogroup" aria-label="${esc(t("mark.ratingOf", { title: nameOf(it) }))}">` +
    [5, 4, 3, 2, 1]
      .map(
        (n) =>
          `<button type="button" role="radio" aria-checked="${n === r}" data-rate="${n}"${n <= r ? ' class="on"' : ""} aria-label="${esc(t("mark.stars", { n }))}" data-tip="${esc(n === r ? t("mark.clearRating") : t("mark.stars", { n }))}">${STAR}</button>`,
      )
      .join("") +
    "</span>"
  );
};
// A rating leaves the state's date alone: it says when it was watched, not rated
function setRating(it, n) {
  if (n) myRatings.set(it.id, n);
  else myRatings.delete(it.id);
  saveRatings();
  paintMark(it);
  paintMarkSeg(it);
  if (xdlg.open) fillExport();
}
// A click on a star sets that rating; on the current one clears it
export function initRatingClicks() {
  document.addEventListener("click", (e) => {
    const b = e.target.closest(".myrate [data-rate]");
    if (!b) return;
    const it = byId.get(b.closest(".myrate").dataset.id);
    const n = Number(b.dataset.rate);
    setRating(it, myRatings.get(it.id) === n ? 0 : n);
  });
}
export function paintMarkSeg(it) {
  const seg = $("d").querySelector(".markseg");
  if (!seg || seg.dataset.id !== it.id) return;
  const st = marks.get(it.id) || "";
  seg
    .querySelectorAll("[data-set]:not(.unmark)")
    .forEach((b) => b.setAttribute("aria-pressed", b.dataset.set === st));
  seg.querySelector(".unmark").hidden = !st;
  // "Watched 3 days ago" and, once watched, "Your rating ★★★★☆"
  const rw = $("d").querySelector(".myratewrap");
  const whenHtml = st ? markWhenHtml(it) : "";
  rw.hidden = !whenHtml && st !== "w";
  rw.innerHTML =
    (whenHtml ? `<span class="mwhen">${whenHtml}</span>` : "") +
    (st === "w" ? `<span>${esc(t("mark.yourRating"))}</span>${rateHtml(it)}` : "");
}

// st: "m" / "o" / "w", or "" to take it off the list
export function setMark(it, st) {
  const was = marks.get(it.id) || "";
  if (st) marks.set(it.id, st);
  else marks.delete(it.id);
  if (st && st !== was) touchMark(it.id);
  if (!st) markTimes.delete(it.id);
  if (!st && myRatings.delete(it.id)) saveRatings(); // off the list: rating goes too
  saveMarks();
  paintMark(it);
  paintMarkSeg(it);
  updateTray();
  if (xdlg.open) fillExport();
  if (state.f.mark) apply(); // the title may leave or join what the filter shows
}

// "5 titles on your list (3 wanted, 1 owned, 1 watched)"
export const stateCounts = (items) =>
  Object.keys(MARK_LABEL)
    .map((st) => [st, items.filter((d) => marks.get(d.id) === st).length])
    .filter(([, n]) => n)
    .map(([st, n]) => t("stateCount." + st, { n }))
    .join(", ");

export function updateTray() {
  const items = markedItems(),
    n = items.length;
  $("tray").hidden = n === 0;
  $("tcount").textContent = t("tray.count", { n });
  $("tcount").dataset.tip = stateCounts(items); // "2 wanted, 1 owned, 1 watched"
  syncMarkFilter();
}
