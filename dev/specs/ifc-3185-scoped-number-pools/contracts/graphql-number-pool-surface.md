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

A division is not tied to a range. The divisions query lists the divisions of the pool with figures
over its whole space. The utilization query, given one division, reports that division over the
pool and over each range. The allocations query, given one division, lists its numbers with the
range holding each one.

## Vocabulary

| Term | Meaning |
|---|---|
| allocation scope | The pool setting: the list of fields of the pool's kind that divide its space. Stored on the pool as `allocation_scope`. |
| scope in force | The subset of the allocation scope that the reading branch's schema defines on the kind, in scope order (FR-008). |
| division | One tuple of values of the scope in force, held by the holder of a tracked number. Derived at read time, never stored. |
| holder | The node whose attribute holds a tracked number. |
| pool's space | The values the pool can allocate: inside one of the pool's ranges, not among the attribute's `excluded_values` (single values or excluded ranges), and within the attribute's `min_value` and `max_value` when they are set. |

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
  Figures over the pool's whole space. On a scoped pool, the figures of the division given as
  division, which a scoped pool requires.
  """
  figures: NumberPoolUtilizationFigures!
  """The pool's ranges ordered by start, each with its own figures."""
  ranges: [NumberPoolRangeUtilization!]!
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
  Figures over the range's values. On a scoped pool, the figures of the division given as
  division.
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
  Every division whose holders hold at least one value the pool tracks on any live branch, ordered
  by utilization descending then by display_label. An unscoped pool lists one division with no
  entry.
  """
  divisions: [NumberPoolDivision!]!
}

"""One division: a tuple of values of the scope in force."""
type NumberPoolDivision {
  """The entries' display labels joined with " / ". Empty for the division of an unscoped pool."""
  display_label: String!
  """One entry per scope entry in force, in scope order."""
  entries: [NumberPoolDivisionEntry!]!
  """Figures over the pool's whole space for this division."""
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
  """The range whose bounds hold the value."""
  range: NumberPoolRangeRef!
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
  """
  Utilization of one number pool and of its ranges. On a scoped pool, division is required and
  the figures are those of that division.
  """
  InfrahubNumberPoolUtilization(
    pool_id: String!
    division: [NumberPoolDivisionEntryInput!]
  ): NumberPoolUtilization!

  """
  The divisions of one number pool that hold at least one value, with their figures over the whole
  pool. Complete list, no pagination.
  """
  InfrahubNumberPoolDivisions(pool_id: String!): NumberPoolDivisions!

  """The numbers one number pool tracks, filtered and paginated."""
  InfrahubNumberPoolAllocations(
    pool_id: String!
    division: [NumberPoolDivisionEntryInput!]
    range_id: String
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
| `range_id` | allocations | Rows whose value the range holds. |
| `division` | utilization | One division: a value for every scope entry in force on the request's branch. Required on a pool whose scope in force is not empty, refused on one whose scope in force is empty. `figures` and `ranges[].figures` count the values held while the holder sits in the division on the row's branch (FR-007 union). A filter that omits an entry in force is refused (section "Refusals"). |
| `division` | allocations | Rows whose holder carries, for every given entry, the given value on at least one live branch (FR-007 union). A partial filter is allowed: on a `["site", "tenant"]` pool, `[{path: "site", value: "<A>"}]` returns every row held in site A across tenants. |
| `branch` | allocations | Rows whose value is held on that branch. Omitted: rows from every live branch. |
| `provenance` | allocations | Rows with that provenance. |
| `offset`, `limit` | allocations | Page of the ordered, filtered rows. Defaults: `offset` 0, `limit` 10, as on `InfrahubResourcePoolAllocated`. |

Several filters combine with "and". `count` reports the filtered rows before `offset` and `limit`.

The utilization query refuses a partial `division` and the allocations query accepts one, because
the first returns figures and the second returns rows. On a `["site", "tenant"]` pool, numbers are
unique per (site, tenant) pair, so (A, X) and (A, Y) can both hold 10. Figures over "site A, every
tenant" would count 10 once against a `size` of one division and match no space the pool allocates
from. A list of the rows held in site A, every tenant, stays correct.

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
| utilization only: `division` omitted on a pool whose scope in force is not empty | `ValidationError` | `The pool <pool_id> has an allocation scope in force on branch <branch>; give a division to read its utilization` |
| utilization only: `division` omits an entry in force on the request's branch | `ValidationError` | `The division filter must give a value for every allocation scope entry in force on branch <branch>; missing: <paths>`, where `<paths>` lists the missing entries in scope order, joined with ", " |
| a `division` entry's `path` is not in the scope in force | `ValidationError` | `The division entry '<path>' is not in the allocation scope in force on branch <branch>` |
| the same `path` twice in `division` | `ValidationError` | `The division entry '<path>' is given twice` |
| `branch` names no branch | `BranchNotFoundError` | `Branch: <branch> not found.` (existing) |

A `division` entry whose `path` is in force but whose `value` matches no holder is not refused; the
allocations list is empty and `count` is 0, and the utilization query reports every `used` figure
as 0. A `provenance` filter matching nothing behaves the same way.

## Figures

`NumberPoolUtilizationFigures` is one block reused for the pool, each range and each division.
`used` is always a count of distinct values of the measured space, never of rows or records: a
value held by three holders consumes one value. `used_branches` counts values held on another
branch and not on the default branch, so `used == used_default_branch + used_branches`. The three
percentages keep the names and meaning of `PoolUtilization`.

| Space | `size` | `used` |
|---|---|---|
| pool | the number of values of the pool's space: over every range, the values not excluded by the attribute and within its `min_value` / `max_value`. Computed from the range set, never from the deprecated `start_range` / `end_range` pair, which is null on a pool holding several ranges | distinct values of the pool's space held |
| range | `end - start + 1` | distinct values between `start` and `end` held |
| division, whole pool | the pool's `size` | distinct values of the pool's space held by holders in the division |
| division, one range (`ranges[].figures` with `division`) | the range's `size` | distinct values of the range held by holders in the division |

## Semantics per pool state

| Pool state | `allocation_scope` on results | `NumberPoolUtilization.figures` | `ranges[].figures` | `NumberPoolDivisions.divisions` | `NumberPoolAllocation.division` | `division` argument |
|---|---|---|---|---|---|---|
| unscoped | `[]` | pool-wide | per range | one row: `entries: []`, `display_label: ""`, figures equal to the pool's | `[]` | refused |
| scoped | the entries in force | the division given as `division`; refused without it (FR-011); at contract time, from the mock partition | the division given as `division` (FR-017); at contract time, from the mock partition | one row per division holding at least one tracked value on any live branch; at contract time, the mock partition | the holder's division on the row's branch; at contract time, the mock division | accepted for paths in force; complete on the utilization query |
| scoped, every entry unknown on the request's branch | `[]` | as unscoped (FR-008) | as unscoped | as unscoped | `[]` | refused |
| no range (every range deleted) | per the rows above | `size` 0, every count and percentage 0 | `[]` | per the rows above, with `size` 0 | no row: the allocations list is empty | per the rows above |

On a scoped pool the utilization query reports one division at a time: the headline and every
range row report the division given as `division`, including a range in which it holds no value
(`used` 0). The fullest division is the first row of `InfrahubNumberPoolDivisions`, which orders
the divisions by utilization descending.

The allocations query returns only values of the pool's space; a value the attribute excludes,
one beyond its `min_value` / `max_value`, or one no range holds is not listed and counts in no
figure.

Because a holder's division is resolved as a union over live branches, one value can appear in
two divisions: a holder in site A on the default branch and moved to site C on branch `b1` puts
its value in A and in C. Per-division `used` figures therefore must not be summed; the pool's
`used` is the distinct count over the whole space.

A scoped pool's division list includes a division keyed by a peer that exists only on another
branch; its entry's `display_label` falls back to the peer's id and `peer_kind` is null. A division
whose nodes exist but hold no value is not listed.

## Mock partition at contract time

The contract change set ships the three queries with real data for everything except the
divisions of a scoped pool, which the division reads of later change sets compute. Until then:

| Field | At contract time | Replaced by |
|---|---|---|
| `NumberPoolUtilization.figures`, `ranges`, every `size` and `used` figure | real, computed by the resolvers from the range set, the attribute's `excluded_values` and its `min_value` / `max_value` | the shared effective-space calculation of P1 (IFC-3213), same definition, one implementation |
| `holder`, `branch`, `identifier`, `provenance`, `range` | real | unchanged |
| the restriction of rows to the pool's space | real, same definition as `size` | the shared effective-space calculation of P1 (IFC-3213) |
| divisions of a scoped pool, `division` on rows, the `division` filter | the mock partition below | the division reads of this slice |

The mock partition: every row of a scoped pool is put in one of three divisions named `mock-1`,
`mock-2` and `mock-3` by a stable hash of its holder's id (the id's integer value modulo three,
plus one). A mock division's `entries` carry the real scope paths in force on the request's
branch, each with `value` and `display_label` equal to the division's name and `peer_kind` null.
`NumberPoolDivisions` lists the mock divisions that hold at least one row, with figures computed
over the rows in each. A `division` filter `[{path: "<path in force>", value: "mock-2"}]` returns
the rows of `mock-2` from the allocations query and the figures of `mock-2` from the utilization
query; a `path` not in force is refused as in the final behaviour; a `value` outside the three
names returns an empty list and zero figures. The three queries read the same partition, so lists,
filters and counts agree.

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
weighted 10 and `51 - 100` with no weight. It tracks three values: 1 and 51 held on the default
branch `main`, and 7 held on branch `b1` only.

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
    ]
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

