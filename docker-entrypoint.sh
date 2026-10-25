#!/bin/sh
# Startet als root nur, um die Eigentümer der eingebundenen Ordner zu setzen,
# und führt die App danach ohne Root-Rechte und ohne Capabilities aus.
set -eu

PUID=${PUID:-10001}
PGID=${PGID:-10001}
case "$PUID$PGID" in
  *[!0-9]*|"") echo "PUID und PGID müssen Zahlen sein." >&2; exit 1 ;;
esac
if [ "$PUID" = 0 ] || [ "$PGID" = 0 ]; then
  echo "PUID/PGID 0 (root) ist nicht erlaubt." >&2
  exit 1
fi

if [ "$(id -u)" = 0 ]; then
  for dir in "$DATA_DIR" "$SECRETS_DIR"; do
    mkdir -p "$dir"
    # Nur bei abweichendem Eigentümer rekursiv anpassen, sonst bleibt der Start schnell.
    if [ "$(stat -c %u:%g "$dir")" != "$PUID:$PGID" ]; then
      chown -R "$PUID:$PGID" "$dir" 2>/dev/null || echo "Hinweis: Eigentümer von $dir ließ sich nicht vollständig setzen." >&2
    fi
  done
  chmod 700 "$SECRETS_DIR"
  # Synology-ACLs können Zugriff trotz passendem Eigentümer verweigern: als Ziel-Benutzer wirklich schreiben.
  for dir in "$DATA_DIR" "$SECRETS_DIR"; do
    if ! setpriv --reuid "$PUID" --regid "$PGID" --clear-groups -- sh -c 'probe="$1/.kilowatch-write-test" && : > "$probe" && rm -f "$probe"' sh "$dir" 2>/dev/null; then
      echo "Kilowatch kann nicht in $dir schreiben (Benutzer-ID $PUID, Gruppen-ID $PGID)." >&2
      echo "Synology: Ordner data im Projektordner anlegen, PUID/PGID in der .env auf einen DSM-Benutzer setzen" >&2
      echo "und diesem Benutzer in der File Station unter Eigenschaften → Berechtigung Lesen/Schreiben geben." >&2
      echo "Anleitung: docs/INSTALLATION-SYNOLOGY.md, Abschnitt 1." >&2
      exit 1
    fi
  done
  exec setpriv --reuid "$PUID" --regid "$PGID" --clear-groups --inh-caps=-all -- "$@"
fi

exec "$@"
