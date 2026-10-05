"""The command line: settings, then the export step by step."""

import argparse
import os
import sys
import time
import urllib.error
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime

from . import PROJECT, ROOT, __version__
from .cache import JsonCache
from .dates import local_today
from .jellyfin import (
    ITEM_FIELDS,
    Jellyfin,
    attach_user_data,
    fetch_all_items,
    fetch_collections,
    fetch_episodes,
    fetch_series_last_played,
    fetch_user_data,
    is_missing,
    user_flags,
)
from .log import fmt_duration, log, progress_logger
from .media import language_flags
from .net import describe_error, tls_context
from .posters import get_poster, store_poster
from .records import (
    attach_episodes,
    attach_seasons,
    build_record,
    build_seasons,
    collection_record,
    pick_collections,
)
from .render import render_html
from .seal import stored_salt
from .seerr import export_requests
from .titles import TITLE_LANGUAGE, attach_alt_titles


def load_dotenv(path):
    """Minimal .env reader: KEY=VALUE lines, # comments, optional quotes and
    'export ' prefix. Never overrides variables already set in the environment."""
    try:
        with open(path, encoding="utf-8-sig") as f:
            lines = f.read().splitlines()
    except OSError:
        return
    for line in lines:
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        if key.startswith("export "):
            key = key[len("export ") :].strip()
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
            value = value[1:-1]
        elif " #" in value:
            value = value.split(" #", 1)[0].rstrip()
        if key:
            os.environ.setdefault(key, value)


def env_flag(name):
    return os.environ.get(name, "").strip().lower() in ("1", "true", "yes", "on")


class HelpFormatter(argparse.ArgumentDefaultsHelpFormatter):
    """Shows defaults, except for settings that may hold a key or a private address
    (they come from .env, and --help output ends up pasted into issues)."""

    PRIVATE = frozenset({
        "url", "api_key", "seerr_url", "seerr_api_key", "seerr_client_cert",
        "seerr_client_key", "public_url", "user_id", "ca_cert",
    })  # fmt: skip

    def _get_help_string(self, action):
        if action.dest in self.PRIVATE:
            return action.help
        return super()._get_help_string(action)


