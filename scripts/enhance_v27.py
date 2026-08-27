#!/usr/bin/env python3
"""v27: stable package-version routes and latest-version API snapshots."""
from __future__ import annotations

from pathlib import Path
from urllib.parse import urlsplit, urlunsplit
import html, json, os, re, shutil, hashlib

ROOT=Path(__file__).resolve().parents[1]
GEN=ROOT/'data'/'generated'
API=ROOT/'api'/'v1'
SITE_ORIGIN=(os.getenv('RAZ_SITE_URL') or 'https://raz-language.github.io').strip().rstrip('/')
MANIFEST=GEN/'package-version-pages.json'


def esc(v): return html.escape(str(v), quote=True)

def inside(path:Path, root:Path)->bool:
    try: path.relative_to(root); return True
    except ValueError: return False

def rel(page:Path,target:Path)->str:
    return os.path.relpath(target,page.parent).replace('\\','/')

def relocate_fragment(text:str, source_page:Path, dest_page:Path, docs_src:Path|None=None, docs_dst:Path|None=None, package_index:Path|None=None, version_index:Path|None=None)->str:
    pat=re.compile(r'(?P<prefix>\b(?:href|src)=)(?P<q>["\'])(?P<url>.*?)(?P=q)',re.I)
    def repl(m):
        raw=m.group('url')
        if not raw or raw.startswith(('#','mailto:','tel:','javascript:','data:')): return m.group(0)
        p=urlsplit(raw)
        if p.scheme or p.netloc: return m.group(0)
        if not p.path: return m.group(0)
        target=(ROOT/p.path.lstrip('/')).resolve() if p.path.startswith('/') else (source_page.parent/p.path).resolve()
        if not inside(target,ROOT): return m.group(0)
        mapped=target
        if docs_src and docs_dst and inside(target,docs_src): mapped=docs_dst/target.relative_to(docs_src)
        elif package_index and version_index and target==package_index.resolve() and not (p.fragment=='versions'):
            mapped=version_index
        out=os.path.relpath(mapped,dest_page.parent).replace('\\','/')
        return f"{m.group('prefix')}{m.group('q')}{urlunsplit(('', '', out, p.query, p.fragment))}{m.group('q')}"
    return pat.sub(repl,text)

def rewrite_head_for_route(text:str, route:str, version:str, noindex=False)->str:
    canonical=f'{SITE_ORIGIN}{route}'
    text=re.sub(r'<link rel="canonical" href="[^"]*">',f'<link rel="canonical" href="{esc(canonical)}">',text,count=1)
    text=re.sub(r'<meta property="og:url" content="[^"]*">',f'<meta property="og:url" content="{esc(canonical)}">',text,count=1)
    text=re.sub(r'<meta name="raz-package-version" content="[^"]*">','',text)
    text=text.replace('</head>',f'  <meta name="raz-package-version" content="{esc(version)}">\n</head>',1)
    if noindex and 'name="robots"' not in text:
        text=text.replace('</head>','  <meta name="robots" content="noindex,follow">\n</head>',1)
    return text

def shell_from(source:Path,dest:Path):
    text=source.read_text(encoding='utf-8')
    m=re.search(r'<header class="(?:marketing-hero|section-hero|product-masthead|reference-header)[^"]*"',text)
    if not m: raise RuntimeError(f'no opening in {source}')
    f=text.find('<footer class="site-footer">')
    if f<0: raise RuntimeError(f'no footer in {source}')
    pre=relocate_fragment(text[:m.start()],source,dest)
    footer=relocate_fragment(text[f:],source,dest)
    return pre,footer

