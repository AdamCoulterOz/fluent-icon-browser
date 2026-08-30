# Interface

## Purpose

`fluent-icon-browser` is a static browser for Fluent System, Segoe, and Azure icons. It owns the generated icon index and public GitHub Pages browsing surface, while not owning upstream sources.

## Responsibilities

- Own the static icon browser UI and committed `icon-data.json` index.
- Publish the browser through GitHub Pages.
- Provide stable URL deep links for externally documented icon references.
- Do not own upstream Fluent, Segoe/MDL2, or Azure Portal source repositories or services.
- Do not expose generated internal normalization details as a cross-repository contract except where documented here.

## Domain Model

- Icon set: a named icon collection from the generated `sets` map. Each set has a full `label` and compact `shortLabel`; published keys are `fluent`, `segoe`, and `azure`. `fabric` is a compatibility alias to `segoe` only while no direct `fabric` set exists.
- Icon: a searchable, selectable icon family with display metadata and available visual variants.
- Variant: a renderable regular, filled, or color representation when present.
- Branded MDL2 icon: an icon sourced from the upstream branded component package and tagged `branded` within the Segoe set.
- Azure remote asset: a variant represented by `remoteSource` with `url`, `format`, `selector`, and `sha256`, resolved from a public Microsoft source at use time.
- Deep link: a URL query identifying an icon set and icon name.

## Public Interfaces

- Site URL: `https://adamcoulteroz.github.io/fluent-icon-browser/`
- Parent project index: `https://adamcoulteroz.github.io/`
- Crawler policy and sitemap: `robots.txt` and `sitemap.xml` at the site URL.
- Deep-link query:
  - `set`: canonical icon set key, currently `fluent`, `segoe`, or `azure`. The `fabric` compatibility alias resolves to `segoe` only when no direct `fabric` set exists.
  - `icon`: icon name from the active generated index.
- `?set=<key>&icon=<name>` should switch to the requested set, filter to the requested icon, and open the icon details panel when the icon is a visible canonical card.
- When `icon` names a folded or normalized variant that is not a visible card, the browser should fall back to search so the link still lands on the relevant canonical family.
- Selecting an icon updates the browser URL with `replaceState` so the current icon view is copy-shareable.

## Invariants

- The browser remains static-first and must not require a frontend bundler or server runtime.
- `icon-data.json` remains committed and directly consumable by the static page.
- Deep-link URLs must remain implementation-independent: external consumers may rely on query parameters, not internal JavaScript function names or DOM structure.
- Upstream icon source URLs and Azure remote descriptors remain attributable and digest-bound in the generated index; upstream source ownership remains external.
- The `segoe` set is the union of ordinary and branded MDL2 component sources; branded icons must remain searchable by the `branded` tag.
- A future canonical `fabric` set would take precedence over the legacy alias. Introducing that collision requires an explicit compatibility decision for existing `fabric` deep links.
- Azure currently indexes 1,374 generated families from 342 public core families and 1,032 default public extension-manifest families, with 1,400 unique SVG descriptors. These counts describe current generated state, not a permanent cardinality contract.
- Azure discovery is bounded to the deterministic default public surface exposed by portal bootstrap, current RequireConfig/dependency data, and default extension-manifest hashes. Authenticated or flight-specific inner blades are outside scope; schema drift or count collapse must fail synchronization.
- Azure formats `portal-amd-svg-module` and `portal-json-pointer-svg` are private adapters. The browser fetches public CORS sources lazily, extracts without eval, verifies the digest, sanitizes, and renders the resolved SVG inline for preview/copy/download.
- Azure artwork with intrinsic chromatic, multi-paint, gradient, or pattern styling must retain its authored colours in gallery and detail previews. This rendering property is independent of the upstream regular, filled, or color variant taxonomy.
- The repository and Pages artifact retain no Azure SVG payload. The 105 legacy Documents SVGs remain unimported and unpublished and are not the Azure source. Future coherent adapters for Fabric, Azure DevOps, Power Platform, Entra, Microsoft 365, and Dynamics 365 are direction only, not implemented contract.

## Side Effects

- Browser runtime fetches `icon-data.json` from the same static site.
- Browser runtime fetches commit-pinned Fluent SVGs and public Azure source documents cross-origin; Azure resolution is lazy and client/service-worker caching does not rehost assets in the repository.
- Selecting icons mutates the current browser URL with `history.replaceState`.
- Copy and download actions interact with the browser clipboard and local download behavior. The preview toolbar exposes `currentColor` and bounds transformations that apply identically to both outputs. Bounds are off by default and retained for the browser-tab session; when enabled, output SVG markup groups its drawable artwork with a zero-opacity path matching the source `viewBox` to preserve document bounds and grouping in native-curve imports.
- The bounds preference is stored in browser `sessionStorage` and expires when the browser-tab session ends.
- GitHub workflows may commit generated index updates and deploy the static site to GitHub Pages.

## Dependency Boundaries

- Upstream dependencies: `microsoft/fluentui-system-icons`, plus the `react-icons-mdl2` and `react-icons-mdl2-branded` packages in `microsoft/fluentui`.
- Downstream consumers: external docs and tools may link to the public site and documented deep-link query contract.
- Trusted contracts: committed static files, generated icon index shape used by this UI, and documented URL query parameters.
- Internal-only concerns: search-index preparation, DOM structure, card maps, normalization implementation details, workflow implementation details.
- Prohibited couplings: downstream consumers should not depend on private JS methods, specific DOM class names, or generated non-canonical variant internals.

## Lifecycle / Execution Model

- The static page loads in the browser, fetches `icon-data.json`, renders the default set, then resolves any deep-link query.
- The icon details panel updates in place when another icon is selected. It closes when the selected card is toggled, the user presses `Esc`, clicks outside the panel without selecting another icon, or swipes the panel downward on a touch screen. A touch dismissal tracks the finger and owns the active gesture so the underlying gallery does not scroll; an incomplete swipe settles the panel back into place.
- Without JavaScript, the static page renders catalogue scope, source information, and parent/source links; it does not render or search the icon index.
- Weekly sync regenerates icon data when upstream SHAs or the Azure source lock change; temporary Portal JS/JSON downloads are parsed without eval, then discarded except for index and small lock metadata.
- Pages deployment runs after pushes, after successful sync workflow runs, and on a daily repair schedule.
- The browser is single-user client-side state. The bounds preference persists only in browser `sessionStorage`; selected icon state remains represented by the current URL, and copy/download effects remain browser-mediated.

## Anti-Goals

- No server-side icon API.
- No package distribution contract for consumers.
- No guarantee that undocumented icon metadata fields or normalization details remain stable.
- No ownership of upstream icon naming, availability, or asset semantics.
- No import, publication, or implied approval of the 105 legacy Azure Documents SVG assets; they are separate from the public Azure Portal source.

## Agent Guidance

- Preserve the documented deep-link query contract when refactoring browser state, search, or selection behavior.
- Preserve branded source attribution and the `branded` search tag when regenerating or regrouping Segoe MDL2 families.
- Update this file alongside changes to public URLs, generated index semantics, side effects, or deployment lifecycle.
- Keep implementation mechanics out of this interface unless they become deliberate public contract.
- Verify deep-link behavior before deployment when changing selection, filtering, set switching, or panel-opening code.
