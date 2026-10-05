// cspell:ignore AQAAAA
// The viewer's list: adding titles, states, rating, the copy text, import and that it
// survives a reload.
import { card, expect, idOf, openDemo, test } from "./helpers.mjs";

test("wanted → owned → watched and rated, then copied", async ({ page }) => {
  await openDemo(page);
  const tray = page.locator("#tray");
  await expect(tray).toBeHidden();

  await card(page, "Iron Orchard").locator(".mark").click();
  await expect(page.locator("#tcount")).toHaveText("1 title on your list");
  await expect(card(page, "Iron Orchard")).toHaveAttribute("data-mark", "m");

  // The state menu on the card
  await card(page, "Iron Orchard").locator(".mark").click();
  await page.locator('.markmenu [data-set="o"]').click();
  await expect(card(page, "Iron Orchard")).toHaveAttribute("data-mark", "o");

  // Watched and rated in the detail view
  await card(page, "Iron Orchard").locator(".open").click();
  await page.locator('#detail .markseg [data-set="w"]').click();
  await page.locator('#detail .myrate [data-rate="4"]').click();
  await page.keyboard.press("Escape");
  await expect(card(page, "Iron Orchard").locator(".mark")).toContainText("4");

  await page.locator("#texport").click();
  const id = idOf("Iron Orchard");
  await expect(page.locator("#xtext")).toHaveValue(
    new RegExp(
      `^\\[${id}\\|w4\\|\\d{4}-\\d\\d-\\d\\d \\d\\d:\\d\\d\\] Iron Orchard \\(2026\\) ★4/5 https://www\\.themoviedb\\.org/movie/\\d+$`,
    ),
  );
  await page.locator("label", { hasText: "Exclude ids" }).click(); // the switch's label
  await expect(page.locator("#xtext")).toHaveValue(
    /^Iron Orchard \(2026\) \(watched .*, ★4\/5\) https:\/\/www\.themoviedb\.org\/movie\/\d+$/,
  );
});

test("the list survives a reload", async ({ page }) => {
  await openDemo(page);
  await card(page, "Saltwind").locator(".mark").click();
  await page.reload();
  await expect(page.locator("#tcount")).toHaveText("1 title on your list");
  await expect(card(page, "Saltwind")).toHaveAttribute("data-mark", "m");
});

test("the Filters panel's 'Your list', and clear", async ({ page }) => {
  await openDemo(page);
  await page.locator("#openFilters").click();
  await expect(page.locator("#markF")).toBeHidden(); // nothing on the list yet
  for (const title of ["Saltwind", "Neon Tides"]) await card(page, title).locator(".mark").click();
  await expect(page.locator("#tshow")).toHaveCount(0); // not in the bar any more
  await page.locator("#markSel").selectOption("on");
  await expect(page.locator("#count")).toHaveText("2 of 17");
  await expect(page.locator("#fcount")).toHaveText("1");
  await page.locator("#markSel").selectOption("off");
  await expect(page.locator("#count")).toHaveText("15 of 17");
  await page.locator("#markSel").selectOption("m");
  await card(page, "Neon Tides").locator(".mark").click(); // wanted -> its menu
  await page.locator('.markmenu [data-set="w"]').click();
  await expect(page.locator("#count")).toHaveText("1 of 17"); // no longer wanted
  await page.locator("#tclear").click(); // confirm() answers yes
  await expect(page.locator("#tray")).toBeHidden();
  await expect(page.locator("#markF")).toBeHidden();
  await expect(page.locator("#count")).toHaveText("17 titles");
});

test("a copied list imports again, tags and CSV rows", async ({ page }) => {
  await openDemo(page);
  const text = [
    `[${idOf("Saltwind")}] Saltwind (2024)`,
    `[${idOf("Tidewater")}|w3|2026-09-12 20:15] Tidewater (2025) ★3/5`,
    `[${idOf("Northbound")}|o] Northbound (2026)`,
    `${idOf("Neon Tides")},owned,,2026-09-25T10:00:00.000Z,movie,Neon Tides,2024,https://x`,
    "[0123456789abcdef0123456789abcdef] Not in this library",
  ].join("\n");
  await page.locator("#openSettings").click();
  await page.locator("#openImport").click();
  await page.locator("#itext").fill(text);
  await page.locator("#ido").click();
  await expect(page.locator("#iok")).toContainText("1");
  await page.keyboard.press("Escape");

  await expect(page.locator("#tcount")).toHaveText("4 titles on your list");
  await expect(card(page, "Saltwind")).toHaveAttribute("data-mark", "m");
  await expect(card(page, "Tidewater")).toHaveAttribute("data-mark", "w");
  await expect(card(page, "Northbound")).toHaveAttribute("data-mark", "o");
  await expect(card(page, "Neon Tides")).toHaveAttribute("data-mark", "o");
  await expect(card(page, "Tidewater").locator(".mark")).toContainText("3");
});

