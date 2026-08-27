#!/usr/bin/env python3
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
errors=[]

def text(path):
    p=ROOT/path
    if not p.exists(): errors.append(f"missing {path}"); return ""
    return p.read_text(encoding="utf-8")

def require(path, pattern, label):
    t=text(path)
    if not re.search(pattern,t,re.S): errors.append(f"{path}: {label}")

require("index.html", r'<section class="hero">', "homepage bespoke hero changed")
require("install/index.html", r'<header class="marketing-hero', "install must retain marketing hero")
require("docs/index.html", r'<header class="section-hero', "docs should use section hero")
require("tools/index.html", r'<header class="section-hero', "tools should use section hero")
require("releases/index.html", r'<header class="section-hero', "releases should use section hero")
require("news/index.html", r'<header class="section-hero', "news should use section hero")
require("packages/index.html", r'<header class="product-masthead package-catalog-masthead', "packages must use catalog masthead")
require("packages/index.html", r'package-catalog-masthead.*data-package-search.*data-package-filter="all"', "package controls must live in masthead")
require("packages/index.html", r'package-catalog-main', "package catalog main density class missing")
require("packages/crypto/index.html", r'<header class="product-masthead package-detail-hero', "package detail masthead missing")
require("packages/crypto/docs/index.html", r'<header class="product-masthead package-docs-hero', "package docs masthead missing")
require("packages/crypto/docs/index.html", r'href="\.\./\.\./\.\./packages/index\.html" aria-current="page"', "package docs global nav should identify Packages")
require("docs/stdlib/index.html", r'<header class="reference-header', "stdlib must use reference header")
require("docs/diagnostics/index.html", r'<header class="reference-header', "diagnostics must use reference header")
require("docs/diagnostics/index.html", r'reference-header-tools.*data-diagnostic-search', "diagnostic search must be pulled into header")
require("status/index.html", r'<header class="reference-header', "status must use compact reference header")
require("learn/book/chapter-10/index.html", r'<header class="reference-header book-chapter-hero', "book chapters must use reference header")

# Frozen/current routes should use the same hierarchy.
require("docs/1.0/stdlib/index.html", r'<header class="reference-header', "versioned stdlib hierarchy differs")
require("learn/1.0/book/chapter-10/index.html", r'<header class="reference-header book-chapter-hero', "versioned book hierarchy differs")

# The old generic hero should survive only on intentionally unclassified routes.
for p in [ROOT/'packages/index.html', ROOT/'status/index.html', ROOT/'docs/stdlib/index.html', ROOT/'docs/diagnostics/index.html']:
    if 'class="page-hero' in p.read_text(encoding='utf-8'):
        errors.append(f"{p.relative_to(ROOT)}: still uses generic page hero")

if errors:
    for e in errors: print("ERROR", e)
    raise SystemExit(1)
print("OK: v25 page-opening hierarchy")
