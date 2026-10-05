"""Dates, ranges, titles and error messages."""

import contextlib
import email.message
import io
import unittest
import urllib.error

from marqueefin.dates import local_date, utc_stamp, year_of
from marqueefin.log import fmt_duration, log
from marqueefin.media import lang
from marqueefin.net import describe_error
from marqueefin.records import episode_ranges
from marqueefin.titles import same_title, tmdb_key


class LocalDate(unittest.TestCase):
    """Jellyfin stores release dates as local midnight in UTC."""

    def test_east_of_utc_moves_to_the_next_day(self):
        self.assertEqual(local_date("2018-07-03T22:00:00Z"), "2018-07-04")
        self.assertEqual(local_date("2018-07-03T23:00:00.0000000Z"), "2018-07-04")

    def test_utc_and_west_stay(self):
        self.assertEqual(local_date("2018-07-04T00:00:00Z"), "2018-07-04")
        self.assertEqual(local_date("2018-07-04T05:00:00Z"), "2018-07-04")

    def test_noon_is_the_turning_point(self):
        self.assertEqual(local_date("2018-07-03T11:59:59Z"), "2018-07-03")
        self.assertEqual(local_date("2018-07-03T12:00:00Z"), "2018-07-04")

    def test_missing_or_odd_values(self):
        self.assertIsNone(local_date(None))
        self.assertIsNone(local_date(""))
        self.assertEqual(local_date("2018-07-04"), "2018-07-04")

    def test_year_of(self):
        self.assertEqual(year_of("2018-07-04T00:00:00Z"), 2018)
        self.assertIsNone(year_of(None))
        self.assertIsNone(year_of("soon"))


class Stamps(unittest.TestCase):
    def test_utc_stamp_drops_fractions(self):
        self.assertEqual(utc_stamp("2026-01-17T17:26:41.8020000Z"), "2026-01-17T17:26:41Z")
        self.assertIsNone(utc_stamp(None))
        self.assertIsNone(utc_stamp("2026-01-17"))

    def test_fmt_duration(self):
        self.assertEqual(fmt_duration(31), "31s")
        self.assertEqual(fmt_duration(168), "2m 48s")


class LogLines(unittest.TestCase):
    """Icons in front of log lines where the log is UTF-8, plain text elsewhere."""

    def logged(self, encoding, msg, icon=""):
        out = io.TextIOWrapper(io.BytesIO(), encoding=encoding)
        with contextlib.redirect_stderr(out):
            log(msg, icon)
        out.seek(0)
        return out.read()

    def test_icon_after_the_indent(self):
        self.assertEqual(
            self.logged("utf-8", "Fetching library...", "📚"),
            "📚 Fetching library...\n",
        )
        self.assertEqual(self.logged("UTF8", "   Skipping x", "⚠️"), "   ⚠️ Skipping x\n")

    def test_plain_without_utf8(self):
        self.assertEqual(self.logged("cp1252", "   Skipping x", "⚠️"), "   Skipping x\n")
        self.assertEqual(self.logged("utf-8", "   titles 1/2"), "   titles 1/2\n")


class EpisodeRanges(unittest.TestCase):
    def test_runs_and_singles(self):
        self.assertEqual(episode_ranges([7, 1, 2, 3]), "E1–E3, E7")
        self.assertEqual(episode_ranges([4]), "E4")
        self.assertEqual(episode_ranges([]), "")


class Titles(unittest.TestCase):
    def test_same_title_ignores_case_and_punctuation(self):
        self.assertTrue(same_title("American Dad!", "American Dad"))
        self.assertTrue(same_title("Rampage: President Down", "Rampage - President Down"))
        self.assertFalse(same_title("Dark", "Darker"))

    def test_tmdb_key(self):
        movie = {"links": [{"url": "https://www.themoviedb.org/movie/603"}]}
        self.assertEqual(tmdb_key(movie), "movie:603")
        self.assertEqual(tmdb_key({"type": "series", "tmdb": 1396}), "tv:1396")
        self.assertEqual(tmdb_key({"type": "movie", "tmdb": 603}), "movie:603")
        self.assertIsNone(tmdb_key({"links": []}))

    def test_language_codes(self):
        self.assertEqual(lang("ger"), "de")
        self.assertEqual(lang("ENG"), "en")
        self.assertIsNone(lang("und"))
        self.assertIsNone(lang(None))


class DescribeError(unittest.TestCase):
    def http_error(self, body, code=500, reason="Internal Server Error"):
        e = urllib.error.HTTPError(
            "https://seerr.example/api/v1/tv/327719?language=en",
            code,
            reason,
            email.message.Message(),
            io.BytesIO(body.encode()),
        )
        self.addCleanup(e.close)
        return e

    def test_json_message(self):
        e = self.http_error('{"message":"Unable to retrieve series."}')
        self.assertEqual(
            describe_error(e),
            "HTTP 500 Internal Server Error from /api/v1/tv/327719: Unable to retrieve series.",
        )

    def test_plain_body_is_shortened(self):
        e = self.http_error("<html>" + "x" * 1000, 502, "Bad Gateway")
        text = describe_error(e)
        self.assertTrue(text.startswith("HTTP 502 Bad Gateway from /api/v1/tv/327719: "))
        self.assertLess(len(text), 400)

    def test_other_errors(self):
        self.assertEqual(describe_error(TimeoutError("timed out")), "TimeoutError: timed out")


if __name__ == "__main__":
    unittest.main()
