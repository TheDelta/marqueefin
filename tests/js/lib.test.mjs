// Unit tests for src/js/lib.js and the translations in src/i18n: `npm run test:js`.
import assert from "node:assert/strict";
import { readdirSync, readFileSync } from "node:fs";
import { describe, test } from "node:test";
import * as L from "../../src/js/lib.js";

const ID = "0123456789abcdef0123456789abcdef";
const I18N_DIR = new URL("../../src/i18n/", import.meta.url);
const CATALOGS = Object.fromEntries(
  readdirSync(I18N_DIR)
    .filter((f) => f.endsWith(".json"))
    .map((f) => [f.slice(0, -5), JSON.parse(readFileSync(new URL(f, I18N_DIR), "utf8"))]),
);
const en = L.createI18n(CATALOGS, "en");
const de = L.createI18n(CATALOGS, "de");

describe("text", () => {
  test("esc escapes HTML", () => {
    assert.equal(
      L.esc(`<a href="x">Tom & Jerry's</a>`),
      "&lt;a href=&quot;x&quot;&gt;Tom &amp; Jerry&#39;s&lt;/a&gt;",
    );
    assert.equal(L.esc(null), "");
    assert.equal(L.esc(7), "7");
  });

  test("initials", () => {
    assert.equal(L.initials("the last lighthouse keeper"), "TLL");
  });

  test("sortTitle ignores a leading article of the title's language", () => {
    assert.equal(L.sortTitle("Der Untergang", "de"), "untergang");
    assert.equal(L.sortTitle("Das Boot", "de"), "boot");
    assert.equal(L.sortTitle("L'Arnacoeur", "fr"), "arnacoeur");
    assert.equal(L.sortTitle("La Haine", "fr"), "haine");
    assert.equal(L.sortTitle("O Auto da Compadecida", "pt-BR"), "auto da compadecida");
    assert.equal(L.sortTitle("Dark", "de"), "dark");
    assert.equal(L.sortTitle("Die", "de"), "die"); // nothing left after the article
    assert.equal(L.sortTitle("千と千尋の神隠し", "ja"), "千と千尋の神隠し");
  });

  test("years of movies, series and collections", () => {
    assert.equal(L.years({ type: "movie", year: 2016 }), "2016");
    assert.equal(L.years({ type: "series", year: 2019, status: "Continuing" }), "2019–");
    assert.equal(L.years({ type: "series", year: 2019, endYear: 2022 }), "2019–2022");
    assert.equal(L.years({ type: "series", year: 2019, endYear: 2019 }), "2019");
    assert.equal(L.years({ type: "collection", year: 2015, endYear: 2023 }), "2015–2023");
    assert.equal(L.years({ type: "movie" }), "");
  });
});

describe("commit scopes", () => {
  test("VS Code offers the scopes commitlint accepts", async () => {
    const { SCOPES } = await import("../../commitlint.config.mjs");
    const settings = JSON.parse(
      readFileSync(new URL("../../.vscode/settings.json", import.meta.url), "utf8"),
    );
    assert.deepEqual(settings["conventionalCommits.scopes"], SCOPES);
  });
});

describe("search", () => {
  test("searchText: lower case, no accents, ß as ss", () => {
    assert.equal(L.searchText("Pokémon"), "pokemon");
    assert.equal(L.searchText("Die stille Küste"), "die stille kuste");
    assert.equal(L.searchText("Straße"), "strasse");
    assert.equal(L.searchText("Amélie ÇA"), "amelie ca");
    assert.equal(L.searchText("千と千尋"), "千と千尋");
    assert.equal(L.searchText(null), "");
  });
});

