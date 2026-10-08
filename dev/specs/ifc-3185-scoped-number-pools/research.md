# Research: Scoped number pools

**Feature**: `dev/specs/ifc-3185-scoped-number-pools` | **Date**: 2026-10-02, surface decisions 2026-10-06 | **Spec**: [spec.md](./spec.md)

Phase 0 of the plan. Every unknown in the technical context is resolved here as a decision with its
rationale and the alternatives weighed. Symbols are cited as `module.py::Symbol`, never by line.

---

## 0. Corrections to the source PRD, from the code as it stands

The PRD was grilled against this branch on 2026-10-01. The table checks its assumptions against
the code of `feature-number-pools-1.12`, and the plan is built on the facts in the second column.

| PRD assumption | What the code says | Consequence |
|---|---|---|
| "P1 (several weighted ranges) has landed: allocation walks a range set" | Holds. The `CoreNumberPoolRange` kind, its mutations (`graphql/mutations/resource_manager/number_pools/pool_range.py`, overlap validation in `pools/number_pool_range_validation.py`), the pool mutations accepting `ranges` and the deprecated shorthand (`number_pools/pool.py`), the migration `m080_number_pool_ranges` giving every existing pool one range, `pools/number_pool_shorthand.py::NumberPoolShorthandMirror` keeping `start_range` / `end_range` equal to the single range's bounds (null for none or several), `pools/number_ranges.py::EffectiveSpace` (the ranges clipped to the attribute's domain, with `size`, `size_of`, `contains`, `range_for`, `as_query_ranges`) and `pools/number_pool_number_picker.py::NumberPoolNumberPicker.next_number`, which drains the space's segments heaviest first through `pools/number_pool_repository.py::NumberPoolRepository.get_free` | The division filter is added inside the shared records fragment, which the range walk calls once per segment; the dedicated surface computes `size`, `used` and the values it lists from `EffectiveSpace`, so allocation and the surface use one definition of the pool's space |
| "The records lookup already resolves each record to its owning object" | `core/query/resource_manager.py::reserved_values_query` matches `(pool)-[:IS_RESERVED]->(attr:Attribute {name})` and reads `HAS_VALUE` forward; it never touches the holder. Only `NumberPoolGetAllocated` resolves the holder, and that one lacks the deleting-branch and fork-window logic the used/free fragment has | The scoped fragment adds the `(n)-[:HAS_ATTRIBUTE]->(attr)` hop and the per-entry division reads; the allocated query is brought onto the same fragment so utilization and allocation read the same liveness |
| "Relationships are processed before attributes when a node is written" | True on create: `core/node/__init__.py::Node._process_fields` runs relationships before attributes. False on update: `Node.from_graphql` applies the payload in dict order and `core/attribute.py::BaseAttribute.from_graphql` calls `pools/attribute_pool_applier.py::AttributePoolApplier.apply(allocate=True)` inline. `Node.from_graphql` and `_process_fields` already take `process_pools`, and `core/node/lock_utils.py::apply_payload_for_lock_names` already applies the payload with `process_pools=False` so that `apply(allocate=False)` resolves the pool for the lock names without allocating | On update, pool handling is deferred until every field in the payload has been applied (D4) |
| "P2 attach is in flight" | Holds in part. The ledger re-anchoring and the retirement of dead records are merged: the global `(pool)-[:IS_RESERVED {identifier, provenance}]->(:Attribute)` edge, migrated by `m081_reanchor_number_pool_reservations` (re-anchor, delete legacy pool source edges, collapse shared-attribute records, delete legacy records), the forward liveness read, closure through the branch-agnostic retirement queries on delete, rename, merge, rebase and branch delete, and `core/query/resource_manager.py::PoolRecordProvenance`. The attach of a provided number is merged: a `<Kind>Update` sending `value` and `from_pool` attaches the number through `pools/number_pool_attribute_allocator.py::NumberPoolAttributeAllocator.attach`; a write sending `from_pool` without `value` on an untracked number is refused. Detach (`from_pool: null`) is accepted by the GraphQL schema and does nothing yet | User Story 7 uses the attach, one node per update; no bulk attach mutation is added. Everything else in this slice reads the ledger as it is today; `provenance` is read from the ledger once the real reads land (IFC-3329), the first delivery returning the fixed dataset's provenance |

