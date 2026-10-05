"""The page: template, styles, scripts, fonts and its security policy."""

import base64
import hashlib
import html
import json
import os
import re
import urllib.parse

from . import PROJECT, PROJECT_URL, ROOT, __version__
from .log import log
from .seal import seal

SRC_DIR = os.path.join(ROOT, "src")
# The page's script and styles, bundled from src/js and src/css by `npm run build`
BUILD_DIR = os.path.join(ROOT, "build")
# Browser-side dependencies, installed with `npm ci` (versions in package-lock.json)
NODE_MODULES = os.path.join(ROOT, "node_modules")
# Variable fonts: one file per character set covers every weight
FONTS = (
    "@fontsource-variable/big-shoulders-display",
    "@fontsource-variable/instrument-sans",
)
FONT_SUBSETS = ("latin", "latin-ext")
FLOATING_UI = (
    "@floating-ui/core",
    "@floating-ui/dom",
)  # dom needs core; utils is bundled


def read_translations():
    """{language: {key: text}} from src/i18n/*.json: the page's texts in every
    language it ships with (the viewer's browser picks one, see src/js/lib.js)."""
    folder = os.path.join(SRC_DIR, "i18n")
    out = {}
    for name in sorted(os.listdir(folder)):
        if name.endswith(".json"):
            with open(os.path.join(folder, name), encoding="utf-8") as f:
                out[name[:-5]] = json.load(f)
    return out


def read_src(name):
    with open(os.path.join(SRC_DIR, name), encoding="utf-8") as f:
        return f.read()


def read_build(name):
    try:
        with open(os.path.join(BUILD_DIR, name), encoding="utf-8") as f:
            return f.read()
    except FileNotFoundError:
        raise SystemExit(
            f"Error: build/{name} is missing: run `npm ci && npm run build` next to the script."
        ) from None


def vendor_js():
    """Floating UI's UMD builds with their MIT license, which copies must carry; ''
    without `npm ci` (native tooltips then)."""
    try:
        parts = [floating_ui_part(pkg) for pkg in FLOATING_UI]
    except (OSError, ValueError, KeyError):
        log(
            "Floating UI not found: run `npm ci` next to the script. "
            "The page falls back to the browser's own tooltips.",
            "⚠️",
        )
        return ""
    return "\n".join(parts)


def floating_ui_part(pkg):
    """One package's UMD build, headed by its name, version and license."""
    folder = os.path.join(NODE_MODULES, *pkg.split("/"))
    with open(os.path.join(folder, "package.json"), encoding="utf-8") as f:
        version = json.load(f)["version"]
    with open(os.path.join(folder, "LICENSE"), encoding="utf-8") as f:
        license_text = f.read().strip()
    name = pkg.split("/")[1]
    with open(
        os.path.join(folder, "dist", f"floating-ui.{name}.umd.min.js"), encoding="utf-8"
    ) as f:
        code = f.read().strip()
    return f"/*! {pkg} {version} | https://floating-ui.com\n{license_text}\n*/\n{code}"


def fonts_css():
    """The two fonts (OFL) inlined as @font-face, each headed by its license. No font
    service: Google Fonts would see every viewer. Latin and Latin Extended only; ''
    without `npm ci` (system fonts then)."""
    try:
        return "\n".join(font_part(pkg) for pkg in FONTS)
    except (OSError, ValueError, KeyError):
        log(
            "Fonts not found: run `npm ci` next to the script. The page uses system fonts.",
            "⚠️",
        )
        return ""


def font_part(pkg):
    """One font package's @font-face rules for FONT_SUBSETS, files as data URIs."""
    folder = os.path.join(NODE_MODULES, *pkg.split("/"))
    with open(os.path.join(folder, "package.json"), encoding="utf-8") as f:
        version = json.load(f)["version"]
    with open(os.path.join(folder, "LICENSE"), encoding="utf-8") as f:
        license_text = f.read().strip().replace("*/", "* /")
    with open(os.path.join(folder, "wght.css"), encoding="utf-8") as f:
        css = f.read()

    def inline(m):
        with open(os.path.join(folder, "files", m.group(1)), "rb") as f:
            data = base64.b64encode(f.read()).decode()
        return f"url(data:font/woff2;base64,{data})"

    rules = [
        re.sub(r"url\(\./files/([\w.-]+\.woff2)\)", inline, rule)
        for name, rule in re.findall(r"/\* (\S+) \*/\s*(@font-face\s*\{[^}]*\})", css)
        if any(name.endswith(f"-{s}-wght-normal") for s in FONT_SUBSETS)
    ]
    if not rules:
        raise ValueError(f"no @font-face rules in {pkg}")
    return f"/*! {pkg} {version} | OFL-1.1\n{license_text}\n*/\n" + "\n".join(rules)


