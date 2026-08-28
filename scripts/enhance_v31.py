#!/usr/bin/env python3
"""v31 navigation consistency hardening.

This final post-generation normalizer owns top-level navigation state and a few
route-level breadcrumb/header semantics that older generators can otherwise
reintroduce during refresh builds.
"""
from __future__ import annotations

from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]


def route(page: Path) -> str:
    return page.relative_to(ROOT).as_posix()


def desired_primary(rel: str) -> str | None:
    # Versioned docs/book snapshots retain the same product section as current.
    if re.match(r"learn/(?:\d+\.\d+/)?(?:index\.html|book/)", rel):
        return "learn"
    if re.match(r"docs/(?:\d+\.\d+/)?", rel):
        return "docs"
    if rel.startswith("packages/") or rel == "packages/index.html":
        return "packages"
    if rel.startswith("tools/"):
        return "tools"
    # CLI is a standalone command-reference destination. It is linked from
    # Reference in the footer, but is not the Tools landing section itself.
    if rel.startswith("cli/"):
        return None
    if rel.startswith("community/") or rel.startswith("contribute/"):
        return "community"
    # Install/releases/news/about/ecosystem/performance/status are independent
    # destinations and should not pretend to belong to a primary section.
    return None


def normalize_primary_nav(text: str, active: str | None) -> str:
    m = re.search(r'(<nav class="primary-links"[^>]*>)(.*?)(</nav>)', text, re.S)
    if not m:
        return text
    body = re.sub(r'\s+aria-current="page"', '', m.group(2))
    if active:
        label = {
            "learn": "Learn",
            "docs": "Docs",
            "packages": "Packages",
            "tools": "Tools",
            "community": "Community",
        }[active]
        pattern = re.compile(r'(<a href="[^"]*")(?=>'+re.escape(label)+r'</a>)')
        body, count = pattern.subn(r'\1 aria-current="page"', body, count=1)
        if count != 1:
            raise SystemExit(f"could not mark {active} primary navigation by label {label}")
    return text[:m.start()] + m.group(1) + body + m.group(3) + text[m.end():]


def normalize_opening(rel: str, text: str) -> str:
    # Older package/status generators can run after the original hierarchy pass.
    # Normalize only the stale generic class; subtype classes remain intact.
    if rel.startswith("packages/"):
        text = re.sub(r'<header class="page-hero(?P<rest>[^"]*)">', r'<header class="product-masthead\g<rest>">', text, count=1)
    elif rel == "status/index.html":
        text = re.sub(r'<header class="page-hero(?P<rest>[^"]*)">', r'<header class="reference-header\g<rest>">', text, count=1)
    return text


def normalize_status(text: str) -> str:
    # Status is an independent generated compatibility dashboard, not Docs.
    text = text.replace(
        '<div class="doc-breadcrumbs"><a href="../docs/index.html">Docs</a><span>/</span><span>Status</span></div>',
        '<div class="doc-breadcrumbs"><a href="../index.html">Home</a><span>/</span><span>Status</span></div>',
        1,
    )
    return text


def normalize_page(page: Path) -> bool:
    rel = route(page)
    text = page.read_text(encoding="utf-8")
    original = text
    text = normalize_primary_nav(text, desired_primary(rel))
    text = normalize_opening(rel, text)
    if rel == "status/index.html":
        text = normalize_status(text)
    if text != original:
        page.write_text(text, encoding="utf-8")
        return True
    return False


def main() -> None:
    changed = 0
    for page in ROOT.rglob("*.html"):
        if "_site" in page.relative_to(ROOT).parts:
            continue
        changed += int(normalize_page(page))
    print(f"OK: v31 normalized navigation/opening semantics on {changed} HTML pages")


if __name__ == "__main__":
    main()
