# Fluent Icon Browser

[Open the website](https://adamcoulteroz.github.io/fluent-icon-browser/)

Static browser UI for searching icons from:

- [microsoft/fluentui-system-icons](https://github.com/microsoft/fluentui-system-icons) (Fluent System)
- [microsoft/fluentui](https://github.com/microsoft/fluentui) `react-icons-mdl2` and `react-icons-mdl2-branded` (Fabric/MDL2)

...with automatic index refresh and GitHub Pages hosting.

## What It Does

- Searches by icon name, description, and metaphors.
- Switches between icon sets (`Fluent System`, `Fabric MDL2`).
- Filters by variant (`regular`, `filled`, `color`) where applicable to the active set.
- Shows SVG previews sourced from pinned upstream assets.
- Supports native size selection per variant in the modal panel.
- Copies/downloads the selected native-size SVG.
- Optional download-time transform for regular/filled icons to replace hardcoded fills with `currentColor`.
- Includes committed MDL2 metadata (`description` + `metaphors`) for all Fabric icons to improve search relevance.
- Tags every icon sourced from `react-icons-mdl2-branded` with the searchable `branded` metaphor.
- Auto-refreshes `icon-data.json` when upstream Fluent System or Fabric MDL2 icons change.
- Deploys the site to GitHub Pages from `main`.
- Supports installation as a PWA with offline access to the app shell and recently viewed icon SVG assets.

## Local Development

### 1. Build index JSON directly from upstream assets/components

```bash
python generate-icon-data.py \
  --fluent-icons-dir /path/to/fluentui-system-icons/assets \
  --fabric-components-dir /path/to/fluentui/packages/react-icons-mdl2/src/components \
  --fabric-branded-components-dir /path/to/fluentui/packages/react-icons-mdl2-branded/src/components \
  --fabric-metadata fabric-mdl2-metadata.json \
  --fluent-upstream-sha <fluent-system-commit-sha> \
  --fabric-upstream-sha <fluentui-commit-sha> \
  --output icon-data.json
```

### Optional: regenerate Fabric metadata

```bash
python generate-fabric-metadata.py \
  --components-dir /path/to/fluentui/packages/react-icons-mdl2/src/components \
  --branded-components-dir /path/to/fluentui/packages/react-icons-mdl2-branded/src/components \
  --output fabric-mdl2-metadata.json
```

### 2. Run locally

```bash
python serve.py
```

Install the site from a browser's install menu after opening it over HTTPS (or from `localhost`). The service worker caches the app shell during installation, then warms the icon cache in six-request batches when a new catalogue version is first opened. It resumes incomplete warm-ups on the next launch. Icon URLs are pinned to their upstream commit, so a changed icon receives a new cache entry while unchanged icons remain cached. When the installed app is opened, focused, or reconnects to the network, it checks the deployed build version and reloads once when an update is available.

### Optional: run transform/consolidation script

`process.py` is intentionally still in the repo for experimentation, but it is not used by the automated sync pipeline.

## Automation

### `.github/workflows/sync-fluent-icons.yml`

- Runs weekly (and manually via workflow dispatch).
- Checks current upstream SHAs for:
  - `microsoft/fluentui-system-icons` (`main`)
  - `microsoft/fluentui` (`master`, for `react-icons-mdl2` and `react-icons-mdl2-branded`)
- Rebuilds only when either upstream SHA changes (or `force_rebuild=true`).
- Pipeline:
  - sparse clone Fluent System `assets/`
  - sparse clone ordinary and branded Fabric MDL2 component sources
  - run `generate-fabric-metadata.py`
  - run `generate-icon-data.py`
  - commit updated `icon-data.json` + `fabric-mdl2-metadata.json` + `.upstream-sha` + `.upstream-fabric-sha`

`icon-data.json` stores both icon sets:
- Fluent entries use pinned raw GitHub URLs to upstream SVG files.
- Fabric entries include parsed SVG payloads and source links to ordinary or branded upstream MDL2 component files.

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

- This project consumes icon assets from Microsoft’s Fluent repositories. Branded MDL2 assets are governed by the Microsoft Fabric Assets License referenced by the upstream `react-icons-mdl2-branded` package; review all relevant license and usage terms before redistribution.
