# Tasks: Number pool allocation scopes

**Input**: Design documents from `dev/specs/ifc-3185-number-pool-scopes/`

**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/, quickstart.md

**Tests**: Included. The constitution requires tests at the right level for every feature, and the spec's success criteria are checked by them. Each story's tests are written first and fail before the implementation lands.

**Organization**: Tasks are grouped by user story so that each story is implemented and tested on its own.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependency on an unfinished task)
- **[Story]**: The user story the task belongs to (US1 to US4)
- Each task names the files it touches. A site inside a file is named by its symbol, never by a line number

## Path Conventions

- Backend code under `backend/infrahub/`, backend tests under `backend/tests/`
- User documentation under `docs/docs/`, internal knowledge under `dev/knowledge/`
- Generated files are regenerated with the commands of `contracts/number-pool-parameters.md`, never edited

---

## Phase 1: Setup (test fixtures and the scope module skeleton)

**Purpose**: The fixtures and the module every story builds on.

- [ ] T001 Add a schema fixture in `backend/tests/helpers/schema/scoped_pool.py`: a `TestingSite` kind, a `TestingScopedDevice` kind with a required cardinality-one `site` relationship, a required `role` Text attribute, an optional `rack` relationship, a many `tags` relationship and a `vlan_id` Number attribute; export it from `backend/tests/helpers/schema/__init__.py` next to the other fixtures
- [ ] T002 Add a `scoped_pool` fixture family to `backend/tests/component/core/resource_manager/conftest.py`: a pool over `TestingScopedDevice.vlan_id` with a one-element scope (`site`), a two-element scope (`site`, `role`) and no scope, plus helpers that create sites and devices with `from_pool`, reusing the existing `pooled_holder` pattern of that conftest
- [ ] T003 [P] Create `backend/infrahub/pools/scope.py` with the frozen dataclasses `ScopeElement` (`id`, `name`), `AllocationScope` (ordered elements, `from_stored`, `to_stored`, `is_empty`, `element_names`) and `Division` (ordered values, `key` as a stable hash of the JSON form, equality), and the unit test file `backend/tests/unit/pools/test_scope.py` covering `from_stored` and `to_stored` round trips and the key's stability

---

## Phase 2: Foundational (the scope on the pool, the resolver, the generated files)

**Purpose**: The attribute, its validation and the regenerated contracts that every story needs.

- [ ] T004 Add the `allocation_scope` attribute (kind `List`, optional, order weight after `end_range`, description from `data-model.md`) to `core_number_pool` in `backend/infrahub/core/schema/definitions/core/resource_pool.py`
- [ ] T005 Add `allocation_scope: list[str] | None` with the `not_supported` update marker to `NumberPoolParameters` in `backend/infrahub/core/schema/attribute_parameters.py`, with the description of `contracts/number-pool-parameters.md`
- [ ] T006 Regenerate the generated files: `uv run invoke backend.generate`, `uv run invoke schema.generate-graphqlschema`, `uv run invoke schema.generate-jsonschema`, `cd frontend/app && pnpm codegen`, `uv run invoke docs.generate`; commit them with T004 and T005 (depends on T004, T005)
- [ ] T007 Implement `AllocationScopeResolver` in `backend/infrahub/pools/scope.py`: `resolve(node_schema, tracked_attribute, entries) -> AllocationScope` accepting an entry as element id, element name or `{id, name}` object, applying every rule of `data-model.md` (declared on the kind or on the generic itself, required, cardinality one, no `__`, not the tracked attribute, no duplicate, tracked attribute not `unique`) and raising `ValidationError` with the messages of `contracts/pool-allocation-scope.md`; add `refresh_names(scope, node_schema) -> AllocationScope` (depends on T003)
- [ ] T008 Unit tests for the resolver in `backend/tests/unit/pools/test_scope.py`: one test per refusal, acceptance by id, by name and by object, order preserved, `refresh_names` after a rename, using the fixture of T001 registered in an in-memory `SchemaBranch` (depends on T007)
- [ ] T009 Implement `Division.from_node(node, scope)` in `backend/infrahub/pools/scope.py`: peer id for a relationship element read from the in-memory relationship manager, attribute value as text for an attribute element, empty string when the node holds nothing; and `Division.from_entries(entries, scope, allow_subset)` for the query inputs, refusing an unknown or repeated path with the contract's message; unit tests in `backend/tests/unit/pools/test_scope.py` (depends on T003)

**Checkpoint**: The pool carries a scope that validates and round-trips; the generated contracts are committed.

---

## Phase 3: User Story 1 - One pool serves every site (Priority: P1)

