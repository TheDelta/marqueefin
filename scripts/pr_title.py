#!/usr/bin/env python3
"""The comment explaining a pull request title (pr-title-help.yaml).

commitlint output | python scripts/pr_title.py fail --title T --pr 12 [--words F] [--lint-ok]
python scripts/pr_title.py unknown --words F --config cspell.config.yaml
commitlint output | python scripts/pr_title.py new-scope --title T --config commitlint.config.mjs
python scripts/pr_title.py ok --title T --pr 12 --author someone
"""

import argparse
import io
import os
import re
import sys

import changelog  # scripts/changelog.py, next to this script

MARKER = "<!-- marqueefin:pr-title -->"
ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
ANSI = re.compile(r"\x1b\[[0-9;]*m")
GUIDE = "blob/main/CONTRIBUTING.md#commit-messages-and-pull-request-titles"

EXAMPLES = [
    ("feat(page): filter by audio language", changelog.FEATURES),
    ("fix(seerr): requests without a date", changelog.FIXES),
    ("perf: faster poster downloads", changelog.PERFORMANCE),
    ("docs: Docker setup on Synology", changelog.DOCS),
    ("ci: …, build: …, chore: …, refactor: …, test: …", changelog.MAINTENANCE),
    ("feat!: new list format (breaking)", changelog.BREAKING),
]


def scopes_in(config_text):
    """SCOPES in a commitlint.config.mjs, read as text."""
    m = re.search(r"SCOPES = \[(.*?)\]", config_text, re.S)
    return re.findall(r'"([^"]+)"', m.group(1)) if m else []


def scopes():
    """The scopes commitlint accepts here (main's commitlint.config.mjs)."""
    with open(os.path.join(ROOT, "commitlint.config.mjs"), encoding="utf-8") as f:
        return scopes_in(f.read())


# commitlint's rules in plain words; others keep commitlint's own message
RULES = {
    "type-empty": "It doesn't start with a type, like `feat:` or `fix:`.",
    "type-enum": "The type isn't one of the known ones (table below).",
    "type-case": "The type is lowercase: `fix:`, not `Fix:`.",
    "subject-empty": "Nothing after the colon says what changed.",
    "scope-enum": "The scope isn't one of the known ones (below).",
    "scope-case": "The scope is lowercase: `fix(page):`.",
    "subject-full-stop": "No full stop at the end.",
    "subject-case": "Start the text after the colon in lowercase.",
    "header-max-length": "It's longer than 100 characters.",
}


def findings(output):
    """commitlint's findings as (rule, message)."""
    found = []
    for line in ANSI.sub("", output).splitlines():
        text = line.strip()
        # "✖   type may not be empty [type-empty]"; the summary has no [rule]
        if not (text.startswith("✖") and text.endswith("]") and "[" in text):
            continue
        cut = text.rindex("[")
        found.append((text[cut + 1 : -1], text[1:cut].strip()))
    return found


def problems(output):
    """commitlint's findings, in plain words where known (RULES)."""
    return list(dict.fromkeys(RULES.get(rule, text) for rule, text in findings(output)))


def only_new_scope(title, output, config_text):
    """True when commitlint's one problem is the scope and the pull request's own
    commitlint.config.mjs adds it. That file is read as text, never run (a fork's
    config could import code); main's config is what commitlint used."""
    m = changelog.TITLE.match(title.strip())
    if m is None or not m["scope"]:
        return False
    rules = [rule for rule, _ in findings(output)]
    return rules == ["scope-enum"] and m["scope"] in scopes_in(config_text)


def quote(title):
    return f"> {title.strip() or '(empty)'}"


def spelling(words):
    shown = ", ".join(f"`{w}`" for w in words)
    return (
        f"Unknown to the spell checker: {shown}. Fix the spelling, or add the word to "
        "`cspell.config.yaml` (sorted) in this pull request: the title becomes a line "
        "in CHANGELOG.md, which is spell-checked."
    )


