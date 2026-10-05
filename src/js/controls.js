// The controls: tabs, search, the menus, the list bar, and Settings (badges, title
// language, page language, theme)
import { hasSeasonYears, paintMark } from "./cards.js";
import {
  $,
  CONFIG,
  DATA,
  REQUESTS,
  availSel,
  cdlg,
  counts,
  dlg,
  fbtn,
  fpanel,
  genreSel,
  hasMedia,
  idlg,
  sdlg,
  searchInput,
  sortSel,
  xdlg,
} from "./dom.js";
import { syncFilters } from "./filters.js";
import { nameOf } from "./format.js";
import { openDetail } from "./detail.js";
import { apply, fillGenres, shownTitles, splitApplies } from "./grid.js";
import { CATALOGS, autoLang, langChoice, langName, t } from "./i18n.js";
import { esc, pickRandom, withLang } from "./lib.js";
import { updateTray } from "./list.js";
import { markTimes, markedItems, marks, myRatings, saveMarks, saveRatings } from "./marks.js";
import { state } from "./state.js";
import {
  ALT,
  GROUP,
  KEY,
  LANG,
  QUALITY,
  RATINGS,
  SPLIT,
  STATUS,
  THEME,
  load,
  save,
} from "./store.js";

// The availability filter only makes sense for series
const hasAvail = DATA.some((d) => d.complete !== undefined);
export const syncAvail = () => {
  availSel.hidden =
    !hasAvail || !(state.type === "series" || (state.type === "all" && !counts.movie));
  if (availSel.hidden) state.avail = availSel.value = "";
};
// The requests list has no sorting or filters
export const syncSort = () => {
  const req = state.type === "requests";
  sortSel.hidden = fbtn.hidden = $("surprise").hidden = req;
  fpanel.hidden = req || fbtn.getAttribute("aria-expanded") !== "true";
  document.documentElement.classList.toggle("sort-added", state.sort === "added");
  document.documentElement.classList.toggle("sort-watched", state.sort === "watched");
};
const splitBox = $("split");
export const syncSplit = () => {
  $("splitWrap").hidden = !hasSeasonYears;
  splitBox.disabled = !splitApplies();
  $("splitHint").hidden = splitApplies();
};
// Poster badges are hidden with a class on <html>, so nothing has to be rebuilt
export const syncBadges = () => {
  document.documentElement.classList.toggle("no-ratings", !state.ratings);
  document.documentElement.classList.toggle("no-status", !state.status);
  document.documentElement.classList.toggle("no-quality", !state.quality);
};

let lastPick;
export function initControls() {
  // A protected page's remembered key: the next visit asks for the passphrase again
  const forget = $("forgetKey");
  forget.hidden = !load(KEY);
  forget.addEventListener("click", () => {
    try {
      localStorage.removeItem(KEY);
    } catch {
      /* storage blocked: nothing was remembered */
    }
    forget.hidden = true;
  });
  // A random title of the ones shown (tab, search, filters)
  $("surprise").addEventListener("click", () => {
    const it = pickRandom(shownTitles(), lastPick);
    if (!it) return;
    lastPick = it;
    openDetail(it);
  });
  $("openSettings").addEventListener("click", () => {
    syncSplit();
    sdlg.showModal();
  });
  sdlg.querySelector(".close").addEventListener("click", () => sdlg.close());
  [dlg, xdlg, sdlg, idlg, cdlg].forEach((d) =>
    d.addEventListener("click", (e) => {
      if (e.target === d) d.close();
    }),
  );
  $("tclear").addEventListener("click", () => {
    if (!confirm(t("tray.confirmClear", { n: markedItems().length }))) return;
    DATA.forEach((d) => {
      marks.delete(d.id); // leaves lists of other pages alone
      markTimes.delete(d.id);
      myRatings.delete(d.id);
    });
    saveMarks();
    saveRatings();
    DATA.forEach(paintMark);
    updateTray();
    apply();
  });
  $("tabs").addEventListener("click", (e) => {
    const b = e.target.closest("button");
    if (!b) return;
    state.type = b.dataset.type;
    $("tabs")
      .querySelectorAll("button")
      .forEach((x) => x.setAttribute("aria-pressed", x === b));
    fillGenres();
    syncAvail();
    syncSplit();
    syncSort();
    syncFilters();
    apply();
  });
  let searchTimer;
  searchInput.addEventListener("input", () => {
    clearTimeout(searchTimer);
    searchTimer = setTimeout(() => {
      state.q = searchInput.value;
      apply();
    }, 120);
  });
  genreSel.addEventListener("change", () => {
    state.genre = genreSel.value;
    apply();
  });
  availSel.addEventListener("change", () => {
    state.avail = availSel.value;
    apply();
  });
  sortSel.addEventListener("change", () => {
    state.sort = sortSel.value;
    syncSort();
    apply();
  });
}

