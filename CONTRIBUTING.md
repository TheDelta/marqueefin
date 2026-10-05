# Contributing to Marqueefin

Thanks for taking the time to help! Bug reports, ideas, documentation fixes and code
are all welcome.

## Before you start

- **Questions** ("how do I…?", "why does…?") belong in
  [Discussions → Q&A](https://github.com/TheDelta/marqueefin/discussions/categories/q-a),
  not in issues.
- **Bugs and feature requests:** please search the
  [existing issues](https://github.com/TheDelta/marqueefin/issues) first, then use
  one of the issue forms.
- **Security problems:** please don't open a public issue. See
  [SECURITY.md](SECURITY.md).
- **Bigger changes:** open an issue or a discussion first, so we can agree on the
  approach before you spend time on it. Small fixes can go straight to a pull
  request.

Everyone taking part is expected to follow the [Code of Conduct](CODE_OF_CONDUCT.md).

## Development setup

You need Python 3.10 or newer, Node.js 24 with npm 11 (`devEngines` in
`package.json`; `npm ci` stops on another Node), and (optionally) Docker.

```sh
git clone https://github.com/TheDelta/marqueefin.git
cd marqueefin
npm ci                                  # Floating UI, the JS tools and the Git hooks
npm run build                           # the page's script and styles (src/js, src/css)
python -m venv .venv                    # the Python tools (Ruff, zizmor, actionlint, ShellCheck)
.venv/bin/pip install -r requirements-dev.txt     # Windows: .venv\Scripts\pip ...
python scripts/demo_page.py             # demo.html with made-up titles, no server needed
```

The tools are found in `node_modules` and `.venv` automatically; nothing needs to be
activated. In VS Code, accept the recommended extensions (`.vscode/extensions.json`)
to see the same findings while you type.

With a Jellyfin server, copy `.env.example` to `.env`, fill in `JELLYFIN_URL` and
`JELLYFIN_API_KEY`, and write test exports somewhere that won't be mistaken for your
real page:

```sh
python -B export.py -o /tmp/marqueefin-test.html
```

[AGENTS.md](AGENTS.md) explains how Marqueefin works and the rules for changing it:
Jellyfin's quirks, the page's code, conventions and how to test. The detail is in
`docs/`: [the page's design decisions](docs/page.md), [the export
pipeline](docs/exporter.md) and [releases, CI and tooling](docs/maintenance.md).
Read the parts that touch your change before you start.

## Ground rules

- **Python standard library only** for Marqueefin itself. Development tools are
  pinned in `requirements-dev.txt` (with hashes) and `package.json`. To change a
  Python tool, edit `requirements-dev.in` and regenerate:
  `.venv/bin/python -m piptools compile --generate-hashes --strip-extras
--no-emit-index-url requirements-dev.in -o requirements-dev.txt` (needs
  `pip install pip-tools`).
- **The output stays one self-contained HTML file.** Markup, styles and scripts live
  in `src/` and are inlined by `render_html()`; posters are embedded.
- **No secrets or personal data in the repository**: no `.env`, keys, server
  addresses, exports of your library or screenshots of it. Use the demo page for
  screenshots.
- **Match the surrounding code.** Small helpers, short comments that explain _why_.
  Formatting isn't a matter of taste here: Prettier (JavaScript, CSS, HTML, YAML,
  JSON, Markdown) and Ruff (Python) decide, `npm run format` applies them.
- **YAML files end in `.yaml`**, everywhere (workflows, Dependabot, issue forms,
  Compose, tool configs).
- **Keep the page accessible**: labels and alt text, keyboard support, contrast in
  light and dark mode.

## Checks

```sh
npm run check      # everything CI checks, then the unit tests with coverage
npm run format     # fix what can be fixed automatically (formatting, simple lint)
npm test           # only the Python tests
npm run test:js    # only the src/js/lib.js tests
npm run test:e2e   # the browser tests, with coverage (once: npx playwright install chromium)
npm run screenshots  # docs/preview*.png again, after a visible change (--offline: no flags)
docker build -t marqueefin:dev .   # if you changed the Docker setup
```

`npm run check` runs Prettier, ESLint, Stylelint, markdownlint, CSpell, Ruff (lint
and format), Pyright (Python types, unused imports), ShellCheck, Hadolint, actionlint and zizmor (GitHub Actions), a
line-ending check and the unit tests with coverage (`scripts/check.mjs`). CI runs
the same command, the browser tests and a vulnerability scan of the Docker image. What
each workflow does, and what to do when one fails:
[.github/workflows/README.md](.github/workflows/README.md).

**Git hooks** (installed by `npm ci`, via Husky):

- **pre-commit:** formats and lints only the staged files and stages the fixes
  (`lint-staged.config.mjs`).
- **commit-msg:** the message follows Conventional Commits (below).
- **pre-push:** builds the page, then the Python and `src/js/lib.js` unit tests.

CSpell knows the project's own words from `cspell.config.yaml`; add new ones there
(keep the list sorted).

**Tests** need no server or network:

- `tests/`: Python unit tests, and the whole export against a fake Jellyfin + Seerr
  (`tests/fake_server.py`). At least 85% of the Python code is covered.
- `tests/js/`: the page's pure logic in `src/js/lib.js` (at least 80%).
- `tests/e2e/`: the demo page in a real browser, with an accessibility scan. They
  measure which lines of `src/js/` run (report: `coverage/e2e/index.html`) and fail
  below the minimum in `tests/e2e/coverage.mjs`.

New logic comes with a test: in `marqueefin/` or `scripts/` a Python test, page logic
in `src/js/lib.js` with a JS test, a new page feature with a browser test. The
Jellyfin and Seerr quirks in AGENTS.md are good test cases.

For changes to the page, also open it in a browser (the demo page or a test export)
and try what you changed in light and dark mode and at a narrow window width.

## Translations

The page's texts are in `src/i18n/` (`en.json`, `de.json`, `fr.json`, `es.json`).
French and Spanish are AI translations: if you speak one of them, a pull request that
makes them sound natural is very welcome (title: `fix(i18n): …`). To add a language, copy
`en.json` to `<code>.json` (e.g. `it.json`), translate the values and keep the keys
and `{placeholders}` as they are. The `_` entries set the formats: month and
weekday names, the date pattern and the locale for numbers. `npm run check` tests
that every language has every key. A browser test in `tests/e2e/i18n.spec.mjs`
for the new language is welcome.

## Pull requests

1. Fork the repository and create a branch from `main`.
2. Keep the change focused: one fix or feature per pull request.
3. Give it a title that works as a line in the release notes: the release adds it
   to [CHANGELOG.md](CHANGELOG.md) with your name (see below). No need to edit the
   changelog yourself.
4. Update the documentation (README, `docker/README.md`, AGENTS.md) when behavior
   or settings change.
5. Fill in the pull request template: what changed, why, and how you tested it.
   Screenshots help for UI changes.

### Commit messages and pull request titles

[Conventional Commits](https://www.conventionalcommits.org): `type(scope): summary`,
lowercase, imperative, no full stop.

| Type                                                | For                                                      | In the release notes |
| --------------------------------------------------- | -------------------------------------------------------- | -------------------- |
| `feat`                                              | a new feature (minor release)                            | 🚀 Features          |
| `fix`                                               | a bug fix (patch release)                                | 🐛 Fixes             |
| `perf`                                              | faster, nothing else changes                             | ⚡ Performance       |
| `docs`                                              | documentation only                                       | 📚 Documentation     |
| `refactor`, `style`, `test`, `build`, `ci`, `chore` | code changes users don't see; Docker, workflows, tooling | 🧰 Maintenance       |

The scope can move a line: `deps` / `deps-dev` go to 📦 Dependencies, `security` to
🔒 Security, `ci` to 🧰 Maintenance (even a fix: users don't see it), `feat(i18n)` /
`fix(i18n)` to 🌐 Translations, and a breaking change (`!`) to ⚠️ Breaking changes.
`fix(page): requests without a date` becomes "**page:** Requests without a date by
@you in #12", plus "fixes #9" when the pull request closes an issue (write
`Fixes #9` in its description).

**Several changes in one pull request:** the squash description can list more,
one per line in the same format. GitHub's squash dialog already fills it with the
branch's commits (`* fix(seerr): requests without a date`); keep the ones users
should read about and delete the work-in-progress ones before merging. Each gets
its own line in the release notes, linked to the same pull request. A line with
the title's type and scope counts as the title's own change, and prose lines don't
count.

In VS Code, the recommended **Conventional Commits** extension builds the message
step by step (Source Control → its icon), so it always fits.

Scopes are optional; commitlint accepts these (`commitlint.config.mjs`): `page` (the
page), `export` (the exporter), `jellyfin`, `seerr`, `i18n` (translations), `docker`,
`ci` (workflows), `security`, `release`, `deps`, `deps-dev`. A
breaking change gets a `!` (`feat!: new list format`) and a `BREAKING CHANGE:` line
in the description.

Pull requests are **squash merged**: the title becomes the one commit on `main`, so
the title is what counts (checked in CI; if it fails, a comment on the pull request
says how to fix it); commits on your branch can be work in
progress (the commit-msg hook still asks for the format, `git commit --no-verify`
skips it). The title is spell-checked too, as it becomes a line in `CHANGELOG.md`: a
word CSpell doesn't know goes into `cspell.config.yaml` (sorted) in the same pull
request. Lines added in the squash description aren't checked until Prepare
release: it names unknown words at the top of the release pull request; fix them on
the release branch. One pull request, one change: if a title needs "and", it's probably two.

## Releases (maintainers)

Nobody tags by hand:

1. **Actions → Prepare release → Run workflow** with `patch`, `minor`, `major`, a
   release candidate (below) or an exact version. It adds a line to `[Unreleased]`
   in `CHANGELOG.md` for every pull request merged since the last release (sorted
   into 🚀 Features, 🐛 Fixes, … by their titles, with authors and fixed issues) and
   opens the pull request "chore(release): v1.2.0" with the version bump and the
   notes.
2. Check the notes and squash merge. To change them, edit `CHANGELOG.md` on that
   branch: reword lines, add highlights at the top, and **describe breaking
   changes** under "⚠️ Breaking changes" (what users have to do). The comment under
   `[Unreleased]` lists the sections. Lines can also be written in any pull request:
   one that mentions a pull request (#12) replaces its generated line.
   **Keep the commit title as GitHub suggests it** (`chore(release): v1.2.0 (#12)`):
   only a commit with that title publishes a release.
3. The merge publishes the release: the tag, the Docker image
   `ghcr.io/thedelta/marqueefin:1.2.0` (plus `:1.2`, `:1`, `:latest`, `:next`; a
   release candidate gets its own tag and `:next`) and the GitHub release.

**Release candidates** (pre-releases, like npm's bumps):

| Input                                | From `1.2.0`                               | From `1.3.0-rc.2`                           |
| ------------------------------------ | ------------------------------------------ | ------------------------------------------- |
| `prepatch` / `preminor` / `premajor` | `1.2.1-rc.1` / `1.3.0-rc.1` / `2.0.0-rc.1` | `1.3.1-rc.1` / `1.4.0-rc.1` / `2.0.0-rc.1`  |
| `rc`                                 | refused: start with a `pre…` input         | `1.3.0-rc.3`                                |
| `patch` / `minor` / `major`          | `1.2.1` / `1.3.0` / `2.0.0`                | `1.3.0` / `1.3.0` / `2.0.0` (the final one) |

`python scripts/release.py next rc` shows what a bump would give. Candidates
collect their lines under `[Unreleased]` (each `rc` adds only what's new); the
final release moves them all into its section.

The GitHub release shows the same notes with @mentions (and the contributors'
avatars) and a "Full Changelog" link: `CHANGELOG.md` is the one place to edit.

## AI-assisted contributions

Marqueefin itself is developed with AI assistance, and AI-assisted contributions are
welcome too. You're responsible for what you submit: understand it, test it, and keep
it to the change at hand. Please mention in the pull request if a substantial part
was generated.

## License

By contributing, you agree that your contributions are licensed under the project's
[MIT License](LICENSE).