**Goal**: A pool created with a scope allocates the lowest free number within the writer's division, locks per division, and refuses an invalid or changed scope.

**Independent Test**: `uv run pytest backend/tests/component/graphql/resource_manager/test_number_pool_scope_mutation.py backend/tests/component/core/resource_manager/test_number_pool_scope_allocation.py backend/tests/component/core/resource_manager/test_number_pool_scope.py`

### Tests for User Story 1

- [ ] T010 [P] [US1] Component tests in `backend/tests/component/graphql/resource_manager/test_number_pool_scope_mutation.py`: create with a scope by name, by id and by object; the stored value is `[{id, name}]` in input order; an empty list creates an unscoped pool; every refusal of `contracts/pool-allocation-scope.md`; update with a different scope refused; update with the same scope accepted; upsert with identical fields accepted (depends on T002)
- [ ] T011 [P] [US1] Component tests in `backend/tests/component/core/resource_manager/test_number_pool_scope.py` for the queries: `NumberPoolGetFree` and `NumberPoolGetUsed` with a division return only that division's values; a two-element division; a holder with an empty value; the same holder moved to another site on a branch is counted under the new site on that branch and the old site on the default branch; no division renders today's rows (depends on T002)
- [ ] T012 [P] [US1] Unit test in `backend/tests/unit/core/query/test_resource_manager_fragments.py` asserting that `reserved_values_query()` with no division renders exactly the text it renders today (snapshot taken before the change)
- [ ] T013 [P] [US1] Component tests in `backend/tests/component/core/resource_manager/test_number_pool_scope_allocation.py`: two sites each receive 1; a second device in site A receives 2; the identifier is repeatable; two writers in one division get two numbers; a full division is refused while another division allocates; an attribute scope element that comes later in attribute order is read before allocation; an update that moves a device to another site allocates in the new site; the unscoped pool keeps today's numbers (depends on T002)

### Implementation for User Story 1

- [ ] T014 [US1] Extend `reserved_values_query()` in `backend/infrahub/core/query/resource_manager.py` with an optional division: a generated, parameter-bound subquery that reads, for each tracked attribute, the holder node and the scope values (relationship by identifier, attribute by name) on the branch holding the value with the default branch as fallback, and keeps the values whose tuple equals `$division`; the caller passes the scope elements with their kind and identifier; no division renders today's text (depends on T009, T012)
- [ ] T015 [US1] Add the optional `division` argument to `NumberPoolGetFree` and `NumberPoolGetUsed` in `backend/infrahub/core/query/resource_manager.py`, and to `CoreNumberPool.get_free`, `get_used`, `get_next` and `get_resource` in `backend/infrahub/core/node/resource_manager/number_pool.py`; `get_resource` locks on `<pool id>.<division key>` when a division is given, and reads the pool's scope through `AllocationScope.from_stored` (depends on T014)
- [ ] T016 [US1] In `backend/infrahub/graphql/mutations/resource_manager.py::InfrahubNumberPoolMutation`: on create, resolve `allocation_scope` with `AllocationScopeResolver` against the default branch's schema (`registry.schema.get_schema_branch(name=registry.default_branch)`) and write the stored form back into the payload; on update, refuse a payload whose scope differs from the stored one with the contract's message (depends on T007)
- [ ] T017 [US1] In `backend/infrahub/core/node/__init__.py`: keep the pool resolution and the `from_pool` normalisation of `Node.handle_pool` inside `_process_fields_attributes`, move the allocation of every pooled attribute to a second pass at the end of `_process_fields` that computes the division with `Division.from_node` when the pool is scoped, then validates the attribute value; make `Node.from_graphql` apply every key first and allocate afterwards (depends on T015)
- [ ] T018 [US1] In `backend/infrahub/core/node/lock_utils.py`: `apply_payload_for_lock_names` resolves each pooled attribute's pool with `handle_pool(allocate_resources=False)` and stores the division key beside the pool id on the attribute when the pool is scoped; `get_lock_names_on_object_mutation` builds `resource_pool.<pool id>.<division key>` from it, and `resource_pool.<pool id>` otherwise (depends on T017)
- [ ] T019 [US1] Run the existing number-pool suites unchanged (`backend/tests/component/core/resource_manager`, `backend/tests/component/graphql/resource_manager`, `backend/tests/integration/schema_lifecycle/test_number_pool_branch_merge.py`, `backend/tests/unit/core`) and fix any regression of the second-pass allocation (depends on T017, T018)

**Checkpoint**: A scoped pool allocates per division through the API; unscoped pools are unchanged.

---

## Phase 4: User Story 2 - View how full each division is and which numbers it holds (Priority: P2)

