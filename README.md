# Fluent Icon Browser

[Open the website](https://adamcoulteroz.github.io/fluent-icon-browser/)

A static GitHub Pages browser for searchable, source-attributed technology icon collections. The committed `icon-data.json` lets the site open without a server-side catalogue API or frontend build runtime.

## Published Collections

| Key | Collection | Published source boundary |
| --- | --- | --- |
| `fluent` | Fluent System Icons | `microsoft/fluentui-system-icons` |
| `segoe` | Segoe | `react-icons-mdl2` and `react-icons-mdl2-branded` in `microsoft/fluentui` |
| `azure` | Azure Portal Icons | Deterministic default public Portal core modules and extension manifests |
| `flight` | HashiCorp Flight Icons | Generic concepts from `hashicorp/design-system/packages/flight-icons` |
| `redhat` | Red Hat Icons | `standard`, `ui`, and `microns` from `RedHat-UX/red-hat-icons` |

`fabric` remains a compatibility alias for `segoe`; it is not a separate published collection. See [SOURCES.md](SOURCES.md) for source status, licences, scope exclusions, and candidates that are not approved for indexing.

## What It Does

- Searches icon names, descriptions, metaphors, and source-supplied categories.
- Populates a native collection picker from the generated `sets` map, using each collection's compact `shortLabel`, and filters available `regular`, `filled`, and `color` variants.
- Shows the selected collection's full label, source attribution, and licence links directly below the header.
- Previews, copies, and downloads native-size SVGs, with optional `currentColor` and bounding-box output transforms.
- Supports stable direct links: `?set=<key>&icon=<name>`.
- Works as a PWA with an offline app shell and browser-local cache of recently resolved assets.

## Source and Provenance

Each generated collection has a public `sources[]` record containing source label, reference, source URL, pinned revision, and, where applicable, licence name, licence URL, and content digest. The browser exposes the source and licence links from those records.

Remote SVG URLs are pinned to upstream commits. Flight and Red Hat synchronization also requires a source lock whose digest binds the approved source files to the selected commit. The repository does not commit Flight or Red Hat SVG payloads. Azure remains descriptor-only: the browser resolves, verifies, sanitizes, and renders public Azure sources lazily; Azure SVG payloads are not retained in this repository or the Pages artifact.

Current generated state at the documented in-flight snapshot is Fluent 2,975, Segoe 1,787, Azure 1,374, Flight 396, and Red Hat 956 icon families. These are observed build results, not permanent catalogue cardinality guarantees.

Flight is package version 5.1.0 under MPL-2.0 and excludes `Products` and `Services`. `-fill` entries are grouped as variants only where a matching generic base concept exists. Red Hat is package version 2.3.1 under CC BY 4.0 and includes only `standard`, `ui`, and `microns`; `social` is excluded.

## Local Development

Serve the static site locally:

```bash
python serve.py
```

The generator accepts the usual Fluent/Segoe inputs plus optional Flight and Red Hat source directories, pinned commits, and source-lock paths. Generation fails when a requested locked collection does not match its source digest. The sync workflow handles the corresponding upstream acquisition and writes the committed index; do not add upstream SVG payloads merely to make a collection available.

`process.py` remains an experiment and is not part of the automated sync path.

## Automation and Deployment

`.github/workflows/sync-fluent-icons.yml` refreshes the generated index when approved upstream revisions or source locks change, or when manually forced. It uses commit-pinned source URLs, retains the public Azure drift/count gates, and commits generated metadata/index and source-lock records only.

`.github/workflows/deploy-pages.yml` publishes the static files and committed index from `main`; scheduled repair deployment remains part of the lifecycle.

## Boundaries

- The browser is static-first. It does not provide a server-side icon API or package-distribution contract.
- Azure discovery is limited to the deterministic default public surface. Authenticated or flight-specific Portal surfaces and the 105 legacy local Documents SVGs are excluded.
- Source availability, diagram-use permission, or a downloadable toolkit does not alone establish permission to mirror assets in a public catalogue. This project records provenance decisions but does not provide legal advice.
- A separate local-only architecture for licensed icon packs is not implemented.
