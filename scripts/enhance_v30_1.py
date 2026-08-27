#!/usr/bin/env python3
"""v30.1 footer balance and information architecture polish."""
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
ASSETS = ROOT / "assets"


def footer_columns(prefix: str) -> str:
    return (
        '<div><h2>Learn</h2>'
        f'<a href="{prefix}learn/index.html">Getting started</a>'
        f'<a href="{prefix}docs/index.html">Documentation</a>'
        f'<a href="{prefix}packages/index.html">Packages</a>'
        f'<a href="{prefix}install/index.html">Install</a></div>\n      '
        '<div><h2>Reference</h2>'
        '<a href="https://github.com/raz-language/raz/blob/main/docs/LANGUAGE-SPECIFICATION.md">Specification ↗</a>'
        '<a href="https://github.com/raz-language/raz/blob/main/docs/STANDARD-LIBRARY.md">Standard library ↗</a>'
        f'<a data-project-cli-link href="{prefix}cli/index.html">CLI</a>'
        '<a href="https://github.com/raz-language/raz/blob/main/docs/PLATFORM-SUPPORT.md">Platforms ↗</a></div>\n      '
        '<div><h2>Project</h2>'
        '<a href="https://github.com/raz-language">GitHub ↗</a>'
        f'<a data-project-contribute-link href="{prefix}contribute/index.html">Contribute</a>'
        '<a href="https://github.com/raz-language/raz/blob/main/SECURITY.md">Security ↗</a>'
        '<a href="https://github.com/raz-language/raz/blob/main/LICENSE">Apache-2.0 ↗</a></div>\n      '
        '<div><h2>Explore</h2>'
        f'<a data-project-release-link href="{prefix}releases/index.html">Releases</a>'
        f'<a data-project-news-link href="{prefix}news/index.html">News</a>'
        f'<a data-project-about-link href="{prefix}about/index.html">About</a>'
        f'<a data-project-ecosystem-link href="{prefix}ecosystem/index.html">Ecosystem</a>'
        f'<a data-project-performance-link href="{prefix}performance/index.html">Performance</a>'
        f'<a href="{prefix}status/index.html">Status</a></div>'
    )


def update_footers() -> int:
    changed = 0
    pattern = re.compile(
        r'(<div class="footer-intro">.*?</div>)\s*'
        r'<div><h2>Learn</h2>.*?</div>\s*'
        r'<div><h2>Reference</h2>.*?</div>\s*'
        r'<div><h2>Project</h2>.*?</div>'
        r'(?:\s*<div><h2>Explore</h2>.*?</div>)?',
        re.S,
    )
    for page in ROOT.rglob("*.html"):
        if "_site" in page.parts:
            continue
        text = page.read_text(encoding="utf-8")
        if '<footer class="site-footer">' not in text:
            continue
        rel = page.relative_to(ROOT)
        prefix = "../" * max(0, len(rel.parts) - 1)
        repl = lambda m: m.group(1) + "\n      " + footer_columns(prefix)
        updated, count = pattern.subn(repl, text, count=1)
        if count:
            page.write_text(updated, encoding="utf-8")
            changed += 1
    return changed


def update_styles() -> None:
    path = ASSETS / "styles.css"
    text = path.read_text(encoding="utf-8")
    marker = "/* v30.1 balanced footer */"
    if marker in text:
        text = text.split(marker, 1)[0].rstrip() + "\n"
    text += r'''
/* v30.1 balanced footer */
@media(min-width:1021px){.footer-main{grid-template-columns:1.55fr repeat(4,minmax(0,1fr));gap:38px}.footer-intro{padding-right:28px}}
@media(min-width:651px) and (max-width:1020px){.footer-main{grid-template-columns:1.25fr repeat(2,minmax(0,1fr));gap:28px}.footer-intro{grid-row:span 2}.footer-main>div:nth-child(5){grid-column:3}}
'''
    path.write_text(text, encoding="utf-8")


def main() -> None:
    changed = update_footers()
    update_styles()
    print(f"v30.1: balanced footer on {changed} HTML pages")


if __name__ == "__main__":
    main()
