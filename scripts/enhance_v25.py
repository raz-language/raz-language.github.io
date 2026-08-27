#!/usr/bin/env python3
"""v25 page-opening hierarchy.

The site keeps one visual system but uses different opening densities for
marketing, section, product, and reference surfaces. Generated reference pages
must prioritize the information users came for instead of repeating a large
marketing hero on every route.
"""
from __future__ import annotations

from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
STYLES = ROOT / "assets" / "styles.css"


def rel(page: Path) -> str:
    return page.relative_to(ROOT).as_posix()


def is_versioned(path: str) -> bool:
    return bool(re.match(r"(?:docs|learn)/\d+\.\d+/", path))


def logical_path(path: str) -> str:
    path = re.sub(r"^docs/\d+\.\d+/", "docs/", path)
    path = re.sub(r"^learn/\d+\.\d+/", "learn/", path)
    return path


def opening_kind(page: Path) -> str | None:
    p = logical_path(rel(page))
    if p == "index.html":
        return None  # homepage keeps its bespoke marketing hero
    if p in {"install/index.html", "learn/index.html", "community/index.html"}:
        return "marketing"
    if p in {"docs/index.html", "tools/index.html", "releases/index.html", "news/index.html", "learn/book/index.html"}:
        return "section"
    if p == "packages/index.html" or p.startswith("packages/"):
        return "product"
    if p == "status/index.html":
        return "reference"
    if p.startswith(("docs/stdlib/", "docs/diagnostics/", "docs/api/", "docs/reference/")):
        return "reference"
    if p.startswith("learn/book/chapter-"):
        return "reference"
    # Guide landing pages are destinations, but less promotional than top-level sections.
    if p.startswith("docs/"):
        return "section"
    return None


def replace_page_hero_class(text: str, kind: str) -> str:
    # Preserve semantic subtype classes while replacing only page-hero.
    cls = {
        "marketing": "marketing-hero",
        "section": "section-hero",
        "product": "product-masthead",
        "reference": "reference-header",
    }[kind]
    return re.sub(r'<header class="page-hero(?P<rest>[^"]*)">', lambda m: f'<header class="{cls}{m.group("rest")}">', text, count=1)


def package_catalog_masthead(text: str) -> str:
    # Pull registry controls into the masthead. Use stable sibling markers rather
    # than a nested-div regex so all statistics survive unchanged.
    toolbar_start = text.find('<div class="package-toolbar">')
    freshness = text.find('<div class="data-freshness">', toolbar_start)
    if toolbar_start < 0 or freshness < 0:
        return text
    block = text[toolbar_start:freshness].strip()
    text = text[:toolbar_start] + text[freshness:]
    # Shorter, catalog-oriented opening copy. External registry links become
    # secondary utilities rather than the primary thing above the catalog.
    head = re.search(r'<header class="product-masthead"><div class="shell narrow">.*?</div></header>', text, re.S)
    if not head:
        return text
    replacement = (
        '<header class="product-masthead package-catalog-masthead"><div class="shell">'
        '<div class="product-title-row"><div><p class="kicker">OFFICIAL REGISTRY</p>'
        '<h1>Packages</h1><p class="page-lead">Search immutable Raz package releases and jump directly into source-derived API documentation.</p></div>'
        '<div class="product-utility-links"><a href="https://github.com/raz-language/packages">Registry source ↗</a>'
        '<a href="https://github.com/raz-language/raz/blob/main/docs/PACKAGE-MANAGEMENT.md">Package management ↗</a></div></div>'
        + block +
        '</div></header>'
    )
    text = text[:head.start()] + replacement + text[head.end():]
    text = text.replace('<section class="section section-white"><div class="shell">', '<section class="section section-white package-catalog-main"><div class="shell">', 1)
    return text

def compact_diagnostics_index(text: str) -> str:
    # Search/filtering belongs with the diagnostic identity, not a full section below it.
    toolbar = re.search(r'\s*<div class="reference-toolbar">.*?</div>', text, re.S)
    if not toolbar:
        return text
    block = toolbar.group(0).strip()
    text = text[:toolbar.start()] + text[toolbar.end():]
    marker = '</div></header>'
    pos = text.find(marker, text.find('<header class="reference-header"'))
    if pos >= 0:
        text = text[:pos] + f'<div class="reference-header-tools">{block}</div>' + text[pos:]
    return text


def package_global_nav(text: str) -> str:
    # Package documentation is a package product surface, not the global Docs section.
    text = re.sub(r'(href="(?:\.\./)*docs/index\.html") aria-current="page"', r'\1', text, count=1)
    if 'href="' in text and '<nav class="package-product-nav"' in text:
        # Mark the first global Packages nav link only.
        text = re.sub(r'(href="(?:\.\./)*packages/index\.html")(?! aria-current)', r'\1 aria-current="page"', text, count=1)
    return text


def enhance_page(page: Path) -> bool:
    text = page.read_text(encoding="utf-8")
    original = text
    kind = opening_kind(page)
    if kind:
        text = replace_page_hero_class(text, kind)

    p = logical_path(rel(page))
    if p == "packages/index.html":
        text = package_catalog_masthead(text)
    if p == "docs/diagnostics/index.html":
        text = compact_diagnostics_index(text)
    if p.startswith("packages/"):
        text = package_global_nav(text)

    if text != original:
        page.write_text(text, encoding="utf-8")
        return True
    return False


