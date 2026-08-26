#!/usr/bin/env python3
from pathlib import Path
import html, json, os, re
ROOT=Path(__file__).resolve().parents[1]
GEN=ROOT/'data'/'generated'; API=ROOT/'api'/'v1'; RAW=ROOT/'data'/'raw'

def esc(x): return html.escape(str(x), quote=True)
def rel(page,target): return os.path.relpath(target,page.parent).replace('\\','/')

def shell_parts(path):
    text=path.read_text(encoding='utf-8')
    m=re.search(r'<header class="page-hero(?: [^"]*)?">',text)
    footer='<footer class="site-footer>'
    if not m or '<footer class="site-footer">' not in text: raise RuntimeError('invalid shell')
    return text[:m.start()], '<footer class="site-footer">'+text.split('<footer class="site-footer">',1)[1]

def rewrite_head(pre,title,desc):
    pre=re.sub(r'<title>.*?</title>',f'<title>{esc(title)}</title>',pre,flags=re.S)
    for attr in ['name="description"','property="og:title"','property="og:description"','name="twitter:title"','name="twitter:description"']:
        value=title if 'title' in attr else desc
        pre=re.sub(r'(<meta '+re.escape(attr)+r' content=")[^"]*(">)',lambda m:m.group(1)+esc(value)+m.group(2),pre)
    return pre

def roadmap():
    result={}
    p=RAW/'package-roadmap.md'
    if not p.exists(): return result
    text=p.read_text(encoding='utf-8')
    for line in text.splitlines():
        m=re.match(r'^\|\s*(\d+)\s*\|\s*`([^`]+)`\s*\|\s*\*\*(.+?)\*\*\s*\|$',line)
        if m: result[m.group(2)]={'state':'implemented','order':int(m.group(1)),'status':m.group(3)}
    fm=re.search(r'Future candidates include (.+?)\.\s*$',text,re.M)
    if fm:
        for n in re.findall(r'`([^`]+)`',fm.group(1)): result.setdefault(n,{'state':'candidate','order':None,'status':'Future candidate'})
    return result

def dependency_href(page,name,package_names):
    if name in package_names: return rel(page,ROOT/'packages'/name/'docs'/'index.html')
    if name in {'core','alloc','collections','std'}: return rel(page,ROOT/'docs'/'stdlib'/'index.html')+'?layer='+name
    return None

def enhance_packages(packages,docs):
    pnames={p['name'] for p in packages}; by={d['name']:d for d in docs}; rev={n:[] for n in pnames}; rm=roadmap()
    for d in docs:
        for dep in d.get('dependencies',[]):
            if dep.get('name') in rev: rev[dep['name']].append(d['name'])
    ecosystem=[]
    for pkg in packages:
        name=pkg['name']; d=by.get(name,{}); r=rm.get(name,{'state':'registry','order':None,'status':'Published in official registry'})
        ecosystem.append({'name':name,'version':pkg['version'],'roadmap':r,'dependencies':d.get('dependencies',[]),'reverse_dependencies':sorted(rev[name]),'modules':len(d.get('modules',[])),'source_available':bool(d.get('available'))})
        page=ROOT/'packages'/name/'docs'/'index.html'
        if not page.exists(): continue
        text=page.read_text(encoding='utf-8')
        badge=f'<div class="package-roadmap-line"><span class="roadmap-badge roadmap-{esc(r["state"])}">{esc(r["state"].upper())}</span><span>{esc(r["status"])}</span></div>'
        if 'package-roadmap-line' not in text:
            text=text.replace('<div class="button-row">',badge+'<div class="button-row">',1)
        graph=[]
        for dep in d.get('dependencies',[]):
            href=dependency_href(page,dep['name'],pnames)
            n=f'<a href="{esc(href)}"><code>{esc(dep["name"])}</code></a>' if href else f'<code>{esc(dep["name"])}</code>'
            graph.append(f'<div class="dependency-edge"><span>depends on</span>{n}<small>{esc(dep.get("requirement",""))}</small></div>')
        used=''.join(f'<a class="dependency-chip" href="{esc(rel(page,ROOT/"packages"/x/"docs"/"index.html"))}">{esc(x)}</a>' for x in sorted(rev[name])) or '<span class="muted">No synchronized official reverse dependencies.</span>'
        section=f'<section class="section section-soft package-graph-section"><div class="shell"><div class="section-top compact"><div><p class="kicker">ECOSYSTEM GRAPH</p><h2>Dependencies and reverse dependencies.</h2></div><p>Links stay inside the Raz docs whenever the dependency is an official package or standard-library layer.</p></div><div class="dependency-graph">{"".join(graph) or "<div class=\"empty-state inline-empty\">No synchronized dependencies.</div>"}</div><div class="reverse-dependencies"><h3>Used by</h3><div class="dependency-chips">{used}</div></div></div></section>'
        if 'package-graph-section' not in text: text=text.replace('</main>',section+'</main>',1)
        page.write_text(text,encoding='utf-8')
    (GEN/'ecosystem.json').write_text(json.dumps(ecosystem,indent=2,sort_keys=True)+'\n',encoding='utf-8')
    API.mkdir(parents=True,exist_ok=True); (API/'ecosystem.json').write_text(json.dumps(ecosystem,indent=2,sort_keys=True)+'\n',encoding='utf-8')
    idx=API/'index.json'
    if idx.exists():
        data=json.loads(idx.read_text()); data.setdefault('resources',{})['ecosystem']='./ecosystem.json'; idx.write_text(json.dumps(data,indent=2,sort_keys=True)+'\n')
    return ecosystem

