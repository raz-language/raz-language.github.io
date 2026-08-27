#!/usr/bin/env python3
"""Bound the lazy API search corpus into cache-addressed deployable shards.

Earlier search generations wrote one assets/search-api.json file. Canonical refreshes
can make that file exceed the site's 1 MiB largest-public-file budget as generated
API documentation grows. Keep all earlier enrichers working against the single
logical corpus, then run this final enhancer to split that corpus for deployment.
"""
from __future__ import annotations

from pathlib import Path
import hashlib
import json
import re

ROOT = Path(__file__).resolve().parents[1]
ASSETS = ROOT / "assets"
API_PATH = ASSETS / "search-api.json"
MANIFEST_PATH = ASSETS / "search-api-manifest.json"
SITE_JS = ASSETS / "site.js"
MAX_SHARD_BYTES = 700 * 1024


def packed(items: list[dict]) -> bytes:
    return (json.dumps(items, separators=(",", ":")) + "\n").encode("utf-8")


def split_items(items: list[dict]) -> list[list[dict]]:
    shards: list[list[dict]] = []
    current: list[dict] = []
    for item in items:
        candidate = current + [item]
        if current and len(packed(candidate)) > MAX_SHARD_BYTES:
            shards.append(current)
            current = [item]
            if len(packed(current)) > MAX_SHARD_BYTES:
                raise SystemExit("single API search entry exceeds shard budget")
        else:
            current = candidate
    if current or not shards:
        shards.append(current)
    return shards


def main() -> None:
    if not API_PATH.exists():
        raise SystemExit("missing assets/search-api.json")
    value = json.loads(API_PATH.read_text(encoding="utf-8"))
    if not isinstance(value, list):
        raise SystemExit("assets/search-api.json must be a JSON array before final sharding")

    # Remove only prior generated continuation shards; keep the canonical first path.
    for old in ASSETS.glob("search-api-*.json"):
        if old.name != MANIFEST_PATH.name:
            old.unlink()

    shards = split_items(value)
    manifest = {"version": 1, "total": len(value), "shards": []}
    for index, items in enumerate(shards):
        name = "search-api.json" if index == 0 else f"search-api-{index}.json"
        path = ASSETS / name
        payload = packed(items)
        path.write_bytes(payload)
        digest = hashlib.sha256(payload).hexdigest()[:12]
        manifest["shards"].append({"file": name, "count": len(items), "bytes": len(payload), "digest": digest})

    MANIFEST_PATH.write_text(json.dumps(manifest, separators=(",", ":")) + "\n", encoding="utf-8")
    manifest_digest = hashlib.sha256(MANIFEST_PATH.read_bytes()).hexdigest()[:12]

    js = SITE_JS.read_text(encoding="utf-8")
    core_digest = hashlib.sha256((ASSETS / "search-core.json").read_bytes()).hexdigest()[:12]
    js = re.sub(
        r"const coreVersion='[0-9a-f]{12}',apiVersion='[0-9a-f]{12}';",
        f"const coreVersion='{core_digest}',apiVersion='{manifest_digest}';",
        js,
        count=1,
    )
    old = re.compile(r"const loadAPI=\(\)=>\{if\(apiItems\)return Promise\.resolve\(apiItems\);if\(!apiPromise\)apiPromise=fetch\(searchURL\('search-api\.json',apiVersion\).*?return apiPromise;\};")
    new = "const loadAPI=()=>{if(apiItems)return Promise.resolve(apiItems);if(!apiPromise)apiPromise=fetch(searchURL('search-api-manifest.json',apiVersion),{credentials:'same-origin'}).then(r=>{if(!r.ok)throw new Error(`search api manifest ${r.status}`);return r.json();}).then(manifest=>Promise.all((Array.isArray(manifest.shards)?manifest.shards:[]).map(shard=>fetch(searchURL(shard.file,shard.digest),{credentials:'same-origin'}).then(r=>{if(!r.ok)throw new Error(`search api ${r.status}`);return r.json();})))).then(parts=>{apiItems=parts.flatMap(data=>Array.isArray(data)?data:[]);return apiItems;});return apiPromise;};"
    js, count = old.subn(new, js, count=1)
    if count != 1:
        # Re-running against an already-sharded checked-in site should just refresh the controller.
        prior = re.compile(r"const loadAPI=\(\)=>\{if\(apiItems\)return Promise\.resolve\(apiItems\);if\(!apiPromise\)apiPromise=fetch\(searchURL\('search-api-manifest\.json',apiVersion\).*?return apiPromise;\};")
        js, count = prior.subn(new, js, count=1)
    if count != 1:
        raise SystemExit("could not locate API search loader")
    SITE_JS.write_text(js, encoding="utf-8")
    sizes = ", ".join(str(s["bytes"]) for s in manifest["shards"])
    print(f"OK: API search corpus split into {len(shards)} bounded shard(s): {sizes} bytes")


if __name__ == "__main__":
    main()
