#!/usr/bin/env python3
"""Build changing Raz website surfaces from canonical repository data.

The deployed output remains ordinary static HTML/CSS/JS. `--refresh` fetches
public data from the Raz GitHub repositories before rendering; `--offline`
uses the checked-in snapshot under data/raw so local builds stay deterministic.
"""
from pathlib import Path
from urllib.request import Request, urlopen
from urllib.error import URLError, HTTPError
from datetime import datetime, timezone
import argparse
import html
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw"
DOC_RAW = RAW / "docs"
GEN = ROOT / "data" / "generated"
API = ROOT / "api" / "v1"
GITHUB = "https://github.com/raz-language"
RAZ = f"{GITHUB}/raz"
PACKAGES_REPO = f"{GITHUB}/packages"
INSTALLER = f"{GITHUB}/installer"

URLS = {
    "packages-search.txt": "https://raw.githubusercontent.com/raz-language/packages/main/search.txt",
    "packages-index.txt": "https://raw.githubusercontent.com/raz-language/packages/main/index.txt",
    "docs-readme.md": "https://raw.githubusercontent.com/raz-language/raz/main/docs/README.md",
    "platform-support.md": "https://raw.githubusercontent.com/raz-language/raz/main/docs/PLATFORM-SUPPORT.md",
    "security.md": "https://raw.githubusercontent.com/raz-language/raz/main/SECURITY.md",
    "nightly.txt": "https://raw.githubusercontent.com/raz-language/installer/main/channels/nightly.txt",
    "releases.json": "https://api.github.com/repos/raz-language/installer/releases",
    "raz-repo.json": "https://api.github.com/repos/raz-language/raz",
    "package-roadmap.md": "https://raw.githubusercontent.com/raz-language/packages/main/sources/PACKAGES.md",
}

CATEGORY_MAP = {
    "archive": "archive", "compression": "archive", "zstd": "archive",
    "base58": "security", "bech32": "security", "crypto": "security", "jwt": "security",
    "merkle": "security", "secp256k1": "security", "uuid": "security",
    "bigint": "numeric", "decimal": "numeric",
    "cbor": "data", "csv": "data", "encoding": "data", "json": "data", "msgpack": "data",
    "protobuf": "data", "rlp": "data", "serde": "data", "ssz": "data", "toml": "data",
    "xml": "data", "yaml": "data",
    "dns": "web", "graphql": "web", "http-router": "web", "http3": "web", "multipart": "web",
    "oauth2": "web", "quic": "web", "rpc": "web", "websocket": "web",
    "postgres": "database", "redis": "database", "sqlite": "database",
    "metrics": "runtime", "mmap": "runtime", "tracing": "runtime", "uring": "runtime",
    "wasm-component": "runtime", "wasm-runtime": "runtime",
    "datetime": "utility", "regex": "utility", "semver": "utility", "testing": "dev",
}

BASE_SEARCH = [
    ("Home", "Overview of Raz, its design and toolchain", "index.html", "overview language systems performance safety"),
    ("Learn Raz", "Install, create a project, and learn the core syntax", "learn/index.html", "learn getting started syntax first program"),
    ("Documentation", "Documentation portal for the language and toolchain", "docs/index.html", "docs documentation reference specification"),
    ("Language guide", "Core language model, types, ownership and syntax", "docs/language/index.html", "language ownership borrowing types syntax"),
    ("Toolchain guide", "Projects, CLI, packages, tests and editor tooling", "docs/toolchain/index.html", "cli raz build run test fmt packages lsp"),
    ("Compiler guide", "HIR, MIR, Forge, LLVM, WebAssembly and RXE", "docs/compiler/index.html", "compiler backend forge llvm wasm rxe mir hir"),
    ("Install Raz", "Install releases or build the toolchain from source", "install/index.html", "install download windows linux razup"),
    ("Releases", "Published toolchains, channel status and source", "releases/index.html", "release stable nightly downloads checksums"),
    ("Packages", "Search the official Raz package catalog", "packages/index.html", "packages registry dependencies"),
    ("Tools", "Raz CLI, Forge, ObLink, LSP and C interoperability", "tools/index.html", "tools forge oblink lsp bindgen c-header"),
    ("WebAssembly", "Portable WebAssembly and RXE targets", "web/index.html", "wasm webassembly rxe portable target"),
    ("Community", "Repositories, contributing, security and project links", "community/index.html", "community github contributing security repos"),
]


def esc(value):
    return html.escape(str(value), quote=True)


def fetch(url):
    headers = {"Accept": "application/vnd.github+json", "User-Agent": "raz-website-sync/1"}
    token = os.getenv("GITHUB_TOKEN")
    if token:
        headers["Authorization"] = f"Bearer {token}"
    with urlopen(Request(url, headers=headers), timeout=30) as response:
        return response.read().decode("utf-8")


def doc_repo_path(path):
    return path[3:] if path.startswith("../") else f"docs/{path}"


def doc_slug(path):
    name = Path(path).name.rsplit(".", 1)[0].lower()
    return re.sub(r"[^a-z0-9]+", "-", name).strip("-")


def doc_cache_path(path):
    return DOC_RAW / Path(path).name


def raw_doc_url(path):
    return f"https://raw.githubusercontent.com/raz-language/raz/main/{doc_repo_path(path)}"


def parse_doc_index_text(text):
    category = None
    result = []
    for line in text.splitlines():
        if line.startswith("## "):
            category = line[3:].strip()
        match = re.match(r"^\| \[([^]]+)\]\(([^)]+)\) \| (.+) \|$", line)
        if not match or not category:
            continue
        title, path, description = match.groups()
        result.append({"title": title, "path": path, "description": description, "category": category})
    return result



