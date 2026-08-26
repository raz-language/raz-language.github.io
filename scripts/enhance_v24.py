#!/usr/bin/env python3
"""v24 correctness and architecture hardening.

Normalizes public canonical metadata, keeps documentation-version metadata scoped
only to documentation channels, adds route-aware structured data/breadcrumbs,
and applies small install-flow presentation improvements.
"""
from __future__ import annotations

from pathlib import Path
from urllib.parse import urljoin
import html
import json
import os
import re

ROOT = Path(__file__).resolve().parents[1]
STYLES = ROOT / "assets" / "styles.css"
SITE_ORIGIN = (os.getenv("RAZ_SITE_URL") or "https://raz-language.github.io").strip().rstrip("/")


def esc(value: object) -> str:
    return html.escape(str(value), quote=True)


def route_for(page: Path) -> str:
    rel = page.relative_to(ROOT).as_posix()
    if rel == "index.html":
        return "/"
    if rel.endswith("/index.html"):
        return "/" + rel[:-10]
    return "/" + rel


def text_content(value: str) -> str:
    value = re.sub(r"<[^>]+>", "", value)
    return html.unescape(value).strip()


def page_title(text: str) -> str:
    m = re.search(r"<title>(.*?)</title>", text, re.S | re.I)
    return text_content(m.group(1)) if m else "Raz"


def page_description(text: str) -> str:
    m = re.search(r'<meta name="description" content="([^"]*)">', text, re.I)
    return html.unescape(m.group(1)) if m else "Raz programming language"


def is_doc_channel(page: Path) -> bool:
    rel = page.relative_to(ROOT).as_posix()
    return rel.startswith("docs/") or rel.startswith("learn/book/") or bool(re.match(r"learn/\d+\.\d+/book/", rel))


def page_schema_type(page: Path) -> str:
    rel = page.relative_to(ROOT).as_posix()
    if rel == "index.html":
        return "WebSite"
    if rel.startswith(("docs/", "learn/")):
        return "TechArticle"
    if rel.startswith(("news/", "releases/")) and rel not in {"news/index.html", "releases/index.html"}:
        return "TechArticle"
    if rel.startswith("packages/"):
        return "SoftwareSourceCode"
    return "WebPage"


def breadcrumb_schema(page: Path, text: str, canonical: str) -> dict | None:
    m = re.search(r'<div class="doc-breadcrumbs">(.*?)</div>', text, re.S)
    if not m:
        return None
    body = m.group(1)
    items = []
    pos = 1
    for match in re.finditer(r'<a[^>]+href="([^"]+)"[^>]*>(.*?)</a>|<span>(.*?)</span>', body, re.S):
        href, linked, plain = match.groups()
        label = text_content(linked if linked is not None else plain or "")
        if not label or label == "/":
            continue
        if href:
            url = urljoin(canonical, href)
        else:
            url = canonical
        items.append({"@type": "ListItem", "position": pos, "name": label, "item": url})
        pos += 1
    if not items:
        return None
    return {"@context": "https://schema.org", "@type": "BreadcrumbList", "itemListElement": items}


def structured_data(page: Path, text: str, canonical: str) -> str:
    title = page_title(text)
    description = page_description(text)
    kind = page_schema_type(page)
    payload = {
        "@context": "https://schema.org",
        "@type": kind,
        "name": title,
        "headline": title,
        "description": description,
        "url": canonical,
        "isPartOf": {"@type": "WebSite", "name": "Raz", "url": SITE_ORIGIN + "/"},
    }
    if kind == "SoftwareSourceCode":
        payload.update({"programmingLanguage": "Raz", "codeRepository": "https://github.com/raz-language/packages" if page.relative_to(ROOT).as_posix().startswith("packages/") else "https://github.com/raz-language/raz"})
    crumbs = breadcrumb_schema(page, text, canonical)
    scripts = [f'<script type="application/ld+json" data-v24-schema="page">{json.dumps(payload, separators=(",", ":"))}</script>']
    if crumbs:
        scripts.append(f'<script type="application/ld+json" data-v24-schema="breadcrumbs">{json.dumps(crumbs, separators=(",", ":"))}</script>')
    return "\n  ".join(scripts)


def normalize_page(page: Path) -> bool:
    text = page.read_text(encoding="utf-8")
    original = text
    rel = page.relative_to(ROOT).as_posix()
    noindex = bool(re.search(r'<meta name="robots" content="[^"]*noindex', text, re.I))
    canonical = SITE_ORIGIN + route_for(page)

    # Public/indexable pages must self-canonicalize. Current-version frozen
    # duplicates intentionally remain noindex with their current-page canonical.
    if not noindex and rel != "404.html":
        if re.search(r'<link rel="canonical" href="[^"]*">', text):
            text = re.sub(r'<link rel="canonical" href="[^"]*">', f'<link rel="canonical" href="{esc(canonical)}">', text, count=1)
        else:
            text = text.replace('</head>', f'  <link rel="canonical" href="{esc(canonical)}">\n</head>', 1)
        if re.search(r'<meta property="og:url" content="[^"]*">', text):
            text = re.sub(r'<meta property="og:url" content="[^"]*">', f'<meta property="og:url" content="{esc(canonical)}">', text, count=1)

    # Status and other project pages must not masquerade as documentation pages.
    if not is_doc_channel(page):
        text = re.sub(r'\s*<meta name="raz-doc-version" content="[^"]*">', '', text)
    if rel == "status/index.html":
        text = text.replace('href="../docs/index.html" aria-current="page"', 'href="../docs/index.html"')

    # Replace v24 additions idempotently.
    text = re.sub(r'\s*<script type="application/ld\+json" data-v24-schema="(?:page|breadcrumbs)">.*?</script>', '', text, flags=re.S)
    if rel != "404.html":
        canonical_for_schema = canonical if not noindex else (re.search(r'<link rel="canonical" href="([^"]+)">', text) or [None, canonical])[1]
        additions = structured_data(page, text, canonical_for_schema)
        text = text.replace('</head>', f'  {additions}\n</head>', 1)

    if text != original:
        page.write_text(text, encoding="utf-8")
        return True
    return False


def add_styles() -> None:
    text = STYLES.read_text(encoding="utf-8")
    marker = "/* v24 correctness + install guidance */"
    if marker in text:
        text = text.split(marker, 1)[0].rstrip() + "\n"
    text += f'''\n{marker}\n.portable-install-steps{{margin-top:26px;padding-top:24px;border-top:1px solid var(--line)}}.portable-install-steps h3{{margin:0 0 8px;font-size:1.18rem}}.portable-install-steps>p{{margin:0 0 14px;color:var(--muted)}}.portable-install-steps .code-card{{max-width:780px}}.install-path-note{{margin-top:12px!important;font-size:.84rem}}\n'''
    STYLES.write_text(text, encoding="utf-8")


def main() -> None:
    changed = 0
    for page in ROOT.rglob("*.html"):
        if "_site" in page.relative_to(ROOT).parts:
            continue
        changed += int(normalize_page(page))
    add_styles()
    print(f"OK: v24 normalized metadata/schema on {changed} HTML pages")


if __name__ == "__main__":
    main()
