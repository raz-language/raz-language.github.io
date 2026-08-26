#!/usr/bin/env python3
from __future__ import annotations
from pathlib import Path
import importlib.util
import json
import re
import tempfile

ROOT=Path(__file__).resolve().parents[1]
ORIGIN='https://raz-language.github.io'
errors=[]

# Footer injection must be structurally valid everywhere.
for page in ROOT.rglob('*.html'):
    if '_site' in page.relative_to(ROOT).parts:
        continue
    text=page.read_text(encoding='utf-8')
    if '<a <a' in text or re.search(r'<a\s+(?=<a\s)', text):
        errors.append(f'malformed footer/anchor markup: {page.relative_to(ROOT)}')

# All indexable pages self-canonicalize; no project page inherits doc version metadata.
for page in ROOT.rglob('*.html'):
    rel=page.relative_to(ROOT).as_posix()
    if '_site' in page.relative_to(ROOT).parts or rel=='404.html':
        continue
    text=page.read_text(encoding='utf-8')
    noindex='name="robots" content="noindex' in text
    route='/' if rel=='index.html' else ('/'+rel[:-10] if rel.endswith('/index.html') else '/'+rel)
    if not noindex and f'<link rel="canonical" href="{ORIGIN}{route}">' not in text:
        errors.append(f'wrong self-canonical: {rel}')
    doc_channel=rel.startswith('docs/') or rel.startswith('learn/book/') or bool(re.match(r'learn/\d+\.\d+/book/',rel))
    if not doc_channel and 'name="raz-doc-version"' in text:
        errors.append(f'non-doc page carries raz-doc-version: {rel}')
    if rel!='404.html' and 'data-v24-schema="page"' not in text:
        errors.append(f'missing route-aware structured data: {rel}')

status=(ROOT/'status/index.html').read_text(encoding='utf-8')
if 'href="../docs/index.html" aria-current="page"' in status:
    errors.append('status page still marks Docs as current top navigation')

# Version manifest must be source-driven from the current language version.
site=json.loads((ROOT/'data/generated/site.json').read_text(encoding='utf-8'))
versions=json.loads((ROOT/'api/v1/versions.json').read_text(encoding='utf-8'))
current=str(site.get('language',{}).get('version'))
if versions.get('current')!=current or current not in versions.get('docs',{}):
    errors.append('version manifest is not driven by current language version')

# Current release page must point at its matching major.minor docs line.
releases=json.loads((ROOT/'data/generated/releases.json').read_text(encoding='utf-8'))
if releases:
    tag=str(releases[0].get('tag') or releases[0].get('name') or '').lstrip('v')
    m=re.match(r'^(\d+)\.(\d+)',tag)
    line=f'{m.group(1)}.{m.group(2)}' if m else current
    if line not in versions.get('docs',{}): line=current
    slug=re.sub(r'[^A-Za-z0-9._-]+','-',str(releases[0].get('tag') or releases[0].get('name') or 'release')).strip('-').lower()
    page=ROOT/'releases'/slug/'index.html'
    if page.exists():
        text=page.read_text(encoding='utf-8')
        if f'../../docs/{line}/index.html' not in text or f'../../learn/{line}/book/index.html' not in text:
            errors.append('release page does not map to matching versioned documentation')

install=(ROOT/'install/index.html').read_text(encoding='utf-8')
for needle in ('install.ps1','install.sh','~/.local/bin'):
    if needle not in install:
        errors.append(f'install page missing portable installation guidance: {needle}')

# Prove the strict validator rejects the exact malformed attribute form that escaped v23.
spec=importlib.util.spec_from_file_location('raz_validate', ROOT/'scripts/validate.py')
mod=importlib.util.module_from_spec(spec); spec.loader.exec_module(mod)
with tempfile.TemporaryDirectory() as td:
    tmp=Path(td); bad=tmp/'index.html'
    bad.write_text('<!doctype html><html lang="en"><head><title>x</title><meta name="description" content="x"><meta name="viewport" content="width=device-width"></head><body><h1>x</h1><a <a href="x">bad</a></body></html>',encoding='utf-8')
    _parsed, detected=mod.parse_pages(tmp)
    if not any('malformed HTML attribute' in e for e in detected):
        errors.append('strict validator does not reject malformed nested start-tag attributes')

if errors:
    for error in errors: print('ERROR',error)
    raise SystemExit(1)
print('OK: v24 footer, canonical, schema, version, release-doc, install, and strict-HTML contracts hold')