describe("translations", () => {
  test("every language has every key, with the same placeholders", () => {
    const ref = CATALOGS.en;
    const holes = (v) => [...JSON.stringify(v).matchAll(/\{(\w+)\}/g)].map((m) => m[1]).sort();
    for (const [lang, cat] of Object.entries(CATALOGS)) {
      assert.deepEqual(Object.keys(cat).sort(), Object.keys(ref).sort(), lang);
      for (const key of Object.keys(ref))
        if (!key.startsWith("_"))
          assert.deepEqual(
            [...new Set(holes(cat[key]))],
            [...new Set(holes(ref[key]))],
            `${lang}: ${key}`,
          );
    }
  });

  test("plural texts have 'one' and 'other'; months and weekdays are complete", () => {
    for (const [lang, cat] of Object.entries(CATALOGS)) {
      for (const [key, v] of Object.entries(cat))
        if (v && typeof v === "object" && !Array.isArray(v))
          assert.ok(v.one && v.other, `${lang}: ${key}`);
      assert.equal(cat._months.length, 12, lang);
      assert.equal(cat._weekdays.length, 7, lang);
    }
  });

  test("pickLanguage: the first browser language there are texts for, else English", () => {
    const have = ["en", "de"];
    assert.equal(L.pickLanguage(["de-AT", "en-US"], have), "de");
    assert.equal(L.pickLanguage(["fr-FR", "de"], have), "de");
    assert.equal(L.pickLanguage(["fr-FR", "es"], have), "en");
    assert.equal(L.pickLanguage([], have), "en");
    assert.equal(L.pickLanguage(["EN-gb"], have), "en");
  });

  test("t: placeholders, plurals, numbers, English fallback", () => {
    assert.equal(en.t("count.titles", { n: 1 }), "1 title");
    assert.equal(en.t("count.titles", { n: 1234 }), "1,234 titles");
    assert.equal(de.t("count.seasons", { n: 1 }), "1 Staffel");
    assert.equal(de.t("count.seasons", { n: 3 }), "3 Staffeln");
    assert.equal(de.t("count.titles", { n: 1234 }), "1.234 Titel");
    assert.equal(de.t("count.shown", { shown: 3, total: 17 }), "3 von 17");
    const partial = L.createI18n({ en: CATALOGS.en, xx: { "tabs.all": "Tout" } }, "xx");
    assert.equal(partial.t("tabs.all"), "Tout");
    assert.equal(partial.t("tabs.movies"), "Movies"); // missing: English
    assert.equal(en.t("no.such.key"), "no.such.key");
  });

  test("numbers, sizes, runtimes", () => {
    assert.equal(en.num(7.94, 1), "7.9");
    assert.equal(de.num(7.94, 1), "7,9");
    assert.equal(en.fmtSize(18_400_000_000), "18.4 GB");
    assert.equal(de.fmtSize(18_400_000_000), "18,4 GB");
    assert.equal(en.fmtSize(1_250_000_000_000), "1.25 TB");
    assert.equal(en.fmtSize(700_000_000), "700 MB");
    assert.equal(en.fmtRate(40_000_000), "40 Mbps");
    assert.equal(de.fmtRate(4_500_000), "4,5 Mbps");
    assert.equal(en.runtime(117), "1h 57m");
    assert.equal(de.runtime(117), "1 Std. 57 Min.");
    assert.equal(en.runtime(45), "45m");
    assert.equal(en.runtime(0), "");
    assert.equal(en.resText({ res: "1080p", resMixed: true }), "Mostly 1080p");
    assert.equal(de.resText({ res: "4K" }), "4K");
  });

  test("language names and lists", () => {
    assert.equal(en.langName("de"), "German");
    assert.equal(de.langName("fr"), "Französisch");
    assert.equal(
      en.list(["13 movies", "4 series", "1 collection"]),
      "13 movies, 4 series and 1 collection",
    );
    assert.equal(de.list(["13 Filme", "4 Serien"]), "13 Filme und 4 Serien");
  });
});