def api_explorer(packages,package_docs,stdlib,diagnostics):
    page=ROOT/'docs'/'api'/'index.html'; page.parent.mkdir(parents=True,exist_ok=True)
    pre,footer=shell_parts(ROOT/'docs'/'index.html'); pre=pre.replace('href="../','href="../../').replace('src="../','src="../../'); footer=footer.replace('href="../','href="../../').replace('src="../','src="../../'); pre=rewrite_head(pre,'API Reference — Raz','Search the Raz standard library, official package APIs, and stable compiler diagnostics from one reference portal.')
    rows=[]
    for m in stdlib.get('modules',[]):
        href=rel(page,ROOT/'docs'/'stdlib'/Path(m['slug'])/'index.html'); kw=(m['name']+' stdlib '+m.get('layer','')+' '+' '.join(i.get('name','') for i in m.get('items',[]))).lower()
        rows.append(f'<a class="api-explorer-row" data-api-entry data-api-scope="stdlib" data-search="{esc(kw)}" href="{esc(href)}"><span class="api-kind">STDLIB</span><div><code>{esc(m["name"])}</code><p>{m.get("item_count",len(m.get("items",[])))} public items</p></div><b>→</b></a>')
    for d in package_docs:
        href=rel(page,ROOT/'packages'/d['name']/'docs'/'index.html'); syms=' '.join(s.get('name','') for m in d.get('modules',[]) for s in m.get('symbols',[])); kw=(d['name']+' package api '+syms).lower()
        rows.append(f'<a class="api-explorer-row" data-api-entry data-api-scope="package" data-search="{esc(kw)}" href="{esc(href)}"><span class="api-kind">PACKAGE</span><div><code>{esc(d["name"])}</code><p>{len(d.get("modules",[]))} synchronized modules · v{esc(d["version"])}</p></div><b>→</b></a>')
    records = diagnostics.get('records', diagnostics) if isinstance(diagnostics, dict) else diagnostics
    cats={}
    for d in records: cats[d.get('category','other')]=cats.get(d.get('category','other'),0)+1
    dh=rel(page,ROOT/'docs'/'diagnostics'/'index.html')
    for cat,count in sorted(cats.items()): rows.append(f'<a class="api-explorer-row" data-api-entry data-api-scope="diagnostics" data-search="{esc((cat+" diagnostics compiler errors").lower())}" href="{esc(dh)}?category={esc(cat)}"><span class="api-kind">DIAGNOSTIC</span><div><code>{esc(cat)}</code><p>{count} stable diagnostic codes</p></div><b>→</b></a>')
    body=f'''<header class="page-hero"><div class="shell narrow"><div class="doc-breadcrumbs"><a href="../index.html">Docs</a><span>/</span><span>API reference</span></div><p class="kicker">UNIFIED API REFERENCE</p><h1>One search surface for the Raz ecosystem.</h1><p class="page-lead">Search standard-library modules, official package APIs, and stable compiler diagnostics without bouncing between separate documentation products.</p><div class="api-explorer-stats"><div><b>{len(stdlib.get('modules',[]))}</b><span>stdlib modules</span></div><div><b>{len(package_docs)}</b><span>official packages</span></div><div><b>{len(diagnostics)}</b><span>diagnostic codes</span></div></div></div></header><main id="main" class="after-hero"><section class="section section-white"><div class="shell"><div class="api-explorer-toolbar"><input type="search" data-api-search placeholder="Search modules, packages, symbols, diagnostics…" aria-label="Search API reference"><div class="api-explorer-filters"><button class="active" data-api-filter="all">All</button><button data-api-filter="stdlib">Standard library</button><button data-api-filter="package">Packages</button><button data-api-filter="diagnostics">Diagnostics</button></div></div><div class="api-explorer-count" data-api-count>{len(rows)} reference groups</div><div class="api-explorer-list">{''.join(rows)}</div><div class="empty-state" data-api-empty hidden>No API references match that search.</div></div></section></main>'''
    page.write_text(pre+body+footer,encoding='utf-8')
    docs=ROOT/'docs'/'index.html'; text=docs.read_text(encoding='utf-8')
    if 'api/index.html' not in text:
        text=text.replace('<main id="main" class="after-hero">','<main id="main" class="after-hero"><section class="section api-explorer-promo"><div class="shell"><a class="api-explorer-promo-card" href="api/index.html"><span>UNIFIED REFERENCE</span><div><h2>Search the entire Raz API surface.</h2><p>Standard library modules, official package APIs, and stable diagnostics in one place.</p></div><b>Open API Reference →</b></a></div></section>',1); docs.write_text(text,encoding='utf-8')

def search_entry():
    p=ROOT/'assets'/'search-index.js'; t=p.read_text(); m=re.match(r'window\.RAZ_SEARCH=(.*);\s*$',t,re.S)
    if not m:return
    a=json.loads(m.group(1)); a=[x for x in a if x.get('url')!='docs/api/index.html']; a.append({'title':'API Reference','description':'Unified standard library, package API, and diagnostic search','url':'docs/api/index.html','keywords':'api reference stdlib packages diagnostics modules symbols'}); p.write_text('window.RAZ_SEARCH='+json.dumps(a,separators=(',',':'))+';\n')

def main():
    packages=json.loads((GEN/'packages.json').read_text()); pd=json.loads((GEN/'package-docs.json').read_text()); std=json.loads((GEN/'stdlib.json').read_text()); diag=json.loads((GEN/'diagnostics.json').read_text())
    enhance_packages(packages,pd); api_explorer(packages,pd,std,diag); search_entry(); print(f'OK: v11 enhancements: {len(packages)} packages, {len(std.get("modules",[]))} stdlib modules, {len(diag.get('records', diag) if isinstance(diag, dict) else diag)} diagnostics')
if __name__=='__main__': main()
