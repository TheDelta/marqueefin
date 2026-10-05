"""docker/*.sh and notify.py run for real in `sh`, with the image's paths pointed at a
temporary folder and stubs for the exporter, sftp and supercronic. Skipped without `sh`."""

import json
import os
import shutil
import subprocess
import sys
import tempfile
import threading
import time
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SH = shutil.which("sh") or ""  # "": skipped
PY = Path(sys.executable).as_posix()

# The exporter's stand-in: STUB_EXPORT=ok | fail | warn; writes EXPORT_OUTPUT and
# its arguments (args.json)
STUB_EXPORT = """
import json, os, sys
with open("args.json", "w") as f:
    json.dump(sys.argv[1:], f)
mode = os.environ.get("STUB_EXPORT", "ok")
print("exporting...")
if mode == "fail":
    print("Error: can't reach the server")
    sys.exit(2)
if mode == "warn":
    print("  Skipping requests: can't read Seerr (timed out).")
with open(os.environ["EXPORT_OUTPUT"], "w") as f:
    f.write("<html>page</html>")
print("Done in 1s")
"""
# notify.py's stand-in: records the title, priority and message
STUB_NOTIFY = """
import json, sys
with open(sys.argv[0] + ".calls", "a") as f:
    f.write(json.dumps([sys.argv[1:], sys.stdin.read()]) + "\\n")
"""
STUB_UPLOAD = """#!/bin/sh
echo "$@" >> "$0.calls"
exit "${STUB_UPLOAD:-0}"
"""
STUB_RUN = """#!/bin/sh
echo "$@" >> "$0.calls"
exit "${STUB_RUN:-0}"
"""
# supercronic and sftp: record their arguments (and sftp its batch from stdin)
STUB_SUPERCRONIC = """#!/bin/sh
echo "$@" > "$STUB_DIR/supercronic.args"
"""
STUB_SFTP = """#!/bin/sh
echo "$@" > "$STUB_DIR/sftp.args"
cat > "$STUB_DIR/sftp.batch"
exit "${STUB_SFTP:-0}"
"""


def write(path, text, executable=False):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8", newline="\n")
    if executable:
        path.chmod(0o755)


