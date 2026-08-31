# Fluent Icon Browser

[Open the website](https://adamcoulteroz.github.io/fluent-icon-browser/)

A static GitHub Pages index, deep-link browser, and client-side resolver for searchable, source-attributed technology icon collections. The committed `icon-data.json` lets the site open without a server-side catalogue API or frontend build runtime; the client retrieves each resolved icon from its source owner and renders it inline.

## Published Collections

| Key | Collection | Published source boundary |
| --- | --- | --- |
| `fluent` | Fluent System Icons | `microsoft/fluentui-system-icons` |
| `segoe` | Segoe | `react-icons-mdl2` and `react-icons-mdl2-branded` in `microsoft/fluentui` |
| `azure` | Azure Portal Icons | Deterministic default public Portal core modules and extension manifests |
| `flight` | HashiCorp Flight Icons | Generic concepts from `hashicorp/design-system/packages/flight-icons` |
| `hashicorp` | HashiCorp Products | Official product marks from the `Products` category in `hashicorp/design-system/packages/flight-icons` |
| `salesforce` | Salesforce SLDS Icons | Official `@salesforce-ux/icons` npm archive, entry-digest verified at runtime |
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

Published sources have a deterministic official source boundary: a revisioned or stable per-icon URL, or an official archive with an entry descriptor and digest. They must be unauthenticated and CORS-accessible to the client, and their terms must be compatible with automated indexing, deep-linking/hotlinking, runtime retrieval, and user copy/download, with appropriate attribution, trademark, and no-endorsement treatment. Remote SVG URLs are pinned to upstream commits. Flight, HashiCorp Products, and Red Hat synchronization require source locks whose digests bind the approved source files to the selected commit. Salesforce synchronisation locks the registry archive digest plus every approved SVG entry; the browser verifies both before sanitizing an extracted entry. The pipeline may temporarily download official sources to inspect and index them, then discards the payloads and retains generated index/lock metadata only. Azure remains descriptor-only: the browser resolves, verifies, sanitizes, and renders public Azure sources lazily.

Current generated state counts are observed build results, not permanent catalogue cardinality guarantees.

Flight is package version 5.1.0 under MPL-2.0 and remains limited to generic concepts, excluding `Products` and `Services`. The separate `hashicorp` set contains only official `Products` marks, including Terraform, Vault, Packer, Nomad, and Consul; `Services` remains excluded. For a product base, canonical `?set=hashicorp&icon=<base>` links combine upstream `<base>`, `<base>-fill`, and `<base>-color` SVGs as regular, filled, and color variants. `<base>-fill-color` remains a searchable alias only, never a fourth visible variant; generic `flight` grouping is unchanged. Salesforce SLDS is package version 10.17.0 under CC BY-ND 4.0 and includes source-colour `standard`, `action`, `doctype`, and `custom` artwork, including the first-party MuleSoft asset; `utility` is excluded. Its no-derivatives source capability disables browser output transforms. Red Hat is package version 2.3.1 under CC BY 4.0 and includes only `standard`, `ui`, and `microns`; `social` is excluded.

## Local Development

Serve the static site locally:

```bash
python serve.py
```

The generator accepts the usual Fluent/Segoe inputs plus optional Flight, HashiCorp Products, Salesforce archive, and Red Hat source inputs with their source locks. Generation fails when a requested locked collection does not match its source digest. The sync workflow handles the corresponding upstream acquisition and writes the committed index; do not add upstream SVG payloads merely to make a collection available.

`process.py` remains an experiment and is not part of the automated sync path.

## Automation and Deployment

`.github/workflows/sync-fluent-icons.yml` refreshes the generated index when approved upstream revisions or source locks change, or when manually forced. It uses commit-pinned source URLs, retains the public Azure drift/count gates, and commits generated metadata/index and source-lock records only.

`.github/workflows/deploy-pages.yml` publishes the static files and committed index from `main`; scheduled repair deployment remains part of the lifecycle.

## Boundaries

- The browser is static-first. It does not provide a server-side icon API or package-distribution contract.
- Azure discovery is limited to the deterministic default public surface. Authenticated or flight-specific Portal surfaces and the 105 legacy local Documents SVGs are excluded.
- Source availability, diagram-use permission, or a downloadable toolkit does not alone establish suitability for this index and runtime resolver. Each candidate must satisfy the documented deterministic-source, client-access, terms, attribution, trademark, and no-endorsement checks; not every vendor source is suitable. This project records provenance decisions but does not provide legal advice.
- A separate local-only architecture for licensed icon packs is not implemented.
