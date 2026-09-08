# Data Model: Number Pools — Several Weighted Ranges per Pool (P1)

## Entities

### CoreNumberPoolRange (new core kind)

One numeric interval a pool draws from.

| Field | Type | Required | Notes |
|-------|------|----------|-------|
| `start` | Number | yes | Inclusive lower bound of the range. |
| `end` | Number | yes | Inclusive upper bound. `start <= end`. |
| `allocation_weight` | Number | no | Inherited from `CoreWeightedPoolResource`. Absent counts as zero. Higher weight is drawn from first. |
| `pool` | Relationship → `CoreNumberPool` | yes (cardinality one) | Owning pool. Mandatory: a range belongs to exactly one pool. |

- **Kind**: `CoreNumberPoolRange`; `inherit_from=[CoreWeightedPoolResource]`; `branch=AGNOSTIC` (see research D2).
- **Declared in**: `backend/infrahub/core/schema/definitions/core/resource_pool.py`; registered in `.../core/__init__.py`; protocol in `backend/infrahub/core/protocols.py`.
- **Constraints**: `start <= end` (mutation guard). Within one pool, ranges MUST NOT overlap (FR-004). Across pools, overlap is permitted.

### CoreNumberPool (modified)

| Field | Change | Notes |
|-------|--------|-------|
| `start_range` | `required` → `optional=True` | Write-shorthand that creates/replaces the single range. Read: value only when the pool holds exactly one range, else null. |
| `end_range` | `required` → `optional=True` | Same as above. |
| `ranges` | **new** relationship → `CoreNumberPoolRange` (cardinality many) | The general multi-range representation. |
| `node`, `node_attribute`, `pool_type` | unchanged | — |

- Branch: unchanged (`AGNOSTIC`).
- No schema relationship existed before; `ranges` is the first (allocation node↔value links remain the runtime `IS_RESERVED`/`HAS_SOURCE` edges).

### Effective space (derived, not stored)

The allocatable set for a pool. Computed, never persisted.

```
effective_space(pool, attribute) =
    ( ⋃ range in pool.ranges of [range.start, range.end] )
    ∩ [attribute.min_value, attribute.max_value]
    − { x ∈ attribute.excluded_values : x lies inside some range ∩ [min,max] }
```

Derived quantities, all from this one definition (research D5):
- **size** = count of the effective space (0 when no ranges, or all ranges clamp empty).
- **utilization** = used ÷ size, reported as 0% when size is 0 (no division by zero).
- **allocation order** = ranges considered by descending `allocation_weight`, then ascending value; lowest free value within the chosen range; fall through to the next range across gaps.
- **fullness** = every effective range exhausted (a range clamping to empty counts as exhausted).

### NumberPoolParameters (modified — schema-created pools)

`backend/infrahub/core/schema/attribute_parameters.py`

| Field | Change | Notes |
|-------|--------|-------|
| `start_range` | default `1` → `None` | So "both spellings set" is detectable (FR-041). |
| `end_range` | default `sys.maxsize` → `None` | Same. |
| `ranges` | **new** optional list of `{start, end, weight}` | Schema-declared multi-range pools (FR-039). |
| validator | **new** | Refuse supplying both the single shorthand and an explicit `ranges` list. |
| `get_pool_size()` | reimplemented | Defer to the effective-space calculator. |

## Held-number record (unchanged in P1)

The `IS_RESERVED` edge (pool → `AttributeValue`, on `-global-`, `identifier` = owning node UUID) and `HAS_SOURCE` edge (attribute → pool) are unchanged in P1. Liveness join `res.identifier = n.uuid` still governs whether a number counts (the standing comment in `resource_manager.py`). Provenance and lifecycle changes are P2.

**FR-002a retention**: a held number outside every current effective range keeps its `IS_RESERVED` edge; it is filtered out by the effective-space read path (invisible to allocation, excluded from utilization) and reappears when a covering range returns. No edge is deleted on range removal.

## State transitions — a held number vs. the pool's ranges

| From | Event | To | Counts toward utilization? | Allocatable? |
|------|-------|----|----------------------------|--------------|
| in an effective range | range removed | outside every range (retained) | no | no |
| outside every range (retained) | covering range re-added | in an effective range | yes | no (still held) |
| in an effective range | attribute min/max narrows past it | outside effective space (retained) | no | no |
| any | object/edge liveness lost (P2 territory) | freed | no | yes |

## Query parameter shape change (research D6)

`NumberPoolGetFree` / `GetUsed` / `GetAllocated` / `GetReserved` / `GetTaken` in `backend/infrahub/core/query/resource_manager.py` move from scalar `$start_range` / `$end_range` to a **list of ranges** `[{start, end, weight}, ...]`. Value-in-range filters become an `ANY`/`OR` over the intervals; the `NumberPoolGetFree` gap walk resumes at the next range's start after exhausting a range. Gap detection stays in Cypher.

## Migration

`m0NN_number_pool_single_range` (`ArbitraryMigration`, modelled on `m066_consolidate_duplicate_number_pools`): for each `CoreNumberPool`, create one `CoreNumberPoolRange` [`start_range`, `end_range`], weight absent, linked via `ranges`. `IS_RESERVED` / `HAS_SOURCE` untouched. `minimum_version` set to the current schema version; registered as `Migration0NN` in `.../graph/__init__.py`.
