# Contract: the GraphQL surface dedicated to number pools

**Feature**: [spec.md](../spec.md) | **Data model**: [data-model.md](../data-model.md)

**Status**: GraphQL schema modification (ask-first list). Three new root query fields and their
types, hand-written in `graphql/queries/number_pool.py` and registered in
`graphql/schema.py::InfrahubBaseQuery`. The generic resource-pool queries keep their shape and
meaning; only their descriptions change (section "Generic queries frozen for number pools").

This contract is published by the contract change set and frozen: no later change set of the
slice renames, retypes or removes a field below (FR-018). The division data a scoped pool returns
is mocked at contract time (section "Mock partition at contract time"); everything else is real.

## Why a dedicated surface

Number pools carry what IP pools do not: several weighted ranges, an allocation scope, numbers a
user provides or attaches, and the provenance of each tracked number. The generic queries
`InfrahubResourcePoolUtilization` and `InfrahubResourcePoolAllocated` cannot carry that without
number-pool-only arguments and fields that would be empty for IP pools:

- `InfrahubResourcePoolAllocated` requires `resource_id` and ignores it for a number pool, so a
  range view lists the whole pool.
- Its `display_label` is the number itself and the holder's own label is not returned.
- Range rows come back as `IPPrefixUtilizationEdge` / `IPPoolUtilizationResource`, which are IP
  types.
- Only percentages are returned, so "50 of 100" cannot be shown reliably.

The three fields below follow the number-pool data model. The frontend builds the pool page, the
range view, the division view and the allocation list from them alone.

## Vocabulary

| Term | Meaning |
|---|---|
| allocation scope | The pool setting: the list of fields of the pool's kind that divide its space. Stored on the pool as `allocation_scope`. |
| scope in force | The subset of the allocation scope that the reading branch's schema defines on the kind, in scope order (FR-008). |
| division | One tuple of values of the scope in force, held by the holder of a tracked number. Derived at read time, never stored. |
| holder | The node whose attribute holds a tracked number. |
| in space | A value the pool can allocate: inside one of the pool's ranges, not among the attribute's `excluded_values` (single values or excluded ranges), and within the attribute's `min_value` and `max_value` when they are set. A value can sit inside a range and still be out of space. |

## SDL

