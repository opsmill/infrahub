# Data Model: IP Prefix Tree Map

**Date**: 2026-10-03 | **Spec**: [spec.md](spec.md) | **Research**: [research.md](research.md)

No stored entity changes. Every type below is a frontend domain type derived on read from the
existing `BuiltinIPPrefix` query. Module: `frontend/app/src/entities/ipam/ip-prefixes/domain/model/ip-prefix-tree-map.ts`.

## Constants

| Name | Value | Used by |
|------|-------|---------|
| `TREE_MAP_CHILD_LIMIT` | `1000` | query variable `limit`, cap notice |
| `TREE_MAP_MIN_TILE_DIVISOR` | `4096n` (threshold is `parentCount / 4096n` in BigInt, i.e. 1/4096 of the parent) | aggregation rule |
| `TREE_MAP_ASPECT_RATIO` | `2` (width over height) | layout and container CSS |

## Types

### `PrefixSize`

Result of parsing a CIDR string. Rule: `domain/rules/parse-prefix-length.ts`.

| Field | Type | Notes |
|-------|------|-------|
| `family` | `"ipv4" \| "ipv6"` | from the presence of `:` |
| `prefixLength` | `number` | 0 to 32 or 0 to 128 |
| `addressCount` | `bigint` | `1n << BigInt(maxLength - prefixLength)` |

Validation: throws a domain error for a string without `/`, a length outside the family range, or a
family mismatch with the parent. Callers treat a throw as a malformed response.

### `TreeMapChild`

One real child prefix, mapped from a node whose `__typename` is not the available kind.

| Field | Type | Source |
|-------|------|--------|
| `id` | `string` | `node.id` |
| `kind` | `string` | `node.__typename`, used to build the drill-down URL |
| `cidr` | `string` | `node.prefix.value` |
| `size` | `PrefixSize` | parsed from `cidr` |
| `memberType` | `"prefix" \| "address"` | `node.member_type.value` |
| `utilization` | `number \| null` | `node.utilization.value`; `null` means unknown |
| `description` | `string \| null` | `node.description.value` |
| `memberCount` | `number` | `children.count` when `memberType` is `prefix`, else `ip_addresses.count` |

### `TreeMapFreeBlock`

One available block, mapped from a node whose `__typename` is `InternalIPPrefixAvailable`.

| Field | Type | Source |
|-------|------|--------|
| `cidr` | `string` | `node.prefix.value` |
| `size` | `PrefixSize` | parsed from `cidr` |

### `TreeMapData`

Output of the use-case `domain/use-cases/get-ip-prefix-tree-map.ts`.

| Field | Type | Notes |
|-------|------|-------|
| `parent` | `{ id: string; cidr: string; size: PrefixSize; memberType: "prefix" \| "address"; utilization: number \| null }` | from the detail page's parent node |
| `children` | `TreeMapChild[]` | address order as returned |
| `freeBlocks` | `TreeMapFreeBlock[]` | address order as returned |
| `totalChildCount` | `number` | the query's `count` |
| `isCapped` | `boolean` | `totalChildCount > children.length` |

### `TreeMapTile`

Output of `domain/rules/build-tree-map-tiles.ts`. A discriminated union on `kind`.

| `kind` | Extra fields | Interaction |
|--------|--------------|-------------|
| `"allocated"` | `child: TreeMapChild` | link to the child's Tree Map tab |
| `"free"` | `block: TreeMapFreeBlock` | button opening the create sheet, gated by permission |
| `"aggregate-allocated"` | `members: TreeMapChild[]` | link to the parent's Children tab |
| `"aggregate-free"` | `members: TreeMapFreeBlock[]` | no action, hover lists members |
| `"remainder"` | `hiddenChildCount: number` | link to the parent's Children tab; present only when `isCapped` |

Common fields on every tile:

| Field | Type | Notes |
|-------|------|-------|
| `key` | `string` | stable React key (CIDR, or the aggregate kind) |
| `addressCount` | `bigint` | exact |
| `weight` | `number` | `addressCount / parent.addressCount` as a six-digit fraction, sums to 1 across tiles within 1e-6 |
| `label` | `string` | CIDR, "N smaller prefixes", "N smaller free blocks", or "N more children" |

Invariants enforced by the rule and asserted in its tests:

- The sum of `addressCount` over all tiles equals `parent.size.addressCount` exactly.
- No two tiles describe the same address range.
- A tile with `addressCount < parent.addressCount / 4096n` never appears as `allocated` or `free`.
- `remainder.addressCount = parent.addressCount - sum(children) - sum(freeBlocks)` and is zero or
  positive; the tile is omitted when zero.

### `TreeMapRect`

Output of `domain/rules/layout-tree-map.ts`, one per tile, in the same order as the input.

| Field | Type | Notes |
|-------|------|-------|
| `tile` | `TreeMapTile` | |
| `x`, `y` | `number` | percent of container, 0 to 100 |
| `width`, `height` | `number` | percent of container |

Invariants asserted in tests: every rect lies inside the unit container, no two rects overlap, and
`width * height / 10000` equals `tile.weight` within 1e-6. Input tiles are sorted by `weight`
descending before layout, ties broken by address order, which the squarified algorithm requires.

## State transitions

None. The map is a pure projection of the query result; the only client state is the open or closed
create sheet and the hovered tile.
