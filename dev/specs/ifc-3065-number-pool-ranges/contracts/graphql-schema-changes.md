# Contract: GraphQL schema changes

**Feature**: [spec.md](../spec.md) | **Data model**: [data-model.md](../data-model.md)

Everything below is produced by the generic generator from the core schema definitions, except where a dedicated mutation class is named.

## New object type

```graphql
type CoreNumberPoolRange implements CoreNode & CoreWeightedPoolResource {
  id: String
  start: NumberAttribute
  end: NumberAttribute
  allocation_weight: NumberAttribute
  pool: NestedEdgedCoreNumberPool!
  # generic node fields as for every core kind
}
```

Generated mutations: `CoreNumberPoolRangeCreate`, `CoreNumberPoolRangeUpdate`, `CoreNumberPoolRangeUpsert`, `CoreNumberPoolRangeDelete`, with the generated `CoreNumberPoolRangeCreateInput` / `UpdateInput` / `UpsertInput` (`start`, `end`, `allocation_weight`, `pool: RelatedNodeInput`).

Generated queries: `CoreNumberPoolRange(...)` with the standard filters.

## Changed object type

```graphql
type CoreNumberPool implements CoreNode & CoreResourcePool & LineageSource {
  start_range: NumberAttribute @deprecated(reason: "Use ranges. start_range reflects the pool's single range and is null otherwise.")
  end_range: NumberAttribute @deprecated(reason: "Use ranges. end_range reflects the pool's single range and is null otherwise.")
  ranges: NestedPaginatedCoreNumberPoolRange
  # other fields unchanged
}
```

| Aspect | Before | After |
|--------|--------|-------|
| Type of `start_range` / `end_range` | `NumberAttribute` (nullable in SDL) | unchanged |
| Description suffix | "(required)" | removed |
| Deprecation | none | `@deprecated` on the object type, the interface projection, and the create / update / upsert inputs |
| Read value | always set | set when the pool holds exactly one range, otherwise `null` |
| Write | required on create | optional on create and update; see refusals |

## Dedicated mutation classes

### `InfrahubNumberPoolMutation` (existing, changed)

Every create or update that carries the shorthand or `ranges` runs under the pool lock.

| Input | Result |
|-------|--------|
| create with `start_range` and `end_range` only | pool created with one range; existing bound checks against `min_value` / `max_value` unchanged |
| create with `ranges` only | pool created; ranges linked; overlap validated |
| create with neither | pool created with zero ranges |
| create or update with shorthand and `ranges` | refused: "start_range/end_range cannot be combined with ranges" |
| update with shorthand, pool has 0 ranges | one range created |
| update with shorthand, pool has 1 range | that range rewritten in place |
| update with shorthand, pool has more than 1 range | refused: message states the shorthand applies to a pool holding at most one range and lists each range as `<start>-<end> (<id>)` |
| update with shorthand or `ranges` on `pool_type: Schema` | refused with the existing message "…update the schema in the default branch instead" (fires first) |
| update changing `node` or `node_attribute` | refused (unchanged) |

### `InfrahubNumberPoolRangeMutation` (new, registered for `CoreNumberPoolRange`)

| Operation | Checks, in order |
|-----------|------------------|
| create | pool lock taken; parent pool exists; pool not `Schema`; `start <= end`; no overlap with the pool's other ranges (message names them); bounds outside the attribute's `[min_value, max_value]` are accepted and clamped at allocation time |
| update | same as create against the pool's other ranges; the parent pool cannot change |
| delete | pool not `Schema` |
| after create / update / delete | pool's `start_range` / `end_range` re-synced from the range set |

## Utilization query

`InfrahubResourcePoolUtilization` for a number pool:

| Field | Before | After |
|-------|--------|-------|
| `count` | `1` | number of ranges |
| `utilization`, `utilization_default_branch`, `utilization_branches` | pool totals | pool totals over the effective space; `0` when the space is empty |
| `edges[].node.id` | pool id | range id |
| `edges[].node.kind` | `CoreNumberPool` | `CoreNumberPoolRange` |
| `edges[].node.display_label` | pool name | `<start>-<end>` |
| `edges[].node.weight` | `1` | `allocation_weight`, `0` when unset |
| `edges[].node.utilization*` | pool totals | per-range figures |

`InfrahubResourcePoolAllocated` for a number pool: unchanged shape; only records inside the effective space are listed.

## Deprecation propagation (general)

Any `deprecation` message on an attribute or relationship of any kind now appears as `@deprecated(reason: <message>)` on: the object type field, the interface field, the relationship field, and the create / update / upsert input fields. Filter arguments are not annotated.

## Error messages introduced

| Situation | Message |
|-----------|---------|
| shorthand and `ranges` together | `start_range/end_range cannot be combined with ranges` |
| shorthand on a multi-range pool | `start_range/end_range apply to a pool holding at most one range; this pool holds: 100-200 (<id>), 205-300 (<id>). Edit the ranges instead.` |
| overlapping range | `Range 150-250 overlaps 100-200 (<id>)` |
| backwards range | `Range end (100) cannot be lower than start (200)` |
| range edit on a schema pool | existing message pointing at the default-branch schema |
