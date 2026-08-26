#!/usr/bin/env python3
"""Release publication, project news, and sharded global search.

This enhancer keeps release/news surfaces source-driven from the canonical Raz
GitHub release snapshot, and splits the lazy global search corpus so ordinary
search opens stay lightweight even as API symbol documentation grows.
"""
from __future__ import annotations

from datetime import datetime, timezone
from email.utils import format_datetime
from pathlib import Path
import hashlib
import html
import json
import os
import re
import shutil
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
ASSETS = ROOT / "assets"
GEN = ROOT / "data" / "generated"
API = ROOT / "api" / "v1"
SITE_JS = ASSETS / "site.js"
STYLES = ASSETS / "styles.css"
SEARCH_INDEX = ASSETS / "search-index.json"
SEARCH_CORE = ASSETS / "search-core.json"
SEARCH_API = ASSETS / "search-api.json"
SITE_ORIGIN = (os.getenv("RAZ_SITE_URL") or "https://raz-language.github.io").strip().rstrip("/")
RAZ_RELEASES = "https://github.com/raz-language/raz/releases"


def esc(value: object) -> str:
    return html.escape(str(value), quote=True)


def parse_dt(value: str | None) -> datetime:
    if not value:
        return datetime(1970, 1, 1, tzinfo=timezone.utc)
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def display_date(value: str | None) -> str:
    dt = parse_dt(value)
    return dt.strftime("%B %d, %Y").replace(" 0", " ")


def slug_for_release(release: dict) -> str:
    tag = release.get("tag") or release.get("name") or "release"
    slug = re.sub(r"[^A-Za-z0-9._-]+", "-", str(tag)).strip("-").lower()
    return slug or "release"


def release_version(release: dict) -> str:
    return str(release.get("tag") or release.get("name") or "release").lstrip("v")


def asset_kind(name: str) -> str:
    lower = name.lower()
    if lower.endswith(".msi"):
        return "Windows installer"
    if "windows" in lower and lower.endswith(".zip"):
        return "Windows portable"
    if "linux" in lower and lower.endswith((".tar.gz", ".tgz")):
        return "Linux toolchain"
    if lower.endswith(".sha256") or lower == "sha256sums":
        return "Checksum"
    if "release-notes" in lower and lower.endswith(".md"):
        return "Release notes"
    return "Release asset"


def human_size(size: object) -> str:
    if not isinstance(size, (int, float)):
        return ""
    n = float(size)
    for unit in ("B", "KB", "MB", "GB"):
        if n < 1024 or unit == "GB":
            return f"{int(n)} {unit}" if unit == "B" else f"{n:.1f} {unit}"
        n /= 1024
    return ""


def shell_parts() -> tuple[str, str]:
    text = (ROOT / "releases" / "index.html").read_text(encoding="utf-8")
    hero = text.index('<header class="page-hero"')
    footer = text.index('<footer class="site-footer">')
    return text[:hero], text[footer:]


def rewrite_head(pre: str, *, title: str, description: str, canonical_path: str, depth: int = 1) -> str:
    prefix = "../" * depth
    if depth != 1:
        pre = pre.replace('../assets/', f'{prefix}assets/')
        pre = pre.replace('../site.webmanifest', f'{prefix}site.webmanifest')
        pre = pre.replace('window.RAZ_BASE="../"', f'window.RAZ_BASE="{prefix}"')
        # Relative shell navigation/footer lives outside pre for the footer, but brand/nav are here.
        for rel in ("index.html", "learn/index.html", "docs/index.html", "packages/index.html", "tools/index.html", "community/index.html", "install/index.html"):
            pre = pre.replace(f'href="../{rel}"', f'href="{prefix}{rel}"')
    pre = re.sub(r'<title>.*?</title>', f'<title>{esc(title)}</title>', pre, count=1, flags=re.S)
    pre = re.sub(r'<meta name="description" content="[^"]*">', f'<meta name="description" content="{esc(description)}">', pre, count=1)
    pre = re.sub(r'<meta property="og:title" content="[^"]*">', f'<meta property="og:title" content="{esc(title)}">', pre, count=1)
    pre = re.sub(r'<meta property="og:description" content="[^"]*">', f'<meta property="og:description" content="{esc(description)}">', pre, count=1)
    pre = re.sub(r'<meta name="twitter:title" content="[^"]*">', f'<meta name="twitter:title" content="{esc(title)}">', pre, count=1)
    pre = re.sub(r'<meta name="twitter:description" content="[^"]*">', f'<meta name="twitter:description" content="{esc(description)}">', pre, count=1)
    canonical = f"{SITE_ORIGIN}{canonical_path}"
    if re.search(r'<link rel="canonical" href="[^"]+">', pre):
        pre = re.sub(r'<link rel="canonical" href="[^"]+">', f'<link rel="canonical" href="{canonical}">', pre, count=1)
    else:
        pre = pre.replace('</head>', f'  <link rel="canonical" href="{canonical}">\n</head>')
    if re.search(r'<meta property="og:url" content="[^"]+">', pre):
        pre = re.sub(r'<meta property="og:url" content="[^"]+">', f'<meta property="og:url" content="{canonical}">', pre, count=1)
    else:
        pre = pre.replace('</head>', f'  <meta property="og:url" content="{canonical}">\n</head>')
    return pre


