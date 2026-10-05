// A page protected by a passphrase: closed until the right one, remembered on request,
// and forgotten again from Settings.
import AxeBuilder from "@axe-core/playwright";
import { PASSPHRASE, expect, openDemo, test } from "./helpers.mjs";

const unlock = async (page, passphrase, remember = false) => {
  await page.locator("#lockPass").fill(passphrase);
  if (remember) await page.locator("label", { hasText: "Remember on this device" }).click();
  await page.locator("#lockOpen").click();
};

test("closed until the right passphrase", async ({ page }) => {
  await openDemo(page, { sealed: true });
  await expect(page.locator("#lock")).toBeVisible();
  await expect(page.locator("#grid")).toBeHidden();
  await expect(page.locator("#summary")).toHaveText("Protected with a passphrase");

  await unlock(page, "not it");
  await expect(page.locator("#lockMsg")).toHaveText("That's not the passphrase.");
  await expect(page.locator("#grid .card").first()).toBeHidden();

  await unlock(page, PASSPHRASE);
  await expect(page.locator("#lock")).toBeHidden();
  await expect(page.locator("#count")).toHaveText("17 titles");
  await expect(page.locator(".summary")).toContainText("13 movies, 4 series and 1 collection");
  await page.locator('#tabs [data-type="requests"]').click();
  await expect(page.locator("#count")).toHaveText("10 requests");
});

test("asks again on the next visit, unless remembered", async ({ page }) => {
  await openDemo(page, { sealed: true });
  await unlock(page, PASSPHRASE);
  await expect(page.locator("#grid .card").first()).toBeVisible();
  await page.reload();
  await expect(page.locator("#lock")).toBeVisible();

  await unlock(page, PASSPHRASE, true);
  await expect(page.locator("#grid .card").first()).toBeVisible();
  await page.reload();
  await expect(page.locator("#grid .card").first()).toBeVisible(); // no form this time
  await expect(page.locator("#lock")).toBeHidden();

  await page.locator("#openSettings").click();
  await page.locator("#forgetKey").click();
  await expect(page.locator("#forgetKey")).toBeHidden();
  await page.reload();
  await expect(page.locator("#lock")).toBeVisible();
});

test("an unprotected page has no form or forget button", async ({ page }) => {
  await openDemo(page);
  await expect(page.locator("#lock")).toBeHidden();
  await page.locator("#openSettings").click();
  await expect(page.locator("#forgetKey")).toBeHidden();
});

for (const theme of ["light", "dark"])
  test(`the form is accessible (${theme})`, async ({ page }) => {
    await page.emulateMedia({ colorScheme: theme });
    await openDemo(page, { sealed: true });
    await expect(page.locator("#lock")).toBeVisible();
    const results = await new AxeBuilder({ page })
      .withTags(["wcag2a", "wcag2aa", "wcag21a", "wcag21aa", "wcag22aa"])
      .analyze();
    expect(results.violations.map((v) => v.id)).toEqual([]);
  });
