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
- installer releases: GitHub Releases on `raz-language/installer`
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

The site deliberately distinguishes **Raz 1.0 language stability** from **prebuilt toolchain publication**. Download buttons are generated only from actual installer releases; when no qualified binary release exists, the site presents source-build instructions instead of a dead or invented download link.

## Canonical production URL

Set `RAZ_SITE_URL` during a production build to the public origin, for example the eventual Raz domain. The generator then adds canonical URLs and `og:url` metadata to every page, emits `sitemap.xml`, and advertises it from `robots.txt`. If the variable is unset, those origin-dependent files are omitted rather than guessing a domain.

The GitHub Pages workflow reads this from the repository variable `RAZ_SITE_URL`.

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
