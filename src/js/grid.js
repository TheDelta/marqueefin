// What the grid shows: the tab, search, the menus and the Filters panel, sorted, and
// grouped by year
import { hasSeasonYears, seasonEntries } from "./cards.js";
import { $, DATA, count, genreSel, grid } from "./dom.js";
import { byName, inTab, watchState, watchedDay } from "./format.js";
import { num, t } from "./i18n.js";
import {
  QUALITY_TEST,
  changed,
  dateKey,
  esc,
  inRange,
  makeSorters,
  markFilter,
  searchText,
  triState,
  yearOrder,
} from "./lib.js";
import { marks } from "./marks.js";
import { applyRequests } from "./requests.js";
import { isNew } from "./seen.js";
import { state } from "./state.js";

export function fillGenres() {
  const pool = DATA.filter(inTab);
  const set = new Set();
  pool.forEach((d) => d.genres.forEach((g) => set.add(g)));
  const list = [...set].sort((a, b) => a.localeCompare(b));
  if (!list.includes(state.genre)) state.genre = "";
  genreSel.innerHTML =
    `<option value="">${esc(t("genre.all"))}</option>` +
    list.map((g) => `<option${g === state.genre ? " selected" : ""}>${esc(g)}</option>`).join("");
  genreSel.hidden = list.length === 0;
}

export const sorters = makeSorters(byName);

// Years: a split-season card counts with its own year (see groupByYear)
const yearOk = (year) =>
  (state.f.yFrom === null && state.f.yTo === null) ||
  Boolean(year && inRange(year, state.f.yFrom, state.f.yTo));
function filterOk(d) {
  const f = state.f;
  if (f.rFrom !== null || f.rTo !== null) {
    if (!d.rating || !inRange(d.rating, f.rFrom, f.rTo)) return false;
  }
  if (f.quality && !(d.media && QUALITY_TEST[f.quality](d.media))) return false;
  if (!triState(f.watched, watchState(d)) || !triState(f.fav, d.fav)) return false;
  if (!markFilter(f.mark, marks.get(d.id))) return false;
  // Split-season cards are filtered by year one by one in groupByYear
  return splitting() && d.type === "series" && seasonEntries(d).length
    ? seasonEntries(d).some((e) => yearOk(e.year))
    : yearOk(d.year);
}
// What the grid shows right now, for "Surprise me"
let shown = [];
export const shownTitles = () => shown;

export const activeFilters = () =>
  Object.values(state.f).filter((v) => v !== null && v !== "").length;

export function apply() {
  const terms = searchText(state.q).split(/\s+/).filter(Boolean);
  if (state.type === "requests") {
    shown = [];
    return applyRequests(terms);
  }
  const list = DATA.filter(
    (d) =>
      inTab(d) &&
      (!state.genre || d.genres.includes(state.genre)) &&
      (!state.avail || d.complete === (state.avail === "complete")) &&
      (!state.onlyNew || isNew(d)) &&
      terms.every((t) => d._s.includes(t)) &&
      filterOk(d),
  ).sort(sorters[state.sort]);
  shown = list;
  $("surprise").disabled = !list.length;
  if (!list.length) grid.innerHTML = `<p class="empty">${esc(t("grid.empty"))}</p>`;
  else if (!state.group) grid.replaceChildren(...list.map((d) => d._el));
  else grid.replaceChildren(...groupByYear(list));
  const total = DATA.filter(inTab).length;
  count.textContent =
    list.length === total
      ? t("count.titles", { n: total })
      : t("count.shown", { shown: num(list.length), total: num(total) });
}

// "Split seasons" only means something in the year view, on tabs that show series
export const splitApplies = () =>
  hasSeasonYears && state.group && ["all", "series"].includes(state.type);
// Year view (order: yearOrder). "Recently added" / "Recently watched" group by that date (never watched last) and
// skip season cards, which would all carry their series' date.
const EVENT_DATE = { added: changed, watched: watchedDay };
const splitting = () => state.split && splitApplies() && !EVENT_DATE[state.sort];
function groupByYear(list) {
  const eventDate = EVENT_DATE[state.sort],
    split = splitting();
  const entries = list.flatMap((d) => {
    const seasons =
      split && d.type === "series" ? seasonEntries(d).filter((e) => yearOk(e.year)) : [];
    if (seasons.length) return seasons;
    if (!eventDate) return [{ d, year: d.year, key: dateKey(d), el: d._el }];
    const day = eventDate(d);
    return [{ d, year: Number(day.slice(0, 4)) || null, key: day, el: d._el }];
  });
  entries.sort(yearOrder(state.sort));
  const perYear = new Map();
  entries.forEach((e) => perYear.set(e.year, (perYear.get(e.year) || 0) + 1));
  const out = [];
  let last;
  entries.forEach((e, i) => {
    if (i === 0 || e.year !== last) {
      const h = document.createElement("h2");
      h.className = "yh";
      const none = t(state.sort === "watched" ? "grid.notWatched" : "grid.unknownYear");
      h.innerHTML = `${esc(e.year || none)} <span class="yc">– ${perYear.get(e.year)}</span>`;
      out.push(h);
      last = e.year;
    }
    out.push(e.el);
  });
  return out;
}
