# Data model: Scoped number pools

**Feature**: `dev/specs/ifc-3185-scoped-number-pools` | **Date**: 2026-10-02 | **Spec**: [spec.md](./spec.md) | **Research**: [research.md](./research.md)

---

## 1. The pool

`core/schema/definitions/core/resource_pool.py::core_number_pool` gains one attribute. Nothing else
on the pool, its ranges or its records changes.

| Attribute | Kind | Optional | Branch | Notes |
|---|---|---|---|---|
| `allocation_scope` | `List` of `str` | yes | agnostic (inherited from the pool) | Scope entries in schema-path notation, normalised to bare field names. Absent or empty means unscoped |

Applied by the core schema update on upgrade (`cli/db.py::update_core_schema`). No graph migration,
`GRAPH_VERSION` stays at 81 (the range and re-anchoring migrations of P1 and P2 are 80 and 81).

### Scope entry

A string naming one field of the pool's `node` kind:

| Entry | Accepted spelling | Stored as | Division value |
|---|---|---|---|
| Relationship, cardinality one, required | `site` | `site` | the peer's `uuid` |
| Attribute, required, scalar kind | `role` or `role__value` | `role` | the attribute's value (enum unwrapped) |

Refused at save, naming the entry: an optional field; a many relationship; a path into a related
node (`site__name__value`); an attribute of list or JSON kind; the pool's own `node_attribute`; a
duplicate entry; an entry the mutation branch's schema does not define.

---

## 2. Number-pool attribute parameters (published contract, ADR 0010)

`core/schema/attribute_parameters.py::NumberPoolParameters`:

| Field | Type | Default | Update support | Notes |
|---|---|---|---|---|
| `allocation_scope` | `list[str] \| None` | `None` | `ALLOWED` | Same notation and rules as on the pool; validated at load against the branch being loaded |

Reconciled onto the schema-created pool from the default-branch schema by
`SchemaNumberPoolSynchronizer`; written at creation by `SchemaNumberPoolUpserter`.

---

## 3. Derived, never persisted

### Division

```python
@dataclass(frozen=True)
class ScopeEntry:
    path: str                    # bare field name
    is_relationship: bool
    relationship_identifier: str | None   # the Relationship vertex name for a relationship entry

@dataclass(frozen=True)
class DivisionKey:
    entries: tuple[ScopeEntry, ...]       # the entries in force on the reading branch, scope order
    values: tuple[str | int | bool | None, ...]   # one per entry; None means the holder holds nothing
```

Produced by `pools/scope.py::DivisionResolver`:

- `entries_in_force(scope, schema_branch, kind)` drops every entry the branch's schema does not
  define on the kind (FR-008). With no entry left the pool is unscoped on that branch. The same
  function gives the three dedicated queries their `allocation_scope` and the paths a division
  filter accepts.
- `division_of(db, node, entries)` reads the in-memory node: peer id through the relationship
  manager (which may read the database for a peer given by id or human-friendly id), attribute
  `.value` with enums unwrapped. It runs after every field of the write has been applied, on all
  three write paths (ordinary create, template create, update).

### Division occupancy of a record

A record occupies, for each entry in force, every value its holder holds for that entry on
any live branch, under the same visibility rule as the value read:

| Leg | Condition |
|---|---|
| Open now | the edge is `active`, `from <= at`, `to IS NULL OR to > at`, and its branch is not `DELETING` |
| Still visible from a fork | the edge is on the default branch, closed at `to <= at`, some live branch forked inside `[from, to)`, and that branch has written no edge of its own on the same vertex |

The record counts in a division when, for every entry, the writer's value is among the values
collected. The per-entry union is a superset of the per-branch tuple union, so it can only add
numbers to the taken set. The same rule decides which rows a `division` filter on
`InfrahubNumberPoolAllocations` returns, so one value can be returned under two divisions.

### Division enumeration

`NumberPoolDivisions` (new query): distinct tuples of entry values over every node of the kind
reachable on any live branch, with the count of nodes per tuple. Used for the attribute-add size
check. The divisions list holds the divisions the allocation rows occupy, so it does not need this
query.

### Allocation rows

`NumberPoolGetAllocated` (existing query, extended): one row per (record, branch-resolved value)
carrying the holder's id, the branch, the value, the record's identifier and its provenance
(`coalesce(provenance, "allocated")`), and, when the pool is scoped, the holder's division on the
row's branch, which the `division` filter and the division figures read and no row returns. Today
the query filters on the deprecated `start_range` / `end_range` pair; the filter becomes an optional
list of range bounds so the dedicated allocation query can list every tracked value, or the values
of one range, on a pool holding any number of ranges. The generic `InfrahubResourcePoolAllocated`
keeps today's behaviour.

### Division report

`pools/division_report.py::DivisionReporter` (pure): takes the allocation rows (holder, value,
branch, per-entry value sets) and the enumerated divisions; returns per division the distinct values
used on the default branch and on other branches, and answers one division's figures over the
pool and within a range (FR-015, FR-017).