**Goal**: The three dedicated queries of `contracts/graphql-number-pool-queries.md` answer from the database.

**Independent Test**: `uv run pytest backend/tests/component/graphql/resource_manager/test_number_pool_queries.py backend/tests/component/core/resource_manager/test_number_pool_scope.py`

### Tests for User Story 2

- [ ] T020 [P] [US2] Component tests for the queries in `backend/tests/component/core/resource_manager/test_number_pool_scope.py`: `NumberPoolGetDivisions` returns one row per division with `used`, `used_default_branch`, `used_branches`, omits a division with no value, handles an empty value; `NumberPoolGetAllocated` with the division subset, range bounds, branch and provenance filters, the provenance of a record without the property reads as `allocated`, and the count before pagination (depends on T002)
- [ ] T021 [P] [US2] Component tests in `backend/tests/component/graphql/resource_manager/test_number_pool_queries.py` with the dataset of the contract's example: each of the three queries on the scoped pool and on the unscoped pool, `allocation_scope` as `{id, name}` objects, entries with `id`, display labels and `peer_kind` of relationship entries, ordering of the divisions and of the rows, every refusal of the contract, and a query-count assertion with `backend/tests/helpers/db_query_counter.py` on the divisions and allocations resolvers (depends on T002)
- [ ] T022 [P] [US2] Snapshot test of the GraphQL SDL of the new types, input, enum and root fields in `backend/tests/unit/graphql/test_number_pool_queries_contract.py` with the snapshot in `backend/tests/unit/graphql/snapshots/number_pool_queries.graphql`, matching the SDL of the contract

### Implementation for User Story 2

- [ ] T023 [US2] Add `NumberPoolGetDivisions` to `backend/infrahub/core/query/resource_manager.py`: groups the tracked values of the pool's space by division tuple, returns a frozen `NumberPoolDivisionResult` (values, used, used_default_branch, used_branches) per division (depends on T014)
- [ ] T024 [US2] Extend `NumberPoolGetAllocated` in `backend/infrahub/core/query/resource_manager.py` with the optional filters `division` (subset allowed), `ranges` (bounds), `branch_name` and `provenance`, project `coalesce(ir.provenance, 'allocated')`, add `provenance` to `NumberPoolAllocatedResult`, keep the default rendering for the existing callers (depends on T014)
- [ ] T025 [US2] Extend `NumberUtilizationGetter` in `backend/infrahub/pools/number.py` with an optional division and expose the used sets per range for the per-range figures; keep `resolve_number_pool_utilization` in `backend/infrahub/graphql/queries/resource_manager.py` unchanged in behaviour (depends on T024)
- [ ] T026 [US2] Create `backend/infrahub/graphql/queries/number_pool.py` with the graphene types of the contract (`NumberPoolScopeElement`, `NumberPoolUtilization`, `NumberPoolUtilizationFigures`, `NumberPoolRangeUtilization`, `NumberPoolDivisions`, `NumberPoolDivision`, `NumberPoolDivisionEntry`, `NumberPoolDivisionEntryInput`, `NumberPoolAllocations`, `NumberPoolAllocation`, `NumberPoolHolder`, `NumberPoolRangeRef`, `NumberPoolProvenance`) and the three resolvers: division filter parsed with `Division.from_entries`, refusals with the contract's messages, holders resolved in one `NodeManager.get_many` per branch, peers resolved in one batched lookup, display labels joined with " / " (depends on T023, T024, T025)
- [ ] T027 [US2] Register `InfrahubNumberPoolUtilization`, `InfrahubNumberPoolDivisions` and `InfrahubNumberPoolAllocations` in `backend/infrahub/graphql/schema.py` and export them from `backend/infrahub/graphql/queries/__init__.py`; regenerate `schema/schema.graphql` and the frontend GraphQL types (depends on T026)
- [ ] T028 [US2] Update the descriptions of `InfrahubResourcePoolUtilization` and `InfrahubResourcePoolAllocated` in `backend/infrahub/graphql/queries/resource_manager.py` to say that, for a number pool, they ignore the allocation scope and to point to the dedicated queries; regenerate `schema/schema.graphql` (depends on T027)

**Checkpoint**: The pool page can be built on the three queries; the snapshot pins the contract.

---

## Phase 5: User Story 3 - Declare the scope of a schema-defined pool (Priority: P3)

**Goal**: `parameters.allocation_scope` on a number-pool attribute creates the pool with that scope, validated against the default branch, immutable afterwards.

**Independent Test**: `uv run pytest backend/tests/component/pools/test_schema_number_pool_scope.py backend/tests/integration/schema_lifecycle/test_number_pool_scope_guard.py -k declared`