```graphql
"""
Utilization of one number pool and of each of its ranges, with the allocation scope in force on
the request's branch. For a number pool, prefer this over InfrahubResourcePoolUtilization.
"""
type NumberPoolUtilization {
  """The pool's id, as given in pool_id."""
  id: String!
  """The pool's display label, read on the request's branch."""
  display_label: String!
  """
  Scope entries in force on the request's branch, in scope order. Empty for an unscoped pool,
  and for a scoped pool none of whose entries the branch's schema defines.
  """
  allocation_scope: [String!]!
  """
  Figures over the pool's whole space. On a scoped pool, the figures of the fullest division.
  """
  figures: NumberPoolUtilizationFigures!
  """The pool's ranges ordered by start, each with its own figures."""
  ranges: [NumberPoolRangeUtilization!]!
  """Number of allocation rows whose value lies outside the pool's space (in_space false)."""
  out_of_space_count: BigInt!
}

"""Absolute and relative utilization of one space: a pool, a range or a division."""
type NumberPoolUtilizationFigures {
  """Number of values the measured space holds. 0 when the pool has no range."""
  size: BigInt!
  """Distinct values of the space held on any live branch."""
  used: BigInt!
  """Distinct values of the space held on the default branch."""
  used_default_branch: BigInt!
  """Distinct values of the space held on other branches and not on the default branch."""
  used_branches: BigInt!
  """used as a percentage of size. 0 when size is 0."""
  utilization: Float!
  """used_default_branch as a percentage of size. 0 when size is 0."""
  utilization_default_branch: Float!
  """used_branches as a percentage of size. 0 when size is 0."""
  utilization_branches: Float!
}

"""One range of a number pool with its own figures."""
type NumberPoolRangeUtilization {
  """The range node's id."""
  id: String!
  """The range node's display label."""
  display_label: String!
  """First value of the range, included."""
  start: BigInt!
  """Last value of the range, included."""
  end: BigInt!
  """The range's allocation weight. 0 when the range declares none."""
  weight: BigInt!
  """
  Figures over the range's values. On a scoped pool, the figures of the division holding the most
  of this range's values.
  """
  figures: NumberPoolUtilizationFigures!
}

"""The divisions of one number pool, each with its figures."""
type NumberPoolDivisions {
  """Number of divisions listed."""
  count: Int!
  """Scope entries in force on the request's branch, in scope order."""
  allocation_scope: [String!]!
  """
  Every division occupied by a node of the pool's kind on any live branch, ordered by utilization
  descending then by display_label. An unscoped pool lists one division with no entry.
  """
  divisions: [NumberPoolDivision!]!
}

"""One division: a tuple of values of the scope in force."""
type NumberPoolDivision {
  """The entries' display labels joined with " / ". Empty for the division of an unscoped pool."""
  display_label: String!
  """One entry per scope entry in force, in scope order."""
  entries: [NumberPoolDivisionEntry!]!
  """Figures over the pool's space, or over the range given as range_id, for this division."""
  figures: NumberPoolUtilizationFigures!
}

"""The value one scope entry takes in a division."""
type NumberPoolDivisionEntry {
  """The scope entry, as stored on the pool ("site", "role")."""
  path: String!
  """
  Relationship entry: the peer's id. Attribute entry: the value as text. A holder holding nothing
  for the entry: an empty string.
  """
  value: String!
  """
  Relationship entry: the peer's display label, read on any branch, falling back to the peer's id
  when the peer cannot be read. Attribute entry: the value as text.
  """
  display_label: String!
  """Relationship entry: the peer's kind when the peer can be read. Otherwise null."""
  peer_kind: String
}

"""One entry of a division filter. Mirrors NumberPoolDivisionEntry."""
input NumberPoolDivisionEntryInput {
  """A scope entry in force on the request's branch."""
  path: String!
  """Relationship entry: the peer's id. Attribute entry: the value as text."""
  value: String!
}

"""A page of the numbers a pool tracks."""
type NumberPoolAllocations {
  """Number of rows matching the filters, before offset and limit."""
  count: BigInt!
  """The page, ordered by value, then branch, then holder id."""
  allocations: [NumberPoolAllocation!]!
}

"""One tracked number as held on one branch: one row per (record, branch-resolved value)."""
type NumberPoolAllocation {
  """The number held."""
  value: BigInt!
  """The branch on which the holder's attribute holds this value."""
  branch: String!
  """The node whose attribute holds the value, read on the row's branch."""
  holder: NumberPoolHolder!
  """The identifier given when the number was allocated, if any."""
  identifier: String
  """ALLOCATED when the pool picked the number, PROVIDED when a user gave it."""
  provenance: NumberPoolProvenance!
  """
  Whether the value lies inside the pool's space and counts in its figures: inside a range, not
  excluded by the attribute, within its min and max. False for an excluded or out-of-limits value
  even when a range holds it.
  """
  in_space: Boolean!
  """The range whose bounds hold the value. Null when no range holds it."""
  range: NumberPoolRangeRef
  """The holder's division on the row's branch, in scope order. Empty when the pool is unscoped."""
  division: [NumberPoolDivisionEntry!]!
}

"""The node holding a tracked number."""
type NumberPoolHolder {
  id: String!
  """The holder's human-friendly id. Null when its kind declares none."""
  hfid: [String!]
  kind: String!
  display_label: String!
}

"""A reference to one range of the pool."""
type NumberPoolRangeRef {
  id: String!
  display_label: String!
}

"""How the number a tracked attribute currently holds got there."""
enum NumberPoolProvenance {
  ALLOCATED
  PROVIDED
}

type Query {
  """Utilization of one number pool and of its ranges."""
  InfrahubNumberPoolUtilization(pool_id: String!): NumberPoolUtilization!

  """
  The divisions of one number pool with their figures, over the whole pool or over one range.
  Complete list, no pagination.
  """
  InfrahubNumberPoolDivisions(pool_id: String!, range_id: String): NumberPoolDivisions!

  """The numbers one number pool tracks, filtered and paginated."""
  InfrahubNumberPoolAllocations(
    pool_id: String!
    division: [NumberPoolDivisionEntryInput!]
    range_id: String
    in_space: Boolean
    branch: String
    provenance: NumberPoolProvenance
    offset: Int
    limit: Int
  ): NumberPoolAllocations!
}
```

