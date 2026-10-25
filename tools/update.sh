#!/bin/sh
# Kilowatch aktualisieren. Für den DSM-Aufgabenplaner (Benutzer root, z. B. wöchentlich)
# oder per SSH. Lädt das in compose.yaml genannte Image (Standard: neueste 1.x)
# und startet den Container nur neu, wenn sich das Image geändert hat.
# Vor dem Start wird die Signatur geprüft (cosign, keyless über GitHub Actions) und
# genau der geprüfte Digest geladen. Ohne gültige Signatur bricht das Update ab.
#   --pull-only   nur prüfen und laden (verwendet der Installer), nicht starten
set -eu

# Fest gepinntes cosign-Image, falls cosign nicht installiert ist.
COSIGN_IMAGE=ghcr.io/sigstore/cosign/cosign:v3.1.4@sha256:0f06154836d2de34f887a5c273506d52ca43edaa1d9e53e6510fa78a48f69c2d
SIGNER_ISSUER=https://token.actions.githubusercontent.com
SIGNER_IDENTITY=${KILOWATCH_SIGNER:-'^https://github\.com/aemjay/Kilowatch/\.github/workflows/nas-image\.yml@refs/(heads/main|tags/v[0-9]+\.[0-9]+\.[0-9]+)$'}

PROJECT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
cd "$PROJECT_DIR"
COMPOSE_FILE=${COMPOSE_FILE:-compose.yaml}
compose() { docker compose -f "$COMPOSE_FILE" "$@"; }

if grep -Eq '^[[:space:]]+build:' "$COMPOSE_FILE"; then
  echo "$COMPOSE_FILE baut das Image selbst. Updates hier: neue Quellen kopieren und neu bauen." >&2
  echo "Automatische Updates gelten nur für das fertige Image (compose.yaml aus dem Repository)." >&2
  exit 1
fi

env_value() { [ -f .env ] && sed -n "s/^$1=//p" .env | tail -n 1 || true; }
VERIFY=${KILOWATCH_VERIFY:-$(env_value KILOWATCH_VERIFY)}
PLATFORM=${KILOWATCH_PLATFORM:-$(env_value KILOWATCH_PLATFORM)}

pull_verified() {
  image=$(compose config --images | grep -m 1 -i kilowatch) || { echo "Image in $COMPOSE_FILE nicht gefunden." >&2; exit 1; }
  if [ "$VERIFY" = 0 ]; then
    echo "Warnung: Signaturprüfung abgeschaltet (KILOWATCH_VERIFY=0)." >&2
    compose pull kilowatch
    return
  fi
  set -- verify "$image" --certificate-oidc-issuer "$SIGNER_ISSUER" --certificate-identity-regexp "$SIGNER_IDENTITY"
  errors=$(mktemp)
  if command -v cosign >/dev/null 2>&1; then
    result=$(cosign "$@" 2>"$errors") || status=$?
  else
    result=$(docker run --rm "$COSIGN_IMAGE" "$@" 2>"$errors") || status=$?
  fi
  digest=$(printf '%s' "${result:-}" | grep -o '"docker-manifest-digest":"sha256:[0-9a-f]\{64\}"' | head -n 1 | grep -o 'sha256:[0-9a-f]*' || true)
  if [ "${status:-0}" != 0 ] || [ -z "$digest" ]; then
    cat "$errors" >&2; rm -f "$errors"
    echo "Signatur von $image ungültig oder nicht prüfbar. Update abgebrochen; der laufende Container bleibt unverändert." >&2
    echo "Nur wenn bewusst gewollt (z. B. eigenes Image): KILOWATCH_VERIFY=0 in .env setzen." >&2
    exit 1
  fi
  rm -f "$errors"
  repository=${image%@*}; repository=${repository%:*}
  # Genau den geprüften Digest laden und lokal unter dem gewohnten Tag ablegen.
  docker pull ${PLATFORM:+--platform "$PLATFORM"} "$repository@$digest"
  docker tag "$repository@$digest" "${image%@*}"
  echo "Signatur geprüft: $repository@$digest"
}

before=$(compose images -q kilowatch 2>/dev/null || true)
pull_verified
[ "${1:-}" = --pull-only ] && exit 0
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
