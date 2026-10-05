// Builds the page's script and styles, then the demo page (offline: no flag downloads).
// The bundle gets an inline source map, in its own folder (build/ stays as exports need it),
// so coverage.mjs can map what ran back to src/js/.
import { execFileSync } from "node:child_process";
import { mkdirSync } from "node:fs";
import path from "node:path";
import { coverage } from "./coverage.mjs";
import { DEMO, DEMO_DIR, DEMO_SEALED, PASSPHRASE, root } from "./helpers.mjs";

export default function globalSetup() {
  mkdirSync(DEMO_DIR, { recursive: true });
  const build = path.join(DEMO_DIR, "build");
  execFileSync(
    process.execPath,
    ["--run", "build", "--", `--outdir=${build}`, "--sourcemap=inline"],
    { cwd: root, stdio: "inherit" },
  );
  const python = process.env.PYTHON || "python";
  const demo = ["-B", "scripts/demo_page.py", "--offline", "--build-dir", build];
  execFileSync(python, [...demo, "-o", DEMO], { cwd: root, stdio: "inherit" });
  execFileSync(python, [...demo, "--passphrase", PASSPHRASE, "-o", DEMO_SEALED], {
    cwd: root,
    stdio: "inherit",
  });
  coverage().cleanCache();
}
