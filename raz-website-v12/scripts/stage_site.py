#!/usr/bin/env python3
"""Stage only deployable Raz website files into a clean static output tree."""
from pathlib import Path
import argparse
import shutil
import sys

ROOT = Path(__file__).resolve().parents[1]

FILES = [
    "index.html",
    "404.html",
    "robots.txt",
    "site.webmanifest",
    "llms.txt",
    ".nojekyll",
    "_headers",
    "_redirects",
    "vercel.json",
    "performance-budget.json",
]
OPTIONAL_FILES = ["sitemap.xml"]
DIRECTORIES = [
    "assets",
    "learn",
    "docs",
    "install",
    "releases",
    "packages",
    "tools",
    "web",
    "community",
    "status",
    "api",
    ".well-known",
]


def copy_tree(src: Path, dst: Path):
    shutil.copytree(src, dst, dirs_exist_ok=True)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", default="_site", help="staging output directory")
    args = parser.parse_args()
    out = (ROOT / args.output).resolve() if not Path(args.output).is_absolute() else Path(args.output)
    if out == ROOT or ROOT in out.parents and out.name in {"assets", "docs", "packages"}:
        raise SystemExit("refusing unsafe staging output")
    if out.exists():
        shutil.rmtree(out)
    out.mkdir(parents=True)

    missing = []
    for rel in FILES:
        src = ROOT / rel
        if not src.exists():
            missing.append(rel)
            continue
        dst = out / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)
    for rel in OPTIONAL_FILES:
        src = ROOT / rel
        if src.exists():
            shutil.copy2(src, out / rel)
    for rel in DIRECTORIES:
        src = ROOT / rel
        if not src.exists():
            missing.append(rel + "/")
            continue
        copy_tree(src, out / rel)

    if missing:
        print("missing deployable inputs:", file=sys.stderr)
        for item in missing:
            print("  " + item, file=sys.stderr)
        raise SystemExit(1)

    files = [p for p in out.rglob("*") if p.is_file()]
    total = sum(p.stat().st_size for p in files)
    print(f"OK: staged {len(files)} files ({total} bytes) to {out}")


if __name__ == "__main__":
    main()
