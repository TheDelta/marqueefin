// The Filters panel (not saved: a fresh look each visit)
import { $, DATA, fbtn, fpanel, hasMedia } from "./dom.js";
import { activeFilters, apply } from "./grid.js";
import { markedItems } from "./marks.js";
import { state } from "./state.js";

const yFrom = $("yFrom"),
  yTo = $("yTo"),
  rFrom = $("rFrom"),
  rTo = $("rTo");
const qualitySel = $("quality"),
  watchedSel = $("watchedSel"),
  favSel = $("favSel"),
  markSel = $("markSel");
const numberIn = (el) =>
  el.value.trim() === "" || Number.isNaN(Number(el.value)) ? null : Number(el.value);
function readFilters() {
  state.f = {
    yFrom: numberIn(yFrom),
    yTo: numberIn(yTo),
    rFrom: numberIn(rFrom),
    rTo: numberIn(rTo),
    quality: qualitySel.value,
    watched: watchedSel.value,
    fav: favSel.value,
    mark: markSel.value,
  };
  const n = activeFilters();
  $("fcount").textContent = n || "";
  fbtn.classList.toggle("on", n > 0);
  apply();
}
// Collections carry no video info: no quality filter on their tab
export function syncFilters() {
  $("qualityF").hidden = !hasMedia || state.type === "collection";
  if ($("qualityF").hidden && qualitySel.value) {
    qualitySel.value = "";
    readFilters();
  }
}

// "Your list" only once there is one; emptying the list drops the filter
export function syncMarkFilter() {
  $("markF").hidden = !markedItems().length;
  if ($("markF").hidden && markSel.value) {
    markSel.value = "";
    readFilters();
  }
}

export function initFilters() {
  const allYears = DATA.map((d) => d.year).filter(Boolean);
  if (allYears.length) {
    const lo = Math.min(...allYears),
      hi = Math.max(...allYears);
    [yFrom, yTo].forEach((el) => {
      el.min = lo;
      el.max = hi;
    });
    yFrom.placeholder = lo;
    yTo.placeholder = hi;
  }
  $("watchedF").hidden = !DATA.some((d) => d.watched || d.watchedPct);
  $("favF").hidden = !DATA.some((d) => d.fav);
  let ft;
  [yFrom, yTo, rFrom, rTo].forEach((el) =>
    el.addEventListener("input", () => {
      clearTimeout(ft);
      ft = setTimeout(readFilters, 250);
    }),
  );
  [qualitySel, watchedSel, favSel, markSel].forEach((el) =>
    el.addEventListener("change", readFilters),
  );
  $("fReset").addEventListener("click", () => {
    [yFrom, yTo, rFrom, rTo, qualitySel, watchedSel, favSel, markSel].forEach((el) => {
      el.value = "";
    });
    readFilters();
  });
  fbtn.addEventListener("click", () => {
    const open = fbtn.getAttribute("aria-expanded") !== "true";
    fbtn.setAttribute("aria-expanded", open);
    fpanel.hidden = !open;
    if (open) yFrom.focus();
  });
}
