#!/usr/bin/env python3
"""Production polish: lazy search, accessibility, canonical UX, and deploy assets."""
from __future__ import annotations

import hashlib
import html
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ASSETS = ROOT / "assets"
SEARCH_JS = ASSETS / "search-index.js"
SEARCH_JSON = ASSETS / "search-index.json"
SITE_JS = ASSETS / "site.js"
STYLES = ASSETS / "styles.css"


def esc(value: object) -> str:
    return html.escape(str(value), quote=True)


def convert_search_index() -> tuple[int, str]:
    if not SEARCH_JS.exists():
        if not SEARCH_JSON.exists():
            raise SystemExit("search index is missing")
        items = json.loads(SEARCH_JSON.read_text(encoding="utf-8"))
    else:
        raw = SEARCH_JS.read_text(encoding="utf-8")
        match = re.match(r"window\.RAZ_SEARCH=(.*);\s*$", raw, re.S)
        if not match:
            raise SystemExit("generated search-index.js has an unexpected format")
        items = json.loads(match.group(1))
    SEARCH_JSON.write_text(json.dumps(items, separators=(",", ":"), ensure_ascii=False) + "\n", encoding="utf-8")
    digest = hashlib.sha256(SEARCH_JSON.read_bytes()).hexdigest()[:12]
    if SEARCH_JS.exists():
        SEARCH_JS.unlink()
    return len(items), digest


def lazy_search_block(search_digest: str) -> str:
    return rf'''  // v22 lazy global search
  const dialog=q('[data-search-dialog]'), input=q('[data-site-search]'), results=q('[data-search-results]');
  let lastFocus=null,items=[],searchReady=false,searchPromise=null;
  const searchVersion='{search_digest}';
  const searchURL=()=>`${{window.RAZ_BASE||''}}assets/search-index.json?v=${{searchVersion}}`;
  const escapeSearch=value=>String(value??'').replace(/[&<>\"]/g,ch=>({{'&':'&amp;','<':'&lt;','>':'&gt;','\"':'&quot;'}}[ch]));
  const searchKind=url=>url.startsWith('packages/')?'Package':url.startsWith('docs/diagnostics/')?'Diagnostic':url.startsWith('docs/stdlib/')?'Standard library':url.startsWith('docs/api/')?'API reference':url.startsWith('learn/book/')?'Book':url.startsWith('install/')?'Install':url.startsWith('releases/')?'Release':url.startsWith('tools/')?'Tooling':'Documentation';
  const loadSearch=()=>{{
    if(searchReady)return Promise.resolve(items);
    if(searchPromise)return searchPromise;
    searchPromise=fetch(searchURL(),{{cache:'force-cache'}}).then(response=>{{if(!response.ok)throw new Error(`search index ${{response.status}}`);return response.json();}}).then(value=>{{items=Array.isArray(value)?value:[];searchReady=true;return items;}}).catch(error=>{{searchPromise=null;throw error;}});
    return searchPromise;
  }};
  const scoreSearch=(item,term,words)=>{{
    const title=String(item.title||'').toLowerCase(),description=String(item.description||'').toLowerCase(),keywords=String(item.keywords||'').toLowerCase(),url=String(item.url||'').toLowerCase();
    if(!words.length)return 1;
    let score=0;
    for(const word of words){{
      let found=false;
      if(title===word){{score+=120;found=true;}}
      else if(title.startsWith(word)){{score+=75;found=true;}}
      else if(title.includes(word)){{score+=45;found=true;}}
      if(keywords.split(/\s+/).includes(word)){{score+=28;found=true;}}
      else if(keywords.includes(word)){{score+=16;found=true;}}
      if(description.includes(word)){{score+=9;found=true;}}
      if(url.includes(word)){{score+=6;found=true;}}
      if(!found)return -1;
    }}
    if(title===term)score+=180;
    if(title.startsWith(term))score+=80;
    if(/^d\d{{4}}$/i.test(term)&&title.includes(term))score+=240;
    if(url.startsWith('packages/')&&title===term)score+=120;
    if(/\b(?:raz|razc)\s+/.test(term)&&keywords.includes('cli'))score+=80;
    return score;
  }};
  const renderSearch=(term='')=>{{
    if(!results)return;
    const normalized=term.trim().toLowerCase(),words=normalized.split(/\s+/).filter(Boolean);
    const ranked=items.map(item=>({{item,score:scoreSearch(item,normalized,words)}})).filter(x=>x.score>=0).sort((a,b)=>b.score-a.score||String(a.item.title).localeCompare(String(b.item.title))).slice(0,10);
    results.innerHTML=ranked.length?ranked.map(({{item}})=>{{const href=/^(?:https?:)?\/\//.test(item.url)?item.url:`${{window.RAZ_BASE||''}}${{item.url}}`;const kind=searchKind(String(item.url||''));return `<a class="search-result" href="${{escapeSearch(href)}}"><span class="search-result-top"><b>${{escapeSearch(item.title)}}</b><em>${{escapeSearch(kind)}}</em></span><span>${{escapeSearch(item.description||'')}}</span></a>`;}}).join(''):'<div class="search-result search-empty"><b>No results</b><span>Try a broader search or a package, diagnostic code, command, module, or symbol name.</span></div>';
  }};
  const openSearch=async()=>{{
    if(!dialog)return;lastFocus=document.activeElement;dialog.hidden=false;document.body.style.overflow='hidden';
    if(results)results.innerHTML='<div class="search-result search-loading"><b>Loading search…</b><span>Preparing the Raz documentation index.</span></div>';
    setTimeout(()=>input&&input.focus(),0);
    try{{await loadSearch();renderSearch(input?.value||'');}}catch(_){{if(results)results.innerHTML='<div class="search-result search-empty"><b>Search unavailable</b><span>The index could not be loaded. Try again in a moment.</span></div>';}}
  }};
  const closeSearch=()=>{{if(!dialog)return;dialog.hidden=true;document.body.style.overflow='';lastFocus&&lastFocus.focus&&lastFocus.focus();}};
  const resultLinks=()=>results?qa('a.search-result',results):[];
  qa('[data-search-open]').forEach(b=>b.addEventListener('click',openSearch));qa('[data-search-close]').forEach(b=>b.addEventListener('click',closeSearch));
  input&&input.addEventListener('input',async()=>{{try{{await loadSearch();renderSearch(input.value);}}catch(_){{}}}});
  document.addEventListener('keydown',e=>{{
    if((e.ctrlKey||e.metaKey)&&e.key.toLowerCase()==='k'){{e.preventDefault();openSearch();}}
    if(e.key==='Escape'&&dialog&&!dialog.hidden){{e.preventDefault();closeSearch();}}
    if(e.key==='/'&&!e.ctrlKey&&!e.metaKey&&!e.altKey&&document.activeElement?.tagName!=='INPUT'&&document.activeElement?.tagName!=='TEXTAREA'){{e.preventDefault();openSearch();}}
    if(dialog&&!dialog.hidden&&(e.key==='ArrowDown'||e.key==='ArrowUp')){{const links=resultLinks();if(!links.length)return;e.preventDefault();const current=links.indexOf(document.activeElement);const delta=e.key==='ArrowDown'?1:-1;const next=current<0?(delta>0?0:links.length-1):(current+delta+links.length)%links.length;links[next].focus();}}
    if(dialog&&!dialog.hidden&&e.key==='Tab'){{const focusable=qa('button:not([disabled]),a[href],input:not([disabled])',dialog).filter(el=>el.offsetParent!==null);if(!focusable.length)return;const first=focusable[0],last=focusable[focusable.length-1];if(e.shiftKey&&document.activeElement===first){{e.preventDefault();last.focus();}}else if(!e.shiftKey&&document.activeElement===last){{e.preventDefault();first.focus();}}}}
  }});
  // end v22 lazy global search
'''


