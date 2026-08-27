#!/usr/bin/env python3
"""v29: performance evidence surface, ecosystem onboarding, and package sorting."""
from __future__ import annotations
from pathlib import Path
import html, json, os, re, hashlib

ROOT=Path(__file__).resolve().parents[1]
ASSETS=ROOT/'assets'; GEN=ROOT/'data/generated'; API=ROOT/'api/v1'
SITE_ORIGIN=(os.getenv('RAZ_SITE_URL') or 'https://raz-language.github.io').strip().rstrip('/')

def esc(v): return html.escape(str(v),quote=True)

def rewrite_head(text,title,description,canonical,schema):
    text=re.sub(r'<title>.*?</title>',f'<title>{esc(title)}</title>',text,count=1,flags=re.S)
    for pat,val in [
        (r'<meta name="description" content="[^"]*">',f'<meta name="description" content="{esc(description)}">'),
        (r'<meta property="og:title" content="[^"]*">',f'<meta property="og:title" content="{esc(title)}">'),
        (r'<meta property="og:description" content="[^"]*">',f'<meta property="og:description" content="{esc(description)}">'),
        (r'<meta name="twitter:title" content="[^"]*">',f'<meta name="twitter:title" content="{esc(title)}">'),
        (r'<meta name="twitter:description" content="[^"]*">',f'<meta name="twitter:description" content="{esc(description)}">'),
        (r'<link rel="canonical" href="[^"]*">',f'<link rel="canonical" href="{esc(canonical)}">'),
        (r'<meta property="og:url" content="[^"]*">',f'<meta property="og:url" content="{esc(canonical)}">')]:
        text=re.sub(pat,val,text,count=1)
    text=re.sub(r'<script type="application/ld\+json" data-v24-schema="page">.*?</script>',
                '<script type="application/ld+json" data-v24-schema="page">'+json.dumps(schema,separators=(',',':'))+'</script>',text,count=1,flags=re.S)
    return text

def shell(source_path:Path):
    source=source_path.read_text(encoding='utf-8')
    opening=re.search(r'<header class="(?:marketing-hero|section-hero|product-masthead|reference-header)[^"]*".*?</header>',source,re.S)
    footer_at=source.find('<footer class="site-footer">')
    if not opening or footer_at<0: raise SystemExit(f'cannot derive shell from {source_path}')
    return source[:opening.start()],source[footer_at:]

