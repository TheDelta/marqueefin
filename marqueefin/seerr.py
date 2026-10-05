"""Seerr requests: titles asked for but not in the library yet."""

import base64
import http.client
import json
import os
import re
import ssl
import urllib.error
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed

from . import USER_AGENT
from .cache import JsonCache
from .dates import local_today, utc_to_local_date, year_of
from .log import log, log_problems, progress_logger
from .net import describe_error, tls_context
from .posters import sniff_mime

TMDB_POSTER = "https://image.tmdb.org/t/p/w154{}"
REQ_PENDING, REQ_DECLINED, REQ_FAILED, REQ_COMPLETED = 1, 3, 4, 5
MEDIA_PARTIAL, MEDIA_AVAILABLE = 4, 5


class Seerr:
    """Minimal Seerr (Overseerr / Jellyseerr) API client."""

    def __init__(self, url, api_key, ctx=None, timeout=30):
        self.base = url.rstrip("/") + "/api/v1"
        self.key = api_key
        self.timeout = timeout
        self.ctx = ctx or tls_context()

    def get_json(self, path, params=None):
        url = self.base + path + ("?" + urllib.parse.urlencode(params) if params else "")
        req = urllib.request.Request(
            url,
            headers={
                "X-Api-Key": self.key,
                "Accept": "application/json",
                "User-Agent": USER_AGENT
            },
        )  # fmt: skip
        with urllib.request.urlopen(req, timeout=self.timeout, context=self.ctx) as r:
            return json.loads(r.read())


def fetch_requests(sr):
    out, skip, report = [], 0, progress_logger("requests")
    while True:
        data = sr.get_json(
            "/request", {"take": 100, "skip": skip, "filter": "all", "sort": "added"}
        )
        results = data.get("results") or []
        out += results
        skip += len(results)
        total = (data.get("pageInfo") or {}).get("results", skip)
        report(skip, total)
        if not results or skip >= total:
            return out


def request_state(req, media, status_key):
    if req.get("status") == REQ_PENDING:
        return "pending"  # waiting for approval
    if req.get("status") == REQ_FAILED:
        return "failed"
    return "partial" if media.get(status_key) == MEDIA_PARTIAL else "approved"


def requested_seasons(req, media, status_key):
    """(requested seasons without the declined ones, those Seerr says are available)"""
    have = {s.get("seasonNumber") for s in media.get("seasons") or []
            if s.get(status_key) == MEDIA_AVAILABLE}  # fmt: skip
    asked = {s["seasonNumber"] for s in req.get("seasons") or [] if s.get("status") != REQ_DECLINED}
    return asked, have & asked


def unfulfilled(requests):
    """Requests still open: no declined or completed ones, no fully available titles.
    Available seasons stay listed ("S1 Available")."""
    for req in requests:
        media, is4k = req.get("media") or {}, bool(req.get("is4k"))
        status_key = "status4k" if is4k else "status"
        if (req.get("status") in (REQ_DECLINED, REQ_COMPLETED) or not media.get("tmdbId")
                or media.get(status_key) == MEDIA_AVAILABLE):  # fmt: skip
            continue
        seasons, have = (
            requested_seasons(req, media, status_key) if req.get("type") == "tv" else (set(), set())
        )
        if req.get("type") == "tv" and seasons <= have:
            continue
        yield {
            "type": req.get("type"),
            "tmdb": media["tmdbId"],
            "is4k": is4k,
            "seasons": seasons,
            "seerr_have": have,
            "requested": utc_to_local_date(req.get("createdAt")),
            "state": request_state(req, media, status_key)
        }  # fmt: skip


def open_requests(requests):
    """One entry per title: separate requests merged, with the earliest date and the
    least advanced state."""
    order = ("failed", "pending", "approved", "partial")
    merged = {}
    for r in unfulfilled(requests):
        key = (r["type"], r["tmdb"], r["is4k"])
        if key not in merged:
            merged[key] = r
            continue
        item = merged[key]
        item["seasons"] |= r["seasons"]
        item["seerr_have"] |= r["seerr_have"]
        item["requested"] = min(filter(None, (item["requested"], r["requested"])), default=None)
        item["state"] = min(item["state"], r["state"], key=order.index)
    return list(merged.values())


