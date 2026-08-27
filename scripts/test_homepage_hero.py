#!/usr/bin/env python3
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
t=(ROOT/'index.html').read_text(encoding='utf-8')
assert 'hero-grid-centered' in t
assert 'hero-copy-centered' in t
assert 'class="hero-code"' not in t
assert 'Raz code example' not in t
print('OK: homepage hero is centered and has no code showcase')
