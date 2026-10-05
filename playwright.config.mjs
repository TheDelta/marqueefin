// The demo page in headless Chromium. First time: `npx playwright install chromium`
import { defineConfig, devices } from "@playwright/test";

const ci = Boolean(process.env.CI);

export default defineConfig({
  testDir: "tests/e2e",
  globalSetup: "./tests/e2e/global-setup.mjs",
  globalTeardown: "./tests/e2e/global-teardown.mjs", // the coverage report
  outputDir: "test-results",
  forbidOnly: ci,
  retries: ci ? 1 : 0,
  reporter: ci ? [["github"], ["html", { open: "never" }]] : "list",
  use: {
    locale: "en-GB",
    timezoneId: "Europe/Berlin",
    reducedMotion: "reduce", // no pop-in animations to wait for (axe saw half-faded text)
    trace: "retain-on-failure",
    screenshot: "only-on-failure",
  },
  projects: [{ name: "chromium", use: { ...devices["Desktop Chrome"] } }],
});
