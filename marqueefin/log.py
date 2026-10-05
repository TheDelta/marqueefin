"""The log: lines with icons, progress, problem lists."""

import sys
import time


def log_problems(problems, what, limit=20):
    """'3 without details from Seerr:' followed by one line per problem."""
    if not problems:
        return
    log(f"   {len(problems)} {what}:", "⚠️")
    for p in problems[:limit]:
        log(f"      {p}")
    if len(problems) > limit:
        log(f"      ... and {len(problems) - limit} more")


def log(msg, icon=""):
    """A line on stderr, with the emoji after the indent where stderr is UTF-8."""
    if icon and utf8_log():
        text = msg.lstrip(" ")
        msg = f"{msg[: len(msg) - len(text)]}{icon} {text}"
    print(msg, file=sys.stderr, flush=True)


def utf8_log():
    encoding = getattr(sys.stderr, "encoding", None) or ""
    return encoding.lower().replace("-", "").replace("_", "") == "utf8"


def progress_logger(label, every=10):
    """A progress(done, total) callback that logs every few seconds and at the end;
    quick steps only log their final line."""
    last = time.monotonic()

    def report(done, total):
        nonlocal last
        now = time.monotonic()
        if done >= total or now - last >= every:
            last = now
            log(f"   {label} {done:,}/{total:,} ({done * 100 // max(total, 1)}%)")

    return report


def fmt_duration(seconds):
    m, s = divmod(round(seconds), 60)
    return f"{m}m {s:02d}s" if m else f"{s}s"
