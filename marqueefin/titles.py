"""Titles in a second language (TMDB, via Seerr) for the page's title switch."""

import http.client
import re
from concurrent.futures import ThreadPoolExecutor, as_completed

from .cache import MISS
from .log import log, log_problems, progress_logger
from .net import describe_error
from .seerr import seerr_client

TMDB_LINK = re.compile(r"themoviedb\.org/(movie|tv|collection)/(\d+)")


# A TMDB language: ISO 639-1 (de), optionally with a region (pt-BR, zh-CN)
TITLE_LANGUAGE = re.compile(r"([a-zA-Z]{2,3})(?:[-_]([a-zA-Z]{2}))?")


def tmdb_key(item):
    """'movie:603' / 'tv:1396' / 'collection:86311' for a record (from its TMDB
    link) or a request (from its tmdb id); None without one."""
    if "tmdb" in item:
        return f"{'movie' if item['type'] == 'movie' else 'tv'}:{item['tmdb']}"
    for link in item.get("links", []):
        m = TMDB_LINK.search(link["url"])
        if m:
            return f"{m.group(1)}:{m.group(2)}"
    return None


def alt_title(sr, key, lang, cache):
    """TMDB's title for 'movie:603' in lang, '' if none. Without a translation TMDB
    returns the original title (Japanese, asked in French): that counts as none unless
    the original is in lang."""
    hit = cache.get(key, MISS)
    if hit is not MISS:
        return hit
    kind, tmdb = key.split(":")
    d = sr.get_json(f"/{kind}/{tmdb}", {"language": lang})
    title = (d.get("title") or d.get("name") or "").strip()
    original = (d.get("originalTitle") or d.get("originalName") or "").strip()
    original_lang = (d.get("originalLanguage") or "").lower()
    if title and title == original and original_lang != lang.split("-")[0]:
        title = ""  # no translation, just the original title
    cache.put(key, title)
    return title


def same_title(a, b):
    """Equal apart from case and punctuation ('American Dad!' / 'American Dad',
    'Rampage: President Down' / 'Rampage - President Down')."""
    return re.sub(r"\W", "", a.casefold()) == re.sub(r"\W", "", b.casefold())


def attach_alt_titles(a, items, cache, workers):
    """titleAlt on every record and request whose title in --title-language differs
    from the main one; the page shows it with its "Use … titles" switch on."""
    lang = a.title_language
    log(f"Fetching titles in '{lang}'...", "🌍")
    try:
        sr = seerr_client(a)
    except (OSError, ValueError) as e:
        log(f"   Skipping the '{lang}' titles: {describe_error(e)}", "⚠️")
        return
    failed = fetch_alt_titles(sr, by_tmdb_key(items), lang, cache, workers)
    differ = sum(1 for it in items if it.get("titleAlt"))
    log(f"   {differ} of {len(items)} titles differ in '{lang}' ({cache.hits} remembered)")
    log_problems(failed, f"without a '{lang}' title (shown as they are)")


def by_tmdb_key(items):
    """{TMDB key: [records and requests with it]}; requests Seerr couldn't look up have none."""
    keys = {}
    for it in items:
        k = None if it.get("unknown") else tmdb_key(it)
        if k:
            keys.setdefault(k, []).append(it)
    return keys


def fetch_alt_titles(sr, keys, lang, cache, workers):
    """Sets titleAlt where the title differs; returns the lookups that failed."""
    report, failed = progress_logger(f"'{lang}' titles"), []
    with ThreadPoolExecutor(max_workers=workers) as pool:
        futs = {pool.submit(alt_title, sr, k, lang, cache): k for k in keys}
        for n, fut in enumerate(as_completed(futs), 1):
            report(n, len(futs))
            try:
                title = fut.result()
            except (OSError, ValueError, http.client.HTTPException) as e:
                failed.append(f"{futs[fut]}: {describe_error(e)}")
                continue
            for it in keys[futs[fut]]:
                if title and not same_title(title, it["title"]):
                    it["titleAlt"] = title
    return failed