Facts about the generic pool queries, which the frontend needs of 2026-10-06 turned into
requirements:

- `graphql/queries/resource_manager.py::PoolAllocated.resolve` requires `resource_id` and ignores
  it for a number pool, so a range view lists the whole pool.
- `resolve_number_pool_allocation` sets `display_label` to the value itself and returns the
  holder's id and kind but not its own label or hfid.
- `NumberPoolGetAllocated` takes the segments of the pool's space (`EffectiveSpace.as_query_ranges()`)
  and filters `any(r IN $ranges WHERE av.value >= r[0] AND av.value <= r[1])`; it resolves the
  holder but lacks the deleting-branch and fork-window logic of the used/free fragment, and it
  projects no provenance.
- `pools/number.py::NumberUtilizationGetter` takes an `EffectiveSpace` and measures the pool and
  each range against it, holding the absolute counts. The generic resolver publishes percentages
  only, as `IPPrefixUtilizationEdge` / `IPPoolUtilizationResource` rows.
- One definition of "in the pool" exists: `EffectiveSpace`, the ranges clipped to the attribute's
  `min_value` / `max_value` minus its `excluded_values`. Allocation
  (`NumberPoolNumberPicker.next_number`), utilization and the allocated rows use it; the dedicated
  surface uses the same definition for `size`, `used` and the values it lists.

Two further facts the PRD does not mention:

- `core/validators/node/attribute.py::NodeAttributeAddChecker` refuses adding a `NumberPool`
  attribute when the pool is smaller than the number of existing nodes. That comparison is
  whole-pool and becomes wrong for a scoped declaration (D9).
