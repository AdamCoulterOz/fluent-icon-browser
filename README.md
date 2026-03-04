# Fluent Icon Browser

Static browser UI for searching icons from [microsoft/fluentui-system-icons](https://github.com/microsoft/fluentui-system-icons), with automatic index refresh and GitHub Pages hosting.

## What It Does

- Searches by icon name, description, and metaphors.
- Filters by variant (`regular`, `filled`, `color`).
- Shows SVG previews sourced from CDN.
- Supports native size selection per variant in the modal panel.
- Copies/downloads the selected native-size SVG.
- Optional download-time transform for regular/filled icons to replace hardcoded fills with `currentColor`.
- Auto-refreshes `icon-data.json` when upstream Fluent icons change.
- Deploys the site to GitHub Pages from `main`.

## Local Development

### 1. Build index JSON directly from upstream assets

```bash
python generate-icon-data.py \
  --icons-dir /path/to/fluentui-system-icons/assets \
  --upstream-sha <upstream-commit-sha> \
  --output icon-data.json
```

### 2. Run locally

```bash
python serve.py
```

### Optional: run transform/consolidation script

`process.py` is intentionally still in the repo for experimentation, but it is not used by the automated sync pipeline.

## Automation

### `.github/workflows/sync-fluent-icons.yml`

- Runs weekly (and manually via workflow dispatch).
- Checks current `microsoft/fluentui-system-icons` `main` commit SHA.
- Rebuilds only when upstream SHA changes (or `force_rebuild=true`).
- Pipeline:
  - sparse clone upstream `assets/`
  - run `generate-icon-data.py`
  - commit updated `icon-data.json` + `.upstream-sha`

`icon-data.json` stores metadata + CDN URLs to upstream SVG files (rather than embedding transformed SVG payloads).

### `.github/workflows/deploy-pages.yml`

- Runs on push to `main`.
- Publishes static files (`index.html`, `style.css`, `script.js`, `icons/`, `icon-data.json`) to GitHub Pages.

## Repository Layout

- `index.html`, `style.css`, `script.js`: static UI.
- `process.py`: optional transform/consolidation script (not used by CI sync).
- `generate-icon-data.py`: generates browser index (`icon-data.json`) with CDN URLs and available native sizes.
- `icons/`: small UI glyph assets for modal action buttons.
- `icon-data.json`: generated icon index served by the browser.
- `requirements.txt`: optional Python dependency for `process.py`.
- `serve.py`: local static file server.

## Notes

- This project consumes icon assets from Microsoft’s Fluent UI System Icons repo. Review their license/usage terms before redistribution in your own downstream projects.
