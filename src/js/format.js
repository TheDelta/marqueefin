// Small pieces of HTML and text that several views share
import { CONFIG, FLAGS, byId } from "./dom.js";
import { dayText, fmtDate, fmtStamp, langName, num, t } from "./i18n.js";
import { EYE } from "./icons.js";
import { esc, isoDay, seasonRanges, sortTitle } from "./lib.js";
import { state } from "./state.js";

export const inTab = (d) =>
  state.type === "all" ? d.type !== "collection" : d.type === state.type;

// Search always looks at both titles
export const nameOf = (d) => (state.alt && d.titleAlt) || d.title;
// A to Z by the shown title, without a leading article of its language
export const sortKey = (d) => {
  if (!(state.alt && d.titleAlt)) return d.sort;
  d._sortAlt ??= sortTitle(d.titleAlt, CONFIG.titleLang); // worked out once
  return d._sortAlt;
};
export const byName = (a, b) => sortKey(a).localeCompare(sortKey(b));

export const countText = (it) => {
  if (it.type === "collection")
    return t(
      it.items.every((id) => byId.get(id).type === "movie") ? "count.movies" : "count.titles",
      { n: it.items.length },
    );
  return it.type === "series" && it.seasons ? t("count.seasons", { n: it.seasons }) : "";
};
// "Added 5 days ago"; stamp (UTC), when known, is what the hover shows
export function dateHtml(key, day, stamp) {
  const text = dayText(day),
    tip = stamp ? fmtStamp(stamp) : text !== fmtDate(day) && fmtDate(day);
  const attr = tip ? ' data-tip="' + esc(tip) + '"' : "";
  return `<span${attr}>${esc(t(key, { when: text }))}</span>`;
}
// Last watched (a UTC time) as the viewer's local day
export const watchedDay = (d) => (d.lastWatched ? isoDay(new Date(d.lastWatched)) : "");
export const watchedHtml = (key, d) => dateHtml(key, watchedDay(d), new Date(d.lastWatched));
export const changedHtml = (d) => {
  if (d.updated) return dateHtml("when.updated", d.updated);
  return d.added ? dateHtml("when.added", d.added) : "";
};
// A flag with the language's name on hover; just the name where there's no flag
export const flag = (code) => {
  const name = esc(code ? langName(code) : t("detail.unknownLanguage"));
  return FLAGS[code]
    ? `<img class="flag" src="${FLAGS[code]}" alt="${name}" data-tip="${name}">`
    : `<span class="lang">${name}</span>`;
};
export const moreChip = (names) =>
  `<span class="more" tabindex="0" data-tip="${esc(names.join("\n"))}">+${names.length}<span class="vh"> ${esc(t("detail.more", { names: names.join(", ") }))}</span></span>`;
// Separate spans: CSS draws the dots between them
export const parts = (list) =>
  `<span class="parts">${list
    .filter(Boolean)
    .map((x) => `<span>${esc(x)}</span>`)
    .join("")}</span>`;
export const watchState = (it) => {
  if (it.watched)
    return {
      full: true,
      label: t(it.type === "series" ? "watch.all" : "watch.done"),
    };
  if (it.watchedPct) return { full: false, label: t("watch.pct", { pct: it.watchedPct }) };
  return null;
};
// A collection's rating is its titles' average
export const ratingTip = (it) =>
  it.ratingOf
    ? t("rating.average", { n: it.ratingOf })
    : t("rating.outOf10", { rating: num(it.rating, 1) });
// "Seasons 1–3, 5"
export const seasonLabel = (ns) => t("card.seasons", { n: ns.length, list: seasonRanges(ns) });
// Eye for a watched (or started) title or season, e.g. in a request row
export function eyeIcon(w, pct) {
  return `<span class="su ${w.full ? "su-watched" : "su-partial"}" data-tip="${esc(w.label)}">${EYE}${w.full ? "" : pct + "%"}<span class="vh">${esc(w.label)}</span></span>`;
}
export function thumb(it) {
  return it.poster
    ? `<img src="${esc(it.poster)}" alt="" loading="lazy">`
    : '<span class="mth"></span>';
}
