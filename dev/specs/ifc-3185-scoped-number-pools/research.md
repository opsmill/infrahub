# Research: Scoped number pools

**Feature**: `dev/specs/ifc-3185-scoped-number-pools` | **Date**: 2026-10-02 | **Spec**: [spec.md](./spec.md)

Phase 0 of the plan. Every unknown in the technical context is resolved here as a decision with its
rationale and the alternatives weighed. Symbols are cited as `module.py::Symbol`, never by line.

---

## 0. Corrections to the source PRD, from the code as it stands

The PRD was grilled against this branch on 2026-10-01. Four of its assumptions do not hold as
written on `feature-number-pools-1.12` at HEAD, and the plan is built on the corrected facts.

| PRD assumption | What the code says | Consequence |
|---|---|---|
| "P1 (several weighted ranges) has landed: allocation walks a range set" | Only the `CoreNumberPoolRange` kind, its GraphQL contract and the per-range utilization rows shipped. `core/node/resource_manager/number_pool.py::CoreNumberPool.get_next` still walks `start_range`–`end_range`; `NumberPoolParameters` has no `ranges`; the ranges checker does not exist | The division filter is added inside the shared records fragment, which P1's range walk will call once per range. The two changes are orthogonal and can land in either order; a coordination note is carried in the plan |
| "The records lookup already resolves each record to its owning object" | `core/query/resource_manager.py::reserved_values_query` matches `(pool)-[:IS_RESERVED]->(attr:Attribute {name})` and reads `HAS_VALUE` forward; it never touches the owning `Node`. Only `NumberPoolGetAllocated` resolves the owner, and that one lacks the deleting-branch and fork-window logic the used/free fragment has | The scoped fragment adds the `(n)-[:HAS_ATTRIBUTE]->(attr)` hop and the per-entry division reads; the allocated query is brought onto the same fragment so utilization and allocation read the same liveness |
| "Relationships are processed before attributes when a node is written" | True on create: `core/node/__init__.py::Node._process_fields` runs relationships before attributes. False on update: `Node.from_graphql` applies the payload in dict order and `core/attribute.py::BaseAttribute.from_graphql` calls `handle_pool` inline | On update, pool handling is deferred until every field in the payload has been applied (D4) |
| "P2 attach is in flight" | The ledger re-anchoring and the retirement of dead records are merged (the attribute-anchored `IS_RESERVED`, the forward liveness read, `provenance`). The attach, detach and intent-resolver work is not built; the attach tasks are unchecked | User Story 7 stays gated on attach. Everything else in this slice reads the ledger as it is today |

Two further facts the PRD does not mention:

- `core/validators/node/attribute.py::NodeAttributeAddChecker` refuses adding a `NumberPool`
  attribute when the pool is smaller than the number of existing nodes. That comparison is
  whole-pool and becomes wrong for a scoped declaration (D9).
- `CoreNumberPool.get_next` still unions `get_taken()` on a `unique` attribute, so every value
  present anywhere on the attribute is skipped. A scope over a unique attribute therefore degrades
  to pool-wide allocation today and refuses nothing; the PRD's `unique: true` edge case describes
  the state after P2 retires that scan. No test of this slice asserts the refusal.

A third fact shapes the create path: `Node._process_fields` calls the template applier before it
applies relationships, and `templates/node_applier.py::NodeTemplateApplier._handle_pool_relationship`
allocates through `pools/default_allocator.py::DefaultPoolAllocator` from the raw field dict, with no
node in hand. A template-created object therefore has no division to read at that point (D4).

---

## 1. Where everything lives today