def add_styles() -> None:
    text = STYLES.read_text(encoding="utf-8")
    marker = "/* v25 page-opening hierarchy */"
    if marker in text:
        text = text.split(marker, 1)[0].rstrip() + "\n"
    text += f'''
{marker}
/* Major section entrances retain breathing room without impersonating the homepage. */
.marketing-hero{{padding:70px 0 76px;background:#f9fafc;border-bottom:1px solid var(--line)}}
.marketing-hero h1{{margin:0;font-size:clamp(3.2rem,6.5vw,6.2rem);line-height:.93;letter-spacing:-.062em}}
.section-hero{{padding:48px 0 52px;background:#f9fafc;border-bottom:1px solid var(--line)}}
.section-hero h1{{margin:0;font-size:clamp(2.7rem,5vw,4.65rem);line-height:.98;letter-spacing:-.052em;max-width:950px}}
.section-hero .page-lead{{margin-top:17px;font-size:1.04rem;max-width:760px}}
.section-hero .doc-breadcrumbs{{margin-bottom:20px}}
.section-hero .doc-version-switcher{{margin-bottom:13px}}

/* Product pages lead with controls and metadata rather than marketing whitespace. */
.product-masthead{{padding:32px 0 30px;background:#fff;border-bottom:1px solid var(--line)}}
.product-masthead>.shell{{width:min(calc(100% - 44px),var(--shell))}}
.product-masthead>.shell.narrow{{max-width:var(--shell)}}
.product-masthead h1{{margin:0;font-size:clamp(2.55rem,5vw,4.3rem);line-height:.98;letter-spacing:-.052em}}
.product-masthead .page-lead{{margin-top:11px;max-width:760px;font-size:.96rem;line-height:1.6}}
.product-masthead .kicker{{margin-bottom:9px}}
.product-masthead .doc-breadcrumbs{{margin-bottom:15px}}
.product-masthead .button-row{{margin-top:18px}}
.product-masthead .package-version-row{{margin-top:16px;color:#68768a}}
.product-masthead .package-version-row b{{color:#1c2737}}
.product-masthead .package-product-stats{{margin-top:14px}}
.product-title-row{{display:flex;align-items:flex-end;justify-content:space-between;gap:36px;margin-bottom:22px}}
.product-title-row .page-lead{{margin-bottom:0}}
.product-utility-links{{display:flex;gap:15px;flex-wrap:wrap;justify-content:flex-end;padding-bottom:4px}}
.product-utility-links a{{font-size:.76rem;font-weight:800;color:#315bd2;text-decoration:none}}
.package-catalog-masthead .package-toolbar{{margin:0;padding:17px;border:1px solid var(--line);background:#f7f9fc;border-radius:8px}}
.package-catalog-masthead .registry-stats{{margin:14px 0 0}}
.package-catalog-main{{padding-top:32px}}
.package-catalog-main>.shell>.data-freshness{{margin-top:0}}

/* Dense references open like documentation, not landing pages. */
.reference-header{{padding:24px 0 26px;background:#fff;border-bottom:1px solid var(--line)}}
.reference-header>.shell{{width:min(calc(100% - 44px),var(--shell));max-width:var(--shell)}}
.reference-header h1{{margin:0;font-size:clamp(2.15rem,4vw,3.35rem);line-height:1;letter-spacing:-.047em;max-width:980px}}
.reference-header .page-lead{{margin-top:9px;max-width:820px;font-size:.9rem;line-height:1.55}}
.reference-header .kicker{{margin-bottom:7px;font-size:.64rem}}
.reference-header .doc-breadcrumbs{{margin-bottom:11px}}
.reference-header .doc-version-switcher{{margin-bottom:10px}}
.reference-header .button-row{{margin-top:15px}}
.reference-header .book-chapter-source{{margin-top:12px}}
.reference-header .package-version-row{{margin-top:12px;color:#68768a}}
.reference-header-tools{{margin-top:18px}}
.reference-header-tools .reference-toolbar{{margin:0}}
.status-summary-grid{{margin-top:0}}

/* Book chapters are reading surfaces; the article should arrive quickly. */
.reference-header.book-chapter-hero{{padding:22px 0 24px}}
.reference-header.book-chapter-hero h1{{font-size:clamp(2.25rem,4.4vw,3.7rem)}}
.reference-header.book-chapter-hero .doc-breadcrumbs{{margin-bottom:10px}}
.book-reading-layout{{padding-top:38px}}

/* Keep historic page-hero styling as a safe fallback for routes not yet classified. */
@media(max-width:760px){{
  .marketing-hero{{padding:48px 0 52px}}.marketing-hero h1{{font-size:clamp(3rem,15vw,4.8rem)}}
  .section-hero{{padding:36px 0 40px}}.section-hero h1{{font-size:clamp(2.6rem,12vw,4rem)}}
  .product-masthead,.reference-header{{padding:24px 0}}
  .product-title-row{{align-items:flex-start;flex-direction:column;gap:12px}}
  .product-utility-links{{justify-content:flex-start}}
  .package-catalog-masthead .package-toolbar{{padding:12px}}
}}
@media print{{.marketing-hero,.section-hero,.product-masthead,.reference-header{{padding:16px 0!important;background:#fff!important}}}}
'''
    STYLES.write_text(text, encoding="utf-8")


def main() -> None:
    changed = 0
    counts = {"marketing": 0, "section": 0, "product": 0, "reference": 0}
    for page in ROOT.rglob("*.html"):
        if "_site" in page.relative_to(ROOT).parts:
            continue
        kind = opening_kind(page)
        if kind:
            counts[kind] += 1
        changed += int(enhance_page(page))
    add_styles()
    print("OK: v25 page hierarchy " + ", ".join(f"{k}={v}" for k, v in counts.items()) + f"; changed {changed} pages")


if __name__ == "__main__":
    main()
