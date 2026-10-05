// The detail dialog, links to single titles (#item=<id>) and copying
import { $, CONFIG, byId, dlg, partOf } from "./dom.js";
import {
  countText,
  dateHtml,
  eyeIcon,
  flag,
  moreChip,
  nameOf,
  parts,
  ratingTip,
  thumb,
  watchState,
  watchedHtml,
} from "./format.js";
import {
  fmtDate,
  fmtRate,
  fmtSize,
  langName,
  monthYear,
  num,
  resText,
  runtime,
  t,
  when,
} from "./i18n.js";
import { CHECK, EXT, EYE, HEART, LINK, PLAY, STAR } from "./icons.js";
import { esc, foldLangs, fskAge, newestFirst, years } from "./lib.js";
import { markSeg, paintMarkSeg, setMark } from "./list.js";
import { isNew } from "./seen.js";
import { state } from "./state.js";

// e.g. ["4K Dolby Vision", "38.2 GB"]
function seasonQuality(q) {
  if (!q) return [];
  const hdr = q.hdr ? " " + q.hdr[0] : "";
  return [q.res && resText(q) + hdr, q.size && fmtSize(q.size)].filter(Boolean);
}

// Jellyfin's default names translated; custom ones ("Book One: Water") stay
const seasonName = (s) => {
  if (!s.name || /^Season \d+$/.test(s.name)) return t("season.name", { n: s.n });
  return s.name === "Specials" ? t("season.specials") : s.name;
};

function seasonRow(s, highlight) {
  const label = t("season." + s.status);
  const bits = [];
  if (s.status === "tba")
    bits.push(s.next ? t("season.starts", { date: fmtDate(s.next) }) : t("season.noDate"));
  else {
    // Airing: out of the whole season. Otherwise out of what has aired, since
    // upcoming episodes aren't missing.
    const outOf = s.status === "airing" ? s.total : s.total - (s.upcoming || 0);
    bits.push(
      s.have >= outOf
        ? t("count.episodes", { n: s.have })
        : t("count.episodesOf", {
            have: s.have,
            total: t("count.episodes", { n: outOf }),
          }),
      ...seasonQuality(s.q),
    );
  }
  if (s.missing) bits.push(t("season.missingEps", { eps: s.missing }));
  if (s.upcoming && s.status !== "tba")
    bits.push(
      [
        t("season.upcoming", { n: s.upcoming }),
        s.next && t("season.next", { date: fmtDate(s.next) }),
      ]
        .filter(Boolean)
        .join(", "),
    );
  const aired = s.date ? `<span class="sdt">${esc(monthYear(s.date))}</span>` : "";
  return `<li${highlight?.includes(s.n) ? ' class="hl"' : ""}><b>${esc(seasonName(s))}</b>${aired}<span class="st st-${s.status}">${esc(label)}</span>${seasonUser(s)}<span class="sd">${parts(bits)}</span></li>`;
}

// Eye (watched / how far) and heart (favorite) for one season
function seasonUser(s) {
  const w = watchState(s);
  return (
    (w ? eyeIcon(w, s.watchedPct) : "") +
    (s.fav
      ? `<span class="su su-fav" data-tip="${esc(t("favorite"))}">${HEART}<span class="vh">${esc(t("favorite"))}</span></span>`
      : "")
  );
}

// FSK in its label colors (fskAge), anything else neutral
function certBadge(cert) {
  const fsk = fskAge(cert);
  if (!fsk) return `<li class="fact cert">${esc(cert)}</li>`;
  return `<li class="fact cert fsk${fsk.age}" data-tip="${esc(t("cert.ages", { n: fsk.age }))}">${esc(fsk.label)}</li>`;
}

