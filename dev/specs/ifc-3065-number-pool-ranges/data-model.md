# Data Model: Number Pools P1 — Weighted Ranges

**Feature**: [spec.md](spec.md) | **Plan**: [plan.md](plan.md)

## Graph kinds

### CoreNumberPoolRange (new)

| Property | Value |
|----------|-------|
| Namespace / name | `Core` / `NumberPoolRange` |
| Branch support | `AGNOSTIC` |
| Inherits | `CoreWeightedPoolResource` (gives `allocation_weight`, Number, optional; becomes agnostic through branch-support processing) |
| Menu / profile | `include_in_menu=False`, `generate_profile=False` |
| Display labels | `start__value`, `end__value` |
| Human-friendly id | none |

Attributes:

| Name | Kind | Optional | Notes |
|------|------|----------|-------|
| `start` | Number | no | inclusive lower bound |
| `end` | Number | no | inclusive upper bound, `>= start` |
| `allocation_weight` | Number | yes | inherited; `None` counts as 0 |

Relationships:

| Name | Peer | Cardinality | Optional | Kind | Identifier |
|------|------|-------------|----------|------|------------|
| `pool` | `CoreNumberPool` | one | no | `PARENT` | `numberpool__range` |

Validation (mutation layer and schema declaration):

| Rule | Where refused |
|------|---------------|
| `start <= end` | range mutation, `NumberPoolParameters` |
| No overlap with another range of the same pool; error names the clashing ranges | range mutation, pool mutation after a `ranges` edit, `NumberPoolParameters` |
| Parent pool `pool_type == Schema` | range create / update / delete refused, pointing at the default-branch schema |

A range partly or wholly outside the attribute's `[min_value, max_value]` is accepted. The
effective-space calculator clips it, and a range clipped to nothing counts as exhausted for
fullness. The pool decides where allocation draws from; the attribute's domain decides which
values are valid.

### CoreNumberPool (changed)

| Field | Before | After |
|-------|--------|-------|
| `start_range` | Number, required | Number, optional, `deprecation` set; mirrors the single range's start, `None` when the pool holds 0 or more than 1 range |
| `end_range` | Number, required | same as `start_range` for the end |
| `ranges` | absent | relationship to `CoreNumberPoolRange`, cardinality many, optional, `COMPONENT`, agnostic, identifier `numberpool__range` |
| everything else | unchanged | unchanged |

Invariant: after every write path that touches ranges (range mutation, pool mutation, upserter, synchronizer, migration), `sync_shorthand_from_ranges(pool)` has run. A pool whose shorthand disagrees with its range set is a bug.

Shorthand write rule on a user pool:

| Range count | `start_range` / `end_range` written |
|-------------|-------------------------------------|
| 0 | create one range with those bounds |
| 1 | rewrite that range's bounds in place, keep its identity and weight |
| more than 1 | refuse; message lists every range by bounds and id |
| any, together with `ranges` in the same write | refuse, conflicting spellings |

On a schema pool the existing default-branch refusal fires before any of the above.

### Reservation records (unchanged)

`IS_RESERVED` edges from the pool to `AttributeValueIndexed` nodes on `-global-`, `identifier` = owning object's uuid. Not modified by this slice. Visibility follows the effective segments passed to the read queries: a record whose value sits outside every segment is not returned, not counted, and returns when a covering range is added.

## Schema parameters

### NumberPoolParameters (changed, published contract)

| Field | Type | Default | Update marker | Notes |
|-------|------|---------|---------------|-------|
| `start_range` | `int \| None` | `None` | `VALIDATE_CONSTRAINT` | deprecated, use `ranges` |
| `end_range` | `int \| None` | `None` | `VALIDATE_CONSTRAINT` | deprecated, use `ranges` |
| `ranges` | `list[NumberPoolRangeParameters]` | `[]` | `VALIDATE_CONSTRAINT` | explicit ranges |
| `number_pool_id` | `str \| None` | `None` | `NOT_SUPPORTED` | unchanged |