def adjust_footer(footer: str, depth: int) -> str:
    prefix = "../" * depth
    if depth == 1:
        return footer
    for rel in ("index.html", "learn/index.html", "docs/index.html", "packages/index.html", "install/index.html", "status/index.html"):
        footer = footer.replace(f'href="../{rel}"', f'href="{prefix}{rel}"')
    return footer


def release_asset_rows(release: dict) -> str:
    rows = []
    for asset in release.get("assets", []):
        name = asset.get("name") or "asset"
        digest = str(asset.get("digest") or "")
        digest_text = digest.split(":", 1)[1] if digest.startswith("sha256:") else digest
        digest_html = f'<code title="SHA-256">{esc(digest_text)}</code>' if digest_text else '<span class="muted">—</span>'
        rows.append(
            f'<div class="release-asset-row"><div><span>{esc(asset_kind(name).upper())}</span><b>{esc(name)}</b></div>'
            f'<small>{esc(human_size(asset.get("size")))}</small><div class="release-asset-digest">{digest_html}</div>'
            f'<a class="button button-secondary button-small" href="{esc(asset.get("url") or release.get("url") or RAZ_RELEASES)}">Download</a></div>'
        )
    return ''.join(rows) or '<div class="empty-state">No published assets are recorded for this release.</div>'


def render_release_details(releases: list[dict]) -> list[dict]:
    pre_base, footer_base = shell_parts()
    root = ROOT / "releases"
    manifest = GEN / "release-pages.json"
    if manifest.exists():
        try:
            previous = json.loads(manifest.read_text(encoding="utf-8"))
        except Exception:
            previous = []
        for slug in previous:
            child = root / str(slug)
            if child.is_dir():
                shutil.rmtree(child)
    entries = []
    generated_slugs = []
    for release in releases:
        slug = slug_for_release(release)
        target = root / slug
        target.mkdir(parents=True, exist_ok=True)
        generated_slugs.append(slug)
        version = release_version(release)
        status = "PRERELEASE" if release.get("prerelease") else "STABLE"
        description = f"Raz {version} release details, official toolchain downloads, checksums, and release metadata."
        pre = rewrite_head(pre_base, title=f"Raz {version} — Release details", description=description, canonical_path=f"/releases/{slug}/", depth=2)
        footer = adjust_footer(footer_base, 2)
        notes = next((a for a in release.get("assets", []) if (a.get("name") or "").lower() == "release-notes.md"), None)
        notes_link = f'<a class="button button-secondary" href="{esc(notes["url"])}">Release notes ↗</a>' if notes else ''
        published = release.get("published_at") or ""
        body = f'''<header class="page-hero"><div class="shell narrow"><div class="doc-breadcrumbs"><a href="../index.html">Releases</a><span>/</span><span>{esc(release.get('tag') or release.get('name') or version)}</span></div><p class="kicker">RAZ RELEASE</p><h1>Raz {esc(version)}</h1><p class="page-lead">Published <time datetime="{esc(published)}">{esc(display_date(published))}</time>. This page is generated from the canonical <code>raz-language/raz</code> GitHub release and remains a stable record of the published artifacts.</p><div class="button-row"><a class="button button-primary" href="{esc(release.get('url') or RAZ_RELEASES)}">GitHub release ↗</a>{notes_link}</div></div></header>
<main id="main" class="after-hero"><section class="section section-white"><div class="shell"><div class="release-detail-summary"><article><span>CHANNEL</span><b>{status}</b><p>{'Pre-release toolchain build.' if release.get('prerelease') else 'Stable Raz toolchain release.'}</p></article><article><span>PUBLISHED</span><b>{esc(display_date(published))}</b><p>Canonical release timestamp from GitHub.</p></article><article><span>ASSETS</span><b>{len(release.get('assets', []))}</b><p>Published files including checksums and notes.</p></article></div></div></section><section class="section section-soft"><div class="shell"><div class="section-top compact"><div><p class="kicker">RELEASE ASSETS</p><h2>Downloads and integrity metadata.</h2></div><p>Artifact names, sizes, SHA-256 digests where available, and download URLs are preserved directly from the release feed.</p></div><div class="release-assets-list">{release_asset_rows(release)}</div></div></section><section class="section section-white"><div class="shell release-detail-foot"><div><p class="kicker">DOCUMENTATION</p><h2>Use the matching Raz documentation.</h2><p>Raz 1.0 documentation is preserved as a versioned static snapshot so release-era language and API references remain stable.</p></div><div class="button-row"><a class="button button-primary" href="../../docs/1.0/index.html">Raz 1.0 docs</a><a class="button button-secondary" href="../../learn/1.0/book/index.html">Raz 1.0 Book</a><a class="text-link" href="../index.html">All releases →</a></div></div></section></main>'''
        (target / "index.html").write_text(pre + body + footer, encoding="utf-8")
        entries.append({
            "title": f"Raz {version} released",
            "description": f"Official Raz {version} {'prerelease' if release.get('prerelease') else 'stable'} toolchain release with {len(release.get('assets', []))} published assets.",
            "published_at": release.get("published_at"),
            "tag": release.get("tag"),
            "prerelease": bool(release.get("prerelease")),
            "url": f"releases/{slug}/index.html",
            "github_url": release.get("url"),
        })
    manifest.write_text(json.dumps(generated_slugs, indent=2) + "\n", encoding="utf-8")
    return entries


