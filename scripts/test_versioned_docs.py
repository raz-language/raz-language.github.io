#!/usr/bin/env python3
from pathlib import Path
import json, sys
ROOT=Path(__file__).resolve().parents[1]
checks=[
 ROOT/'docs/1.0/index.html',
 ROOT/'docs/1.0/reference/language-stability/index.html',
 ROOT/'docs/1.0/diagnostics/index.html',
 ROOT/'docs/1.0/stdlib/index.html',
 ROOT/'docs/1.0/api/index.html',
 ROOT/'learn/1.0/book/index.html',
 ROOT/'learn/1.0/book/chapter-01/index.html',
]
missing=[str(p.relative_to(ROOT)) for p in checks if not p.exists()]
if missing: raise SystemExit('missing versioned docs: '+', '.join(missing))
for p in checks:
    t=p.read_text(encoding='utf-8')
    if 'doc-version-switcher' not in t: raise SystemExit(f'missing version switcher: {p.relative_to(ROOT)}')
    if p.suffix=='.html' and 'http-equiv="refresh"' in t: raise SystemExit(f'version route still redirects: {p.relative_to(ROOT)}')
versions=json.loads((ROOT/'api/v1/versions.json').read_text())
entry=versions.get('docs',{}).get('1.0',{})
if entry.get('snapshot_url')!='docs/1.0/index.html' or entry.get('book_snapshot_url')!='learn/1.0/book/index.html':
    raise SystemExit('versions API does not advertise frozen 1.0 snapshots')
# Internal frozen reference link must stay inside the snapshot.
sample=(ROOT/'docs/1.0/reference/language-stability/index.html').read_text(encoding='utf-8')
if 'doc-version-switcher' not in sample or 'http-equiv="refresh"' in sample:
    raise SystemExit('versioned reference is not a real frozen page')
print('OK: versioned documentation snapshots are real, navigable, and advertised')
