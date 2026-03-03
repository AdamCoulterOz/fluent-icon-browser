# Project Context

## Overview

`fluent-icon-browser` is a static web app that indexes and browses icons from `microsoft/fluentui-system-icons`.

The UI loads `icon-data.json` at runtime and provides:

- text search (name, description, metaphors)
- style filtering (`regular`, `filled`, `color`)
- modal preview with copy/download for SVG variants

## Key Files

- `index.html`: page layout and modal structure.
- `style.css`: all styling, including dark mode behavior and icon action button masks.
- `script.js`: browser logic for loading/filtering/rendering icon data and modal actions.
- `process.py`: consolidates raw upstream assets into normalized per-icon SVG variants.
- `generate-icon-data.py`: builds `icon-data.json` from consolidated icon folders.
- `icon-data.json`: generated index consumed by the frontend.
- `.upstream-sha`: last synced upstream commit SHA (written by automation).

## Build + Sync Pipeline

### Local build flow

1. `process.py --input-dir <upstream-assets> --output-dir consolidated`
2. `generate-icon-data.py --icons-dir consolidated --output icon-data.json`

### GitHub automation

- `.github/workflows/sync-fluent-icons.yml`
  - runs weekly + manual trigger
  - checks upstream SHA for `microsoft/fluentui-system-icons` `main`
  - only rebuilds when SHA changed (or forced)
  - commits updated `icon-data.json` and `.upstream-sha`
- `.github/workflows/deploy-pages.yml`
  - runs on pushes to `main`
  - deploys static site to GitHub Pages

## Current Decisions

- Repository should stay static-first (no bundler/build frontend stack).
- `icon-data.json` is committed so Pages can serve immediately.
- Sync workflow uses sparse checkout of upstream `assets/` for efficiency.

## Open Questions / Ambiguities

- Whether to keep generated `consolidated/` artifacts out of git permanently (currently assumed: do not commit).
