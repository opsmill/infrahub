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
allocation list with holder, provenance, range and division. The generic resource-pool queries are
frozen for number pools and gain a description note.

The work is sequenced so the frontend and the SDK are unblocked first: the schema attribute and the
parameters field land, the dedicated surface is published and frozen with real pool, range and
allocation data and a deterministic mock partition for the divisions of a scoped pool, then the
allocation and utilization seams, then the internals in parallel, then the mock is removed.

---

## Technical Context

**Language/Version**: Python 3.14

**Primary Dependencies**: FastAPI 0.131, graphene (pinned), Pydantic 2.12, Neo4j driver 6.2

**Storage**: Neo4j 2026.05, temporal and branch-aware property graph (`dev/knowledge/backend/database-schema.md`)

**Testing**: pytest 9.0. `tests/unit/` for the resolver, validator, reporter and the SDL snapshot;
`tests/component/` for queries, mutations, checkers and the three dedicated GraphQL queries;
`tests/functional/` for the lifecycle and branch suites; `tests/integration_docker/` for the
schema-load refusal; `tests/query_benchmark/` for SC-005 and SC-006.

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
| **V. Query Performance & Efficiency** | ⚠️ gated | The division hop adds one two-leg subquery per entry per record, bounded by pool occupancy. `EXPLAIN` on the scoped free query is recorded in `measurements.md`; SC-005 and SC-006 are benchmarks under `tests/query_benchmark/`. All parameters bound; only needed properties returned. The dedicated allocation query pushes `range_id`, the pool's space, `branch` and `provenance` into Cypher; the `division` filter is Python-side only while the mock partition exists. |
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
│   │   ├── __init__.py                          # handle_pool passes the division; from_graphql defers pools
│   │   ├── create.py                            # template allocation passes the division
│   │   └── resource_manager/number_pool.py      # get_resource(division=…), get_next, get_free, get_used
│   ├── migrations/schema/node_attribute_add.py  # backfill loads the scoped fields and passes each node's division
│   └── validators/
│       ├── __init__.py                          # map the new checker
│       ├── pool/scope.py                        # ScopedPoolDependencyChecker (new)
│       └── node/attribute.py                    # size check against the largest division
├── templates/node_applier.py                    # pool allocation deferred until relationships are applied
├── pools/
│   ├── effective_space.py                       # keeps the values of the pool's space and computes its size from the range set (new; replaced by P1's shared calculation)
│   ├── default_allocator.py                     # no longer allocates from the raw field dict
│   ├── scope.py                                 # ScopeEntry, DivisionKey, DivisionResolver, ScopeValidator (new)
│   ├── division_report.py                       # DivisionReporter (new, pure)
│   ├── division_mock.py                         # mock partition (new in B, deleted in E)
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
├── unit/pools/                                  # test_scope.py, test_division_report.py (new)
├── unit/graphql/                                # test_number_pool_surface_contract.py (SDL snapshot, new)
├── component/core/resource_manager/             # test_number_pool_scoped_query.py (new), fragment snapshot
├── component/graphql/resource_manager/number_pools/   # test_pool_scope.py (new), beside test_pool_create.py and test_pool_update.py
├── component/graphql/queries/                   # test_number_pool_surface.py (new), test_resource_pool.py (regression)
├── component/core/constraint_validators/        # test_scoped_pool_dependency.py (new), attribute-add case
├── component/pools/                             # test_schema_number_pool_scope.py (new)
├── functional/pools/                            # test_numberpool_scoped_allocation.py, test_numberpool_scoped_branch.py (new)
├── integration_docker/                          # test_number_pool_scope_schema_load.py (new)
├── query_benchmark/                             # test_number_pool_scoped_allocation.py (new, SC-006)
└── helpers/number_pool.py, helpers/schema/      # a non-unique pooled attribute on a kind with a required
                                                 # cardinality-one relationship and a required scalar attribute

