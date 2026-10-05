import js from "@eslint/js";
import globals from "globals";

export default [
  {
    ignores: ["node_modules/", ".venv/", "build/", "coverage/", "collection.html", "demo.html"],
  },
  js.configs.recommended,
  {
    files: ["src/**/*.js"], // ES modules in the browser, bundled by esbuild
    languageOptions: {
      ecmaVersion: 2022,
      sourceType: "module",
      globals: globals.browser,
    },
  },
  {
    files: ["**/*.mjs"],
    languageOptions: {
      ecmaVersion: 2024,
      sourceType: "module",
      globals: globals.node,
    },
  },
  {
    files: ["tests/e2e/**/*.mjs"], // browser tests
    languageOptions: { globals: { ...globals.node, ...globals.browser } },
  },
  {
    rules: {
      "no-unused-vars": ["error", { args: "none" }],
      eqeqeq: ["error", "smart"],
      "no-var": "error",
      "prefer-const": "error",
    },
  },
];
