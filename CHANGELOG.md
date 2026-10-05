# Changelog

All notable changes to Marqueefin. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and versions follow
[Semantic Versioning](https://semver.org/):

- **Major** (2.0.0): something you rely on changed: a setting or environment variable,
  a command-line flag, the copied list format, or the Docker setup.
- **Minor** (1.1.0): new features, nothing breaks.
- **Patch** (1.0.1): fixes.

The lines come from the pull requests: **Actions → Prepare release** adds one for
every pull request merged since the last release, with its author and the issues
it fixes, and opens a pull request to release them (see CONTRIBUTING.md). Each
release's notes on GitHub are its section here.

## [Unreleased]

<!--
  Prepare release adds a line here for every pull request merged since the last
  release, from its title (and from "* fix: …" lines in its squash description).
  Edit anything: a line that mentions a pull request (#12) replaces the ones that
  would be generated for it.

  - Highlights or an intro: a paragraph right here, above the first heading.
  - Breaking changes: a "⚠️ Breaking changes" section (feat!: and fix!: pull
    requests land there by themselves). Say what users have to do, e.g. which
    setting was renamed to what.
  - Upgrade notes, known issues: a "📝 Notes" section.
  - Sections: 🚀 Features, 🐛 Fixes, ⚡ Performance, 🌐 Translations,
    🔒 Security, 📚 Documentation, 📦 Dependencies, 🧰 Maintenance.
-->

The first public release. Marqueefin exports a whole Jellyfin library into one
self-contained HTML page to share with friends: they browse it offline, keep their own
list and compare it with yours.

### 🚀 Features

- **The whole library on one page:** movies, series and collections with posters
  (WebP), release month, runtime, age rating (German FSK in its label colors),
  ★ score, genres, overview and links to IMDb, TMDB, TVDB and, with `--public-url`,
  Jellyfin.
- **Picture and sound at a glance:** 4K / 1080p, Dolby Vision, HDR10(+), HLG, codec
  and bit depth, the best audio track, and every audio and subtitle language as a
  flag.
- **Seasons per series:** available, airing (with the next episode's date), partial
  (which episodes are missing), missing or TBA; optionally a card per season.
- **Browsing:** search (accents ignored, "pokemon" finds "Pokémon"), sorting (newest,
  oldest, A to Z, recently added or updated, recently watched, highest rated), a view
  grouped by release year, filters for year, rating, quality, watched, favorites and
  the viewer's list, and "Surprise me" for a random title.
- **New since the last visit:** new titles, seasons and collection entries stay
  marked until the viewer marks everything as seen.
- **The viewer's own list:** wanted, owned or watched, a 1–5 star rating and the date
  of each change. Copied as text, CSV or a link to the page, imported again on another
  device, or compared with a friend's list.
- **Requests tab** (optional, from Seerr): open requests with their approval state,
  release dates, aired seasons, and a shortcut when part of a title is already in the
  library.
- **Languages:** the page in English, German, French or Spanish (French and Spanish
  are AI translations), picked from the browser; titles in a second language on
  request (`--title-language`, any language TMDB knows).
- **Protected with a passphrase** (optional, `EXPORT_PASSPHRASE`): the library is
  sealed inside the page and opens only with the passphrase, which a browser can
  remember.
- **Private and self-contained:** no outside request at all (fonts built in, a strict
  Content Security Policy, no referrer), works offline and on phones; light, dark or
  automatic theme, with colors that keep WCAG AA contrast.
- **Fast exports:** caching between runs and parallel fetching (a 700-title library
  refreshes in about 30 seconds); big libraries stay smooth in the browser.
- **Docker image** for amd64 and arm64: scheduled runs, upload over SFTP to a
  locked-down account, Gotify notifications, a health check; with an SBOM, a signed
  build attestation and regular vulnerability scans.
- **Python standard library only**, and a demo page with made-up titles
  (`scripts/demo_page.py`) to try it without a server.