// The 10-point score as it is, not converted to five stars
function facts(it) {
  const out = [];
  const y = when(it),
    len = it.type === "movie" ? runtime(it.runtime) : countText(it);
  if (y) out.push(`<li class="fact">${esc(y)}</li>`);
  if (len) out.push(`<li class="fact">${esc(len)}</li>`);
  if (it.cert) out.push(certBadge(it.cert));
  if (it.rating)
    out.push(
      `<li class="fact rating" data-tip="${esc(ratingTip(it))}">${STAR}${num(it.rating, 1)}<span class="vh">${esc(t("rating.outOf10Hidden"))}</span></li>`,
    );
  return out.length ? `<ul class="facts">${out.join("")}</ul>` : "";
}

// Under the cover: watched (and when), favorite, added, updated
function sideFacts(it) {
  const out = [],
    w = watchState(it);
  if (isNew(it)) out.push(`<li class="fact newfact">${esc(t("detail.newSince"))}</li>`);
  if (w) out.push(`<li class="fact ${w.full ? "watched" : "partial"}">${EYE}${esc(w.label)}</li>`);
  if (it.lastWatched)
    out.push(`<li class="fact added">${watchedHtml("when.lastWatched", it)}</li>`);
  if (it.fav) out.push(`<li class="fact fav">${HEART}${esc(t("favorite"))}</li>`);
  if (it.added) out.push(`<li class="fact added">${dateHtml("when.added", it.added)}</li>`);
  if (it.updated) out.push(`<li class="fact added">${dateHtml("when.updated", it.updated)}</li>`);
  return out.length ? `<ul class="side">${out.join("")}</ul>` : "";
}

// For series: what most episodes have ("Mostly 1080p")
function techBadges(m) {
  if (!m) return "";
  const b = [];
  if (m.res) b.push(`<li class="fact res">${esc(resText(m))}</li>`);
  (m.hdr || []).forEach((h) => b.push(`<li class="fact hdr">${esc(h)}</li>`));
  if (m.codec)
    b.push(
      `<li class="fact tech">${esc(m.codec)}${m.bits ? " " + esc(t("detail.bits", { n: m.bits })) : ""}</li>`,
    );
  if (m.audio) b.push(`<li class="fact tech">${esc(m.audio)}</li>`);
  return b.length
    ? `<ul class="facts" aria-label="${esc(t("detail.videoAudio"))}">${b.join("")}</ul>`
    : "";
}

// Languages other than the main ones (--main-languages) fold into "+2" (foldLangs)
const trackText = ([, ch, fmt, commentary]) =>
  [ch, fmt].filter(Boolean).join(" ") + (commentary ? " " + t("detail.commentary") : "");
function audioTracks(tracks) {
  const other = new Set(foldLangs([...new Set(tracks.map((x) => x[0]))], CONFIG.mainLangs));
  const track = (x) => `<span class="trk">${flag(x[0])}${esc(trackText(x))}</span>`;
  const rest = tracks.filter((x) => other.has(x[0]));
  const more = rest.length
    ? `<span class="trk">${moreChip(rest.map((x) => langName(x[0]) + " " + trackText(x)))}</span>`
    : "";
  return (
    tracks
      .filter((x) => !other.has(x[0]))
      .map(track)
      .join("") + more
  );
}
function subtitleFlags(langs) {
  const other = foldLangs(langs, CONFIG.mainLangs);
  const more = other.length ? moreChip(other.map(langName)) : "";
  return `<span class="flags">${langs
    .filter((l) => !other.includes(l))
    .map(flag)
    .join("")}${more}</span>`;
}

// Languages and file details, below the description
function specs(m) {
  if (!m) return "";
  const rows = [];
  // Values are HTML: data goes through esc() / flag()
  if (m.tracks) rows.push([t("detail.audio"), audioTracks(m.tracks)]);
  if (m.subLangs) rows.push([t("detail.subtitles"), subtitleFlags(m.subLangs)]);
  const file = [
    m.episodes ? t("count.episodes", { n: m.episodes }) : "",
    m.container,
    m.size ? fmtSize(m.size) : "",
    !m.episodes && m.bitrate ? fmtRate(m.bitrate) : "",
    m.versions ? t("count.versions", { n: m.versions }) : "",
  ].filter(Boolean);
  if (file.length) rows.push([t(m.episodes ? "detail.files" : "detail.file"), parts(file)]);
  const items = rows.map(([k, v]) => `<dt>${esc(k)}</dt><dd>${v}</dd>`).join("");
  return items ? `<dl class="specs">${items}</dl>` : "";
}