### Allocations of an unscoped pool in one range

```graphql
query {
  InfrahubNumberPoolAllocations(pool_id: "17f3c0a2-…", range_id: "17f3c1d4-…") {
    count
    allocations {
      value branch identifier provenance
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
    "count": 2,
    "allocations": [
      {
        "value": 1, "branch": "main", "identifier": null, "provenance": "ALLOCATED",
        "holder": { "id": "17f3d001-…", "hfid": ["sw-core-01"], "kind": "InfraDevice", "display_label": "sw-core-01" },
        "range": { "id": "17f3c1d4-…", "display_label": "1 - 50" },
        "division": []
      },
      {
        "value": 7, "branch": "b1", "identifier": null, "provenance": "ALLOCATED",
        "holder": { "id": "17f3d002-…", "hfid": ["sw-core-02"], "kind": "InfraDevice", "display_label": "sw-core-02" },
        "range": { "id": "17f3c1d4-…", "display_label": "1 - 50" },
        "division": []
      }
    ]
  }
}
```

The pool `Device index` in the next three examples is scoped by `["site"]`, with ranges `1 - 50`
and `51 - 100`. Site A's devices hold forty values in `1 - 50`, site B's devices hold thirty in
`51 - 100`, and site C has devices but no value of its own. Device `D1` of site A holds 5 on
`main` and was moved to site C on branch `b1`. Site D has devices and no value on any branch. The
responses show the final behaviour; at contract time the same requests return the mock
partition.