def parse_args():
    # .env in the current directory wins over one next to the script
    load_dotenv(os.path.join(os.getcwd(), ".env"))
    load_dotenv(os.path.join(ROOT, ".env"))

    p = argparse.ArgumentParser(
        description=f"{PROJECT} {__version__}: export your whole Jellyfin library to one shareable HTML page.",
        formatter_class=HelpFormatter,
    )
    p.add_argument("--version", action="version", version=f"{PROJECT} {__version__}")
    p.add_argument(
        "--url",
        default=os.environ.get("JELLYFIN_URL"),
        help="Jellyfin server URL (or env JELLYFIN_URL)",
    )
    p.add_argument(
        "--api-key",
        default=os.environ.get("JELLYFIN_API_KEY"),
        help="Jellyfin API key (or env JELLYFIN_API_KEY)",
    )
    p.add_argument(
        "--output",
        "-o",
        default=os.environ.get("EXPORT_OUTPUT", "collection.html"),
        help="Output HTML file (or env EXPORT_OUTPUT)",
    )
    p.add_argument(
        "--title",
        default=os.environ.get("EXPORT_TITLE", "My collection"),
        help="Heading shown on the page (or env EXPORT_TITLE)",
    )
    p.add_argument(
        "--types",
        default="movies,series,collections",
        help="What to include, comma separated: movies, series, collections",
    )
    p.add_argument(
        "--library",
        action="append",
        default=[],
        help="Only these libraries (by name). Repeatable.",
    )
    p.add_argument(
        "--list-libraries",
        action="store_true",
        help="Print your library names and exit",
    )
    p.add_argument(
        "--no-seasons",
        action="store_true",
        help="Skip the per-season available / missing check (faster)",
    )
    p.add_argument(
        "--seerr-url",
        default=os.environ.get("SEER_URL") or None,
        help="Seerr URL for the Requests tab (or env SEER_URL)",
    )
    p.add_argument(
        "--seerr-api-key",
        default=os.environ.get("SEER_API_KEY") or None,
        help="Seerr API key, Settings > General (or env SEER_API_KEY)",
    )
    p.add_argument(
        "--seerr-client-cert",
        default=os.environ.get("SEER_CLIENT_CERT") or None,
        help="Client certificate (PEM) if a proxy in front of Seerr asks for one "
        "(or env SEER_CLIENT_CERT)",
    )
    p.add_argument(
        "--seerr-client-key",
        default=os.environ.get("SEER_CLIENT_KEY") or None,
        help="Private key (PEM) for --seerr-client-cert, if it's a separate file "
        "(or env SEER_CLIENT_KEY)",
    )
    p.add_argument(
        "--no-requests",
        action="store_true",
        help="Skip the Seerr Requests tab even if Seerr is configured",
    )
    p.add_argument(
        "--title-language",
        default=os.environ.get("EXPORT_TITLE_LANGUAGE") or None,
        help="Also look up titles in this language via Seerr (TMDB codes: de, fr, "
        "pt-BR, zh-CN, ...); viewers can switch to them on the page (or env "
        "EXPORT_TITLE_LANGUAGE)",
    )
    p.add_argument(
        "--main-languages",
        default=os.environ.get("EXPORT_MAIN_LANGUAGES") or None,
        help="Audio / subtitle languages always shown as flags, comma separated; with "
        "more than 3 languages the others fold into '+2' (default: en and the title "
        "language; or env EXPORT_MAIN_LANGUAGES)",
    )
    p.add_argument(
        "--no-user-data",
        action="store_true",
        help="Leave out your watched / favorite status (it's shown to whoever opens the page)",
    )
    p.add_argument(
        "--no-media",
        action="store_true",
        help="Skip video / audio / language info (faster: ~1 min less on big libraries)",
    )
    p.add_argument(
        "--posters",
        choices=["embed", "folder", "none"],
        default="embed",
        help="embed: posters inside the HTML (one file to send); "
        "folder: posters in a folder next to the HTML (zip both); "
        "none: no posters",
    )
    p.add_argument(
        "--passphrase-file",
        default=os.environ.get("EXPORT_PASSPHRASE_FILE") or None,
        help="Protect the page with the passphrase in this file: the library is sealed "
        "and friends type the passphrase to open it (or env EXPORT_PASSPHRASE_FILE, or "
        "the passphrase itself in env EXPORT_PASSPHRASE)",
    )
    p.add_argument("--poster-width", type=int, default=260, help="Poster width in px")
    p.add_argument("--poster-quality", type=int, default=75, help="Image quality 1-100")
    p.add_argument(
        "--poster-format",
        choices=["webp", "jpeg"],
        default=os.environ.get("EXPORT_POSTER_FORMAT", "webp"),
        help="Poster format: webp (smaller) or jpeg (or env EXPORT_POSTER_FORMAT)",
    )
    p.add_argument("--workers", type=int, default=8, help="Parallel poster downloads and lookups")
    p.add_argument(
        "--parallel-pages",
        type=int,
        default=int(os.environ.get("EXPORT_PARALLEL_PAGES") or 4),
        help="Result pages fetched from Jellyfin at the same time "
        "(1 = one after another; or env EXPORT_PARALLEL_PAGES)",
    )
    p.add_argument(
        "--refresh",
        action="store_true",
        default=env_flag("EXPORT_REFRESH"),
        help="Ignore what's remembered from earlier runs (episode file details, box set "
        "contents, Seerr lookups) and fetch everything again (or env EXPORT_REFRESH=1)",
    )
    p.add_argument(
        "--cache-dir",
        default=os.environ.get("EXPORT_CACHE_DIR", ".marqueefin_cache"),
        help="Where downloaded posters are cached between runs ('' to disable; or env EXPORT_CACHE_DIR)",
    )
    p.add_argument(
        "--public-url",
        default=os.environ.get("JELLYFIN_PUBLIC_URL") or None,
        help="Add an 'Open in Jellyfin' link using this URL "
        "(only useful for viewers with a Jellyfin account; or env JELLYFIN_PUBLIC_URL)",
    )
    p.add_argument(
        "--user-id",
        default=os.environ.get("JELLYFIN_USER_ID") or None,
        help="Jellyfin user to query as, and whose watched / favorite status to show (default: the first admin; or env JELLYFIN_USER_ID)",
    )
    p.add_argument(
        "--ca-cert",
        default=os.environ.get("EXPORT_CA_CERT") or None,
        help="Extra CA certificate (PEM) to trust, e.g. for a self-signed Jellyfin / Seerr "
        "certificate (or env EXPORT_CA_CERT)",
    )
    p.add_argument(
        "--insecure",
        action="store_true",
        default=env_flag("JELLYFIN_INSECURE"),
        help="Don't check TLS certificates at all (prefer --ca-cert; or env JELLYFIN_INSECURE=1)",
    )
    return p.parse_args()