## Arguments

| Argument | Queries | Meaning |
|---|---|---|
| `pool_id` | all three | The number pool. Required. |
| `range_id` | divisions, allocations | Divisions: figures restricted to the range's values, `size` equal to the range's size. Allocations: rows whose value the range holds. |
| `division` | allocations | Rows whose holder carries, for every given entry, the given value on at least one live branch (FR-007 union). A partial filter is allowed: on a `["site", "tenant"]` pool, `[{path: "site", value: "<A>"}]` returns every row held in site A across tenants. |
| `in_space` | allocations | `true`: rows counted in the figures. `false`: rows outside the pool's space. Omitted: both. |
| `branch` | allocations | Rows whose value is held on that branch. Omitted: rows from every live branch. |
| `provenance` | allocations | Rows with that provenance. |
| `offset`, `limit` | allocations | Page of the ordered, filtered rows. Defaults: `offset` 0, `limit` 10, as on `InfrahubResourcePoolAllocated`. |

Several filters combine with "and". `count` reports the filtered rows before `offset` and `limit`.

## Branch and time

The three queries read the pool, its ranges and its records branch-agnostically, as the pool is:
the records of a pool live on the global branch, and the values they reserve are read on every
live branch, under the liveness rule the allocation read uses (a value held by a non-deleting
branch, or still visible from a branch forked while the default branch held it).

| Read from | Branch |
|---|---|
| Pool, ranges, records | every live branch (branch-agnostic) |
| Values and the rows they produce | every live branch; `branch` on the row names which. The `branch` filter keeps rows for that branch only |
| Scope in force (`allocation_scope` on the results, the `path` accepted in a filter) | the request's branch (FR-008) |
| Division entries of a division row and of an allocation row | peer labels and kinds read on any branch; a row's `division` is the holder's division on the row's branch |
| `holder.display_label`, `holder.hfid` | the row's branch |
| `NumberPoolUtilization.display_label` | the request's branch |

The three queries honour the request's `at`: every read above is taken at that time.

## Ordering

| List | Order |
|---|---|
| `NumberPoolUtilization.ranges` | `start` ascending |
| `NumberPoolDivisions.divisions` | `figures.utilization` descending, then `display_label` ascending |
| `NumberPoolAllocations.allocations` | `value` ascending, then `branch`, then `holder.id` |

The divisions list is complete and not paginated; the frontend searches it locally. A row of the
allocations list is identified by `(holder.id, value, branch)`, which is unique under the
one-row-per-(record, branch-resolved value) rule.

## Refusals

