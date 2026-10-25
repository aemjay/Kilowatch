import os
from pathlib import Path
import shutil
import subprocess

import pytest

ROOT = Path(__file__).resolve().parents[1]
DIGEST = "sha256:" + "0" * 63 + "7"
# Minimaler Docker-Ersatz. Zustand in $STUB_STATE: current = Image des Containers, tagged = Image hinter dem Tag.
STUB = """#!/bin/sh
echo "docker $*" >> "$STUB_LOG"
state() { cat "$STUB_STATE/$1" 2>/dev/null || true; }
case "$*" in
  "compose version") exit 0 ;;
  *"compose -f compose.yaml config --images"*) echo ghcr.io/aemjay/kilowatch:1 ;;
  *"compose -f compose.yaml images -q"*) state current ;;
  *"compose -f compose.yaml ps -q"*) echo container ;;
  *"compose -f compose.yaml up -d"*)
    [ -n "$(state tagged)" ] && state tagged > "$STUB_STATE/current"
    [ -d data ] && printf 'Kilowatch-Setup-Code: TESTCODE\\n' > data/SETUP-CODE.txt ;;
  "tag ghcr.io/aemjay/kilowatch@"*) echo new > "$STUB_STATE/tagged" ;;
  "tag "*) echo "$2" > "$STUB_STATE/tagged" ;;
  inspect*Health*) [ "$(state current)" = "$STUB_BAD" ] && echo unhealthy || echo healthy ;;
  "run --rm ghcr.io/sigstore/cosign/cosign:"*)
    [ -n "$STUB_UNSIGNED" ] && { echo "no signatures found" >&2; exit 1; }
    case "$*" in *"--certificate-identity-regexp ^https://github"*"nas-image"*) ;; *) exit 1 ;; esac
    printf '[{"critical":{"image":{"docker-manifest-digest":"%s"}}}]\\n' "$STUB_DIGEST" ;;
esac
"""

pytestmark = pytest.mark.skipif(not hasattr(os, "geteuid") or os.geteuid() != 0 or shutil.which("sh") is None,
                                reason="Erstinstallation verlangt root")


@pytest.fixture
def box(tmp_path):
    bin_dir, source, state = tmp_path / "bin", tmp_path / "src", tmp_path / "state"
    for folder in (bin_dir, source, state):
        folder.mkdir()
    (bin_dir / "docker").write_text(STUB)
    (bin_dir / "docker").chmod(0o755)
    shutil.copy(ROOT / "compose.yaml", source / "compose.yaml")
    shutil.copy(ROOT / "tools/update.sh", source / "update.sh")
    shutil.copy(ROOT / ".env.example", source / "env.example")
    (tmp_path / "log").write_text("")
    env = dict(os.environ, PATH=f"{bin_dir}:{os.environ['PATH']}", STUB_LOG=str(tmp_path / "log"), STUB_STATE=str(state),
               STUB_DIGEST=DIGEST, KILOWATCH_HEALTH_TRIES="2", KILOWATCH_HEALTH_INTERVAL="0")

    class Box:
        root, src, target, log = tmp_path, source, tmp_path / "kw", tmp_path / "log"

        def run(self, *args, script=None, **extra):
            # Immer einen eigenen Projektordner angeben, damit nie das Repository selbst eingerichtet wird.
            return subprocess.run(["sh", str(script or ROOT / "tools/update.sh"), "--dir", str(tmp_path / "kw"), "--source", str(source), *args],
                                  capture_output=True, text=True, env=dict(env, **extra))

        def install(self, *args, **extra):
            return self.run("--user", "nobody", *args, **extra)

        def update(self, *args, **extra):
            return self.run(*args, script=self.target / "tools/update.sh", **extra)

        def state(self, name, value=None):
            path = state / name
            if value is not None:
                path.write_text(value + "\n")
            return path.read_text().strip() if path.exists() else ""

    return Box()


def test_fresh_install_prepares_folder_owner_env_and_prints_setup_code(box):
    result = box.install("--port", "9090")
    assert result.returncode == 0, result.stderr
    assert "TESTCODE" in result.stdout and ":9090" in result.stdout
    assert (box.target / "data").stat().st_uid == int(subprocess.check_output(["id", "-u", "nobody"]))
    assert "HTTP_PORT=9090" in (box.target / ".env").read_text()
    assert (box.target / "compose.yaml").read_text() == (ROOT / "compose.yaml").read_text()
    assert (box.target / "tools/update.sh").read_text() == (ROOT / "tools/update.sh").read_text()