def rewrite_site_js(search_digest: str) -> None:
    text = SITE_JS.read_text(encoding="utf-8")
    block = lazy_search_block(search_digest)
    marker_re = re.compile(r"  // v22 lazy global search.*?  // end v22 lazy global search\n", re.S)
    if marker_re.search(text):
        text = marker_re.sub(lambda _m: block, text, count=1)
    else:
        old_re = re.compile(r"  const dialog=q\('\[data-search-dialog\]'\).*?(?=\n  const platformButtons=)", re.S)
        if not old_re.search(text):
            raise SystemExit("could not locate the global search controller in site.js")
        text = old_re.sub(lambda _m: block.rstrip("\n"), text, count=1)
    SITE_JS.write_text(text, encoding="utf-8")


def polish_html() -> tuple[int, int, int]:
    changed = buttons = captions = 0
    search_script_re = re.compile(r"\s*<script src=\"(?:\.\./)*assets/search-index\.js(?:\?v=[^\"]*)?\"></script>")
    button_re = re.compile(r"<button(?![^>]*\btype=)([^>]*)>", re.I)
    table_re = re.compile(r"(<table\b[^>]*>)(?!\s*<caption\b)", re.I)
    for page in ROOT.rglob("*.html"):
        if "_site" in page.relative_to(ROOT).parts:
            continue
        text = page.read_text(encoding="utf-8")
        original = text
        text = search_script_re.sub("", text)
        text = text.replace("raz-mark.png", "raz-mark-128.png")
        text, button_count = button_re.subn(r'<button type="button"\1>', text)
        buttons += button_count
        text, caption_count = table_re.subn(r'\1<caption class="sr-only">Reference data</caption>', text)
        captions += caption_count
        for attr in ("data-package-count", "data-package-api-count", "data-diagnostic-count", "data-stdlib-count", "data-stdlib-item-count"):
            text = re.sub(rf'({attr})(?![^>]*\baria-live=)', rf'\1 role="status" aria-live="polite"', text)
        text = re.sub(r'(class="search-results" data-search-results)(?![^>]*\baria-live=)', r'\1 role="status" aria-live="polite"', text)
        text = re.sub(r'(<input type="search" data-site-search)(?![^>]*\baria-label=)', r'\1 aria-label="Search Raz website"', text)
        if text != original:
            page.write_text(text, encoding="utf-8")
            changed += 1
    return changed, buttons, captions


