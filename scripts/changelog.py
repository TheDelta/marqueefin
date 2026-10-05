"""CHANGELOG.md lines from the squash commits on main, for release.py.

    feat(page): theme switch (#12)
    -> 🚀 Features: - **page:** Theme switch by [@someone](…) in [#12](…) (fixes [#9](…))

A pull request with several changes lists the others in its squash description,
one per line ("* fix(seerr): requests without a date"): each becomes a line of
its own.

Authors and closed issues come from GitHub's API (with a token). A pull request that
[Unreleased] already mentions is left alone, so hand-written lines win.
"""

import json
import os
import re
import subprocess
import sys
import urllib.request

BREAKING = "⚠️ Breaking changes"
NOTES = "📝 Notes"
FEATURES = "🚀 Features"
FIXES = "🐛 Fixes"
PERFORMANCE = "⚡ Performance"
TRANSLATIONS = "🌐 Translations"
SECURITY = "🔒 Security"
DOCS = "📚 Documentation"
DEPENDENCIES = "📦 Dependencies"
MAINTENANCE = "🧰 Maintenance"
# The order of a release's sections; hand-written sections with other names go
# after the notes
FIRST = [BREAKING, NOTES]
LAST = [FEATURES, FIXES, PERFORMANCE, TRANSLATIONS, SECURITY, DOCS, DEPENDENCIES,
        MAINTENANCE]  # fmt: skip
TYPES = {"feat": FEATURES, "fix": FIXES, "revert": FIXES, "perf": PERFORMANCE,
         "docs": DOCS}  # fmt: skip
# Scopes the section already says
QUIET_SCOPES = {"deps", "deps-dev", "i18n", "security"}

# Stays at the top of [Unreleased]; not part of a release's notes
TEMPLATE = """<!--
  Prepare release adds a line here for every pull request merged since the last
  release, from its title (and from "* fix: …" lines in its squash description).
  Edit anything: a line that mentions a pull request (#12) replaces the ones that
  would be generated for it.

  - Highlights or an intro: a paragraph right here, above the first heading.
  - Breaking changes: a "⚠️ Breaking changes" section (feat!: and fix!: pull
    requests land there by themselves). Say what users have to do, e.g. which
    setting was renamed to what.
  - Upgrade notes, known issues: a "📝 Notes" section.
  - Sections: 🚀 Features, 🐛 Fixes, ⚡ Performance, 🌐 Translations,
    🔒 Security, 📚 Documentation, 📦 Dependencies, 🧰 Maintenance.
-->"""

TITLE = re.compile(r"(?P<type>[a-z]+)(?:\((?P<scope>[^)]+)\))?(?P<bang>!)?: (?P<text>.+)")
PR_SUFFIX = re.compile(r" \(#(\d+)\)$")
LIST_MARKER = re.compile(r"^[*+-] +")
# A line of a squash commit's description that is a change of its own; only the
# Conventional Commits types, so prose bullets ("- Note: …") don't count
BODY_LINE = re.compile(
    r"^[*-] (?P<line>(?:feat|fix|perf|docs|refactor|style|test|build|ci|chore|revert)"
    r"(?:\([^)\n]+\))?!?: [^\n]+)$",
    re.M,
)
# npm packages like @floating-ui/dom would read as @mentions on GitHub
PACKAGE = re.compile(r"(?<![\w`])(@[\w.-]+/[\w.-]+)")
COMMENT = re.compile(r"<!--.*?-->", re.S)
# Lines that start a Markdown block of their own (not the rest of a paragraph)
BLOCK_START = re.compile(r"(?:[-*+] |\d+[.)] |#|>|\||```|<)")


def git(root, *args):
    return subprocess.run(  # noqa: S603  # fixed arguments, no shell
        ["git", "-C", root, *args],  # noqa: S607  # git from PATH
        capture_output=True, text=True, encoding="utf-8", check=True,
    ).stdout  # fmt: skip


def commits(root):
    """The commits since the last release tag, oldest first; [] outside a git
    repository. Before the first release: all of them but the repository's first
    commit, which imports the project rather than changing it."""
    if not os.path.exists(os.path.join(root, ".git")):
        return []
    try:
        base = git(root, "describe", "--tags", "--abbrev=0", "--match", "v[0-9]*")
        span = f"{base.strip()}..HEAD"
    except subprocess.CalledProcessError:  # no release yet
        span = "HEAD"
    out = git(root, "log", "--no-merges", "--reverse",
              "--format=%H%x1f%P%x1f%s%x1f%b%x1e", span)  # fmt: skip
    found = []
    for record in out.split("\x1e"):
        parts = record.strip("\n").split("\x1f")
        if len(parts) == 4 and parts[1]:  # no parents: the first commit
            found.append({"sha": parts[0], "subject": parts[2], "body": parts[3]})
    return found


