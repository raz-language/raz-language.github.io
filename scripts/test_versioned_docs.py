#!/usr/bin/env python3
from pathlib import Path
import json
ROOT=Path(__file__).resolve().parents[1]
versions=json.loads((ROOT/'api/v1/versions.json').read_text())
current=str(versions.get('current') or '1.0')
checks=[
 ROOT/f'docs/{current}/index.html',
 ROOT/f'docs/{current}/diagnostics/index.html',
 ROOT/f'docs/{current}/stdlib/index.html',
 ROOT/f'docs/{current}/api/index.html',
 ROOT/f'learn/{current}/book/index.html',
 ROOT/f'learn/{current}/book/chapter-01/index.html',
]
missing=[str(p.relative_to(ROOT)) for p in checks if not p.exists()]
if missing: raise SystemExit('missing versioned docs: '+', '.join(missing))
for p in checks:
    t=p.read_text(encoding='utf-8')
    if 'doc-version-switcher' not in t: raise SystemExit(f'missing version switcher: {p.relative_to(ROOT)}')
    if 'http-equiv="refresh"' in t: raise SystemExit(f'version route still redirects: {p.relative_to(ROOT)}')
entry=versions.get('docs',{}).get(current,{})
if entry.get('snapshot_url')!=f'docs/{current}/index.html' or entry.get('book_snapshot_url')!=f'learn/{current}/book/index.html':
    raise SystemExit('versions API does not advertise current frozen snapshots')
print(f'OK: versioned documentation snapshots are real, navigable, and version-driven ({current})')
