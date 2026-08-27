#!/usr/bin/env python3
"""v26: technical About page, rendered release notes, and structured search metadata."""
from __future__ import annotations

from pathlib import Path
import html
import hashlib
import json
import os
import re

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw"
GEN = ROOT / "data" / "generated"
ASSETS = ROOT / "assets"
SITE_ORIGIN = (os.getenv("RAZ_SITE_URL") or "https://raz-language.github.io").strip().rstrip("/")


def esc(v: object) -> str:
    return html.escape(str(v), quote=True)


def rewrite_head(text: str, *, title: str, description: str, canonical: str, schema: dict) -> str:
    text = re.sub(r'<title>.*?</title>', f'<title>{esc(title)}</title>', text, count=1, flags=re.S)
    text = re.sub(r'<meta name="description" content="[^"]*">', f'<meta name="description" content="{esc(description)}">', text, count=1)
    text = re.sub(r'<meta property="og:title" content="[^"]*">', f'<meta property="og:title" content="{esc(title)}">', text, count=1)
    text = re.sub(r'<meta property="og:description" content="[^"]*">', f'<meta property="og:description" content="{esc(description)}">', text, count=1)
    text = re.sub(r'<meta name="twitter:title" content="[^"]*">', f'<meta name="twitter:title" content="{esc(title)}">', text, count=1)
    text = re.sub(r'<meta name="twitter:description" content="[^"]*">', f'<meta name="twitter:description" content="{esc(description)}">', text, count=1)
    text = re.sub(r'<link rel="canonical" href="[^"]*">', f'<link rel="canonical" href="{esc(canonical)}">', text, count=1)
    text = re.sub(r'<meta property="og:url" content="[^"]*">', f'<meta property="og:url" content="{esc(canonical)}">', text, count=1)
    text = re.sub(r'<script type="application/ld\+json">.*?</script>', '<script type="application/ld+json">' + json.dumps(schema, separators=(",", ":")) + '</script>', text, count=1, flags=re.S)
    return text


