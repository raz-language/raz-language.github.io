#!/usr/bin/env python3
"""Validate the Raz static site, generated surfaces, and deployment artifact."""
from pathlib import Path
from html.parser import HTMLParser
import argparse
import json
import re
import shutil
import subprocess
import sys

SOURCE_ROOT = Path(__file__).resolve().parents[1]


class PageParser(HTMLParser):
    def __init__(self, path):
        super().__init__(convert_charrefs=True)
        self.path = path
        self.ids = set()
        self.duplicate_ids = set()
        self.refs = []
        self.h1_count = 0
        self.has_title = False
        self.has_description = False
        self.has_viewport = False
        self.has_lang = False
        self.blank_target_links = []
        self.missing_alt = 0
        self.invalid_attributes = []
        self.nested_interactive = []
        self._anchor_depth = 0
        self._button_depth = 0

    def handle_starttag(self, tag, attrs):
        for name, _value in attrs:
            if not name or not re.fullmatch(r"[A-Za-z_:][A-Za-z0-9_:.\-]*", name):
                self.invalid_attributes.append(name or "<empty>")
        if tag == "a":
            if self._anchor_depth:
                self.nested_interactive.append("nested <a>")
            self._anchor_depth += 1
        if tag == "button":
            if self._button_depth:
                self.nested_interactive.append("nested <button>")
            self._button_depth += 1
        d = dict(attrs)
        if tag == "html" and d.get("lang"):
            self.has_lang = True
        if tag == "title":
            self.has_title = True
        if tag == "meta" and d.get("name") == "description" and d.get("content"):
            self.has_description = True
        if tag == "meta" and d.get("name") == "viewport" and d.get("content"):
            self.has_viewport = True
        if tag == "h1":
            self.h1_count += 1
        ident = d.get("id")
        if ident:
            if ident in self.ids:
                self.duplicate_ids.add(ident)
            self.ids.add(ident)
        if tag == "img" and "alt" not in d:
            self.missing_alt += 1
        if tag == "a" and d.get("target") == "_blank":
            rel = set((d.get("rel") or "").split())
            if "noopener" not in rel:
                self.blank_target_links.append(d.get("href") or "")
        for attr in ("href", "src"):
            value = d.get(attr)
            if value:
                self.refs.append((attr, value))

    def handle_endtag(self, tag):
        if tag == "a" and self._anchor_depth:
            self._anchor_depth -= 1
        if tag == "button" and self._button_depth:
            self._button_depth -= 1


def parse_pages(root):
    parsed = {}
    errors = []
    for path in sorted(root.rglob("*.html")):
        parser = PageParser(path)
        try:
            raw_text = path.read_text(encoding="utf-8")
            if "@@TOKEN" in raw_text:
                errors.append(f"{path}: unresolved Markdown token placeholder")
            parser.feed(raw_text)
        except Exception as error:
            errors.append(f"{path}: HTML parser error: {error}")
            continue
        parsed[path.resolve()] = parser
        if not parser.has_title:
            errors.append(f"{path}: missing <title>")
        if not parser.has_description:
            errors.append(f"{path}: missing meta description")
        if not parser.has_viewport:
            errors.append(f"{path}: missing viewport meta")
        if not parser.has_lang:
            errors.append(f"{path}: missing html lang")
        if parser.h1_count != 1:
            errors.append(f"{path}: expected exactly one h1, found {parser.h1_count}")
        if parser.duplicate_ids:
            errors.append(f"{path}: duplicate ids: {', '.join(sorted(parser.duplicate_ids))}")
        if parser.invalid_attributes:
            errors.append(f"{path}: malformed HTML attribute name(s): {', '.join(sorted(set(parser.invalid_attributes)))}")
        if parser.nested_interactive:
            errors.append(f"{path}: invalid interactive nesting: {', '.join(sorted(set(parser.nested_interactive)))}")
        if parser.missing_alt:
            errors.append(f"{path}: {parser.missing_alt} image(s) missing alt")
        for href in parser.blank_target_links:
            errors.append(f"{path}: target=_blank link missing rel=noopener: {href}")
    return parsed, errors


def resolve_local(path, raw, root):
    if raw.startswith(("http://", "https://", "mailto:", "tel:", "data:", "javascript:")):
        return None, None
    clean, sep, fragment = raw.partition("#")
    clean = clean.split("?", 1)[0]
    if clean.startswith("/"):
        target = (root / clean.lstrip("/")).resolve()
    elif clean:
        target = (path.parent / clean).resolve()
    else:
        target = path.resolve()
    if target.is_dir():
        target = target / "index.html"
    return target, fragment if sep else None


def validate_refs(root, parsed):
    errors = []
    root_resolved = root.resolve()
    for path, parser in parsed.items():
        for attr, raw in parser.refs:
            target, fragment = resolve_local(path, raw, root)
            if target is None:
                continue
            try:
                target.relative_to(root_resolved)
            except ValueError:
                errors.append(f"{path}: local {attr} escapes site root: {raw}")
                continue
            if not target.exists():
                errors.append(f"{path}: broken {attr}: {raw}")
                continue
            if fragment and target.suffix.lower() == ".html":
                target_parser = parsed.get(target.resolve())
                if target_parser and fragment not in target_parser.ids:
                    errors.append(f"{path}: broken fragment {raw}")
    return errors


