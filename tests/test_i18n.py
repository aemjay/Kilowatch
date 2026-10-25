import importlib.util
import json
from pathlib import Path
import re

import pytest

from app.i18n import LANGUAGES, UserError, translate, translate_error

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("i18n_extract", ROOT / "tools" / "i18n_extract.py")
extract = importlib.util.module_from_spec(spec)
spec.loader.exec_module(extract)
KEYS = extract.keys()
PLACEHOLDER = re.compile(r"\{(\w+)\}")


def catalog(language):
    return json.loads((ROOT / "app/static/i18n" / f"{language}.json").read_text(encoding="utf-8"))


def forms(value):
    return list(value.values()) if isinstance(value, dict) else [value]


def test_every_language_has_a_catalog():
    assert set(LANGUAGES) == {"de", *extract.LANGUAGES}


@pytest.mark.parametrize("language", extract.LANGUAGES)
def test_catalog_covers_exactly_the_source_texts(language):
    data = catalog(language)
    assert sorted(set(KEYS) - set(data)) == []
    assert sorted(set(data) - set(KEYS)) == []


@pytest.mark.parametrize("language", extract.LANGUAGES)
def test_translations_keep_placeholders_units_and_plain_text(language):
    for key, value in catalog(language).items():
        if isinstance(value, dict):
            assert "{count}" in key and set(value) <= {"zero", "one", "two", "few", "many", "other"} and "other" in value, key
        for text in forms(value):
            assert isinstance(text, str) and text.strip(), key
            assert set(PLACEHOLDER.findall(text)) == set(PLACEHOLDER.findall(key)), (key, text)
            assert not re.search(r"[<>]", text), (key, text)
            # Währungen tauscht die Oberfläche zur Laufzeit über € und ct aus.
            assert not re.search(r"\b(kr|øre|öre|NOK|SEK|EUR|cents?)\b", text), (key, text)
            if key.isupper():
                assert text == text.upper(), (key, text)
            assert text.startswith(" ") == key.startswith(" ") and text.endswith(" ") == key.endswith(" "), (key, text)


def test_interface_has_no_untranslated_german_texts():
    assert extract.untranslated() == []


def test_server_messages_are_translated_with_parameters_and_currency():
    assert translate("Bitte anmelden.", "en") != "Bitte anmelden."
    assert translate("Bitte anmelden.", "de") == "Bitte anmelden."
    assert translate("Bitte anmelden.", "xx") == "Bitte anmelden."
    error = UserError("Zeile {index}: UTC-Offset, Viertelstundengrenzen oder Preis ungültig.", index=3)
    assert str(error).startswith("Zeile 3:")
    english = translate_error(error, "en")
    assert "3" in english and english != str(error)
    budget = "In diesem Monat sind bereits mindestens {spent} € erfasst. Eingestelltes Budget: {budget} €. Fehlende Daten oder Preise können weitere Kosten enthalten."
    assert "kr" in translate(budget, "nb", "NOK", spent="1,00", budget="2,00") and "€" not in translate(budget, "nb", "NOK", spent="1", budget="2")
    assert translate("{count} Lücke(n)", "de", count=1) == "1 Lücke" and translate("{count} Lücke(n)", "de", count=2) == "2 Lücken"
    assert translate("Unbekannter Text {x}", "sv", x=5) == "Unbekannter Text 5"


def test_api_errors_follow_the_requested_language(client):
    assert client.get("/api/settings", headers={"X-Kilowatch-Language": "en"}).json()["detail"] == translate("Bitte anmelden.", "en")
    assert client.get("/api/settings").json()["detail"] == "Bitte anmelden."


def test_language_and_currency_settings_are_validated_and_stored(authenticated):
    assert authenticated.get("/api/settings").json()["language"] == ""
    assert authenticated.put("/api/settings", json={"language": "xx"}).status_code in (400, 422)
    assert authenticated.put("/api/settings", json={"currency": "USD"}).status_code in (400, 422)
    assert authenticated.put("/api/settings", json={"language": "sv", "currency": "SEK"}).status_code == 200
    saved = authenticated.get("/api/settings").json()
    assert (saved["language"], saved["currency"]) == ("sv", "SEK")
    # Ohne Kopfzeile gilt die gespeicherte Sprache, z. B. für Fehlermeldungen.
    response = authenticated.put("/api/settings", json={"bridge_host": "http://x/"})
    assert response.status_code in (400, 422)


def test_notifications_use_the_stored_language(authenticated):
    notifier = authenticated.app.state.notifier
    authenticated.app_store.update_settings({"language": "en", "currency": "NOK"})
    assert notifier.text("Testnachricht") == translate("Testnachricht", "en")
    body = "In diesem Monat sind bereits mindestens {spent} € erfasst. Eingestelltes Budget: {budget} €. Fehlende Daten oder Preise können weitere Kosten enthalten."
    text = notifier.text(body, spent=(12.5, 2), budget=(100, 2))
    assert "12.50" in text and "100.00" in text and "kr" in text and "€" not in text
    authenticated.app_store.update_settings({"language": "de", "currency": "EUR"})
    assert "12,50 €" in notifier.text(body, spent=(12.5, 2), budget=(100, 2))