def version_page(package, item, latest):
    name=package['name']; version=item['version']
    root=ROOT/'packages'/name/version
    page=root/'index.html'; root.mkdir(parents=True,exist_ok=True)
    source=ROOT/'packages'/name/'index.html'
    pre,footer=shell_from(source,page)
    title=f'{name} {version} — Raz package release'
    desc=f'Immutable registry record for {name} {version}, including install command, package-tree checksum, archive, and versioned documentation status.'
    pre=re.sub(r'<title>.*?</title>',f'<title>{esc(title)}</title>',pre,count=1,flags=re.S)
    pre=re.sub(r'<meta name="description" content="[^"]*">',f'<meta name="description" content="{esc(desc)}">',pre,count=1)
    pre=re.sub(r'<meta property="og:title" content="[^"]*">',f'<meta property="og:title" content="{esc(title)}">',pre,count=1)
    pre=re.sub(r'<meta property="og:description" content="[^"]*">',f'<meta property="og:description" content="{esc(desc)}">',pre,count=1)
    pre=re.sub(r'<meta name="twitter:title" content="[^"]*">',f'<meta name="twitter:title" content="{esc(title)}">',pre,count=1)
    pre=re.sub(r'<meta name="twitter:description" content="[^"]*">',f'<meta name="twitter:description" content="{esc(desc)}">',pre,count=1)
    pre=rewrite_head_for_route(pre,f'/packages/{name}/{version}/',version)
    label='LATEST RELEASE' if latest else 'IMMUTABLE RELEASE'
    docs_copy='Frozen API snapshot from the synchronized current package source.' if latest else 'Historical API source is not cached in this website snapshot; this route remains stable until an immutable source snapshot is available.'
    body=f'''<header class="product-masthead package-detail-hero"><div class="shell"><div class="doc-breadcrumbs"><a href="../../index.html">Packages</a><span>/</span><a href="../index.html">{esc(name)}</a><span>/</span><span>{esc(version)}</span></div><p class="kicker">{label}</p><h1><code>{esc(name)}</code> <span class="package-version-title">{esc(version)}</span></h1><p class="page-lead">{esc(package['description'])}</p><div class="package-version-row"><span>Version <b>{esc(version)}</b></span><span>Owner <b>{esc(package['owner'])}</b></span><span>Category <b>{esc(package['category'])}</b></span></div><div class="button-row"><a class="button button-primary" href="docs/index.html">Version docs</a><a class="button button-secondary" href="{esc(item['source_url'])}">Registry archive ↗</a></div></div></header>
<main id="main" class="after-hero"><section class="section section-white"><div class="shell package-detail-grid"><article><p class="kicker">INSTALL THIS VERSION</p><h2>Pin the immutable release.</h2><div class="command-copy"><code>raz add {esc(name)}@{esc(version)}</code><button type="button" data-copy="raz add {esc(name)}@{esc(version)}">Copy</button></div><p>The registry record is immutable. Raz records the resolved package tree in <code>raz.lock</code>.</p></article><aside class="package-meta-card"><div><span>Version</span><b>{esc(version)}</b></div><div><span>Tree checksum</span><code>{esc(item['checksum'])}</code></div><div><span>Archive</span><code>{esc(item['archive'])}</code></div><div><span>Status</span><b>{'Latest' if latest else 'Historical'}</b></div></aside></div></section><section class="section section-soft"><div class="shell two-col"><div><p class="kicker">VERSIONED DOCUMENTATION</p><h2>Documentation follows immutable releases.</h2><p class="section-copy">{esc(docs_copy)}</p><div class="button-row"><a class="button button-primary" href="docs/index.html">Open {esc(version)} docs</a><a class="button button-secondary" href="../index.html#versions">All versions</a></div></div><div class="fact-list"><div><b>Package</b><span>{esc(name)}</span></div><div><b>Release</b><span>{esc(version)}</span></div><div><b>Checksum</b><span><code>{esc(item['checksum'])}</code></span></div><div><b>Registry</b><span>raz-language/packages</span></div></div></div></section></main>'''
    page.write_text(pre+body+footer,encoding='utf-8')
    return page

def snapshot_latest_docs(package,version):
    name=package['name']; src=ROOT/'packages'/name/'docs'; dst=ROOT/'packages'/name/version/'docs'
    if dst.exists(): shutil.rmtree(dst)
    package_index=(ROOT/'packages'/name/'index.html').resolve(); version_index=(ROOT/'packages'/name/version/'index.html').resolve()
    for s in src.rglob('*'):
        d=dst/s.relative_to(src)
        if s.is_dir(): d.mkdir(parents=True,exist_ok=True); continue
        d.parent.mkdir(parents=True,exist_ok=True)
        if s.suffix.lower()=='.html':
            text=s.read_text(encoding='utf-8')
            text=relocate_fragment(text,s,d,src,dst,package_index,version_index)
            relroute=d.relative_to(ROOT).as_posix()
            route='/' + relroute.removesuffix('index.html')
            text=rewrite_head_for_route(text,route,version,noindex=True)
            d.write_text(text,encoding='utf-8')
        else: shutil.copy2(s,d)

def historical_docs_page(package,item):
    name=package['name']; version=item['version']; page=ROOT/'packages'/name/version/'docs'/'index.html'; page.parent.mkdir(parents=True,exist_ok=True)
    source=ROOT/'packages'/name/'docs'/'index.html'; pre,footer=shell_from(source,page)
    title=f'{name} {version} API documentation — Raz packages'
    desc=f'Historical documentation route for immutable {name} {version}. The registry record is available even when the historical source API snapshot is not cached.'
    pre=re.sub(r'<title>.*?</title>',f'<title>{esc(title)}</title>',pre,count=1,flags=re.S)
    pre=re.sub(r'<meta name="description" content="[^"]*">',f'<meta name="description" content="{esc(desc)}">',pre,count=1)
    pre=rewrite_head_for_route(pre,f'/packages/{name}/{version}/docs/',version,noindex=True)
    body=f'''<header class="reference-header package-docs-hero"><div class="shell"><div class="doc-breadcrumbs"><a href="../../../index.html">Packages</a><span>/</span><a href="../../index.html">{esc(name)}</a><span>/</span><a href="../index.html">{esc(version)}</a><span>/</span><span>API docs</span></div><p class="kicker">HISTORICAL PACKAGE API</p><h1><code>{esc(name)}</code> {esc(version)}</h1><p class="page-lead">This immutable version route is reserved for the API published with {esc(name)} {esc(version)}.</p></div></header><main id="main" class="after-hero"><section class="section section-white"><div class="shell narrow"><div class="empty-state"><h2>Historical source snapshot not cached yet.</h2><p>The website will not substitute the latest package source for an older immutable release. The registry archive and checksum remain authoritative until version-specific source extraction is available.</p><div class="button-row"><a class="button button-primary" href="{esc(item['source_url'])}">Registry archive ↗</a><a class="button button-secondary" href="../../docs/index.html">Latest API docs</a></div></div></div></section></main>'''
    page.write_text(pre+body+footer,encoding='utf-8')

