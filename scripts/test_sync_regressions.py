#!/usr/bin/env python3
"""Small generator regressions for canonical refresh-sensitive behavior."""
import importlib.util
from pathlib import Path
import tempfile

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("sync_site", ROOT / "scripts" / "sync_site.py")
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)

assert mod.heading_slug("2.6 Precedence and associativity") == "26-precedence-and-associativity"
assert mod.heading_slug("8.1 Absence and recoverable errors") == "81-absence-and-recoverable-errors"
assert mod.heading_slug("core::abi") == "coreabi"
assert mod.heading_slug("core::trait_object::trait_identity") == "coretrait_objecttrait_identity"

with tempfile.TemporaryDirectory() as tmp:
    old = mod.PACKAGE_DOC_RAW
    try:
        mod.PACKAGE_DOC_RAW = Path(tmp)
        pkg = Path(tmp) / "demo"
        (pkg / "src").mkdir(parents=True)
        (pkg / "src" / "frame.rz").write_text(
            "namespace demo::frame;\n"
            "public const u64 DATA = 0;\n"
            "public const u64 HEADERS = 1;\n"
            "public struct FrameView { u64 frame_type; }\n",
            encoding="utf-8",
        )
        doc = mod._package_source_doc("demo")
        symbols = doc["modules"][0]["symbols"]
        assert [x["name"] for x in symbols] == ["DATA", "HEADERS", "FrameView"]
        assert [x["slug"] for x in symbols] == ["const/data", "const/headers", "struct/frameview"]
    finally:
        mod.PACKAGE_DOC_RAW = old
print("OK: refresh-sensitive generator regression tests pass")