### NumberPoolRangeParameters (new)

| Field | Type | Default |
|-------|------|---------|
| `start` | `int` | required |
| `end` | `int` | required |
| `weight` | `int \| None` | `None` |

`_sort_by = ["start", "end"]` so list diffing and merging work.

### Normalisation: `effective_ranges()`

| Declaration | Result |
|-------------|--------|
| `ranges` non-empty, shorthand absent | `ranges` |
| shorthand (one or both bounds), `ranges` empty | one range; a missing bound resolves to `1` (start) or `sys.maxsize` (end); weight `None` |
| neither | `[]` |
| both | validation error, never reaches normalisation |

Fields are never rewritten by validation. `get_pool_size()` is the sum of effective range sizes.

## Effective space (derived, in memory)

Module `backend/infrahub/pools/number_ranges.py`.

| Type | Fields |
|------|--------|
| `PoolRange` (frozen) | `id: str \| None`, `start: int`, `end: int`, `weight: int` (already defaulted to 0) |
| `EffectiveSegment` (frozen) | `start: int`, `end: int`, `range_id: str \| None`, `size` property |
| `EffectiveSpace` | built from `ranges: Sequence[PoolRange]` and the attribute's `NumberAttributeParameters \| None` |

Construction:

1. Clip each range to `[min_value, max_value]` when the attribute declares them; a range clipped to nothing yields no segment.
2. Subtract excluded single values and excluded ranges from each clipped range, splitting it into segments.
3. Order segments by their range's `(-weight, start)`, then by segment start inside a range.

Operations:

| Method | Returns |
|--------|---------|
| `segments` | ordered tuple of `EffectiveSegment` |
| `size` | sum of segment sizes; `0` for a pool with no ranges or no surviving segment |
| `as_query_ranges()` | `list[list[int]]` of `[start, end]` for `$ranges` |
| `contains(value)` | whether any segment holds the value |
| `range_for(value)` | the `range_id` of the segment holding the value, or `None` |
| `is_empty` | `size == 0` |

## Allocation (state machine)

```text
build EffectiveSpace
if space.is_empty                      -> PoolExhaustedError
taken = get_taken(space) if attribute.unique else {}
for segment in space.segments:
    cursor = segment.start
    loop:
        candidate = NumberPoolGetFree(cursor, segment.end)
        if candidate is None:          -> next segment
        if candidate in taken:         cursor = candidate + 1; continue (or next segment if > end)
        return candidate
PoolExhaustedError
```

## Utilization

| Figure | Source |
|--------|--------|
| size | `space.size` |
| used (all branches / default / others) | `NumberPoolGetAllocated(ranges=space.as_query_ranges())`, split by branch as today |
| per-range used | group used values by `space.range_for(value)` |
| ratios | `used / size`, `0.0` when size is 0 |

## Migration m079

| Step | Detail |
|------|--------|
| Preconditions | `minimum_version = 78` |
| Bootstrap | create the `CoreNumberPoolRange` schema node and the `ranges` relationship on `CoreNumberPool` in the database schema when absent (count guard) |
| Data | for every live `CoreNumberPool` with no `ranges` peer: create one `CoreNumberPoolRange(start=start_range, end=end_range)` on `-global-` linked through `ranges`, no weight |
| Idempotence | pools that already hold a range are skipped |
| Validation | number of live pools without ranges must be 0 |
| Version | `GRAPH_VERSION = 79` |

## Schema-created pool reconciliation

Input: `effective_ranges()` of the default-branch declaration, sorted by start. Existing ranges of the pool, sorted by start.

| Position | Action |
|----------|--------|
| both present | update bounds and weight in place when they differ |
| desired only | create |
| existing only | delete |
| after any change | `sync_shorthand_from_ranges` |

Records are never touched by reconciliation.