def test_update_runs_from_project_folder_without_options(box):
    assert box.install().returncode == 0
    box.state("current", "old")
    result = box.update()
    assert result.returncode == 0, result.stderr
    assert "aktualisiert" in result.stdout or "aktuell" in result.stdout


def test_update_keeps_env_and_replaces_untouched_compose_with_backup(box):
    box.install("--no-start")
    (box.target / ".env").write_text("HTTP_PORT=1234\n")
    (box.target / "compose.yaml").write_text("old")
    (box.target / ".compose.sha256").unlink()
    (box.src / "compose.yaml").write_text((ROOT / "compose.yaml").read_text() + "# neu\n")
    result = box.update("--no-start")
    assert result.returncode == 0, result.stderr
    assert (box.target / ".env").read_text() == "HTTP_PORT=1234\n"
    assert (box.target / "compose.yaml").read_text().endswith("# neu\n")
    assert [p.read_text() for p in box.target.glob("compose.yaml.bak-*")] == ["old"]


def test_update_never_overwrites_a_compose_file_the_user_changed(box):
    box.install("--no-start")
    mine = (box.target / "compose.yaml").read_text() + "# meine Änderung\n"
    (box.target / "compose.yaml").write_text(mine)
    (box.src / "compose.yaml").write_text((ROOT / "compose.yaml").read_text() + "# neu\n")
    result = box.update("--no-start")
    assert result.returncode == 0, result.stderr
    assert (box.target / "compose.yaml").read_text() == mine
    assert (box.target / "compose.yaml.new").read_text().endswith("# neu\n")
    assert "compose.yaml.new" in result.stderr
    # Ändert das Release die Datei nicht mehr, bleibt die eigene Fassung ohne weitere Warnung.
    (box.target / "compose.yaml.new").unlink()
    (box.src / "compose.yaml").write_text((ROOT / "compose.yaml").read_text() + "# neu\n")
    assert "compose.yaml.new" in box.update("--no-start").stderr


def test_update_replaces_itself_and_continues_with_the_release_version(box):
    box.install("--no-start")
    old = box.target / "tools/update.sh"
    old.write_text((ROOT / "tools/update.sh").read_text() + "\n# veraltete Fassung\n")
    result = box.update("--no-start")
    assert result.returncode == 0, result.stderr
    assert old.read_text() == (ROOT / "tools/update.sh").read_text()
    assert result.stdout.count("Image prüfen") == 1


def test_version_option_is_stored_and_accepts_latest(box):
    box.install("--version", "1.2.3", "--no-start")
    assert "KILOWATCH_VERSION=1.2.3" in (box.target / ".env").read_text()
    box.update("--version", "latest", "--no-start")
    assert "KILOWATCH_VERSION=\n" in (box.target / ".env").read_text()


@pytest.mark.parametrize("args,message", [([], "--user"), (["--user", "root"], "nicht root"),
                                          (["--user", "nobody", "--version", "1.2"], "1.2.3"),
                                          (["--user", "nobody", "--dir", "relative"], "absoluten"),
                                          (["--user", "nobody", "--port", "x"], "Zahl")])
def test_rejects_invalid_input(box, args, message):
    result = box.run(*args)
    assert result.returncode != 0 and message in result.stderr


def test_pulls_exactly_the_verified_digest(box):
    result = box.install()
    assert result.returncode == 0, result.stderr
    log = box.log.read_text()
    assert f"docker pull ghcr.io/aemjay/kilowatch@{DIGEST}" in log
    assert f"docker tag ghcr.io/aemjay/kilowatch@{DIGEST} ghcr.io/aemjay/kilowatch:1" in log
    assert log.index("docker tag") < log.index("up -d")
    assert "pull kilowatch" not in log


def test_unsigned_image_aborts_before_anything_is_pulled_or_started(box):
    box.install("--no-start")
    box.log.write_text("")
    result = box.update(STUB_UNSIGNED="1")
    assert result.returncode == 1 and "Signatur" in result.stderr
    log = box.log.read_text()
    assert "pull" not in log and "up -d" not in log


def test_unhealthy_update_rolls_back_to_the_previous_image(box):
    assert box.install().returncode == 0
    box.state("current", "old")
    result = box.update(STUB_BAD="new")
    assert result.returncode == 1
    assert "zurück" in result.stderr.lower()
    assert "docker tag old ghcr.io/aemjay/kilowatch:1" in box.log.read_text()
    assert box.state("current") == "old"


def test_unchanged_image_is_not_restarted_as_an_update(box):
    box.install()
    box.state("current", "new")
    box.state("tagged", "new")
    result = box.update()
    assert result.returncode == 0 and "aktuell" in result.stdout