| Condition | Error | Message |
|---|---|---|
| `pool_id` names no node, or a node that is not a `CoreNumberPool` | `NodeNotFoundError` | `Unable to find the node <pool_id> / CoreNumberPool in the database.` |
| `range_id` is not a range of the pool | `ValidationError` | `The selected pool_id=<pool_id> doesn't contain the requested range_id=<range_id>` |
| `division` given on a pool whose scope in force is empty (unscoped, or every entry unknown on the request's branch) | `ValidationError` | `The pool <pool_id> has no allocation scope in force on branch <branch>; the division filter cannot be applied` |
| a `division` entry's `path` is not in the scope in force | `ValidationError` | `The division entry '<path>' is not in the allocation scope in force on branch <branch>` |
| the same `path` twice in `division` | `ValidationError` | `The division entry '<path>' is given twice` |
| `branch` names no branch | `BranchNotFoundError` | `Branch: <branch> not found.` (existing) |

A `division` entry whose `path` is in force but whose `value` matches no holder is not refused; the
list is empty and `count` is 0. A `provenance` or `in_space` filter matching nothing behaves the
same way.

## Figures

`NumberPoolUtilizationFigures` is one block reused for the pool, each range and each division.
`used` is always a count of distinct values of the measured space, never of rows or records: a
value held by three holders consumes one value. `used_branches` counts values held on another
branch and not on the default branch, so `used == used_default_branch + used_branches`. The three
percentages keep the names and meaning of `PoolUtilization`.

| Space | `size` | `used` |
|---|---|---|
| pool | the number of in-space values: over every range, the values not excluded by the attribute and within its `min_value` / `max_value`. Computed from the range set, never from the deprecated `start_range` / `end_range` pair, which is null on a pool holding several ranges | distinct in-space values held |
| range | `end - start + 1` | distinct values between `start` and `end` held |
| division, whole pool | the pool's `size` | distinct in-space values held by holders in the division |
| division with `range_id` | the range's `size` | distinct values of the range held by holders in the division |

## Semantics per pool state

| Pool state | `allocation_scope` on results | `NumberPoolUtilization.figures` | `ranges[].figures` | `NumberPoolDivisions.divisions` | `NumberPoolAllocation.division` | `division` filter |
|---|---|---|---|---|---|---|
| unscoped | `[]` | pool-wide | per range | one row: `entries: []`, `display_label: ""`, figures equal to the pool's | `[]` | refused |
| scoped | the entries in force | the fullest division's figures (FR-011); at contract time, pool-wide | the division holding the most of the range's values (FR-017); at contract time, range-wide | one row per division occupied by a node of the kind on any live branch, 0 for a division holding no value; at contract time, the mock partition | the holder's division on the row's branch; at contract time, the mock division | accepted for paths in force |
| scoped, every entry unknown on the request's branch | `[]` | as unscoped (FR-008) | as unscoped | as unscoped | `[]` | refused |
| no range (every range deleted) | per the rows above | `size` 0, every count and percentage 0 | `[]` | per the rows above, with `size` 0 | `range: null` and `in_space: false` on every row | per the rows above |

The headline and a range row can name different divisions: the headline is the fullest over the
whole space, a range row the fullest within that range. Both are worst-case figures.

`range` and `in_space` are two different facts. A value the attribute lists in `excluded_values`,
or outside its `min_value` / `max_value`, can sit inside a range (`range` set) and still be out of
space (`in_space: false`): it does not count in any figure and `out_of_space_count` includes it. A
value no range holds has `range: null` and is always out of space. Every pool holds at least one
range since the migration that gave each existing pool the range its bounds described, so `range:
null` with `in_space: true` does not occur.

Because a holder's division is resolved as a union over live branches, one value can appear in
two divisions: a holder in site A on the default branch and moved to site C on branch `b1` puts
its value in A and in C. Per-division `used` figures therefore must not be summed; the pool's
`used` is the distinct count over the whole space.

A scoped pool's division list includes a division keyed by a peer that exists only on another
branch; its entry's `display_label` falls back to the peer's id and `peer_kind` is null.

## Mock partition at contract time

The contract change set ships the three queries with real data for everything except the
divisions of a scoped pool, which the division reads of later change sets compute. Until then:

| Field | At contract time | Replaced by |
|---|---|---|
| `NumberPoolUtilization.figures`, `ranges`, every `size` and `used` figure | real, computed by the resolvers from the range set, the attribute's `excluded_values` and its `min_value` / `max_value` | the shared effective-space calculation of P1 (IFC-3213), same definition, one implementation |
| `holder`, `branch`, `identifier`, `provenance`, `range` | real | unchanged |
| `in_space`, `out_of_space_count` | real, same definition as `size` | the shared effective-space calculation of P1 (IFC-3213) |
| divisions of a scoped pool, `division` on rows, the `division` filter | the mock partition below | the division reads of this slice |

The mock partition: every row of a scoped pool is put in one of three divisions named `mock-1`,
`mock-2` and `mock-3` by a stable hash of its holder's id (the id's integer value modulo three,
plus one). A mock division's `entries` carry the real scope paths in force on the request's
branch, each with `value` and `display_label` equal to the division's name and `peer_kind` null.
`NumberPoolDivisions` lists the three mock divisions, with figures computed over the rows in each
(a division with no row reports 0). A `division` filter `[{path: "<path in force>", value:
"mock-2"}]` returns the rows of `mock-2`; a `path` not in force is refused as in the final
behaviour; a `value` outside the three names returns an empty list. The three queries read the
same partition, so lists, filters and counts agree.

