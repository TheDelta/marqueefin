#!/usr/bin/env python3
"""A page with made-up titles and drawn posters, for screenshots and for trying the
page without a Jellyfin server.

    python scripts/demo_page.py                 # writes demo.html
    python scripts/demo_page.py -o /tmp/x.html

docs/preview*.png are taken from this page: npm run screenshots (scripts/screenshots.mjs)
"""

import argparse
import base64
import hashlib
import html
import os
import sys
from datetime import datetime, timedelta, timezone

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
from marqueefin import render
from marqueefin.media import language_flags
from marqueefin.render import render_html

FSK0, FSK6, FSK12, FSK16 = "FSK 0", "FSK 6", "FSK 12", "FSK 16"
DV = "Dolby Vision"
COLLECTION = "Wayfinders Collection"

# (type, title, year, month, rating, cert, genres, colors, extra)
# fmt: off
TITLES = [
    ("movie", "The Last Lighthouse", 2026, 8, 7.9, FSK12, ["Drama", "Mystery"], ("#0f2a44", "#e8a33d"), {"res": "4K", "hdr": DV, "new": True}),
    ("series", "Signal Lost", 2026, 6, 8.4, FSK16, ["Sci-Fi", "Thriller"], ("#14123a", "#6c5ce7"), {"res": "4K", "hdr": "HDR10", "seasons": 2, "airing": True}),
    ("movie", "Paper Moons", 2026, 5, 7.1, FSK6, ["Comedy", "Romance"], ("#3b1f2b", "#f08a9b"), {"res": "1080p", "watched": True, "de": "Papiermonde"}),
    ("movie", "Iron Orchard", 2026, 4, 6.8, FSK16, ["Action"], ("#2b2b2b", "#c0392b"), {"res": "4K", "hdr": "HDR10+"}),
    ("series", "The Quiet Coast", 2026, 2, 8.1, FSK12, ["Drama"], ("#0e3b43", "#7fd1c7"), {"res": "4K", "hdr": DV, "seasons": 3, "incomplete": True, "de": "Die stille Küste"}),
    ("movie", "Northbound", 2026, 1, 7.4, FSK12, ["Adventure"], ("#1d3557", "#a8dadc"), {"res": "4K", "fav": True}),
    ("movie", "Second Spring", 2026, 3, 7.3, FSK0, ["Family", "Comedy"], ("#283618", "#dda15e"), {"res": "1080p", "new": True}),
    ("movie", "Glass Harbor", 2026, 1, 6.9, FSK16, ["Thriller", "Crime"], ("#102027", "#4fc3f7"), {"res": "1080p"}),
    ("series", "Kitchen Brigade", 2025, 11, 8.6, FSK12, ["Comedy", "Drama"], ("#3e2723", "#ffb74d"), {"res": "4K", "hdr": DV, "seasons": 4, "watched_pct": 65}),
    ("movie", "Ember & Ash", 2025, 10, 7.7, FSK16, ["Fantasy", "Action"], ("#2a0f0f", "#ff7043"), {"res": "4K", "hdr": "HDR10"}),
    ("movie", "Small Hours", 2025, 9, 7.2, FSK12, ["Drama"], ("#1a1a2e", "#e94560"), {"res": "1080p", "watched": True}),
    ("movie", "Tidewater", 2025, 7, 6.5, FSK12, ["Mystery"], ("#003049", "#fcbf49"), {"res": "720p"}),
    ("series", "Orbit Street", 2025, 5, 7.8, FSK6, ["Animation", "Comedy"], ("#2d0b59", "#ffd166"), {"res": "1080p", "seasons": 2}),
    ("movie", "The Cartographer", 2025, 3, 8.0, FSK12, ["History", "Drama"], ("#3d2c1e", "#d4a373"), {"res": "4K", "hdr": DV, "fav": True}),
    ("movie", "Neon Tides", 2024, 12, 6.7, FSK16, ["Sci-Fi"], ("#0b0033", "#00f5d4"), {"res": "4K", "hdr": "HDR10"}),
    ("movie", "Under the Linden", 2024, 9, 7.5, FSK0, ["Family", "Drama"], ("#1b4332", "#95d5b2"), {"res": "1080p", "watched": True}),
    ("movie", "Saltwind", 2024, 6, 6.9, FSK12, ["Adventure"], ("#012a4a", "#61a5c2"), {"res": "1080p"}),
]
# fmt: on
OVERVIEW = (
    "An invented title for the Marqueefin demo page. Nothing here is a real film or "
    "show; the poster is drawn from the title and two colors."
)


def item_id(title):
    """A stable made-up Jellyfin id (MD5 as a name hash, not for security)."""
    return hashlib.md5(title.encode(), usedforsecurity=False).hexdigest()


def tmdb_id(title):
    return int(item_id(title)[:6], 16)


