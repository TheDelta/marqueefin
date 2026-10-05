# Maintenance: versions, releases, CI and tooling

The decisions behind the release flow, the workflows, the dependencies and the tool
settings. How to use them: [CONTRIBUTING.md](../CONTRIBUTING.md) and
[.github/workflows/README.md](../.github/workflows/README.md).

## Versions and releases

- **SemVer** (env vars, CLI flags, the copied list format and Docker tags are
  contracts; a major version means one of them breaks).
- **Single source:** `__version__` in `marqueefin/__init__.py` (with `PROJECT`, `PROJECT_URL`,
  `USER_AGENT`): `--version`, the first log line, the User-Agent, the footer, the
  `generator` meta tag. `package.json` has no version (private, it would drift).
- **CHANGELOG.md** (Keep a Changelog's layout, generated, editable): Prepare release
  adds a line per pull request since the last tag (`scripts/changelog.py`, from the
  squash titles on `main`), sorted by type into emoji sections (⚠️ Breaking changes,
  📝 Notes, hand-written ones, 🚀 Features, 🐛 Fixes, ⚡ Performance, 🌐 Translations
  for `i18n`, 🔒 Security for `security`, 📚 Documentation, 📦 Dependencies for
  `deps` / `deps-dev`, 🧰 Maintenance, also for `ci` whatever the type), "**scope:** Text by [@author] in [#12] (fixes [#9])" with explicit
  links (Markdown files don't autolink); author, bot flag and closing issues from
  GraphQL with the workflow's token. Commits without a pull request get their short
  SHA. Release commits are left out, and so is a repository's first commit before
  its first release (the import of the project; the public repository starts at
  `0.0.0` with its notes under `[Unreleased]`, and Prepare release `major` makes
  1.0.0). Lines of a squash description that are
  Conventional Commits themselves (`* fix(seerr): …`, known types only) become
  lines of their own with the same pull request (`changes()`), except one with
  the title's type and scope (GitHub's dialog repeats the title as its first line)
  and repeats. A pull request or SHA already mentioned in
  `[Unreleased]` (outside comments) isn't added again, so hand-written lines win.
  An HTML comment under `[Unreleased]` (`changelog.TEMPLATE`) says where
  highlights and breaking changes go; it's kept there and left out of a version's
  section and of the notes. `notes --github` (release page) turns the links back
  into @mentions / #refs (avatars, hovercards; bots keep their `apps/` link) and
  appends "Full Changelog". Inspired by the release notes of homepage and Sentry.
- **Release flow** (no manual tagging):
  1. Actions → **Prepare release** (`prepare-release.yaml`, input `patch` / `minor` /
     `major` / `rc` / `prepatch` / `preminor` / `premajor` / an exact version). `scripts/release.py prepare` adds the changelog lines, sets `__version__`
     and, for a final version, turns `[Unreleased]` into `[x.y.z] - <date>` with a
     fresh `[Unreleased]` above it and compare links at the bottom. It pushes
     `release/vX.Y.Z` and opens the pull request "chore(release): vX.Y.Z" (unknown
     words in the new notes in a warning box on top: they'd fail its CSpell check; titles
     without a type or a pull request number in another, `release.py titles`) with the
     notes.
  2. Review (edit the notes on that branch if needed) and squash merge.
  3. **`release.yaml`** sees a push to `main` titled `chore(release): vX.Y.Z` (the
     merged release pull request; other pull requests that touch the version
     publish nothing) that changed `__version__` to that untagged version: builds `linux/amd64` + `linux/arm64`, pushes `ghcr.io/<owner>/<repo>:x.y.z`,
     `:x.y`, `:x`, `:latest`, `:next` (named after the repo, lowercased), then
     `gh release create --target <sha>` creates the tag and the release from the
     changelog section. Notes are checked before anything is published.
     Prepare release refuses when nothing was merged since the last release (`main`'s
     newest commit carries a release tag), except to make that candidate final.
- **Why it's built this way:** pushes, tags and pull requests made with the
  workflow's `GITHUB_TOKEN` don't start other workflows (a bot's pull request at most
  waits for an approval). So the tag is created in the same run that publishes, and
  Prepare release uses the **release bot**, a GitHub App (`actions/create-github-app-token`,
  environment `release`: `APP_RELEASE_BOT_ID`, `APP_RELEASE_BOT_KEY`): its token is
  limited to this repository, contents and pull requests; its branch and pull request
  start CI and the title check like anyone's, and it's the author of the release
  commit (never whoever started the run: see the co-author note in the workflow).
  The bot makes that commit through the Git database API (tree, commit, then the
  branch), not with `git push`: GitHub signs a commit a GitHub App creates that way,
  so it shows as Verified, and the checkout keeps no credentials.
  The workflow's own token only reads. The release image is built without the Actions
  cache (zizmor: cache poisoning).
- Pushing a tag by hand (`git tag v1.2.3 && git push origin v1.2.3`) still releases;
  the tag must match `__version__` at that commit.
- **Pre-releases** (`1.0.0-rc.1`): `prepare` only changes `__version__`; the notes
  come from `[Unreleased]`, they become GitHub pre-releases, and the image gets its
  exact tag and `:next`. Bumps work like npm's (`minor` of `1.1.0-rc.1` is `1.1.0`;
  `preminor` of `1.0.0` is `1.1.0-rc.1`, counting from rc.1, not npm's rc.0); `rc`
  is the next candidate (`1.1.0-rc.1` → `1.1.0-rc.2`) and refuses a final version.
- `scripts/release.py` (stdlib): `current`, `next <how>`, `prepare <how>`,
  `notes <version>`, `--root <dir>` to work on a copy (`tests/test_release.py`).
- **Image tags:** `:latest` (newest final release), `:1` / `:1.2` (newest of that
  major / minor), `:next` (moves with every release, candidates and final ones, like
  npm's dist-tag; testers move on to the final version by themselves), `:1.2.3` /
  `:1.2.3-rc.1` (exact). No `:stable`: in Docker `latest` already means that.
  `compose.yaml` names the published image (`ghcr.io/thedelta/marqueefin:latest`);
  another tag or a local build (`build: .`, `image: marqueefin:dev`) goes into
  `compose.override.yaml`, not an environment variable. A moving tag doesn't
  update a running container: `docker compose pull && docker compose up -d` (a
  scheduled task, docker/README.md).

## CI and updates

- **One command, everywhere:** `npm run check` (`scripts/check.mjs`) runs every
  check: Prettier, ESLint, Stylelint, markdownlint, CSpell, Ruff lint + format,
  Pyright, ShellCheck, Hadolint, actionlint, zizmor, LF line endings, then the Python tests
  with coverage and the `src/js/lib.js` tests with coverage. CI's "Lint and checks"
  job runs it (`--no-tests`); `npm run format` fixes what can be fixed. Tools come
  from `node_modules` and `.venv` (or PATH), no activation needed. The browser tests
  run separately: `npm run test:e2e`.
- **Workflows** (overview for humans: `.github/workflows/README.md`; keep it in step):
  - `ci.yaml` (push to main, pull requests, by hand on release branches): "Lint and
    checks", "Tests (Python 3.10)" / "(Python 3.14)" (unit + integration tests,
    coverage table in the run summary), "Browser tests" (`src/js/lib.js` unit tests,
    Playwright, coverage of `src/js/` per module in the run summary), "Docker image
    builds" (with a smoke run and a Trivy scan).
  - `pull-request.yaml`: "PR title" (commitlint and CSpell: the title becomes a
    CHANGELOG.md line, which CSpell checks; on failure the run summary explains it).
    The commit-msg hook spell-checks the first line too.
  - `pr-title-help.yaml` (`pull_request_target`, so forks too): a comment on the
    pull request when the title fails (`scripts/pr_title.py`: commitlint's rules
    in plain words, types and their release-notes sections, scopes, unknown words;
    words in the pull request's own `cspell.config.yaml` and scopes in its
    `commitlint.config.mjs` count, both read as text through the API, never run),
    updated to
    "✅ fine now" with the release-notes line once fixed; found again by its
    `<!-- marqueefin:pr-title -->` marker. Never checks out or runs the pull
    request's code (main's checkout, the title via env); zizmor's
    dangerous-triggers finding is ignored with that reason.
  - `prepare-release.yaml`, `release.yaml`: see above.
  - Weekly, public repository only: `scorecard.yaml` (OpenSSF Scorecard, badge),
    `image-scan.yaml` (Trivy on the published `:latest`, results in the Security
    tab), `links.yaml` (lychee, `lychee.toml`).