def parse(commit):
    """Type, scope, text, pull request number and breaking flag of a commit.
    A title that isn't a Conventional Commit keeps its text (type None)."""
    # A squash merge can take a description line as its title: "* feat(page): …"
    subject = LIST_MARKER.sub("", commit["subject"].strip())
    pr = PR_SUFFIX.search(subject)
    if pr:
        subject = subject[: pr.start()]
    m = TITLE.fullmatch(subject)
    kind, scope, text = (m["type"], m["scope"], m["text"]) if m else (None, None, subject)
    breaking = bool(m and m["bang"]) or bool(
        re.search(r"^BREAKING[ -]CHANGE:", commit["body"], re.M)
    )
    return {"type": kind, "scope": scope, "text": text.strip(),
            "pr": int(pr.group(1)) if pr else None, "breaking": breaking,
            "sha": commit["sha"]}  # fmt: skip


def title_problems(commit):
    """Why a commit's title didn't make a proper release-notes line; [] when it did."""
    found = []
    if LIST_MARKER.match(commit["subject"]):
        found.append("starts with a list marker: the squash merge took a description line")
    c = parse(commit)
    if c["type"] is None:
        found.append("not a Conventional Commit, so it's listed under Maintenance as is")
    if c["pr"] is None:
        found.append("no pull request number: linked to the commit, without an author")
    return found


def titles_warning(found, url):
    """A warning box for the release pull request listing the commits (since the last
    release) whose titles need a look; '' when every title is fine."""
    rows = []
    for commit in found:
        problems = title_problems(commit)
        if not problems or is_release(parse(commit)):
            continue
        subject = commit["subject"].replace("`", "'")
        sha = commit["sha"]
        rows.append(f"> - [`{sha[:7]}`]({url}/commit/{sha}) `{subject}`: {'; '.join(problems)}.")
    if not rows:
        return ""
    return "\n".join([
        "> [!WARNING]",
        "> **These commit titles didn't make proper release-notes lines:**",
        ">",
        *rows,
        ">",
        "> Check their lines in `CHANGELOG.md` on this branch (section and wording come from",
        "> the title). When squash merging, keep the suggested title `type(scope): … (#12)`.",
        "",
    ])  # fmt: skip


def changes(commit):
    """The title's change, plus each description line that is a Conventional Commit
    itself ("* fix(seerr): …", as GitHub lists the branch's commits). Skips the line
    repeating the title's type and scope, and duplicates."""
    title = parse(commit)
    found, texts = [title], {title["text"].lower()}
    for m in BODY_LINE.finditer(commit["body"]):
        c = parse({"sha": commit["sha"], "subject": m["line"], "body": ""})
        same_kind = (c["type"], c["scope"]) == (title["type"], title["scope"])
        if same_kind or c["text"].lower() in texts:
            continue
        texts.add(c["text"].lower())
        found.append({**c, "pr": title["pr"]})
    return found


def section_of(c):
    if c["breaking"]:
        return BREAKING
    if c["scope"] in ("deps", "deps-dev"):
        return DEPENDENCIES
    if c["scope"] == "security":
        return SECURITY
    if c["scope"] == "ci":  # users don't see it, even when it's a fix
        return MAINTENANCE
    if c["scope"] == "i18n" and c["type"] in ("feat", "fix"):
        return TRANSLATIONS
    return TYPES.get(c["type"], MAINTENANCE)


def is_release(c):
    return c["type"] == "chore" and c["scope"] == "release"


def person(info):
    login = info.get("author")
    if not login:
        return ""
    profile = f"apps/{login}" if info.get("bot") else login
    return f" by [@{login}](https://github.com/{profile})"


def line(c, info, url):
    """One changelog line, with explicit links: CHANGELOG.md doesn't link #12 or
    @someone by itself (the release page does, see for_github)."""
    text = PACKAGE.sub(r"`\1`", c["text"][:1].upper() + c["text"][1:])
    scope = c["scope"]
    prefix = f"**{scope}:** " if scope and scope not in QUIET_SCOPES else ""
    if not c["pr"]:
        return f"- {prefix}{text} ([`{c['sha'][:7]}`]({url}/commit/{c['sha']}))"
    issues = ", ".join(f"[#{n}]({url}/issues/{n})" for n in info.get("issues", []))
    fixes = f" (fixes {issues})" if issues else ""
    return f"- {prefix}{text}{person(info)} in [#{c['pr']}]({url}/pull/{c['pr']}){fixes}"


