"""marqueefin/seal.py: the data of a page protected by a passphrase. The page opens it
in the browser (src/js/unlock.js); tests/e2e/lock.spec.mjs checks that both sides fit."""

import base64
import os
import tempfile
import unittest

from marqueefin import seal

FAST = 1000  # PBKDF2 rounds for the tests; pages use seal.ITERATIONS
TEXT = '{"data":[{"title":"Paper Moons ✨"}]}'


def changed(sealed, key):
    """The sealed object with one byte of key flipped."""
    data = bytearray(base64.b64decode(sealed[key]))
    data[0] ^= 1
    return {**sealed, key: base64.b64encode(bytes(data)).decode()}


class Seal(unittest.TestCase):
    def test_round_trip(self):
        sealed = seal.seal(TEXT, "correct horse", iterations=FAST)
        self.assertEqual(sealed["v"], 1)
        self.assertEqual(sealed["iter"], FAST)
        self.assertNotIn("Paper", base64.b64decode(sealed["ct"]).decode("latin-1"))
        self.assertEqual(seal.unseal(sealed, "correct horse"), TEXT)

    def test_a_wrong_passphrase_opens_nothing(self):
        sealed = seal.seal(TEXT, "correct horse", iterations=FAST)
        self.assertIsNone(seal.unseal(sealed, "correct horse!"))

    def test_a_changed_file_is_refused(self):
        sealed = seal.seal(TEXT, "correct horse", iterations=FAST)
        for key in ("ct", "nonce", "tag", "salt"):
            with self.subTest(key=key):
                self.assertIsNone(seal.unseal(changed(sealed, key), "correct horse"))

    def test_every_page_gets_its_own_keystream(self):
        salt = os.urandom(16)
        a, b = (seal.seal(TEXT, "pass", salt, FAST) for _ in range(2))
        self.assertEqual(a["salt"], b["salt"])
        self.assertNotEqual(a["nonce"], b["nonce"])
        self.assertNotEqual(a["ct"], b["ct"])

    def test_the_passphrase_is_normalized(self):
        # "é" typed as one character or as e + accent: the same passphrase
        sealed = seal.seal(TEXT, "café au lait", iterations=FAST)
        self.assertEqual(seal.unseal(sealed, "café au lait"), TEXT)

    def test_defaults(self):
        self.assertGreaterEqual(seal.ITERATIONS, 600_000)


class StoredSalt(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.dir = os.path.join(tmp.name, "cache")  # created on first use

    def test_made_once_then_kept(self):
        first = seal.stored_salt(self.dir)
        self.assertEqual(len(first), 16)
        self.assertEqual(seal.stored_salt(self.dir), first)

    def test_a_broken_file_is_replaced(self):
        seal.stored_salt(self.dir)
        with open(os.path.join(self.dir, "seal_salt"), "w", encoding="ascii") as f:
            f.write("not hex")
        self.assertEqual(len(seal.stored_salt(self.dir)), 16)

    def test_without_a_cache_a_new_one_each_time(self):
        first, second = seal.stored_salt(None), seal.stored_salt(None)
        self.assertNotEqual(first, second)


if __name__ == "__main__":
    unittest.main()
