"""A fake Jellyfin + Seerr with the quirks AGENTS.md lists, plus flags and TMDB covers,
so nothing goes to the internet. Unknown paths land in `unknown` (tests fail on them);
`hits` counts requests, for the cache tests."""

import json
import threading
import urllib.parse
from collections import Counter
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

JELLYFIN_KEY = "test-jellyfin-key"
SEERR_KEY = "test-seerr-key"
USER = "user1"
WEBP = b"RIFF\x1a\x00\x00\x00WEBPVP8 fake poster"
SVG = b'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 4 3"/>'
AIRED, FUTURE = "2019-03-01T23:00:00.0000000Z", "2099-01-01T00:00:00.0000000Z"


def video(width=3840, height=2160, hdr="DOVIWithHDR10"):
    return {"Type": "Video", "Codec": "hevc", "Width": width, "Height": height,
            "BitDepth": 10, "VideoRangeType": hdr}  # fmt: skip


def stream(kind, codec, lang, **extra):
    return {"Type": kind, "Codec": codec, "Language": lang, **extra}


def movie(mid, name, year, tmdb, **extra):
    return {"Id": mid, "Type": "Movie", "Name": name, "SortName": name,
            "ProductionYear": year, "PremiereDate": f"{year}-05-03T22:00:00.0000000Z",
            "ProviderIds": {"Tmdb": tmdb}, "CommunityRating": 7.0, "Genres": ["Action"],
            "DateCreated": "2024-01-02T10:00:00.0000000Z", "RunTimeTicks": 117 * 600_000_000,
            "ImageTags": {"Primary": f"tag-{mid}"}, "_lib": "lib-movies", **extra}  # fmt: skip


ARRIVAL = movie(
    "m1", "Arrival", 2016, "329865",
    ProviderIds={"Imdb": "tt2543164", "Tmdb": "329865"},
    PremiereDate="2016-11-09T23:00:00.0000000Z",  # 10 Nov in Germany
    CommunityRating=7.94, OfficialRating="FSK 12",
    MediaSources=[{
        "Container": "mkv", "Size": 30_000_000_000, "Bitrate": 40_000_000,
        "MediaStreams": [
            video(),
            stream("Audio", "truehd", "eng", Channels=8, DisplayTitle="TrueHD Atmos 7.1"),
            stream("Audio", "ac3", "ger", Channels=6),
            stream("Subtitle", "srt", "ger"),
            stream("Subtitle", "srt", "eng", IsForced=True),
        ],
    }],
)  # fmt: skip
ANT_MAN = movie("m2", "Ant-Man", 2015, "102899")
WASP = movie("m3", "Ant-Man and the Wasp", 2018, "363088")
SERIES = {
    "Id": "s1", "Type": "Series", "Name": "Dark Coast", "SortName": "Dark Coast",
    "ProductionYear": 2019, "PremiereDate": AIRED, "Status": "Continuing",
    "ProviderIds": {"Tmdb": "1396", "Tvdb": "81189"}, "ChildCount": 3,
    "DateCreated": "2023-05-01T10:00:00.0000000Z", "Genres": ["Drama"],
    "ImageTags": {"Primary": "tag-s1"}, "_lib": "lib-shows",
}  # fmt: skip
# Box sets: two copies of the same TMDB collection (one with a poster), and one
# whose only member isn't in the library
BOXSETS = [
    {"Id": "bs-a", "Type": "BoxSet", "Name": "Ant-Man [boxset]", "ChildCount": 1,
     "ProviderIds": {"Tmdb": "422834"}, "DateCreated": "2024-01-01T00:00:00Z"},
    {"Id": "bs-b", "Type": "BoxSet", "Name": "Ant-Man Collection", "ChildCount": 2,
     "ProviderIds": {"Tmdb": "422834"}, "DateCreated": "2024-01-01T00:00:00Z",
     "ImageTags": {"Primary": "tag-bs-b"}},
    {"Id": "bs-x", "Type": "BoxSet", "Name": "Elsewhere", "ChildCount": 1},
]  # fmt: skip
MEMBERS = {"bs-a": ["m2"], "bs-b": ["m2", "m3"], "bs-x": ["not-in-library"]}


