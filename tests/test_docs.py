"""Die Dokumentation darf keine toten Verweise haben: Dateien, Bilder, Anker und Namen entfernter Dateien."""
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
MARKDOWN = [ROOT / "README.md", ROOT / "SECURITY.md", ROOT / "THIRD-PARTY.md", *sorted((ROOT / "docs").glob("*.md"))]
REMOVED = ("SCHNELLSTART", "INSTALLATION-SYNOLOGY", "GERAETESUCHE", "tools/install.sh", "tools/setup.py", "fritz")


def slug(heading):
    """Anker wie auf GitHub: klein, ohne Satzzeichen (Umlaute bleiben), Leerzeichen zu Bindestrichen."""
    heading = re.sub(r"[`*_]", "", heading.strip().lower())
    return re.sub(r"[^\w\- ]", "", heading).replace(" ", "-")


def anchors(path):
    found, fenced = set(), False
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.startswith("```"):
            fenced = not fenced
        match = None if fenced else re.match(r"#{1,6}\s+(.*)", line)
        if match:
            found.add(slug(match.group(1)))
    return found


def links(path):
    text = re.sub(r"```.*?```", "", path.read_text(encoding="utf-8"), flags=re.S)
    return re.findall(r"!?\[[^\]]*\]\(([^)\s]+)\)", text)


def test_every_relative_link_image_and_anchor_resolves():
    problems = []
    for path in MARKDOWN:
        for url in links(path):
            if re.match(r"[a-z]+:", url):
                continue
            target, _, fragment = url.partition("#")
            file = (path.parent / target).resolve() if target else path
            if not file.exists():
                problems.append(f"{path.name}: {url} (Datei fehlt)")
            elif fragment and file.suffix == ".md" and slug(fragment) not in anchors(file):
                problems.append(f"{path.name}: {url} (Überschrift fehlt)")
    assert problems == []


def test_docs_do_not_mention_removed_files_or_vendor_specific_examples():
    for path in MARKDOWN:
        text = path.read_text(encoding="utf-8").lower()
        for name in REMOVED:
            assert name.lower() not in text, f"{path.name} erwähnt {name}"


def test_external_links_use_https_and_the_project_repository():
    for path in MARKDOWN:
        for url in links(path):
            if url.startswith("http"):
                assert url.startswith("https://"), f"{path.name}: {url}"
            if "github.com/aemjay" in url.lower():
                assert re.match(r"https://github\.com/aemjay/Kilowatch(/|$)", url), f"{path.name}: {url}"