### Tests for User Story 3

- [ ] T029 [P] [US3] Component tests in `backend/tests/component/pools/test_schema_number_pool_scope.py` using `backend/tests/helpers/number_pool.py::register_and_provision_number_pools`: a declared scope is stored as ids and names on the created pool; nodes in two sites each receive 1; a declaration naming an optional, many, path or absent element fails `SchemaBranch.validate_*` with the attribute and the element named (depends on T002)
- [ ] T030 [P] [US3] Integration tests in `backend/tests/integration/schema_lifecycle/test_number_pool_scope_guard.py` (declared part, pattern of `test_attribute_parameters_update.py`): loading a schema that changes or clears the declared scope of an existing pool is refused with the attribute named; loading on a branch a scope that names an element absent from the default branch is refused

### Implementation for User Story 3

- [ ] T031 [US3] In `backend/infrahub/core/schema/schema_branch.py::_validate_number_pool_parameters`, resolve `parameters.allocation_scope` with `AllocationScopeResolver` against the default branch's schema (the candidate schema when validating the default branch itself), raising `ValidationError` with `<kind>.<attribute>: allocation_scope: <reason>` (depends on T007)
- [ ] T032 [US3] In `backend/infrahub/pools/schema_number_pool_upserter.py::upsert_number_pool`, create the pool with the resolved scope in its stored form; in `backend/infrahub/pools/schema_number_pool_synchronizer.py::_update_pool_from_schema`, leave the scope untouched (the `not_supported` marker refuses a change at load) (depends on T031)
- [ ] T033 [US3] Verify with a test in `backend/tests/integration/schema_lifecycle/test_number_pool_scope_guard.py` that the `not_supported` marker of `allocation_scope` is enforced by `backend/infrahub/core/models.py::SchemaUpdateValidationResult` on a change and on a clear, and that an unchanged declaration reloads without error (depends on T005, T030)

**Checkpoint**: A schema-created pool is scoped from its declaration.

---

## Phase 6: User Story 4 - Keep a scoped pool valid when the schema changes (Priority: P4)

**Goal**: Breaking schema changes are refused on every branch with the pool named; a rename is allowed and the stored name follows.

**Independent Test**: `uv run pytest backend/tests/integration/schema_lifecycle/test_number_pool_scope_guard.py`

### Tests for User Story 4

- [ ] T034 [P] [US4] Integration tests in `backend/tests/integration/schema_lifecycle/test_number_pool_scope_guard.py` (guard part): making the scoped relationship optional, changing its cardinality to many, removing it, making the scoped attribute optional, removing it, and setting `unique: true` on the tracked attribute are each refused with the pool and the element named; the same refusal on a branch; renaming the relationship succeeds, the pool reads the new name, and a new node still allocates per site; the schema check endpoint reports the same refusal without loading
- [ ] T035 [P] [US4] Unit tests in `backend/tests/unit/pools/test_scope_guard.py` for the guard's decision table against a schema diff, without a database

### Implementation for User Story 4

- [ ] T036 [US4] Create `backend/infrahub/pools/scope_guard.py` with `ScopedPoolSchemaGuard`: loads the scoped pools in one query, indexes element ids to pools, and returns the refusals for a candidate schema whose diff makes an element optional, changes a relationship's cardinality, removes an element or sets `unique: true` on a tracked attribute; one message per element naming every dependent pool (depends on T003)
- [ ] T037 [US4] Call the guard from the schema load and schema check endpoints in `backend/infrahub/api/schema.py`, after the diff is computed and before `_validate_migrations`, on every branch, turning its refusals into the endpoint's error response (depends on T036)
- [ ] T038 [US4] Add a `_refresh_scope_names` step to `backend/infrahub/pools/schema_number_pool_synchronizer.py::run` that, on the default branch, rewrites the stored name of each element whose name changed, for user-created and schema-created pools, using `AllocationScopeResolver.refresh_names` (depends on T007)

**Checkpoint**: The scope survives a rename and refuses a breaking change.

---

## Phase 7: Polish and cross-cutting work

**Purpose**: Documentation, measurements, the changelog, and the checks before the pull request.