An unscoped pool never returns mock data. The mock is removed by the last change set of the
slice, and a test asserts that no value or label beginning with `mock-` is returned by any of the
three queries on a scoped pool (FR-019).

## Generic queries frozen for number pools

`InfrahubResourcePoolUtilization`, `InfrahubResourcePoolAllocated`, `PoolUtilization`,
`PoolAllocated`, `PoolAllocatedNode`, `IPPrefixUtilizationEdge` and `IPPoolUtilizationResource`
keep their shape and meaning. For a number pool they report pool-wide figures and the whole pool's
values, scope or not. GraphQL cannot deprecate a field for one pool kind, so no `@deprecated` is
added; their descriptions gain a note. The exported schema diff for them is description text only
(SC-B).

| Where | Note appended to the description |
|---|---|
| root field `InfrahubResourcePoolUtilization`, type `PoolUtilization` | `For a number pool this query reports pool-wide figures and ignores the pool's allocation scope; number-pool consumers read InfrahubNumberPoolUtilization and InfrahubNumberPoolDivisions instead.` |
| root field `InfrahubResourcePoolAllocated`, types `PoolAllocated` and `PoolAllocatedNode` | `For a number pool, resource_id is ignored, every value the pool tracks inside its bounds is listed and display_label is the value itself; number-pool consumers read InfrahubNumberPoolAllocations instead.` |

The frontend's `get-pool-utilization-from-api.ts` and `get-resource-allocated-from-api.ts` keep
working unchanged; their migration to the dedicated queries is its own ticket.

## Examples

The pool `VLANs` in the first three examples has no allocation scope and two ranges, `1 - 50`
weighted 10 and `51 - 100` with no weight. It tracks four values: 1 and 51 held on the default
branch `main`, 7 held on branch `b1` only, and 500 provided by a user on `main`, which no range
holds.

### Utilization of an unscoped pool

```graphql
query {
  InfrahubNumberPoolUtilization(pool_id: "17f3c0a2-…") {
    id
    display_label
    allocation_scope
    figures { size used used_default_branch used_branches utilization utilization_default_branch utilization_branches }
    ranges {
      id display_label start end weight
      figures { size used used_default_branch used_branches utilization }
    }
    out_of_space_count
  }
}
```

```json
{
  "InfrahubNumberPoolUtilization": {
    "id": "17f3c0a2-…",
    "display_label": "VLANs",
    "allocation_scope": [],
    "figures": {
      "size": 100, "used": 3, "used_default_branch": 2, "used_branches": 1,
      "utilization": 3.0, "utilization_default_branch": 2.0, "utilization_branches": 1.0
    },
    "ranges": [
      {
        "id": "17f3c1d4-…", "display_label": "1 - 50", "start": 1, "end": 50, "weight": 10,
        "figures": { "size": 50, "used": 2, "used_default_branch": 1, "used_branches": 1, "utilization": 4.0 }
      },
      {
        "id": "17f3c2e8-…", "display_label": "51 - 100", "start": 51, "end": 100, "weight": 0,
        "figures": { "size": 50, "used": 1, "used_default_branch": 1, "used_branches": 0, "utilization": 2.0 }
      }
    ],
    "out_of_space_count": 1
  }
}
```

