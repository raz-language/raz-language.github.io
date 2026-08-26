#!/usr/bin/env python3
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ORIGIN = "https://raz-language.github.io"

env = os.environ.copy()
env["RAZ_SITE_URL"] = ""
probe = subprocess.run(
    [sys.executable, "-c", "import scripts.enhance_v23 as m; print(m.SITE_ORIGIN)"],
    cwd=ROOT,
    env=env,
    check=True,
    text=True,
    stdout=subprocess.PIPE,
).stdout.strip()

if probe != ORIGIN:
    print(f"ERROR empty RAZ_SITE_URL resolved to {probe!r}, expected {ORIGIN!r}")
    raise SystemExit(1)
print("OK: empty RAZ_SITE_URL resolves to https://raz-language.github.io")
