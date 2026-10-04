# Research: IP Prefix Tree Map

**Date**: 2026-10-03 | **Spec**: [spec.md](spec.md) | **Plan**: [plan.md](plan.md)

Each entry records a decision, why, and what was rejected. Code locations are cited as
`module::Symbol`.

## R1. Data source: one typed query on the IP prefix generic

**Decision**: Add a typed gql.tada document, `GET_IP_PREFIX_TREE_MAP`, in a new api module
`frontend/app/src/entities/ipam/ip-prefixes/api/get-ip-prefix-tree-map-from-api.ts`. It queries
`BuiltinIPPrefix(parent__ids: $parentIds, include_available: true, limit: $limit)` and selects
`count` plus, on each node, `__typename id display_label prefix{value} member_type{value}
utilization{value} description{value} children{count} ip_addresses{count}`. The contract and a
sample response are in [contracts/graphql-query.md](contracts/graphql-query.md).

**Rationale**:

- The backend already returns everything one level needs. The resolver
  `backend/infrahub/graphql/resolvers/ipam.py::ipam_paginated_list_resolver` annotates the page
  with `InternalIPPrefixAvailable` nodes computed by `_resolve_available_prefix_nodes`, so free
  blocks need no client-side maths.
- Selecting the attribute fields at the interface level works for both real and virtual nodes. The
  field extractor (`backend/infrahub/graphql/field_extractor.py`) already takes the union of all
  fragment selections, so the existing Children query hits the same code path. Verified against the
  public sandbox: available nodes answer `prefix.value` with their CIDR and `utilization.value` as
  `null`; real nodes answer an integer percentage.
- A static, typed document satisfies the constitution's type-safety principle and gives the domain
  layer a stable shape, which the runtime-built Children query
  (`entities/ipam/ip-prefixes/api/get-ip-prefix-list-from-api.ts::buildGetIpPrefixListWithAvailabilityQuery`)
  cannot. The IPAM tree already uses this pattern
  (`entities/ipam/ipam-tree/api/get-ipam-tree-nodes-by-parent-from-api.ts::GET_IPAM_TREE_NODES`).
- `count` is the number of real children matching the filter, independent of the page, which is
  what the cap notice needs.

**Alternatives considered**:

- Reuse `useGetIpPrefixList`. Rejected: it is an infinite query paged at 40 to 200 rows, built
  from the schema's visible attribute list, and untyped. A treemap needs the whole set in one
  render and a fixed field list.
- Add a backend subtree or batched utilisation query. Rejected for v1: crosses the GraphQL
  ask-first gate and is not needed for one level. Revisit only if SC-001 fails (see R9).

## R2. Pagination semantics force an address-ordered cap

**Decision**: Request `limit: 1000` with no offset. When `count` exceeds the number of real children
returned, the map shows the children it received, in address order, plus one aggregated tile sized
to the address space not covered by any returned tile, and a notice "showing the first 1,000 of N
children". The spec's FR-011 and User Story 5 are amended to say "first 1,000 in address order"
rather than "largest".

**Rationale**: The resolver computes free blocks only inside the fetched window. It fetches
`limit + 1` rows, drops the extra row as `last_node_context`, and
`_resolve_available_prefix_nodes` skips any free block beyond that context. Results are ordered by
prefix value, and any other ordering disables availability
(`entities/ipam/ip-availability/domain/rules/should-exclude-ip-availability.ts`). "Largest first"
is therefore not available from the server, and the client cannot see children it did not fetch.
Computing the remainder as parent space minus the sum of returned tiles keeps FR-003 (areas sum to
the parent) exact in the capped case.

**Alternatives considered**: Fetch all pages until exhausted. Rejected: unbounded utilisation
queries on the backend, and the spec caps at 1,000 for exactly that reason.

## R3. Layout: a squarified treemap written as a pure domain rule, rendered with HTML

**Decision**: Implement the squarified treemap algorithm (Bruls, Huizing and van Wijk, 2000) as a
pure function in `entities/ipam/ip-prefixes/domain/rules/layout-tree-map.ts`. Input: tiles with
weights summing to 1 and a container aspect ratio. Output: rectangles as percentages of the
container. Render each rectangle as an absolutely positioned HTML element inside a container with a
fixed CSS aspect ratio, so no resize observation is needed.

**Rationale**:

- Keyboard and screen-reader access. Allocated tiles are links and free tiles are buttons, which
  HTML gives for free. The installed Recharts `Treemap` (`recharts/types/chart/Treemap.d.ts`)
  only accepts SVG content and exposes click through an `onClick(node)` callback, so tiles would
  not be focusable without extra work.
- Reuse of existing primitives. The hover card is the `@infrahub/ui` `Tooltip` and the create
  action is the `@infrahub/ui` `Button` plus `Sheet`, all HTML. They cannot be rendered inside the
  Recharts SVG.
- Testability. A pure layout function gets unit tests for bounds and proportionality without a
  browser. The multiple-segment bar (`shared/components/stats/multiple-progress-bar.tsx`) is the
  in-repo precedent for percentage-sized HTML boxes with tooltips.
