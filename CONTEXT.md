# Project Context

## Overview

`fluent-icon-browser` is a static web app that indexes and browses:

- Fluent System icons from `microsoft/fluentui-system-icons`
- Fabric MDL2 icons from `microsoft/fluentui` (`react-icons-mdl2` and `react-icons-mdl2-branded`)

The UI loads `icon-data.json` at runtime and provides:

- text search (name, description, metaphors)
- icon-set switching (Fluent/MDL2)
- compact 64-pixel sticky frosted header using Meridian's Keel surface treatment, containing title (`Icons`), set switcher, search, and segmented style filter (`regular`, `solid`, `color`)
  - current control order: brand (`logo + Icons`), search, icon set selector, style selector
  - search box is constrained to `max-width: 442px` and centered within the available search lane
  - search input and both segmented selectors share a unified control height (`32px`)
  - visible result count is shown as a compact numeric pill inside the search box (right side), replacing the previous standalone "Showing ... icons" line
  - selector widths are fixed (not elastic): icon set selector `125px`, style selector `134px`
  - style options are icon-only buttons with accessible labels: outlined (`regular`), filled (`solid`), and outlined-with-full tricolor fill (`color`)
  - style selection is optional (default unselected) and mutually exclusive; clicking the active option toggles back to no style filter
  - narrow behavior: title text collapses away and only the logo is shown, while logo + search always remain on the same row
  - spacing tuned for readability: slightly increased gap between brand and search in both desktop and compact layouts
  - top navigation and controls use the exact Keel light/dark surface, border, text, accent, focus, radius, shadow, and motion tokens; the app follows `prefers-color-scheme` and does not persist a separate theme choice
  - the search field is borderless and tints the frosted header beneath it rather than painting an opaque card: a subtle transparent black tint in light mode and transparent white tint in dark mode, strengthened slightly on focus; its placeholder and magnifier share a contrast-adjusted neutral that is modestly darker in light mode and lighter in dark mode
  - result count pill uses a slightly offset blue accent so it reads as a distinct status badge from the surrounding nav background
  - nav controls are borderless externally (search field, count pill, and segmented-control outer stroke removed) while keeping internal vertical dividers inside segmented controls; search field corners are fully pill-rounded to match the selectors
  - search input includes a subtle leading magnifier icon inside the field, with text padding adjusted to preserve alignment
  - segmented option dividers use the nav background tone (not white) to blend with the bar and reduce visual noise
  - non-selected segmented-control backgrounds are slightly elevated from the nav bar (`--nav-segment-bg`) for clearer contrast without introducing heavy outlines; selected controls and gallery tiles share `--selection-bg` (`#dfe9ff` in light mode and the existing translucent blue in dark mode), while their labels, glyphs, and monochrome gallery artwork share `--selection-fg`; colour icon artwork is never recoloured
  - search count pill is inset by equal top/right spacing (`5px`) so it aligns cleanly with the search field's rounded edge
  - icon gallery is now dense/tile-based: labels hidden in grid, each card is a compact `60x60` square, and cards expose icon names via tooltip/aria label
  - gallery tiles now add inset breathing room: icon artwork remains `60x60`, while each card/tile is `90x90` (`15px` padding on all sides)
  - gallery tiles use maximally rounded `999px` squircle corners when `corner-shape` is supported, fall back to an 18px rounded square otherwise, and signal selection with the muted fill alone rather than a boundary treatment
  - dense gallery uses fluid grid columns (`minmax(90px, 1fr)`) with centered `90x90` cards to avoid large trailing whitespace on wide rows
  - grid top padding now matches horizontal padding (`20px` desktop, `12px` mobile) so first row spacing mirrors side gutters
  - the light-theme gallery canvas uses a slightly darker `#f7f7f9` base so borderless white tiles remain distinct; dark mode retains its existing base surface
- header segmented controls have protected minimum widths for stable layout:
  - icon set selector: `min-width: 125px`, `height: 32px`
  - style filter selector: `min-width: 134px`, `height: 32px`
  - segmented button labels use explicit flex centering + fixed line-height to keep vertical alignment stable after runtime tab state updates (notably in Chrome)
