"""JsonCache: what's remembered between runs."""

import json
import os
import tempfile
import time
import unittest
from unittest import mock

from marqueefin.cache import MISS, JsonCache


class JsonCacheTest(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.dir = tmp.name

    def cache(self, **kw):
        return JsonCache(self.dir, "test.json", max_days=7, **kw)

    def test_round_trip(self):
        c = self.cache()
        c.put("a", {"x": 1})
        c.save()
        self.assertEqual(self.cache().get("a"), {"x": 1})

    def test_entries_not_used_are_dropped_on_save(self):
        c = self.cache()
        c.put("a", 1)
        c.put("b", 2)
        c.save()
        c = self.cache()
        c.get("a")
        c.save()
        c = self.cache()
        self.assertEqual((c.get("a"), c.get("b")), (1, None))

    def test_entries_expire(self):
        c = self.cache()
        c.put("a", 1)
        c.save()
        later = time.time() + 8 * 86400  # past even the longest lifetime
        with mock.patch("marqueefin.cache.time.time", return_value=later):
            self.assertIsNone(self.cache().get("a"))

    def test_refresh_ignores_what_is_stored(self):
        c = self.cache()
        c.put("a", 1)
        c.save()
        self.assertIsNone(self.cache(refresh=True).get("a"))

    def test_other_format_versions_are_ignored(self):
        with open(os.path.join(self.dir, "test.json"), "w", encoding="utf-8") as f:
            json.dump({"version": -1, "entries": {"a": [time.time(), 1]}}, f)
        self.assertIsNone(self.cache().get("a"))

    def test_broken_file_starts_over(self):
        with open(os.path.join(self.dir, "test.json"), "w", encoding="utf-8") as f:
            f.write("{not json")
        self.assertIsNone(self.cache().get("a"))

    def test_none_is_a_value(self):
        c = self.cache()
        c.put("a", None)
        c.save()
        self.assertIs(self.cache().get("a", MISS), None)

    def test_without_a_cache_dir_nothing_is_written(self):
        c = JsonCache("", "test.json", 7)
        c.put("a", 1)
        c.save()
        self.assertEqual(os.listdir(self.dir), [])


if __name__ == "__main__":
    unittest.main()
