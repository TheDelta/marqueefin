"""A page protected by a passphrase: its data is sealed, and the page opens it in the
browser (src/js/unlock.js) once the viewer types the passphrase.

The standard library has no AES, so the scheme uses what both sides have built in
(Python's hashlib / hmac, the browser's WebCrypto) plus SHAKE256 in the page
(@noble/hashes), as encrypt-then-MAC:

- keys: PBKDF2-HMAC-SHA256 of the passphrase (NFC), ITERATIONS rounds, 64 bytes:
  the first 32 for the keystream, the last 32 for the MAC;
- keystream: SHAKE256(stream key || nonce), XORed with the UTF-8 JSON;
- tag: HMAC-SHA256(MAC key, HEADER || nonce || ciphertext), checked before anything
  is decrypted (a wrong passphrase or a changed file fails here).

The salt can stay the same across exports (the cache keeps it), so a viewer's
remembered key still opens tomorrow's page; the nonce is new every time, so no two
pages share a keystream.
"""

import base64
import hashlib
import hmac
import os
import unicodedata

ITERATIONS = 600_000  # OWASP's 2023 figure for PBKDF2-HMAC-SHA256
HEADER = b"marqueefin-sealed-v1"


def b64(data):
    return base64.b64encode(data).decode("ascii")


def derive(passphrase, salt, iterations=ITERATIONS):
    text = unicodedata.normalize("NFC", passphrase).encode("utf-8")
    return hashlib.pbkdf2_hmac("sha256", text, salt, iterations, dklen=64)


def xor_stream(key, nonce, data):
    stream = hashlib.shake_256(key + nonce).digest(len(data))
    # One big-integer XOR: fast for the page's 20+ MB, unlike a loop over bytes
    mixed = int.from_bytes(data, "big") ^ int.from_bytes(stream, "big")
    return mixed.to_bytes(len(data), "big")


def seal(text, passphrase, salt=None, iterations=ITERATIONS):
    """The text sealed with the passphrase, as the page's #sealed JSON object."""
    salt = salt or os.urandom(16)
    nonce = os.urandom(16)
    keys = derive(passphrase, salt, iterations)
    ct = xor_stream(keys[:32], nonce, text.encode("utf-8"))
    tag = hmac.new(keys[32:], HEADER + nonce + ct, hashlib.sha256).digest()
    return {
        "v": 1,
        "iter": iterations,
        "salt": b64(salt),
        "nonce": b64(nonce),
        "tag": b64(tag),
        "ct": b64(ct),
    }


def unseal(sealed, passphrase):
    """The text, or None for a wrong passphrase or a changed file (what the page does,
    for the tests)."""
    salt, nonce, tag, ct = (base64.b64decode(sealed[k]) for k in ("salt", "nonce", "tag", "ct"))
    keys = derive(passphrase, salt, sealed["iter"])
    mac = hmac.new(keys[32:], HEADER + nonce + ct, hashlib.sha256).digest()
    if not hmac.compare_digest(mac, tag):
        return None
    return xor_stream(keys[:32], nonce, ct).decode("utf-8")


def stored_salt(cache_dir):
    """The salt kept in the cache folder (made once), so the key stays the same across
    exports; a new one each time without a cache."""
    if not cache_dir:
        return os.urandom(16)
    path = os.path.join(cache_dir, "seal_salt")
    try:
        with open(path, encoding="ascii") as f:
            salt = bytes.fromhex(f.read().strip())
        if len(salt) == 16:
            return salt
    except (OSError, ValueError):
        pass
    salt = os.urandom(16)
    os.makedirs(cache_dir, exist_ok=True)
    with open(path, "w", encoding="ascii", newline="\n") as f:
        f.write(salt.hex() + "\n")
    return salt