| Concern | Location |
|---|---|
| Pool kind | `core/schema/definitions/core/resource_pool.py::core_number_pool` (branch-agnostic, `node`, `node_attribute`, deprecated `start_range`/`end_range`, `pool_type`, `ranges` relationship) |
| Attribute parameters | `core/schema/attribute_parameters.py::NumberPoolParameters`; validated at load by `core/schema/schema_branch.py::SchemaBranch._validate_number_pool_parameters` |
| Schema-created pool provisioning | `pools/schema_number_pool_upserter.py::SchemaNumberPoolUpserter`, `pools/schema_number_pool_synchronizer.py::SchemaNumberPoolSynchronizer._update_pool_from_schema` (copies bounds from the default-branch schema only) |
| Allocation | `core/node/__init__.py::Node.handle_pool` → `core/node/resource_manager/number_pool.py::CoreNumberPool.get_resource` (lock `resource_pool.<pool id>`) → `get_next` → `NumberPoolGetFree` |
| Records fragment | `core/query/resource_manager.py::reserved_values_query`, consumed by `NumberPoolGetUsed` and `NumberPoolGetFree` |
| Utilization | `graphql/queries/resource_manager.py::resolve_number_pool_utilization` over `pools/number.py::NumberUtilizationGetter`, which runs `NumberPoolGetAllocated` |
| Pool mutation | `graphql/mutations/resource_manager.py::InfrahubNumberPoolMutation` (schema-pool refusal text lives in `mutate_update`) |
| Schema-path parsing and validation | `core/schema/basenode_schema.py::parse_schema_path`, `SchemaAttributePath`; `core/schema/schema_branch.py::SchemaBranch.validate_schema_path` with `core/constants/schema.py::SchemaElementPathType` |
| Runtime path values | `core/node/constraints/grouped_uniqueness.py::_get_unique_valued_paths` (peer id through `RelationshipManager.get_peer_id`, attribute through `.value`, enum unwrapped, `None` → `NULL_VALUE`) |
| Schema-change checkers | `core/validators/__init__.py::CONSTRAINT_VALIDATOR_MAP`; constraints and migrations derived in `core/models.py::SchemaUpdateValidationResult.process_diff` (field removal is a migration, not a constraint) |
| Schema pools per field | `pools/registration.py::get_branches_with_schema_number_pool` (schema side only; no pool-side lookup exists) |
| Test helpers | `backend/tests/helpers/number_pool.py`, `backend/tests/helpers/agnostic_edges.py` |

---

## 2. Decisions

### D1 — `allocation_scope` is a `List` attribute on the pool kind, applied by the core schema update

**Decision**: add `allocation_scope` to `core_number_pool` as `kind="List"`, optional, with the
pool's branch support (agnostic). No graph migration: `cli/db.py::update_core_schema` diffs the
stored core schema against the definitions and applies an added optional attribute as a schema
update, as it did for `pool_type`. `GRAPH_VERSION` stays at 79.

**Rationale**: a list of strings is what uniqueness constraints already store on the schema side;
`List` is the existing kind for that shape on core nodes (`CoreGraphQLQuery.models`,
`CoreMenuItem`). The attribute is branch-agnostic because the pool is: FR-021 and the PRD's
rejection of a branch-aware scope.

**Alternatives**: a JSON attribute (no stricter, worse generated types); a child kind per entry (a
second kind with mutations for a two-element list; rejected under Principle VII).

### D2 — Scope entries are validated by the existing schema-path validator plus four local rules, in one shared component

**Decision**: a `ScopeValidator` in `pools/scope.py`, constructed with the `SchemaBranch` to
validate against, exposing `validate(kind, attribute_name, scope) -> tuple[str, ...]` which returns
the normalised entries or raises a `ValidationError` naming the entry. It calls
`SchemaBranch.validate_schema_path` with
`SchemaElementPathType.ATTR | SchemaElementPathType.REL_ONE_MANDATORY_NO_ATTR`, which already
refuses many relationships and paths into a related node, and adds what that validator does not
check: the field must be required (`optional=False`) — checked locally for relationships too,
because `validate_schema_path` exempts `ip_namespace` on IP kinds from its mandatory check — the
attribute's kind must be a single comparable scalar (list and JSON kinds refused), the entry must
not be the pool's own attribute, and entries must be distinct. Attribute entries are normalised to
the bare name (`role__value` → `role`); only the `value` property is accepted.

Both callers use it: `InfrahubNumberPoolMutation` on create, update and upsert against the mutation
branch's schema (FR-009), and `SchemaBranch._validate_number_pool_parameters` against the schema
being loaded (FR-012). The mutation invokes it only when the normalised submitted scope differs from
the stored one: the scope is written once on `-global-`, so a pool saved from a branch that knows an
entry would otherwise be refused whenever the whole object is re-sent from a branch that does not,
and an entry would become un-resavable from anywhere once that branch is deleted.

**Rationale**: the uniqueness-constraint flags are almost the FR-009 rules; the delta is small and
local. One component for both surfaces is what FR-009 and FR-012 ask for ("the same rules").

**Alternatives**: a new `SchemaElementPathType` flag for "required attribute" (touches a shared enum
for one caller); duplicating the checks in the mutation and the schema validator (two drifting
copies).

### D3 — The division is derived inside the records fragment, per entry, as a union over branches with the same visibility rule the value read uses

