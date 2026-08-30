# Fluent Icon Browser

[Open the website](https://adamcoulteroz.github.io/fluent-icon-browser/)

Static browser UI for searching icons from:

- [microsoft/fluentui-system-icons](https://github.com/microsoft/fluentui-system-icons) (Fluent System)
- [microsoft/fluentui](https://github.com/microsoft/fluentui) `react-icons-mdl2` and `react-icons-mdl2-branded` (Segoe)
- Public Microsoft Azure Portal core icon modules and default extension manifests (Azure)

...with automatic index refresh and GitHub Pages hosting.

## What It Does

- Searches by icon name, description, and metaphors.
- Switches between icon sets (`Fluent System`, `Segoe`, `Azure`).
- Renders collection tabs from the generated index, so a future approved collection can be added without a browser code fork.
- Filters by variant (`regular`, `filled`, `color`) where applicable to the active set.
- Shows SVG previews sourced from pinned upstream assets or resolved lazily from public Microsoft Azure Portal sources.
- Supports native size selection per variant in the modal panel.
- Copies/downloads the selected native-size SVG.
- Optional download-time transform for regular/filled icons to replace hardcoded fills with `currentColor`.
- Includes committed MDL2 metadata (`description` + `metaphors`) for all Segoe icons to improve search relevance.
- Tags every icon sourced from `react-icons-mdl2-branded` with the searchable `branded` metaphor.
- Auto-refreshes `icon-data.json` when upstream Fluent System, Segoe, or Azure Portal source indexes change.
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

The Azure collection is enabled by supplying an Azure source lock produced by `azure_portal_icons.py`:

```bash
python azure_portal_icons.py \
  --source-lock .tmp/azure-portal-source.json \
  --previous-source-lock .upstream-azure-portal.json
python generate-icon-data.py ... \
  --azure-source-lock .tmp/azure-portal-source.json \
  --azure-previous-source-lock .upstream-azure-portal.json
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

Install the site from a browser's install menu after opening it over HTTPS (or from `localhost`). The service worker caches the app shell during installation, then warms the icon cache with CORS-readable SVG responses in 60-request batches when a new catalogue version is first opened. It resumes incomplete warm-ups on the next launch. Image previews may also cache opaque responses, but those entries are never reused for copy/download requests that need readable SVG text. Icon URLs are pinned to their upstream commit, so a changed icon receives a new cache entry while unchanged icons remain cached. When the installed app is opened, focused, or reconnects to the network, it checks the deployed build version and reloads once when an update is available.

### Optional: run transform/consolidation script

`process.py` is intentionally still in the repo for experimentation, but it is not used by the automated sync pipeline.

## Automation

### `.github/workflows/sync-fluent-icons.yml`

- Runs weekly (and manually via workflow dispatch).
- Checks current upstream SHAs for:
  - `microsoft/fluentui-system-icons` (`main`)
  - `microsoft/fluentui` (`master`, for `react-icons-mdl2` and `react-icons-mdl2-branded`)
- Probes the public Azure Portal bootstrap, RequireConfig/dependency tree, and default extension manifests; schema drift or a collapsed count fails the run.
- Rebuilds when either upstream SHA or the Azure source lock changes (or `force_rebuild=true`).
- Pipeline:
  - sparse clone Fluent System `assets/`
  - sparse clone ordinary and branded MDL2 component sources for Segoe
  - temporarily download public Microsoft Portal JS/JSON to parse and index the deterministic default public Azure surface, without evaluating JavaScript
  - run `generate-fabric-metadata.py`
  - run `generate-icon-data.py`
  - commit updated `icon-data.json` + `fabric-mdl2-metadata.json` + `.upstream-sha` + `.upstream-fabric-sha` + `.upstream-azure-portal.json`

`icon-data.json` stores the published collections:
- Fluent entries use pinned raw GitHub URLs to upstream SVG files.
- Segoe entries include parsed SVG payloads and source links to ordinary or branded upstream MDL2 component files.
- Azure currently contains 1,374 generated families from 342 public core families plus 1,032 default public extension-manifest families, with 1,400 unique SVG descriptors. These are current generated-state counts, not eternal contract guarantees.
- Azure variants retain `remoteSource` descriptors containing `url`, `format`, `selector`, and `sha256`; the static browser fetches and verifies the selected public SVG at use time. No Azure SVG payload is retained in this repository or its Pages artifact, and the browser/service worker only caches resolved assets client-side.

The generator assembles these collections through private descriptors. Collection keys and `shortLabel` values in the generated `sets` map drive the compact browser tabs, while full labels continue to drive source context. The published keys are `fluent`, `segoe`, and `azure`; `fabric` remains a compatibility alias to `segoe` only while no direct `fabric` set exists.

### `.github/workflows/deploy-pages.yml`

- Runs on push to `main`.
- Publishes static files (`index.html`, `style.css`, `script.js`, `icons/`, `icon-data.json`) to GitHub Pages.

## Repository Layout

- `index.html`, `style.css`, `script.js`: static UI.
- `process.py`: optional transform/consolidation script (not used by CI sync).
- `generate-icon-data.py`: generates browser index (`icon-data.json`) for the published collections.
- `azure_portal_icons.py`, `remote-icon-source.js`: bounded Azure source discovery/indexing and browser-side remote SVG adapters.
- `generate-fabric-metadata.py`: generates/maintains `fabric-mdl2-metadata.json` (`id`, `name`, `description`, `metaphors`) for all Segoe icons.
- `fabric-mdl2-metadata.json`: committed metadata used to enrich Segoe icon search.
- `icons/`: small UI glyph assets for modal action buttons.
- `icon-data.json`: generated icon index served by the browser.
- `requirements.txt`: optional Python dependency for `process.py`.
- `serve.py`: local static file server.

## Notes

- This project consumes Microsoft Fluent, Segoe, and public Azure Portal sources. Branded MDL2 assets are governed by the Microsoft Fabric Assets License referenced by the upstream `react-icons-mdl2-branded` package; review all relevant license and usage terms before redistribution.
- Azure source URLs are retained as attribution and resolution inputs, not as rehosted assets. The weekly pipeline never touches the 105 legacy Documents SVGs; those local assets remain unimported and unpublished and are not the Azure source.
- The Azure index covers the deterministic default public surface discovered from portal bootstrap, current RequireConfig/dependency data, and default extension-manifest hashes. It does not claim authenticated or flight-specific inner blades, and this project does not own upstream source availability or semantics.
- Future coherent Microsoft adapters (Fabric, Azure DevOps, Power Platform, Entra, Microsoft 365, and Dynamics 365) are open future direction, not implemented or public collections.
