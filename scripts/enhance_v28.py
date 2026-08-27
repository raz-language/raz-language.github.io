#!/usr/bin/env python3
"""v28: responsive/reference usability hardening for dense generated surfaces."""
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
CSS = ROOT / 'assets' / 'styles.css'
MARKER = '/* v28 responsive + dense-reference usability */'

SCROLL_CLASSES = ('doc-table-wrap','status-table-wrap','release-table','reference-table','version-table-wrap')


def patch_scroll_regions() -> int:
    changed = 0
    class_alt = '|'.join(re.escape(x) for x in SCROLL_CLASSES)
    pat = re.compile(r'<(?P<tag>div|section)(?P<before>[^>]*\bclass="[^"]*(?:' + class_alt + r')[^"]*")(?P<after>[^>]*)>')
    for page in ROOT.rglob('*.html'):
        if '_site' in page.relative_to(ROOT).parts:
            continue
        text = page.read_text(encoding='utf-8')
        def repl(m):
            raw = m.group(0)
            attrs = ''
            if 'data-scroll-region' not in raw:
                attrs += ' data-scroll-region'
            if 'tabindex=' not in raw:
                attrs += ' tabindex="0"'
            if 'role=' not in raw:
                attrs += ' role="region"'
            if 'aria-label=' not in raw:
                attrs += ' aria-label="Scrollable reference content"'
            if not attrs:
                return raw
            return raw[:-1] + attrs + '>'
        new = pat.sub(repl, text)
        if new != text:
            page.write_text(new, encoding='utf-8')
            changed += 1
    return changed


def add_css() -> None:
    text = CSS.read_text(encoding='utf-8')
    if MARKER in text:
        text = text.split(MARKER, 1)[0].rstrip() + '\n'
    text += r'''

/* v28 responsive + dense-reference usability */
/* Dense generated identifiers must never force the page wider than the viewport. */
.reference-header h1,.product-masthead h1,.api-item-hero h1,.api-module-hero h1,
.doc-reference-content h2,.doc-reference-content h3,.book-article h2,.book-article h3,
.package-api-module-row code,.api-item-row code,.api-signature-card code,
.release-asset-row b,.version-row code{overflow-wrap:anywhere;word-break:break-word}

/* Keyboard/touch discoverability for horizontally scrollable reference data. */
[data-scroll-region]{max-width:100%;overflow:auto;overscroll-behavior-inline:contain;-webkit-overflow-scrolling:touch;scrollbar-gutter:stable}
[data-scroll-region]:focus{outline:3px solid rgba(45,107,255,.18);outline-offset:2px}
[data-scroll-region] table{min-width:max-content}
.doc-table-wrap,.status-table-wrap{background:#fff}
.doc-table th,.status-table th{position:sticky;top:0;z-index:1}

/* Keep touch navigation one-dimensional instead of wrapping into a tall pseudo-grid. */
.package-product-nav{scrollbar-width:thin;scroll-snap-type:x proximity;overscroll-behavior-inline:contain}
.package-product-nav a{scroll-snap-align:start}

@media(max-width:900px){
  .release-asset-row{min-width:0}
  .release-asset-row>div:first-child,.release-asset-row b{min-width:0;overflow-wrap:anywhere}
  .api-item-layout{grid-template-columns:1fr;gap:28px}
  .api-meta-card{max-width:680px}
}

@media(max-width:820px){
  /* Reference TOCs remain available but stop dominating the article opening. */
  .doc-reference-sidebar{max-height:210px;overflow:auto;overscroll-behavior:contain;border:1px solid var(--line);border-radius:8px;padding:14px 15px}
  .doc-reference-sidebar .back-docs{margin-bottom:12px}
  .doc-reference-sidebar nav{grid-template-columns:1fr 1fr;gap:2px 14px}
  .doc-reference-layout{gap:22px}
  .book-sidebar{max-height:190px;overflow:auto;overscroll-behavior:contain}
  .book-sidebar nav{display:block;padding-top:10px}
  .book-nav-group{margin-top:12px}
  .book-reading-layout{gap:22px}
  .reference-header .doc-source-meta,.product-masthead .package-version-row{gap:7px 14px}
}

@media(max-width:680px){
  /* Search behaves like a mobile bottom sheet with the result list using the remaining viewport. */
  .search-dialog{display:flex;align-items:flex-end}
  .search-panel{width:100%;max-height:min(88dvh,720px);margin:0;border-radius:16px 16px 0 0;border-left:0;border-right:0;border-bottom:0}
  .search-results{max-height:calc(88dvh - 118px);padding-bottom:max(10px,env(safe-area-inset-bottom))}
  .search-box{padding:15px max(15px,env(safe-area-inset-right)) 15px max(15px,env(safe-area-inset-left))}
  .search-hint{display:none}

  .package-product-nav{top:68px;padding-inline:12px}
  .package-product-nav a{padding:12px 11px}
  .package-product-stats{display:grid;grid-template-columns:1fr;width:100%}
  .package-product-stats div{justify-content:space-between;border-right:0;border-bottom:1px solid var(--line)}
  .package-product-stats div:last-child{border-bottom:0}

  .doc-reference-sidebar{max-height:165px}
  .doc-reference-sidebar nav{grid-template-columns:1fr}
  .book-sidebar{max-height:155px}

  .reference-summary,.library-stats,.api-module-stats{grid-template-columns:1fr}
  .api-module-stats>div{padding:13px 14px}
  .api-item-row{grid-template-columns:55px minmax(0,1fr) 16px;gap:9px;padding:12px}
  .api-signature-card{grid-template-columns:1fr;padding:14px}
  .api-signature-card button{justify-self:start}
  .diagnostic-row{padding:12px}

  .doc-table,.status-table{font-size:.78rem}
  .doc-table th,.doc-table td,.status-table th,.status-table td{padding:9px 10px}
  [data-scroll-region]::after{content:'Scroll →';position:sticky;right:8px;float:right;margin:5px 4px 5px 0;padding:3px 6px;border-radius:999px;background:rgba(17,23,34,.84);color:#fff;font-size:.58rem;font-weight:850;letter-spacing:.04em;pointer-events:none}
}

@media(max-width:480px){
  .reference-header h1,.product-masthead h1{font-size:clamp(2rem,11vw,3rem)}
  .reference-toolbar input,.package-api-search input{font-size:16px} /* prevents iOS zoom */
  .reference-filters{margin-inline:-2px}
  .reference-filters button{min-height:34px}
  .book-article-meta{align-items:flex-start;flex-direction:column}
  .release-detail-summary article{padding:18px}
  .release-asset-row .button{width:100%;justify-content:center}
  .doc-pager a,.book-pager a{min-width:0;overflow-wrap:anywhere}
}
'''
    CSS.write_text(text, encoding='utf-8')


def main():
    patched = patch_scroll_regions()
    add_css()
    print(f'v28: responsive/reference usability; scroll regions patched on {patched} pages')

if __name__ == '__main__':
    main()
