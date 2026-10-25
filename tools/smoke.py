"""Integrationstest eines gestarteten Containers; nur synthetische Konfiguration."""
import argparse
import http.cookiejar
import json
import re
import subprocess
import time
import urllib.error
import urllib.request


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", default="http://127.0.0.1:18088")
    parser.add_argument("--password", default="synthetic-ci-password-long")
    parser.add_argument("--seed", action="store_true")
    parser.add_argument("--container", help="Nur CI: Setup-Code aus diesem Testcontainer lesen")
    parser.add_argument("--expect-persisted", action="store_true")
    args = parser.parse_args()
    opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))
    for attempt in range(40):
        try:
            with opener.open(args.url + "/healthz", timeout=2) as response:
                assert json.load(response)["status"] == "ok"
            break
        except (OSError, AssertionError):
            time.sleep(.5)
    else:
        raise SystemExit("Container wird nicht gesund.")

    def api(path, method="GET", data=None):
        body = json.dumps(data).encode() if data is not None else None
        request = urllib.request.Request(args.url + path, data=body, method=method,
                                        headers={"Content-Type": "application/json", "X-Kilowatch-Request": "1"})
        with opener.open(request, timeout=10) as response:
            return json.load(response)

    if api("/api/setup/status")["needs_setup"]:
        if not args.container:
            raise SystemExit("Ersteinrichtung nötig; für CI --container angeben.")
        logs = subprocess.run(["docker", "logs", args.container], capture_output=True, text=True, check=True)
        match = re.search(r"Setup-Code ([A-Za-z0-9_-]+)", logs.stdout + logs.stderr)
        assert match, "Setup-Code fehlt im Testcontainer-Protokoll."
        api("/api/setup", "POST", {"setup_code": match[1], "password": args.password})
    api("/api/login", "POST", {"password": args.password})
    if args.seed:
        api("/api/settings", "PUT", {"name": "CI Persistence", "enabled": False, "bridge_password":"synthetic-ci-bridge-secret"})
        api("/api/tariffs", "PUT", {"start_date": "2020-01-01", "name": "CI synthetic", "mode": "dual", "eur_kwh": .3, "low_eur_kwh":.2, "low_start":"22:00", "low_end":"06:00", "base_month": 12, "feedin_eur_kwh": 0})
    if args.expect_persisted:
        assert api("/api/settings")["name"] == "CI Persistence"
        assert api("/api/tariffs")["tariffs"][0]["name"] == "CI synthetic"
        assert api("/api/tariffs")["tariffs"][0]["low_eur_kwh"] == .2
        assert api("/api/settings")["password_configured"]
    assert api("/api/overview")["summary"]["import_kwh"] is None
    assert "forecast" in api("/api/analysis")
    assert api("/api/notifications")["settings"]["enabled"] is False
    assert api("/api/settings")["bridge_host"] == ""
    with opener.open(args.url + "/api/backup") as response:
        assert response.read(16) == b"SQLite format 3\x00"
    print("Container, API, Dateirechte, konsistentes Backup und Persistenz: OK")


if __name__ == "__main__":
    main()