function collLink(c) {
  const sub = parts([countText(c), years(c)]);
  return (
    `<button type="button" class="collink" data-open="${esc(c.id)}">${thumb(c)}` +
    `<span class="cl"><small>${esc(t("detail.partOf"))}</small><b>${esc(nameOf(c))}</b><span class="y">${sub}</span></span>` +
    `<span class="chev" aria-hidden="true">›</span></button>`
  );
}

// A title in a collection: poster, title, year and length; rating and watched on the right
function memberRow(m) {
  const sub = [years(m), m.type === "movie" ? runtime(m.runtime) : countText(m)]
    .filter(Boolean)
    .join(", ");
  const w = watchState(m);
  const side =
    (w ? eyeIcon(w, m.watchedPct) : "") +
    (m.rating
      ? `<span class="mrate">${STAR}${num(m.rating, 1)}<span class="vh">${esc(t("rating.outOf10Hidden"))}</span></span>`
      : "");
  return `<li><button type="button" class="member" data-open="${esc(m.id)}">${thumb(m)}<span class="mt"><b>${esc(nameOf(m))}</b><span class="y">${esc(sub)}</span></span><span class="mside">${side}</span></button></li>`;
}

// The other title under the heading; main titles are taken as English
function altTitle(it) {
  if (!it.titleAlt) return "";
  const lang = state.alt ? "en" : CONFIG.titleLang;
  const label = t("detail.altTitle", { language: langName(lang) });
  return `<p class="alttitle">${esc(label)}<span lang="${esc(lang)}">${esc(state.alt ? it.title : it.titleAlt)}</span></p>`;
}

// Jumping between a title and its collection keeps a trail, so "Back" works
const trail = [];
let current = null;