def make_performance():
    pre,footer=shell(ROOT/'about/index.html')
    title='Raz Performance — Evidence, methodology and cost model'
    desc='Raz performance methodology, reproducibility requirements, and the evidence contract for future published benchmarks.'
    canonical=f'{SITE_ORIGIN}/performance/'
    schema={'@context':'https://schema.org','@type':'TechArticle','headline':'Raz performance and benchmarking','description':desc,'url':canonical,'about':{'@type':'SoftwareSourceCode','name':'Raz','programmingLanguage':'Raz'}}
    pre=rewrite_head(pre,title,desc,canonical,schema)
    body='''<header class="section-hero"><div class="shell narrow"><p class="kicker">PERFORMANCE</p><h1>Measure first. Publish evidence second.</h1><p class="page-lead">Raz is designed for predictable native performance, but this website does not publish benchmark numbers until the project has a reproducible canonical result corpus.</p><div class="button-row"><a class="button button-primary" href="https://github.com/raz-language/raz/blob/main/docs/PERFORMANCE.md">Performance model ↗</a><a class="button button-secondary" href="https://github.com/raz-language/raz/blob/main/docs/STANDARD-LIBRARY-PERFORMANCE.md">Library performance ↗</a></div></div></header>
<main id="main" class="after-hero"><section class="section section-white"><div class="shell"><div class="section-top compact"><div><p class="kicker">EVIDENCE CONTRACT</p><h2>No unverifiable speed claims.</h2></div><p>Every future benchmark published here must identify source revision, compiler/backend, optimization profile, hardware, operating system, benchmark source, warmup policy, sample count, and raw result data.</p></div><div class="about-principle-grid"><article><span>01</span><h3>Reproducible</h3><p>Results must be runnable from public source with pinned inputs and commands.</p></article><article><span>02</span><h3>Comparable</h3><p>Cross-language comparisons must solve the same problem and disclose compiler flags and runtime assumptions.</p></article><article><span>03</span><h3>Representative</h3><p>Microbenchmarks may explain one mechanism; broader workloads are required before making general performance claims.</p></article><article><span>04</span><h3>Raw data preserved</h3><p>Charts are summaries. Machine-readable measurements and environment metadata remain the authoritative record.</p></article></div></div></section>
<section class="section section-soft"><div class="shell"><div class="section-top compact"><div><p class="kicker">PLANNED SUITE</p><h2>What the benchmark corpus should cover.</h2></div><p>The site has the publication surface now; measurements remain intentionally unpublished until a canonical harness produces them.</p></div><div class="use-grid"><div><h3>Runtime throughput</h3><p>Integer, floating-point, collections, parsing, compression, hashing and representative application kernels.</p></div><div><h3>Latency</h3><p>Allocation, function dispatch, synchronization, filesystem/network operations and tail-latency-sensitive paths.</p></div><div><h3>Build performance</h3><p>Cold builds, incremental builds, self-host compilation and backend-specific code-generation time.</p></div><div><h3>Artifact characteristics</h3><p>Executable size, startup time, peak memory, allocation counts and generated-code size.</p></div></div></div></section>
<section class="section section-white"><div class="shell two-col"><div><p class="kicker">CURRENT STATUS</p><h2>Methodology published. Result corpus pending.</h2><p class="section-copy">The absence of numbers here is deliberate. Once a canonical benchmark dataset exists, this page can render it without changing the surrounding contract.</p></div><div class="fact-list"><div><b>Published benchmark dataset</b><span>Not yet available</span></div><div><b>Performance model</b><span>Documented</span></div><div><b>Standard-library performance model</b><span>Documented</span></div><div><b>Invented estimates</b><span>Never published</span></div></div></div></section></main>'''
    p=ROOT/'performance/index.html';p.parent.mkdir(parents=True,exist_ok=True);p.write_text(pre+body+footer,encoding='utf-8')
    payload={'status':'methodology-only','measurements':[],'policy':{'reproducible':True,'raw_data_required':True},'sources':['https://github.com/raz-language/raz/blob/main/docs/PERFORMANCE.md','https://github.com/raz-language/raz/blob/main/docs/STANDARD-LIBRARY-PERFORMANCE.md']}
    (API/'performance.json').write_text(json.dumps(payload,indent=2,sort_keys=True)+'\n',encoding='utf-8')

