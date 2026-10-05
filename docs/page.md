# The page: data and design decisions

What the exported page shows, how it behaves, and why. The rules for the page's code
(ES modules, the Content Security Policy) are in [AGENTS.md](../AGENTS.md).

## Data model (records passed to the page as JSON)

Common fields: `id` (Jellyfin item id), `type` (`movie` | `series` | `collection`),
`title`, `sort`, `year`, `released` (local `YYYY-MM-DD`), `added`, `updated?`,
`rating` (10-point), `critic`, `cert`, `genres`, `overview`, `links[] {label, url}`,
`poster`, `media?`, `watched?` (fully watched), `watchedPct?` (partly watched),
`fav?`, `lastWatched?` (UTC, `2026-09-27T20:15:03Z`), `titleAlt?` (the title in
`--title-language`, only when it differs by more than case / punctuation; requests
have it too).

Next to the data: `#config` (`{titleLang, mainLangs}`, the export's settings) and
`#i18n` (every `src/i18n/*.json`).

- Movie: `runtime` (minutes).
- Series: `seasons`, `status`, `endYear`, `complete?`, `seasonList[]`; each season
  `{n, name, status, have, total, missing?, upcoming?, next?, year?, date?, q?}`.
- Collection: `items[]` (member ids by year), `year` / `endYear` and `released` from
  the members; `rating` is the members' average and `ratingOf` how many were averaged.
- `media`: `{res, resMixed?, codec, bits?, hdr[], audio, tracks[[lang, channels,
format, commentary?]], subLangs[], size, bitrate?, container, versions?,
episodes?}`. For series and seasons: what most episodes have (`resMixed` → "Mostly
  1080p"). Subtitle languages leave out forced subtitles.

Requests (separate `#requests` block, newest first): `{type (movie | series), tmdb,
title, year, poster (w154 TMDB cover as data URI), requested (local date), state
(pending | approved | partial | failed), is4k?, link (TMDB), release? {kind: released |
upcoming | cinema | tba | canceled, date?, what: digital | cinema} (movies), seasons?
[{n, kind: available | partial | aired | airing | upcoming | tba, date?, next?,
missing?}] (series), unknown?}`.

## Page behavior and design decisions

### Views, sorting and filters

- Tabs: All / Movies / Series / Collections / Requests. **Collections never appear
  under All, Movies or Series.**
- Default: **"Newest first" with "By year" on.** Year headings read `2026 – 22` (count
  follows the filters). Cards show the release month (`Feb 2023`, `Mar 2025–`).
- "Recently added or updated" sorts by `updated` else `added` and groups by that
  year; "Recently watched" (only with play dates) sorts by `lastWatched`, never-watched
  last under "Not watched". Both show "Added 5 days ago" / "Watched yesterday" on
  the cards and don't use split-season cards.
- Relative dates within the last 21 days (`RECENT_DAYS`, `relDay`), else "13 Oct 2018";
  the exact date (and time) on hover.
- **Surprise me** (dice button next to Settings): opens a random title of the ones the
  grid shows (tab, search, filters), never the same one twice in a row
  (`pickRandom`); hidden on Requests, disabled when nothing is shown.
- **Big libraries:** cards have `content-visibility: auto` (with
  `contain-intrinsic-size: auto 340px`), so cards off screen are neither laid out nor
  drawn: re-sorting 5,000 titles takes about 0.14 s instead of 0.54 s. `dom.js` empties
  `#data` once it's parsed (the text is mostly posters). What's left is reading the
  file (about 2 s for 5,000 titles with 25 KB posters, 171 MB): smaller posters are
  the lever, and the export log suggests them above `BIG_PAGE_MB` (60).
- Grid: posters at least 148px wide, never more than 10 per row; page up to 2200px.
- **Filters panel** (button with the number of active filters): year from–to, rating
  from–to (titles without a rating are left out while set), quality (4K and up /
  1080p / 720p / SD / HDR / Dolby Vision; hidden on Collections and without media
  info, `--no-media`), watched (partly watched counts as watched), favorites, your
  list (on it / one state / not on it, `markFilter`; shown once the list has a title,
  dropped when it's emptied), reset. Not saved between visits.
- **Split seasons** (Settings, By year on, All / Series tabs): one card per year a
  season premiered; season cards reuse the series poster and open the series with
  those seasons highlighted.
- **"New since your last visit":** `marqueefin:seen` = `{at, items: {id: changed}}`. A
  title is new when its latest change differs from what's stored. It only moves on
  with "Mark all as seen" (confirm); a first visit starts with nothing new. Header:
  "32 new since 20 Sep 2026" (toggle: only new); cards: green "New" chip top left.
- **Second title language** (`--title-language de|fr|pt-BR|…`, Seerr's
  `language=` on its TMDB lookups, works for any TMDB language): the Settings switch
  "Use {language} titles" (named in the page's language by `Intl.DisplayNames`, e.g.
  "Use German titles"; off by default) makes cards, headings, lists, Requests and the
  copy text use `titleAlt`; A to Z ignores that language's leading article
  (`ARTICLES` in lib.js: en, de, fr, es, it, pt, nl); search always matches both
  titles; the detail view shows the other title under the heading. Without Seerr,
  or when no title differs, the switch is hidden.
  - **TMDB's fallback:** without a translation TMDB answers with the _original_
    title (Japanese for a Japanese film, asked in French). `alt_title` treats a title
    equal to `originalTitle` / `originalName` in another `originalLanguage` as none.
  - The main titles are taken as English (the detail view labels them so): they're
    what Jellyfin has.

### Season statuses

Available (everything aired is there), **Airing** (everything aired is there, more to
come; counts as complete), Partial (aired episodes missing, listed as "missing
E4–E5, E7"), Missing (none), TBA (not aired yet). Specials are listed only if at least
one is there.

### Detail dialog

Left: the cover and under it watched / last watched / favorite / added / updated.
Right: back link (between a title and its collection), title with a copy-link button,
facts (month / year, runtime or seasons, age rating, ★ score), tech badges
(resolution, HDR, codec, best audio track), genres, "Part of" collection card,
overview, IMDb / TMDB / TVDB as text links with Jellyfin (`--public-url`) as an
outlined "Open in Jellyfin" button on the right (a TV icon, not Jellyfin's logo: the
project stays clear of its branding), then "Your list" as a section of its own under a
line: the switch (Wanted | Owned | Watched, Remove; rating and date under it), audio tracks (flag + "7.1 TrueHD Atmos"), subtitle
flags, file details, then seasons **newest first** or collection members.

### Links to single titles

Every title is linkable as `#item=<jellyfin id>` (`history.replaceState`, falling back
to `location.replace`). The copy-link button copies `<page URL>#item=<id>`. Clipboard:
`navigator.clipboard` gets 500 ms (it can hang on a permission prompt), then a hidden
textarea + `execCommand('copy')`.

### Poster badges and Settings

- Bottom left: ★ rating, eye (green watched / blue "65%"), heart (favorite); above
  them smaller quality chips: "4K" / "8K" and one HDR format ("DV", "HDR10+", "HDR",
  "HLG"); 1080p and below get none. Top left: "New", then "Incomplete" / "Partial".
- Settings (icon button): theme, group by year, split seasons, ratings, 4K / HDR
  chips, watched / favorite icons, the second title language, "Import a list…" and
  About; the page language on top. Chips
  are hidden with classes on `<html>` (`no-ratings`, `no-quality`, `no-status`),
  nothing is rebuilt.
- **Theme:** Auto (default, follows the system) / Light / Dark, a segmented radio
  control. A picked theme sets `data-theme` on `<html>`, which the CSS tokens and
  `color-scheme` follow. A small script in the template's `<head>` applies the saved
  choice before the first paint (no flash); `setTheme()` (`controls.js`) also points both
  `theme-color` metas at the picked theme's color.

### Requests tab (Seerr)

- Open requests only (declined / completed / fully available ones left out); several
  requests for a title are merged.
- One row per title: cover, title (TMDB link), year, "Series · Seasons 2–6 · Requested
  25 Sep 2026 · 4K", status chips. Request state as a filled chip (Awaiting approval /
  Partly available / Failed; "Approved" gets none). Colors: released or aired but not
  in the library orange, in the library green, partly green dashed, upcoming / airing
  blue, TBA grey. An eye when the exporting user has watched it; "In library ›" opens
  the title.
- Seerr API: `GET /api/v1/request?take=100&skip=..&filter=all&sort=added`, then
  `/movie/{tmdbId}` or `/tv/{tmdbId}` (`language=en`, header `X-Api-Key`). Request
  status 1 pending, 2 approved, 3 declined, 4 failed, 5 completed; media status 4
  partly available, 5 available (`status4k` for 4K). Any Seerr failure only skips the
  tab, with a logged reason.

### Badges

- FSK ratings in their official label colors (0 white, 6 yellow, 12 green, 16 blue,
  18 red); other ratings neutral.
- Community rating: **one star plus the native 10-point score** ("★ 7.5"), not
  converted to 5 stars. Collections show their members' average.
- Dolby Vision with an HDR10 / HLG base layer shows both. Best audio track: Atmos
  (TrueHD) > DTS:X > DD+ Atmos > DTS-HD MA / TrueHD > PCM / FLAC > DTS > DD+ > DD > AAC;
  more channels win ties.

### The viewer's list: states, rating, copy, import

- Stored in `localStorage` (`marqueefin:marks`) as `{id: {s, at}}` or `{id: "m"}`
  without a time; `s` is `m` **Wanted** (star, amber), `o` **Owned** (check, blue:
  they have it too), `w` **Watched** (eye, green). `at` = when the
  **state** last changed (ISO UTC); ratings don't touch it. Keyed by Jellyfin item
  id, so lists survive re-exports.
- **Wording:** the list is for comparing collections and for a backup, not for
  handing files over. Keep labels and docs neutral ("owned", "have it too"), never
  "received", "send me" or "download".
- Cards: the corner button adds a title as wanted; once on the list it shows the
  state and opens a **state menu** (Wanted / Owned / Watched / Remove), placed with
  Floating UI. Detail view: the same as a switch.
- **Personal rating** while Watched: 1–5 stars (`marqueefin:myratings`), shown under
  the switch and on the list rows; clicking the current star clears it. A rated
  watched card shows "eye 4★".
- Bottom bar (light or dark with the theme, `--tray-*` tokens): count, "Your list"
  (amber, the main action; showing only listed titles is the Filters panel's job),
  "Clear" (trash icon, red: a soft red button in light mode, dark red in dark mode).
- **"Your list" dialog:** rows grouped by state (with "Watched 3 days ago"), then the
  text to copy. Default "Titles with links", one line per title:
  `[<id>] Title (Year) <link>` wanted, `[<id>|o] …` owned, `[<id>|w4] … ★4/5 …`
  watched and rated; with the time of the last change (local time):
  `[<id>|w4|2026-09-30 14:05] …`, `[<id>|m|2026-09-30 14:05] …`. Switches: **Exclude
  ids** (state and date then follow the title: "(watched 30 Sep 2026, ★4/5)"), **Only
  wanted**. Formats: titles with links, titles only, CSV
  (`id,state,rating,updated,type,title,year,link`). Collection members are listed
  without ids, so importing doesn't add them. A hint says why to copy it: to compare
  with a friend, or as a backup (the list lives only in the browser's storage).
- **The list as a link** ("Copy as link" in the list dialog, "Only wanted" applies):
  `<page URL>#list=<base64url>` (`encodeList` / `decodeList` in lib.js): a version
  byte, then per title the id's first 8 bytes, a byte for state, rating and "a time
  follows", and the time in minutes since 2020. About 18 characters a title; nothing
  is stored anywhere. Opening one (`openSharedList`, also on `hashchange`) removes the
  hash and opens the import dialog with the list as tag text (titles not in this
  library skipped and counted), so it imports like a pasted list. A cut-off link
  (messengers shorten long ones) says so. The format is a contract like the copy
  text: decode version 1 forever.
- **Compare** ("Compare with my list" in the import dialog, for pasted text and
  opened links): `compareLists` (lib.js) groups both lists into both want, they want /
  you have or watched it, you want / they have or watched it, both watched (with both
  ratings), both have, only theirs, only yours. Rows like the list dialog's, a chip
  per side ("You: Owned", "Them: Watched ★2"), the title opens the detail view. Your
  list isn't changed.
- **Import** (Settings or the list dialog): reads every `[id|state rating|YYYY-MM-DD
HH:MM]` tag (all parts optional) and CSV rows starting `id,state,` (rating / updated
  columns optional). Replaces the list for this
  page's titles (confirm), skips ids not in the library and says how many.

### Languages as flags

- Country-flag SVGs from [flag-icons](https://github.com/lipis/flag-icons), downloaded
  once at export time, cached (`flag_<cc>.svg`), and only the languages in use are
  embedded (`#flags` block). Not emoji (Windows renders flag emoji as letters). A
  language without a flag shows its name.
- `LANGS` maps ISO 639-2 codes to 2-letter codes; `LANG_FLAGS` picks a flag by
  convention (English → UK, Arabic → Saudi Arabia, Catalan / Basque / Galician →
  regional flags).
- With more than 3 languages (audio or subtitles), only the main languages
  (`--main-languages`, default English plus the title language) and unknown stay
  visible (`foldLangs`); the rest fold into a "+5" chip listing them on hover.

### Languages of the page (i18n)

- Texts live in `src/i18n/<code>.json` (`en`, `de`, `fr`, `es`): flat keys (`"tabs.movies"`),
  `{placeholders}`, plural texts as `{"one", "other"}` objects (picked with
  `Intl.PluralRules`). `_`-keys hold formats: `_intl` (the locale for numbers,
  lists, relative times and language names), `_months`, `_weekdays`, `_date`
  ("{d} {mon} {y}" / "{d}. {mon} {y}"), `_monthYear`, `_stamp`, `_onDate` ("am
  {date}" in German), `_name`.
- `export.py` embeds all of them (`#i18n`). `pickLanguage` (lib.js) takes the
  viewer's choice (Settings → Language, `marqueefin:lang`; a change reloads with `?lang=`, which the new page saves and removes from the address: storage written right before a reload isn't always there yet), else
  the first browser language there are texts for, else English. `createI18n` gives
  `t(key, vars)` (falls back to English per key) and the formatters (`fmtDate`,
  `dayText`, `relTime`, `num`, `fmtSize`, `runtime`, `langName`, `list`).
- Template texts carry `data-i18n="key"` (text) or `data-i18n-attr="attr:key;…"`;
  `translatePage()` (`i18n.js`) fills them in at start. Without JavaScript the English texts stay.
- **Stays English on purpose:** the list's tags (`[id|o]`) and the CSV header and
  states, so a list imports in every language; the log, the docs, the link-preview
  description. Library data (overviews, genres, custom season names) is whatever
  Jellyfin has; Jellyfin's default "Season 3" / "Specials" are translated.
- Rules (tests/js): every catalog has every key, with the same placeholders; plural
  texts have `one` and `other` (French and Spanish also have "many", which falls
  back to `other`); 12 months, 7 weekdays. The page talks to friends: German "du",
  French "tu", Spanish "tú"; French puts a no-break space before `: ? !` and inside
  « ». CSpell checks each catalog with its language's dictionary
  (`@cspell/dict-de-de`, `-fr-fr`, `-es-es`). French and Spanish are AI translations
  (the README says so): reviews by native speakers are welcome.
- A new language: copy `en.json` to `<code>.json`, translate, add a browser test.
  Right-to-left languages would need layout work first.

### Tooltips

All tooltips are `data-tip` attributes, not `title` (native ones are slow and can't
be styled). One shared `#tip` element positioned by Floating UI (`computePosition` +
`offset` / `flip` / `shift`, `autoUpdate`); chosen over Tippy.js, whose last release is
from 2021 and builds on the deprecated Popper 2. Shows after 150 ms, instantly from
tip to tip, on keyboard focus, not on touch; moved into an open modal dialog (top
layer). Without Floating UI: native `title` tooltips.

### Header, footer and metadata

- Summary ("533 movies, 151 series and 67 collections") and an "Updated 2 hours ago"
  badge (exact time on hover, refreshed every minute).
- Footer: "Made with Marqueefin 1.0.0 · GitHub" (`credit_html()`, link from
  `PROJECT_URL`) and "Not affiliated with the Jellyfin project." The same lines are
  under "About" in Settings, since the footer is far away on a long library. Kept out
  of the header on purpose: the top of the page belongs to the owner's title.
- Favicon and logo `src/favicon.svg`: a cinema marquee, a dark board framed by amber
  bulbs, with an M (shapes, no text font; reads at 16px, a lighter edge for dark tab
  bars; the README shows it too). Metadata:
  description, light / dark `theme-color`, `robots: noindex, nofollow`, Open Graph,
  `generator: Marqueefin <version>`.
- Template placeholders: `STYLE VENDOR SCRIPT TITLE SUMMARY DESCRIPTION FAVICON
GENERATED UPDATED VERSION CREDIT DATA FLAGS REQUESTS SETTINGS I18N`, plus `CSP`,
  filled after the others (see below).

### Security of the page

- **Content Security Policy** (`content_security_policy()`, a meta tag first in
  `<head>`): `default-src 'none'`; `script-src` and `style-src` list the SHA-256 of
  each inline `<script>` / `<style>` block of the finished page (so the policy is
  computed last; its meta tag sits before `<title>`, so replacing the first `__CSP__`
  can never hit library text); `img-src 'self' data:` (the posters folder for
  `--posters folder`); `font-src data:`; `base-uri` / `form-action 'none'`. Even if
  text from the library slipped past `esc()`, no script of its own could run and
  nothing could be sent anywhere. Rules for page code: no inline event handlers, no
  `style="…"` in HTML strings (set `el.style.x` instead), no `eval`; every new
  inline `<script>` / `<style>` in the template is hashed automatically. A
  violation is a console error, which fails the browser tests.
  `frame-ancestors` only works as a header: the web server example sets it.
- **Fonts** (`fonts_css()`): Big Shoulders Display and Instrument Sans, the variable
  builds from Fontsource (`@fontsource-variable/*`, npm, OFL 1.1), Latin and Latin
  extended only, inlined as data URIs and headed by their license. No Google Fonts:
  that would send every viewer's address to Google (a GDPR problem in Germany, LG
  München 2022). Without `npm ci` the page uses system fonts.
- `referrer: no-referrer`: the links to IMDb / TMDB don't reveal where the page lives.
- **A page protected by a passphrase** (`marqueefin/seal.py` seals, `unlock.js` opens):
  `#data`, `#requests` and `#flags` are empty and `#sealed` holds `{v, iter, salt,
nonce, tag, ct}` (base64); `<body class="locked">` hides everything but the header
  and the passphrase form (`lock.css`), and the summary says only "Protected with a
  passphrase". The form derives the keys (PBKDF2, WebCrypto), checks the HMAC before
  decrypting, XORs the SHAKE256 keystream, fills the three blocks and lets `main.js`
  load the page. "Remember on this device" stores the derived key (`marqueefin:key`,
  with its salt; Settings → "Forget the passphrase on this device"). WebCrypto needs a
  secure context (https, localhost, a file): over plain http the form says so. The
  page is about a third bigger (base64).
- Search folds text on both sides (`searchText`: lower case, no accents, ß as ss).

### Browser storage and dates

- `localStorage` keys (per viewer, every access wrapped in try / catch): `marqueefin:`
  `marks`, `myratings`, `seen`, `format`, `noids`, `onlywanted`, `group`, `split`,
  `ratings`, `status`, `quality`, `alttitles`, `theme`, `lang`, `key`.
- UI dates are formatted by hand (`fmtDate`, `monthOf`) from `YYYY-MM-DD` with the
  language's month names and pattern: "4 Jul 2018", "4. Juli 2018"; "Sep" (not
  "Sept") in English; no `Date` parsing, so no time-zone shifts.
