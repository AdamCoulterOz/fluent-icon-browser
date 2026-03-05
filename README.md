# Fluent Icon Browser

Static browser UI for searching icons from:

- [microsoft/fluentui-system-icons](https://github.com/microsoft/fluentui-system-icons) (Fluent System)
- [microsoft/fluentui](https://github.com/microsoft/fluentui) `react-icons-mdl2` (Fabric/MDL2)

...with automatic index refresh and GitHub Pages hosting.

## What It Does

- Searches by icon name, description, and metaphors.
- Switches between icon sets (`Fluent System`, `Fabric MDL2`).
- Filters by variant (`regular`, `filled`, `color`) where applicable to the active set.
- Shows SVG previews sourced from CDN.
- Supports native size selection per variant in the modal panel.
- Copies/downloads the selected native-size SVG.
- Optional download-time transform for regular/filled icons to replace hardcoded fills with `currentColor`.
- Includes committed MDL2 metadata (`description` + `metaphors`) for all Fabric icons to improve search relevance.
- Auto-refreshes `icon-data.json` when upstream Fluent System or Fabric MDL2 icons change.
- Deploys the site to GitHub Pages from `main`.

## Local Development

### 1. Build index JSON directly from upstream assets/components

```bash
python generate-icon-data.py \
  --fluent-icons-dir /path/to/fluentui-system-icons/assets \
  --fabric-components-dir /path/to/fluentui/packages/react-icons-mdl2/src/components \
  --fabric-metadata fabric-mdl2-metadata.json \
  --fluent-upstream-sha <fluent-system-commit-sha> \
  --fabric-upstream-sha <fluentui-commit-sha> \
  --output icon-data.json
```

### Optional: regenerate Fabric metadata

```bash
python generate-fabric-metadata.py \
  --components-dir /path/to/fluentui/packages/react-icons-mdl2/src/components \
  --output fabric-mdl2-metadata.json
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
- Checks current upstream SHAs for:
  - `microsoft/fluentui-system-icons` (`main`)
  - `microsoft/fluentui` (`master`, for `react-icons-mdl2`)
- Rebuilds only when either upstream SHA changes (or `force_rebuild=true`).
- Pipeline:
  - sparse clone Fluent System `assets/`
  - sparse clone Fabric MDL2 component sources
  - run `generate-fabric-metadata.py`
  - run `generate-icon-data.py`
  - commit updated `icon-data.json` + `fabric-mdl2-metadata.json` + `.upstream-sha` + `.upstream-fabric-sha`

`icon-data.json` stores both icon sets:
- Fluent entries use CDN URLs to upstream SVG files.
- Fabric entries include parsed SVG payloads and source links to upstream MDL2 component files.

### `.github/workflows/deploy-pages.yml`

- Runs on push to `main`.
- Publishes static files (`index.html`, `style.css`, `script.js`, `icons/`, `icon-data.json`) to GitHub Pages.

## Repository Layout

- `index.html`, `style.css`, `script.js`: static UI.
- `process.py`: optional transform/consolidation script (not used by CI sync).
- `generate-icon-data.py`: generates browser index (`icon-data.json`) for both icon sets.
- `generate-fabric-metadata.py`: generates/maintains `fabric-mdl2-metadata.json` (`id`, `name`, `description`, `metaphors`) for all Fabric icons.
- `fabric-mdl2-metadata.json`: committed metadata used to enrich Fabric icon search.
- `icons/`: small UI glyph assets for modal action buttons.
- `icon-data.json`: generated icon index served by the browser.
- `requirements.txt`: optional Python dependency for `process.py`.
- `serve.py`: local static file server.

## Notes

- This project consumes icon assets from Microsoft’s Fluent UI System Icons repo. Review their license/usage terms before redistribution in your own downstream projects.
