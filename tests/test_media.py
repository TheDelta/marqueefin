"""Video and audio details from Jellyfin's MediaSources."""

import unittest
from itertools import pairwise

from marqueefin.media import (
    audio_track,
    audio_tracks,
    combined_media,
    item_media,
    resolution,
    source_media,
)


def audio(codec, channels=6, profile="", title="", language="eng", **extra):
    return {
        "Type": "Audio",
        "Codec": codec,
        "Channels": channels,
        "Profile": profile,
        "DisplayTitle": title,
        "Language": language,
        **extra,
    }


class Resolution(unittest.TestCase):
    def test_classes(self):
        self.assertEqual(resolution(3840, 1600), "4K")  # cinemascope 4K
        self.assertEqual(resolution(1920, 800), "1080p")
        self.assertEqual(resolution(1280, 720), "720p")
        self.assertEqual(resolution(720, 576), "SD")
        self.assertEqual(resolution(7680, 4320), "8K")
        self.assertIsNone(resolution(None, None))


class AudioRanking(unittest.TestCase):
    """The best track is the poster's audio badge: Atmos (TrueHD) > DTS:X > DD+
    Atmos > DTS-HD MA / TrueHD > PCM / FLAC > DTS > DD+ > DD > AAC."""

    def best(self, *tracks):
        return max(audio_track(t) for t in tracks)[1]

    def test_order(self):
        ordered = [
            audio("truehd", 8, title="TrueHD Atmos"),
            audio("dts", 8, profile="DTS:X"),
            audio("eac3", 6, profile="Dolby Digital Plus + Dolby Atmos"),
            audio("dts", 8, profile="DTS-HD MA"),
            audio("flac", 2),
            audio("dts", 6),
            audio("eac3", 6),
            audio("ac3", 6),
            audio("aac", 2),
        ]
        for better, worse in pairwise(ordered):
            with self.subTest(better=better, worse=worse):
                self.assertGreater(audio_track(better)[0], audio_track(worse)[0])

    def test_more_channels_win_ties(self):
        self.assertEqual(
            max(audio_track(t) for t in (audio("ac3", 2), audio("ac3", 6)))[2],
            "5.1",
        )

    def test_names_and_layouts(self):
        self.assertEqual(
            audio_track(audio("truehd", 8, title="TrueHD Atmos 7.1"))[1:],
            ("TrueHD Atmos", "7.1"),
        )
        self.assertEqual(
            audio_track(audio("dts", 6, profile="DTS-HD MA"))[1:],
            ("DTS-HD MA", "5.1"),
        )

    def test_commentary_and_duplicates(self):
        tracks = audio_tracks(
            [
                audio("ac3", 6),
                audio("ac3", 6),  # same again: listed once
                audio("aac", 2, Title="Director's Commentary"),
            ]
        )
        self.assertEqual(tracks, [["en", "5.1", "Dolby Digital"], ["en", "2.0", "AAC", 1]])


class SourceMedia(unittest.TestCase):
    def test_summary(self):
        src = {
            "Container": "mkv,webm",
            "Size": 1000,
            "MediaStreams": [
                {
                    "Type": "Video",
                    "Codec": "hevc",
                    "Width": 3840,
                    "Height": 2160,
                    "BitDepth": 10,
                    "VideoRangeType": "DOVIWithHDR10",
                },
                audio("truehd", 8, title="TrueHD Atmos"),
                audio("ac3", 6, language="ger"),
                {"Type": "Subtitle", "Language": "ger"},
                {"Type": "Subtitle", "Language": "eng", "IsForced": True},
            ],
        }
        m = source_media(src)
        self.assertEqual(m["res"], "4K")
        self.assertEqual(m["codec"], "HEVC")
        self.assertEqual(m["bits"], 10)
        self.assertEqual(m["hdr"], ["Dolby Vision", "HDR10"])  # DV with a fallback
        self.assertEqual(m["audio"], "TrueHD Atmos 7.1")
        self.assertEqual(m["subLangs"], ["de"])  # forced subtitles left out
        self.assertEqual(m["container"], "MKV")

    def test_best_version_wins(self):
        def version(width, height, size):
            video = {"Type": "Video", "Width": width, "Height": height}
            return {"Size": size, "MediaStreams": [video]}

        item = {"MediaSources": [version(1920, 1080, 9), version(3840, 2160, 5)]}
        m = item_media(item)
        if m is None:
            self.fail("no media summary")
        self.assertEqual((m["res"], m["versions"]), ("4K", 2))


class CombinedMedia(unittest.TestCase):
    def test_most_common_values_and_total_size(self):
        eps = [
            {"res": "1080p", "audio": "DD+ 5.1", "size": 10, "subLangs": ["en"]},
            {"res": "1080p", "audio": "DD+ 5.1", "size": 20, "subLangs": ["en"]},
            {"res": "4K", "audio": "DD+ 5.1", "size": 30, "hdr": ["HDR10"]},
        ]
        m = combined_media(eps)
        if m is None:
            self.fail("no media summary")
        self.assertEqual(m["res"], "1080p")
        self.assertTrue(m["resMixed"])
        self.assertNotIn("hdr", m)  # one HDR episode of three isn't an HDR series
        self.assertEqual(m["size"], 60)
        self.assertEqual(m["subLangs"], ["en"])
        self.assertEqual(m["episodes"], 3)

    def test_nothing(self):
        self.assertIsNone(combined_media([None, {}]))


if __name__ == "__main__":
    unittest.main()