def favicon_uri():
    """src/favicon.svg (the marquee) as a data URI, so the page stays one file."""
    svg = re.sub(r"<!--.*?-->", "", read_src("favicon.svg"), flags=re.DOTALL)
    svg = " ".join(svg.split()).replace("> <", "><")
    return "data:image/svg+xml," + urllib.parse.quote(svg)


def credit_html():
    """The footer's "Marqueefin 1.0.0 · GitHub" (the link only with PROJECT_URL)."""
    credit = f"{PROJECT} {html.escape(__version__)}"
    if PROJECT_URL:
        label = "GitHub" if "github.com" in PROJECT_URL else "Source code"
        url = html.escape(PROJECT_URL, quote=True)
        credit += f' <span aria-hidden="true">&middot;</span> <a href="{url}" target="_blank" rel="noopener">{label}</a>'
    return credit


def script_json(value):
    """JSON that's safe inside <script>."""
    return json.dumps(value, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")


def render_html(title, records, generated, flags=None, requests=None, settings=None, protect=None):
    """Fill src/template.html, inlining the fonts and the bundled styles and script
    (build/), so the result is a single self-contained file. protect: (passphrase,
    salt) seals the library's data (seal.py); the page then asks for the passphrase."""
    parts = []
    for kind, one, many in (
        ("movie", "movie", "movies"),
        ("series", "series", "series"),
        ("collection", "collection", "collections"),
    ):
        n = sum(1 for r in records if r["type"] == kind)
        if n:
            parts.append(f"{n:,} {one if n == 1 else many}")
    if len(parts) > 1:
        parts = [", ".join(parts[:-1]), parts[-1]]
    summary = " and ".join(parts) or "Nothing here yet"
    generated = generated.astimezone()  # the page shows it relative ("2 hours ago")

    data = {"data": records, "requests": requests or [], "flags": flags or {}}
    sealed = None
    if protect:  # the data only inside the seal; the header doesn't say what's there
        passphrase, salt = protect
        sealed = seal(json.dumps(data, ensure_ascii=False, separators=(",", ":")), passphrase, salt)
        data = {"data": [], "requests": [], "flags": {}}
        summary = "Protected with a passphrase"

    values = {
        "STYLE": fonts_css() + "\n" + read_build("page.css"),
        "SCRIPT": read_build("page.js"),
        "VENDOR": vendor_js(),
        "TITLE": html.escape(title),
        "SUMMARY": html.escape(summary),
        "DESCRIPTION": html.escape(f"{summary}. Updated {generated.day} {generated:%b %Y}."),
        "FAVICON": favicon_uri(),
        "GENERATED": generated.isoformat(timespec="seconds"),
        "VERSION": __version__,
        "CREDIT": credit_html(),
        "UPDATED": f"{generated.day} {generated:%b %Y}, {generated:%H:%M}",  # without JS
        "DATA": script_json(data["data"]),
        "FLAGS": script_json(data["flags"]),
        "SEALED": json.dumps(sealed),
        "LOCKED": "locked" if sealed else "",
        "SETTINGS": json.dumps({"titleLang": "", "mainLangs": ["en"], **(settings or {})}),
        "I18N": json.dumps(read_translations(), ensure_ascii=False).replace("</", "<\\/"),
        "REQUESTS": script_json(data["requests"]),
    }
    # Single pass, so placeholder-looking text inside titles or data is left alone
    page = re.sub(
        r"__(STYLE|SCRIPT|VENDOR|TITLE|SUMMARY|DESCRIPTION|FAVICON|GENERATED|UPDATED|VERSION|CREDIT|DATA|FLAGS|REQUESTS|SETTINGS|I18N|SEALED|LOCKED)__",
        lambda m: values[m.group(1)],
        read_src("template.html"),
    )
    # Last, as it hashes the finished page. Its meta tag comes before <title>, so the
    # first match is the tag, whatever the library's text holds.
    return page.replace("__CSP__", content_security_policy(page), 1)


def content_security_policy(page):
    """Hashes of the inline scripts and styles; images and fonts only from data: (and
    the posters folder). frame-ancestors only works as a header."""

    def hashes(tag):
        found = re.findall(rf'^[ \t]*<{tag}(?: type="module")?>(.*?)</{tag}>', page, re.M | re.S)
        return " ".join(
            "'sha256-" + base64.b64encode(hashlib.sha256(s.encode()).digest()).decode() + "'"
            for s in found
        )

    return "; ".join([
        "default-src 'none'",
        f"script-src {hashes('script')}",
        f"style-src {hashes('style')}",
        "img-src 'self' data:",
        "font-src data:",
        "base-uri 'none'",
        "form-action 'none'",
    ])  # fmt: skip
