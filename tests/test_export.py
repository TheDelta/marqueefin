"""The whole export against tests/fake_server.py, no network."""

import contextlib
import io
import json
import os
import re
import sys
import tempfile
import unittest
from unittest import mock

from marqueefin import __version__
from marqueefin.cli import main
from marqueefin.seal import unseal
from tests import fake_server
from tests.fake_server import FakeServer

PREFIXES = ("JELLYFIN_", "SEER_", "EXPORT_", "GOTIFY_", "UPLOAD_")


def read_block(page, block_id):
    """The JSON in <script type="application/json" id="..."> of the page."""
    m = re.search(rf'<script[^>]*id="{block_id}"[^>]*>(.*?)</script>', page, re.S)
    if not m:
        raise AssertionError(f"no #{block_id} block in the page")
    return json.loads(m.group(1).replace("<\\/", "</"))


class Runner:
    """Runs main() against a fake server, with settings only from the command
    line (not from the developer's .env or environment), into a temporary folder."""

    def __init__(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = self.tmp.name
        self.out = os.path.join(self.dir, "page.html")
        env = {k: v for k, v in os.environ.items() if not k.startswith(PREFIXES)}
        self.patches = [
            mock.patch.dict(os.environ, env, clear=True),
            mock.patch("marqueefin.cli.load_dotenv"),
        ]
        for patch in self.patches:
            patch.start()

    def close(self):
        for patch in reversed(self.patches):
            patch.stop()
        self.tmp.cleanup()

    def run(self, server, *args, seerr=True):
        """The export's log. Fails on requests the fake server doesn't know."""
        argv = ["export.py", "--url", server.url, "--api-key", fake_server.JELLYFIN_KEY,
                "-o", self.out, "--cache-dir", os.path.join(self.dir, "cache"),
                "--title", "Test Night", "--workers", "4", *args]  # fmt: skip
        if seerr:
            argv += ["--seerr-url", server.seerr_url, "--seerr-api-key", fake_server.SEERR_KEY]  # fmt: skip
        log = io.StringIO()
        with (
            mock.patch.object(sys, "argv", argv),
            mock.patch("marqueefin.media.FLAG_URL", server.url + "/flags/{}.svg"),
            mock.patch("marqueefin.seerr.TMDB_POSTER", server.url + "/tmdb{}"),
            contextlib.redirect_stderr(log),
            contextlib.redirect_stdout(log),
        ):
            main()
        if server.unknown:
            raise AssertionError(f"requests the fake server doesn't know: {server.unknown}")
        return log.getvalue()

    def page(self):
        with open(self.out, encoding="utf-8") as f:
            return f.read()


class ExportTest(unittest.TestCase):
    def setUp(self):
        self.runner = Runner()
        self.addCleanup(self.runner.close)
        self.dir, self.out = self.runner.dir, self.runner.out

    def _run_export(self, server, *args, seerr=True):
        return self.runner.run(server, *args, seerr=seerr)

    def _page(self):
        return self.runner.page()


class FullExport(unittest.TestCase):
    """One full export (Seerr included); the tests look at its page and log."""

    @classmethod
    def setUpClass(cls):
        runner = Runner()
        cls.addClassCleanup(runner.close)
        with FakeServer() as server:
            cls.log = runner.run(server, "--title-language", "de")
        cls.page_text = runner.page()
        cls.records = {r["id"]: r for r in read_block(cls.page_text, "data")}
        cls.requests = read_block(cls.page_text, "requests")
        cls.flags = read_block(cls.page_text, "flags")
        cls.config = read_block(cls.page_text, "config")

    def test_movies_in_box_sets_are_not_lost(self):
        # Without CollapseBoxSetItems=false the box set would replace them
        movies = sorted(r["title"] for r in self.records.values() if r["type"] == "movie")
        self.assertEqual(movies, ["Ant-Man", "Ant-Man and the Wasp", "Arrival"])

    def test_movie_record(self):
        m = self.records["m1"]
        self.assertEqual(m["released"], "2016-11-10")  # local date, not the UTC one
        self.assertEqual((m["rating"], m["cert"], m["runtime"]), (7.9, "FSK 12", 117))
        self.assertEqual(m["media"]["res"], "4K")
        self.assertEqual(m["media"]["hdr"], ["Dolby Vision", "HDR10"])
        self.assertEqual(m["media"]["audio"], "TrueHD Atmos 7.1")
        self.assertEqual(m["media"]["subLangs"], ["de"])  # forced English left out
        self.assertEqual((m["watched"], m["fav"]), (True, True))
        self.assertEqual(m["lastWatched"], "2026-09-27T20:15:03Z")
        self.assertTrue(m["poster"].startswith("data:image/webp;base64,"))
        self.assertEqual([link["label"] for link in m["links"]], ["IMDb", "TMDB"])

    def test_duplicate_box_sets_become_one_collection(self):
        colls = [r for r in self.records.values() if r["type"] == "collection"]
        self.assertEqual(len(colls), 1)  # "Elsewhere" has nothing exported: dropped
        coll = colls[0]
        self.assertEqual(coll["id"], "bs-b")  # the copy with a poster
        self.assertEqual(coll["items"], ["m2", "m3"])  # the union, by year
        self.assertEqual((coll["year"], coll["endYear"]), (2015, 2018))
        self.assertEqual(coll["titleAlt"], "Ant-Man Filmreihe")

    def test_series_seasons(self):
        s = self.records["s1"]
        seasons = {x["n"]: x for x in s["seasonList"]}
        self.assertEqual(seasons[1]["status"], "partial")
        self.assertEqual(seasons[1]["missing"], "E3")
        self.assertTrue(seasons[1]["watched"])  # from the real season, not the stale one
        self.assertEqual(seasons[2]["status"], "airing")
        self.assertEqual(seasons[2]["next"], "2099-01-01")
        self.assertEqual(seasons[3]["status"], "tba")
        self.assertEqual((s["seasons"], s["complete"]), (2, False))
        self.assertEqual(s["updated"], "2026-09-01")  # the newest episode
        self.assertEqual(s["watchedPct"], 40)
        self.assertEqual(s["lastWatched"], "2026-10-01T10:00:00Z")  # newest episode play
        self.assertEqual(s["media"]["res"], "1080p")  # from the episodes' files
        self.assertEqual(s["titleAlt"], "Dunkle Küste")

    def test_requests(self):
        by_tmdb = {r["tmdb"]: r for r in self.requests}
        # in the library already, and declined: left out
        self.assertEqual(sorted(by_tmdb), [1001, 1396, 327719])
        film = by_tmdb[1001]
        self.assertEqual(film["state"], "pending")
        self.assertEqual(
            film["release"],
            {"kind": "upcoming", "date": "2099-08-01", "what": "digital"},
        )
        self.assertEqual(film["titleAlt"], "Zukunftsfilm")
        self.assertTrue(film["poster"].startswith("data:image/webp;base64,"))
        show = by_tmdb[1396]
        self.assertEqual([s["kind"] for s in show["seasons"]], ["partial", "available"])
        gone = by_tmdb[327719]
        self.assertEqual((gone["title"], gone["unknown"]), ("TMDB #327719", True))
        self.assertIn("Unable to retrieve series.", self.log)
        # newest request first
        self.assertEqual([r["tmdb"] for r in self.requests], [1001, 1396, 327719])

    def test_second_title_language(self):
        self.assertEqual(self.config, {"titleLang": "de", "mainLangs": ["en", "de"]})
        # TMDB had no German title for Ant-Man: its Japanese original isn't used
        self.assertNotIn("titleAlt", self.records["m2"])
        self.assertNotIn("titleAlt", self.records["m1"])  # the same in German
        i18n = read_block(self.page_text, "i18n")
        folder = os.path.join(os.path.dirname(os.path.dirname(__file__)), "src", "i18n")
        catalogs = sorted(f[:-5] for f in os.listdir(folder) if f.endswith(".json"))
        self.assertEqual(sorted(i18n), catalogs)  # every language of src/i18n
        self.assertIn("de", catalogs)

    def test_flags_and_page(self):
        self.assertEqual(sorted(self.flags), ["de", "en"])
        self.assertIn("<title>Test Night</title>", self.page_text)
        self.assertIn("3 movies, 1 series and 1 collection", self.page_text)
        for secret in (fake_server.JELLYFIN_KEY, fake_server.SEERR_KEY):
            self.assertNotIn(secret, self.page_text)
            self.assertNotIn(secret, self.log)
        self.assertIn(f"Marqueefin {__version__}", self.log)


class Caching(ExportTest):
    def test_a_second_run_reuses_the_cache_and_gives_the_same_page(self):
        with FakeServer() as server:
            self._run_export(server)
            first = read_block(self._page(), "data")
            first_requests = read_block(self._page(), "requests")
            server.hits.clear()
            log = self._run_export(server)
            self.assertEqual(server.hits["episode details"], 0)
            # Box set contents are remembered while all their titles still exist;
            # "Elsewhere" holds one that isn't in the library, so it's asked again
            asked_again = [k for k in server.hits if k.startswith("members:bs-")]
            self.assertEqual(asked_again, ["members:bs-x"])
            self.assertIn("2 remembered, 1 fetched", log)
            self.assertEqual(read_block(self._page(), "data"), first)
            self.assertEqual(read_block(self._page(), "requests"), first_requests)

    def test_refresh_one_page_at_a_time_gives_the_same_records(self):
        with (
            FakeServer() as server,
            mock.patch("marqueefin.jellyfin.PAGE_SIZE", 2),  # several pages per query
        ):
            self._run_export(server)
            cached = read_block(self._page(), "data")
            self._run_export(server, "--refresh", "--parallel-pages", "1")
            self.assertEqual(read_block(self._page(), "data"), cached)


class Options(ExportTest):
    def test_lean_export(self):
        with FakeServer() as server:
            self._run_export(
                server, "--types", "movies", "--no-user-data", "--posters", "none",
                "--no-media", "--library", "Movies", seerr=False,
            )  # fmt: skip
        records = read_block(self._page(), "data")
        self.assertEqual({r["type"] for r in records}, {"movie"})
        for r in records:
            self.assertNotIn("watched", r)
            self.assertNotIn("media", r)
            self.assertIsNone(r["poster"])
        self.assertEqual(read_block(self._page(), "requests"), [])

    def test_posters_in_a_folder(self):
        with FakeServer() as server:
            self._run_export(server, "--posters", "folder", "--no-seasons", seerr=False)
        folder = os.path.join(self.dir, "page_posters")
        poster = read_block(self._page(), "data")[0]["poster"]
        self.assertTrue(poster.startswith("page_posters/"))
        self.assertTrue(os.path.isfile(os.path.join(self.dir, poster)))
        self.assertTrue(os.listdir(folder))

    def test_a_passphrase_seals_the_page(self):
        os.environ["EXPORT_PASSPHRASE"] = "correct horse battery"  # Runner restores it
        with FakeServer() as server:
            log = self._run_export(server, "--no-seasons", seerr=False)
        self.assertIn("protected with a passphrase", log)
        page = self._page()
        self.assertEqual(read_block(page, "data"), [])
        opened = json.loads(unseal(read_block(page, "sealed"), "correct horse battery") or "null")
        self.assertEqual(len(opened["data"]), 5)
        # The salt stays in the cache, so a remembered key opens the next page too
        with FakeServer() as server:
            self._run_export(server, "--no-seasons", seerr=False)
        self.assertEqual(
            read_block(self._page(), "sealed")["salt"], read_block(page, "sealed")["salt"]
        )

    def test_passphrase_from_a_file_and_its_checks(self):
        path = os.path.join(self.dir, "passphrase")
        with open(path, "w", encoding="utf-8") as f:
            f.write("short\n")
        with FakeServer() as server:
            log = self._run_export(server, "--passphrase-file", path, "--no-seasons", seerr=False)
        self.assertIn("the passphrase is short", log)
        self.assertIsNotNone(unseal(read_block(self._page(), "sealed"), "short"))
        with FakeServer() as server, self.assertRaises(SystemExit) as e:
            self._run_export(server, "--passphrase-file", path, "--posters", "folder")
        self.assertIn("needs --posters embed", str(e.exception))
        with FakeServer() as server, self.assertRaises(SystemExit) as e:
            self._run_export(server, "--passphrase-file", path + ".missing")
        self.assertIn("can't be read", str(e.exception))

    def test_a_big_page_suggests_smaller_posters(self):
        with FakeServer() as server, mock.patch("marqueefin.cli.BIG_PAGE_MB", 0):
            log = self._run_export(server, "--no-seasons", seerr=False)
        self.assertIn("--poster-width 200 --poster-quality 60", log)
        with FakeServer() as server:
            log = self._run_export(server, "--no-seasons", seerr=False)
        self.assertNotIn("--poster-width", log)

    def test_items_without_a_user_falls_back_to_the_user_endpoint(self):
        with FakeServer(require_user=True) as server:
            log = self._run_export(server, seerr=False)
        self.assertIn("using user-scoped endpoint", log)
        self.assertEqual(len(read_block(self._page(), "data")), 5)

    def test_title_language_checks(self):
        with FakeServer() as server:
            log = self._run_export(server, "--title-language", "pt_br", seerr=False)
        self.assertIn("--title-language needs Seerr", log)
        self.assertEqual(read_block(self._page(), "config")["titleLang"], "")
        with FakeServer() as server, self.assertRaises(SystemExit) as e:
            self._run_export(server, "--title-language", "german!")
        self.assertIn("isn't a language code", str(e.exception))

    def test_main_languages(self):
        with FakeServer() as server:
            self._run_export(server, "--main-languages", "EN, fr", "--no-seasons", seerr=False)
        self.assertEqual(read_block(self._page(), "config")["mainLangs"], ["en", "fr"])

    def test_list_libraries(self):
        with FakeServer() as server:
            log = self._run_export(server, "--list-libraries", seerr=False)
        self.assertIn("Movies  (movies)", log)
        self.assertFalse(os.path.exists(self.out))


class Failures(ExportTest):
    def test_wrong_api_key(self):
        with FakeServer(reject_key=True) as server, self.assertRaises(SystemExit) as e:
            self._run_export(server, seerr=False)
        self.assertIn("rejected the API key", str(e.exception))

    def test_unreachable_server(self):
        with FakeServer() as server:
            pass  # stopped: nothing listens there any more
        with self.assertRaises(SystemExit) as e:
            self._run_export(server, seerr=False)
        self.assertIn("can't reach", str(e.exception))

    def test_unknown_library(self):
        with FakeServer() as server, self.assertRaises(SystemExit) as e:
            self._run_export(server, "--library", "Music", seerr=False)
        self.assertIn("no library called 'Music'", str(e.exception))

    def test_missing_settings(self):
        with (
            mock.patch.object(sys, "argv", ["export.py", "-o", self.out]),
            contextlib.redirect_stderr(io.StringIO()),
            self.assertRaises(SystemExit) as e,
        ):
            main()
        self.assertIn("--url and --api-key are required", str(e.exception))

    def test_seerr_down_only_skips_the_requests(self):
        with FakeServer() as seerr:
            pass  # stopped
        with FakeServer() as server:
            server.seerr_url = seerr.seerr_url
            log = self._run_export(server)
        self.assertIn("Skipping requests: can't read Seerr", log)
        self.assertEqual(read_block(self._page(), "requests"), [])
        self.assertEqual(len(read_block(self._page(), "data")), 5)


if __name__ == "__main__":
    unittest.main()