- horizontal toolbar overflow on both the header and details panel uses unpainted directional-chevron overlays plus 72px alpha-only content masks with eased opacity stops, keeping control boundaries inside the transparency transition instead of exposing a hard seam
- docked details panel with copy/download for SVG variants (replaces blocking overlay modal)
  - icon details are presented in a persistent bottom dock (non-blocking) across all screen sizes
  - the preview dock and compact title metadata popover use moderated 48px and 24px squircles when supported, while retaining their existing 18px and 12px rounded-corner fallbacks respectively; the compact header retains its full-width divider
  - panel stays open while browsing, so clicking different icons updates the same panel without forcing close/reopen
  - keeping the panel bottom-docked avoids horizontal grid reflow when opening details
  - opening/closing the docked panel applies grid spacing immediately (no animated padding transition) to avoid visible multi-step reflow/judder
  - selected icon card remains visually highlighted while the panel is open; clicking the same selected icon again toggles selection off and closes the panel
  - pressing `Esc`, clicking outside the panel, or swiping the panel downward on a touch screen dismisses it; touch swipes directly track the finger, settle back when cancelled, animate off-screen when accepted, and own their movement so the icon grid cannot scroll underneath; clicking a different icon updates the open panel in place
  - panel internals are now split into a two-column desktop layout:
    - left column: icon title, description, and metaphor chips; it retains its 42%-to-480px desktop share, but yields to a 160px minimum between the 600px compact-layout breakpoint and 740px viewport width so even the widest three-variant preview toolbar fits without scrolling before the compact collapse
    - right column: variant preview + controls, with a segmented variant switcher using the same visual language as the top nav controls
    - right-column control bar now includes, on one row: variant selector, size selector, `currentColor` toggle icon, copy, and download buttons; removing the redundant close control releases the toolbar's reserved trailing space
    - panel size selector is an accessible, divider-free custom listbox that opens directly below its pill control with a fast, reduced-motion-aware downward reveal; its selected value and option use the shared muted selection colours, while the chevron and unselected options use shared neutral control colours
    - preview variant and output-toggle selected states reuse the header style switcher's muted `--nav-segment-active-bg` surface and `--nav-segment-active-text` glyph colour, with no inset ring treatment
    - copy/download buttons use the shared Keel blue action accent so primary actions and selection controls follow one interaction language
    - `Use currentColor` and `Include bounding box` are adjacent pressed-state output toggles, ordered immediately after the size selector; both transformations apply equally to copied and downloaded SVGs; the current-colour control uses Fluent `Dark Theme 24 Filled`
    - bounding boxes are off by default and use the same 14px rounded-square geometry as the Regular style chooser, rendered as an explicit SVG stroke with compact 2px dashes; the setting is retained in `sessionStorage` while the browser tab remains open, including across icon changes and reloads
    - when bounds are enabled, copied and downloaded SVG markup groups the drawable artwork with a leading zero-opacity path matching the source `viewBox`; root definitions/metadata remain outside the bounds group
    - preview variant dividers and deselected variant/output-toggle glyphs reuse the header switcher's neutral `--nav-divider-color` and `--nav-segment-text` tokens rather than blue-tinted mixes
    - panel preview column uses a subtle Keel layered surface rather than an app-specific gradient
    - panel size and action controls retain dedicated control-surface tokens, while selector/toggle state colours share the header segmented-control tokens
    - copy/download controls are grouped in a trailing action cluster with responsive separation from variant/size/currentColor controls (`clamp(8px, 5vw, 50px)`)
    - copy/download glyph styling is intentionally heavier/larger than before to balance visual weight against neighboring segmented controls
    - when an icon has no description text, the description line is hidden entirely (no placeholder sentence rendered)
    - when no metaphors are present for an icon, the metaphors section is omitted (no placeholder text rendered)
    - metaphor tags use soft filled pills without outlines for a cleaner, lighter metadata treatment
    - metaphor tag pills now have a stronger dark-mode fill contrast so they remain legible against the docked panel background
    - per-icon variant selector only shows variants that actually exist for the selected icon (no disabled/greyed options)
    - copy/download buttons are circular accent CTA controls with brief success/error feedback states
    - icon preview area is centered and uses the full available preview space without an extra background tile
  - on narrow layouts, the panel stacks to a single-column flow while preserving the same controls/content
    - compact stacked header condenses metadata into a single row; when the complete preview toolbar would overflow, Copy and Download are promoted into the right side of this header so variant, size, and output toggles remain the first toolbar controls exposed
    - promoted actions make the title left-aligned and ellipsis-truncated as needed; a truncated title is included in the existing metadata popover even when the icon has no description or metaphor tags
    - without promoted actions, the compact title remains centred; titles with descriptions or metaphor tags continue to trigger the metadata popover
  - panel styling aligns with the same Keel rounded pills, blue-accent segmented controls, layered surfaces, and consistent light/dark treatment as the header
- per-variant themed size listbox in the details panel
- URL deep links for icon selection:
  - `?set=<key>&icon=<name>` switches to the matching icon set, filters to the icon, and opens the details panel
  - selecting an icon updates the current URL via `replaceState`, making the visible icon view copy-shareable
  - folded MDL2 variants fall back to name search so external links still land on the canonical visible icon family