def make_about() -> None:
    source = (ROOT / "community" / "index.html").read_text(encoding="utf-8")
    # Use the shared global shell, but About is not a top-level nav item.
    source = source.replace('href="../community/index.html" aria-current="page"', 'href="../community/index.html"')
    opening = re.search(r'<header class="(?:marketing-hero|section-hero|product-masthead|reference-header)[^"]*".*?</header>', source, re.S)
    footer_at = source.find('<footer class="site-footer">')
    if not opening or footer_at < 0:
        raise SystemExit("could not derive About shell from Community")
    pre = source[:opening.start()]
    footer = source[footer_at:]
    title = "Why Raz — Design goals and engineering model"
    description = "Why Raz exists, how its ownership and compiler model differ from C++ and Rust, and what kinds of systems software the language is designed for."
    canonical = f"{SITE_ORIGIN}/about/"
    schema = {
        "@context": "https://schema.org",
        "@type": "AboutPage",
        "name": "Why Raz",
        "url": canonical,
        "description": description,
        "mainEntity": {
            "@type": "SoftwareSourceCode",
            "name": "Raz",
            "programmingLanguage": "Raz",
            "codeRepository": "https://github.com/raz-language/raz",
            "license": "https://www.apache.org/licenses/LICENSE-2.0",
        },
    }
    pre = rewrite_head(pre, title=title, description=description, canonical=canonical, schema=schema)
    body = '''<header class="section-hero"><div class="shell narrow"><p class="kicker">WHY RAZ</p><h1>A systems language built around visible costs.</h1><p class="page-lead">Raz is designed for native software that needs low-level control without making ordinary memory-safety work a permanent manual burden.</p><div class="button-row"><a class="button button-primary" href="../learn/index.html">Learn Raz</a><a class="button button-secondary" href="../docs/index.html">Read the docs</a></div></div></header>
<main id="main" class="after-hero"><section class="section section-white"><div class="shell about-principles"><div class="section-top compact"><div><p class="kicker">THE DESIGN TARGET</p><h2>Performance should be understandable from source.</h2></div><p>Raz keeps ownership, borrowing, allocation, dispatch, backend choice, unsafe boundaries, and package interfaces explicit enough to reason about while still giving the compiler room to prove ordinary safety properties.</p></div><div class="about-principle-grid"><article><span>01</span><h3>Native first</h3><p>Raz targets native executables through Forge or LLVM, with WebAssembly and RXE available when portability or bytecode execution is the better fit.</p></article><article><span>02</span><h3>Safe by default</h3><p>Ownership, moves, borrowing, bounds-aware views, and deterministic destruction make memory safety the normal language path instead of an external discipline.</p></article><article><span>03</span><h3>No mandatory tracing GC</h3><p>The language does not require a tracing garbage collector or a hidden runtime ownership model to manage ordinary values.</p></article><article><span>04</span><h3>One semantic pipeline</h3><p>Typed HIR and verified MIR settle program meaning before Forge, LLVM, WebAssembly, or RXE emission.</p></article></div></div></section>
<section class="section section-soft"><div class="shell"><div class="section-top compact"><div><p class="kicker">POSITIONING</p><h2>Where Raz sits.</h2></div><p>Raz is not trying to hide systems programming. It is trying to make the dangerous and expensive parts explicit while making the routine parts easier to prove and tool.</p></div><div class="about-compare-grid"><article><h3>Compared with C and C++</h3><p>Raz adds ownership and borrow analysis, deterministic package/tooling conventions, stable diagnostics, and a compiler-owned project workflow while retaining explicit native costs and controlled unsafe/FFI boundaries.</p></article><article><h3>Compared with Rust</h3><p>Raz shares the goal of memory safety without a tracing GC, but uses its own type-first syntax, compiler architecture, package/tooling model, Forge backend, and language semantics. It should be evaluated as its own language rather than as Rust syntax with different spelling.</p></article><article><h3>Compared with managed languages</h3><p>Raz prioritizes deterministic destruction, native layouts, explicit allocation behavior, direct ABI interoperability, and backend-visible compilation over a VM or mandatory managed runtime.</p></article></div></div></section>
<section class="section section-white"><div class="shell two-col"><div><p class="kicker">WHO IT IS FOR</p><h2>Software where behavior and resource cost matter.</h2><p class="section-copy">Compilers, runtimes, databases, storage engines, network services, developer tools, native libraries, and other software where latency, memory use, ABI behavior, or predictable cleanup are part of correctness.</p></div><div class="fact-list"><div><b>Language</b><span>Statically typed systems programming</span></div><div><b>Memory model</b><span>Ownership + borrowing + deterministic destruction</span></div><div><b>Native backends</b><span>Forge and LLVM</span></div><div><b>Portable outputs</b><span>WebAssembly and RXE</span></div><div><b>License</b><span>Apache-2.0</span></div></div></div></section>
<section class="section section-dark"><div class="shell two-col"><div><p class="kicker kicker-bright">WHEN NOT TO USE RAZ</p><h2>A systems language is not automatically the right tool.</h2></div><div><p class="section-copy">If a project benefits more from a large mature managed-runtime ecosystem, needs a platform Raz does not yet qualify, or depends on libraries that do not have a practical C ABI/package path, another language may currently be the better engineering choice.</p><p class="section-copy">The project status page deliberately distinguishes stable language guarantees, qualified targets, published binaries, and experimental backend work.</p><a class="text-link text-link-light" href="../status/index.html">Check current support →</a></div></div></section>
<section class="final-cta"><div class="shell"><p class="kicker">RAZ 1.0</p><h2>See the language in detail.</h2><div class="hero-actions"><a class="button button-primary" href="../learn/index.html">Start learning</a><a class="button button-secondary" href="../docs/language/index.html">Language guide</a><a class="text-link" href="https://github.com/raz-language/raz">Compiler source ↗</a></div></div></section></main>'''
    target = ROOT / "about" / "index.html"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(pre + body + footer, encoding="utf-8")


def inline_release(text: str) -> str:
    text = esc(text)
    text = re.sub(r'`([^`]+)`', r'<code>\1</code>', text)
    text = re.sub(r'\*\*([^*]+)\*\*', r'<strong>\1</strong>', text)
    return text


