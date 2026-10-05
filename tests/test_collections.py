"""Box sets: duplicates merged, members ordered, ratings and dates borrowed."""

import unittest

from marqueefin.jellyfin import attach_user_data
from marqueefin.records import collection_record, pick_collections


def record(rid, year, rating=None, added="2024-01-01", **extra):
    return {"id": rid, "type": "movie", "year": year, "sort": rid, "rating": rating,
            "released": f"{year}-05-01", "added": added, "genres": ["Action"],
            **extra}  # fmt: skip


BY_ID = {
    "m1": record("m1", 2015, 7.0),
    "m2": record("m2", 2018, 8.0, added="2026-09-01"),
    "m3": record("m3", 2023),
}


class PickCollections(unittest.TestCase):
    def test_duplicates_are_merged_by_tmdb_id(self):
        boxsets = [
            {"Id": "a", "Name": "Ant-Man", "ProviderIds": {"Tmdb": "422834"}},
            {"Id": "b", "Name": "Ant-Man Collection", "ProviderIds": {"Tmdb": "422834"},
             "ImageTags": {"Primary": "x"}},
        ]  # fmt: skip
        members = {"a": ["m2", "m1"], "b": ["m3", "m1"]}
        (kept, ids), *rest = pick_collections(boxsets, members, BY_ID)
        self.assertEqual(rest, [])
        self.assertEqual(kept["Id"], "b")  # the one with a poster
        self.assertEqual(ids, ["m1", "m2", "m3"])  # the union, by year

    def test_box_sets_without_exported_members_are_dropped(self):
        boxsets = [{"Id": "c", "Name": "Elsewhere"}]
        self.assertEqual(pick_collections(boxsets, {"c": ["gone"]}, BY_ID), [])


class CollectionRecord(unittest.TestCase):
    def test_borrows_from_the_members(self):
        item = {"Id": "c", "Type": "BoxSet", "Name": "Trilogy",
                "DateCreated": "2024-01-01T10:00:00Z",
                "ProviderIds": {"Tmdb": "86311"}}  # fmt: skip
        rec = collection_record(item, ["m1", "m2", "m3"], BY_ID, None)
        self.assertEqual(rec["type"], "collection")
        self.assertEqual((rec["year"], rec["endYear"]), (2015, 2023))
        self.assertEqual(rec["released"], "2015-05-01")
        self.assertEqual(rec["updated"], "2026-09-01")  # the newest member
        self.assertEqual((rec["rating"], rec["ratingOf"]), (7.5, 2))
        self.assertEqual(rec["genres"], ["Action"])
        self.assertEqual(
            rec["links"],
            [{"label": "TMDB", "url": "https://www.themoviedb.org/collection/86311"}],
        )


class UserData(unittest.TestCase):
    def test_flags_and_collection_last_watched(self):
        records = [
            {"id": "m1", "type": "movie"},
            {"id": "s1", "type": "series"},
            {"id": "c1", "type": "collection", "items": ["m1"]},
        ]
        user_data = {
            "m1": {"Played": True, "IsFavorite": True,
                   "LastPlayedDate": "2026-09-27T20:15:03.1234567Z"},
            "s1": {"PlayedPercentage": 64.6},
        }  # fmt: skip
        attach_user_data(records, user_data, {"s1": "2026-09-30T10:00:00Z"})
        movie, series, coll = records
        self.assertEqual((movie["watched"], movie["fav"]), (True, True))
        self.assertEqual(movie["lastWatched"], "2026-09-27T20:15:03Z")
        self.assertEqual(series["watchedPct"], 65)
        self.assertEqual(series["lastWatched"], "2026-09-30T10:00:00Z")
        self.assertEqual(coll["lastWatched"], "2026-09-27T20:15:03Z")


if __name__ == "__main__":
    unittest.main()
