#!/usr/bin/env python3
from pathlib import Path
import re,sys
R=Path(__file__).resolve().parents[1]
def fail(m): print('ERROR',m); raise SystemExit(1)
css=(R/'assets/styles.css').read_text(encoding='utf-8')
required=[
 '/* v28 responsive + dense-reference usability */',
 '.search-dialog{display:flex;align-items:flex-end}',
 '.search-panel{width:100%;max-height:min(88dvh,720px)',
 '.package-product-nav{scrollbar-width:thin;scroll-snap-type:x proximity',
 '.doc-reference-sidebar{max-height:210px;overflow:auto',
 '.book-sidebar{max-height:190px;overflow:auto',
 '.api-item-layout{grid-template-columns:1fr;gap:28px}',
 '.reference-toolbar input,.package-api-search input{font-size:16px}',
 '[data-scroll-region]:focus{outline:3px solid rgba(45,107,255,.18)'
]
for x in required:
    if x not in css: fail('missing responsive contract: '+x[:70])
# Representative generated dense surfaces must expose keyboard-scrollable regions.
reps=[R/'docs/reference/standard-library/index.html',R/'status/index.html']
found=0
for p in reps:
    if p.exists():
        t=p.read_text(encoding='utf-8')
        if 'data-scroll-region' in t:
            found+=1
            if 'tabindex="0"' not in t or 'role="region"' not in t: fail(f'incomplete scroll accessibility {p}')
if found==0: fail('no representative keyboard-scrollable reference region found')
# No inline fixed widths that are common overflow regressions on package/API headers.
for p in [R/'packages/index.html',R/'docs/stdlib/index.html',R/'docs/diagnostics/index.html']:
    if p.exists() and re.search(r'style="[^"]*width:\s*\d{4,}px',p.read_text(encoding='utf-8'),re.I): fail(f'large fixed inline width in {p}')
print(f'OK: v28 responsive contracts + {found} representative keyboard-scroll regions')
