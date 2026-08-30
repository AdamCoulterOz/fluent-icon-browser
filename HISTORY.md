# History

## 2026-08-30: Generalize Coherent Icon Collections

- Replaced the generator's fixed two-set assembly with private collection descriptors while preserving the public `fluent` and `fabric` keys; added compatible `shortLabel` metadata for compact tabs.
- Changed the static browser to render its accessible set tabs from the generated `sets` map, including keyboard navigation for future approved collections.
- Recorded legacy Azure icons as blocked: no Azure asset, source, URL, or set is imported or published until provenance and licensing are verified.

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
