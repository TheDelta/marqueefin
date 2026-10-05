"""The project's own files: Compose files that Docker accepts (with the hardening
in place), and every setting the code reads documented where users look."""

import json
import re
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DOCKER = shutil.which("docker") or ""  # "": skipped


def read(name):
    return (ROOT / name).read_text(encoding="utf-8")


def docker_compose_works():
    if not DOCKER:
        return False
    r = subprocess.run([DOCKER, "compose", "version"], capture_output=True, check=False)
    return r.returncode == 0


@unittest.skipUnless(docker_compose_works(), "needs Docker Compose")
class ComposeFiles(unittest.TestCase):
    """compose.yaml (and the override example) as `docker compose config` sees them,
    in a copy with .env made from .env.example."""

    def config(self, with_override):
        with tempfile.TemporaryDirectory() as tmp:
            shutil.copy(ROOT / "compose.yaml", tmp)
            shutil.copy(ROOT / ".env.example", Path(tmp) / ".env")
            if with_override:
                shutil.copy(
                    ROOT / "compose.override.example.yaml",
                    Path(tmp) / "compose.override.yaml",
                )
            secrets = Path(tmp) / "secrets"
            secrets.mkdir()
            for name in ("upload_key", "upload_known_hosts"):
                (secrets / name).write_text("")
            r = subprocess.run(
                [DOCKER, "compose", "config", "--format", "json"],
                cwd=tmp, capture_output=True, text=True, check=False,
            )  # fmt: skip
        self.assertEqual(r.returncode, 0, r.stderr)
        return json.loads(r.stdout)

    def test_compose_yaml(self):
        service = self.config(with_override=False)["services"]["marqueefin"]
        # The published image; another tag or a build goes into compose.override.yaml
        self.assertEqual(service["image"], "ghcr.io/thedelta/marqueefin:latest")
        self.assertNotIn("build", service)
        self.assertEqual(service["container_name"], "marqueefin")
        self.assertTrue(service["read_only"])
        self.assertEqual(service["cap_drop"], ["ALL"])
        self.assertIn("no-new-privileges:true", service["security_opt"])
        self.assertTrue(service.get("tmpfs"))  # the one writable place besides /data
        self.assertEqual(
            sorted(s["source"] for s in service["secrets"]),
            ["upload_key", "upload_known_hosts"],
        )

    def test_with_the_override_example(self):
        config = self.config(with_override=True)
        self.assertIn("proxy_net", config["services"]["marqueefin"]["networks"])
        self.assertTrue(config["networks"]["proxy_net"]["external"])


class SettingsAreDocumented(unittest.TestCase):
    """Every environment variable the code reads is in .env.example (the exporter's
    and the container's settings) and, for the container's, in docker/README.md."""

    # Set by compose.yaml itself, or for tests only
    INTERNAL = frozenset({
        "UPLOAD_KEY_FILE", "UPLOAD_KNOWN_HOSTS",
        "MARQUEEFIN_APP", "MARQUEEFIN_DATA", "MARQUEEFIN_STATE",
    })  # fmt: skip

    def read_vars(self, text, shell_script):
        found = set(re.findall(r'environ(?:\.get)?\(\s*"([A-Z][A-Z0-9_]+)"', text))
        found |= set(re.findall(r'environ\["([A-Z][A-Z0-9_]+)"\]', text))
        found |= set(re.findall(r'env_flag\("([A-Z][A-Z0-9_]+)"\)', text))
        if shell_script:
            found |= set(re.findall(r"\$\{([A-Z][A-Z0-9_]+)", text))
        return found - self.INTERNAL

    def test_exporter_settings(self):
        code = "".join(read(p.relative_to(ROOT).as_posix()) for p in ROOT.glob("marqueefin/*.py"))
        used = self.read_vars(code + read("docker/notify.py"), shell_script=False)
        self.assertIn("JELLYFIN_URL", used)  # the search still finds the settings
        example = read(".env.example")
        self.assertEqual(sorted(v for v in used if v not in example), [])

    def test_container_settings(self):
        scripts = "".join(read(f"docker/{n}") for n in (
            "entrypoint.sh", "run.sh", "upload.sh", "healthcheck.sh"))  # fmt: skip
        used = self.read_vars(scripts, shell_script=True) - {"TZ"}
        example, readme = read(".env.example"), read("docker/README.md")
        self.assertEqual(sorted(v for v in used if v not in example), [])
        self.assertEqual(sorted(v for v in used if v not in readme), [])


class WorkflowsAreDocumented(unittest.TestCase):
    """Every workflow has a row in .github/workflows/README.md."""

    def test_workflows(self):
        folder = ROOT / ".github" / "workflows"
        readme = (folder / "README.md").read_text(encoding="utf-8")
        missing = [p.name for p in sorted(folder.glob("*.yaml"))
                   if f"]({p.name})" not in readme]  # fmt: skip
        self.assertEqual(missing, [])

    def test_every_workflow_has_a_name(self):
        """Without one, the Actions tab lists runs by file name."""
        folder = ROOT / ".github" / "workflows"
        unnamed = [p.name for p in sorted(folder.glob("*.yaml"))
                   if not re.search(r"^name: \S", p.read_text(encoding="utf-8"), re.M)]  # fmt: skip
        self.assertEqual(unnamed, [])


class DependenciesArePinned(unittest.TestCase):
    """package.json names exact versions, as package-lock.json installs them: no ranges
    that a plain `npm install` could move (.npmrc save-exact keeps new ones exact)."""

    EXACT = re.compile(r"\d+\.\d+\.\d+(?:-[0-9A-Za-z.-]+)?")

    def test_npm(self):
        pkg = json.loads(read("package.json"))
        ranges = {
            name: spec
            for section in ("dependencies", "devDependencies")
            for name, spec in pkg.get(section, {}).items()
            if not self.EXACT.fullmatch(spec)
        }
        self.assertEqual(ranges, {})
        self.assertIn("save-exact=true", read(".npmrc"))


if __name__ == "__main__":
    unittest.main()
