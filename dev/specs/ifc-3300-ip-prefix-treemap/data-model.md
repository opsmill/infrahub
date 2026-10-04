# Data Model: IP Prefix Tree Map

**Date**: 2026-10-03 | **Spec**: [spec.md](spec.md) | **Research**: [research.md](research.md)

No stored entity changes. Every type below is a frontend domain type derived on read from the
existing `BuiltinIPPrefix` query. Module: `frontend/app/src/entities/ipam/ip-prefixes/domain/model/ip-prefix-tree-map.ts`.

## Constants

| Name | Value | Used by |
|------|-------|---------|
| `TREE_MAP_CHILD_LIMIT` | `1000` | query variable `limit`, cap notice |
| `TREE_MAP_CELL_DEPTH` | `12` (a block more than 12 bits narrower than the parent, below 1/4096 of its space, is aggregated into the `/(parent length + 12)` cell that contains it) | aggregation rule |
| `TREE_MAP_ASPECT_RATIO` | `2` (width over height) | layout and container CSS |

## Types

### `PrefixSize`

A placed CIDR block. Built by `domain/rules/prefix-size.ts` from the API's prefix attribute, which
supplies the length and the family; only the network address is parsed from the CIDR string.

| Field | Type | Notes |
|-------|------|-------|
| `family` | `"ipv4" \| "ipv6"` | from `prefix.version` (4 or 6) |
| `prefixLength` | `number` | from `prefix.prefixlen`, 0 to 32 or 0 to 128 |
| `networkAddress` | `bigint` | the parsed address masked to the prefix length |
| `addressCount` | `bigint` | `2n ** BigInt(maxLength - prefixLength)` |

Validation: throws a plain error for an unknown version, a length outside the family range, or an
address that does not parse (IPv4 dotted quads; IPv6 with `::` compression and embedded IPv4).
Callers treat a throw as a malformed response and drop the node. The same module provides the block
end, CIDR formatting (IPv6 zero-run compression), the aligned block containing an address at a
given length, and the decomposition of an arbitrary address range into aligned CIDR blocks.

### `TreeMapChild`

One real child prefix, mapped from a node whose `__typename` is not the available kind.

| Field | Type | Source |
|-------|------|--------|
| `id` | `string` | `node.id` |
| `kind` | `string` | `node.__typename`, used to build the drill-down URL |
| `cidr` | `string` | `node.prefix.value` |
| `size` | `PrefixSize` | built from `node.prefix.value`, `node.prefix.prefixlen` and `node.prefix.version` |
| `memberType` | `"prefix" \| "address"` | `node.member_type.value` |
| `isPool` | `boolean` | `node.is_pool.value === true`; a pool tile takes the pool colour family |
| `utilization` | `number \| null` | `node.utilization.value`; `null` means unknown |
| `description` | `string \| null` | `node.description.value` |
| `memberCount` | `number` | `children.count` when `memberType` is `prefix`, else `ip_addresses.count` |

### `TreeMapFreeBlock`

One available block, mapped from a node whose `__typename` is `InternalIPPrefixAvailable`.

| Field | Type | Source |
|-------|------|--------|
| `cidr` | `string` | `node.prefix.value` |
| `size` | `PrefixSize` | built from `node.prefix.value`, `node.prefix.prefixlen` and `node.prefix.version` |

### `TreeMapParent`

The parent prefix, mapped from the aliased `parent` root field of the same query.

| Field | Type | Source |
|-------|------|--------|
| `id` | `string` | `node.id` |
| `kind` | `string` | `node.__typename`, used to build the Children tab URL |
| `cidr` | `string` | `node.prefix.value` |
| `size` | `PrefixSize` | built from the prefix fields as for a child |
| `memberType` | `"prefix" \| "address"` | `node.member_type.value` |
| `utilization` | `number \| null` | `node.utilization.value` |

The use-case throws when the query returns no usable parent, and the tab shows the standard error
state.

### `TreeMapData`

The composed screen model, returned whole by the use-case
`domain/use-cases/get-ip-prefix-tree-map.ts`; the page passes only the parent id in.

| Field | Type | Notes |
|-------|------|-------|
| `parent` | `TreeMapParent` | from the same query |
| `children` | `TreeMapChild[]` | address order as returned; a child whose prefix cannot be placed is dropped with a console warning |
| `freeBlocks` | `TreeMapFreeBlock[]` | address order as returned |
| `totalChildCount` | `number` | the query's `count` less the children dropped as unplaceable, never below `children.length` |
| `isCapped` | `boolean` | `totalChildCount > children.length` |

### `TreeMapTile`

Output of `domain/rules/build-tree-map-tiles.ts`. A discriminated union on `kind`.

| `kind` | Extra fields | Interaction |
|--------|--------------|-------------|
| `"allocated"` | `child: TreeMapChild` | link to the child's Tree Map tab |
| `"free"` | `block: TreeMapFreeBlock` | button opening the create sheet, gated by permission |
| `"aggregate-allocated"` | `children: TreeMapChild[]`, `freeBlocks: TreeMapFreeBlock[]` | one per cell holding at least one small prefix; link to the parent's Children tab, hover lists members (free ones marked) |
| `"aggregate-free"` | `freeBlocks: TreeMapFreeBlock[]` | one per cell holding only small free blocks; no action, hover lists members |
| `"not-loaded"` | `hiddenChildCount: number` | one per aligned block of the not-loaded range; link to the parent's Children tab; present only when `isCapped` |

Common fields on every tile:

| Field | Type | Notes |
|-------|------|-------|
| `key` | `string` | stable React key (the tile's CIDR, prefixed by kind for aggregates and not-loaded blocks) |
| `size` | `PrefixSize` | the block the tile occupies: the prefix itself, the cell for an aggregate, the aligned block for a not-loaded tile |
| `label` | `string` | CIDR, "`<cell CIDR>`: N smaller prefixes", "`<cell CIDR>`: N smaller free blocks", or "Not loaded" |

Tiles are emitted in network-address order.

Invariants enforced by the rule and asserted in its tests:

- The sum of `size.addressCount` over all tiles equals `parent.size.addressCount` exactly.
- No two tiles describe overlapping address ranges, and the tiles are sorted by network address.
- A block more than `TREE_MAP_CELL_DEPTH` bits narrower than the parent never appears as
  `allocated` or `free`; it is counted in the aggregate of the cell that contains it.
- When `isCapped`, the not-loaded tiles cover exactly the range from the end of the last fetched
  block (child or free) to the end of the parent, decomposed into aligned CIDR blocks; when the
  map is not capped there are none.

### `TreeMapRect`

Output of `domain/rules/layout-tree-map.ts`, which takes the tiles and the parent's `PrefixSize`,
one rect per tile, in the same order as the input.

| Field | Type | Notes |
|-------|------|-------|
| `tile` | `TreeMapTile` | |
| `x`, `y` | `number` | percent of container, 0 to 100 |
| `width`, `height` | `number` | percent of container |

Placement is by address along a Hilbert curve over the parent's space: a block at an even depth
below the parent is one curve cell (a square), a block at an odd depth is the bounding box of two
consecutive cells (a 2:1 rectangle). Invariants asserted in tests: every rect lies inside the unit
container, no two rects overlap, `width * height / 10000` equals
`tile.size.addressCount / parent.addressCount` within 1e-6, and any two tiles whose blocks are
consecutive in address space share an edge. No sorting happens in the layout; the tile builder's
address order is preserved.

## State transitions

None. The map is a pure projection of the query result; the only client state is the open or closed
create sheet and the hovered tile.
