"""scripts/python_versions.py: the supported Python versions and the places naming them."""

import json
import os
import re
import shutil
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "scripts"))
import python_versions as pv  # from scripts/, added to the path above

# As peps.python.org/api/release-cycle.json has them (fewer fields)
CYCLE = {
    "3.17": {"status": "feature"},
    "3.16": {"status": "prerelease"},
    "3.15": {"status": "bugfix"},
    "3.14": {"status": "bugfix"},
    "3.13": {"status": "security"},
    "3.12": {"status": "security"},
    "3.11": {"status": "end-of-life"},
    "3.9": {"status": "end-of-life"},
}


class Supported(unittest.TestCase):
    def test_oldest_and_newest_with_fixes(self):
        self.assertEqual(pv.supported(CYCLE), ("3.12", "3.15"))

    def test_versions_sort_as_numbers(self):
        cycle = {"3.9": {"status": "security"}, "3.10": {"status": "bugfix"}}
        self.assertEqual(pv.supported(cycle), ("3.9", "3.10"))

    def test_none_supported_stops(self):
        with self.assertRaises(SystemExit):
            pv.supported({"3.9": {"status": "end-of-life"}})


class Places(unittest.TestCase):
    def test_this_repository_matches_python_versions_json(self):
        self.assertEqual(
            pv.sync(ROOT, save=False), [], "run: python scripts/python_versions.py sync"
        )

    def test_ci_tests_the_oldest_the_newest_and_the_image(self):
        """ci.yaml reads the versions by these names (the bot can't edit workflows)."""
        self.assertEqual(set(json.loads(pv.read(ROOT, pv.SOURCE))), {"oldest", "newest"})
        ci = pv.read(ROOT, ".github/workflows/ci.yaml")
        self.assertIn("python: [oldest, newest, image]", ci)

    def test_python_version_is_the_images(self):
        """CI's "image" tests run on .python-version: Dependabot moves the Dockerfile only,
        so its pull request for a new Python has to move .python-version too."""
        image = re.search(r"^FROM python:(\d+\.\d+)-alpine@", pv.read(ROOT, "Dockerfile"), re.M)
        self.assertIsNotNone(image, "the Dockerfile has no FROM python:<x.y>-alpine@…")
        self.assertEqual(pv.read(ROOT, ".python-version").strip(), image and image.group(1))

    def test_the_image_runs_a_supported_python(self):
        """When the oldest moves past the image's Python, the image has to move too."""
        oldest, newest = pv.source(ROOT)
        image = pv.read(ROOT, ".python-version").strip()
        self.assertTrue(pv.key(oldest) <= pv.key(image) <= pv.key(newest), image)


class Update(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = tmp.name
        for name in [pv.SOURCE, *pv.places("3.11", "3.15")]:
            shutil.copy(os.path.join(ROOT, name), os.path.join(self.root, name))

    def test_an_end_of_life_and_a_release(self):
        cycle = {**CYCLE, "3.16": {"status": "bugfix"}}
        title = pv.update(self.root, cycle)
        self.assertEqual(
            title, "require Python 3.12 or newer (3.11 is end of life) and test Python 3.16"
        )
        self.assertEqual(pv.source(self.root), ("3.12", "3.16"))
        self.assertIn('target-version = "py312"', pv.read(self.root, "ruff.toml"))
        self.assertIn("python-3.12%2B", pv.read(self.root, "README.md"))
        self.assertIn("CI tests 3.12 and 3.16", pv.read(self.root, "AGENTS.md"))
        sonar = pv.read(self.root, "sonar-project.properties")
        self.assertIn("sonar.python.version=3.12, 3.13, 3.14, 3.15, 3.16\n", sonar)
        self.assertEqual(pv.sync(self.root, save=False), [])

    def test_a_release_only(self):
        cycle = {"3.11": {"status": "security"}, "3.16": {"status": "bugfix"}}
        self.assertEqual(pv.update(self.root, cycle), "test Python 3.16")

    def test_up_to_date_changes_nothing(self):
        before = pv.read(self.root, "README.md")
        cycle = {"3.11": {"status": "security"}, "3.15": {"status": "bugfix"}}
        self.assertEqual(pv.update(self.root, cycle), "")
        self.assertEqual(pv.read(self.root, "README.md"), before)

    def test_a_place_that_is_gone_stops(self):
        pv.write(self.root, "CONTRIBUTING.md", "Any Python.\n")
        with self.assertRaises(SystemExit):
            pv.sync(self.root)


if __name__ == "__main__":
    unittest.main()
