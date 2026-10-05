// The page's data, and the elements several modules use
export const $ = (id) => document.getElementById(id);
const json = (id, empty) => JSON.parse($(id)?.textContent || empty);

export const DATA = JSON.parse($("data").textContent);
// Read once: the text (mostly posters, 150+ MB in a big library) can be cleared
$("data").textContent = "";
export const REQUESTS = json("requests", "[]");
export const FLAGS = json("flags", "{}");
export const CONFIG = { titleLang: "", mainLangs: ["en"], ...json("config", "{}") };

export const grid = $("grid"),
  fpanel = $("filters"),
  fbtn = $("openFilters"),
  searchInput = $("q"),
  genreSel = $("genre"),
  availSel = $("avail"),
  sortSel = $("sort"),
  count = $("count");
export const dlg = $("detail"),
  xdlg = $("export"),
  sdlg = $("settings"),
  idlg = $("import"),
  cdlg = $("compare");

// Collections are their own category: never shown under All / Movies / Series
export const byId = new Map(DATA.map((d) => [d.id, d]));
export const partOf = new Map(); // member id -> collections containing it
DATA.filter((d) => d.type === "collection").forEach((c) => {
  c.items = c.items.filter((id) => byId.has(id));
  c.items.forEach((id) => partOf.set(id, [...(partOf.get(id) || []), c]));
});

export const counts = { movie: 0, series: 0, collection: 0, requests: REQUESTS.length };
DATA.forEach((d) => counts[d.type]++);
export const hasMedia = DATA.some((d) => d.media?.res);
