#!/bin/sh
# Kilowatch installieren oder die Compose-Datei auf den neuesten Release-Stand bringen.
#
# Als root ausführen, entweder per SSH:
#   curl -fsSLO https://github.com/aemjay/Kilowatch/releases/latest/download/install.sh
#   sudo sh install.sh
# oder einmalig im DSM-Aufgabenplaner (Benutzer: root), dann mit --user <DSM-Benutzer>.
#
# Optionen:
#   --user NAME     DSM-Benutzer, dem die Daten gehören (Standard: wer sudo aufruft)
#   --dir PFAD      Projektordner (Standard: /volume1/docker/kilowatch)
#   --port PORT     HTTP-Port der Oberfläche (Standard: 8088)
#   --version X.Y.Z feste Version statt neuester 1.x
#   --no-start      nur vorbereiten, nicht starten
#   --source PFAD   Release-Dateien (compose.yaml, update.sh, env.example) aus einem lokalen Ordner statt von GitHub
set -eu

REPO=${KILOWATCH_REPOSITORY:-aemjay/Kilowatch}
DIR=/volume1/docker/kilowatch
OWNER=${SUDO_USER:-}
PORT=8088
VERSION=""
START=1
SOURCE=""

fail() { echo "Fehler: $*" >&2; exit 1; }
info() { echo "• $*"; }

while [ $# -gt 0 ]; do
  case "$1" in
    --user) OWNER=${2:-}; shift 2 ;;
    --dir) DIR=${2:-}; shift 2 ;;
    --port) PORT=${2:-}; shift 2 ;;
    --version) VERSION=${2:-}; shift 2 ;;
    --no-start) START=0; shift ;;
    --source) SOURCE=${2:-}; shift 2 ;;
    -h|--help) sed -n '2,17p' "$0"; exit 0 ;;
    *) fail "Unbekannte Option $1 (Hilfe: --help)" ;;
  esac
done

[ "$(id -u)" = 0 ] || fail "Bitte als root ausführen (sudo sh install.sh oder Aufgabenplaner mit Benutzer root)."
case "$PORT" in ''|*[!0-9]*) fail "Port muss eine Zahl sein." ;; esac
[ -z "$VERSION" ] || echo "$VERSION" | grep -Eq '^[0-9]+\.[0-9]+\.[0-9]+$' || fail "Version im Format 1.2.3 angeben."
case "$DIR" in /*) ;; *) fail "Projektordner als absoluten Pfad angeben." ;; esac
[ -n "$OWNER" ] || fail "Mit --user <DSM-Benutzer> angeben, wem die Daten gehören sollen (im Aufgabenplaner erforderlich)."
[ "$OWNER" != root ] || fail "Bitte einen normalen DSM-Benutzer angeben, nicht root."
uid=$(id -u "$OWNER" 2>/dev/null) || fail "DSM-Benutzer $OWNER existiert nicht."
gid=$(id -g "$OWNER")
command -v docker >/dev/null || fail "Docker fehlt. Auf Synology zuerst den Container Manager installieren."
docker compose version >/dev/null 2>&1 || fail "docker compose fehlt. Container Manager aktualisieren."

if [ -n "$VERSION" ]; then release="download/v$VERSION"; else release="latest/download"; fi
fetch() {
  # $1 Dateiname im Release bzw. im Quellordner, $2 Ziel
  tmp="$2.download"
  if [ -n "$SOURCE" ]; then
    cp "$SOURCE/$1" "$tmp" || fail "$1 fehlt in $SOURCE."
  else
    curl -fsSL "https://github.com/$REPO/releases/$release/$1" -o "$tmp" || fail "Download von $1 fehlgeschlagen. Internetzugang prüfen."
  fi
  if [ -f "$2" ] && ! cmp -s "$tmp" "$2"; then
    cp "$2" "$2.bak-$(date +%Y%m%d-%H%M%S)"
    info "Bisherige $(basename "$2") gesichert."
  fi
  mv "$tmp" "$2"
}

info "Projektordner $DIR"
mkdir -p "$DIR/data" "$DIR/tools"
fetch compose.yaml "$DIR/compose.yaml"
fetch update.sh "$DIR/tools/update.sh"
fetch env.example "$DIR/.env.example"
chmod 755 "$DIR/tools/update.sh"

if [ ! -f "$DIR/.env" ]; then
  sed -e "s/^HTTP_PORT=.*/HTTP_PORT=$PORT/" -e "s/^KILOWATCH_VERSION=.*/KILOWATCH_VERSION=$VERSION/" "$DIR/.env.example" > "$DIR/.env"
  info ".env angelegt (Port $PORT)."
fi

# Der Eigentümer von data bestimmt, unter welchem Benutzer die App läuft.
chown "$uid:$gid" "$DIR/data"
if command -v synoacltool >/dev/null 2>&1; then
  # Synology-ACL: dem Benutzer ausdrücklich Lesen/Schreiben geben, vererbt auf neue Dateien.
  synoacltool -add "$DIR/data" "user:$OWNER:allow:rwxpdDaARWcCo:fd--" >/dev/null 2>&1 \
    || echo "Hinweis: ACL nicht gesetzt. Falls der Start scheitert, in der File Station $OWNER Lesen/Schreiben auf data geben." >&2
fi
info "Daten gehören $OWNER (Benutzer-ID $uid)."

if [ "$START" = 0 ]; then
  info "Vorbereitet. Start: cd $DIR && docker compose up -d"
  exit 0
fi

cd "$DIR"
info "Image laden und starten …"
docker compose up -d
state=unknown
for i in $(seq 1 60); do
  state=$(docker inspect -f '{{.State.Health.Status}}' kilowatch 2>/dev/null || echo unknown)
  [ "$state" = healthy ] && break
  sleep 3
done
[ "$state" = healthy ] || { docker compose logs --tail=30 kilowatch >&2 || true; fail "Kilowatch startet nicht. Protokoll oben prüfen."; }

address=$(ip -4 route get 1.1.1.1 2>/dev/null | sed -n 's/.* src \([0-9.]*\).*/\1/p')
echo
echo "Kilowatch läuft: http://${address:-<NAS-Adresse>}:$PORT"
if [ -f "$DIR/data/SETUP-CODE.txt" ]; then
  sed -n '1p' "$DIR/data/SETUP-CODE.txt"
  echo "(Der Code steht auch in $DIR/data/SETUP-CODE.txt und verschwindet nach der Einrichtung.)"
else
  echo "Bereits eingerichtet – mit dem bisherigen App-Passwort anmelden."
fi
