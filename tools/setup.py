"""Optionale .env mit Port und Plattform; Zugangsdaten werden im Browser erfragt."""
from pathlib import Path
import argparse
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


def render(example, port, choice):
    text = example.replace("HTTP_PORT=8088", f"HTTP_PORT={port}")
    return text.replace("KILOWATCH_PLATFORM=\n", f"KILOWATCH_PLATFORM={PLATFORMS[choice]}\n")


def main():
    parser = argparse.ArgumentParser(description="Optionale .env ohne Zugangsdaten erstellen")
    parser.add_argument("--port", type=int, default=8088)
    parser.add_argument("--platform", choices=sorted(PLATFORMS), help="ohne Angabe wird interaktiv gefragt")
    args = parser.parse_args()
    if not 1 <= args.port <= 65535:
        raise SystemExit("Port muss zwischen 1 und 65535 liegen.")
    root = Path(__file__).resolve().parents[1]
    target = root / ".env"
    if target.exists():
        raise SystemExit(".env ist bereits vorhanden und wird nicht überschrieben.")
    choice = args.platform or ask_platform()
    target.write_text(render((root / ".env.example").read_text(encoding="utf-8"), args.port, choice), encoding="utf-8")
    print(".env ohne Zugangsdaten erstellt. App starten und im Browser einrichten.")
    if choice != "auto":
        print(f"Für das vorgebaute Image das Artefakt kilowatch-nas-{choice} verwenden.")


if __name__ == "__main__":
    main()