def render_release_history(releases: list[dict]) -> None:
    page = ROOT / "releases" / "index.html"
    text = page.read_text(encoding="utf-8")
    start = '<!-- release-history:start -->'
    end = '<!-- release-history:end -->'
    if start in text and end in text:
        text = text.split(start, 1)[0] + text.split(end, 1)[1]
    cards = []
    for release in releases:
        version = release_version(release)
        slug = slug_for_release(release)
        channel = "Prerelease" if release.get("prerelease") else "Stable"
        cards.append(f'''<article class="release-history-item"><div><span>{esc(channel.upper())}</span><h3>Raz {esc(version)}</h3><p><time datetime="{esc(release.get('published_at') or '')}">{esc(display_date(release.get('published_at')))}</time> · {len(release.get('assets', []))} published assets</p></div><div><a class="text-link" href="{slug}/index.html">Release details <span>→</span></a></div></article>''')
    section = f'''{start}<section class="section section-soft"><div class="shell"><div class="section-top compact"><div><p class="kicker">RELEASE HISTORY</p><h2>Permanent records for every published toolchain.</h2></div><p>Each Raz GitHub release receives a stable website page with its original artifacts and integrity metadata.</p></div><div class="release-history">{''.join(cards) if cards else '<div class="empty-state">No published releases are currently recorded.</div>'}</div></div></section>{end}'''
    marker = '<section class="section section-white"><div class="shell"><div class="section-top compact"><div><p class="kicker">QUALIFIED TARGETS</p>'
    if marker in text:
        text = text.replace(marker, section + marker, 1)
    else:
        text = text.replace('</main>', section + '</main>', 1)
    page.write_text(text, encoding="utf-8")