- optional download-time `currentColor` transform for mono variants
- enriched Fabric search metadata (`description` + `metaphors`) for 1,985 unique MDL2 component names across the ordinary and branded packages
- every component supplied by `react-icons-mdl2-branded` contributes the searchable `branded` metaphor to its generated family
- performance improvements for large result sets:
  - icon metadata is loaded up front and the gallery mounts all cards once per set; subsequent search/style changes are applied as single-pass class/preview updates (no visible chunk-by-chunk transition)
  - search input is debounced and icons are pre-indexed per set for faster filtering
  - style mode toggles (`regular`/`solid`/`color`, plus unselected/no-filter state) update existing rendered cards in-place without rebuilding the grid

## Key Files

- `index.html`: page layout and modal structure.
- `style.css`: all styling, including dark mode behavior and icon action button masks.
- `script.js`: browser logic for loading/filtering/rendering icon data and modal actions.
- `process.py`: legacy/optional icon transform script (kept for reference, not used in CI pipeline).
- `generate-icon-data.py`: builds `icon-data.json` directly from upstream `assets` plus ordinary/branded MDL2 components and emits commit-pinned source URLs + native sizes.
- `generate-fabric-metadata.py`: builds `fabric-mdl2-metadata.json` for ordinary and branded MDL2 icons (`id`, `name`, `description`, `metaphors`).
- `fabric-mdl2-metadata.json`: committed metadata source for Fabric icon descriptions/metaphors.
- `generate-fabric-samples.py`: creates visual MDL2 review sheets (10x10 icon grids) for human-in-the-loop metadata QA.
- `samples/fabric-grids/batch-0001-metadata-draft.json`: trial metadata draft for the first 100 MDL2 icons from grid review, now including:
  - `literalDescription` (what is visually depicted)
  - `semanticDescription` (intended usage meaning)
  - `description` (combined literal + semantic, compatibility field)
- `icon-data.json`: generated index consumed by the frontend.
- `.upstream-sha`: last synced Fluent System upstream commit SHA.
- `.upstream-fabric-sha`: last synced Fluent/Fabric upstream commit SHA.

## Build + Sync Pipeline

### Local build flow

1. `generate-icon-data.py --fluent-icons-dir <upstream-assets> --fabric-components-dir <upstream-mdl2-components> --fabric-branded-components-dir <upstream-branded-mdl2-components> --fabric-metadata fabric-mdl2-metadata.json --output icon-data.json`

### GitHub automation

- `.github/workflows/sync-fluent-icons.yml`
  - runs weekly + manual trigger
  - checks upstream SHAs for:
    - `microsoft/fluentui-system-icons` `main`
    - `microsoft/fluentui` `master` (MDL2 components)
  - only rebuilds when either SHA changed (or forced)
  - generates combined index from:
    - generated `fabric-mdl2-metadata.json` (committed)
    - upstream Fluent `assets` (raw GitHub SVG URLs pinned to upstream SHA)
    - upstream ordinary and branded Fabric MDL2 component sources (parsed inline SVG + source links)
  - commits updated `icon-data.json`, `fabric-mdl2-metadata.json`, `.upstream-sha`, `.upstream-fabric-sha`
- `.github/workflows/deploy-pages.yml`
  - runs on pushes to `main`
  - runs after successful `Sync Icon Indexes` completions on `main`
  - runs daily as a repair path for transient GitHub Pages or Actions failures
  - checks out `main` directly so scheduled and workflow-run deployments publish the current committed site state
  - builds and deploys in a single job to avoid a second hosted-runner allocation between artifact upload and Pages deployment
  - deploys static site to GitHub Pages
  - public site URL: `https://adamcoulteroz.github.io/fluent-icon-browser/`

## Current Decisions

