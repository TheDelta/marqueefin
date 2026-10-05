// Your list: id -> "m" wanted / "o" owned / "w" watched, when the state last changed,
// and your ratings. Stored as {id: {s, at}}, or {id: "m"} without a time.
import { DATA } from "./dom.js";
import { dateHtml } from "./format.js";
import { dayText, t } from "./i18n.js";
import { MARK_STATES, isoDay } from "./lib.js";
import { MYRATE, STORE, load, save } from "./store.js";

export const MARK_LABEL = Object.fromEntries(MARK_STATES.map((st) => [st, t("state." + st)]));

export const marks = new Map(),
  markTimes = new Map();
try {
  for (const [id, v] of Object.entries(JSON.parse(load(STORE) || "{}"))) {
    const st = typeof v === "string" ? v : v?.s;
    if (!MARK_LABEL[st]) continue;
    marks.set(id, st);
    if (v?.at && !Number.isNaN(Date.parse(v.at))) markTimes.set(id, v.at);
  }
} catch {
  marks.clear();
}
export const saveMarks = () =>
  save(
    STORE,
    JSON.stringify(
      Object.fromEntries(
        [...marks].map(([id, s]) => [id, markTimes.has(id) ? { s, at: markTimes.get(id) } : s]),
      ),
    ),
  );
export const touchMark = (id) => markTimes.set(id, new Date().toISOString());
export const markAt = (d) => (markTimes.has(d.id) ? new Date(markTimes.get(d.id)) : null);
// "Watched 3 days ago" as HTML (exact time on hover) and as text; "2026-09-30 14:05"
// for the copy text, which Import reads back
export const markWhenHtml = (d) => {
  const at = markAt(d);
  return at ? dateHtml("markWhen." + marks.get(d.id), isoDay(at), at) : "";
};
export const markWhenText = (d) => {
  const at = markAt(d);
  return at ? dayText(isoDay(at)) : "";
};

// The viewer's own rating of a title they watched: 1-5 stars, by id
function loadRatings() {
  try {
    return new Map(
      Object.entries(JSON.parse(load(MYRATE) || "{}")).filter(
        ([, n]) => Number.isInteger(n) && n >= 1 && n <= 5,
      ),
    );
  } catch {
    return new Map();
  }
}
export const myRatings = loadRatings();
export const saveRatings = () => save(MYRATE, JSON.stringify(Object.fromEntries(myRatings)));
// A rating only counts while the title is marked as watched
export const myRating = (d) => (marks.get(d.id) === "w" && myRatings.get(d.id)) || 0;
export const markedItems = () => DATA.filter((d) => marks.has(d.id));
