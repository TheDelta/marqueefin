// The cards: one per title (built once; filtering re-orders and detaches them), plus
// one per year a season premiered when seasons are split
import { openDetail } from "./detail.js";
import { DATA, byId } from "./dom.js";
import {
  changedHtml,
  countText,
  nameOf,
  ratingTip,
  seasonLabel,
  watchState,
  watchedHtml,
} from "./format.js";
import { monthYear, num, resText, t, when } from "./i18n.js";
import { EYE, HEART, STAR, markIcon } from "./icons.js";
import { esc, initials, percent, searchText, seasonsStatus } from "./lib.js";
import { setMark } from "./list.js";
import { MARK_LABEL, marks, markWhenText, myRating } from "./marks.js";
import { openMarkMenu } from "./menu.js";
import { isNew } from "./seen.js";

// status / q: whose watched state and quality the poster shows (season cards: their seasons')
export function makeCard(it, sub, gap, onOpen, status = it, q = it.media) {
  const card = document.createElement("div");
  card.className = "card";
  const poster = it.poster
    ? `<img src="${esc(it.poster)}" alt="" loading="lazy" decoding="async">`
    : `<span class="ph" aria-hidden="true">${esc(initials(it.title))}</span>`;
  const gapBadge = gap
    ? `<span class="pgap" aria-hidden="true" data-tip="${esc(t("card.gapTip"))}">${gap}</span>`
    : "";
  // "Added 5 days ago" / "Watched yesterday": only shown with those sort orders
  const watched = it.lastWatched ? watchedHtml("when.watched", it) : "";
  // "New" above "Incomplete" / "Partial", top left
  const topLeft = `<span class="ptl"><span class="pnew" aria-hidden="true">${esc(t("card.new"))}</span>${gapBadge}</span>`;
  const gapText = gap ? `<span class="vh">${esc(t("card.gapHidden"))}</span>` : "";
  card.innerHTML =
    `<button type="button" class="open"><div class="poster">${poster}${topLeft}${posterBadges(it, status, q)}</div><span class="t">${esc(nameOf(it))}</span><span class="y">${esc(sub)}</span><span class="y ya">${changedHtml(it)}</span><span class="y yw">${watched}</span><span class="vh vnew">${esc(t("card.newHidden"))}</span>${gapText}</button>` +
    `<button type="button" class="mark" aria-pressed="false"></button>`;
  card.querySelector(".open").addEventListener("click", onOpen);
  // Not on your list: one click adds it as wanted. On it: a menu to change the state
  card
    .querySelector(".mark")
    .addEventListener("click", (e) =>
      marks.has(it.id) ? openMarkMenu(it, e.currentTarget) : setMark(it, "m"),
    );
  card.classList.toggle("is-new", isNew(it));
  it._els.push(card);
  paintMark(it);
  return card;
}

// 1080p and below are the norm: no badge
const HDR_SHORT = {
  "Dolby Vision": "DV",
  "HDR10+": "HDR10+",
  HDR10: "HDR",
  HLG: "HLG",
};
function qualityChips(q) {
  if (!q) return "";
  const out = [];
  if (["4K", "8K"].includes(q.res))
    out.push(
      `<span class="pq pq-res" data-tip="${esc(t("res.tip", { res: resText(q) }))}">${esc(q.res)}</span>`,
    );
  const hdr = (q.hdr || [])[0];
  if (hdr)
    out.push(
      `<span class="pq pq-hdr" data-tip="${esc(q.hdr.join(", "))}">${esc(HDR_SHORT[hdr] || hdr)}</span>`,
    );
  return out.length ? `<span class="pqs">${out.join("")}</span>` : "";
}

function posterBadges(it, status = it, q = it.media) {
  const b = [];
  if (it.rating)
    b.push(
      `<span class="pb pb-rating" data-tip="${esc(ratingTip(it))}">${STAR}${num(it.rating, 1)}</span>`,
    );
  const w = watchState(status);
  if (w)
    b.push(
      `<span class="pb pb-status ${w.full ? "pb-watched" : "pb-partial"}" data-tip="${esc(w.label)}">${EYE}${w.full ? "" : percent(status.watchedPct) + "%"}</span>`,
    );
  if (status.fav)
    b.push(`<span class="pb pb-status pb-fav" data-tip="${esc(t("favorite"))}">${HEART}</span>`);
  const chips = qualityChips(q) + (b.length ? `<span class="pbadges">${b.join("")}</span>` : "");
  return chips ? `<span class="pbot" aria-hidden="true">${chips}</span>` : "";
}

export function buildCards() {
  DATA.forEach((it) => {
    it._els = [];
    it._el = makeCard(
      it,
      [when(it), countText(it)].filter(Boolean).join(", "),
      it.complete === false ? t("card.incomplete") : "",
      () => openDetail(it),
    );
    const memberTitles = (it.items || []).flatMap((id) => [
      byId.get(id).title,
      byId.get(id).titleAlt,
    ]);
    // What search looks at: both titles, the year, genres, a collection's titles
    it._s = searchText(
      [it.title, it.titleAlt, it.year, ...it.genres, ...memberTitles].filter(Boolean).join(" "),
    );
  });
}

// "Split seasons": one card per year a season premiered (owned seasons only)
export function seasonEntries(it) {
  if (it._split) return it._split;
  const byYear = new Map();
  (it.seasonList || []).forEach((s) => {
    if (s.n > 0 && s.year && ["available", "airing", "partial"].includes(s.status))
      byYear.set(s.year, [...(byYear.get(s.year) || []), s]);
  });
  it._split = [...byYear].map(([year, ss]) => {
    const ns = ss.map((s) => s.n).sort((a, b) => a - b);
    const first = ss
      .map((s) => s.date)
      .filter(Boolean)
      .sort()[0];
    const sub = (first ? monthYear(first, year) + ", " : "") + seasonLabel(ns); // like "Feb 2023" on movies
    const newest = ss.reduce((a, s) => (s.n > a.n ? s : a));
    const el = makeCard(
      it,
      sub,
      ss.some((s) => s.status === "partial") ? t("card.partial") : "",
      () => openDetail(it, false, ns),
      seasonsStatus(ss),
      newest.q,
    );
    return { d: it, year, key: first || year + "-00", el };
  });
  return it._split;
}
export const hasSeasonYears = DATA.some((d) => (d.seasonList || []).some((s) => s.year));

// The card's corner button: empty star, or the state's icon and color
export function paintMark(it) {
  const st = marks.get(it.id) || "";
  it._els.forEach((el) => {
    el.classList.toggle("is-marked", Boolean(st));
    el.dataset.mark = st;
    const b = el.querySelector(".mark");
    // Watched and rated: the eye plus the rating ("4★"), as a small pill
    const rated = myRating(it);
    b.innerHTML = markIcon(st) + (rated ? `<span class="mrt">${rated}${STAR}</span>` : "");
    b.classList.toggle("rated", Boolean(rated));
    b.setAttribute("aria-pressed", Boolean(st));
    b.setAttribute(
      "aria-label",
      st
        ? t("mark.change", { title: nameOf(it), state: MARK_LABEL[st] })
        : t("mark.addTitle", { title: nameOf(it) }),
    );
    // "Watched 3 days ago, rated 4/5 (click to change)"
    const whenText = markWhenText(it);
    const about = [
      whenText ? t("markWhen." + st, { when: whenText }) : MARK_LABEL[st],
      rated ? t("mark.rated", { r: rated }) : "",
    ].filter(Boolean);
    b.dataset.tip = st ? t("mark.tip", { state: about.join(", ") }) : t("mark.add");
  });
}
