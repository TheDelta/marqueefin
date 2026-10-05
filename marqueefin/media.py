"""Media info: resolution, HDR, codecs, audio, languages, size, flags."""

import base64
import os
import urllib.request
from collections import Counter

from .log import log

RES_RANK = {"8K": 5, "4K": 4, "1080p": 3, "720p": 2, "SD": 1}
VIDEO_CODECS = {"hevc": "HEVC", "h265": "HEVC", "h264": "H.264", "avc": "H.264",
                "av1": "AV1", "vp9": "VP9", "mpeg2video": "MPEG-2", "vc1": "VC-1",
                "mpeg4": "MPEG-4"}  # fmt: skip


# Jellyfin's VideoRangeType -> what to show. Dolby Vision profiles with an HDR10 /
# HLG base layer also play as that on TVs without Dolby Vision, so show both.
DV, HDR10P = "Dolby Vision", "HDR10+"
HDR_TYPES = {"DOVI": [DV], "DOVIWithHDR10": [DV, "HDR10"], "DOVIWithEL": [DV, "HDR10"],
             "DOVIWithELHDR10Plus": [DV, HDR10P], "DOVIWithHDR10Plus": [DV, HDR10P],
             "DOVIWithHLG": [DV, "HLG"], "DOVIWithSDR": [DV], "DOVIInvalid": [DV],
             "HDR10": ["HDR10"], "HDR10Plus": [HDR10P], "HLG": ["HLG"]}  # fmt: skip


# ISO 639-2 (as Jellyfin reports it) -> 2-letter code the page turns into a name
LANGS = {"ger": "de", "deu": "de", "eng": "en", "fre": "fr", "fra": "fr", "spa": "es",
         "ita": "it", "jpn": "ja", "kor": "ko", "chi": "zh", "zho": "zh", "rus": "ru",
         "por": "pt", "dut": "nl", "nld": "nl", "swe": "sv", "nor": "no", "nob": "nb",
         "dan": "da", "fin": "fi", "pol": "pl", "tur": "tr", "ara": "ar", "hin": "hi",
         "cze": "cs", "ces": "cs", "hun": "hu", "gre": "el", "ell": "el", "heb": "he",
         "tha": "th", "ukr": "uk", "rum": "ro", "ron": "ro", "ind": "id", "vie": "vi",
         "msa": "ms", "may": "ms", "hrv": "hr", "slk": "sk", "slo": "sk", "slv": "sl",
         "bul": "bg", "est": "et", "lit": "lt", "lav": "lv", "tam": "ta", "tel": "te",
         "mal": "ml", "cat": "ca", "eus": "eu", "baq": "eu", "glg": "gl", "isl": "is",
         "ice": "is", "mkd": "mk", "mac": "mk", "srp": "sr", "fil": "fil", "tgl": "tl",
         "ben": "bn", "urd": "ur", "fas": "fa", "per": "fa", "nno": "nn"}  # fmt: skip


# Language -> country flag (flag-icons code). Languages aren't countries, so this is
# the usual convention (English -> UK); languages without a clear flag show their name.
LANG_FLAGS = {"de": "de", "en": "gb", "fr": "fr", "es": "es", "it": "it", "pt": "pt",
              "nl": "nl", "sv": "se", "fi": "fi", "zh": "cn", "pl": "pl", "da": "dk",
              "hu": "hu", "tr": "tr", "ko": "kr", "cs": "cz", "ja": "jp", "el": "gr",
              "ru": "ru", "th": "th", "no": "no", "nb": "no", "nn": "no", "ro": "ro",
              "ar": "sa", "he": "il", "uk": "ua", "sk": "sk", "vi": "vn", "ms": "my",
              "hr": "hr", "sl": "si", "bg": "bg", "et": "ee", "lt": "lt", "lv": "lv",
              "hi": "in", "ta": "in", "te": "in", "ml": "in", "bn": "bd", "ca": "es-ct",
              "eu": "es-pv", "gl": "es-ga", "is": "is", "mk": "mk", "sr": "rs", "id": "id",
              "fil": "ph", "tl": "ph", "ur": "pk", "fa": "ir"}  # fmt: skip