describe("dates", () => {
  test("fmtDate and monthOf: by hand, 'Sep' not 'Sept' in English", () => {
    assert.equal(en.fmtDate("2018-07-04"), "4 Jul 2018");
    assert.equal(de.fmtDate("2018-07-04"), "4. Juli 2018");
    assert.equal(en.monthOf("2026-09-30"), "Sep");
    assert.equal(de.monthOf("2026-09-30"), "Sept.");
    assert.equal(en.monthOf("2026"), "");
    assert.equal(de.monthYear("2023-03-10"), "März 2023");
  });

  test("when: release month, if the date matches the year", () => {
    assert.equal(en.when({ type: "movie", year: 2023, released: "2023-02-10" }), "Feb 2023");
    assert.equal(de.when({ type: "movie", year: 2023, released: "2023-02-10" }), "Feb. 2023");
    assert.equal(
      en.when({
        type: "series",
        year: 2025,
        status: "Continuing",
        released: "2025-03-01",
      }),
      "Mar 2025–",
    );
    assert.equal(en.when({ type: "movie", year: 2023, released: "2022-12-30" }), "2023");
    assert.equal(
      en.when({
        type: "collection",
        year: 2015,
        endYear: 2018,
        released: "2015-05-01",
      }),
      "2015–2018",
    );
  });

  test("dateKey: titles with only a year sort after the dated ones", () => {
    assert.equal(L.dateKey({ released: "2026-03-01", year: 2026 }), "2026-03-01");
    assert.equal(L.dateKey({ year: 2026 }), "2026-00");
    assert.equal(L.dateKey({}), "");
  });

  test("relDay and dayText: relative within 21 days, else the date", () => {
    const now = new Date(2026, 9, 2, 12, 0); // 2 Oct 2026, local time
    assert.equal(en.relDay("2026-10-02", now), "today");
    assert.equal(en.relDay("2026-10-01", now), "yesterday");
    assert.equal(en.relDay("2026-09-27", now), "5 days ago");
    assert.equal(en.relDay("2026-09-18", now), "2 weeks ago");
    assert.equal(de.relDay("2026-09-27", now), "vor 5 Tagen");
    assert.equal(en.relDay("2026-09-10", now), null); // 22 days
    assert.equal(en.relDay("2026-10-05", now), null); // future
    assert.equal(en.dayText("2018-07-04", now), "4 Jul 2018");
    assert.equal(de.dayText("2018-07-04", now), "am 4. Juli 2018");
    assert.equal(
      de.t("when.added", { when: de.dayText("2026-10-01", now) }),
      "Hinzugefügt gestern",
    );
  });

  test("relTime for the 'Updated' badge", () => {
    const now = Date.UTC(2026, 9, 2, 12, 0);
    assert.equal(en.relTime(new Date(now - 2 * 3600e3), now), "2 hours ago");
    assert.equal(de.relTime(new Date(now - 2 * 3600e3), now), "vor 2 Stunden");
    assert.equal(en.relTime(new Date(now - 30e3), now), "now");
    assert.equal(en.relTime(new Date(now - 400 * 86400e3), now), "last year");
  });

  test("fmtStamp, isoDay and stampText in local time", () => {
    const d = new Date(2026, 8, 29, 17, 5);
    assert.equal(en.fmtStamp(d), "Tue, 29 Sep 2026, 17:05");
    assert.equal(de.fmtStamp(d), "Di., 29. Sept. 2026, 17:05");
    assert.equal(L.isoDay(d), "2026-09-29");
    assert.equal(L.stampText(d), "2026-09-29 17:05");
  });

  test("changed: updated, else added", () => {
    assert.equal(L.changed({ added: "2024-01-01", updated: "2026-09-01" }), "2026-09-01");
    assert.equal(L.changed({ added: "2024-01-01" }), "2024-01-01");
    assert.equal(L.changed({}), "");
  });
});

