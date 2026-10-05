// Every check CI runs; lists the failed ones at the end.
//   node scripts/check.mjs [--fix] [--no-tests]
import { spawnSync } from "node:child_process";
import { readdirSync } from "node:fs";
import { nodeTool, pyTool, root } from "./tools.mjs";

const fix = process.argv.includes("--fix");
const tests = !process.argv.includes("--no-tests");
const ci = Boolean(process.env.GITHUB_ACTIONS);
// For zizmor's online audits
const token = process.env.GH_TOKEN || process.env.GITHUB_TOKEN;

const node = (pkg, ...args) => [...nodeTool(pkg), ...args];
const py = (tool, ...args) => [pyTool(tool), ...args];
const shellScripts = readdirSync(`${root}/docker`)
  .filter((f) => f.endsWith(".sh"))
  .map((f) => `docker/${f}`);

// [name, check command, fix command (optional)]
const steps = [
  // First: the tests (and the render step of the Python tests) need the bundle
  ["Build (esbuild)", [process.execPath, "--run", "build"]],
  ["Prettier (format)", node("prettier", "--check", "."), node("prettier", "--write", ".")],
  ["ESLint", node("eslint", "."), node("eslint", "--fix", ".")],
  ["Stylelint", node("stylelint", "src/**/*.css"), node("stylelint", "--fix", "src/**/*.css")],
  ["markdownlint", node("markdownlint-cli2"), node("markdownlint-cli2", "--fix")],
  // --dot: .github and .vscode too, as the hook sees them
  ["CSpell (spelling)", node("cspell", "--no-progress", "--gitignore", "--dot", ".")],
  ["Ruff (lint)", py("ruff", "check", "."), py("ruff", "check", "--fix", ".")],
  ["Ruff (format)", py("ruff", "format", "--check", "."), py("ruff", "format", ".")],
  // Also unused imports Ruff misses (`import a.b` next to a used `import a.c`)
  ["Pyright (types)", node("pyright")],
  ["ShellCheck", py("shellcheck", "-s", "sh", ...shellScripts)],
  ["Hadolint (Dockerfile)", py("hadolint", "Dockerfile")],
  [
    "actionlint (workflows)",
    py("actionlint", "-shellcheck", pyTool("shellcheck"), "-pyflakes", ""),
  ],
  ["zizmor (workflow security)", py("zizmor", ...(token ? [] : ["--offline"]), ".github")],
  ["Line endings (LF)", null],
  ...(tests
    ? [
        [
          "Python tests (with coverage)",
          py("coverage", "run", "-m", "unittest", "discover", "-s", "tests", "-t", "."),
        ],
        ["Python coverage (.coveragerc)", py("coverage", "report")],
        [
          "JavaScript tests (src/js/lib.js, with coverage)",
          [process.execPath, "--run", "test:js"], // package.json
        ],
      ]
    : []),
];

// Files committed with CRLF (or mixed) line endings; .gitattributes wants LF
function lineEndings() {
  // git from PATH: a developer tool on the developer's own machine
  const options = { cwd: root, encoding: "utf8" };
  const out = spawnSync("git", ["ls-files", "--eol"], options); // NOSONAR
  if (out.status !== 0) return out.stderr || "git ls-files failed";
  const bad = out.stdout.split("\n").filter((l) => /^i\/(crlf|mixed)/.test(l));
  return bad.length ? `CRLF line endings in the index:\n${bad.join("\n")}` : "";
}

const failed = [];
for (const [name, check, fixCmd] of steps) {
  console.log(ci ? `::group::${name}` : `\n=== ${name}`);
  let ok;
  if (check === null) {
    const problem = lineEndings();
    if (problem) console.log(problem);
    ok = !problem;
  } else {
    const [cmd, ...args] = fix && fixCmd ? fixCmd : check;
    const run = spawnSync(cmd, args, { cwd: root, stdio: "inherit" });
    if (run.error?.code === "ENOENT")
      console.log(
        `${cmd} not found: install the Python tools with ` +
          "`pip install -r requirements-dev.txt` (see CONTRIBUTING.md)",
      );
    ok = run.status === 0;
  }
  if (ci) console.log("::endgroup::");
  if (!ok) {
    failed.push(name);
    if (ci) console.log(`::error::${name} failed`);
  }
}

console.log(
  failed.length ? `\nFailed: ${failed.join(", ")}` : `\nAll ${steps.length} checks passed.`,
);
process.exitCode = failed.length ? 1 : 0;
