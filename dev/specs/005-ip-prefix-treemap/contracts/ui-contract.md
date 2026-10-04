# Contract: Tree Map tab UI

**Date**: 2026-10-03 | **Research**: [../research.md](../research.md) R3, R6, R7, R10

What the page exposes to users and to tests. Selectors here are the ones the E2E and component
tests will use, so they are part of the contract.

## Route

| Path | Shim | Notes |
|------|------|-------|
| `/ipam/:objectKind/:objectId/tree-map` | `pages/ipam/ipam-details-tree-map-page.tsx` (`Component`) | declared before `:relationshipName`; keeps the `namespace` and `kind` query params through `constructPathForIpam("tree-map")` |

## Tab

- A `LinkTab` labelled **Tree Map** inside the existing IPAM tab row, after Details and before the
  relationship tabs. Rendered only for IP prefix kinds.
- Test selector: `get_by_role("link", name="Tree Map")`, matching how sibling tabs are selected.

## Container

| Element | Role and name | Notes |
|---------|---------------|-------|
| Map | `role="group"`, `aria-label="Tree map of <parent CIDR>"` | `data-testid="ip-prefix-tree-map"`, fixed 2:1 aspect ratio, full content width |
| Cap notice | `role="status"` | text "Showing the first 1,000 of N children", present only when capped |
| Legend | plain text | "Allocated", "Pool", "Free", "Smaller than 1/4096 of the prefix" |

## Tiles

| Tile kind | Element | Accessible name | Visual | Action |
|-----------|---------|-----------------|--------|--------|
| allocated | `<a>` (react-router `Link`) | `"<CIDR>, <N>% utilized"` or `"<CIDR>, utilization unknown"`, with `, pool` appended for a pool | accent surface with a solid accent border, inner fill width = utilisation %; a pool (`is_pool`) uses the pool surface, border and fill instead and carries `data-tile-pool="true"` | navigate to the child's `tree-map` route, query params preserved |
| free | `<button>` (`@infrahub/ui` `Button`) | `"<CIDR> available"` | content surface with diagonal hatching, dashed border | open the create sheet prefilled with the CIDR; disabled with the permission tooltip when `permission.create.isAllowed` is false |
| aggregate-allocated | `<a>` | `"<N> smaller prefixes"` | muted surface | navigate to the parent's `children` route |
| aggregate-free | `<div role="img">` | `"<N> smaller free blocks"` | muted surface, dashed border | none |
| remainder | `<a>` | `"<N> more children not shown"` | muted surface | navigate to the parent's `children` route |

Common:

- `data-testid="ip-prefix-tree-map-tile"` and `data-tile-kind="<kind>"` on every tile.
- Visible label is the CIDR or the aggregate label, hidden when the tile is too small; the
  accessible name never depends on the visible label.
- An allocated tile with a description shows it on a second line once the tile is at least 11rem
  wide; from 5rem to under 11rem it shows a small description marker
  (`data-testid="ip-prefix-tree-map-tile-description-marker"`) next to the CIDR and leaves the text
  to the tooltip; below 5rem the whole label, marker included, is hidden.
- The accessible name of a pool tile ends in `, pool`.
- Hover and focus show the `@infrahub/ui` `Tooltip`. Allocated: CIDR, description, member type,
  utilisation, member count. Free: CIDR. Aggregates: the list of member CIDRs, truncated after 20
  with "and N more".

## Empty state (address-type parent with no child prefixes)

Rendered by the map container after the query returns, so a prefix whose member type is `address`
but which still holds child prefixes gets the map.

| Element | Selector | Content |
|---------|----------|---------|
| Container | `data-testid="ip-prefix-tree-map-empty"` | |
| Meter | `get_by_role("meter", name="Utilization")` | parent utilisation, same `Meter` as the Children table; omitted when the utilisation is unknown |
| Text | | "This prefix holds IP addresses. The tree map shows child prefixes." |
| Link | `get_by_role("link", name="IP Addresses")` | `constructPathForIpam("../ip_addresses")` (parent-relative, because the link renders inside the `tree-map` child route) |

## Create sheet

Reuses the extracted `IpPrefixCreateSheet`. Same title, form and success toast as the Children tab's
available row. On success: sheet closes, `objectQueryKeys.all` is invalidated, the map refetches.

## States

| State | Rendering |
|-------|-----------|
| Loading | shared `LoadingIndicator` in place of the map |
| Error | shared `ErrorScreen` with the error message |
| Parent fully allocated | no free tiles, no create affordance |
| Parent empty | free tiles only (the backend returns the two halves) |
