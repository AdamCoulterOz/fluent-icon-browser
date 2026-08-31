# History

## 2026-09-01: Consolidate Shared Google Cloud Console UI Templates

- Folded GCP catalogue entries into a `Common UI` group only when their retained SVG SHA-256 is shared across more than one source module. The SVG source tree, manifest, source lock, and Pages ZIP contract remain complete and unchanged; module-local duplicate names are not folded.
- Common cards use a digest-bound canonical family and retain every replaced per-module family id as a deep-link alias.
- Excluded 514 source-authored empty SVG templates from browsing while retaining them as source evidence. Preserved valid local SVG `<use>` references through sanitization after finding that their previous removal blanked one retained icon.

## 2026-09-01: Merge AWS Theme Source Variants

- Merged official AWS Architecture Icon Light/Dark exports into their semantic canonical families, including paired terminal-name service exports such as AWS Marketplace, using generic per-size theme descriptors selected by `prefers-color-scheme`. The terminal-name normalization requires an exact Light/Dark pair at every matching size. Former themed AWS names remain aliases, and the generated observation is now 809 families across 45 source categories.
- Preserved archive and entry digest verification, client-side extraction/sanitization, and unthemed source fallback; no upstream SVG payloads were added.

## 2026-09-01: Add Deterministic Google Cloud Console Discovery

- Added canonical `gcp` discovery from the public Console `routemapdata` index. The route map deterministically names the public gstatic MicroUI/StandaloneUI module surface, avoiding manual Console traversal and retaining no source JavaScript.
- The deliberate static-archive exception commits a validated SVG-only `gcp-console-icons/` tree with manifest, source lock, and the supplied `REFERENTIAL-FAIR-USE.md` notice. Pages creates `gcp-console-icons.zip` during deployment; the generated archive is not committed.
- The archive/entry-digest resolver contract is retained for browser extraction and sanitization. The notice provides requested attribution/no-endorsement language and is not recorded as a licence conclusion.

## 2026-08-31: Publish AWS Architecture Icons Collection

- Published canonical `aws` from the official AWS Architecture Icons ZIP for technical documentation and architecture diagrams, with 859 current families across 45 generated source categories.
- Documented archive and per-entry SHA-256 verification, client-side ZIP extraction/sanitization, no committed upstream SVG payloads, existing group-selector integration, and no source-transforming outputs; Google Cloud remains unindexed because its current owner archives lack browser CORS access and no qualifying mirror exists.

## 2026-08-31: Document Group Filtering and Cloud Source Boundaries

- Accepted the browser contract for source-taxonomy groups: collections with more than one source-supplied `icon.category` show a Keel-native group selector that combines with search and style filtering and resets on collection switch. No group parameter was added to stable `?set=<key>&icon=<name>` links; collections without a multi-category taxonomy do not show it.
- Accepted Azure capability-based colour filtering: any regular, filled, or color variant with descriptor `preserveSourceColors` is colour-capable. The current generated observation is 1,216 colour-capable families out of 1,374; upstream variant keys and public deep links are unchanged, and the counts are not permanent contract values.
- Kept Google Cloud unindexed because its current owner category/core ZIPs have no ACAO and preflight 405; no qualifying Google-owned CORS mirror was found, and build-time indexing alone cannot make browser extraction work.

## 2026-08-31: Include Salesforce Utility Artwork

- Accepted the Salesforce generated-state refresh: the published `standard`, `action`, `doctype`, `custom`, and `utility` individual-SVG families total 1,780.
- Kept the five `*-sprite` SVG/RTL sprite sheets excluded as generated support artifacts; `Product` is not a sixth `@salesforce-ux/icons` category.
- Preserved CC BY-ND 4.0, verified archive and entry digests, no source-transforming output, and no-rehosting semantics.

## 2026-08-31: Refresh Vendored Keel Assets

- Accepted the Keel `v0.4.4` vendor refresh: `keel.css` is sourced from the official tag by `update-keel.sh`, and its asset revision/cache advances with bundle updates.

## 2026-08-31: Theme-Adapt Monochrome Source Previews

- Replaced the Salesforce contrast tile with generic `previewThemeColor` metadata. Light-only Salesforce artwork now previews as black in light mode and white in dark mode, with no preview background; the verified runtime, copy, and download source bytes remain unchanged.
- Applied the same preview-only contract to pure-black HashiCorp Products `color` variants. Inline SVG previews use theme `currentColor`; owner-hosted SVG image previews remain black in light mode and invert white in dark mode. Multi-colour artwork remains source-coloured.
- Kept named HashiCorp fill/color aliases searchable and deep-linkable through their canonical product-family links rather than exposing additional canonical icons.
- Moved the collection selector onto Keel's `keel-select` primitive and advanced revisioned frontend assets with the `fluent-icon-browser-v12` app-shell cache.

## 2026-08-31: Add Salesforce SLDS Archive Collection