describe("filters and languages", () => {
  test("inRange with open ends", () => {
    assert.ok(L.inRange(2015, null, null));
    assert.ok(L.inRange(2015, 2010, null));
    assert.ok(!L.inRange(2015, 2016, null));
    assert.ok(L.inRange(7.5, 7, 8));
    assert.ok(!L.inRange(8.1, null, 8));
  });

  test("quality tests", () => {
    const q = L.QUALITY_TEST;
    assert.ok(q["4K"]({ res: "8K" }));
    assert.ok(!q["4K"]({ res: "1080p" }));
    assert.ok(q.hdr({ hdr: ["HDR10"] }));
    assert.ok(!q.hdr({}));
    assert.ok(q.dv({ hdr: ["Dolby Vision", "HDR10"] }));
    assert.ok(!q.dv({ hdr: ["HDR10+"] }));
  });

  test("triState: all, only, hide", () => {
    assert.ok(L.triState("", false));
    assert.ok(L.triState("only", true));
    assert.ok(!L.triState("only", false));
    assert.ok(L.triState("hide", false));
    assert.ok(!L.triState("hide", 65)); // partly watched counts as watched
  });

  test("foldLangs: with more than 3, all but the main languages and unknown", () => {
    assert.deepEqual(L.foldLangs(["en", "de", "fr"]), []);
    assert.deepEqual(L.foldLangs(["en", "de", "fr", "es", ""], ["en", "de"]), ["fr", "es"]);
    assert.deepEqual(L.foldLangs(["en", "de", "fr", "es"], ["en", "fr"]), ["de", "es"]);
  });
});

describe("the list's text format", () => {
  const at = new Date(2026, 8, 30, 14, 5);

  test("listTag", () => {
    assert.equal(L.listTag(ID, "m", 0, null), `[${ID}]`);
    assert.equal(L.listTag(ID, "m", 0, at), `[${ID}|m|2026-09-30 14:05]`);
    assert.equal(L.listTag(ID, "o", 0, null), `[${ID}|o]`);
    assert.equal(L.listTag(ID, "w", 4, at), `[${ID}|w4|2026-09-30 14:05]`);
  });

  test("parseList reads tags anywhere in the text", () => {
    const found = L.parseList(
      `Filme\n[${ID}|w4|2026-09-30 14:05] Title (2026) ★4/5 https://x\n` +
        `[${"f".repeat(32)}] Wanted (2025)\nno tag here [abc]`,
    );
    assert.equal(found.size, 2);
    assert.deepEqual(found.get(ID), ["w", 4, at.toISOString()]);
    assert.deepEqual(found.get("f".repeat(32)), ["m", 0, ""]);
  });

  test("parseList reads CSV rows, with or without rating and time", () => {
    const found = L.parseList(
      "id,state,rating,updated,type,title,year,link\n" +
        `${ID},watched,5,2026-09-25T10:00:00.000Z,movie,A,2026,https://x\n` +
        `${"a".repeat(32)},owned,movie,B,2024,https://x\n`,
    );
    assert.deepEqual(found.get(ID), ["w", 5, "2026-09-25T10:00:00.000Z"]);
    assert.deepEqual(found.get("a".repeat(32)), ["o", 0, ""]);
  });

  test("only the three states", () => {
    const found = L.parseList(`[${ID}|x] Odd\n${"b".repeat(32)},received,,,movie,C,2020,https://x`);
    assert.equal(found.get(ID), undefined);
    assert.equal(found.get("b".repeat(32)), undefined);
  });

  test("ids are case-insensitive; a tag round-trips", () => {
    const tag = L.listTag(ID.toUpperCase(), "w", 3, at);
    assert.deepEqual(L.parseList(tag).get(ID), ["w", 3, at.toISOString()]);
  });

  test("isoFrom", () => {
    assert.equal(L.isoFrom("2026-09-30 14:05"), at.toISOString());
    assert.equal(L.isoFrom("not a time"), "");
    assert.equal(L.isoFrom(undefined), "");
  });

  test("every state has a CSV name and texts in every language", () => {
    for (const st of L.MARK_STATES) {
      assert.equal(L.CSV_CODE[L.CSV_STATE[st]], st);
      for (const cat of Object.values(CATALOGS)) assert.ok(cat["state." + st]);
    }
  });
});

