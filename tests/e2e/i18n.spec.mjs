// The page's language: the browser's when the page has texts for it (src/i18n),
// else English; Settings can pick one. The list's tags and CSV stay English.
import AxeBuilder from "@axe-core/playwright";
import { card, expect, idOf, openDemo, test } from "./helpers.mjs";

test.describe("a German browser", () => {
  test.use({ locale: "de-DE" });

  test("gets the page in German", async ({ page }) => {
    await openDemo(page);
    await expect(page.locator("html")).toHaveAttribute("lang", "de");
    await expect(page.locator("#summary")).toHaveText("13 Filme, 4 Serien und 1 Sammlung");
    await expect(page.locator("#count")).toHaveText("17 Titel");
    await expect(page.locator('#tabs [data-type="movie"]')).toHaveText("Filme");
    await expect(page.locator("#q")).toHaveAttribute("placeholder", "Titel, Jahre, Genres suchen");
    await expect(card(page, "The Last Lighthouse").locator(".y").first()).toHaveText("Aug. 2026");
    await expect(card(page, "Signal Lost").locator(".y").first()).toHaveText(
      "Juni 2026–, 2 Staffeln",
    );
  });

  test("the detail view and the list in German", async ({ page }) => {
    await openDemo(page);
    await card(page, "The Quiet Coast").locator(".open").click();
    const dialog = page.locator("#detail");
    await expect(dialog).toContainText("Staffeln");
    await expect(dialog).toContainText("es fehlen E4–E5");
    await expect(dialog.locator(".rating")).toContainText("8,1");
    await page.keyboard.press("Escape");

    await card(page, "Iron Orchard").locator(".mark").click();
    await expect(page.locator("#tcount")).toHaveText("1 Titel auf deiner Liste");
    await page.locator("#texport").click();
    // Readable parts translated, the tag stays as Import reads it
    await expect(page.locator("#xtext")).toHaveValue(
      new RegExp(`^\\[${idOf("Iron Orchard")}\\|m\\|[\\d-]+ [\\d:]+\\] Iron Orchard \\(2026\\)`),
    );
    await page.locator("#xfmt").selectOption("csv");
    await expect(page.locator("#xtext")).toHaveValue(
      /^id,state,rating,updated,type,title,year,link\n.*,wanted,/,
    );
  });

  test("the second title language's switch is named in German", async ({ page }) => {
    await openDemo(page);
    await page.locator("#openSettings").click();
    await expect(page.locator("#altLabel")).toHaveText("Titel auf Deutsch");
  });

  test("Settings can switch to English", async ({ page }) => {
    await openDemo(page);
    await page.locator("#openSettings").click();
    await expect(page.locator("#langSel option").first()).toHaveText("Automatisch (Deutsch)");
    await page.locator("#langSel").selectOption("en"); // reloads, with ?lang=en
    await expect(page.locator("#summary")).toHaveText("13 movies, 4 series and 1 collection");
    await expect(page.locator("html")).toHaveAttribute("lang", "en");
    expect(new URL(page.url()).search).toBe(""); // taken out of the address again
    await page.reload(); // and remembered
    await expect(page.locator("#summary")).toHaveText("13 movies, 4 series and 1 collection");
  });

  test("accessibility in German", async ({ page }) => {
    await openDemo(page);
    await card(page, "The Quiet Coast").locator(".open").click();
    const results = await new AxeBuilder({ page })
      .withTags(["wcag2a", "wcag2aa", "wcag21aa"])
      .analyze();
    expect(results.violations.map((v) => v.id)).toEqual([]);
  });
});

test("a page opened with ?lang= keeps that language and drops the parameter", async ({ page }) => {
  // What the reload after Settings → Language opens (the switch's own test leaves that
  // page again, so it's checked here, where the page stays)
  await openDemo(page, { search: "?lang=de", hash: "item=" + idOf("Northbound") });
  await expect(page.locator("#summary")).toHaveText("13 Filme, 4 Serien und 1 Sammlung");
  const url = new URL(page.url());
  expect(url.search).toBe("");
  expect(url.hash).toBe("#item=" + idOf("Northbound")); // the rest of the address stays
  expect(await page.evaluate(() => localStorage.getItem("marqueefin:lang"))).toBe("de");
});

test("a ?lang= the page doesn't offer is dropped, not stored", async ({ page }) => {
  await openDemo(page, { search: "?lang=not-a-language" }); // simulate bad lang code
  await expect(page.locator("#summary")).toHaveText("13 movies, 4 series and 1 collection");
  expect(new URL(page.url()).search).toBe("");
  expect(await page.evaluate(() => localStorage.getItem("marqueefin:lang"))).toBeNull();
});

test.describe("a browser in a language the page doesn't have", () => {
  test.use({ locale: "pl-PL" }); // no pl.json

  test("gets English", async ({ page }) => {
    await openDemo(page);
    await expect(page.locator("html")).toHaveAttribute("lang", "en");
    await expect(page.locator('#tabs [data-type="movie"]')).toHaveText("Movies");
  });
});

// French and Spanish (AI-translated, like the README says): the same checks in short
for (const [locale, t] of [
  [
    "fr-FR",
    {
      lang: "fr",
      summary: "13 films, 4 séries et 1 collection",
      count: "17 titres",
      movies: "Films",
      month: "août 2026",
      missing: "il manque E4–E5",
    },
  ],
  [
    "es-ES",
    {
      lang: "es",
      summary: "13 películas, 4 series y 1 colección",
      count: "17 títulos",
      movies: "Películas",
      month: "ago 2026",
      missing: "faltan E4–E5",
    },
  ],
])
  test.describe(`a ${locale} browser`, () => {
    test.use({ locale });

    test("gets the page in its language", async ({ page }) => {
      await openDemo(page);
      await expect(page.locator("html")).toHaveAttribute("lang", t.lang);
      await expect(page.locator("#summary")).toHaveText(t.summary);
      await expect(page.locator("#count")).toHaveText(t.count);
      await expect(page.locator('#tabs [data-type="movie"]')).toHaveText(t.movies);
      await expect(card(page, "The Last Lighthouse").locator(".y").first()).toHaveText(t.month);
      await card(page, "The Quiet Coast").locator(".open").click();
      await expect(page.locator("#detail")).toContainText(t.missing);
      await expect(page.locator("#detail .rating")).toContainText("8,1");
    });
  });
