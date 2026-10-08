# Data Model: Number pool allocation scopes

## Entities

### Number pool (`CoreNumberPool`, existing)

| Field | Type | Change | Notes |
|-------|------|--------|-------|
| `node` | Text, required | unchanged | Kind the pool is attached to (node or generic) |
| `node_attribute` | Text, required | unchanged | Tracked attribute of that kind |
| `start_range`, `end_range` | Number, optional, deprecated | unchanged | Single-range shorthand, mirrored from the ranges |
| `pool_type` | Text enum `User` / `Schema`, read-only | unchanged | |
| `ranges` | relationship to `CoreNumberPoolRange`, many | unchanged | |
| `allocation_scope` | List, optional | **content changes** | Exists today and stores element names. Stores ordered scope elements (below) instead. Absent or empty means unscoped. Branch-agnostic like the pool. Set at creation only |

### Scope element (stored inside `allocation_scope`)

| Key | Type | Notes |
|-----|------|-------|
| `id` | string | Schema element id of the attribute or relationship on the default branch. The reference |
| `name` | string | Readable name of the element at the time of the last schema update of the default branch. Display only |

Order inside the list is the scope order; division tuples follow it.

**Reading the stored value** (`backend/infrahub/pools/scope.py::AllocationScope.from_stored`): an entry that is not an object with `id` and `name` (a plain name written before this change, on a database built from the feature branch) is refused with an error naming the pool and asking to recreate it. No migration rewrites the old shape, because no released version stores a scope.

**Validation rules at creation** (`backend/infrahub/pools/scope.py::AllocationScopeResolver`), each refusal names the element:

1. Every entry resolves, by id or by name, to one attribute or one relationship declared on the pool's kind in the schema of the default branch. When the kind is a generic, the element must be declared on the generic itself.
2. An attribute entry is `optional: false`; any attribute kind is accepted, `List` and `JSON` included. A relationship entry is `optional: false` with `cardinality: one`.
3. An entry does not contain `__` (no path into a peer or into an attribute property).
4. An entry is not the pool's `node_attribute`.
5. No entry appears twice (by id).
6. The pool's tracked attribute is not `unique: true` when the scope is not empty.

**Immutability**: an update whose `allocation_scope` differs from the stored list, or is `null`, is refused. An update carrying the stored list unchanged (same ids in the same order) is accepted.

### Division (derived, not stored)

| Field | Type | Notes |
|-------|------|-------|
| `values` | ordered list | One value per scope element, in scope order |

Value of an element for a holder node, read on the branch of the request with the normal branch filter:

- relationship element: the peer's id, or an empty string when the holder has no peer on that branch;
- attribute element: the attribute value as stored (text for a scalar, the stored list or document for a `List` or `JSON` attribute, compared with no normalisation), or an empty string when the holder has no value.

A holder that does not exist on the request branch has no division there and is not counted.

`key`: a stable hash of the JSON form of `values`, used in lock names (`<pool id>.<key>`).

Equality: two divisions are equal when their `key` is equal, that is when their values have the same JSON form. The key order of a document does not matter; `1`, `1.0` and `true` are three different values.

**Refusal**: when the schema of the request branch does not define an element on the pool's kind, the division cannot be read; the request is refused naming the element and the branch.

### Tracked number record (`IS_RESERVED` edge, existing)

Unchanged: pool to holder attribute, on the global branch, with `identifier` and `provenance` (`allocated` or `provided`). The division of a record is the division of its holder on the branch considered.

### Number-pool attribute parameters (`NumberPoolParameters`, existing)

| Field | Type | Update support | Change |
|-------|------|----------------|--------|
| `start_range`, `end_range`, `ranges` | int, list | validate constraint | unchanged |
| `number_pool_id` | str or None | not supported | unchanged |
| `allocation_scope` | list of str or None | **validate constraint** (was not supported) | Exists today. Element names, resolved and validated against the default branch's schema at load; stored on the pool the schema creates as ids and names; compared by id to the stored scope on every later load |

## Figures (returned by the dedicated queries)

For one space (the pool, one range, or one division over the pool or over a range):

| Figure | Definition |
|--------|------------|
| `size` | Number of values the space holds: the effective space (ranges clipped to the attribute's bounds, minus its excluded values), or the part of it one range contributes. 0 when the pool has no range |
| `used` | Distinct values of the space held on any live branch by a holder whose division, read on the request branch, is the one measured |
| `used_default_branch` | Those values held on the default branch |
| `used_branches` | Those values held on other branches and not on the default branch |
| `utilization`, `utilization_default_branch`, `utilization_branches` | The three counts as a percentage of `size`; 0 when `size` is 0 |

The denominators keep the rule of today's `NumberUtilizationGetter`: `EffectiveSpace.size` for the pool and `EffectiveSpace.size_of(range_id)` for a range.

## State transitions

- Pool creation: scope resolved, validated, stored. No later transition of the scope.
- Schema update on the default branch: stored names refreshed from the ids (no change of ids or order).
- Schema update that breaks an element (optional, cardinality, removal, `unique: true` on the tracked attribute), or that changes a declared scope to other ids, or that renames an element without updating the declaration: refused, no transition.
- Schema update that renames an element and declares its new name: accepted; the stored name follows.
- Pool deletion: the scope goes with the pool; no record changes.
