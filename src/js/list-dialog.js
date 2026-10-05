// "Your list": the titles grouped by state, and the text to copy (or a CSV)
import { copyToClipboard } from "./detail.js";
import { $, byId, xdlg } from "./dom.js";
import { nameOf, thumb } from "./format.js";
import { sorters } from "./grid.js";
import { fmtDate, t, when } from "./i18n.js";
import { markIcon } from "./icons.js";
import { encodeList, esc, isoDay, listText, years } from "./lib.js";
import { rateHtml, stateCounts } from "./list.js";
import {
  MARK_LABEL,
  markAt,
  markTimes,
  markWhenHtml,
  markedItems,
  marks,
  myRating,
} from "./marks.js";
import { openMarkMenu } from "./menu.js";
import { FMT, NOIDS, WANTED, load, save } from "./store.js";

const xfmt = $("xfmt"),
  xtext = $("xtext"),
  xok = $("xok"),
  xnoids = $("xnoids"),
  xwanted = $("xwanted");
const firstLink = (d) => (d.links.find((l) => l.label !== "Jellyfin") ?? d.links[0])?.url || "";
// A title as listText (lib.js) takes it
const entryOf = (d) => ({
  id: d.id,
  type: d.type,
  name: nameOf(d),
  year: d.year,
  years: d.year ? years(d) : "",
  link: firstLink(d),
});
const listItem = (d) => ({
  ...entryOf(d),
  state: marks.get(d.id),
  rating: myRating(d),
  at: markAt(d),
  updated: markTimes.get(d.id) || "",
  members: (d.items || []).map((id) => entryOf(byId.get(id))),
});
const textOf = (fmt, ids, wantedOnly) =>
  listText(markedItems().sort(sorters.title).map(listItem), {
    fmt,
    ids,
    wantedOnly,
    heads: {
      movie: t("export.movies"),
      series: t("export.series"),
      collection: t("export.collections"),
    },
    stateText: (st, at) => t("stateWord." + st) + (at ? " " + fmtDate(isoDay(at)) : ""),
  });
export function fillExport() {
  const n = markedItems().length;
  $("xmeta").textContent = n
    ? t("export.meta", {
        titles: t("count.titles", { n }),
        counts: stateCounts(markedItems()),
      })
    : t("export.empty");
  fillXList();
  xtext.value = textOf(xfmt.value, !xnoids.checked, xwanted.checked);
  $("xlink").disabled = !n;
  xok.textContent = "";
}
// "Watched 3 days ago" in a row, when the time is known
const changedAt = (d) => (markAt(d) ? `<span>${markWhenHtml(d)}</span>` : "");
// The list as rows, grouped by state; each state button opens the state menu
function fillXList() {
  const items = markedItems().sort(sorters.title);
  $("xlist").innerHTML = Object.entries(MARK_LABEL)
    .map(([st, label]) => {
      const rows = items.filter((d) => marks.get(d.id) === st);
      if (!rows.length) return "";
      const row = (d) =>
        `<li class="xrow">${thumb(d)}<span class="xt"><b>${esc(nameOf(d))}</b>` +
        `<span class="y parts"><span>${esc(when(d))}</span>${changedAt(d)}</span></span>` +
        (st === "w" ? rateHtml(d) : "") +
        `<button type="button" class="xstate" data-id="${esc(d.id)}" aria-haspopup="menu" aria-label="${esc(t("mark.change", { title: nameOf(d), state: label }))}">${markIcon(st)}${esc(label)}</button></li>`;
      return `<li class="xgroup xg-${st}"><h3>${esc(label)} <span class="yc">${rows.length}</span></h3><ul>${rows.map(row).join("")}</ul></li>`;
    })
    .join("");
}

export function initListDialog() {
  $("xlist").addEventListener("click", (e) => {
    const b = e.target.closest(".xstate");
    if (b) openMarkMenu(byId.get(b.dataset.id), b);
  });
  const savedFmt = load(FMT);
  if (["plain", "links", "csv"].includes(savedFmt)) xfmt.value = savedFmt;
  xnoids.checked = load(NOIDS) === "1";
  xfmt.addEventListener("change", () => {
    save(FMT, xfmt.value);
    fillExport();
  });
  xnoids.addEventListener("change", () => {
    save(NOIDS, xnoids.checked ? "1" : "0");
    fillExport();
  });
  // "Only wanted" filters the text, not the rows
  xwanted.checked = load(WANTED) === "1";
  xwanted.addEventListener("change", () => {
    save(WANTED, xwanted.checked ? "1" : "0");
    fillExport();
  });
  $("texport").addEventListener("click", () => {
    fillExport();
    xdlg.showModal();
  });
  // The list in a link to this page; "Only wanted" applies here too
  $("xlink").addEventListener("click", async () => {
    const items = markedItems()
      .filter((d) => !xwanted.checked || marks.get(d.id) === "m")
      .sort(sorters.title)
      .map((d) => ({ id: d.id, state: marks.get(d.id), rating: myRating(d), at: markAt(d) }));
    await copyToClipboard(location.href.split("#")[0] + "#list=" + encodeList(items));
    xok.textContent = t(location.protocol === "file:" ? "export.linkLocal" : "export.linkCopied");
  });
  $("xcopy").addEventListener("click", async () => {
    await copyToClipboard(xtext.value);
    xok.textContent = t("export.copied");
  });
  xdlg.querySelector(".close").addEventListener("click", () => xdlg.close());
}
