# Implementation Plan: Number pool allocation scopes

**Branch**: `pmi-number-pool-scopes-spec-ifc-3185` (from `feature-number-pools-1.12`) | **Date**: 2026-10-08 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `dev/specs/ifc-3185-number-pool-scopes/spec.md`

## Summary

A number pool's existing `allocation_scope` attribute changes from a list of element names to an immutable, ordered list of `{id, name}` objects, each referencing one required attribute or one required cardinality-one relationship of the pool's kind, resolved against the schema of the default branch. With a scope, the pool allocates the lowest free number within the division of the node being written, read on the branch of the request; the lock is keyed per pool and division; and the three dedicated GraphQL queries of PR #10932, served today from a fixed dataset, read the divisions, their figures and the tracked numbers from the database. The scope declared in the parameters of a number-pool attribute is compared to the stored scope by id on every schema load, and a schema change that would break a scoped element is refused by a constraint checker on every branch.

The approach keeps the existing record model (one `IS_RESERVED` edge from the pool to the holder's attribute, on the global branch) and derives the division of each record from its holder node at read time, in the database. The element validation, the division resolution and the division key live in one new package module, `backend/infrahub/pools/scope.py`, so that scoped behaviour is one branch in one place in the allocation chain and in the queries. Every other change is an extension of a module that exists on `feature-number-pools-1.12`.

## Technical Context

**Language/Version**: Python 3.14 (backend), TypeScript 5.9 (generated frontend types only)

**Primary Dependencies**: FastAPI, graphene (GraphQL), Pydantic 2, Neo4j driver 6 (existing; no new dependency)

**Storage**: Neo4j. The scope is stored on the pool node in the existing `allocation_scope` `List` attribute; divisions are not stored, they are derived from the holder nodes.

**Testing**: pytest unit (`backend/tests/unit/pools/`, `backend/tests/unit/core/validators/`, `backend/tests/unit/graphql/`), component with TestContainers (`backend/tests/component/core/resource_manager/`, `backend/tests/component/graphql/resource_manager/number_pools/`, `backend/tests/component/graphql/queries/`, `backend/tests/component/core/constraint_validators/`, `backend/tests/component/pools/`), functional through GraphQL (`backend/tests/functional/pools/`), integration schema lifecycle (`backend/tests/integration/schema_lifecycle/`), live-stack measurements recorded in `quickstart.md`.

**Target Platform**: Infrahub server and task worker (Linux containers)

**Project Type**: Web service (backend); the frontend pool page is tracked in IFC-3363 and is out of scope.

**Performance Goals**: One allocation holds a bounded amount of memory whatever the number of tracked values (PRD FR-013). A scoped allocation runs one free-number query with the division filter in the database, no per-candidate round trip. The divisions list is one grouped query plus one batched peer lookup.

**Constraints**: No change to what a pool records. Unscoped pools render the same Cypher as today. The GraphQL contract of PR #10932 is kept, except `allocation_scope` becoming a list of `{id, name}` objects, division entries gaining `id`, and the wording about a scope "in force on the request's branch" going away. The core schema does not change shape (the attribute and the parameter exist); their descriptions and the parameter's update marker change, which regenerates `schema/schema.graphql`, `schema/openapi.json`, the frontend types, `backend/infrahub/core/schema/generated/` and the schema reference docs.

**Scale/Scope**: A scope of one to three elements over pools holding up to tens of thousands of tracked values; the live-stack measurement of the quickstart reports the figures.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Gate | Status |
|-----------|------|--------|
| I. Schema-driven integrity | The attribute and the parameter already exist in the core schema definitions; generated files are regenerated, not edited; no graph migration, because no released version stores a scope | Pass |
| II. Branch-safe by default | The pool and its scope are branch-agnostic; a division is read on the branch of the request; the schema checker runs on every branch; the known limitation of decision 7 is asserted by a test and documented | Pass |
| III. Type safety and explicit contracts | The GraphQL contract is written in `contracts/` before implementation; query results are frozen dataclasses; the scope and the division are frozen dataclasses | Pass |
| IV. Test discipline | Unit tests for the pure resolver, the division key and the checker's decision table; component tests for queries, allocation, mutations and the checker; functional tests for the two-branch cases; integration schema-lifecycle tests for the declared scope; the E2E pool test stays green; frontend E2E travels with IFC-3363 | Pass |
| V. Query performance | Division filtering and grouping run in Cypher with parameters; the holder and peer lookups are batched; `EXPLAIN` of the scoped free query is part of the quickstart measurement | Pass |
| VI. Security and input boundaries | Scope entries, division filters and pagination arguments are validated at the GraphQL boundary; element names and ids are bound as parameters, never interpolated | Pass |
| VII. Simplicity | One new module for the scope, one new checker; no new kind, no new migration, no new dependency; the dedicated queries reuse the existing allocated-rows query and utilization getter | Pass |

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
├── alignment-check.md   # Phase 5: the spec against the sources
└── tasks.md             # Phase 2 (/speckit-tasks)
```

### Source Code (repository root)

Files marked `existing` are on `feature-number-pools-1.12`; files marked `PR #10932` land with the rebased mock pull request; `NEW` files are created here.

```text
backend/infrahub/
├── core/
│   ├── schema/definitions/core/resource_pool.py      # existing: allocation_scope attribute description
│   ├── schema/attribute_parameters.py                # existing: NumberPoolParameters.allocation_scope update marker
│   ├── schema/definitions/internal.py                # existing: relationship name update support
│   ├── schema/schema_branch.py                       # existing: _validate_number_pool_parameters
│   ├── node/__init__.py                              # existing: _process_fields_attributes, from_graphql
│   ├── node/lock_utils.py                            # existing: apply_payload_for_lock_names, get_lock_names_on_object_mutation
│   ├── node/resource_manager/number_pool.py          # existing: CoreNumberPool.get_resource
│   ├── attribute.py                                  # existing: BaseAttribute.from_graphql
│   ├── query/resource_manager.py                     # existing: reserved_values_query, NumberPoolGetFree, NumberPoolGetUsed, NumberPoolGetAllocated
│   └── validators/
│       ├── __init__.py                               # existing: CONSTRAINT_VALIDATOR_MAP
│       ├── enum.py                                   # existing: ConstraintIdentifier
│       └── pool/scope.py                             # NEW: NumberPoolScopeChecker
├── dependencies/builder/constraint/schema/
│   ├── aggregated.py                                 # existing: checker list
│   └── number_pool_scope.py                          # NEW: dependency builder of the checker
├── pools/
│   ├── scope.py                                      # NEW: ScopeElement, AllocationScope, AllocationScopeResolver, Division
│   ├── attribute_pool_applier.py                     # existing: AttributePoolApplier (division passed to the allocator)
│   ├── number_pool_attribute_allocator.py            # existing: NumberPoolAttributeAllocator.allocate
│   ├── number_pool_number_picker.py                  # existing: NumberPoolNumberPicker.next_number
│   ├── number_pool_repository.py                     # existing: NumberPoolRepository.get_free, get_used, get_divisions
│   ├── number.py                                     # existing: NumberUtilizationGetter
│   ├── schema_number_pool_upserter.py                # existing: upsert_number_pool
│   ├── schema_number_pool_synchronizer.py            # existing: run, _update_pool_from_schema
│   └── number_pool_mock.py                           # PR #10932: fixed dataset, deleted when the resolvers read the database
├── graphql/
│   ├── mutations/resource_manager/number_pools/
│   │   ├── pool.py                                   # existing: InfrahubNumberPoolMutation
│   │   └── common.py                                 # existing: refusal constants
│   ├── queries/number_pool.py                        # PR #10932: the three dedicated queries
│   ├── queries/resource_manager.py                   # existing: generic pool queries (descriptions from PR #10932)
│   └── schema.py                                     # PR #10932: root fields registration
└── api/schema.py                                     # existing, unchanged: load and check endpoints run the checkers

backend/tests/
├── unit/pools/test_scope.py                          # NEW: resolver rules, division values, division key
├── unit/core/validators/test_number_pool_scope_checker.py   # NEW: the checker's decision table
├── unit/core/test_resource_manager_query.py          # NEW: unscoped rendering of the shared fragment
├── helpers/number_pool.py                            # PR #10932: SCOPED_POOL_SCHEMA, extended here
├── component/core/resource_manager/conftest.py       # existing: scoped pool fixture added
├── component/core/resource_manager/test_number_pool_scope.py        # NEW: scoped free, used, divisions, allocated queries
├── component/core/resource_manager/test_number_pool_scope_allocation.py  # NEW: allocation per division, locks, identifier
├── component/graphql/resource_manager/number_pools/test_pool_allocation_scope.py  # existing: rewritten to the {id, name} shape and the refusals
├── component/graphql/queries/test_number_pool_surface.py    # PR #10932: real-data cases replace the fixed dataset
├── component/core/constraint_validators/test_number_pool_scope.py   # NEW: the checker against a database
├── component/pools/test_schema_number_pool_scope.py  # NEW: declared scope on schema-created pools
├── functional/pools/test_numberpool_scoped_branch.py # NEW: two-branch scenarios, the known limitation
└── integration/schema_lifecycle/test_number_pool_scope_schema.py    # NEW: declared scope, rename, refusals through the API

docs/docs/resource-manager/
├── overview.mdx                                      # existing: number pools, allocation scope paragraph
├── allocate-number.mdx                               # existing: "Scope a pool" section
└── scoped-number-pools.mdx                           # NEW guide: read a scoped pool, replace per-site pools
```

**Structure Decision**: Backend-only change in the existing layout. The scope logic goes in `backend/infrahub/pools/`, next to the applier, the picker and the repository, because that package already owns number-pool behaviour that is not a node method. The checker goes under `backend/infrahub/core/validators/` with the other schema constraint checkers, because the schema load and check endpoints already run that list on every branch.

## Design overview

### Storage and resolution of the scope

- `CoreNumberPool.allocation_scope` keeps its kind (`List`, optional, branch-agnostic like the pool). Each element becomes `{"id": "<schema element id>", "name": "<element name>"}`. The attribute is absent or an empty list on an unscoped pool. Its description in `backend/infrahub/core/schema/definitions/core/resource_pool.py` says so.
- `backend/infrahub/pools/scope.py` holds `ScopeElement` (id, name), `AllocationScope` (ordered elements, `from_stored`, `to_stored`), `AllocationScopeResolver` (turns input entries into a scope against a schema branch, applying every refusal of spec FR-003 to FR-006; `refresh_names` for R2) and `Division` (ordered values, `key` for lock names, `from_node` to read the division of an in-memory node, `from_entries` to read a division filter).
- Every resolution uses the schema branch of the default branch (`registry.schema.get_schema_branch(name=registry.default_branch)`), whatever branch the request runs on. On the default branch itself, a schema load validates against the candidate schema, since the candidate becomes the default.
- `InfrahubNumberPoolMutation.mutate_create` (`backend/infrahub/graphql/mutations/resource_manager/number_pools/pool.py`) resolves `allocation_scope` from the payload and writes the stored form back before the node is created; `mutate_update` refuses a payload whose scope differs from the stored one, `null` included, with the message of `contracts/pool-allocation-scope.md`. The existing test `test_update_with_null_clears_the_scope` of `backend/tests/component/graphql/resource_manager/number_pools/test_pool_allocation_scope.py` is replaced by the refusal.
- Names are refreshed by `SchemaNumberPoolSynchronizer.run` on each schema update of the default branch, by looking each stored id up in the default schema.

### Allocation within a division

- The allocation chain on the branch is `AttributePoolApplier.apply` (`backend/infrahub/pools/attribute_pool_applier.py`) → `NumberPoolAttributeAllocator.allocate` → `CoreNumberPool.get_resource` → `NumberPoolNumberPicker.next_number` → `NumberPoolRepository.get_free` / `get_taken` → `NumberPoolGetFree`. Each link gains one optional `division` argument, default `None`; the applier computes it with `Division.from_node` when the resolved pool carries a scope. `get_taken` / `NumberPoolGetTaken` keep their global scan: a scope is refused on a `unique: true` attribute, so the two never meet.
- `CoreNumberPool.get_resource` locks on `<pool id>.<division key>` when a division is given, on `<pool id>` otherwise, and passes the division to the reservation lookup and the picker.
- `NumberPoolGetFree`, `NumberPoolGetUsed` and `NumberPoolGetAllocated` take one optional `division` argument that defaults to `None`. When given, `reserved_values_query()` is extended with a division subquery that, for each tracked attribute, reads the holder node and its scope values on the branch of the request (the query's `branch` and `Branch.get_query_filter_path`, as `NumberPoolGetAllocated` already does for the value edges), and keeps only the values whose scope tuple equals the parameter. With no division the fragment renders byte for byte the Cypher of today, which a unit test asserts.
- The writer's division is read after every field of the node is processed (research R6), with one order on create and on update: the pool is resolved inside the field loop (the applier with `allocate=False`, which normalises `from_pool` to the pool id) and the allocation runs in a second pass after the loop, for every pooled attribute whether the pool is scoped or not. On create this is `Node._process_fields_attributes`, which already calls the applier with `allocate=process_pools` in the loop. On update, `BaseAttribute.from_graphql` skips the applier when `process_pools` is false today, so `Node.from_graphql` changes to call the applier with `allocate=False` for each attribute whose payload carries `from_pool` and to run the second pass with `allocate=True` when `process_pools` is true. The validation of a pooled attribute's value runs after that pass. The full number-pool suites prove unscoped pools keep today's behaviour.
- The mutation-level lock keeps covering the allocation and the save. `create_node`'s preview (`Node.new(process_pools=False)`) and `lock_utils.apply_payload_for_lock_names` (`Node.from_graphql(process_pools=False)`) both resolve each pooled attribute's pool with `allocate=False` once the previous point lands; when that pool carries a scope, the step reads the writer's division from the preview node as the allocation will read it (an attribute from the node, a peer the payload, a template or a profile set from the relationship manager, a peer the payload did not set with one relationship read, since the preview node leaves its stored peers unread) and stores the key beside the pool id on the attribute (`from_pool = {"id": ..., "division": ...}`). `lock_utils.get_lock_names_on_object_mutation` then builds `resource_pool.<pool id>.<division key>` from it, and `resource_pool.<pool id>` otherwise. A component test covers a scope element set by a template and by a profile.
- When the schema of the request's branch does not define a scope element on the pool's kind, `Division.from_node` raises a `ValidationError` naming the element and the branch, and the request allocates nothing (spec FR-016).
- The attach path of IFC-3184 (`AttributePoolApplier._attach`, `NumberPoolAttributeAllocator.attach`) records the provided number unchanged; the division of that record is derived from its holder like any other, so spec FR-014 needs no write-path change beyond the lock key.

### Reading a scoped pool

- PR #10932 is rebased onto `feature-number-pools-1.12` and updated to the contract first: `backend/infrahub/graphql/queries/number_pool.py` gains the `NumberPoolScopeElement` type and the `id` field of `NumberPoolDivisionEntry`; `backend/infrahub/pools/number_pool_mock.py` carries `{id, name}` scope elements and reads each holder's division on the request branch; the mock's tests follow. The frontend team builds on that shape.
- `NumberPoolGetDivisions` (new query in `backend/infrahub/core/query/resource_manager.py`) groups the tracked values by division tuple on the request branch and returns, per division, the distinct values on any live branch, on the default branch, and on other branches only. `NumberPoolRepository.get_divisions` runs it. The resolver turns relationship values into display labels with one batched node lookup.
- `NumberPoolGetAllocated` gains the filters `division` (subset of elements allowed), range bounds, branch name and provenance, projects `coalesce(ir.provenance, "allocated")`, and keeps its default rendering for the existing callers (`NumberUtilizationGetter`, `resolve_number_pool_allocation`). The resolver resolves holders in batches per branch.
- The component tests of the divisions and allocations resolvers assert the number of database queries with `backend/tests/helpers/db_query_counter.py`, so that a per-row lookup cannot slip in.
- `NumberUtilizationGetter` (`backend/infrahub/pools/number.py`) takes an optional division and keeps measuring the `EffectiveSpace` of `backend/infrahub/pools/number_ranges.py`; the per-range figures come from `range_figures` as today.
- The three resolvers of `backend/infrahub/graphql/queries/number_pool.py` read the database per `contracts/graphql-number-pool-queries.md`, and `backend/infrahub/pools/number_pool_mock.py` is deleted.

### Declared scope and schema checker

- `NumberPoolParameters.allocation_scope` moves from `UpdateSupport.NOT_SUPPORTED` to `UpdateSupport.VALIDATE_CONSTRAINT`; `ConstraintIdentifier` gains `ATTRIBUTE_PARAMETERS_ALLOCATION_SCOPE_UPDATE = "attribute.parameters.allocation_scope.update"`.
- `SchemaBranch._validate_number_pool_parameters` applies the structural rules of research R3 to the declaration against the candidate schema; for an attribute whose pool does not exist yet, every declared name must resolve.
- `SchemaNumberPoolUpserter.upsert_number_pool` creates the pool with the resolved scope in its stored form; `SchemaNumberPoolSynchronizer._update_pool_from_schema` leaves the scope untouched.
- `backend/infrahub/core/validators/pool/scope.py::NumberPoolScopeChecker`, registered in `CONSTRAINT_VALIDATOR_MAP` under the nine names of research R8 and added to the aggregated checker's list, loads the scoped pools of the kind once, indexes element ids to pools, and returns one violation per dependent pool when the diff makes an element optional, changes a relationship's cardinality, removes an element or sets `unique: true` on the tracked attribute. For `attribute.name.update`, `relationship.name.update` and `attribute.parameters.allocation_scope.update` on a kind with a schema-created pool, it compares the declaration to the stored scope by id (research R9) and names a rename. The relationship `name` field of `backend/infrahub/core/schema/definitions/internal.py` moves to `UpdateSupport.VALIDATE_CONSTRAINT` so that a relationship rename reaches the checker; `backend/infrahub/core/schema/generated/relationship_schema.py` is regenerated.

## Complexity Tracking

No constitution violation to justify. One choice deserves a note: the readable name is stored beside the id although it could be resolved on every read. `research.md` records why (every read of the pool node, including the generic GraphQL node query, must show the pair, and a refresh on schema load keeps it current).