def patch_overview_links(package):
    page=ROOT/'packages'/package['name']/'index.html'; text=page.read_text(encoding='utf-8')
    for item in package.get('versions',[]):
        version=item['version']
        pattern=rf'(<div class="version-actions">)(.*?)(<a href="{re.escape(item["source_url"])}">Archive ↗</a>)'
        repl=rf'\1\2<a href="{version}/index.html">Details</a>\3'
        text,n=re.subn(pattern,repl,text,count=1,flags=re.S)
    page.write_text(text,encoding='utf-8')

def update_api(records):
    payload={'generated_from':'official Raz package registry index','versions':records}
    (API/'package-versions.json').write_text(json.dumps(payload,indent=2,sort_keys=True)+'\n',encoding='utf-8')
    idx=API/'index.json'; data=json.loads(idx.read_text(encoding='utf-8')); data.setdefault('resources',{})['package-versions']='./package-versions.json'; idx.write_text(json.dumps(data,indent=2,sort_keys=True)+'\n',encoding='utf-8')
    by={}
    for r in records: by.setdefault(r['package'],[]).append(r)
    for name, versions in by.items():
        p=API/'packages'/name/'index.json'
        if p.exists():
            d=json.loads(p.read_text(encoding='utf-8')); d['versions']=versions; p.write_text(json.dumps(d,indent=2,sort_keys=True)+'\n',encoding='utf-8')

def enrich_search(records):
    path=ROOT/'assets'/'search-core.json'; items=json.loads(path.read_text(encoding='utf-8'))
    items=[x for x in items if x.get('kind')!='package-version']
    for r in records:
        items.append({'title':f"{r['package']} {r['version']}",'name':r['package'],'namespace':'','qualified_name':f"{r['package']}@{r['version']}",'kind':'package-version','description':f"Immutable Raz package release {r['package']} {r['version']}",'url':r['website_url'].lstrip('/'),'keywords':f"package version release {r['package']} {r['version']} checksum registry"})
    path.write_text(json.dumps(items,separators=(',',':'))+'\n',encoding='utf-8')
    # Keep the lazy-search controller cache key synchronized with the enriched shard.
    site_js=ROOT/'assets'/'site.js'
    js=site_js.read_text(encoding='utf-8')
    core_digest=hashlib.sha256(path.read_bytes()).hexdigest()[:12]
    js,n=re.subn(r"const coreVersion='[0-9a-f]{12}',apiVersion='([0-9a-f]{12})';",lambda m:f"const coreVersion='{core_digest}',apiVersion='{m.group(1)}';",js,count=1)
    if n!=1: raise RuntimeError('could not synchronize v27 search core cache key')
    site_js.write_text(js,encoding='utf-8')

def main():
    packages=json.loads((GEN/'packages.json').read_text(encoding='utf-8'))
    # Remove only version directories previously owned by this enhancer.
    previous=[]
    if MANIFEST.exists():
        try: previous=json.loads(MANIFEST.read_text(encoding='utf-8'))
        except Exception: previous=[]
    for entry in previous:
        p=ROOT/entry
        if p.is_dir(): shutil.rmtree(p)
    records=[]; owned=[]
    for package in packages:
        versions=package.get('versions',[])
        for i,item in enumerate(versions):
            latest=(i==0)
            version=item['version']; version_page(package,item,latest)
            owned.append(f"packages/{package['name']}/{version}")
            if latest: snapshot_latest_docs(package,version)
            else: historical_docs_page(package,item)
            records.append({'package':package['name'],'version':version,'latest':latest,'checksum':item['checksum'],'archive':item['archive'],'archive_url':item['source_url'],'website_url':f"/packages/{package['name']}/{version}/",'docs_url':f"/packages/{package['name']}/{version}/docs/",'docs_state':'frozen-current-source' if latest else 'historical-source-not-cached'})
        patch_overview_links(package)
    MANIFEST.write_text(json.dumps(owned,indent=2)+'\n',encoding='utf-8')
    update_api(records); enrich_search(records)
    print(f"v27: generated {len(records)} package-version records; {len(packages)} latest API snapshots")

if __name__=='__main__': main()
