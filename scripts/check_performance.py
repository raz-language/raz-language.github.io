#!/usr/bin/env python3
"""Enforce Raz.org per-request performance budgets and corpus-growth guardrails.

Source-tree checks intentionally inspect only files that stage_site.py can deploy.
This keeps Git metadata, caches, archives, and local build artifacts out of the
public-site budget while still applying the same limits to a staged _site tree.
"""
from pathlib import Path
import argparse
import json
import sys

ROOT = Path(__file__).resolve().parents[1]

DEPLOY_FILES = {
    "index.html", "404.html", "robots.txt", "site.webmanifest", "llms.txt",
    ".nojekyll", "_headers", "_redirects", "vercel.json",
    "performance-budget.json", "sitemap.xml",
}
SOURCE_ONLY_ASSETS = {"raz-logo.png", "raz-logo-original.png", "raz-mark.png"}

DEPLOY_DIRECTORIES = {
    "assets", "learn", "docs", "install", "releases", "packages", "tools",
    "web", "community", "status", "news", "api", ".well-known",
}

def is_staged(root: Path) -> bool:
    return root.name == "_site" or "_site" in root.parts

def deployable_files(root: Path):
    if is_staged(root):
        return [p for p in root.rglob("*") if p.is_file()]
    files = []
    for name in DEPLOY_FILES:
        p = root / name
        if p.is_file():
            files.append(p)
    for name in DEPLOY_DIRECTORIES:
        d = root / name
        if d.is_dir():
            files.extend(
                p for p in d.rglob("*")
                if p.is_file() and not (name == "assets" and p.name in SOURCE_ONLY_ASSETS)
            )
    return files

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", default=".")
    args = parser.parse_args()
    root = (ROOT / args.root).resolve() if not Path(args.root).is_absolute() else Path(args.root).resolve()
    budget = json.loads((ROOT / "performance-budget.json").read_text())["limits"]
    checks = [
        ("homepage_html_bytes", root / "index.html"),
        ("styles_css_bytes", root / "assets/styles.css"),
        ("site_js_bytes", root / "assets/site.js"),
        ("search_core_json_bytes", root / "assets/search-core.json"),
        ("search_api_json_bytes", root / "assets/search-api.json"),
    ]
    errors = []
    for key, path in checks:
        if not path.exists():
            errors.append(f"missing {path.relative_to(root)}")
            continue
        size = path.stat().st_size
        limit = budget[key]
        if size > limit:
            errors.append(f"{path.relative_to(root)}: {size} bytes exceeds {limit}")

    public = deployable_files(root)
    if public:
        largest = max(public, key=lambda p: p.stat().st_size)
        largest_size = largest.stat().st_size
        if largest_size > budget["largest_public_file_bytes"]:
            errors.append(
                f"largest deployable file {largest.relative_to(root)}: "
                f"{largest_size} bytes exceeds {budget['largest_public_file_bytes']}"
            )
        total = sum(p.stat().st_size for p in public)
        if is_staged(root) and total > budget["staged_site_bytes"]:
            errors.append(f"staged documentation corpus: {total} bytes exceeds {budget['staged_site_bytes']}")

    if errors:
        print("performance budget failed:", file=sys.stderr)
        for error in errors:
            print("  " + error, file=sys.stderr)
        raise SystemExit(1)
    print(f"OK: performance budgets satisfied ({len(public)} deployable files scanned)")

if __name__ == "__main__":
    main()