### Divisions of an unscoped pool

```graphql
query { InfrahubNumberPoolDivisions(pool_id: "17f3c0a2-…") { count allocation_scope divisions { display_label entries { path } figures { size used } } } }
```

```json
{
  "InfrahubNumberPoolDivisions": {
    "count": 1,
    "allocation_scope": [],
    "divisions": [ { "display_label": "", "entries": [], "figures": { "size": 100, "used": 3 } } ]
  }
}
```

### Allocations of an unscoped pool outside its space

```graphql
query {
  InfrahubNumberPoolAllocations(pool_id: "17f3c0a2-…", in_space: false) {
    count
    allocations {
      value branch identifier provenance in_space
      holder { id hfid kind display_label }
      range { id display_label }
      division { path value }
    }
  }
}
```

```json
{
  "InfrahubNumberPoolAllocations": {
    "count": 1,
    "allocations": [
      {
        "value": 500, "branch": "main", "identifier": null, "provenance": "PROVIDED", "in_space": false,
        "holder": { "id": "17f3d001-…", "hfid": ["sw-core-01"], "kind": "InfraDevice", "display_label": "sw-core-01" },
        "range": null,
        "division": []
      }
    ]
  }
}
```

The pool `Device index` in the next three examples is scoped by `["site"]`, with ranges `1 - 50`
and `51 - 100`. Site A's devices hold forty values in `1 - 50`, site B's devices hold thirty in
`51 - 100`, and site C has devices but no value. Device `D1` of site A holds 5 on `main` and was
moved to site C on branch `b1`. The responses show the final behaviour; at contract time the same
requests return pool-wide `figures` and the mock partition.

### Utilization of a scoped pool

```graphql
query {
  InfrahubNumberPoolUtilization(pool_id: "2a91…") {
    allocation_scope
    figures { size used utilization }
    ranges { display_label figures { size used utilization } }
    out_of_space_count
  }
}
```

```json
{
  "InfrahubNumberPoolUtilization": {
    "allocation_scope": ["site"],
    "figures": { "size": 100, "used": 40, "utilization": 40.0 },
    "ranges": [
      { "display_label": "1 - 50", "figures": { "size": 50, "used": 40, "utilization": 80.0 } },
      { "display_label": "51 - 100", "figures": { "size": 50, "used": 30, "utilization": 60.0 } }
    ],
    "out_of_space_count": 0
  }
}
```

The headline is site A's 40 of 100 (the fullest division). Range `1 - 50` reports A's 40 of 50,
range `51 - 100` reports B's 30 of 50. The pool-wide distinct count, 70, appears on no figure of a
scoped pool.

### Divisions of a scoped pool, restricted to one range

```graphql
query {
  InfrahubNumberPoolDivisions(pool_id: "2a91…", range_id: "<id of 1 - 50>") {
    count
    allocation_scope
    divisions {
      display_label
      entries { path value display_label peer_kind }
      figures { size used used_default_branch used_branches utilization }
    }
  }
}
```