- Added the canonical `salesforce` collection from the official `@salesforce-ux/icons` 10.17.0 registry archive under CC BY-ND 4.0, covering the then-approved `standard`, `action`, `doctype`, and `custom` artwork with first-party MuleSoft; `utility` was excluded at that stage.
- Locked the archive SHA-256 and every selected entry SHA-256. The browser fetches the owner-hosted archive, verifies both values before extraction/sanitization, and retains no upstream SVG payloads in the repository or Pages artifact.
- Preserved intrinsic source colours and disabled `currentColor` and bounding-box output transforms for this no-derivatives source. Stable links use `?set=salesforce&icon=<category>_<source-name>`.

## 2026-08-31: Add HashiCorp Product Marks

- Added the canonical `hashicorp` collection from the official Flight package's `Products` category, independently locked from the generic `flight` collection.
- Kept `flight` generic and unchanged: `Products` and `Services` remain excluded there. The new collection includes Terraform, Vault, Packer, Nomad, Consul, and the remaining approved HashiCorp product marks; `Services` remains excluded.
- Both collections use the same commit-pinned owner-hosted SVG URLs and separate digest-bound locks. No upstream SVG payloads are committed.
- Normalized each Products `<base>`, `<base>-fill`, and `<base>-color` source group into canonical `?set=hashicorp&icon=<base>` regular, filled, and color variants; retained `<base>-fill-color` only as a search alias rather than a fourth visible variant.

## 2026-08-31: Publish Federated Technology Icon Catalogue Provenance

- Documented the additive `flight` and `redhat` collections alongside Fluent, Segoe, and Azure, with generalized visible `sources[]` attribution/provenance and source/licence links.
- Recorded commit-pinned, digest-bound Flight 5.1.0 (MPL-2.0; generic concepts only, `Products`/`Services` excluded, matched `-fill` pairs as variants) and Red Hat 2.3.1 (CC BY 4.0; `standard`/`ui`/`microns` only, `social` excluded) source boundaries. No new SVG payloads are committed.
- Replaced the growing set-tab row with a scalable native collection picker driven by generated `shortLabel` values, kept full source/licence attribution visible below the header, and advanced the PWA app-shell cache so installed clients receive the picker UI.
- Added the source registry and held cloud/vendor/logo/social/security candidates outside public indexing until they have a deterministic official source boundary, unauthenticated CORS client access, compatible terms for automated indexing/deep links/runtime retrieval/user copy-download, and appropriate attribution, trademark, and no-endorsement treatment. No rehosting is recorded separately as an implementation invariant; a local-only licensed-pack architecture remains unimplemented.

## 2026-08-31: Preserve Intrinsic Azure Artwork Colours

- Fixed Azure extension-manifest artwork being flattened into monochrome silhouettes in dark mode when its source variant was labelled `regular`.
- Added deterministic per-variant paint analysis for chromatic colours, multiple paints, gradients, and patterns, plus locked public Portal Base.Images palette materialization for the source SVG classes that use it; the descriptor-only index and upstream regular/filled/color taxonomy remain unchanged.
- Applied the generated preservation metadata consistently to gallery and detail previews; copy/download source resolution and stable deep links are unchanged.

## 2026-08-31: Harden Azure Sync Source-Lock Handoff

- Kept the initial Portal probe's drift and count gates against the committed Azure source lock.
- Made the subsequent full index generation reuse that fresh validated temporary lock, avoiding a second lookup of an old RequireConfig URL during a Portal deployment transition.
- When Portal advertises a RequireConfig that disappears with `403`/`404` before the initial probe can fetch it, fall back to the complete strictly validated prior source snapshot; never combine a prior RequireConfig with new bootstrap manifests, and continue to fetch, parse, and count-gate every locked asset.

## 2026-08-31: Reconcile Legacy Azure Artwork Without Importing It

- Audited all 105 local legacy SVGs as read-only: none exactly matches a canonical generated-source hash; reconciliation found 23 exact-name metadata counterparts, 28 high-confidence renamed counterparts, 43 ambiguous items, and 11 initially absent metadata candidates.
- Classified the absent candidates against existing Azure, Marketplace, and shell surfaces. The bounded future discovery gaps are Marketplace catalogue image metadata and the embedded-Entra App registrations inner-blade asset mapping; no deterministic public revisioned Entra mapping is yet established, so this did not broaden the default source boundary or import any legacy asset.

## 2026-08-31: Add Bounded Azure Portal Remote Sources

- Published the additive `azure` collection alongside `fluent` and `segoe`; `fabric` remains a compatibility alias to `segoe` while no direct `fabric` set exists.
- Added current generated-state evidence of 1,374 Azure families from 342 core families and 1,032 default extension-manifest families, with 1,400 unique SVG descriptors.
- Defined digest-bound `remoteSource` descriptors and lazy, no-eval browser resolution from public CORS Microsoft Portal sources; Azure SVG payloads remain absent from the repository and Pages artifact.
- Bounded discovery to the deterministic default public Portal surface and kept the 105 legacy Documents SVGs unimported/unpublished. Future Microsoft product adapters remain open work.

## 2026-08-30: Rename the MDL2 Collection to Segoe

