#!/usr/bin/env python3
from pathlib import Path
import argparse,json,sys
ROOT=Path(__file__).resolve().parents[1]
parser=argparse.ArgumentParser(); parser.add_argument('--root',default='.'); args=parser.parse_args()
root=(ROOT/args.root).resolve() if not Path(args.root).is_absolute() else Path(args.root)
budget=json.loads((ROOT/'performance-budget.json').read_text())['limits']
checks=[
 ('homepage_html_bytes',root/'index.html'),
 ('styles_css_bytes',root/'assets/styles.css'),
 ('site_js_bytes',root/'assets/site.js'),
 ('search_index_js_bytes',root/'assets/search-index.js'),
]
errors=[]
for key,path in checks:
    if not path.exists(): errors.append(f'missing {path.relative_to(root)}'); continue
    size=path.stat().st_size; limit=budget[key]
    if size>limit: errors.append(f'{path.relative_to(root)}: {size} bytes exceeds {limit}')
public=[p for p in root.rglob('*') if p.is_file()]
if public:
    largest=max(public,key=lambda p:p.stat().st_size); ls=largest.stat().st_size
    if ls>budget['largest_public_file_bytes']: errors.append(f'largest file {largest.relative_to(root)}: {ls} bytes exceeds {budget["largest_public_file_bytes"]}')
    total=sum(p.stat().st_size for p in public)
    if root.name=='_site' or '_site' in root.parts:
        if total>budget['staged_site_bytes']: errors.append(f'staged site: {total} bytes exceeds {budget["staged_site_bytes"]}')
if errors:
    print('performance budget failed:',file=sys.stderr)
    for e in errors: print('  '+e,file=sys.stderr)
    raise SystemExit(1)
print('OK: performance budgets satisfied')
