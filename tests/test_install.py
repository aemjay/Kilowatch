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
