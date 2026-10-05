"""The rendered page, the demo page and the command line."""

import base64
import contextlib
import hashlib
import io
import json
import os
import re
import sys
import tempfile
import unittest
from datetime import datetime, timezone
from unittest import mock

from marqueefin import __version__, render
from marqueefin.cli import load_dotenv, parse_args
from marqueefin.render import NODE_MODULES, render_html
from marqueefin.seal import unseal

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "scripts"))
import demo_page  # from scripts/, added to the path above

GENERATED = datetime(2026, 9, 29, 15, 5, tzinfo=timezone.utc)
PLACEHOLDERS = ("STYLE", "VENDOR", "SCRIPT", "TITLE", "SUMMARY", "DESCRIPTION",
                "FAVICON", "GENERATED", "UPDATED", "VERSION", "CREDIT", "DATA",
                "FLAGS", "REQUESTS", "SETTINGS", "I18N", "SEALED", "LOCKED")  # fmt: skip


def movie(title, rid="m1"):
    return {"id": rid, "type": "movie", "title": title, "sort": title.lower(),
            "year": 2026, "added": "2026-09-01", "genres": [], "links": []}  # fmt: skip


class RenderHtml(unittest.TestCase):
    def render(self, records, title="Movie Night", **kw):
        return render_html(title, records, GENERATED, **kw)

    def test_every_placeholder_is_filled(self):
        page = self.render([movie("Paper Moons")])
        left = [p for p in PLACEHOLDERS if f"__{p}__" in page]
        self.assertEqual(left, [])
        self.assertIn(f"Marqueefin {__version__}", page)
        self.assertIn("Not affiliated with the Jellyfin project.", page)

    def test_placeholder_text_in_data_is_left_alone(self):
        page = self.render([movie("The __TITLE__ Story")], title="__DATA__ night")
        self.assertIn("The __TITLE__ Story", page)
        self.assertIn("<title>__DATA__ night</title>", page)

    def test_data_cannot_close_the_script_block(self):
        page = self.render([movie("</script><script>alert(1)</script>")])
        self.assertNotIn("</script><script>alert(1)", page)
        self.assertIn("<\\/script>", page)

    def test_title_is_escaped(self):
        page = self.render([], title="<b>Bob & Alice</b>")
        self.assertIn("<title>&lt;b&gt;Bob &amp; Alice&lt;/b&gt;</title>", page)

    def test_translations_and_settings_are_embedded(self):
        page = self.render([], settings={"titleLang": "fr"})
        self.assertIn('"titleLang": "fr"', page)
        self.assertIn('"mainLangs": ["en"]', page)  # the default
        self.assertIn('"_name": "Deutsch"', page)
        self.assertIn('"_name": "English"', page)

    def test_content_security_policy(self):
        page = self.render([movie("__CSP__ </script>")], title="__CSP__")
        m = re.search(r'Content-Security-Policy"\s+content="([^"]+)"', page)
        if not m:
            self.fail("no Content-Security-Policy")
        policy = m[1]
        self.assertIn("default-src 'none'", policy)
        self.assertNotIn("unsafe-inline", policy)
        self.assertNotIn("unsafe-eval", policy)
        # every inline script and the style block, by hash: nothing else may run
        for tag in ("script", "style"):
            bodies = re.findall(
                rf'^[ \t]*<{tag}(?: type="module")?>(.*?)</{tag}>', page, re.M | re.S
            )
            self.assertGreaterEqual(len(bodies), 1)
            for body in bodies:
                digest = base64.b64encode(hashlib.sha256(body.encode()).digest()).decode()
                self.assertIn(f"'sha256-{digest}'", policy)
        self.assertIn('<script type="module">', page)  # the page's script, hashed above
        self.assertIn("<title>__CSP__</title>", page)  # the placeholder text stays
        self.assertIn(r'"title":"__CSP__ <\/script>"', page)

    def test_no_outside_requests(self):
        page = self.render([])
        for host in ("fonts.googleapis.com", "fonts.gstatic.com", "cdn.jsdelivr"):
            self.assertNotIn(host, page)
        self.assertIn('name="referrer" content="no-referrer"', page)

    @unittest.skipUnless(os.path.isdir(NODE_MODULES), "needs `npm ci` (the fonts)")
    def test_fonts_are_embedded_with_their_license(self):
        page = self.render([])
        self.assertEqual(page.count("url(data:font/woff2;base64,"), 4)
        self.assertIn("SIL OPEN FONT LICENSE Version 1.1", page)
        self.assertIn("Big Shoulders Display Variable", page)
        self.assertIn("Instrument Sans Variable", page)

    def test_summary(self):
        records = [
            movie("A", "1"),
            movie("B", "2"),
            {**movie("C", "3"), "type": "series"},
        ]
        self.assertIn("2 movies and 1 series", self.render(records))
        self.assertIn("Nothing here yet", self.render([]))

    @unittest.skipUnless(os.path.isdir(NODE_MODULES), "needs `npm ci` (Floating UI)")
    def test_floating_ui_and_its_license_are_inlined(self):
        page = self.render([])
        self.assertIn("@floating-ui/dom", page)
        self.assertIn("Permission is hereby granted", page)


