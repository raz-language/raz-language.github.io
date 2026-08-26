#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ASSETS = ("styles.css", "site.js")
versions = {name: hashlib.sha256((ROOT / "assets" / name).read_bytes()).hexdigest()[:12] for name in ASSETS}
errors = []
checked = 0
pattern = re.compile(r'(?:href|src)="(?:\.\./)*assets/(styles\.css|site\.js)(?:\?v=([0-9a-f]+))?"')
for page in ROOT.rglob('*.html'):
    if '_site' in page.relative_to(ROOT).parts:
        continue
    text = page.read_text(encoding='utf-8')
    for name, version in pattern.findall(text):
        checked += 1
        if version != versions[name]:
            errors.append(f'{page.relative_to(ROOT)}: {name} cache key {version or "<missing>"} != {versions[name]}')
if checked == 0:
    errors.append('no cache-busted core asset references were found')
if errors:
    for error in errors[:50]:
        print('ERROR', error)
    raise SystemExit(1)
print(f'OK: {checked} core asset references use content-derived cache keys')
