"""Einrichtung im Projektordner: .env (Port, Plattform, Dateibesitzer) und Ordner data.

Zugangsdaten werden nie hier, sondern im Browser erfragt.
"""
from pathlib import Path
import argparse
import os
import platform

PLATFORMS = {"auto": "", "amd64": "linux/amd64", "arm64": "linux/arm64"}


def detected():
    machine = platform.machine().lower()
    if machine in ("x86_64", "amd64"):
        return "amd64"
    if machine in ("aarch64", "arm64"):
        return "arm64"
    return None


def ask_platform():
    guess = detected()
    hint = f" (dieses Gerät: {guess})" if guess else ""
    print("Auf welcher Plattform läuft der Container?" + hint)
    print("  auto  – Plattform des Docker-Hosts verwenden (empfohlen, wenn setup.py auf dem NAS läuft)")
    print("  amd64 – Intel/AMD-Prozessor")
    print("  arm64 – ARM64-Prozessor")
    while True:
        answer = input("Plattform [auto]: ").strip().lower() or "auto"
        if answer in PLATFORMS:
            return answer
        print("Bitte auto, amd64 oder arm64 eingeben.")


def default_owner():
    """Aufrufenden DSM-Benutzer vorschlagen, auch wenn setup.py per sudo läuft."""
    uid = os.environ.get("SUDO_UID") or (str(os.getuid()) if hasattr(os, "getuid") and os.getuid() else "")
    gid = os.environ.get("SUDO_GID") or (str(os.getgid()) if hasattr(os, "getgid") and os.getgid() else "")
    return uid, gid


def ask_owner():
    uid, gid = default_owner()
    print("Welchem DSM-Benutzer sollen die Dateien in data/ gehören?")
    print("  Auf Synology einen echten Benutzer mit Lese-/Schreibrecht auf den Ordner verwenden (IDs per SSH: id <benutzer>).")
    print("  Leer lassen = interne ID 10001; dann muss diese ID selbst Schreibrecht erhalten (siehe Installationsanleitung).")
    while True:
        puid = input(f"Benutzer-ID [{uid or 'leer'}]: ").strip() or uid
        pgid = input(f"Gruppen-ID [{gid or 'leer'}]: ").strip() or gid
        if all(value == "" or (value.isdigit() and value != "0") for value in (puid, pgid)):
            return puid, pgid
        print("Bitte Zahlen größer 0 eingeben (root ist nicht erlaubt) oder leer lassen.")


def render(example, port, choice, puid="", pgid=""):
    text = example.replace("HTTP_PORT=8088", f"HTTP_PORT={port}")
    text = text.replace("PUID=\n", f"PUID={puid}\n").replace("PGID=\n", f"PGID={pgid}\n")
    return text.replace("KILOWATCH_PLATFORM=\n", f"KILOWATCH_PLATFORM={PLATFORMS[choice]}\n")


def prepare_data(root, puid, pgid):
    """data/ vorab anlegen: Container Manager legt fehlende Bind-Mount-Ordner nicht immer selbst an."""
    data = root / "data"
    data.mkdir(exist_ok=True)
    if puid and pgid and hasattr(os, "geteuid") and os.geteuid() == 0:
        os.chown(data, int(puid), int(pgid))
    return data


def main():
    parser = argparse.ArgumentParser(description="Optionale .env ohne Zugangsdaten erstellen und data/ anlegen")
    parser.add_argument("--port", type=int, default=8088)
    parser.add_argument("--platform", choices=sorted(PLATFORMS), help="ohne Angabe wird interaktiv gefragt")
    parser.add_argument("--puid", help="Benutzer-ID für data/ (ohne Angabe wird interaktiv gefragt)")
    parser.add_argument("--pgid", help="Gruppen-ID für data/")
    args = parser.parse_args()
    if not 1 <= args.port <= 65535:
        raise SystemExit("Port muss zwischen 1 und 65535 liegen.")
    root = Path(__file__).resolve().parents[1]
    target = root / ".env"
    if target.exists():
        raise SystemExit(".env ist bereits vorhanden und wird nicht überschrieben.")
    choice = args.platform or ask_platform()
    if args.puid is not None or args.pgid is not None:
        puid, pgid = args.puid or "", args.pgid or ""
    else:
        puid, pgid = ask_owner()
    for value in (puid, pgid):
        if value and (not value.isdigit() or value == "0"):
            raise SystemExit("PUID/PGID müssen Zahlen größer 0 sein.")
    target.write_text(render((root / ".env.example").read_text(encoding="utf-8"), args.port, choice, puid, pgid), encoding="utf-8")
    data = prepare_data(root, puid, pgid)
    print(f".env ohne Zugangsdaten erstellt und {data} angelegt.")
    print("Auf Synology prüfen: File Station → data → Eigenschaften → Berechtigung: der gewählte Benutzer braucht Lesen/Schreiben.")
    print("Danach das Projekt starten und im Browser einrichten.")


if __name__ == "__main__":
    main()