- Renamed the published MDL2 collection from `fabric` to `segoe`, with full and compact labels both `Segoe`; source-package attribution is unchanged.
- Added the generated `fabric` compatibility alias for existing deep links. Direct set keys take precedence over aliases, so any future `fabric` collection needs an explicit compatibility decision.

## 2026-08-30: Generalize Coherent Icon Collections

- Replaced the generator's fixed two-set assembly with private collection descriptors while preserving the public `fluent` and `fabric` keys; added compatible `shortLabel` metadata for compact tabs.
- Changed the static browser to render its accessible set tabs from the generated `sets` map, including keyboard navigation for future approved collections.
- Recorded the then-current decision to block legacy Azure assets pending provenance and licensing; this was superseded by the bounded public Azure Portal remote-source architecture on 2026-08-31.

## 2026-08-28: Refine Keel Presentation and Search

- Took the design tokens from the keel package instead of restating them, vendoring `keel.css` from AdamCoulterOz/keel via `update-keel.sh`. The palette values are unchanged; the focus ring and the elevated shadows now come from keel's scales.
- Added a contextual × control inside the search field that clears active terms immediately while preserving the icon set and returning focus to search, and restored the intended `442px` desktop width clamp while retaining full-width compact behavior.

## 2026-08-09: Refine the App Mark

- Tightened the four-tile favicon/header composition by moving each unchanged tile `1.5` artboard units toward the centre while retaining the `24×24` canvas.
- Removed the enclosing favicon tile and outlined treatment, then uniformly expanded the four shared `n=3` inner tiles to the former outer `24×24` bounds as a filled blue mark on transparency.
- Rounded the four shared inner favicon/header tiles from Lamé `n=4` to `n=3` while retaining the `n=4` outer favicon silhouette, tile geometry, stroke weight, and action-blue identity.

## 2026-07-26: Include Branded Fabric MDL2 Components

- Expanded the Fabric MDL2 source boundary from `react-icons-mdl2` alone to the union of `react-icons-mdl2` and `react-icons-mdl2-branded`.
- Kept branded assets within the existing `fabric` set and added `branded` as a searchable metadata tag rather than introducing a separate public icon-set key.
- Preserved commit-pinned SVG source attribution to the owning ordinary or branded upstream package.

## 2026-07-09: Harden GitHub Pages Autonomous Deployment

- Updated GitHub-maintained workflow actions to current major versions after a Pages deployment failed under older action runtimes.
- Collapsed the Pages artifact build and deployment into a single workflow job so a deploy does not need a second hosted-runner allocation after the artifact has already been uploaded.
- Added a daily scheduled Pages deployment repair run so transient GitHub Pages or Actions failures can self-heal without a manual rerun.

## 2026-07-09: Add Icon Deep-Link Contract

- Added query-string deep links for selected icon views using `?set=<key>&icon=<name>`.
- Treat the deep-link shape as a stable public URL contract so external documentation can link directly to browsed icons.

## 2026-08-02: Align the Browser UI with Meridian Keel

- Adopted Meridian's Keel palette, Hanken Grotesk and Fira Code typography, radii, focus, motion, shadow, and layered surface tokens across the static browser.
- Recast the compact sticky header as the shared 64-pixel frosted navigation surface and aligned search, segmented controls, gallery cards, selected states, metadata pills, and the docked details panel with the same system light/dark theme.
- Preserved the dense icon catalogue, existing `Icons` identity, responsive layout, copy/download behavior, and stable `?set=<key>&icon=<name>` deep-link contract.

## 2026-08-02: Add static discovery and parent navigation

- Added canonical, keyword, social, crawler, and Schema.org metadata for the published icon browser.
- Added an honest JavaScript-disabled catalogue description while retaining client-side search and rendering as the interactive lifecycle.
- Added a persistent footer route back to the root Adam Coulter project index and included crawler files in the Pages artifact.

## 2026-08-09: Separate Preview and SVG Text Cache Semantics

- Stopped opaque cross-origin responses cached for icon image previews from satisfying readable SVG fetches used by copy and download actions.
- Made background icon warming request CORS-readable SVGs and advanced the cache generation so existing opaque entries are discarded after the service-worker update.

## 2026-08-09: Unify SVG Output Transformations

- Added adjacent `currentColor` and bounds toggles that apply the same transformations to both copied and downloaded SVGs.
- Made bounds opt-in and retained that preference for the browser-tab session, while keeping the grouped transparent `viewBox` path behavior when enabled.

## 2026-08-09: Simplify Preview Selection and Dismissal

- Replaced the native size selector with a themed, keyboard-accessible listbox whose selected and unselected states match the segmented controls.
- Removed the dedicated close control and made outside click, `Esc`, same-card toggling, and downward touch swipe the panel dismissal gestures; selecting another icon continues to update the open panel in place.

## 2026-08-09: Preserve Preview Configuration Visibility

- Made Copy and Download move into the compact title bar only when their presence would otherwise cause the preview toolbar to scroll.
- Kept configuration controls at the leading edge of any remaining overflow and exposed ellipsis-truncated icon names through the existing metadata popover.
