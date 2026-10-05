# Running Marqueefin in Docker

The container runs next to Jellyfin (on a NAS or any Docker host). It builds the page
on a schedule and uploads it over SFTP to a web server, which serves it behind a
password. Without a schedule it runs once and exits.

```text
compose.yaml             the service: schedule, secrets, hardening
Dockerfile               python:3.13-alpine, non-root (uid 10001), tini, supercronic;
                         a Node build stage bundles the page's script and styles
                         and installs Floating UI and the fonts (package-lock.json)
docker/entrypoint.sh     run once, or hand the schedule to supercronic
docker/run.sh            export, then upload when UPLOAD_HOST is set
docker/upload.sh         SFTP upload: temporary name, then an atomic rename
docker/healthcheck.sh    unhealthy when the last good run is too old
docker/notify.py         Gotify message when a run fails
```

## On the Docker host

1. Put `compose.yaml` and `.env.example` there (or the whole project folder), then
   create `.env` from `.env.example` (Jellyfin, Seerr, title, `TZ`) and add the upload
   settings:

   ```sh
   UPLOAD_HOST=<server>          # exactly as used for ssh-keyscan (step 4 below)
   UPLOAD_PORT=22
   UPLOAD_USER=marqueefin
   UPLOAD_DIR=/library           # the web folder, as the upload account sees it
   UPLOAD_FILENAME=index.html
   ```

2. Put the key and the pinned host key in `secrets/` (see "Server setup" steps 3 and 4) and let the container read both. It runs as uid 10001, and compose mounts
   file secrets with their host owner and mode. The key is readable by that user
   only. The host key is public, so it's readable by everyone:

   ```sh
   sudo chown 10001 secrets/upload_key && sudo chmod 400 secrets/upload_key
   sudo chmod 644 secrets/upload_known_hosts
   ls -ln secrets/   # upload_key: 10001, -r--------; upload_known_hosts: -rw-r--r--
   ```

   "Can't read known_hosts" or "can't read the SSH key" in the log means one of these
   is missing. A `+` after the mode in `ls -l` means the file also has access control
   entries (common on Synology shares), which can deny access despite the mode: keep
   `secrets/` outside shared folders, or allow uid 10001 read access there.

3. Check the setup with a one-off run. It exits with an error and the reason if
   something's wrong (a wrong URL or key, an unreachable server, a failed upload):

   ```sh
   docker compose run --rm -e SCHEDULE= marqueefin
   ```