def render_news(entries: list[dict]) -> None:
    pre_base, footer_base = shell_parts()
    news_dir = ROOT / "news"
    news_dir.mkdir(parents=True, exist_ok=True)
    title = "Raz News — Releases and project updates"
    description = "Official Raz release announcements and durable project updates generated from canonical publication sources."
    pre = rewrite_head(pre_base, title=title, description=description, canonical_path="/news/", depth=1)
    if 'application/rss+xml' not in pre:
        pre = pre.replace('</head>', f'  <link rel="alternate" type="application/rss+xml" title="Raz News" href="{SITE_ORIGIN}/news/feed.xml">\n</head>')
    footer = footer_base
    cards = []
    for entry in sorted(entries, key=lambda x: x.get("published_at") or "", reverse=True):
        rel = "../" + entry["url"]
        cards.append(f'''<article class="news-card"><div class="news-meta"><span>{'PRERELEASE' if entry.get('prerelease') else 'RELEASE'}</span><time datetime="{esc(entry.get('published_at') or '')}">{esc(display_date(entry.get('published_at')))}</time></div><h2><a href="{esc(rel)}">{esc(entry['title'])}</a></h2><p>{esc(entry['description'])}</p><div class="news-actions"><a class="text-link" href="{esc(rel)}">Read release details <span>→</span></a><a href="{esc(entry.get('github_url') or RAZ_RELEASES)}">GitHub ↗</a></div></article>''')
    body = f'''<header class="page-hero"><div class="shell narrow"><p class="kicker">RAZ NEWS</p><h1>Releases and project updates.</h1><p class="page-lead">A durable publication surface for official Raz releases and major project announcements. Release entries are generated from the canonical Raz GitHub release feed rather than maintained as a second source of truth.</p><div class="button-row"><a class="button button-primary" href="../releases/index.html">Browse releases</a><a class="button button-secondary" href="feed.xml">RSS feed</a></div></div></header><main id="main" class="after-hero"><section class="section section-white"><div class="shell news-layout"><div class="news-list">{''.join(cards) if cards else '<div class="empty-state">No project updates have been published yet.</div>'}</div><aside class="news-about"><p class="kicker">PUBLICATION MODEL</p><h2>Signal, not a development log.</h2><p>News is reserved for releases, migration guidance, security announcements, and other durable project updates. Day-to-day compiler development stays in GitHub.</p><a class="text-link" href="https://github.com/raz-language">Follow development on GitHub ↗</a></aside></div></section></main>'''
    (news_dir / "index.html").write_text(pre + body + footer, encoding="utf-8")

    # RSS 2.0 feed.
    rss = ET.Element("rss", {"version": "2.0"})
    channel = ET.SubElement(rss, "channel")
    ET.SubElement(channel, "title").text = "Raz News"
    ET.SubElement(channel, "link").text = f"{SITE_ORIGIN}/news/"
    ET.SubElement(channel, "description").text = description
    ET.SubElement(channel, "language").text = "en-us"
    for entry in sorted(entries, key=lambda x: x.get("published_at") or "", reverse=True)[:50]:
        item = ET.SubElement(channel, "item")
        ET.SubElement(item, "title").text = entry["title"]
        url = f"{SITE_ORIGIN}/{entry['url'].replace('index.html', '')}"
        ET.SubElement(item, "link").text = url
        ET.SubElement(item, "guid", {"isPermaLink": "true"}).text = url
        ET.SubElement(item, "description").text = entry["description"]
        dt = parse_dt(entry.get("published_at"))
        ET.SubElement(item, "pubDate").text = format_datetime(dt)
    ET.ElementTree(rss).write(news_dir / "feed.xml", encoding="utf-8", xml_declaration=True)


def inject_home_release(entries: list[dict]) -> None:
    if not entries:
        return
    page = ROOT / "index.html"
    text = page.read_text(encoding="utf-8")
    start = '<!-- latest-release:start -->'
    end = '<!-- latest-release:end -->'
    if start in text and end in text:
        text = text.split(start, 1)[0] + text.split(end, 1)[1]
    entry = sorted(entries, key=lambda x: x.get("published_at") or "", reverse=True)[0]
    strip = f'''{start}<section class="home-release-strip" aria-label="Latest Raz release"><div class="shell"><div><span>LATEST RELEASE</span><b>{esc(entry['title'])}</b><small>{esc(display_date(entry.get('published_at')))}</small></div><div><a href="{esc(entry['url'])}">Release details →</a><a href="news/index.html">Project news →</a></div></div></section>{end}'''
    hero_end = text.find('</section>', text.find('<section class="hero">'))
    if hero_end >= 0:
        hero_end += len('</section>')
        text = text[:hero_end] + strip + text[hero_end:]
    page.write_text(text, encoding="utf-8")


def add_footer_links() -> None:
    for page in ROOT.rglob("*.html"):
        if "_site" in page.relative_to(ROOT).parts:
            continue
        text = page.read_text(encoding="utf-8")
        # Remove prior generated footer links so relative paths can be recomputed deterministically.
        text = re.sub(r'<a data-project-release-link[^>]*>Releases</a><a data-project-news-link[^>]*>News</a>', '', text)
        match = re.search(r'href="(?P<prefix>(?:\.\./)*)status/index\.html">Status</a>', text)
        if not match:
            continue
        prefix = match.group("prefix")
        insert = f'<a data-project-release-link href="{prefix}releases/index.html">Releases</a><a data-project-news-link href="{prefix}news/index.html">News</a>'
        text = text[:match.start()] + insert + text[match.start():]
        page.write_text(text, encoding="utf-8")


