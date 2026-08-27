# Raz website

Production-oriented static website and documentation frontend for the Raz programming language.

The deployed site is plain HTML, CSS, JavaScript, JSON, and text files. It has no application server, framework runtime, package manager, or browser-time dependency on GitHub APIs.

## Source-driven architecture

Changing public information is synchronized at build time from the canonical Raz repositories:

- package names, latest versions, owners, and descriptions: `raz-language/packages/search.txt`
- immutable package version/archive/checksum history: `raz-language/packages/index.txt`
- documentation index: `raz-language/raz/docs/README.md`
- canonical documentation Markdown: individual files referenced by that index
- qualified target matrix: `raz-language/raz/docs/PLATFORM-SUPPORT.md`
- stable toolchain releases and downloadable artifacts: GitHub Releases on `raz-language/raz`
- nightly publication state: `raz-language/installer/channels/nightly.txt`
- compiler repository metadata and security policy: `raz-language/raz`

`data/raw/` is the checked-in source snapshot used for deterministic offline builds. `data/generated/` is normalized generated data. The public machine-readable projection is emitted under `/api/v1/`.

## Documentation mirroring

`python3 scripts/sync_site.py --refresh` synchronizes every document referenced by the canonical Raz documentation index. Available Markdown is rendered into `/docs/reference/<document>/` with:

- a stable local URL;
- table-of-contents navigation;
- heading anchors;
- internal cross-document links;
- code blocks and tables;
- previous/next navigation;
- source provenance back to GitHub; and
- inclusion in site search.

If an indexed source document is unavailable, the docs portal keeps its GitHub source fallback rather than generating an empty or fabricated page.

## Package registry views

`/packages/` is built from the official registry. Every package page includes the latest version plus all immutable versions present in `index.txt`, their package-tree checksums, exact-version install commands, and links to the canonical `.dpk` records.

## Build

Render from the checked-in snapshot without network access:

```sh
python3 scripts/sync_site.py --offline
```

Refresh canonical repository data and render:

```sh
python3 scripts/sync_site.py --refresh
```

`GITHUB_TOKEN` is optional locally and recommended in CI to avoid public GitHub API limits.

Verify generated output is deterministic and current with the checked-in snapshot:

```sh
python3 scripts/sync_site.py --offline --check
python3 scripts/validate.py
```

## Validation

The validator checks more than file existence. It verifies:

- titles, descriptions, viewport metadata, language metadata, and one H1 per page;
- duplicate IDs;
- local links and local fragment anchors;
- image `alt` attributes;
- safe `target="_blank"` links;
- generated package/version invariants;
- generated documentation pages;
- public API JSON;
- `/.well-known/security.txt`;
- JavaScript syntax when Node is available; and
- required deploy assets.

Canonical-source inconsistencies are preserved as non-fatal warnings in `data/generated/source-audit.json` and `/api/v1/source-audit.json` rather than silently hidden by the website generator.

## Deployment staging

Create a clean public artifact that excludes build scripts and raw source snapshots:

```sh
python3 scripts/stage_site.py --output _site
python3 scripts/validate.py --root _site
```

The staged artifact contains only deployable site assets, generated HTML, `/api/v1/`, and public metadata files.

## GitHub Pages

`.github/workflows/deploy-pages.yml`:

1. refreshes canonical Raz data and documentation;
2. renders the static site;
3. validates the generated source tree;
4. stages a clean `_site` artifact;
5. validates the artifact again; and
6. deploys it to GitHub Pages.

A six-hour schedule keeps docs, packages, releases, and target information current without adding a runtime dependency to the public website.

## Publication semantics

The site treats GitHub Releases on `raz-language/raz` as the canonical stable toolchain distribution feed. `/install/`, `/releases/`, `/status/`, and `/api/v1/releases.json` are generated from real published assets. Windows MSI, Windows portable ZIP, Linux tarball, checksum, and release-note links appear only when those artifacts exist in the release feed. Compiler bootstrap instructions remain developer documentation rather than the normal installation path.

## Canonical production URL

The default production origin is `https://raz-language.github.io`. Generated pages carry canonical URLs, Open Graph URL/image metadata, and the build emits `sitemap.xml` plus the matching `robots.txt` declaration. `RAZ_SITE_URL` can override the default when the project moves to a custom domain without changing page-generation logic.

## Client search architecture

Global search is generated at build time as `assets/search-index.json` and is **not** loaded during ordinary page navigation. `assets/site.js` fetches the content-hashed index only when the search dialog is opened, then ranks exact titles, diagnostic codes, package names, commands, modules, symbols, descriptions, and keywords locally in the browser. The public site therefore keeps the complete source-derived search corpus without charging every page view for it.

The search dialog supports `Ctrl/Cmd+K`, `/`, Escape, arrow-key result navigation, and a keyboard focus loop. Search results and generated catalog counts use live-region semantics where appropriate.

## Production branding assets

High-resolution source artwork remains in the repository for design work, while deployment staging excludes those originals and ships optimized header, application-icon, and social-preview derivatives. This keeps the real Raz artwork while avoiding hundreds of kilobytes of unnecessary image transfer on ordinary pages.

