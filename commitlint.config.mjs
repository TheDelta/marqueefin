// Commit messages and pull request titles (the squash commit on main).
// .vscode/settings.json lists the same scopes; a test keeps them in sync.
export const SCOPES = [
  "ci",
  "deps-dev",
  "deps",
  "docker",
  "export",
  "i18n",
  "jellyfin",
  "page",
  "release",
  "security",
  "seerr",
];

export default {
  extends: ["@commitlint/config-conventional"],
  rules: {
    "header-max-length": [2, "always", 100], // Dependabot's titles are long
    "scope-enum": [2, "always", SCOPES],
  },
};