describe("the list's copy text", () => {
  const at = new Date(2026, 8, 30, 14, 5);
  const B = "b".repeat(32),
    C = "c".repeat(32);
  const movie = {
    id: ID,
    type: "movie",
    name: "Paper Moons",
    year: 2026,
    years: "2026",
    link: "https://tmdb/1",
    state: "w",
    rating: 4,
    at,
    updated: at.toISOString(),
    members: [],
  };
  const wanted = { ...movie, id: B, name: "Saltwind", years: "2024", year: 2024 };
  Object.assign(wanted, { state: "m", rating: 0, at: null, updated: "", link: "https://tmdb/2" });
  const box = {
    ...wanted,
    id: C,
    type: "collection",
    name: "Wayfinders, the Collection",
    years: "2024–2026",
    state: "o",
    members: [{ name: "Northbound", years: "2026", link: "https://tmdb/3" }],
  };
  const opts = (more) => ({
    fmt: "links",
    ids: true,
    wantedOnly: false,
    heads: { movie: "Movies", series: "Series", collection: "Collections" },
    stateText: (st, when) => `${L.CSV_STATE[st]}${when ? " " + L.isoDay(when) : ""}`,
    ...more,
  });

  test("titles with links: tags, rating, one group", () => {
    assert.equal(
      L.listText([movie, wanted], opts()),
      `[${ID}|w4|2026-09-30 14:05] Paper Moons (2026) ★4/5 https://tmdb/1\n` +
        `[${B}] Saltwind (2024) https://tmdb/2`,
    );
  });

  test("without ids: state and date follow the title; wanted without a date says nothing", () => {
    assert.equal(
      L.listText([movie, wanted], opts({ ids: false, fmt: "plain" })),
      "Paper Moons (2026) (watched 2026-09-30, ★4/5)\nSaltwind (2024)",
    );
  });

  test("several kinds get headings; a collection lists its members without tags", () => {
    assert.equal(
      L.listText([movie, box], opts({ fmt: "plain" })),
      `Movies\n[${ID}|w4|2026-09-30 14:05] Paper Moons (2026) ★4/5\n\n` +
        `Collections\n[${C}|o] Wayfinders, the Collection (2024–2026)\n    Northbound (2026)`,
    );
  });

  test("only wanted", () => {
    assert.equal(
      L.listText([movie, wanted], opts({ wantedOnly: true, fmt: "plain" })),
      `[${B}] Saltwind (2024)`,
    );
  });

  test("CSV: header, English states, quoted cells; ids optional", () => {
    assert.equal(
      L.listText([movie, box], opts({ fmt: "csv" })),
      "id,state,rating,updated,type,title,year,link\n" +
        `${ID},watched,4,${at.toISOString()},movie,Paper Moons,2026,https://tmdb/1\n` +
        `${C},owned,,,collection,"Wayfinders, the Collection",2024,https://tmdb/2`,
    );
    const quoted = { ...wanted, name: 'Say "Hi"\nagain' };
    assert.equal(
      L.listText([quoted], opts({ fmt: "csv", ids: false }))
        .split("\n")
        .slice(1)
        .join("\n"),
      'wanted,,,movie,"Say ""Hi""\nagain",2024,https://tmdb/2',
    );
  });

  test("the copied text imports again", () => {
    const back = L.parseList(L.listText([movie, wanted, box], opts()));
    assert.deepEqual([...back.keys()], [ID, B, C]);
    assert.deepEqual(back.get(ID), ["w", 4, at.toISOString()]);
    const csv = L.parseList(L.listText([movie, box], opts({ fmt: "csv" })));
    assert.deepEqual(csv.get(C), ["o", 0, ""]);
  });
});

