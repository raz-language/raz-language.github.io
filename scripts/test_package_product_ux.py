#!/usr/bin/env python3
from collections import Counter
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from enhance_v21 import _anchor_manifest_dependencies

landing = ROOT / "packages/json/index.html"
docs = ROOT / "packages/json/docs/index.html"
for p in (landing, docs):
    if not p.exists():
        raise SystemExit(f"missing package fixture: {p}")

lt = landing.read_text(encoding="utf-8")
dt = docs.read_text(encoding="utf-8")
for token in ("package-product-nav", "package-product-stats", 'id="versions"'):
    if token not in lt:
        raise SystemExit(f"package overview missing {token}")
for token in ("package-product-nav", "data-package-api-search", "data-package-api-row", 'id="package-dependencies"', "data-package-api-filter-controller"):
    if token not in dt:
        raise SystemExit(f"package API landing missing {token}")
if '#package-dependencies' not in dt:
    raise SystemExit("package navigation does not target the collision-safe dependency anchor")

# Reproduce the live-refresh edge case: a package README can already own the
# normal GitHub-style `dependencies` heading ID. Our generated manifest section
# must keep a distinct website-owned anchor.
synthetic = (
    '<section class="source-readme"><h2 id="dependencies">Dependencies</h2></section>'
    '<section class="section section-white"><div class="shell"><div class="section-top compact">'
    '<div><p class="kicker">DEPENDENCIES</p><h2>Manifest dependency surface.</h2></div></div></div></section>'
)
anchored = _anchor_manifest_dependencies(synthetic)
if anchored.count('id="dependencies"') != 1:
    raise SystemExit("source-derived dependencies anchor was altered")
if anchored.count('id="package-dependencies"') != 1:
    raise SystemExit("manifest dependency section did not receive unique package-dependencies anchor")

# Catch this class of refresh-only regression before the full site validator.
id_re = re.compile(r'\bid="([^"]+)"')
for page in (ROOT / "packages").glob("*/docs/**/*.html"):
    ids = id_re.findall(page.read_text(encoding="utf-8"))
    dup = sorted(k for k, n in Counter(ids).items() if n > 1)
    if dup:
        raise SystemExit(f"{page.relative_to(ROOT)} has duplicate ids: {', '.join(dup)}")

print("OK: package overview/API navigation, collision-safe dependencies, versions, API search, and unique package-doc ids are wired")
