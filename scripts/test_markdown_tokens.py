#!/usr/bin/env python3
from pathlib import Path
import importlib.util
ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location("sync_site", ROOT/"scripts/sync_site.py")
m=importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
case='[`core::abi`](https://raz-language.github.io/docs/reference/standard-library/index.html#coreabi)'
out=m.inline_markdown(case,{})
assert '@@TOKEN' not in out, out
assert '<code>core::abi</code>' in out, out
assert '<a href=' in out, out
leaks=[]
for page in ROOT.rglob('*.html'):
    if '_site' in page.parts: continue
    if '@@TOKEN' in page.read_text(encoding='utf-8',errors='ignore'):
        leaks.append(str(page.relative_to(ROOT)))
if leaks: raise SystemExit('unresolved markdown tokens: '+', '.join(leaks[:20]))
print('OK: markdown inline tokens resolve without leaking placeholders')
