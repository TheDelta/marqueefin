// The page's language: the viewer's choice, else the browser's, else English. Not
// dom.js: unlock.js uses this before the page's data is there.
import { createI18n, pickLanguage } from "./lib.js";
import { LANG, load } from "./store.js";

export const CATALOGS = JSON.parse(document.getElementById("i18n")?.textContent || "{}");
export const autoLang = pickLanguage(
  navigator.languages?.length ? navigator.languages : [navigator.language],
  Object.keys(CATALOGS),
);
export const langChoice = load(LANG) || "auto";
export const I18N = createI18n(CATALOGS, CATALOGS[langChoice] ? langChoice : autoLang);
export const {
  t,
  num,
  fmtDate,
  monthYear,
  dayText,
  relTime,
  fmtStamp,
  when,
  runtime,
  fmtSize,
  fmtRate,
  resText,
  langName,
} = I18N;

// Without JavaScript the template's English texts stay
export function translatePage() {
  document.documentElement.lang = I18N.lang;
  document.querySelectorAll("[data-i18n]").forEach((el) => {
    el.textContent = t(el.dataset.i18n);
  });
  document.querySelectorAll("[data-i18n-attr]").forEach((el) =>
    el.dataset.i18nAttr.split(";").forEach((pair) => {
      const [attr, key] = pair.split(":");
      el.setAttribute(attr, t(key));
    }),
  );
}