FLAG_URL = "https://cdn.jsdelivr.net/npm/flag-icons@7.2.3/flags/4x3/{}.svg"


def resolution(width, height):
    w, h = width or 0, height or 0
    if w >= 7000 or h >= 4000:
        return "8K"
    if w >= 3200 or h >= 1900:
        return "4K"
    if w >= 1800 or h >= 1000:
        return "1080p"
    if w >= 1200 or h >= 700:
        return "720p"
    return "SD" if w or h else None


# codec -> ((name, rank), (name, rank) when the track carries Atmos). Higher rank = better.
AUDIO_CODECS = {"truehd": (("TrueHD", 7), ("TrueHD Atmos", 10)),
                "eac3": (("Dolby Digital+", 4), ("DD+ Atmos", 8)),
                "ac3": (("Dolby Digital", 3),) * 2, "flac": (("FLAC", 6),) * 2,
                "aac": (("AAC", 2),) * 2, "opus": (("Opus", 2),) * 2,
                "vorbis": (("Vorbis", 2),) * 2, "mp3": (("MP3", 1),) * 2}  # fmt: skip


def dts_kind(profile, text):
    if "dts:x" in text or "dts-x" in text:
        return "DTS:X", 9
    if "ma" in profile.split():
        return "DTS-HD MA", 7
    return ("DTS-HD", 5) if "hd" in profile else ("DTS", 5)


def audio_track(s):
    """(rank, format, channels) for one audio stream, e.g. ((10, 8), 'TrueHD Atmos', '7.1')."""
    codec = (s.get("Codec") or "").lower()
    profile = (s.get("Profile") or "").lower()
    text = profile + " " + (s.get("DisplayTitle") or "").lower()
    if codec == "dts":
        name, rank = dts_kind(profile, text)
    elif codec.startswith("pcm"):
        name, rank = "PCM", 6
    else:
        plain, atmos = AUDIO_CODECS.get(codec, ((codec.upper() or "Audio", 1),) * 2)
        name, rank = atmos if "atmos" in text else plain
    ch = s.get("Channels") or 0
    layout = {8: "7.1", 7: "6.1", 6: "5.1", 2: "2.0", 1: "1.0"}.get(ch, f"{ch}ch" if ch else "")
    return (rank, ch), name, layout


def audio_tracks(streams):
    """Every distinct audio track as [language, channels, format] (+ 1 for a
    commentary), in file order: [['en', '7.1', 'TrueHD Atmos'], ['de', '5.1', 'DTS']]."""
    out = []
    for a in streams:
        _, name, layout = audio_track(a)
        track = [lang(a.get("Language")) or "", layout, name]
        if "comment" in (a.get("Title") or a.get("DisplayTitle") or "").lower():
            track.append(1)
        if track not in out:
            out.append(track)
    return out


def lang(code):
    code = (code or "").lower()
    return None if code in ("", "und", "unk", "mis", "zxx", "mul") else LANGS.get(code, code)


def fetch_flags(langs, cache_dir):
    """{language: SVG data URI} from flag-icons, cached. Not emoji: Windows shows flag
    emoji as letters. A language whose flag fails shows its name."""
    out = {}
    for code in sorted(langs):
        cc = LANG_FLAGS.get(code)
        if not cc:
            continue
        path = os.path.join(cache_dir, f"flag_{cc}.svg") if cache_dir else None
        try:
            if path and os.path.exists(path):
                with open(path, "rb") as f:
                    data = f.read()
            else:
                with urllib.request.urlopen(FLAG_URL.format(cc), timeout=15) as r:
                    data = r.read()
                if path:
                    with open(path, "wb") as f:
                        f.write(data)
        except OSError:  # URLError is an OSError
            continue
        out[code] = "data:image/svg+xml;base64," + base64.b64encode(data).decode()
    return out


def unique(values):
    return list(dict.fromkeys(v for v in values if v))


