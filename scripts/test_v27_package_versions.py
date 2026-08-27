#!/usr/bin/env python3
from pathlib import Path
import json,re,sys
R=Path(__file__).resolve().parents[1]
def fail(m): print('ERROR',m); raise SystemExit(1)
pkgs=json.loads((R/'data/generated/packages.json').read_text())
records=json.loads((R/'api/v1/package-versions.json').read_text())['versions']
expected=sum(len(p.get('versions',[])) for p in pkgs)
if len(records)!=expected: fail(f'package version count {len(records)} != {expected}')
for p in pkgs:
  for i,v in enumerate(p.get('versions',[])):
    base=R/'packages'/p['name']/v['version']
    if not (base/'index.html').exists(): fail(f'missing {p["name"]} {v["version"]} page')
    if not (base/'docs/index.html').exists(): fail(f'missing {p["name"]} {v["version"]} docs route')
    txt=(base/'index.html').read_text()
    if f'raz add {p["name"]}@{v["version"]}' not in txt: fail(f'install command missing {p["name"]} {v["version"]}')
    if v['checksum'] not in txt: fail(f'checksum missing {p["name"]} {v["version"]}')
    docs=(base/'docs/index.html').read_text()
    if i==0:
      if 'raz-package-version' not in docs: fail(f'latest docs missing version metadata {p["name"]}')
    else:
      if 'Historical source snapshot not cached yet.' not in docs: fail(f'historical docs honesty contract missing {p["name"]} {v["version"]}')
idx=json.loads((R/'api/v1/index.json').read_text())
if idx.get('resources',{}).get('package-versions')!='./package-versions.json': fail('API index missing package-versions')
# Search must expose at least a known multi-version package release.
search=json.loads((R/'assets/search-core.json').read_text())
if not any(x.get('qualified_name')=='crypto@0.4.0' and x.get('kind')=='package-version' for x in search): fail('search missing structured package version')
print(f'OK: {expected} stable package version routes + version-aware docs contract')
