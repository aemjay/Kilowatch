#!/bin/sh
# Kilowatch installieren und aktualisieren: ein Skript für beides.
#
# Erstinstallation (als root oder mit sudo; der Dateibesitzer wird mit --user bestimmt):
#   curl -fsSLO https://github.com/aemjay/Kilowatch/releases/latest/download/update.sh
#   sudo sh update.sh --user <benutzer>
# Update (SSH oder Aufgabenplaner, z. B. wöchentlich):
#   sudo sh <projektordner>/tools/update.sh
#
# Das Skript
#   1. aktualisiert sich selbst und gleicht compose.yaml mit dem Release ab,
#   2. prüft die Signatur des Images (cosign) und lädt genau den geprüften Digest,
#   3. startet den Container nur bei einer neuen Version neu und wartet auf den Healthcheck,
#   4. rollt bei einem Fehlstart automatisch auf das vorherige Image zurück.
# Es fragt nie nach Eingaben und ist deshalb für den Aufgabenplaner geeignet.
#
# Optionen:
#   --dir PFAD       Projektordner (Standard: der Ordner dieses Skripts, sonst /volume1/docker/kilowatch
#                    auf Synology bzw. /opt/kilowatch)
#   --user NAME      Benutzer, dem data gehört (nur bei der Erstinstallation als root nötig)
#   --port PORT      HTTP-Port der Oberfläche (wird in .env gespeichert)
#   --version X.Y.Z  feste Version; "latest" hebt die Festlegung auf (neueste 1.x)
#   --no-start       nur vorbereiten und Image prüfen/laden, nicht starten
#   --source PFAD    Release-Dateien (compose.yaml, update.sh, env.example) aus einem lokalen Ordner statt von GitHub
set -eu

REPO=${KILOWATCH_REPOSITORY:-aemjay/Kilowatch}
# Fest gepinntes cosign-Image, falls cosign nicht installiert ist.
COSIGN_IMAGE=ghcr.io/sigstore/cosign/cosign:v3.1.4@sha256:0f06154836d2de34f887a5c273506d52ca43edaa1d9e53e6510fa78a48f69c2d
SIGNER_ISSUER=https://token.actions.githubusercontent.com
SIGNER_IDENTITY=${KILOWATCH_SIGNER:-'^https://github\.com/aemjay/Kilowatch/\.github/workflows/nas-image\.yml@refs/(heads/main|tags/v[0-9]+\.[0-9]+\.[0-9]+)$'}
HEALTH_TRIES=${KILOWATCH_HEALTH_TRIES:-60}
HEALTH_INTERVAL=${KILOWATCH_HEALTH_INTERVAL:-5}

DIR=""
OWNER=${SUDO_USER:-}
PORT=""
VERSION=""
START=1
SOURCE=""

fail() { echo "Fehler: $*" >&2; exit 1; }
info() { echo "• $*"; }

while [ $# -gt 0 ]; do
  case "$1" in
    --dir) DIR=${2:-}; shift 2 ;;
    --user) OWNER=${2:-}; shift 2 ;;
    --port) PORT=${2:-}; shift 2 ;;
    --version) VERSION=${2:-}; shift 2 ;;
    --no-start) START=0; shift ;;
    --source) SOURCE=${2:-}; shift 2 ;;
    -h|--help) sed -n '2,27p' "$0"; exit 0 ;;
    *) fail "Unbekannte Option $1 (Hilfe: --help)" ;;
  esac
done

SELF=$0
SELF_DIR=$(CDPATH= cd -- "$(dirname -- "$SELF")" && pwd)
if [ -z "$DIR" ]; then
  if [ "$(basename "$SELF_DIR")" = tools ] && [ -f "$SELF_DIR/../compose.yaml" ]; then
    DIR=$(CDPATH= cd -- "$SELF_DIR/.." && pwd)
  elif [ -d /volume1 ]; then
    DIR=/volume1/docker/kilowatch
  else
    DIR=/opt/kilowatch
  fi