def is_api_item(item: dict) -> bool:
    url = str(item.get("url") or "")
    if url.startswith("docs/stdlib/"):
        return bool(re.search(r'/(?:function|struct|enum|trait|type|constant|method)/', url))
    if url.startswith("packages/") and "/docs/module/" in url:
        return True
    # Unified API detail groups can grow large and are symbol-oriented.
    if url.startswith("docs/api/") and url != "docs/api/index.html":
        return True
    return False


def split_search(entries: list[dict]) -> tuple[int, int, str, str]:
    if SEARCH_INDEX.exists():
        items = json.loads(SEARCH_INDEX.read_text(encoding="utf-8"))
    else:
        items = []
        for shard in (SEARCH_CORE, SEARCH_API):
            if shard.exists():
                value = json.loads(shard.read_text(encoding="utf-8"))
                if isinstance(value, list):
                    items.extend(value)
    # Keep release/news discoverable without making them part of the canonical source generator.
    items = [i for i in items if not str(i.get("url") or "").startswith("news/") and not re.match(r'^releases/[^/]+/index\.html$', str(i.get("url") or ""))]
    items.append({"title": "Raz News", "description": "Official Raz releases and durable project updates", "url": "news/index.html", "keywords": "news release announcements updates project"})
    for entry in entries:
        items.append({"title": entry["title"], "description": entry["description"], "url": entry["url"], "keywords": f"release changelog download notes {entry.get('tag') or ''}"})
    # Deduplicate on (url,title) while preserving generator order.
    seen = set(); deduped = []
    for item in items:
        key = (item.get("url"), item.get("title"))
        if key in seen:
            continue
        seen.add(key); deduped.append(item)
    core = [i for i in deduped if not is_api_item(i)]
    api = [i for i in deduped if is_api_item(i)]
    SEARCH_CORE.write_text(json.dumps(core, separators=(",", ":")) + "\n", encoding="utf-8")
    SEARCH_API.write_text(json.dumps(api, separators=(",", ":")) + "\n", encoding="utf-8")
    if SEARCH_INDEX.exists():
        SEARCH_INDEX.unlink()
    core_digest = hashlib.sha256(SEARCH_CORE.read_bytes()).hexdigest()[:12]
    api_digest = hashlib.sha256(SEARCH_API.read_bytes()).hexdigest()[:12]
    return len(core), len(api), core_digest, api_digest