- The algorithm is about eighty lines and has no dependency. The constitution asks for existing
  dependencies over new ones; it does not ask for a chart library to be used where it does not fit.

**Alternatives considered**:

- Recharts `Treemap` with a custom `content` renderer. Rejected for the accessibility and reuse
  reasons above, and because its animation and tooltip state add nothing here.
- `d3-hierarchy` for `treemapSquarify`. Rejected: a new dependency (ask-first gate) for one
  function.

## R4. Exact area arithmetic with BigInt, float only at layout time

**Decision**: Parse each CIDR into `{ family, prefixLength }` and compute address counts as
`BigInt` (`2n ** BigInt(maxLength - prefixLength)`; the shift form is ruled out by the lint
rule on bitwise operators). Sums, the capped remainder and the aggregation threshold are computed
in `BigInt`. Each tile's weight becomes a `number` fraction of the parent only after aggregation,
via `Number(count) / Number(parentCount)`.

**Rationale**: An IPv6 /32 holds 2^96 addresses, past `Number.MAX_SAFE_INTEGER`. Powers of two are exact
as doubles, but sums and differences of mixed powers are not once exponents differ by more than 53,
which is exactly the IPv6 case. BigInt makes FR-002 and FR-003 provable in unit tests across prefix
lengths 0 to 128. For the weight, plain double division is exact for every single-prefix tile
(both operands are powers of two) and accurate to about 1e-16 for aggregated tiles. A fixed
six-digit scale was considered and rejected: 1/256 (a /16 in a /8) is not representable at six
digits, so the demo case would have summed to 0.999999 and failed its own invariant.

**Alternatives considered**: `Number` throughout with a tolerance. Rejected: FR-003's "sums to the
parent" would be approximate and the IPv6 edge tests would be flaky.

## R5. Legibility threshold as a fraction of the parent, not pixels

**Decision**: A tile whose address count is below `parentCount / 4096` is aggregated. Allocated
tiles below the threshold collapse into one "N smaller prefixes" tile, free tiles into one "N
smaller free blocks" tile. The constant lives with the model as `TREE_MAP_MIN_TILE_DIVISOR` (`4096n`).

**Rationale**: A fraction keeps tile preparation a pure function of the data, so it is unit
testable and deterministic. At the container size the tab gives (full content width, 2:1 aspect),
1/4096 of the area is a square of roughly 12 to 16 px, which is the smallest tile that still
accepts a click. The spec says the exact threshold is a presentation choice.

**Alternatives considered**: Measure the container and aggregate below a pixel area. Rejected for
v1: needs a resize observer (none exists in the frontend), couples layout to the DOM, and the
benefit over a fixed fraction is marginal at one level deep. Can be revisited with nested rendering.

## R6. Route, tab and page shim

**Decision**:

- Route: a new static child `tree-map` under `ipam/:objectKind/:objectId` in
  `frontend/app/src/app/router.tsx`, declared before `:relationshipName`. The hyphen guarantees it
  can never collide with a schema relationship name, which are snake_case identifiers.
- Tab: a `LinkTab` labelled "Tree Map" in
  `pages/ipam/ipam-details-layout.tsx::IpamDetailsTabs`, rendered only when the object schema is
  an IP prefix kind (`isOfKind(IP_PREFIX_GENERIC, objectSchema)`), placed after "Details" and
  before the relationship tabs. The same layout serves IP address detail pages, which get no tab.
- Shim: `pages/ipam/ipam-details-tree-map-page.tsx` exporting `Component`. It reads the parent
  prefix from `useCurrentFormContext()` as the sibling index page does, wraps the content in
  `RequireObjectPermissions objectKind={parentSchema.kind}` to obtain the create permission the
  same way the Children tab does through `ObjectTableProvider`, and renders
  `IpPrefixTreeMap`.

**Rationale**: The route guideline prefers outlet context, but it also says not to mix patterns
within one detail-page family. Every IPAM sibling reads the parent through `FormContext`, so the
new tab does the same. `RequireObjectPermissions` is backed by a cached react-query, so running it
again in the shim costs no extra request.

**Alternatives considered**: Migrate the IPAM family to outlet context in this change. Rejected as
scope creep; it is a separate cleanup.

## R7. Create-from-free-tile reuses the existing sheet

**Decision**: Extract the `Sheet` plus `ObjectForm` block from
`entities/ipam/ip-prefixes/ui/ip-prefix-available-identifier.tsx::IpPrefixAvailableIdentifier`
into `ui/ip-prefix-create-sheet.tsx` taking `{ schema, prefix, isOpen, onOpenChange, onSuccess }`.
The identifier and the free tile both use it. On success the tile handler invalidates
`objectQueryKeys.all`, which already covers the tree map query because its key is built under the
same root (R8).

**Rationale**: Two callers now exist, which is the constitution's bar for extraction. The permission
gate and the disabled tooltip (`permission.create.isAllowed`, `permission.create.message`) stay
exactly as the Children tab shows them.

## R8. Query hook, key and context