fi
case "$DIR" in /*) ;; *) fail "Projektordner als absoluten Pfad angeben." ;; esac
case "$PORT" in *[!0-9]*) fail "Port muss eine Zahl sein." ;; esac
[ -z "$VERSION" ] || [ "$VERSION" = latest ] || echo "$VERSION" | grep -Eq '^[0-9]+\.[0-9]+\.[0-9]+$' || fail "Version im Format 1.2.3 angeben."
command -v docker >/dev/null || fail "Docker fehlt. Auf Synology zuerst den Container Manager installieren."
docker compose version >/dev/null 2>&1 || fail "docker compose fehlt. Docker bzw. Container Manager aktualisieren."

FRESH=0
[ -f "$DIR/compose.yaml" ] || FRESH=1
if [ "$FRESH" = 1 ]; then
  if [ "$(id -u)" = 0 ]; then
    [ -n "$OWNER" ] || fail "Mit --user <Benutzer> angeben, wem die Daten gehören sollen."
    [ "$OWNER" != root ] || fail "Bitte einen normalen Benutzer angeben, nicht root."
    uid=$(id -u "$OWNER" 2>/dev/null) || fail "Benutzer $OWNER existiert nicht."
    gid=$(id -g "$OWNER")
  else
    OWNER=$(id -un)
  fi
fi

mkdir -p "$DIR/data" "$DIR/tools"
cd "$DIR"

env_value() { [ -f .env ] && sed -n "s/^$1=//p" .env | tail -n 1 || true; }
set_env() {
  # $1 Schlüssel, $2 Wert; ersetzt die Zeile oder hängt sie an.
  if grep -q "^$1=" .env 2>/dev/null; then
    sed "s|^$1=.*|$1=$2|" .env > .env.tmp && mv .env.tmp .env
  else
    printf '%s=%s\n' "$1" "$2" >> .env
  fi
}
sum_of() { sha256sum "$1" | cut -d' ' -f1; }
stamp() { date +%Y%m%d-%H%M%S; }

# Release, aus dem Dateien geholt werden: festgelegte Version, sonst das neueste Release.
[ -n "$VERSION" ] || VERSION=$(env_value KILOWATCH_VERSION)
CLEAR_VERSION=0
[ "$VERSION" != latest ] || { VERSION=""; CLEAR_VERSION=1; }
if [ -n "$VERSION" ]; then release="download/v$VERSION"; else release="latest/download"; fi

get() {
  # $1 Dateiname im Release bzw. Quellordner, $2 Ziel
  if [ -n "$SOURCE" ]; then
    cp "$SOURCE/$1" "$2"
  else
    curl -fsSL "https://github.com/$REPO/releases/$release/$1" -o "$2"
  fi
}

if grep -Eq '^[[:space:]]+build:' compose.yaml 2>/dev/null; then
  echo "compose.yaml baut das Image selbst. Updates hier: neue Quellen kopieren und neu bauen." >&2
  echo "Dieses Skript gilt nur für das fertige Image (compose.yaml aus dem Release)." >&2
  exit 1
fi

# Selbstaktualisierung: Weiter mit der Fassung aus dem Release, falls sie von dieser abweicht.
if [ -z "${KILOWATCH_REEXEC:-}" ]; then
  if get update.sh tools/update.sh.download 2>/dev/null; then
    changed=0
    cmp -s tools/update.sh.download "$SELF" || changed=1
    chmod 755 tools/update.sh.download
    mv tools/update.sh.download tools/update.sh
    if [ "$changed" = 1 ]; then
      [ "$FRESH" = 1 ] || info "Aktualisierungsskript auf die Fassung des Releases gebracht."
      set -- --dir "$DIR"
      [ -z "$OWNER" ] || set -- "$@" --user "$OWNER"
      [ -z "$PORT" ] || set -- "$@" --port "$PORT"
      [ -z "$VERSION" ] || set -- "$@" --version "$VERSION"
      [ "$CLEAR_VERSION" = 0 ] || set -- "$@" --version latest
      [ "$START" = 1 ] || set -- "$@" --no-start
      [ -z "$SOURCE" ] || set -- "$@" --source "$SOURCE"
      KILOWATCH_REEXEC=1 exec sh "$DIR/tools/update.sh" "$@"
    fi
  else
    rm -f tools/update.sh.download
    echo "Hinweis: Neueste Fassung des Skripts nicht erreichbar; es läuft die vorhandene." >&2
  fi
fi

# compose.yaml mit dem Release abgleichen. Selbst geänderte Dateien bleiben unangetastet.
get compose.yaml compose.yaml.download || fail "Download von compose.yaml fehlgeschlagen. Internetzugang prüfen."
new=$(sum_of compose.yaml.download)
if [ ! -f compose.yaml ]; then
  mv compose.yaml.download compose.yaml
  echo "$new" > .compose.sha256
  info "compose.yaml angelegt."
else
  current=$(sum_of compose.yaml)
  recorded=$(cat .compose.sha256 2>/dev/null || true)
  if [ "$current" = "$new" ]; then
    rm compose.yaml.download
    echo "$new" > .compose.sha256
  elif [ -z "$recorded" ] || [ "$current" = "$recorded" ]; then
    cp compose.yaml "compose.yaml.bak-$(stamp)"
    mv compose.yaml.download compose.yaml
    echo "$new" > .compose.sha256
    info "compose.yaml auf die Fassung des Releases gebracht (bisherige gesichert als compose.yaml.bak-*)."
  elif [ "$new" != "$recorded" ]; then
    mv compose.yaml.download compose.yaml.new
    echo "Warnung: Deine compose.yaml wurde geändert, das Release bringt eine neue Fassung." >&2
    echo "         Sie liegt als compose.yaml.new im Projektordner; Änderungen bitte selbst übernehmen." >&2
  else
    rm compose.yaml.download
  fi
fi
get env.example .env.example || true

if [ ! -f .env ]; then
  sed -e "s/^KILOWATCH_VERSION=.*/KILOWATCH_VERSION=$VERSION/" .env.example > .env
  info ".env angelegt."