```json
{
  "InfrahubNumberPoolDivisions": {
    "count": 3,
    "allocation_scope": ["site"],
    "divisions": [
      {
        "display_label": "Site A",
        "entries": [ { "path": "site", "value": "a1…", "display_label": "Site A", "peer_kind": "LocationSite" } ],
        "figures": { "size": 50, "used": 40, "used_default_branch": 40, "used_branches": 0, "utilization": 80.0 }
      },
      {
        "display_label": "Site C",
        "entries": [ { "path": "site", "value": "c3…", "display_label": "Site C", "peer_kind": "LocationSite" } ],
        "figures": { "size": 50, "used": 1, "used_default_branch": 0, "used_branches": 1, "utilization": 2.0 }
      },
      {
        "display_label": "Site B",
        "entries": [ { "path": "site", "value": "b2…", "display_label": "Site B", "peer_kind": "LocationSite" } ],
        "figures": { "size": 50, "used": 0, "used_default_branch": 0, "used_branches": 0, "utilization": 0.0 }
      }
    ]
  }
}
```

Site C holds one value of the range: `D1`'s 5, through `b1`, on which `D1` sits in C, so C sorts
before B (1 of 50 against 0 of 50). Site B's thirty values lie in `51 - 100`, outside the range
given. Without `range_id` the same request lists the same three divisions with `size` 100, in the
order A (40), B (30), C (1).

### Allocations filtered on one division, a value present in two divisions

```graphql
query {
  InfrahubNumberPoolAllocations(pool_id: "2a91…", division: [{ path: "site", value: "a1…" }], limit: 2) {
    count
    allocations {
      value branch provenance
      holder { id display_label }
      range { display_label }
      division { path value display_label }
    }
  }
}
```

```json
{
  "InfrahubNumberPoolAllocations": {
    "count": 41,
    "allocations": [
      {
        "value": 1, "branch": "main", "provenance": "ALLOCATED",
        "holder": { "id": "d0…", "display_label": "D0" },
        "range": { "display_label": "1 - 50" },
        "division": [ { "path": "site", "value": "a1…", "display_label": "Site A" } ]
      },
      {
        "value": 5, "branch": "b1", "provenance": "ALLOCATED",
        "holder": { "id": "d1…", "display_label": "D1" },
        "range": { "display_label": "1 - 50" },
        "division": [ { "path": "site", "value": "c3…", "display_label": "Site C" } ]
      }
    ]
  }
}
```

`count` is 41: the forty values of site A's devices on `main`, plus `D1`'s value 5 as held on
`b1`, because `D1` carries site A on `main` (the FR-007 union keeps every row of a holder that
sits in the division on any live branch). The `b1` row's own `division` names site C, where `D1`
sits on that branch. Filtering on site C returns `D1`'s two rows, so value 5 is counted in A and
in C; the two divisions' `used` figures (40 and 1) must not be summed.

### A scoped pool read at contract time

```json
{
  "InfrahubNumberPoolDivisions": {
    "count": 3,
    "allocation_scope": ["site"],
    "divisions": [
      {
        "display_label": "mock-1",
        "entries": [ { "path": "site", "value": "mock-1", "display_label": "mock-1", "peer_kind": null } ],
        "figures": { "size": 100, "used": 24, "utilization": 24.0 }
      },
      { "display_label": "mock-2", "entries": [ { "path": "site", "value": "mock-2", "display_label": "mock-2", "peer_kind": null } ], "figures": { "size": 100, "used": 23, "utilization": 23.0 } },
      { "display_label": "mock-3", "entries": [ { "path": "site", "value": "mock-3", "display_label": "mock-3", "peer_kind": null } ], "figures": { "size": 100, "used": 23, "utilization": 23.0 } }
    ]
  }
}
```

## Generated artefacts touched

| Artefact | Change |
|---|---|
| `schema/schema.graphql` | the three root fields, ten object types, one input and one enum above; description text on the generic queries and types |
| `frontend/app/src/shared/api/graphql/generated/*` | regenerated by `pnpm codegen` |
| `backend/infrahub/core/protocols.py`, `python_sdk/infrahub_sdk/protocols.py` | unchanged by this contract (no new kind) |

Regenerate, never edit: `uv run invoke schema.generate-graphqlschema`, then
`cd frontend/app && pnpm codegen`. A snapshot test pins the SDL of every type above so a later
change set cannot rename, retype or remove a field.
