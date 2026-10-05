// The header: the summary and tabs, "12 new since 28 Sep 2026", "Updated 2 hours ago"
import { $, DATA, REQUESTS, counts } from "./dom.js";
import { apply } from "./grid.js";
import { I18N, fmtDate, fmtStamp, relTime, t } from "./i18n.js";
import { isoDay } from "./lib.js";
import { isNew, markAllSeen, seenSince } from "./seen.js";
import { state } from "./state.js";

// Hide tabs that would be empty; "13 movies, 4 series and 1 collection" (the export
// wrote it in English)
export function initHeader() {
  $("reqCount").textContent = REQUESTS.length || "";
  $("tabs")
    .querySelectorAll("[data-type]")
    .forEach((b) => {
      if (b.dataset.type !== "all") b.hidden = !counts[b.dataset.type];
    });
  if (Object.values(counts).filter(Boolean).length < 2) $("tabs").hidden = true;
  const summary = [
    ["page.summary.movies", counts.movie],
    ["page.summary.series", counts.series],
    ["page.summary.collections", counts.collection],
  ]
    .filter(([, n]) => n)
    .map(([key, n]) => t(key, { n }));
  if ($("summary"))
    $("summary").textContent = summary.length ? I18N.list(summary) : t("page.summary.empty");
}

// Click: only the new ones; "Mark all as seen" moves the date on
const newToggle = $("newToggle"),
  markSeen = $("markSeen");
function paintNew() {
  const n = DATA.filter(isNew).length,
    since = fmtDate(isoDay(new Date(seenSince())));
  if (!n) state.onlyNew = false;
  newToggle.textContent = n ? t("new.count", { n, date: since }) : t("new.none", { date: since });
  newToggle.disabled = !n;
  newToggle.setAttribute("aria-pressed", Boolean(state.onlyNew));
  markSeen.hidden = !n;
  DATA.forEach((d) => d._els.forEach((el) => el.classList.toggle("is-new", isNew(d))));
}
export function initNewSince() {
  newToggle.addEventListener("click", () => {
    state.onlyNew = !state.onlyNew;
    paintNew();
    apply();
  });
  markSeen.addEventListener("click", () => {
    const n = DATA.filter(isNew).length;
    const ask = t("new.confirm", { n });
    if (!confirm(ask)) return;
    markAllSeen();
    paintNew();
    apply();
  });
  $("newWrap").hidden = false;
  paintNew();
}

// The exact date and time on hover
const updEl = $("updated");
function paintUpdated() {
  const when = new Date(updEl?.getAttribute("datetime"));
  const rel = Number.isNaN(when.getTime()) ? null : relTime(when);
  if (!rel) return; // keeps the plain date written by the export
  updEl.textContent = t("page.updated", { when: rel });
  updEl.dataset.tip = fmtStamp(when);
  updEl.tabIndex = 0; // keyboard users get the tooltip too
}
export function initUpdated() {
  paintUpdated();
  setInterval(paintUpdated, 60000);
}