@unittest.skipUnless(SH, "needs a POSIX shell (sh)")
class ShellTest(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.tmp = Path(tmp.name)
        self.app, self.data, self.state, self.bin = (
            self.tmp / n for n in ("app", "data", "state", "bin")
        )
        for d in (self.data, self.state, self.bin):
            d.mkdir()
        write(self.bin / "supercronic", STUB_SUPERCRONIC, executable=True)
        write(self.bin / "sftp", STUB_SFTP, executable=True)
        self.env = {
            **os.environ,
            "PATH": str(self.bin) + os.pathsep + os.environ.get("PATH", ""),
            "MARQUEEFIN_APP": self.app.as_posix(),
            "MARQUEEFIN_DATA": self.data.as_posix(),
            "MARQUEEFIN_STATE": self.state.as_posix(),
            "STUB_DIR": self.tmp.as_posix(),
            "EXPORT_OUTPUT": (self.data / "collection.html").as_posix(),
        }
        for k in ("SCHEDULE", "UPLOAD_HOST", "GOTIFY_URL", "EXPORT_ARGS"):
            self.env.pop(k, None)

    def sh(self, script, *args, timeout=20, **env):
        return subprocess.run(
            [SH, Path(script).as_posix(), *args],
            env={**self.env, **env},
            capture_output=True,
            text=True,
            encoding="utf-8",  # the scripts log emoji
            timeout=timeout,
            check=False,
        )

    def calls(self, path):
        p = Path(str(path) + ".calls")
        return p.read_text(encoding="utf-8").splitlines() if p.exists() else []


class RunScript(ShellTest):
    """docker/run.sh: export, upload, notifications, the health check's result."""

    def setUp(self):
        super().setUp()
        (self.app / "docker").mkdir(parents=True)
        shutil.copy(ROOT / "docker" / "run.sh", self.app / "docker" / "run.sh")
        write(self.app / "export.py", STUB_EXPORT)
        write(self.app / "docker" / "notify.py", STUB_NOTIFY)
        write(self.app / "docker" / "upload.sh", STUB_UPLOAD, executable=True)
        self.notify = self.app / "docker" / "notify.py"

    def run_script(self, *args, **env):
        return self.sh(self.app / "docker" / "run.sh", *args, **env)

    def result(self):
        return (self.state / "run.result").read_text().strip()

    def test_a_good_run(self):
        r = self.run_script()
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(self.result(), "ok")
        self.assertTrue((self.data / ".last-success").exists())
        self.assertTrue((self.data / "collection.html").exists())
        self.assertIn("Done in 1s", r.stdout)  # the export's log reaches the container log
        self.assertEqual(self.calls(self.notify), [])  # good runs stay quiet

    def test_a_failed_export(self):
        r = self.run_script(STUB_EXPORT="fail")
        self.assertEqual(r.returncode, 1)
        self.assertEqual(self.result(), "failed")
        self.assertFalse((self.data / ".last-success").exists())
        [call] = self.calls(self.notify)
        (title, priority), message = json.loads(call)
        self.assertEqual((title, priority), ("Marqueefin: export failed", "8"))
        self.assertIn("can't reach the server", message)

    def test_warnings_are_sent_quietly(self):
        r = self.run_script(STUB_EXPORT="warn")
        self.assertEqual(r.returncode, 0)
        self.assertEqual(self.result(), "ok")
        [call] = self.calls(self.notify)
        (title, priority), message = json.loads(call)
        self.assertEqual((title, priority), ("Marqueefin: finished with warnings", "5"))
        self.assertEqual(message.strip(), "Skipping requests: can't read Seerr (timed out).")

    def test_arguments_reach_the_exporter(self):
        self.run_script("--title", "Movie Night", EXPORT_ARGS="--no-media --workers 4")
        args = json.loads((self.data / "args.json").read_text())
        self.assertEqual(args, ["--no-media", "--workers", "4", "--title", "Movie Night"])

    def test_upload(self):
        upload = self.app / "docker" / "upload.sh"
        r = self.run_script(UPLOAD_HOST="web.example")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(self.calls(upload), [self.env["EXPORT_OUTPUT"]])
        r = self.run_script(UPLOAD_HOST="web.example", STUB_UPLOAD="1")
        self.assertEqual(r.returncode, 1)
        self.assertEqual(self.result(), "failed")
        self.assertIn("Marqueefin: upload failed", self.calls(self.notify)[-1])


class EntrypointScript(ShellTest):
    """docker/entrypoint.sh: one run, or the schedule."""

    def setUp(self):
        super().setUp()
        self.run_sh = self.app / "docker" / "run.sh"
        write(self.run_sh, STUB_RUN, executable=True)

    def entrypoint(self, *args, **env):
        return self.sh(ROOT / "docker" / "entrypoint.sh", *args, **env)

    def test_without_a_schedule_it_runs_once(self):
        r = self.entrypoint("--no-media", STUB_RUN="3")
        self.assertEqual(r.returncode, 3)  # the run's status is the container's
        self.assertEqual(self.calls(self.run_sh), ["--no-media"])
        self.assertFalse((self.tmp / "supercronic.args").exists())

    def test_a_schedule_runs_at_start_then_hands_over(self):
        r = self.entrypoint(SCHEDULE="15 5 * * *", TZ="Europe/Berlin")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("Scheduled: '15 5 * * *' (Europe/Berlin)", r.stdout)
        crontab = (self.state / "crontab").read_text()
        self.assertEqual(crontab, f"15 5 * * * {self.app.as_posix()}/docker/run.sh\n")
        self.assertEqual(len(self.calls(self.run_sh)), 1)  # the run at start
        self.assertTrue((self.state / "first-run").exists())
        self.assertTrue((self.state / "started").exists())
        args = (self.tmp / "supercronic.args").read_text().split()
        self.assertEqual(args[-1], (self.state / "crontab").as_posix())
        self.assertIn("-no-reap", args)

    def test_no_run_at_start(self):
        self.entrypoint(SCHEDULE="15 5 * * *", RUN_ON_START="0")
        self.assertEqual(self.calls(self.run_sh), [])
        self.assertFalse((self.state / "first-run").exists())

    def test_a_failed_first_run_keeps_the_schedule(self):
        r = self.entrypoint(SCHEDULE="15 5 * * *", STUB_RUN="1")
        self.assertEqual(r.returncode, 0)
        self.assertIn("trying again on schedule", r.stderr)
        self.assertTrue((self.tmp / "supercronic.args").exists())


class HealthCheck(ShellTest):
    """docker/healthcheck.sh: the latest run's result and its age."""

    def check(self, **env):
        return self.sh(ROOT / "docker" / "healthcheck.sh", SCHEDULE="15 5 * * *", **env)

    def age(self, path, hours):
        t = time.time() - hours * 3600
        os.utime(path, (t, t))

    def result(self, text):
        (self.state / "run.result").write_text(text + "\n")

    def test_one_off_runs_are_always_healthy(self):
        r = self.sh(ROOT / "docker" / "healthcheck.sh")
        self.assertEqual(r.returncode, 0)

    def test_the_latest_run(self):
        (self.data / ".last-success").touch()
        self.result("ok")
        self.assertEqual(self.check().returncode, 0)
        self.result("failed")
        self.assertEqual(self.check().returncode, 1)

    def test_the_last_good_run_is_too_old(self):
        self.result("ok")
        (self.data / ".last-success").touch()
        self.age(self.data / ".last-success", 30)
        self.assertEqual(self.check().returncode, 1)  # 26 hours by default
        self.assertEqual(self.check(HEALTH_MAX_AGE_HOURS="48").returncode, 0)

    def test_before_the_first_run(self):
        (self.state / "started").touch()  # RUN_ON_START=0: nothing has run yet
        self.assertEqual(self.check().returncode, 0)
        self.age(self.state / "started", 30)
        self.assertEqual(self.check().returncode, 1)

    def test_it_waits_for_the_first_run(self):
        (self.state / "first-run").touch()
        (self.data / ".last-success").touch()

        def finish():
            time.sleep(1)
            self.result("ok")

        threading.Thread(target=finish).start()
        started = time.monotonic()
        self.assertEqual(self.check().returncode, 0)
        self.assertGreaterEqual(time.monotonic() - started, 0.9)


class UploadScript(ShellTest):
    """docker/upload.sh: a pinned host key, a temporary name, then a rename."""

    def setUp(self):
        super().setUp()
        self.key, self.known = self.tmp / "key", self.tmp / "known_hosts"
        self.key.write_text("PRIVATE KEY")
        self.known.write_text("[web.example]:2222 ssh-ed25519 AAAA")
        self.page = self.data / "collection.html"
        self.page.write_text("<html></html>")
        self.upload_env = {
            "UPLOAD_HOST": "web.example", "UPLOAD_USER": "marqueefin",
            "UPLOAD_PORT": "2222", "UPLOAD_DIR": "/library",
            "UPLOAD_KEY_FILE": self.key.as_posix(),
            "UPLOAD_KNOWN_HOSTS": self.known.as_posix(),
        }  # fmt: skip

    def upload(self, **env):
        return self.sh(
            ROOT / "docker" / "upload.sh",
            self.page.as_posix(),
            **{**self.upload_env, **env},
        )

    def test_upload_then_rename(self):
        r = self.upload()
        self.assertEqual(r.returncode, 0, r.stderr)
        batch = (self.tmp / "sftp.batch").read_text().splitlines()
        self.assertEqual(batch, [
            f'@put "{self.page.as_posix()}" "/library/.index.html.part"',
            '@rename "/library/.index.html.part" "/library/index.html"',
        ])  # fmt: skip
        args = (self.tmp / "sftp.args").read_text()
        for expected in ("-P 2222", "StrictHostKeyChecking=yes", "BatchMode=yes",
                         f"UserKnownHostsFile={self.known.as_posix()}",
                         "marqueefin@web.example"):  # fmt: skip
            self.assertIn(expected, args)
        self.assertIn("Uploaded", r.stdout)

    def test_a_failed_transfer_fails(self):
        self.assertNotEqual(self.upload(STUB_SFTP="1").returncode, 0)

    def test_missing_settings_and_secrets(self):
        r = self.upload(UPLOAD_KEY_FILE=(self.tmp / "nope").as_posix())
        self.assertEqual(r.returncode, 1)
        self.assertIn("can't read the SSH key", r.stderr)
        r = self.upload(UPLOAD_KNOWN_HOSTS=(self.tmp / "nope").as_posix())
        self.assertIn("can't read known_hosts", r.stderr)
        env: dict = {k: v for k, v in self.upload_env.items() if k != "UPLOAD_USER"}
        r = self.sh(ROOT / "docker" / "upload.sh", self.page.as_posix(), **env)
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("UPLOAD_USER", r.stderr)


class FakeGotify:
    def __enter__(self):
        self.messages, self.status = [], 200
        fake = self

        class Handler(BaseHTTPRequestHandler):
            def do_POST(self):
                body = self.rfile.read(int(self.headers["Content-Length"]))
                fake.messages.append((self.path, dict(self.headers), json.loads(body)))
                self.send_response(fake.status)
                self.end_headers()

            def log_message(self, format, *args):  # noqa: A002 - quiet
                pass

        self.httpd = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.url = f"http://127.0.0.1:{self.httpd.server_address[1]}"
        threading.Thread(
            target=self.httpd.serve_forever, kwargs={"poll_interval": 0.02}, daemon=True
        ).start()
        return self

    def __exit__(self, *exc):
        self.httpd.shutdown()
        self.httpd.server_close()


class Notify(unittest.TestCase):
    """docker/notify.py: a Gotify message with the end of the log."""

    def notify(self, *args, stdin="", **env):
        base = {k: v for k, v in os.environ.items() if not k.startswith("GOTIFY_")}
        return subprocess.run(
            [sys.executable, str(ROOT / "docker" / "notify.py"), *args],
            input=stdin, env={**base, **env}, capture_output=True, text=True, encoding="utf-8",
            timeout=30, check=False,
        )  # fmt: skip

    def test_a_message(self):
        with FakeGotify() as g:
            log = "line\n" * 2000 + "Error: export failed"
            r = self.notify("Marqueefin: export failed", "8", stdin=log,
                            GOTIFY_URL=g.url + "/", GOTIFY_TOKEN="app-token")  # fmt: skip
        self.assertEqual(r.returncode, 0, r.stderr)
        [(path, headers, body)] = g.messages
        self.assertEqual(path, "/message")
        self.assertEqual(headers["X-Gotify-Key"], "app-token")  # a header, not the URL
        self.assertEqual((body["title"], body["priority"]), ("Marqueefin: export failed", 8))
        self.assertTrue(body["message"].endswith("Error: export failed"))
        self.assertLessEqual(len(body["message"]), 3000)  # the end of a long log

    def test_not_configured_does_nothing(self):
        self.assertEqual(self.notify("Title").returncode, 0)

    def test_bad_settings_and_errors(self):
        r = self.notify("T", GOTIFY_URL="ftp://gotify", GOTIFY_TOKEN="x")
        self.assertEqual(r.returncode, 1)
        self.assertIn("must start with https:// or http://", r.stderr)
        with FakeGotify() as g:
            g.status = 401
            r = self.notify("T", GOTIFY_URL=g.url, GOTIFY_TOKEN="wrong")
        self.assertEqual(r.returncode, 1)
        self.assertIn("Gotify notification failed", r.stderr)
        self.assertNotIn("wrong", r.stderr)  # the token stays out of the log


if __name__ == "__main__":
    unittest.main()
