// Settings and per-viewer state: theme, German titles, poster badges, "new since
// your last visit".
import { card, expect, openDemo, records, test } from "./helpers.mjs";

test("the theme: auto by default, a picked one survives a reload", async ({ page }) => {
  await openDemo(page);
  const html = page.locator("html");
  await expect(html).not.toHaveAttribute("data-theme", /./);
  await page.locator("#openSettings").click();
  await page.locator(".seg label", { hasText: "Dark" }).click();
  await expect(html).toHaveAttribute("data-theme", "dark");
  await page.reload();
  await expect(html).toHaveAttribute("data-theme", "dark");
  const bar = await page
    .locator('meta[name="theme-color"]')
    .evaluateAll((m) => m.map((x) => x.content));
  expect(new Set(bar)).toEqual(new Set(["#131824"]));
  await page.locator("#openSettings").click();
  await page.locator(".seg label", { hasText: "Auto" }).click();
  await expect(html).not.toHaveAttribute("data-theme", /./);
});

test("German titles: shown on request, search finds both", async ({ page }) => {
  await openDemo(page);
  await page.locator("#openSettings").click();
  await page.locator("label", { hasText: "Use German titles" }).click();
  await page.keyboard.press("Escape");
  await expect(card(page, "Papiermonde")).toHaveCount(1);
  await page.locator("#q").fill("paper moons");
  await expect(card(page, "Papiermonde")).toHaveCount(1);
});

test("split seasons: a card per year a season premiered", async ({ page }) => {
  await openDemo(page);
  await page.locator("#openSettings").click();
  await page.locator("label", { hasText: "Split series into seasons" }).click();
  await page.keyboard.press("Escape");
  // Kitchen Brigade: seasons 1-4, one a year from 2022
  const seasons = card(page, "Kitchen Brigade");
  await expect(seasons).toHaveCount(4);
  await expect(seasons.first()).toContainText("Season 4");
  await expect(seasons.last()).toContainText("Season 1");
  await expect(seasons.last().locator(".pb-watched")).toHaveCount(1); // season 1 is watched
  await expect(card(page, "The Quiet Coast").filter({ hasText: "Partial" })).toHaveCount(1);
  // A season card opens its series with that season highlighted
  await seasons.nth(1).locator(".open").click();
  await expect(page.locator("#detail #d-title")).toHaveText("Kitchen Brigade");
  await expect(page.locator("#detail .seasons .hl")).toContainText("Season 3");
  await page.keyboard.press("Escape");
  // Sorted by when added, each series is one card again
  await page.locator("#sort").selectOption("added");
  await expect(card(page, "Kitchen Brigade")).toHaveCount(1);
});

test("poster badges can be switched off", async ({ page }) => {
  await openDemo(page);
  await page.locator("#openSettings").click();
  await page.locator("label", { hasText: "Show ratings on posters" }).click();
  await expect(page.locator("html")).toHaveClass(/no-ratings/);
  await expect(card(page, "Northbound").locator(".pb-rating")).toBeHidden();
});

test("new since the last visit, until marked as seen", async ({ page }) => {
  // A returning viewer who has seen everything except two titles
  const changed = (r) => r.updated || r.added || "";
  const seen = Object.fromEntries(
    records()
      .filter((r) => !["The Last Lighthouse", "Second Spring"].includes(r.title))
      .map((r) => [r.id, changed(r)]),
  );
  await openDemo(page, {
    storage: { seen: { at: "2026-09-20T09:00:00Z", items: seen } },
  });
  await expect(page.locator("#newToggle")).toHaveText("2 new since 20 Sep 2026");
  await expect(card(page, "Second Spring").locator(".pnew")).toBeVisible();
  await page.locator("#newToggle").click();
  await expect(page.locator("#count")).toHaveText("2 of 17");
  await page.locator("#markSeen").click(); // confirm() answers yes
  await expect(page.locator("#newToggle")).toHaveText(/^Nothing new since/);
  await expect(page.locator("#count")).toHaveText("17 titles");
});
