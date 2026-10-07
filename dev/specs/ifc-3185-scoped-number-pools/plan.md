# Implementation Plan: Scoped number pools — one pool serves every scope

**Branch**: `feature-number-pools-1.12` | **Date**: 2026-10-02 | **Spec**: [spec.md](./spec.md)

**Epic**: [IFC-3185](https://opsmill.atlassian.net/browse/IFC-3185)

**Input**: Feature specification from `dev/specs/ifc-3185-scoped-number-pools/spec.md`, derived
from `SCOPED-POOLS-PRD.md`. Research and decisions in [research.md](./research.md).

---

## Summary

A number pool gains `allocation_scope`, a list of fields of its kind. With a scope set, allocation
returns the lowest free number within the division the object being written belongs to, and
utilization reports the fullest division as the headline with every division listed. The scope
decides which number comes next and nothing else: it refuses nothing and stores nothing. A record's
division is derived at read time from its owning object's fields, as a union over every live
branch, inside the records fragment the used and free reads already share. A pool with no scope
issues the query it issues today.

The work is sequenced so the frontend and the SDK are unblocked first: the schema attribute and the
parameters field land, the GraphQL contract is published and frozen with an honest placeholder,
then the allocation and utilization seams, then the internals in parallel.

---

## Technical Context

**Language/Version**: Python 3.14

**Primary Dependencies**: FastAPI 0.131, graphene (pinned), Pydantic 2.12, Neo4j driver 6.2

**Storage**: Neo4j 2026.05, temporal and branch-aware property graph (`dev/knowledge/backend/database-schema.md`)

**Testing**: pytest 9.0. `tests/unit/` for the resolver, validator and reporter; `tests/component/`
for queries, mutations and checkers; `tests/functional/` for the lifecycle and branch suites;
`tests/integration_docker/` for the schema-load refusal; `tests/query_benchmark/` for SC-005 and
SC-006.

**Target Platform**: Linux server (containerised backend)

**Project Type**: Backend-only change to an existing web service. No frontend work; the contract
must carry everything the pool form and a per-division view need.

**Performance Goals**: no numeric gate. SC-005 (throughput of one scoped pool against N per-site
pools under concurrent allocation) and SC-006 (latency on a full 4094-number pool, three entries,
five branches) are measured and reported.

**Constraints**:

- The unscoped records fragment renders byte-for-byte as today (FR-005, SC-003).
- Liveness stays one-sided: a number may read as taken that is free on some branch, never free when
  taken on any (FR-007).
- The scope is branch-agnostic; a branch that cannot resolve an entry drops it (FR-008, FR-021).
- The contract published in User Story 1 does not change afterwards (FR-018).
- No graph migration, no new kind, no new edge, no new record property.

**Scale/Scope**: 1 new core attribute, 1 new parameters field, 1 records-fragment extension, 1
new enumeration query, 1 query moved onto the shared fragment, 3 new pure modules, 1 new checker, 1
new repository, 3 GraphQL types and 1 field, 0 migrations, 0 dependencies.

---

## Constitution Check

*Gate evaluated before Phase 0 and re-evaluated after Phase 1 design. Constitution v1.0.0.*

| Principle | Verdict | Notes |
|---|---|---|
| **I. Schema-Driven Integrity** | ✅ passes | One new optional attribute on a core kind applied by the core schema update; no data migration. Generated files regenerated with `uv run invoke backend.generate`, `schema.generate-graphqlschema`, `schema.generate-jsonschema`, `docs.generate` and `pnpm codegen`. |
| **II. Branch-Safe by Default** | ⚠️ gated, this is the principle under test | The cross-branch read is the design: records are `-global-`, objects are branch-aware, the division is a union over live branches with the visibility rule the value read already uses. Merge needs no new validator (the scope does not merge; the values it reads do). Every branch case in the spec's edge list gets a two-branch component test. |
| **III. Type Safety & Explicit Contracts** | ✅ passes | Three contracts agreed before implementation (`contracts/`). Query results come back as frozen dataclasses; the division key is a frozen dataclass; GraphQL types are explicit. |
| **IV. Test Discipline** | ✅ passes | Unit for `entries_in_force`, `ScopeValidator` and `DivisionReporter`; component for `division_of`, every query, mutation and checker; functional for the journeys and the concurrent case; one integration-docker test for the schema-load refusal; no E2E because no screen ships. The shared snow fixture's pooled attribute is `unique`, which the global taken-values scan masks, so scoped tests use a non-unique pooled attribute on a kind with a required cardinality-one relationship and a required scalar attribute (extending `tests/helpers/number_pool.py` with such a schema). |
| **V. Query Performance & Efficiency** | ⚠️ gated | The division hop adds one two-leg subquery per entry per record, bounded by pool occupancy. `EXPLAIN` on the scoped free query is recorded in `measurements.md`; SC-005 and SC-006 are benchmarks under `tests/query_benchmark/`. All parameters bound; only needed properties returned. |
| **VI. Security & Input Boundaries** | ✅ passes | Scope entries validated at the mutation and the schema-load boundary before any query uses them; entry names are bound as parameters, never interpolated (the relationship identifier and attribute name are looked up from the schema and bound). Errors name the entry or the pool, never internals. |
| **VII. Simplicity** | ✅ passes with one justification | Derived scope: no hook, no migration, no batch, no new kind. One shared Cypher visibility constant is extracted because it reaches three consumers (the bar the query guideline sets). The repository and the three pure modules each serve two callers at introduction (see Complexity Tracking). |

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
│   ├── graphql-pool-scope.md
│   ├── graphql-pool-utilization.md
│   └── number-pool-parameters.md
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
│   │                                            # constant, NumberPoolGetAllocated on the fragment,
│   │                                            # NumberPoolDivisions (new)
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
│   ├── default_allocator.py                     # no longer allocates from the raw field dict
│   ├── scope.py                                 # ScopeEntry, DivisionKey, DivisionResolver, ScopeValidator (new)
│   ├── division_report.py                       # DivisionReporter (new, pure)
│   ├── referencing.py                           # PoolsReferencingField (new repository)
│   ├── number.py                                # NumberUtilizationGetter → seam over DivisionReporter
│   ├── schema_number_pool_upserter.py           # writes allocation_scope at creation
│   └── schema_number_pool_synchronizer.py       # copies allocation_scope from the default branch
└── graphql/
    ├── queries/resource_manager.py              # PoolDivisionEntry, PoolDivisionUtilization, divisions
    └── mutations/resource_manager.py            # ScopeValidator on create/update/upsert; schema-pool refusal

backend/tests/
├── unit/pools/                                  # test_scope.py, test_division_report.py (new)
├── component/core/resource_manager/             # test_number_pool_scoped_query.py (new), fragment snapshot
├── component/graphql/resource_manager/          # test_number_pool_scope_mutation.py (new)
├── component/graphql/queries/                   # test_resource_pool_divisions.py (new)
├── component/core/constraint_validators/        # test_scoped_pool_dependency.py (new), attribute-add case
├── component/pools/                             # test_schema_number_pool_scope.py (new)
├── functional/pools/                            # test_numberpool_scoped_allocation.py, test_numberpool_scoped_branch.py (new)
├── integration_docker/                          # test_number_pool_scope_schema_load.py (new)
├── query_benchmark/                             # test_number_pool_scoped_allocation.py (new, SC-006)
└── helpers/number_pool.py, helpers/schema/      # a non-unique pooled attribute on a kind with a required
                                                 # cardinality-one relationship and a required scalar attribute

tasks/backend.py                                 # SdkSchemaGenerator.number_pool_parameters_fields gains the List field
python_sdk/                                      # regenerated models (separate PR, pointer bump after)
frontend/app/src/shared/api/                     # regenerated types only
docs/docs/schema/number-pool.mdx, docs/docs/resource-manager/allocate-number.mdx   # new section each
dev/knowledge/backend/database-schema.md         # the division read beside the reservation read
changelog/                                       # 5 towncrier fragments
```

**Structure decision**: the feature slots into the existing layout. Pure logic goes in
`backend/infrahub/pools/`, which already owns pool arithmetic and is imported from `core/` and
`graphql/`. Cypher stays in `core/query/resource_manager.py`, where every pool query lives. The
checker goes under `core/validators/` beside its peers. No new top-level package.

---

## Phase 1 — Design

### 1. Delivery order and the four change sets

| Set | Content | Depends on | Unblocks |
|---|---|---|---|
| **A. Schema** | `allocation_scope` on the pool kind; `NumberPoolParameters.allocation_scope`; the hand-maintained SDK generator entry in `tasks/backend.py::SdkSchemaGenerator.number_pool_parameters_fields`; regenerate protocols, GraphQL schema, OpenAPI, SDK models, docs snippet | — | everything |
| **B. Contract** | Mutation validation through `ScopeValidator` against the mutation branch, invoked only when the scope changes; the schema-pool refusal; the upserter and synchronizer writes so a schema-declared scope reads back; `divisions` on `PoolUtilization` with the single-row placeholder and an explicit empty list on IP pools; regenerate; frontend `pnpm codegen` | A | frontend, SDK |
| **C. Seams** | `DivisionResolver`; `get_resource(division=…)` threaded from the three write paths (ordinary create, template create with the applier's allocation deferred to `_process_fields_attributes`, update with `handle_pool` deferred in `from_graphql`) and from the attribute-add backfill; `NumberUtilizationGetter` reduced to a seam over `DivisionReporter` returning one division | A | D1, D2 |
| **D1. Scoped allocation** | `reserved_values_query(division=…, with_branch=…)`, the shared visibility constant, both anchor orders profiled, the scoped `get_free` / `get_used`; the unscoped snapshot test | C | E |
| **D2. Scoped utilization** | `NumberPoolGetAllocated` on the fragment with branch and per-entry values; `NumberPoolDivisions`; the real `divisions` resolver; peer display labels with the identifier fallback; per-range rows as the fullest division within the range | B, C | E |
| **D3. Schema-declared scope** | `_validate_number_pool_parameters` through `ScopeValidator`; the attribute-add size check against the largest division | A | — |
| **D4. Dependency checker** | `PoolsReferencingField`; `ScopedPoolDependencyChecker` registered for the three update constraints and the two removal migrations; integration-docker test | A | — |
| **E. Close** | SC-006 benchmark, SC-005 timed scenario, `measurements.md`; user docs; knowledge entry; changelog fragments | D1, D2 | ship |

B, C and D3/D4 run concurrently once A lands. D1 and D2 run concurrently once C lands.

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
value vertex, walk to the objects that hold it, then to their reserved attributes — and touches only
the records in the division. Both are rendered behind the same parameter and profiled at the
SC-006 shape and at a hub shape; the kept order and the figures go to `measurements.md`.

### 3. The writer's division (C)

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

### 4. Utilization (C, D2)

`NumberUtilizationGetter.load_data` runs `NumberPoolGetAllocated` (now on the shared fragment with
`with_branch=True`, keeping owner id, branch, value and record identifier per row because
`InfrahubResourcePoolAllocated` shares the class, plus per-entry value lists per row when scoped)
and `NumberPoolDivisions`, and hands both to
`DivisionReporter.report(rows, divisions, effective_size, entries)`. The reporter returns:

```python
@dataclass(frozen=True)
class DivisionFigures:
    key: DivisionKey
    used_default_branch: frozenset[int]
    used_branches: frozenset[int]

@dataclass(frozen=True)
class DivisionReport:
    divisions: tuple[DivisionFigures, ...]   # every enumerated division, fullest first
    fullest: DivisionFigures
```

The resolver computes the headline and the branch split from `fullest`, each per-range row from
the division holding the most of that range's values (the reporter exposes
`fullest_within(start, end)`), and `divisions` from the tuple. Peer display labels come from one
`NodeManager.get_many(..., branch_agnostic=True)` over the distinct peer ids of relationship
entries; a peer that still cannot be read is labelled by its identifier, and an object holding
nothing for an entry carries an empty value, so the non-null fields never void the list. Unscoped:
`divisions` is one entry with an empty key. The IP pool branch of `PoolUtilization.resolve` sets
`divisions` to `[]` explicitly. Regression tests pin `InfrahubResourcePoolAllocated`'s count, offset
and limit and the headline branch split across the move onto the shared fragment.

### 5. Validation (B, D3, D4)

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
  their results; the two removal names, unmapped today, map to the new checker directly. The checker reads the kind and field
  from `request.schema_path` only, never from `request.node_schema`, which is the candidate schema
  the removed field is already gone from.
- `NodeAttributeAddChecker`: for a scoped declaration, size against the largest division's object
  count from `NumberPoolDivisions`.

### 6. Interface contracts

[contracts/graphql-pool-scope.md](./contracts/graphql-pool-scope.md),
[contracts/graphql-pool-utilization.md](./contracts/graphql-pool-utilization.md),
[contracts/number-pool-parameters.md](./contracts/number-pool-parameters.md).

### 7. Data model

[data-model.md](./data-model.md).

---

## Testing Strategy

- **Unit** (`tests/unit/pools/`): `DivisionResolver.entries_in_force` (unknown entry dropped, all
  unknown → empty), `ScopeValidator` (every refusal row, normalisation, unchanged scope accepted),
  `DivisionReporter` (fullest selection, fullest within a range, empty division, branch split,
  unscoped single division), `ScopedPoolDependencyChecker` with a `node_schema` lacking the field.
- **Component**: `division_of` (relationship, attribute, enum, peer by id); the scoped fragment
  with one and two entries, relationship and attribute entries, both anchor orders; the
  FR-001/FR-007 two-branch case and the fork-window case on the hop; the unknown-entry drop; the
  enumeration including empty divisions and branch-only objects, read from the default branch with
  the identifier fallback; the mutation refusals and the unchanged-scope round trip from a branch
  that lacks the entry; the dependency checker's three refusals and the never-existed acceptance; the
  schema-created pool with a scope, its reconciliation and its direct-edit refusal; the attribute-add
  size check per division; `divisions` on an IP pool; `InfrahubResourcePoolAllocated` count, offset
  and limit across the fragment move; a snapshot of the unscoped fragment text.
- **Functional**: the User Story 2 journey through GraphQL including fifty concurrent creates per
  division; a template-created object in a scoped division; the User Story 6 branch journey; the
  update-path deferral (scoped field changed and allocated in one update) with the pool lock still
  taken.
- **Integration docker**: the FR-010 removal refusal through the schema-load API.
- **Measurement**: SC-006 as a query benchmark; SC-005 as a timed functional scenario excluded from
  the default run; figures and the chosen anchor order to `measurements.md`.
- **Regression**: every existing number-pool suite unchanged; the lifecycle matrix rows that touch
  the scope (scoped-field move on a branch, schema divergence) added as two-branch tests.

---

## Risks

| Risk | Mitigation |
|---|---|
| The hop's fork-window leg makes the scoped free query slow at high occupancy | SC-006 measures; the stored key is the documented next lever |
| Deferring `handle_pool` on update reorders error surfacing for mixed payloads | Functional test pins the order; P2's intent resolver slots in after the deferral |
| P1's remaining work and this slice touch `NumberPoolParameters`, `get_next`, the size calculation and the SDK generator | Fragment change is parameter-only; whichever lands second rebases one hunk; each slice opens its own SDK regeneration PR; the landing order is the P1 owner's call (open question in the critique) |
| The record-side anchor runs the entry subqueries once per record at full occupancy | Both anchor orders rendered and profiled before one is kept |
| `NumberPoolGetAllocated` on the shared fragment changes the in-use list on a deleting branch | Intended; changelog entry; component test |
| The placeholder `divisions` row is mistaken for final behaviour on a scoped pool | Contract says so; FR-019 task removes it before ship; frontend told not to assume one row |

---

## Complexity Tracking

| Addition | Why needed | Simpler alternative rejected because |
|---|---|---|
| Shared `VISIBLE` Cypher constant | three consumers (value, peer, attribute) of a two-leg predicate | duplicating it three times inside one fragment makes the query unreadable, the opposite of the guideline's intent |
| `PoolsReferencingField` repository | two callers at introduction (the dependency checker, the attribute-add checker's scoped branch) and the rename path later | inlining `NodeManager.query` plus a Python filter in each checker |
| Three pure modules in `pools/` | each has two callers (mutation + schema load; allocation + utilization; utilization + the attribute-add check) and none needs a database | keeping the logic in `handle_pool`, the mutation and the getter spreads the branch and schema subtleties across four files |

---

## Progress

- [x] Phase 0 — research complete (`research.md`, decisions D1–D12)
- [x] Phase 1 — design complete (`data-model.md`, `contracts/`, `quickstart.md`)
- [x] Constitution Check — pre-design
- [x] Constitution Check — post-design (two gated items carried as tasks)
- [x] Phase 3 — dual-lens critique ([critiques/critique-20261002.md](./critiques/critique-20261002.md));
      5 must-address findings applied (E1, E13, E2, E4, P5), 13 recommendations applied, 3 questions
      resolved or escalated (see the critique's Resolution footer)
- [x] Phase 2 — `tasks.md` (69 tasks, phases follow change sets A, B, C, D1–D4, E)
