# Implementation Plan: Scoped number pools — one pool serves every scope

**Branch**: `feature-number-pools-1.12` | **Date**: 2026-10-02, surface decisions 2026-10-06 | **Spec**: [spec.md](./spec.md)

**Epic**: [IFC-3185](https://opsmill.atlassian.net/browse/IFC-3185)

**Input**: Feature specification from `dev/specs/ifc-3185-scoped-number-pools/spec.md`, derived
from `SCOPED-POOLS-PRD.md`, the frontend needs of 2026-10-06 and the grilling decisions of the same
day. Research and decisions in [research.md](./research.md).

---

## Summary

A number pool gains `allocation_scope`, a list of fields of its kind. With a scope set, allocation
returns the lowest free number within the division the node being written belongs to, and
utilization reports one division at a time, with every division holding a value listed from the
fullest. The scope decides which number comes next and nothing else: it refuses nothing and stores
nothing. A record's
division is derived at read time from its holder's fields, as a union over every live branch,
inside the records fragment the used and free reads already share. A pool with no scope issues the
query it issues today.

Every read a number pool screen needs is published on three GraphQL root fields dedicated to
number pools: utilization with absolute figures per pool and per range, the divisions list, and the
allocation list with holder, provenance and range, filterable by division. The generic
resource-pool queries are frozen for number pools and gain a description note.

The work is sequenced so the frontend and the SDK are unblocked first: the schema attribute and the
parameters field land, the dedicated surface is published and frozen over a fixed in-memory
dataset that reads nothing from the database, then the allocation and utilization seams, then the
internals in parallel, then the real reads replace the fixed dataset.

---

## Technical Context

**Language/Version**: Python 3.14

**Primary Dependencies**: FastAPI 0.131, graphene (pinned), Pydantic 2.12, Neo4j driver 6.2

**Storage**: Neo4j 2026.05, temporal and branch-aware property graph (`dev/knowledge/backend/database-schema.md`)

**Testing**: pytest 9.0. `tests/unit/` for the resolver, validator, reporter and the SDL snapshot;
`tests/component/` for queries, mutations, checkers and the three dedicated GraphQL queries;
`tests/functional/` for the lifecycle and branch suites; `tests/integration_docker/` for the
schema-load refusal; `tests/query_benchmark/` for SC-006; SC-005 as a timed functional scenario
under `tests/functional/pools/`.

**Target Platform**: Linux server (containerised backend)

**Project Type**: Backend-only change to an existing web service. No frontend work beyond
regenerating the GraphQL types; the dedicated surface must carry everything the pool form, the
range view, the division view and the allocation list need.

**Performance Goals**: no numeric gate. SC-005 (throughput of one scoped pool against N per-site
pools under concurrent allocation) and SC-006 (latency on a full 4094-number pool, three entries,
five branches) are measured and reported.

**Constraints**:

- The unscoped records fragment renders byte-for-byte as today (FR-005, SC-003).
- Liveness stays one-sided: a number may read as taken that is free on some branch, never free when
  taken on any (FR-007).
- The scope is branch-agnostic; a branch that cannot resolve an entry drops it (FR-008, FR-021).
- The contract published in User Story 1 does not change afterwards (FR-018); the generic queries
  change in description text only (FR-029, SC-009).
- No graph migration, no new kind, no new edge, no new record property.

**Scale/Scope**: 1 new core attribute, 1 new parameters field, 1 records-fragment extension, 1
new enumeration query, 1 query moved onto the shared fragment and extended, 3 new pure modules, 1
temporary mock module, 1 new checker, 1 new repository, 3 GraphQL root fields with 10 object types,
1 input and 1 enum, 0 migrations, 0 dependencies.

---

## Constitution Check

*Gate evaluated before Phase 0 and re-evaluated after Phase 1 design. Constitution v1.0.0.*

| Principle | Verdict | Notes |
|---|---|---|
| **I. Schema-Driven Integrity** | ✅ passes | One new optional attribute on a core kind applied by the core schema update; no data migration. Generated files regenerated with `uv run invoke backend.generate`, `schema.generate-graphqlschema`, `schema.generate-jsonschema`, `docs.generate` and `pnpm codegen`. |
| **II. Branch-Safe by Default** | ⚠️ gated, this is the principle under test | The cross-branch read is the design: records are `-global-`, nodes are branch-aware, the division is a union over live branches with the visibility rule the value read already uses. Merge needs no new validator (the scope does not merge; the values it reads do). Every branch case in the spec's edge list gets a two-branch component test. |
| **III. Type Safety & Explicit Contracts** | ✅ passes | Three contracts agreed before implementation (`contracts/`). Query results come back as frozen dataclasses; the division key is a frozen dataclass; GraphQL types are explicit and pinned by an SDL snapshot test. |
| **IV. Test Discipline** | ✅ passes | Unit for `entries_in_force`, `ScopeValidator`, `DivisionReporter` and the SDL snapshot; component for `division_of`, every query, mutation and checker, and the three dedicated GraphQL queries on an unscoped pool, a scoped pool and an IP pool; functional for the journeys and the concurrent case; one integration-docker test for the schema-load refusal; no E2E because no screen ships. The shared snow fixture's pooled attribute is `unique`, which the global taken-values scan masks, so scoped tests use a non-unique pooled attribute on a kind with a required cardinality-one relationship and a required scalar attribute (extending `tests/helpers/number_pool.py` with such a schema). |
| **V. Query Performance & Efficiency** | ⚠️ gated | The division hop adds one two-leg subquery per entry per record, bounded by pool occupancy. `EXPLAIN` on the scoped free query is recorded in `measurements.md`; SC-006 is a benchmark under `tests/query_benchmark/` and SC-005 a timed functional scenario under `tests/functional/pools/`. All parameters bound; only needed properties returned. The dedicated allocation query pushes the pool's space, `range_id`, `branch` and `provenance` into Cypher; the first delivery filters its fixed dataset in memory and runs no query. |
| **VI. Security & Input Boundaries** | ✅ passes | Scope entries validated at the mutation and the schema-load boundary before any query uses them; entry names are bound as parameters, never interpolated (the relationship identifier and attribute name are looked up from the schema and bound). The `division` filter's paths are checked against the scope in force before any read. Errors name the entry, the pool or the range, never internals. |
| **VII. Simplicity** | ✅ passes with two justifications | Derived scope: no hook, no migration, no batch, no new kind. One shared Cypher visibility constant is extracted because it reaches three consumers (the bar the query guideline sets). The repository and the three pure modules each serve two callers at introduction; the dedicated surface is a new module rather than fields on the generic queries (see Complexity Tracking). |

Post-design re-check: no new violations. Two gated items (II, V) carry their conditions as tasks.

---

## Project Structure

### Documentation (this feature)

```text
dev/specs/ifc-3185-scoped-number-pools/
├── spec.md
├── plan.md                  # this file
├── research.md              # Phase 0: corrections to the PRD, decisions D1–D12
├── data-model.md            # Phase 1
├── quickstart.md            # Phase 1
├── contracts/
│   ├── graphql-pool-scope.md               # allocation_scope on the pool and its inputs
│   ├── graphql-number-pool-surface.md      # the three dedicated root fields; generic queries frozen
│   └── number-pool-parameters.md           # allocation_scope in the attribute parameters
├── checklists/requirements.md
├── critiques/               # Phase 3
├── measurements.md          # written when SC-005 / SC-006 run
└── tasks.md                 # Phase 2 (/speckit-tasks)
```

### Source code (repository root)

```text
backend/infrahub/
├── core/
│   ├── schema/
│   │   ├── definitions/core/resource_pool.py     # allocation_scope on core_number_pool
│   │   ├── attribute_parameters.py              # NumberPoolParameters.allocation_scope
│   │   └── schema_branch.py                     # _validate_number_pool_parameters → ScopeValidator
│   ├── query/resource_manager.py                # reserved_values_query(division=…), shared visibility
│   │                                            # constant, NumberPoolGetAllocated on the fragment with
│   │                                            # provenance and a range-set filter, NumberPoolDivisions (new)
│   ├── node/
│   │   ├── __init__.py                          # from_graphql and _process_fields_attributes defer the pool applier
│   │   ├── create.py                            # template allocation passes the division
│   │   ├── lock_utils.py                        # the mutation-level pool lock is not derived for a scoped pool
│   │   └── resource_manager/number_pool.py      # get_resource(division=…) locks per pool and division, hands the division to the picker
│   ├── migrations/schema/node_attribute_add.py  # backfill loads the scoped fields and passes each node's division
│   ├── schema/definitions/internal.py           # relationship `name` moves to VALIDATE_CONSTRAINT so a rename yields a constraint (FR-032)
│   └── validators/
│       ├── __init__.py                          # map the new checker, the two rename names included
│       ├── composite.py                         # CompositeConstraintChecker (new)
│       ├── pool/scope.py                        # ScopedPoolDependencyChecker (new)
│       └── node/attribute.py                    # size check against the largest division
├── templates/node_applier.py                    # pool allocation deferred until relationships are applied
├── pools/
│   ├── number_ranges.py                         # EffectiveSpace: the pool's space, size, contains, range_for (existing, consumed)
│   ├── number_pool_space.py                     # builds the EffectiveSpace from the ranges and the attribute's domain (existing, consumed)
│   ├── attribute_pool_applier.py                # AttributePoolApplier.apply resolves the division and passes it to the allocator
│   ├── number_pool_attribute_allocator.py       # allocate(division=…) (existing)
│   ├── number_pool_number_picker.py             # next_number(division=…) drains the ranges heaviest first (existing)
│   ├── number_pool_repository.py                # get_free / get_used take the division; get_taken keeps the global scan (existing)
│   ├── default_allocator.py                     # no longer allocates from the raw field dict
│   ├── scope.py                                 # ScopeEntry, DivisionKey, DivisionResolver, ScopeValidator (new)
│   ├── division_report.py                       # DivisionReporter (new, pure)
│   ├── number_pool_mock.py                      # fixed in-memory dataset (new in B, deleted in E)
│   ├── referencing.py                           # PoolsReferencingField (new repository)
│   ├── number.py                                # NumberUtilizationGetter → seam over DivisionReporter
│   ├── schema_number_pool_upserter.py           # writes allocation_scope at creation
│   └── schema_number_pool_synchronizer.py       # copies allocation_scope from the default branch
└── graphql/
    ├── schema.py                                # registers the three dedicated root fields
    ├── queries/number_pool.py                   # the dedicated surface: types, input, enum, resolvers (new)
    ├── queries/resource_manager.py              # description notes on the generic queries and types
    └── mutations/resource_manager/number_pools/pool.py   # ScopeValidator on create/update/upsert; schema-pool refusal

backend/tests/
├── unit/pools/                                  # test_scope.py, test_division_report.py (new); test_number_pool_mock.py (set B, deleted in E)
├── unit/graphql/                                # test_number_pool_surface_contract.py (SDL snapshot, new)
├── unit/core/validators/                        # test_scoped_pool_dependency.py, test_composite_checker.py (new)
├── component/core/resource_manager/             # test_number_pool_scoped_query.py, test_division_resolver.py, test_number_pool_divisions_query.py (new), fragment snapshot
├── component/graphql/resource_manager/number_pools/   # test_pool_allocation_scope.py (#10917, extended), beside test_pool_create.py and test_pool_update.py
├── component/graphql/queries/                   # test_number_pool_surface.py (new), test_resource_pool.py (regression)
├── component/core/constraint_validators/        # test_scoped_pool_dependency.py, test_scoped_field_rename.py (new), attribute-add case
├── component/pools/                             # test_schema_number_pool_scope.py, test_pools_referencing_field.py (new)
├── functional/pools/                            # test_numberpool_scoped_allocation.py, test_numberpool_scoped_branch.py, test_numberpool_scoped_throughput.py (new)
├── integration_docker/                          # test_number_pool_scope_schema_load.py (new)
├── query_benchmark/                             # test_number_pool_scoped_allocation.py (new, SC-006)
└── helpers/number_pool.py                       # SCOPED_POOL_SCHEMA (set B): a non-unique pooled attribute on a kind with a required
                                                 # cardinality-one relationship and a required scalar attribute; the fixture and the
                                                 # site, node and two-range pool factories land with IFC-3349

tasks/backend.py                                 # SdkSchemaGenerator.number_pool_parameters_fields gains the List field
python_sdk/                                      # regenerated models (separate PR, pointer bump after)
schema/schema.graphql                            # regenerated
frontend/app/src/shared/api/graphql/generated/   # regenerated by pnpm codegen
docs/docs/schema/number-pool.mdx, docs/docs/resource-manager/allocate-number.mdx   # new section each
dev/knowledge/backend/database-schema.md         # the division read beside the reservation read
changelog/                                       # 8 towncrier fragments
```

**Structure decision**: the feature slots into the existing layout. Pure logic goes in
`backend/infrahub/pools/`, which already owns pool arithmetic and is imported from `core/` and
`graphql/`. Cypher stays in `core/query/resource_manager.py`, where every pool query lives. The
dedicated surface is one new module under `graphql/queries/`, beside the generic resource-pool
module, so the generic file changes in description strings only. The checker goes under
`core/validators/` beside its peers. No new top-level package.

---

## Phase 1 — Design

### 1. Delivery order and the change sets

| Set | Content | Depends on | Unblocks |
|---|---|---|---|
| **A. Schema** | `allocation_scope` on the pool kind; `NumberPoolParameters.allocation_scope`; the hand-maintained SDK generator entry in `tasks/backend.py::SdkSchemaGenerator.number_pool_parameters_fields`; regenerate protocols, GraphQL schema, OpenAPI, SDK models, docs snippet | — | everything |
| **B. Surface** | `graphql/queries/number_pool.py` with the three root fields and every type of the contract, answering from the fixed in-memory dataset of `pools/number_pool_mock.py` (no database read); description notes on the generic queries and types; regenerate `schema/schema.graphql` and the frontend types; SDL snapshot test | A | frontend, SDK |
| **C. Seams** | the division threaded from the three write paths (ordinary create, template create with the applier's allocation deferred to `_process_fields_attributes`, update with `AttributePoolApplier.apply` deferred in `from_graphql`) and from the attribute-add backfill, along `AttributePoolApplier.apply` → `NumberPoolAttributeAllocator.allocate` → `CoreNumberPool.get_resource` → `NumberPoolNumberPicker.next_number` → `NumberPoolRepository.get_free` / `get_used`; `NumberUtilizationGetter` reduced to a seam over `DivisionReporter` returning one division. `DivisionKey` and `entries_in_force` come from D3's validator ticket (IFC-3348) | A, D3 (`DivisionKey`) | D1, D2 |
| **D1. Scoped allocation** | `DivisionResolver.division_of`; `reserved_values_query(division=…, with_branch=…)`, the shared visibility constant, both anchor orders profiled, the division applied inside the fragment `NumberPoolGetFree` and `NumberPoolGetUsed` share; the lock per pool and division replacing the mutation-level pool lock on a scoped pool; the unscoped snapshot test | C | F |
| **D2. Scoped reads** | `NumberPoolGetAllocated` on the fragment with branch and per-entry values; `NumberPoolDivisions`; the reporter's division figures over the pool and over one range; the three dedicated queries read the pool, its ranges, its rows and the reporter instead of the fixed dataset (with `NumberPoolGetAllocated` projecting provenance and filtering on the pool's space, the bounds, branch and provenance); peer display labels with the identifier fallback; range rows of the division read; the `division` filter in Cypher | B, C, D1, and IFC-3348 (`DivisionResolver.entries_in_force`) | E |
| **D3. Scope write path** | `ScopeEntry`, `DivisionKey`, `entries_in_force`; `ScopeValidator`; the mutation validation against the schema of the branch where the mutation runs, on every save that carries `allocation_scope`; the schema-pool refusal; the upserter and synchronizer writes so a schema-declared scope reads back and follows the default-branch declaration (`update: ALLOWED`); `_validate_number_pool_parameters` through `ScopeValidator`; the attribute-add size check against the largest division | A (the size check also needs D2's `NumberPoolDivisions`) | — |
| **D4. Dependency checker** | `PoolsReferencingField`; `ScopedPoolDependencyChecker` registered for the four update constraints, the two removal migrations and the two rename names (FR-032, the relationship `name` switched to `VALIDATE_CONSTRAINT`); integration-docker test | A | — |
| **E. Mock removal** | delete `pools/number_pool_mock.py` and its call sites; the test that the three queries return the requested pool's own data and refuse an unknown `pool_id`; the SDL snapshot unchanged | D2 | F |
| **F. Close** | SC-006 benchmark, SC-005 timed scenario, `measurements.md`; the consolidation journey through attach; user docs; knowledge entry; changelog fragments; the record of the surface decision (form A) | D1, E | ship |

The change sets ship as the Jira tickets of [tasks.md](./tasks.md): A is IFC-3334; B is IFC-3346
(the contract) and IFC-3347 (the queries over the fixed dataset); the validator of D3 is IFC-3348;
D4 is IFC-3352; C and D1 together are IFC-3349; the size check of D3 is IFC-3353; the schema side
of D3 is IFC-3351; D2 and E together are IFC-3329; F is IFC-3354 (final testing: two-branch
verification, consolidation, measurement) and IFC-3356 (wrap up: docs, changelog, SDK pointer). The
validator lands before scoped allocation so that the division resolver only meets scopes the
validator accepted; IFC-3352 runs in parallel with both.

### 2. The division read inside the records fragment (D1)

`reserved_values_query(pool_id, attribute_name, at, default_branch_name, division=None,
with_branch=False)`. With `division=None` and `with_branch=False` the rendered text is today's.
With `with_branch=True` (the allocated read only) both legs of the value read also project
`branch` — the open edge's branch, or each surviving window's name for the fork-window leg — and
the fragment ends `WITH DISTINCT res, value, branch`. With a division:

```cypher
MATCH (pool:Node:CoreNumberPool { uuid: $pool_id })-[res:IS_RESERVED]->(attr:Attribute { name: $attribute_name })
WHERE <res open at $at>
MATCH (n:Node)-[:HAS_ATTRIBUTE]->(attr)
// one subquery per entry in force, i = 0..k-1
CALL (n, deleting_branches, branch_windows) {
    MATCH (n)-[r1:IS_RELATED]-(rel:Relationship { name: $entry_0_identifier })-[r2:IS_RELATED]-(peer:Node)
    WHERE <VISIBLE(r1)> AND <VISIBLE(r2)>
    RETURN collect(DISTINCT peer.uuid) AS entry_0_values
}
CALL (n, deleting_branches, branch_windows) {
    MATCH (n)-[ha:HAS_ATTRIBUTE]->(a:Attribute { name: $entry_1_name })-[hv:HAS_VALUE]->(av)
    WHERE <VISIBLE(ha)> AND <VISIBLE(hv)>
    RETURN collect(DISTINCT av.value) AS entry_1_values
}
WITH attr, res, deleting_branches, branch_windows
WHERE $entry_0_value IN entry_0_values AND $entry_1_value IN entry_1_values
CALL (attr, deleting_branches, branch_windows) { <the existing two-leg value read> }
WITH DISTINCT res, value
```

`VISIBLE(edge)` is the named constant: open now on a non-deleting branch, or closed on the default
branch and still seen from a fork window with no hiding edge on the same vertex. It is the rule the
value read already applies, lifted so the three consumers share it. For a relationship hop the
arrows are rendered from the relationship's `direction`, as `RelationshipGetPeerQuery` does, so a
self-referencing relationship does not collect its reverse peers. Entry names and identifiers are
schema lookups bound as parameters; the number of subqueries is the number of entries in force,
which is small and fixed per pool.

The sketch above anchors on the record and filters on the division last, which runs the entry
subqueries once per record. The alternative anchors on the division — match the writer's peer or
value vertex, walk to the nodes that hold it, then to their reserved attributes — and touches only
the records in the division. Both are rendered behind the same parameter and profiled at the
SC-006 shape and at a hub shape; the kept order and the figures go to `measurements.md`.

### 3. The writer's division (C, D1)

```python
@dataclass(frozen=True)
class DivisionKey:
    entries: tuple[ScopeEntry, ...]
    values: tuple[str | int | bool | None, ...]

class DivisionResolver:
    def entries_in_force(self, scope: Sequence[str], schema_branch: SchemaBranch, kind: str) -> tuple[ScopeEntry, ...]
    async def division_of(self, db: InfrahubDatabase, node: Node, entries: tuple[ScopeEntry, ...]) -> DivisionKey
```

`entries_in_force` is pure and unit-tested. `division_of` is not: the relationship manager may read
the database to resolve a peer given by id or human-friendly id, so it takes `db` and is
component-tested.

`pools/attribute_pool_applier.py::AttributePoolApplier.apply(node, attribute, allocate)`, the
allocation entry point `BaseAttribute.from_graphql` and `Node._process_fields_attributes` call,
resolves the entries against `registry.schema.get_schema_branch(node._branch.name)` and the
division from the node, then calls `NumberPoolAttributeAllocator.allocate(..., division=key)`,
which passes it to `CoreNumberPool.get_resource`, then to `NumberPoolNumberPicker.next_number`,
which passes it to `NumberPoolRepository.get_free` on every segment of its range walk; `get_used`
takes it for the same reason. `get_taken` keeps its global scan over the attribute: on a `unique`
attribute every value present anywhere is skipped, scope or not. An empty `entries` tuple means
unscoped on this branch and the fragment renders unchanged.

Three write paths reach allocation, and each reads the division after the scoped fields are set:

| Path | Today | Change |
|---|---|---|
| Create, ordinary | `Node._process_fields` applies relationships, then attributes, where `_process_fields_attributes` calls `AttributePoolApplier.apply` | none |
| Create through a template | `Node._process_fields` calls the template applier first; `templates/node_applier.py::NodeTemplateApplier._handle_pool_relationship` allocates through `pools/default_allocator.py::DefaultPoolAllocator` from the raw field dict, before any relationship exists and with no node | the applier records the pool id and marks the attribute pending (`TemplatePoolFields.pending` exists and the mandatory check tolerates it); `_process_fields_attributes` runs `AttributePoolApplier.apply` for it after the relationships are applied |
| Update | `Node.from_graphql` applies the payload in dict order and `BaseAttribute.from_graphql` calls `AttributePoolApplier.apply(allocate=True)` inline when `process_pools` is set | `from_graphql` applies every attribute with `process_pools=False` (the flag and the `allocate=False` pass exist: `lock_utils.apply_payload_for_lock_names` uses them to resolve the pool for the lock names), then calls `AttributePoolApplier.apply(..., allocate=True)` for each attribute whose payload carried `from_pool` |

Invariant on the update path: `from_pool` is still assigned inline by `BaseAttribute.from_graphql`;
only the allocation is deferred, and `Node.from_graphql` has exactly two callers
(`lock_utils.apply_payload_for_lock_names`, `graphql/mutations/main.py`). The allocation lock is
keyed by pool and division on a scoped pool (`resource_pool.<pool id>.<division key>`) and by pool
alone on an unscoped pool; `get_resource` takes it after the division is resolved, which on update
is after every field of the payload is applied. On a scoped pool that lock replaces the
mutation-level pool lock that `core/node/lock_utils.py::get_lock_names_on_object_mutation` derives
from `from_pool` before the node is saved: held for the whole mutation it would serialise every
division, so it is not derived for a scoped pool. An unscoped pool keeps it. A functional test
pins the outcome: two writers in different divisions allocate in parallel, two writers in one
division serialise, and the deferral holds.

### 4. The dedicated surface (B, D2, E)

`graphql/queries/number_pool.py` holds the object types, the input, the enum and three resolvers,
one per root field, registered in `graphql/schema.py::InfrahubBaseQuery` as
`InfrahubNumberPoolUtilization`, `InfrahubNumberPoolDivisions` and `InfrahubNumberPoolAllocations`.
Each resolver loads the pool with `NodeManager.get_one` on the request's branch, refuses anything
that is not a `CoreNumberPool` with `NodeNotFoundError(node_type="CoreNumberPool")`, loads the
ranges branch-agnostically ordered by `start`, and resolves the scope in force with
`DivisionResolver.entries_in_force` (the function is pure and lands with the scope validator,
IFC-3348, before the real reads).

| Root field | Reads | Builds |
|---|---|---|
| `InfrahubNumberPoolUtilization` | the rows of `NumberPoolGetAllocated` over every range, kept to one division when `division` is given, the ranges from `NumberPoolRepository.get_ranges`, the attribute's `excluded_values`, `min_value` and `max_value` | `figures` for the pool and each range from the reporter, with `size` as the count of values of the pool's space; `allocation_scope` from the entries in force |
| `InfrahubNumberPoolDivisions` | the same rows, the pool's space as the measured space | one `NumberPoolDivision` per division holding at least one row, from the reporter (set B: from the fixed dataset), ordered by `utilization` descending then `display_label`; no division and `count` 0 when the scope in force is empty |
| `InfrahubNumberPoolAllocations` | `NumberPoolGetAllocated` with the pool's space (or the part of it in the range of `range_id`), `branch` and `provenance` pushed into the query; `offset` and `limit` | rows with `holder` (one `NodeManager.get_many` per distinct row branch for display label and hfid), `range` from the pool's ranges (set B: every column comes from the fixed dataset) |

None of the three resolvers reads the deprecated `start_range` / `end_range` pair: the shorthand
mirror leaves it null on a pool holding several ranges. The pool's space comes from
`pools/number_ranges.py::EffectiveSpace`, built from the pool's ranges and the attribute's domain
(`min_value` / `max_value` minus `excluded_values`) by `pools/number_pool_space.py`: `size` and
`size_of(range_id)` give the figures' denominators, `contains` decides whether a row is listed, `range_for`
gives the id of the row's range (its `display_label` comes from the range node loaded by `_ranges`),
`as_query_ranges` gives the bounds the rows query filters on. Allocation
draws from the same `EffectiveSpace`, so the surface and the picker use one definition of the
pool's space.

In set B every filter is applied in Python to the fixed dataset, and `count`, `offset` and `limit`
apply to the filtered list. In D2 the filters move into the queries: the `division` filter into the
scoped records fragment with the writer's division replaced by the requested entries, so `count` is
a Cypher count.

`NumberPoolGetAllocated` keeps its `ranges` argument and makes it optional (None: no bounds filter,
every tracked value; a list: the segments of the pool's space, `EffectiveSpace.as_query_ranges()`,
or those of the one range of `range_id`), gains `branch_name: str | None` and
`provenance: PoolRecordProvenance | None` filters, and projects
`coalesce(ir.provenance, "allocated") AS provenance`. The generic `InfrahubResourcePoolAllocated`
and `NumberUtilizationGetter` pass the space's segments as today and render the same text as today.

The reporter, after D2, returns:

```python
@dataclass(frozen=True)
class Figures:
    size: int
    used_default_branch: frozenset[int]
    used_branches: frozenset[int]          # values on other branches and not on the default branch

@dataclass(frozen=True)
class DivisionFigures:
    key: DivisionKey
    figures: Figures

@dataclass(frozen=True)
class DivisionReport:
    divisions: tuple[DivisionFigures, ...]   # every division holding a value, fullest first
    def of(self, key: DivisionKey) -> DivisionFigures: ...                         # one division over the pool
    def of_within(self, key: DivisionKey, start: int, end: int) -> DivisionFigures: ...   # one division over one range
```

The utilization resolver computes the pool's block from `of(key)` and each range's block from
`of_within(key, start, end)`, `key` being the division given; the divisions resolver lists
`divisions`. Peer display labels come from one
`NodeManager.get_many(..., branch_agnostic=True)` over the distinct peer ids of relationship
entries; a peer that still cannot be read is labelled by its identifier, and a holder holding
nothing for an entry carries an empty value, so the non-null fields never void the list. Unscoped:
`divisions` is one entry with an empty key, the pool's block equals today's figures, and the
divisions resolver lists no division. Regression
tests pin `InfrahubResourcePoolAllocated`'s count, offset and limit and the generic utilization
figures across the move onto the shared fragment.

The fixed dataset (`pools/number_pool_mock.py`, set B) holds two pools: a pool scoped by `site`
returned for any `pool_id`, and an unscoped pool returned for the reserved id `mock-unscoped`
(contract section "Fixed dataset of the first delivery"). It exposes `get_utilization`,
`get_divisions` and `get_allocations`, which compute every figure from the dataset's rows, apply the
filters, ordering and pagination in memory and raise the contract's `range_id` and `division`
refusals, including the refusal of an incomplete `division` on the utilization query. The resolvers
read nothing from the database. Set E deletes the module, and a component test asserts that the
three queries return the requested pool's own data and refuse a `pool_id` naming no number pool.

The generic queries change in description strings only: `description=` on the two root `Field`s in
`graphql/queries/resource_manager.py` and `class Meta: description` on `PoolUtilization`,
`PoolAllocated` and `PoolAllocatedNode`, with the texts of the contract. SC-009 is checked by
diffing `schema/schema.graphql` for those types.

### 5. Validation (D3, D4)

- `ScopeValidator(schema_branch).validate(kind, attribute_name, scope)` → normalised entries or
  `ValidationError` naming the entry (rules in `data-model.md` §1; the required check covers
  relationships locally because `validate_schema_path` exempts `ip_namespace` on IP kinds). Called
  by the mutation against the schema of the branch the mutation runs on
  (`registry.schema.get_schema_branch(name=branch.name)`) on every create, update or upsert that
  carries `allocation_scope`, and by `_validate_number_pool_parameters` (branch being loaded). The
  same rules, run by `entries_in_force` at read time, decide which entries apply on a branch
  (FR-008): an entry the reading branch does not define, or defines as an illegal entry, is
  ignored there.
- `ScopedPoolDependencyChecker.check(request)` → for the changed field, `PoolsReferencingField.get`
  and a `ValueError` naming each pool that names the field. Registered in `CONSTRAINT_VALIDATOR_MAP`
  for the six names in `contracts/number-pool-parameters.md`;
  `SchemaUpdateValidationResult.add_validator_for_migration` already turns the two removal
  migrations into constraints, so `core/models.py` is untouched. The map holds one checker class
  per name, so the four update names that already have a checker get a small
  `CompositeConstraintChecker` (`core/validators/composite.py`) that runs both and concatenates
  their results; the two removal names, unmapped today, map to the new checker directly. The checker
  reads the kind and field from `request.schema_path` only, never from `request.node_schema`, which
  is the candidate schema the removed field is already gone from.
- The rename refusal (FR-032): the same checker, registered for `attribute.name.update` (a
  migration name, turned into a constraint by `add_validator_for_migration` once it is in the map)
  and `relationship.name.update` (the relationship `name` in `core/schema/definitions/internal.py`
  switched from `ALLOWED` to `VALIDATE_CONSTRAINT`, `relationship_schema.py` regenerated), looks the
  pools up by the field's previous name and raises naming the field and each pool, with the
  two-step instruction. No stored scope is rewritten.
- `NodeAttributeAddChecker`: for a scoped declaration, size against the largest division's node
  count from `NumberPoolDivisions`.
- The three dedicated resolvers: `range_id` must be one of the pool's ranges; a `division` filter
  needs a non-empty scope in force, every path in force, no duplicate path, and on the utilization
  query a value for every path in force (messages in the contract).

### 6. Interface contracts

[contracts/graphql-pool-scope.md](./contracts/graphql-pool-scope.md),
[contracts/graphql-number-pool-surface.md](./contracts/graphql-number-pool-surface.md),
[contracts/number-pool-parameters.md](./contracts/number-pool-parameters.md).

### 7. Data model

[data-model.md](./data-model.md).

---

## Testing Strategy

- **Unit** (`tests/unit/pools/`, `tests/unit/graphql/`): `DivisionResolver.entries_in_force`
  (unknown entry dropped, all unknown → empty), `ScopeValidator` (every refusal row, normalisation,
  the `unique: true` and generic refusals), `DivisionReporter` (ordering by utilization, one division over the
  pool and within a range, empty division, branch split, unscoped single division, absolute counts),
  the fixed dataset (figures computed from the rows, each filter, the partial division filter,
  ordering, pagination, the refusals),
  `ScopedPoolDependencyChecker` with a `node_schema` lacking the field, and the SDL snapshot of
  every type of the dedicated surface plus `allocation_scope` on the three pool inputs.
- **Component**: the three dedicated queries on an unscoped pool (figures, ranges, no division,
  rows with provenance and range, a value no range holds and an excluded value absent from the
  rows and the figures, every filter, pagination, a pool holding two ranges with
  a null shorthand), on the fixed scoped dataset of set B (divisions, rows and filters agree, SC-010) and after D2
  (real divisions, the FR-025 two-division row), on an IP pool and an unknown id (refusals);
  `division_of` (relationship, attribute, enum, peer by id); the scoped fragment with one and two
  entries, relationship and attribute entries, both anchor orders; the FR-001/FR-007 two-branch
  case and the fork-window case on the hop; the unknown-entry drop; the enumeration including empty
  divisions and branch-only nodes, read from the default branch with the identifier fallback; the
  mutation refusals on the saving branch's schema (a field only `b1` has: accepted on `b1`,
  refused on the default branch); the dependency checker's refusals, the acceptance of a load
  touching an entry that does not apply on the branch, and the rename refusal on a
  user-created and a schema-created pool; the schema-created pool with a scope, its reconciliation
  from the default branch and its direct-edit refusal; the attribute-add size check per
  division; `InfrahubResourcePoolAllocated` count, offset and limit and `InfrahubResourcePoolUtilization`
  figures across the fragment move; a snapshot of the unscoped fragment text.
- **Functional**: the User Story 2 journey through GraphQL including fifty concurrent creates per
  division; a template-created node in a scoped division; the User Story 6 branch journey with the
  divisions query on both branches; the update-path deferral (scoped field changed and allocated in
  one update) with the lock per pool and division taken after the division is resolved; two
  divisions allocating in parallel and two writers in one division serialising.
- **Integration docker**: the FR-010 removal refusal through the schema-load API.
- **Measurement**: SC-006 as a query benchmark; SC-005 as a timed functional scenario excluded from
  the default run; figures and the chosen anchor order to `measurements.md`.
- **Regression**: every existing number-pool suite unchanged; the generic queries' responses
  unchanged for an unscoped pool; the lifecycle matrix rows that touch the scope (scoped-field move
  on a branch, schema divergence) added as two-branch tests.

---

## Risks

| Risk | Mitigation |
|---|---|
| The hop's fork-window leg makes the scoped free query slow at high occupancy | SC-006 measures; the stored key is the documented next lever |
| Deferring the pool applier on update reorders error surfacing for mixed payloads | Functional test pins the order; P2's intent resolver slots in after the deferral |
| This slice and part 1 share `NumberPoolParameters`, the picker's range walk, `EffectiveSpace` and the SDK generator | The fragment change is parameter-only and sits inside the range walk; `size`, `used` and the values listed on the dedicated surface come from `EffectiveSpace`, so allocation and the surface use one definition of the pool's space; the SDK models of both parts merge into `infrahub-develop` before the release merge (IFC-3356) |
| The generic queries and today's getter read the deprecated shorthand, null on a pool holding several ranges | The dedicated surface never reads the shorthand; the generic queries stay as they are (frozen), and their behaviour on a multi-range pool is P1's to fix |
| The record-side anchor runs the entry subqueries once per record at full occupancy | Both anchor orders rendered and profiled before one is kept |
| `NumberPoolGetAllocated` on the shared fragment changes the allocation lists on a deleting branch | Intended; changelog entry; component test |
| The fixed dataset is mistaken for final data | The contract states it; any `pool_id` returns the same pool; set E's test fails the slice until the real reads land |
| The generic queries drift while the dedicated surface is built | SC-009 schema diff in the contract change set; regression tests on their responses |

---

## Complexity Tracking

| Addition | Why needed | Simpler alternative rejected because |
|---|---|---|
| Shared `VISIBLE` Cypher constant | three consumers (value, peer, attribute) of a two-leg predicate | duplicating it three times inside one fragment makes the query unreadable, the opposite of the guideline's intent |
| `PoolsReferencingField` repository | one caller at introduction, the dependency checker, reached from eight constraint names (field changes, removals, renames) | inlining `NodeManager.query` plus a Python filter in the checker |
| Three pure modules in `pools/` | each has two callers (`scope.py`: mutation + schema load; `division_report.py`: the utilization resolver + the divisions resolver; the fixed dataset: the three resolvers) and none needs a database | keeping the logic in the pool applier, the mutation and the getter spreads the branch and schema subtleties across four files |
| A dedicated GraphQL module with three root fields | the frontend needs ranges, divisions, holders, provenance and absolute figures that the generic queries cannot carry for IP pools; `resource_id` is already required and ignored for number pools | `divisions` on `PoolUtilization` and a `division` argument on `InfrahubResourcePoolAllocated`: empty or ignored for IP pools, range rows stay IP types, no holder label |
| A temporary module holding a fixed dataset | the frontend builds every screen against plausible data before the reads exist | a single empty-key division (nothing to build a division view against); waiting for D2 (blocks the frontend) |

---

## Progress

- [x] Phase 0 — research complete (`research.md`, decisions D1–D12; D6, D7 and D11 revised on
      2026-10-06 for the dedicated surface)
- [x] Phase 1 — design complete (`data-model.md`, `contracts/`, `quickstart.md`)
- [x] Constitution Check — pre-design
- [x] Constitution Check — post-design (two gated items carried as tasks)
- [x] Phase 3 — dual-lens critique ([critiques/critique-20261002.md](./critiques/critique-20261002.md));
      5 must-address findings applied (E1, E13, E2, E4, P5), 13 recommendations applied, 3 questions
      resolved or escalated (see the critique's Resolution footer). The critique predates the
      dedicated surface; its findings on the utilization shape are superseded by D7, and its
      Erratum lists the outcomes the decisions of 2026-10-07 and 2026-10-08 reversed.
- [x] Phase 2 — `tasks.md` (phases follow change sets A, B, C, D1–D4, E, F)
- [x] Tickets — `tasks.md` regrouped by Jira ticket (IFC-3334, IFC-3346 to IFC-3354, IFC-3356, IFC-3329), one
      pull request per ticket; the surface keeps form A and User Story 7 is in scope (decisions of
      2026-10-07)