def improve_404() -> None:
    page = ROOT / "404.html"
    text = page.read_text(encoding="utf-8")
    start = text.find('<body class="error-page">')
    end = text.rfind('</body>')
    if start < 0 or end < 0:
        return
    body = '''<body class="error-page"><a class="skip-link" href="#main">Skip to content</a><main id="main" class="error-main"><div class="error-wrap"><a class="error-brand" href="index.html"><img src="assets/raz-mark-128.png" alt="" width="40" height="40"><span>Raz</span></a><p class="error-code">404</p><h1>That page isn't here.</h1><p>The link may be old, or the page may have moved. Search the Raz site or jump directly to one of the main references.</p><div class="button-row"><button type="button" class="button button-primary" data-search-open>Search Raz</button><a class="button button-secondary" href="index.html">Go home</a></div><nav class="error-destinations" aria-label="Popular destinations"><a href="learn/book/index.html"><b>The Raz Book</b><span>Learn the language →</span></a><a href="docs/api/index.html"><b>API reference</b><span>Browse public APIs →</span></a><a href="packages/index.html"><b>Packages</b><span>Official package ecosystem →</span></a><a href="install/index.html"><b>Install Raz</b><span>Windows and Linux →</span></a><a href="docs/diagnostics/index.html"><b>Diagnostics</b><span>Look up compiler codes →</span></a><a href="docs/compiler/index.html"><b>Compiler</b><span>Understand the toolchain →</span></a></nav></div></main><div class="search-dialog" data-search-dialog hidden><div class="search-backdrop" data-search-close></div><section class="search-panel" role="dialog" aria-modal="true" aria-label="Search Raz website"><div class="search-box"><span aria-hidden="true">⌕</span><input type="search" data-site-search autocomplete="off" spellcheck="false" placeholder="Search Raz…" aria-label="Search Raz website"><kbd>Esc</kbd></div><div class="search-results" data-search-results role="status" aria-live="polite"></div><p class="search-hint">Search documentation, installation, packages, tools, diagnostics, and API symbols.</p></section></div></body>'''
    page.write_text(text[:start] + body + text[end + len('</body>'):], encoding="utf-8")


def add_styles() -> None:
    text = STYLES.read_text(encoding="utf-8")
    marker = "/* production search + accessibility polish */"
    if marker in text:
        text = text.split(marker, 1)[0].rstrip() + "\n"
    text += f'''\n{marker}\n.search-result-top{{display:flex;align-items:baseline;justify-content:space-between;gap:14px}}.search-result-top em{{flex:0 0 auto;font-style:normal;font-size:.61rem;font-weight:900;letter-spacing:.08em;text-transform:uppercase;color:#61718a}}.search-loading{{opacity:.72}}.search-empty{{cursor:default}}.error-destinations{{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:1px;margin-top:38px;border:1px solid var(--line);background:var(--line);border-radius:9px;overflow:hidden}}.error-destinations a{{display:flex;justify-content:space-between;gap:18px;padding:18px 20px;background:#fff;text-decoration:none}}.error-destinations a:hover{{background:var(--soft-blue)}}.error-destinations b{{font-size:.9rem}}.error-destinations span{{color:var(--muted);font-size:.74rem}}@media(max-width:680px){{.error-destinations{{grid-template-columns:1fr}}.search-result-top{{align-items:flex-start;flex-direction:column;gap:3px}}}}\n'''
    STYLES.write_text(text, encoding="utf-8")


def write_manifest() -> None:
    manifest = {
        "name": "Raz Programming Language",
        "short_name": "Raz",
        "start_url": "./index.html",
        "display": "standalone",
        "background_color": "#0b1018",
        "theme_color": "#0b1018",
        "icons": [
            {"src": "assets/raz-icon-192.png", "sizes": "192x192", "type": "image/png"},
            {"src": "assets/raz-icon-512.png", "sizes": "512x512", "type": "image/png"},
        ],
    }
    (ROOT / "site.webmanifest").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")


def main() -> None:
    items, digest = convert_search_index()
    rewrite_site_js(digest)
    changed, buttons, captions = polish_html()
    improve_404()
    add_styles()
    write_manifest()
    print(f"OK: production polish: lazy search {items} entries, {changed} pages, {buttons} button types, {captions} table captions")


if __name__ == "__main__":
    main()