def movie_release(d, today):
    """When a requested movie can be had: its digital / disc release, else cinema."""
    if (d.get("status") or "").lower() == "canceled":
        return {"kind": "canceled"}
    home = [rd["release_date"][:10]
            for country in (d.get("releases") or {}).get("results") or []
            for rd in country.get("release_dates") or []
            if rd.get("type") in (4, 5) and rd.get("release_date")]  # fmt: skip
    if home:
        first = min(home)
        return {
            "kind": "released" if first <= today else "upcoming",
            "date": first,
            "what": "digital",
        }
    if d.get("releaseDate"):
        cinema = d["releaseDate"][:10]
        return {
            "kind": "cinema" if cinema <= today else "upcoming",
            "date": cinema,
            "what": "cinema",
        }
    return {"kind": "tba"}


def episode_dates(sr, tmdb, n, today, cache):
    """Sorted air dates of a season's episodes (/tv/{id}/season/{n}); [] if unknown.
    Remembered once the whole season has aired: then they won't change."""
    key = f"season:{tmdb}:{n}"
    dates = cache.get(key)
    if dates is not None:
        return dates
    try:
        eps = sr.get_json(f"/tv/{tmdb}/season/{n}", {"language": "en"}).get("episodes") or []
    except (OSError, ValueError, http.client.HTTPException) as e:
        if isinstance(e, urllib.error.HTTPError):
            e.close()
        return []
    dates = sorted((e.get("airDate") or "")[:10] for e in eps if e.get("airDate"))
    if dates and dates[-1] <= today:
        cache.put(key, dates)
    return dates


def season_release(sr, d, n, today, cache):
    """aired / airing (+ next date) / upcoming (+ date) / tba, from the episode air
    dates: the show's season list can have empty ones."""
    dates = episode_dates(sr, d.get("id"), n, today, cache) if d.get("id") else []
    return dates_release(n, dates, today) if dates else details_release(d, n, today)


def dates_release(n, dates, today):
    upcoming = [x for x in dates if x > today]
    if not upcoming:
        return {"n": n, "kind": "aired", "date": dates[0]}
    kind = "upcoming" if upcoming[0] == dates[0] else "airing"
    return {"n": n, "kind": kind, "date": upcoming[0]}


def details_release(d, n, today):
    """Without episode dates: what the show's details say."""
    season = next((s for s in d.get("seasons") or [] if s.get("seasonNumber") == n), {})
    air = (season.get("airDate") or "")[:10]
    nxt = d.get("nextEpisodeToAir") or {}
    if air and air <= today and nxt.get("seasonNumber") == n:
        return {"n": n, "kind": "airing", "date": (nxt.get("airDate") or "")[:10] or None}
    if not air:
        return {"n": n, "kind": "tba"}
    return {"n": n, "kind": "aired" if air <= today else "upcoming", "date": air}


def library_season(n, have):
    """A requested season that's (partly) there already: 'available' (with the next
    episode's date while it's airing) or 'partial' (with the missing episodes)."""
    s = have.get(n)
    if not s:
        return None
    if s["status"] == "partial":
        return {"n": n, "kind": "partial", "missing": s.get("missing")}
    return (
        {"n": n, "kind": "available", "next": s.get("next")}
        if s.get("next")
        else {"n": n, "kind": "available"}
    )


def tmdb_poster(path, cache_dir):
    if not path:
        return None
    cache_file = os.path.join(cache_dir, "tmdb_w154_" + path.strip("/")) if cache_dir else None
    if cache_file and os.path.exists(cache_file):
        with open(cache_file, "rb") as f:
            data = f.read()
    else:
        with urllib.request.urlopen(TMDB_POSTER.format(path), timeout=20) as r:
            data = r.read()
        if cache_file:
            with open(cache_file, "wb") as f:
                f.write(data)
    mime, _ = sniff_mime(data)
    return f"data:{mime};base64,{base64.b64encode(data).decode()}"


