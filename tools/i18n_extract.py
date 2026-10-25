"""Sammelt alle übersetzbaren Quelltexte (deutsch) aus Oberfläche und Server.

Aufruf: python tools/i18n_extract.py            -> Liste aller Schlüssel (JSON) auf stdout
        python tools/i18n_extract.py --missing  -> je Sprache fehlende und überzählige Schlüssel

Quellen:
- JavaScript: t('…') und tk('…') mit einfachen Anführungszeichen
- index.html: Inhalt von data-i18n-Elementen und data-i18n-*-Attributen
- Python: Meldungen in ValueError/UserError/BridgeError/HTTPException, _('…'), self.text('…'),
  rule(…, Titel, Text), failure(…, Text), Statusmeldungen (message=…) und Antwortfelder
  wie "reason", "method", "title", "text"
"""
import ast
import json
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[1]
STATIC = ROOT / "app" / "static"
CATALOGS = STATIC / "i18n"
LANGUAGES = ("en", "nb", "sv", "nl")
JS_CALL = re.compile(r"(?<![\w$.])tk?\('((?:[^'\\\n]|\\.)*)'")
HTML_TEXT = re.compile(r"<(\w+)[^>]*\bdata-i18n\b(?!-)[^>]*>([^<]*)</\1>")
HTML_ATTR = re.compile(r'data-i18n-(?:placeholder|aria-label|title)="([^"]*)"')
ERRORS = {"ValueError", "UserError", "BridgeError", "HTTPException", "_", "text", "failure", "rule", "translate", "issue"}
FIELDS = {"reason", "method", "title", "text", "message", "forecast_reason"}


def unescape(text):
    return re.sub(r"\\(.)", r"\1", text)


def from_javascript():
    for path in sorted(STATIC.glob("*.js")):
        for match in JS_CALL.finditer(path.read_text(encoding="utf-8")):
            yield unescape(match.group(1))


def from_html():
    html = (STATIC / "index.html").read_text(encoding="utf-8")
    for match in HTML_TEXT.finditer(html):
        yield match.group(2)
    yield from HTML_ATTR.findall(html)


def strings(node):
    """Zeichenketten eines Ausdrucks, auch in Bedingungen (a if x else b)."""
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        yield node.value
    elif isinstance(node, ast.IfExp):
        yield from strings(node.body)
        yield from strings(node.orelse)
    elif isinstance(node, ast.Call) and getattr(node.func, "id", None) == "_":
        yield from strings(node.args[0])


def wanted(text):
    return bool(re.search(r"[A-Za-zÄÖÜäöüß]{2,}", text)) and not text.startswith(("Kilowatch · ", "SELECT", "INSERT", "UPDATE"))


def from_python():
    for path in sorted((ROOT / "app").glob("*.py")):
        if path.name in ("cli.py", "i18n.py"):
            continue
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            if isinstance(node, ast.Call):
                name = getattr(node.func, "id", None) or getattr(node.func, "attr", None)
                if name in ERRORS:
                    for arg in node.args:
                        yield from strings(arg)
                for keyword in node.keywords:
                    if keyword.arg == "message":
                        yield from strings(keyword.value)
            elif isinstance(node, ast.Dict):
                for key, value in zip(node.keys, node.values):
                    if isinstance(key, ast.Constant) and key.value in FIELDS:
                        yield from strings(value)
            elif isinstance(node, ast.Assign) and isinstance(node.targets[0], ast.Subscript):
                key = node.targets[0].slice
                if isinstance(key, ast.Constant) and key.value in FIELDS:
                    yield from strings(node.value)


def keys():
    found = set()
    for text in [*from_javascript(), *from_html(), *from_python()]:
        if wanted(text):
            found.add(text)
    return sorted(found)


def main():
    result = keys()
    if "--missing" in sys.argv:
        for language in LANGUAGES:
            path = CATALOGS / f"{language}.json"
            catalog = json.loads(path.read_text(encoding="utf-8")) if path.is_file() else {}
            missing = [key for key in result if key not in catalog]
            extra = [key for key in catalog if key not in result]
            print(f"{language}: {len(missing)} fehlen, {len(extra)} überzählig")
            for key in missing:
                print("  +", key)
            for key in extra:
                print("  -", key)
        return
    json.dump(result, sys.stdout, ensure_ascii=False, indent=1)
    print()


if __name__ == "__main__":
    main()