def release_markdown(markdown: str) -> str:
    out: list[str] = []
    in_list = False
    paragraph: list[str] = []
    def flush_p():
        nonlocal paragraph
        if paragraph:
            out.append('<p>' + inline_release(' '.join(x.strip() for x in paragraph)) + '</p>')
            paragraph = []
    def close_list():
        nonlocal in_list
        if in_list:
            out.append('</ul>'); in_list = False
    for line in markdown.splitlines():
        if not line.strip():
            flush_p(); close_list(); continue
        h = re.match(r'^(#{2,4})\s+(.+)$', line)
        if h:
            flush_p(); close_list()
            level = min(4, len(h.group(1)) + 1)
            label = h.group(2).strip()
            ident = re.sub(r'[^a-z0-9]+', '-', label.lower()).strip('-') or 'section'
            out.append(f'<h{level} id="release-{esc(ident)}">{inline_release(label)}</h{level}>')
            continue
        m = re.match(r'^[-*]\s+(.+)$', line)
        if m:
            flush_p()
            if not in_list:
                out.append('<ul>'); in_list = True
            out.append('<li>' + inline_release(m.group(1)) + '</li>')
            continue
        close_list(); paragraph.append(line)
    flush_p(); close_list()
    return ''.join(out)


def render_release_notes() -> int:
    releases_path = GEN / "releases.json"
    if not releases_path.exists():
        return 0
    releases = json.loads(releases_path.read_text(encoding="utf-8"))
    state_path = RAW / "release-notes-state.json"
    state = json.loads(state_path.read_text(encoding="utf-8")) if state_path.exists() else {}
    changed = 0
    for release in releases:
        tag = str(release.get('tag') or '').strip()
        if not tag:
            continue
        slug = re.sub(r'[^A-Za-z0-9._-]+', '-', tag).strip('-').lower() or 'release'
        notes_path = RAW / 'release-notes' / f'{slug}.md'
        page = ROOT / 'releases' / slug / 'index.html'
        if not page.exists():
            continue
        text = page.read_text(encoding='utf-8')
        text = re.sub(r'<!-- release-notes-rendered:start -->.*?<!-- release-notes-rendered:end -->', '', text, flags=re.S)
        if not notes_path.exists():
            page.write_text(text, encoding='utf-8'); continue
        notes_html = release_markdown(notes_path.read_text(encoding='utf-8'))
        info = state.get(tag, {})
        source = info.get('source')
        source_kind = info.get('source_kind', 'cached-release-notes')
        if source_kind == 'tag-changelog-fallback':
            source_label = 'Canonical tagged changelog section'
        elif source_kind == 'release-asset':
            source_label = 'Published RELEASE-NOTES.md asset'
        else:
            source_label = 'Cached canonical release notes'
        source_link = f'<a href="{esc(source)}">{esc(source_label)} ↗</a>' if source else esc(source_label)
        section = f'''<!-- release-notes-rendered:start --><section class="section section-white release-notes-section"><div class="shell release-notes-layout"><aside><p class="kicker">WHAT CHANGED</p><h2>Release notes.</h2><p>Rendered from canonical Raz release-era source rather than rewritten website copy.</p><small>{source_link}</small></aside><article class="release-notes-prose">{notes_html}</article></div></section><!-- release-notes-rendered:end -->'''
        marker = '<section class="section section-soft"><div class="shell"><div class="section-top compact"><div><p class="kicker">RELEASE ASSETS</p>'
        if marker in text:
            text = text.replace(marker, section + marker, 1)
        else:
            text = text.replace('</main>', section + '</main>', 1)
        page.write_text(text, encoding='utf-8')
        changed += 1
    return changed