## Documentation product surfaces

v7 adds two generated first-class references:

- `docs/diagnostics/` parses the canonical stable diagnostic index into a searchable code browser.
- `docs/stdlib/` parses the generated standard-library index into searchable layers, modules, and public API metadata.

Raz code blocks are highlighted by a tiny dependency-free lexer in `assets/site.js`; no client-side highlighting library or framework is shipped. A production `--refresh` build mirrors the full canonical Markdown inputs before rendering, while the checked-in offline snapshot remains deterministic.

### Source-audit behavior

The current checked-in source snapshot demonstrates why the audit layer exists: it preserves upstream inconsistencies as warnings instead of silently rewriting them. In addition to stale/missing documentation references, the canonical generated standard-library index currently declares 102 modules / 1,427 public items while its module table enumerates 103 modules / 1,447 items. The browser shows both declared and observed values until the canonical source is regenerated consistently.


## v8 learning experience

The learning surface is generated as **The Raz Book** from the canonical `raz/docs/GETTING-STARTED.md` document when a refresh is available. It provides 29 chapter pages, persistent local progress, previous/next navigation, specification cross-links, stable diagnostic links, copyable code examples, and a generated `/api/v1/book.json` index. The checked-in offline snapshot remains useful without network access and is replaced by the complete canonical chapter text during `--refresh`.


## v9 API reference

The standard-library surface is generated as a hierarchy of stable static pages. Every module gets a route under `docs/stdlib/<module path>/`; when the canonical generated library index carries item metadata, types, functions, constants, and methods also receive stable item pages. The checked-in offline snapshot seeds representative core/alloc/collections/std APIs so the feature can be reviewed without network access, while `python3 scripts/sync_site.py --refresh` expands the reference from `docs/STANDARD-LIBRARY.md`.

## v11 package API documentation

The official package registry is now treated as a documentation source as well as a release index. During `--refresh`, the generator reads each canonical `sources/<package>/` tree from `raz-language/packages`, caches its README, `raz.toml`, and `.rz` modules, then emits:

- `/packages/<package>/docs/` for package overview, manifest metadata, dependencies, and modules;
- `/packages/<package>/docs/module/<namespace>/` for source-derived module APIs;
- stable item pages for exported functions, structs, enums, traits, constants, and types;
- `/api/v1/package-docs.json` for the aggregate package-doc catalog; and
- `/api/v1/packages/<package>/index.json` for package-specific machine-readable documentation metadata.

The checked-in offline snapshot includes the canonical `json` package as a populated reference implementation while preserving stable documentation routes for every official registry package. Production refreshes expand the same static hierarchy from the current package source repository without requiring GitHub access in the browser.

Package README heading IDs remain source-derived. Website-owned package fragment IDs use a `package-` prefix (for example `#package-dependencies`) so generated navigation cannot collide with headings such as `# Dependencies` in synchronized README content. CI scans every generated package documentation page for duplicate IDs after each refresh.

## v12 release-quality hardening

The website now generates `/status/` from the canonical platform/release snapshot, publishes `/api/v1/status.json` and `/api/v1/versions.json`, and carries explicit performance budgets. Deployment staging includes `_headers`, `_redirects`, and `vercel.json` so hosts that support static configuration can apply CSP/security headers, cache policy, and compatibility redirects. GitHub Pages still serves the same static files; header configuration is naturally host-dependent.

Run the release checks with:

```text
python3 scripts/sync_site.py --offline --check
python3 scripts/validate.py
python3 scripts/check_performance.py
python3 scripts/stage_site.py --output _site
python3 scripts/validate.py --root _site
python3 scripts/check_performance.py --root _site
```

## Refresh-sensitive CI regressions

The build includes `scripts/test_sync_regressions.py` to cover failures that only
appear after a live canonical refresh. It verifies GitHub-compatible Markdown
heading anchors and Raz type-first constant extraction (`public const T NAME = ...`).
The deployment and validation workflows run this regression test before the full
site validator.


## v16 deployment budget semantics

The performance checker separates page/request cost from the size of the complete generated documentation corpus. `site.js`, CSS, the homepage, the search index, and every individual public file retain tight byte ceilings. The fully staged site uses a 64 MiB corpus-growth guardrail because canonical refresh can generate tens of megabytes of independent API/documentation pages; users never download that corpus as one request. Both the checked-in budget and `enhance_v12.py` are regression-tested so refresh cannot silently restore obsolete limits.


## v17 deployment queue hardening

GitHub Pages deployment now rejects stale workflow runs by comparing the workflow commit to the current `main` SHA both before the build and immediately before artifact upload. The Pages concurrency group no longer allows a delayed run to cancel a newer successful build. Main-branch pushes run the complete validation suite only once through `deploy-pages`; `validate-site` is reserved for pull requests, non-main branches, and manual validation.

## v18 package search fix

