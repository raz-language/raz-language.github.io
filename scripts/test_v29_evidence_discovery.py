#!/usr/bin/env python3
from pathlib import Path
import json,re
ROOT=Path(__file__).resolve().parents[1]
errors=[]
perf=(ROOT/'performance/index.html').read_text(encoding='utf-8')
eco=(ROOT/'ecosystem/index.html').read_text(encoding='utf-8')
pkg=(ROOT/'packages/index.html').read_text(encoding='utf-8')
core=json.loads((ROOT/'assets/search-core.json').read_text(encoding='utf-8'))
api=json.loads((ROOT/'api/v1/performance.json').read_text(encoding='utf-8'))
site=(ROOT/'sitemap.xml').read_text(encoding='utf-8')
if 'Published benchmark dataset</b><span>Not yet available' not in perf: errors.append('performance page does not clearly state results are unpublished')
if 'No unverifiable speed claims' not in perf: errors.append('performance evidence contract missing')
if api.get('measurements')!=[] or api.get('status')!='methodology-only': errors.append('performance API must not fabricate measurements')
if 'tools/sync-embedded-components.py' not in eco or 'tools/check-embedded-components.py' not in eco: errors.append('ecosystem contribution synchronization flow missing')
if 'data-package-sort' not in pkg or 'Most versions' not in pkg: errors.append('package sort control missing')
if 'data-package-sort-controller' not in pkg: errors.append('package sort controller missing')
rows=re.findall(r'<article class="package-item"[^>]*data-name="([^"]+)"[^>]*data-version-count="(\d+)"',pkg)
if len(rows)<40: errors.append('package version-count sorting metadata incomplete')
for url in ('performance/index.html','ecosystem/index.html'):
    if not any(i.get('url')==url for i in core): errors.append(f'{url} missing from search')
for route in ('https://raz-language.github.io/performance/','https://raz-language.github.io/ecosystem/'):
    if route not in site: errors.append(f'sitemap missing {route}')
if 'performance' not in json.loads((ROOT/'api/v1/index.json').read_text()) .get('resources',{}): errors.append('API index missing performance resource')
# Every page with About in project footer should expose the two new durable project links.
for sample in (ROOT/'index.html',ROOT/'docs/index.html',ROOT/'packages/index.html'):
    text=sample.read_text(encoding='utf-8')
    if 'data-project-ecosystem-link' not in text or 'data-project-performance-link' not in text: errors.append(f'{sample}: project footer links missing')
if errors:
    for e in errors: print('ERROR',e)
    raise SystemExit(1)
print(f'OK: v29 evidence/discovery contract ({len(rows)} sortable package cards; {len(core)} core search entries)')