def infer_search_metadata(item: dict) -> dict:
    item = dict(item)
    url = str(item.get('url') or '')
    title = str(item.get('title') or '')
    desc = str(item.get('description') or '')
    kind = 'page'; namespace = ''; name = title; qname = title
    if re.fullmatch(r'D\d{4}', title): kind = 'diagnostic'; name = title; qname = title
    elif url.startswith('packages/'):
        parts = url.split('/')
        kind = 'package-api' if '/docs/' in url else 'package'
        namespace = parts[1] if len(parts) > 1 else ''
    elif url.startswith('docs/stdlib/'):
        path_parts = url.split('/')
        kind_match = re.search(r'/(function|struct|enum|trait|type|constant|method)/', url)
        kind = kind_match.group(1) if kind_match else 'stdlib-module'
        if ' · ' in title:
            name, namespace = [x.strip() for x in title.split(' · ', 1)]
            qname = f'{namespace}::{name}' if namespace else name
    elif url.startswith('docs/api/'): kind = 'api'
    elif url.startswith('learn/book/'): kind = 'book'
    elif url.startswith('releases/'): kind = 'release'
    elif url.startswith('news/'): kind = 'news'
    elif url.startswith('docs/'): kind = 'docs'
    if title.startswith('raz ') or desc.startswith('raz '): kind = 'cli'
    item.update({'kind': kind, 'name': name, 'namespace': namespace, 'qualified_name': qname})
    return item


def enrich_search() -> tuple[int, int]:
    counts = []
    for filename in ('search-core.json', 'search-api.json'):
        path = ASSETS / filename
        items = json.loads(path.read_text(encoding='utf-8'))
        if filename == 'search-core.json' and not any(i.get('url') == 'about/index.html' for i in items):
            items.append({'title':'Why Raz','description':'Design goals, ownership model, compiler architecture, and where Raz fits among systems languages.','url':'about/index.html','keywords':'about why raz design goals c++ rust ownership borrow forge systems language'})
        items = [infer_search_metadata(i) for i in items]
        path.write_text(json.dumps(items, separators=(',', ':')) + '\n', encoding='utf-8')
        counts.append(len(items))
    return counts[0], counts[1]



def improve_search_controller() -> None:
    path = ASSETS / 'site.js'
    text = path.read_text(encoding='utf-8')
    core_digest = hashlib.sha256((ASSETS / 'search-core.json').read_bytes()).hexdigest()[:12]
    api_digest = hashlib.sha256((ASSETS / 'search-api.json').read_bytes()).hexdigest()[:12]
    text = re.sub(r"const coreVersion='[0-9a-f]{12}',apiVersion='[0-9a-f]{12}';", f"const coreVersion='{core_digest}',apiVersion='{api_digest}';", text, count=1)
    old = "const scoreSearch=(item,term,words)=>{if(!term)return 1;const title=String(item.title||'').toLowerCase(),description=String(item.description||'').toLowerCase(),keywords=String(item.keywords||'').toLowerCase(),url=String(item.url||'').toLowerCase(),hay=`${title} ${description} ${keywords}`;if(!words.every(w=>hay.includes(w)))return -1;let score=words.length*20;if(title===term)score+=240;if(title.startsWith(term))score+=130;if(title.includes(term))score+=70;if(keywords.split(/\\s+/).includes(term))score+=55;if(url.includes(term.replace(/::/g,'/')))score+=35;if(/^d\\d{4}$/i.test(term)&&title===term)score+=220;if(/^(?:raz\\s+|razc\\s+)/.test(term)&&keywords.includes('cli'))score+=80;if(term.includes('::')&&(title.includes(term)||keywords.includes(term)))score+=95;return score;};"
    new = "const scoreSearch=(item,term,words)=>{if(!term)return 1;const title=String(item.title||'').toLowerCase(),name=String(item.name||'').toLowerCase(),qualified=String(item.qualified_name||'').toLowerCase(),namespace=String(item.namespace||'').toLowerCase(),kind=String(item.kind||''),description=String(item.description||'').toLowerCase(),keywords=String(item.keywords||'').toLowerCase(),url=String(item.url||'').toLowerCase(),hay=`${title} ${name} ${qualified} ${namespace} ${description} ${keywords}`;if(!words.every(w=>hay.includes(w)))return -1;let score=words.length*20;if(qualified===term)score+=360;if(name===term)score+=280;if(title===term)score+=240;if(qualified.startsWith(term))score+=170;if(title.startsWith(term))score+=130;if(title.includes(term)||qualified.includes(term))score+=70;if(keywords.split(/\\s+/).includes(term))score+=55;if(url.includes(term.replace(/::/g,'/')))score+=35;if(/^d\\d{4}$/i.test(term)&&name===term)score+=220;if(/^(?:raz\\s+|razc\\s+)/.test(term)&&kind==='cli')score+=110;if(term.includes('::')&&qualified.includes(term))score+=140;return score;};"
    if old in text:
        text = text.replace(old, new, 1)
    elif 'qualified_name||' not in text:
        raise SystemExit('could not locate v23 scoreSearch controller')
    path.write_text(text, encoding='utf-8')

