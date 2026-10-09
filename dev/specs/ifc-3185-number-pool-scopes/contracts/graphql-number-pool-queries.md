# Contract: the three dedicated number-pool queries

The surface is the one described in PR #10932, served from the database. This file lists the full SDL, and the table below lists the changes relative to the PR description.

## Changes relative to PR #10932

| Where | PR #10932 | This contract | Kind of change |
|-------|-----------|---------------|----------------|
| `NumberPoolUtilization.allocation_scope`, `NumberPoolDivisions.allocation_scope` | `[String!]!` (element names) | `[NumberPoolScopeElement!]!` with `id` and `name` | Breaking (decision 4 and 5) |
| `NumberPoolDivisionEntry` | `path`, `value`, `display_label`, `peer_kind` | adds `id: String!`, the schema element id of the entry | Additive |
| Descriptions mentioning "the scope in force on the request's branch" | scope could be partial on a branch | the scope is the pool's scope on every branch; a query on a branch whose schema lacks an element is refused | Wording and one refusal (decisions 1 and 7) |
| Division of a holding object | counted under every division the object occupies on any live branch | read on the branch the query runs on | Changed (decision 7) |
| Enum of `NumberPoolAllocation.provenance` and of the `provenance` argument | `NumberPoolProvenance`, a type of its own | `PoolRecordProvenance`, the enum that `InfrahubResourcePoolAllocated` already returns, with the same values `ALLOCATED` and `PROVIDED` | Breaking for a client that names the type in a query variable |

Everything else (root fields, arguments, defaults, ordering, pagination, holder and range references) is unchanged. PR #10932 is open against another branch; it is rebased onto `feature-number-pools-1.12`, and its fixed dataset and tests are updated to this contract before the resolvers read the database.

## SDL

```graphql
"""One attribute or relationship of a pool's allocation scope."""
type NumberPoolScopeElement {
  """The schema element id of the attribute or relationship, on the default branch."""
  id: String!
  """The attribute or relationship name, as currently declared on the default branch."""
  name: String!
}

"""
Utilization of one number pool and of each of its ranges. For a number pool, prefer this over
InfrahubResourcePoolUtilization.
"""
type NumberPoolUtilization {
  """The pool's id, as given in pool_id."""
  id: String!
  """The pool's display label."""
  display_label: String!
  """The pool's allocation scope, in scope order. Empty for an unscoped pool."""
  allocation_scope: [NumberPoolScopeElement!]!
  """
  Figures over all the values the pool can allocate. On a scoped pool, only the values held in the
  division passed in the division argument, which is required.
  """
  figures: NumberPoolUtilizationFigures!
  """The pool's ranges ordered by start, each with its own figures."""
  ranges: [NumberPoolRangeUtilization!]!
}

"""Absolute and relative utilization of a pool, a range or a division."""
type NumberPoolUtilizationFigures {
  """Number of values the pool, range or division can allocate. 0 when the pool has no range."""
  size: BigInt!
  """Number of these values in use on any branch. A value used on several branches counts once."""
  used: BigInt!
  """Number of these values in use on the default branch."""
  used_default_branch: BigInt!
  """Number of these values in use only on other branches, not on the default branch."""
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
  """Figures over the range's values. On a scoped pool, only the values held in the division passed in the division argument."""
  figures: NumberPoolUtilizationFigures!
}

"""The divisions of one number pool, each with its figures."""
type NumberPoolDivisions {
  """Number of divisions listed."""
  count: Int!
  """The pool's allocation scope, in scope order."""
  allocation_scope: [NumberPoolScopeElement!]!
  """
  Every division that holds at least one value the pool tracks on any live branch. Each holding object's
  division is read on the request's branch. Ordered by utilization descending, then by display_label.
  Empty for an unscoped pool.
  """
  divisions: [NumberPoolDivision!]!
}

"""One combination of values of the allocation scope, with its own number space."""
type NumberPoolDivision {
  """The entries' display labels joined with " / "."""
  display_label: String!
  """One entry per scope element, in scope order."""
  entries: [NumberPoolDivisionEntry!]!
  """Figures for this division, over all the values the pool can allocate."""
  figures: NumberPoolUtilizationFigures!
}

"""One attribute or relationship of the allocation scope and the value a division holds for it."""
type NumberPoolDivisionEntry {
  """The schema element id of the attribute or relationship."""
  id: String!
  """The name of the scope attribute or relationship."""
  path: String!
  """
  For a relationship, the peer's id. For an attribute, the value as text. An empty string when the
  holding object has no value for it.
  """
  value: String!
  """
  For a relationship, the peer's display label read on any branch, or the peer's id when the peer
  cannot be read. For an attribute, the value as text.
  """
  display_label: String!
  """For a relationship, the peer's kind when the peer can be read. Null otherwise."""
  peer_kind: String
}

"""One attribute or relationship of the allocation scope and the value the requested division holds for it."""
input NumberPoolDivisionEntryInput {
  """The name of the scope attribute or relationship."""
  path: String!
  """For a relationship, the peer's id. For an attribute, the value as text."""
  value: String!
}

"""A page of the numbers a pool tracks."""
type NumberPoolAllocations {
  """Number of rows matching the filters, before offset and limit."""
  count: BigInt!
  """The page, ordered by value, then branch, then the holding object's id."""
  allocations: [NumberPoolAllocation!]!
}

"""One tracked number as held on one branch. A number held on several branches gives one row per branch."""
type NumberPoolAllocation {
  """The number held."""
  value: BigInt!
  """The branch on which the holding object's attribute holds this value."""
  branch: String!
  """The node whose attribute holds the value, read on the row's branch."""
  holder: NumberPoolHolder!
  """The identifier given when the number was allocated, if any."""
  identifier: String
  """ALLOCATED when the pool picked the number, PROVIDED when a user gave it."""
  provenance: PoolRecordProvenance!
  """The range whose bounds hold the value."""
  range: NumberPoolRangeRef!
}

"""The node holding a tracked number."""
type NumberPoolHolder {
  id: String!
  """The holding object's human-friendly id. Null when its kind declares none."""
  hfid: [String!]
  kind: String!
  display_label: String!
}

"""A reference to one range of the pool."""
type NumberPoolRangeRef {
  id: String!
  display_label: String!
}

"""Whether the pool allocated a value or a user provided it."""
enum PoolRecordProvenance {
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
  pool.
  """
  InfrahubNumberPoolDivisions(pool_id: String!): NumberPoolDivisions!

  """The numbers one number pool tracks, filtered and paginated."""
  InfrahubNumberPoolAllocations(
    pool_id: String!
    division: [NumberPoolDivisionEntryInput!]
    range_id: String
    branch: String
    provenance: PoolRecordProvenance
    offset: Int
    limit: Int
  ): NumberPoolAllocations!
}
```