describe("sorting", () => {
  const byName = (a, b) => a.t.localeCompare(b.t);
  const S = L.makeSorters(byName);
  const order = (list, sort) => [...list].sort(S[sort]).map((d) => d.t);
  const list = [
    { t: "B", released: "2024-05-01", year: 2024, rating: 7, added: "2026-01-01" },
    { t: "A", released: "2026-02-01", year: 2026, rating: 7, updated: "2026-03-01" },
    { t: "C", year: 2024, added: "2025-12-01", lastWatched: "2026-09-01T10:00:00Z" },
    { t: "D", added: "2026-01-01", lastWatched: "2026-09-02T10:00:00Z" },
  ];

  test("each order, ties A to Z", () => {
    assert.deepEqual(order(list, "title"), ["A", "B", "C", "D"]);
    assert.deepEqual(order(list, "new"), ["A", "B", "C", "D"]); // a year only: after its dated titles
    assert.deepEqual(order(list, "old"), ["C", "B", "A", "D"]); // no date at all: last
    assert.deepEqual(order(list, "rating"), ["A", "B", "C", "D"]); // no rating: last
    assert.deepEqual(order(list, "added"), ["A", "B", "D", "C"]); // updated counts as a change
    assert.deepEqual(order(list, "watched"), ["D", "C", "A", "B"]); // never watched: last
  });

  test("the year view: newest year first, no year last, dates within a year", () => {
    const e = [
      { year: 2024, key: "2024-05" },
      { year: null, key: "" },
      { year: 2026, key: "2026-01" },
      { year: 2024, key: "2024-11" },
    ];
    const keys = (sort) => [...e].sort(L.yearOrder(sort)).map((x) => x.key || "none");
    assert.deepEqual(keys("new"), ["2026-01", "2024-11", "2024-05", "none"]);
    assert.deepEqual(keys("old"), ["2024-05", "2024-11", "2026-01", "none"]);
    // Other orders keep their own order within a year (a stable sort)
    assert.deepEqual(keys("title"), ["2026-01", "2024-05", "2024-11", "none"]);
  });
});

describe("seasons and age ratings", () => {
  test("seasonRanges", () => {
    assert.equal(L.seasonRanges([1, 2, 3, 5]), "1–3, 5");
    assert.equal(L.seasonRanges([4]), "4");
    assert.equal(L.seasonRanges([1, 3, 4, 6, 7, 8]), "1, 3–4, 6–8");
    assert.equal(L.seasonRanges([]), "");
  });

  test("newestFirst: specials last, the list itself unchanged", () => {
    const ss = [{ n: 0 }, { n: 1 }, { n: 3 }, { n: 2 }];
    assert.deepEqual(
      L.newestFirst(ss).map((s) => s.n),
      [3, 2, 1, 0],
    );
    assert.deepEqual(
      ss.map((s) => s.n),
      [0, 1, 3, 2],
    );
  });

  test("seasonsStatus: all watched, an average, any favorite", () => {
    assert.deepEqual(L.seasonsStatus([{ watched: true }, { watched: true, fav: true }]), {
      watched: true,
      watchedPct: 0,
      fav: true,
    });
    assert.deepEqual(L.seasonsStatus([{ watched: true }, { watchedPct: 50 }, {}]), {
      watched: false,
      watchedPct: 50,
      fav: false,
    });
  });

  test("fskAge: German ratings in their forms, others not", () => {
    assert.deepEqual(L.fskAge("FSK 12"), { age: 12, label: "FSK 12" });
    assert.deepEqual(L.fskAge("DE-16"), { age: 16, label: "FSK 16" });
    assert.deepEqual(L.fskAge(" fsk0 "), { age: 0, label: "FSK 0" });
    assert.deepEqual(L.fskAge("DE/18"), { age: 18, label: "FSK 18" });
    assert.deepEqual(L.fskAge("6+"), { age: 6, label: "6+" });
    for (const other of ["PG-13", "TV-MA", "FSK 14", "R", "16 Jahre"])
      assert.equal(L.fskAge(other), null);
  });
});

describe("surprise me", () => {
  test("pickRandom: any entry, not the last pick when there's a choice", () => {
    const list = ["a", "b", "c"];
    assert.equal(
      L.pickRandom(list, undefined, () => 0),
      "a",
    );
    assert.equal(
      L.pickRandom(list, "a", () => 0),
      "b",
    ); // "a" was last time
    assert.equal(
      L.pickRandom(list, "a", (n) => n - 1),
      "c",
    );
    assert.equal(
      L.pickRandom(["a"], "a", () => 0),
      "a",
    ); // the only one
    assert.equal(L.pickRandom([], undefined), undefined);
  });
});

