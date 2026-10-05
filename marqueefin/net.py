"""TLS and HTTP error messages for the Jellyfin and Seerr clients."""

import http.client
import json
import ssl
import urllib.error
import urllib.parse


def tls_context(ca_file=None, cert=None, key=None, insecure=False):
    """TLS 1.2+, certificates and host names checked. ca_file: an extra CA for a self-
    signed server; cert / key: a client certificate for a proxy in front of Seerr."""
    # Checks certificates and host names; only --insecure turns that off (below)
    ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)  # NOSONAR
    ctx.minimum_version = ssl.TLSVersion.TLSv1_2
    ctx.load_default_certs()
    if ca_file:
        ctx.load_verify_locations(ca_file)
    if cert:
        ctx.load_cert_chain(cert, key or None)
        ctx.post_handshake_auth = True  # proxies often ask for it after the handshake
    if insecure:
        # Only with --insecure, which logs a warning; --ca-cert is the safe way
        ctx.check_hostname = False  # NOSONAR  # explicit opt-in, see above
        ctx.verify_mode = ssl.CERT_NONE  # NOSONAR  # explicit opt-in, see above
    return ctx


def describe_error(e):
    """One line for the log: for an HTTP error the status, the endpoint and the
    server's own message (JSON "message" / "error", else the start of the body)."""
    if not isinstance(e, urllib.error.HTTPError):
        return f"{e.__class__.__name__}: {e}"
    where = urllib.parse.urlparse(e.url or "").path or "?"
    try:
        body = e.read().decode("utf-8", "replace")
    except (OSError, http.client.HTTPException):
        body = ""
    finally:
        e.close()  # the error holds the open response
    detail = body
    try:
        data = json.loads(body)
        if isinstance(data, dict):
            detail = data.get("message") or data.get("error") or data.get("title") or body
    except ValueError:
        pass
    detail = " ".join(str(detail).split())[:300]
    return f"HTTP {e.code} {e.reason} from {where}" + (f": {detail}" if detail else "")
