#!/usr/bin/env python3
"""Finalize browser asset cache keys from the actual final asset bytes.

This must run after every enhancer that can mutate assets/site.js or assets/styles.css.
It deliberately performs no content generation beyond rewriting HTML ?v= digests.
"""
from __future__ import annotations

import hashlib
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ASSETS = ("styles.css", "site.js")


def versions() -> dict[str, str]:
    return {name: hashlib.sha256((ROOT / "assets" / name).read_bytes()).hexdigest()[:12] for name in ASSETS}


def main() -> None:
    digests = versions()
    names = "|".join(re.escape(name) for name in ASSETS)
    pattern = re.compile(rf'(?P<attr>href|src)="(?P<prefix>(?:\.\./)*assets/)(?P<name>{names})(?:\?v=[0-9a-f]+)?"')
    changed = 0
    refs = 0
    for page in ROOT.rglob("*.html"):
        if "_site" in page.relative_to(ROOT).parts:
            continue
        text = page.read_text(encoding="utf-8")
        refs += len(pattern.findall(text))
        updated = pattern.sub(lambda m: f'{m.group("attr")}="{m.group("prefix")}{m.group("name")}?v={digests[m.group("name")]}"', text)
        if updated != text:
            page.write_text(updated, encoding="utf-8")
            changed += 1
    if refs == 0:
        raise SystemExit("no core browser asset references found")
    detail = ", ".join(f"{name}={digest}" for name, digest in digests.items())
    print(f"OK: finalized {refs} browser asset references across {changed} changed HTML pages ({detail})")


if __name__ == "__main__":
    main()
