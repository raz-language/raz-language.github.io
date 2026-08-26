#!/usr/bin/env python3
"""v19 frontend hardening: deterministic cache-busting for core browser assets."""
from __future__ import annotations

import hashlib
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ASSETS = ("styles.css", "site.js")


def digest(name: str) -> str:
    return hashlib.sha256((ROOT / "assets" / name).read_bytes()).hexdigest()[:12]


def rewrite_asset_versions() -> tuple[int, dict[str, str]]:
    versions = {name: digest(name) for name in ASSETS}
    names = "|".join(re.escape(name) for name in ASSETS)
    pattern = re.compile(rf'(?P<attr>href|src)="(?P<prefix>(?:\.\./)*assets/)(?P<name>{names})(?:\?v=[0-9a-f]+)?"')
    changed = 0
    for page in ROOT.rglob("*.html"):
        if "_site" in page.relative_to(ROOT).parts:
            continue
        text = page.read_text(encoding="utf-8")
        updated = pattern.sub(lambda m: f'{m.group("attr")}="{m.group("prefix")}{m.group("name")}?v={versions[m.group("name")]}"', text)
        if updated != text:
            page.write_text(updated, encoding="utf-8")
            changed += 1
    return changed, versions


def main() -> None:
    changed, versions = rewrite_asset_versions()
    detail = ", ".join(f"{name}={value}" for name, value in versions.items())
    print(f"OK: v19 cache-busted core assets across {changed} HTML pages ({detail})")


if __name__ == "__main__":
    main()