def add_footer_about() -> int:
    changed = 0
    for page in ROOT.rglob('*.html'):
        rel = page.relative_to(ROOT)
        if '_site' in rel.parts:
            continue
        text = page.read_text(encoding='utf-8')
        text = re.sub(r'<a data-project-about-link[^>]*>About</a>', '', text)
        m = re.search(r'<a data-project-news-link href="(?P<prefix>(?:\.\./)*)news/index\.html">News</a>', text)
        if not m:
            continue
        prefix = m.group('prefix')
        insert = m.group(0) + f'<a data-project-about-link href="{prefix}about/index.html">About</a>'
        text = text[:m.start()] + insert + text[m.end():]
        page.write_text(text, encoding='utf-8'); changed += 1
    return changed


def add_styles() -> None:
    path = ASSETS / 'styles.css'
    text = path.read_text(encoding='utf-8')
    marker = '/* v26 about + release notes */'
    if marker in text:
        text = text.split(marker,1)[0].rstrip() + '\n'
    text += '''\n/* v26 about + release notes */\n.about-principle-grid,.about-compare-grid{display:grid;grid-template-columns:repeat(4,1fr);gap:1px;background:var(--line);border:1px solid var(--line)}.about-principle-grid article,.about-compare-grid article{background:#fff;padding:26px}.about-principle-grid article>span{display:block;font-family:var(--mono);font-size:.68rem;font-weight:900;color:#4f64d8;margin-bottom:28px}.about-principle-grid h3,.about-compare-grid h3{margin:0 0 10px;font-size:1.05rem}.about-principle-grid p,.about-compare-grid p{margin:0;color:var(--muted);font-size:.84rem;line-height:1.65}.about-compare-grid{grid-template-columns:repeat(3,1fr)}.release-notes-layout{display:grid;grid-template-columns:minmax(220px,.36fr) minmax(0,1fr);gap:64px;align-items:start}.release-notes-layout aside{position:sticky;top:98px}.release-notes-layout aside h2{margin:8px 0 12px;font-size:2rem}.release-notes-layout aside p{color:var(--muted);font-size:.84rem;line-height:1.6}.release-notes-layout aside small{display:block;margin-top:16px}.release-notes-layout aside a{font-weight:800;text-decoration:none}.release-notes-prose{max-width:850px}.release-notes-prose h3{margin:30px 0 10px;font-size:1.2rem}.release-notes-prose h3:first-child{margin-top:0}.release-notes-prose ul{margin:0 0 18px;padding-left:20px}.release-notes-prose li{margin:7px 0;color:#3e4a5d;line-height:1.65}.release-notes-prose code{font-size:.85em}@media(max-width:900px){.about-principle-grid{grid-template-columns:repeat(2,1fr)}.about-compare-grid{grid-template-columns:1fr}.release-notes-layout{grid-template-columns:1fr;gap:28px}.release-notes-layout aside{position:static}}@media(max-width:560px){.about-principle-grid{grid-template-columns:1fr}}\n'''
    path.write_text(text, encoding='utf-8')


def update_sitemap() -> None:
    path = ROOT / 'sitemap.xml'
    if not path.exists(): return
    text = path.read_text(encoding='utf-8')
    url = f'{SITE_ORIGIN}/about/'
    if f'<loc>{url}</loc>' not in text:
        text = text.replace('</urlset>', f'  <url><loc>{url}</loc></url>\n</urlset>')
        path.write_text(text, encoding='utf-8')


def main() -> None:
    make_about()
    notes = render_release_notes()
    footer = add_footer_about()
    core, api = enrich_search()
    improve_search_controller()
    add_styles()
    update_sitemap()
    print(f'v26: about page; {notes} release note page(s); footer updated on {footer} pages; search {core} core/{api} API entries')

if __name__ == '__main__':
    main()
