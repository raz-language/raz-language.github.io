#!/usr/bin/env python3
from __future__ import annotations
import re
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
errors=[]
for page in ROOT.rglob('*.html'):
    if '_site' in page.relative_to(ROOT).parts: continue
    text=page.read_text(encoding='utf-8')
    for match in re.finditer(r'<button\b([^>]*)>', text, re.I):
        if not re.search(r'\btype=', match.group(1), re.I): errors.append(f'{page.relative_to(ROOT)}: button missing explicit type')
    for match in re.finditer(r'<table\b[^>]*>', text, re.I):
        if not re.match(r'\s*<caption\b', text[match.end():], re.I): errors.append(f'{page.relative_to(ROOT)}: table missing caption')
    if 'data-search-dialog' in text:
        if 'aria-modal="true"' not in text: errors.append(f'{page.relative_to(ROOT)}: search dialog missing aria-modal')
        if re.search(r'<input[^>]*data-site-search', text) and not re.search(r'<input[^>]*data-site-search[^>]*aria-label=', text): errors.append(f'{page.relative_to(ROOT)}: site search input missing aria-label')
    for attr in ('data-package-count','data-package-api-count','data-diagnostic-count','data-stdlib-count','data-stdlib-item-count'):
        if attr in text and not re.search(rf'{attr}[^>]*aria-live="polite"', text): errors.append(f'{page.relative_to(ROOT)}: {attr} missing aria-live')
if errors:
    for error in errors[:80]: print('ERROR',error)
    raise SystemExit(1)
print('OK: interactive controls, data tables, search dialogs, and dynamic counts meet the site accessibility contract')