def season(sid, n):
    return {"Id": sid, "Type": "Season", "SeriesId": "s1", "IndexNumber": n,
            "Name": f"Season {n}", "ProductionYear": 2019 + n}  # fmt: skip


def episode(n, i, aired=AIRED, created="2023-05-01T10:00:00.0000000Z", **extra):
    return {"Id": f"e{n}x{i}", "Type": "Episode", "SeriesId": "s1",
            "ParentIndexNumber": n, "IndexNumber": i, "PremiereDate": aired,
            "DateCreated": created, **extra}  # fmt: skip


# Season 1: E1, E2 there, E3 missing (partial). Season 2: E1 there, E2 not aired yet
# (airing). Season 3: announced, no episodes (TBA). "sea1-stale" is a leftover
# duplicate of season 1 without user data.
SEASONS = [season("sea1", 1), season("sea1-stale", 1), season("sea2", 2), season("sea3", 3)]  # fmt: skip
OWNED = [episode(1, 1), episode(1, 2),
         episode(2, 1, "2021-04-01T22:00:00.0000000Z", created="2026-09-01T08:00:00.0000000Z")]  # fmt: skip
MISSING = [episode(1, 3, LocationType="Virtual"),
           episode(2, 2, FUTURE, LocationType="Virtual")]  # fmt: skip
EPISODE_MEDIA = {
    "Container": "mkv", "Size": 2_000_000_000,
    "MediaStreams": [video(1920, 1080, "SDR"), stream("Audio", "eac3", "eng", Channels=6),
                     stream("Subtitle", "srt", "ger")],
}  # fmt: skip
USER_DATA = {
    "m1": {"Played": True, "IsFavorite": True,
           "LastPlayedDate": "2026-09-27T20:15:03.1234567Z"},
    "s1": {"PlayedPercentage": 40.4},
    "sea1": {"Played": True},
}  # fmt: skip
PLAYED = {"IsPlayed": [{**OWNED[0], "UserData": {"LastPlayedDate": "2026-09-30T10:00:00.0000000Z"}}],
          "IsResumable": [{**OWNED[2], "UserData": {"LastPlayedDate": "2026-10-01T10:00:00.0000000Z"}}]}  # fmt: skip

# Seerr: open requests and the details behind them
REQUESTS = [
    # in the library already (Seerr lags behind): left out
    {"type": "movie", "status": 2, "media": {"tmdbId": 329865, "status": 3},
     "createdAt": "2026-09-01T10:00:00.000Z"},
    # waiting for approval, digital release far ahead
    {"type": "movie", "status": 1, "media": {"tmdbId": 1001, "status": 2},
     "createdAt": "2026-09-25T10:00:00.000Z"},
    # the series above: season 1 partly there, season 2 airing
    {"type": "tv", "status": 2, "media": {"tmdbId": 1396, "status": 4},
     "seasons": [{"seasonNumber": 1, "status": 2}, {"seasonNumber": 2, "status": 2}],
     "createdAt": "2026-09-20T10:00:00.000Z"},
    # gone from TMDB: Seerr answers 500 for its details
    {"type": "tv", "status": 2, "media": {"tmdbId": 327719, "status": 2},
     "seasons": [{"seasonNumber": 1, "status": 2}], "createdAt": "2026-09-10T10:00:00.000Z"},
    # declined: left out
    {"type": "movie", "status": 3, "media": {"tmdbId": 2002, "status": 1},
     "createdAt": "2026-09-05T10:00:00.000Z"},
]  # fmt: skip
SEERR_DETAILS = {
    ("movie", "1001", "en"): {
        "id": 1001, "title": "Future Film", "releaseDate": "2099-05-01",
        "posterPath": "/ff.jpg", "status": "Post Production",
        "releases": {"results": [{"release_dates": [
            {"type": 3, "release_date": "2099-05-01T00:00:00.000Z"},
            {"type": 4, "release_date": "2099-08-01T00:00:00.000Z"}]}]},
    },
    ("movie", "1001", "de"): {"id": 1001, "title": "Zukunftsfilm"},
    ("tv", "1396", "en"): {"id": 1396, "name": "Dark Coast", "firstAirDate": "2019-03-02",
                           "posterPath": "/dc.jpg"},
    ("tv", "1396", "de"): {"id": 1396, "name": "Dunkle Küste"},
    ("movie", "329865", "de"): {"id": 329865, "title": "Arrival"},
    # No German translation: TMDB answers with the original title, in another
    # language (made up here), which must not count as the German title
    ("movie", "102899", "de"): {"id": 102899, "title": "アントマン",
                                "originalTitle": "アントマン", "originalLanguage": "ja"},
    ("movie", "363088", "de"): {"id": 363088, "title": "Ant-Man and the Wasp"},
    ("collection", "422834", "de"): {"id": 422834, "name": "Ant-Man Filmreihe"},
}  # fmt: skip


