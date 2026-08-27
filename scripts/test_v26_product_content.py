#!/usr/bin/env python3
from pathlib import Path
import json, re, sys
ROOT=Path(__file__).resolve().parents[1]
errors=[]

def need(cond,msg):
    if not cond: errors.append(msg)

about=ROOT/'about/index.html'
need(about.exists(),'missing about/index.html')
if about.exists():
    t=about.read_text(encoding='utf-8')
    need('Why Raz' in t,'about page missing Why Raz content')
    need('https://raz-language.github.io/about/' in t,'about canonical missing')
    need('"@type":"AboutPage"' in t,'about schema missing AboutPage')
    need('WHEN NOT TO USE RAZ' in t,'about page missing limitations section')
    need(t.count('data-project-about-link')==1,'about footer About link not exactly once')

release=ROOT/'releases/v1.0.0/index.html'
need(release.exists(),'missing v1.0.0 release page')
if release.exists():
    t=release.read_text(encoding='utf-8')
    need('release-notes-rendered:start' in t,'release notes section not rendered')
    need('WHAT CHANGED' in t and 'Release notes.' in t,'release notes heading missing')
    # Release note structure belongs to the canonical upstream source.  Online
    # refreshes prefer the published RELEASE-NOTES.md asset, while offline
    # builds may use the tagged changelog fallback; those sources need not
    # share the same section headings.  Verify meaningful rendered content
    # and provenance without imposing the fallback's outline on the asset.
    article = re.search(r'<article class="release-notes-prose">(.*?)</article>', t, re.S)
    need(article is not None,'release notes prose article missing')
    if article:
        prose = re.sub(r'<[^>]+>', ' ', article.group(1))
        prose = re.sub(r'\s+', ' ', prose).strip()
        need(len(prose) >= 200,'release notes rendered content is unexpectedly short')
        need(bool(re.search(r'<(?:h[2-6]|ul|ol|p)\b', article.group(1))), 'release notes rendered content has no semantic structure')
    need('Canonical tagged changelog section' in t or 'Published RELEASE-NOTES.md asset' in t or 'Cached canonical release notes' in t,'release notes source provenance missing')

for fn in ('assets/search-core.json','assets/search-api.json'):
    p=ROOT/fn
    items=json.loads(p.read_text(encoding='utf-8'))
    need(bool(items),f'{fn} empty')
    for i,item in enumerate(items):
        for key in ('kind','name','namespace','qualified_name'):
            need(key in item,f'{fn} item {i} missing {key}')
core=json.loads((ROOT/'assets/search-core.json').read_text())
need(any(i.get('url')=='about/index.html' and i.get('kind')=='page' for i in core),'About missing from core search')
api=json.loads((ROOT/'assets/search-api.json').read_text())
ptr=next((i for i in api if i.get('name')=='pointer_size'),None)
need(ptr is not None,'pointer_size structured search fixture missing')
if ptr:
    need(ptr.get('qualified_name')=='core::abi::pointer_size',f"pointer_size qualified name wrong: {ptr.get('qualified_name')}")
    need(ptr.get('kind')=='function',f"pointer_size kind wrong: {ptr.get('kind')}")
js=(ROOT/'assets/site.js').read_text(encoding='utf-8')
need('qualified_name' in js and 'qualified===term' in js,'structured search ranking not wired into site.js')
stage=(ROOT/'scripts/stage_site.py').read_text(encoding='utf-8')
need('\"about\"' in stage,'stage_site.py does not deploy about/')
sitemap=(ROOT/'sitemap.xml').read_text(encoding='utf-8')
need('<loc>https://raz-language.github.io/about/</loc>' in sitemap,'About omitted from sitemap')
# Source audits remain truthful; v26 must not suppress upstream inconsistencies.
audit=json.loads((ROOT/'api/v1/source-audit.json').read_text())
codes={x.get('code') for x in audit.get('warnings',[])}
for code in ('security-version-drift','missing-indexed-doc','stdlib-index-count-drift'):
    need(code in codes,f'v26 improperly suppressed upstream warning {code}')
if errors:
    print('\n'.join('ERROR '+e for e in errors),file=sys.stderr); raise SystemExit(1)
print('OK: v26 About, rendered release notes, source provenance, and structured search metadata')