def links(kind, title):
    """A TMDB link (a made-up id): the Requests tab finds library titles by it. And
    one to Jellyfin, as --public-url adds it."""
    path = "movie" if kind == "movie" else "tv"
    return [
        {"label": "TMDB", "url": f"https://www.themoviedb.org/{path}/{tmdb_id(title)}"},
        {
            "label": "Jellyfin",
            "url": f"https://jellyfin.example.com/web/#/details?id={item_id(title)}",
        },
    ]


def poster(title, colors):
    """A 2:3 poster: a gradient and the title, as an SVG data URI. The lower third
    stays plain, the page puts its rating and status chips there."""
    top, accent = colors
    lines = "".join(
        f'<text x="24" y="{196 + i * 42}" font-family="Impact,Arial Narrow,sans-serif" '
        f'font-size="38" fill="#fff">{html.escape(w)}</text>'
        for i, w in enumerate(title.upper().split()[:3])
    )
    svg = (
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 300 450">'
        '<defs><linearGradient id="g" x1="0" y1="0" x2="0.4" y2="1">'
        f'<stop offset="0" stop-color="{top}"/><stop offset="1" stop-color="{accent}"/>'
        "</linearGradient></defs>"
        '<rect width="300" height="450" fill="url(#g)"/>'
        f'<circle cx="230" cy="96" r="62" fill="{accent}" opacity=".55"/>'
        f'<rect x="24" y="150" width="60" height="5" fill="{accent}"/>{lines}</svg>'
    )
    return "data:image/svg+xml;base64," + base64.b64encode(svg.encode()).decode()


def media(extra):
    hdr = [extra["hdr"]] if extra.get("hdr") else []
    return {
        "res": extra["res"], "codec": "HEVC", "bits": 10, "hdr": hdr,
        "audio": "TrueHD Atmos 7.1", "container": "MKV", "size": 18_400_000_000,
        "tracks": [["en", "7.1", "TrueHD Atmos"], ["de", "5.1", "DD+"]],
        "subLangs": ["en", "de", "fr", "es", "it"],
    }  # fmt: skip


def days_from_now(days):
    return (datetime.now(timezone.utc) + timedelta(days=days)).date().isoformat()


def season_status(s, n, extra):
    if s == n and extra.get("airing"):
        return "airing"
    if s == n - 1 and extra.get("incomplete"):
        return "partial"
    return "available"


def season(s, n, extra, year):
    """Season s of n; the last one airing, the one before partial, as extra says."""
    status = season_status(s, n, extra)
    out = {"n": s, "name": f"Season {s}", "status": status, "have": 8, "total": 8,
           "year": year - (n - s), "date": f"{year - (n - s)}-03-01"}  # fmt: skip
    if status == "airing":
        out.update(have=3, total=8, upcoming=5, next=days_from_now(4))
    if status == "partial":
        out.update(have=6, missing="E4–E5")
    if s == 1 and extra.get("watched_pct"):  # where a series in progress started
        out["watched"] = True
    hdr = [extra["hdr"]] if extra.get("hdr") else []
    out["q"] = {"res": extra["res"], "hdr": hdr, "size": 9_000_000_000 + s * 700_000_000}
    return out


def seasons(n, extra, year):
    out = [season(s, n, extra, year) for s in range(1, n + 1)]
    if extra.get("airing"):  # renewed, no air date for the next season yet
        out.append({"n": n + 1, "name": f"Season {n + 1}", "status": "tba", "have": 0,
                    "total": 0, "next": days_from_now(120)})  # fmt: skip
    if extra.get("watched_pct"):  # Jellyfin's season 0
        out.append({"n": 0, "name": "Specials", "status": "available", "have": 2, "total": 2,
                    "fav": True})  # fmt: skip
    return out


def kind_fields(rec, kind, extra, year, i):
    """A movie's runtime, a series' seasons."""
    if kind == "movie":
        rec["runtime"] = 96 + i * 3
        return
    n = extra["seasons"]
    rec.update(seasons=n, status="Continuing", seasonList=seasons(n, extra, year),
               complete=not extra.get("incomplete"))  # fmt: skip


def viewer_fields(rec, extra):
    """The exporting user's watched / favorite status, and a German title."""
    if extra.get("watched"):
        rec["watched"] = True
        three_days_ago = datetime.now(timezone.utc) - timedelta(days=3)
        rec["lastWatched"] = three_days_ago.strftime("%Y-%m-%dT%H:%M:%SZ")
    if extra.get("watched_pct"):
        rec["watchedPct"] = extra["watched_pct"]
    if extra.get("fav"):
        rec["fav"] = True
    if extra.get("de"):  # a German title, for the page's title switch
        rec["titleAlt"] = extra["de"]


