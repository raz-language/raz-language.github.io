#!/usr/bin/env python3
from pathlib import Path
import json,re
R=Path(__file__).resolve().parents[1]
cli=(R/'cli/index.html').read_text(); con=(R/'contribute/index.html').read_text(); api=json.loads((R/'api/v1/cli.json').read_text())
assert 'data-cli-search' in cli and 'data-cli-command' in cli
assert 'Canonical CLI docs' in cli and 'docs/CLI.md' in cli
assert len(api['commands']) >= 30
names={x['name'] for x in api['commands']}
for n in ['build','run','test','install','publish','bindgen','c-header','forge','llvm','diagnostics']:
    assert n in names and f'id="{n}"' in cli
assert 'tools/sync-embedded-components.py' in con and 'tools/check-embedded-components.py' in con
assert 'cmake --preset debug' in con and 'ctest --preset debug' in con
assert 'Language behavior belongs in Raz' in con
search=json.loads((R/'assets/search-core.json').read_text())
for q in ['raz build','raz install','raz bindgen']:
    assert any(i.get('qualified_name')==q for i in search),q
stage=(R/'scripts/stage_site.py').read_text();assert '"cli"' in stage and '"contribute"' in stage
for wf in ['validate.yml','deploy-pages.yml']:
    t=(R/'.github/workflows'/wf).read_text();assert 'test_v30_developer_surfaces.py' in t
print('OK: v30 developer surfaces')