export function initSettings() {
  if (!DATA.some((d) => d.lastWatched)) $("sortWatched").remove();
  const groupBox = $("group"),
    ratingsBox = $("ratings"),
    statusBox = $("status"),
    qualityBox = $("qualityBox");
  $("statusWrap").hidden = !DATA.some((d) => d.watched || d.watchedPct || d.fav);
  $("qualityWrap").hidden = !hasMedia;
  groupBox.checked = state.group;
  splitBox.checked = state.split;
  ratingsBox.checked = state.ratings;
  statusBox.checked = state.status;
  qualityBox.checked = state.quality;
  groupBox.addEventListener("change", () => {
    state.group = groupBox.checked;
    save(GROUP, state.group ? "1" : "0");
    syncSplit();
    apply();
  });
  splitBox.addEventListener("change", () => {
    state.split = splitBox.checked;
    save(SPLIT, state.split ? "1" : "0");
    apply();
  });
  ratingsBox.addEventListener("change", () => {
    state.ratings = ratingsBox.checked;
    save(RATINGS, state.ratings ? "1" : "0");
    syncBadges();
  });
  statusBox.addEventListener("change", () => {
    state.status = statusBox.checked;
    save(STATUS, state.status ? "1" : "0");
    syncBadges();
  });
  qualityBox.addEventListener("change", () => {
    state.quality = qualityBox.checked;
    save(QUALITY, state.quality ? "1" : "0");
    syncBadges();
  });
  initAltTitles();
  initPageLanguage();
  initTheme();
}

// Only the title texts change; A to Z follows them, so re-sort
function initAltTitles() {
  const altBox = $("altBox");
  $("altWrap").hidden =
    !CONFIG.titleLang || (!DATA.some((d) => d.titleAlt) && !REQUESTS.some((r) => r.titleAlt));
  $("altLabel").textContent = t("settings.altTitles", {
    language: langName(CONFIG.titleLang || "en"),
  });
  altBox.checked = state.alt;
  altBox.addEventListener("change", () => {
    state.alt = altBox.checked;
    save(ALT, state.alt ? "1" : "0");
    DATA.forEach((d) =>
      d._els.forEach((el) => {
        el.querySelector(".t").textContent = nameOf(d);
      }),
    );
    DATA.forEach(paintMark); // the mark buttons' labels name the title
    apply();
  });
}

// A change reloads: the texts are built once
function initPageLanguage() {
  const langSel = $("langSel");
  langSel.innerHTML =
    `<option value="auto">${esc(t("settings.languageAuto", { language: CATALOGS[autoLang]?._name || autoLang }))}</option>` +
    Object.entries(CATALOGS)
      .map(([code, c]) => `<option value="${esc(code)}">${esc(c._name || code)}</option>`)
      .join("");
  langSel.value = CATALOGS[langChoice] ? langChoice : "auto";
  langSel.addEventListener("change", () => {
    save(LANG, langSel.value);
    location.replace(withLang(location.href, langSel.value)); // see withLang (lib.js)
  });
}

// <head> applies a saved choice before the first paint; this keeps theme-color in step
function initTheme() {
  const themeMetas = [...document.querySelectorAll('meta[name="theme-color"]')];
  const metaScheme = (m) => (m.media.includes("dark") ? "dark" : "light");
  const themeColor = Object.fromEntries(themeMetas.map((m) => [metaScheme(m), m.content]));
  const setTheme = (t) => {
    if (t === "light" || t === "dark") document.documentElement.dataset.theme = t;
    else delete document.documentElement.dataset.theme;
    themeMetas.forEach((m) => {
      m.content = themeColor[t] || themeColor[metaScheme(m)];
    });
  };
  const savedTheme = load(THEME) || "auto";
  setTheme(savedTheme);
  document.querySelectorAll('input[name="theme"]').forEach((r) => {
    r.checked = r.value === savedTheme;
    r.addEventListener("change", () => {
      save(THEME, r.value);
      setTheme(r.value);
    });
  });
}