### Divisions of a scoped pool

```graphql
query {
  InfrahubNumberPoolDivisions(pool_id: "2a91…") {
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
        "figures": { "size": 100, "used": 40, "used_default_branch": 40, "used_branches": 0, "utilization": 40.0 }
      },
      {
        "display_label": "Site B",
        "entries": [ { "path": "site", "value": "b2…", "display_label": "Site B", "peer_kind": "LocationSite" } ],
        "figures": { "size": 100, "used": 30, "used_default_branch": 30, "used_branches": 0, "utilization": 30.0 }
      },
      {
        "display_label": "Site C",
        "entries": [ { "path": "site", "value": "c3…", "display_label": "Site C", "peer_kind": "LocationSite" } ],
        "figures": { "size": 100, "used": 1, "used_default_branch": 0, "used_branches": 1, "utilization": 1.0 }
      }
    ]
  }
}
```

Site C is listed because `D1` holds 5 there through `b1`. Site D is not listed: its devices hold no
value.

### Utilization of one division

```graphql
query {
  InfrahubNumberPoolUtilization(pool_id: "2a91…", division: [{ path: "site", value: "a1…" }]) {
    allocation_scope
    figures { size used utilization }
    ranges { display_label figures { size used utilization } }
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
      { "display_label": "51 - 100", "figures": { "size": 50, "used": 0, "utilization": 0.0 } }
    ]
  }
}
```

Site A holds forty values in `1 - 50` and none in `51 - 100`. With `[{ path: "site", value: "b2…"
}]` the same request reports 30 of 100, 0 of 50 and 30 of 50.

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
