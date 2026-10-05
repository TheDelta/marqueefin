# AGENTS.md: Marqueefin

Guidance for AI coding agents and contributors: how Marqueefin works, the decisions
behind it, and how to change it safely.

## What Marqueefin is

`export.py` exports a whole Jellyfin library (movies, series, collections) into **one
self-contained HTML page** that you share with your friends. They browse it offline
and keep their own list (wanted / owned / watched, with a rating), which they can copy
to compare with you or keep as a backup.

- The name: a marquee is the lit sign above a cinema entrance showing what's playing;
  "-fin" follows the Jellyfin community naming (Swiftfin, Findroid, Finamp) without
  using the full name. The page footer says "Not affiliated with the Jellyfin
  project."
- Inspired by
  [Jellyfin-Latest-Content-Export-To-HTML-Website](https://github.com/arab21dwc/Jellyfin-Latest-Content-Export-To-HTML-Website),
  but exports the whole library, not only the latest items.
- The page speaks English, German, French and Spanish (`src/i18n/`; French and
  Spanish are AI translations, not yet reviewed), picked from the viewer's
  browser; more languages are a JSON file each (see [docs/page.md](docs/page.md)). Titles
  can come in a second language too (`--title-language`).

## Hard constraints

- **Python standard library only** (3.10+, the oldest version with security updates;
  CI tests 3.10 and 3.14). No `pip install`. `.env` is read by a small built-in parser
  (`load_dotenv`), not python-dotenv.
- **Two browser-side dependencies from npm.** `@noble/hashes` (SHAKE256 for pages
  protected by a passphrase, audited, MIT) is bundled by esbuild into `build/page.js`;
  `src/js/noble-license.js` puts its license next to it (a test compares it with the
  package's). **Floating UI**: `package.json`
  (`@floating-ui/dom`, which pulls in `core`; `utils` is bundled in core's UMD build)
  and `package-lock.json` pin it; `npm ci` installs it into `node_modules/`
  (git-ignored). `vendor_js()` inlines the two UMD builds, each headed by its package
  name, version and full MIT license text (the license requires it in copies). Without
  `node_modules` the export logs "run `npm ci`" and the page falls back to native
  tooltips.
- **The output must stay one file, and makes no outside request.** `render_html()`
  inlines the fonts, the bundled styles (`build/page.css`), Floating UI and the bundled
  script (`build/page.js`) into `src/template.html`; posters are embedded as data URIs by default (`--posters
embed`). A Content Security Policy enforces it (see "The page's code" below).
- **HTML, CSS and JS live in `src/`**, not in the Python. The Python fills placeholders
  (`__TITLE__`, `__DATA__`, `__STYLE__`, …) in a single `re.sub` pass, so
  placeholder-like text inside titles or data is never substituted. Never write a
  placeholder name literally anywhere else in the template, including comments.
- **Secrets stay out of the repo.** `.env`, `secrets/`, the cache dir, `collection.html`
  and `*_posters/` are git-ignored. Never print an API key.
- **Don't overwrite a real `collection.html` when testing.** Write test exports
  elsewhere with `-o <path>`.

## Layout

```text
export.py            the entry point: `python export.py` (marqueefin.cli.run)
marqueefin/          the exporter, standard library only, one module per concern:
  __init__.py          version, project name and URL, ROOT (the repository / /app)
  cli.py               arguments, .env, main() and its steps (fetch_titles, add_seasons, ...)
  jellyfin.py          the Jellyfin client: titles, episodes, user data, box sets
  records.py           records, seasons and collections for the page
  media.py             resolution, HDR, codecs, audio, languages, flags
  seerr.py             requests (the Requests tab)
  titles.py            titles in a second language
  posters.py           posters; render.py: fonts, Floating UI, CSP, the page
  seal.py              the passphrase protection (PBKDF2, SHAKE256 keystream, HMAC)
  cache.py, dates.py, net.py, log.py   JsonCache, local dates, TLS + errors, the log
src/template.html    page markup with placeholders
src/js/              the page's script as ES modules: main.js opens a protected page
                     (unlock.js), then loads app.js, which starts everything
  lib.js               pure helpers (dates, text, filters, list format), unit-tested
  dom.js, store.js, i18n.js, state.js, marks.js, seen.js, format.js, icons.js
                       data, storage, texts, view state, your list, "new", shared HTML
  cards.js, grid.js, detail.js, requests.js, list.js, list-dialog.js, menu.js,
  import.js, controls.js, filters.js, header.js, tooltips.js     one per part of the page
src/css/             the styles; main.css imports the parts in cascade order
build/               page.js and page.css, bundled by `npm run build` (esbuild; git-ignored)
src/favicon.svg      the icon and logo (a cinema marquee: bulbs around an M), inlined
package.json         Floating UI for the page and the JS dev tools (+ package-lock.json)
requirements-dev.in  the Python dev tools (Ruff, zizmor, actionlint, ShellCheck, Hadolint,
                     coverage); requirements-dev.txt: the same pinned with hashes
.env.example         settings template (copy to .env)
Dockerfile           python:3.13-alpine (pinned by digest), non-root (uid 10001), tini,
                     supercronic, no pip; a Node build stage bundles the page and
                     installs Floating UI and the fonts
compose.yaml         scheduled service with SFTP upload secrets and hardening
docker/              entrypoint / run / upload / healthcheck / notify + README (setup)
docs/                exporter.md, page.md, maintenance.md: the detail (see the end)
.github/             workflows (ci, pull-request, prepare-release, release, sonar, ...),
                     CODEOWNERS, Dependabot, issue forms, PR template; CONTRIBUTING /
                     SECURITY / CODE_OF_CONDUCT.md in the root
scripts/demo_page.py a page with made-up titles and drawn posters (no server needed);
                     used for docs/preview*.png and tested
scripts/screenshots.mjs  `npm run screenshots`: docs/preview*.png from the demo page
scripts/release.py   version bump, changelog section, release notes (release workflows)
scripts/check.mjs    `npm run check` / `npm run format`: every check CI runs
scripts/tools.mjs    finds the tools (node_modules, .venv, PATH) for check.mjs and hooks
tests/               Python tests: unit + the whole export against fake_server.py
tests/js/            unit tests for src/js/lib.js (Node's test runner)
tests/e2e/           browser tests (Playwright + axe) on the demo page
.husky/              Git hooks: pre-commit (lint-staged), commit-msg, pre-push (tests)
ruff.toml  eslint.config.mjs  .stylelintrc.yaml  .prettierrc.yaml  .prettierignore
.markdownlint-cli2.yaml  cspell.config.yaml  commitlint.config.mjs
lint-staged.config.mjs  .editorconfig  .gitattributes  sonar-project.properties
.coveragerc  .hadolint.yaml  lychee.toml  playwright.config.mjs
                     tool settings
.vscode/extensions.json  recommended editor extensions (the rest of .vscode is ignored)
```

Screenshots for the docs come from the demo page, never from a real library (watched
history, copyrighted artwork).

## Running

```sh
npm ci                      # once, and after package-lock.json changes
cp .env.example .env        # JELLYFIN_URL, JELLYFIN_API_KEY (+ EXPORT_TITLE etc.)
python export.py            # writes collection.html
python export.py --help
```

- Priority: command-line flags, then real environment variables, then `.env` (current
  directory first, then the script's directory).
- Env vars: `JELLYFIN_URL`, `JELLYFIN_API_KEY`, `JELLYFIN_PUBLIC_URL`, `JELLYFIN_USER_ID`,
  `JELLYFIN_INSECURE`, `EXPORT_TITLE`, `EXPORT_OUTPUT`, `EXPORT_CACHE_DIR`,
  `EXPORT_CA_CERT`, `EXPORT_PARALLEL_PAGES`, `EXPORT_REFRESH`, `EXPORT_POSTER_FORMAT`,
  `EXPORT_TITLE_LANGUAGE`, `EXPORT_MAIN_LANGUAGES`, `SEER_URL`, `SEER_API_KEY`,
  `SEER_CLIENT_CERT`,
  `SEER_CLIENT_KEY` (`SEER_` with one R).
- `JELLYFIN_USER_ID` / `--user-id` picks whose watched / favorite status is shown
  (default: the first admin).
- **Every slow or paginated step reports progress** through `progress_logger(label)`
  (about every 10 seconds plus a final 100% line). New slow steps should too: pass
  `progress=progress_logger(...)` to `fetch_all_items` / `iter_items`, or call
  `report(n, total)` inside an `as_completed` loop.
- Reference sizes (a library of about 700 titles and 13,000 seasons / episodes):
  about 30 s with a warm cache, about 2 minutes cold; the page is about 22 MB. Above 60 MB
  (`BIG_PAGE_MB`) the log suggests smaller posters, which are most of the page; the
  page lays out only the cards on screen (`content-visibility`), see docs/page.md.

## TLS and dates

- Jellyfin and Seerr clients get their context from `tls_context()`:
  `SSLContext(PROTOCOL_TLS_CLIENT)` (certificates and host names checked), TLS 1.2
  minimum, system CAs, plus `--ca-cert` / `EXPORT_CA_CERT` for a self-signed server and
  an optional client certificate for Seerr (`post_handshake_auth`, for proxies that
  ask after the handshake). Built in a local variable (Sonar S4423 doesn't follow
  settings made on `self.ctx`).
- **The passphrase** (`EXPORT_PASSPHRASE`, or `--passphrase-file` /
  `EXPORT_PASSPHRASE_FILE`; no flag with the passphrase itself, a command line shows
  in the process list) seals the data with `seal.py`: no AES in the standard library,
  so PBKDF2-HMAC-SHA256 (600,000 rounds) for the keys, a SHAKE256 keystream and an
  HMAC-SHA256 tag (encrypt-then-MAC), the same in `unlock.js` (WebCrypto, noble's
  SHAKE256). The salt lives in the cache (`seal_salt`) so a remembered key keeps
  working; the nonce is new each export. Never log the passphrase.
- `--insecure` is an explicit opt-in with a warning in the log; its two lines carry
  `# NOSONAR` with the reason.
- Dates: `local_today()` (`datetime.now().astimezone()`), never `date.today()` or a
  naive `datetime.now()` (Ruff DTZ).

## Jellyfin and Seerr quirks (important)

- **"Group movies into collections" leaks into the API.** Without
  `CollapseBoxSetItems=false`, `/Items` replaces movies that are in a box set with the
  box set itself (movies disappear, box sets show up as "series"). Always pass it on
  movie / series queries.
- **Box sets can be duplicated** (e.g. `Ant-Man [boxset]` and `Ant-Man Collection
[boxset]`, each with some of the movies). `pick_collections` merges them by TMDB
  collection id, keeps the copy with a poster and takes the union of the members.
  Box sets with no exported members are dropped.
- **Box set members:** `/Users/{id}/Items?ParentId=<boxset>&Recursive=true` (needs
  `Recursive=true`; the user endpoint avoids a fallback per empty box set).
- **Stale duplicate season items** can exist: `/Items?IncludeItemTypes=Season` (no
  user) may return two items per season number. Only the real one has watched data,
  so `build_seasons` keeps every candidate id per season (`_ids`, removed before
  render) and takes the user data from whichever has some.
- **Release dates are local midnight stored as UTC.** East of UTC, `PremiereDate`
  looks like `2018-07-03T22:00:00Z` for 4 July. Always use `local_date()` (times from
  noon onward move to the next day); never slice `[:10]`.
- **Missing episodes** are virtual items (`LocationType == "Virtual"`, also fetched with
  `IsMissing=true`). They exist only if the metadata provider creates them; without
  them every season looks available.
- **No "updated" date for movies** (`DateLastMediaAdded` etc. come back empty). Series
  "updated" = the newest owned episode's `DateCreated`; collection "updated" = the
  newest member's "added".
- **Only movies and episodes have a `LastPlayedDate`.** A series' `lastWatched` is the
  newest play date of its episodes (`Filters=IsPlayed`, then `IsResumable`); a
  collection's is its newest member's.
- **Media info** comes from `MediaSources[].MediaStreams`. `VideoRangeType`: `DOVI`,
  `DOVIWithHDR10`, `DOVIWithEL`, `HDR10`, `HDR10Plus`, `HLG`, …; audio `Profile` carries
  "Dolby TrueHD + Dolby Atmos", "DTS-HD MA".
- **Seerr:**
  - `/tv/{id}` can return seasons with empty `airDate`, so season dates come from
    `/tv/{id}/season/{n}` episode dates (`episode_dates`).
  - Some titles fail with `500 {"message":"Unable to retrieve series."}` (e.g. gone
    from TMDB). One such title must not break the tab: it's logged and listed as
    `TMDB #<id>` with a "Details unavailable" chip (`unknown_request`).
  - Seerr's availability can lag behind Jellyfin, so `drop_fulfilled` cross-checks with
    the library by TMDB id: requested movies in the library are dropped, and a series
    request is dropped when Jellyfin has every requested season. Otherwise seasons
    that are there show as "S1 Available" / "S1 Partial". Jellyfin's season info wins;
    4K requests are kept.
- **Error logging:** `describe_error(e)` turns an HTTP error into "HTTP 500 Internal
  Server Error from /api/v1/tv/123: Unable to retrieve series." (status, endpoint and
  the JSON `message` / `error`). Per-title problems are listed with `log_problems`
  (at most 20 lines).

## The exporter

The pipeline in `main()` is one function per step (`check_args`, `connect`,
`library_ids`, `open_caches`, `fetch_titles`, `add_collections`, `add_user_data`,
`add_seasons`, `add_posters`, `add_seerr`, `write_page`); what each does, the log
style and the cache are in [docs/exporter.md](docs/exporter.md). Rules:

- What changes every day (titles, watched / favorites, episodes, season status,
  requests) is always fetched fresh; only settled things are cached (`JsonCache`).
  A cached parallel run and a `--refresh --parallel-pages 1` run must produce
  identical records and requests (tested).
- Log lines: a step starts with its emoji, details are indented three spaces,
  problems get ⚠️. `docker/run.sh` greps "Skipping " and "couldn't be downloaded"
  for its notifications: keep those words.
- The page is written to `<file>.part`, then renamed over the old file, so a web
  server never serves half a page.

## The page's code

- **ES modules in `src/js/`, bundled by esbuild** (`npm run build` -> `build/page.js`
  and `build/page.css`, an ES module inlined as `<script type="module">`, so top-level
  `await` works; the Docker image builds it in its Node stage,
  `render_html()` inlines it). `export.py` stops with "run `npm ci && npm run build`"
  when the bundle is missing. esbuild is a regular dependency (the image needs it),
  without install scripts (`--ignore-scripts` works).
- **The page's data may not be there yet.** A page protected by a passphrase is
  sealed: `main.js` imports only `unlock.js`, which fills in `#data`, `#requests` and
  `#flags` once the passphrase is right, then `import("./app.js")` (esbuild keeps it in
  the same file and evaluates those modules only then). So `unlock.js` and what it
  imports (`i18n.js`, `store.js`, `lib.js`) never import `dom.js` or anything else
  that reads the data when it loads.
- **Modules only declare.** Everything that runs at start (loading the list, building
  the cards, event listeners) is an `init…()` function, and `app.js` calls them in
  order. Modules import each other in circles (cards, list, detail, grid), which ES
  modules allow as long as nothing uses an import while the modules are still being
  evaluated: keep top-level code to constants from non-circular modules (`dom.js`,
  `i18n.js`, `store.js`, `state.js`, `lib.js`, `format.js`, `icons.js`).
- **A variable that changes lives in one module** (`seen`, the detail view's `current`,
  the menu and tooltip state): imports are read-only, so others call its functions.
- **CSS**: plain CSS, split into parts that `src/css/main.css` imports in the old
  order; that order is the cascade, so move rules between files only knowingly.
  No Sass: custom properties, native nesting (esbuild can lower it) and `@import`
  cover it.
- **Content Security Policy** (`content_security_policy()`): only the page's own
  inline `<script>` / `<style>` blocks run, by their hashes (new ones in the template
  are hashed automatically), and nothing is fetched from anywhere. So in page code:
  no inline event handlers, no `style="…"` in HTML strings (set `el.style.x`
  instead), no `eval`. A violation is a console error, which fails the browser tests.
  Text from the library always goes through `esc()`.
- **Browser storage:** every `localStorage` access is wrapped in try / catch (keys:
  `marqueefin:` + the names in `store.js`). Dates in the UI are formatted by hand from
  `YYYY-MM-DD` (`fmtDate`), never parsed with `Date`: no time-zone shifts.
- **Texts** come from `src/i18n/<code>.json` through `t(key, vars)`; every catalog has
  every key (tested). The list's tags (`[id|o]`) and the CSV header and states stay
  English, so a copied list imports in every language.
- **Wording of the list:** it's for comparing collections and for a backup, not for
  handing files over. Keep labels and docs neutral ("owned", "have it too"), never
  "received", "send me" or "download".

## Releases, CI and Docker

How to use them: [CONTRIBUTING.md](CONTRIBUTING.md),
[.github/workflows/README.md](.github/workflows/README.md),
[docker/README.md](docker/README.md). The decisions behind them:
[docs/maintenance.md](docs/maintenance.md) and the Docker README's "Design notes".
The ones a change must not undo:

- **SemVer:** env vars, CLI flags, the copied list format (text, CSV and `#list=`
  links) and the Docker tags are contracts. `__version__` in `marqueefin/__init__.py` is the only version; nobody tags
  by hand (Prepare release, then the merge publishes).
- **`CHANGELOG.md` is generated** from pull request titles (Conventional Commits), so
  the title is what counts; hand-written lines under `[Unreleased]` win.
- **Supply chain:** everything pinned exactly (npm without ranges, Python tools by
  hash, base images by digest, actions by commit SHA); `npm ci --ignore-scripts` in CI
  and the image; minimal `permissions` per job; `pull_request_target` and
  `workflow_run` workflows never run a pull request's code. zizmor checks the
  workflows.
- **`npm run check`** runs every check CI runs (Prettier, ESLint, Stylelint,
  markdownlint, CSpell, Ruff, Pyright, ShellCheck, Hadolint, actionlint, zizmor, the
  tests); `npm run format` fixes what it can.
- **Renaming a CI job** renames a required check: the `main` ruleset on GitHub must
  change with it.
- **Docker:** the container runs read-only as uid 10001 with no capabilities;
  uploads go over SFTP to a chrooted account with a pinned host key.

## Conventions

- **LF everywhere** (`.gitattributes` `* text=auto eol=lf`; only `*.cmd` / `*.bat`
  CRLF), whatever `core.autocrlf` says. `.editorconfig`: UTF-8, LF, final newline, no
  trailing spaces, 2-space indents (4 for Python and Dockerfile continuations).
- **Formatting is enforced:** Prettier (`.prettierrc.yaml`) for JavaScript, CSS,
  HTML, YAML, JSON and Markdown; Ruff for Python. Run `npm run format` after editing
  (the pre-commit hook does it for staged files). Re-read a file before patching it:
  editors format on save.
- **YAML files end in `.yaml`**, all of them (workflows, Dependabot, issue forms,
  Compose, tool configs).
- **Commits and pull request titles:** Conventional Commits (`feat:`, `fix(seerr):`,
  `docs:`, `chore(deps):`, `feat!:` for breaking changes); `commitlint.config.mjs`.
  Squash merges: the title is the commit on `main`.
- **Windows pitfall:** Python's `open(path, "w")` writes CRLF; scripts that edit repo
  files must pass `newline="\n"` (or write bytes). Shell scripts and SSH key files
  must stay LF (`/bin/sh^M: not found`; OpenSSH can reject a CRLF key).
- Keep Sonar / Ruff / IDE warnings low; short comments that explain _why_; small
  helpers. When a change is a design decision, record it where its topic lives (here or in
  `docs/`, see the end).

## Testing

All tests run without a server and without the internet.

- **Python** (`tests/`, stdlib `unittest`, `npm test`; coverage with `.coveragerc`,
  at least 85%):
  - unit tests for the helpers (dates, media, seasons, collections, requests,
    cache, rendering, `--help`, `scripts/release.py`);
  - `tests/test_export.py`: the whole export against `tests/fake_server.py`, a fake
    Jellyfin + Seerr (plus flags and TMDB covers) whose library has the quirks
    above. It checks the records, the requests, the cache on a second run, that a
    cached run and `--refresh --parallel-pages 1` give the same page, the options,
    and the error messages. A request the fake server doesn't know fails the test,
    so new API calls need a route there.
- **`src/js/lib.js`** (`tests/js/`, Node's test runner, `npm run test:js`, at least
  80% of lines): the page logic that doesn't touch the DOM (sorting, the year order,
  season ranges, FSK, the list's copy text and import). New pure logic goes there,
  exported, with a test; a module passes it plain data (`listText` gets the titles
  as `{name, years, state, …}`, not records).
- **Browser** (`tests/e2e/`, Playwright + axe, `npm run test:e2e`; first time
  `npx playwright install chromium`): the demo page (`scripts/demo_page.py
--offline`) in headless Chromium with reduced motion. Browsing, the list (states,
  rating, copy, import, old lists), settings (theme, German titles, badges, "new
  since"), phone width, and an accessibility scan (WCAG 2.2 AA) of the page and its
  dialogs in light and dark mode. Any script error fails the test.
  - `helpers.mjs`: `openDemo(page, {storage, hash, confirm})` seeds `localStorage`
    (without the `marqueefin:` prefix) before the page runs; `records()` / `idOf()`
    read the demo data; `card(page, title)`.
  - Use retrying assertions (`await expect(locator).toHaveText(...)`): the grid
    updates after input events.
  - Colors: light-theme text colors keep 4.5:1 on the page, dialogs and their own
    14% tinted chips; axe catches regressions.
  - **Coverage** (`coverage.mjs`, monocart-coverage-reports): every test records
    Chromium's V8 coverage; the global setup bundles the page with an inline source
    map into its own folder (`demo_page.py --build-dir`, so `build/` stays as exports
    need it), which maps the bundle back to `src/js/`. The teardown writes
    `coverage/e2e/` (HTML, lcov, Markdown for CI's run summary) and fails below
    `MINIMUM` (raise it with new tests). V8 counts blocks, so a range's edges can sit
    a token off; the lines are right.
  - The demo data has one of every kind the page draws differently (request states,
    releases, season states, a TBA season, specials, TMDB links): a new kind gets a
    demo entry and a test.
- **A real export** to a scratch file: `python -B export.py -o <scratch>/test.html`.
- **Screenshots for the docs:** `npm run screenshots` (`scripts/screenshots.mjs`,
  Playwright's Chromium) takes both from the demo page with a fixed viewer state (four
  titles on the list, two new), never from a real library. Run it after a visible
  change to the grid or the detail view.

## Known limitations

- **Languages:** the page speaks English, German, French and Spanish (the last two
  AI-translated); the main titles are taken as
  English. FSK colors apply to German age ratings only (other systems stay
  neutral).
- Missing-episode detection depends on the metadata provider creating virtual items.
- Jellyfin's `MinDateLastSaved` filter doesn't help for incremental fetching (metadata
  refreshes touch many items). Movie media isn't cached (it's cheap).
- Collections have no quality chips or quality filter (no media info of their own).

## More detail

| File                                                       | What's in it                                                                                                                                        |
| ---------------------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------- |
| [docs/page.md](docs/page.md)                               | The data passed to the page and every design decision of the page: views, filters, badges, the detail view, the list, Requests, i18n, tooltips, CSP |
| [docs/exporter.md](docs/exporter.md)                       | The export pipeline step by step, the log style, caching and parallel pages                                                                         |
| [docs/maintenance.md](docs/maintenance.md)                 | Versions, the changelog generator, the release flow and why it's built so, CI, Dependabot, SonarQube Cloud, rulesets, tool settings                 |
| [docker/README.md](docker/README.md#design-notes)          | The image's design: modes, upload, secrets, health, base images, Gotify                                                                             |
| [.github/workflows/README.md](.github/workflows/README.md) | Each workflow, and what to do when it fails                                                                                                         |

Read the parts that touch your change first: a change to the page's behavior starts
with `docs/page.md`, one to the release flow with `docs/maintenance.md`.