- `NumberPoolNumberPicker.next_number` still unions `NumberPoolRepository.get_taken()` on a
  `unique` attribute, so every value present anywhere on the attribute is skipped. A scope on a
  pool whose attribute is `unique` is refused at save (FR-009, the PRD's FR-017 carve-out), so the
  global scan and a scope never meet on one pool.

A third fact shapes the create path: `Node._process_fields` calls the template applier before it
applies relationships, and `templates/node_applier.py::NodeTemplateApplier._handle_pool_relationship`
allocates through `pools/default_allocator.py::DefaultPoolAllocator` from the raw field dict, with no
node in hand. A template-created node therefore has no division to read at that point (D4).

---

## 1. Where everything lives today

| Concern | Location |
|---|---|
| Pool kind | `core/schema/definitions/core/resource_pool.py::core_number_pool` (branch-agnostic, `node`, `node_attribute`, deprecated `start_range`/`end_range`, `pool_type`, `ranges` relationship) |
| Attribute parameters | `core/schema/attribute_parameters.py::NumberPoolParameters`; validated at load by `core/schema/schema_branch.py::SchemaBranch._validate_number_pool_parameters` |
| Schema-created pool provisioning | `pools/schema_number_pool_upserter.py::SchemaNumberPoolUpserter`, `pools/schema_number_pool_synchronizer.py::SchemaNumberPoolSynchronizer._update_pool_from_schema` (copies bounds from the default-branch schema only) |
| Allocation | `core/attribute.py::BaseAttribute.from_graphql` (update) and `core/node/__init__.py::Node._process_fields_attributes` (create) → `pools/attribute_pool_applier.py::AttributePoolApplier.apply` (resolves the pool; `allocate=False` resolves it for the lock names only) → `pools/number_pool_attribute_allocator.py::NumberPoolAttributeAllocator.allocate` → `core/node/resource_manager/number_pool.py::CoreNumberPool.get_resource` (lock `resource_pool.<pool id>`) → `pools/number_pool_number_picker.py::NumberPoolNumberPicker.next_number` → `pools/number_pool_repository.py::NumberPoolRepository.get_free` → `NumberPoolGetFree` |
| Effective space | `pools/number_ranges.py::EffectiveSpace`, built from the pool's ranges and the attribute's domain by `pools/number_pool_space.py::to_pool_ranges` and `attribute_domain` |
| Records fragment | `core/query/resource_manager.py::reserved_values_query`, consumed by `NumberPoolGetUsed` and `NumberPoolGetFree` |
| Allocated rows | `core/query/resource_manager.py::NumberPoolGetAllocated` (holder id, branch, value, identifier; filter on the space's segments) |
| Utilization | `graphql/queries/resource_manager.py::resolve_number_pool_utilization` over `pools/number.py::NumberUtilizationGetter`, which runs `NumberPoolGetAllocated` |
| Generic pool queries | `graphql/queries/resource_manager.py::InfrahubResourcePoolAllocated`, `InfrahubResourcePoolUtilization`, registered in `graphql/schema.py::InfrahubBaseQuery` |
| Pool mutation | `graphql/mutations/resource_manager/number_pools/pool.py::InfrahubNumberPoolMutation` (shorthand parsing, `ranges` handling, the schema-pool refusal of a shorthand or `ranges` write in `_refuse_unsupported_writes`, the shorthand mirror sync); range mutations in `number_pools/pool_range.py`; shared lock and sync helpers and the refusal messages (`SCHEMA_POOL_EDIT_HINT`, `SCHEMA_POOL_SHORTHAND_REFUSED`, `SCHEMA_POOL_RANGES_REFUSED`) in `number_pools/common.py` |
| Range persistence | `pools/number_pool_repository.py::NumberPoolRepository` (`get_ranges` ordered by start, `create_range`, `save_range_bounds`, reservations) |
| Schema-path parsing and validation | `core/schema/basenode_schema.py::BaseNodeSchema.parse_schema_path`, `SchemaAttributePath`; `core/schema/schema_branch.py::SchemaBranch.validate_schema_path` with `core/constants/schema.py::SchemaElementPathType` |
| Runtime path values | `core/node/constraints/grouped_uniqueness.py::_get_unique_valued_paths` (peer id through `RelationshipManager.get_peer_id`, attribute through `.value`, enum unwrapped, `None` → `NULL_VALUE`) |
| Schema-change checkers | `core/validators/__init__.py::CONSTRAINT_VALIDATOR_MAP`; constraints and migrations derived in `core/models.py::SchemaUpdateValidationResult.process_diff` (field removal is a migration, not a constraint) |
| Schema pools per field | `pools/registration.py::get_branches_with_schema_number_pool` (schema side only; no pool-side lookup exists) |
| Frontend consumers of the generic queries | `frontend/app/src/entities/resource-manager/api/get-pool-utilization-from-api.ts`, `get-resource-allocated-from-api.ts`, `pages/resource-manager/resource-pool-details.tsx`, `resource-allocation-details.tsx` (unchanged by this slice) |
| Test helpers | `backend/tests/helpers/number_pool.py`, `backend/tests/helpers/agnostic_edges.py` |

---

## 2. Decisions

### D1 — `allocation_scope` is a `List` attribute on the pool kind, applied by the core schema update

**Decision**: add `allocation_scope` to `core_number_pool` as `kind="List"`, optional, with the
pool's branch support (agnostic). No graph migration: `cli/db.py::update_core_schema` diffs the
stored core schema against the definitions and applies an added optional attribute as a schema
update, as it did for `pool_type`. `GRAPH_VERSION` stays at 81.

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

Three further rules sit in the same component: a scope on a pool whose target attribute is
`unique: true` is refused naming the attribute (a scoped allocation on such an attribute would be
refused by the uniqueness validator whenever the number is held in another division); when the
pool's attribute is inherited from a generic, every entry must be a required cardinality-one field
declared on the generic itself, and an entry only some implementing kinds declare is refused
naming the generic; an entry the reference schema does not define on the kind is refused naming
the entry.

Both callers use it: `InfrahubNumberPoolMutation` on create, update and upsert against the default
branch's schema, whatever branch the mutation runs on, on every save that carries
`allocation_scope` (FR-009); and `SchemaBranch._validate_number_pool_parameters` against the schema
being loaded (FR-012), since the declaration travels with the fields it names. The default branch
is the reference at pool save because the pool and its scope are branch-agnostic while the kind's
schema is branch-aware: a field that exists only on a branch enters a scope once it is merged, and
a pool re-sent whole from any branch validates against the same schema, so no exemption for an
unchanged scope is needed.

**Rationale**: the uniqueness-constraint flags are almost the FR-009 rules; the delta is small and
local. One component for both surfaces is what FR-009 and FR-012 ask for ("the same rules").

**Alternatives**: a new `SchemaElementPathType` flag for "required attribute" (touches a shared enum
for one caller); duplicating the checks in the mutation and the schema validator (two drifting
copies).

### D3 — The division is derived inside the records fragment, per entry, as a union over branches with the same visibility rule the value read uses

**Decision**: `reserved_values_query` gains an optional `division` parameter: the entries in force
and the writer's value for each. When present, the fragment adds `(n:Node)-[:HAS_ATTRIBUTE]->(attr)`
and, per entry, a `CALL (n, ...)` subquery that collects the values the holder holds for that entry
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
branch`, which is what the per-branch split and the allocation list need.

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

The per-entry union is a superset of the per-branch tuple union: a holder in (A, T1) on the default
branch and (C, T1) on `b1` counts in `{A, C} × {T1}`. That can only add numbers to the taken set, so
the error stays one-sided (FR-007). The same rule answers the `division` filter of the allocation
list, so one value can be returned under two divisions (FR-025).

**Rationale**: the PRD's FR-001 and FR-007 ask for exactly this read. Omitting the fork-window leg
on the hop would free a number in a division an older branch still sees the holder in, which breaks
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
attribute `.value`, enum unwrapped). `AttributePoolApplier.apply` calls it and passes the key
through `NumberPoolAttributeAllocator.allocate` to `CoreNumberPool.get_resource`, whose signature
gains `division: DivisionKey | None`.

Three write paths reach allocation:

- **Create through the ordinary path**: nothing moves; `Node._process_fields` applies relationships
  before attributes.
- **Create through a template**: the applier allocates before any relationship exists and without a
  node. It stops allocating: `_handle_pool_relationship` records the pool id and marks the attribute
  pending (the `TemplatePoolFields.pending` mechanism exists and the mandatory-attribute check
  already tolerates it), and `_process_fields_attributes` runs `AttributePoolApplier.apply` for it
  after the relationships are applied, as it does for a user `from_pool`.
- **Update**: `Node.from_graphql` applies every attribute with `process_pools=False` (the flag
  exists; the lock-name preview already uses it), then runs `AttributePoolApplier.apply(...,
  allocate=True)` for each attribute whose payload carried `from_pool`. `from_pool` itself is still
  assigned inline by `BaseAttribute.from_graphql`; only the allocation is deferred, and with it
  the lock per pool and division, which `get_resource` takes once the division is resolved (D5).

The attribute-add backfill (`core/migrations/schema/node_attribute_add.py`) loads each node with its
scoped fields in the same query it already runs and passes the node's division; the template
allocation in `core/node/create.py` runs after `obj.new()` and passes the division of the built
node.

**Rationale**: FR-002. The in-memory node is the only place the "node as it will be saved" exists
before the write, and the relationship manager already answers `get_peer_id` from it.

**Alternatives**: read the division from the database (wrong on a create and on a same-request
move); reorder the payload dict (fragile, and P2's intent resolver will also sit on this path);
keep the applier allocating from the raw field dict (no node, so no division).

### D5 — The lock is keyed by pool and division

**Decision**: on a scoped pool `CoreNumberPool.get_resource` locks on
`resource_pool.<pool id>.<division key>`, the division key being the normalised tuple of the
writer's entry values in scope order; on an unscoped pool it keeps `resource_pool.<pool id>`. The
lock is taken inside `get_resource`, after the division is resolved, so on the update path after
every field of the payload is applied (D4). Every write that takes the pool lock for a tracked
attribute uses the same key. On a scoped pool the lock on pool and division replaces the
mutation-level pool lock that `core/node/lock_utils.py::get_lock_names_on_object_mutation` derives
from `from_pool` before the node is saved: that lock is not taken for a scoped pool, because held
for the whole mutation it would serialise every division. An unscoped pool keeps the pool-level
lock. A functional test pins it: two writers in different divisions allocate in parallel and two
writers in one division serialise.

**Rationale**: the Notion PRD's Mechanism table ("Lock": `pool_id` → `pool_id + scope_key`) and
FR-031 ask for it: without it one scoped pool serialises every division that a pool per site ran in
parallel, which is the consolidation journey's regression. SC-005 measures what the key buys; it
does not decide whether it exists.

**Alternatives**: the pool-level lock alone (serialises divisions; rejected by the PRD); a lock per
division taken at the mutation level from the payload (the division is not known before the fields
are applied on update and template create, D4).

### D6 — Utilization: one query returns rows with their division values; a pure reporter computes every figures block

**Decision**: `NumberPoolGetAllocated` moves onto the shared records fragment (so it gains the
deleting-branch and fork-window behaviour the used/free reads have), projects the record's
provenance, makes its bounds filter optional, and, when the pool is scoped, returns per row the
collected values of each entry in force. `pools/number.py::NumberUtilizationGetter` becomes a seam
that loads rows and hands them to a pure `pools/division_report.py::DivisionReporter`, which
expands each row into the divisions it occupies, counts distinct values per division per branch
split, and orders the divisions by utilization. The reporter answers every
`NumberPoolUtilizationFigures` block: each division's over the pool, and one given division's over
the pool and over each range (FR-011, FR-015, FR-017, FR-022); on an unscoped pool, the pool's and
each range's. A division's figures count the rows whose holder occupies the division on any live
branch, the same union the `division` filter applies (D3), so one value can count in several
divisions; `used_default_branch` is the division's values held on the default branch and
`used_branches` those held on other branches only. The divisions listed are those the rows occupy,
so a division whose nodes hold no value is not listed (FR-011). For the divisions list,
relationship peers are resolved to display labels by one `NodeManager.get_many(...,
branch_agnostic=True)` over the distinct peer ids, and a peer that still cannot be read (a
division keyed by a node that exists only on a branch the reader cannot see) is labelled by its
identifier so the non-null field never voids the list. A new `NumberPoolDivisions` query
enumerates the distinct division tuples over `(n:Node:<kind>)-[:IS_PART_OF]->(:Root)` on any live
branch, with the node count of each, for the sizing check on a scoped attribute add (D9); the
divisions list does not use it.

The generic `InfrahubResourcePoolAllocated` query shares `NumberPoolGetAllocated`, so the row shape
keeps holder id, branch, value and record identifier and the generic resolver keeps the bounds
filter on; the move onto the shared fragment is pinned by regression tests on that query's count,
offset and limit and on the generic utilization figures.

On an unscoped pool the getter's report holds a single entry with an empty key and the figures it
computes today; the divisions query lists no division for it (FR-022).

**Rationale**: one read for the figures keeps the headline, the range rows and the divisions
consistent by construction. The enumeration is the one place the pool reads the kind's data, as
the PRD decided.

**Alternatives**: one query per division (N+1); a division breakdown inside every range row (more
than the first division view needs; additive later).

### D7 — Number-pool reads are published on a surface dedicated to number pools; the generic queries are frozen

**Decision**: three new root query fields, `InfrahubNumberPoolUtilization`,
`InfrahubNumberPoolDivisions` and `InfrahubNumberPoolAllocations`, with their types, input and
enum, hand-written in a new module `graphql/queries/number_pool.py` and registered in
`graphql/schema.py::InfrahubBaseQuery` beside the generic fields. Their shape follows the
number-pool data model: one figures block with absolute counts reused for the pool, each range and
each division; ranges typed as ranges; rows carrying the holder as a flat type (id, hfid, kind,
display label), the provenance and the range; a structured `division` filter mirroring the
entries of a listed division; `allocation_scope` in force on the results. See
[contracts/graphql-number-pool-surface.md](./contracts/graphql-number-pool-surface.md).

`InfrahubResourcePoolUtilization`, `InfrahubResourcePoolAllocated`, `PoolUtilization`,
`PoolAllocated` and `PoolAllocatedNode` keep their shape and meaning for every pool kind; a scoped
pool reports pool-wide figures there. Their descriptions gain a note pointing number-pool consumers
at the dedicated queries. No `@deprecated`: GraphQL cannot deprecate a field for one pool kind.
P2's provenance, which `dev/specs/ifc-3184-pool-number-attach` placed on the generic pool queries,
is carried by the dedicated surface instead (`provenance` on each row). The dedicated surface
lists only values of the pool's space; a value outside it is not listed and counts in no figure.

Form A (several root fields, following the `Infrahub*` convention) is the shape of the surface;
form B (one root object with sub-fields) is not built. Decided on 2026-10-07.

**Rationale**: the frontend needs of 2026-10-06 (ranges with absolute figures, per-division rows
with branch split, divisions per range, holder labels, provenance filter) cannot be met by the
generic queries without number-pool-only arguments and fields that would be empty for IP pools;
`resource_id` is already required and ignored for number pools. A surface shaped like number pools
lets the frontend build every number pool screen against a frozen contract before the backend
computes divisions.

**Alternatives**: `divisions` on `PoolUtilization` and a `division` argument on
`InfrahubResourcePoolAllocated` (always empty or ignored for IP pools, and the range rows stay IP
types); one root object `InfrahubNumberPool` (form B, not built; decided on 2026-10-07); `edges { node }` wrapping on
the dedicated lists (rejected for uniformity with `ranges` and `divisions`, which the frontend
consumes as plain lists).

### D8 — FR-010 is a constraint checker over a pool-side lookup, registered for the removal migrations too

**Decision**: a `ScopedPoolDependencyChecker` in `core/validators/pool/scope.py` registered in
`CONSTRAINT_VALIDATOR_MAP` for `attribute.optional.update`, `relationship.optional.update`,
`relationship.cardinality.update`, `attribute.unique.update` (the pool's own attribute made unique
while the pool carries a scope), `node.attribute.remove` and `node.relationship.remove`. Nothing
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

A rename of a field a scope names is refused by the same checker (FR-032), naming the field and
every pool that names it, user-created or schema-created, with a message telling the author to
remove the entry from the scopes, rename, then set the scope with the new name. The checker looks
the pools up by the field's previous name, taken from the previous schema by the attribute or
relationship id, since that is the name the stored scopes hold. Neither rename name is a key of
`CONSTRAINT_VALIDATOR_MAP` today: `attribute.name.update` exists as a migration (the attribute's
`name` is `MIGRATION_REQUIRED`), so adding the key to the map is enough, as for the two removal
names; the relationship's `name` is `UpdateSupport.ALLOWED` in `core/schema/definitions/internal.py`
and yields neither a migration nor a constraint, so it becomes `VALIDATE_CONSTRAINT` (the generated
`relationship_schema.py` regenerated) and `relationship.name.update` is added to the map. The
pool's own `node_attribute` has the same exposure to a rename today and is outside this epic.

**Rationale for the refusal**: a stored scope is data the system never rewrites; the operator
changes it through the pool (or the declaration) in two explicit steps. Decided on 2026-10-08.

**Alternatives**: a pure schema-branch check (cannot see pools, which are data); a Cypher filter on
the list value (format-dependent); rewriting the scope entries during the rename's schema
migration (a system write to pool data, with a branch rule to invent for the branch-agnostic pool;
rejected on 2026-10-08).

### D9 — The attribute-add size check compares against the largest division

**Decision**: when a `NumberPool` attribute being added declares `allocation_scope`,
`NodeAttributeAddChecker` compares the pool size against the largest per-division node count
from `NumberPoolDivisions` rather than the kind's total count.

**Rationale**: a scoped pool legitimately serves more nodes than its size.

### D10 — Schema-declared scope is reconciled from the default branch, like the bounds

**Decision**: `NumberPoolParameters.allocation_scope: list[str] | None = None`, with `update`
support `ALLOWED` (changing it moves no data, FR-006); #10917 shipped the field as
`NOT_SUPPORTED` and IFC-3351 switches it, so that a schema load that sets, changes or clears the
declaration passes the schema-update validation. FR-009's entry rules run in
`_validate_number_pool_parameters` on the branch being loaded. `SchemaNumberPoolUpserter` writes
the scope at creation; `SchemaNumberPoolSynchronizer._update_pool_from_schema` copies it from the
default-branch schema as it copies the bounds. `InfrahubNumberPoolMutation.mutate_update` refuses a
scope change on a `pool_type == Schema` pool with the existing default-branch message (FR-013).
This is the Notion PRD's FR-018 amendment ("set, change and clear are one attribute update"),
applied to the schema declaration as to the pool. Decided on 2026-10-08.

**Alternatives**: keeping `NOT_SUPPORTED` as shipped, the declaration fixed with the attribute
(rejected on 2026-10-08: it departs from the PRD and leaves no way to change a schema-created
pool's scope).

The SDK, OpenAPI and frontend REST models are not introspected from the Pydantic class:
`tasks/backend.py::SdkSchemaGenerator.number_pool_parameters_fields` lists the parameter fields by
hand, so the new field is added there as a `List` field and the generators re-run.

### D11 — Contract first, over a fixed in-memory dataset

**Decision**: the delivery order the spec records. The schema attribute and the parameters field
land first; then the dedicated surface with every shape frozen. That change set answers the three
queries from a fixed in-memory dataset in `pools/number_pool_mock.py` and reads nothing from the
database: a pool scoped by `site` for any `pool_id`, and an unscoped pool for the reserved id
`mock-unscoped`. Every figure is computed from the dataset's rows with the contract's definitions
(on the scoped dataset, the headline and range rows of the division given), and the filters,
ordering, pagination and refusals apply to the dataset, so lists, filters and counts agree (SC-010).
The generated artefacts are regenerated once at the contract step and must not change afterwards
(FR-018); a snapshot test pins the SDL. The real reads replace the module, and the last change set
of the slice deletes it and adds a test asserting that the three queries return the requested pool's
own data (FR-019, SC-011).

**Rationale**: the user decided that the first delivery reads nothing from the database, so the
frontend builds every screen against plausible data with the final shapes before any read exists.
A fixed dataset reproducing the contract's scoped example is the same on every request and across
the three queries, which is what makes the contract testable before the internals exist. The model is the weighted-ranges contract change set, which published
the whole GraphQL surface with indicative range figures and landed the allocation internals later.

**Alternatives**: a single empty-key division on every pool (the frontend cannot build the division
view against it); random partitions (lists and filters disagree between requests); waiting for the
division reads (blocks the frontend).

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
A  schema attribute + parameters field + SDK generator entry       (one PR, small, first)
B  dedicated GraphQL surface: three root fields over a fixed        (depends on A; unblocks frontend + SDK)
   in-memory dataset (no database read),
   description notes on the generic queries, regen, SDL snapshot
C  seams: get_resource(division) on all three write paths,          (depends on A and on D3's
   NumberUtilizationGetter → DivisionReporter                        DivisionKey; parallel with B)
D1 DivisionResolver.division_of + scoped records fragment +         (depends on C)       ┐
   allocation
D2 NumberPoolDivisions + scoped allocated rows + real reads        (depends on B, C,    ├ parallel
   in the three queries                                              D3's entries_in_force)
D3 scope write path: ScopeEntry, DivisionKey, entries_in_force,     (depends on A)       │
   ScopeValidator in the mutation, schema-pool refusal,
   upserter/synchronizer, schema-load validation, attribute-add size check
D4 ScopedPoolDependencyChecker + PoolsReferencingField + the        (depends on A)       ┘
   rename refusal
E  mock removal: delete number_pool_mock.py, real-data test         (depends on D2)
F  measurement, docs, changelog                                     (depends on D1, E)
```

This slice and part 1 share `NumberPoolParameters`, the picker's range walk, `EffectiveSpace` and
the SDK generator. D1's fragment change is parameter-only and sits inside the range walk, which
calls the fragment once per segment; `size`, `used` and the listed values of the dedicated surface come
from `EffectiveSpace`, so the surface and allocation use one definition of the pool's space. The
SDK models of both parts merge into `infrahub-develop` before the release merge (IFC-3356).

---

## 4. Open risks carried into the plan

- **The hop's fork-window leg** doubles the subquery per entry, and the record-side anchor runs it
  per record. Both anchor orders are profiled before one is kept; SC-006 is the measurement; if the
  figure is still bad, the next lever is a stored division key, which the PRD keeps as an
  optimisation.
- **Test fixtures**: the shared snow schema's pooled attribute is `unique`, so a scoped test on it
  is masked by the global taken-values scan. Scoped tests use a non-unique pooled attribute on a
  kind with a required cardinality-one relationship and a required scalar attribute.
- **Update-path deferral of the pool allocation** (`AttributePoolApplier.apply` run after the loop)
  changes the order in which validation errors surface for a payload that both fails a
  relationship update and allocates. The functional lifecycle suite pins the observable order.
- **P2's intent resolver** will also sit on `from_graphql`; D4 keeps the deferral in one place so the
  resolver slots in after it.
- **`NumberPoolGetAllocated` on the shared fragment** changes which records the allocation lists
  show on a deleting branch. That is the fix the P2 research already asked for; it is noted in the
  changelog.
- **The fixed dataset mistaken for final data**: the contract states it, any `pool_id` returns the
  same pool, and the test of set E fails the slice until the real reads land.
