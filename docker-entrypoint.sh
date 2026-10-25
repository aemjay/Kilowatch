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
      chown -R "$PUID:$PGID" "$dir"
    fi
  done
  chmod 700 "$SECRETS_DIR"
  exec setpriv --reuid "$PUID" --regid "$PGID" --clear-groups --inh-caps=-all -- "$@"
fi

exec "$@"
