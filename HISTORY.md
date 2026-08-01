# History

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