**Decision**: `ui/queries/get-ip-prefix-tree-map.query.ts` exports `getIpPrefixTreeMapQueryOptions`
and `useGetIpPrefixTreeMap({ parentId })`. The hook injects `branchName` from `useCurrentBranch`
and `atDate` from `datetimeAtom`, as `useGetObjectPermissions` does. The key factory lives in
`ui/queries/ip-prefix.query-keys.ts` as
`ipPrefixesQueryKeys.treeMap(params) => [...objectQueryKeys.all, "ip-prefix-tree-map", params]`,
with a single params object ending the key.

**Rationale**: Branch and time-machine date in the key satisfy FR-013 without any effect code: a
branch switch changes the key and refetches. Rooting under `objectQueryKeys.all` means every
existing object mutation invalidation (including the create sheet's) refreshes the map (FR-009).

## R9. Performance budget and the batching trigger

**Decision**: Ship with no backend change. During implementation, measure the tab on the demo
stack for a prefix with 256 direct children and record the figure in
[quickstart.md](quickstart.md). If it exceeds SC-001's 3 seconds, open a separate, explicitly gated
change for a batched utilisation lookup; do not fold it into this feature.

**Rationale**: `backend/infrahub/core/node/ipam.py::BuiltinIPPrefix.to_graphql` runs one
`PrefixUtilizationGetter` per node, and the getter already accepts many prefixes in one query, so a
batched resolver is a small, well-bounded follow-up if needed. Free blocks also pass through this
path today (they answer `null`), which the Children tab already pays for.

## R10. Visual encoding with theme tokens

**Decision**:

- Pool tile (`is_pool`): the same shape as an allocated tile in the `pool` token family
  (`bg-pool-surface`, `border-pool`, `bg-pool-fill`), a fuchsia hue because it is the one hue the
  accent and the status families leave free; it has its own legend entry.
- Allocated tile: `bg-accent-surface`, `border-accent-strong`, label `text-foreground`; inner fill is a
  child element with `width: <utilisation>%` (the only inline style, because it is data) and the
  `bg-accent-fill` token, a 55% alpha of `--accent-strong` declared in the shared theme for both
  themes so no component carries a `color-mix` or a `var(--x)` colour inline.
- Free tile: `bg-content` under a diagonal hatch drawn from `--border-strong` (the `tree-map-hatch`
  utility), `border-dashed border-border-strong`, label `text-foreground-muted`. The hatch is what
  separates "empty" from "allocated" at a glance; the dashed border alone was too subtle.
  (`bg-subtle` was considered and rejected: the `subtle` token is a foreground colour and renders
  as dark grey.)
- Aggregated tiles: `bg-content-strong`, label `text-foreground-muted`; the allocated aggregate
  and the remainder keep a solid border, the free aggregate keeps the dashed border of free tiles
  (`bg-content-muted` is indistinguishable from the page background).
- The container's aspect ratio is an inline style derived from the shared constant rather than an
  arbitrary Tailwind value, so the CSS box and the layout maths cannot drift apart.
- Unknown utilisation: no inner fill, tooltip says "utilization unknown".
- Label hidden with a container query (each tile is a `@container`, the label shows from
  `@min-[5rem]`), with the CIDR always in the tooltip and `aria-label`.

**Rationale**: `dev/knowledge/frontend/theming.md` requires semantic tokens and forbids fixed
palette classes; `multiple-progress-bar.tsx` is the precedent for `color-mix` on `--accent-strong`.

## R11. Testing approach

**Decision**:

- Unit (Vitest, co-located `*.test.ts`): `parse-prefix-length`, `build-tree-map-tiles` (areas sum,
  aggregation, capped remainder, IPv4 and IPv6 extremes), `layout-tree-map` (rects inside bounds,
  area proportional to weight within 1e-6, no overlap).
- Component (Vitest browser mode, `frontend/app/tests/components/render.tsx`):
  `ip-prefix-tree-map-tile` for the three tile states and the 0, 50 and 100 percent fills; the
  disabled free tile when `permission.create.isAllowed` is false; the address-type empty state.
- E2E (`tests/e2e/ipam/test_ip_prefix_tree_map.py`, `shard_foundation`, `data_ipam_pools`): open
  10.0.0.0/8, click the "Tree Map" link, assert the three /16 links and the 10.3.0.0/16 free
  button; drill into 10.1.0.0/16 and assert the heading and the preserved query string; open
  10.0.0.0/16 and assert the empty state with the "IP Addresses" link; on a throwaway branch,
  create from a free tile and assert the new link appears.

**Rationale**: Mirrors the tiers the constitution names and the selectors the existing IPAM E2E
tests use (`get_by_role("link", name=...)` for tabs, `get_by_test_id("ip-prefix-available")` for
the available row).

## R12. Documentation and changelog

**Decision**: Add a "Tree Map" subsection under "Utilization" in `docs/docs/ipam/overview.mdx`
describing what the tiles mean and the cap, and a towncrier fragment created with
`towncrier create` of type `added`.

**Rationale**: The constitution requires user docs for new features and a changelog fragment for
every user-visible change.
