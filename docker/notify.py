#!/usr/bin/env python3
"""Send a message to Gotify (run.sh does on failures).

    tail -n 25 run.log | python notify.py "Title" [priority]

GOTIFY_URL and GOTIFY_TOKEN (an application token) come from the environment; without
them this does nothing. EXPORT_CA_CERT is trusted too.
"""

import json
import os
import ssl
import sys
import urllib.request


def tls_context():
    ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)  # checks certificates and host names
    ctx.minimum_version = ssl.TLSVersion.TLSv1_2
    ctx.load_default_certs()
    if os.environ.get("EXPORT_CA_CERT"):
        ctx.load_verify_locations(os.environ["EXPORT_CA_CERT"])
    return ctx


def main():
    url, token = os.environ.get("GOTIFY_URL"), os.environ.get("GOTIFY_TOKEN")
    if not url or not token:
        return 0  # not configured
    if not url.startswith(("https://", "http://")):
        print("GOTIFY_URL must start with https:// or http://", file=sys.stderr)
        return 1
    title = sys.argv[1] if len(sys.argv) > 1 else "Marqueefin"
    priority = int(sys.argv[2]) if len(sys.argv) > 2 else 8
    message = sys.stdin.read().strip()[-3000:] or title  # the end of the log is what matters
    body = json.dumps({"title": title, "message": message, "priority": priority}).encode()
    req = urllib.request.Request(
        url.rstrip("/") + "/message",
        data=body,
        # The token goes in a header, so it doesn't end up in proxy / access logs
        headers={"Content-Type": "application/json", "X-Gotify-Key": token},
        method="POST",
    )
    try:
        ctx = tls_context() if req.type == "https" else None
        with urllib.request.urlopen(req, timeout=20, context=ctx) as r:
            r.read()
    except (OSError, ValueError) as e:
        print(f"Gotify notification failed: {e}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
