# Source Registry

This registry records the source/provenance decision for public indexing. It is not legal advice. An asset's availability, a downloadable architecture toolkit, or diagram-use permission does not by itself establish permission to mirror that asset in a public web catalogue.

## Published

| Collection | Primary source | Version / provenance | Public-index status |
| --- | --- | --- | --- |
| Fluent System | [microsoft/fluentui-system-icons](https://github.com/microsoft/fluentui-system-icons) | Commit-pinned upstream SVG URLs; MIT record in generated `sources[]`. | Published. |
| Segoe | [microsoft/fluentui](https://github.com/microsoft/fluentui) MDL2 and branded MDL2 packages | Commit-pinned component sources; ordinary MDL2 MIT, branded assets retain their upstream Microsoft Fabric Assets License reference. | Published; branded entries stay inside `segoe`. |
| Azure Portal | [Microsoft Azure Portal](https://portal.azure.com/) public core modules and default extension manifests | Descriptor-only public source provenance; digest-verified remote resolution. | Published only for the deterministic default public surface; no Azure SVG payload is committed. |
| HashiCorp Flight | [hashicorp/design-system](https://github.com/hashicorp/design-system/tree/main/packages/flight-icons) | Package 5.1.0, MPL-2.0; pinned commit and digest-bound lock. | Published generic concepts only. `Products` and `Services` are excluded; matching `-fill` names are variants, not separate concepts. |
| Red Hat | [RedHat-UX/red-hat-icons](https://github.com/RedHat-UX/red-hat-icons) | Package 2.3.1, CC BY 4.0; pinned commit and digest-bound lock. | Published `standard`, `ui`, and `microns` only. `social` is excluded. |

The generated `sources[]` entries are the browser-visible, per-collection attribution and licence/link data. Source locks bind selected source files, path names, and contents to their recorded commit digest; they are provenance checks, not a replacement for licence review.

## Candidates Requiring Resolution

| Candidate | Official starting point | Status before public indexing |
| --- | --- | --- |
| AWS Architecture Icons | [AWS architecture icons](https://aws.amazon.com/architecture/icons/) | Diagram/toolkit availability observed; determine public-catalogue mirroring rights and a revisioned source boundary. |
| Google Cloud Icon Library | [Google Cloud product icons](https://cloud.google.com/icons) | Official downloads exist; resolve reuse, redistribution, and source-lock approach. |
| IBM Cloud architecture-icons | [IBM-Cloud/architecture-icons](https://github.com/IBM-Cloud/architecture-icons) | Inspect repository licensing, asset scope, and stable upstream boundary. |
| Oracle OCI toolkits and Sun legacy | [Oracle Architecture Center](https://www.oracle.com/cloud/architecture/architecture-center/) | Resolve current OCI terms, source, and treatment of legacy Sun artwork. |
| Salesforce SLDS | [Lightning Design System icons](https://www.lightningdesignsystem.com/icons/) | Resolve asset licence and whether public mirroring is permitted. |
| Datadog | [Datadog](https://www.datadoghq.com/) | No approved asset source or rights decision. |
| MuleSoft | [MuleSoft](https://www.mulesoft.com/) | No approved asset source or rights decision. |
| Vendor, product, social, and logo marks | Source-owner brand/asset terms | Excluded unless a source-specific public-catalogue decision approves them. |
| Other security vendors | Source-owner brand/asset terms | Excluded pending an approved source, rights review, and reproducible provenance method. |

No candidate above is indexed merely because it is publicly downloadable or useful for diagrams. A separate local-only architecture for licensed packs is not implemented.
