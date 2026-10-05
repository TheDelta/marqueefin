// Browsing: tabs, search, sorting, the year view, filters, the detail view, links
// to single titles and the Requests tab.
import { card, cardTitles, expect, idOf, openDemo, test } from "./helpers.mjs";

test.beforeEach(async ({ page }) => {
  await openDemo(page);
});

test("the page shows the library grouped by year, newest first", async ({ page }) => {
  await expect(page).toHaveTitle("Movie Night");
  await expect(page.locator(".summary")).toContainText("13 movies, 4 series and 1 collection");
  await expect(page.locator("#count")).toHaveText("17 titles");
  const years = await page.locator("#grid .yh").allTextContents();
  expect(years.map((y) => y.split(" ")[0])).toEqual(["2026", "2025", "2024"]);
  await expect(page.locator("#grid .yh").first()).toContainText("– 8");
});

test("tabs show one kind each; collections only on their own tab", async ({ page }) => {
  const tab = (type) => page.locator(`#tabs [data-type="${type}"]`);
  await expect(card(page, "Wayfinders Collection")).toHaveCount(0);
  await tab("movie").click();
  await expect(page.locator("#count")).toHaveText("13 titles");
  await tab("series").click();
  await expect(page.locator("#count")).toHaveText("4 titles");
  await tab("collection").click();
  await expect(cardTitles(page)).toHaveText(["Wayfinders Collection"]);
  await expect(tab("collection")).toHaveAttribute("aria-pressed", "true");
});

test("search matches titles, years and genres", async ({ page }) => {
  await page.locator("#q").fill("coast");
  await expect(cardTitles(page)).toHaveText(["The Quiet Coast"]);
  await page.locator("#q").fill("animation");
  await expect(cardTitles(page)).toHaveText(["Orbit Street"]);
  // Accents and ß don't matter, and the second-language title counts too
  await page.locator("#q").fill("kuste");
  await expect(cardTitles(page)).toHaveText(["The Quiet Coast"]);
  await page.locator("#q").fill("no such title");
  await expect(page.locator("#grid .empty")).toBeVisible();
});

test("A to Z without the year view", async ({ page }) => {
  await page.locator("#sort").selectOption("title");
  await page.locator("#openSettings").click();
  await page.locator("label", { hasText: "Group by release year" }).click();
  await page.keyboard.press("Escape");
  await expect(page.locator("#grid .yh")).toHaveCount(0);
  const titles = await cardTitles(page).allTextContents();
  expect(titles[0]).toBe("Ember & Ash");
  expect(titles).toEqual([...titles].sort((a, b) => a.localeCompare(b)));
});

test("filters: quality and rating, with a count on the button", async ({ page }) => {
  await page.locator("#openFilters").click();
  await page.locator("#quality").selectOption("dv");
  await expect(page.locator("#count")).toHaveText("4 of 17");
  await page.locator("#rFrom").fill("8");
  await expect(page.locator("#count")).toHaveText("3 of 17");
  expect((await cardTitles(page).allTextContents()).sort()).toEqual([
    "Kitchen Brigade",
    "The Cartographer",
    "The Quiet Coast",
  ]);
  await expect(page.locator("#fcount")).toHaveText("2");
  await page.locator("#fReset").click();
  await expect(page.locator("#count")).toHaveText("17 titles");
});

