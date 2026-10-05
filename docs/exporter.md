# The exporter: pipeline, log and cache

How `export.py` (the `marqueefin/` package) collects the library and writes the page.
The Jellyfin and Seerr quirks it works around, and the rules for changing it, are in
[AGENTS.md](../AGENTS.md).

## Pipeline

The pipeline in `main()`, one function per step (`check_args`, `connect`,
`library_ids`, `open_caches`, `fetch_titles`, `add_collections`, `add_user_data`,
`add_seasons`, `add_posters`, `add_seerr`, `write_page`):

1. Libraries: `/Library/VirtualFolders`. `--library` limits to named libraries.
2. Movies and series: `/Items`, with `CollapseBoxSetItems=false` (see the quirks in AGENTS.md) and
   `MediaSources` unless `--no-media`.
3. Collections: box sets fetched separately, members per box set, duplicates merged
   (`fetch_collections`, `pick_collections`, `collection_record`).
4. Watched / favorite status and last-watched time of the exporting Jellyfin user
   (the first admin unless `--user-id`; `fetch_user_data`, `fetch_series_last_played`,
   `attach_user_data`). Skipped with `--no-user-data`.
5. Seasons and episodes: status per season, series and season media summaries, the
   series "updated" date (`fetch_episodes`, `build_seasons`, `attach_seasons`,
   `attach_episodes`). Skipped with `--no-seasons`.
6. Posters as **WebP** (`format=Webp` on Jellyfin's image API, about a quarter smaller
   than JPEG at the same quality; `--poster-format jpeg` to go back), fetched in
   parallel and cached (`*_webp.img`). Jellyfin converts each poster once.
7. Seerr (`add_seerr`): open requests for the Requests tab (`export_requests`), then
   the titles in `--title-language` for records and requests (`attach_alt_titles`).
   Skipped without `SEER_URL` / `SEER_API_KEY`, `--no-requests` / no title language.
8. Language flags for every audio and subtitle language in use (`language_flags`).
9. Render and write (sealed first with a passphrase, `seal.py`; to `<file>.part`,
   then renamed over the old file, so a web
   server never serves half a page). The log ends with `✅ Done in 31s: <file> (<size>)`.

## Log

Log style: `log(msg, icon)`: a step starts with an emoji (📚 library, 📦 collections,
👀 watched, 📺 seasons, 🖼️ posters, 📨 requests, 🌍 titles, 🚩 flags, ✅ done), its details
are indented three spaces, problems get ⚠️ (after the indent), fatal errors ❌ (the
`sys.exit("Error: ...")` text, logged in `__main__`). Icons only when stderr is UTF-8
(`utf8_log()`); the Docker scripts use the same icons. `run.sh` greps "Skipping " and
"couldn't be downloaded" for Gotify warnings: keep those words.

## Speed: caching and parallel pages

What changes every day is always fetched fresh: titles, watched / favorites, the
episode list, missing episodes, season status, the request list.

- **Parallel pages** (`--parallel-pages`, env `EXPORT_PARALLEL_PAGES`, default 4):
  `iter_items` fetches the first page for the total, then the rest N at a time via
  `pool.map` (order kept). `1` = sequential.
- **`JsonCache`** (one JSON file per kind in the cache dir, `{key: [saved, value]}`,
  `CACHE_VERSION` guards the format): an entry lives between half and all of its
  lifetime depending on a hash of its key, so entries from one run don't expire
  together; entries not used in a run are dropped on save; files are written
  atomically. `--refresh` (env `EXPORT_REFRESH=1`) ignores them for one run.
  - `episode_media.json` (7 days): an episode's media summary by episode id. The
    episode list is fetched without `MediaSources` (about 15x cheaper) and file details
    only for unknown ids, 150 per request (`items_by_id`; 500 ids overflow the URL:
    HTTP 414). An upgraded file normally gets a new name and so a new item id; the
    expiry catches in-place swaps.
  - `boxsets.json` (7 days): members per box set, reused while `ChildCount` is
    unchanged and every remembered member still exists. `ChildCount` is **only filled
    in by `/Users/{id}/Items`** (null from `/Items`), so box sets are listed there.
  - `seerr.json` (7 days): trimmed movie / show details and season episode dates,
    **only once settled** (`SETTLED`: released / canceled movies, seasons that have
    aired or are in the library). Anything still moving is asked every run.
  - `alt_titles_<lang>.json` (30 days): the title in `--title-language` per TMDB key
    (`movie:603`, `tv:1396`, `collection:86311`), '' when TMDB has none.
- A cached parallel run and a `--refresh --parallel-pages 1` run must produce
  identical records and requests (requests are sorted by date, then title).
