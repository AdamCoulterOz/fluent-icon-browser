# Interface

## Purpose

`fluent-icon-browser` is a static browser for Fluent System and Segoe icons. It owns the generated icon index and the public GitHub Pages browsing surface.

## Responsibilities

- Own the static icon browser UI and committed `icon-data.json` index.
- Publish the browser through GitHub Pages.
- Provide stable URL deep links for externally documented icon references.
- Do not own upstream Fluent or Fabric icon source repositories.
- Do not expose generated internal normalization details as a cross-repository contract except where documented here.

## Domain Model

- Icon set: a named icon collection from the generated `sets` map. Each set has a full `label` and an additive compact `shortLabel`; the browser renders an accessible tab for every supplied collection. The currently published keys are `fluent` (Fluent System) and `segoe` (Segoe).
- Icon: a searchable, selectable icon family with display metadata and available visual variants.
- Variant: a renderable regular, filled, or color representation when present.
- Branded MDL2 icon: an icon sourced from the upstream branded component package and tagged `branded` within the Segoe set.
- Deep link: a URL query identifying an icon set and icon name.

## Public Interfaces

- Site URL: `https://adamcoulteroz.github.io/fluent-icon-browser/`
- Parent project index: `https://adamcoulteroz.github.io/`
- Crawler policy and sitemap: `robots.txt` and `sitemap.xml` at the site URL.
- Deep-link query:
  - `set`: canonical icon set key, currently `fluent` or `segoe`. The legacy `fabric` key resolves to `segoe` only when no `fabric` set exists.
  - `icon`: icon name from the active generated index.
- `?set=<key>&icon=<name>` should switch to the requested set, filter to the requested icon, and open the icon details panel when the icon is a visible canonical card.
- When `icon` names a folded or normalized variant that is not a visible card, the browser should fall back to search so the link still lands on the relevant canonical family.
- Selecting an icon updates the browser URL with `replaceState` so the current icon view is copy-shareable.

## Invariants

- The browser remains static-first and must not require a frontend bundler or server runtime.
- `icon-data.json` remains committed and directly consumable by the static page.
- Deep-link URLs must remain implementation-independent: external consumers may rely on query parameters, not internal JavaScript function names or DOM structure.
- Upstream icon source URLs remain pinned to upstream SHAs recorded in the generated index.
- The `segoe` set is the union of ordinary and branded MDL2 component sources; branded icons must remain searchable by the `branded` tag.
- A future canonical `fabric` set would take precedence over the legacy alias. Introducing that collision requires an explicit compatibility decision for existing `fabric` deep links.
- A future collection must have verified provenance and licensing before its assets, source locations, or public set key are added. Legacy Azure assets are explicitly blocked pending that verification; Microsoft Learn's Azure Architecture Center terms do not currently establish permission for this browser's public preview/copy/download catalogue.

## Side Effects

- Browser runtime fetches `icon-data.json` from the same static site.
- Browser runtime fetches commit-pinned Fluent SVGs cross-origin; preview images may use opaque cached responses, while copy/download require CORS-readable SVG text.
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
- Weekly sync regenerates icon data when upstream SHAs change.
- Pages deployment runs after pushes, after successful sync workflow runs, and on a daily repair schedule.
- The browser is single-user client-side state. The bounds preference persists only in browser `sessionStorage`; selected icon state remains represented by the current URL, and copy/download effects remain browser-mediated.

## Anti-Goals

- No server-side icon API.
- No package distribution contract for consumers.
- No guarantee that undocumented icon metadata fields or normalization details remain stable.
- No ownership of upstream icon naming, availability, or asset semantics.
- No import, publication, or implied approval of legacy Azure icon assets.

## Agent Guidance

- Preserve the documented deep-link query contract when refactoring browser state, search, or selection behavior.
- Preserve branded source attribution and the `branded` search tag when regenerating or regrouping Segoe MDL2 families.
- Update this file alongside changes to public URLs, generated index semantics, side effects, or deployment lifecycle.
- Keep implementation mechanics out of this interface unless they become deliberate public contract.
- Verify deep-link behavior before deployment when changing selection, filtering, set switching, or panel-opening code.