def records(today):
    out = []
    for kind, title, year, month, rating, cert, genres, colors, extra in TITLES:
        added = today - timedelta(days=2 if extra.get("new") else 40 + len(out) * 9)
        rec = {
            "id": item_id(title), "type": kind, "title": title, "sort": title.lower(),
            "year": year, "released": f"{year}-{month:02d}-12", "added": added.isoformat(),
            "rating": rating, "critic": None, "cert": cert, "genres": genres,
            "overview": OVERVIEW, "links": links(kind, title), "poster": poster(title, colors),
            "media": media(extra),
        }  # fmt: skip
        kind_fields(rec, kind, extra, year, len(out))
        viewer_fields(rec, extra)
        out.append(rec)
    members = [r["id"] for r in out if r["title"] in ("Northbound", "The Cartographer", "Saltwind")]
    out.append({
        "id": item_id(COLLECTION), "type": "collection", "title": COLLECTION,
        "sort": "wayfinders collection", "year": 2024, "endYear": 2026, "released": "2024-06-12",
        "added": (today - timedelta(days=60)).isoformat(), "rating": 7.6, "ratingOf": 3,
        "critic": None, "cert": None, "genres": ["Adventure"], "overview": OVERVIEW, "links": [],
        "poster": poster(COLLECTION, ("#0b3d2e", "#b7e4c7")), "items": members,
    })  # fmt: skip
    return out


def requests(today):
    """One of every kind: request states, movie releases, season states, a title
    Seerr has no details for, and series that are partly in the library."""

    def req(title, kind, colors, days=1, **extra):
        return {"type": kind, "tmdb": tmdb_id(title), "title": title, "year": 2026,
                "poster": poster(title, colors), "requested": (today - timedelta(days=days)).isoformat(),
                "state": "pending", "link": "https://www.themoviedb.org/", **extra}  # fmt: skip

    def day(n):
        return (today + timedelta(days=n)).isoformat()

    unknown = {"type": "series", "tmdb": 4242, "title": "TMDB #4242", "year": None,
               "requested": day(-30), "state": "approved", "unknown": True, "poster": None,
               "link": "https://www.themoviedb.org/tv/4242", "seasons": [{"n": 1, "kind": "tba"}]}  # fmt: skip
    return [
        req("Silver Delta", "movie", ("#1b1b3a", "#c0c0ff"),
            release={"kind": "upcoming", "date": day(24), "what": "digital"}),
        req("Long Way Home", "series", ("#2d1e2f", "#e07a5f"),
            seasons=[{"n": 1, "kind": "aired", "date": "2026-02-01"}]),
        req("Harbor Lights", "movie", ("#22223b", "#f2e9e4"), days=3, state="approved", is4k=True,
            release={"kind": "released", "date": day(-10), "what": "digital"}),
        req("Afterglow", "movie", ("#3c1518", "#f2a65a"), days=5, state="approved",
            release={"kind": "cinema", "date": day(-20), "what": "cinema"}),
        req("Still Water", "movie", ("#1d2d44", "#a9def9"), days=8, state="approved",
            release={"kind": "upcoming", "date": day(40), "what": "cinema"}),
        req("The Glass Garden", "movie", ("#2b2d42", "#8d99ae"), days=12, state="failed"),
        req("Copper Sky", "movie", ("#432818", "#bb9457"), days=15, state="approved",
            release={"kind": "canceled"}),
        # In the library, with seasons still to come
        {**req("Kitchen Brigade", "series", ("#3e2723", "#ffb74d"), days=20), "state": "partial",
         "seasons": [{"n": 1, "kind": "available", "next": day(6)},
                     {"n": 5, "kind": "airing", "date": day(2)},
                     {"n": 6, "kind": "upcoming", "date": day(90)}, {"n": 7, "kind": "tba"}]},
        {**req("The Quiet Coast", "series", ("#0e3b43", "#7fd1c7"), days=25), "state": "approved",
         "seasons": [{"n": 2, "kind": "partial", "missing": "E4–E5"}]},
        unknown,
    ]  # fmt: skip


def main():
    p = argparse.ArgumentParser(description="Write a Marqueefin page with made-up titles.")
    p.add_argument("-o", "--output", default="demo.html")
    p.add_argument("--title", default="Movie Night")
    p.add_argument(
        "--offline",
        action="store_true",
        help="no flag downloads: languages show as names (the browser tests use this)",
    )
    p.add_argument(
        "--passphrase",
        help="protect the page with this passphrase (the browser tests use it; the "
        "exporter takes EXPORT_PASSPHRASE or a file instead)",
    )
    p.add_argument(
        "--build-dir",
        help="the bundled script and styles from here, not build/ (the browser tests' "
        "build with a source map, for coverage)",
    )
    a = p.parse_args()
    if a.build_dir:
        render.BUILD_DIR = a.build_dir
    today = datetime.now().astimezone().date()
    recs = records(today)
    # Flags are downloaded once (like a real export) and cached
    flags = (
        {}
        if a.offline
        else language_flags(recs, os.environ.get("EXPORT_CACHE_DIR", ".marqueefin_cache"))
    )
    settings = {"titleLang": "de", "mainLangs": ["en", "de"]}
    protect = (a.passphrase, None) if a.passphrase else None
    page = render_html(
        a.title, recs, datetime.now().astimezone(), flags, requests(today), settings, protect
    )
    with open(a.output, "w", encoding="utf-8", newline="\n") as f:
        f.write(page)
    print(f"Wrote {a.output} ({len(recs)} titles)")


if __name__ == "__main__":
    main()
