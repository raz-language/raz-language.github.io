#!/usr/bin/env python3
from __future__ import annotations
import re
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
ORIGIN='https://raz-language.github.io'
errors=[]
home=(ROOT/'index.html').read_text(encoding='utf-8')
for needle in (f'<link rel="canonical" href="{ORIGIN}/">', f'<meta property="og:url" content="{ORIGIN}/">'):
    if needle not in home: errors.append(f'homepage missing production metadata: {needle}')
if not re.search(rf'<meta property="og:image" content="{re.escape(ORIGIN)}/assets/raz-social\.png"', home):
    errors.append('homepage missing production social preview image')
robots=(ROOT/'robots.txt').read_text(encoding='utf-8')
if f'Sitemap: {ORIGIN}/sitemap.xml' not in robots: errors.append('robots.txt does not advertise the production sitemap')
sitemap=ROOT/'sitemap.xml'
if not sitemap.exists(): errors.append('sitemap.xml is missing')
elif '<meta name="robots" content="noindex' in home: errors.append('homepage must be indexable')
if sitemap.exists():
    sx=sitemap.read_text(encoding='utf-8')
    if f'<loc>{ORIGIN}/</loc>' not in sx: errors.append('sitemap omits homepage')
    if f'<loc>{ORIGIN}/404.html</loc>' in sx: errors.append('sitemap must not include the 404 page')
    if f'{ORIGIN}/docs/1.0/' in sx: errors.append('noindex duplicate 1.0 snapshot should not be in sitemap while 1.0 is current stable')
for asset,limit in [('raz-mark-128.png',50000),('raz-social.png',250000)]:
    p=ROOT/'assets'/asset
    if not p.exists(): errors.append(f'missing optimized branding asset {asset}')
    elif p.stat().st_size>limit: errors.append(f'{asset} is unexpectedly large: {p.stat().st_size} bytes')
if errors:
    for error in errors: print('ERROR',error)
    raise SystemExit(1)
print('OK: production canonical, sitemap, social metadata, and optimized brand assets are configured')
