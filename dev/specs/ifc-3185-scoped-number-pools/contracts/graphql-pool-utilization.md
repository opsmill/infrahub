# Contract: per-division rows on the pool utilization query

**Feature**: [spec.md](../spec.md) | **Data model**: [data-model.md](../data-model.md)

**Status**: GraphQL schema modification (ask-first list). Hand-written types in
`graphql/queries/resource_manager.py`. Additive: every existing field of `PoolUtilization` keeps its
name, type and meaning for an unscoped pool.

This contract is published with the scope contract and frozen (FR-018). Its resolver first ships
with the placeholder behaviour described below (FR-019).

## New types

```graphql
type PoolDivisionEntry {
  path: String!           # the scope entry, as stored ("site", "role")
  value: String!          # relationship entry: the peer's id; attribute entry: the value as text;
                          # an object holding nothing for the entry: ""
  display_label: String!  # relationship entry: the peer's display label, read on any branch, falling
                          # back to the peer's id when the peer cannot be read; attribute entry: the value as text
  peer_kind: String       # relationship entry: the peer's kind when the peer can be read; otherwise null
}

type PoolDivisionUtilization {
  division: [PoolDivisionEntry!]!     # the entries in force on the reading branch, in scope order
  utilization: Float!
  utilization_default_branch: Float!
  utilization_branches: Float!
}

type PoolUtilization {
  count: BigInt!
  utilization: Float!
  utilization_branches: Float!
  utilization_default_branch: Float!
  edges: [IPPrefixUtilizationEdge!]!
  divisions: [PoolDivisionUtilization!]!    # new
}
```

## Semantics

| Pool | `divisions` | Headline figures | Per-range `edges` |
|---|---|---|---|
| Unscoped | exactly one row, `division: []`, figures equal to the headline | as today | as today |
| Scoped | one row per division occupied by an object of the kind on any live branch, ordered by `utilization` descending then by the entry values; a division with objects and no records reports 0 | the fullest division's figures (FR-011) | each range reports the fullest division within that range: the largest count, over divisions, of that range's values held in one division, against the range's size (FR-017) |
| Scoped, every entry unknown on the reading branch | as unscoped (FR-008) | as unscoped | as unscoped |
| IP pools | `[]` | unchanged | unchanged |

A division's `division` list carries only the entries in force on the reading branch, so the same
pool can report two-entry rows on one branch and one-entry rows on another. A division keyed by an
object that exists only on another branch is still listed; its label falls back to the identifier.

The headline and the per-range rows can name different divisions: the headline is the fullest over
the whole effective space, a range row the fullest within that range. Both are worst-case figures.

## Placeholder (FR-019)

Until the division reads land, the resolver returns the single empty-key row for every number
pool, scoped or not. That is the permanent behaviour for an unscoped pool and a transitional one
for a scoped pool. It is replaced before the slice ships; the frontend MUST NOT assume a scoped pool
returns one row.

## Example

```graphql
query { InfrahubResourcePoolUtilization(pool_id: "…") {
  utilization
  divisions {
    division { path value display_label peer_kind }
    utilization utilization_default_branch utilization_branches
  }
} }
```

```json
{ "utilization": 50.0,
  "divisions": [
    { "division": [{"path": "site", "value": "a1…", "display_label": "Site A", "peer_kind": "LocationSite"}],
      "utilization": 50.0, "utilization_default_branch": 50.0, "utilization_branches": 0.0 },
    { "division": [{"path": "site", "value": "b2…", "display_label": "Site B", "peer_kind": "LocationSite"}],
      "utilization": 0.0, "utilization_default_branch": 0.0, "utilization_branches": 0.0 }
  ] }
```

## Generated artefacts touched

`schema/schema.graphql`; frontend `shared/api/graphql/generated/*` via `pnpm codegen`. The frontend
query in `entities/resource-manager/api/get-pool-utilization-from-api.ts` is not changed by this
slice; the field is available for the deferred per-division view.