class Credit(unittest.TestCase):
    """The footer's project link: "GitHub" only when it really points there."""

    def credit(self, url):
        with mock.patch("marqueefin.render.PROJECT_URL", url):
            return render.credit_html()

    def test_github(self):
        self.assertIn(">GitHub</a>", self.credit("https://github.com/TheDelta/marqueefin"))

    def test_github_elsewhere_in_the_address_is_not_github(self):
        for url in ("https://evil.example/github.com", "https://github.com.evil.example/x"):
            with self.subTest(url=url):
                self.assertIn(">Source code</a>", self.credit(url))

    def test_no_link_without_a_url(self):
        self.assertNotIn("<a ", self.credit(""))


class ProtectedPage(unittest.TestCase):
    """A page protected by a passphrase: nothing of the library in the clear."""

    @classmethod
    def setUpClass(cls):
        cls.page = render_html(
            "Movie Night",
            [movie("Paper Moons"), movie("Glass Harbor", "m2")],
            GENERATED,
            {"de": "data:image/svg+xml;base64,AAAA"},
            [{"type": "movie", "title": "Silver Delta"}],
            protect=("correct horse battery", None),
        )

    def block(self, name):
        m = re.search(rf'<script type="application/json" id="{name}">\s*(.*?)\s*</script>',
                      self.page, re.S)  # fmt: skip
        if m is None:
            self.fail(f"no #{name} block")
        return json.loads(m.group(1))

    def test_nothing_of_the_library_in_the_clear(self):
        for text in ("Paper Moons", "Glass Harbor", "Silver Delta", "2 movies"):
            self.assertNotIn(text, self.page)
        self.assertEqual(self.block("data"), [])
        self.assertEqual(self.block("requests"), [])
        self.assertEqual(self.block("flags"), {})
        self.assertIn('<body class="locked">', self.page)
        self.assertIn("Protected with a passphrase", self.page)

    def test_the_passphrase_opens_it(self):
        opened = json.loads(unseal(self.block("sealed"), "correct horse battery") or "null")
        self.assertEqual([r["title"] for r in opened["data"]], ["Paper Moons", "Glass Harbor"])
        self.assertEqual(opened["requests"][0]["title"], "Silver Delta")
        self.assertIn("de", opened["flags"])

    def test_unprotected_pages_have_no_seal(self):
        page = render_html("Movie Night", [movie("Paper Moons")], GENERATED)
        self.assertIn('<body class="">', page)
        self.assertRegex(page, r'id="sealed">\s*null\s*</script>')

    def test_the_bundle_carries_the_license_of_its_sha3_code(self):
        # unlock.js bundles @noble/hashes; noble-license.js puts its license next to it
        with open(os.path.join(ROOT, "src", "js", "noble-license.js"), encoding="utf-8") as f:
            ours = " ".join(f.read().split())
        license_file = os.path.join(NODE_MODULES, "@noble", "hashes", "LICENSE")
        if not os.path.isfile(license_file):
            self.skipTest("npm ci first")
        with open(license_file, encoding="utf-8") as f:
            theirs = " ".join(f.read().split())
        self.assertIn(theirs, ours)


class DemoPage(unittest.TestCase):
    """scripts/demo_page.py goes through the real renderer (flags left out: no
    network in tests)."""

    def test_renders(self):
        today = datetime.now().astimezone().date()
        records = demo_page.records(today)
        page = render_html("Demo", records, GENERATED, {}, demo_page.requests(today))
        self.assertIn("The Quiet Coast", page)
        self.assertIn("Long Way Home", page)  # a request
        self.assertEqual(len({r["id"] for r in records}), len(records))


class CommandLine(unittest.TestCase):
    def test_help_never_shows_keys_or_addresses(self):
        secrets = {
            "JELLYFIN_URL": "https://jellyfin.private.example",
            "JELLYFIN_API_KEY": "secret-jellyfin-key",
            "SEER_API_KEY": "secret-seerr-key",
            "JELLYFIN_USER_ID": "secret-user-id",
        }
        out = io.StringIO()
        with (
            mock.patch.dict(os.environ, secrets),
            mock.patch.object(sys, "argv", ["export.py", "--help"]),
            mock.patch("marqueefin.cli.load_dotenv"),  # not the developer's .env
            contextlib.redirect_stdout(out),
            self.assertRaises(SystemExit),
        ):
            parse_args()
        text = out.getvalue()
        for value in secrets.values():
            self.assertNotIn(value, text)
        self.assertIn("collection.html", text)  # other defaults are still shown

    def test_load_dotenv(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, ".env")
            with open(path, "w", encoding="utf-8") as f:
                f.write(
                    "# comment\n"
                    "MQF_TEST_A=plain value # trailing comment\n"
                    'export MQF_TEST_B="quoted # not a comment"\n'
                    "MQF_TEST_C='single'\n"
                    "MQF_TEST_SET=from the file\n"
                    "not a setting\n"
                )
            with mock.patch.dict(os.environ, {"MQF_TEST_SET": "from the environment"}):
                load_dotenv(path)
                self.assertEqual(os.environ["MQF_TEST_A"], "plain value")
                self.assertEqual(os.environ["MQF_TEST_B"], "quoted # not a comment")
                self.assertEqual(os.environ["MQF_TEST_C"], "single")
                self.assertEqual(os.environ["MQF_TEST_SET"], "from the environment")


if __name__ == "__main__":
    unittest.main()