def check_args(a):
    if not a.url or not a.api_key:
        sys.exit(
            "Error: --url and --api-key are required (or set JELLYFIN_URL / JELLYFIN_API_KEY)."
        )
    if a.ca_cert and not os.path.isfile(a.ca_cert):
        sys.exit(f"Error: CA certificate '{a.ca_cert}' not found (--ca-cert / EXPORT_CA_CERT).")
    if a.insecure:
        log(
            "Warning: --insecure: TLS certificates are not checked (use --ca-cert for a self-signed one)",
            "⚠️",
        )
    a.title_language = title_language(a)
    a.main_languages = main_languages(a)
    a.passphrase = passphrase(a)
    wanted = {t.strip().lower() for t in a.types.split(",")}
    if not wanted & {"movies", "series"}:
        sys.exit("Error: --types must include 'movies' and/or 'series'.")
    return wanted


def title_language(a):
    """--title-language normalized ("pt-br" -> "pt-BR"), or None (also without Seerr)."""
    if not a.title_language:
        return None
    m = TITLE_LANGUAGE.fullmatch(a.title_language.strip())
    if not m:
        sys.exit(
            f"Error: --title-language '{a.title_language}' isn't a language code "
            "like de, fr or pt-BR (or env EXPORT_TITLE_LANGUAGE)."
        )
    if not (a.seerr_url and a.seerr_api_key):
        log("Warning: --title-language needs Seerr (SEER_URL / SEER_API_KEY): skipped", "⚠️")
        return None
    region = f"-{m.group(2).upper()}" if m.group(2) else ""
    return m.group(1).lower() + region


def passphrase(a):
    """The passphrase that protects the page, or None: --passphrase-file /
    EXPORT_PASSPHRASE_FILE, else EXPORT_PASSPHRASE. There's no flag for the passphrase
    itself: a command line can be seen in the process list."""
    if a.passphrase_file:
        try:
            with open(a.passphrase_file, encoding="utf-8") as f:
                text = f.read().strip()
        except OSError:
            sys.exit(
                f"Error: passphrase file '{a.passphrase_file}' can't be read "
                "(--passphrase-file / EXPORT_PASSPHRASE_FILE)."
            )
    else:
        text = os.environ.get("EXPORT_PASSPHRASE", "")
    if not text:
        return None
    if a.posters == "folder":
        sys.exit(
            "Error: a page protected by a passphrase needs --posters embed "
            "(a posters folder next to it would stay readable)."
        )
    if len(text) < 12:
        log(
            "Warning: the passphrase is short. Anyone with the page can try passphrases "
            "offline: use 12+ characters, or a few words.",
            "⚠️",
        )
    log("The page is protected with a passphrase", "🔒")
    return text


def main_languages(a):
    """--main-languages as a list; by default English plus the title language."""
    default = ["en"] + ([a.title_language.split("-")[0]] if a.title_language else [])
    codes = (a.main_languages or ",".join(default)).split(",")
    return list(dict.fromkeys(x.strip().lower() for x in codes if x.strip()))


def connect(a):
    """The Jellyfin client and its libraries; exits with a clear message when the
    server can't be reached or rejects the key."""
    jf = Jellyfin(
        a.url,
        a.api_key,
        tls_context(a.ca_cert, insecure=a.insecure),
        page_workers=a.parallel_pages,
    )
    try:
        return jf, jf.libraries()
    except urllib.error.HTTPError as e:
        if e.code == 401:
            sys.exit(
                "Error: Jellyfin rejected the API key (401). Check it under Dashboard > API Keys."
            )
        sys.exit(f"Error talking to Jellyfin: {describe_error(e)}")
    except urllib.error.URLError as e:
        sys.exit(
            f"Error: can't reach {a.url} ({e.reason}). "
            "Check the URL, or pass the server's CA with --ca-cert for a self-signed certificate."
        )


def library_ids(a, libs):
    """Ids of the libraries named with --library (none: all libraries)."""
    by_name = {lib.get("Name", "").lower(): lib for lib in libs}
    ids = []
    for name in a.library or []:
        lib = by_name.get(name.lower())
        if not lib:
            sys.exit(
                f"Error: no library called '{name}'. "
                f"Available: {', '.join(lib.get('Name', '') for lib in libs)}"
            )
        ids.append(lib["ItemId"])
    return ids