def sharded_search_block(core_digest: str, api_digest: str) -> str:
    return rf'''  // v23 sharded lazy global search
  const dialog=q('[data-search-dialog]'),input=q('[data-site-search]'),results=q('[data-search-results]');
  let lastFocus=null,coreItems=null,apiItems=null,corePromise=null,apiPromise=null;
  const coreVersion='{core_digest}',apiVersion='{api_digest}';
  const searchURL=(name,version)=>`${{window.RAZ_BASE||''}}assets/${{name}}?v=${{version}}`;
  const loadCore=()=>{{if(coreItems)return Promise.resolve(coreItems);if(!corePromise)corePromise=fetch(searchURL('search-core.json',coreVersion),{{credentials:'same-origin'}}).then(r=>{{if(!r.ok)throw new Error(`search core ${{r.status}}`);return r.json();}}).then(data=>{{coreItems=Array.isArray(data)?data:[];return coreItems;}});return corePromise;}};
  const loadAPI=()=>{{if(apiItems)return Promise.resolve(apiItems);if(!apiPromise)apiPromise=fetch(searchURL('search-api.json',apiVersion),{{credentials:'same-origin'}}).then(r=>{{if(!r.ok)throw new Error(`search api ${{r.status}}`);return r.json();}}).then(data=>{{apiItems=Array.isArray(data)?data:[];return apiItems;}});return apiPromise;}};
  const escapeSearch=value=>String(value??'').replace(/[&<>\"]/g,ch=>({{'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}}[ch]));
  const searchKind=url=>url.startsWith('packages/')?'Package':url.startsWith('docs/diagnostics/')?'Diagnostic':url.startsWith('docs/stdlib/')?'Stdlib API':url.startsWith('docs/api/')?'API':url.startsWith('learn/')?'Book':url.startsWith('releases/')?'Release':url.startsWith('news/')?'News':url.startsWith('docs/')?'Docs':'Site';
  const scoreSearch=(item,term,words)=>{{if(!term)return 1;const title=String(item.title||'').toLowerCase(),description=String(item.description||'').toLowerCase(),keywords=String(item.keywords||'').toLowerCase(),url=String(item.url||'').toLowerCase(),hay=`${{title}} ${{description}} ${{keywords}}`;if(!words.every(w=>hay.includes(w)))return -1;let score=words.length*20;if(title===term)score+=240;if(title.startsWith(term))score+=130;if(title.includes(term))score+=70;if(keywords.split(/\s+/).includes(term))score+=55;if(url.includes(term.replace(/::/g,'/')))score+=35;if(/^d\d{{4}}$/i.test(term)&&title===term)score+=220;if(/^(?:raz\s+|razc\s+)/.test(term)&&keywords.includes('cli'))score+=80;if(term.includes('::')&&(title.includes(term)||keywords.includes(term)))score+=95;return score;}};
  const renderSearch=(term='',includeAPI=false)=>{{if(!results)return;const normalized=term.trim().toLowerCase(),words=normalized.split(/\s+/).filter(Boolean);const source=[...(coreItems||[]),...(includeAPI?(apiItems||[]):[])];const ranked=source.map(item=>({{item,score:scoreSearch(item,normalized,words)}})).filter(x=>x.score>=0).sort((a,b)=>b.score-a.score||String(a.item.title).localeCompare(String(b.item.title))).slice(0,12);results.innerHTML=ranked.length?ranked.map(({{item}})=>{{const href=/^(?:https?:)?\/\//.test(item.url)?item.url:`${{window.RAZ_BASE||''}}${{item.url}}`;return `<a class="search-result" href="${{escapeSearch(href)}}"><span class="search-result-top"><b>${{escapeSearch(item.title)}}</b><em>${{escapeSearch(searchKind(String(item.url||'')))}}</em></span><span>${{escapeSearch(item.description||'')}}</span></a>`;}}).join(''):'<div class="search-result search-empty"><b>No results</b><span>Try a package, diagnostic code, command, module, or symbol name.</span></div>';}};
  const runSearch=async()=>{{const term=(input?.value||'').trim();await loadCore();if(term.length>=2){{if(results&&!apiItems)results.setAttribute('aria-busy','true');try{{await loadAPI();}}finally{{results&&results.removeAttribute('aria-busy');}}renderSearch(term,true);}}else renderSearch(term,false);}};
  const openSearch=async()=>{{if(!dialog)return;lastFocus=document.activeElement;dialog.hidden=false;document.body.style.overflow='hidden';if(results)results.innerHTML='<div class="search-result search-loading"><b>Loading search…</b><span>Preparing the Raz documentation index.</span></div>';setTimeout(()=>input&&input.focus(),0);try{{await loadCore();renderSearch(input?.value||'',false);if((input?.value||'').trim().length>=2)await runSearch();}}catch(_){{if(results)results.innerHTML='<div class="search-result search-empty"><b>Search unavailable</b><span>The index could not be loaded. Try again in a moment.</span></div>';}}}};
  const closeSearch=()=>{{if(!dialog)return;dialog.hidden=true;document.body.style.overflow='';lastFocus&&lastFocus.focus&&lastFocus.focus();}};
  const resultLinks=()=>results?qa('a.search-result',results):[];let searchTimer=null;
  qa('[data-search-open]').forEach(b=>b.addEventListener('click',openSearch));qa('[data-search-close]').forEach(b=>b.addEventListener('click',closeSearch));input&&input.addEventListener('input',()=>{{clearTimeout(searchTimer);searchTimer=setTimeout(()=>runSearch().catch(()=>{{}}),90);}});
  document.addEventListener('keydown',e=>{{if((e.ctrlKey||e.metaKey)&&e.key.toLowerCase()==='k'){{e.preventDefault();openSearch();}}if(e.key==='Escape'&&dialog&&!dialog.hidden){{e.preventDefault();closeSearch();}}if(e.key==='/'&&!e.ctrlKey&&!e.metaKey&&!e.altKey&&document.activeElement?.tagName!=='INPUT'&&document.activeElement?.tagName!=='TEXTAREA'){{e.preventDefault();openSearch();}}if(dialog&&!dialog.hidden&&(e.key==='ArrowDown'||e.key==='ArrowUp')){{const links=resultLinks();if(!links.length)return;e.preventDefault();const current=links.indexOf(document.activeElement),delta=e.key==='ArrowDown'?1:-1,next=current<0?(delta>0?0:links.length-1):(current+delta+links.length)%links.length;links[next].focus();}}if(dialog&&!dialog.hidden&&e.key==='Tab'){{const focusable=qa('button:not([disabled]),a[href],input:not([disabled])',dialog).filter(el=>el.offsetParent!==null);if(!focusable.length)return;const first=focusable[0],last=focusable[focusable.length-1];if(e.shiftKey&&document.activeElement===first){{e.preventDefault();last.focus();}}else if(!e.shiftKey&&document.activeElement===last){{e.preventDefault();first.focus();}}}}}});
  // end v23 sharded lazy global search
'''