fi
[ -z "$PORT" ] || set_env HTTP_PORT "$PORT"
if [ -n "$VERSION" ] && [ "$(env_value KILOWATCH_VERSION)" != "$VERSION" ]; then set_env KILOWATCH_VERSION "$VERSION"; fi
[ "$CLEAR_VERSION" = 0 ] || set_env KILOWATCH_VERSION ""

if [ "$FRESH" = 1 ] && [ "$(id -u)" = 0 ]; then
  # Der Eigentümer von data bestimmt, unter welchem Benutzer die App läuft.
  chown "$uid:$gid" data
  if command -v synoacltool >/dev/null 2>&1; then
    # Synology-ACL: dem Benutzer ausdrücklich Lesen/Schreiben geben, vererbt auf neue Dateien.
    synoacltool -add data "user:$OWNER:allow:rwxpdDaARWcCo:fd--" >/dev/null 2>&1 \
      || echo "Hinweis: ACL nicht gesetzt. Falls der Start scheitert, in der File Station $OWNER Lesen/Schreiben auf data geben." >&2
  fi
  info "Daten gehören $OWNER (Benutzer-ID $uid)."
fi

VERIFY=${KILOWATCH_VERIFY:-$(env_value KILOWATCH_VERIFY)}
PLATFORM=${KILOWATCH_PLATFORM:-$(env_value KILOWATCH_PLATFORM)}
compose() { docker compose -f compose.yaml "$@"; }

