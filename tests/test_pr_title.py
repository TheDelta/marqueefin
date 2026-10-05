"""scripts/pr_title.py: the comment that explains a pull request title."""

# cspell:ignore recieve

import os
import subprocess
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "scripts"))
import pr_title  # from scripts/, added to the path above

# commitlint's output for "Fix: Something.", colors and all
OUTPUT = (
    "\x1b[90m⧗\x1b[39m   --- input ---\n\x1b[1mFix: Something.\x1b[22m\n"
    "\x1b[31m✖\x1b[39m   subject must not end with full stop \x1b[90m[subject-full-stop]\x1b[39m\n"
    "\x1b[31m✖\x1b[39m   type must be lower-case \x1b[90m[type-case]\x1b[39m\n"
    "\x1b[31m✖\x1b[39m   something new \x1b[90m[some-new-rule]\x1b[39m\n\n"
    "\x1b[1m\x1b[31m✖\x1b[39m   found 3 problems, 0 warnings\x1b[22m\n"
    "ⓘ   Get help: https://github.com/conventional-changelog/commitlint\n"
)


class Problems(unittest.TestCase):
    def test_plain_words_and_unknown_rules(self):
        self.assertEqual(pr_title.problems(OUTPUT), [
            "No full stop at the end.",
            "The type is lowercase: `fix:`, not `Fix:`.",
            "something new",  # commitlint's own words
        ])  # fmt: skip

    def test_nothing_recognized(self):
        self.assertEqual(pr_title.problems("odd output"), [])


class NewScope(unittest.TestCase):
    CONFIG = 'export const SCOPES = [\n  "ci",\n  "page",\n];\n'
    # commitlint's output for "fix(ci): …" with main's scopes
    SCOPE = "\x1b[31m✖\x1b[39m   scope must be one of [page] \x1b[90m[scope-enum]\x1b[39m\n"

    def test_a_scope_the_pull_request_adds(self):
        self.assertTrue(pr_title.only_new_scope("fix(ci): the checkout", self.SCOPE, self.CONFIG))

    def test_not_without_a_scope(self):
        self.assertFalse(pr_title.only_new_scope("ci: x", self.SCOPE, self.CONFIG))

    def test_not_when_the_scope_is_unknown_there_too(self):
        self.assertFalse(pr_title.only_new_scope("fix(cii): x", self.SCOPE, self.CONFIG))

    def test_not_when_something_else_fails_too(self):
        both = self.SCOPE + OUTPUT
        self.assertFalse(pr_title.only_new_scope("fix(ci): x.", both, self.CONFIG))

    def test_scopes_are_read_as_text(self):
        self.assertEqual(pr_title.scopes_in(self.CONFIG), ["ci", "page"])
        self.assertEqual(pr_title.scopes_in("no list"), [])


class Comment(unittest.TestCase):
    def test_failing(self):
        text = pr_title.failing("Fix: Something.", OUTPUT, "o/r")
        self.assertTrue(text.startswith(pr_title.MARKER))
        self.assertIn("> Fix: Something.", text)
        self.assertIn("- No full stop at the end.", text)
        self.assertIn("| `feat(page): filter by audio language` | 🚀 Features |", text)
        self.assertIn("`page`", text)  # the scopes from commitlint.config.mjs
        self.assertIn("`seerr`", text)
        self.assertIn("https://github.com/o/r/blob/main/CONTRIBUTING.md", text)

    def test_failing_without_details(self):
        text = pr_title.failing("", "", "o/r")
        self.assertIn("> (empty)", text)
        self.assertIn("doesn't match `type(scope): what changed`", text)

    def test_spelling_only(self):
        text = pr_title.failing("fix: recieve it", "", "o/r", ["recieve"], lint_ok=True)
        self.assertIn("spell checker doesn't know", text)
        self.assertIn("`recieve`", text)
        self.assertIn("cspell.config.yaml", text)
        self.assertNotIn("Conventional Commits", text)

    def test_format_and_spelling(self):
        text = pr_title.failing("Fix: recieve.", OUTPUT, "o/r", ["recieve"])
        self.assertIn("doesn't follow Conventional Commits", text)
        self.assertIn("- No full stop at the end.", text)
        self.assertIn("Unknown to the spell checker: `recieve`", text)

    def test_words_the_pull_request_adds(self):
        config = "words:\n  - docstrings\n  - 'Pokémon'\nignorePaths:\n  - build/**\n"
        self.assertEqual(
            pr_title.not_listed(["Docstrings", "pokémon", "recieve"], config), ["recieve"]
        )

    def test_unknown_writes_nothing_when_every_word_is_known(self):
        # The workflow tests the output file for emptiness: a lone newline would make
        # every title "misspelled", with an empty list of words
        with tempfile.TemporaryDirectory() as tmp:
            words = os.path.join(tmp, "words.txt")
            config = os.path.join(tmp, "cspell.yaml")
            with open(config, "w", encoding="utf-8", newline="\n") as f:
                f.write("words:\n  - docstrings\n")
            script = os.path.join(ROOT, "scripts", "pr_title.py")
            for found, expected in (("", ""), ("docstrings\n", ""), ("recieve\n", "recieve\n")):
                with open(words, "w", encoding="utf-8", newline="\n") as f:
                    f.write(found)
                out = subprocess.run(
                    [sys.executable, script, "unknown", "--words", words, "--config", config],
                    capture_output=True,
                    check=True,
                ).stdout
                self.assertEqual(out.decode().replace("\r\n", "\n"), expected)

    def test_passing_shows_the_release_notes_line(self):
        text = pr_title.passing("fix(seerr): no date", 12, "someone", False, "o/r")
        self.assertTrue(text.startswith(pr_title.MARKER))
        self.assertIn("under **🐛 Fixes**", text)
        self.assertIn(
            "- **seerr:** No date by [@someone](https://github.com/someone) in "
            "[#12](https://github.com/o/r/pull/12)",
            text,
        )


if __name__ == "__main__":
    unittest.main()
