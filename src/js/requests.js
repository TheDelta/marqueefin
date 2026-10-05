// The Requests tab (Seerr): titles asked for but not in the library yet
import { openDetail } from "./detail.js";
import { DATA, REQUESTS, byId, count, grid } from "./dom.js";
import { eyeIcon, nameOf, parts, seasonLabel, watchState } from "./format.js";
import { fmtDate, t } from "./i18n.js";
import { EXT, PLAY } from "./icons.js";
import { esc, searchText } from "./lib.js";

// The season colors: released but not in the library warn, in it ok, partly part
const TONE = {
  ok: "st-available",
  info: "st-airing",
  warn: "st-partial",
  bad: "st-missing",
  muted: "st-tba",
  part: "st-part",
};
const chip = (label, tone, tip, extra = "") => {
  const attr = tip ? ' data-tip="' + esc(tip) + '"' : "";
  return `<span class="st ${TONE[tone]}"${attr}>${esc(label)}${extra}</span>`;
};
// "Approved" is the norm and gets no chip; filled, unlike the release chips
const REQ_STATE = {
  pending: [t("req.awaiting"), "warn"],
  partial: [t("req.partly"), "ok"],
  failed: [t("req.failed"), "bad"],
};
// A request for something partly in the library (e.g. a new season) links to it
const inLibrary = new Map();
DATA.forEach((d) =>
  d.links.forEach((l) => {
    const m = /themoviedb\.org\/(movie|tv)\/(\d+)/.exec(l.url);
    if (m) inLibrary.set((m[1] === "tv" ? "series:" : "movie:") + m[2], d);
  }),
);

// When a requested movie can be had (its digital / disc release, else cinema)
function movieRelease(rel = {}) {
  const d = rel.date ? fmtDate(rel.date) : "";
  if (rel.kind === "released")
    return chip(
      t("req.released"),
      "warn",
      t(rel.what === "digital" ? "req.releasedDigitalTip" : "req.releasedTip", {
        date: d,
      }),
    );
  if (rel.kind === "upcoming")
    return chip(t(rel.what === "digital" ? "req.digital" : "req.cinemaOn", { date: d }), "info");
  if (rel.kind === "cinema") return chip(t("req.cinema"), "muted", t("req.cinemaTip", { date: d }));
  if (rel.kind === "canceled") return chip(t("req.canceled"), "bad");
  return chip(t("req.tba"), "muted", t("req.noDate"));
}

// "S1 Available", "S4 airing, next 2 Oct 2026", "S6 TBA"; lib: the series in the
// library, for the watched eye
function seasonRelease(s, lib) {
  const ls = lib && (lib.seasonList || []).find((x) => x.n === s.n);
  const w = ls && watchState(ls),
    eye = w ? eyeIcon(w, ls.watchedPct) : "";
  const with_ = (...bits) => bits.filter(Boolean).join(", ");
  if (s.kind === "available")
    return chip(
      t("req.sAvailable", { n: s.n }),
      "ok",
      with_(t("req.inLibrary"), s.next && t("req.nextEpisode", { date: fmtDate(s.next) })),
      eye,
    );
  if (s.kind === "partial")
    return chip(
      t("req.sPartial", { n: s.n }),
      "part",
      with_(t("req.partlyInLibrary"), s.missing && t("season.missingEps", { eps: s.missing })),
      eye,
    );
  if (s.kind === "aired") return chip(t("req.sAired", { n: s.n }), "warn", t("req.airedTip"));
  if (s.kind === "airing")
    return chip(
      with_(t("req.sAiring", { n: s.n }), s.date && t("season.next", { date: fmtDate(s.date) })),
      "info",
    );
  if (s.kind === "upcoming") return chip(t("req.sAirs", { n: s.n, date: fmtDate(s.date) }), "info");
  return chip(t("req.sTba", { n: s.n }), "muted", t("req.noAirDate"));
}

// Opens the title in the library: a real button, not a chip
const libButton = (lib) =>
  `<button type="button" class="rq-lib" data-lib="${esc(lib.id)}" data-tip="${esc(t("req.openInLibrary", { title: nameOf(lib) }))}">${PLAY}${esc(t("req.inLibraryButton"))}<span class="chev" aria-hidden="true">›</span></button>`;

function requestRow(r) {
  const [stateLabel, tone] = REQ_STATE[r.state] || [];
  const lib = inLibrary.get(r.type + ":" + r.tmdb);
  const cover = r.poster
    ? `<img class="rq-cover" src="${esc(r.poster)}" alt="" loading="lazy">`
    : '<span class="rq-cover"></span>';
  const seasons = r.seasons ? seasonLabel(r.seasons.map((s) => s.n)) : "";
  const meta = [
    t(r.type === "movie" ? "req.movie" : "req.series"),
    seasons,
    r.requested ? t("req.requested", { date: fmtDate(r.requested) }) : "",
    r.is4k ? "4K" : "",
  ];
  let release;
  if (r.unknown) release = chip(t("req.unavailable"), "muted", t("req.unavailableTip"));
  else
    release = r.seasons
      ? r.seasons.map((s) => seasonRelease(s, lib)).join("")
      : movieRelease(r.release);
  const w = lib && watchState(lib);
  const reqChip = stateLabel
    ? `<span class="st st-fill ${TONE[tone]}">${esc(stateLabel)}</span>`
    : "";
  return `<li class="req">${cover}
      <div class="rq-main">
        <div class="rq-title"><a href="${esc(r.link)}" target="_blank" rel="noopener">${esc(nameOf(r))}${EXT}<span class="vh">${esc(t("req.tmdbNewTab"))}</span></a>${r.year ? `<span class="rq-year">${r.year}</span>` : ""}${w ? eyeIcon(w, lib.watchedPct) : ""}</div>
        <div class="rq-meta">${parts(meta)}</div>
      </div>
      <div class="rq-status">${reqChip}${release}${lib ? libButton(lib) : ""}</div>
    </li>`;
}

export function applyRequests(terms) {
  const list = REQUESTS.filter((r) =>
    terms.every((t) =>
      searchText([r.title, r.titleAlt, r.year].filter(Boolean).join(" ")).includes(t),
    ),
  );
  if (list.length) {
    const ul = document.createElement("ul");
    ul.className = "reqs";
    ul.innerHTML = list.map(requestRow).join("");
    grid.replaceChildren(ul);
  } else grid.innerHTML = `<p class="empty">${esc(t("req.none"))}</p>`;
  count.textContent =
    list.length === REQUESTS.length
      ? t("count.requests", { n: REQUESTS.length })
      : t("count.shown", { shown: list.length, total: REQUESTS.length });
}

export function initRequests() {
  grid.addEventListener("click", (e) => {
    const b = e.target.closest("[data-lib]");
    if (b) openDetail(byId.get(b.dataset.lib));
  });
}