def open_caches(a):
    """What's remembered between runs (a week at most, see JsonCache); posters and
    flags are cached as files next to these."""
    if a.refresh:
        log("Refresh: ignoring what's remembered from earlier runs", "🔄")
    cache_dir = a.cache_dir or None
    if cache_dir:  # also holds posters, request covers and flags
        os.makedirs(cache_dir, exist_ok=True)
    return {
        "media": JsonCache(cache_dir, "episode_media.json", 7, a.refresh),
        "boxsets": JsonCache(cache_dir, "boxsets.json", 7, a.refresh),
        "seerr": JsonCache(cache_dir, "seerr.json", 7, a.refresh),
        "titles_alt": JsonCache(
            cache_dir, f"alt_titles_{a.title_language or 'none'}.json", 30, a.refresh
        ),
    }


def fetch_titles(jf, a, wanted, parent_ids):
    """(raw items, records). CollapseBoxSetItems=false, or "group movies into
    collections" swaps movies for their box set."""
    log("Fetching library...", "📚")
    types = ",".join(t for t, key in (("Movie", "movies"), ("Series", "series")) if key in wanted)
    items = fetch_all_items(
        jf,
        types,
        parent_ids,
        a.user_id,
        fields=ITEM_FIELDS + ("" if a.no_media else ",MediaSources"),
        extra={"CollapseBoxSetItems": "false"},
        progress=progress_logger("titles"),
    )
    records = [build_record(it, a.public_url) for it in items]
    log(
        f"   found {sum(r['type'] == 'movie' for r in records)} movies, "
        f"{sum(r['type'] == 'series' for r in records)} series"
    )
    return items, records


def add_collections(jf, a, records, items, cache):
    """Collections: their own category, pointing at the movies / series above.
    Their box set items join `items`, so they get posters too."""
    log("Fetching collections...", "📦")
    by_id = {r["id"]: r for r in records}
    boxsets, members = fetch_collections(jf, a.user_id, a.workers, cache, set(by_id))
    cache.save()
    picked = pick_collections(boxsets, members, by_id)
    for b, ids in picked:
        records.append(collection_record(b, ids, by_id, a.public_url))
        items.append(b)
    log(f"   {len(picked)} collections ({len(boxsets)} box sets on the server)")


def add_user_data(jf, a, records):
    """Watched / favorite / last watched, as seen by your user (the first admin
    unless --user-id). Returns the raw user data by item id (seasons use it too)."""
    uid, uname = jf.user(a.user_id)
    if not uid:
        return {}
    log(f"Fetching watched / favorite status of '{uname}'...", "👀")
    user_data = fetch_user_data(jf, uid)
    has_series = any(r["type"] == "series" for r in records)
    series_played = fetch_series_last_played(jf, uid) if has_series else {}
    attach_user_data(records, user_data, series_played)
    log(
        f"   {sum(1 for r in records if r.get('watched'))} watched, "
        f"{sum(1 for r in records if r.get('fav'))} favorites"
    )
    return user_data


def add_seasons(jf, a, records, parent_ids, user_data, cache):
    """Seasons: what's there, what's missing, per-season watched state, and the
    series' "updated" date and media summary."""
    series_recs = [r for r in records if r["type"] == "series"]
    log("Checking seasons and episodes...", "📺")
    eps, missing_ids = fetch_episodes(jf, parent_ids, a.user_id, None if a.no_media else cache)
    cache.save()
    by_series = build_seasons(eps, missing_ids, local_today())
    owned = owned_by_series(eps, missing_ids)
    for r in series_recs:
        attach_series(r, by_series.get(r["id"]), owned.get(r["id"], []), user_data)
    incomplete = sum(1 for r in series_recs if r.get("complete") is False)
    log(
        f"   {len(eps)} seasons/episodes, {len(missing_ids)} known missing, "
        f"{incomplete} series incomplete"
    )
    if not missing_ids:
        log(
            "   (Jellyfin reported no missing episodes; if that seems wrong, your "
            "metadata provider may not be adding them, so everything shows as available)"
        )


def owned_by_series(eps, missing_ids):
    owned = {}
    for ep in eps:
        if ep.get("Type") == "Episode" and not is_missing(ep, missing_ids):
            owned.setdefault(ep.get("SeriesId"), []).append(ep)
    return owned


def attach_series(rec, seasons, owned, user_data):
    if seasons is not None:
        attach_seasons(rec, seasons)
    for s in rec.get("seasonList", []):  # watched / favorite per season
        ids = s.pop("_ids", [])
        user_flags(s, next((user_data[i] for i in ids if i in user_data), None))
    attach_episodes(rec, owned)


