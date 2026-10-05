// The page's logic that doesn't touch the DOM; tests/js/ test it in Node.
export const esc = (s) =>
  String(s ?? "").replace(
    /[&<>"']/g,
    (c) =>
      ({
        "&": "&amp;",
        "<": "&lt;",
        ">": "&gt;",
        '"': "&quot;",
        "'": "&#39;",
      })[c],
  );
export const pad = (n) => String(n).padStart(2, "0");
// "pokemon" finds "Pokémon", "strasse" "Straße"
export const searchText = (s) =>
  String(s ?? "")
    .normalize("NFD")
    .replace(/\p{M}/gu, "")
    .replaceAll("ß", "ss")
    .toLowerCase();

// ---- Titles ----
// For A to Z, as Jellyfin's sort names do for the main titles. Elided ones end in '.
export const ARTICLES = {
  en: ["the", "a", "an"],
  de: ["der", "die", "das", "ein", "eine"],
  fr: ["le", "la", "les", "l'", "un", "une"],
  es: ["el", "la", "los", "las", "un", "una"],
  it: ["il", "lo", "la", "i", "gli", "le", "l'", "un", "uno", "una", "un'"],
  pt: ["o", "a", "os", "as", "um", "uma"],
  nl: ["de", "het", "een"],
};
export const sortTitle = (t, lang = "en") => {
  const low = t.toLowerCase();
  for (const a of ARTICLES[lang.split("-")[0]] || []) {
    const lead = a.endsWith("'") ? a : a + " ";
    if (low.startsWith(lead) && low.length > lead.length) return low.slice(lead.length);
  }
  return low;
};
export const years = (it) => {
  if (it.type === "movie") return it.year ? String(it.year) : "";
  if (!it.year) return "";
  if (it.status === "Continuing") return it.year + "–";
  if (it.endYear && it.endYear !== it.year) return it.year + "–" + it.endYear;
  return String(it.year);
};
export const initials = (t) =>
  t
    .split(/\s+/)
    .slice(0, 3)
    .map((w) => w[0])
    .join("")
    .toUpperCase();

// ---- Sorting ----
// The sort menu's orders; byName (A to Z by the shown title) breaks ties
export const makeSorters = (byName) => ({
  title: byName,
  added: (a, b) => changed(b).localeCompare(changed(a)) || byName(a, b),
  new: (a, b) => dateKey(b).localeCompare(dateKey(a)) || byName(a, b),
  old: (a, b) => (dateKey(a) || "9999").localeCompare(dateKey(b) || "9999") || byName(a, b),
  rating: (a, b) => (b.rating || 0) - (a.rating || 0) || byName(a, b),
  // Last watched first; never watched after that, A to Z
  watched: (a, b) => (b.lastWatched || "").localeCompare(a.lastWatched || "") || byName(a, b),
});
// The year view's entries ({year, key}): no year last, newest year first ("old":
// oldest). Within a year the date orders sort by date (key); the others keep the sort
// menu's order, since the sort is stable.
export const yearOrder = (sort) => {
  const dir = sort === "old" ? 1 : -1;
  const byDate = ["new", "old", "added", "watched"].includes(sort);
  return (a, b) =>
    !a.year - !b.year ||
    (a.year && b.year ? dir * (a.year - b.year) : 0) ||
    (byDate ? dir * a.key.localeCompare(b.key) : 0);
};

// randomIndex(n): 0 to n - 1, from the browser's crypto source, every index equally
// likely: draws from the top that would favor the low indexes are thrown away
export const randomIndex = (n) => {
  const limit = 2 ** 32 - (2 ** 32 % n);
  const draw = new Uint32Array(1);
  do {
    crypto.getRandomValues(draw);
  } while (draw[0] >= limit);
  return draw[0] % n;
};
// "Surprise me": a random entry, not the one picked last time when there's a choice
export const pickRandom = (list, last, index = randomIndex) => {
  const pool = list.length > 1 ? list.filter((x) => x !== last) : list;
  return pool.length ? pool[index(pool.length)] : undefined;
};

// convert to safe percent value
export const percent = (value) => Math.round(Number(value) || 0);

// ---- Seasons ----
// [1, 2, 3, 5] -> "1–3, 5"
export const seasonRanges = (ns) => {
  const parts = [];
  let i = 0;
  while (i < ns.length) {
    let j = i;
    while (j + 1 < ns.length && ns[j + 1] === ns[j] + 1) j++;
    parts.push(i === j ? ns[i] : ns[i] + "–" + ns[j]);
    i = j + 1;
  }
  return parts.join(", ");
};
// Newest season at the top, season 1 at the bottom, specials below that
export const newestFirst = (seasons) =>
  [...seasons].sort((a, b) => (a.n === 0) - (b.n === 0) || b.n - a.n);
// Several seasons on one card: watched when all are, else their average; a favorite
// when any is
export const seasonsStatus = (ss) => {
  const pct = Math.round(
    ss.reduce((sum, s) => sum + (s.watched ? 100 : s.watchedPct || 0), 0) / ss.length,
  );
  return {
    watched: ss.every((s) => s.watched),
    watchedPct: pct < 100 ? pct : 0,
    fav: ss.some((s) => s.fav),
  };
};

// ---- Age ratings ----
// German ones (FSK) get their label colors: "FSK 12", "DE-16", "fsk0", "12+" ->
// {age, label}; anything else (PG-13, TV-MA) null
export const fskAge = (cert) => {
  const text = cert.trim();
  const age = /^(?:FSK|DE)?[\s\-/]*(0|6|12|16|18)\+?$/i.exec(text);
  if (!age) return null;
  return { age: Number(age[1]), label: /^(FSK|DE)/i.test(text) ? "FSK " + age[1] : text };
};

// ---- Dates ----
// "YYYY-MM-DD", already local, formatted by hand: no Date parsing, no time zone shifts.
// A title with only a year sorts after the dated ones of that year
export const dateKey = (d) => d.released || (d.year ? d.year + "-00" : "");
export const RECENT_DAYS = 21;
export const isoDay = (d) => `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`;
const dayNum = (s) =>
  Date.UTC(Number(s.slice(0, 4)), Number(s.slice(5, 7)) - 1, Number(s.slice(8, 10))) / 864e5;
// Latest change: new episodes / new collection members ("updated"), else when added
export const changed = (d) => d.updated || d.added || "";

// ---- Languages ----
// More than 3: only the main languages and unknown ('') stay, the rest fold into "+2"
export const foldLangs = (codes, main = ["en"]) =>
  codes.length > 3 ? codes.filter((c) => c && !main.includes(c)) : [];

// ---- Filters ----
export const inRange = (v, from, to) => (from === null || v >= from) && (to === null || v <= to);
export const QUALITY_TEST = {
  "4K": (m) => ["4K", "8K"].includes(m.res),
  "1080p": (m) => m.res === "1080p",
  "720p": (m) => m.res === "720p",
  SD: (m) => m.res === "SD",
  hdr: (m) => (m.hdr || []).length > 0,
  dv: (m) => (m.hdr || []).includes("Dolby Vision"),
};
// The Filters panel's "Your list": "" any, "on" / "off" the list, or one state
export const markFilter = (mode, st) => {
  if (mode === "on") return Boolean(st);
  if (mode === "off") return !st;
  return !mode || st === mode;
};
// "Watched" includes partly watched (a series in progress, a movie stopped half way)
export const triState = (mode, on) => !mode || (mode === "only") === Boolean(on);

// ---- The viewer's list: states and the text format ----
// Tags and CSV stay English in every language, so a list imports anywhere
export const MARK_STATES = ["m", "o", "w"];
export const CSV_STATE = { m: "wanted", o: "owned", w: "watched" };
export const CSV_CODE = { wanted: "m", owned: "o", watched: "w" };
// "2026-09-30 14:05" (local time) for the copy text, which Import reads back
export const stampText = (at) => `${isoDay(at)} ${pad(at.getHours())}:${pad(at.getMinutes())}`;
// "[id]", "[id|o]", "[id|w4|2026-09-30 14:05]" (watched, rated 4, local time)
export const listTag = (id, st, rating, at) => {
  const code = st && (st !== "m" || at) ? "|" + st + (rating || "") : "";
  return `[${id}${code}${at ? "|" + stampText(at) : ""}]`;
};
// "2026-09-30 14:05" (local) -> ISO UTC, "" when it isn't a time
export const isoFrom = (local) => {
  const t = local ? new Date(local.replace(" ", "T")) : null;
  return t && !Number.isNaN(t.getTime()) ? t.toISOString() : "";
};
// A cell of the CSV: quoted when it has a comma, a quote or a line break
const csvCell = (v) => {
  v = String(v ?? "");
  return /[",\r\n]/.test(v) ? '"' + v.replaceAll('"', '""') + '"' : v;
};
function listCsv(items, ids) {
  const row = (d) =>
    (ids ? [d.id] : [])
      .concat([CSV_STATE[d.state], d.rating || "", d.updated, d.type, d.name, d.year, d.link])
      .map(csvCell)
      .join(",");
  return [(ids ? "id," : "") + "state,rating,updated,type,title,year,link", ...items.map(row)].join(
    "\n",
  );
}
/**
 * The list as text to copy; Import reads it back. items: the marked titles, sorted:
 * {id, type, name, year, years ("2024–"), link, state, rating, at (Date | null),
 * updated (ISO), members: [{name, years, link}]}. o: {fmt ("links" | "plain" | "csv"),
 * ids, wantedOnly, heads: {movie, series, collection}, stateText(state, at)}.
 */
export function listText(items, o) {
  items = items.filter((d) => !o.wantedOnly || d.state === "m");
  if (o.fmt === "csv") return listCsv(items, o.ids);
  // "[id|w4|2026-09-30 14:05] Title (Year) link": the tag makes it importable.
  // Without ids: "Title (Year) (watched 30 Sep 2026, ★4/5)". Collection members
  // get no tag: they're context, not on the list.
  const entry = (d, member) => {
    const stars = !member && d.rating ? `★${d.rating}/5` : "";
    let state = "";
    if (!member && !o.ids && d.state && (d.state !== "m" || d.at)) {
      state = ` (${[o.stateText(d.state, d.at), stars].filter(Boolean).join(", ")})`;
    } else if (stars) state = " " + stars;
    return [
      o.ids && !member ? listTag(d.id, d.state, d.rating, d.at) : "",
      d.name + (d.years ? ` (${d.years})` : "") + state,
      o.fmt === "links" ? d.link : "",
    ]
      .filter(Boolean)
      .join(" ");
  };
  // A marked collection lists what's in it, indented underneath
  const line = (d) =>
    [entry(d, false), ...(d.members || []).map((m) => "    " + entry(m, true))].join("\n");
  const groups = ["movie", "series", "collection"]
    .map((type) => [o.heads[type], items.filter((d) => d.type === type)])
    .filter(([, list]) => list.length);
  if (groups.length > 1)
    return groups.map(([head, list]) => [head, ...list.map(line)].join("\n")).join("\n\n");
  return items.map(line).join("\n");
}

// Your list and someone else's (Maps id -> {state, rating}), grouped by what you
// both want, who has (or saw) what the other wants, and what's on one list only
export function compareLists(mine, theirs) {
  const g = {
    bothWant: [],
    theyWant: [],
    youWant: [],
    bothWatched: [],
    bothHave: [],
    onlyTheirs: [],
    onlyYours: [],
  };
  for (const [id, them] of theirs) {
    const you = mine.get(id);
    if (!you) g.onlyTheirs.push(id);
    else if (them.state === "m" && you.state === "m") g.bothWant.push(id);
    else if (them.state === "m") g.theyWant.push(id);
    else if (you.state === "m") g.youWant.push(id);
    else if (them.state === "w" && you.state === "w") g.bothWatched.push(id);
    else g.bothHave.push(id);
  }
  for (const id of mine.keys()) if (!theirs.has(id)) g.onlyYours.push(id);
  return g;
}

// ---- The list as a link ----
// "#list=" and the list in base64url: a version byte (1), then per title the first 8
// bytes of its id, a byte with the state (bits 0-1: m, o, w), the rating (bits 2-4)
// and whether a time follows (bit 5), and that time in minutes since 2020 (4 bytes).
// About 18 characters a title, so a long list still fits in a message.
const LINK_EPOCH = Date.UTC(2020, 0, 1);
const toBase64Url = (bytes) => {
  let bin = "";
  for (const b of bytes) bin += String.fromCodePoint(b);
  return btoa(bin).replaceAll("+", "-").replaceAll("/", "_").replaceAll("=", ""); // "=" only pads
};
/** items: [{id, state, rating, at (Date | null)}] */
export function encodeList(items) {
  const bytes = [1];
  for (const { id, state, rating, at } of items) {
    for (let i = 0; i < 16; i += 2) bytes.push(Number.parseInt(id.slice(i, i + 2), 16));
    const mins = at ? Math.max(0, Math.round((at.getTime() - LINK_EPOCH) / 6e4)) : 0;
    bytes.push(MARK_STATES.indexOf(state) | ((rating || 0) << 2) | (mins ? 32 : 0));
    if (mins) bytes.push(mins >>> 24, (mins >>> 16) & 255, (mins >>> 8) & 255, mins & 255);
  }
  return toBase64Url(bytes);
}
/** [{prefix (the id's first 16 hex digits), state, rating, at (ISO or "")}], or null
 * when the text isn't such a list (e.g. a link cut off by a messenger) */
export function decodeList(code) {
  let bin;
  try {
    bin = atob(code.replaceAll("-", "+").replaceAll("_", "/"));
  } catch {
    return null;
  }
  const byte = (i) => bin.codePointAt(i);
  if (byte(0) !== 1) return null;
  const out = [];
  let i = 1;
  while (i + 9 <= bin.length) {
    let prefix = "";
    for (let k = 0; k < 8; k++) prefix += pad(byte(i + k).toString(16));
    const flags = byte(i + 8);
    const state = MARK_STATES[flags & 3],
      rating = (flags >> 2) & 7;
    i += 9;
    let at = "";
    if (flags & 32) {
      if (i + 4 > bin.length) return null;
      const mins = byte(i) * 2 ** 24 + byte(i + 1) * 65536 + byte(i + 2) * 256 + byte(i + 3);
      at = new Date(LINK_EPOCH + mins * 6e4).toISOString();
      i += 4;
    }
    if (!state || rating > 5) return null;
    out.push({ prefix, state, rating, at });
  }
  return i === bin.length ? out : null;
}

// id -> [state, rating (0 = none), ISO time or ""], from tags and from CSV rows
// (rating and updated are optional, so "id,state" is enough)
export function parseList(text) {
  const found = new Map();
  const tag = /\[([0-9a-f]{32})(?:\|([mow])([1-5])?(?:\|(\d{4}-\d\d-\d\d[ T]\d\d:\d\d))?)?\]/gi;
  for (const m of text.matchAll(tag))
    found.set(m[1].toLowerCase(), [(m[2] || "m").toLowerCase(), Number(m[3] || 0), isoFrom(m[4])]);
  const csv =
    /^([0-9a-f]{32}),(wanted|owned|watched),(?:([1-5])?,)?(?:(\d{4}-\d\d-\d\dT[\d:.]+Z)?,)?/gim;
  for (const m of text.matchAll(csv))
    found.set(m[1].toLowerCase(), [CSV_CODE[m[2].toLowerCase()], Number(m[3] || 0), m[4] || ""]);
  return found;
}

// ---- Translations ----
// prefs: ["de-AT", "en"]; available: ["en", "de"]
export function pickLanguage(prefs, available, fallback = "en") {
  for (const p of prefs || []) {
    const base = String(p).toLowerCase().split("-")[0];
    if (available.includes(base)) return base;
  }
  return available.includes(fallback) ? fallback : available[0];
}

// Switching the language reloads with `?lang=`
// (storage written right before a reload isn't always there yet)
// the new page takes it out again
export const withLang = (href, lang) => {
  const url = new URL(href);
  url.searchParams.set("lang", lang);
  return url.href;
};
/** {lang, href}: the language a URL carries ("" for none) and the URL without it. */
export function langFromUrl(href) {
  const url = new URL(href);
  const lang = url.searchParams.get("lang") || "";
  url.searchParams.delete("lang");
  return { lang, href: url.href };
}

// Missing keys fall back to English; plural texts are {one, other} objects
export function createI18n(catalogs, lang) {
  const en = catalogs.en || {};
  const cat = catalogs[lang] || en;
  const intl = cat._intl || lang;
  const safe = (make) => {
    try {
      return make();
    } catch {
      return null;
    }
  };
  const plurals = safe(() => new Intl.PluralRules(intl));
  const rtf = safe(() => new Intl.RelativeTimeFormat(intl, { numeric: "auto" }));
  const names = safe(() => new Intl.DisplayNames([intl], { type: "language" }));
  const lists = safe(() => new Intl.ListFormat(intl, { type: "conjunction" }));
  const raw = (key) => cat[key] ?? en[key];

  // 7.5 -> "7.5" / "7,5"; digits: fixed decimals
  const num = (x, digits) =>
    Number(x).toLocaleString(
      intl,
      digits === undefined ? {} : { minimumFractionDigits: digits, maximumFractionDigits: digits },
    );
  const fill = (text, vars) =>
    text.replace(/\{(\w+)\}/g, (m, k) => {
      if (!(k in vars)) return m;
      return k === "n" && typeof vars.n === "number" ? num(vars.n) : String(vars[k]);
    });
  function t(key, vars = {}) {
    let v = raw(key) ?? key;
    if (v && typeof v === "object") v = v[plurals?.select(vars.n ?? 0)] ?? v.other;
    return fill(String(v), vars);
  }

  const months = raw("_months") || [];
  const monthOf = (s) => months[Number(s.slice(5, 7)) - 1] || "";
  const fmtDate = (s) =>
    fill(raw("_date") || "{d} {mon} {y}", {
      d: Number(s.slice(8, 10)),
      mon: monthOf(s),
      y: s.slice(0, 4),
    });
  const monthYear = (s, y = s.slice(0, 4)) =>
    fill(raw("_monthYear") || "{mon} {y}", { mon: monthOf(s), y });
  // "today", "yesterday", "5 days ago", "2 weeks ago"; null when older than RECENT_DAYS
  function relDay(s, now = new Date()) {
    const days = Math.round(dayNum(isoDay(now)) - dayNum(s));
    if (!rtf || days < 0 || days > RECENT_DAYS) return null;
    return days < 14 ? rtf.format(-days, "day") : rtf.format(-Math.round(days / 7), "week");
  }
  // A day for a sentence: "5 days ago", else "4 Jul 2018" / "am 4. Juli 2018"
  const dayText = (s, now) =>
    relDay(s, now) || fill(raw("_onDate") || "{date}", { date: fmtDate(s) });
  // "2 hours ago", "in 3 days", "just now"; null without Intl.RelativeTimeFormat
  const UNITS = [
    ["year", 31536000],
    ["month", 2592000],
    ["week", 604800],
    ["day", 86400],
    ["hour", 3600],
    ["minute", 60],
  ];
  function relTime(date, now = Date.now()) {
    if (!rtf) return null;
    const secs = (date - now) / 1000; // negative: in the past
    const [unit, size] = UNITS.find(([, s]) => Math.abs(secs) >= s) || [];
    return rtf.format(unit ? Math.round(secs / size) : 0, unit || "second");
  }
  // "Tue, 29 Sep 2026, 17:05" in the viewer's time zone
  const fmtStamp = (d) =>
    fill(raw("_stamp") || "{wd}, {d} {mon} {y}, {time}", {
      wd: (raw("_weekdays") || [])[d.getDay()] || "",
      d: d.getDate(),
      mon: months[d.getMonth()] || "",
      y: d.getFullYear(),
      time: `${pad(d.getHours())}:${pad(d.getMinutes())}`,
    });
  // "Jul 2018", or "Apr 2014–" for a series; collections keep their year range
  const when = (it) => {
    const y = years(it);
    if (!y || it.type === "collection" || !it.released?.startsWith(String(it.year))) return y;
    return monthYear(it.released, y);
  };
  const runtime = (m) => {
    if (!m) return "";
    return m >= 60 ? t("runtime.hm", { h: Math.floor(m / 60), m: m % 60 }) : t("runtime.m", { m });
  };
  const fmtSize = (b) => {
    if (b >= 1e12) return num(b / 1e12, 2) + " TB";
    if (b >= 1e9) return num(b / 1e9, 1) + " GB";
    return num(Math.round(b / 1e6)) + " MB";
  };
  const fmtRate = (b) => num(b / 1e6, b >= 1e7 ? 0 : 1) + " Mbps";
  const resText = (m) => (m.resMixed ? t("res.mostly", { res: m.res }) : m.res);
  // "de" -> "German" / "Deutsch"; unknown codes as they are
  const langName = (code) => {
    try {
      return names?.of(code) || code;
    } catch {
      return code;
    }
  };
  // ["13 movies", "4 series", "1 collection"] -> "13 movies, 4 series and 1 collection"
  const list = (items) => (lists ? lists.format(items) : items.join(", "));
  return {
    lang,
    intl,
    t,
    num,
    monthOf,
    fmtDate,
    monthYear,
    relDay,
    dayText,
    relTime,
    fmtStamp,
    when,
    runtime,
    fmtSize,
    fmtRate,
    resText,
    langName,
    list,
  };
}
