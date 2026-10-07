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
`GRAPH_VERSION` unchanged.

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

### Division key

```python
@dataclass(frozen=True)
class ScopeEntry:
    path: str                    # bare field name
    is_relationship: bool
    relationship_identifier: str | None   # the Relationship vertex name for a relationship entry

@dataclass(frozen=True)
class DivisionKey:
    entries: tuple[ScopeEntry, ...]       # the entries in force on the reading branch, scope order
    values: tuple[str | int | bool | None, ...]   # one per entry; None means the object holds nothing
```

Produced by `pools/scope.py::DivisionResolver`:

- `entries_in_force(scope, schema_branch, kind)` drops every entry the branch's schema does not
  define on the kind (FR-008). With no entry left the pool is unscoped on that branch.
- `division_of(db, node, entries)` reads the in-memory node: peer id through the relationship
  manager (which may read the database for a peer given by id or human-friendly id), attribute
  `.value` with enums unwrapped. It runs after every field of the write has been applied, on all
  three write paths (ordinary create, template create, update).

### Division occupancy of a record

A record occupies, for each entry in force, every value its owning object holds for that entry on
any live branch, under the same visibility rule as the value read:

| Leg | Condition |
|---|---|
| Open now | the edge is `active`, `from <= at`, `to IS NULL OR to > at`, and its branch is not `DELETING` |
| Still visible from a fork | the edge is on the default branch, closed at `to <= at`, some live branch forked inside `[from, to)`, and that branch has written no edge of its own on the same vertex |

The record counts in a division when, for every entry, the writer's value is among the values
collected. The per-entry union is a superset of the per-branch tuple union, so it can only add
numbers to the taken set.

### Division enumeration

`NumberPoolDivisions` (new query): distinct tuples of entry values over every object of the kind
reachable on any live branch, with the count of objects per tuple. Used for the per-division listing
(divisions with objects but no records report 0) and for the attribute-add size check.

### Division report

`pools/division_report.py::DivisionReporter` (pure): takes the allocated rows (owner, value,
branch, per-entry value sets) and the enumerated divisions; returns per division the distinct values
used on the default branch and on other branches, names the fullest division, and answers the
fullest division within a range (FR-011, FR-017).

| Quantity | Rule |
|---|---|
| Division utilization | distinct values held in that division ÷ effective size |
| Headline utilization | the fullest division's utilization |
| Headline branch split | the fullest division's default-branch and other-branch figures |
| Per-range row | max over divisions of (that division's values inside the range) ÷ range size, with its branch split |
| Division label | relationship entry: the peer's display label read branch-agnostically, falling back to its identifier; attribute entry: the value as text; an object holding nothing for an entry: the empty string |
| Unscoped pool | exactly one division with an empty key; figures as today |
| IP pools | no divisions (an empty list) |

---

## 4. Validation and refusal

| Surface | Component | Rule | Error names |
|---|---|---|---|
| Pool create / update / upsert | `pools/scope.py::ScopeValidator` against the mutation branch's schema, invoked only when the normalised submitted scope differs from the stored one | FR-009 and the local rules in §1; the required check covers relationships locally | the entry |
| Schema load, number-pool attribute parameters | the same validator inside `SchemaBranch._validate_number_pool_parameters` | same | the entry |
| Pool update on a schema-created pool | `InfrahubNumberPoolMutation.mutate_update` | a scope change is refused | the default-branch schema (existing message) |
| Schema load changing a scoped field | `core/validators/pool/scope.py::ScopedPoolDependencyChecker` registered for `attribute.optional.update`, `relationship.optional.update`, `relationship.cardinality.update`, `node.attribute.remove`, `node.relationship.remove`; reads kind and field from the schema path only, since the candidate schema no longer holds a removed field | refused when a pool names the field | the pool |
| Schema load adding a scoped number-pool attribute | `NodeAttributeAddChecker` | pool size ≥ largest division's object count | existing message with the division count |

### Pools-referencing-field lookup

`pools/referencing.py::PoolsReferencingField` (repository, `db` in the constructor):
`get(kind, field_name, branch) -> list[CoreNumberPool]`. Loads the pools whose `node` is the kind or
a generic the kind inherits from, filters in Python on `allocation_scope` and `node_attribute`.

---

## 5. State and transitions

The pool has no new state machine. Scope changes are plain attribute writes:

| Transition | Data moved | Next read |
|---|---|---|
| unscoped → scoped | none | each record counts in the divisions its object occupies |
| scoped → wider scope | none | numbers taken under the finer division become free |
| scoped → narrower scope | none | more numbers appear taken |
| scoped → unscoped | none | every record counts pool-wide, as today |

---

## 6. Entities not changed

- The `IS_RESERVED` record: same vertex, same properties, same branch (`-global-`).
- `CoreNumberPoolRange` and the effective-space arithmetic (P1).
- The IP pool kinds and their queries.
- The allocation lock key.
