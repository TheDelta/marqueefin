#!/usr/bin/env python3
"""The supported Python versions: python-versions.json and the places that name them.

    python scripts/python_versions.py sync      # rewrite them from python-versions.json
    python scripts/python_versions.py update    # follow Python's release cycle (online)

Supported is what https://devguide.python.org/versions/ lists as "bugfix" or
"security": the oldest of them is the minimum (Ruff, Pyright, the docs), and CI tests
the oldest and the newest (ci.yaml reads python-versions.json). `update` prints what
changed, the title of the monthly workflow's pull request (python-versions.yaml), or
nothing.
"""

import argparse
import json
import os
import re
import sys
import urllib.request

CYCLE_URL = "https://peps.python.org/api/release-cycle.json"  # the devguide's table
SOURCE = "python-versions.json"
SUPPORTED = ("bugfix", "security")  # not "feature" / "prerelease" / "end-of-life"
ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")


def key(version):
    """'3.9' < '3.10' as numbers."""
    return tuple(int(n) for n in version.split("."))


def supported(cycle):
    """(oldest, newest) of the versions with bug fixes or security fixes."""
    versions = sorted((v for v, info in cycle.items() if info.get("status") in SUPPORTED), key=key)
    if not versions:
        sys.exit(f"No supported Python version in {CYCLE_URL}")
    return versions[0], versions[-1]


def places(oldest, newest):
    """{file: [(pattern, text)]}: each pattern matches once and becomes the text."""
    major, low, high = key(oldest)[0], key(oldest)[1], key(newest)[1]
    every = ", ".join(f"{major}.{minor}" for minor in range(low, high + 1))
    return {
        "ruff.toml": [(r'target-version = "py\d+"', f'target-version = "py{oldest.replace(".", "")}"')],
        "pyrightconfig.json": [(r'"pythonVersion": "\d+\.\d+"', f'"pythonVersion": "{oldest}"')],
        "sonar-project.properties": [(r"sonar\.python\.version=.*", f"sonar.python.version={every}")],
        "README.md": [
            (r'alt="Python \d+\.\d+\+"', f'alt="Python {oldest}+"'),
            (r"python-\d+\.\d+%2B", f"python-{oldest}%2B"),
            (r"\*\*Python \d+\.\d+\+\*\*", f"**Python {oldest}+**"),
        ],
        "CONTRIBUTING.md": [(r"You need Python \d+\.\d+ or newer", f"You need Python {oldest} or newer")],
        "AGENTS.md": [
            (r"\(\d+\.\d+\+, the oldest version", f"({oldest}+, the oldest version"),
            (r"CI tests \d+\.\d+ and \d+\.\d+", f"CI tests {oldest} and {newest}"),
        ],
    }  # fmt: skip


def read(root, name):
    with open(os.path.join(root, name), encoding="utf-8") as f:
        return f.read()


def write(root, name, text):
    with open(os.path.join(root, name), "w", encoding="utf-8", newline="\n") as f:
        f.write(text)


def source(root):
    data = json.loads(read(root, SOURCE))
    return data["oldest"], data["newest"]


def sync(root, save=True):
    """The files whose versions differ from python-versions.json (rewritten if save)."""
    changed = []
    for name, replacements in places(*source(root)).items():
        old = new = read(root, name)
        for pattern, text in replacements:
            new, count = re.subn(pattern, text, new)  # the texts have no backslashes
            if count != 1:
                sys.exit(f"{name}: {pattern!r} matches {count} times, not once (see places())")
        if new != old:
            changed.append(name)
            if save:
                write(root, name, new)
    return changed


def update(root, cycle):
    """python-versions.json (and the places) from the release cycle; what changed."""
    old_oldest, old_newest = source(root)
    oldest, newest = supported(cycle)
    news = []
    if key(oldest) > key(old_oldest):
        news.append(f"require Python {oldest} or newer ({old_oldest} is end of life)")
    elif oldest != old_oldest:
        news.append(f"support Python {oldest} or newer")
    if newest != old_newest:
        news.append(f"test Python {newest}")
    if news:
        data = {"oldest": oldest, "newest": newest}
        write(root, SOURCE, json.dumps(data, indent=2) + "\n")
        sync(root)
    return " and ".join(news)


def fetch_cycle():
    req = urllib.request.Request(CYCLE_URL, headers={"User-Agent": "marqueefin-python-versions"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.load(r)


def main():
    p = argparse.ArgumentParser(description="The supported Python versions")
    p.add_argument("--root", default=ROOT)
    sub = p.add_subparsers(dest="cmd", required=True)
    sub.add_parser("sync", help="rewrite the places from python-versions.json")
    sub.add_parser("update", help="follow Python's release cycle; print what changed")
    a = p.parse_args()
    if a.cmd == "sync":
        for name in sync(a.root):
            print(f"updated {name}")
    else:
        print(update(a.root, fetch_cycle()))


if __name__ == "__main__":
    main()
