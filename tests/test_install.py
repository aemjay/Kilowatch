import os
from pathlib import Path
import shutil
import subprocess

import pytest

ROOT = Path(__file__).resolve().parents[1]
STUB = """#!/bin/sh
echo "docker $*" >> "$STUB_LOG"
case "$*" in
  "compose version") exit 0 ;;
  "compose up -d") printf 'Kilowatch-Setup-Code: TESTCODE\\n' > data/SETUP-CODE.txt ;;
  inspect*) echo healthy ;;
  *"config --images"*) echo ghcr.io/aemjay/kilowatch:1 ;;
  "run --rm ghcr.io/sigstore/cosign/cosign:"*)
    [ -n "$STUB_UNSIGNED" ] && { echo "no signatures found" >&2; exit 1; }
    case "$*" in *"--certificate-identity-regexp ^https://github"*"nas-image"*) ;; *) exit 1 ;; esac
    printf '[{"critical":{"image":{"docker-manifest-digest":"sha256:%064d"}}}]\n' 7 ;;
esac
"""

pytestmark = pytest.mark.skipif(not hasattr(os, "geteuid") or os.geteuid() != 0 or shutil.which("sh") is None,
                                reason="Installer verlangt root")


def run(tmp_path, *args):
    bin_dir, source = tmp_path / "bin", tmp_path / "src"
    bin_dir.mkdir(exist_ok=True)
    source.mkdir(exist_ok=True)
    (bin_dir / "docker").write_text(STUB)
    (bin_dir / "docker").chmod(0o755)
    shutil.copy(ROOT / "compose.yaml", source / "compose.yaml")
    shutil.copy(ROOT / "tools/update.sh", source / "update.sh")
    shutil.copy(ROOT / ".env.example", source / "env.example")
    env = dict(os.environ, PATH=f"{bin_dir}:{os.environ['PATH']}", STUB_LOG=str(tmp_path / "log"))
    return subprocess.run(["sh", str(ROOT / "tools/install.sh"), "--source", str(source), *args],
                          capture_output=True, text=True, env=env)


def test_installer_prepares_folder_owner_env_and_prints_setup_code(tmp_path):
    target = tmp_path / "kw"
    result = run(tmp_path, "--user", "nobody", "--dir", str(target), "--port", "9090")
    assert result.returncode == 0, result.stderr
    assert "TESTCODE" in result.stdout
    assert (target / "data").stat().st_uid == int(subprocess.check_output(["id", "-u", "nobody"]))
    assert "HTTP_PORT=9090" in (target / ".env").read_text()
    assert (target / "compose.yaml").read_text() == (ROOT / "compose.yaml").read_text()


def test_installer_keeps_existing_env_and_backs_up_changed_compose(tmp_path):
    target = tmp_path / "kw"
    run(tmp_path, "--user", "nobody", "--dir", str(target), "--no-start")
    (target / ".env").write_text("HTTP_PORT=1234\n")
    (target / "compose.yaml").write_text("old")
    result = run(tmp_path, "--user", "nobody", "--dir", str(target), "--no-start")
    assert result.returncode == 0, result.stderr
    assert (target / ".env").read_text() == "HTTP_PORT=1234\n"
    assert list(target.glob("compose.yaml.bak-*"))


@pytest.mark.parametrize("args,message", [([], "--user"), (["--user", "root"], "nicht root"),
                                          (["--user", "nobody", "--version", "1.2"], "1.2.3"),
                                          (["--user", "nobody", "--dir", "relative"], "absoluten")])
def test_installer_rejects_invalid_input(tmp_path, args, message):
    result = run(tmp_path, *args)
    assert result.returncode != 0 and message in result.stderr


def test_installer_pulls_exactly_the_verified_digest(tmp_path):
    result = run(tmp_path, "--user", "nobody", "--dir", str(tmp_path / "kw"))
    assert result.returncode == 0, result.stderr
    log = (tmp_path / "log").read_text()
    digest = "sha256:" + "0" * 63 + "7"
    assert f"docker pull ghcr.io/aemjay/kilowatch@{digest}" in log
    assert f"docker tag ghcr.io/aemjay/kilowatch@{digest} ghcr.io/aemjay/kilowatch:1" in log
    assert log.index("docker tag") < log.index("docker compose up -d")
    assert "compose -f compose.yaml pull" not in log


def test_unsigned_image_aborts_before_anything_is_pulled_or_started(tmp_path):
    target = tmp_path / "kw"
    run(tmp_path, "--user", "nobody", "--dir", str(target), "--no-start")
    env = dict(os.environ, PATH=f"{tmp_path / 'bin'}:{os.environ['PATH']}", STUB_LOG=str(tmp_path / "log"), STUB_UNSIGNED="1")
    (tmp_path / "log").write_text("")
    result = subprocess.run(["sh", str(target / "tools/update.sh")], capture_output=True, text=True, env=env)
    assert result.returncode == 1 and "Signatur" in result.stderr
    log = (tmp_path / "log").read_text()
    assert "pull" not in log and " up " not in log
