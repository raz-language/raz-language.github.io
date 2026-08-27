#!/usr/bin/env python3
from pathlib import Path
import hashlib, json, re, sys
ROOT=Path(__file__).resolve().parents[1]; ASSETS=ROOT/'assets'; errors=[]
def need(c,m):
    if not c: errors.append(m)
manifest_path=ASSETS/'search-api-manifest.json'
need(manifest_path.exists(),'missing search-api-manifest.json')
manifest={}
if manifest_path.exists():
    try: manifest=json.loads(manifest_path.read_text())
    except Exception as e: errors.append(f'invalid search API manifest: {e}')
shards=manifest.get('shards',[]) if isinstance(manifest,dict) else []
need(bool(shards),'search API manifest has no shards')
total=0
for i,s in enumerate(shards):
    p=ASSETS/str(s.get('file',''))
    need(p.exists(),f'missing API search shard {p.name}')
    if not p.exists(): continue
    size=p.stat().st_size; total += int(s.get('count',0))
    need(size <= 700*1024,f'{p.name} exceeds 700 KiB shard target: {size}')
    need(size == s.get('bytes'),f'{p.name} byte count disagrees with manifest')
    need(hashlib.sha256(p.read_bytes()).hexdigest()[:12] == s.get('digest'),f'{p.name} digest disagrees with manifest')
need(total == manifest.get('total'),f"manifest total mismatch: {total} != {manifest.get('total')}")
js=(ASSETS/'site.js').read_text()
need("fetch(searchURL('search-api-manifest.json'" in js,'browser search does not lazy-load API manifest')
need('Promise.all' in js and 'shard.file' in js and 'shard.digest' in js,'browser search does not load bounded API shards')
md=hashlib.sha256(manifest_path.read_bytes()).hexdigest()[:12] if manifest_path.exists() else ''
need(f"apiVersion='{md}'" in js,'site.js API cache key is not manifest digest')
# Prove refresh-time growth is handled before it reaches the 1 MiB deploy ceiling.
import importlib.util
spec=importlib.util.spec_from_file_location('search_sharder',ROOT/'scripts/enhance_v31_1.py')
mod=importlib.util.module_from_spec(spec); spec.loader.exec_module(mod)
synthetic=[{'title':f'symbol{i}','description':'x'*700,'url':f'docs/api/function/symbol{i}/','keywords':'x'*120,'kind':'function','name':f'symbol{i}','namespace':'core::test','qualified_name':f'core::test::symbol{i}'} for i in range(1600)]
parts=mod.split_items(synthetic); sizes=[len(mod.packed(part)) for part in parts]
need(len(parts)>1,'synthetic refresh-growth corpus did not split into multiple shards')
need(max(sizes,default=0)<=700*1024,f'synthetic API shard exceeds bound: {max(sizes,default=0)}')
if errors:
    print('\n'.join('ERROR '+e for e in errors),file=sys.stderr);raise SystemExit(1)
print(f"OK: API search corpus uses {len(shards)} bounded deployable shard(s), {total} entries")
