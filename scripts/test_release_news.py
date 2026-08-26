#!/usr/bin/env python3
from __future__ import annotations
import json
import re
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
releases=json.loads((ROOT/'data/generated/releases.json').read_text(encoding='utf-8'))
errors=[]
news=ROOT/'news/index.html'
feed=ROOT/'news/feed.xml'
api=ROOT/'api/v1/news.json'
for path in (news,feed,api):
    if not path.exists(): errors.append(f'missing {path.relative_to(ROOT)}')
if news.exists():
    text=news.read_text(encoding='utf-8')
    if 'Signal, not a development log.' not in text: errors.append('news page lost durable publication framing')
    if 'feed.xml' not in text: errors.append('news page does not expose RSS feed')
for release in releases:
    tag=str(release.get('tag') or release.get('name') or 'release')
    slug=re.sub(r'[^A-Za-z0-9._-]+','-',tag).strip('-').lower() or 'release'
    page=ROOT/'releases'/slug/'index.html'
    if not page.exists(): errors.append(f'missing permanent release page for {tag}')
    else:
        text=page.read_text(encoding='utf-8')
        if tag.lstrip('v') not in text: errors.append(f'release page {tag} does not identify its version')
        for asset in release.get('assets',[]):
            name=asset.get('name') or ''
            if name and name not in text: errors.append(f'release page {tag} missing asset {name}')
if feed.exists():
    try: ET.parse(feed)
    except Exception as exc: errors.append(f'news RSS feed invalid: {exc}')
if api.exists():
    payload=json.loads(api.read_text(encoding='utf-8'))
    if len(payload.get('entries',[])) != len(releases): errors.append('news API entry count does not match releases')
release_index=(ROOT/'releases/index.html').read_text(encoding='utf-8')
if '<!-- release-history:start -->' not in release_index: errors.append('release history section missing')
home=(ROOT/'index.html').read_text(encoding='utf-8')
if releases and '<!-- latest-release:start -->' not in home: errors.append('homepage latest-release strip missing')
if errors:
    for error in errors[:80]: print('ERROR',error)
    raise SystemExit(1)
print(f'OK: release/news publication surfaces cover {len(releases)} published release(s)')
