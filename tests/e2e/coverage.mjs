// Which lines of src/js/ the browser tests reach: Chromium's V8 coverage of the page's
// bundle, mapped back to the modules by its inline source map (see global-setup.mjs).
// Report: coverage/e2e/index.html; CI adds the summary to the run.
import path from "node:path";
import MCR from "monocart-coverage-reports";

const root = path.resolve(import.meta.dirname, "..", "..");

// Fails the run below these (in %, a little under what the tests reach); raise them
// as tests are added
const MINIMUM = { lines: 88, functions: 88, branches: 75 };

export const options = {
  name: "Browser tests: src/js",
  outputDir: path.join(root, "coverage", "e2e"),
  reports: [
    ["console-summary"],
    ["v8", { outputFile: "index.html" }],
    ["lcovonly", { file: "lcov.info" }],
    ["markdown-summary", { outputFile: "summary.md" }],
    ["markdown-details", { outputFile: "details.md" }],
  ],
  // Only the bundle (it carries the source map), not Floating UI or the theme script
  entryFilter: (entry) => entry.source?.includes("sourceMappingURL=data:"),
  sourceFilter: (file) => file.includes("src/js/"),
  sourcePath: (file) => file.slice(file.indexOf("src/js/")),
  onEnd: (results) => {
    const low = Object.entries(MINIMUM).filter(([k, min]) => results.summary[k].pct < min);
    if (low.length) {
      const text = low.map(([k, min]) => `${k} ${results.summary[k].pct}% < ${min}%`).join(", ");
      throw new Error(`Browser test coverage of src/js below the minimum: ${text}`);
    }
  },
};

let mcr;
/** Adds one page's coverage (from page.coverage.stopJSCoverage()). */
export async function addCoverage(entries) {
  mcr ??= MCR(options);
  await mcr.add(entries);
}

export const coverage = () => MCR(options);