describe("the list as a link", () => {
  const at = new Date(Date.UTC(2026, 8, 30, 12, 5));
  const items = [
    { id: ID, state: "w", rating: 4, at },
    { id: "f".repeat(32), state: "m", rating: 0, at: null },
    { id: "a".repeat(32), state: "o", rating: 0, at },
  ];

  test("round trip: state, rating, the time to the minute", () => {
    assert.deepEqual(L.decodeList(L.encodeList(items)), [
      { prefix: ID.slice(0, 16), state: "w", rating: 4, at: at.toISOString() },
      { prefix: "f".repeat(16), state: "m", rating: 0, at: "" },
      { prefix: "a".repeat(16), state: "o", rating: 0, at: at.toISOString() },
    ]);
  });

  test("short and safe in a URL", () => {
    const code = L.encodeList(items);
    assert.match(code, /^[\w-]+$/);
    assert.ok(code.length < 18 * items.length + 4, code.length);
    assert.deepEqual(L.decodeList(L.encodeList([])), []);
  });

  test("anything else is no list", () => {
    const code = L.encodeList(items);
    assert.equal(L.decodeList(code.slice(0, -3)), null); // cut off by a messenger
    assert.equal(L.decodeList("not base64!"), null);
    assert.equal(L.decodeList("AA"), null); // another version
    assert.equal(L.decodeList(""), null);
  });
});

describe("comparing lists", () => {
  const m = (state, rating = 0) => ({ state, rating });
  test("compareLists groups both lists", () => {
    const mine = new Map([
      ["a", m("m")],
      ["b", m("o")],
      ["c", m("m")],
      ["d", m("w", 4)],
      ["e", m("o")],
      ["f", m("w")],
    ]);
    const theirs = new Map([
      ["a", m("m")], // both want
      ["b", m("m")], // they want, you have
      ["c", m("w", 3)], // you want, they watched
      ["d", m("w", 5)], // both watched
      ["e", m("w")], // both have (owned / watched)
      ["g", m("o")], // only theirs
    ]);
    assert.deepEqual(L.compareLists(mine, theirs), {
      bothWant: ["a"],
      theyWant: ["b"],
      youWant: ["c"],
      bothWatched: ["d"],
      bothHave: ["e"],
      onlyTheirs: ["g"],
      onlyYours: ["f"],
    });
  });
});

describe("the Filters panel's 'Your list'", () => {
  test("markFilter: any, on or off the list, one state", () => {
    assert.ok(L.markFilter("", undefined));
    assert.ok(L.markFilter("on", "o") && !L.markFilter("on", undefined));
    assert.ok(L.markFilter("off", undefined) && !L.markFilter("off", "m"));
    assert.ok(L.markFilter("w", "w") && !L.markFilter("w", "m") && !L.markFilter("w", undefined));
  });
});

describe("the language in the address", () => {
  const page = "file:///C:/demo.html";
  test("withLang adds or replaces ?lang=, keeping the rest", () => {
    assert.equal(L.withLang(page, "en"), page + "?lang=en");
    assert.equal(L.withLang(page + "?lang=de#item=1", "fr"), page + "?lang=fr#item=1");
  });
  test("langFromUrl takes it out again", () => {
    assert.deepEqual(L.langFromUrl(page + "?lang=en#item=1"), {
      lang: "en",
      href: page + "#item=1",
    });
    assert.deepEqual(L.langFromUrl(page), { lang: "", href: page });
    assert.deepEqual(L.langFromUrl("https://x.example/p/?a=1&lang=es"), {
      lang: "es",
      href: "https://x.example/p/?a=1",
    });
  });
});

describe("values from the data in the page", () => {
  test("percent: a whole number, whatever the data holds", () => {
    assert.equal(L.percent(65), 65);
    assert.equal(L.percent("64.6"), 65);
    assert.equal(L.percent('"><img src=x onerror=alert(1)>'), 0);
    assert.equal(L.percent(undefined), 0);
  });
  test("pickRandom's default draws from crypto, within the list", () => {
    for (let i = 0; i < 50; i++) assert.ok(["a", "b", "c"].includes(L.pickRandom(["a", "b", "c"])));
  });
  test("randomIndex: every index of the range, none outside", () => {
    const seen = new Set();
    for (let i = 0; i < 200; i++) seen.add(L.randomIndex(3));
    assert.deepEqual([...seen].sort(), [0, 1, 2]);
    assert.equal(L.randomIndex(1), 0);
  });
});
