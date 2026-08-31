# Source Registry

This registry records source/provenance and eligibility decisions for the public index, deep links, and client-side runtime resolver. It is not legal advice. A published source needs a deterministic official source boundary: a revisioned or stable per-icon URL, or an official archive with an entry descriptor and digest; unauthenticated CORS client accessibility; terms compatible with automated indexing, deep-linking/hotlinking, runtime retrieval, and user copy/download; and appropriate attribution, trademark, and no-endorsement treatment. Availability, a downloadable architecture toolkit, or diagram-use permission alone is insufficient, and not every vendor source is suitable. No rehosting is a separate implementation invariant: the repository retains metadata/index data and source descriptors, not upstream SVG payloads.

## Published

| Collection | Primary source | Version / provenance | Public-index status |
| --- | --- | --- | --- |
| Fluent System | [microsoft/fluentui-system-icons](https://github.com/microsoft/fluentui-system-icons) | Commit-pinned upstream SVG URLs; MIT record in generated `sources[]`. | Published. |
| Segoe | [microsoft/fluentui](https://github.com/microsoft/fluentui) MDL2 and branded MDL2 packages | Commit-pinned component sources; ordinary MDL2 MIT, branded assets retain their upstream Microsoft Fabric Assets License reference. | Published; branded entries stay inside `segoe`. |
| Azure Portal | [Microsoft Azure Portal](https://portal.azure.com/) public core modules and default extension manifests | Descriptor-only public source provenance; digest-verified remote resolution. | Published only for the deterministic default public surface; no Azure SVG payload is committed. |
| HashiCorp Flight | [hashicorp/design-system](https://github.com/hashicorp/design-system/tree/main/packages/flight-icons) | Package 5.1.0, MPL-2.0; pinned commit and digest-bound lock. | Published generic concepts only. `Products` and `Services` are excluded; matching `-fill` names are variants, not separate concepts. |
| HashiCorp Products | [hashicorp/design-system](https://github.com/hashicorp/design-system/tree/main/packages/flight-icons) | Package 5.1.0, MPL-2.0; independently pinned and digest-bound `Products` subset lock. | Published official `Products` category only, including Terraform, Vault, Packer, Nomad, and Consul. Canonical `hashicorp` families combine `<base>`, `<base>-fill`, and `<base>-color` as regular, filled, and color variants; `<base>-fill-color` is search-only alias metadata, not a fourth variant. `Services` stays excluded; generic `flight` behavior is unchanged. |
| Salesforce SLDS | [@salesforce-ux/icons](https://www.npmjs.com/package/@salesforce-ux/icons) | Package 10.17.0, CC BY-ND 4.0; registry archive digest plus per-entry digests, verified before browser extraction and sanitization. | Published `standard`, `action`, `doctype`, and `custom` artwork, including first-party MuleSoft. `utility` is excluded. No source-transforming `currentColor` or bounding-box output is offered. |
| Red Hat | [RedHat-UX/red-hat-icons](https://github.com/RedHat-UX/red-hat-icons) | Package 2.3.1, CC BY 4.0; pinned commit and digest-bound lock. | Published `standard`, `ui`, and `microns` only. `social` is excluded. |

The generated `sources[]` entries are the browser-visible, per-collection attribution and licence/link data. Source locks bind selected source files, path names, and contents to their recorded commit digest; they are provenance checks, not a replacement for licence review.

## Candidates Requiring Resolution

| Candidate | Official starting point | Status before public indexing |
| --- | --- | --- |
| AWS Architecture Icons | [AWS architecture icons](https://aws.amazon.com/architecture/icons/) | A dated official ZIP is a plausible archive-descriptor source, but per-icon runtime access and terms for public retrieval/copy-download are unresolved. |
| Google Cloud Icon Library | [Google Cloud product icons](https://cloud.google.com/icons) | Official ZIPs exist, but their browser-fetch path is not CORS-readable and the current product-icon guidance is not an approved public-runtime source boundary. |
| IBM Cloud architecture-icons | [IBM-Cloud/architecture-icons](https://github.com/IBM-Cloud/architecture-icons) | Commit-pinned CORS-readable source files are technically suitable, but the repository has no declared asset licence or explicit public retrieval/copy-download grant. |
| Oracle OCI toolkits and Sun legacy | [Oracle Architecture Center](https://www.oracle.com/cloud/architecture/architecture-center/) | CORS-readable OCI archives exist, but Oracle's current terms do not establish the required automated/index/runtime path; no current authoritative Sun catalogue was found. |
| Microsoft Fabric | [@fabric-msft/svg-icons](https://www.npmjs.com/package/@fabric-msft/svg-icons) | Versioned CORS-readable package archive and MIT package metadata are technically suitable; confirm that its grant covers public catalogue display and user download beyond Fabric extension development. |
| Power Platform, Entra, Microsoft 365, and Dynamics 365 | Microsoft architecture icon guidance | Official archives exist, but current download paths are not browser CORS-readable and their diagram/training terms do not establish this runtime resolver's use. Existing Azure/Segoe entries remain individually discoverable, not complete collection coverage. |
| CNCF project artwork | [cncf/artwork](https://github.com/cncf/artwork) | Commit-pinned CORS-readable project artwork is technically suitable; Linux Foundation trademark/no-endorsement treatment and source-transforming export need an explicit collection decision. |
| Jenkins artwork | [Jenkins artwork](https://www.jenkins.io/artwork/) | Commit-pinned source artwork is technically suitable, but CC BY-SA/trademark attribution and derivative-output handling need a collection-specific decision. |
| Datadog | [Datadog](https://www.datadoghq.com/) | No public, versioned first-party product/service SVG collection with a suitable runtime source and terms was identified. |
| Vendor, product, social, and logo marks | Source-owner brand/asset terms | Excluded unless a source-specific public-catalogue decision approves them. |
| Other security vendors | Source-owner brand/asset terms | Excluded pending an approved source, rights review, and reproducible provenance method. |

No candidate above is indexed merely because it is publicly downloadable or useful for diagrams. A separate local-only architecture for licensed packs is not implemented.