- **Rulesets** (set up in GitHub, not in the repository) on `main`:
  - `main`: pull requests only, squash, signed and linear history, no force push or
    deletion, and the seven job names of ci.yaml and pull-request.yaml as required
    checks, from GitHub Actions only, with "require branches to be up to date", so
    every merged state has passed CI (what gets released is what was tested). **No
    bypass**, not even for admins. Renaming a job means updating it.
  - `reviews`: one approval by a code owner (`.github/CODEOWNERS`), on the latest
    push. Admins may bypass it in a pull request: GitHub doesn't let you approve your
    own, and since `main` can't be bypassed, the checks still apply. Pull requests
    from the release bot, Dependabot and contributors need the maintainer's approval
    (a leaked bot key can't merge anything).
  - Code scanning (CodeQL, public repository only) and release tags (`v*` can't move
    or be deleted; creating stays open for the Release workflow).
- **Supply chain in CI:** `npm ci --ignore-scripts` everywhere (no install script of
  any package runs; a pull request's package.json may come from a fork); Python
  tools from `requirements-dev.txt`, pinned **with hashes** (`pip-compile
--generate-hashes` from `requirements-dev.in`; Dependabot updates both); the
  read-only token only in the separate "zizmor (online audits)" step. actionlint-py
  is a source package that downloads the actionlint binary when installed (the
  one tool outside the hashes).
- **Container test** in the Docker job: the image runs once against
  `tests/fake_server.py` (`python -m tests.fake_server 8099`), hardened like
  compose.yaml, then in scheduled mode until the health check says healthy.
- **Actions are pinned to full commit SHAs** with the version as a comment
  (`actions/checkout@<sha> # v<version>`); Dependabot updates both. `persist-credentials:
false` on every checkout that doesn't push; top-level `permissions` minimal,
  widened per job. zizmor checks all of this (online audits in CI with the read-only
  token, `--offline` locally). Node's version has one source:
  `devEngines.runtime` in `package.json` (`^24`: the newest 24.x LTS). npm refuses
  `npm ci` with another major (`onFail: error`), and `actions/setup-node`
  (v7+, `node-version-file: package.json`) installs it in CI. Not `engines`: that
  field is for consumers of a published package, and this one is private. Moving to
  a new LTS is a one-line change; Dependabot doesn't touch it.
- **Dependabot** (`dependabot.yaml`, auto-merge for safe updates in
  `dependabot-auto-merge.yaml`): docker, npm, pip, github-actions; weekly, a
  7-day cooldown for new releases, Conventional Commits prefixes (`build(deps)`,
  `fix(deps)` for Floating UI, `chore(deps-dev)`, `ci(deps)`), dev tools and actions
  grouped (minor / patch).
- **Everything is pinned exactly:** npm packages in `package.json` (no ranges; `.npmrc`
  `save-exact=true` for new ones, Dependabot `versioning-strategy: increase` moves the
  pin, `tests/test_project.py` fails on a range), Python tools by hash, base images by
  digest, actions by SHA. The one range is `devEngines.runtime` (`^24`): the newest
  Node 24 LTS.
- **Release supply chain:** the image carries an SBOM and BuildKit provenance, and
  (public repository) a signed GitHub build attestation:
  `gh attestation verify oci://ghcr.io/<owner>/<repo>:1.2.3 --owner <owner>`.
- **Ruff** (`ruff.toml`): F, E9, B, UP, SIM, DTZ, C90 (max complexity 10), S, I, A, C4,
  PIE, RET, PERF, RUF; `S310` (urlopen on the user's own URLs) ignored, the en dash
  allowed (`allowed-confusables`). Pylint rules are left out on purpose. `ruff format`
  (Black's style) formats all Python. **100 columns** for all code (Ruff
  `line-length`, Prettier `printWidth`, `.editorconfig`); Markdown keeps its own
  breaks (release notes join them again, see `changelog.unwrap`).
- **Pyright** (`pyrightconfig.json`, npm, the engine behind Pylance): standard type
  checking of all Python, plus unused imports / variables / functions / classes as
  errors. Ruff misses an unused `import a.b` next to a used `import a.c` (both bind
  `a`); Pyright doesn't. Typing rules of thumb: `-> dict | None` where a function
  can return nothing, `if m is None: self.fail(...)` in tests (narrows the type;
  `assert` is Ruff S101), `shutil.which(...) or ""` for optional tools, overrides
  keep the base signature (`log_message(self, format, *args)`).
- **ESLint** (`eslint.config.mjs`): recommended rules; `src/*.js` are classic
  browser scripts. **Stylelint**: `stylelint-config-standard` with the blank-line
  rules (Prettier's job) and `no-descending-specificity` off. **Hadolint**
  (`.hadolint.yaml`): DL3018 (pinned apk versions) off, the base image is pinned.
- **Git hooks** (Husky, installed by `npm ci`): pre-commit runs lint-staged (only
  staged files, fixes restaged, one tool at a time), commit-msg runs commitlint,
  pre-push builds the page, then runs the Python and `src/js/lib.js` unit tests. The Docker build installs
  with `--ignore-scripts`, CI sets `HUSKY=0`.
- **SonarQube Cloud**, analyzed in CI (ci.yaml's `sonar` job, `sonar-project.properties`)
  for the coverage: automatic analysis can't read coverage reports. CI's jobs upload
  `coverage-python` (`coverage.xml`, Python 3.14), `coverage-js` (`npm run test:js`
  writes `coverage/js/lcov.info`) and `coverage-e2e` (`coverage/e2e/lcov.info`).
  Only `main` and pull requests from this repository's branches are analyzed; forks
  are skipped. It once ran on `workflow_run` to analyze forks with the token, but the
  scanner reads its settings (`sonar-project.properties`) from the checkout, so a
  fork could steer a run that holds the token (CodeQL's untrusted checkout, Scorecard's
  Dangerous-Workflow). Forks show up in `main`'s analysis after the merge. On pull
  requests the job waits for the quality gate (`sonar.qualitygate.wait`), so the job
  itself is the required check: skipped for a fork, it passes, while the app's
  "SonarCloud Code Analysis" check would never come and block the merge. Organization
  and project key are repository variables
  (`SONAR_ORGANIZATION`, `SONAR_PROJECT_KEY`), so the test and the public repository
  share the file. `main`'s analyses pass `sonar.projectVersion` (read with `sed`, no
  repository code runs), so with New Code = "Previous version" SonarQube shows
  what each release adds and marks releases in its Activity graph. SonarLint in the
  editor shows the same rules.
