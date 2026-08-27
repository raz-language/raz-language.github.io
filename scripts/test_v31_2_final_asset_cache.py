#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

def need(ok: bool, message: str) -> None:
    if not ok:
        print("ERROR", message)
        raise SystemExit(1)

# The finalizer must be ordered after the API sharder because the sharder mutates site.js.
sync=(ROOT/'scripts/sync_site.py').read_text(encoding='utf-8')
need(sync.find('enhance_v31_1.py') < sync.find('enhance_v31_2.py'), 'final asset cache pass must run after API search sharding')

# Prove a late site.js mutation is reflected in HTML rather than merely checking today's snapshot.
with tempfile.TemporaryDirectory() as td:
    tmp=Path(td)/'site'
    (tmp/'assets').mkdir(parents=True)
    (tmp/'scripts').mkdir()
    shutil.copy2(ROOT/'scripts/enhance_v31_2.py', tmp/'scripts/enhance_v31_2.py')
    (tmp/'assets/styles.css').write_text('body{}\n',encoding='utf-8')
    (tmp/'assets/site.js').write_text('console.log(1);\n',encoding='utf-8')
    (tmp/'index.html').write_text('<link href="assets/styles.css?v=deadbeef"><script src="assets/site.js?v=deadbeef"></script>',encoding='utf-8')
    # Simulate the refresh-time late mutation that caused the CI failure.
    (tmp/'assets/site.js').write_text('console.log(2);\n',encoding='utf-8')
    subprocess.run([sys.executable, str(tmp/'scripts/enhance_v31_2.py')], cwd=tmp, check=True, stdout=subprocess.DEVNULL)
    html=(tmp/'index.html').read_text(encoding='utf-8')
    expected=hashlib.sha256((tmp/'assets/site.js').read_bytes()).hexdigest()[:12]
    need(f'site.js?v={expected}' in html, 'late site.js mutation did not receive final content digest')

subprocess.run([sys.executable, str(ROOT/'scripts/test_asset_cache_busting.py')], cwd=ROOT, check=True)
print('OK: final asset cache keys follow the actual post-enhancer asset bytes')
