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
    if not m or '<footer class="site-footer">' not in text: raise RuntimeError(f'invalid shell: {path}')
    return text[:m.start()], '<footer class="site-footer">'+text.split('<footer class="site-footer">',1)[1]

def rewrite_head(pre,title,desc):
    pre=re.sub(r'<title>.*?</title>',f'<title>{esc(title)}</title>',pre,flags=re.S)
    pairs=[('name="description"',desc),('property="og:title"',title),('property="og:description"',desc),('name="twitter:title"',title),('name="twitter:description"',desc)]
    for attr,value in pairs:
        pre=re.sub(r'(<meta '+re.escape(attr)+r' content=")[^"]*(">)',lambda m:m.group(1)+esc(value)+m.group(2),pre)
    return pre

def write_status(site):
    page=ROOT/'status'/'index.html'; page.parent.mkdir(parents=True,exist_ok=True)
    pre,footer=shell_parts(ROOT/'docs'/'index.html')
    pre=pre.replace('href="../','href="../').replace('src="../','src="../')
    # docs shell is already one level deep, same as /status/.
    title='Compatibility & Status — Raz'
    desc='Current Raz language stability, qualified native targets, backend support, and binary release status.'
    pre=rewrite_head(pre,title,desc)
    platforms=site.get('platforms',[])
    rows=''.join(f'''<tr><td><code>{esc(p.get('target',''))}</code></td><td>{esc(p.get('host_use',''))}</td><td>{esc(p.get('backend',''))}</td><td>{esc(p.get('abi',''))}</td><td>{esc(p.get('object',''))}</td></tr>''' for p in platforms)
    br=site.get('binary_releases',{}); nightly=br.get('nightly') or {}
    release_state='Published' if br.get('published') else 'Not yet published'
    release_class='status-good' if br.get('published') else 'status-pending'
    nightly_state=str(nightly.get('status') or 'unknown')
    warnings=site.get('source_audit',{}).get('warnings',[])
    warning_html=''.join(f'<li><code>{esc(w.get("code"))}</code><span>{esc(w.get("message"))}</span></li>' for w in warnings) or '<li><span>No source consistency warnings.</span></li>'
    body=f'''<header class="page-hero"><div class="shell narrow"><div class="doc-breadcrumbs"><a href="../docs/index.html">Docs</a><span>/</span><span>Status</span></div><p class="kicker">QUALIFICATION STATUS</p><h1>What Raz supports today.</h1><p class="page-lead">A generated compatibility view of the stable language contract, qualified native targets, backend selection, and published toolchain availability.</p></div></header><main id="main" class="after-hero"><section class="section section-white"><div class="shell"><div class="status-summary-grid"><article><span>LANGUAGE</span><b>Raz {esc(site.get('language',{}).get('version','1.0'))}</b><p><strong class="status-good">Stable</strong> within the documented 1.x compatibility contract.</p></article><article><span>NATIVE TARGETS</span><b>{len(platforms)}</b><p>Qualified target triples in the current platform-support contract.</p></article><article><span>BINARY RELEASES</span><b>{esc(release_state)}</b><p><strong class="{release_class}">{esc(release_state)}</strong> · nightly channel: {esc(nightly_state)}</p></article><article><span>SOURCE AUDIT</span><b>{len(warnings)}</b><p>Known upstream documentation consistency warning{'' if len(warnings)==1 else 's'}.</p></article></div></div></section><section class="section section-soft"><div class="shell"><div class="section-top compact"><div><p class="kicker">QUALIFIED TARGETS</p><h2>Native platform matrix.</h2></div><p>Backend support is a toolchain qualification contract; it does not change Raz source-language semantics.</p></div><div class="status-table-wrap"><table class="status-table"><thead><tr><th>Target</th><th>Host use</th><th>Backend</th><th>ABI</th><th>Object</th></tr></thead><tbody>{rows}</tbody></table></div><div class="status-note"><b>AArch64 qualification</b><p>LLVM is the release-default native backend on Linux AArch64 and macOS arm64. Forge has experimental AArch64 machine/object support, but recursive bootstrap and remaining backend qualification gaps keep LLVM as the qualified default.</p></div></div></section><section class="section section-white"><div class="shell two-col"><div><p class="kicker">RELEASE AVAILABILITY</p><h2>Language stability and binary publication are separate.</h2><p class="section-copy">Raz 1.0 defines the stable language surface even when prebuilt toolchain artifacts have not yet been published. The installer channel and GitHub release feed remain the source of truth for binaries.</p><div class="button-row"><a class="button button-primary" href="../install/index.html">Install Raz</a><a class="button button-secondary" href="../releases/index.html">Release status</a></div></div><div class="fact-list"><div><b>Language</b><span>1.0 stable</span></div><div><b>Published binary releases</b><span>{esc(br.get('count',0))}</span></div><div><b>Nightly version</b><span>{esc(nightly.get('version','—'))}</span></div><div><b>Nightly status</b><span>{esc(nightly_state)}</span></div></div></div></section><section class="section section-soft"><div class="shell"><div class="section-top compact"><div><p class="kicker">SOURCE CONSISTENCY</p><h2>Known documentation drift.</h2></div><p>The website reports inconsistencies instead of silently rewriting canonical project claims.</p></div><ul class="status-warning-list">{warning_html}</ul></div></section></main>'''
    page.write_text(pre+body+footer,encoding='utf-8')
    status={
      'language':site.get('language',{}),
      'platforms':platforms,
      'binary_releases':br,
      'source_audit':site.get('source_audit',{}),
      'url':'status/index.html'
    }
    (GEN/'status.json').write_text(json.dumps(status,indent=2,sort_keys=True)+'\n',encoding='utf-8')
    API.mkdir(parents=True,exist_ok=True); (API/'status.json').write_text(json.dumps(status,indent=2,sort_keys=True)+'\n',encoding='utf-8')
    idx=API/'index.json'
    if idx.exists():
        data=json.loads(idx.read_text()); data.setdefault('resources',{})['status']='./status.json'; idx.write_text(json.dumps(data,indent=2,sort_keys=True)+'\n')

