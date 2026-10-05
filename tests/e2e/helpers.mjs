// The demo page, a `page` that fails on any script error, and ways to open it
import { readFileSync } from "node:fs";
import path from "node:path";
import { pathToFileURL } from "node:url";
import { test as base, expect } from "@playwright/test";
import { addCoverage } from "./coverage.mjs";

export const root = path.resolve(import.meta.dirname, "..", "..");
// Built by global-setup.mjs; node_modules is git-ignored
export const DEMO_DIR = path.join(root, "node_modules", ".cache", "marqueefin-e2e");
export const DEMO = path.join(DEMO_DIR, "demo.html");
const DEMO_URL = pathToFileURL(DEMO).href;
// The same page protected by a passphrase (lock.spec.mjs)
export const DEMO_SEALED = path.join(DEMO_DIR, "demo-sealed.html");
export const PASSPHRASE = "correct horse battery";

export const test = base.extend({
  page: async ({ page }, use) => {
    const errors = [];
    page.on("pageerror", (e) => errors.push(e.message));
    page.on("console", (m) => {
      if (m.type() === "error") errors.push(m.text());
    });
    await page.coverage.startJSCoverage({ resetOnNavigation: false }); // reloads count too
    await use(page);
    await addCoverage(await page.coverage.stopJSCoverage());
    expect(errors, "script errors on the page").toEqual([]);
  },
});
export { expect };

/**
 * Opens the demo page. storage: localStorage entries (without the "marqueefin:"
 * prefix) set before the page's script runs; hash: e.g. "item=<id>"; confirm:
 * the answer to confirm() dialogs (default yes); sealed: the protected page, which
 * waits for its passphrase.
 */
export async function openDemo(
  page,
  { storage = {}, hash = "", confirm = true, sealed = false } = {},
) {
  await page.addInitScript(
    ({ storage, confirm }) => {
      // Only on the first load: a reload must see what the page saved
      if (!sessionStorage.getItem("seeded")) {
        sessionStorage.setItem("seeded", "1");
        localStorage.clear();
        for (const [k, v] of Object.entries(storage))
          localStorage.setItem(`marqueefin:${k}`, typeof v === "string" ? v : JSON.stringify(v));
      }
      window.confirm = () => confirm;
    },
    { storage, confirm },
  );
  if (sealed) return page.goto(pathToFileURL(DEMO_SEALED).href); // the passphrase first
  await page.goto(DEMO_URL + (hash ? `#${hash}` : ""));
  await expect(page.locator("#grid .card").first()).toBeVisible();
}

/** The demo page's records (its #data block), e.g. to look up ids by title. */
export function records() {
  const page = readFileSync(DEMO, "utf8");
  const json = /<script[^>]*id="data"[^>]*>([\s\S]*?)<\/script>/.exec(page)[1];
  return JSON.parse(json.replaceAll(String.raw`<\/`, "</"));
}

export const idOf = (title) => records().find((r) => r.title === title).id;

export const card = (page, title) =>
  page.locator("#grid .card").filter({ has: page.locator(".t", { hasText: title }) });

/** The titles in the grid; with expect(...).toHaveText([...]) it waits for them. */
export const cardTitles = (page) => page.locator("#grid .card .t");