**Decision**: `reserved_values_query` gains an optional `division` parameter: the entries in force
and the writer's value for each. When present, the fragment adds `(n:Node)-[:HAS_ATTRIBUTE]->(attr)`
and, per entry, a `CALL (n, ...)` subquery that collects the values the object holds for that entry
on any live branch — a relationship entry through `IS_RELATED` → `Relationship {name: identifier}`
→ `IS_RELATED` → peer `uuid`, an attribute entry through `HAS_ATTRIBUTE {name}` → `HAS_VALUE` →
`value`. The relationship hop renders its arrows from the relationship's `direction`, as
`RelationshipGetPeerQuery` does, so a self-referencing relationship whose reverse side shares the
identifier does not collect the reverse peers. The record counts when, for every entry, the
writer's value is in the collected set. The unscoped call renders the fragment byte-for-byte as
today (FR-005, SC-003).

The fragment also takes a `with_branch` render flag, off for the used and free reads so their text
is unchanged, and on for the allocated read: it projects `branch` from both legs (the open edge's
branch; for the fork-window leg, each surviving window's name) and ends `WITH DISTINCT res, value,
branch`, which is what the per-branch split and the in-use list need.

Two anchor orders are rendered behind the same `division` parameter — from the record side filtering
on the division last, and from the division side (the writer's peers or values) joining to the
records — and profiled at the SC-006 shape and at a hub shape before one is kept. The record-side
order runs one subquery per record; at full occupancy that is thousands of subqueries to discard
most rows.

Each entry subquery applies the two-leg visibility rule the value read already has: an edge open now
on a non-deleting branch, or an edge closed on the default branch that a branch forked inside its
window still sees and has not hidden. That predicate is lifted into a named Cypher constant in
`core/query/resource_manager.py` because it now has three consumers (value, relationship peer,
attribute value), which is the bar the query guideline sets for a shared fragment.

The per-entry union is a superset of the per-branch tuple union: an object in (A, T1) on the default
branch and (C, T1) on `b1` counts in `{A, C} × {T1}`. That can only add numbers to the taken set, so
the error stays one-sided (FR-007).

**Rationale**: the PRD's FR-001 and FR-007 ask for exactly this read. Omitting the fork-window leg
on the hop would free a number in a division an older branch still sees the object in, which breaks
"never free when taken on any branch". The cost is bounded by pool occupancy times entries, which
SC-006 measures.

**Alternatives**: open-edges-only on the hop (simpler, not one-sided); a per-branch tuple union
(exact, but a cross-branch aggregate inside an already two-legged subquery for no safety gain); a
stored division key (rejected by the PRD; the derived read is its repair path).

### D4 — The writer's division is read from the in-memory node after every field in the payload has been applied

**Decision**: a `DivisionResolver` in `pools/scope.py` with
`entries_in_force(scope, schema_branch, kind)` (pure: drops entries the branch's schema does not
define, FR-008) and `async division_of(db, node, entries) -> DivisionKey` (peer id through the
relationship manager, which may read the database for a peer given by id or human-friendly id;
attribute `.value`, enum unwrapped). `Node.handle_pool` calls it and passes the key to
`CoreNumberPool.get_resource`, whose signature gains `division: DivisionKey | None`.

Three write paths reach allocation:

- **Create through the ordinary path**: nothing moves; `Node._process_fields` applies relationships
  before attributes.
- **Create through a template**: the applier allocates before any relationship exists and without a
  node. It stops allocating: `_handle_pool_relationship` records the pool id and marks the attribute
  pending (the `TemplatePoolFields.pending` mechanism exists and the mandatory-attribute check
  already tolerates it), and `_process_fields_attributes` runs `handle_pool` for it after the
  relationships are applied, as it does for a user `from_pool`.
- **Update**: `Node.from_graphql` applies every attribute with `process_pools=False`, then runs
  `handle_pool` for each attribute whose payload carried `from_pool`. `from_pool` itself is still
  assigned inline by `BaseAttribute.from_graphql`, because the mutation lock names are read from it
  before the node is saved; only the allocation is deferred.

The attribute-add backfill (`core/migrations/schema/node_attribute_add.py`) loads each node with its
scoped fields in the same query it already runs and passes the node's division; the template
allocation in `core/node/create.py` runs after `obj.new()` and passes the division of the built
node.

**Rationale**: FR-002. The in-memory node is the only place the "node as it will be saved" exists
before the write, and the relationship manager already answers `get_peer_id` from it.

**Alternatives**: read the division from the database (wrong on a create and on a same-request
move); reorder the payload dict (fragile, and P2's intent resolver will also sit on this path);
keep the applier allocating from the raw field dict (no node, so no division).

### D5 — The lock stays on the pool

**Decision**: `get_resource` keeps `resource_pool.<pool id>`. No per-division key.

**Rationale**: the PRD defers this to SC-005. A per-division key changes no contract and can be
added later behind the same `get_resource` signature.

### D6 — Utilization: one query returns rows with their division values; a pure reporter picks the fullest division

**Decision**: `NumberPoolGetAllocated` moves onto the shared records fragment (so it gains the
deleting-branch and fork-window behaviour the used/free reads have) and, when the pool is scoped,
returns per row the collected values of each entry in force. `pools/number.py::NumberUtilizationGetter`
becomes a seam that loads rows and hands them to a pure `pools/division_report.py::DivisionReporter`,
which expands each row into the divisions it occupies, counts distinct values per division per
branch split, and names the fullest division. The headline and its branch split are computed over
that division; each per-range row reports the fullest division within that range (FR-011, FR-017).
A new `NumberPoolDivisions` query enumerates the distinct division tuples over
`(n:Node:<kind>)-[:IS_PART_OF]->(:Root)` on any live branch so that a division with objects but no
records reports 0 (FR-011); relationship peers are resolved to display labels by one
`NodeManager.get_many(..., branch_agnostic=True)` over the distinct peer ids, and a peer that still
cannot be read (a division keyed by an object that exists only on a branch the reader cannot see)
is labelled by its identifier so the non-null field never voids the list.

The `InfrahubResourcePoolAllocated` query shares `NumberPoolGetAllocated`, so the row shape keeps
owner id, branch, value and record identifier; the move onto the shared fragment is pinned by
regression tests on that query's count, offset and limit and on the headline branch split.

On an unscoped pool the getter returns one division with an empty key and the figures it computes
today (FR-015). The IP pool branch of the resolver sets `divisions` to an empty list explicitly,
since the field is non-null.

**Rationale**: one read for the figures keeps the headline and the breakdown consistent by
construction. The enumeration is the one place the pool reads the kind's data, as the PRD decided.

**Alternatives**: one query per division (N+1); a division breakdown inside every range row (more
than the first per-division view needs; additive later).

### D7 — Per-division rows ride on the existing utilization query

**Decision**: `graphql/queries/resource_manager.py::PoolUtilization` gains
`divisions: [PoolDivisionUtilization!]!`, each row carrying `division: [PoolDivisionEntry!]!` and
the three figures. See [contracts/graphql-pool-utilization.md](./contracts/graphql-pool-utilization.md).

**Rationale**: the frontend reads this query for the pool detail; one round trip; the PRD's open
question 1 resolved as the spec records.

### D8 — FR-010 is a constraint checker over a pool-side lookup, registered for the removal migrations too

**Decision**: a `ScopedPoolDependencyChecker` in `core/validators/pool/scope.py` registered in
`CONSTRAINT_VALIDATOR_MAP` for `attribute.optional.update`, `relationship.optional.update`,
`relationship.cardinality.update`, `node.attribute.remove` and `node.relationship.remove`. Nothing
in `core/models.py` changes: `SchemaUpdateValidationResult.add_validator_for_migration` already
appends a constraint for every migration whose name is in the map, which is how `node.attribute.add`
reaches its checker today. The checker reads only `request.schema_path.schema_kind` and
`field_name`, never the field from `request.node_schema`, because the schema it receives is the
candidate schema in which a removed field no longer exists. It uses
`pools/referencing.py::PoolsReferencingField` — a repository that loads the pools whose `node` is the
kind or a generic it inherits from and filters in Python on `allocation_scope` and `node_attribute`
— and raises naming the pool. An entry absent from the branch's schema is skipped (FR-010's "never
existed" clause).

**Rationale**: the constraint-checker path is where schema loads are refused with a message today,
on the branch being loaded. Pools per kind are few, so a Python filter beats a `CONTAINS` over a
list attribute's stored value.

**Alternatives**: a pure schema-branch check (cannot see pools, which are data); a Cypher filter on
the list value (format-dependent).

### D9 — The attribute-add size check compares against the largest division

**Decision**: when a `NumberPool` attribute being added declares `allocation_scope`,
`NodeAttributeAddChecker` compares the pool size against the largest per-division object count
from `NumberPoolDivisions` rather than the kind's total count.

**Rationale**: a scoped pool legitimately serves more objects than its size.

### D10 — Schema-declared scope is reconciled from the default branch, like the bounds

**Decision**: `NumberPoolParameters.allocation_scope: list[str] | None = None`, with `update`
support `ALLOWED` (changing it moves no data, FR-006); FR-009's entry rules run in
`_validate_number_pool_parameters` on the branch being loaded. `SchemaNumberPoolUpserter` writes it
at creation; `SchemaNumberPoolSynchronizer._update_pool_from_schema` copies it from the
default-branch schema as it copies the bounds. Those two writes belong to the contract change set,
because User Story 1's "a schema-declared scope reads back on the pool" needs them.
`InfrahubNumberPoolMutation.mutate_update` refuses a scope change on a `pool_type == Schema` pool
with the existing default-branch message (FR-013).

The SDK, OpenAPI and frontend REST models are not introspected from the Pydantic class:
`tasks/backend.py::SdkSchemaGenerator.number_pool_parameters_fields` lists the parameter fields by
hand, so the new field is added there as a `List` field and the generators re-run.

### D11 — Contract first, with an honest placeholder

**Decision**: the delivery order the spec records. The schema attribute and the parameters field
land first; then the mutation validation and the `divisions` field, whose resolver returns the
single empty-key division computed by today's getter for every pool. For an unscoped pool that is
the final behaviour; for a scoped pool it is the FR-019 placeholder, replaced when D6 lands. The
generated artefacts are regenerated once at the contract step and must not change afterwards
(FR-018).

### D12 — Measurement, not a gate

**Decision**: a benchmark module under `backend/tests/query_benchmark/` builds the SC-006 shape
(4094 numbers, three entries, five branches, full occupancy) and records one allocation's latency
and the free query's plan. SC-005 (one scoped pool versus N per-site pools under concurrent
allocation) cannot run in that folder, which profiles single queries; it runs as a timed functional
scenario under `backend/tests/functional/pools/`, marked so it is excluded from the default run.
Both record their figures in `dev/specs/ifc-3185-scoped-number-pools/measurements.md`. No threshold.

---

## 3. Sequencing and concurrency

```text
A  schema attribute + parameters field + SDK generator entry   (one PR, small, first)
B  GraphQL contract: mutation validation, schema-pool refusal,  (depends on A; unblocks frontend + SDK)
   upserter/synchronizer writes, divisions field with the
   placeholder, regen
C  seams: DivisionResolver, get_resource(division) on all three (depends on A; parallel with B)
   write paths, NumberUtilizationGetter → DivisionReporter
D1 scoped records fragment + allocation                         (depends on C)       ┐
D2 NumberPoolDivisions + real divisions resolver                (depends on B, C)    ├ parallel
D3 schema-load validation + attribute-add size check            (depends on A)       │
D4 ScopedPoolDependencyChecker + PoolsReferencingField          (depends on A)       ┘
E  measurement, docs, changelog                                 (depends on D1, D2)
```

P1's remaining allocation-over-ranges work touches `get_next`, `NumberPoolParameters`, the size
calculation and the SDK regeneration; D1 touches the fragment those queries share and set A touches
the same parameters class and generator. Whichever slice lands second rebases a small hunk, and each
slice opens its own SDK regeneration PR when it lands. Which lands first is the P1 owner's call and
is recorded as an open question in the critique.

---

## 4. Open risks carried into the plan

- **The hop's fork-window leg** doubles the subquery per entry, and the record-side anchor runs it
  per record. Both anchor orders are profiled before one is kept; SC-006 is the measurement; if the
  figure is still bad, the next lever is a stored division key, which the PRD keeps as an
  optimisation.
- **Test fixtures**: the shared snow schema's pooled attribute is `unique`, so a scoped test on it
  is masked by the global taken-values scan. Scoped tests use a non-unique pooled attribute on a
  kind with a required cardinality-one relationship and a required scalar attribute.
- **Update-path deferral of `handle_pool`** changes the order in which validation errors surface for
  a payload that both fails a relationship update and allocates. The functional lifecycle suite
  pins the observable order.
- **P2's intent resolver** will also sit on `from_graphql`; D4 keeps the deferral in one place so the
  resolver slots in after it.
- **`NumberPoolGetAllocated` on the shared fragment** changes which records the in-use list shows on
  a deleting branch. That is the fix the P2 research already asked for; it is noted in the changelog.
