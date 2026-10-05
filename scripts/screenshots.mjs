// The README's screenshots (docs/preview.png, docs/preview-detail.png), taken from
// the demo page: made-up titles and drawn posters, never a real library.
//
//   npm run screenshots               (once: npx playwright install chromium)
//   npm run screenshots -- --offline  (no flag downloads: languages show as names)
import { execFileSync } from "node:child_process";
import { mkdirSync, readFileSync } from "node:fs";
import path from "node:path";
import { pathToFileURL } from "node:url";
import { chromium } from "playwright";
import { root } from "./tools.mjs";

const dir = path.join(root, "node_modules", ".cache", "marqueefin-screenshots");
const demo = path.join(dir, "demo.html");
const offline = process.argv.includes("--offline");

mkdirSync(dir, { recursive: true });
execFileSync(process.execPath, ["--run", "build"], { cwd: root, stdio: "inherit" });
execFileSync(
  process.env.PYTHON || "python",
  ["-B", "scripts/demo_page.py", ...(offline ? ["--offline"] : []), "-o", demo],
  { cwd: root, stdio: "inherit" },
);

const data = JSON.parse(
  /<script[^>]*id="data"[^>]*>([\s\S]*?)<\/script>/
    .exec(readFileSync(demo, "utf8"))[1]
    .replaceAll(String.raw`<\/`, "</"),
);
const id = (title) => data.find((d) => d.title === title).id;
const daysAgo = (n) => new Date(Date.now() - n * 864e5).toISOString();

// A viewer with four titles on their list, who last looked 11 days ago (so the two
// recently added titles are "new")
const NEW = new Set(["The Last Lighthouse", "Second Spring"]);
const storage = (theme) => ({
  "marqueefin:theme": theme,
  "marqueefin:marks": JSON.stringify({
    [id("Signal Lost")]: { s: "m", at: daysAgo(3) },
    [id("Iron Orchard")]: { s: "m", at: daysAgo(1) },
    [id("Paper Moons")]: { s: "w", at: daysAgo(4) },
    [id("Kitchen Brigade")]: { s: "o", at: daysAgo(9) },
  }),
  "marqueefin:myratings": JSON.stringify({ [id("Paper Moons")]: 4 }),
  "marqueefin:seen": JSON.stringify({
    at: daysAgo(11),
    items: Object.fromEntries(
      data.filter((d) => !NEW.has(d.title)).map((d) => [d.id, d.updated || d.added || ""]),
    ),
  }),
});

let browser;
try {
  browser = await chromium.launch();
} catch (e) {
  console.error(`${e.message}\n\nInstall the browser once: npx playwright install chromium`);
  process.exit(1);
}

async function shot(theme, file, act) {
  const page = await browser.newPage({
    viewport: { width: 1600, height: 1000 },
    colorScheme: theme,
    locale: "en-GB",
    timezoneId: "Europe/Berlin",
    reducedMotion: "reduce",
  });
  await page.addInitScript((s) => {
    for (const [k, v] of Object.entries(s)) localStorage.setItem(k, v);
  }, storage(theme));
  await page.goto(pathToFileURL(demo).href);
  await page.locator("#grid .card").first().waitFor();
  await page.evaluate("document.fonts.ready"); // runs in the page
  if (act) await act(page);
  await page.waitForTimeout(400); // the last image decodes
  await page.screenshot({ path: path.join(root, "docs", file) });
  await page.close();
  console.log(`docs/${file}`);
}

await shot("dark", "preview.png");
await shot("light", "preview-detail.png", async (page) => {
  await page
    .locator("#grid .card")
    .filter({ has: page.locator(".t", { hasText: "The Quiet Coast" }) })
    .locator(".open")
    .click();
  await page.locator("#detail #d-title").waitFor();
});
await browser.close();