def trim_details(d):
    """The parts of Seerr's movie / show details that request_record uses, so the
    cache stays small."""
    keep = (
        "id",
        "title",
        "name",
        "releaseDate",
        "firstAirDate",
        "posterPath",
        "status",
    )
    out = {k: d[k] for k in keep if d.get(k)}
    out["releases"] = {"results": [
        {"release_dates": [{"type": rd.get("type"), "release_date": rd.get("release_date")}
                           for rd in c.get("release_dates") or [] if rd.get("type") in (4, 5)]}
        for c in (d.get("releases") or {}).get("results") or []]}  # fmt: skip
    out["seasons"] = [
        {"seasonNumber": x.get("seasonNumber"), "airDate": x.get("airDate")}
        for x in d.get("seasons") or []
    ]
    nxt = d.get("nextEpisodeToAir") or {}
    out["nextEpisodeToAir"] = {
        "seasonNumber": nxt.get("seasonNumber"),
        "airDate": nxt.get("airDate"),
    }
    return out


# Nothing left to wait for: released / canceled movies, seasons that have aired or
# are in the library. Their lookups are remembered; anything else is asked every run.
SETTLED = {"released", "canceled", "aired", "available", "partial"}


def request_record(sr, item, today, cache_dir, cache):
    """Title, year, cover and release state of one open request (English titles, to
    match the rest of the page)."""
    kind = "movie" if item["type"] == "movie" else "tv"
    key = f"{kind}:{item['tmdb']}"
    d = cache.get(key)
    fresh = d is None
    if fresh:
        d = trim_details(sr.get_json(f"/{kind}/{item['tmdb']}", {"language": "en"}))
    rec = request_base(item, kind, d)
    if kind == "movie":
        rec["release"] = movie_release(d, today)
        kinds = [rec["release"]["kind"]]
    else:
        have = item.get("have", {})
        rec["seasons"] = [library_season(n, have) or season_release(sr, d, n, today, cache)
                          for n in sorted(item["seasons"])]  # fmt: skip
        kinds = [s["kind"] for s in rec["seasons"]]
    if fresh and all(k in SETTLED for k in kinds):
        cache.put(key, d)
    rec["poster"] = cover(d, cache_dir)
    return rec


def request_base(item, kind, d):
    first = (d.get("releaseDate") if kind == "movie" else d.get("firstAirDate")) or ""
    rec = {
        "type": "movie" if kind == "movie" else "series",
        "tmdb": item["tmdb"],
        "title": d.get("title") or d.get("name") or "Untitled",
        "year": year_of(first),
        "requested": item["requested"],
        "state": item["state"],
        "link": f"https://www.themoviedb.org/{kind}/{item['tmdb']}",
    }
    if item["is4k"]:
        rec["is4k"] = True
    return rec


def cover(d, cache_dir):
    try:
        return tmdb_poster(d.get("posterPath"), cache_dir)
    except OSError:
        return None  # the row shows a placeholder


TMDB_IN_LINK = re.compile(r"themoviedb\.org/(movie|tv)/(\d+)")


def library_by_tmdb(records):
    """{("movie" | "tv", TMDB id): record}, from the records' TMDB links."""
    lib = {}
    for r in records:
        for link in r.get("links", []):
            m = TMDB_IN_LINK.search(link["url"])
            if m:
                lib[(m.group(1), int(m.group(2)))] = r
    return lib


def seasons_there(item, rec):
    """{n: season} of a requested series that are (partly) there; Jellyfin knows better
    than Seerr."""
    if rec and rec.get("seasonList"):
        return {
            s["n"]: s
            for s in rec["seasonList"]
            if s["status"] in ("available", "airing", "partial")
        }
    return {n: {"status": "available"} for n in item["seerr_have"]}