def refresh_package_docs():
    """Synchronize official package README/manifest/source files for static API docs."""
    PACKAGE_DOC_RAW.mkdir(parents=True, exist_ok=True)
    packages = []
    search_path = RAW / "packages-search.txt"
    if search_path.exists():
        for line in search_path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                packages.append(line.split("\t", 1)[0])
    wanted = set(packages)
    for child in list(PACKAGE_DOC_RAW.iterdir()):
        if child.is_dir() and child.name not in wanted:
            shutil.rmtree(child)

    tree_url = "https://api.github.com/repos/raz-language/packages/git/trees/main?recursive=1"
    tree_payload = json.loads(fetch(tree_url))
    entries = tree_payload.get("tree", [])
    paths = []
    for entry in entries:
        path = entry.get("path", "")
        if entry.get("type") != "blob" or not path.startswith("sources/"):
            continue
        parts = path.split("/")
        if len(parts) < 3 or parts[1] not in wanted:
            continue
        relative = "/".join(parts[2:])
        if relative in {"README.md", "raz.toml"} or (relative.startswith("src/") and relative.endswith(".rz")):
            paths.append((parts[1], relative, path))

    def grab(item):
        package, relative, repository_path = item
        url = f"https://raw.githubusercontent.com/raz-language/packages/main/{repository_path}"
        return package, relative, fetch(url)

    for package in wanted:
        target = PACKAGE_DOC_RAW / package
        if target.exists():
            shutil.rmtree(target)
        target.mkdir(parents=True, exist_ok=True)

    errors = []
    with ThreadPoolExecutor(max_workers=8) as pool:
        futures = {pool.submit(grab, item): item for item in paths}
        for future in as_completed(futures):
            item = futures[future]
            try:
                package, relative, text = future.result()
                target = PACKAGE_DOC_RAW / package / relative
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_text(text, encoding="utf-8")
            except Exception as error:
                errors.append((item[2], str(error)))
    state = {
        "packages": len(wanted),
        "files": len(paths) - len(errors),
        "errors": [{"path": path, "error": message} for path, message in errors],
    }
    (RAW / "package-docs-state.json").write_text(json.dumps(state, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    if errors:
        print(f"warning: {len(errors)} package source file(s) could not be synchronized")

def refresh_raw():
    RAW.mkdir(parents=True, exist_ok=True)
    DOC_RAW.mkdir(parents=True, exist_ok=True)
    state = {
        "snapshot_generated_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        "sources": {},
    }
    for name, url in URLS.items():
        text = fetch(url)
        if name.endswith(".json"):
            text = json.dumps(json.loads(text), indent=2, sort_keys=True) + "\n"
        (RAW / name).write_text(text, encoding="utf-8")
        state["sources"][name] = {"url": url}

    docs_state = {}
    indexed = parse_doc_index_text((RAW / "docs-readme.md").read_text(encoding="utf-8"))
    expected = {Path(item["path"]).name for item in indexed}
    for old in DOC_RAW.glob("*.md"):
        if old.name not in expected:
            old.unlink()
    for item in indexed:
        path = item["path"]
        url = raw_doc_url(path)
        key = Path(path).name
        try:
            text = fetch(url)
            target = doc_cache_path(path)
            target.write_text(text, encoding="utf-8")
            docs_state[key] = {
                "available": True,
                "url": url,
                "sha256": hashlib.sha256(text.encode("utf-8")).hexdigest(),
            }
        except HTTPError as error:
            if error.code != 404:
                raise
            target = doc_cache_path(path)
            if target.exists():
                target.unlink()
            docs_state[key] = {"available": False, "url": url, "status": 404}
    (RAW / "docs-state.json").write_text(json.dumps(docs_state, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    refresh_package_docs()
    (RAW / "source-state.json").write_text(json.dumps(state, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def parse_package_versions():
    versions = {}
    path = RAW / "packages-index.txt"
    if not path.exists():
        return versions
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        name, version, archive, checksum = line.split(None, 3)
        versions.setdefault(name, []).append({
            "version": version,
            "archive": archive,
            "checksum": checksum,
            "source_url": f"{PACKAGES_REPO}/blob/main/{archive}",
        })
    return versions


def version_key(value):
    main = value.split("-", 1)[0]
    parts = []
    for part in main.split("."):
        try:
            parts.append(int(part))
        except ValueError:
            parts.append(0)
    return tuple(parts)


def parse_packages():
    history = parse_package_versions()
    result = []
    for line in (RAW / "packages-search.txt").read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        name, version, owner, description = line.split("\t", 3)
        versions = sorted(history.get(name, []), key=lambda item: version_key(item["version"]), reverse=True)
        result.append({
            "name": name,
            "version": version,
            "owner": owner,
            "description": description,
            "category": CATEGORY_MAP.get(name, "utility"),
            "versions": versions,
        })
    return sorted(result, key=lambda item: item["name"])

def parse_docs():
    text = (RAW / "docs-readme.md").read_text(encoding="utf-8")
    state_path = RAW / "docs-state.json"
    state = json.loads(state_path.read_text(encoding="utf-8")) if state_path.exists() else {}
    result = []
    for item in parse_doc_index_text(text):
        path = item["path"]
        filename = Path(path).name
        source_url = f"{RAZ}/blob/main/{doc_repo_path(path)}"
        cache = doc_cache_path(path)
        available = cache.exists()
        info = state.get(filename, {})
        item.update({
            "url": source_url,
            "slug": doc_slug(path),
            "available": available,
            "local_url": f'reference/{doc_slug(path)}/index.html' if available else None,
            "sha256": info.get("sha256") or (hashlib.sha256(cache.read_bytes()).hexdigest() if available else None),
        })
        result.append(item)
    return result


def parse_platforms():
    text = (RAW / "platform-support.md").read_text(encoding="utf-8")
    result = []
    for line in text.splitlines():
        if not line.startswith("| `"):
            continue
        columns = [part.strip().strip("`") for part in line.strip("|").split("|")]
        if len(columns) >= 5:
            result.append({"target": columns[0], "host_use": columns[1], "backend": columns[2], "abi": columns[3], "object": columns[4]})
    return result


def parse_channel(path):
    result = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        if "=" in line:
            key, value = line.split("=", 1)
            result[key.strip()] = value.strip()
    return result


def build_data():
    GEN.mkdir(parents=True, exist_ok=True)
    packages = parse_packages()
    docs = parse_docs()
    platforms = parse_platforms()
    raw_releases = json.loads((RAW / "releases.json").read_text(encoding="utf-8"))
    nightly = parse_channel(RAW / "nightly.txt")
    repo = json.loads((RAW / "raz-repo.json").read_text(encoding="utf-8"))
    source_state = json.loads((RAW / "source-state.json").read_text(encoding="utf-8"))

    releases = []
    for release in raw_releases:
        releases.append({
            "tag": release.get("tag_name"),
            "name": release.get("name") or release.get("tag_name"),
            "published_at": release.get("published_at"),
            "prerelease": bool(release.get("prerelease")),
            "url": release.get("html_url"),
            "assets": [
                {"name": asset.get("name"), "size": asset.get("size"), "url": asset.get("browser_download_url")}
                for asset in release.get("assets", [])
            ],
        })

    license_value = repo.get("license", "Apache-2.0")
    if isinstance(license_value, dict):
        license_value = license_value.get("spdx_id") or license_value.get("name")
    security_text = (RAW / "security.md").read_text(encoding="utf-8") if (RAW / "security.md").exists() else ""
    source_warnings = []
    if "pre-1.0" in security_text.lower():
        source_warnings.append({
            "code": "security-version-drift",
            "message": "SECURITY.md still describes Raz as pre-1.0 while the language stability contract declares Raz 1.0 stable.",
            "source": "raz-language/raz/SECURITY.md",
        })
    docs_state_path = RAW / "docs-state.json"
    if docs_state_path.exists():
        docs_state = json.loads(docs_state_path.read_text(encoding="utf-8"))
        for filename, info in sorted(docs_state.items()):
            if not info.get("available", False):
                source_warnings.append({
                    "code": "missing-indexed-doc",
                    "message": f"The canonical documentation index references {filename}, but the source path was unavailable during synchronization.",
                    "source": filename,
                })

    site = {
        "language": {"version": "1.0", "stability": "stable"},
        "repository": {
            "full_name": repo.get("full_name", "raz-language/raz"),
            "description": repo.get("description", ""),
            "default_branch": repo.get("default_branch", "main"),
            "license": license_value,
            "pushed_at": repo.get("pushed_at"),
        },
        "binary_releases": {
            "published": bool(releases),
            "count": len(releases),
            "latest": releases[0] if releases else None,
            "nightly": nightly,
        },
        "platforms": platforms,
        "snapshot": source_state,
        "source_audit": {"warnings": source_warnings, "warning_count": len(source_warnings)},
    }

    for filename, value in [
        ("packages.json", packages),
        ("docs.json", docs),
        ("releases.json", releases),
        ("site.json", site),
        ("source-audit.json", site["source_audit"]),
    ]:
        (GEN / filename).write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return packages, docs, releases, site


def shell_parts(path):
    text = path.read_text(encoding="utf-8")
    hero = re.search(r'<header class="page-hero(?: [^"]*)?">', text)
    if not hero:
        raise ValueError(f"page shell has no page hero: {path}")
    before_hero = text[:hero.start()]
    footer_marker = '<footer class="site-footer">'
    if footer_marker not in text:
        raise ValueError(f"page shell has no site footer: {path}")
    footer = footer_marker + text.split(footer_marker, 1)[1]
    return before_hero, footer


def rewrite_head(pre, title, description):
    pre = re.sub(r"<title>.*?</title>", f"<title>{esc(title)}</title>", pre, flags=re.S)
    replacements = [
        (r'(<meta name="description" content=")[^"]*(">)', description),
        (r'(<meta property="og:title" content=")[^"]*(">)', title),
        (r'(<meta property="og:description" content=")[^"]*(">)', description),
        (r'(<meta name="twitter:title" content=")[^"]*(">)', title),
        (r'(<meta name="twitter:description" content=")[^"]*(">)', description),
    ]
    for pattern, value in replacements:
        pre = re.sub(pattern, lambda m: m.group(1) + esc(value) + m.group(2), pre)
    return pre


def package_card(package):
    searchable = f"{package['name']} {package['description']} {package['category']}".lower()
    history = len(package.get("versions", []))
    history_text = f"{history} version{'s' if history != 1 else ''}" if history else "registry package"
    return f'''<article class="package-item" data-package data-name="{esc(package['name'])}" data-category="{esc(package['category'])}" data-search="{esc(searchable)}">
      <a class="package-item-link" href="{esc(package['name'])}/index.html"><div><span>{esc(package['category'].upper())}</span><div class="package-title-row"><h3>{esc(package['name'])}</h3><small>v{esc(package['version'])}</small></div><p>{esc(package['description'])}</p><small class="package-history-count">{esc(history_text)}</small></div><b>View package →</b></a>
      <button type="button" class="copy-command" data-copy="raz add {esc(package['name'])}">raz add {esc(package['name'])}</button>
    </article>'''


def package_history(package):
    versions = package.get("versions", [])
    if not versions:
        return '<div class="empty-state inline-empty">No version-history records are present in the registry snapshot.</div>'
    rows = []
    for index, item in enumerate(versions):
        latest = '<span class="mini-badge">LATEST</span>' if index == 0 else ''
        command = f"raz add {package['name']}@{item['version']}"
        rows.append(f'''<div class="version-row">
          <div><b>{esc(item['version'])}</b>{latest}</div>
          <code>{esc(item['checksum'])}</code>
          <div class="version-actions"><button type="button" data-copy="{esc(command)}">Copy install</button><a href="{esc(item['source_url'])}">Archive ↗</a></div>
        </div>''')
    return '<div class="version-history"><div class="version-row version-head"><span>Version</span><span>Tree checksum</span><span>Actions</span></div>' + ''.join(rows) + '</div>'


PACKAGE_DOC_RAW = RAW / "package-docs"


def _package_doc_slug(value):
    return re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-") or "item"


def _package_source_doc(package_name):
    base = PACKAGE_DOC_RAW / package_name
    readme = base / "README.md"
    manifest = base / "raz.toml"
    modules = []
    source_root = base / "src"
    source_files = sorted(source_root.rglob("*.rz")) if source_root.exists() else []
    for source in source_files:
        rel = source.relative_to(base).as_posix()
        text = source.read_text(encoding="utf-8")
        namespace_match = re.search(r"(?m)^\s*namespace\s+([^;{]+)", text)
        namespace = namespace_match.group(1).strip() if namespace_match else f"{package_name}::{source.stem}"
        symbols = []
        docs = []
        lines = text.splitlines()
        i = 0
        while i < len(lines):
            line = lines[i]
            stripped = line.strip()
            if stripped.startswith("///"):
                docs.append(stripped[3:].strip())
                i += 1
                continue
            m = re.match(r"^\s*public\s+(fn|struct|enum|trait|const|type)\s+([A-Za-z_][A-Za-z0-9_]*)", line)
            if m:
                kind, name = m.groups()
                sig_parts = [stripped]
                if kind == "fn":
                    balance = stripped.count("(") - stripped.count(")")
                    while balance > 0 and i + 1 < len(lines):
                        i += 1
                        nxt = lines[i].strip()
                        sig_parts.append(nxt)
                        balance += nxt.count("(") - nxt.count(")")
                sig = " ".join(sig_parts)
                sig = re.sub(r"\s*\{.*$", "", sig).strip()
                symbols.append({
                    "name": name,
                    "kind": kind,
                    "signature": sig,
                    "description": " ".join(docs).strip(),
                    "slug": f"{kind}/{_package_doc_slug(name)}",
                })
                docs = []
            elif stripped and not stripped.startswith("//"):
                docs = []
            i += 1
        modules.append({
            "name": namespace,
            "file": rel,
            "slug": _package_doc_slug(namespace.replace("::", "/")),
            "symbols": symbols,
            "source_url": f"{PACKAGES_REPO}/blob/main/sources/{package_name}/{rel}",
        })
    dependencies = []
    package_meta = {}
    if manifest.exists():
        section = None
        for raw in manifest.read_text(encoding="utf-8").splitlines():
            line = raw.strip()
            sec = re.match(r"^\[([^]]+)\]$", line)
            if sec:
                section = sec.group(1)
                continue
            kv = re.match(r'^([A-Za-z0-9_.-]+)\s*=\s*"([^"]*)"', line)
            if kv:
                key, value = kv.groups()
                if section == "package":
                    package_meta[key] = value
                elif section and section.endswith("dependencies"):
                    dependencies.append({"name": key, "requirement": value, "section": section})
    return {
        "available": readme.exists() or manifest.exists() or bool(modules),
        "readme": readme.read_text(encoding="utf-8") if readme.exists() else "",
        "manifest": manifest.read_text(encoding="utf-8") if manifest.exists() else "",
        "package": package_meta,
        "dependencies": dependencies,
        "modules": modules,
        "source_root": f"{PACKAGES_REPO}/tree/main/sources/{package_name}",
    }


def _render_package_readme(markdown):
    if not markdown.strip():
        return '<div class="empty-state inline-empty">Package README content is not present in this offline snapshot. A production refresh synchronizes it from the registry source tree.</div>'
    lines = markdown.splitlines()
    out = []
    paragraph = []
    in_list = False

    def flush_p():
        nonlocal paragraph
        if paragraph:
            text = ' '.join(x.strip() for x in paragraph).strip()
            if text:
                text = esc(text)
                text = re.sub(r'`([^`]+)`', r'<code>\1</code>', text)
                text = re.sub(r'\*\*([^*]+)\*\*', r'<strong>\1</strong>', text)
                out.append(f'<p>{text}</p>')
            paragraph = []

    def close_list():
        nonlocal in_list
        if in_list:
            out.append('</ul>')
            in_list = False

    for line in lines:
        if line.startswith('# '):
            continue
        if line.startswith('## '):
            flush_p(); close_list()
            ident = heading_slug(line[3:])
            out.append(f'<h2 id="{esc(ident)}">{esc(line[3:].strip())}</h2>')
            continue
        if line.startswith('### '):
            flush_p(); close_list()
            ident = heading_slug(line[4:])
            out.append(f'<h3 id="{esc(ident)}">{esc(line[4:].strip())}</h3>')
            continue
        m = re.match(r'^\s*[-*]\s+(.+)$', line)
        if m:
            flush_p()
            if not in_list:
                out.append('<ul>')
                in_list = True
            item = esc(m.group(1))
            item = re.sub(r'`([^`]+)`', r'<code>\1</code>', item)
            out.append(f'<li>{item}</li>')
            continue
        if not line.strip():
            flush_p(); close_list()
            continue
        paragraph.append(line)
    flush_p(); close_list()
    return ''.join(out)


def _package_symbol_page(package, module, symbol, module_page):
    page = module_page.parent / symbol['slug'] / 'index.html'
    page.parent.mkdir(parents=True, exist_ok=True)
    pre, footer = _shell_for_doc_page(page, f"{symbol['name']} — {module['name']} — {package['name']}", symbol.get('description') or symbol['signature'])
    module_href = _rel_href(page, module_page)
    package_href = _rel_href(page, ROOT / 'packages' / package['name'] / 'index.html')
    docs_href = _rel_href(page, ROOT / 'packages' / package['name'] / 'docs' / 'index.html')
    desc = symbol.get('description') or f"Public {symbol['kind']} exported by {module['name']}."
    body = f'''<header class="page-hero api-item-hero"><div class="shell narrow"><div class="doc-breadcrumbs"><a href="{esc(package_href)}">{esc(package['name'])}</a><span>/</span><a href="{esc(docs_href)}">API docs</a><span>/</span><a href="{esc(module_href)}">{esc(module['name'])}</a><span>/</span><span>{esc(symbol['name'])}</span></div><p class="kicker">{esc(symbol['kind'].upper())} · PACKAGE API</p><h1><code>{esc(symbol['name'])}</code></h1><p class="page-lead">{esc(desc)}</p></div></header>
<main id="main" class="after-hero"><section class="section section-white"><div class="shell api-item-layout"><article><p class="kicker">SIGNATURE</p><div class="api-signature-card"><code class="language-raz">{esc(symbol['signature'])}</code><button type="button" data-copy="{esc(symbol['signature'])}">Copy</button></div><div class="button-row"><a class="button button-secondary" href="{esc(module_href)}">← Back to module</a><a class="button button-secondary" href="{esc(module['source_url'])}">Source ↗</a></div></article><aside class="api-meta-card"><div><span>Package</span><a href="{esc(package_href)}">{esc(package['name'])}</a></div><div><span>Module</span><a href="{esc(module_href)}">{esc(module['name'])}</a></div><div><span>Kind</span><b>{esc(symbol['kind'])}</b></div><div><span>Version</span><b>{esc(package['version'])}</b></div></aside></div></section></main>'''
    page.write_text(pre + body + footer, encoding='utf-8')
    return page


def _render_package_module(package, module):
    page = ROOT / 'packages' / package['name'] / 'docs' / 'module' / Path(*module['name'].split('::')) / 'index.html'
    page.parent.mkdir(parents=True, exist_ok=True)
    pre, footer = _shell_for_doc_page(page, f"{module['name']} — {package['name']} package API", f"API reference for {module['name']} in the {package['name']} package.")
    package_href = _rel_href(page, ROOT / 'packages' / package['name'] / 'index.html')
    docs_href = _rel_href(page, ROOT / 'packages' / package['name'] / 'docs' / 'index.html')
    rows = []
    symbol_pages = []
    for symbol in module['symbols']:
        sym_page = _package_symbol_page(package, module, symbol, page)
        symbol_pages.append(sym_page)
        href = _rel_href(page, sym_page)
        description = f'<p>{esc(symbol["description"])}</p>' if symbol.get('description') else ''
        rows.append(f'<a class="api-item-row" href="{esc(href)}"><span class="api-kind">{esc(symbol["kind"])}</span><div><code class="language-raz">{esc(symbol["signature"])}</code>{description}</div><b>→</b></a>')
    empty = '' if rows else '<div class="empty-state inline-empty">No public declarations were extracted from this module in the current snapshot.</div>'
    body = f'''<header class="page-hero api-module-hero"><div class="shell narrow"><div class="doc-breadcrumbs"><a href="{esc(package_href)}">{esc(package['name'])}</a><span>/</span><a href="{esc(docs_href)}">API docs</a><span>/</span><span>{esc(module['name'])}</span></div><p class="kicker">PACKAGE MODULE</p><h1><code>{esc(module['name'])}</code></h1><p class="page-lead">{len(module['symbols'])} public declaration{'s' if len(module['symbols']) != 1 else ''} extracted from <code>{esc(module['file'])}</code>.</p><div class="button-row"><a class="button button-primary" href="{esc(module['source_url'])}">Source ↗</a><a class="button button-secondary" href="{esc(docs_href)}">Package docs</a></div></div></header>
<main id="main" class="after-hero"><section class="section section-white"><div class="shell"><div class="api-source-path"><span>Source</span><code>{esc(module['file'])}</code></div><div class="api-item-group"><div class="api-item-group-head"><h2>Public API</h2><span>{len(module['symbols'])}</span></div>{''.join(rows)}{empty}</div></div></section></main>'''
    page.write_text(pre + body + footer, encoding='utf-8')
    return page, symbol_pages


def render_package_docs(packages):
    catalog = []
    for package in packages:
        doc = _package_source_doc(package['name'])
        catalog.append({
            "name": package['name'], "version": package['version'], "available": doc['available'],
            "source_root": doc['source_root'], "package": doc['package'], "dependencies": doc['dependencies'],
            "modules": doc['modules'],
        })
        docs_dir = ROOT / 'packages' / package['name'] / 'docs'
        docs_dir.mkdir(parents=True, exist_ok=True)
        for child in list(docs_dir.iterdir()):
            if child.is_dir():
                shutil.rmtree(child)
            elif child.name != 'index.html':
                child.unlink()
        page = docs_dir / 'index.html'
        pre, footer = _shell_for_doc_page(page, f"{package['name']} API documentation — Raz packages", f"Source-derived documentation for the {package['name']} Raz package.")
        package_href = _rel_href(page, ROOT / 'packages' / package['name'] / 'index.html')
        readme_html = _render_package_readme(doc['readme'])
        dep_rows = ''.join(f'<div class="package-dependency-row"><code>{esc(dep["name"])}</code><span>{esc(dep["requirement"])}</span><small>{esc(dep["section"])}</small></div>' for dep in doc['dependencies']) or '<div class="empty-state inline-empty">No package dependencies are present in the synchronized manifest.</div>'
        module_rows = []
        for module in doc['modules']:
            module_page, _ = _render_package_module(package, module)
            href = _rel_href(page, module_page)
            module_rows.append(f'<a class="package-api-module-row" href="{esc(href)}"><div><code>{esc(module["name"])}</code><span>{esc(module["file"])}</span></div><b>{len(module["symbols"])} public items →</b></a>')
        modules_html = ''.join(module_rows) or f'<div class="empty-state inline-empty">Source modules are not cached in this offline snapshot. <a href="{esc(doc["source_root"])}">Browse the canonical source tree ↗</a></div>'
        manifest_meta = doc['package']
        kind = manifest_meta.get('kind', '—')
        entry = manifest_meta.get('entry', '—')
        status = 'Source synchronized' if doc['available'] else 'Source expands during production refresh'
        body = f'''<header class="page-hero package-docs-hero"><div class="shell narrow"><div class="doc-breadcrumbs"><a href="{esc(package_href)}">{esc(package['name'])}</a><span>/</span><span>API docs</span></div><p class="kicker">OFFICIAL PACKAGE · API DOCUMENTATION</p><h1><code>{esc(package['name'])}</code> documentation</h1><p class="page-lead">{esc(package['description'])}</p><div class="package-version-row"><span>Version <b>{esc(package['version'])}</b></span><span>Kind <b>{esc(kind)}</b></span><span>{esc(status)}</span></div><div class="button-row"><a class="button button-primary" href="{esc(doc['source_root'])}">Package source ↗</a><a class="button button-secondary" href="{esc(package_href)}">Versions & install</a></div></div></header>
<main id="main" class="after-hero"><section class="section section-white"><div class="shell package-docs-layout"><article class="package-readme"><p class="kicker">OVERVIEW</p>{readme_html}</article><aside class="package-meta-card"><div><span>Version</span><b>{esc(package['version'])}</b></div><div><span>Kind</span><b>{esc(kind)}</b></div><div><span>Entry</span><code>{esc(entry)}</code></div><div><span>Modules</span><b>{len(doc['modules'])}</b></div></aside></div></section>
<section class="section section-soft"><div class="shell"><div class="section-top compact"><div><p class="kicker">MODULES</p><h2>Browse the source-derived API.</h2></div><p>Routes are generated from the package's canonical <code>sources/{esc(package['name'])}/src</code> tree.</p></div><div class="package-api-module-list">{modules_html}</div></div></section>
<section class="section section-white"><div class="shell"><div class="section-top compact"><div><p class="kicker">DEPENDENCIES</p><h2>Manifest dependency surface.</h2></div><p>Read directly from the synchronized <code>raz.toml</code>; path dependencies shown here describe the registry source workspace.</p></div><div class="package-dependency-list">{dep_rows}</div></div></section></main>'''
        page.write_text(pre + body + footer, encoding='utf-8')
    (GEN / 'package-docs.json').write_text(json.dumps(catalog, indent=2, sort_keys=True) + '\n', encoding='utf-8')
    return catalog

def render_packages(packages):
    page = ROOT / "packages" / "index.html"
    pre, footer = shell_parts(page)
    categories = []
    for package in packages:
        if package["category"] not in categories:
            categories.append(package["category"])
    filters = '<button class="active" data-package-filter="all">All</button>' + "".join(
        f'<button data-package-filter="{esc(category)}">{esc(category.title())}</button>' for category in categories
    )
    cards = "".join(package_card(package) for package in packages)
    version_records = sum(len(package.get("versions", [])) for package in packages)
    source_cached = sum(1 for package in packages if _package_source_doc(package['name'])['available'])
    body = f'''<header class="page-hero"><div class="shell narrow"><p class="kicker">PACKAGES</p><h1>Build on the official Raz package ecosystem.</h1><p class="page-lead">Search immutable registry releases, then move directly into source-derived package documentation without leaving the Raz site.</p><div class="button-row"><a class="button button-primary" href="{PACKAGES_REPO}">Registry source ↗</a><a class="button button-secondary" href="{RAZ}/blob/main/docs/PACKAGE-MANAGEMENT.md">Package docs ↗</a></div></div></header>
<main id="main" class="after-hero"><section class="section section-white"><div class="shell">
  <div class="package-toolbar"><label><span class="sr-only">Search packages</span><input type="search" placeholder="Search packages…" data-package-search></label><div class="package-filters" aria-label="Filter packages">{filters}</div></div>
  <div class="registry-stats"><div><b>{len(packages)}</b><span>official packages</span></div><div><b>{version_records}</b><span>published versions</span></div><div><b>{source_cached}</b><span>source docs cached offline</span></div></div>
  <div class="data-freshness"><span class="live-dot"></span><span>Registry metadata comes from <code>search.txt</code>/<code>index.txt</code>; package docs come from <code>sources/&lt;package&gt;</code>.</span></div>
  <div class="package-count" data-package-count>{len(packages)} packages</div>
  <div class="package-catalog">{cards}</div><div class="empty-state" data-package-empty hidden>No packages match that search.</div>
</div></section></main>'''
    page.write_text(pre + body + footer, encoding="utf-8")

    valid = {package["name"] for package in packages}
    for child in (ROOT / "packages").iterdir():
        if child.is_dir() and child.name not in valid:
            shutil.rmtree(child)

    index_pre, index_footer = shell_parts(page)
    detail_pre = index_pre.replace('href="../', 'href="../../').replace('src="../', 'src="../../')
    detail_footer = index_footer.replace('href="../', 'href="../../').replace('src="../', 'src="../../')
    for package in packages:
        name = package["name"]
        title = f"{name} — Raz package"
        desc = package["description"]
        pre2 = rewrite_head(detail_pre, title, desc)
        metadata_url = f"{PACKAGES_REPO}/blob/main/metadata/{name}.json"
        latest = package.get("versions", [{}])[0] if package.get("versions") else {}
        latest_hash = latest.get("checksum", "—")
        history = package_history(package)
        source_doc = _package_source_doc(name)
        docs_state = 'Source API available' if source_doc['available'] else 'Source API generated on refresh'
        detail = f'''<header class="page-hero package-detail-hero"><div class="shell narrow"><div class="doc-breadcrumbs"><a href="../index.html">Packages</a><span>/</span><span>{esc(name)}</span></div><p class="kicker">{esc(package['category'].upper())} · OFFICIAL PACKAGE</p><h1><code>{esc(name)}</code></h1><p class="page-lead">{esc(desc)}</p><div class="package-version-row"><span>Latest <b>{esc(package['version'])}</b></span><span>Owner <b>{esc(package['owner'])}</b></span><span>{len(package.get('versions', []))} published version{'s' if len(package.get('versions', [])) != 1 else ''}</span></div><div class="button-row"><a class="button button-primary" href="docs/index.html">API documentation</a><a class="button button-secondary" href="{esc(source_doc['source_root'])}">Source ↗</a></div></div></header>
<main id="main" class="after-hero"><section class="section section-white"><div class="shell package-detail-grid"><article><p class="kicker">ADD TO A PROJECT</p><h2>Install the latest compatible release.</h2><div class="command-copy"><code>raz add {esc(name)}</code><button type="button" data-copy="raz add {esc(name)}">Copy</button></div><p>Raz resolves the package through the official registry and pins the selected immutable package tree in <code>raz.lock</code>.</p><p class="package-doc-state"><span class="live-dot"></span>{esc(docs_state)}</p></article><aside class="package-meta-card"><div><span>Version</span><b>{esc(package['version'])}</b></div><div><span>Tree checksum</span><code>{esc(latest_hash)}</code></div><div><span>Owner</span><b>{esc(package['owner'])}</b></div><div><span>Category</span><b>{esc(package['category'])}</b></div></aside></div></section>
<section class="section section-soft"><div class="shell"><div class="section-top compact"><div><p class="kicker">VERSION HISTORY</p><h2>Published versions are immutable.</h2></div><p>Each registry record points at a deterministic <code>.dpk</code> archive and the verified package-tree checksum recorded by the registry.</p></div>{history}</div></section>
<section class="section section-white"><div class="shell"><div class="section-top compact"><div><p class="kicker">SOURCE OF TRUTH</p><h2>Registry metadata and source stay canonical.</h2></div><p>The website is a generated view of the package registry and source tree, not a second package database.</p></div><div class="resource-list"><a href="docs/index.html"><span>Package API documentation</span><b>Browse docs →</b></a><a href="{metadata_url}"><span>Package ownership metadata</span><b>metadata/{esc(name)}.json ↗</b></a><a href="{PACKAGES_REPO}/blob/main/index.txt"><span>Immutable version index</span><b>index.txt ↗</b></a><a href="{esc(source_doc['source_root'])}"><span>Canonical package source</span><b>sources/{esc(name)} ↗</b></a></div></div></section></main>'''
        directory = ROOT / "packages" / name
        directory.mkdir(exist_ok=True)
        (directory / "index.html").write_text(pre2 + detail + detail_footer, encoding="utf-8")

    return render_package_docs(packages)

def heading_slug(text):
    clean = re.sub(r"[`*_]", "", text).lower()
    clean = re.sub(r"<[^>]+>", "", clean)
    return re.sub(r"[^a-z0-9]+", "-", clean).strip("-") or "section"


def inline_markdown(text, docs_by_name):
    tokens = []
    def hold(value):
        tokens.append(value)
        return f"@@TOKEN{len(tokens)-1}@@"
    text = re.sub(r"`([^`]+)`", lambda m: hold(f"<code>{esc(m.group(1))}</code>"), text)
    text = esc(text)
    def link_repl(match):
        label = match.group(1)
        target = html.unescape(match.group(2))
        if target.startswith(("http://", "https://", "mailto:")):
            href = target
        else:
            path, sep, anchor = target.partition("#")
            if path.lower().endswith(".md"):
                key = Path(path).name
                known = docs_by_name.get(key)
                if known and known.get("available"):
                    href = f'../{known["slug"]}/index.html'
                    if sep:
                        href += "#" + anchor
                else:
                    repo_path = doc_repo_path(path)
                    href = f"{RAZ}/blob/main/{repo_path}"
                    if sep:
                        href += "#" + anchor
            else:
                href = target
        return hold(f'<a href="{esc(href)}">{label}</a>')
    text = re.sub(r"\[([^]]+)\]\(([^)]+)\)", link_repl, text)
    text = re.sub(r"\*\*([^*]+)\*\*", r"<strong>\1</strong>", text)
    text = re.sub(r"(?<!\*)\*([^*]+)\*(?!\*)", r"<em>\1</em>", text)
    for i, token in enumerate(tokens):
        text = text.replace(f"@@TOKEN{i}@@", token)
    return text


def markdown_to_html(markdown, docs):
    docs_by_name = {Path(item["path"]).name: item for item in docs}
    lines = markdown.splitlines()
    out = []
    toc = []
    paragraph = []
    in_code = False
    code_lang = "text"
    code_lines = []
    list_type = None
    table_rows = []

    def flush_paragraph():
        nonlocal paragraph
        if paragraph:
            joined = " ".join(part.strip() for part in paragraph).strip()
            if joined:
                out.append(f"<p>{inline_markdown(joined, docs_by_name)}</p>")
            paragraph = []

    def flush_list():
        nonlocal list_type
        if list_type:
            out.append(f"</{list_type}>")
            list_type = None

    def flush_table():
        nonlocal table_rows
        if not table_rows:
            return
        header = table_rows[0]
        rows = table_rows[1:]
        out.append('<div class="doc-table-wrap"><table class="doc-table"><thead><tr>' + ''.join(f"<th>{inline_markdown(cell, docs_by_name)}</th>" for cell in header) + '</tr></thead><tbody>')
        for row in rows:
            out.append('<tr>' + ''.join(f"<td>{inline_markdown(cell, docs_by_name)}</td>" for cell in row) + '</tr>')
        out.append('</tbody></table></div>')
        table_rows = []

    i = 0
    while i < len(lines):
        line = lines[i]
        if in_code:
            if line.startswith("```"):
                lang_class = ' class="language-raz"' if (code_lang or '').lower() in {'raz', 'rz'} else ''
                code_text = chr(10).join(code_lines)
                out.append(f'<div class="doc-code" data-language="{esc((code_lang or "text").lower())}"><div class="doc-code-toolbar"><span class="doc-code-label">{esc(code_lang or "text")}</span><button type="button" class="doc-code-copy" data-copy="{esc(code_text)}">Copy</button></div><pre><code{lang_class}>{esc(code_text)}</code></pre></div>')
                in_code = False
                code_lines = []
            else:
                code_lines.append(line)
            i += 1
            continue
        if line.startswith("```"):
            flush_paragraph(); flush_list(); flush_table()
            code_lang = line[3:].strip() or "text"
            in_code = True
            i += 1
            continue
        heading = re.match(r"^(#{1,4})\s+(.+)$", line)
        if heading:
            flush_paragraph(); flush_list(); flush_table()
            level = len(heading.group(1))
            title = heading.group(2).strip()
            ident = heading_slug(title)
            if level in (2, 3):
                toc.append((level, re.sub(r"[`*_]", "", title), ident))
            if level == 1:
                # The page hero owns the document H1.
                i += 1
                continue
            out.append(f'<h{level} id="{esc(ident)}">{inline_markdown(title, docs_by_name)}<a class="heading-anchor" href="#{esc(ident)}" aria-label="Link to this section">#</a></h{level}>')
            i += 1
            continue
        if re.match(r"^\s*[-*]\s+", line):
            flush_paragraph(); flush_table()
            if list_type != "ul":
                flush_list(); out.append("<ul>"); list_type = "ul"
            item = re.sub(r"^\s*[-*]\s+", "", line)
            out.append(f"<li>{inline_markdown(item, docs_by_name)}</li>")
            i += 1
            continue
        if re.match(r"^\s*\d+\.\s+", line):
            flush_paragraph(); flush_table()
            if list_type != "ol":
                flush_list(); out.append("<ol>"); list_type = "ol"
            item = re.sub(r"^\s*\d+\.\s+", "", line)
            out.append(f"<li>{inline_markdown(item, docs_by_name)}</li>")
            i += 1
            continue
        if line.startswith("|") and line.endswith("|"):
            flush_paragraph(); flush_list()
            cells = [cell.strip() for cell in line.strip("|").split("|")]
            # Skip Markdown's separator row.
            if all(re.fullmatch(r":?-{3,}:?", cell.replace(" ", "")) for cell in cells):
                i += 1
                continue
            table_rows.append(cells)
            i += 1
            continue
        if not line.strip():
            flush_paragraph(); flush_list(); flush_table()
            i += 1
            continue
        flush_list(); flush_table()
        paragraph.append(line)
        i += 1
    flush_paragraph(); flush_list(); flush_table()
    if in_code:
        lang_class = ' class="language-raz"' if (code_lang or '').lower() in {'raz', 'rz'} else ''
        code_text = chr(10).join(code_lines)
        out.append(f'<div class="doc-code" data-language="{esc((code_lang or "text").lower())}"><div class="doc-code-toolbar"><span class="doc-code-label">{esc(code_lang)}</span><button type="button" class="doc-code-copy" data-copy="{esc(code_text)}">Copy</button></div><pre><code{lang_class}>{esc(code_text)}</code></pre></div>')
    return "\n".join(out), toc


def render_doc_pages(docs):
    reference = ROOT / "docs" / "reference"
    reference.mkdir(parents=True, exist_ok=True)
    valid = {doc["slug"] for doc in docs if doc.get("available")}
    for child in reference.iterdir():
        if child.is_dir() and child.name not in valid:
            shutil.rmtree(child)

    index_pre, index_footer = shell_parts(ROOT / "docs" / "index.html")
    detail_pre = index_pre.replace('href="../', 'href="../../../').replace('src="../', 'src="../../../')
    detail_footer = index_footer.replace('href="../', 'href="../../../').replace('src="../', 'src="../../../')
    available_docs = [doc for doc in docs if doc.get("available")]
    for pos, doc in enumerate(available_docs):
        markdown = doc_cache_path(doc["path"]).read_text(encoding="utf-8")
        article_html, toc = markdown_to_html(markdown, docs)
        title = f'{doc["title"]} — Raz documentation'
        pre = rewrite_head(detail_pre, title, doc["description"])
        toc_html = ''.join(f'<a class="toc-level-{level}" href="#{esc(anchor)}">{esc(label)}</a>' for level, label, anchor in toc)
        prev_doc = available_docs[pos - 1] if pos > 0 else None
        next_doc = available_docs[pos + 1] if pos + 1 < len(available_docs) else None
        prev_html = f'<a href="../{prev_doc["slug"]}/index.html"><span>Previous</span><b>← {esc(prev_doc["title"])}</b></a>' if prev_doc else '<span></span>'
        next_html = f'<a class="next" href="../{next_doc["slug"]}/index.html"><span>Next</span><b>{esc(next_doc["title"])} →</b></a>' if next_doc else '<span></span>'
        body = f'''<header class="page-hero doc-reference-hero"><div class="shell narrow"><div class="doc-breadcrumbs"><a href="../../index.html">Docs</a><span>/</span><span>{esc(doc['category'])}</span></div><p class="kicker">CANONICAL RAZ DOCUMENTATION</p><h1>{esc(doc['title'])}</h1><p class="page-lead">{esc(doc['description'])}</p><div class="doc-source-meta"><span>Synced from <code>{esc(doc_repo_path(doc['path']))}</code></span><a href="{esc(doc['url'])}">View source ↗</a></div></div></header>
<main id="main" class="after-hero"><div class="shell doc-reference-layout"><aside class="doc-reference-sidebar"><a class="back-docs" href="../../index.html">← All documentation</a><p>ON THIS PAGE</p><nav aria-label="On this page">{toc_html or '<span class="muted">No subsections</span>'}</nav></aside><article class="doc-reference-content">{article_html}<nav class="doc-pager" aria-label="Documentation pagination">{prev_html}{next_html}</nav></article></div></main>'''
        directory = reference / doc["slug"]
        directory.mkdir(exist_ok=True)
        (directory / "index.html").write_text(pre + body + detail_footer, encoding="utf-8")


def render_docs(docs):
    page = ROOT / "docs" / "index.html"
    pre, footer = shell_parts(page)
    grouped = {}
    for doc in docs:
        grouped.setdefault(doc["category"], []).append(doc)
    groups = []
    hosted = sum(1 for doc in docs if doc.get("available"))
    for category, items in grouped.items():
        cards = []
        for item in items:
            filename = Path(item["path"]).name
            if filename == "GETTING-STARTED.md":
                href = "../learn/book/index.html"
                label = "Read The Raz Book →"
                status = '<span class="doc-hosted-badge">BOOK</span>'
            elif filename == "STANDARD-LIBRARY.md":
                href = "stdlib/index.html"
                label = "Browse API →"
                status = '<span class="doc-hosted-badge">API</span>'
            elif filename == "DIAGNOSTIC-INDEX.md":
                href = "diagnostics/index.html"
                label = "Browse diagnostics →"
                status = '<span class="doc-hosted-badge">INDEX</span>'
            elif item.get("available"):
                href = item["local_url"]
                label = "Read here →"
                status = '<span class="doc-hosted-badge">HOSTED</span>'
            else:
                href = item["url"]
                label = "GitHub source ↗"
                status = '<span class="doc-source-badge">SOURCE</span>'
            cards.append(f'<a class="docs-card canonical-doc" href="{esc(href)}"><div class="doc-card-top"><span>{esc(category.upper())}</span>{status}</div><h3>{esc(item["title"])}</h3><p>{esc(item["description"])}</p><b>{label}</b></a>')
        groups.append(f'<section class="canonical-doc-group"><div class="canonical-doc-heading"><h2>{esc(category)}</h2><span>{len(items)} references</span></div><div class="docs-grid canonical-grid">{"".join(cards)}</div></section>')
    body = f'''<header class="page-hero"><div class="shell narrow"><p class="kicker">DOCUMENTATION</p><h1>Everything you need to use and understand Raz.</h1><p class="page-lead">Canonical Markdown is synchronized from the compiler repository at build time and rendered into the website. When a document has not been mirrored into the current snapshot, the source link remains available directly.</p><div class="button-row"><button class="button button-primary" type="button" data-search-open>Search documentation</button><a class="button button-secondary" href="../learn/index.html">Getting started</a></div></div></header>
<main id="main" class="after-hero"><section class="section section-white"><div class="shell"><div class="docs-grid" data-doc-grid>
<a class="docs-card featured" href="language/index.html"><span>LANGUAGE</span><h2>Language guide</h2><p>Syntax, types, ownership, borrowing, deterministic destruction, generics, traits, control flow and unsafe boundaries.</p><b>Read the guide →</b></a>
<a class="docs-card featured" href="toolchain/index.html"><span>TOOLCHAIN</span><h2>Toolchain guide</h2><p>Projects, manifests, builds, tests, formatting, docs, packages, workspaces, diagnostics and language-server workflows.</p><b>Read the guide →</b></a>
<a class="docs-card featured" href="compiler/index.html"><span>COMPILER</span><h2>Compiler guide</h2><p>Typed HIR, verified MIR, Forge, LLVM, WebAssembly, RXE, native linking and reproducibility.</p><b>Read the guide →</b></a>
<a class="docs-card featured" href="diagnostics/index.html"><span>DIAGNOSTICS</span><h2>Error index</h2><p>Search stable compiler codes across lexer, parser, semantic, lowering, and backend diagnostics.</p><b>Browse diagnostics →</b></a>
<a class="docs-card featured" href="stdlib/index.html"><span>API REFERENCE</span><h2>Standard library</h2><p>Browse generated modules and public items across core, alloc, collections, and std.</p><b>Browse the library →</b></a>
</div><div class="docs-sync-summary"><div><b>{hosted}</b><span>hosted canonical docs</span></div><div><b>{len(docs)}</b><span>indexed references</span></div><div><b>build-time</b><span>GitHub synchronization</span></div></div><div class="data-freshness docs-freshness"><span class="live-dot"></span><span>Documentation index generated from <code>raz/docs/README.md</code></span></div>{''.join(groups)}</div></section>
<section class="section section-soft"><div class="shell path-layout"><div><p class="kicker">RECOMMENDED PATH</p><h2>New to Raz?</h2></div><ol class="learning-path"><li><span>1</span><div><b>Install or build the toolchain</b><p>Verify the environment with <code>raz doctor</code>.</p></div></li><li><span>2</span><div><b>Build your first package</b><p>Learn the project model and core syntax.</p></div></li><li><span>3</span><div><b>Learn ownership and types</b><p>Understand the language's safety and cost model.</p></div></li><li><span>4</span><div><b>Explore the compiler</b><p>See how one verified MIR feeds every backend.</p></div></li></ol></div></section></main>'''
    page.write_text(pre + body + footer, encoding="utf-8")
    render_doc_pages(docs)

def platform_table(platforms):
    rows = "".join(
        f'<div class="tr"><code>{esc(item["target"])}</code><span>{esc(item["backend"])}</span><span>{esc(item["abi"])} · {esc(item["object"])}</span></div>'
        for item in platforms
    )
    return f'<div class="release-table" role="table" aria-label="Qualified native targets"><div class="tr head"><span>Target</span><span>Backend</span><span>ABI / object</span></div>{rows}</div>'


def render_releases(releases, site):
    page = ROOT / "releases" / "index.html"
    pre, footer = shell_parts(page)
    nightly = site["binary_releases"]["nightly"]
    nightly_status = nightly.get("status", "unknown")
    nightly_version = nightly.get("version", "—")
    if releases:
        latest = releases[0]
        hero_actions = f'<div class="button-row"><a class="button button-primary" href="{esc(latest["url"])}">Latest release ↗</a><a class="button button-secondary" href="{INSTALLER}/releases">Release history ↗</a></div>'
        primary = f'<article class="release-main"><span class="status-pill">PUBLISHED</span><h2>{esc(latest["name"] or latest["tag"])}</h2><p>The latest published Raz toolchain release is available from the installer repository.</p><a class="text-link" href="{esc(latest["url"])}">Open latest release ↗</a></article>'
    else:
        hero_actions = f'<div class="button-row"><a class="button button-primary" href="{RAZ}">Build from source ↗</a><a class="button button-secondary" href="{INSTALLER}/releases">Watch releases ↗</a></div>'
        primary = f'<article class="release-main release-pending"><span class="status-pill pending-pill">NOT YET PUBLISHED</span><h2>Binary releases pending</h2><p>Raz 1.0 is the stable language contract, but the installer repository currently contains no published GitHub release. Build from source until qualified binary artifacts are published.</p><a class="text-link" href="{RAZ}">Build Raz from source ↗</a></article>'
    body = f'''<header class="page-hero"><div class="shell narrow"><p class="kicker">RELEASES</p><h1>Language stability and toolchain publication, clearly separated.</h1><p class="page-lead">Release state is generated from the installer repository rather than being hard-coded into the website.</p>{hero_actions}</div></header>
<main id="main" class="after-hero"><section class="section section-white"><div class="shell"><div class="release-grid">{primary}<article><span class="status-pill muted-pill">NIGHTLY</span><h3>{esc(nightly_status.title())}</h3><p>The nightly channel currently reports version <code>{esc(nightly_version)}</code> with status <code>{esc(nightly_status)}</code>.</p><a href="https://raw.githubusercontent.com/raz-language/installer/main/channels/nightly.txt">View channel manifest ↗</a></article><article><span class="status-pill muted-pill">LANGUAGE</span><h3>Raz 1.0 stable</h3><p>The Raz 1.x compatibility contract is stable independently of prebuilt installer publication.</p><a href="{RAZ}/blob/main/docs/LANGUAGE-STABILITY.md">Stability contract ↗</a></article></div><div class="data-freshness release-freshness"><span class="live-dot"></span><span>{len(releases)} published installer release{'s' if len(releases) != 1 else ''} detected</span></div></div></section>
<section class="section section-soft"><div class="shell"><div class="section-top compact"><div><p class="kicker">QUALIFIED TARGETS</p><h2>Generated from platform support.</h2></div><p>These are compiler/toolchain target qualifications, not a promise that a prebuilt archive currently exists for every target.</p></div>{platform_table(site['platforms'])}</div></section></main>'''
    page.write_text(pre + body + footer, encoding="utf-8")


def asset_cards(assets, keyword):
    matches = [asset for asset in assets if keyword in (asset.get("name") or "").lower()]
    if not matches:
        return '<div class="install-option unavailable"><b>No matching artifact in latest release</b><span>Check the release page or use the source build path.</span><em>Not available</em></div>'
    return "".join(
        f'<a href="{esc(asset["url"])}"><b>{esc(asset["name"])}</b><span>Official release artifact</span><em>Download ↗</em></a>'
        for asset in matches
    )


def render_install(releases, site):
    page = ROOT / "install" / "index.html"
    pre, footer = shell_parts(page)
    if releases:
        latest = releases[0]
        assets = latest.get("assets", [])
        hero_actions = f'<div class="button-row"><a class="button button-primary" href="{esc(latest["url"])}">Latest release ↗</a><a class="button button-secondary" href="../releases/index.html">Release details</a></div>'
        notice = f'<div class="release-notice release-ready"><span class="status-pill">PUBLISHED</span><div><b>{esc(latest["name"] or latest["tag"])} is available.</b><p>Artifact links below are generated from the latest GitHub release.</p></div></div>'
        windows_options = asset_cards(assets, "windows")
        linux_options = asset_cards(assets, "linux")
    else:
        hero_actions = f'<div class="button-row"><a class="button button-primary" href="{RAZ}">Build from source ↗</a><a class="button button-secondary" href="../releases/index.html">Release status</a></div>'
        notice = '<div class="release-notice"><span class="status-pill pending-pill">BINARY PUBLICATION PENDING</span><div><b>Raz 1.0 is stable; prebuilt installer releases are not published yet.</b><p>Download controls will appear automatically when qualified artifacts are published.</p></div></div>'
        windows_options = '<div class="install-option unavailable"><b>Windows installer artifacts</b><span>MSI and portable ZIP publication is pending.</span><em>Not published</em></div>'
        linux_options = '<div class="install-option unavailable"><b>Linux release artifact</b><span>Portable tarball publication is pending.</span><em>Not published</em></div>'
    body = f'''<header class="page-hero"><div class="shell narrow"><p class="kicker">INSTALL RAZ</p><h1>Get a verified Raz toolchain.</h1><p class="page-lead">The installer view is generated from real release publication state, while the source-build path always points to the canonical compiler repository.</p>{hero_actions}</div></header>
<main id="main" class="after-hero">{notice}<section class="section section-white"><div class="shell install-layout"><aside class="platform-switch" aria-label="Choose platform"><p>YOUR PLATFORM</p><button class="active" data-platform-button="windows">Windows</button><button data-platform-button="linux">Linux</button><button data-platform-button="source">Other / source</button><small data-platform-detected></small></aside><div class="platform-panels">
<section data-platform-panel="windows"><p class="kicker">WINDOWS</p><h2>MSI or portable toolchain.</h2><p>Published artifacts appear here automatically when the installer repository has a qualified Windows release.</p><div class="install-options">{windows_options}</div></section>
<section data-platform-panel="linux" hidden><p class="kicker">LINUX</p><h2>Portable toolchain.</h2><p>Published Linux artifacts appear here automatically when present in the latest installer release.</p><div class="install-options">{linux_options}</div></section>
<section data-platform-panel="source" hidden><p class="kicker">SOURCE BUILD</p><h2>Bootstrap the production compiler.</h2><p>x86-64 Windows/Linux use the repository bootstrap path. Other qualified hosts follow the documented stage-0/toolchain contract.</p><div class="install-options"><a href="{RAZ}/blob/main/docs/COMPILER-BOOTSTRAP.md"><b>Compiler bootstrap</b><span>Stage-0 and self-hosting architecture</span><em>Read docs ↗</em></a><a href="{RAZ}"><b>Compiler source</b><span>Clone and build the canonical Raz repository</span><em>GitHub ↗</em></a></div></section>
</div></div></section><section class="section section-soft"><div class="shell two-col"><div><p class="kicker">AFTER INSTALLATION</p><h2>Verify before you build.</h2><p class="section-copy">The normal first checks are intentionally small and deterministic.</p></div><div class="code-card"><div class="code-bar"><span>shell</span><button class="copy-button" type="button" data-copy="raz --version&#10;raz doctor&#10;raz new hello&#10;cd hello&#10;raz run">Copy</button></div><pre><code>raz --version\nraz doctor\nraz new hello\ncd hello\nraz run</code></pre></div></div></section></main>'''
    page.write_text(pre + body + footer, encoding="utf-8")



DIAGNOSTIC_FALLBACK = [
    ("lexer", "D0001", "unterminated block comment"),
    ("lexer", "D0004", "unterminated string literal"),
    ("lexer", "D0006", "character literal must contain exactly one character"),
    ("lexer", "D0007", "unexpected character in source file"),
    ("parser", "D1001", "expected <...> (message names the construct the parser required)"),
    ("semantic", "D2001", "duplicate top-level declaration '<...>'"),
    ("semantic", "D2005", "cannot initialize '<...>' with '<...>'"),
    ("semantic", "D2007", "condition must have type 'bool'"),
    ("semantic", "D2008", "unknown name '<...>'"),
    ("semantic", "D2009", "binary operands have incompatible types '<...>' and '<...>'"),
    ("semantic", "D2011", "unknown function '<...>'"),
    ("semantic", "D2038", "non-exhaustive match; missing variant '<...>.<...>'"),
    ("semantic", "D2047", "the '?' operator requires Result<T,E> or Option<T>"),
    ("semantic", "D2050", "deferred code cannot contain return, break, or continue"),
    ("semantic", "D2052", "moving Copy value '<...>' is equivalent to copying it"),
    ("semantic", "D2053", "value '<...>' has already been moved"),
    ("semantic", "D2054", "use of moved value '<...>'"),
    ("semantic", "D2055", "cannot move '<...>' while it is borrowed"),
    ("semantic", "D2056", "cannot mutably borrow '<...>' while an overlapping borrow is active"),
    ("semantic", "D2057", "cannot immutably borrow '<...>' while an overlapping mutable borrow is active"),
    ("semantic", "D2064", "cannot return a reference to local storage '<...>'"),
    ("semantic", "D2068", "type '<...>' cannot implement both Copy and Drop"),
    ("semantic", "D2097", "type '<...>' does not satisfy trait bound '<...>'"),
    ("semantic", "D2114", "implementation of '<...>' requires supertrait '<...>' for '<...>'"),
    ("semantic", "D2125", "FnOnce closure '<...>' has already been called"),
    ("semantic", "D2135", "cannot partially move '<...>' because '<...>' implements Drop"),
    ("semantic", "D2155", "assignment through a shared slice is not allowed"),
    ("semantic", "D2205", "division by zero during compile-time evaluation"),
    ("semantic", "D2212", "compile-time assertion failed"),
    ("semantic", "D2215", "@no_panic function contains an operation that may panic"),
    ("semantic", "D2240", "compile-time execution exceeded 100000 steps"),
    ("semantic", "D2286", "type '<...>' does not implement trait '<...>'"),
    ("semantic", "D2289", "'as' requires numeric types or an unsafe raw-pointer cast"),
    ("lowering", "D3001", "function '<...>' may exit without returning a value"),
    ("lowering", "D3006", "break used outside a loop"),
    ("lowering", "D3007", "continue used outside a loop"),
    ("lowering", "D3033", "dynamic trait object lowering requires a reference or compatible object initializer"),
    ("backend", "D4000", "Forge IR verification failed: <...>"),
    ("backend", "D4004", "unsupported numeric cast from '<...>' to '<...>'"),
    ("backend", "D4013", "trait method invocation has no typed dispatch ABI descriptor"),
]

DIAGNOSTIC_RANGES = {
    "lexer": "D0000–D0999",
    "parser": "D1000–D1999",
    "semantic": "D2000–D2999",
    "lowering": "D3000–D3999",
    "backend": "D4000–D4999",
}

STDLIB_FALLBACK_LAYERS = [
    {"name": "core", "modules": 16, "items": 158, "scope": "Language and runtime-independent foundations."},
    {"name": "alloc", "modules": 9, "items": 148, "scope": "Allocation-backed collections and memory utilities."},
    {"name": "collections", "modules": 4, "items": 123, "scope": "Growable container implementations."},
    {"name": "std", "modules": 73, "items": 998, "scope": "Operating-system, networking, concurrency, and application APIs."},
]

STDLIB_FALLBACK_MODULES = [
    ('core::abi', 'core', 19),
    ('core::ascii', 'core', 13),
    ('core::atomic', 'core', 17),
    ('core::bytes', 'core', 17),
    ('core::callable::weak', 'core', 4),
    ('core::hardware', 'core', 4),
    ('core::hash', 'core', 22),
    ('core::iter::iterator', 'core', 2),
    ('core::mem', 'core', 10),
    ('core::option', 'core', 7),
    ('core::ptr', 'core', 1),
    ('core::result', 'core', 5),
    ('core::slice', 'core', 29),
    ('core::trait_object::trait_identity', 'core', 2),
    ('core::trait_object::type_identity', 'core', 2),
    ('core::trait_object::weak', 'core', 4),
    ('alloc::arena', 'alloc', 15),
    ('alloc::box', 'alloc', 10),
    ('alloc::deque', 'alloc', 17),
    ('alloc::hash_map', 'alloc', 14),
    ('alloc::hash_set', 'alloc', 12),
    ('alloc::pool', 'alloc', 14),
    ('alloc::string', 'alloc', 45),
    ('alloc::string::hash', 'alloc', 2),
    ('alloc::vec', 'alloc', 19),
    ('collections::deque', 'collections', 30),
    ('collections::hash_map', 'collections', 35),
    ('collections::hash_set', 'collections', 23),
    ('collections::vector', 'collections', 35),
    ('std::cli::parser', 'std', 9),
    ('std::compress::lz4', 'std', 9),
    ('std::encoding::base64', 'std', 6),
    ('std::encoding::binary', 'std', 31),
    ('std::encoding::checksum', 'std', 4),
    ('std::encoding::hex', 'std', 6),
    ('std::encoding::json', 'std', 15),
    ('std::encoding::json::document', 'std', 21),
    ('std::env', 'std', 4),
    ('std::env::owned', 'std', 6),
    ('std::env::path', 'std', 1),
    ('std::fmt', 'std', 14),
    ('std::fs', 'std', 22),
    ('std::fs::async_fs', 'std', 4),
    ('std::fs::bytes', 'std', 3),
    ('std::fs::file', 'std', 35),
    ('std::fs::metadata', 'std', 6),
    ('std::fs::owned', 'std', 15),
    ('std::fs::read_dir', 'std', 5),
    ('std::fs::text', 'std', 4),
    ('std::fs::tree', 'std', 2),
    ('std::io', 'std', 7),
    ('std::io::adapters', 'std', 8),
    ('std::io::buffer', 'std', 37),
    ('std::io::buffered', 'std', 20),
    ('std::io::error', 'std', 4),
    ('std::io::stdio', 'std', 20),
    ('std::log', 'std', 15),
    ('std::net', 'std', 78),
    ('std::net::address', 'std', 16),
    ('std::net::async_socket', 'std', 8),
    ('std::net::buffered', 'std', 13),
    ('std::net::framed', 'std', 2),
    ('std::net::http', 'std', 19),
    ('std::net::http::client', 'std', 29),
    ('std::net::http::cookie', 'std', 9),
    ('std::net::http::headers', 'std', 11),
    ('std::net::http::server', 'std', 23),
    ('std::net::poll_set', 'std', 20),
    ('std::net::reactor', 'std', 37),
    ('std::net::resolve', 'std', 32),
    ('std::net::tls', 'std', 22),
    ('std::net::typed', 'std', 3),
    ('std::net::url', 'std', 5),
    ('std::net::url::form', 'std', 4),
    ('std::net::url::query', 'std', 4),
    ('std::net::vectored', 'std', 13),
    ('std::path', 'std', 17),
    ('std::path::buf', 'std', 32),
    ('std::process', 'std', 4),
    ('std::process::args', 'std', 5),
    ('std::process::command', 'std', 14),
    ('std::process::owned', 'std', 1),
    ('std::random', 'std', 17),
    ('std::sync::barrier', 'std', 4),
    ('std::sync::condition', 'std', 15),
    ('std::sync::mutex', 'std', 19),
    ('std::sync::once', 'std', 4),
    ('std::sync::rwlock', 'std', 23),
    ('std::sync::semaphore', 'std', 7),
    ('std::thread', 'std', 10),
    ('std::thread::cancellation', 'std', 9),
    ('std::thread::channel', 'std', 20),
    ('std::thread::executor', 'std', 17),
    ('std::thread::future', 'std', 19),
    ('std::thread::latch', 'std', 6),
    ('std::thread::mpmc', 'std', 11),
    ('std::thread::pool', 'std', 16),
    ('std::thread::scheduler', 'std', 13),
    ('std::thread::spsc', 'std', 13),
    ('std::thread::task', 'std', 13),
    ('std::thread::timer', 'std', 6),
    ('std::time', 'std', 18),
    ('std::testing', 'std', 4),
]


def clean_md_inline(value):
    value = value.strip()
    value = re.sub(r"`([^`]+)`", r"\\1", value)
    value = re.sub(r"\[([^]]+)\]\([^)]+\)", r"\\1", value)
    return value.replace("**", "").replace("*", "")


def parse_diagnostics_data():
    source = DOC_RAW / "DIAGNOSTIC-INDEX.md"
    records = []
    complete = source.exists()
    if source.exists():
        category = None
        for line in source.read_text(encoding="utf-8").splitlines():
            heading = re.match(r"^##\s+(Lexer|Parser|Semantic|Lowering|Backend)\b", line, re.I)
            if heading:
                category = heading.group(1).lower()
                continue
            row = re.match(r"^\|\s*`(D\d{4})`\s*\|\s*(.*?)\s*\|$", line)
            if row and category:
                records.append({"category": category, "code": row.group(1), "message": clean_md_inline(row.group(2))})
    if not records:
        records = [{"category": cat, "code": code, "message": message} for cat, code, message in DIAGNOSTIC_FALLBACK]
        complete = False
    counts = {name: sum(1 for item in records if item["category"] == name) for name in DIAGNOSTIC_RANGES}
    return {
        "complete": complete,
        "source": f"{RAZ}/blob/main/docs/DIAGNOSTIC-INDEX.md",
        "records": records,
        "counts": counts,
        "ranges": DIAGNOSTIC_RANGES,
    }


def parse_stdlib_data():
    source = DOC_RAW / "STANDARD-LIBRARY.md"
    layers = []
    modules = []
    total_modules = 102
    total_items = 1427
    complete = source.exists()
    if source.exists():
        text = source.read_text(encoding="utf-8")
        total = re.search(r"Module map of the\s+(\d+)\s+standard-library modules and their\s+(\d+)\s+public items", text)
        if total:
            total_modules, total_items = int(total.group(1)), int(total.group(2))
        module_counts = {}
        for line in text.splitlines():
            layer = re.match(r"^\|\s*\[`([^`]+)`\]\(#[^)]+\)\s*\|\s*(\d+)\s*\|\s*(\d+)\s*\|\s*(.*?)\s*\|$", line)
            if layer and layer.group(1) in {"core", "alloc", "collections", "std"}:
                layers.append({"name": layer.group(1), "modules": int(layer.group(2)), "items": int(layer.group(3)), "scope": clean_md_inline(layer.group(4))})
                continue
            module_row = re.match(r"^\|\s*\[`([^`]+::[^`]+)`\]\(#[^)]+\)\s*\|\s*(\d+)\s*\|$", line)
            if module_row:
                module_counts[module_row.group(1)] = int(module_row.group(2))
        # Every module has a generated level-3 heading and a source path immediately below it.
        lines = text.splitlines()
        for i, line in enumerate(lines):
            if not line.startswith("### "):
                continue
            name = line[4:].strip()
            if "::" not in name:
                continue
            path = None
            for candidate in lines[i + 1:i + 5]:
                m = re.fullmatch(r"`(library/[^`]+\.rz)`", candidate.strip())
                if m:
                    path = m.group(1)
                    break
            modules.append({"name": name, "layer": name.split("::", 1)[0], "path": path, "item_count": module_counts.get(name), "items": []})
        # Populate item signatures while walking each module section. This intentionally stays permissive;
        # the canonical generated index is the source of truth and can add new headings without breaking us.
        current = None
        in_code = False
        for line in lines:
            if line.startswith("### "):
                name = line[4:].strip()
                current = next((m for m in modules if m["name"] == name), None)
                in_code = False
                continue
            if not current:
                continue
            if line.startswith("```"):
                in_code = not in_code
                continue
            if in_code and line.strip().startswith(("fn ", "const ", "static ", "struct ", "enum ", "trait ", "type ")):
                sig = line.strip()
                current["items"].append({"signature": sig, "description": ""})
                continue
            row = re.match(r"^\|\s*`([^`]+)`\s*\|\s*(.*?)\s*\|$", line)
            if row and row.group(1) not in {"Function", "Type", "Item"}:
                current["items"].append({"signature": row.group(1), "description": clean_md_inline(row.group(2))})
        # De-duplicate signatures produced by overlapping generated sections.
        for module in modules:
            seen = set(); dedup = []
            for item in module["items"]:
                if item["signature"] in seen:
                    continue
                seen.add(item["signature"]); dedup.append(item)
            module["items"] = dedup
    if not layers:
        layers = [dict(item) for item in STDLIB_FALLBACK_LAYERS]
    if not modules:
        modules = [{"name": name, "layer": layer, "path": None, "item_count": count, "items": []} for name, layer, count in STDLIB_FALLBACK_MODULES]
        complete = False
    for module in modules:
        if module.get("item_count") is None:
            module["item_count"] = len(module.get("items", []))
    observed_modules = len(modules)
    observed_items = sum(int(module.get("item_count") or 0) for module in modules)
    declared_layer_modules = sum(int(layer.get("modules") or 0) for layer in layers)
    declared_layer_items = sum(int(layer.get("items") or 0) for layer in layers)
    consistency = {
        "consistent": total_modules == observed_modules == declared_layer_modules and total_items == observed_items == declared_layer_items,
        "declared_total_modules": total_modules,
        "declared_total_items": total_items,
        "declared_layer_modules": declared_layer_modules,
        "declared_layer_items": declared_layer_items,
        "observed_modules": observed_modules,
        "observed_items": observed_items,
    }
    return {
        "complete": complete,
        "source": f"{RAZ}/blob/main/docs/STANDARD-LIBRARY.md",
        "total_modules": total_modules,
        "total_items": total_items,
        "layers": layers,
        "modules": modules,
        "consistency": consistency,
    }



# v9: richer standard-library API model. The canonical generated Markdown remains
# authoritative; these helpers only turn it into stable website routes.
STDLIB_OFFLINE_ITEMS = {
    "core::abi": {
        "Functions": [
            "fn pointer_size() -> i64", "fn pointer_alignment() -> i64", "fn bool_size() -> i64", "fn bool_alignment() -> i64",
            "fn i8_size() -> i64", "fn i8_alignment() -> i64", "fn i16_size() -> i64", "fn i16_alignment() -> i64",
            "fn i32_size() -> i64", "fn i32_alignment() -> i64", "fn i64_size() -> i64", "fn i64_alignment() -> i64",
            "fn f32_size() -> i64", "fn f32_alignment() -> i64", "fn f64_size() -> i64", "fn f64_alignment() -> i64",
            "fn size_t_size() -> i64", "fn size_t_alignment() -> i64", "fn little_endian() -> bool",
        ],
    },
    "core::ascii": {"Functions": [
        "fn is_ascii(i64 value) -> bool", "fn is_digit(i64 value) -> bool", "fn is_lower(i64 value) -> bool",
        "fn is_upper(i64 value) -> bool", "fn is_alpha(i64 value) -> bool", "fn is_alphanumeric(i64 value) -> bool",
        "fn is_whitespace(i64 value) -> bool", "fn is_hex_digit(i64 value) -> bool", "fn digit_value(i64 value) -> i64",
        "fn hex_value(i64 value) -> i64", "fn to_lower(i64 value) -> i64", "fn to_upper(i64 value) -> i64",
        "fn equal_ignore_case(usize left, usize right, i64 length) -> bool",
    ]},
    "core::atomic": {
        "Types": ["const i64 relaxed = 0", "const i64 acquire = 1", "const i64 release = 2", "const i64 acquire_release = 3", "const i64 sequentially_consistent = 4"],
        "Functions": [
            "fn load_i64(usize value) -> i64", "fn store_i64(usize value, i64 desired)",
            "fn fetch_add_i64(usize value, i64 delta) -> i64", "fn exchange_i64(usize value, i64 desired) -> i64",
            "fn compare_exchange_i64(usize value, i64 expected, i64 desired) -> bool", "fn load_i64_ordered(usize value, i64 order) -> i64",
            "fn store_i64_ordered(usize value, i64 desired, i64 order)", "fn fetch_add_i64_ordered(usize value, i64 delta, i64 order) -> i64",
            "fn exchange_i64_ordered(usize value, i64 desired, i64 order) -> i64",
            "fn compare_exchange_i64_ordered(usize value, i64 expected, i64 desired, i64 success_order, i64 failure_order) -> bool",
            "fn cpu_relax()", "fn fence(i64 order)",
        ],
    },
    "core::hardware": {"Functions": ["fn has_sse2() -> bool", "fn has_avx2() -> bool", "fn has_neon() -> bool", "fn cache_line_size() -> i64"]},
    "core::mem": {
        "Types": ["struct Layout"],
        "Functions": [
            "fn min_i64(i64 left, i64 right) -> i64", "fn max_i64(i64 left, i64 right) -> i64",
            "fn clamp_i64(i64 value, i64 low, i64 high) -> i64", "fn copy_bytes(usize destination, usize source, i64 size)",
            "fn move_bytes(usize destination, usize source, i64 size)", "fn fill_bytes(usize destination, i64 value, i64 size)",
            "fn layout_of<T>() -> Layout", "fn layout_is_valid(Layout& layout) -> bool", "fn layout_array_bytes(Layout& layout, i64 count) -> i64",
        ],
    },
    "core::option": {
        "Types": ["enum Option<T>"],
        "Methods on `Option<T>`": [
            "fn is_some(Option<T>& self) -> bool", "fn is_none(Option<T>& self) -> bool",
            "fn unwrap_or(Option<T> self, T fallback) -> T", "fn or(Option<T> self, Option<T> fallback) -> Option<T>",
            "fn take(Option<T>&mut self) -> Option<T>", "fn replace(Option<T>&mut self, T value) -> Option<T>",
        ],
    },
    "core::result": {
        "Types": ["enum Result<T, E>"],
        "Methods on `Result<T, E>`": [
            "fn is_ok(Result<T, E>& self) -> bool", "fn is_error(Result<T, E>& self) -> bool",
            "fn unwrap_or(Result<T, E> self, T fallback) -> T", "fn or(Result<T, E> self, Result<T, E> fallback) -> Result<T, E>",
        ],
    },
    "alloc::arena": {
        "Types": ["struct BumpArena"],
        "Functions": [
            "fn create_aligned(i64 capacity, i64 max_alignment) -> BumpArena", "fn create(i64 capacity) -> BumpArena",
            "fn valid(BumpArena& arena) -> bool", "fn capacity(BumpArena& arena) -> i64", "fn used(BumpArena& arena) -> i64",
            "fn remaining(BumpArena& arena) -> i64", "fn allocate(BumpArena&mut arena, i64 size, i64 alignment) -> usize",
            "fn allocate_zeroed(BumpArena&mut arena, i64 size, i64 alignment) -> usize", "fn mark(BumpArena& arena) -> i64",
            "fn rewind(BumpArena&mut arena, i64 checkpoint) -> bool", "fn reset(BumpArena&mut arena)",
            "fn contains(BumpArena& arena, usize pointer) -> bool", "fn destroy(BumpArena&mut arena)",
        ],
        "Methods on `BumpArena : Drop`": ["fn drop(BumpArena&mut self)"],
    },
    "alloc::box": {"Functions": [
        "fn allocate(i64 size) -> usize", "fn deallocate(usize pointer)", "fn allocate_aligned(i64 size, i64 alignment) -> usize",
        "fn deallocate_aligned(usize pointer, i64 alignment)", "fn allocate_zeroed(i64 size) -> usize",
        "fn allocate_zeroed_aligned(i64 size, i64 alignment) -> usize", "fn allocate_type<T>() -> usize",
        "fn allocate_array<T>(i64 count) -> usize", "fn deallocate_type<T>(usize pointer)", "fn allocate_zeroed_array<T>(i64 count) -> usize",
    ]},
    "collections::vector": {
        "Types": ["struct Vector<T>", "struct VectorIter<T>"],
        "Methods on `Vector<T>`": [
            "fn new() -> Vector<T>", "fn with_capacity(i64 capacity) -> Vector<T>", "fn len(Vector<T>& self) -> i64",
            "fn capacity(Vector<T>& self) -> i64", "fn is_empty(Vector<T>& self) -> bool", "fn reserve(Vector<T>&mut self, i64 capacity) -> bool",
            "fn reserve_exact(Vector<T>&mut self, i64 capacity) -> bool", "fn push(Vector<T>&mut self, T value) -> bool",
            "fn get_ptr(Vector<T>& self, i64 index) -> T*const", "fn get_mut_ptr(Vector<T>&mut self, i64 index) -> T*mut",
            "fn pop(Vector<T>&mut self) -> Option<T>", "fn remove(Vector<T>&mut self, i64 index) -> Option<T>",
            "fn try_pop(Vector<T>&mut self, T&mut output) -> bool", "fn try_remove(Vector<T>&mut self, i64 index, T&mut output) -> bool",
            "fn first_ptr(Vector<T>& self) -> T*const", "fn last_ptr(Vector<T>& self) -> T*const",
            "fn insert(Vector<T>&mut self, i64 index, T value) -> bool", "fn swap_remove(Vector<T>&mut self, i64 index) -> Option<T>",
            "fn append(Vector<T>&mut self, Vector<T>&mut other) -> bool", "fn shrink_to_fit(Vector<T>&mut self) -> bool",
            "fn as_slice(Vector<T>& self) -> Slice<T>", "fn as_mut_slice(Vector<T>&mut self) -> SliceMut<T>",
            "fn truncate(Vector<T>&mut self, i64 length) -> bool", "fn clear(Vector<T>&mut self)",
            "fn iter(Vector<T>& self) -> VectorIter<T>", "fn into_iter(Vector<T>&mut self) -> VectorIter<T>",
            "fn position(Vector<T>& self, T& value) -> i64", "fn contains(Vector<T>& self, T& value) -> bool",
            "fn count(Vector<T>& self, T& value) -> i64", "fn remove_first(Vector<T>&mut self, T& value) -> Option<T>",
        ],
        "Methods on `VectorIter<T> : Iterator`": ["fn next(VectorIter<T>&mut self) -> bool"],
        "Methods on `Vector<T> : IntoIterator`": ["fn into_iter(Vector<T>&mut self) -> VectorIter<T>"],
        "Methods on `Vector<T> : Drop`": ["fn drop(Vector<T>&mut self)"],
    },
    "std::cli::parser": {
        "Types": ["struct ArgView", "struct LongOption"],
        "Functions": [
            "fn view(usize data, i64 length) -> ArgView", "fn valid(ArgView arg) -> bool", "fn is_terminator(ArgView arg) -> bool",
            "fn is_long_option(ArgView arg) -> bool", "fn is_short_option(ArgView arg) -> bool",
            "fn split_long_option(ArgView arg) -> LongOption", "fn equals(ArgView arg, usize bytes, i64 length) -> bool",
        ],
    },
}

STDLIB_OFFLINE_PATHS = {
    "core::abi": "library/core/abi/abi.rz",
    "core::ascii": "library/core/ascii/ascii.rz",
    "core::atomic": "library/core/atomic/atomic.rz",
    "core::hardware": "library/core/hardware/hardware.rz",
    "core::mem": "library/core/mem/mem.rz",
    "core::option": "library/core/option/option.rz",
    "core::result": "library/core/result/result.rz",
    "alloc::arena": "library/alloc/arena/arena.rz",
    "alloc::box": "library/alloc/box/box.rz",
    "collections::vector": "library/collections/vector/vector.rz",
    "std::cli::parser": "library/std/cli/parser/parser.rz",
}

STDLIB_OFFLINE_DESCRIPTIONS = {
    "core::ascii|fn is_ascii(i64 value) -> bool": "Returns true when the value is representable by one ASCII byte.",
    "core::ascii|fn equal_ignore_case(usize left, usize right, i64 length) -> bool": "Allocation-free ASCII case-insensitive comparison over equal-length buffers.",
    "core::mem|struct Layout": "Runtime layout descriptor backed by the compiler's concrete generic layout.",
    "core::option|enum Option<T>": "Optional value with either no payload or one value.",
    "core::result|enum Result<T, E>": "Recoverable result with success and error payloads.",
    "alloc::arena|fn create(i64 capacity) -> BumpArena": "Creates an arena suitable for ordinary cacheline-aligned data structures.",
    "alloc::arena|fn mark(BumpArena& arena) -> i64": "Captures a cheap stack-like checkpoint for scoped scratch allocations.",
    "alloc::arena|fn rewind(BumpArena&mut arena, i64 checkpoint) -> bool": "Releases every allocation made after the checkpoint in O(1).",
    "alloc::arena|fn reset(BumpArena&mut arena)": "Releases all arena allocations in O(1) while retaining the backing block.",
    "collections::vector|struct Vector<T>": "Typed growable contiguous storage with compiler-specialized element layout.",
    "std::cli::parser|struct ArgView": "Allocation-free view over one command-line token.",
    "std::cli::parser|struct LongOption": "Result of splitting --name=value; has_value is false for --name.",
    "std::cli::parser|fn split_long_option(ArgView arg) -> LongOption": "Splits a long option without allocating or copying.",
}


def stdlib_module_slug(name):
    return "/".join(part.lower().replace("_", "-") for part in name.split("::"))


def stdlib_item_name(signature):
    value = signature.strip()
    m = re.match(r"fn\s+([A-Za-z_][A-Za-z0-9_]*)", value)
    if m: return m.group(1)
    m = re.match(r"(?:struct|enum|trait|type)\s+([A-Za-z_][A-Za-z0-9_]*)", value)
    if m: return m.group(1)
    m = re.match(r"(?:const|static)\s+\S+\s+([A-Za-z_][A-Za-z0-9_]*)", value)
    if m: return m.group(1)
    return re.sub(r"[^A-Za-z0-9_]+", "_", value).strip("_")[:80] or "item"


def stdlib_item_kind(signature, group):
    value = signature.strip()
    if group.startswith("Methods on ") and value.startswith("fn "): return "method"
    for prefix, kind in (("struct ", "struct"), ("enum ", "enum"), ("trait ", "trait"), ("type ", "type"), ("const ", "constant"), ("static ", "static"), ("fn ", "function")):
        if value.startswith(prefix): return kind
    return "item"


def stdlib_owner_from_group(group):
    m = re.match(r"Methods on `([^`]+)`", group or "")
    return m.group(1) if m else None


def stdlib_item_slug(item):
    base = re.sub(r"[^a-z0-9]+", "-", item["name"].lower()).strip("-") or "item"
    if item.get("owner"):
        owner = re.sub(r"[^a-z0-9]+", "-", item["owner"].lower()).strip("-")
        return f'{item["kind"]}/{owner}/{base}'
    return f'{item["kind"]}/{base}'


def normalize_stdlib_items(module):
    normalized=[]
    seen=set()
    for raw in module.get("items", []):
        signature=raw.get("signature", "").strip()
        if not signature: continue
        group=raw.get("group") or "Public API"
        item={"signature":signature,"description":raw.get("description", ""),"group":group,
              "kind":stdlib_item_kind(signature,group),"name":stdlib_item_name(signature),
              "owner":raw.get("owner") or stdlib_owner_from_group(group)}
        key=(group,signature)
        if key in seen: continue
        seen.add(key)
        slug=stdlib_item_slug(item)
        if any(x.get("slug")==slug and x["signature"]!=signature for x in normalized):
            slug += "-" + hashlib.sha1((group+"\n"+signature).encode("utf-8")).hexdigest()[:8]
        item["slug"]=slug
        normalized.append(item)
    module["items"]=normalized
    module["slug"]=stdlib_module_slug(module["name"])
    module["documented_items"]=len(normalized)
    return module


def parse_stdlib_data():
    source = DOC_RAW / "STANDARD-LIBRARY.md"
    layers=[]; modules=[]; total_modules=102; total_items=1427; complete=source.exists()
    if source.exists():
        text=source.read_text(encoding="utf-8")
        total=re.search(r"Module map of the\s+(\d+)\s+standard-library modules and their\s+(\d+)\s+public items",text)
        if total: total_modules,total_items=int(total.group(1)),int(total.group(2))
        module_counts={}
        for line in text.splitlines():
            layer=re.match(r"^\|\s*\[`([^`]+)`\]\(#[^)]+\)\s*\|\s*(\d+)\s*\|\s*(\d+)\s*\|\s*(.*?)\s*\|$",line)
            if layer and layer.group(1) in {"core","alloc","collections","std"}:
                layers.append({"name":layer.group(1),"modules":int(layer.group(2)),"items":int(layer.group(3)),"scope":clean_md_inline(layer.group(4))}); continue
            mr=re.match(r"^\|\s*\[`([^`]+::[^`]+)`\]\(#[^)]+\)\s*\|\s*(\d+)\s*\|$",line)
            if mr: module_counts[mr.group(1)]=int(mr.group(2))
        lines=text.splitlines()
        for i,line in enumerate(lines):
            if not line.startswith("### "): continue
            name=line[4:].strip()
            if "::" not in name: continue
            path=None
            for candidate in lines[i+1:i+6]:
                m=re.fullmatch(r"`(library/[^`]+\.rz)`",candidate.strip())
                if m: path=m.group(1); break
            modules.append({"name":name,"layer":name.split("::",1)[0],"path":path,"item_count":module_counts.get(name),"items":[]})
        by_name={m["name"]:m for m in modules}; current=None; group="Public API"; in_code=False
        for line in lines:
            if line.startswith("### "):
                current=by_name.get(line[4:].strip()); group="Public API"; in_code=False; continue
            if not current: continue
            sec=re.fullmatch(r"\*\*(.+)\*\*",line.strip())
            if sec: group=clean_md_inline(sec.group(1)); continue
            if line.startswith("```"): in_code=not in_code; continue
            if in_code and line.strip().startswith(("fn ","const ","static ","struct ","enum ","trait ","type ")):
                current["items"].append({"signature":line.strip(),"description":"","group":group}); continue
            row=re.match(r"^\|\s*`([^`]+)`\s*\|\s*(.*?)\s*\|$",line)
            if row and row.group(1) not in {"Function","Type","Item"}:
                current["items"].append({"signature":row.group(1),"description":clean_md_inline(row.group(2)),"group":group})
    if not layers: layers=[dict(item) for item in STDLIB_FALLBACK_LAYERS]
    if not modules:
        modules=[{"name":name,"layer":layer,"path":None,"item_count":count,"items":[]} for name,layer,count in STDLIB_FALLBACK_MODULES]; complete=False
    for module in modules:
        if not module.get("items") and module["name"] in STDLIB_OFFLINE_ITEMS:
            seeded=[]
            for group,signatures in STDLIB_OFFLINE_ITEMS[module["name"]].items():
                for signature in signatures:
                    seeded.append({"signature":signature,"description":STDLIB_OFFLINE_DESCRIPTIONS.get(module["name"]+"|"+signature,""),"group":group})
            module["items"]=seeded
        if not module.get("path") and module["name"] in STDLIB_OFFLINE_PATHS:
            module["path"] = STDLIB_OFFLINE_PATHS[module["name"]]
        if module.get("item_count") is None: module["item_count"]=len(module.get("items",[]))
        normalize_stdlib_items(module)
    observed_modules=len(modules); observed_items=sum(int(m.get("item_count") or 0) for m in modules)
    declared_layer_modules=sum(int(x.get("modules") or 0) for x in layers); declared_layer_items=sum(int(x.get("items") or 0) for x in layers)
    consistency={"consistent":total_modules==observed_modules==declared_layer_modules and total_items==observed_items==declared_layer_items,
                 "declared_total_modules":total_modules,"declared_total_items":total_items,"declared_layer_modules":declared_layer_modules,
                 "declared_layer_items":declared_layer_items,"observed_modules":observed_modules,"observed_items":observed_items}
    return {"complete":complete,"source":f"{RAZ}/blob/main/docs/STANDARD-LIBRARY.md","total_modules":total_modules,"total_items":total_items,
            "layers":layers,"modules":modules,"consistency":consistency,"documented_modules":sum(1 for m in modules if m.get("items")),
            "documented_items":sum(len(m.get("items",[])) for m in modules)}

def render_diagnostics(diagnostics):
    page = ROOT / "docs" / "diagnostics" / "index.html"
    page.parent.mkdir(parents=True, exist_ok=True)
    base_pre, base_footer = shell_parts(ROOT / "docs" / "index.html")
    pre = base_pre.replace('href="../', 'href="../../').replace('src="../', 'src="../../')
    footer = base_footer.replace('href="../', 'href="../../').replace('src="../', 'src="../../')
    pre = rewrite_head(pre, "Diagnostics — Raz documentation", "Search stable Raz compiler diagnostic codes by category and message.")
    filters = '<button class="active" data-diagnostic-filter="all">All</button>' + ''.join(
        f'<button data-diagnostic-filter="{esc(name)}">{esc(name.title())}</button>' for name in DIAGNOSTIC_RANGES
    )
    records = []
    for item in diagnostics["records"]:
        hay = f'{item["code"]} {item["category"]} {item["message"]}'.lower()
        records.append(f'''<article class="diagnostic-row" id="{esc(item['code'].lower())}" data-diagnostic data-category="{esc(item['category'])}" data-search="{esc(hay)}">
          <a class="diagnostic-code" href="#{esc(item['code'].lower())}">{esc(item['code'])}</a>
          <span class="diagnostic-category">{esc(item['category'])}</span>
          <p>{esc(item['message'])}</p>
        </article>''')
    status = "Full canonical catalog" if diagnostics["complete"] else "Offline seed; full catalog syncs during refresh"
    rendered = ROOT / "docs" / "reference" / "diagnostic-index" / "index.html"
    rendered_link = '<a class="button button-secondary" href="../reference/diagnostic-index/index.html">Rendered source</a>' if rendered.exists() else f'<a class="button button-secondary" href="{RAZ}/blob/main/docs/CLI.md#diagnostics">CLI diagnostics ↗</a>'
    body = f'''<header class="page-hero"><div class="shell narrow"><div class="doc-breadcrumbs"><a href="../index.html">Docs</a><span>/</span><span>Diagnostics</span></div><p class="kicker">COMPILER DIAGNOSTICS</p><h1>Find an error by stable diagnostic code.</h1><p class="page-lead">Raz diagnostic codes keep their meaning even when message wording improves, making errors searchable and suitable for warning policy.</p><div class="button-row"><a class="button button-primary" href="{esc(diagnostics['source'])}">Canonical index ↗</a>{rendered_link}</div></div></header>
<main id="main" class="after-hero"><section class="section section-white"><div class="shell"><div class="reference-toolbar"><label><span class="sr-only">Search diagnostics</span><input type="search" placeholder="Search D2054, borrow, trait…" data-diagnostic-search></label><div class="reference-filters" aria-label="Filter diagnostics">{filters}</div></div><div class="reference-summary"><div><b data-diagnostic-count>{len(diagnostics['records'])}</b><span>diagnostics in this snapshot</span></div><div><b>5</b><span>stable categories</span></div><div><b>{esc(status)}</b><span>source state</span></div></div><div class="diagnostic-list">{''.join(records)}</div><div class="empty-state" data-diagnostic-empty hidden>No diagnostics match that search.</div></div></section></main>'''
    page.write_text(pre + body + footer, encoding="utf-8")



def _shell_for_doc_page(page, title, description):
    base_pre, base_footer = shell_parts(ROOT / "docs" / "index.html")
    rel = os.path.relpath(ROOT, page.parent).replace("\\", "/")
    prefix = "" if rel == "." else rel.rstrip("/") + "/"
    pre = base_pre.replace('href="../', f'href="{prefix}').replace('src="../', f'src="{prefix}')
    footer = base_footer.replace('href="../', f'href="{prefix}').replace('src="../', f'src="{prefix}')
    return rewrite_head(pre, title, description), footer


def _rel_href(page, target):
    return os.path.relpath(target, page.parent).replace("\\", "/")


def _stdlib_kind_label(kind):
    return {"struct":"struct","enum":"enum","trait":"trait","type":"type","constant":"const","static":"static","function":"function","method":"method"}.get(kind,"item")


def _stdlib_module_summary(module):
    if not module.get("items"):
        return "Canonical item details synchronize during the full documentation refresh."
    kinds={}
    for item in module["items"]: kinds[item["kind"]]=kinds.get(item["kind"],0)+1
    order=["struct","enum","trait","type","constant","static","function","method"]
    return " · ".join(f'{kinds[k]} {k}{"s" if kinds[k]!=1 else ""}' for k in order if kinds.get(k))


def stdlib_source_url(module):
    return f'{RAZ}/blob/main/{module["path"]}' if module.get("path") else f'{RAZ}/blob/main/docs/STANDARD-LIBRARY.md'


def render_stdlib_item_page(module, item, module_page):
    page=module_page.parent/item["slug"]/"index.html"; page.parent.mkdir(parents=True,exist_ok=True)
    desc=item.get("description") or f'{_stdlib_kind_label(item["kind"]).title()} in {module["name"]}.'
    pre,footer=_shell_for_doc_page(page,f'{item["name"]} — {module["name"]} — Raz stdlib',desc)
    module_href=_rel_href(page,module_page); stdlib_href=_rel_href(page,ROOT/"docs"/"stdlib"/"index.html"); source=stdlib_source_url(module)
    owner=f'<div><span>Receiver / implementation</span><code>{esc(item["owner"])}</code></div>' if item.get("owner") else ''
    detail=f'<p class="api-description">{esc(item["description"])}</p>' if item.get("description") else '<p class="api-description muted">The generated index does not currently carry an extended documentation sentence for this item.</p>'
    body=f'''<header class="page-hero api-item-hero"><div class="shell narrow"><div class="doc-breadcrumbs"><a href="{esc(stdlib_href)}">Standard library</a><span>/</span><a href="{esc(module_href)}">{esc(module['name'])}</a><span>/</span><span>{esc(item['name'])}</span></div><p class="kicker">{esc(_stdlib_kind_label(item['kind']).upper())} · RAZ STDLIB</p><h1><code>{esc(item['name'])}</code></h1><p class="page-lead">{esc(desc)}</p></div></header>
<main id="main" class="after-hero"><section class="section section-white"><div class="shell api-item-layout"><article><p class="kicker">SIGNATURE</p><div class="api-signature-card"><code class="language-raz">{esc(item['signature'])}</code><button type="button" data-copy="{esc(item['signature'])}">Copy</button></div>{detail}<div class="button-row"><a class="button button-secondary" href="{esc(module_href)}">← Back to module</a><a class="button button-secondary" href="{esc(source)}">Source file ↗</a></div></article><aside class="api-meta-card"><div><span>Module</span><a href="{esc(module_href)}">{esc(module['name'])}</a></div><div><span>Kind</span><b>{esc(_stdlib_kind_label(item['kind']))}</b></div><div><span>Section</span><b>{esc(item['group'])}</b></div>{owner}<div><span>Layer</span><b>{esc(module['layer'])}</b></div></aside></div></section></main>'''
    page.write_text(pre+body+footer,encoding="utf-8"); return page


def render_stdlib_module_page(stdlib,module):
    page=ROOT/"docs"/"stdlib"/Path(module["slug"])/"index.html"; page.parent.mkdir(parents=True,exist_ok=True)
    desc=f'{module.get("item_count",0)} public items in the Raz {module["name"]} module.'
    pre,footer=_shell_for_doc_page(page,f'{module["name"]} — Raz standard library',desc)
    stdlib_href=_rel_href(page,ROOT/"docs"/"stdlib"/"index.html"); source=stdlib_source_url(module)
    groups=[]
    for item in module.get("items",[]):
        if item["group"] not in groups: groups.append(item["group"])
    sections=[]
    for group in groups:
        rows=[]
        for item in [x for x in module["items"] if x["group"]==group]:
            item_page=page.parent/item["slug"]/"index.html"; href=_rel_href(page,item_page)
            description=f'<p>{esc(item["description"])}</p>' if item.get("description") else ''
            hay=f'{item["name"]} {item["signature"]} {item["kind"]} {item.get("owner") or ""} {item.get("description") or ""}'.lower()
            rows.append(f'''<a class="api-item-row" href="{esc(href)}" data-stdlib-api-item data-search="{esc(hay)}"><span class="api-kind">{esc(_stdlib_kind_label(item['kind']))}</span><div><code class="language-raz">{esc(item['signature'])}</code>{description}</div><b>→</b></a>''')
        sections.append(f'<section class="api-group"><div class="api-group-title"><h2>{esc(group)}</h2><span>{len(rows)} item{"s" if len(rows)!=1 else ""}</span></div><div class="api-item-list">{"".join(rows)}</div></section>')
    if not sections:
        sections=['<div class="api-empty-detail"><b>Module route is ready.</b><p>The checked-in offline snapshot preserves the module map, while complete signatures and documentation synchronize from the canonical generated index during deployment.</p></div>']
    source_path=f'<code>{esc(module["path"])}</code>' if module.get("path") else '<span>Available after full canonical sync</span>'
    searchbar=f'<div class="reference-toolbar api-local-search"><label><span class="sr-only">Search this module</span><input type="search" placeholder="Search {esc(module["name"])}…" data-stdlib-item-search></label><span data-stdlib-item-count>{len(module.get("items",[]))} documented item{"s" if len(module.get("items",[]))!=1 else ""}</span></div>' if module.get("items") else ''
    body=f'''<header class="page-hero api-module-hero"><div class="shell narrow"><div class="doc-breadcrumbs"><a href="{esc(stdlib_href)}">Standard library</a><span>/</span><span>{esc(module['name'])}</span></div><p class="kicker">{esc(module['layer'].upper())} · MODULE</p><h1><code>{esc(module['name'])}</code></h1><p class="page-lead">{esc(desc)}</p><div class="button-row"><a class="button button-primary" href="{esc(source)}">Source ↗</a><a class="button button-secondary" href="{esc(stdlib_href)}">All modules</a></div></div></header>
<main id="main" class="after-hero"><section class="section section-white"><div class="shell"><div class="api-module-stats"><div><b>{module.get('item_count',0)}</b><span>public items</span></div><div><b>{len(module.get('items',[]))}</b><span>documented here</span></div><div><b>{esc(module['layer'])}</b><span>library layer</span></div></div><div class="api-source-path"><span>Source</span>{source_path}</div>{searchbar}<div data-stdlib-item-groups>{''.join(sections)}</div><div class="empty-state" data-stdlib-item-empty hidden>No items match that search.</div></div></section></main>'''
    page.write_text(pre+body+footer,encoding="utf-8")
    items=[render_stdlib_item_page(module,item,page) for item in module.get("items",[])]
    return page,items


def render_stdlib(stdlib):
    page=ROOT/"docs"/"stdlib"/"index.html"; page.parent.mkdir(parents=True,exist_ok=True)
    pre,footer=_shell_for_doc_page(page,"Standard library — Raz documentation","Browse Raz standard-library modules, types, functions, methods, and generated public API metadata.")
    for child in page.parent.iterdir():
        if child.is_dir(): shutil.rmtree(child)
    layer_cards=''.join(f'''<article class="stdlib-layer"><span>{esc(layer['name'].upper())}</span><h2>{layer['modules']} modules</h2><b>{layer['items']} public items</b><p>{esc(layer['scope'])}</p></article>''' for layer in stdlib["layers"])
    cards=[]
    for module in stdlib["modules"]:
        search=f'{module["name"]} {module["layer"]} {module.get("path") or ""} '+' '.join(i["signature"] for i in module.get("items",[]))
        preview=''.join(f'<li><span class="api-kind">{esc(_stdlib_kind_label(i["kind"]))}</span><code>{esc(i["signature"])}</code></li>' for i in module.get("items",[])[:4])
        if not preview: preview='<li class="muted">Stable module route available; full item detail expands during canonical refresh.</li>'
        cards.append(f'''<article class="stdlib-module" data-stdlib-module data-layer="{esc(module['layer'])}" data-search="{esc(search.lower())}"><a class="stdlib-module-link" href="{esc(module['slug'])}/index.html"><div class="stdlib-module-head"><div><span>{esc(module['layer'].upper())}</span><h3>{esc(module['name'])}</h3></div><b>{module.get('item_count',0)} items</b></div><p>{esc(_stdlib_module_summary(module))}</p><ul>{preview}</ul><div class="stdlib-module-foot"><span>{len(module.get('items',[]))} item pages in snapshot</span><b>Open module →</b></div></a></article>''')
    filters='<button class="active" data-stdlib-filter="all">All</button>'+''.join(f'<button data-stdlib-filter="{esc(layer["name"])}">{esc(layer["name"])}</button>' for layer in stdlib["layers"])
    note="Full generated module and item index" if stdlib["complete"] else "All module routes are available offline; representative item pages are seeded and the complete API expands during CI refresh"
    consistency=stdlib.get("consistency",{}); warning=''
    if consistency and not consistency.get("consistent",True):
        warning=f'<div class="source-consistency-warning"><b>Canonical index consistency warning</b><p>The source currently declares {consistency.get("declared_total_modules")} modules / {consistency.get("declared_total_items")} items, while its module table enumerates {consistency.get("observed_modules")} modules / {consistency.get("observed_items")} items. Raz.org preserves both values instead of silently normalizing the source.</p></div>'
    rendered=ROOT/"docs"/"reference"/"standard-library"/"index.html"; rendered_link='<a class="button button-secondary" href="../reference/standard-library/index.html">Rendered source</a>' if rendered.exists() else f'<a class="button button-secondary" href="{RAZ}/blob/main/docs/STANDARD-LIBRARY-PERFORMANCE.md">Performance guide ↗</a>'
    body=f'''<header class="page-hero"><div class="shell narrow"><div class="doc-breadcrumbs"><a href="../index.html">Docs</a><span>/</span><span>Standard library</span></div><p class="kicker">STANDARD LIBRARY</p><h1>Navigate Raz APIs by module and item.</h1><p class="page-lead">Every standard-library module gets a stable website route. Types, functions, constants, and method groups become first-class item pages as canonical generated metadata is synchronized.</p><div class="button-row"><a class="button button-primary" href="{esc(stdlib['source'])}">Canonical index ↗</a>{rendered_link}</div></div></header>
<main id="main" class="after-hero"><section class="section section-white"><div class="shell"><div class="library-stats"><div><b>{stdlib['total_modules']}</b><span>declared modules</span></div><div><b>{stdlib['total_items']}</b><span>declared public items</span></div><div><b>{stdlib.get('documented_items',0)}</b><span>item pages in snapshot</span></div></div>{warning}<div class="stdlib-layers">{layer_cards}</div></div></section><section class="section section-soft"><div class="shell"><div class="reference-toolbar"><label><span class="sr-only">Search standard library</span><input type="search" placeholder="Search module, function, type…" data-stdlib-search></label><div class="reference-filters" aria-label="Filter standard library">{filters}</div></div><div class="data-freshness"><span class="live-dot"></span><span>{esc(note)}</span></div><div class="stdlib-count" data-stdlib-count>{len(stdlib['modules'])} modules</div><div class="stdlib-module-grid">{''.join(cards)}</div><div class="empty-state" data-stdlib-empty hidden>No modules match that search.</div></div></section></main>'''
    page.write_text(pre+body+footer,encoding="utf-8")
    module_pages=[]; item_pages=[]
    for module in stdlib["modules"]:
        mp,ips=render_stdlib_module_page(stdlib,module); module_pages.append(mp); item_pages.extend(ips)
    stdlib["generated_module_pages"]=len(module_pages); stdlib["generated_item_pages"]=len(item_pages)

def render_reference_products():
    diagnostics = parse_diagnostics_data()
    stdlib = parse_stdlib_data()
    render_diagnostics(diagnostics)
    render_stdlib(stdlib)
    GEN.mkdir(parents=True, exist_ok=True)
    (GEN / "diagnostics.json").write_text(json.dumps(diagnostics, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    (GEN / "stdlib.json").write_text(json.dumps(stdlib, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return diagnostics, stdlib



def augment_search_index(diagnostics, stdlib):
    path=ROOT/"assets"/"search-index.js"; raw=path.read_text(encoding="utf-8"); prefix="window.RAZ_SEARCH="
    if not raw.startswith(prefix): return
    items=json.loads(raw[len(prefix):].rstrip().rstrip(";"))
    items.append({"title":"Diagnostic reference","description":"Search stable compiler diagnostic codes","url":"docs/diagnostics/index.html","keywords":"diagnostics errors codes compiler warnings"})
    items.append({"title":"Standard library","description":"Browse standard-library modules and public APIs","url":"docs/stdlib/index.html","keywords":"stdlib standard library api modules functions types methods"})
    for item in diagnostics["records"]:
        items.append({"title":item["code"],"description":item["message"],"url":f'docs/diagnostics/index.html#{item["code"].lower()}',"keywords":f'diagnostic {item["category"]} error warning'})
    for module in stdlib["modules"]:
        module_url=f'docs/stdlib/{module["slug"]}/index.html'
        items.append({"title":module["name"],"description":f'{module.get("item_count",0)} public items in the {module["layer"]} layer',"url":module_url,"keywords":f'stdlib api module {module["layer"]} '+' '.join(i["signature"] for i in module.get("items",[])[:12])})
        base=module_url[:-10]
        for item in module.get("items",[]):
            items.append({"title":f'{item["name"]} · {module["name"]}',"description":item.get("description") or item["signature"],"url":f'{base}{item["slug"]}/index.html',"keywords":f'stdlib api {item["kind"]} {item.get("owner") or ""} {item["signature"]}'})
    path.write_text(prefix+json.dumps(items,separators=(",",":"))+";\n",encoding="utf-8")


def augment_public_api(diagnostics, stdlib):
    API.mkdir(parents=True, exist_ok=True)
    (API / "diagnostics.json").write_text(json.dumps(diagnostics, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    (API / "stdlib.json").write_text(json.dumps(stdlib, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    module_api = API / "stdlib" / "modules"
    if module_api.exists():
        shutil.rmtree(module_api)
    for module in stdlib.get("modules", []):
        target = module_api / Path(module["slug"]) / "index.json"
        target.parent.mkdir(parents=True, exist_ok=True)
        payload = dict(module)
        payload["website_url"] = f'/docs/stdlib/{module["slug"]}/index.html'
        for item in payload.get("items", []):
            item["website_url"] = f'/docs/stdlib/{module["slug"]}/{item["slug"]}/index.html'
        target.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    index_path = API / "index.json"
    index = json.loads(index_path.read_text(encoding="utf-8"))
    index.setdefault("resources", {})["diagnostics"] = "./diagnostics.json"
    index.setdefault("resources", {})["stdlib"] = "./stdlib.json"
    index.setdefault("resources", {})["stdlib_modules"] = "./stdlib/modules/<module-path>/index.json"
    index_path.write_text(json.dumps(index, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def augment_package_docs_search(package_docs):
    path = ROOT / "assets" / "search-index.js"
    text = path.read_text(encoding="utf-8")
    match = re.match(r"window\.RAZ_SEARCH=(.*);\s*$", text, re.S)
    items = json.loads(match.group(1)) if match else []
    for package in package_docs:
        base = f'packages/{package["name"]}/docs/'
        items.append({
            "title": f'{package["name"]} API documentation',
            "description": f'Source-derived modules and public API for {package["name"]}',
            "url": base + 'index.html',
            "keywords": f'package api docs {package["name"]} ' + ' '.join(m['name'] for m in package.get('modules', [])),
        })
        for module in package.get('modules', []):
            module_url = base + 'module/' + '/'.join(module['name'].split('::')) + '/index.html'
            items.append({
                "title": f'{module["name"]} · {package["name"]}',
                "description": f'{len(module.get("symbols", []))} public declarations in {module["file"]}',
                "url": module_url,
                "keywords": 'package module api ' + ' '.join(s['name'] for s in module.get('symbols', [])),
            })
            module_base = module_url[:-len('index.html')]
            for symbol in module.get('symbols', []):
                items.append({
                    "title": f'{symbol["name"]} · {module["name"]} · {package["name"]}',
                    "description": symbol.get('description') or symbol['signature'],
                    "url": module_base + symbol['slug'] + '/index.html',
                    "keywords": f'package api {symbol["kind"]} {symbol["signature"]}',
                })
    path.write_text('window.RAZ_SEARCH=' + json.dumps(items, separators=(',', ':')) + ';\n', encoding='utf-8')


def augment_package_docs_api(package_docs):
    API.mkdir(parents=True, exist_ok=True)
    (API / 'package-docs.json').write_text(json.dumps(package_docs, indent=2, sort_keys=True) + '\n', encoding='utf-8')
    root = API / 'packages'
    if root.exists():
        shutil.rmtree(root)
    for package in package_docs:
        target = root / package['name'] / 'index.json'
        target.parent.mkdir(parents=True, exist_ok=True)
        payload = dict(package)
        payload['website_url'] = f'/packages/{package["name"]}/docs/'
        target.write_text(json.dumps(payload, indent=2, sort_keys=True) + '\n', encoding='utf-8')
    index_path = API / 'index.json'
    if index_path.exists():
        index = json.loads(index_path.read_text(encoding='utf-8'))
        index.setdefault('resources', {})['package-docs'] = './package-docs.json'
        index['resources']['package-api'] = './packages/<package>/index.json'
        index_path.write_text(json.dumps(index, indent=2, sort_keys=True) + '\n', encoding='utf-8')

def render_search(packages, docs):
    items = [{"title": title, "description": description, "url": url, "keywords": keywords} for title, description, url, keywords in BASE_SEARCH]
    for package in packages:
        versions = " ".join(item["version"] for item in package.get("versions", []))
        items.append({"title": package["name"], "description": package["description"], "url": f'packages/{package["name"]}/index.html', "keywords": f'package {package["category"]} {versions}'})
    for doc in docs:
        url = f'docs/{doc["local_url"]}' if doc.get("available") else doc["url"]
        keywords = f'documentation {doc["category"]} {Path(doc["path"]).stem}'
        items.append({"title": doc["title"], "description": doc["description"], "url": url, "keywords": keywords})
    (ROOT / "assets" / "search-index.js").write_text("window.RAZ_SEARCH=" + json.dumps(items, separators=(",", ":")) + ";\n", encoding="utf-8")

    for page in ROOT.rglob("*.html"):
        text = page.read_text(encoding="utf-8")
        rel_search = os.path.relpath(ROOT / "assets" / "search-index.js", page.parent).replace("\\", "/")
        rel_root = os.path.relpath(ROOT, page.parent).replace("\\", "/")
        base = "" if rel_root == "." else rel_root.rstrip("/") + "/"
        scripts = f'<script>window.RAZ_BASE={json.dumps(base)};</script>\n  <script src="{rel_search}"></script>'
        text = re.sub(r'<script>window\.RAZ_SEARCH=.*?</script>', scripts, text, flags=re.S)
        text = re.sub(r'<script>window\.RAZ_BASE=.*?</script>\s*<script src="[^"]*search-index\.js"></script>', scripts, text, flags=re.S)
        page.write_text(text, encoding="utf-8")


def render_public_api(packages, docs, releases, site):
    API.mkdir(parents=True, exist_ok=True)
    public_docs = []
    for doc in docs:
        item = dict(doc)
        if item.get("available"):
            item["website_url"] = f'/docs/{item["local_url"]}'
        public_docs.append(item)
    payloads = {
        "packages.json": packages,
        "docs.json": public_docs,
        "releases.json": releases,
        "site.json": site,
        "source-audit.json": site.get("source_audit", {"warnings": [], "warning_count": 0}),
    }
    for name, value in payloads.items():
        (API / name).write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    (API / "index.json").write_text(json.dumps({
        "version": 1,
        "resources": {name[:-5]: f"./{name}" for name in payloads},
        "generated_from": "checked-in Raz repository snapshots",
    }, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def render_machine_files(packages, docs, releases, site):
    render_public_api(packages, docs, releases, site)
    well_known = ROOT / ".well-known"
    well_known.mkdir(exist_ok=True)
    stamp = site.get("snapshot", {}).get("snapshot_generated_at") or "2026-08-25T00:00:00Z"
    try:
        parsed = datetime.fromisoformat(stamp.replace("Z", "+00:00"))
        expires = parsed.replace(year=parsed.year + 1).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    except (ValueError, TypeError):
        expires = "2027-08-25T00:00:00Z"
    security = "\n".join([
        "Contact: https://github.com/raz-language/raz/security/advisories/new",
        f"Expires: {expires}",
        "Policy: https://github.com/raz-language/raz/blob/main/SECURITY.md",
        "Preferred-Languages: en",
        "",
    ])
    (well_known / "security.txt").write_text(security, encoding="utf-8")
    llms = [
        "# Raz",
        "",
        "> Raz is a systems programming language for safe, fast, predictable native software.",
        "",
        "## Primary resources",
        "- /learn/book/ — The Raz Book, a chapter-based language guide",
        "- /docs/ — documentation portal",
        "- /packages/ — official package catalog",
        "- /install/ — toolchain installation and publication status",
        "- /tools/ — compiler and toolchain overview",
        "- https://github.com/raz-language/raz — canonical compiler source",
        "",
        f"This snapshot contains {len(packages)} official packages and {sum(1 for doc in docs if doc.get('available'))} locally mirrored canonical documents.",
        "",
    ]
    (ROOT / "llms.txt").write_text("\n".join(llms), encoding="utf-8")



def apply_canonical_metadata():
    base = os.getenv("RAZ_SITE_URL", "").strip().rstrip("/")
    sitemap = ROOT / "sitemap.xml"
    robots = ROOT / "robots.txt"
    if not base:
        if sitemap.exists():
            sitemap.unlink()
        if robots.exists():
            lines = [line for line in robots.read_text(encoding="utf-8").splitlines() if not line.startswith("Sitemap:")]
            robots.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")
        for page in ROOT.rglob("*.html"):
            if "_site" in page.parts:
                continue
            text = page.read_text(encoding="utf-8")
            text = re.sub(r"\s*<link rel=\"canonical\"[^>]*>", "", text)
            text = re.sub(r"\s*<meta property=\"og:url\"[^>]*>", "", text)
            page.write_text(text, encoding="utf-8")
        return

    urls = []
    for page in sorted(ROOT.rglob("*.html")):
        if "_site" in page.parts:
            continue
        rel = page.relative_to(ROOT).as_posix()
        if rel == "404.html":
            canonical = f"{base}/404.html"
        elif rel == "index.html":
            canonical = base + "/"
        elif rel.endswith("/index.html"):
            canonical = f"{base}/{rel[:-10]}"
        else:
            canonical = f"{base}/{rel}"
        text = page.read_text(encoding="utf-8")
        text = re.sub(r"\s*<link rel=\"canonical\"[^>]*>", "", text)
        text = re.sub(r"\s*<meta property=\"og:url\"[^>]*>", "", text)
        injection = f'  <link rel="canonical" href="{esc(canonical)}">\n  <meta property="og:url" content="{esc(canonical)}">\n'
        text = text.replace("</head>", injection + "</head>")
        page.write_text(text, encoding="utf-8")
        if rel != "404.html":
            urls.append(canonical)

    xml = ['<?xml version="1.0" encoding="UTF-8"?>', '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">']
    xml.extend(f"  <url><loc>{esc(url)}</loc></url>" for url in urls)
    xml.append("</urlset>")
    sitemap.write_text("\n".join(xml) + "\n", encoding="utf-8")
    if robots.exists():
        lines = [line for line in robots.read_text(encoding="utf-8").splitlines() if not line.startswith("Sitemap:")]
        lines.append(f"Sitemap: {base}/sitemap.xml")
        robots.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")



# v8: chapter-based Raz Book generated from docs/GETTING-STARTED.md when available.
BOOK_META = [
    (1, "What Raz Is", "Start here", "Understand Raz's visible cost model, native execution model, and the role of Forge and LLVM.", "18-compilation-semantics", "Compilation semantics", ["D4000"]),
    (2, "Create and Build a Project", "Start here", "Create a package, understand raz.toml, and learn the normal check/build/run/test workflow.", "17-packages-and-dependencies", "Packages and dependencies", []),
    (3, "Your First Program", "Start here", "Write functions, type-first parameters, semicolon-terminated statements, and documentation comments.", "1-source-files-and-declarations", "Source files and declarations", ["D1001"]),
    (4, "Variables and Types", "Start here", "Use Raz scalar types and make numeric conversions explicit with as.", "4-primitive-and-compound-types", "Primitive and compound types", ["D2009", "D2289"]),
    (5, "Arrays, Slices, References, and Pointers", "Start here", "Work with fixed arrays, borrowed slices, references, and explicit raw-pointer boundaries.", "9-ownership-moves-and-references", "Ownership, moves, and references", ["D2056", "D2064"]),
    (6, "Expressions and Control Flow", "Language foundations", "Use operators, bool-only conditions, loops, ranges, break, continue, and return.", "7-control-flow", "Control flow", ["D2007", "D3006", "D3007"]),
    (7, "Structs and Methods", "Language foundations", "Model data with type-first fields and attach behavior through explicit impl receivers.", "5-structs-and-enums", "Structs and enums", []),
    (8, "Enums and Exhaustive Match", "Language foundations", "Use payload enums and exhaustive pattern matching so missing cases become compile-time errors.", "8-pattern-matching", "Pattern matching", ["D2038"]),
    (9, "Option, Result, and ?", "Language foundations", "Represent absence and recoverable failure in types and propagate failure with postfix ?.", "8-pattern-matching", "Pattern matching and recoverable errors", ["D2047"]),
    (10, "Ownership and Moves", "Ownership & abstraction", "Learn the single-owner model, explicit move, and why moved sources become unusable.", "9-ownership-moves-and-references", "Ownership, moves, and references", ["D2052", "D2054", "D2055"]),
    (11, "Borrowing and Lifetimes", "Ownership & abstraction", "Use many shared or one mutable borrow with non-lexical loan analysis and safe reference escape rules.", "9-ownership-moves-and-references", "Ownership, moves, and references", ["D2056", "D2057", "D2064"]),
    (12, "Drop and defer", "Ownership & abstraction", "Build deterministic cleanup with type-owned Drop and lexical LIFO defer.", "10-deterministic-destruction", "Deterministic destruction", ["D2050", "D2068"]),
    (13, "Generics", "Ownership & abstraction", "Write statically specialized generic functions, types, const generics, and bounded abstractions.", "11-generics-and-traits", "Generics and traits", ["D2097"]),
    (14, "Traits and Associated Items", "Ownership & abstraction", "Define reusable behavior with traits, associated items, static dispatch, and explicit dyn dispatch.", "11-generics-and-traits", "Generics and traits", ["D2097", "D2114"]),
    (15, "Iterators and Ranges", "Ownership & abstraction", "Understand the Iterator and IntoIterator contracts that power for loops beyond built-in arrays.", "12-iteration", "Iteration", []),
    (16, "Compile-Time Programming", "Ownership & abstraction", "Use deterministic bounded comptime execution, const functions, reflection, and layout queries.", "13-compile-time-programming", "Compile-time programming", ["D2212", "D2240"]),
    (17, "Closures and Callable Values", "Ownership & abstraction", "Capture by shared borrow, mutable borrow, or move and understand callable ownership modes.", "14-closures-and-function-pointers", "Closures and function pointers", ["D2125"]),
    (18, "Async, Tasks, and await", "Ownership & abstraction", "Use async fn, spawn, and await while preserving ownership across compiler-generated suspension frames.", "15-async", "Async", []),
    (19, "Modules, Packages, and Dependencies", "Build real software", "Split code into modules, import namespaces, lock dependency graphs, and consume the official registry.", "17-packages-and-dependencies", "Packages and dependencies", []),
    (20, "Standard Library", "Build real software", "Navigate core, alloc, collections, and std and understand why APIs live in each layer.", "4-primitive-and-compound-types", "Types and library foundations", []),
    (21, "Concurrency and Synchronization", "Build real software", "Build with threads, atomics, locks, channels, futures, tasks, timers, and cancellation.", "18-compilation-semantics", "Compilation semantics", []),
    (22, "Networking and I/O", "Build real software", "Use caller-controlled buffering, sockets, DNS, readiness, filesystem, and async I/O foundations.", "18-compilation-semantics", "Compilation semantics", []),
    (23, "Unsafe Code and Native Interop", "Build real software", "Keep extern, raw pointers, casts, and C ABI boundaries small, explicit, and auditable.", "16-unsafe-code-and-native-abi", "Unsafe code and native ABI", ["D2289"]),
    (24, "The Compiler Pipeline", "Compiler & production", "Follow source through semantic analysis, typed HIR, verified MIR, Forge, LLVM, WebAssembly, and RXE.", "18-compilation-semantics", "Compilation semantics", ["D4000"]),
    (25, "Native Performance", "Compiler & production", "Reason about performance across language semantics, library allocation behavior, and backend optimization.", "18-compilation-semantics", "Compilation semantics", []),
    (26, "Diagnostics, Formatting, and Testing", "Compiler & production", "Use stable diagnostic codes, canonical formatting, tests, and project inspection tools.", "19-diagnostics-and-implementation-freedom", "Diagnostics and implementation freedom", ["D2008", "D2009"]),
    (27, "A Complete Small Program", "Compiler & production", "Combine traits, generics, borrowing, enums, matching, and deterministic values in one program.", "11-generics-and-traits", "Generics and traits", []),
    (28, "Quick Reference", "Compiler & production", "Keep the core Raz syntax forms close at hand while writing real code.", "appendix-b-grammar-summary", "Grammar summary", []),
    (29, "Where to Go Next", "Compiler & production", "Turn the tutorial into a real project: resources, modules, tests, concurrency, packages, and carefully bounded unsafe code.", "contents", "Specification contents", []),
]

BOOK_EXAMPLES = {
    2: ("terminal", "raz new hello\ncd hello\nraz check\nraz run"),
    3: ("raz", 'fn main() -> i64 {\n    string message = "Hello from Raz";\n    print(message);\n    return 0;\n}'),
    4: ("raz", "i64 count = 42;\nf64 precise = count as f64;\nbool ready = true;"),
    5: ("raz", "i64 values[4] = [10, 20, 30, 40];\ni64 value = 41;\ni64& view = &value;\ni64& mut edit = &mut value;"),
    6: ("raz", 'i64 total = 0;\nfor value in 0..=4 {\n    total += value;\n}\nif (total == 10) {\n    print("ten");\n}'),
    7: ("raz", "struct Point {\n    i64 x;\n    i64 y;\n}\n\nimpl Point {\n    fn sum(Point& self) -> i64 {\n        return self.x + self.y;\n    }\n}"),
    8: ("raz", "enum Message {\n    Quit,\n    Number(i64),\n}\n\nfn value(Message message) -> i64 {\n    match message {\n        Message.Quit => { return 0; },\n        Message.Number(value) => { return value; },\n    }\n}"),
    9: ("raz", "fn relay(bool fail) -> Result<i64, i64> {\n    i64 value = produce(fail)?;\n    return Result<i64, i64>.Ok(value + 1);\n}"),
    10: ("raz", "Resource first = Resource(42);\nResource second = move first;\n// first can no longer be used here."),
    11: ("raz", "fn increment_twice(i64& mut input) -> i64 {\n    {\n        i64& mut child = &mut*input;\n        *child += 1;\n    }\n    *input += 1;\n    return *input;\n}"),
    12: ("raz", "impl Drop for Resource {\n    fn drop(Resource& mut self) {\n        release(self.handle);\n    }\n}\n\nfn work() {\n    defer cleanup();\n}"),
    13: ("raz", "fn identity<T>(T value) -> T {\n    return value;\n}\n\nstruct Buffer<T, const usize N> {\n    T values[N];\n}"),
    14: ("raz", "trait Measurable {\n    fn measure(Self& self) -> i64;\n}\n\nfn read<T: Measurable>(T& value) -> i64 {\n    return value.measure();\n}"),
    15: ("raz", "i64 total = 0;\nfor value in 0..10 {\n    total += value;\n}"),
    16: ("raz", "const i64 BASE = 40 + 2;\ncomptime {\n    assert(BASE == 42);\n}"),
    17: ("raz", "i64 value = 40;\nauto read = ref fn() -> i64 {\n    return *value;\n};"),
    18: ("raz", "async fn compute(i64 value) -> i64 {\n    return value + 1;\n}\n\nasync fn pipeline() -> i64 {\n    i64 child = spawn compute(41);\n    return await child;\n}"),
    19: ("toml", '[package]\nname = "app"\nversion = "1.0.0"\nkind = "executable"\n\n[dependencies]\njson = "^0.1.0"'),
    23: ("raz", "extern fn native_call(i64 value) -> i64;\n\nfn call_native(i64 value) -> i64 {\n    unsafe {\n        return native_call(value);\n    }\n}"),
    24: ("text", "Raz source\n  -> semantic analysis\n  -> typed HIR\n  -> verified MIR\n  -> Forge / LLVM / WebAssembly / RXE"),
    26: ("terminal", "raz check\nraz fmt --check\nraz test\nraz diagnostics"),
    27: ("raz", "fn validate<T: Score>(T& value) -> Check<i64> {\n    i64 result = value.score();\n    if (result == 42) {\n        return Check<i64>.Ok(result);\n    }\n    return Check<i64>.Failed(result);\n}"),
}

BOOK_KEY_IDEAS = {
    1: ["Native execution without a mandatory tracing collector", "One frontend settles semantics before backend code generation", "Forge is the default native backend; LLVM is a production alternative"],
    10: ["Exactly one active owner is responsible for an owned resource", "move transfers ownership instead of copying it", "Borrowing lets code access a value without changing its owner"],
    11: ["Many shared borrows or one exclusive mutable borrow", "Loans can end at last use through non-lexical analysis", "Returned references must have a lifetime the compiler can prove"],
    12: ["Drop is type-owned deterministic cleanup", "defer is lexical LIFO cleanup", "Cleanup is elaborated into MIR across early exits"],
    18: ["Async state lives in compiler-generated frames", "Owned values can move into an async frame", "Unsafe reference escapes across suspension are rejected"],
    24: ["Language meaning is fixed before a backend runs", "MIR is the verified executable semantic boundary", "Backend selection does not redefine Raz semantics"],
}

BOOK_GROUP_DESCRIPTIONS = {
    "Start here": "Get the toolchain mental model, create a project, and learn the core surface syntax.",
    "Language foundations": "Build data and control flow with structs, enums, matching, and typed error handling.",
    "Ownership & abstraction": "Learn the ownership model, deterministic cleanup, generics, traits, iteration, comptime, closures, and async.",
    "Build real software": "Move from language constructs to packages, the standard library, concurrency, networking, and native boundaries.",
    "Compiler & production": "Understand the compiler pipeline, performance model, diagnostics, testing, and how to keep growing after the tutorial.",
}


def _book_fallback_markdown(number, title, description):
    ideas = BOOK_KEY_IDEAS.get(number, [description, "Keep cost and ownership decisions visible in source", "Use compiler diagnostics as part of the development loop"])
    lines = [description, "", "### Key ideas", ""]
    lines.extend(f"- {item}" for item in ideas)
    example = BOOK_EXAMPLES.get(number)
    if example:
        lang, code = example
        lines += ["", "### Example", "", f"```{lang}", code, "```"]
    lines += ["", "**Summary**", "", description, "", "**Exercises**", "", "1. Change the example or concept in one small way and predict the compiler result before running it.", "2. Follow the related specification or diagnostic link and connect the rule back to the source code."]
    return "\n".join(lines)


def parse_book_data(docs):
    meta = {number: {"number": number, "title": title, "group": group, "description": description, "spec_anchor": spec_anchor, "spec_label": spec_label, "diagnostics": diagnostics} for number, title, group, description, spec_anchor, spec_label, diagnostics in BOOK_META}
    source = DOC_RAW / "GETTING-STARTED.md"
    chapters = []
    canonical = False
    if source.exists():
        raw = source.read_text(encoding="utf-8")
        matches = list(re.finditer(r"^## Chapter\s+(\d+)\s+-\s+(.+?)\s*$", raw, flags=re.M))
        for index, match in enumerate(matches):
            number = int(match.group(1))
            if number not in meta:
                continue
            end = matches[index + 1].start() if index + 1 < len(matches) else len(raw)
            body = raw[match.end():end].strip()
            body = re.sub(r"\n---\s*$", "", body).strip()
            item = dict(meta[number])
            item["title"] = match.group(2).strip()
            item["markdown"] = body
            item["canonical"] = True
            chapters.append(item)
        canonical = len(chapters) >= 29
    if not canonical:
        chapters = []
        for number in range(1, 30):
            item = dict(meta[number])
            item["markdown"] = _book_fallback_markdown(number, item["title"], item["description"])
            item["canonical"] = False
            chapters.append(item)
    for chapter in chapters:
        chapter["slug"] = f'chapter-{chapter["number"]:02d}'
        chapter["url"] = f'learn/book/{chapter["slug"]}/index.html'
    return {
        "title": "The Raz Book",
        "source": f"{RAZ}/blob/main/docs/GETTING-STARTED.md",
        "canonical": canonical,
        "chapter_count": len(chapters),
        "chapters": chapters,
        "groups": list(BOOK_GROUP_DESCRIPTIONS),
    }


def _book_spec_href(docs, chapter, prefix="../../../"):
    spec = next((doc for doc in docs if Path(doc["path"]).name == "LANGUAGE-SPECIFICATION.md"), None)
    anchor = chapter.get("spec_anchor", "contents")
    if spec and spec.get("available"):
        return f'{prefix}docs/reference/{spec["slug"]}/index.html#{anchor}'
    return f'{RAZ}/blob/main/docs/LANGUAGE-SPECIFICATION.md#{anchor}'


def _decorate_book_html(article_html):
    # Give the canonical Summary/Exercises blocks stronger learning affordances.
    article_html = re.sub(r'<p><strong>Summary</strong></p>\s*<p>(.*?)</p>', r'<aside class="book-summary"><span>CHAPTER SUMMARY</span><p>\1</p></aside>', article_html, flags=re.S)
    article_html = re.sub(r'<p><strong>Exercises</strong></p>\s*<ol>(.*?)</ol>', r'<section class="book-exercises"><div><span>PRACTICE</span><h2>Exercises</h2></div><ol>\1</ol></section>', article_html, flags=re.S)
    return article_html


def _book_concept_visual(chapter):
    if chapter["number"] == 10:
        return '''<section class="ownership-model" aria-label="Ownership transfer model"><div class="ownership-model-heading"><span>MENTAL MODEL</span><h2>Ownership is a transfer, not a hidden copy.</h2></div><div class="ownership-flow"><div class="ownership-node active"><span>OWNER</span><b>first</b><small>Resource(42)</small></div><div class="ownership-arrow"><code>move first</code><span>→</span></div><div class="ownership-node active"><span>NEW OWNER</span><b>second</b><small>Resource(42)</small></div><div class="ownership-node unavailable"><span>SOURCE</span><b>first</b><small>no longer usable</small></div></div><p>The compiler tracks which place owns the resource at every program point. Moving a non-Copy value changes that state; the old source cannot be read again unless it is reinitialized.</p></section>'''
    if chapter["number"] == 11:
        return '''<section class="borrow-model" aria-label="Borrowing permission model"><div class="ownership-model-heading"><span>MENTAL MODEL</span><h2>Borrow permissions are intentionally asymmetric.</h2></div><div class="borrow-compare"><article><span>SHARED <code>T&amp;</code></span><b>Many readers</b><div class="borrow-icons"><i></i><i></i><i></i></div><p>Multiple overlapping shared borrows can observe the same value while mutation is excluded.</p></article><article><span>MUTABLE <code>T&amp; mut</code></span><b>One writer</b><div class="borrow-icons single"><i></i></div><p>An exclusive mutable borrow can update the value, so overlapping access that could alias it is rejected.</p></article></div><div class="borrow-rule"><span>NON-LEXICAL LOANS</span><p>A borrow constrains its source through its last use, not automatically until the closing brace. This lets safe code regain access as soon as the loan is actually dead.</p></div></section>'''
    if chapter["number"] == 18:
        return '''<section class="ownership-model async-model" aria-label="Async ownership model"><div class="ownership-model-heading"><span>ASYNC MODEL</span><h2>Values that survive <code>await</code> live in the async frame.</h2></div><div class="async-flow"><div><span>CALL</span><b>async fn</b></div><span>→</span><div><span>LOWER</span><b>state machine</b></div><span>→</span><div><span>SUSPEND</span><b>await</b></div><span>→</span><div><span>RESUME</span><b>same frame</b></div></div><p>Ownership does not disappear when execution suspends. The compiler stabilizes values that live across suspension and rejects references whose source storage cannot safely outlive the await point.</p></section>'''
    return ""


def _book_related(chapter, docs, prefix="../../../"):
    links = [f'<a href="{esc(_book_spec_href(docs, chapter, prefix))}"><span>Normative reference</span><b>{esc(chapter["spec_label"])} →</b></a>']
    for code in chapter.get("diagnostics", []):
        links.append(f'<a href="{prefix}docs/diagnostics/index.html#{code.lower()}"><span>Diagnostic</span><b>{esc(code)} →</b></a>')
    number = chapter["number"]
    if number in (19,):
        links.append(f'<a href="{prefix}packages/index.html"><span>Ecosystem</span><b>Official packages →</b></a>')
    if number in (20, 21, 22):
        links.append(f'<a href="{prefix}docs/stdlib/index.html"><span>API reference</span><b>Standard library →</b></a>')
    if number in (24, 25):
        links.append(f'<a href="{prefix}docs/compiler/index.html"><span>Architecture</span><b>Compiler guide →</b></a>')
    if number == 26:
        links.append(f'<a href="{prefix}docs/diagnostics/index.html"><span>Reference</span><b>Diagnostic index →</b></a>')
    return "".join(links)


def _book_nav(chapters, current=None, href_prefix=""):
    rows = []
    current_group = None
    for chapter in chapters:
        if chapter["group"] != current_group:
            current_group = chapter["group"]
            rows.append(f'<p class="book-nav-group">{esc(current_group)}</p>')
        current_attr = ' aria-current="page"' if current == chapter["number"] else ''
        current_class = ' current' if current == chapter["number"] else ''
        rows.append(f'<a class="book-nav-item{current_class}" data-book-nav-item="{chapter["number"]}" href="{href_prefix}{chapter["slug"]}/index.html"{current_attr}><span class="book-check" aria-hidden="true"></span><em>{chapter["number"]:02d}</em><b>{esc(chapter["title"])}</b></a>')
    return "".join(rows)


def _book_group_cards(book, href_prefix="book/"):
    groups = []
    for group in book["groups"]:
        chapters = [chapter for chapter in book["chapters"] if chapter["group"] == group]
        links = ''.join(f'<a data-book-nav-item="{chapter["number"]}" href="{href_prefix}{chapter["slug"]}/index.html"><span class="book-check" aria-hidden="true"></span><em>{chapter["number"]:02d}</em><div><b>{esc(chapter["title"])}</b><p>{esc(chapter["description"])}</p></div><strong>→</strong></a>' for chapter in chapters)
        groups.append(f'<section class="book-group"><div class="book-group-heading"><div><p class="kicker">{esc(group.upper())}</p><h2>{esc(group)}</h2></div><p>{esc(BOOK_GROUP_DESCRIPTIONS[group])}</p></div><div class="book-chapter-list">{links}</div></section>')
    return ''.join(groups)


def render_learn_landing(book):
    page = ROOT / "learn" / "index.html"
    pre, footer = shell_parts(page)
    source_badge = "Canonical tutorial synchronized" if book["canonical"] else "Offline curated snapshot · canonical text expands on refresh"
    groups = []
    for group in book["groups"]:
        members = [c for c in book["chapters"] if c["group"] == group]
        groups.append(f'<article><span>{members[0]["number"]:02d}–{members[-1]["number"]:02d}</span><h3>{esc(group)}</h3><p>{esc(BOOK_GROUP_DESCRIPTIONS[group])}</p></article>')
    body = f'''<header class="page-hero learn-hero"><div class="shell narrow"><p class="kicker">LEARN RAZ</p><h1>Learn the language from first program to production systems.</h1><p class="page-lead">The Raz Book turns the canonical 29-chapter Getting Started guide into a focused reading path with progress tracking, direct specification links, diagnostics, and API references.</p><div class="button-row"><a class="button button-primary" href="book/chapter-01/index.html">Start the Raz Book</a><a class="button button-secondary" href="book/index.html">Browse all 29 chapters</a></div><div class="learn-source-state"><span class="live-dot"></span>{esc(source_badge)}</div></div></header>
<main id="main" class="after-hero"><section class="section section-white"><div class="shell"><div class="learn-dashboard"><div><p class="kicker">YOUR PATH</p><h2>One coherent route through Raz.</h2><p>Read front to back for a complete introduction, or jump directly to ownership, async, packages, compiler internals, or another topic.</p></div><aside class="book-progress-card"><div><span>BOOK PROGRESS</span><b data-book-progress-count>0 / {book['chapter_count']} chapters</b></div><div class="book-progress-track"><i data-book-progress-bar style="width:0%"></i></div><a href="book/chapter-01/index.html" data-book-continue data-book-prefix="book/">Continue reading →</a></aside></div><div class="learn-track-grid">{''.join(groups)}</div></div></section>
<section class="section section-soft"><div class="shell"><div class="section-top compact"><div><p class="kicker">THE RAZ BOOK</p><h2>29 chapters, generated from one source of truth.</h2></div><p>The deployed site splits <code>docs/GETTING-STARTED.md</code> into readable chapters while keeping the original repository document canonical.</p></div>{_book_group_cards(book)}</div></section>
<section class="section section-dark"><div class="shell two-col"><div><p class="kicker">REFERENCE WHILE YOU LEARN</p><h2>Move from explanation to exact rules without leaving the site.</h2><p class="section-copy">Each chapter links directly into the normative language specification, relevant stable diagnostics, the package registry, standard-library browser, or compiler documentation.</p></div><div class="learn-reference-links"><a href="../docs/reference/language-specification/index.html">Language specification <span>→</span></a><a href="../docs/diagnostics/index.html">Diagnostic index <span>→</span></a><a href="../docs/stdlib/index.html">Standard library <span>→</span></a><a href="../docs/compiler/index.html">Compiler guide <span>→</span></a></div></div></section></main>'''
    # Avoid a broken local spec link in an offline snapshot where that document is not mirrored.
    if not (ROOT / "docs" / "reference" / "language-specification" / "index.html").exists():
        body = body.replace('href="../docs/reference/language-specification/index.html"', f'href="{RAZ}/blob/main/docs/LANGUAGE-SPECIFICATION.md"')
    page.write_text(rewrite_head(pre, "Learn Raz — The Raz Book", "A chapter-based path through the Raz systems programming language, from first program to ownership, async, packages, and compiler internals.") + body + footer, encoding="utf-8")


def render_book_hub(book):
    learn_page = ROOT / "learn" / "index.html"
    pre, footer = shell_parts(learn_page)
    pre = pre.replace('href="../', 'href="../../').replace('src="../', 'src="../../')
    footer = footer.replace('href="../', 'href="../../').replace('src="../', 'src="../../')
    source_state = "Full canonical chapter text" if book["canonical"] else "Curated offline chapter snapshot"
    body = f'''<header class="page-hero book-hub-hero"><div class="shell narrow"><div class="doc-breadcrumbs"><a href="../index.html">Learn</a><span>/</span><span>The Raz Book</span></div><p class="kicker">THE RAZ BOOK</p><h1>A practical guide to Raz 1.0.</h1><p class="page-lead">Follow the language in order—from the project model and syntax through ownership, traits, async, packages, native interop, and the compiler pipeline.</p><div class="book-hub-meta"><span>{book['chapter_count']} chapters</span><span>{esc(source_state)}</span><a href="{esc(book['source'])}">Canonical source ↗</a></div></div></header>
<main id="main" class="after-hero"><section class="section section-white"><div class="shell"><div class="book-hub-progress"><div><span>READING PROGRESS</span><b data-book-progress-count>0 / {book['chapter_count']} chapters</b></div><div class="book-progress-track"><i data-book-progress-bar style="width:0%"></i></div><a class="button button-primary button-small" href="chapter-01/index.html" data-book-continue data-book-prefix="">Continue</a></div>{_book_group_cards(book, "")}</div></section></main>'''
    directory = ROOT / "learn" / "book"
    directory.mkdir(exist_ok=True)
    (directory / "index.html").write_text(rewrite_head(pre, "The Raz Book — Learn Raz", "The 29-chapter Raz systems programming language guide, with progress tracking and direct links to the specification and diagnostics.") + body + footer, encoding="utf-8")


def render_book_chapters(book, docs):
    root = ROOT / "learn" / "book"
    root.mkdir(parents=True, exist_ok=True)
    valid = {chapter["slug"] for chapter in book["chapters"]}
    for child in root.iterdir():
        if child.is_dir() and child.name not in valid:
            shutil.rmtree(child)
    learn_pre, learn_footer = shell_parts(ROOT / "learn" / "index.html")
    detail_pre = learn_pre.replace('href="../', 'href="../../../').replace('src="../', 'src="../../../')
    detail_footer = learn_footer.replace('href="../', 'href="../../../').replace('src="../', 'src="../../../')
    nav = _book_nav(book["chapters"], href_prefix="../")
    for index, chapter in enumerate(book["chapters"]):
        article_html, toc = markdown_to_html(chapter["markdown"], docs)
        article_html = _decorate_book_html(article_html)
        toc_html = ''.join(f'<a class="toc-level-{level}" href="#{esc(anchor)}">{esc(label)}</a>' for level, label, anchor in toc)
        previous = book["chapters"][index - 1] if index else None
        following = book["chapters"][index + 1] if index + 1 < len(book["chapters"]) else None
        prev_link = f'<a href="../{previous["slug"]}/index.html"><span>Previous</span><b>← {esc(previous["title"])}</b></a>' if previous else '<span></span>'
        next_link = f'<a class="next" href="../{following["slug"]}/index.html"><span>Next</span><b>{esc(following["title"])} →</b></a>' if following else '<a class="next" href="../index.html"><span>Finished</span><b>Back to the book →</b></a>'
        percent = round(chapter["number"] / book["chapter_count"] * 100)
        source_note = "Synced from canonical Getting Started" if chapter["canonical"] else "Curated offline snapshot; CI refresh expands to canonical chapter text"
        body = f'''<div class="book-reading-progress" aria-hidden="true"><i style="width:{percent}%"></i></div><header class="page-hero book-chapter-hero"><div class="shell narrow"><div class="doc-breadcrumbs"><a href="../../index.html">Learn</a><span>/</span><a href="../index.html">The Raz Book</a><span>/</span><span>Chapter {chapter['number']}</span></div><p class="kicker">CHAPTER {chapter['number']:02d} OF {book['chapter_count']}</p><h1>{esc(chapter['title'])}</h1><p class="page-lead">{esc(chapter['description'])}</p><div class="book-chapter-source"><span>{esc(source_note)}</span><a href="{esc(book['source'])}">View canonical guide ↗</a></div></div></header>
<main id="main" class="after-hero"><div class="shell book-reading-layout"><aside class="book-sidebar"><div class="book-sidebar-top"><a href="../index.html">← The Raz Book</a><div><span>YOUR PROGRESS</span><b data-book-progress-count>0 / {book['chapter_count']}</b></div><div class="book-progress-track"><i data-book-progress-bar style="width:0%"></i></div></div><nav aria-label="Book chapters">{_book_nav(book['chapters'], current=chapter['number'], href_prefix='../')}</nav></aside><article class="book-article"><div class="book-article-meta"><span>{esc(chapter['group'])}</span><button type="button" data-book-complete data-book-chapter="{chapter['number']}">Mark chapter complete</button></div>{_book_concept_visual(chapter)}{article_html}<section class="book-related"><div><span>GO DEEPER</span><h2>Related references</h2></div><div class="resource-list">{_book_related(chapter, docs)}</div></section><nav class="doc-pager book-pager" aria-label="Book pagination">{prev_link}{next_link}</nav></article><aside class="book-toc"><p>IN THIS CHAPTER</p><nav>{toc_html or '<span class="muted">Core concepts</span>'}</nav><a class="book-spec-shortcut" href="{esc(_book_spec_href(docs, chapter))}"><span>SPECIFICATION</span><b>{esc(chapter['spec_label'])} ↗</b></a></aside></div></main>'''
        directory = root / chapter["slug"]
        directory.mkdir(exist_ok=True)
        title = f'Chapter {chapter["number"]}: {chapter["title"]} — The Raz Book'
        (directory / "index.html").write_text(rewrite_head(detail_pre, title, chapter["description"]) + body + detail_footer, encoding="utf-8")


def render_learning_product(docs):
    book = parse_book_data(docs)
    render_learn_landing(book)
    render_book_hub(book)
    render_book_chapters(book, docs)
    GEN.mkdir(parents=True, exist_ok=True)
    public = {key: value for key, value in book.items() if key != "chapters"}
    public["chapters"] = [{k: v for k, v in chapter.items() if k != "markdown"} for chapter in book["chapters"]]
    (GEN / "book.json").write_text(json.dumps(public, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return public


def augment_book_search(book):
    path = ROOT / "assets" / "search-index.js"
    prefix = "window.RAZ_SEARCH="
    raw = path.read_text(encoding="utf-8")
    if not raw.startswith(prefix):
        return
    items = json.loads(raw[len(prefix):].rstrip().rstrip(";"))
    items.append({"title": "The Raz Book", "description": "A 29-chapter path through Raz 1.0", "url": "learn/book/index.html", "keywords": "learn book tutorial chapters ownership borrowing async traits packages"})
    for chapter in book["chapters"]:
        items.append({"title": f'Chapter {chapter["number"]}: {chapter["title"]}', "description": chapter["description"], "url": chapter["url"], "keywords": f'learn book chapter {chapter["group"]} {chapter["spec_label"]} ' + ' '.join(chapter.get("diagnostics", []))})
    path.write_text(prefix + json.dumps(items, separators=(",", ":")) + ";\n", encoding="utf-8")


def augment_book_api(book):
    API.mkdir(parents=True, exist_ok=True)
    (API / "book.json").write_text(json.dumps(book, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    index_path = API / "index.json"
    index = json.loads(index_path.read_text(encoding="utf-8"))
    index.setdefault("resources", {})["book"] = "./book.json"
    index_path.write_text(json.dumps(index, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def render(packages, docs, releases, site):
    package_docs = render_packages(packages)
    render_docs(docs)
    book = render_learning_product(docs)
    render_releases(releases, site)
    render_install(releases, site)
    diagnostics, stdlib = render_reference_products()
    consistency = stdlib.get("consistency", {})
    if consistency and not consistency.get("consistent", True):
        warnings = site.setdefault("source_audit", {}).setdefault("warnings", [])
        code = "stdlib-index-count-drift"
        if not any(item.get("code") == code for item in warnings):
            warnings.append({
                "code": code,
                "message": (f"STANDARD-LIBRARY.md declares {consistency.get('declared_total_modules')} modules / "
                            f"{consistency.get('declared_total_items')} public items, while its generated module table "
                            f"enumerates {consistency.get('observed_modules')} modules / {consistency.get('observed_items')} items."),
                "source": "raz-language/raz/docs/STANDARD-LIBRARY.md",
            })
        site["source_audit"]["warning_count"] = len(warnings)
        (GEN / "site.json").write_text(json.dumps(site, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        (GEN / "source-audit.json").write_text(json.dumps(site["source_audit"], indent=2, sort_keys=True) + "\n", encoding="utf-8")
    render_search(packages, docs)
    augment_search_index(diagnostics, stdlib)
    augment_book_search(book)
    augment_package_docs_search(package_docs)
    render_machine_files(packages, docs, releases, site)
    augment_public_api(diagnostics, stdlib)
    augment_book_api(book)
    augment_package_docs_api(package_docs)
    apply_canonical_metadata()

def snapshot_files():
    ignored = {Path("data/raw/source-state.json")}
    return {
        path.relative_to(ROOT): path.read_bytes()
        for path in ROOT.rglob("*")
        if path.is_file()
        and path.relative_to(ROOT) not in ignored
        and "_site" not in path.relative_to(ROOT).parts
        and "__pycache__" not in path.relative_to(ROOT).parts
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--refresh", action="store_true", help="refresh data/raw from GitHub before rendering")
    parser.add_argument("--offline", action="store_true", help="render only from the checked-in snapshot")
    parser.add_argument("--check", action="store_true", help="fail if rendering would change checked-in generated output")
    args = parser.parse_args()

    if args.refresh:
        try:
            refresh_raw()
        except (URLError, HTTPError, TimeoutError) as error:
            raise SystemExit(f"failed to refresh Raz website data: {error}")

    before = snapshot_files() if args.check else None
    data = build_data()
    render(*data)
    enhancer = ROOT / "scripts" / "enhance_v11.py"
    if enhancer.exists():
        subprocess.run([sys.executable, str(enhancer)], cwd=ROOT, check=True)
    enhancer_v12 = ROOT / "scripts" / "enhance_v12.py"
    if enhancer_v12.exists():
        subprocess.run([sys.executable, str(enhancer_v12)], cwd=ROOT, check=True)

    if args.check:
        after = snapshot_files()
        changed = [str(path) for path in sorted(set(before) | set(after), key=str) if before.get(path) != after.get(path)]
        if changed:
            print("generated site is stale; run: python3 scripts/sync_site.py --offline")
            print("\n".join("  " + item for item in changed))
            raise SystemExit(1)
        print("OK: generated pages match the checked-in Raz data snapshot")
    else:
        print(f"OK: synchronized {len(data[0])} packages, {len(data[1])} docs, {len(data[2])} published releases")


if __name__ == "__main__":
    main()
