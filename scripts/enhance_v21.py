#!/usr/bin/env python3
"""v21: frozen 1.0 documentation snapshots and unified package/API UX."""
from __future__ import annotations

import html
import json
import os
import re
import shutil
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit

ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT / "docs"
DOC_SNAPSHOT = DOCS / "1.0"
BOOK = ROOT / "learn" / "book"
BOOK_SNAPSHOT = ROOT / "learn" / "1.0" / "book"
GEN = ROOT / "data" / "generated"
API = ROOT / "api" / "v1"
VERSION = "1.0"


def esc(value: object) -> str:
    return html.escape(str(value), quote=True)


def _inside(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
        return True
    except ValueError:
        return False


def _map_snapshot_target(target: Path) -> Path:
    if _inside(target, DOCS) and not _inside(target, DOC_SNAPSHOT):
        return DOC_SNAPSHOT / target.relative_to(DOCS)
    if _inside(target, BOOK):
        return BOOK_SNAPSHOT / target.relative_to(BOOK)
    return target


def _rewrite_relative_url(raw: str, source: Path, destination: Path) -> str:
    if not raw or raw.startswith(("#", "mailto:", "tel:", "javascript:", "data:")):
        return raw
    parts = urlsplit(raw)
    if parts.scheme or parts.netloc:
        return raw
    path_text = parts.path
    if not path_text:
        return raw
    if path_text.startswith("/"):
        target = ROOT / path_text.lstrip("/")
    else:
        target = (source.parent / path_text).resolve()
    if not _inside(target, ROOT):
        return raw
    mapped = _map_snapshot_target(target)
    rel = os.path.relpath(mapped, destination.parent).replace("\\", "/")
    return urlunsplit(("", "", rel, parts.query, parts.fragment))


def _snapshot_html(text: str, source: Path, destination: Path) -> str:
    attr_re = re.compile(r'(?P<prefix>\b(?:href|src)=)(?P<q>["\'])(?P<url>.*?)(?P=q)', re.I)
    def repl(match: re.Match[str]) -> str:
        url = _rewrite_relative_url(match.group("url"), source, destination)
        return f'{match.group("prefix")}{match.group("q")}{url}{match.group("q")}'
    text = attr_re.sub(repl, text)
    text = re.sub(r'<meta name="raz-doc-version" content="[^"]*">', f'<meta name="raz-doc-version" content="{VERSION}-snapshot">', text)
    if 'name="raz-doc-version"' not in text and '<head>' in text:
        text = text.replace('</head>', f'  <meta name="raz-doc-version" content="{VERSION}-snapshot">\n</head>', 1)
    if 'name="robots"' not in text and '<head>' in text:
        # 1.0 equals current stable today, so avoid duplicate search indexing. When
        # current stable advances, this can be lifted for the historical snapshot.
        text = text.replace('</head>', '  <meta name="robots" content="noindex,follow">\n</head>', 1)
    return text


def _copy_tree(source_root: Path, destination_root: Path, exclude: set[str] | None = None) -> int:
    exclude = exclude or set()
    if destination_root.exists():
        shutil.rmtree(destination_root)
    count = 0
    for source in source_root.rglob("*"):
        rel = source.relative_to(source_root)
        if rel.parts and rel.parts[0] in exclude:
            continue
        destination = destination_root / rel
        if source.is_dir():
            destination.mkdir(parents=True, exist_ok=True)
            continue
        destination.parent.mkdir(parents=True, exist_ok=True)
        if source.suffix.lower() == ".html":
            text = source.read_text(encoding="utf-8")
            destination.write_text(_snapshot_html(text, source, destination), encoding="utf-8")
        else:
            shutil.copy2(source, destination)
        count += 1
    return count


def _counterpart(page: Path, snapshot: bool) -> Path | None:
    if snapshot:
        if _inside(page, DOC_SNAPSHOT):
            return DOCS / page.relative_to(DOC_SNAPSHOT)
        if _inside(page, BOOK_SNAPSHOT):
            return BOOK / page.relative_to(BOOK_SNAPSHOT)
    else:
        if _inside(page, DOCS) and not _inside(page, DOC_SNAPSHOT):
            return DOC_SNAPSHOT / page.relative_to(DOCS)
        if _inside(page, BOOK):
            return BOOK_SNAPSHOT / page.relative_to(BOOK)
    return None


def _rel(page: Path, target: Path) -> str:
    return os.path.relpath(target, page.parent).replace("\\", "/")


def _version_switcher(page: Path, snapshot: bool) -> str:
    other = _counterpart(page, snapshot)
    current_target = other if snapshot else page
    snapshot_target = page if snapshot else other
    current_href = _rel(page, current_target) if current_target else "#"
    snapshot_href = _rel(page, snapshot_target) if snapshot_target else "#"
    return (
        '<details class="doc-version-switcher">'
        f'<summary><span>Raz</span><b>{VERSION}</b><em>{"snapshot" if snapshot else "stable"}</em></summary>'
        '<div class="doc-version-menu">'
        f'<a href="{esc(current_href)}" class="{"active" if not snapshot else ""}"><span>Current stable</span><b>{VERSION}</b></a>'
        f'<a href="{esc(snapshot_href)}" class="{"active" if snapshot else ""}"><span>Frozen snapshot</span><b>{VERSION}</b></a>'
        '</div></details>'
    )


def _inject_version_switchers(root: Path, snapshot: bool) -> int:
    changed = 0
    for page in root.rglob("*.html"):
        text = page.read_text(encoding="utf-8")
        text = re.sub(r'<details class="doc-version-switcher">.*?</details>', '', text, flags=re.S)
        switcher = _version_switcher(page, snapshot)
        marker = '<div class="doc-breadcrumbs">'
        if marker in text:
            text = text.replace(marker, switcher + marker, 1)
        elif '<header class="page-hero' in text:
            text = re.sub(r'(<header class="page-hero[^"]*"><div class="shell(?: narrow)?">)', r'\1' + switcher, text, count=1)
        else:
            continue
        page.write_text(text, encoding="utf-8")
        changed += 1
    return changed


def write_version_manifest() -> None:
    versions = {
        "current": VERSION,
        "language_status": "stable",
        "stable": [VERSION],
        "docs": {
            VERSION: {
                "current_url": "docs/index.html",
                "snapshot_url": f"docs/{VERSION}/index.html",
                "book_current_url": "learn/book/index.html",
                "book_snapshot_url": f"learn/{VERSION}/book/index.html",
                "mode": "frozen-snapshot",
            }
        },
    }
    for path in (GEN / "versions.json", API / "versions.json"):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(versions, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    index = API / "index.json"
    if index.exists():
        data = json.loads(index.read_text(encoding="utf-8"))
        data.setdefault("resources", {})["versions"] = "./versions.json"
        index.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _package_nav(page: Path, package: str, active: str) -> str:
    base = ROOT / "packages" / package
    items = [
        ("overview", base / "index.html", "Overview"),
        ("api", base / "docs" / "index.html", "API docs"),
        ("dependencies", base / "docs" / "index.html", "Dependencies"),
        ("versions", base / "index.html", "Versions"),
    ]
    links = []
    for key, target, label in items:
        href = _rel(page, target)
        if key == "dependencies":
            href += "#dependencies"
        elif key == "versions":
            href += "#versions"
        current = ' aria-current="page"' if key == active else ""
        links.append(f'<a href="{esc(href)}"{current}>{esc(label)}</a>')
    source = f"https://github.com/raz-language/packages/tree/main/sources/{package}"
    links.append(f'<a href="{esc(source)}">Source ↗</a>')
    return '<nav class="package-product-nav" aria-label="Package navigation">' + "".join(links) + "</nav>"


def _public_item_count(doc: dict) -> int:
    return sum(len(module.get("symbols", [])) for module in doc.get("modules", []))


def enhance_packages() -> int:
    catalog_path = GEN / "package-docs.json"
    if not catalog_path.exists():
        return 0
    docs = {item["name"]: item for item in json.loads(catalog_path.read_text(encoding="utf-8"))}
    changed = 0
    for package, doc in docs.items():
        base = ROOT / "packages" / package
        overview = base / "index.html"
        if overview.exists():
            text = overview.read_text(encoding="utf-8")
            text = re.sub(r'<nav class="package-product-nav".*?</nav>', '', text, flags=re.S)
            nav = _package_nav(overview, package, "overview")
            text = text.replace('</header>\n<main id="main"', '</header>' + nav + '\n<main id="main"', 1)
            text = text.replace('<section class="section section-soft"><div class="shell"><div class="section-top compact"><div><p class="kicker">VERSION HISTORY</p>', '<section class="section section-soft" id="versions"><div class="shell"><div class="section-top compact"><div><p class="kicker">VERSION HISTORY</p>', 1)
            stats = (
                '<div class="package-product-stats">'
                f'<div><span>Modules</span><b>{len(doc.get("modules", []))}</b></div>'
                f'<div><span>Public API</span><b>{_public_item_count(doc)}</b></div>'
                f'<div><span>Dependencies</span><b>{len(doc.get("dependencies", []))}</b></div>'
                '</div>'
            )
            text = re.sub(r'(<div class="package-version-row">.*?</div>)', r'\1' + stats, text, count=1, flags=re.S)
            overview.write_text(text, encoding="utf-8")
            changed += 1

        api_landing = base / "docs" / "index.html"
        if api_landing.exists():
            text = api_landing.read_text(encoding="utf-8")
            text = re.sub(r'<nav class="package-product-nav".*?</nav>', '', text, flags=re.S)
            text = text.replace('</header>\n<main id="main"', '</header>' + _package_nav(api_landing, package, "api") + '\n<main id="main"', 1)
            text = text.replace('<section class="section section-white"><div class="shell"><div class="section-top compact"><div><p class="kicker">DEPENDENCIES</p>', '<section class="section section-white" id="dependencies"><div class="shell"><div class="section-top compact"><div><p class="kicker">DEPENDENCIES</p>', 1)
            # Make module rows searchable by module and symbol names.
            modules = doc.get("modules", [])
            for module in modules:
                needle = f'<a class="package-api-module-row" href="'
                idx = text.find(needle)
                if idx < 0:
                    break
                end = text.find('>', idx)
                if end < 0:
                    break
                hay = " ".join([module.get("name", ""), module.get("file", "")] + [s.get("name", "") + " " + s.get("signature", "") for s in module.get("symbols", [])]).lower()
                text = text[:idx] + text[idx:end].replace('class="package-api-module-row"', f'class="package-api-module-row" data-package-api-row data-search="{esc(hay)}"') + text[end:]
            search = ('<div class="package-api-search"><label><span class="sr-only">Search package API</span>'
                      '<input type="search" placeholder="Search modules and symbols…" data-package-api-search></label>'
                      '<span data-package-api-count></span></div>')
            text = text.replace('<div class="package-api-module-list">', search + '<div class="package-api-module-list">', 1)
            controller = '''<script data-package-api-filter-controller>(()=>{const input=document.querySelector('[data-package-api-search]');const rows=[...document.querySelectorAll('[data-package-api-row]')];const count=document.querySelector('[data-package-api-count]');if(!input||!rows.length)return;const apply=()=>{const q=input.value.trim().toLowerCase();let shown=0;rows.forEach(row=>{const visible=!q||(row.dataset.search||'').includes(q);row.hidden=!visible;if(visible)shown++;});if(count)count.textContent=`${shown} module${shown===1?'':'s'}`};input.addEventListener('input',apply);apply();})();</script>'''
            text = text.replace('</main>', '</main>' + controller, 1)
            api_landing.write_text(text, encoding="utf-8")
            changed += 1

        for page in (base / "docs").rglob("*.html") if (base / "docs").exists() else []:
            if page == api_landing:
                continue
            text = page.read_text(encoding="utf-8")
            text = re.sub(r'<nav class="package-product-nav".*?</nav>', '', text, flags=re.S)
            text = text.replace('</header>\n<main id="main"', '</header>' + _package_nav(page, package, "api") + '\n<main id="main"', 1)
            page.write_text(text, encoding="utf-8")
            changed += 1
    return changed


def add_styles() -> None:
    path = ROOT / "assets" / "styles.css"
    text = path.read_text(encoding="utf-8")
    marker = "/* v21 documentation versions + package product UX */"
    if marker in text:
        text = text.split(marker, 1)[0].rstrip() + "\n"
    text += f'''\n{marker}\n.doc-version-switcher{{position:relative;display:inline-block;margin:0 0 18px}}.doc-version-switcher summary{{list-style:none;display:flex;align-items:center;gap:8px;cursor:pointer;border:1px solid var(--line);background:#fff;padding:7px 10px;border-radius:7px;font-size:.76rem;box-shadow:0 5px 16px rgba(17,23,34,.05)}}.doc-version-switcher summary::-webkit-details-marker{{display:none}}.doc-version-switcher summary span{{color:var(--muted);font-weight:700}}.doc-version-switcher summary b{{font-family:var(--mono)}}.doc-version-switcher summary em{{font-style:normal;text-transform:uppercase;letter-spacing:.08em;color:#315bd2;font-size:.62rem;font-weight:900}}.doc-version-menu{{position:absolute;left:0;top:calc(100% + 7px);z-index:30;width:230px;padding:6px;border:1px solid var(--line);background:#fff;border-radius:8px;box-shadow:var(--shadow)}}.doc-version-menu a{{display:flex;justify-content:space-between;gap:16px;padding:8px 10px;border-radius:5px;text-decoration:none;font-size:.76rem}}.doc-version-menu a:hover,.doc-version-menu a.active{{background:var(--soft-blue)}}.doc-version-menu a span{{color:var(--muted)}}.doc-version-menu a b{{font-family:var(--mono)}}.package-product-nav{{position:sticky;top:72px;z-index:45;display:flex;gap:2px;overflow:auto;padding:0 max(24px,calc((100vw - var(--shell))/2));background:rgba(255,255,255,.97);border-bottom:1px solid var(--line);backdrop-filter:blur(12px)}}.package-product-nav a{{flex:0 0 auto;padding:13px 14px;text-decoration:none;font-size:.78rem;font-weight:800;color:#5d6878;border-bottom:2px solid transparent}}.package-product-nav a:hover{{color:#2458d6}}.package-product-nav a[aria-current=page]{{color:#111722;border-color:#2d6bff}}.package-product-stats{{display:flex;flex-wrap:wrap;gap:1px;margin-top:20px;border:1px solid var(--line);border-radius:8px;overflow:hidden;width:max-content;max-width:100%}}.package-product-stats div{{display:flex;gap:10px;align-items:center;padding:8px 11px;background:#fff;border-right:1px solid var(--line);font-size:.72rem}}.package-product-stats div:last-child{{border-right:0}}.package-product-stats span{{color:var(--muted)}}.package-product-stats b{{font-family:var(--mono)}}.package-api-search{{display:flex;align-items:center;justify-content:space-between;gap:16px;margin:0 0 16px}}.package-api-search label{{flex:1}}.package-api-search input{{width:100%;border:1px solid #cfd7e2;background:#fff;border-radius:7px;padding:11px 13px}}.package-api-search>span{{color:var(--muted);font-size:.78rem;white-space:nowrap}}@media(max-width:720px){{.package-product-nav{{top:72px;padding-inline:18px}}.package-product-stats{{width:100%}}.package-product-stats div{{flex:1;justify-content:center}}.package-api-search{{align-items:stretch;flex-direction:column;gap:7px}}}}\n'''
    path.write_text(text, encoding="utf-8")


def main() -> None:
    package_pages = enhance_packages()
    add_styles()
    docs_files = _copy_tree(DOCS, DOC_SNAPSHOT, exclude={"1.0"})
    book_files = _copy_tree(BOOK, BOOK_SNAPSHOT)
    current_docs = _inject_version_switchers(DOCS, snapshot=False)
    current_book = _inject_version_switchers(BOOK, snapshot=False)
    frozen_docs = _inject_version_switchers(DOC_SNAPSHOT, snapshot=True)
    frozen_book = _inject_version_switchers(BOOK_SNAPSHOT, snapshot=True)
    write_version_manifest()
    print(f"OK: v21 versioned docs ({docs_files} docs files, {book_files} book files; switchers {current_docs+current_book+frozen_docs+frozen_book}; package pages {package_pages})")


if __name__ == "__main__":
    main()