def write_versions(site):
    versions={
      'current':'1.0',
      'stable':['1.0'],
      'docs':{'1.0':'docs/index.html'},
      'language_status':site.get('language',{}).get('stability','stable')
    }
    (GEN/'versions.json').write_text(json.dumps(versions,indent=2,sort_keys=True)+'\n')
    (API/'versions.json').write_text(json.dumps(versions,indent=2,sort_keys=True)+'\n')
    idx=API/'index.json'
    if idx.exists():
        data=json.loads(idx.read_text()); data.setdefault('resources',{})['versions']='./versions.json'; idx.write_text(json.dumps(data,indent=2,sort_keys=True)+'\n')
    # Stable version landing route without duplicating the full documentation tree.
    page=ROOT/'docs'/'1.0'/'index.html'; page.parent.mkdir(parents=True,exist_ok=True)
    target='../index.html'
    page.write_text(f'''<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><meta name="description" content="Raz 1.0 stable language documentation."><meta name="robots" content="noindex"><meta http-equiv="refresh" content="0; url={target}"><title>Raz 1.0 documentation</title><link rel="canonical" href="{target}"></head><body><main><h1>Raz 1.0 documentation</h1><p><a href="{target}">Continue to the Raz 1.0 documentation.</a></p></main></body></html>''',encoding='utf-8')

def add_status_links():
    for page in ROOT.rglob('*.html'):
        if '_site' in page.parts: continue
        text=page.read_text(encoding='utf-8')
        href=rel(page,ROOT/'status'/'index.html')
        if '<footer class="site-footer">' in text and '>Status<' not in text:
            # Add next to Security in Project column when possible.
            text=text.replace('>Security ↗</a>',f'>Security ↗</a><a href="{esc(href)}">Status</a>',1)
        if page.parts[-3:-1] == ('docs','1.0'): # redirect page; leave minimal
            pass
        elif '<head>' in text and 'name="raz-doc-version"' not in text and ('/docs/' in str(page).replace('\\','/') or '/learn/' in str(page).replace('\\','/')):
            text=text.replace('</head>','  <meta name="raz-doc-version" content="1.0">\n</head>',1)
        page.write_text(text,encoding='utf-8')

