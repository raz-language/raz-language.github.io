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
items = re.findall(r'<article class="package-item"[^>]*data-package[^>]*data-name="([^"]*)"[^>]*data-category="([^"]*)"[^>]*data-search="([^"]*)"', html)
if not items:
    errors.append('packages page has no searchable package items')
buttons = re.findall(r'<button type="button"[^>]*data-package-filter="([^"]+)"', html)
if 'all' not in buttons:
    errors.append('package filter controls are not explicit non-submit buttons')
if 'aria-pressed="true" data-package-filter="all"' not in html:
    errors.append('package filter controls do not expose pressed state')
if 'data-package-filter-controller' not in html:
    errors.append('packages page has no local filter controller')
if "item.style.setProperty('display', 'none', 'important')" not in html:
    errors.append('local package controller does not directly hide filtered cards')
if "item.style.removeProperty('display')" not in html:
    errors.append('local package controller cannot restore visible cards')
if "item.style.setProperty('display','none','important')" not in js:
    errors.append('shared package filter does not directly hide filtered cards')
if "classList.toggle('package-filtered-out',!show)" not in js:
    errors.append('shared package filter does not maintain filtered-out state')
if '[hidden]{display:none!important}' not in css:
    errors.append('hidden elements can be overridden by component display styles')
if '.package-item.package-filtered-out{display:none!important}' not in css:
    errors.append('package filtered-out class has no display:none rule')

# Exercise the generated metadata using the same matching rules as the browser controller.
def matches(row, term='', category='all'):
    name, item_category, search = row
    term = term.strip().lower()
    return (category == 'all' or item_category == category) and (not term or term in search.lower())

if items:
    json_hits = [row for row in items if matches(row, 'json')]
    if not json_hits or len(json_hits) == len(items):
        errors.append('text search metadata cannot distinguish json from the catalog')
    security_hits = [row for row in items if matches(row, category='security')]
    if not security_hits or len(security_hits) == len(items):
        errors.append('category metadata cannot distinguish security packages')
    combined_hits = [row for row in items if matches(row, 'crypto', 'security')]
    if not combined_hits:
        errors.append('combined text/category filtering has no valid fixture')

if errors:
    for error in errors:
        print('ERROR', error)
    raise SystemExit(1)
print(f'OK: package search/filter behavior contract ({len(items)} package cards, {len(buttons)} category controls)')
