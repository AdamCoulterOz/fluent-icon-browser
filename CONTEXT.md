# Project Context

## Overview

`fluent-icon-browser` is a static web app that indexes and browses:

- Fluent System icons from `microsoft/fluentui-system-icons`
- Fabric MDL2 icons from `microsoft/fluentui` (`react-icons-mdl2`)

The UI loads `icon-data.json` at runtime and provides:

- text search (name, description, metaphors)
- icon-set switching (Fluent/MDL2)
- compact top sticky header with single blue row containing title (`Icons`), set switcher, search, and segmented style filter (`regular`, `solid`, `color`)
  - current control order: brand (`logo + Icons`), search, icon set selector, style selector
  - search box is constrained to `max-width: 442px` and centered within the available search lane
  - search input and both segmented selectors share a unified control height (`32px`)
  - visible result count is shown as a compact numeric pill inside the search box (right side), replacing the previous standalone "Showing ... icons" line
  - selector widths are fixed (not elastic): icon set selector `125px`, style selector `134px`
  - style options are icon-only buttons with accessible labels: outlined (`regular`), filled (`solid`), and outlined-with-full tricolor fill (`color`)
  - style selection is optional (default unselected) and mutually exclusive; clicking the active option toggles back to no style filter
  - narrow behavior: title text collapses away and only the logo is shown, while logo + search always remain on the same row
  - spacing tuned for readability: slightly increased gap between brand and search in both desktop and compact layouts
  - top nav uses dedicated light/dark tokens (separate from generic accent color) for gradient background, segment contrast, and input/pill colors to reduce flat single-tone appearance and improve dark-mode legibility
  - in dark mode, the search field itself is also dark (with light text/placeholder) rather than white, to match the dark nav surface
  - result count pill uses a slightly offset blue accent so it reads as a distinct status badge from the surrounding nav background
  - nav controls are borderless externally (search field, count pill, and segmented-control outer stroke removed) while keeping internal vertical dividers inside segmented controls; search field corners are fully pill-rounded to match the selectors
  - search input includes a subtle leading magnifier icon inside the field, with text padding adjusted to preserve alignment
  - segmented option dividers use the nav background tone (not white) to blend with the bar and reduce visual noise
  - non-selected segmented-control backgrounds are slightly elevated from the nav bar (`--nav-segment-bg`) for clearer contrast without introducing heavy outlines
  - search count pill is inset by equal top/right spacing (`5px`) so it aligns cleanly with the search field's rounded edge
  - icon gallery is now dense/tile-based: labels hidden in grid, each card is a compact `60x60` square, and cards expose icon names via tooltip/aria label
  - gallery tiles now add inset breathing room: icon artwork remains `60x60`, while each card/tile is `90x90` (`15px` padding on all sides)
  - dense gallery uses fluid grid columns (`minmax(90px, 1fr)`) with centered `90x90` cards to avoid large trailing whitespace on wide rows
  - grid top padding now matches horizontal padding (`20px` desktop, `12px` mobile) so first row spacing mirrors side gutters
- header segmented controls have protected minimum widths for stable layout:
  - icon set selector: `min-width: 125px`, `height: 32px`
  - style filter selector: `min-width: 134px`, `height: 32px`
  - segmented button labels use explicit flex centering + fixed line-height to keep vertical alignment stable after runtime tab state updates (notably in Chrome)
- docked details panel with copy/download for SVG variants (replaces blocking overlay modal)
  - icon details are presented in a persistent bottom dock (non-blocking) across all screen sizes
  - panel stays open while browsing, so clicking different icons updates the same panel without forcing close/reopen
  - keeping the panel bottom-docked avoids horizontal grid reflow when opening details
  - opening/closing the docked panel applies grid spacing immediately (no animated padding transition) to avoid visible multi-step reflow/judder
  - selected icon card remains visually highlighted while the panel is open; clicking the same selected icon again toggles selection off and closes the panel
  - pressing `Esc` or using the panel close button dismisses the panel
  - panel internals are now split into a two-column desktop layout:
    - left column: icon title, description, and metaphor chips
    - right column: variant preview + controls, with a segmented variant switcher using the same visual language as the top nav controls
    - right-column control bar now includes, on one row: variant selector, size selector, `currentColor` toggle icon, copy, and download buttons
    - panel size selector uses a dedicated icon asset (`icons/chevron_down_regular.svg`) for a consistent down-chevron indicator and stable right padding
    - panel selected states for variant/currentColor now rely on solid fill contrast (no inset "ring" treatment)
    - copy/download buttons use a distinct warm CTA palette (orange family) to stand apart from the blue selection controls
    - panel variant selector dividers use a solid mid-tone blend (between active and inactive surfaces) so divider contrast stays consistent without looking too dark
    - panel preview column keeps a subtle top gradient that now resolves within the top section (currently ~30% of column height) instead of fading through the entire preview area
    - panel controls now use dedicated control-surface tokens; dark mode slightly brightens unselected control backgrounds to improve contrast while keeping the same visual language
    - copy/download controls are grouped in a trailing action cluster with responsive separation from variant/size/currentColor controls (`clamp(8px, 5vw, 50px)`)
    - copy/download glyph styling is intentionally heavier/larger than before to balance visual weight against neighboring segmented controls
    - when an icon has no description text, the description line is hidden entirely (no placeholder sentence rendered)
    - when no metaphors are present for an icon, the metaphors section is omitted (no placeholder text rendered)
    - per-icon variant selector only shows variants that actually exist for the selected icon (no disabled/greyed options)
    - copy/download buttons are circular accent CTA controls with brief success/error feedback states
    - icon preview area is centered and uses the full available preview space without an extra background tile
  - on narrow layouts, the panel stacks to a single-column flow while preserving the same controls/content
    - compact stacked header condenses metadata into a single row (title + truncated inline description); metaphor tags are hidden there
  - panel styling now aligns with nav theming tokens (rounded pills, blue-accent segmented control, consistent light/dark treatment)
