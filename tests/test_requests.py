"""Seerr requests: which are open, merging, release dates, the library cross-check."""

import unittest

from marqueefin.seerr import (
    drop_fulfilled,
    library_season,
    movie_release,
    open_requests,
    unknown_request,
)

TODAY = "2026-10-01"


def req(tmdb, kind="movie", status=2, media_status=3, seasons=(), created="2026-09-20T10:00:00.000Z", **extra):  # fmt: skip
    media = {"tmdbId": tmdb, "status": media_status, **extra.pop("media", {})}
    return {"type": kind, "status": status, "media": media, "createdAt": created,
            "seasons": [{"seasonNumber": n, "status": 2} for n in seasons], **extra}  # fmt: skip


class OpenRequests(unittest.TestCase):
    def test_finished_ones_are_left_out(self):
        requests = [
            req(1),  # approved, not there yet: open
            req(2, status=3),  # declined
            req(3, status=5),  # completed
            req(4, media_status=5),  # available
        ]
        self.assertEqual([r["tmdb"] for r in open_requests(requests)], [1])

    def test_state(self):
        (pending,) = open_requests([req(1, status=1)])
        (failed,) = open_requests([req(1, status=4)])
        (partial,) = open_requests([req(1, media_status=4)])
        self.assertEqual(
            (pending["state"], failed["state"], partial["state"]),
            ("pending", "failed", "partial"),
        )

    def test_series_requests_are_merged(self):
        merged = open_requests([
            req(9, "tv", seasons=[2], created="2026-09-25T10:00:00Z"),
            req(9, "tv", status=1, seasons=[3], created="2026-09-20T10:00:00Z"),
        ])  # fmt: skip
        (one,) = merged
        self.assertEqual(one["seasons"], {2, 3})
        self.assertEqual(one["state"], "pending")  # the one least far along
        self.assertEqual(one["requested"], "2026-09-20")

    def test_series_with_every_season_available_is_left_out(self):
        media = {"seasons": [{"seasonNumber": 1, "status": 5}]}
        self.assertEqual(open_requests([req(9, "tv", seasons=[1], media=media)]), [])


class MovieRelease(unittest.TestCase):
    def details(self, cinema=None, home=(), status="Released"):
        dates = [{"type": 4, "release_date": f"{d}T00:00:00.000Z"} for d in home]
        return {"status": status, "releaseDate": cinema,
                "releases": {"results": [{"release_dates": dates}]}}  # fmt: skip

    def test_digital_release(self):
        self.assertEqual(
            movie_release(self.details(home=["2026-11-02", "2026-12-01"]), TODAY),
            {"kind": "upcoming", "date": "2026-11-02", "what": "digital"},
        )
        self.assertEqual(
            movie_release(self.details(home=["2026-02-12"]), TODAY)["kind"],
            "released",
        )

    def test_cinema_only_and_unknown(self):
        self.assertEqual(
            movie_release(self.details(cinema="2026-09-03"), TODAY)["kind"],
            "cinema",
        )
        self.assertEqual(movie_release(self.details(), TODAY), {"kind": "tba"})
        self.assertEqual(
            movie_release(self.details(status="Canceled"), TODAY),
            {"kind": "canceled"},
        )


class DropFulfilled(unittest.TestCase):
    """Seerr lags behind Jellyfin, so the library has the last word."""

    def library(self, kind, tmdb, seasons=()):
        return {"links": [{"url": f"https://www.themoviedb.org/{kind}/{tmdb}"}],
                "seasonList": [{"n": n, "status": s} for n, s in seasons]}  # fmt: skip

    def item(self, tmdb, kind="movie", seasons=(), is4k=False):
        return {"type": kind, "tmdb": tmdb, "is4k": is4k, "seasons": set(seasons),
                "seerr_have": set(), "requested": TODAY, "state": "approved"}  # fmt: skip

    def test_movie_in_the_library_is_dropped_unless_4k(self):
        records = [self.library("movie", 603)]
        self.assertEqual(drop_fulfilled([self.item(603)], records), [])
        kept = drop_fulfilled([self.item(603, is4k=True)], records)
        self.assertEqual(len(kept), 1)

    def test_series_seasons_from_the_library(self):
        records = [self.library("tv", 1396, [(1, "available"), (2, "partial")])]
        done = self.item(1396, "tv", seasons=[1])
        open_ = self.item(1396, "tv", seasons=[2, 3])
        kept = drop_fulfilled([done, open_], records)
        self.assertEqual(kept, [open_])
        self.assertEqual(list(open_["have"]), [2])
        self.assertEqual(
            library_season(2, open_["have"]),
            {"n": 2, "kind": "partial", "missing": None},
        )

    def test_unknown_request_row(self):
        row = unknown_request(
            {
                "type": "tv",
                "tmdb": 327719,
                "requested": TODAY,
                "state": "approved",
                "seasons": {1},
            }
        )
        self.assertEqual(row["title"], "TMDB #327719")
        self.assertEqual(row["seasons"], [{"n": 1, "kind": "tba"}])
        self.assertTrue(row["unknown"])


if __name__ == "__main__":
    unittest.main()
