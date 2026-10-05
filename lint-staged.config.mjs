// Pre-commit: the `npm run check` tools on the staged files only
import { pyTool } from "./scripts/tools.mjs";

const q = (s) => `"${s}"`;
const ruff = q(pyTool("ruff"));
const shellcheck = q(pyTool("shellcheck"));
const files = (list) => list.map(q).join(" ");
// Windows caps a command line at about 8k characters
// if more then do CSpell check on the whole repository instead (should be init commit only)
const cspell = (list) =>
  files(list).length > 6000
    ? "cspell --no-progress --gitignore --dot ."
    : `cspell --no-progress --no-must-find-files --gitignore ${files(list)}`;

export default {
  "*.{js,mjs}": ["eslint --fix", "prettier --write"],
  "*.css": ["stylelint --fix", "prettier --write"],
  "*.{html,json,yaml}": ["prettier --write --ignore-unknown"],
  "*.md": ["prettier --write --ignore-unknown", "markdownlint-cli2 --fix"],
  "*.py": [`${ruff} check --fix`, `${ruff} format`, "pyright"],
  "docker/*.sh": [`${shellcheck} -s sh`],
  Dockerfile: [`${q(pyTool("hadolint"))}`],
  ".github/workflows/*.yaml": (list) => [
    `${q(pyTool("actionlint"))} -shellcheck ${shellcheck} -pyflakes= ${files(list)}`,
    `${q(pyTool("zizmor"))} --offline ${files(list)}`,
  ],
  "*": cspell,
};
