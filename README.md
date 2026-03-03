# Fluent Icon Browser

Static browser UI for searching icons from [microsoft/fluentui-system-icons](https://github.com/microsoft/fluentui-system-icons), with automatic index refresh and GitHub Pages hosting.

## What It Does

- Searches by icon name, description, and metaphors.
- Filters by variant (`regular`, `filled`, `color`).
- Shows SVG previews with copy/download actions.
- Auto-refreshes `icon-data.json` when upstream Fluent icons change.
- Deploys the site to GitHub Pages from `main`.

## Local Development

### 1. Install dependencies

```bash
python -m pip install -r requirements.txt
```

### 2. Build consolidated icons + index JSON

```bash
python process.py --input-dir /path/to/fluentui-system-icons/assets --output-dir consolidated
python generate-icon-data.py --icons-dir consolidated --output icon-data.json
```

### 3. Run locally

```bash
python serve.py
```

## Automation

### `.github/workflows/sync-fluent-icons.yml`

- Runs hourly (and manually via workflow dispatch).
- Checks current `microsoft/fluentui-system-icons` `main` commit SHA.
- Rebuilds only when upstream SHA changes (or `force_rebuild=true`).
- Pipeline:
  - sparse clone upstream `assets/`
  - run `process.py`
  - run `generate-icon-data.py`
  - commit updated `icon-data.json` + `.upstream-sha`

### `.github/workflows/deploy-pages.yml`

- Runs on push to `main`.
- Publishes static files (`index.html`, `style.css`, `script.js`, `icons/`, `icon-data.json`) to GitHub Pages.

## Repository Layout

- `index.html`, `style.css`, `script.js`: static UI.
- `process.py`: consolidates upstream icon assets.
- `generate-icon-data.py`: generates browser index (`icon-data.json`).
- `icons/`: small UI glyph assets for modal action buttons.
- `icon-data.json`: generated icon index served by the browser.
- `requirements.txt`: Python build dependencies.
- `serve.py`: local static file server.

## Notes

- This project consumes icon assets from Microsoft’s Fluent UI System Icons repo. Review their license/usage terms before redistribution in your own downstream projects.
