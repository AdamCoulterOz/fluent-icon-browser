# Interface

## Purpose

`fluent-icon-browser` is a static, source-attributed icon index, deep-link browser, and client-side resolver published through GitHub Pages. It owns the browser experience and committed generated index, not upstream icon repositories, licences, or availability.

## Public Surface

- Site: `https://adamcoulteroz.github.io/fluent-icon-browser/`
- Stable selection URL: `?set=<key>&icon=<name>`
- Canonical set keys: `fluent`, `segoe`, `azure`, `flight`, `hashicorp`, `salesforce`, `aws`, `gcp`, and `redhat`.
- `fabric` is a compatibility alias for `segoe` while no canonical `fabric` set exists. A future key collision requires an explicit compatibility decision.
- The generated `sets` map supplies each collection's `label`, `shortLabel`, source context, `sources[]` provenance, and icon families. The browser renders collection selection from that map.
- When a collection has more than one source-supplied `icon.category`, the browser shows a Keel-native group selector. It combines with search and style filtering and resets when the collection changes. No group parameter is added to the stable `?set=<key>&icon=<name>` URL; collections without a multi-category source taxonomy do not show the selector.

The `icon` parameter identifies a visible canonical family. A known folded/non-canonical alias resolves and opens its canonical family while preserving the supplied stable URL; unknown names may fall back to relevant search. Selecting a canonical family updates the URL with `replaceState` so the current view remains shareable.

## Provenance Semantics

- A collection's `sources[]` entries expose attribution/provenance: label, reference, URL, pinned revision, and when supplied, licence name, licence URL, and content digest.
- The browser presents those source and licence URLs as visible external links.
- Published source boundaries and candidate status live in [SOURCES.md](SOURCES.md). Eligibility requires a deterministic official source boundary: a revisioned or stable per-icon URL, or an official archive with an entry descriptor and digest; unauthenticated client accessibility where runtime retrieval is owner-hosted; terms compatible with automated indexing, deep-linking/hotlinking, runtime retrieval, and user copy/download; and appropriate attribution, trademark, and no-endorsement treatment. Source metadata is attribution and provenance information, not a warranty of upstream availability or a legal-rights conclusion.
- Flight, HashiCorp Products, and Red Hat sources are commit-pinned and digest-bound by source locks. Flight is limited to generic concepts, excluding `Products` and `Services`, and its grouping behavior is unchanged. The separate `hashicorp` set contains only official `Products` marks, including Terraform, Vault, Packer, Nomad, and Consul; `Services` remains excluded. Canonical `?set=hashicorp&icon=<base>` links combine upstream `<base>`, `<base>-fill`, and `<base>-color` SVGs as regular, filled, and color variants. `<base>-fill-color` is retained only as a searchable alias, never a fourth visible variant. Red Hat is limited to `standard`, `ui`, and `microns`, excluding `social`.
- Azure is limited to the deterministic default public Portal core and extension-manifest surface. Its source SVGs are resolved lazily from public sources; the repository and Pages artifact contain no Azure SVG payloads. Colour filtering is capability-based: any regular, filled, or color variant whose descriptor has `preserveSourceColors` is colour-capable. The current generated observation is 1,216 colour-capable families out of 1,374; counts are not permanent contracts, and upstream variant keys and public deep links remain unchanged.
- Salesforce SLDS covers the approved `standard`, `action`, `doctype`, `custom`, and `utility` archive paths; these five genuine individual-SVG families total 1,780. The five `*-sprite` SVG/RTL sprite sheets remain excluded as generated support artifacts, and `Product` is not a sixth `@salesforce-ux/icons` category. The client verifies the official registry archive and selected entry SHA-256 values before extraction and sanitization; its CC BY-ND source capability disables `currentColor` and bounding-box output transforms.
- AWS Architecture Icons is published as canonical set `aws` for technical documentation and architecture diagrams. The current generated observation is 809 families across 45 source categories. The official AWS Architecture Icons ZIP is the source boundary; the archive and each selected entry are SHA-256 verified before client-side ZIP extraction and SVG sanitization. Only source descriptors and generated metadata are committed, with no upstream SVG payload or rehosting. Official Light/Dark exports resolve as theme alternatives inside one canonical family when they form exact terminal-name pairs at matching sizes, selected by `prefers-color-scheme`; former themed family names remain aliases. Its generated source categories use the existing group selector, and no source-transforming outputs are exposed.
- Google Cloud Console Icons is published as canonical set `gcp`. Sync derives the public route-map module surface from `https://console.cloud.google.com/p/routemapdata`, fetches the referenced public `www.gstatic.com` MicroUI/StandaloneUI modules, and retains only literal SVG templates. The current observation is 4,363 templates from 257 modules and 270 browseable cards: 99 reviewed `Resource Icons` families and 171 `Common UI` families; 535 source templates have no `data-icon-name` and retain a deterministic opaque metadata fallback. Resource names are reviewed source evidence, with same-style byte collisions kept as distinct deterministic families; exact retained SVG digests shared across module IDs become `Common UI`. Unclassified module-local templates and source-authored non-renderable templates stay in the source tree/manifest but are excluded from the catalogue. Replaced generated names remain aliases for `?set=gcp&icon=` links. Runtime sanitization retains only local-fragment `<use>` references so valid source templates remain previewable without admitting external SVG references. The route map does not enumerate the observed versioned core `OneCloudBarMicroUi`/`CloudConsoleWeb` resource library, and its URL is not discoverable without an authenticated Console bootstrap; it is outside the current deterministic source boundary. The resulting deterministic `gcp-console-icons/` source tree contains SVGs, a manifest, a source lock, and the required `REFERENTIAL-FAIR-USE.md` attribution/no-endorsement notice; no source JavaScript is retained. Pages deterministically packages that tree as same-origin `gcp-console-icons.zip`, whose archive and entry digests are verified before extraction and sanitization.

