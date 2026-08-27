#!/usr/bin/env python3
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
html=(ROOT/'index.html').read_text(encoding='utf-8')
css=(ROOT/'assets/styles.css').read_text(encoding='utf-8')
assert 'class="hero hero-centered"' in html
assert 'hero-grid-centered' in html
assert 'hero-copy-centered' in html
assert 'class="hero-code"' not in html
assert 'Raz code example' not in html
assert '.hero-grid-centered{display:flex;grid-template-columns:none;justify-content:center;align-items:center;text-align:center}' in css
assert '.hero-copy-centered{width:min(100%,980px);margin-inline:auto;text-align:center}' in css
assert '.hero-copy-centered .hero-actions{justify-content:center}' in css
assert '.hero-copy-centered .trust-row{justify-content:center;max-width:760px;margin:42px auto 0}' in css
print('OK: homepage hero uses full-width centered geometry and has no code showcase')
