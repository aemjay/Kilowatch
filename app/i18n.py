"""Serverseitige Übersetzungen mit denselben Katalogen wie die Oberfläche (app/static/i18n).

Der deutsche Quelltext ist der Schlüssel. Fehlt eine Übersetzung, gilt Englisch, dann Deutsch.
"""
from functools import lru_cache
import json
from pathlib import Path
import re

LANGUAGES = ("de", "en", "nb", "sv", "nl")
CURRENCIES = {"EUR": ("€", "ct"), "NOK": ("kr", "øre"), "SEK": ("kr", "öre")}
CATALOGS = Path(__file__).parent / "static" / "i18n"
# Gleiche Mehrzahlregeln wie Intl.PluralRules für die unterstützten Sprachen: one bei genau 1.
DE_PLURALS = {"{count} Lücke(n)": {"one": "{count} Lücke", "other": "{count} Lücken"},
              "Letzte {count} Std.": {"one": "Letzte Stunde", "other": "Letzte {count} Std."}}


def _(text):
    """Markiert Quelltexte für die Extraktion; übersetzt wird beim Ausliefern."""
    return text


class UserError(ValueError):
    """Meldung für die Oberfläche mit Platzhaltern, damit sie übersetzbar bleibt."""

    def __init__(self, template, **params):
        self.template, self.params = template, params
        super().__init__(format_text(template, params))


@lru_cache(maxsize=None)
def catalog(language):
    path = CATALOGS / f"{language}.json"
    if language == "de" or not path.is_file():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def format_text(template, params):
    return re.sub(r"\{(\w+)\}", lambda m: str(params[m.group(1)]) if m.group(1) in params else m.group(0), template)


def translate(text, language="de", currency="EUR", **params):
    language = language if language in LANGUAGES else "de"
    value = catalog(language).get(text) or catalog("en").get(text) if language != "de" else None
    value = value or DE_PLURALS.get(text) or text
    if isinstance(value, dict):
        value = value["one"] if params.get("count") == 1 and "one" in value else value.get("other", text)
    result = format_text(value, params)
    symbol, sub = CURRENCIES.get(currency, CURRENCIES["EUR"])
    if currency != "EUR":
        result = re.sub(r"\bct\b", sub, result.replace("€", symbol))
    return result


def translate_error(error, language="de", currency="EUR"):
    if isinstance(error, UserError):
        return translate(error.template, language, currency, **error.params)
    return translate(str(error), language, currency)
