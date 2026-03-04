# Project Context

## Overview

`fluent-icon-browser` is a static web app that indexes and browses icons from `microsoft/fluentui-system-icons`.

The UI loads `icon-data.json` at runtime and provides:

- text search (name, description, metaphors)
- style filtering (`regular`, `filled`, `color`)
- modal preview with copy/download for SVG variants
- per-variant native size selector in the modal
- optional download-time `currentColor` transform for mono variants

## Key Files

- `index.html`: page layout and modal structure.
- `style.css`: all styling, including dark mode behavior and icon action button masks.
- `script.js`: browser logic for loading/filtering/rendering icon data and modal actions.
- `process.py`: legacy/optional icon transform script (kept for reference, not used in CI pipeline).
- `generate-icon-data.py`: builds `icon-data.json` directly from upstream `assets` and emits CDN URLs + native sizes.
- `icon-data.json`: generated index consumed by the frontend.
- `.upstream-sha`: last synced upstream commit SHA (written by automation).

## Build + Sync Pipeline

### Local build flow

1. `generate-icon-data.py --icons-dir <upstream-assets> --upstream-sha <sha> --output icon-data.json`

### GitHub automation

- `.github/workflows/sync-fluent-icons.yml`
  - runs weekly + manual trigger
  - checks upstream SHA for `microsoft/fluentui-system-icons` `main`
  - only rebuilds when SHA changed (or forced)
  - generates index directly from upstream `assets` (no transform step)
  - commits updated `icon-data.json` and `.upstream-sha`
- `.github/workflows/deploy-pages.yml`
  - runs on pushes to `main`
  - deploys static site to GitHub Pages

## Current Decisions

- Repository should stay static-first (no bundler/build frontend stack).
- `icon-data.json` is committed so Pages can serve immediately.
- Sync workflow uses sparse checkout of upstream `assets/` for efficiency.
- Icon SVG payloads are loaded from CDN URLs pinned to upstream SHA instead of being embedded in `icon-data.json`.
- UI can optionally rewrite regular/filled icon `fill` values to `currentColor` when downloading.

## Open Questions / Ambiguities

- Whether to keep generated `consolidated/` artifacts out of git permanently (currently assumed: do not commit).
