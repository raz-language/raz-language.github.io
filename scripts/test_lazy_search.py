#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
core = ROOT / 'assets' / 'search-core.json'
api = ROOT / 'assets' / 'search-api.json'
site_js = ROOT / 'assets' / 'site.js'
errors = []
for path in (core, api):
    if not path.exists(): errors.append(f'{path.relative_to(ROOT)} is missing')
if (ROOT / 'assets' / 'search-index.json').exists(): errors.append('legacy combined assets/search-index.json still exists')
if (ROOT / 'assets' / 'search-index.js').exists(): errors.append('legacy eager assets/search-index.js still exists')
core_items = api_items = []
for path, label in ((core, 'core'), (api, 'api')):
    if path.exists():
        try:
            value = json.loads(path.read_text(encoding='utf-8'))
            if not isinstance(value, list): errors.append(f'{label} search shard must be a JSON array')
            elif label == 'core': core_items = value
            else: api_items = value
        except Exception as exc: errors.append(f'{label} search shard is invalid: {exc}')
if not core_items: errors.append('core search shard must be non-empty')
text = site_js.read_text(encoding='utf-8')
core_digest = hashlib.sha256(core.read_bytes()).hexdigest()[:12] if core.exists() else ''
api_digest = hashlib.sha256(api.read_bytes()).hexdigest()[:12] if api.exists() else ''
for needle in (
    f"const coreVersion='{core_digest}',apiVersion='{api_digest}'",
    "fetch(searchURL('search-core.json'",
    "fetch(searchURL('search-api.json'",
    "if(term.length>=2)",
    "e.key==='ArrowDown'",
    "e.key==='Tab'",
):
    if needle not in text: errors.append(f'site.js missing sharded-search behavior: {needle}')
# API detail URLs should live in the API shard, while ordinary navigation stays core.
if any('/function/' in str(i.get('url','')) for i in core_items if str(i.get('url','')).startswith('docs/stdlib/')):
    errors.append('stdlib item pages leaked into the core search shard')
if api_items and not any(str(i.get('url','')).startswith('docs/stdlib/') or '/docs/module/' in str(i.get('url','')) for i in api_items):
    errors.append('API search shard does not contain API-oriented entries')
script_re = re.compile(r'<script[^>]+search-(?:index|core|api)\.(?:js|json)')
for page in ROOT.rglob('*.html'):
    if '_site' in page.relative_to(ROOT).parts: continue
    if script_re.search(page.read_text(encoding='utf-8')):
        errors.append(f'{page.relative_to(ROOT)} eagerly loads a search shard')
if errors:
    for error in errors[:50]: print('ERROR', error)
    raise SystemExit(1)
print(f'OK: global search is sharded and lazy (core={len(core_items)}, api={len(api_items)}, cache keys {core_digest}/{api_digest})')