def public(item):
    return {k: v for k, v in item.items() if not k.startswith("_")}


class FakeServer:
    """with FakeServer() as srv: ... srv.url (Jellyfin), srv.seerr_url, srv.hits"""

    def __init__(self, require_user=False, reject_key=False, port=0, host="127.0.0.1"):
        self.port, self.host = port, host  # port 0: any free port
        self.require_user = require_user  # /Items without a user: 400
        self.reject_key = reject_key  # every Jellyfin request: 401
        self.hits, self.unknown = Counter(), []
        self.lock = threading.Lock()

    # ---- routing ------------------------------------------------------------
    def handle(self, path, q, headers):
        if path.startswith("/flags/"):
            return 200, SVG, "image/svg+xml"
        if path.startswith("/tmdb/"):
            return 200, WEBP, "image/webp"
        if path.startswith("/seerr/api/v1/"):
            if headers.get("X-Api-Key") != SEERR_KEY:
                return 401, b'{"message":"Unauthorized"}', "application/json"
            return self.seerr(path[len("/seerr/api/v1") :], q)
        if self.reject_key or headers.get("X-Emby-Token") != JELLYFIN_KEY:
            return 401, b"", "text/plain"
        return self.jellyfin(path, q)

    def jellyfin(self, path, q):
        if path == "/Library/VirtualFolders":
            return self.json([{"Name": "Movies", "ItemId": "lib-movies", "CollectionType": "movies"},
                              {"Name": "Shows", "ItemId": "lib-shows", "CollectionType": "tvshows"}])  # fmt: skip
        if path == "/Users":
            return self.json([{"Id": USER, "Name": "Viewer", "Policy": {"IsAdministrator": True}}])  # fmt: skip
        if path.startswith("/Items/") and path.endswith("/Images/Primary"):
            return 200, WEBP, "image/webp"
        if path == "/Items" and self.require_user:
            return 400, b"user required", "text/plain"
        if path in ("/Items", f"/Users/{USER}/Items"):
            return self.json(self.page(self.items(q), q))
        return self.unknown_path(path)

    def items(self, q):
        types = set((q.get("IncludeItemTypes") or "").split(","))
        parent = q.get("ParentId")
        if "Ids" in q:  # episode file details
            ids = q["Ids"].split(",")
            return [{**public(e), "MediaSources": [EPISODE_MEDIA]} for e in OWNED if e["Id"] in ids]  # fmt: skip
        if q.get("IsMissing") == "true":
            return MISSING
        if q.get("Filters") in PLAYED:
            return PLAYED[q["Filters"]]
        if parent in MEMBERS:  # a box set's contents
            members = {i["Id"]: i for i in (ARRIVAL, ANT_MAN, WASP)}
            return [public(members.get(i, {"Id": i, "Type": "Movie"})) for i in MEMBERS[parent]]  # fmt: skip
        if types == {"BoxSet"}:
            return BOXSETS
        if types == {"Season", "Episode"}:
            return SEASONS + OWNED if parent in (None, "lib-shows") else []
        if types == {"Movie", "Series", "Season", "BoxSet"}:  # user data
            ids = ["m1", "m2", "m3", "s1", "sea1", "sea1-stale", "sea2", "sea3"]
            return [{"Id": i, "UserData": USER_DATA.get(i, {})} for i in ids]
        if types <= {"Movie", "Series"}:
            return self.titles(q, types, parent)
        self.unknown_path(f"items {sorted(q.items())}")
        return []

    @staticmethod
    def titles(q, types, parent):
        """Movies and series of one library (or all)."""
        titles = [ARRIVAL, ANT_MAN, WASP, SERIES]
        if q.get("CollapseBoxSetItems") != "false":
            # Jellyfin's "group movies into collections": the box set replaces them
            titles = [ARRIVAL, {**BOXSETS[1], "_lib": "lib-movies"}, SERIES]
        if "MediaSources" not in q.get("Fields", ""):
            titles = [{k: v for k, v in t.items() if k != "MediaSources"} for t in titles]  # fmt: skip
        return [public(t) for t in titles
                if parent in (None, t["_lib"]) and t["Type"] in types]  # fmt: skip

    def seerr(self, path, q):
        if path == "/request":
            skip, take = int(q.get("skip", 0)), int(q.get("take", 100))
            return self.json({"pageInfo": {"results": len(REQUESTS)},
                              "results": REQUESTS[skip : skip + take]})  # fmt: skip
        if path == "/tv/327719":
            return 500, b'{"message":"Unable to retrieve series."}', "application/json"
        parts = path.strip("/").split("/")
        if len(parts) == 2:
            details = SEERR_DETAILS.get((parts[0], parts[1], q.get("language")))
            if details:
                return self.json(details)
        return self.unknown_path(path)

    # ---- helpers ------------------------------------------------------------
    @staticmethod
    def json(data):
        return 200, json.dumps(data).encode(), "application/json"

    @staticmethod
    def page(items, q):
        start, limit = int(q.get("StartIndex", 0)), int(q.get("Limit", 10_000))
        return {"Items": items[start : start + limit], "TotalRecordCount": len(items)}

    def unknown_path(self, what):
        with self.lock:
            self.unknown.append(what)
        return 404, b"not found", "text/plain"

    # ---- server ---------------------------------------------------------------
    def __enter__(self):
        fake = self

        class Handler(BaseHTTPRequestHandler):
            def do_GET(self):
                url = urllib.parse.urlsplit(self.path)
                q = dict(urllib.parse.parse_qsl(url.query))
                with fake.lock:
                    fake.hits[url.path] += 1
                    if "ParentId" in q:
                        fake.hits[f"members:{q['ParentId']}"] += 1
                    if "Ids" in q:
                        fake.hits["episode details"] += 1
                status, body, ctype = fake.handle(url.path, q, self.headers)
                self.send_response(status)
                self.send_header("Content-Type", ctype)
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            def log_message(self, format, *args):  # noqa: A002 - quiet
                pass

        self.httpd = ThreadingHTTPServer((self.host, self.port), Handler)
        self.url = f"http://127.0.0.1:{self.httpd.server_address[1]}"
        self.seerr_url = self.url + "/seerr"
        threading.Thread(
            target=self.httpd.serve_forever, kwargs={"poll_interval": 0.02}, daemon=True
        ).start()
        return self

    def __exit__(self, *exc):
        self.httpd.shutdown()
        self.httpd.server_close()


if __name__ == "__main__":
    # A standalone fake server, e.g. to run the Docker image against it in CI:
    #   python -m tests.fake_server 8099 [host]   (host 0.0.0.0 for Docker Desktop)
    import sys

    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8099
    host = sys.argv[2] if len(sys.argv) > 2 else "127.0.0.1"
    with FakeServer(port=port, host=host) as srv:
        print(f"Fake Jellyfin on {srv.url}, Seerr on {srv.seerr_url}", flush=True)
        threading.Event().wait()