| Quantity | Rule |
|---|---|
| `size` of the pool | the number of values of the pool's space over the range set: values inside a range, not in the attribute's `excluded_values` (single values and excluded ranges), within its `min_value` / `max_value`. Never read from the deprecated `start_range` / `end_range` pair, which is null on a pool holding several ranges. P1's shared effective-space calculation replaces the resolver-side computation when it lands |
| `size` of a range | `end - start + 1` |
| `used` | distinct values of the measured space held on any live branch; `used_default_branch` on the default branch; `used_branches` on other branches and not on the default branch |
| Division figures | `used` restricted to the values held by holders in that division, over the pool's `size` (divisions query, utilization headline with `division`) or over a range's `size` (utilization range rows with `division`) |
| Headline figures of a scoped pool | the figures of the division given as `division`, which a scoped pool requires |
| Range row of a scoped pool | the values of that range held in the division given as `division`, against the range's `size`, with its branch split |
| Division display label | the entries' display labels joined with " / "; a relationship entry: the peer's display label read branch-agnostically, falling back to its id; an attribute entry: the value as text; a holder holding nothing for an entry: the empty string |
| Unscoped pool | exactly one division with no entry and an empty label; figures as today |
| Rows listed and counted | only values of the pool's space: inside a range, not excluded by the attribute and within its `min_value` / `max_value`; a value outside it is not listed and counts in no figure |
| `range` of a row | the range whose bounds hold the value |

### Fixed dataset (contract change set only)

`pools/number_pool_mock.py` (deleted by the last change set) holds the fixed in-memory dataset the
three dedicated queries return until the real reads exist: a pool scoped by `site` for any
`pool_id`, and an unscoped pool for the reserved id `mock-unscoped`. Nothing is read from the
database. Every figure is computed from the dataset's rows with the definitions above, and the
filters, ordering, pagination and refusals apply to the dataset, so lists, filters and counts agree.
The contents are listed in the contract, section "Fixed dataset of the first delivery".

---

## 4. Read shapes of the dedicated surface

Defined in [contracts/graphql-number-pool-surface.md](./contracts/graphql-number-pool-surface.md).

| GraphQL type | Built from |
|---|---|
| `NumberPoolUtilization` | the pool node (id, display label), `entries_in_force`, the division report's headline and range figures |
| `NumberPoolUtilizationFigures` | one block per measured space, from the division report |
| `NumberPoolRangeUtilization` | each `CoreNumberPoolRange` of the pool ordered by `start`, plus its figures |
| `NumberPoolDivisions`, `NumberPoolDivision`, `NumberPoolDivisionEntry` | the division enumeration, the division report and one branch-agnostic `NodeManager.get_many` over the distinct peer ids for labels and kinds |
| `NumberPoolDivisionEntryInput` | the division filter; validated against `entries_in_force` |
| `NumberPoolAllocations`, `NumberPoolAllocation`, `NumberPoolHolder`, `NumberPoolRangeRef`, `NumberPoolProvenance` | the allocation rows, with the holder's display label and hfid read on each row's branch and the range resolved from the pool's ranges |

---

## 5. Validation and refusal

| Surface | Component | Rule | Error names |
|---|---|---|---|
| Pool create / update / upsert | `pools/scope.py::ScopeValidator` against the mutation branch's schema, invoked only when the normalised submitted scope differs from the stored one | FR-009 and the local rules in §1; the required check covers relationships locally | the entry |
| Schema load, number-pool attribute parameters | the same validator inside `SchemaBranch._validate_number_pool_parameters` | same | the entry |
| Pool update on a schema-created pool | `InfrahubNumberPoolMutation.mutate_update` | a scope change is refused | the default-branch schema (existing message) |
| Schema load changing a scoped field | `core/validators/pool/scope.py::ScopedPoolDependencyChecker` registered for `attribute.optional.update`, `relationship.optional.update`, `relationship.cardinality.update`, `node.attribute.remove`, `node.relationship.remove`; reads kind and field from the schema path only, since the candidate schema no longer holds a removed field | refused when a pool names the field | the pool |
| Schema load adding a scoped number-pool attribute | `NodeAttributeAddChecker` | pool size ≥ largest division's node count | existing message with the division count |
| The three dedicated queries | `graphql/queries/number_pool.py` resolvers | `pool_id` must be a `CoreNumberPool`; `range_id` must be a range of the pool; a `division` filter needs a non-empty scope in force, paths in force, no duplicate path, and on the utilization query a value for every path in force | the pool, the range, the entry (messages in the contract) |

### Pools-referencing-field lookup

`pools/referencing.py::PoolsReferencingField` (repository, `db` in the constructor):
`get(kind, field_name, branch) -> list[CoreNumberPool]`. Loads the pools whose `node` is the kind or
a generic the kind inherits from, filters in Python on `allocation_scope` and `node_attribute`.

---

## 6. State and transitions

The pool has no new state machine. Scope changes are plain attribute writes:

| Transition | Data moved | Next read |
|---|---|---|
| unscoped → scoped | none | each record counts in the divisions its holder occupies |
| scoped → wider scope | none | numbers taken under the finer division become free |
| scoped → narrower scope | none | more numbers appear taken |
| scoped → unscoped | none | every record counts pool-wide, as today |

---

## 7. Entities not changed

- The `IS_RESERVED` record: same vertex, same properties, same branch (`-global-`).
- `CoreNumberPoolRange` and the effective-space arithmetic (P1).
- The IP pool kinds and their queries.
- The generic resource-pool query types (`PoolUtilization`, `PoolAllocated`, `PoolAllocatedNode`,
  `IPPrefixUtilizationEdge`, `IPPoolUtilizationResource`): description text only.
- The allocation lock key.
