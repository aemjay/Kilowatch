#!/bin/sh
# Startet als root nur, um Benutzer und Eigentümer der eingebundenen Ordner festzulegen,
# und führt die App danach ohne Root-Rechte und ohne Capabilities aus.
set -eu

if [ "$(id -u)" != 0 ]; then
  exec "$@"
fi

mkdir -p "$DATA_DIR" "$SECRETS_DIR"

# Benutzer bestimmen: ausdrücklich gesetzt > Eigentümer des Datenordners > 10001.
# Wer data/ in der File Station anlegt, ist dessen Eigentümer und hat dort laut ACL Zugriff;
# so braucht es auf Synology weder PUID/PGID noch eine eigene Berechtigung.
owner_uid=$(stat -c %u "$DATA_DIR")
owner_gid=$(stat -c %g "$DATA_DIR")
PUID=${PUID:-}
PGID=${PGID:-}
source="PUID/PGID"
if [ -z "$PUID" ]; then
  if [ "$owner_uid" != 0 ]; then
    PUID=$owner_uid
    source="Eigentümer von data"
  else
    PUID=10001
    source="Standard"
  fi
fi
if [ -z "$PGID" ]; then
  if [ "$owner_gid" != 0 ]; then PGID=$owner_gid; else PGID=$PUID; fi
fi
case "$PUID$PGID" in
  *[!0-9]*) echo "PUID und PGID müssen Zahlen sein." >&2; exit 1 ;;
esac
if [ "$PUID" = 0 ] || [ "$PGID" = 0 ]; then
  echo "PUID/PGID 0 (root) ist nicht erlaubt." >&2
  exit 1
fi
echo "Kilowatch läuft als Benutzer-ID $PUID, Gruppen-ID $PGID ($source)."

for dir in "$DATA_DIR" "$DATA_DIR/live" "$SECRETS_DIR"; do
  [ -d "$dir" ] || continue
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
    echo "Synology: den Ordner data im Projektordner selbst in der File Station anlegen (nicht vom Container anlegen lassen)" >&2
    echo "und das Projekt neu starten. Alternativ PUID/PGID in der .env auf einen DSM-Benutzer mit Lese-/Schreibrecht setzen." >&2
    echo "Anleitung: docs/SCHNELLSTART.md" >&2
    exit 1
  fi
done

exec setpriv --reuid "$PUID" --regid "$PGID" --clear-groups --inh-caps=-all -- "$@"
