"""Nur CI: prüft im Container, dass der App-Prozess ohne root und ohne Capabilities läuft."""
import os
import sys

found = []
for pid in filter(str.isdigit, os.listdir("/proc")):
    try:
        with open(f"/proc/{pid}/cmdline", "rb") as handle:
            if b"uvicorn" not in handle.read():
                continue
        with open(f"/proc/{pid}/status") as handle:
            fields = dict(line.split(":", 1) for line in handle if ":" in line)
    except OSError:
        continue
    found.append((fields["Uid"].split()[0], int(fields["CapEff"].strip(), 16)))
if not found or any(uid == "0" or caps for uid, caps in found):
    sys.exit(f"App-Prozess läuft privilegiert oder fehlt: {found}")
print("App-Prozess ohne root und ohne Capabilities:", found)