def add_posters(jf, a, records, items):
    """Posters, fetched in parallel and cached; a failed one gets a placeholder."""
    cache_dir = a.cache_dir or None
    if cache_dir:
        os.makedirs(cache_dir, exist_ok=True)
    folder = None
    if a.posters == "folder":
        folder = os.path.splitext(a.output)[0] + "_posters"
        os.makedirs(folder, exist_ok=True)
    by_id = {r["id"]: r for r in records}
    todo = [it for it in items if (it.get("ImageTags") or {}).get("Primary")]
    log(f"Downloading {len(todo)} posters...", "🖼️")
    failed, report = 0, progress_logger("posters")
    with ThreadPoolExecutor(max_workers=a.workers) as pool:
        futs = {
            pool.submit(
                get_poster,
                jf,
                it,
                a.poster_width,
                a.poster_quality,
                cache_dir,
                a.poster_format,
            ): it
            for it in todo
        }
        for n, fut in enumerate(as_completed(futs), 1):
            try:
                data = fut.result()
            except Exception:  # keep going, just skip this poster
                failed, data = failed + 1, None
            if data:
                store_poster(by_id[futs[fut]["Id"]], data, folder)
            report(n, len(todo))
    if failed:
        log(
            f"   {failed} posters couldn't be downloaded (those titles get a placeholder)",
            "⚠️",
        )


# Above this the log suggests smaller posters (700 titles make about 22 MB)
BIG_PAGE_MB = 60


def write_page(a, records, requests, started):
    """Render and write the page. Written next to the target, then renamed over it:
    a web server serving the file never sees a half-written page."""
    flags = language_flags(records, a.cache_dir or None)
    records.sort(key=lambda r: r["sort"])
    settings = {"titleLang": a.title_language or "", "mainLangs": a.main_languages}
    protect = (a.passphrase, stored_salt(a.cache_dir or None)) if a.passphrase else None
    page = render_html(
        a.title, records, datetime.now().astimezone(), flags, requests, settings, protect
    )
    tmp = a.output + ".part"
    with open(tmp, "w", encoding="utf-8") as f:
        f.write(page)
    os.replace(tmp, a.output)
    size_mb = os.path.getsize(a.output) / 1_048_576
    log(
        f"Done in {fmt_duration(time.monotonic() - started)}: {a.output} ({size_mb:.1f} MB)",
        "✅",
    )
    if size_mb > BIG_PAGE_MB and a.posters == "embed":
        log(
            f"The page is big ({size_mb:.0f} MB), mostly posters: it takes longer to open. "
            "Smaller posters shrink it most, e.g. --poster-width 200 --poster-quality 60 "
            "(or --posters folder)",
            "💡",
        )
    if a.posters == "folder":
        log(
            f"Send {a.output} together with the folder '{os.path.splitext(a.output)[0]}_posters' "
            "(zip them up).",
            "💡",
        )


def main():
    started = time.monotonic()
    a = parse_args()
    log(f"{PROJECT} {__version__}", "🎬")
    wanted = check_args(a)
    jf, libs = connect(a)
    if a.list_libraries:
        for lib in libs:
            print(f"{lib.get('Name')}  ({lib.get('CollectionType') or 'mixed'})")
        return
    parent_ids = library_ids(a, libs)
    caches = open_caches(a)
    seerr = a.seerr_url and a.seerr_api_key

    items, records = fetch_titles(jf, a, wanted, parent_ids)
    if "collections" in wanted:
        add_collections(jf, a, records, items, caches["boxsets"])
    user_data = {} if a.no_user_data else add_user_data(jf, a, records)
    if any(r["type"] == "series" for r in records) and not a.no_seasons:
        add_seasons(jf, a, records, parent_ids, user_data, caches["media"])
    if a.posters != "none" and items:
        add_posters(jf, a, records, items)

    requests = add_seerr(a, records, caches) if seerr else []
    write_page(a, records, requests, started)


def add_seerr(a, records, caches):
    """The Requests tab and the second-language titles, both from Seerr. Returns
    the requests."""
    requests = []
    if not a.no_requests:
        requests = export_requests(a, a.cache_dir or None, a.workers, records, caches["seerr"])
        caches["seerr"].save()
    if a.title_language:  # for the page's "Use … titles" switch
        attach_alt_titles(a, records + requests, caches["titles_alt"], a.workers)
        caches["titles_alt"].save()
    return requests


def run():
    """main(), with an error message (sys.exit("Error: ...")) logged like any other line."""
    try:
        main()
    except SystemExit as e:
        if not isinstance(e.code, str):
            raise
        log(e.code, "❌")
        sys.exit(1)