def make_ecosystem():
    pre,footer=shell(ROOT/'community/index.html')
    pre=pre.replace('href="../community/index.html" aria-current="page"','href="../community/index.html"')
    title='Raz Ecosystem — Repositories, architecture and contribution flow'
    desc='How the Raz compiler, Forge backend, ObLink linker, packages, installer and editor tooling fit together and where to contribute.'
    canonical=f'{SITE_ORIGIN}/ecosystem/'
    schema={'@context':'https://schema.org','@type':'TechArticle','headline':'Raz ecosystem architecture','description':desc,'url':canonical}
    pre=rewrite_head(pre,title,desc,canonical,schema)
    body='''<header class="section-hero"><div class="shell narrow"><p class="kicker">ECOSYSTEM</p><h1>Separate repositories. One toolchain.</h1><p class="page-lead">Raz keeps major responsibilities independently maintainable while preserving explicit integration contracts between the compiler, backend, linker, package registry, installer and editor tooling.</p><div class="button-row"><a class="button button-primary" href="https://github.com/raz-language">Browse organization ↗</a><a class="button button-secondary" href="../community/index.html">Community</a></div></div></header>
<main id="main" class="after-hero"><section class="section section-white"><div class="shell"><div class="section-top compact"><div><p class="kicker">ARCHITECTURE</p><h2>How the repositories fit together.</h2></div><p>The compiler repository embeds synchronized Forge and ObLink copies for an integrated native toolchain while the standalone repositories remain their canonical component homes.</p></div><div class="ecosystem-architecture"><article><b>raz</b><span>Language + production compiler</span><p>Owns language semantics, HIR/MIR, project driver, LSP and integrated toolchain behavior.</p></article><i>→</i><article><b>forge</b><span>Native backend</span><p>Default native code-generation backend; mirrored into Raz for bundled builds.</p></article><i>→</i><article><b>oblink</b><span>Native linker</span><p>Links toolchain-produced native objects and is mirrored into Raz for integration.</p></article></div><div class="ecosystem-support-grid"><article><b>packages</b><span>Official registry + package source</span></article><article><b>installer</b><span>MSI, portable archives, channels and release packaging</span></article><article><b>raz-vscode</b><span>Editor integration backed by the compiler LSP</span></article><article><b>demo-project</b><span>Reference application/project workflow</span></article><article><b>gitcomp</b><span>Git-oriented component tooling</span></article></div></div></section>
<section class="section section-soft"><div class="shell"><div class="section-top compact"><div><p class="kicker">CONTRIBUTION FLOW</p><h2>Change the canonical component first.</h2></div><p>Forge and ObLink are not Raz-specific forks. Intentional component changes belong in their standalone repositories, then the embedded copies are synchronized into Raz.</p></div><div class="contributor-steps"><article><span>1</span><h3>Choose the owning repository</h3><p>Language behavior belongs in Raz; Forge backend work belongs in Forge; linker work belongs in ObLink; packaging belongs in installer.</p></article><article><span>2</span><h3>Run repository checks</h3><p>Normal compiler work uses the documented CMake debug build and test presets plus focused qualification for the changed subsystem.</p></article><article><span>3</span><h3>Synchronize embedded components</h3><p>When Forge or ObLink changes, synchronize and byte-check the embedded mirrors in the Raz repository.</p></article><article><span>4</span><h3>Preserve determinism</h3><p>Source discovery, generated identifiers, dependency order and compiler output are expected to remain reproducible.</p></article></div><div class="code-card ecosystem-command"><div class="code-bar"><span>compiler contribution checks</span></div><pre><code>cmake --preset debug
cmake --build --preset debug
ctest --preset debug

python tools/sync-embedded-components.py
python tools/check-embedded-components.py</code></pre></div><p class="source-note">Use the repository-specific contribution guide before submitting changes; the commands above reflect the Raz compiler repository's documented workflow.</p></div></section></main>'''
    p=ROOT/'ecosystem/index.html';p.parent.mkdir(parents=True,exist_ok=True);p.write_text(pre+body+footer,encoding='utf-8')

