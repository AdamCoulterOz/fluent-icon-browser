# Interface

## Purpose

`fluent-icon-browser` is a static, source-attributed icon catalogue published through GitHub Pages. It owns the browser experience and committed generated index, not upstream icon repositories, licences, or availability.

## Public Surface

- Site: `https://adamcoulteroz.github.io/fluent-icon-browser/`
- Stable selection URL: `?set=<key>&icon=<name>`
- Canonical set keys: `fluent`, `segoe`, `azure`, `flight`, and `redhat`.
- `fabric` is a compatibility alias for `segoe` while no canonical `fabric` set exists. A future key collision requires an explicit compatibility decision.
- The generated `sets` map supplies each collection's `label`, `shortLabel`, source context, `sources[]` provenance, and icon families. The browser renders collection selection from that map.

The `icon` parameter identifies a visible canonical family. A folded/non-canonical icon name may fall back to a relevant family search. Selecting an icon updates the URL with `replaceState` so the current view remains shareable.

## Provenance Semantics

- A collection's `sources[]` entries expose attribution/provenance: label, reference, URL, pinned revision, and when supplied, licence name, licence URL, and content digest.
- The browser presents those source and licence URLs as visible external links.
- Published source boundaries and candidate status live in [SOURCES.md](SOURCES.md). Source metadata is attribution and provenance information, not a warranty of upstream availability or a legal-rights conclusion.
- Flight and Red Hat sources are commit-pinned and digest-bound by source locks. Flight is limited to generic concepts, excluding `Products` and `Services`; matched `-fill` entries are variants. Red Hat is limited to `standard`, `ui`, and `microns`, excluding `social`.
- Azure is limited to the deterministic default public Portal core and extension-manifest surface. Its source SVGs are resolved lazily from public sources; the repository and Pages artifact contain no Azure SVG payloads.

## Invariants

- The browser remains static-first: no frontend bundler, server runtime, or server-side icon API is required.
- `icon-data.json` remains committed and directly consumed by the static page.
- Deep-link query parameters are the public contract; DOM shape, internal adapters, normalizers, and workflow implementation are not.
- The Segoe set is the union of ordinary and branded MDL2 components, and branded icons retain the searchable `branded` tag.
- Azure's 105 legacy local Documents SVGs remain unimported and unpublished.
- Collection counts are generated-state observations, not permanent interface contracts.

## Lifecycle and Side Effects

- The static page loads the committed index, renders the default set, then resolves an optional deep link.
- Runtime fetches commit-pinned source SVGs as needed. Browser and service-worker caching is local browser state and does not rehost upstream assets in the repository.
- Copy/download uses browser clipboard/download facilities. The optional output transforms apply to both actions; the bounding-box preference lasts only for the browser-tab session.
- Sync may regenerate and commit the index/source metadata; Pages deploys the committed static site after pushes, successful sync, and scheduled repair runs.

## Anti-Goals

- No ownership claim over upstream names, assets, licences, or service behaviour.
- No public indexing of a source until its source boundary and public-catalogue rights have been deliberately resolved.
- No implemented local-only licensed-pack architecture.

## Agent Guidance

- Preserve the deep-link and `sources[]` semantics when changing the generated index or UI.
- Update this file and [SOURCES.md](SOURCES.md) when public set keys, source boundaries, provenance semantics, or lifecycle behaviour change.
