# Raz website

Production static website and documentation frontend for the Raz programming language.

The public site is plain HTML, CSS, JavaScript, JSON, XML, and text. It has no application server, framework runtime, browser package manager, or runtime dependency on GitHub APIs. Canonical project data is synchronized at build time and emitted as a self-contained static artifact.

## Architecture

The website is source-driven. Changing project information is synchronized from the canonical Raz repositories rather than maintained as a second hand-written database.

Primary inputs include:

- `raz-language/raz` for language documentation, platform support, CLI documentation, compiler metadata, security policy, and stable GitHub Releases;
- `raz-language/packages` for the official registry, immutable package records, package manifests, READMEs, and package source APIs;
- `raz-language/installer` for nightly-channel publication state; and
- the remaining `raz-language` repositories for project/ecosystem links and contributor routing.

`data/raw/` contains the checked-in source snapshot used for deterministic offline generation. `data/generated/` contains normalized build data. Public machine-readable projections are emitted under `/api/v1/`.

The browser never resolves packages, release state, or documentation from GitHub directly. A deployed build is complete on its own.

## Public surfaces

The generator produces the main language and project surfaces together so navigation, metadata, search, and versioning stay consistent:

- learning material and The Raz Book;
- current and versioned language documentation;
- diagnostics, standard-library, and unified API reference pages;
- official package catalog, immutable package-version pages, and versioned package API documentation;
- installation and permanent release pages;
- CLI command reference;
- status, ecosystem, performance-methodology, About, and contribution pages;
- project news/feed output; and
- JSON APIs for releases, packages, package versions, documentation, CLI commands, status, search-adjacent data, and other generated catalogs.

Historical documentation is never silently replaced with newer source. When an immutable historical package source snapshot is unavailable, the corresponding route reports that state instead of presenting the latest API as historical documentation.

## Documentation synchronization

A refresh build mirrors Markdown referenced by the canonical Raz documentation index and renders stable local routes with:

- heading anchors and table-of-contents navigation;
- internal cross-document links;
- code blocks and tables;
- source provenance back to the canonical repository;
- previous/next navigation where appropriate;
- version switching; and
- inclusion in generated site search.

If an indexed document cannot be synchronized, the generator preserves a source fallback and reports the inconsistency through the source-audit data rather than fabricating content.

## Package registry model

The website is a read-only presentation of the official GitHub-controlled registry. Package resolution and publication authority remain in `raz-language/packages`.

Package pages are generated from registry metadata and synchronized source. Immutable versions receive permanent routes and exact-version install commands. Latest-version API trees are frozen under versioned documentation routes; older versions only expose source-derived API documentation when the matching immutable source snapshot is actually available.

## Release and installation model

Stable toolchain distribution is sourced from GitHub Releases on `raz-language/raz`. `/install/`, `/releases/`, `/status/`, and release APIs are generated from published artifacts.

Windows MSI is the normal Windows installation path. The Windows portable ZIP and Linux x86-64 tarball are also presented when published, together with checksums and release notes. Compiler bootstrap/build-from-source material remains developer documentation rather than the normal installation flow.

Published `RELEASE-NOTES.md` assets are preferred during refresh builds. A checked-in canonical release-era fallback can be used for deterministic offline rendering. Website validation checks that release notes are substantive and source-attributed, but does not require upstream release notes to follow a website-specific heading outline.

## Search

Global search is generated into content-hashed static shards and loaded only when the search interface is opened. Search records carry structured fields such as kind, name, namespace, and qualified name so exact symbols, diagnostic codes, package versions, and CLI commands can rank ahead of broad text matches.

Search is entirely client-side after deployment and requires no hosted search service.

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

Verify that generated output matches the checked-in snapshot:

```sh
python3 scripts/sync_site.py --offline --check
```

## Validation

Run the main validator with:

```sh
python3 scripts/validate.py
```

The validation suite checks structural HTML, metadata, duplicate IDs, unresolved Markdown placeholders, local links and fragments, accessibility contracts, package/version invariants, generated APIs, search cache integrity, responsive/reference layout contracts, release distribution, documentation versioning, deployment staging, and performance budgets.

Source inconsistencies are emitted as non-fatal warnings in `data/generated/source-audit.json` and `/api/v1/source-audit.json`. The website does not suppress or silently rewrite upstream discrepancies.

## Deployment staging

Create the public artifact with:

```sh
python3 scripts/stage_site.py --output _site
python3 scripts/validate.py --root _site
```

`_site` contains only deployable website assets and public generated data. Raw synchronization inputs, generator code, tests, and other development state are excluded.

## GitHub Pages

`.github/workflows/deploy-pages.yml` refreshes canonical data, regenerates the site, runs the regression suite, stages and revalidates `_site`, and publishes the artifact through GitHub Pages.

The deployment workflow is serialized so an older run cannot replace a newer successful build. Scheduled refreshes keep documentation, package, target, and release data current without creating a runtime dependency for visitors.

The default production origin is `https://raz-language.github.io`. Set `RAZ_SITE_URL` to change canonical URLs, Open Graph URLs, sitemap entries, and related generated metadata for a custom domain.

## Hosting notes

The project emits `_headers`, `_redirects`, and `vercel.json` for static hosts that support those conventions. GitHub Pages does not apply `_headers`; those files must not be treated as live GitHub Pages security headers.

High-resolution branding source files remain in the repository, while deployment staging ships optimized derivatives for the header, application icons, and social previews.

## Generator conventions

Website behavior should remain deterministic and source-derived:

- do not invent package popularity, download, benchmark, or support data;
- do not present current package APIs as historical release APIs;
- keep canonical-source inconsistencies visible until fixed upstream;
- add new generated surfaces to deployment staging and regression coverage in the same change;
- preserve stable public routes once published; and
- prefer reusable generator rules over hand-editing individual generated pages.

Durable architecture and operating instructions belong in this README. Release-by-release implementation history belongs in version control and release notes, not in the project overview.

## License and project

Raz is Apache-2.0 licensed. The language, compiler, packages, tooling, and website are developed in the open under the [`raz-language`](https://github.com/raz-language) GitHub organization.
