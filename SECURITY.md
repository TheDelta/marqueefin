# Security policy

## Supported versions

Security fixes go into the latest release. Please update to it (or use the `:1`
Docker image tag) before reporting.

| Version | Supported |
| ------- | --------- |
| 1.x     | ✅        |
| < 1.0   | ❌        |

## Reporting a vulnerability

**Please don't report security problems in public issues or discussions.**

Report them privately through GitHub:
[**Report a vulnerability**](https://github.com/TheDelta/marqueefin/security/advisories/new)
(repository → **Security** → **Report a vulnerability**).

Please include:

- what's affected (the exporter, the generated page, the Docker image or the upload),
- how to reproduce it, ideally with a minimal example,
- the impact you see, and the Marqueefin version (`python export.py --version`).

Leave out real API keys, passwords and server addresses.

Marqueefin is maintained in spare time, so responses are best effort. You'll get an
acknowledgement as soon as possible, and a fix and an advisory once the problem is
confirmed. Credit is given in the advisory unless you prefer otherwise.

## Scope

In scope, for example:

- API keys or other secrets ending up in the generated page, logs or error messages,
- script injection in the generated page through library data (titles, overviews,
  Seerr data),
- weaknesses in the Docker image or the SFTP upload.

Out of scope: vulnerabilities in Jellyfin, Seerr or other software Marqueefin talks
to (please report those to their projects), and the protection of the published page
itself, which is up to the web server it's hosted on.