def not_listed(words, config_text):
    """The words that a pull request's own cspell.config.yaml doesn't list: it may add
    the ones its title uses. Only its word list is read, as text: a fork's config is
    never given to CSpell (a config can import code)."""
    listed = {
        w.lower() for w in re.findall(r"""^\s+-\s+['"]?([^\s'"#]+)['"]?\s*$""", config_text, re.M)
    }
    return [w for w in words if w.lower() not in listed]


def failing(title, output, repo, words=(), lint_ok=False):
    """The comment for a title that fails commitlint (output), the spell check
    (words), or both."""
    if lint_ok:
        return "\n".join([
            MARKER,
            "### ❌ The title has a word the spell checker doesn't know",
            "",
            quote(title),
            "",
            f"- {spelling(words)}",
            "",
            "**Edit the title at the top of this pull request** (or push the word); this "
            "comment updates itself.",
        ])  # fmt: skip
    found = problems(output) or ["the title doesn't match `type(scope): what changed`"]
    if words:
        found.append(spelling(words))
    rows = "\n".join(f"| `{t}` | {section} |" for t, section in EXAMPLES)
    names = ", ".join(f"`{s}`" for s in scopes())
    return "\n".join([
        MARKER,
        "### ❌ The title doesn't follow Conventional Commits",
        "",
        quote(title),
        "",
        *[f"- {p}" for p in found],
        "",
        "Pull requests are squash merged: the title becomes the commit on `main` and its "
        "line in the release notes. Write it as `type(scope): what changed`, lowercase, "
        "without a full stop, so it reads well for users:",
        "",
        "| Title | In the release notes |",
        "| --- | --- |",
        rows,
        "",
        f"Scopes are optional: {names}." if names else "",
        f"More in [CONTRIBUTING.md](https://github.com/{repo}/{GUIDE}).",
        "",
        "**Edit the title at the top of this pull request**; this comment updates itself.",
    ])  # fmt: skip


def passing(title, pr, author, bot, repo):
    c = changelog.parse({"sha": "", "subject": f"{title} (#{pr})", "body": ""})
    line = changelog.line(c, {"author": author, "bot": bot}, f"https://github.com/{repo}")
    return "\n".join([
        MARKER,
        "### ✅ The title is fine now",
        "",
        f"In the release notes, under **{changelog.section_of(c)}**:",
        "",
        line,
    ])  # fmt: skip


def main():
    p = argparse.ArgumentParser(description="The comment on a pull request's title")
    p.add_argument("state", choices=["ok", "fail", "unknown", "new-scope"])
    p.add_argument("--title", default="")
    p.add_argument("--pr", type=int, default=0)
    p.add_argument("--author", default="")
    p.add_argument("--bot", action="store_true", help="the author is an app")
    p.add_argument("--repo", default=os.environ.get("GITHUB_REPOSITORY", "o/r"))
    p.add_argument("--words", help="a file with the words the spell check didn't know")
    p.add_argument("--lint-ok", action="store_true", help="commitlint passed")
    p.add_argument(
        "--config",
        help="unknown: the pull request's cspell.config.yaml; new-scope: its commitlint.config.mjs",
    )
    a = p.parse_args()
    words = []
    if a.words:
        with open(a.words, encoding="utf-8") as f:
            words = [w for w in f.read().split() if w]
    if isinstance(sys.stdout, io.TextIOWrapper):
        sys.stdout.reconfigure(encoding="utf-8")  # emoji in the comment
    if a.state == "new-scope":  # exit 0: the title is fine with the pull request's scopes
        with open(a.config, encoding="utf-8") as f:
            lint = sys.stdin.buffer.read().decode("utf-8", "replace")
            sys.exit(0 if only_new_scope(a.title, lint, f.read()) else 1)
    if a.state == "unknown":  # the words its own word list doesn't have
        with open(a.config, encoding="utf-8") as f:
            for word in not_listed(words, f.read()):
                print(word)  # nothing at all for none: the workflow tests for an empty file
    elif a.state == "fail":
        lint = sys.stdin.buffer.read().decode("utf-8", "replace")
        print(failing(a.title, lint, a.repo, words, a.lint_ok))
    else:
        print(passing(a.title, a.pr, a.author, a.bot, a.repo))


if __name__ == "__main__":
    main()