def mentioned(c, text):
    if c["pr"]:
        return re.search(rf"(?:#|/pull/){c['pr']}\b", text) is not None
    return c["sha"][:7] in text


def split(body):
    """(preamble, [(heading, content)]) of a version's section."""
    parts = re.split(r"^### (.+)$", body, flags=re.M)
    return parts[0].strip(), [
        (h.strip(), c.strip()) for h, c in zip(parts[1::2], parts[2::2], strict=True)
    ]


def join(preamble, sections):
    known = FIRST + LAST
    ordered = [s for h in FIRST for s in sections if s[0] == h]
    ordered += [s for s in sections if s[0] not in known]
    ordered += [s for h in LAST for s in sections if s[0] == h]
    blocks = [preamble] if preamble else []
    blocks += [f"### {h}\n\n{c}" for h, c in ordered if c]
    return "\n\n".join(blocks)


def add(body, entries):
    """[Unreleased]'s body with the (section, line) entries added at the end of
    their sections."""
    preamble, sections = split(body)
    content = dict(sections)
    for heading, text in entries:
        content[heading] = f"{content[heading]}\n{text}".strip() if heading in content else text
    names = [h for h, _ in sections] + [h for h, _ in entries if h not in dict(sections)]
    return join(preamble, [(h, content[h]) for h in dict.fromkeys(names)])


def lines(found, body, url, lookup):
    """(section, line) for every change worth listing that the body doesn't
    mention yet (a pull request with several changes: one line each)."""
    visible = without_comments(body)  # the hints' examples don't count
    todo = [
        c
        for commit in found
        if not is_release(parse(commit))
        for c in changes(commit)
        if not mentioned(c, visible)
    ]
    numbers = list(dict.fromkeys(c["pr"] for c in todo if c["pr"]))
    details = lookup(numbers) if numbers else {}
    return [(section_of(c), line(c, details.get(c["pr"], {}), url)) for c in todo]


def github_lookup(repo, token):
    """A lookup(numbers) -> {number: {author, bot, issues}} through GitHub's
    GraphQL API, or one that returns {} without a token."""

    def lookup(numbers):
        if not (token and numbers and re.fullmatch(r"[\w.-]+/[\w.-]+", repo)):
            return {}
        owner, name = repo.split("/")
        fields = " ".join(
            f"p{n}: pullRequest(number: {n}) {{ author {{ __typename login }} "
            f"closingIssuesReferences(first: 10) {{ nodes {{ number }} }} }}"
            for n in numbers
        )
        query = f'{{ repository(owner: "{owner}", name: "{name}") {{ {fields} }} }}'
        req = urllib.request.Request(
            "https://api.github.com/graphql",
            data=json.dumps({"query": query}).encode(),
            headers={
                "Authorization": f"bearer {token}",
                "User-Agent": "marqueefin-release",
            },
        )
        try:
            with urllib.request.urlopen(req, timeout=30) as r:
                repository = (json.load(r).get("data") or {}).get("repository") or {}
        except (OSError, ValueError) as e:
            print(f"No pull request details from GitHub: {e}", file=sys.stderr)
            return {}
        out = {}
        for n in numbers:
            pr = repository.get(f"p{n}") or {}
            author = pr.get("author") or {}
            closes = (pr.get("closingIssuesReferences") or {}).get("nodes", [])
            out[n] = {
                "author": author.get("login"),
                "bot": author.get("__typename") == "Bot",
                "issues": [i["number"] for i in closes],
            }
        return out

    return lookup


def without_comments(text):
    return COMMENT.sub("", text).strip()


def unwrap(text):
    """Hand-wrapped lines joined again: release pages and pull request descriptions show
    every line break. Lists, headings, quotes, tables and code keep their lines."""
    out, in_code = [], False
    for line in text.split("\n"):
        stripped = line.strip()
        if stripped.startswith("```"):
            in_code = not in_code
        elif (
            not in_code
            and stripped
            and out
            and out[-1].strip()
            and not BLOCK_START.match(stripped)
            and not out[-1].lstrip().startswith(("#", "|", "```"))
            and not out[-1].endswith("  ")  # a hard break written on purpose
        ):
            out[-1] = f"{out[-1].rstrip()} {stripped}"
            continue
        out.append(line)
    return "\n".join(out)


def for_github(body):
    """The notes as the release page shows them: @someone and #12 instead of
    their links, so GitHub shows hovercards and the contributors' avatars."""
    body = re.sub(r"\[@([\w-]+)\]\(https://github\.com/\1\)", r"@\1", body)
    return re.sub(
        r"\[#(\d+)\]\(https://github\.com/[\w.-]+/[\w.-]+/(?:pull|issues)/\1\)",
        r"#\1",
        body,
    )
