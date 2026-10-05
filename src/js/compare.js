// Comparing your list with someone else's (pasted, or from a link): what you both
// want, who has what the other wants, what you both watched and how you rated it
import { openDetail } from "./detail.js";
import { $, byId, cdlg, idlg } from "./dom.js";
import { nameOf, thumb } from "./format.js";
import { sorters } from "./grid.js";
import { t, when } from "./i18n.js";
import { markIcon } from "./icons.js";
import { compareLists, esc } from "./lib.js";
import { MARK_LABEL, markedItems, marks, myRating } from "./marks.js";

// The groups in the order they're shown (lib.js compareLists)
const GROUPS = [
  "bothWant",
  "theyWant",
  "youWant",
  "bothWatched",
  "bothHave",
  "onlyTheirs",
  "onlyYours",
];
// "You: ✔ Owned", "Them: 👁 Watched ★4"
const chip = (who, mark) =>
  mark
    ? `<span class="cmpst cmp-${mark.state}">${markIcon(mark.state)}${esc(
        t(who, { state: MARK_LABEL[mark.state] + (mark.rating ? ` ★${mark.rating}` : "") }),
      )}</span>`
    : "";
const row = (d, yours, theirs) =>
  `<li class="xrow">${thumb(d)}<span class="xt"><button type="button" class="cmpopen" data-id="${esc(d.id)}">${esc(nameOf(d))}</button><span class="y">${esc(when(d))}</span></span>` +
  `<span class="cmpsts">${chip("compare.you", yours)}${chip("compare.them", theirs)}</span></li>`;

/** theirs: Map id -> {state, rating}, titles of this library only */
export function openCompare(theirs) {
  const mine = new Map(
    markedItems().map((d) => [d.id, { state: marks.get(d.id), rating: myRating(d) }]),
  );
  const groups = compareLists(mine, theirs);
  $("cmeta").textContent = t("compare.meta", {
    theirs: t("count.titles", { n: theirs.size }),
    yours: t("count.titles", { n: mine.size }),
    both: t("count.titles", { n: theirs.size - groups.onlyTheirs.length }),
  });
  $("clist").innerHTML = GROUPS.filter((g) => groups[g].length)
    .map((g) => {
      const rows = groups[g]
        .map((id) => byId.get(id))
        .sort(sorters.title)
        .map((d) => row(d, mine.get(d.id), theirs.get(d.id)))
        .join("");
      return `<li class="xgroup"><h3>${esc(t("compare." + g))} <span class="yc">${groups[g].length}</span></h3><ul>${rows}</ul></li>`;
    })
    .join("");
  idlg.close();
  cdlg.showModal();
}

export function initCompare() {
  $("clist").addEventListener("click", (e) => {
    const b = e.target.closest(".cmpopen");
    if (b) openDetail(byId.get(b.dataset.id));
  });
  cdlg.querySelector(".close").addEventListener("click", () => cdlg.close());
}
