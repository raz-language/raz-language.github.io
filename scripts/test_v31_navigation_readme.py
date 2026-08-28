#!/usr/bin/env python3
from pathlib import Path
import re, sys

R=Path(__file__).resolve().parents[1]
errors=[]
def need(c,m):
    if not c: errors.append(m)

# README is an evergreen project reference, not a release/dev log.
readme=(R/'README.md').read_text(encoding='utf-8')
need(not re.search(r'^##\s+v\d+', readme, re.M), 'README contains version-history/dev-log headings')
for required in ('## Architecture','## Build','## Validation','## Deployment staging','## Generator conventions'):
    need(required in readme, f'README missing enduring section {required}')
need('pass-by-pass' not in readme.lower(), 'README still reads like a pass-by-pass log')

# Every primary nav has at most one active item and route families own the
# correct top-level section after all generators have run.
def active_primary(path: Path):
    t=path.read_text(encoding='utf-8')
    m=re.search(r'<nav class="primary-links"[^>]*>(.*?)</nav>', t, re.S)
    if not m: return []
    return re.findall(r'<a href="([^"]+)" aria-current="page"', m.group(1))

fixtures={
    'docs/index.html':'docs/index.html',
    'learn/index.html':'learn/index.html',
    'packages/index.html':'packages/index.html',
    'tools/index.html':'tools/index.html',
    'community/index.html':'community/index.html',
    'contribute/index.html':'community/index.html',
}
for rel,target in fixtures.items():
    p=R/rel; need(p.exists(), f'missing fixture {rel}')
    if p.exists():
        active=active_primary(p)
        need(len(active)==1, f'{rel} should have exactly one active primary nav item: {active}')
        if active: need(active[0].endswith(target), f'{rel} active nav should be {target}: {active[0]}')


# Standalone destinations must not borrow a top-level active state merely
# because they are adjacent to a primary product section.
for rel in (
    'cli/index.html', 'install/index.html', 'releases/index.html', 'news/index.html',
    'about/index.html', 'ecosystem/index.html', 'performance/index.html',
    'status/index.html', 'web/index.html',
):
    p=R/rel
    need(p.exists(), f'missing standalone fixture {rel}')
    if p.exists():
        need(active_primary(p)==[], f'{rel} should have no active primary nav item: {active_primary(p)}')

# Package API docs must stay under Packages, even after late package enhancers.
for p in list((R/'packages').glob('*/docs/index.html'))[:12]:
    active=active_primary(p)
    need(len(active)==1 and active[0].endswith('packages/index.html'), f'{p.relative_to(R)} does not mark Packages active: {active}')
    t=p.read_text(encoding='utf-8')
    need('<header class="product-masthead' in t, f'{p.relative_to(R)} lost product masthead')

status=R/'status/index.html'
if status.exists():
    t=status.read_text(encoding='utf-8')
    need(active_primary(status)==[], f'status should not claim a primary section: {active_primary(status)}')
    need('<a href="../index.html">Home</a><span>/</span><span>Status</span>' in t, 'status breadcrumb should be Home / Status')
    need('<header class="reference-header' in t, 'status should use compact reference header')

# v26 must validate source-driven release notes without requiring fallback-only headings.
v26=(R/'scripts/test_v26_product_content.py').read_text(encoding='utf-8')
need("for heading in ('Language','Compiler','CLI and tooling'" not in v26, 'v26 test still hardcodes fallback release-note headings')
need('release notes rendered content is unexpectedly short' in v26, 'v26 release-note substance check missing')

# Full generated navigation should never have two active primary items.
for p in R.rglob('*.html'):
    if '_site' in p.relative_to(R).parts: continue
    active=active_primary(p)
    need(len(active)<=1, f'{p.relative_to(R)} has multiple active primary nav items: {active}')

if errors:
    print('\n'.join('ERROR '+e for e in errors), file=sys.stderr)
    raise SystemExit(1)
print('OK: v31 evergreen README, release-note regression, and route navigation semantics')
