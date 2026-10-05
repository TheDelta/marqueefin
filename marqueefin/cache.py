"""What's remembered between runs."""

import json
import os
import threading
import time
import zlib

CACHE_VERSION = 1  # bump when what's stored changes; old files are then ignored


class JsonCache:
    """{key: [saved, value]} in one JSON file in the cache dir.

    An entry lives between half and all of max_days, by a hash of its key, so one run's
    entries don't expire together. Entries a run didn't use are dropped on save; refresh
    ignores what's stored."""

    def __init__(self, cache_dir, name, max_days, refresh=False):
        self.path = os.path.join(cache_dir, name) if cache_dir else None
        self.max_age = max_days * 86400
        self.data, self.used, self.hits = {}, {}, 0
        self.lock = threading.Lock()
        if self.path and not refresh and os.path.exists(self.path):
            try:
                with open(self.path, encoding="utf-8") as f:
                    stored = json.load(f)
                if stored.get("version") == CACHE_VERSION:
                    self.data = stored.get("entries", {})
            except (OSError, ValueError):
                pass  # unreadable: start over

    def get(self, key, default=None):
        entry = self.data.get(key)
        if not entry:
            return default
        spread = 0.5 + (zlib.crc32(key.encode()) % 1000) / 2000  # 0.5 .. 1.0
        if time.time() - entry[0] > self.max_age * spread:
            return default
        with self.lock:
            self.used[key] = entry
            self.hits += 1
        return entry[1]

    def put(self, key, value):
        with self.lock:
            self.used[key] = [time.time(), value]

    def save(self):
        if not self.path:
            return
        os.makedirs(os.path.dirname(self.path) or ".", exist_ok=True)
        tmp = self.path + ".part"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(
                {"version": CACHE_VERSION, "entries": self.used},
                f,
                separators=(",", ":"),
            )
        os.replace(tmp, self.path)


MISS = object()  # "not in the cache", as opposed to a cached None