## Invariants

- The browser remains static-first: no frontend bundler, server runtime, or server-side icon API is required.
- `icon-data.json` remains committed and directly consumed by the static page.
- New federated collections commit metadata, index data, and source descriptors, never upstream SVG payloads. The deliberate exception is `gcp`: its validated SVG-only source tree and attribution/no-endorsement notice are committed so Pages can produce a same-origin archive for the public Google Cloud Console collection; raw Google source modules are never retained. Sync may temporarily download other official sources to inspect/index them, then discards the payloads; the client retrieves those icons from their source owner at runtime and renders them inline. The established Segoe component path retains extracted inline render data in the generated index while preserving source links; replacing that legacy representation with a source-owner runtime resolver is separate migration work.
- Deep-link query parameters are the public contract; DOM shape, internal adapters, normalizers, and workflow implementation are not.
- The Segoe set is the union of ordinary and branded MDL2 components, and branded icons retain the searchable `branded` tag.
- Azure's 105 legacy local Documents SVGs remain unimported and unpublished.
- Collection counts are generated-state observations, not permanent interface contracts.
- Google Cloud uses the bounded static-archive exception described above. It is not a general proxy, dynamic crawler, or a licence conclusion; only deterministic public route-map/module discovery, SVG extraction, and Pages packaging are in scope.

## Lifecycle and Side Effects

- The static page loads the committed index, renders the default set, then resolves an optional deep link.
- Runtime fetches commit-pinned source SVGs or digest-bound archive entries as needed. GCP fetches the same-origin Pages archive produced during deployment; all other browser and service-worker caching is local browser state and does not rehost upstream assets in the repository.
- Copy/download uses browser clipboard/download facilities. The optional output transforms apply to both actions where the source capability permits them; the bounding-box preference lasts only for the browser-tab session.
- Sync may regenerate and commit the index/source metadata; Pages deploys the committed static site after pushes, successful sync, and scheduled repair runs.

## Anti-Goals

- No ownership claim over upstream names, assets, licences, or service behaviour.
- No public indexing of a source until the documented source-boundary, client-access, terms, attribution, trademark, and no-endorsement eligibility checks have been deliberately resolved.
- No implemented local-only licensed-pack architecture.

## Agent Guidance

- Preserve the deep-link and `sources[]` semantics when changing the generated index or UI.
- Update this file and [SOURCES.md](SOURCES.md) when public set keys, source boundaries, provenance semantics, or lifecycle behaviour change.