## Behaviour

- `InfrahubNumberPoolUtilization`: on a scoped pool, `division` is required and must give a value for every scope element; the figures are those of that division over the pool and over each range. On an unscoped pool, `division` is refused and the figures cover the whole pool.
- `InfrahubNumberPoolDivisions`: only the divisions holding at least one tracked value; figures over the whole pool; ordered by `utilization` descending then `display_label`. Empty list and empty scope on an unscoped pool.
- The division of a holding object is read on the branch the query runs on, as a normal branch read: an object moved to another site on branch `b1` counts under the new site on `b1` and under the old site on the default branch; an object that exists only on another branch is not counted. Each value counts in one division per branch read.
- `InfrahubNumberPoolAllocations`: all arguments except `pool_id` optional; `offset` defaults to 0, `limit` to 10; rows are the values inside the pool's space (inside one of its ranges, not excluded by the attribute, within its `min_value` and `max_value`); `division` may name a subset of the scope elements; rows ordered by value, branch and the holding object's id; `count` is the number of rows before pagination.
- The existing `InfrahubResourcePoolUtilization` and `InfrahubResourcePoolAllocated` keep their shape; for a number pool they ignore the scope and their descriptions point to the dedicated queries.

## Refusals

All are `ValidationError`.

| Case | Queries | Message |
|------|---------|---------|
| Scoped pool, `division` omitted or missing an element | `InfrahubNumberPoolUtilization` | `The pool <pool_id> has an allocation scope; give a division with a value for every element to read its utilization` |
| Unscoped pool, `division` given | `InfrahubNumberPoolUtilization`, `InfrahubNumberPoolAllocations` | `The pool <pool_id> has no allocation scope; the division filter cannot be applied` |
| `division` names a path that is not a scope element, or names one twice | all three with `division` | `The division entry "<path>" is not an element of the pool's allocation scope` |
| `pool_id` is not a number pool | all three | `NodeNotFoundError` for `CoreNumberPool` |
| `range_id` is not a range of the pool | `InfrahubNumberPoolAllocations` | `The range <range_id> does not belong to the pool <pool_id>` |
| Negative `offset` or `limit` | `InfrahubNumberPoolAllocations` | `<argument> must be 0 or greater` |
| The schema of the request's branch does not define a scope element on the pool's kind | all three | `The scope element "<name>" of pool <pool_id> does not exist on <kind> on branch <branch>; rebase the branch to get it` |

`InfrahubNumberPoolAllocations` on a scoped pool without `division` is not an error: it lists the values of every division.

## Example

Pool scoped by `site`, ranges `1 - 50` and `51 - 100`; site A holds 40 values, site B holds 30 (3 of them only on branches other than the default branch), site D holds none. Device D1 holds 5 in site A on the default branch and was moved to site C on branch `b1`. Read on branch `b1`, the list holds sites A (39), B (30) and C (1); read on the default branch, it holds sites A (40) and B (30). The response below is the read on `b1`.

```graphql
query {
  InfrahubNumberPoolDivisions(pool_id: "2a91…") {
    count
    allocation_scope { id name }
    divisions {
      display_label
      entries { id path value display_label peer_kind }
      figures { size used used_default_branch used_branches utilization }
    }
  }
}
```

```json
{
  "count": 3,
  "allocation_scope": [{ "id": "17d0a4c2…", "name": "site" }],
  "divisions": [
    { "display_label": "Site A", "entries": [{ "id": "17d0a4c2…", "path": "site", "value": "a1…", "display_label": "Site A", "peer_kind": "LocationSite" }],
      "figures": { "size": 100, "used": 39, "used_default_branch": 39, "used_branches": 0, "utilization": 39.0 } },
    { "display_label": "Site B", "entries": [{ "id": "17d0a4c2…", "path": "site", "value": "b2…", "display_label": "Site B", "peer_kind": "LocationSite" }],
      "figures": { "size": 100, "used": 30, "used_default_branch": 27, "used_branches": 3, "utilization": 30.0 } },
    { "display_label": "Site C", "entries": [{ "id": "17d0a4c2…", "path": "site", "value": "c3…", "display_label": "Site C", "peer_kind": "LocationSite" }],
      "figures": { "size": 100, "used": 1, "used_default_branch": 1, "used_branches": 0, "utilization": 1.0 } }
  ]
}
```