def package_sort():
    page=ROOT/'packages/index.html'; text=page.read_text(encoding='utf-8')
    if 'data-package-sort' not in text:
        select='<label class="package-sort"><span>Sort</span><select data-package-sort><option value="name">Name A–Z</option><option value="category">Category</option><option value="versions">Most versions</option></select></label>'
        # Insert after the category filters but before the toolbar closes.
        needle='</div></div>\n  <div class="registry-stats">'
        if needle not in text: raise SystemExit('package toolbar insertion point missing')
        text=text.replace(needle,'</div>'+select+'</div>\n  <div class="registry-stats">',1)
    # attach version counts from visible history text
    packages=json.loads((GEN/'packages.json').read_text(encoding='utf-8'))
    counts={p['name']:len(p.get('versions') or []) for p in packages}
    def add_count(m):
        tag=m.group(0)
        name_match=re.search(r'data-name="([^"]+)"',tag)
        if not name_match:return tag
        value=str(counts.get(name_match.group(1),0))
        if 'data-version-count=' in tag:
            return re.sub(r'data-version-count="[^"]*"',f'data-version-count="{value}"',tag,count=1)
        return tag[:-1]+f' data-version-count="{value}">'
    text=re.sub(r'<article class="package-item"[^>]*>',add_count,text)
    # replace prior sort controller if any
    text=re.sub(r'<script data-package-sort-controller>.*?</script>','',text,flags=re.S)
    controller='''<script data-package-sort-controller>(()=>{const select=document.querySelector('[data-package-sort]');const catalog=document.querySelector('.package-catalog');if(!select||!catalog)return;const rows=[...catalog.querySelectorAll('[data-package]')];const cmp=(a,b)=>{const mode=select.value;const an=a.dataset.name||'',bn=b.dataset.name||'';if(mode==='category'){const c=(a.dataset.category||'').localeCompare(b.dataset.category||'');return c||an.localeCompare(bn)}if(mode==='versions'){const c=Number(b.dataset.versionCount||0)-Number(a.dataset.versionCount||0);return c||an.localeCompare(bn)}return an.localeCompare(bn)};const apply=()=>{[...rows].sort(cmp).forEach(row=>catalog.appendChild(row));};select.addEventListener('change',apply);apply();})();</script>'''
    text=text.replace('<footer class="site-footer">',controller+'<footer class="site-footer">',1)
    page.write_text(text,encoding='utf-8')

def add_footer_links():
    for page in ROOT.rglob('*.html'):
        if '_site' in page.parts: continue
        text=page.read_text(encoding='utf-8')
        rel=page.relative_to(ROOT)
        prefix='../'*max(0,len(rel.parts)-1)
        text=re.sub(r'<a data-project-ecosystem-link[^>]*>Ecosystem</a><a data-project-performance-link[^>]*>Performance</a>','',text)
        about=re.search(r'<a data-project-about-link[^>]*>About</a>',text)
        if about:
            ins=f'<a data-project-ecosystem-link href="{prefix}ecosystem/index.html">Ecosystem</a><a data-project-performance-link href="{prefix}performance/index.html">Performance</a>'
            text=text[:about.end()]+ins+text[about.end():]
            page.write_text(text,encoding='utf-8')

def enrich_search():
    core=ASSETS/'search-core.json'; items=json.loads(core.read_text(encoding='utf-8'))
    items=[i for i in items if i.get('url') not in {'performance/index.html','ecosystem/index.html'}]
    items.extend([
      {'title':'Raz Performance','description':'Performance methodology, reproducibility contract, and benchmark publication status.','url':'performance/index.html','keywords':'performance benchmarks benchmark methodology throughput latency compile time evidence','kind':'performance','name':'Raz Performance','namespace':'','qualified_name':'Raz Performance'},
      {'title':'Raz Ecosystem','description':'Repository architecture and contribution flow across Raz, Forge, ObLink, packages, installer, and editor tooling.','url':'ecosystem/index.html','keywords':'ecosystem architecture repositories contribute forge oblink installer packages vscode','kind':'ecosystem','name':'Raz Ecosystem','namespace':'','qualified_name':'Raz Ecosystem'}])
    core.write_text(json.dumps(items,separators=(',',':'))+'\n',encoding='utf-8')
    # Refresh shard hashes in JS.
    js=ASSETS/'site.js'; text=js.read_text(encoding='utf-8')
    cd=hashlib.sha256(core.read_bytes()).hexdigest()[:12]; ad=hashlib.sha256((ASSETS/'search-api.json').read_bytes()).hexdigest()[:12]
    text=re.sub(r"const coreVersion='[0-9a-f]{12}',apiVersion='[0-9a-f]{12}';",f"const coreVersion='{cd}',apiVersion='{ad}';",text,count=1)
    js.write_text(text,encoding='utf-8')

