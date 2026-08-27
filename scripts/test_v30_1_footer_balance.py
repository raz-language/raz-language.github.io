#!/usr/bin/env python3
from pathlib import Path
import re, sys

ROOT=Path(__file__).resolve().parents[1]
errors=[]; checked=0
for p in ROOT.rglob('*.html'):
    if '_site' in p.parts: continue
    t=p.read_text(encoding='utf-8')
    if '<footer class="site-footer">' not in t: continue
    checked += 1
    f=t.split('<footer class="site-footer">',1)[1]
    for heading in ('Learn','Reference','Project','Explore'):
        if f.count(f'<h2>{heading}</h2>') != 1:
            errors.append(f'{p.relative_to(ROOT)}: expected one {heading} footer group')
    m=re.search(r'<div><h2>Project</h2>(.*?)</div>',f,re.S)
    if not m or len(re.findall(r'<a\b',m.group(1))) != 4:
        errors.append(f'{p.relative_to(ROOT)}: Project footer group must contain exactly 4 links')
    m=re.search(r'<div><h2>Explore</h2>(.*?)</div>',f,re.S)
    if not m or len(re.findall(r'<a\b',m.group(1))) != 6:
        errors.append(f'{p.relative_to(ROOT)}: Explore footer group must contain exactly 6 links')
    if 'data-project-cli-link' not in f or '<h2>Reference</h2>' not in f:
        errors.append(f'{p.relative_to(ROOT)}: CLI reference footer link missing')
if checked < 800: errors.append(f'only checked {checked} footer pages')
if errors:
    print('\n'.join(errors[:50]),file=sys.stderr);raise SystemExit(1)
print(f'OK: balanced footer contract on {checked} HTML pages')
