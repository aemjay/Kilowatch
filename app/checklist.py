"""Offene Einrichtungsschritte für die Übersicht. Prüft nur vorhandene Daten, ruft nichts aus dem Internet ab."""
import time

KEYS = ("tariff", "price_source", "notifications", "backup", "update")
# Ohne erfolgreichen Preisabruf seit dieser Zeit gilt die Preisquelle als gestört (stündlicher Abruf + Puffer).
PRICE_STALE_SECONDS = 26 * 3600
BACKUP_MAX_AGE = 8 * 86400


def newest_backup(store):
    """Zeitpunkt der jüngsten täglichen Sicherung im Sicherungsordner oder None."""
    stamps = []
    for path in (store.directory / "backups").glob("kilowatch-*.sqlite3"):
        try:
            stamps.append(path.stat().st_mtime)
        except OSError:
            pass
    return max(stamps, default=None)


def open_items(store, notifier, feed, updates, demo=False, now=None):
    now = time.time() if now is None else now
    items = []
    tariffs = store.rows("SELECT mode FROM tariffs")
    if not tariffs:
        items.append({"key": "tariff", "page": "costs", "title": "Kein Tarif hinterlegt",
                      "text": "Ohne Arbeits- und Grundpreis zeigt Kilowatch keine Kosten."})
    if any(row["mode"] == "dynamic" for row in tariffs):
        config, status = feed.config(), feed.status()
        succeeded = status.get("succeeded_at") or (status.get("fetched_at") if not status.get("error") else None)
        if not config["source"]:
            items.append({"key": "price_source", "page": "costs", "title": "Dynamischer Tarif ohne Preisquelle",
                          "text": "Preisquelle wählen oder Preise per CSV importieren; ohne Preise bleibt Energie unbepreist."})
        elif (succeeded is None and status.get("error")) or (succeeded is not None and now - succeeded > PRICE_STALE_SECONDS):
            items.append({"key": "price_source", "page": "costs", "title": "Preisabruf gestört",
                          "text": "Seit mehr als 26 Stunden ist kein Preisabruf gelungen. Fehlermeldung unter Kosten & Tarife prüfen."})
    mail = notifier.config()
    if not (mail.enabled and mail.email_enabled and mail.smtp_host and mail.email_to):
        items.append({"key": "notifications", "page": "notifications", "title": "E-Mail-Benachrichtigungen aus",
                      "text": "Ohne E-Mail erfährst du nicht, wenn die Messung ausfällt."})
    newest = newest_backup(store)
    if newest is None or now - newest > BACKUP_MAX_AGE:
        items.append({"key": "backup", "page": "system", "title": "Keine aktuelle Sicherung",
                      "text": "Im Sicherungsordner liegt keine Sicherung der letzten acht Tage. Speicherplatz und Schreibrechte prüfen."})
    release = updates.status()
    if release.get("available"):
        items.append({"key": "update", "page": "system", "title": "Update verfügbar",
                      "text": "Version {version} ist erschienen. Hinweise unter System & Datenqualität.", "params": {"version": release["latest"]}})
    elif demo:
        items.append({"key": "update", "page": "system", "title": "Update verfügbar",
                      "text": "Beispiel im Demo-Modus: Hier erscheint ein Hinweis, sobald die Update-Prüfung eine neue Version findet."})
    return items


def checklist(store, notifier, feed, updates, demo=False, now=None):
    muted = [key for key in store.state("checklist_muted", []) if key in KEYS]
    items = open_items(store, notifier, feed, updates, demo, now)
    return {"items": [item for item in items if item["key"] not in muted], "muted": muted,
            "muted_open": sum(item["key"] in muted for item in items)}
