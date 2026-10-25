#!/bin/sh
# Kilowatch aktualisieren. Für den DSM-Aufgabenplaner (Benutzer root, z. B. wöchentlich)
# oder per SSH. Lädt das in compose.prebuilt.yaml genannte Image (Standard: neueste 1.x)
# und startet den Container nur neu, wenn sich das Image geändert hat.
set -eu

PROJECT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
cd "$PROJECT_DIR"
COMPOSE_FILE=${COMPOSE_FILE:-compose.prebuilt.yaml}
compose() { docker compose -f "$COMPOSE_FILE" "$@"; }

before=$(compose images -q kilowatch 2>/dev/null || true)
compose pull kilowatch
compose up -d kilowatch
after=$(compose images -q kilowatch)

if [ "$before" = "$after" ]; then
  echo "Kilowatch ist aktuell."
  exit 0
fi

# Auf den Healthcheck warten; eine Datenbank-Migration legt vorher selbst eine Sicherung an.
container=$(compose ps -q kilowatch)
for i in $(seq 1 60); do
  state=$(docker inspect -f '{{.State.Health.Status}}' "$container" 2>/dev/null || echo unknown)
  if [ "$state" = healthy ]; then
    docker image prune -f --filter "label=org.opencontainers.image.title=Kilowatch" >/dev/null
    echo "Kilowatch aktualisiert: $(docker inspect -f '{{index .Config.Labels "org.opencontainers.image.version"}}' "$container")"
    exit 0
  fi
  sleep 5
done

echo "Kilowatch ist nach dem Update nicht gesund. Protokoll prüfen; Rückweg in docs/UPDATES.md." >&2
compose logs --tail=50 kilowatch >&2 || true
exit 1
