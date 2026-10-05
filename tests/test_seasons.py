"""Season status from episodes: available, airing, partial, missing, TBA."""

import unittest

from marqueefin.records import attach_seasons, build_seasons

TODAY = "2026-10-01"


def season(series, n, sid=None):
    return {"Type": "Season", "Id": sid or f"{series}-s{n}", "SeriesId": series,
            "IndexNumber": n, "Name": f"Season {n}"}  # fmt: skip


def episode(series, n, i, aired="2026-01-05T23:00:00Z", virtual=False):
    ep = {"Type": "Episode", "Id": f"{series}-s{n}e{i}", "SeriesId": series,
          "ParentIndexNumber": n, "IndexNumber": i, "PremiereDate": aired}  # fmt: skip
    if virtual:
        ep["LocationType"] = "Virtual"
    return ep


def seasons_of(items, series="show"):
    return {s["n"]: s for s in build_seasons(items, set(), TODAY)[series]}


class SeasonStatus(unittest.TestCase):
    def test_available(self):
        s = seasons_of([season("show", 1)] + [episode("show", 1, i) for i in (1, 2)])[1]
        self.assertEqual((s["status"], s["have"], s["total"]), ("available", 2, 2))
        self.assertEqual(s["date"], "2026-01-06")  # local date, not the UTC one

    def test_partial_lists_the_missing_episodes(self):
        eps = [episode("show", 1, i, virtual=i in (4, 5, 7)) for i in range(1, 9)]
        s = seasons_of([season("show", 1), *eps])[1]
        self.assertEqual(s["status"], "partial")
        self.assertEqual(s["missing"], "E4–E5, E7")
        self.assertEqual((s["have"], s["total"]), (5, 8))

    def test_airing_has_the_next_date(self):
        eps = [
            episode("show", 2, 1),
            episode("show", 2, 2, "2026-10-04T22:00:00Z", virtual=True),
            episode("show", 2, 3, "2026-10-11T22:00:00Z", virtual=True),
        ]
        s = seasons_of([season("show", 2), *eps])[2]
        self.assertEqual(s["status"], "airing")
        self.assertEqual((s["upcoming"], s["next"]), (2, "2026-10-05"))

    def test_missing_and_tba(self):
        aired = episode("show", 1, 1, virtual=True)
        future = episode("show", 2, 1, "2027-03-01T00:00:00Z", virtual=True)
        items = [season("show", 1), season("show", 2), season("show", 3), aired, future]
        found = seasons_of(items)
        self.assertEqual(found[1]["status"], "missing")
        self.assertEqual(found[2]["status"], "tba")
        self.assertEqual(found[3]["status"], "tba")  # announced, no episodes yet

    def test_specials_only_when_you_have_some(self):
        items = [season("show", 0), episode("show", 0, 1, virtual=True)]
        self.assertNotIn(0, seasons_of(items))
        found = seasons_of([season("show", 0), episode("show", 0, 1)])
        self.assertEqual(found[0]["name"], "Season 0")

    def test_specials_sort_last(self):
        items = [season("show", n) for n in (0, 2, 1)]
        items += [episode("show", n, 1) for n in (0, 2, 1)]
        order = [s["n"] for s in build_seasons(items, set(), TODAY)["show"]]
        self.assertEqual(order, [1, 2, 0])

    def test_duplicate_season_items_keep_every_id(self):
        items = [
            season("show", 1, "real"),
            season("show", 1, "stale"),
            episode("show", 1, 1),
        ]
        self.assertEqual(seasons_of(items)[1]["_ids"], ["real", "stale"])


class AttachSeasons(unittest.TestCase):
    def test_complete_counts_airing_as_complete(self):
        rec = {}
        attach_seasons(rec, [
            {"n": 1, "status": "available"},
            {"n": 2, "status": "airing"},
            {"n": 3, "status": "tba"},
        ])  # fmt: skip
        self.assertEqual((rec["seasons"], rec["complete"]), (2, True))

    def test_incomplete(self):
        rec = {}
        attach_seasons(rec, [{"n": 1, "status": "partial"}])
        self.assertFalse(rec["complete"])


if __name__ == "__main__":
    unittest.main()