def update_api():
    idx=API/'index.json'; data=json.loads(idx.read_text(encoding='utf-8')); data.setdefault('resources',{})['performance']='./performance.json'; idx.write_text(json.dumps(data,indent=2,sort_keys=True)+'\n',encoding='utf-8')

def update_sitemap():
    path=ROOT/'sitemap.xml'
    urls=[]
    for page in sorted(ROOT.rglob('*.html')):
        rel=page.relative_to(ROOT)
        if '_site' in rel.parts or rel.as_posix()=='404.html': continue
        text=page.read_text(encoding='utf-8',errors='ignore')
        if re.search(r'<meta name="robots" content="[^"]*noindex',text,re.I): continue
        route='/' if rel.as_posix()=='index.html' else '/'+rel.as_posix().removesuffix('index.html')
        urls.append(f'{SITE_ORIGIN}{route}')
    path.write_text('<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'+''.join(f'  <url><loc>{esc(u)}</loc></url>\n' for u in urls)+'</urlset>\n',encoding='utf-8')


def add_styles():
    p=ASSETS/'styles.css'; text=p.read_text(encoding='utf-8'); marker='/* v29 evidence + ecosystem + package discovery */'
    if marker in text:text=text.split(marker,1)[0].rstrip()+'\n'
    text+='''\n/* v29 evidence + ecosystem + package discovery */
.package-sort{display:flex;align-items:center;gap:8px;margin-left:auto;font-size:.72rem;font-weight:800;color:var(--muted)}.package-sort select{min-height:38px;border:1px solid var(--line);border-radius:6px;background:#fff;padding:0 30px 0 10px;font:inherit;color:var(--ink)}
.ecosystem-architecture{display:grid;grid-template-columns:1fr auto 1fr auto 1fr;align-items:stretch;gap:14px;margin-top:28px}.ecosystem-architecture article,.ecosystem-support-grid article,.contributor-steps article{border:1px solid var(--line);background:#fff;padding:22px}.ecosystem-architecture i{align-self:center;font-style:normal;font-size:1.35rem;color:var(--muted)}.ecosystem-architecture b,.ecosystem-support-grid b{display:block;font-family:var(--mono);font-size:1.05rem}.ecosystem-architecture span,.ecosystem-support-grid span{display:block;margin-top:5px;color:var(--muted);font-size:.78rem}.ecosystem-architecture p{margin:14px 0 0;color:var(--muted);font-size:.84rem}.ecosystem-support-grid{display:grid;grid-template-columns:repeat(5,1fr);gap:10px;margin-top:14px}.contributor-steps{display:grid;grid-template-columns:repeat(4,1fr);gap:12px;margin:28px 0}.contributor-steps span{display:grid;place-items:center;width:26px;height:26px;border-radius:999px;background:var(--ink);color:#fff;font-weight:900;font-size:.7rem}.contributor-steps h3{margin:15px 0 8px}.contributor-steps p,.source-note{color:var(--muted)}.ecosystem-command{max-width:760px}.source-note{font-size:.78rem}
@media(max-width:900px){.ecosystem-architecture{grid-template-columns:1fr}.ecosystem-architecture i{transform:rotate(90deg);justify-self:center}.ecosystem-support-grid{grid-template-columns:1fr 1fr}.contributor-steps{grid-template-columns:1fr 1fr}}
@media(max-width:680px){.package-sort{width:100%;margin-left:0;justify-content:space-between}.package-sort select{flex:1;max-width:220px}.ecosystem-support-grid,.contributor-steps{grid-template-columns:1fr}}
'''
    p.write_text(text,encoding='utf-8')

def main():
    make_performance(); make_ecosystem(); package_sort(); add_footer_links(); enrich_search(); update_api(); update_sitemap(); add_styles()
    print('v29: performance evidence surface, ecosystem onboarding, package sorting')
if __name__=='__main__': main()