4. Start it. `--wait` returns once the first run is done, and fails if that run
   failed (see "Health" below):

   ```sh
   docker compose up -d --wait
   docker compose logs -f
   ```

   This pulls the published image `ghcr.io/thedelta/marqueefin:latest`. For another
   tag, or to build it yourself, see "Image tags and updates" below.

   Published images are built by the release workflow from the tagged commit,
   with a list of their packages (SBOM) and a signed build attestation. To check
   that an image really comes from the repository (needs the
   [GitHub CLI](https://cli.github.com)):

   ```sh
   gh attestation verify oci://ghcr.io/thedelta/marqueefin:1.0.0 --owner TheDelta
   ```

A one-off run in between, e.g. after adding a lot of titles (add `-e EXPORT_REFRESH=1`
to fetch everything fresh):

```sh
docker compose run --rm -e SCHEDULE= marqueefin
```

The page and the cache live in the `marqueefin-data` volume (`/data/collection.html`,
`/data/cache`). Keep it: with the cache a run takes seconds instead of minutes.

## Image tags and updates

| Tag                    | What it is                                                  | For                               |
| ---------------------- | ----------------------------------------------------------- | --------------------------------- |
| `latest` (the default) | the newest release                                          | most people                       |
| `1`, `1.2`             | the newest release of 1.x / 1.2.x                           | no surprises from a major version |
| `next`                 | the newest release candidate or release, whichever is newer | trying what's coming              |
| `1.2.3`, `1.3.0-rc.1`  | exactly that version                                        | pinning, going back               |

A tag other than `latest` goes into `compose.override.yaml` (copy
`compose.override.example.yaml`), so `compose.yaml` stays as it comes:

```yaml
services:
  marqueefin:
    image: ghcr.io/thedelta/marqueefin:next
```

**Updates:** a tag moving on doesn't change a running container. Pull the new image
and recreate the container, e.g. once a week as a scheduled task (Synology: Control
Panel → Task Scheduler → Create → Scheduled Task → User-defined script, as root):

```sh
cd /path/to/marqueefin && docker compose pull && docker compose up -d && docker image prune -f
```

`up -d` only recreates the container when the image changed; `image prune` removes the
old one. Breaking changes only come with a new major version (see CHANGELOG.md), so
`latest` and `1` are safe to update this way.

**Building it yourself** (to try a change): in `compose.override.yaml`, set
`build: .` and `image: marqueefin:dev`, then `docker compose up -d --build`.

## Reaching Jellyfin, Seerr and Gotify

If they run as containers on the same host, don't point Marqueefin at their public
domains: from inside a container those often fail with "Host is unreachable" (errno
113). Typical causes are a reverse proxy or service on a macvlan network, which
containers on the same host can't reach, or a host firewall that blocks Docker's
networks. Join their Docker network instead and use container names.

A common setup is an external network that Jellyfin and Seerr share with a reverse
proxy such as Caddy (`networks: [default, proxy_net]` in their compose file, with
`proxy_net` declared `external: true`). `compose.override.example.yaml` joins
Marqueefin to that `proxy_net`; change the name if yours differs:

```sh
cp compose.override.example.yaml compose.override.yaml
```

```sh
JELLYFIN_URL=http://jellyfin:8096                    # in .env
SEER_URL=http://seerr:5055
GOTIFY_URL=http://gotify
JELLYFIN_PUBLIC_URL=https://jellyfin.example.com     # links on the page stay public
```

The host names are the service names from their compose file (compose registers them
on every network a service joins) or their `container_name`. That traffic stays on
the host, so plain HTTP is fine. `docker network ls` lists the networks.

## Health

In scheduled mode the container is healthy when its latest run (export and upload)
succeeded and the last good run is less than `HEALTH_MAX_AGE_HOURS` old (default 26).
The first check waits for the first run after start, so `docker compose up --wait`
returns as soon as that run is done, and fails when it failed. One failed scheduled
run makes the container unhealthy until the next good run. Needs Docker Engine 25+
for the quick first check; older engines check after a minute.

## Notifications (Gotify)

With `GOTIFY_URL` and `GOTIFY_TOKEN` (an application token: Gotify > Apps) in `.env`,
a failed run sends a message with the end of its log:

- **"export failed"** / **"upload failed"**, priority 8.
- **"finished with warnings"**, priority 5: the page was built, but something was
  skipped (Seerr unreachable, so no Requests tab or second-language titles; posters that
  couldn't be downloaded).

Successful runs stay quiet. A failed run also shows up as `unhealthy` in
`docker ps`; so does a schedule that stops running (after `HEALTH_MAX_AGE_HOURS`).

## Schedule

`SCHEDULE` is cron syntax in the container's `TZ` (set it to your time zone, e.g.
`TZ=Europe/Berlin`; the default is UTC). The compose default, **daily at 05:15**
(`15 5 * * *`), comes after typical nightly library scans and Seerr's availability
sync, and the page shows how fresh it is ("Updated 3 hours ago"). For fresher pages
use `15 5,17 * * *`. With anything slower than daily, raise `HEALTH_MAX_AGE_HOURS`
(default 26). Runs never overlap.

## Server setup (SFTP-only upload account)

The upload account can do exactly one thing: write files into the web folder over
SFTP. No shell, no forwarding; the key only works for that. Uploads go to
`.index.html.part` and are renamed over `index.html`, so the web server never serves
half a page. The server's host key is pinned, so a spoofed server gets nothing.

The examples use the account `marqueefin`, the web folder `/var/www/library` and the
web server group `www-data` (Debian / Ubuntu). sshd only accepts a chroot whose every
directory belongs to root, so the account is locked into a root-owned
`/srv/sftp/marqueefin`, with the web folder bind-mounted inside as `/library`. That
also works when the web folder lives in a user's home directory.

**Web server on the same host as Docker?** Skip all of this: mount the web folder at
`/data` and set `EXPORT_OUTPUT=/data/index.html`. The page is written to a temporary
file and renamed, so that's atomic too.

1. **Account, web folder, chroot:**

   ```sh
   sudo useradd --system --no-create-home --shell /usr/sbin/nologin marqueefin

   # Written by the upload account, readable by the web server (uploads are 0644);
   # setgid keeps new files in the folder's group
   sudo install -d -o marqueefin -g www-data -m 2775 /var/www/library

   # The chroot, with the web folder mounted inside as /library
   sudo install -d -o root -g root -m 755 /srv/sftp/marqueefin /srv/sftp/marqueefin/library
   echo '/var/www/library /srv/sftp/marqueefin/library none bind 0 0' | sudo tee -a /etc/fstab
   sudo systemctl daemon-reload && sudo mount /srv/sftp/marqueefin/library
   ```

   Add `marqueefin` to `AllowUsers` / `AllowGroups` in `sshd_config` if there is such
   a line.

2. **sshd rules, as a drop-in.** A `Match` block in its own file ends with that file,
   so it can't swallow later settings of the main config (pasted into `sshd_config`
   above `HostKey` lines it fails with "not allowed within a Match block").
   `sshd_config` needs `Include /etc/ssh/sshd_config.d/*.conf`, which Debian and
   Ubuntu have by default.

   ```sh
   sudo tee /etc/ssh/sshd_config.d/90-marqueefin.conf > /dev/null <<'EOF'
   # SFTP-only upload account for the Marqueefin page
   Match User marqueefin
       ChrootDirectory /srv/sftp/marqueefin
       ForceCommand internal-sftp -u 0022 -d /library
       AuthorizedKeysFile /etc/ssh/authorized_keys/%u
       AuthenticationMethods publickey
       PasswordAuthentication no
       PermitTTY no
       AllowTcpForwarding no
       AllowAgentForwarding no
       X11Forwarding no
       PermitTunnel no
   EOF
   sudo sshd -t && sudo systemctl reload ssh
   ```

   `-u 0022`: uploaded files are readable by the web server. `-d /library`: sessions
   start in the web folder. To confirm the rules only hit this account, the second
   line must print `forcecommand none` and `chrootdirectory none`:

   ```sh
   sudo sshd -T -C user=marqueefin,host=docker,addr=192.0.2.1 | grep -Ei 'chrootdirectory|forcecommand'
   sudo sshd -T -C user=root,host=docker,addr=192.0.2.1 | grep -Ei 'chrootdirectory|forcecommand'
   ```

3. **Key.** Create it where the container runs (or copy it there), and install the
   public half on the server as one line with `restrict` in front:

   ```sh
   ssh-keygen -t ed25519 -N "" -C marqueefin -f secrets/upload_key
   cat secrets/upload_key.pub

   # on the server
   sudo install -d -m 755 /etc/ssh/authorized_keys
   echo 'restrict <the line from upload_key.pub>' | sudo tee /etc/ssh/authorized_keys/marqueefin
   ```

4. **Pin the host key** with the same address and port that go into `UPLOAD_HOST` /
   `UPLOAD_PORT` (the entry only matches that exact address), and compare the
   fingerprint with the server's own:

   ```sh
   ssh-keyscan -t ed25519 -p 22 <server> > secrets/upload_known_hosts
   ssh-keygen -lf secrets/upload_known_hosts               # here
   ssh-keygen -lf /etc/ssh/ssh_host_ed25519_key.pub        # on the server: must match
   ```

5. **Test.** It should start in `/library` and see nothing else; `ssh` is refused:

   ```sh
   sftp -i secrets/upload_key -o UserKnownHostsFile=secrets/upload_known_hosts -P 22 marqueefin@<server>
   ```

**`Permission denied (publickey)`?** The reason is only in the server's log:
`sudo journalctl -u ssh --since "15 min ago" | grep -i marqueefin`.

- `not listed in AllowUsers`: add the account there (step 1).
- `account is locked`: only with `UsePAM no`. Run `sudo usermod -p '*' marqueefin`
  (still no usable password, just not locked; never `usermod -U` / `passwd -d`, they
  leave an empty password).
- `bad ownership or modes`: `/etc/ssh/authorized_keys` and the key file must belong
  to root and be writable only by root.
- Nothing logged: check that `sudo ssh-keygen -lf /etc/ssh/authorized_keys/marqueefin`
  shows the fingerprint of `secrets/upload_key.pub`, and that the drop-in is active
  (`sudo sshd -T -C user=marqueefin,... | grep authorizedkeysfile`).

**`dest open "/library/.index.html.part": Permission denied`?** The login works, but
the account can't write to the folder:

```sh
findmnt /srv/sftp/marqueefin/library     # nothing: the bind mount isn't active
ls -ldn /srv/sftp/marqueefin/library     # owner, group and mode as the account sees it
sudo -u marqueefin test -w /srv/sftp/marqueefin/library && echo writable
```

- **Nothing mounted** (after a reboot, or the fstab line is missing): the account sees
  the empty, root-owned mount point. Run `sudo mount /srv/sftp/marqueefin/library`
  and check the fstab line from step 1.
- **Not writable:** the web folder must belong to the account, or be group-writable
  for a group it's in. Run
  `sudo chown marqueefin /var/www/library && sudo chmod 2775 /var/www/library`, and
  keep the web server's group. An existing `index.html` can stay as it is: replacing
  it only needs write access to the folder (unless the folder has the sticky bit,
  `t` in `ls -ld`).

## Web server (Apache example)

The page lists your library, your watched history and your Seerr requests. It carries
`noindex`, but keep it behind a password and HTTPS. Because the upload account can
write to the folder, lock it down:

- **Nothing in it may run** (no PHP, CGI or server-side includes), and only
  `index.html` can be fetched, so a leaked upload key can't turn into running code.
  The half-uploaded `.index.html.part` stays private too.
- **Auth in the server config**, not in a `.htaccess` the upload account could
  replace.
- **The server's own error pages** for the folder: if the site sends error pages
  through an app, the 401 that asks for the password would show that app instead of
  a login prompt.

For a site whose `DocumentRoot` contains `/var/www/library`, inside its
`<VirtualHost>`:

```apache
<Directory /var/www/library>
    DirectoryIndex index.html
    # Nothing runs here: no CGI, server-side includes, listings or MultiViews
    Options None
    AllowOverride None

    AuthType Basic
    AuthName "Library"
    AuthUserFile /etc/apache2/marqueefin.htpasswd
    Require valid-user

    # The server's own error pages: the browser shows its login prompt
    ErrorDocument 401 default
    ErrorDocument 403 default
    ErrorDocument 404 default

    # Always check for a newer export instead of showing a cached one
    Header set Cache-Control "no-cache"
    # The page brings its own Content Security Policy; these can only come from the
    # server: no framing by other sites, no MIME sniffing, no referrer
    Header set Content-Security-Policy "frame-ancestors 'none'"
    Header set X-Content-Type-Options "nosniff"
    Header set Referrer-Policy "no-referrer"
</Directory>

# Only the page itself: anything else in the folder (the half-uploaded
# .index.html.part, a .php file, ...) is refused before PHP or any other handler
# sees it. <Location> is applied after <Directory>, so this wins.
<LocationMatch "^/library/(?!index\.html$).+">
    Require all denied
</LocationMatch>
```

```sh
sudo htpasswd -c /etc/apache2/marqueefin.htpasswd <name>   # one login per viewer
sudo a2enmod headers
sudo apachectl configtest && sudo systemctl reload apache2
```

Expected: 401, 200, 403, 403.

```sh
curl -sI https://example.com/library/ | head -1
curl -sI -u <name>:<password> https://example.com/library/ | head -1
curl -sI -u <name>:<password> https://example.com/library/.index.html.part | head -1
curl -sI -u <name>:<password> https://example.com/library/x.php | head -1
```

Other web servers need the same three things: basic auth, only `index.html`
servable, `Cache-Control: no-cache`.

**Another app on the same site shows up instead of the page until a force reload?**
That app has a service worker registered for the whole site; it answers page loads
from its cache and never asks the server (Ctrl+Shift+R bypasses it). Exclude the
page's path in the app's service-worker configuration, or give the page its own
subdomain, which also keeps your viewers' lists apart from that app's storage.

## Settings

| Variable                 | Default                           | Meaning                                                            |
| ------------------------ | --------------------------------- | ------------------------------------------------------------------ |
| `SCHEDULE`               | empty (run once)                  | cron syntax, e.g. `15 5 * * *`                                     |
| `TZ`                     | `UTC`                             | your time zone (schedule and the dates on the page)                |
| `RUN_ON_START`           | `1`                               | with `SCHEDULE`: also run at container start                       |
| `EXPORT_ARGS`            | empty                             | extra exporter flags, e.g. `--no-media`                            |
| `EXPORT_PARALLEL_PAGES`  | `4`                               | Jellyfin result pages fetched at the same time                     |
| `EXPORT_REFRESH`         | empty                             | `1`: ignore what's remembered and fetch everything                 |
| `EXPORT_TITLE_LANGUAGE`  | empty                             | titles in a second language too (`de`, `fr`, `pt-BR`; needs Seerr) |
| `EXPORT_MAIN_LANGUAGES`  | `en` + the title language         | languages always shown as flags (`en,de`)                          |
| `EXPORT_POSTER_FORMAT`   | `webp`                            | `jpeg` for Jellyfin's default format                               |
| `EXPORT_PASSPHRASE`      | empty (no passphrase)             | protects the page: friends type it to open it                      |
| `EXPORT_PASSPHRASE_FILE` | empty                             | the same, from a file, e.g. a compose secret                       |
| `UPLOAD_HOST`            | empty (no upload)                 | as used for `ssh-keyscan`                                          |
| `UPLOAD_PORT`            | `22`                              |                                                                    |
| `UPLOAD_USER`            |                                   | the SFTP account, e.g. `marqueefin`                                |
| `UPLOAD_DIR`             | `.`                               | the web folder as the account sees it, e.g. `/library`             |
| `UPLOAD_FILENAME`        | `index.html`                      |                                                                    |
| `UPLOAD_KEY_FILE`        | `/run/secrets/upload_key`         |                                                                    |
| `UPLOAD_KNOWN_HOSTS`     | `/run/secrets/upload_known_hosts` |                                                                    |
| `HEALTH_MAX_AGE_HOURS`   | `26`                              | unhealthy when the last good run is older                          |
| `GOTIFY_URL`             | empty (no notifications)          | e.g. `https://gotify.example.com`                                  |
| `GOTIFY_TOKEN`           |                                   | Gotify application token                                           |

Everything else in `.env.example` works as outside Docker. `EXPORT_OUTPUT` and
`EXPORT_CACHE_DIR` point into `/data` in the image. Only the single-file page is
uploaded, so keep the default `--posters embed`.

## Design notes

Why the image and this setup are built the way they are (for contributors):

- **One image, two modes.** Without `SCHEDULE` it runs once and exits. With
  `SCHEDULE` (cron syntax, in `TZ`) supercronic runs it on a schedule, plus once at
  start (`RUN_ON_START=1`); runs never overlap.
- **Upload: SFTP to a chrooted, SFTP-only account** (`ForceCommand internal-sftp`,
  key-only, `restrict`ed key, no TTY or forwarding). Upload to `.index.html.part`, then
  `rename` (OpenSSH uses `posix-rename`, so it's atomic). The server's host key is
  pinned via a `known_hosts` secret (`StrictHostKeyChecking=yes`). Web server on the
  same host: mount the web root at `/data` instead of uploading.
- sshd refuses a chroot unless every path part is root-owned, so the guide uses a
  root-owned chroot with the web folder bind-mounted inside. The `Match` block lives in
  a drop-in under `/etc/ssh/sshd_config.d/`: a `Match` in an included file ends with
  that file (pasted into `sshd_config` above `HostKey` lines it breaks the config).
- Secrets (SSH key, known_hosts) are compose file secrets; they keep their host owner
  and mode, so the key must be readable by uid 10001 (and `known_hosts` too: 0644). `upload.sh` copies it to a 0600
  temp file because ssh refuses keys others can read.
- Hardening: `read_only`, tmpfs `/tmp`, `cap_drop: ALL`, `no-new-privileges`, capped
  logs.
- `container_name: marqueefin` (not `<folder>-marqueefin-1`); the service name
  stays `marqueefin`, so `docker compose logs marqueefin` etc. are unchanged.
- **Health** (scheduled mode): `run.sh` writes `/tmp/run.result` (`ok` / `failed`); the
  entrypoint touches `/tmp/first-run` before the start run. `healthcheck.sh` waits for
  the first result while `/tmp/first-run` exists, then fails on `failed` or when
  `/data/.last-success` is older than `HEALTH_MAX_AGE_HOURS` (26). Docker:
  `--start-period=1s --start-interval=1s --interval=1m --timeout=30m --retries=1`, so
  `docker compose up --wait` answers right after the first run (a quick failure lands
  after the 1 s start period, so it counts). Supercronic runs with `-no-reap` (tini
  is PID 1 and reaps).
- **Networking:** services on the same host should be reached by container name on a
  shared Docker network (`compose.override.example.yaml`, example `proxy_net` shared with a reverse proxy such as Caddy); public domains often fail
  from containers with errno 113 (macvlan reverse proxies, host firewalls).
- **Base images** are a moving tag pinned by digest (`python:3.13-alpine@sha256:…`,
  `node:24-alpine@sha256:…`): reproducible builds, and Dependabot proposes the new
  digest when the tag moves (new Python patch, new Alpine). Tags that name an Alpine
  version (`3.13.13-alpine3.22`) stop getting builds when Alpine moves on, and
  Dependabot keeps the old suffix: that's how the image once sat on Alpine 3.22 with
  10 fixed-but-unpatched OpenSSL / util-linux issues. Every build also runs `apk
upgrade`, and pip is removed (nothing installs packages at runtime; Trivy flagged
  its bundled urllib3 / setuptools / msgpack). SonarLint's "tag or digest, not
  both" (S8431) is accepted on purpose.
- The image adds only Alpine packages (tini, openssh-client, supercronic, tzdata).
  The bundle (`build/`), Floating UI and the fonts come from a Node build stage
  (`--platform=$BUILDPLATFORM`: its output is platform-independent); only those files
  are copied over, and of `src/` only the template, the texts and the favicon.
- **Gotify** (`docker/notify.py`, stdlib only): `run.sh` keeps each run's output in
  `/tmp/run.log` (`step()` preserves the exit status through `tee`). Export or upload
  failure: priority 8 with the last 25 lines; a finished run whose log has "Skipping"
  or "couldn't be downloaded" lines: priority 5; success: nothing. Token in the
  `X-Gotify-Key` header.
- Web server guidance (above): basic auth in the server config, not a
  `.htaccess` the upload account could overwrite; nothing in the folder may run
  (`Options None`, only `index.html` servable), so a leaked upload key can't become
  running code.