test("the detail view of a series, linked by its id", async ({ page }) => {
  await card(page, "The Quiet Coast").locator(".open").click();
  const dialog = page.locator("#detail");
  await expect(dialog).toBeVisible();
  await expect(dialog.locator("#d-title")).toHaveText("The Quiet Coast");
  await expect(dialog).toContainText("missing E4–E5");
  const jellyfin = dialog.locator(".jfbtn");
  await expect(jellyfin).toHaveText(/Open in Jellyfin/);
  await expect(jellyfin).toHaveAttribute("href", /^https:\/\/jellyfin\.example\.com\//);
  await expect(dialog.locator(".yourlist h3")).toHaveText("Your list");
  await expect(dialog).toContainText("Dolby Vision");
  const id = idOf("The Quiet Coast");
  expect(new URL(page.url()).hash).toBe(`#item=${id}`);
  await page.keyboard.press("Escape");
  await expect(dialog).toBeHidden();
  expect(new URL(page.url()).hash).toBe("");
});

test("season rows: newest first, episodes, upcoming, a start date, specials", async ({ page }) => {
  const rows = page.locator("#detail .seasons li");
  await card(page, "Signal Lost").locator(".open").click();
  await expect(rows).toHaveCount(3);
  await expect(rows.nth(0)).toContainText("Season 3");
  await expect(rows.nth(0)).toContainText(/TBA.*Starts \d/);
  await expect(rows.nth(1)).toContainText("Airing");
  await expect(rows.nth(1)).toContainText(/3 of 8 episodes.*4K HDR10.*5 upcoming, next \d/);
  await page.keyboard.press("Escape");

  await card(page, "Kitchen Brigade").locator(".open").click();
  await expect(rows).toHaveCount(5);
  await expect(rows.nth(3)).toContainText("Season 1");
  await expect(rows.nth(3).locator(".su-watched")).toHaveCount(1);
  await expect(rows.last()).toContainText("Specials");
  await expect(rows.last().locator(".su-fav")).toHaveCount(1);
});

test("opening the page with #item= shows that title", async ({ page }) => {
  const id = idOf("Northbound");
  await openDemo(page, { hash: `item=${id}` });
  await expect(page.locator("#detail #d-title")).toHaveText("Northbound");
});

test("a collection lists its titles and links to them", async ({ page }) => {
  await page.locator('#tabs [data-type="collection"]').click();
  await card(page, "Wayfinders Collection").locator(".open").click();
  const dialog = page.locator("#detail");
  await expect(dialog).toContainText("Saltwind");
  await dialog.getByText("The Cartographer").first().click();
  await expect(dialog.locator("#d-title")).toHaveText("The Cartographer");
});

test("the Requests tab: request states, releases and seasons", async ({ page }) => {
  await expect(page.locator("#reqCount")).toHaveText("10");
  await page.locator('#tabs [data-type="requests"]').click();
  const rows = page.locator("#grid .req");
  const chips = (title) => rows.filter({ hasText: title }).locator(".rq-status .st");
  await expect(rows).toHaveCount(10);
  await expect(page.locator("#count")).toHaveText("10 requests");
  await expect(page.locator("#sort")).toBeHidden();
  await expect(chips("Silver Delta")).toHaveText(["Awaiting approval", /^Digital \d/]);
  await expect(chips("Harbor Lights")).toHaveText(["Released"]); // approved: no chip of its own
  await expect(rows.filter({ hasText: "Harbor Lights" }).locator(".rq-meta")).toContainText("4K");
  await expect(chips("Afterglow")).toHaveText(["In cinemas"]);
  await expect(chips("Still Water")).toHaveText([/^In cinemas \d/]);
  await expect(chips("The Glass Garden")).toHaveText(["Failed", "TBA"]);
  await expect(chips("Copper Sky")).toHaveText(["Canceled"]);
  await expect(chips("Long Way Home")).toHaveText(["Awaiting approval", "S1 aired"]);
  await expect(chips("Kitchen Brigade")).toHaveText([
    "Partly available",
    /^S1 Available/, // with the eye: season 1 is watched
    /^S5 airing, next \d/,
    /^S6 airs \d/,
    "S7 TBA",
  ]);
  await expect(chips("Kitchen Brigade").nth(1).locator(".su-watched")).toHaveCount(1);
  await expect(rows.filter({ hasText: "Kitchen Brigade" }).locator(".rq-meta")).toContainText(
    "Seasons 1, 5–7",
  );
  await expect(chips("The Quiet Coast")).toHaveText(["S2 Partial"]);
  await expect(chips("TMDB #4242")).toHaveText(["Details unavailable"]);
});

test("a request in the library opens its title; search covers requests", async ({ page }) => {
  await page.locator('#tabs [data-type="requests"]').click();
  const rows = page.locator("#grid .req");
  await expect(rows.locator(".rq-lib")).toHaveCount(2);
  await rows.filter({ hasText: "Kitchen Brigade" }).locator(".rq-lib").click();
  await expect(page.locator("#detail #d-title")).toHaveText("Kitchen Brigade");
  await page.keyboard.press("Escape");

  await page.locator("#q").fill("glass");
  await expect(rows).toHaveCount(1);
  await expect(page.locator("#count")).toHaveText("1 of 10");
  await page.locator("#q").fill("nothing like this");
  await expect(page.locator("#grid .empty")).toHaveText("No requests match.");
});

test("no sideways scrolling on a phone", async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  const overflow = await page.evaluate(
    () => document.documentElement.scrollWidth - window.innerWidth,
  );
  expect(overflow).toBeLessThanOrEqual(0);
});

test("surprise me opens a random title of the ones shown", async ({ page }) => {
  const surprise = page.locator("#surprise");
  await page.locator("#q").fill("northbound");
  await expect(cardTitles(page)).toHaveText(["Northbound"]);
  await surprise.click();
  await expect(page.locator("#detail #d-title")).toHaveText("Northbound");
  await page.keyboard.press("Escape");

  await page.locator("#q").fill("");
  await page.locator('#tabs [data-type="movie"]').click();
  await surprise.click();
  const first = await page.locator("#detail #d-title").textContent();
  const movies = await cardTitles(page).allTextContents();
  expect(movies).toContain(first);
  await page.keyboard.press("Escape");
  await surprise.click(); // never the same twice in a row
  await expect(page.locator("#detail #d-title")).not.toHaveText(first);

  await page.keyboard.press("Escape");
  await page.locator("#q").fill("nothing like this");
  await expect(surprise).toBeDisabled();
  await page.locator('#tabs [data-type="requests"]').click();
  await expect(surprise).toBeHidden();
});
