# Data Model: Number pool allocation scopes

## Entities

### Number pool (`CoreNumberPool`, existing)

| Field | Type | Change | Notes |
|-------|------|--------|-------|
| `node` | Text, required | unchanged | Kind the pool is attached to (node or generic) |
| `node_attribute` | Text, required | unchanged | Tracked attribute of that kind |
| `start_range`, `end_range` | Number, optional, deprecated | unchanged | Single-range shorthand |
| `pool_type` | Text enum `User` / `Schema`, read-only | unchanged | |
| `ranges` | relationship to `CoreNumberPoolRange`, many | unchanged | |
| `allocation_scope` | List, optional | **new** | Ordered list of scope elements, see below. Absent or empty means unscoped. Branch-agnostic like the pool. Set at creation only |

### Scope element (stored inside `allocation_scope`)

| Key | Type | Notes |
|-----|------|-------|
| `id` | string | Schema element id of the attribute or relationship on the default branch. The reference |
| `name` | string | Readable name of the element at the time of the last schema update of the default branch. Display only |

Order inside the list is the scope order; division tuples follow it.

**Validation rules at creation** (`backend/infrahub/pools/scope.py::AllocationScopeResolver`), each refusal names the element:

1. Every entry resolves, by id or by name, to one attribute or one relationship declared on the pool's kind in the schema of the default branch. When the kind is a generic, the element must be declared on the generic itself.
2. An attribute entry is `optional: false`. A relationship entry is `optional: false` with `cardinality: one`.
3. An entry does not contain `__` (no path into a peer or into an attribute property).
4. An entry is not the pool's `node_attribute`.
5. No entry appears twice (by id).
6. The pool's tracked attribute is not `unique: true` when the scope is not empty.

**Immutability**: an update whose `allocation_scope` differs from the stored list is refused. An update carrying the stored list unchanged (same ids in the same order) is accepted.

### Division (derived, not stored)

| Field | Type | Notes |
|-------|------|-------|
| `values` | ordered list of strings | One value per scope element, in scope order |

Value of an element for a holder node, read on the branch that holds the counted value, with the default branch as fallback:

- relationship element: the peer's id, or an empty string when the holder has no peer;
- attribute element: the attribute value as text, or an empty string when the holder has no value.

`key`: a stable hash of the JSON form of `values`, used in lock names (`<pool id>.<key>`).

Equality: two divisions are equal when their value lists are equal element by element.

### Tracked number record (`IS_RESERVED` edge, existing)

Unchanged: pool to holder attribute, on the global branch, with `identifier` and `provenance`. The division of a record is the division of its holder on the branch considered.

### Number-pool attribute parameters (`NumberPoolParameters`, existing)

| Field | Type | Update support | Change |
|-------|------|----------------|--------|
| `start_range`, `end_range` | int | validate constraint | unchanged |
| `number_pool_id` | str or None | not supported | unchanged |
| `allocation_scope` | list of str or None | not supported | **new**: element names, resolved and validated against the default branch's schema at load; stored on the pool the schema creates as ids and names |

## Figures (returned by the dedicated queries)

For one space (the pool, one range, or one division over the pool or over a range):

| Figure | Definition |
|--------|------------|
| `size` | Number of values the space holds. For the pool and a division over the pool: sum of the range sizes minus the attribute's excluded values. For a range: `end - start + 1`. 0 when the pool has no range |
| `used` | Distinct values of the space held on any live branch |
| `used_default_branch` | Distinct values held on the default branch |
| `used_branches` | Distinct values held on other branches and not on the default branch |
| `utilization`, `utilization_default_branch`, `utilization_branches` | The three counts as a percentage of `size`; 0 when `size` is 0 |

The denominators keep the rule of today's `resolve_number_pool_utilization`: the pool total subtracts the attribute's excluded values, a range counts every value between its bounds.

## State transitions

- Pool creation: scope resolved, validated, stored. No later transition of the scope.
- Schema update on the default branch: stored names refreshed from the ids (no change of ids or order).
- Schema update that breaks an element (optional, cardinality, removal, `unique: true` on the tracked attribute): refused, no transition.
- Pool deletion: the scope goes with the pool; no record changes.
