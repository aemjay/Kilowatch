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
# Aufrufname -> Positionen der Meldungen (None = alle Argumente).
CALLS = {"ValueError": None, "UserError": None, "BridgeError": None, "HTTPException": None, "_": None,
         "text": None, "failure": None, "translate": [0], "rule": [2, 3], "issue": [1], "reserve_attempt": [2]}
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
    return bool(re.search(r"[A-Za-zÄÖÜäöüß]{2,}|\bz\. B\.", text)) and not text.startswith(("SELECT", "INSERT", "UPDATE"))


def from_python():
    for path in sorted((ROOT / "app").glob("*.py")):
        if path.name in ("cli.py", "i18n.py"):
            continue
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            if isinstance(node, ast.Call):
                name = getattr(node.func, "id", None) or getattr(node.func, "attr", None)
                if name in CALLS:
                    positions = CALLS[name]
                    for index, arg in enumerate(node.args):
                        if positions is None or index in positions:
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


def js_literals(code):
    """String-Literale und Textstücke von Template-Literalen samt Position und dem Text davor."""
    found, n = [], len(code)

    def quoted(i):
        j = i + 1
        while j < n and code[j] != code[i]:
            j += 2 if code[j] == "\\" else 1
        found.append((code[i + 1:j], i, code[max(0, i - 4):i]))
        return j + 1

    def template(i):
        start, buffer = i, []
        while i < n:
            if code[i] == "\\":
                buffer.append(code[i:i + 2]); i += 2; continue
            if code[i] == "`":
                found.append(("".join(buffer), start, "`")); return i + 1
            if code.startswith("${", i):
                found.append(("".join(buffer), start, "`")); buffer = []
                i = expression(i + 2); start = i; continue
            buffer.append(code[i]); i += 1
        return i

    def expression(i):
        depth = 0
        while i < n:
            c = code[i]
            if c in "'\"":
                i = quoted(i); continue
            if c == "`":
                i = template(i + 1); continue
            if c == "{":
                depth += 1
            elif c == "}":
                if not depth:
                    return i + 1
                depth -= 1
            i += 1
        return i

    i = 0
    while i < n:
        c = code[i]
        if code.startswith("//", i):
            i = code.find("\n", i); i = n if i < 0 else i
        elif c == "/" and not code.startswith("/*", i) and re.match(r"[=(,:!&|?{};\s]", code[i - 1] if i else " "):
            j = i + 1  # Regex-Literal überspringen
            while j < n and code[j] not in "/\n":
                j += 2 if code[j] == "\\" else 1
            i = j + 1
        elif c in "'\"":
            i = quoted(i)
        elif c == "`":
            i = template(i + 1)
        else:
            i += 1
    return found


MARKUP = re.compile(r'="|[<>&]|/api/|hsl\(|prefers-color|#page|#settings|start,end|:not\(')


def untranslated():
    """Deutsch wirkende Texte in JavaScript, die weder in t()/tk() stehen noch Katalogschlüssel sind."""
    known, result = set(keys()), []
    for path in sorted(STATIC.glob("*.js")):
        if path.name == "i18n.js":
            continue
        code = path.read_text(encoding="utf-8")
        for text, position, before in js_literals(code):
            if before != "`" and re.search(r"(?<![\w$.])tk?\($", before):
                continue
            for chunk in re.split(r"<[^>]*>", text) if before == "`" else [text]:
                stripped = chunk.strip()
                if (unescape(chunk) in known or not re.search(r"[A-Za-zÄÖÜäöüß]{3,}", chunk) or MARKUP.search(chunk)
                        or stripped.startswith('"') or (re.fullmatch(r"[\w.#\[\]=:/*,-]+", stripped) and not re.fullmatch(r"[A-ZÄÖÜ]{4,}|[A-ZÄÖÜ][a-zäöüß]{2,}(-[A-ZÄÖÜa-zäöüß]+)*", stripped))
                        or stripped in ("HTTP", "POST", "DELETE", "JSON", "OBIS", "Content-Type", "Demo", "Signal")
                        or (re.fullmatch(r"[a-z][\w -]*", stripped) and not re.search(r"[äöüß]", stripped))):
                    continue
                result.append(f"{path.name}:{code.count(chr(10), 0, position) + 1}: {stripped[:100]}")
    return result


def main():
    result = keys()
    if "--untranslated" in sys.argv:
        print("\n".join(untranslated()))
        return
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
