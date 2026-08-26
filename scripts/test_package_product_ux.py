#!/usr/bin/env python3
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
landing=ROOT/'packages/json/index.html'; docs=ROOT/'packages/json/docs/index.html'
for p in (landing,docs):
    if not p.exists(): raise SystemExit(f'missing package fixture: {p}')
lt=landing.read_text(encoding='utf-8'); dt=docs.read_text(encoding='utf-8')
for token in ('package-product-nav','package-product-stats','id="versions"'):
    if token not in lt: raise SystemExit(f'package overview missing {token}')
for token in ('package-product-nav','data-package-api-search','data-package-api-row','id="dependencies"','data-package-api-filter-controller'):
    if token not in dt: raise SystemExit(f'package API landing missing {token}')
print('OK: package overview/API navigation, stats, dependencies, versions, and API search are wired')