- per-variant native size selector in the details panel
- optional download-time `currentColor` transform for mono variants
- enriched Fabric search metadata (`description` + `metaphors`) for all 1,736 MDL2 icons
- performance improvements for large result sets:
  - icon metadata is loaded up front and the gallery mounts all cards once per set; subsequent search/style changes are applied as single-pass class/preview updates (no visible chunk-by-chunk transition)
  - search input is debounced and icons are pre-indexed per set for faster filtering
  - style mode toggles (`regular`/`solid`/`color`, plus unselected/no-filter state) update existing rendered cards in-place without rebuilding the grid

## Key Files

- `index.html`: page layout and modal structure.
- `style.css`: all styling, including dark mode behavior and icon action button masks.
- `script.js`: browser logic for loading/filtering/rendering icon data and modal actions.
- `process.py`: legacy/optional icon transform script (kept for reference, not used in CI pipeline).
- `generate-icon-data.py`: builds `icon-data.json` directly from upstream `assets` and emits CDN URLs + native sizes.
- `generate-fabric-metadata.py`: builds `fabric-mdl2-metadata.json` for all MDL2 icons (`id`, `name`, `description`, `metaphors`).
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

1. `generate-icon-data.py --fluent-icons-dir <upstream-assets> --fabric-components-dir <upstream-mdl2-components> --fabric-metadata fabric-mdl2-metadata.json --output icon-data.json`

### GitHub automation

- `.github/workflows/sync-fluent-icons.yml`
  - runs weekly + manual trigger
  - checks upstream SHAs for:
    - `microsoft/fluentui-system-icons` `main`
    - `microsoft/fluentui` `master` (MDL2 components)
  - only rebuilds when either SHA changed (or forced)
  - generates combined index from:
    - generated `fabric-mdl2-metadata.json` (committed)
    - upstream Fluent `assets` (CDN-linked SVG URLs)
    - upstream Fabric MDL2 component sources (parsed inline SVG + source links)
  - commits updated `icon-data.json`, `fabric-mdl2-metadata.json`, `.upstream-sha`, `.upstream-fabric-sha`
- `.github/workflows/deploy-pages.yml`
  - runs on pushes to `main`
  - deploys static site to GitHub Pages

## Current Decisions

- Repository should stay static-first (no bundler/build frontend stack).
- `icon-data.json` is committed so Pages can serve immediately.
- Sync workflow uses sparse checkout of upstream `assets/` for efficiency.
- Icon SVG payloads are loaded from CDN URLs pinned to upstream SHA instead of being embedded in `icon-data.json`.
- Fabric/MDL2 icons are sourced from upstream component definitions and stored as inline SVG in `icon-data.json` (with source links), because upstream raw SVG files are not published as a parallel asset folder.
- Fabric metadata is maintained in-repo and regenerated by script/workflow; manual overrides are defined in `generate-fabric-metadata.py`.
- UI can optionally rewrite regular/filled icon `fill` values to `currentColor` when downloading.
- Main page container is now full-width fluid (`100%`) rather than capped, to keep Chrome/Safari responsive behavior consistent across window sizes.
- Header has responsive breakpoints to avoid clipping and preserve selector usability:
  - `<=620px`: compact 2-row layout (`logo + search` on row 1, then both selectors together on row 2) so selector widths do not influence the search row width
    - on this compact row, both selector controls are center-aligned as a group
  - `<=480px`: same header structure is retained (only icon card grid density changes), so selectors remain on one row and do not stack vertically
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
