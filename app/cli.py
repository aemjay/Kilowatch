"""Wartung im gestoppten Container: python -m app.cli ..."""
import argparse
from contextlib import closing
from pathlib import Path
import sqlite3
import time

from .config import Config
from .storage import SCHEMA_VERSION


def reset_login(directory, confirmed=False):
    if not confirmed:
        raise ValueError("Anmeldung nur mit --confirm-stopped nach Stoppen des App-Containers zurücksetzen.")
    target = Path(directory) / "app-auth.json"
    if not target.exists():
        raise ValueError("Noch keine eingerichtete Anmeldung vorhanden.")
    backup = target.with_name(f"app-auth.before-reset-{time.time_ns()}.json")
    target.replace(backup)
    return backup


def restore(source, directory, confirmed=False):
    if not confirmed:
        raise ValueError("Wiederherstellung nur mit --confirm-stopped nach Stoppen des App-Containers.")
    source = Path(source).resolve(strict=True)
    directory = Path(directory).resolve()
    target = directory / "kilowatch.sqlite3"
    if source == target:
        raise ValueError("Quelle und Ziel sind identisch.")
    directory.mkdir(parents=True, exist_ok=True)
    temporary = directory / "restore-checked.tmp"
    try:
        with closing(sqlite3.connect(source.as_uri() + "?mode=ro", uri=True)) as original:
            if original.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
                raise ValueError("Sicherung ist beschädigt.")
            version = original.execute("PRAGMA user_version").fetchone()[0]
            tables = {r[0] for r in original.execute("SELECT name FROM sqlite_master WHERE type='table'")}
            if not 1 <= version <= SCHEMA_VERSION or not {"samples", "buckets", "settings", "state", "gaps", "tariffs", "prices", "events", "issues"} <= tables:
                raise ValueError(f"Keine kompatible Kilowatch-Sicherung (Schema 1 bis {SCHEMA_VERSION}).")
            with closing(sqlite3.connect(temporary)) as dest:
                original.backup(dest)
        if target.exists():
            backup = directory / "backups" / ("before-restore-" + time.strftime("%Y%m%d-%H%M%S") + ".sqlite3")
            backup.parent.mkdir(exist_ok=True)
            with closing(sqlite3.connect(target)) as old, closing(sqlite3.connect(backup)) as copy:
                old.backup(copy)
        for suffix in ("-wal", "-shm"):
            sidecar = Path(str(target) + suffix)
            if sidecar.exists():
                sidecar.unlink()
        temporary.replace(target)
    finally:
        if temporary.exists():
            temporary.unlink()
    return target


def main():
    parser = argparse.ArgumentParser(description="Kilowatch-Wartung")
    sub = parser.add_subparsers(dest="command", required=True)
    restore_parser = sub.add_parser("restore", help="Geprüfte Sicherung bei gestoppter Anwendung zurückspielen")
    restore_parser.add_argument("source")
    restore_parser.add_argument("--confirm-stopped", action="store_true")
    backup_parser = sub.add_parser("backup", help="Konsistente SQLite-Sicherung erstellen")
    backup_parser.add_argument("target")
    reset_parser = sub.add_parser("reset-login", help="Vergessenes App-Passwort bei gestoppter Anwendung zurücksetzen")
    reset_parser.add_argument("--confirm-stopped", action="store_true")
    args = parser.parse_args()
    config = Config.from_env()
    directory = config.data_folder
    if args.command == "restore":
        print("Wiederhergestellt:", restore(args.source, directory, args.confirm_stopped))
    elif args.command == "reset-login":
        print("Bisherigen Passwort-Hash gesichert:", reset_login(config.secrets_folder, args.confirm_stopped))
        print("App starten und neuen Setup-Code aus dem Container-Protokoll verwenden. Messdaten und Zugangsdaten bleiben erhalten.")
    else:
        source = directory / "kilowatch.sqlite3"
        if not source.exists():
            raise SystemExit("Noch keine Datenbank vorhanden.")
        with closing(sqlite3.connect(source.as_uri() + "?mode=ro", uri=True)) as original, closing(sqlite3.connect(args.target)) as dest:
            original.backup(dest)
            if dest.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
                raise SystemExit("Sicherungsprüfung fehlgeschlagen.")
        print("Sicherung erstellt:", args.target)


if __name__ == "__main__":
    main()
