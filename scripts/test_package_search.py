#!/usr/bin/env python3
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
html = (ROOT / "packages/index.html").read_text(encoding="utf-8")
js = (ROOT / "assets/site.js").read_text(encoding="utf-8")
css = (ROOT / "assets/styles.css").read_text(encoding="utf-8")

errors = []
if 'data-package-search' not in html:
    errors.append('packages page has no package search input')
items = re.findall(r'<article class="package-item"[^>]*data-package[^>]*data-search="([^"]*)"', html)
if len(items) < 1:
    errors.append('packages page has no searchable package items')
if "pkgSearch&&pkgSearch.addEventListener('input',filter)" not in js:
    errors.append('package search input is not bound to the filter handler')
if "classList.toggle('package-filtered-out',!show)" not in js:
    errors.append('package filter does not apply the explicit filtered-out class')
if '[hidden]{display:none!important}' not in css:
    errors.append('hidden elements can be overridden by component display styles')
if '.package-item.package-filtered-out{display:none!important}' not in css:
    errors.append('package filtered-out class has no display:none rule')

# Ensure search metadata can distinguish a known package from unrelated entries.
known = [x.lower() for x in items]
json_matches = sum('json' in x for x in known)
if json_matches < 1 or json_matches == len(known):
    errors.append('package search metadata cannot distinguish json from the catalog')

if errors:
    for error in errors:
        print('ERROR', error)
    raise SystemExit(1)
print(f'OK: package search contract ({len(items)} searchable package cards)')