def social_metadata():
    base=os.getenv('RAZ_SITE_URL','').rstrip('/')
    image=f'{base}/assets/raz-logo.png' if base else ''
    generated_re=re.compile(r'\s*<meta [^>]*data-v12-social="true"[^>]*>')
    for page in ROOT.rglob('*.html'):
        if '_site' in page.parts: continue
        text=page.read_text(encoding='utf-8')
        if '<head>' not in text: continue
        text=generated_re.sub('',text)
        text=text.replace('<meta name="twitter:card" content="summary_large_image">','<meta name="twitter:card" content="summary">')
        if base:
            tags=(f'  <meta property="og:image" content="{esc(image)}" data-v12-social="true">\n'
                  f'  <meta property="og:image:alt" content="Raz programming language logo" data-v12-social="true">\n'
                  f'  <meta property="og:locale" content="en_US" data-v12-social="true">\n'
                  f'  <meta name="twitter:image" content="{esc(image)}" data-v12-social="true">\n')
            text=text.replace('</head>',tags+'</head>',1)
            text=text.replace('<meta name="twitter:card" content="summary">','<meta name="twitter:card" content="summary_large_image">')
        page.write_text(text,encoding='utf-8')

def write_deploy_files():
    csp="default-src 'self'; base-uri 'self'; object-src 'none'; frame-ancestors 'none'; form-action 'self'; img-src 'self' data:; font-src 'self'; style-src 'self'; script-src 'self' 'unsafe-inline'; connect-src 'self'; upgrade-insecure-requests"
    headers=f'''/*\n  X-Content-Type-Options: nosniff\n  Referrer-Policy: strict-origin-when-cross-origin\n  X-Frame-Options: DENY\n  Permissions-Policy: camera=(), microphone=(), geolocation=(), payment=(), usb=()\n  Cross-Origin-Opener-Policy: same-origin\n  Content-Security-Policy: {csp}\n\n/assets/*\n  Cache-Control: public, max-age=3600, stale-while-revalidate=86400\n\n/api/*\n  Cache-Control: public, max-age=300, stale-while-revalidate=3600\n\n/*.html\n  Cache-Control: public, max-age=0, must-revalidate\n'''
    (ROOT/'_headers').write_text(headers,encoding='utf-8')
    redirects='''/getting-started /learn/book/ 301\n/book /learn/book/ 301\n/reference /docs/api/ 301\n/stdlib /docs/stdlib/ 301\n/diagnostics /docs/diagnostics/ 301\n/download /install/ 301\n/downloads /releases/ 301\n'''
    (ROOT/'_redirects').write_text(redirects,encoding='utf-8')
    vercel={
      'headers':[{'source':'/(.*)','headers':[
        {'key':'X-Content-Type-Options','value':'nosniff'},
        {'key':'Referrer-Policy','value':'strict-origin-when-cross-origin'},
        {'key':'X-Frame-Options','value':'DENY'},
        {'key':'Permissions-Policy','value':'camera=(), microphone=(), geolocation=(), payment=(), usb=()'},
        {'key':'Cross-Origin-Opener-Policy','value':'same-origin'},
        {'key':'Content-Security-Policy','value':csp},
      ]}],
      'redirects':[
        {'source':'/getting-started','destination':'/learn/book/','permanent':True},
        {'source':'/book','destination':'/learn/book/','permanent':True},
        {'source':'/reference','destination':'/docs/api/','permanent':True},
        {'source':'/stdlib','destination':'/docs/stdlib/','permanent':True},
        {'source':'/diagnostics','destination':'/docs/diagnostics/','permanent':True},
        {'source':'/download','destination':'/install/','permanent':True},
        {'source':'/downloads','destination':'/releases/','permanent':True},
      ]
    }
    (ROOT/'vercel.json').write_text(json.dumps(vercel,indent=2)+'\n')

