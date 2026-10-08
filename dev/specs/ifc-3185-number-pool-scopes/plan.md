# Implementation Plan: Number pool allocation scopes

**Branch**: `number-pool-scopes-ifc-3185` | **Date**: 2026-10-08 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `dev/specs/ifc-3185-number-pool-scopes/spec.md`

## Summary

A number pool gains an optional, immutable allocation scope: an ordered list of elements, each stored as the schema element id and the readable name of one required attribute or one required cardinality-one relationship of the pool's kind, resolved against the schema of the default branch. With a scope, the pool allocates the lowest free number within the division of the node being written, the lock is keyed per pool and division, and three dedicated GraphQL queries report the divisions, their figures and the tracked numbers. The scope can be declared in the parameters of a number-pool attribute, and a schema change that would break a scoped element is refused.

The approach keeps the existing record model (one `IS_RESERVED` edge from the pool to the holder's attribute, on the global branch) and derives the division of each record from its holder node at read time, in the database. The scope is a `List` attribute on `CoreNumberPool`; the element validation, the division resolution and the division key live in one new package module, `backend/infrahub/pools/scope.py`, so that scoped behaviour is one branch in one place in the allocator and in the queries.

## Technical Context

**Language/Version**: Python 3.14 (backend), TypeScript 5.9 (generated frontend types only)

**Primary Dependencies**: FastAPI, graphene (GraphQL), Pydantic 2, Neo4j driver 6 (existing; no new dependency)

**Storage**: Neo4j. The scope is stored on the pool node as a `List` attribute; divisions are not stored, they are derived from the holder nodes.

**Testing**: pytest unit (`backend/tests/unit/pools/`), component with TestContainers (`backend/tests/component/core/resource_manager/`, `backend/tests/component/graphql/resource_manager/`), integration schema lifecycle (`backend/tests/integration/schema_lifecycle/`), live-stack measurements recorded in `quickstart.md`.

**Target Platform**: Infrahub server and task worker (Linux containers)

**Project Type**: Web service (backend); the frontend pool page is tracked in IFC-3363 and is out of scope.

**Performance Goals**: One allocation holds a bounded amount of memory whatever the number of tracked values (PRD FR-013). A scoped allocation runs one free-number query with the division filter in the database, no per-candidate round trip. The divisions list is one grouped query plus one batched peer lookup.

**Constraints**: No change to what a pool records. Unscoped pools render the same Cypher as today. The GraphQL contract of PR #10932 is kept, except `allocation_scope` becoming a list of `{id, name}` objects and division entries gaining `id`. The core schema change (new attribute on `CoreNumberPool`, new parameter on the number-pool attribute kind) regenerates protocols, the GraphQL schema, the frontend types and the schema reference docs.

**Scale/Scope**: A scope of one to three elements over pools holding up to tens of thousands of tracked values; the live-stack measurement of the quickstart reports the figures.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Gate | Status |
|-----------|------|--------|
| I. Schema-driven integrity | The scope attribute and the parameter are declared in the core schema definitions; generated files are regenerated, not edited; adding an optional attribute to a core node needs no graph migration | Pass |
| II. Branch-safe by default | The pool and its scope are branch-agnostic; a division is read on the branch that holds the value; the schema guard runs on every branch; merge behaviour is covered by the existing branch tests of number pools plus the two-branch scenarios of the quickstart | Pass |
| III. Type safety and explicit contracts | The GraphQL contract is written in `contracts/` before implementation; query results are frozen dataclasses; the scope and the division are frozen dataclasses | Pass |
| IV. Test discipline | Unit tests for the pure resolver and division key; component tests for queries, allocation and mutations; integration schema-lifecycle tests for the declared scope and the guard; the E2E pool test stays green; frontend E2E travels with IFC-3363 | Pass |
| V. Query performance | Division filtering and grouping run in Cypher with parameters; the holder and peer lookups are batched; `EXPLAIN` of the scoped free query is part of the quickstart measurement | Pass |
| VI. Security and input boundaries | Scope entries, division filters and pagination arguments are validated at the GraphQL boundary; element names and ids are bound as parameters, never interpolated | Pass |
| VII. Simplicity | One new module for the scope; no new kind, no new migration, no new dependency; the dedicated queries reuse the existing allocated-rows query and utilization getter | Pass |

Post-design re-check: no violation introduced. The one deviation from the simplest storage (storing the name beside the id) is justified in `research.md`.

## Project Structure

### Documentation (this feature)

```text
dev/specs/ifc-3185-number-pool-scopes/
├── spec.md
├── plan.md              # This file
├── research.md          # Phase 0: decisions and alternatives
├── data-model.md        # Phase 1: entities, stored shapes, validation rules
├── quickstart.md        # Phase 1: validation scenarios and measurements
├── contracts/
│   ├── pool-allocation-scope.md        # Scope input, storage and refusals on the pool mutations
│   ├── number-pool-parameters.md       # allocation_scope parameter of the number-pool attribute kind
│   └── graphql-number-pool-queries.md  # The three dedicated queries, with the changes to PR #10932
└── tasks.md             # Phase 2 (/speckit-tasks)
```

### Source Code (repository root)

```text
backend/infrahub/
├── core/
│   ├── schema/definitions/core/resource_pool.py      # allocation_scope attribute on CoreNumberPool
│   ├── schema/attribute_parameters.py                # NumberPoolParameters.allocation_scope
│   ├── schema/schema_branch.py                       # declared-scope validation against the default branch
│   ├── node/__init__.py                              # scoped allocation deferred until the node's fields are processed
│   ├── node/lock_utils.py                            # lock name per pool and division
│   ├── node/resource_manager/number_pool.py          # division passed to the free and used queries, lock per division
│   └── query/resource_manager.py                     # division fragment, divisions query, extended allocated-rows query
├── pools/
│   ├── scope.py                                      # NEW: scope elements, resolver, division, division key
│   ├── scope_guard.py                                # NEW: refuse schema changes that break a scoped element
│   ├── number.py                                     # utilization per division
│   ├── schema_number_pool_upserter.py                # create schema pools with their declared scope
│   └── schema_number_pool_synchronizer.py            # refresh stored element names after a rename
├── graphql/
│   ├── mutations/resource_manager.py                 # scope on create, immutability on update
│   ├── queries/number_pool.py                        # NEW: the three dedicated queries
│   ├── queries/resource_manager.py                   # descriptions of the generic pool queries
│   └── schema.py                                     # root fields registration
└── api/schema.py                                     # scope guard called on schema load and check

backend/tests/
├── unit/pools/test_scope.py                          # resolver rules, division values, division key
├── component/core/resource_manager/test_number_pool_scope.py        # scoped free, used, divisions, allocated queries
├── component/core/resource_manager/test_number_pool_scope_allocation.py  # allocation per division, locks, identifier
├── component/graphql/resource_manager/test_number_pool_scope_mutation.py # scope on create, refusals, immutability
├── component/graphql/resource_manager/test_number_pool_queries.py   # the three dedicated queries and their refusals
├── component/pools/test_schema_number_pool_scope.py  # declared scope on schema-created pools
└── integration/schema_lifecycle/test_number_pool_scope_guard.py     # guard, rename, branch load

docs/docs/resource-manager/
├── overview.mdx                                      # number pools: allocation scope paragraph
└── scoped-number-pools.mdx                           # NEW guide: scope a pool, read it, replace per-site pools
```

**Structure Decision**: Backend-only change in the existing layout. The scope logic goes in `backend/infrahub/pools/`, next to the schema pool synchronizer and the utilization getter, because that package already owns number-pool behaviour that is not a node method. The dedicated queries get their own module under `backend/infrahub/graphql/queries/` because the generic resource-pool module serves three pool kinds and the new queries serve one.

## Design overview

### Storage and resolution of the scope

- `CoreNumberPool` gains `allocation_scope`, kind `List`, optional, branch-agnostic like the pool. Each element is `{"id": "<schema element id>", "name": "<element name>"}`. The attribute is absent or an empty list on an unscoped pool.
- `backend/infrahub/pools/scope.py` holds `ScopeElement` (id, name), `AllocationScope` (ordered elements, `from_stored`, `to_stored`), `AllocationScopeResolver` (turns input entries into a scope against a schema branch, applying every refusal of spec FR-003 to FR-006) and `Division` (ordered values, `key` for lock names, `from_node` to read the division of an in-memory node, `from_entries` to read a division filter).
- Every resolution uses the schema branch of the default branch (`registry.default_branch`), whatever branch the request runs on. On the default branch itself, a schema load validates against the candidate schema, since the candidate becomes the default.
- Names are refreshed by `SchemaNumberPoolSynchronizer` on each schema update of the default branch, by looking each stored id up in the default schema.

### Allocation within a division

- `CoreNumberPool.get_resource` takes an optional division. The lock name is `<pool id>` for an unscoped pool and `<pool id>.<division key>` for a scoped one.
- The mutation-level lock uses the same name. `lock_utils.get_lock_names_on_object_mutation` is synchronous and cannot read the pool, so `lock_utils.apply_payload_for_lock_names` (asynchronous, with `db`) resolves each pooled attribute's pool through `Node.handle_pool` with `allocate_resources=False`, which already normalises `from_pool` to the pool id, and stores the division key next to the id on the attribute (`from_pool = {"id": ..., "division": ...}`) when the pool is scoped. The synchronous function then builds the per-division name from what the attribute carries.
- `NumberPoolGetFree`, `NumberPoolGetUsed` and `NumberPoolGetAllocated` take one optional `division` argument that defaults to None. When given, the shared `reserved_values_query()` fragment is extended with a division subquery that, for each tracked attribute, reads the holder node and its scope values on the branch holding the value, and keeps only the values whose scope tuple equals the parameter. With no division the fragment renders byte for byte the Cypher of today, which a unit test asserts. The in-progress range-aware allocator (IFC-3065) and the attach paths (IFC-3184) pass the same argument through, so the scoped behaviour stays one optional argument on each query and on `get_resource`.
- `Node._process_fields` keeps resolving each pooled attribute's pool inside the attribute loop (normalising `from_pool`) and moves the allocation itself, for every pooled attribute whether the pool is scoped or not, to a second pass that runs after all attributes and relationships are processed, so that the division is read from the node as it will be saved. The validation of a pooled attribute's value runs after that pass. `Node.from_graphql` applies every key of the payload first and allocates afterwards. One order for every pool; the full number-pool suites prove unscoped pools keep today's behaviour.

### Reading a scoped pool

- `NumberPoolGetDivisions` (new query) groups the tracked values by division tuple and returns, per division, the distinct values on any live branch, on the default branch, and on other branches only. The resolver turns relationship values into display labels with one batched node lookup.
- `NumberPoolGetAllocated` gains the filters `division` (subset of elements allowed), range bounds, branch name and provenance, and returns the provenance. The resolver resolves holders in batches per branch.
- The component tests of the divisions and allocations resolvers assert the number of database queries with `backend/tests/helpers/db_query_counter.py`, so that a per-row lookup cannot slip in.
- `NumberUtilizationGetter` takes an optional division and reuses the extended allocated-rows query; the per-range figures come from the pool's `CoreNumberPoolRange` nodes as today.
- `backend/infrahub/graphql/queries/number_pool.py` exposes `InfrahubNumberPoolUtilization`, `InfrahubNumberPoolDivisions` and `InfrahubNumberPoolAllocations` per `contracts/graphql-number-pool-queries.md`.

### Declared scope and schema guard

- `NumberPoolParameters.allocation_scope: list[str] | None`, `update: not_supported`, so a later change of the declaration is refused by the existing schema update validation.
- `SchemaBranch._validate_number_pool_parameters` resolves the declared names with `AllocationScopeResolver` against the default branch's schema and refuses the load with the element named.
- `SchemaNumberPoolUpserter.upsert_number_pool` creates the pool with the resolved scope.
- `backend/infrahub/pools/scope_guard.py` loads the scoped pools once, indexes them by element id, and refuses a candidate schema whose diff makes a scoped element optional, changes its cardinality, removes it, or sets `unique: true` on the tracked attribute. It is called from the schema load and schema check endpoints in `backend/infrahub/api/schema.py`, on every branch, before migrations are computed.

## Complexity Tracking

No constitution violation to justify. One choice deserves a note: the readable name is stored beside the id although it could be resolved on every read. `research.md` records why (every read of the pool node, including the generic GraphQL node query, must show the pair, and a refresh on schema load keeps it current).