def drop_fulfilled(items, records):
    """Seerr lags behind Jellyfin: drops requested movies that are in the library and
    series requests Jellyfin has in full (4K requests stay). item["have"]: the requested
    seasons that are (partly) there. Matched by TMDB id."""
    lib = library_by_tmdb(records)
    out = []
    for it in items:
        kind = "movie" if it["type"] == "movie" else "tv"
        rec = None if it["is4k"] else lib.get((kind, it["tmdb"]))
        if kind == "movie":
            if not rec:
                out.append(it)
            continue
        have = seasons_there(it, rec)
        it["have"] = {n: have[n] for n in it["seasons"] if n in have}
        if not all(have.get(n, {}).get("status") in ("available", "airing") for n in it["seasons"]):
            out.append(it)
    return out


def unknown_request(item):
    """A row for a request whose details Seerr can't fetch (e.g. the title was removed
    from TMDB): shown with its TMDB id instead of being dropped."""
    kind = "movie" if item["type"] == "movie" else "tv"
    rec = {
        "type": "movie" if kind == "movie" else "series",
        "tmdb": item["tmdb"],
        "title": f"TMDB #{item['tmdb']}",
        "year": None,
        "requested": item["requested"],
        "state": item["state"],
        "link": f"https://www.themoviedb.org/{kind}/{item['tmdb']}",
        "unknown": True,
        "poster": None,
    }
    if kind == "tv":
        have = item.get("have", {})
        rec["seasons"] = [
            library_season(n, have) or {"n": n, "kind": "tba"} for n in sorted(item["seasons"])
        ]
    return rec


def export_requests(a, cache_dir, workers, records=(), cache=None):
    """Open Seerr requests for the Requests tab. If Seerr can't be read at all the tab
    is skipped; a title whose details fail is logged and shown by its TMDB id."""
    log("Fetching Seerr requests...", "📨")
    cache = cache if cache is not None else JsonCache(None, "", 0)  # no cache: ask every time
    try:
        sr = seerr_client(a)
        seerr_open = open_requests(fetch_requests(sr))
        items = drop_fulfilled(seerr_open, records)
        if len(items) < len(seerr_open):
            log(
                f"   {len(seerr_open) - len(items)} already in Jellyfin (Seerr hasn't caught up), left out"
            )
    except (OSError, ValueError, http.client.HTTPException) as e:
        log(f"   Skipping requests: can't read Seerr ({describe_error(e)}).", "⚠️")
        if isinstance(e, (http.client.RemoteDisconnected, ssl.SSLError, ConnectionResetError)):
            log(
                "   Seerr closed the connection. If it sits behind a proxy that wants a client "
                "certificate, point SEER_URL at Seerr itself (e.g. http://<host>:5055) or set "
                "SEER_CLIENT_CERT / SEER_CLIENT_KEY."
            )
        return []

    def record(item):
        try:
            return request_record(sr, item, today, cache_dir, cache), None
        except (OSError, ValueError, http.client.HTTPException) as e:
            kind = "movie" if item["type"] == "movie" else "tv"
            return unknown_request(item), f"{kind} {item['tmdb']}: {describe_error(e)}"

    today, report, out, problems = (
        local_today(),
        progress_logger("request details"),
        [],
        [],
    )
    with ThreadPoolExecutor(max_workers=workers) as pool:
        futs = [pool.submit(record, it) for it in items]
        for n, fut in enumerate(as_completed(futs), 1):
            rec, problem = fut.result()
            out.append(rec)
            if problem:
                problems.append(problem)
            report(n, len(futs))
    # Newest request first; same day A to Z (lookups finish in any order)
    out.sort(key=lambda r: r["title"].lower())
    out.sort(key=lambda r: r.get("requested") or "", reverse=True)
    log(f"   {len(out)} open requests ({cache.hits} lookups remembered)")
    log_problems(problems, "without details from Seerr (listed by TMDB id instead)")
    return out


def seerr_client(a):
    ctx = tls_context(a.ca_cert, a.seerr_client_cert, a.seerr_client_key, a.insecure)
    return Seerr(a.seerr_url, a.seerr_api_key, ctx)