def write_performance_budget():
    budget={
      'version':3,
      'limits':{
        'homepage_html_bytes':65536,
        'styles_css_bytes':131072,
        'site_js_bytes':65536,
        'search_index_js_bytes':1572864,
        'largest_public_file_bytes':1048576,
        'staged_site_bytes':67108864
      },
      'notes':'Budgets distinguish per-request performance from total generated documentation corpus size. Handwritten runtime assets and generated search data stay tightly bounded; staged_site_bytes is a 64 MiB corpus-growth guardrail, not a page-load budget. Source-tree scans inspect deployable files only, so repository metadata and build artifacts cannot affect public-site budgets.'
    }
    (ROOT/'performance-budget.json').write_text(json.dumps(budget,indent=2,sort_keys=True)+'\n')

def update_search():
    p=ROOT/'assets'/'search-index.js'
    if not p.exists(): return
    t=p.read_text(); m=re.match(r'window\.RAZ_SEARCH=(.*);\s*$',t,re.S)
    if not m:return
    a=json.loads(m.group(1)); a=[x for x in a if x.get('url')!='status/index.html']; a.append({'title':'Compatibility & Status','description':'Qualified targets, backend support, language stability, and binary release status','url':'status/index.html','keywords':'status compatibility platform targets forge llvm releases qualification'}); p.write_text('window.RAZ_SEARCH='+json.dumps(a,separators=(',',':'))+';\n')

def append_styles():
    p=ROOT/'assets'/'styles.css'; t=p.read_text()
    if '.status-summary-grid' in t: return
    t+='''\n/* v12 — release-quality status and compatibility surfaces */\n.status-summary-grid{display:grid;grid-template-columns:repeat(4,1fr);gap:12px}.status-summary-grid article{border:1px solid var(--line);background:#fff;padding:22px;min-height:170px}.status-summary-grid article>span{font-size:.66rem;font-weight:900;letter-spacing:.11em;color:#6d7b8f}.status-summary-grid article>b{display:block;margin:18px 0 10px;font-size:1.55rem;letter-spacing:-.03em}.status-summary-grid article p{margin:0;color:var(--muted);font-size:.86rem}.status-good{color:#0b7a4a}.status-pending{color:#9a6710}.status-table-wrap{overflow-x:auto;border:1px solid var(--line);background:#fff}.status-table{width:100%;border-collapse:collapse;min-width:820px}.status-table th,.status-table td{padding:14px 16px;text-align:left;border-bottom:1px solid var(--line);font-size:.86rem}.status-table th{background:#f7f9fc;color:#667386;font-size:.69rem;letter-spacing:.08em;text-transform:uppercase}.status-table tr:last-child td{border-bottom:0}.status-note{margin-top:18px;border-left:3px solid var(--blue);background:#fff;padding:18px 20px}.status-note p{margin:6px 0 0;color:var(--muted)}.status-warning-list{list-style:none;margin:0;padding:0;border-top:1px solid var(--line)}.status-warning-list li{display:grid;grid-template-columns:220px 1fr;gap:20px;padding:15px 0;border-bottom:1px solid var(--line);align-items:start}.status-warning-list code{color:#845d11}.status-warning-list span{color:var(--muted)}@media(max-width:900px){.status-summary-grid{grid-template-columns:repeat(2,1fr)}}@media(max-width:620px){.status-summary-grid{grid-template-columns:1fr}.status-warning-list li{grid-template-columns:1fr;gap:5px}}\n'''
    p.write_text(t,encoding='utf-8')

def main():
    site=json.loads((GEN/'site.json').read_text())
    write_status(site); write_versions(site); add_status_links(); social_metadata(); write_deploy_files(); write_performance_budget(); update_search(); append_styles()
    print(f"OK: v12 release hardening: {len(site.get('platforms',[]))} qualified targets, {site.get('binary_releases',{}).get('count',0)} published binary releases")
if __name__=='__main__': main()
