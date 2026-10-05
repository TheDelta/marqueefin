// Import: [id|state …] tags anywhere in the text, or CSV rows. Replaces the list for
// this page's titles; unknown ids are skipped and counted.
import { paintMark } from "./cards.js";
import { openCompare } from "./compare.js";
import { $, DATA, byId, idlg, sdlg, xdlg } from "./dom.js";
import { nameOf } from "./format.js";
import { apply } from "./grid.js";
import { t } from "./i18n.js";
import { decodeList, listTag, parseList, years } from "./lib.js";
import { stateCounts, updateTray } from "./list.js";
import { markTimes, markedItems, marks, myRatings, saveMarks, saveRatings } from "./marks.js";

const itext = $("itext"),
  iok = $("iok"),
  ifrom = $("ifrom");
function openImport() {
  sdlg.close();
  xdlg.close();
  itext.value = "";
  iok.textContent = "";
  ifrom.hidden = true;
  idlg.showModal();
  itext.focus();
}
// The pasted (or linked) list's titles of this library; null and a message if none
function pastedList() {
  const found = parseList(itext.value);
  const known = [...found].filter(([id]) => byId.has(id));
  if (!known.length) iok.textContent = t(found.size ? "import.noneHere" : "import.noIds");
  return known.length ? { known, skipped: found.size - known.length } : null;
}
function compareList() {
  const list = pastedList();
  if (list) openCompare(new Map(list.known.map(([id, [st, r]]) => [id, { state: st, rating: r }])));
}
function importList() {
  const list = pastedList();
  if (!list) return;
  const { known, skipped } = list;
  const current = markedItems().length;
  const ask = t("import.confirm", {
    current: t("count.titles", { n: current }),
    imported: t("count.titles", { n: known.length }),
  });
  if (current && !confirm(ask)) return;
  DATA.forEach((d) => {
    marks.delete(d.id); // leaves lists of other pages alone
    markTimes.delete(d.id);
    myRatings.delete(d.id);
  });
  known.forEach(([id, [st, r, at]]) => {
    marks.set(id, st);
    if (at) markTimes.set(id, at);
    if (st === "w" && r) myRatings.set(id, r);
  });
  saveMarks();
  saveRatings();
  DATA.forEach(paintMark);
  updateTray();
  apply();
  iok.textContent = [
    t("import.done", {
      titles: t("count.titles", { n: known.length }),
      counts: stateCounts(markedItems()),
    }),
    skipped ? t("import.skipped", { n: skipped }) : "",
  ]
    .filter(Boolean)
    .join(" ");
}

// A link's ids are shortened to their first 16 hex digits (see encodeList)
const byPrefix = new Map(DATA.map((d) => [d.id.slice(0, 16).toLowerCase(), d]));
// "#list=…": the shared list in the import dialog, as text with tags and titles
export function openSharedList() {
  const m = /[#&]list=([\w-]+)/.exec(location.hash);
  if (!m) return;
  try {
    history.replaceState(null, "", location.pathname + location.search);
  } catch {
    /* file:// in some browsers: the hash stays, which is harmless */
  }
  openImport();
  const list = decodeList(m[1]);
  if (!list) {
    iok.textContent = t("share.invalid");
    return;
  }
  const known = list.filter((e) => byPrefix.has(e.prefix));
  itext.value = known
    .map((e) => {
      const d = byPrefix.get(e.prefix);
      const tag = listTag(d.id, e.state, e.rating, e.at ? new Date(e.at) : null);
      const year = d.year ? ` (${years(d)})` : "";
      return `${tag} ${nameOf(d)}${year}`;
    })
    .join("\n");
  const skipped = list.length - known.length;
  ifrom.textContent = [
    t("share.opened", { titles: t("count.titles", { n: known.length }) }),
    skipped ? t("import.skipped", { n: skipped }) : "",
  ]
    .filter(Boolean)
    .join(" ");
  ifrom.hidden = false;
}

export function initImport() {
  addEventListener("hashchange", openSharedList);
  $("openImport").addEventListener("click", openImport);
  $("xImport").addEventListener("click", openImport);
  $("ido").addEventListener("click", importList);
  $("icompare").addEventListener("click", compareList);
  idlg.querySelector(".close").addEventListener("click", () => idlg.close());
}