- Repository should stay static-first (no bundler/build frontend stack).
- The browser follows Meridian's Keel design language while retaining its dense gallery and icon-specific interaction model: Hanken Grotesk for interface copy, Fira Code for numeric/status content, a 64-pixel frosted header, neutral layered surfaces, blue action accents, 10/12/18-pixel radii, and shared system light/dark tokens.
- The favicon/app mark uses the base action blue (`#0B5FFF`) for an exact `nX=4`, `nY=4` Lamé superellipse containing four compact outlined `n=4` superellipses. The curves follow Squircle Portal's default 64-segment sampling and two-decimal coordinate precision; the inner tiles remain `7×7` with a `1.5` stroke for 16px legibility. Favicon URLs carry a revision query when the artwork changes to avoid stale browser caches. The page header reuses the same sampled inner path without the outer tile and fills it with the theme's current action blue (`--accent`).
- `icon-data.json` is committed so Pages can serve immediately.
- Sync workflow uses sparse checkout of upstream `assets/` for efficiency.
- Fluent icon SVG payloads are loaded from `raw.githubusercontent.com` URLs pinned to upstream SHA instead of being embedded in `icon-data.json`.
- The service worker may retain opaque cross-origin SVG responses for image previews, but copy/download fetches require readable CORS responses; opaque cache entries are bypassed and replaced for those requests, and background cache warming explicitly requests CORS-readable SVGs.
- Fluent preview/download URLs intentionally avoid jsDelivr because browser image requests for some pinned SVG assets returned intermittent `403` responses.
- Fabric/MDL2 icons are sourced from both upstream component packages and stored as inline SVG in `icon-data.json` (with source links), because upstream raw SVG files are not published as a parallel asset folder.
- Branded MDL2 components remain part of the `fabric` icon set rather than a separate UI set; `branded` is a searchable metaphor/tag and the upstream branded-assets license remains applicable.
- Fabric metadata is maintained in-repo and regenerated by script/workflow; manual overrides are defined in `generate-fabric-metadata.py`.
- UI can optionally rewrite regular/filled icon `fill` values to `currentColor` when downloading.
- `?set=<key>&icon=<name>` is a public, stable deep-link contract for external docs and tools that need to link directly to an icon.
- `index.html`, `robots.txt`, and `sitemap.xml` expose canonical, social, structured, crawler, and no-JavaScript discovery content. The no-JavaScript surface describes the catalogue honestly; search and icon rendering remain client-side features.
- The normal page footer is fixed to the viewport bottom, links back to the parent project index at `https://adamcoulteroz.github.io/`, and exposes the GitHub repository link at its right edge; its two phrase groups wrap naturally when space requires, and a footer `ResizeObserver` keeps the details dock aligned above its rendered height.
- Main page container is now full-width fluid (`100%`) rather than capped, to keep Chrome/Safari responsive behavior consistent across window sizes.
- Header has responsive breakpoints to avoid clipping and preserve selector usability:
  - `<=620px`: compact 2-row layout (`logo + search` on row 1, then both selectors together on row 2) so selector widths do not influence the search row width
    - on this compact row, both selector controls are center-aligned as a group
  - `<=480px`: same header structure is retained (only icon card grid density changes), so selectors remain on one row and do not stack vertically
  - `<=290px`: only once the selectors' 267px intrinsic group width no longer fits, the second row switches from centred alignment to horizontal scrolling
- Sticky header behavior was hardened for cross-browser reliability:
  - removed root-level overflow clipping behavior that broke `position: sticky` in Chrome
  - `.top-bar` now includes `position: -webkit-sticky` + `position: sticky`
  - `.container` uses `overflow: visible` so sticky positioning is not constrained
  - `.icon-grid` has top padding (`20px` desktop, `12px` on mobile breakpoint) so the first icon row clears the pinned header and mirrors side gutters
- Legacy checkbox filters (including hide mirrored/inverse duplicates) were removed from the header in favor of compact segmented controls.
- Fabric normalization behavior:
  - mirrored variants are folded into one icon variant entry when they are naming mirrors (`*_mirrored*`)
  - numeric suffixes (`*8`, `*12`, etc.) are not implicitly treated as style variants, because MDL2 uses these inconsistently across icons
  - known MDL2 naming quirks are still explicitly overridden in `FABRIC_GROUP_OVERRIDES`, including `arrow_up_right8` mapped as a filled variant of `arrow_up_right`, `end_point`/`end_point_solid` mapped into the `flag` family as filled, `blocked_site_solid12` mapped as filled `blocked_site`, `double_chevron_*12` mapped as filled variants of the corresponding non-`8` chevrons, `parking_location` mapped as regular `parking`, and `pin_solid12` mapped as filled `pin`
  - semantic inverse pairs (token-swap style like `increase`/`decrease`, `left`/`right`, etc.) are annotated into normalized families
  - canonical family member keeps aliases for normalized members so search still finds hidden duplicates
  - non-canonical members are marked with `normalizedTo`

## Open Questions / Ambiguities

- Whether to keep generated `consolidated/` artifacts out of git permanently (currently assumed: do not commit).
- Whether to introduce synthetic transform variants (rotation/mirroring) as optional generated entries for missing directional forms, and how to label them clearly vs native upstream icons.
- How to expose exact legacy `font-icons-mdl2`-only glyphs without weakening the SVG copy/download contract.
- How to preserve separate same-size `Fill` and `Solid` artworks when both normalize to the current `filled` variant slot; `MailSolid` and `PinnedSolid` remain known collisions.