def video_media(video):
    """res, codec, bits (10 and up) and hdr of a video stream."""
    codec = (video.get("Codec") or "").lower()
    hdr = HDR_TYPES.get(video.get("VideoRangeType") or "")
    bits = video.get("BitDepth") or 0
    return {
        "res": resolution(video.get("Width"), video.get("Height")),
        "codec": VIDEO_CODECS.get(codec, codec.upper()),
        "bits": bits if bits >= 10 else None,
        "hdr": hdr or (["HDR"] if video.get("VideoRange") == "HDR" else None),
    }


def source_media(src):
    streams = src.get("MediaStreams") or []
    video = next((s for s in streams if s.get("Type") == "Video"), None)
    audio = [s for s in streams if s.get("Type") == "Audio"]
    subs = [s for s in streams if s.get("Type") == "Subtitle" and not s.get("IsForced")]
    m = video_media(video) if video else {}
    if audio:
        _, name, layout = max(audio_track(a) for a in audio)
        m["audio"] = f"{name} {layout}".strip()  # the best track, for the badge
    m["tracks"] = audio_tracks(audio)
    m["subLangs"] = unique(lang(s.get("Language")) for s in subs)
    m["size"] = src.get("Size")
    m["bitrate"] = src.get("Bitrate")
    m["container"] = (src.get("Container") or "").split(",")[0].upper()
    return {k: v for k, v in m.items() if v}


def item_media(item) -> dict | None:
    """Media summary of a movie / episode: its best version, plus how many there are."""
    if "_media" in item:  # an episode's, from attach_episode_media
        return item["_media"]
    sources = [s for s in item.get("MediaSources") or [] if s.get("MediaStreams")]
    if not sources:
        return None
    rank = lambda s: (RES_RANK.get(s.get("res"), 0), s.get("size", 0))
    best = max((source_media(s) for s in sources), key=rank)
    if len(sources) > 1:
        best["versions"] = len(sources)
    return best


def common_values(lists, n):
    """Values that at least half of the n episodes have, in first-seen order."""
    seen = [v for values in lists for v in values]
    counts = Counter(seen)
    return [v for v in dict.fromkeys(seen) if counts[v] * 2 >= n]


def common_field(summaries, key):
    """(the most common value of key, how many have it); (None, 0) when none has it."""
    counts = Counter(tuple(s[key]) if key == "hdr" else s[key] for s in summaries if s.get(key))
    return counts.most_common(1)[0] if counts else (None, 0)


def combined_media(summaries):
    """Summary over many episodes: the most common value per field (flagged when
    not all agree), languages most episodes have, and the total size."""
    summaries = [s for s in summaries if s]
    if not summaries:
        return None
    n = len(summaries)
    res, with_res = common_field(summaries, "res")
    hdr, with_hdr = common_field(summaries, "hdr")
    tracks = common_values(([tuple(t) for t in s.get("tracks", [])] for s in summaries), n)
    out = {
        "episodes": n,
        "res": res,
        "resMixed": bool(res) and with_res < n,
        "codec": common_field(summaries, "codec")[0],
        "audio": common_field(summaries, "audio")[0],
        "container": common_field(summaries, "container")[0],
        # A few HDR episodes don't make the whole thing HDR
        "hdr": list(hdr) if hdr and with_hdr * 2 >= n else None,
        "tracks": [list(t) for t in tracks],
        "subLangs": common_values((s.get("subLangs", []) for s in summaries), n),
        "size": sum(s.get("size", 0) for s in summaries),
    }
    return {k: v for k, v in out.items() if v}


def language_flags(records, cache_dir):
    """Flags for every audio / subtitle language used anywhere in the export."""
    langs = set()
    for r in records:
        m = r.get("media") or {}
        langs.update(t[0] for t in m.get("tracks", []))
        langs.update(m.get("subLangs", []))
    langs.discard("")
    if not langs:
        return {}
    if cache_dir:
        os.makedirs(cache_dir, exist_ok=True)
    flags = fetch_flags(langs, cache_dir)
    unflagged = len(langs) - len(flags)
    note = f" ({unflagged} shown by name)" if unflagged else ""
    log(f"{len(flags)} language flags{note}", "🚩")
    return flags