- Makes the package catalog visibly hide non-matching cards even when component display styles would otherwise override the HTML `hidden` attribute.
- Adds an explicit semantic `[hidden]` CSS rule and a package-specific filtered-out fallback class.
- Adds `scripts/test_package_search.py` to both validation and Pages deployment workflows so the search wiring cannot silently regress.

## Documentation versioning

`/docs/` and `/learn/book/` are the current-stable documentation surfaces. Stable language releases also receive frozen, directly navigable snapshots under `/docs/<major.minor>/` and `/learn/<major.minor>/book/`. Internal links inside a frozen snapshot remain inside that snapshot, while links to non-versioned project surfaces such as installation, packages, status, and the repository continue to resolve to the current project site.

`/api/v1/versions.json` advertises the current stable version and the current/frozen documentation routes. A version selector is rendered on documentation, reference, standard-library, diagnostics, API, and Book pages. While a frozen snapshot is byte-equivalent to the current stable documentation, it is marked `noindex,follow` to avoid duplicate search indexing; when a later stable line becomes current, historical snapshot indexing policy can be relaxed without changing its URLs.

## Package documentation product

Package overview and source-derived API pages share a single navigation model for overview, API documentation, dependencies, immutable versions, and canonical source. Package landing pages summarize module, public-API, and dependency counts. API landing pages provide local module/symbol filtering while preserving stable module and item URLs. The official GitHub registry remains authoritative; these pages are generated documentation and discovery views, not a second package database.

## Release publication and project news

Stable toolchain releases are sourced from GitHub Releases on `raz-language/raz`. The website does not maintain a second release database. Each synchronized GitHub release receives a permanent route under `/releases/<tag>/` containing the published artifacts, sizes, integrity digests when GitHub exposes them, and links back to the canonical release. `/releases/` remains the download/history index.

`/news/` is a durable publication surface rather than a development log. Release announcements are generated automatically from the canonical release feed and are exposed through `/news/feed.xml` and `/api/v1/news.json`. Future editorial entries should be limited to durable project updates such as migrations, security announcements, and major ecosystem changes; ordinary development activity belongs in GitHub.

## Search scaling model

Global search is client-side but does not preload its corpus. The generated index is split into two cache-versioned JSON shards:

- `assets/search-core.json` contains navigation, documentation, packages, diagnostics, modules, releases, and project pages;
- `assets/search-api.json` contains high-cardinality standard-library and package API symbol entries.

Opening search loads only the core shard. The API shard is fetched after the user begins a query, keeping ordinary pages and an unopened search dialog independent of API-corpus growth. Both shards have separate performance budgets and content-derived cache keys.

The GitHub Pages workflow reads this from the repository variable `RAZ_SITE_URL`. An unset or explicitly empty variable is treated identically and falls back to `https://raz-language.github.io`; release/news feeds and sitemap generation use the same origin resolver so CI cannot emit relative production URLs.

## Documentation version architecture

`/docs/` and `/learn/book/` are aliases for the current stable Raz documentation line. The current language version is read from generated canonical site data rather than hard-coded into the versioning enhancer. A frozen snapshot is published at `/docs/<major.minor>/` and `/learn/<major.minor>/book/`; older snapshot directories are preserved when the current stable line advances. The current-version duplicate snapshot is `noindex,follow`, while superseded historical snapshots become independently indexable. `/api/v1/versions.json` is the machine-readable version manifest used to describe the available documentation lines.

Release detail pages derive their documentation line from the release tag's `major.minor` version and fall back to the current stable documentation only when that line is not present in the version manifest.

## HTML and metadata integrity

The site validator treats malformed attribute names and invalid nested anchors/buttons as build failures in addition to checking links, fragments, IDs, metadata, accessibility basics, and generated data invariants. Indexable pages are required to self-canonicalize; frozen current-version duplicate documentation is the deliberate exception because it remains `noindex,follow` and canonicalizes to the current stable route.

Route-aware JSON-LD is emitted for public pages, with `TechArticle`, `SoftwareSourceCode`, `WebPage`, or `WebSite` selected by surface. Pages with visible breadcrumb navigation also receive matching `BreadcrumbList` structured data.

## Portable binary installation

The public install page follows the official release archive contract. Windows MSI remains the recommended installation. The Windows portable ZIP contains a single toolchain directory with `install.ps1` / `uninstall.ps1`; the Linux archive contains a single toolchain directory with `install.sh` / `uninstall.sh`. Linux's installer manages the toolchain below `${XDG_DATA_HOME:-~/.local/share}/raz` and command links in `~/.local/bin` without editing shell startup files.

## Page-opening hierarchy

The public site uses one visual system with page openings matched to the job of
the route rather than a universal hero template. The homepage retains its
bespoke hero; major onboarding surfaces use a marketing opening; documentation
and project entrances use a smaller section opening; package surfaces use a
dense product masthead with controls and metadata; and high-density reference
surfaces use compact breadcrumb/title headers so content begins quickly.

`enhance_v25.py` applies this hierarchy after generated content and versioned
snapshots exist, while `test_v25_layout_hierarchy.py` keeps current and frozen
routes consistent and verifies that package/diagnostic controls remain attached
to their intended product openings.
