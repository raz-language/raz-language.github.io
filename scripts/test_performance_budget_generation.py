#!/usr/bin/env python3
"""Regression test for generated performance budgets.

The release enhancer is part of sync_site.py. It must not silently restore an
obsolete search-index ceiling after a canonical --refresh build.
"""
from pathlib import Path
import json
import re
import sys

ROOT = Path(__file__).resolve().parents[1]
ENHANCER = ROOT / "scripts" / "enhance_v12.py"
BUDGET = ROOT / "performance-budget.json"
EXPECTED_SEARCH_LIMIT = 1572864

text = ENHANCER.read_text(encoding="utf-8")
match = re.search(r"['\"]search_index_js_bytes['\"]\s*:\s*(\d+)", text)
if not match:
    raise SystemExit("ERROR: enhance_v12.py does not define search_index_js_bytes")
value = int(match.group(1))
if value != EXPECTED_SEARCH_LIMIT:
    raise SystemExit(
        f"ERROR: generated search-index budget is {value}; expected {EXPECTED_SEARCH_LIMIT}"
    )

budget = json.loads(BUDGET.read_text(encoding="utf-8"))
actual = int(budget["limits"]["search_index_js_bytes"])
if actual != EXPECTED_SEARCH_LIMIT:
    raise SystemExit(
        f"ERROR: checked-in search-index budget is {actual}; expected {EXPECTED_SEARCH_LIMIT}"
    )

print(f"OK: generated search-index budget remains {EXPECTED_SEARCH_LIMIT} bytes")