def load_json(path, errors):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception as error:
        errors.append(f"{path}: invalid JSON: {error}")
        return None


def validate_generated(root, errors, warnings):
    generated = root / "data" / "generated"
    api = root / "api" / "v1"
    packages = None
    docs = None
    site = None

    if generated.exists():
        for required in ["packages.json", "docs.json", "releases.json", "site.json", "source-audit.json", "diagnostics.json", "stdlib.json", "book.json", "package-docs.json"]:
            if not (generated / required).exists():
                errors.append(f"missing data/generated/{required}")
        if (generated / "packages.json").exists():
            packages = load_json(generated / "packages.json", errors)
        if (generated / "docs.json").exists():
            docs = load_json(generated / "docs.json", errors)
        if (generated / "site.json").exists():
            site = load_json(generated / "site.json", errors)

    for required in ["index.json", "packages.json", "docs.json", "releases.json", "site.json", "source-audit.json", "diagnostics.json", "stdlib.json", "book.json", "package-docs.json"]:
        if not (api / required).exists():
            errors.append(f"missing api/v1/{required}")
        else:
            load_json(api / required, errors)

    if packages is None and (api / "packages.json").exists():
        packages = load_json(api / "packages.json", errors)
    if docs is None and (api / "docs.json").exists():
        docs = load_json(api / "docs.json", errors)
    if site is None and (api / "site.json").exists():
        site = load_json(api / "site.json", errors)

    if packages:
        seen = set()
        for package in packages:
            name = package.get("name")
            if not name or name in seen:
                errors.append(f"package catalog has invalid/duplicate name: {name}")
                continue
            seen.add(name)
            versions = package.get("versions") or []
            if versions and versions[0].get("version") != package.get("version"):
                errors.append(f"package {name}: latest version does not match first version-history record")
            page = root / "packages" / name / "index.html"
            if not page.exists():
                errors.append(f"package {name}: missing generated detail page")
            for version in versions:
                if not version.get("checksum") or not version.get("archive"):
                    errors.append(f"package {name} {version.get('version')}: incomplete version-history record")

    if docs:
        slugs = set()
        for doc in docs:
            slug = doc.get("slug")
            if slug in slugs:
                errors.append(f"duplicate documentation slug: {slug}")
            slugs.add(slug)
            if doc.get("available"):
                page = root / "docs" / "reference" / slug / "index.html"
                if not page.exists():
                    errors.append(f"hosted doc {doc.get('title')}: missing {page.relative_to(root)}")

    stdlib = None
    if generated.exists() and (generated / "stdlib.json").exists():
        stdlib = load_json(generated / "stdlib.json", errors)
    elif (api / "stdlib.json").exists():
        stdlib = load_json(api / "stdlib.json", errors)
    if stdlib:
        module_slugs = set()
        expected_item_pages = 0
        for module in stdlib.get("modules", []):
            slug = module.get("slug")
            if not slug:
                errors.append(f"stdlib module {module.get('name')}: missing slug")
                continue
            if slug in module_slugs:
                errors.append(f"stdlib duplicate module slug: {slug}")
            module_slugs.add(slug)
            module_page = root / "docs" / "stdlib" / Path(slug) / "index.html"
            if not module_page.exists():
                errors.append(f"stdlib module {module.get('name')}: missing generated module page")
            module_api = root / "api" / "v1" / "stdlib" / "modules" / Path(slug) / "index.json"
            if not module_api.exists():
                errors.append(f"stdlib module {module.get('name')}: missing module API JSON")
            item_slugs = set()
            for item in module.get("items", []):
                item_slug = item.get("slug")
                if not item_slug:
                    errors.append(f"stdlib module {module.get('name')}: item missing slug")
                    continue
                if item_slug in item_slugs:
                    errors.append(f"stdlib module {module.get('name')}: duplicate item slug {item_slug}")
                item_slugs.add(item_slug)
                expected_item_pages += 1
                item_page = root / "docs" / "stdlib" / Path(slug) / Path(item_slug) / "index.html"
                if not item_page.exists():
                    errors.append(f"stdlib item {module.get('name')}::{item.get('name')}: missing generated item page")
        if stdlib.get("generated_module_pages") not in (None, len(module_slugs)):
            errors.append("stdlib generated module-page count does not match module catalog")
        if stdlib.get("generated_item_pages") not in (None, expected_item_pages):
            errors.append("stdlib generated item-page count does not match item catalog")

    book = None
    if generated.exists() and (generated / "book.json").exists():
        book = load_json(generated / "book.json", errors)
    elif (api / "book.json").exists():
        book = load_json(api / "book.json", errors)
    if book:
        chapters = book.get("chapters") or []
        if book.get("chapter_count") != 29 or len(chapters) != 29:
            errors.append(f"Raz Book: expected 29 chapters, found {len(chapters)}")
        numbers = [item.get("number") for item in chapters]
        if numbers != list(range(1, 30)):
            errors.append("Raz Book: chapter numbering is not contiguous 1..29")
        for chapter in chapters:
            slug = chapter.get("slug")
            page = root / "learn" / "book" / str(slug) / "index.html"
            if not page.exists():
                errors.append(f"Raz Book chapter {chapter.get('number')}: missing generated page")
        if not (root / "learn" / "book" / "index.html").exists():
            errors.append("Raz Book: missing book index page")

    package_docs = None
    if generated.exists() and (generated / "package-docs.json").exists():
        package_docs = load_json(generated / "package-docs.json", errors)
    elif (api / "package-docs.json").exists():
        package_docs = load_json(api / "package-docs.json", errors)
    if package_docs:
        package_names = set()
        for package in package_docs:
            name = package.get("name")
            if not name or name in package_names:
                errors.append(f"package docs catalog has invalid/duplicate package: {name}")
                continue
            package_names.add(name)
            docs_page = root / "packages" / name / "docs" / "index.html"
            if not docs_page.exists():
                errors.append(f"package docs {name}: missing docs landing page")
            package_api = root / "api" / "v1" / "packages" / name / "index.json"
            if not package_api.exists():
                errors.append(f"package docs {name}: missing package API JSON")
            module_names = set()
            for module in package.get("modules", []):
                module_name = module.get("name")
                if not module_name or module_name in module_names:
                    errors.append(f"package docs {name}: invalid/duplicate module {module_name}")
                    continue
                module_names.add(module_name)
                module_page = root / "packages" / name / "docs" / "module" / Path(*module_name.split("::")) / "index.html"
                if not module_page.exists():
                    errors.append(f"package docs {name}: missing module page {module_name}")
                symbol_routes = set()
                for symbol in module.get("symbols", []):
                    slug = symbol.get("slug")
                    if not slug or slug in symbol_routes:
                        errors.append(f"package docs {name}/{module_name}: invalid/duplicate symbol route {slug}")
                        continue
                    symbol_routes.add(slug)
                    symbol_page = module_page.parent / Path(slug) / "index.html"
                    if not symbol_page.exists():
                        errors.append(f"package docs {name}/{module_name}: missing symbol page {symbol.get('name')}")

    audit = None
    if generated.exists() and (generated / "source-audit.json").exists():
        audit = load_json(generated / "source-audit.json", errors)
    elif (api / "source-audit.json").exists():
        audit = load_json(api / "source-audit.json", errors)
    if audit:
        for item in audit.get("warnings", []):
            warnings.append(f"source audit [{item.get('code')}]: {item.get('message')}")

    for rel in ["api/v1/status.json", "api/v1/versions.json"]:
        if not (root / rel).exists():
            errors.append(f"missing {rel}")
    if (root / "vercel.json").exists():
        load_json(root / "vercel.json", errors)

    security = root / ".well-known" / "security.txt"
    if not security.exists():
        errors.append("missing .well-known/security.txt")
    else:
        text = security.read_text(encoding="utf-8")
        for field in ("Contact:", "Expires:", "Policy:"):
            if field not in text:
                errors.append(f"security.txt missing {field}")
    if not (root / "llms.txt").exists():
        errors.append("missing llms.txt")