def rewrite_site_js(core_digest: str, api_digest: str) -> None:
    text = SITE_JS.read_text(encoding="utf-8")
    block = sharded_search_block(core_digest, api_digest)
    old = re.compile(r"  // v22 lazy global search.*?  // end v22 lazy global search\n", re.S)
    prior = re.compile(r"  // v23 sharded lazy global search.*?  // end v23 sharded lazy global search\n", re.S)
    if prior.search(text):
        text = prior.sub(lambda _m: block, text, count=1)
    elif old.search(text):
        text = old.sub(lambda _m: block, text, count=1)
    else:
        raise SystemExit("could not locate lazy global search controller")
    # v22 may leave an outer v23 marker when it temporarily replaces the controller.
    # Collapse any accumulated marker lines so repeated full builds are byte-stable.
    text = re.sub(r'(?:  // v23 sharded lazy global search\n)+', '  // v23 sharded lazy global search\n', text)
    SITE_JS.write_text(text, encoding="utf-8")


def update_api(entries: list[dict]) -> None:
    API.mkdir(parents=True, exist_ok=True)
    payload = {"generated_from": "raz-language/raz GitHub Releases", "entries": entries}
    (API / "news.json").write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    index_path = API / "index.json"
    if index_path.exists():
        index = json.loads(index_path.read_text(encoding="utf-8"))
        index.setdefault("resources", {})["news"] = "./news.json"
        index_path.write_text(json.dumps(index, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def update_sitemap() -> None:
    path = ROOT / "sitemap.xml"
    urls = []
    for page in sorted(ROOT.rglob("*.html")):
        rel = page.relative_to(ROOT)
        if "_site" in rel.parts or rel.as_posix() == "404.html":
            continue
        text = page.read_text(encoding="utf-8", errors="ignore")
        if re.search(r'<meta name="robots" content="[^"]*noindex', text, re.I):
            continue
        route = "/" if rel.as_posix() == "index.html" else "/" + rel.as_posix().removesuffix("index.html")
        urls.append(f"{SITE_ORIGIN}{route}")
    content = '<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n' + ''.join(f'  <url><loc>{html.escape(url)}</loc></url>\n' for url in urls) + '</urlset>\n'
    path.write_text(content, encoding="utf-8")


def add_styles() -> None:
    text = STYLES.read_text(encoding="utf-8")
    marker = "/* release publication + search sharding */"
    if marker in text:
        text = text.split(marker, 1)[0].rstrip() + "\n"
    text += f'''\n{marker}\n.home-release-strip{{border-bottom:1px solid #dfe5ec;background:#fff}}.home-release-strip>.shell{{min-height:66px;display:flex;align-items:center;justify-content:space-between;gap:24px}}.home-release-strip div>div:first-child{{display:flex;align-items:baseline;gap:12px;flex-wrap:wrap}}.home-release-strip span,.release-history-item span,.news-meta span,.release-asset-row>div>span,.release-detail-summary span{{font-size:.64rem;font-weight:900;letter-spacing:.1em;color:#657286}}.home-release-strip b{{font-size:.9rem}}.home-release-strip small{{color:var(--muted)}}.home-release-strip div>div:last-child{{display:flex;gap:18px}}.home-release-strip a{{font-size:.78rem;font-weight:800;text-decoration:none;color:#2458d6}}.release-history{{border-top:1px solid var(--line)}}.release-history-item{{display:flex;align-items:center;justify-content:space-between;gap:30px;padding:22px 0;border-bottom:1px solid var(--line)}}.release-history-item h3{{margin:4px 0 2px;font-size:1.25rem}}.release-history-item p{{margin:0;color:var(--muted);font-size:.82rem}}.release-detail-summary{{display:grid;grid-template-columns:repeat(3,1fr);border:1px solid var(--line)}}.release-detail-summary article{{padding:24px;border-right:1px solid var(--line)}}.release-detail-summary article:last-child{{border-right:0}}.release-detail-summary b{{display:block;margin:12px 0 4px;font-size:1.35rem}}.release-detail-summary p{{margin:0;color:var(--muted);font-size:.82rem}}.release-assets-list{{border-top:1px solid var(--line)}}.release-asset-row{{display:grid;grid-template-columns:minmax(260px,1.4fr) 90px minmax(180px,1fr) auto;gap:18px;align-items:center;padding:17px 0;border-bottom:1px solid var(--line)}}.release-asset-row>div:first-child{{display:flex;flex-direction:column}}.release-asset-row small{{color:var(--muted)}}.release-asset-digest code{{font-size:.68rem;word-break:break-all;color:#57657a}}.release-detail-foot{{display:grid;grid-template-columns:1fr 1fr;gap:60px;align-items:end}}.news-layout{{display:grid;grid-template-columns:minmax(0,760px) minmax(240px,320px);gap:72px;align-items:start}}.news-list{{border-top:1px solid var(--line)}}.news-card{{padding:30px 0;border-bottom:1px solid var(--line)}}.news-meta{{display:flex;align-items:center;gap:12px}}.news-meta time{{font-size:.72rem;color:var(--muted)}}.news-card h2{{margin:9px 0 9px;font-size:1.8rem;letter-spacing:-.03em}}.news-card h2 a{{text-decoration:none}}.news-card h2 a:hover{{color:#2458d6}}.news-card p{{margin:0;color:var(--muted)}}.news-actions{{display:flex;align-items:center;gap:20px;margin-top:17px}}.news-actions>a:last-child{{font-size:.78rem;color:var(--muted);text-decoration:none}}.news-about{{position:sticky;top:104px;border-left:2px solid var(--line);padding-left:22px}}.news-about h2{{font-size:1.45rem;line-height:1.1;margin:0 0 12px}}.news-about>p:not(.kicker){{color:var(--muted);font-size:.9rem}}@media(max-width:900px){{.news-layout,.release-detail-foot{{grid-template-columns:1fr}}.news-about{{position:static}}.release-asset-row{{grid-template-columns:1fr auto}}.release-asset-digest{{grid-column:1/-1}}}}@media(max-width:680px){{.home-release-strip>.shell{{align-items:flex-start;flex-direction:column;padding-top:15px;padding-bottom:15px}}.release-history-item{{align-items:flex-start;flex-direction:column}}.release-detail-summary{{grid-template-columns:1fr}}.release-detail-summary article{{border-right:0;border-bottom:1px solid var(--line)}}.release-detail-summary article:last-child{{border-bottom:0}}.release-asset-row{{grid-template-columns:1fr}}}}\n'''
    STYLES.write_text(text, encoding="utf-8")


def update_llms(entries: list[dict]) -> None:
    path = ROOT / "llms.txt"
    if not path.exists():
        return
    text = path.read_text(encoding="utf-8")
    lines = text.splitlines()
    additions = [
        "- /releases/ — official stable toolchain releases and checksums",
        "- /news/ — official release announcements and durable project updates",
        "- /docs/api/ — unified generated API reference",
        "- /api/v1/ — machine-readable website data",
    ]
    # Keep the file concise and deterministic; insert new primary resources before GitHub.
    lines = [line for line in lines if not any(line.startswith(prefix) for prefix in ("- /releases/", "- /news/", "- /docs/api/", "- /api/v1/"))]
    try:
        idx = next(i for i, line in enumerate(lines) if line.startswith("- https://github.com/raz-language/raz"))
    except StopIteration:
        idx = len(lines)
    lines[idx:idx] = additions
    path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")


def main() -> None:
    releases_path = GEN / "releases.json"
    releases = json.loads(releases_path.read_text(encoding="utf-8")) if releases_path.exists() else []
    releases = sorted(releases, key=lambda x: x.get("published_at") or "", reverse=True)
    entries = render_release_details(releases)
    render_release_history(releases)
    render_news(entries)
    inject_home_release(entries)
    add_footer_links()
    update_api(entries)
    update_llms(entries)
    core_count, api_count, core_digest, api_digest = split_search(entries)
    rewrite_site_js(core_digest, api_digest)
    add_styles()
    update_sitemap()
    print(f"OK: release/news publication: {len(entries)} releases; search shards core={core_count}, api={api_count}")


if __name__ == "__main__":
    main()
