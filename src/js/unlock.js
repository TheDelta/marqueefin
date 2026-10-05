// A page protected by a passphrase (export.py --passphrase-file / EXPORT_PASSPHRASE;
// the scheme is in marqueefin/seal.py): the library stays sealed until the viewer
// types the passphrase, then lands where the rest of the script reads it. Imports
// nothing that reads the page's data (dom.js): that only exists afterwards.
import "./noble-license.js";
import { shake256 } from "@noble/hashes/sha3.js";
import { t, translatePage } from "./i18n.js";
import { KEY, load, save } from "./store.js";

const HEADER = new TextEncoder().encode("marqueefin-sealed-v1");
const $ = (id) => document.getElementById(id);

// Base64 into a new buffer, `before` bytes left free at its start
function decode(text, before = 0) {
  const bin = atob(text);
  const out = new Uint8Array(before + bin.length);
  for (let i = 0; i < bin.length; i++) out[before + i] = bin.codePointAt(i);
  return out;
}
const encode = (bytes) => btoa(String.fromCodePoint(...bytes)); // the 64-byte key only

// PBKDF2-SHA256: 32 bytes for the keystream, 32 for the MAC
async function derive(passphrase, sealed) {
  const text = new TextEncoder().encode(passphrase.normalize("NFC"));
  const base = await crypto.subtle.importKey("raw", text, "PBKDF2", false, ["deriveBits"]);
  const params = { name: "PBKDF2", hash: "SHA-256", salt: decode(sealed.salt) };
  const bits = await crypto.subtle.deriveBits({ ...params, iterations: sealed.iter }, base, 512);
  return new Uint8Array(bits);
}

// The sealed text, or null when the key doesn't fit (a wrong passphrase, a changed
// file): the MAC is checked before anything is decrypted
async function open(sealed, keys) {
  const nonce = decode(sealed.nonce);
  const signed = decode(sealed.ct, HEADER.length + nonce.length);
  signed.set(HEADER);
  signed.set(nonce, HEADER.length);
  const mac = await crypto.subtle.importKey(
    "raw",
    keys.slice(32),
    { name: "HMAC", hash: "SHA-256" },
    false,
    ["verify"],
  );
  if (!(await crypto.subtle.verify("HMAC", mac, decode(sealed.tag), signed))) return null;
  const seed = new Uint8Array(32 + nonce.length);
  seed.set(keys.slice(0, 32));
  seed.set(nonce, 32);
  const data = signed.subarray(HEADER.length + nonce.length);
  const stream = shake256(seed, { dkLen: data.length });
  for (let i = 0; i < data.length; i++) data[i] ^= stream[i];
  return new TextDecoder().decode(data);
}

// The opened library where the page's script reads it
function place(text) {
  const { data, requests, flags } = JSON.parse(text);
  $("data").textContent = JSON.stringify(data);
  $("requests").textContent = JSON.stringify(requests);
  $("flags").textContent = JSON.stringify(flags);
  document.body.classList.remove("locked");
}

function rememberedKey(sealed) {
  try {
    const stored = JSON.parse(load(KEY) || "null");
    return stored?.salt === sealed.salt ? decode(stored.key) : null;
  } catch {
    return null;
  }
}

/** Resolves once the page's data is there: at once for a page without a passphrase. */
export async function unlock() {
  const sealed = JSON.parse($("sealed")?.textContent || "null");
  if (!sealed) return;
  translatePage();
  const msg = $("lockMsg");
  // WebCrypto exists only in secure contexts: https, localhost or a file
  if (!globalThis.crypto?.subtle) {
    msg.textContent = t("lock.unsupported");
    $("lockOpen").disabled = true;
    return new Promise(() => {});
  }
  const key = rememberedKey(sealed);
  const text = key && (await open(sealed, key).catch(() => null));
  if (text) return place(text);

  const pass = $("lockPass"),
    button = $("lockOpen");
  pass.focus();
  return new Promise((resolve) => {
    $("lock").addEventListener("submit", async (e) => {
      e.preventDefault(); // no navigation (the policy forbids form targets anyway)
      button.disabled = true;
      msg.textContent = t("lock.working");
      try {
        const keys = await derive(pass.value, sealed);
        const opened = await open(sealed, keys);
        if (opened === null) {
          msg.textContent = t("lock.wrong");
          pass.select();
          return;
        }
        if ($("lockRemember").checked)
          save(KEY, JSON.stringify({ salt: sealed.salt, key: encode(keys) }));
        place(opened);
        resolve();
      } finally {
        button.disabled = false;
      }
    });
  });
}