def validate_required(root, source_mode, errors):
    public_required = [
        "assets/styles.css",
        "assets/site.js",
        "assets/search-core.json",
        "assets/search-api.json",
        "site.webmanifest",
        "robots.txt",
        "404.html",
        "index.html",
        "status/index.html",
        "_headers",
        "_redirects",
        "vercel.json",
        "performance-budget.json",
    ]
    for required in public_required:
        if not (root / required).exists():
            errors.append(f"missing {required}")
    if source_mode:
        for required in [
            "scripts/sync_site.py",
            "scripts/stage_site.py",
            "data/raw/packages-index.txt",
            "data/raw/packages-search.txt",
        ]:
            if not (root / required).exists():
                errors.append(f"missing {required}")


def validate_js(root, errors):
    node = shutil.which("node")
    if not node:
        return False
    for rel in ["assets/site.js"]:
        path = root / rel
        if not path.exists():
            continue
        result = subprocess.run([node, "--check", str(path)], capture_output=True, text=True)
        if result.returncode:
            errors.append(f"{rel} syntax: {result.stderr.strip()}")
    return True


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", default=str(SOURCE_ROOT), help="site root to validate")
    args = parser.parse_args()
    root = Path(args.root).resolve()
    if not root.exists():
        raise SystemExit(f"site root does not exist: {root}")

    source_mode = (root / "scripts" / "sync_site.py").exists()
    warnings = []
    parsed, errors = parse_pages(root)
    errors.extend(validate_refs(root, parsed))
    validate_required(root, source_mode, errors)
    validate_generated(root, errors, warnings)
    js = validate_js(root, errors)

    for warning in warnings:
        print("WARN", warning)
    if errors:
        for error in errors:
            print("ERROR", error)
        raise SystemExit(1)

    print(
        f"OK: {len(parsed)} HTML pages; local files + fragments resolve; generated surfaces valid; "
        f"accessibility metadata present" + ("; JavaScript parses" if js else "")
    )


if __name__ == "__main__":
    main()