pull_verified() {
  IMAGE=$(compose config --images | grep -m 1 -i kilowatch) || fail "Image in compose.yaml nicht gefunden."
  if [ "$VERIFY" = 0 ]; then
    echo "Warnung: Signaturprüfung abgeschaltet (KILOWATCH_VERIFY=0)." >&2
    compose pull kilowatch
    return
  fi
  set -- verify "$IMAGE" --certificate-oidc-issuer "$SIGNER_ISSUER" --certificate-identity-regexp "$SIGNER_IDENTITY"
  errors=$(mktemp)
  status=0
  if command -v cosign >/dev/null 2>&1; then
    result=$(cosign "$@" 2>"$errors") || status=$?
  else
    result=$(docker run --rm "$COSIGN_IMAGE" "$@" 2>"$errors") || status=$?
  fi
  digest=$(printf '%s' "${result:-}" | grep -o '"docker-manifest-digest":"sha256:[0-9a-f]\{64\}"' | head -n 1 | grep -o 'sha256:[0-9a-f]*' || true)
  if [ "$status" != 0 ] || [ -z "$digest" ]; then
    cat "$errors" >&2; rm -f "$errors"
    echo "Signatur von $IMAGE ungültig oder nicht prüfbar. Abgebrochen; der laufende Container bleibt unverändert." >&2
    echo "Nur wenn bewusst gewollt (z. B. eigenes Image): KILOWATCH_VERIFY=0 in .env setzen." >&2
    exit 1
  fi
  rm -f "$errors"
  repository=${IMAGE%@*}; repository=${repository%:*}
  # Genau den geprüften Digest laden und lokal unter dem gewohnten Tag ablegen.
  docker pull ${PLATFORM:+--platform "$PLATFORM"} "$repository@$digest"
  docker tag "$repository@$digest" "${IMAGE%@*}"
  echo "Signatur geprüft: $repository@$digest"
}

wait_healthy() {
  container=$(compose ps -q kilowatch)
  i=0
  while [ "$i" -lt "$HEALTH_TRIES" ]; do
    state=$(docker inspect -f '{{.State.Health.Status}}' "$container" 2>/dev/null || echo unknown)
    [ "$state" = healthy ] && return 0
    i=$((i + 1))
    sleep "$HEALTH_INTERVAL"
  done
  return 1
}

before=$(compose images -q kilowatch 2>/dev/null || true)
info "Image prüfen und laden …"
pull_verified
if [ "$START" = 0 ]; then
  info "Vorbereitet. Start: cd $DIR && docker compose up -d"
  exit 0
fi
compose up -d kilowatch
after=$(compose images -q kilowatch)

if [ "$FRESH" = 0 ] && [ "$before" = "$after" ]; then
  echo "Kilowatch ist aktuell."
  exit 0
fi

# Eine Datenbank-Migration legt vor der Änderung selbst eine Sicherung an.
if ! wait_healthy; then
  compose logs --tail=40 kilowatch >&2 || true
  if [ -n "$before" ]; then
    echo "Kilowatch ist nach dem Update nicht gesund. Rolle auf das vorherige Image zurück …" >&2
    docker tag "$before" "${IMAGE%@*}"
    compose up -d kilowatch
    if wait_healthy; then
      echo "Zurückgerollt: Die vorherige Version läuft wieder. Protokoll prüfen und Fehler melden." >&2
    else
      echo "Auch die vorherige Version startet nicht. Falls das Update die Datenbank geändert hat: Sicherung" >&2
      echo "data/live/backups/pre-migration-*.sqlite3 zurückspielen (docs/UPDATES.md)." >&2
    fi
  else
    echo "Kilowatch startet nicht. Protokoll oben prüfen." >&2
  fi
  exit 1
fi

docker image prune -f --filter "label=org.opencontainers.image.title=Kilowatch" >/dev/null 2>&1 || true
version=$(docker inspect -f '{{index .Config.Labels "org.opencontainers.image.version"}}' "$container" 2>/dev/null || true)
if [ "$FRESH" = 1 ]; then
  port=$(env_value HTTP_PORT); port=${port:-8088}
  address=$(ip -4 route get 1.1.1.1 2>/dev/null | sed -n 's/.* src \([0-9.]*\).*/\1/p')
  echo
  echo "Kilowatch ${version:+$version }läuft: http://${address:-<Adresse dieses Geräts>}:$port"
  if [ -f data/SETUP-CODE.txt ]; then
    sed -n '1p' data/SETUP-CODE.txt
    echo "(Der Code steht auch in $DIR/data/SETUP-CODE.txt und verschwindet nach der Einrichtung.)"
  else
    echo "Bereits eingerichtet – mit dem bisherigen App-Passwort anmelden."
  fi
else
  echo "Kilowatch aktualisiert${version:+: $version}"
fi