export function openDetail(it, keepTrail, highlight) {
  if (!keepTrail) trail.length = 0;
  current = it;
  const prev = trail.at(-1);
  const seasons = it.seasonList?.length
    ? `<h3>${esc(t("detail.seasons"))}</h3><ul class="seasons">${newestFirst(it.seasonList)
        .map((s) => seasonRow(s, highlight))
        .join("")}</ul>`
    : "";
  const members =
    it.type === "collection"
      ? `<h3>${esc(t("detail.inCollection"))}</h3><ul class="members">${it.items.map((id) => memberRow(byId.get(id))).join("")}</ul>`
      : "";
  const colls = (partOf.get(it.id) || []).map(collLink).join("");
  const genreItems = it.genres.map((g) => `<li>${esc(g)}</li>`).join("");
  // The databases as links; Jellyfin itself (--public-url) as a button
  const newTab = `<span class="vh">${esc(t("detail.newTab"))}</span>`;
  const links = it.links
    .map((l) =>
      l.label === "Jellyfin"
        ? `<a class="btn jfbtn" href="${esc(l.url)}" target="_blank" rel="noopener">${PLAY}${esc(t("detail.openJellyfin"))}${EXT}${newTab}</a>`
        : `<a href="${esc(l.url)}" target="_blank" rel="noopener">${esc(l.label)}${EXT}${newTab}</a>`,
    )
    .join("");
  $("d").innerHTML = `
      <button class="close" type="button" aria-label="${esc(t("page.close"))}">×</button>
      <div class="dcol">
        ${it.poster ? `<img src="${esc(it.poster)}" alt="${esc(t("detail.poster", { title: nameOf(it) }))}">` : '<div class="dph"></div>'}
        ${sideFacts(it)}
      </div>
      <div class="dmain">
        ${prev ? `<button type="button" class="back" data-back>‹ ${esc(nameOf(prev))}</button>` : ""}
        <div class="titlerow">
          <h2 id="d-title">${esc(nameOf(it))}</h2>
          <button type="button" class="iconbtn copylink" aria-label="${esc(t("detail.copyLinkTo", { title: nameOf(it) }))}" data-tip="${esc(t("detail.copyLink"))}">${LINK}</button>
          <span class="copied" role="status"></span>
        </div>
        ${altTitle(it)}
        ${facts(it)}
        ${techBadges(it.media)}
        ${genreItems ? `<ul class="genres">${genreItems}</ul>` : ""}
        ${colls}
        ${it.overview ? `<p class="ov">${esc(it.overview)}</p>` : ""}
        ${links ? `<div class="links">${links}</div>` : ""}
        <section class="yourlist" aria-labelledby="d-list">
          <h3 id="d-list">${esc(t("mark.yourList"))}</h3>
          <div class="actions">${markSeg(it)}</div>
        </section>
        ${specs(it.media)}
        ${seasons}
        ${members}
      </div>`;
  $("d")
    .querySelector(".markseg")
    .addEventListener("click", (e) => {
      const b = e.target.closest("[data-set]");
      if (b) setMark(it, b.dataset.set);
    });
  paintMarkSeg(it);
  $("d")
    .querySelector(".close")
    .addEventListener("click", () => dlg.close());
  $("d")
    .querySelector(".copylink")
    .addEventListener("click", (e) => copyLink(it, e.currentTarget));
  setHash(it.id);
  if (!dlg.open) dlg.showModal(); // already open when jumping collection <-> member
  dlg.scrollTop = 0;
  const hl = $("d").querySelector(".seasons .hl");
  if (hl) hl.scrollIntoView({ block: "center" });
}

// ---- Links to single titles: #item=<id>, without history entries ----
const hashId = () => (/[#&]item=([0-9a-f]+)/i.exec(location.hash) || [])[1];
function setHash(id) {
  const url = location.pathname + location.search + (id ? "#item=" + id : "");
  try {
    history.replaceState(null, "", url);
  } catch {
    location.replace(id ? "#item=" + id : "#");
  } // e.g. file:// in some browsers
}
export function openFromHash() {
  const it = byId.get(hashId());
  if (it && it !== current) openDetail(it);
}

export async function copyToClipboard(text) {
  // The Clipboard API can sit on a permission prompt forever, so it gets half a second
  const timeout = new Promise((_, fail) => setTimeout(fail, 500));
  try {
    await Promise.race([navigator.clipboard.writeText(text), timeout]);
    return;
  } catch {
    /* not allowed or no answer: fall back below */
  }
  const ta = Object.assign(document.createElement("textarea"), {
    value: text,
  });
  document.body.append(ta);
  ta.select();
  document.execCommand("copy"); // NOSONAR: deprecated, but the one fallback where the Clipboard API isn't allowed
  ta.remove();
}
async function copyLink(it, btn) {
  await copyToClipboard(location.href.split("#")[0] + "#item=" + it.id);
  btn.innerHTML = CHECK;
  btn.classList.add("done");
  btn.nextElementSibling.textContent = t("detail.linkCopied");
  setTimeout(() => {
    btn.innerHTML = LINK;
    btn.classList.remove("done");
    btn.nextElementSibling.textContent = "";
  }, 2000);
}

export function initDetail() {
  $("d").addEventListener("click", (e) => {
    const open = e.target.closest("[data-open]"),
      back = e.target.closest("[data-back]");
    if (open) {
      trail.push(current);
      openDetail(byId.get(open.dataset.open), true);
    } else if (back) openDetail(trail.pop(), true);
  });
  dlg.addEventListener("close", () => {
    trail.length = 0;
    current = null;
    setHash(null);
  });
  addEventListener("hashchange", openFromHash);
}