- [ ] T039 [P] Write the user guide `docs/docs/resource-manager/scoped-number-pools.mdx`: scope a pool (the three input forms), declare the scope in the schema, read a pool with the three queries, replace per-site pools with one scoped pool; add it to `docs/sidebars.ts` after `resource-manager/allocate-number`; add an allocation-scope paragraph to the "Number pools" section of `docs/docs/resource-manager/overview.mdx`; run `uv run invoke docs.lint`
- [ ] T040 [P] Extend the "Resource Pool Reservations" section of `dev/knowledge/backend/database-schema.md` with how a record's division is derived from its holder, and the branch fallback of research R5
- [ ] T041 Run the manual and two-branch scenarios of `quickstart.md` on a live stack built from the branch, and the measurement table; record the ratios in `dev/specs/ifc-3185-number-pool-scopes/measurements.md`; if the holder-anchored Cypher order is clearly faster, switch `reserved_values_query()` to it and update `plan.md` and `research.md` (depends on T019, T027)
- [ ] T042 Write the changelog fragments with the `creating-changelog-entries` skill: the allocation scope on number pools, the scoped allocation, the three dedicated queries (including the `{id, name}` shape of `allocation_scope`), the declared scope in the number-pool attribute parameters, and the schema refusal when a scoped element would break; one fragment per user-visible change, at the end of the work (depends on T041)
- [ ] T043 Open the SDK pull request that regenerates the schema models of `python_sdk/infrahub_sdk/schema/generated/` with `allocation_scope` in the number-pool parameters, then move the `python_sdk` submodule pointer once it is merged (depends on T006)
- [ ] T044 Run `/pre-ci` (format, lint, `ty`, mypy over `backend/`, generated-file and generated-doc validation) and fix what it reports; confirm `tests/e2e/resource-manager/test_number_pool.py` still passes against a stack built from the branch (depends on T042)

---

## Dependencies and execution order

### Phase dependencies

- **Setup (Phase 1)**: no dependency; T001 to T003 can run in parallel
- **Foundational (Phase 2)**: depends on Phase 1; blocks every user story
- **User Story 1 (Phase 3)**: depends on Phase 2
- **User Story 2 (Phase 4)**: depends on T014 (the division fragment) from User Story 1; otherwise independent of the rest of Phase 3
- **User Story 3 (Phase 5)**: depends on T007 (the resolver) and on User Story 1 for the allocation test of T029
- **User Story 4 (Phase 6)**: depends on T003 and T007; independent of Stories 2 and 3
- **Polish (Phase 7)**: depends on every story being complete

### User story dependencies

- **User Story 1**: starts after Phase 2; no dependency on another story
- **User Story 2**: starts once T014 exists; testable on its own with the fixtures of T002
- **User Story 3**: starts once T007 exists; testable on its own through the schema load
- **User Story 4**: starts once T007 exists; testable on its own through the schema load and check endpoints

### Within each user story

- Tests first, failing before the implementation
- Queries before node methods, node methods before GraphQL resolvers and mutations
- The existing number-pool suites run green before the story is called complete

### Parallel opportunities

- T001, T002, T003 together; T010 to T013 together; T020 to T022 together; T029 and T030 together; T034 and T035 together; T039 and T040 together
- Once T014 lands, User Story 2's queries (T023, T024) can proceed while User Story 1 finishes T016 to T019
- User Story 4 can be developed in parallel with Stories 2 and 3 by a second developer

---

## Parallel example: User Story 1

```bash
# The four test files of User Story 1 together:
Task: "Component tests of the scope on the pool mutations in backend/tests/component/graphql/resource_manager/test_number_pool_scope_mutation.py"
Task: "Component tests of the scoped free and used queries in backend/tests/component/core/resource_manager/test_number_pool_scope.py"
Task: "Rendering test of the shared fragment in backend/tests/unit/core/query/test_resource_manager_fragments.py"
Task: "Component tests of allocation per division in backend/tests/component/core/resource_manager/test_number_pool_scope_allocation.py"
```

---

## Implementation strategy

### First deliverable (User Story 1 only)

1. Phase 1 and Phase 2
2. Phase 3
3. Stop and validate: a scoped pool allocates per division through the API, unscoped pools unchanged

### Incremental delivery

1. Phase 1 and 2: the scope exists on the pool and validates
2. User Story 1: scoped allocation and locks
3. User Story 2: the three queries, which unblocks the frontend page
4. User Story 3: the declared scope
5. User Story 4: the schema guard and the rename follow-up
6. Phase 7: documentation, measurements, changelog, SDK

### Not in this task list

- FR-014 (a provided number checked per division) is applied by the attach paths of IFC-3184 when they land; the division-aware used query of T015 is what they call.
- The frontend pool form and pool page (IFC-3363).

---

## Notes

- [P] tasks touch different files and do not depend on an unfinished task
- Each task names its files; a site in a file is named by its symbol
- Commit after each task or logical group; changelog fragments are written once, in T042
- Generated files are regenerated with the listed commands and committed with the change that caused them
