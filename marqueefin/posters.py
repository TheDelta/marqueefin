"""Posters: fetched, cached, embedded or written next to the page."""

import base64
import os


def sniff_mime(data):
    if data[:3] == b"\xff\xd8\xff":
        return "image/jpeg", "jpg"
    if data[:8] == b"\x89PNG\r\n\x1a\n":
        return "image/png", "png"
    if data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "image/webp", "webp"
    if data[:3] == b"GIF":
        return "image/gif", "gif"
    return "image/jpeg", "jpg"


def get_poster(jf, item, width, quality, cache_dir, fmt="webp"):
    """A poster scaled to width: WebP (a quarter smaller than JPEG) or JPEG."""
    tag = (item.get("ImageTags") or {}).get("Primary")
    if not tag:
        return None
    cache_file = None
    if cache_dir:
        suffix = "_webp" if fmt == "webp" else ""  # JPEG keeps its older cache names
        cache_file = os.path.join(cache_dir, f"{item['Id']}_{tag}_{width}_{quality}{suffix}.img")
        if os.path.exists(cache_file):
            with open(cache_file, "rb") as f:
                return f.read()
    params = {"maxWidth": width, "quality": quality, "tag": tag}
    if fmt == "webp":
        params["format"] = "Webp"
    data = jf.request(f"/Items/{item['Id']}/Images/Primary", params)
    if cache_file:
        with open(cache_file, "wb") as f:
            f.write(data)
    return data


def store_poster(rec, data, folder):
    """The poster on its record: embedded as a data URI, or saved into the posters
    folder (--posters folder)."""
    mime, ext = sniff_mime(data)
    if not folder:
        rec["poster"] = f"data:{mime};base64,{base64.b64encode(data).decode()}"
        return
    fname = f"{rec['id']}.{ext}"
    with open(os.path.join(folder, fname), "wb") as f:
        f.write(data)
    rec["poster"] = f"{os.path.basename(folder)}/{fname}"
