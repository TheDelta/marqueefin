// Accessibility (axe-core, WCAG 2.x A and AA): the page and its dialogs, in light
// and dark mode.
import AxeBuilder from "@axe-core/playwright";
import { card, expect, openDemo, test } from "./helpers.mjs";

const scan = (page) =>
  new AxeBuilder({ page })
    .withTags(["wcag2a", "wcag2aa", "wcag21a", "wcag21aa", "wcag22aa"])
    .analyze();

// "rule: element, element" per violation, so a failure says what to fix
const summary = (results) =>
  results.violations.map((v) => `${v.id}: ${v.nodes.map((n) => n.target.join(" ")).join(", ")}`);

for (const theme of ["light", "dark"]) {
  test.describe(`${theme} mode`, () => {
    test.use({ colorScheme: theme });

    test("the grid", async ({ page }) => {
      await openDemo(page);
      await card(page, "Iron Orchard").locator(".mark").click(); // the list bar too
      expect(summary(await scan(page))).toEqual([]);
    });

    test("the detail view", async ({ page }) => {
      await openDemo(page);
      await card(page, "The Quiet Coast").locator(".open").click();
      await expect(page.locator("#detail")).toBeVisible();
      expect(summary(await scan(page))).toEqual([]);
    });

    test("settings, the list and the requests", async ({ page }) => {
      await openDemo(page);
      await page.locator("#openSettings").click();
      expect(summary(await scan(page))).toEqual([]);
      await page.keyboard.press("Escape");
      await card(page, "Iron Orchard").locator(".mark").click();
      await page.locator("#texport").click();
      expect(summary(await scan(page))).toEqual([]);
      await page.keyboard.press("Escape");
      await page.locator('#tabs [data-type="requests"]').click();
      expect(summary(await scan(page))).toEqual([]);
    });

    test("comparing lists", async ({ page }) => {
      await openDemo(page);
      for (const title of ["Iron Orchard", "Saltwind"])
        await card(page, title).locator(".mark").click();
      await page.locator("#texport").click();
      const text = await page.locator("#xtext").inputValue();
      await page.locator("#xImport").click();
      await page.locator("#itext").fill(text); // the same list: everything in common
      await page.locator("#icompare").click();
      await expect(page.locator("#compare")).toBeVisible();
      expect(summary(await scan(page))).toEqual([]);
    });
  });
}