test("the stored list loads, states with and without a time", async ({ page }) => {
  const marks = {
    [idOf("Saltwind")]: "o",
    [idOf("Glass Harbor")]: { s: "w", at: "2026-09-01T10:00:00Z" },
  };
  await openDemo(page, { storage: { marks } });
  await expect(card(page, "Saltwind")).toHaveAttribute("data-mark", "o");
  await expect(card(page, "Glass Harbor")).toHaveAttribute("data-mark", "w");
});

test("the state menu: arrow keys, Escape, a second click, a click elsewhere", async ({ page }) => {
  await openDemo(page);
  const mark = card(page, "Saltwind").locator(".mark");
  const menu = page.locator(".markmenu");
  await mark.click(); // on the list as wanted
  await mark.click();
  await expect(menu).toBeVisible();
  await expect(menu.locator('[aria-checked="true"]')).toBeFocused();
  await page.keyboard.press("ArrowDown");
  await expect(menu.locator('[data-set="o"]')).toBeFocused();
  await page.keyboard.press("ArrowUp");
  await page.keyboard.press("ArrowUp"); // wraps around to the last item
  await expect(menu.locator('[data-set=""]')).toBeFocused();
  await page.keyboard.press("Escape");
  await expect(menu).toBeHidden();
  await expect(mark).toBeFocused();

  await mark.click();
  await expect(menu).toBeVisible();
  await mark.click();
  await expect(menu).toBeHidden();
  await mark.click();
  await page.locator("h1").click();
  await expect(menu).toBeHidden();
  await expect(card(page, "Saltwind")).toHaveAttribute("data-mark", "m");
});

test("the list as a link: copied, opened, imported", async ({ page, context }) => {
  await context.grantPermissions(["clipboard-read", "clipboard-write"]);
  await openDemo(page);
  await card(page, "Saltwind").locator(".mark").click();
  await card(page, "Iron Orchard").locator(".mark").click();
  await page.locator("#texport").click();
  await page.locator("#xlink").click();
  await expect(page.locator("#xok")).toContainText("file on this device"); // the demo is a file
  const link = await page.evaluate(() => navigator.clipboard.readText());
  expect(link).toMatch(/#list=[\w-]+$/);

  const other = await context.newPage();
  await openDemo(other, { hash: link.split("#")[1] });
  await expect(other.locator("#import")).toBeVisible();
  await expect(other.locator("#ifrom")).toContainText("2 titles");
  await expect(other.locator("#itext")).toHaveValue(/Iron Orchard \(2026\)\n.*Saltwind \(2024\)$/);
  await other.locator("#ido").click();
  await expect(other.locator("#tcount")).toHaveText("2 titles on your list");
  expect(new URL(other.url()).hash).toBe(""); // a reload doesn't offer it again
});

test("a cut-off list link says so", async ({ page }) => {
  await openDemo(page, { hash: "list=AQAAAA" }); // the version byte and 3 stray bytes
  await expect(page.locator("#iok")).toContainText("can't be read");
});

test("comparing with a pasted list", async ({ page }) => {
  await openDemo(page, {
    storage: {
      marks: {
        [idOf("Saltwind")]: "m",
        [idOf("Neon Tides")]: { s: "w", at: "2026-09-25T10:00:00Z" },
      },
      myratings: { [idOf("Neon Tides")]: 4 },
    },
  });
  await page.locator("#texport").click();
  await page.locator("#xImport").click();
  await page
    .locator("#itext")
    .fill(
      [
        `[${idOf("Saltwind")}] Saltwind`,
        `[${idOf("Neon Tides")}|w2] Neon Tides`,
        `[${idOf("Tidewater")}|o] Tidewater`,
      ].join("\n"),
    );
  await page.locator("#icompare").click();
  const dialog = page.locator("#compare");
  await expect(dialog).toBeVisible();
  await expect(page.locator("#cmeta")).toHaveText(
    "Their list: 3 titles · Yours: 2 titles · On both: 2 titles",
  );
  const group = (name) => dialog.locator(".xgroup").filter({ hasText: name });
  await expect(group("You both want")).toContainText("Saltwind");
  await expect(group("You both watched")).toContainText("You: Watched ★4");
  await expect(group("You both watched")).toContainText("Them: Watched ★2");
  await expect(group("Only on their list")).toContainText("Tidewater");
  // Your list stays as it was
  await expect(page.locator("#tcount")).toHaveText("2 titles on your list");

  await group("Only on their list").locator(".cmpopen").click();
  await expect(page.locator("#detail #d-title")).toHaveText("Tidewater");
});