tasks/backend.py                                 # SdkSchemaGenerator.number_pool_parameters_fields gains the List field
python_sdk/                                      # regenerated models (separate PR, pointer bump after)
schema/schema.graphql                            # regenerated
frontend/app/src/shared/api/graphql/generated/   # regenerated by pnpm codegen
docs/docs/schema/number-pool.mdx, docs/docs/resource-manager/allocate-number.mdx   # new section each
dev/knowledge/backend/database-schema.md         # the division read beside the reservation read
changelog/                                       # 6 towncrier fragments
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
| **B. Surface** | `graphql/queries/number_pool.py` with the three root fields and every type of the contract; `NumberPoolGetAllocated` projecting provenance with an optional bounds filter; real pool, range and allocation data; `pools/division_mock.py` for the divisions of a scoped pool; description notes on the generic queries and types; regenerate `schema/schema.graphql` and the frontend types; SDL snapshot test | A | frontend, SDK |
| **C. Seams** | `DivisionKey`; `get_resource(division=…)` threaded from the three write paths (ordinary create, template create with the applier's allocation deferred to `_process_fields_attributes`, update with `handle_pool` deferred in `from_graphql`) and from the attribute-add backfill; `NumberUtilizationGetter` reduced to a seam over `DivisionReporter` returning one division | A | D1, D2 |
| **D1. Scoped allocation** | `DivisionResolver`; `reserved_values_query(division=…, with_branch=…)`, the shared visibility constant, both anchor orders profiled, the scoped `get_free` / `get_used`; the unscoped snapshot test | C | F |
| **D2. Scoped reads** | `NumberPoolGetAllocated` on the fragment with branch and per-entry values; `NumberPoolDivisions`; the reporter's division figures over the pool and over one range; the three dedicated queries read the reporter instead of the mock; peer display labels with the identifier fallback; range rows of the division read; the `division` filter in Cypher | B, C, D1 (`DivisionResolver.entries_in_force`) | E |
| **D3. Scope write path** | `ScopeValidator`; the mutation validation against the mutation branch, invoked only when the scope changes; the schema-pool refusal; the upserter and synchronizer writes so a schema-declared scope reads back; `_validate_number_pool_parameters` through `ScopeValidator`; the attribute-add size check against the largest division | A (the size check also needs D2's `NumberPoolDivisions`) | — |
| **D4. Dependency checker** | `PoolsReferencingField`; `ScopedPoolDependencyChecker` registered for the three update constraints and the two removal migrations; integration-docker test | A | — |
| **E. Mock removal** | delete `pools/division_mock.py` and its call sites; the no-mock test on a scoped pool; the SDL snapshot unchanged | D2 | F |
| **F. Close** | SC-006 benchmark, SC-005 timed scenario, `measurements.md`; user docs; knowledge entry; changelog fragments; the form A versus form B review | D1, E | ship |

B, C, D3 and D4 run concurrently once A lands. D1 and D2 run concurrently once C lands, D2 taking
`entries_in_force` from D1's module as soon as it exists.

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

`handle_pool` resolves the entries against `registry.schema.get_schema_branch(self._branch.name)`
and the division from `self`, then calls `get_resource(..., division=key)`. `get_resource` passes it
to `get_next`, which passes it to `get_free`; `get_used` takes it for the same reason. An empty
`entries` tuple means unscoped on this branch and the fragment renders unchanged.

Three write paths reach allocation, and each reads the division after the scoped fields are set:

| Path | Today | Change |
|---|---|---|
| Create, ordinary | `Node._process_fields` applies relationships, then attributes, where `handle_pool` runs | none |
| Create through a template | `Node._process_fields` calls the template applier first; `templates/node_applier.py::NodeTemplateApplier._handle_pool_relationship` allocates through `pools/default_allocator.py::DefaultPoolAllocator` from the raw field dict, before any relationship exists and with no node | the applier records the pool id and marks the attribute pending (`TemplatePoolFields.pending` exists and the mandatory check tolerates it); `_process_fields_attributes` runs `handle_pool` for it after the relationships are applied |
| Update | `Node.from_graphql` applies the payload in dict order and `BaseAttribute.from_graphql` calls `handle_pool` inline | `from_graphql` applies every attribute with `process_pools=False`, then calls `handle_pool` for each attribute whose payload carried `from_pool` |

Invariant on the update path: `from_pool` is still assigned inline by `BaseAttribute.from_graphql`;
only the allocation is deferred. `core/node/lock_utils.py::get_lock_names_on_object_mutation` reads
`from_pool` to take the pool lock before the node is saved, and `Node.from_graphql` has exactly two
callers. The functional test pins both the deferral and the lock.

### 4. The dedicated surface (B, D2, E)

`graphql/queries/number_pool.py` holds the object types, the input, the enum and three resolvers,
one per root field, registered in `graphql/schema.py::InfrahubBaseQuery` as
`InfrahubNumberPoolUtilization`, `InfrahubNumberPoolDivisions` and `InfrahubNumberPoolAllocations`.
Each resolver loads the pool with `NodeManager.get_one` on the request's branch, refuses anything
that is not a `CoreNumberPool` with `NodeNotFoundError(node_type="CoreNumberPool")`, loads the
ranges branch-agnostically ordered by `start`, and resolves the scope in force with
`DivisionResolver.entries_in_force` (set B ships a minimal `entries_in_force` in `pools/scope.py`
if D1 has not landed; the function is pure).

| Root field | Reads | Builds |
|---|---|---|
| `InfrahubNumberPoolUtilization` | the rows of `NumberPoolGetAllocated` over the pool's space, kept to one division when `division` is given, the ranges from `NumberPoolRepository.get_ranges`, the attribute's `excluded_values`, `min_value` and `max_value` | `figures` for the pool and each range from the reporter, with `size` as the count of values of the pool's space; `allocation_scope` from the entries in force |
| `InfrahubNumberPoolDivisions` | the same rows, the pool's space as the measured space | one `NumberPoolDivision` per division holding at least one row, from the reporter (set B: from the mock partition), ordered by `utilization` descending then `display_label`; one division with no entry when the scope in force is empty |
| `InfrahubNumberPoolAllocations` | `NumberPoolGetAllocated` with the range set (or the one range of `range_id`), the attribute's `excluded_values` and limits, `branch` and `provenance` pushed into the query; `offset` and `limit` | rows with `holder` (one `NodeManager.get_many` per distinct row branch for display label and hfid), `range` from the pool's ranges, `division` from the reporter (set B: the mock partition) |

None of the three resolvers reads the deprecated `start_range` / `end_range` pair: the shorthand
mirror leaves it null on a pool holding several ranges, where today's getter and allocated query
stop working. A small pure helper (`pools/effective_space.py`, kept until P1's shared calculation
replaces it) keeps only the values of the pool's space and computes the size of that space from
the range set, the attribute's `excluded_values` and its `min_value` / `max_value`.

In set B the `division` filter is applied in Python after the query, on the mock partition, and
`count`, `offset` and `limit` apply to the filtered list. In D2 the filter moves into the scoped
records fragment with the writer's division replaced by the requested entries, so `count` is a
Cypher count again.

`NumberPoolGetAllocated` gains `ranges: Sequence[tuple[int, int]] | None` (None: no bounds
filter, every tracked value; a list: values of the pool's space inside any of the given bounds,
the pool's range set or the one range of `range_id`, not excluded and within the attribute's
limits), `branch: str | None` and
`provenance: PoolRecordProvenance | None` filters, and projects `coalesce(ir.provenance,
"allocated") AS provenance`. The generic `InfrahubResourcePoolAllocated` and `NumberUtilizationGetter`
keep today's shorthand filter and render the same text as today.

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
`divisions` is one entry with an empty key, and the pool's block equals today's figures. Regression
tests pin `InfrahubResourcePoolAllocated`'s count, offset and limit and the generic utilization
figures across the move onto the shared fragment.

The mock partition (`pools/division_mock.py`, set B) exposes `division_of_row(holder_id, entries)
-> DivisionKey` and `divisions(entries) -> tuple[DivisionKey, ...]`, assigning `mock-1..3` by
`int(UUID(holder_id)) % 3 + 1` and building entries from the real paths in force with the division's
name as value and label. The three resolvers call it only when the scope in force is not empty. Set
E deletes the module, and a component test on the scoped fixture asserts that no `value` or
`display_label` returned by the three queries begins with `mock-`.

The generic queries change in description strings only: `description=` on the two root `Field`s in
`graphql/queries/resource_manager.py` and `class Meta: description` on `PoolUtilization`,
`PoolAllocated` and `PoolAllocatedNode`, with the texts of the contract. SC-009 is checked by
diffing `schema/schema.graphql` for those types.

### 5. Validation (D3, D4)

- `ScopeValidator(schema_branch).validate(kind, attribute_name, scope)` → normalised entries or
  `ValidationError` naming the entry (rules in `data-model.md` §1; the required check covers
  relationships locally because `validate_schema_path` exempts `ip_namespace` on IP kinds). Called
  by the mutation (branch of the request) only when the normalised submitted scope differs from the
  stored one, and by `_validate_number_pool_parameters` (branch being loaded).
- `ScopedPoolDependencyChecker.check(request)` → for the changed field, `PoolsReferencingField.get`
  and a `ValueError` naming each pool that names the field. Registered in `CONSTRAINT_VALIDATOR_MAP`
  for the five names in `contracts/number-pool-parameters.md`;
  `SchemaUpdateValidationResult.add_validator_for_migration` already turns the two removal
  migrations into constraints, so `core/models.py` is untouched. The map holds one checker class
  per name, so the three update names that already have a checker get a small
  `CompositeConstraintChecker` (`core/validators/composite.py`) that runs both and concatenates
  their results; the two removal names, unmapped today, map to the new checker directly. The checker
  reads the kind and field from `request.schema_path` only, never from `request.node_schema`, which
  is the candidate schema the removed field is already gone from.
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
  unchanged scope accepted), `DivisionReporter` (ordering by utilization, one division over the
  pool and within a range, empty division, branch split, unscoped single division, absolute counts),
  the mock partition (stable, three divisions, entries from the paths in force),
  `ScopedPoolDependencyChecker` with a `node_schema` lacking the field, and the SDL snapshot of
  every type of the dedicated surface plus `allocation_scope` on the three pool inputs.
- **Component**: the three dedicated queries on an unscoped pool (figures, ranges, one division,
  rows with provenance and `range`, no row for a value no range holds nor for an excluded value,
  every filter, pagination, a pool holding two ranges with a null shorthand), on a scoped pool at contract time (mock partition agreement, SC-010) and after D2
  (real divisions, the FR-025 two-division row), on an IP pool and an unknown id (refusals);
  `division_of` (relationship, attribute, enum, peer by id); the scoped fragment with one and two
  entries, relationship and attribute entries, both anchor orders; the FR-001/FR-007 two-branch
  case and the fork-window case on the hop; the unknown-entry drop; the enumeration including empty
  divisions and branch-only nodes, read from the default branch with the identifier fallback; the
  mutation refusals and the unchanged-scope round trip from a branch that lacks the entry; the
  dependency checker's three refusals and the never-existed acceptance; the schema-created pool
  with a scope, its reconciliation and its direct-edit refusal; the attribute-add size check per
  division; `InfrahubResourcePoolAllocated` count, offset and limit and `InfrahubResourcePoolUtilization`
  figures across the fragment move; a snapshot of the unscoped fragment text.
- **Functional**: the User Story 2 journey through GraphQL including fifty concurrent creates per
  division; a template-created node in a scoped division; the User Story 6 branch journey with the
  divisions query on both branches; the update-path deferral (scoped field changed and allocated in
  one update) with the pool lock still taken.
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
| Deferring `handle_pool` on update reorders error surfacing for mixed payloads | Functional test pins the order; P2's intent resolver slots in after the deferral |
| P1's remaining work and this slice touch `NumberPoolParameters`, `get_next`, the size calculation and the SDK generator | Fragment change is parameter-only; whichever lands second rebases one hunk; each slice opens its own SDK regeneration PR; the landing order is the P1 owner's call (open question in the critique); the dedicated surface's `size`, `used` and the values of the pool's space it lists are computed by a small helper with the definition P1's shared calculation will carry, so the switch is an implementation swap, not a contract change |
| The generic queries and today's getter read the deprecated shorthand, null on a pool holding several ranges | The dedicated surface never reads the shorthand; the generic queries stay as they are (frozen), and their behaviour on a multi-range pool is P1's to fix |
| The record-side anchor runs the entry subqueries once per record at full occupancy | Both anchor orders rendered and profiled before one is kept |
| `NumberPoolGetAllocated` on the shared fragment changes the allocation lists on a deleting branch | Intended; changelog entry; component test |
| The mock partition is mistaken for final data on a scoped pool | The contract states it; the division labels read `mock-N`; set E's no-mock test fails the slice until the real reads land |
| The generic queries drift while the dedicated surface is built | SC-009 schema diff in the contract change set; regression tests on their responses |
| Form A is replaced by form B at the final review | Only the three root field names would change; every type is kept; the frontend is told at contract time |

---

## Complexity Tracking

| Addition | Why needed | Simpler alternative rejected because |
|---|---|---|
| Shared `VISIBLE` Cypher constant | three consumers (value, peer, attribute) of a two-leg predicate | duplicating it three times inside one fragment makes the query unreadable, the opposite of the guideline's intent |
| `PoolsReferencingField` repository | two callers at introduction (the dependency checker, the attribute-add checker's scoped branch) and the rename path later | inlining `NodeManager.query` plus a Python filter in each checker |
| Three pure modules in `pools/` | each has two callers (mutation + schema load; allocation + utilization; utilization + the attribute-add check) and none needs a database | keeping the logic in `handle_pool`, the mutation and the getter spreads the branch and schema subtleties across four files |
| A dedicated GraphQL module with three root fields | the frontend needs ranges, divisions, holders, provenance and absolute figures that the generic queries cannot carry for IP pools; `resource_id` is already required and ignored for number pools | `divisions` on `PoolUtilization` and a `division` argument on `InfrahubResourcePoolAllocated`: empty or ignored for IP pools, range rows stay IP types, no holder label |
| A temporary mock module | the frontend builds the division view against plausible data before the division reads exist | a single empty-key division (nothing to build a division view against); waiting for D2 (blocks the frontend) |

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
      dedicated surface; its findings on the utilization shape are superseded by D7.
- [x] Phase 2 — `tasks.md` (phases follow change sets A, B, C, D1–D4, E, F)
