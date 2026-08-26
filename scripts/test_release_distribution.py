#!/usr/bin/env python3
"""Regression checks for official Raz binary-release distribution surfaces."""
from pathlib import Path
import json
import re

ROOT = Path(__file__).resolve().parents[1]


def require(condition, message):
    if not condition:
        raise SystemExit(f"release distribution regression: {message}")


sync = (ROOT / "scripts" / "sync_site.py").read_text(encoding="utf-8")
require('"releases.json": "https://api.github.com/repos/raz-language/raz/releases"' in sync,
        "sync source must be raz-language/raz GitHub Releases")
require('https://api.github.com/repos/raz-language/installer/releases' not in sync,
        "installer repository must not be used as the stable release feed")

raw = json.loads((ROOT / "data" / "raw" / "releases.json").read_text(encoding="utf-8"))
require(raw, "offline snapshot must contain the published stable release")
latest = next((release for release in raw if not release.get("prerelease")), raw[0])
require(latest.get("tag_name") == "v1.0.0" or latest.get("tag_name"), "stable release must have a tag")
names = {asset.get("name") for asset in latest.get("assets", [])}
require(any(name and name.endswith(".msi") for name in names), "stable release must expose a Windows MSI")
require(any(name and "windows" in name and name.endswith(".zip") for name in names), "stable release must expose a Windows portable ZIP")
require(any(name and "linux" in name and name.endswith(".tar.gz") for name in names), "stable release must expose a Linux tarball")

site = json.loads((ROOT / "data" / "generated" / "site.json").read_text(encoding="utf-8"))
binary = site.get("binary_releases", {})
require(binary.get("published") is True, "generated site must report published binaries")
require(binary.get("source", {}).get("repository") == "raz-language/raz", "generated release source must identify raz-language/raz")
require((binary.get("latest") or {}).get("tag") == latest.get("tag_name"), "generated current stable tag must match release snapshot")

install = (ROOT / "install" / "index.html").read_text(encoding="utf-8")
releases = (ROOT / "releases" / "index.html").read_text(encoding="utf-8")
status = (ROOT / "status" / "index.html").read_text(encoding="utf-8")
combined = "\n".join([install, releases, status]).lower()
for forbidden in ["build from source", "source build path", "binary publication pending", "not yet published"]:
    require(forbidden not in combined, f'public install/release/status surfaces must not advertise stale state: "{forbidden}"')

require("Windows x64 Installer" in install, "install page must present the Windows installer")
require("RECOMMENDED" in install and ".msi" in install, "Windows MSI must be the recommended install path")
require("Portable ZIP" in install, "install page must present the Windows portable ZIP")
require("Linux x86-64 Toolchain" in install, "install page must present the Linux prebuilt toolchain")
require('data-platform-button="source"' not in install, "install platform selector must not expose a source-build tab")
require('data-platform-button="other"' in install, "install platform selector must expose a neutral Other-host view")
require("raz-language/raz" in releases and "CURRENT STABLE" in releases, "release page must identify the canonical repository and current stable release")
require("Official stable binaries are published." in status, "status page must reflect published stable binaries")

api_releases = json.loads((ROOT / "api" / "v1" / "releases.json").read_text(encoding="utf-8"))
require(api_releases and api_releases[0].get("tag") == latest.get("tag_name"), "public releases API must expose the stable release")

print("OK: official Raz release distribution is wired to raz-language/raz and exposes Windows/Linux binaries")
