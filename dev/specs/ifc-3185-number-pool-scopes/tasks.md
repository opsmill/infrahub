# Tasks: Number pool allocation scopes

**Input**: Design documents from `dev/specs/ifc-3185-number-pool-scopes/`

**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/, quickstart.md

**Tests**: Included. The constitution requires tests at the right level for every feature, and the spec's success criteria are checked by them. Each story's tests are written first and fail before the implementation lands.

**Organization**: Tasks are grouped by user story so that each story is implemented and tested on its own. Every task ends with the Jira ticket of IFC-3185 it belongs to (`Jira: IFC-xxxx`) or `Jira: none`; the mapping is summarised under [Jira tickets](#jira-tickets).

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependency on an unfinished task)
- **[Story]**: The user story the task belongs to (US1 to US4)
- Each task names the files it touches. A site inside a file is named by its symbol, never by a line number

## Path Conventions

- Backend code under `backend/infrahub/`, backend tests under `backend/tests/`
- User documentation under `docs/docs/`, internal knowledge under `dev/knowledge/`
- Generated files are regenerated with the commands of `contracts/number-pool-parameters.md`, never edited

---

## Phase 1: Setup (the mock pull request, test fixtures and the scope module skeleton)

**Purpose**: The contract the frontend builds on, and the fixtures and the module every story builds on.

- [X] T001 Rebase PR #10932 (`pmi-number-pool-scoped-pools-ifc-3185`, based on `pmi-number-pool-graphql-surface-ifc-3185` today) onto `feature-number-pools-1.12`, delete `backend/tests/component/graphql/resource_manager/number_pools/test_pool_scope.py` (its three tests repeat `test_pool_allocation_scope.py`), and regenerate `schema/schema.graphql` and `frontend/app/src/shared/api/graphql/generated/` after the rebase. Done: the branch was rebased onto `number-pool-branch-provenance` (PR #10949, itself based on `feature-number-pools-1.12`) instead, because that branch moves the `python_sdk` submodule to an SDK commit that knows `allocation_scope`; PR #10932 is stacked on #10949. Jira: IFC-3347
- [X] T002 Update the fixed dataset of PR #10932 to the contract of `contracts/graphql-number-pool-queries.md`: in `backend/infrahub/graphql/queries/number_pool.py` add the `NumberPoolScopeElement` object type (`id`, `name`), make `NumberPoolUtilization.allocation_scope` and `NumberPoolDivisions.allocation_scope` lists of it, add `id` to `NumberPoolDivisionEntry`, and drop "in force on the request's branch" from every description and refusal message; in `backend/infrahub/pools/number_pool_mock.py` make `MockPool.allocation_scope`, `MockUtilization.allocation_scope` and `MockDivisions.allocation_scope` tuples of `{id, name}` objects, give `MockDivisionEntry` an `id`, and read each holding object's division on the request branch (on `main`, D1 sits in site A and site C holds no value; on `branch1`, site C holds D1's 5); update `backend/tests/unit/pools/test_number_pool_mock.py` and `backend/tests/component/graphql/queries/test_number_pool_surface.py` (the branch-naming refusal test goes); update the description of PR #10932 so that the frontend team reads the `{id, name}` shape and the new example figures (depends on T001). Done: `backend/tests/unit/pools/test_number_pool_mock.py` was already deleted on the PR branch, so the component tests cover the change. The PR description is published with the `{id, name}` shape and the new example figures. The SDL snapshot test (`backend/tests/unit/graphql/test_number_pool_surface_contract.py` and its snapshot) was removed on 2026-10-09: the contract is agreed with the frontend team directly, and `schema/schema.graphql` shows any change to it in a pull request. Jira: IFC-3347
- [X] T003 [P] Extend the scoped-pool test schema of PR #10932 in `backend/tests/helpers/number_pool.py` (`SCOPED_SITE`, `SCOPED_DEVICE`, `SCOPED_POOL_SCHEMA`): a required `role` Text attribute, a `tags` List attribute, an optional `rack` relationship and a many `links` relationship on `SCOPED_DEVICE`, plus a generic `ScopedHolder` declaring `site` and the pooled attribute with one implementing kind that adds a required `pod` attribute of its own (depends on T001). Done: the pooled attribute is `vlan_id`; the peer kinds are `ScopeRack` and `ScopeLink`; the generic is `ScopeHolder` (constant `SCOPED_HOLDER`) and its implementing kind `ScopePodHolder`. Jira: none
- [X] T004 [P] Add a `scoped_pool` fixture family to `backend/tests/component/core/resource_manager/conftest.py`: a pool over `SCOPED_DEVICE.vlan_id` with a one-element scope (`site`), a two-element scope (`site`, `role`), a `List` scope (`tags`) and no scope, plus helpers that create sites and devices with `from_pool`, reusing the `serial_pool` and `pooled_holder` pattern of that conftest (depends on T003). Done: the pools store their scope as names until T015 changes the stored shape. The `List` scope fixture was removed when decision 10 was revised on 2026-10-09; the `tags` attribute stays in the test schema to test the refusal. Jira: none
- [X] T005 [P] Create `backend/infrahub/pools/scope.py` with the frozen dataclasses `ScopeElement` (`id`, `name`), `AllocationScope` (ordered elements, `from_stored` refusing an entry that is not an `{id, name}` object with the message of `data-model.md`, `to_stored`, `is_empty`, `element_names`) and `Division` (ordered values, `key` as a stable hash of the JSON form, equality), and the unit test file `backend/tests/unit/pools/test_scope.py` covering `from_stored` and `to_stored` round trips, the old-shape refusal and the key's stability for scalar, `List` and `JSON` values. Revised on 2026-10-09 with decision 10: a division holds only scalar values, so its key is tested on scalars. Jira: IFC-3348

---

## Phase 2: Foundational (the resolver, the stored shape, the generated files)

**Purpose**: The validation, the new stored shape and the regenerated contracts that every story needs.

- [X] T006 Update the description of the `allocation_scope` attribute of `core_number_pool` in `backend/infrahub/core/schema/definitions/core/resource_pool.py` to the `{id, name}` shape of `data-model.md`. The `NumberPoolParameters.allocation_scope` description, its update marker and the constraint identifier are part of T031, so that the marker does not change before the checker that handles it exists. Jira: none
- [X] T007 Regenerate the generated files: `uv run invoke backend.generate`, `uv run invoke schema.generate-graphqlschema`, `uv run invoke schema.generate-jsonschema`, `cd frontend/app && pnpm codegen`, `uv run invoke docs.generate`; commit them with T006 (depends on T006). Jira: none
- [X] T008 Implement `AllocationScopeResolver` in `backend/infrahub/pools/scope.py`: `resolve(node_schema, tracked_attribute, entries) -> AllocationScope` accepting an entry as element id, element name or `{id, name}` object, applying every rule of `data-model.md` (declared on the kind or on the generic itself, required, cardinality one, any attribute kind, no `__`, not the tracked attribute, no duplicate, tracked attribute not `unique`) and raising `ValidationError` with the messages of `contracts/pool-allocation-scope.md`; add `refresh_names(scope, node_schema) -> AllocationScope` and `default_branch_schema()` returning `registry.schema.get_schema_branch(name=registry.default_branch)` (depends on T005). Jira: IFC-3348
- [X] T009 Unit tests for the resolver in `backend/tests/unit/pools/test_scope.py`: one test per refusal, acceptance by id, by name and by object, a `List`, a `JSON` and an `Any` attribute refused, order preserved, the generic rule with the fixture of T003 registered in an in-memory `SchemaBranch`, `refresh_names` after a rename (depends on T008). Jira: IFC-3348
- [X] T010 Implement `Division.from_node(node, scope, branch_schema)` in `backend/infrahub/pools/scope.py`: peer id for a relationship element read from the in-memory relationship manager, attribute value as stored for an attribute element, empty string when the node holds nothing, `ValidationError` with the message of `contracts/pool-allocation-scope.md` when `branch_schema` does not define the element on the kind; unit tests in `backend/tests/unit/pools/test_scope.py` (depends on T005). `Division.from_entries` moved to T027 on 2026-10-09, because only the dedicated queries read division entries. Jira: IFC-3349

**Checkpoint**: The scope validates and round-trips in its stored shape; the generated contracts are committed.

---

## Phase 3: User Story 1 - One pool serves every site (Priority: P1)

**Goal**: A pool created with a scope stores `{id, name}` elements, refuses an invalid or changed scope, allocates the lowest free number within the writer's division read on the request branch, and locks per division.

**Independent Test**: `uv run pytest backend/tests/component/graphql/resource_manager/number_pools/test_pool_allocation_scope.py backend/tests/component/core/resource_manager/test_number_pool_scope_allocation.py backend/tests/component/core/resource_manager/test_number_pool_scope.py`

### Tests for User Story 1

- [X] T011 [P] [US1] Rewrite `backend/tests/component/graphql/resource_manager/number_pools/test_pool_allocation_scope.py`: create with a scope by name, by id and by object; the stored value is `[{id, name}]` in input order; an empty list creates an unscoped pool; every refusal of `contracts/pool-allocation-scope.md` through create and update; update with a different scope, with `null` (replacing `test_update_with_null_clears_the_scope`) and on a schema-created pool refused; update with the same scope accepted; upsert with identical fields accepted; a `List` attribute refused (depends on T004). Jira: IFC-3348
- [X] T012 [P] [US1] Component tests in `backend/tests/component/core/resource_manager/test_number_pool_scope.py` for the queries: `NumberPoolGetFree` and `NumberPoolGetUsed` with a division return only that division's values; a two-element division; a holding object with an empty value; a holding object moved to another site on a branch is counted under the new site when the query runs on that branch and under the old site when it runs on the default branch; a holding object that exists only on another branch is not counted; no division renders today's rows (depends on T004). Jira: IFC-3349
- [X] T013 [P] [US1] Component test in `backend/tests/component/core/resource_manager/test_number_pool_scope.py` asserting that the free and used queries with no division read the same numbers as before, against the database (`test_without_a_division_every_tracked_number_is_read`). A test of the rendered Cypher text was written first and dropped on 2026-10-09: it checked a string, not what the query reads. Jira: IFC-3349
- [X] T014 [P] [US1] Component tests in `backend/tests/component/core/resource_manager/test_number_pool_scope_allocation.py`: two sites each receive 1; a second device in site A receives 2; the identifier is repeatable; two writers in one division get two numbers and hold the same lock name, two writers in two divisions hold different lock names; a full division is refused while another division allocates; an attribute scope element that comes later in attribute order is read before allocation; an update that moves a device to another site and allocates in one request allocates in the new site; a scope element set by an object template and by a profile gives the same lock key as the allocation's division; a provided number (`value` with `from_pool`) is recorded under the writer's division and the next allocation there skips it; an allocation on a branch whose schema lacks the element is refused naming the element and the branch; the unscoped pool keeps today's numbers (depends on T004). Jira: IFC-3349

### Implementation for User Story 1

- [X] T015 [US1] In `backend/infrahub/graphql/mutations/resource_manager/number_pools/pool.py::InfrahubNumberPoolMutation`: in `mutate_create`, resolve `allocation_scope` with `AllocationScopeResolver` against `default_branch_schema()` and write the stored form back into the payload before the node is created; in `mutate_update`, load the stored scope and refuse a payload whose scope differs or is `null` with the message of `contracts/pool-allocation-scope.md`, through `_refuse_unsupported_writes` for the schema-created pool case; add the message constant to `backend/infrahub/graphql/mutations/resource_manager/number_pools/common.py`; change the `scoped_pool` fixtures of `backend/tests/component/core/resource_manager/conftest.py` and the expected `allocation_scope` of `backend/tests/component/core/resource_manager/test_number_pool_scope.py` to `{id, name}` elements (depends on T008). Jira: IFC-3348
- [X] T016 [US1] Extend `reserved_values_query()` in `backend/infrahub/core/query/resource_manager.py` with optional `division` and `branch_filter` arguments: a generated, parameter-bound subquery that reaches the holding object through its `HAS_ATTRIBUTE` edge, reads the scope values (relationship by identifier through the `Relationship` vertex, attribute by name) with the request branch's filter from `Branch.get_query_filter_path`, and keeps the values whose tuple equals `$division`; the caller passes the scope elements with their kind and identifier; with no division the query reads the same numbers as before (depends on T010, T013). Jira: IFC-3349
- [X] T017 [US1] Add the optional `division` argument to `NumberPoolGetFree` and `NumberPoolGetUsed` in `backend/infrahub/core/query/resource_manager.py`, to `NumberPoolRepository.get_free` and `get_used` in `backend/infrahub/pools/number_pool_repository.py`, to `NumberPoolNumberPicker.next_number` in `backend/infrahub/pools/number_pool_number_picker.py`, to `NumberPoolAttributeAllocator.allocate` in `backend/infrahub/pools/number_pool_attribute_allocator.py` and to `CoreNumberPool.get_resource` in `backend/infrahub/core/node/resource_manager/number_pool.py`; `get_resource` locks on `<pool id>.<division key>` when a division is given, reading the pool's scope through `AllocationScope.from_stored` (depends on T016). Jira: IFC-3349
- [X] T018 [US1] In `backend/infrahub/pools/attribute_pool_applier.py::AttributePoolApplier.apply` and `_allocate`: when the resolved pool carries a scope, compute the writer's division with `Division.from_node` against the schema branch of the node's branch and pass it to the allocator; with `allocate=False`, store the division key beside the pool id on `attribute.from_pool` (depends on T017). Jira: IFC-3349
- [X] T019 [US1] In `backend/infrahub/core/node/__init__.py`: keep the applier call with `allocate=False` inside `_process_fields_attributes` and move the allocation of every pooled attribute to a second pass at the end of `_process_fields` that calls the applier with `allocate=process_pools`, then validates the attribute value; in `Node.from_graphql`, call the applier with `allocate=False` for each attribute whose payload carries `from_pool` while the keys are applied and run the same second pass afterwards; in `backend/infrahub/core/attribute.py::BaseAttribute.from_graphql`, stop calling the applier (the node runs it) (depends on T018). Jira: IFC-3349
- [X] T020 [US1] In `backend/infrahub/core/node/lock_utils.py`: `apply_payload_for_lock_names` reads, for each pooled attribute whose resolved pool is scoped, the peers of the scope relationships the payload did not set with one relationship read each, so that the division key stored by T018 matches the allocation's division; `get_lock_names_on_object_mutation` builds `resource_pool.<pool id>.<division key>` when the attribute carries a division key, and `resource_pool.<pool id>` otherwise; `backend/infrahub/core/node/create.py::create_node` needs no change beyond the preview's `new(process_pools=False)` running the same applier (depends on T019). Jira: IFC-3349
- [X] T021 [US1] Run the existing number-pool suites unchanged (`backend/tests/component/core/resource_manager`, `backend/tests/component/graphql/resource_manager`, `backend/tests/component/graphql/queries`, `backend/tests/functional/pools`, `backend/tests/unit/pools`, `backend/tests/integration/schema_lifecycle/test_number_pool_branch_merge.py`) and fix any regression of the second-pass allocation (depends on T019, T020). Jira: IFC-3349
- [ ] T047 [US1] Follow-up pull request, outside the spec: a node created from an object template whose `<attribute>__pool` relationship names a scoped number pool gets the lowest number free in its own division. Today the template draws the number from the whole pool, and the mutation's lock is pool-wide. [CLAUDE RECOMMENDED – based on the review of the IFC-3349 branch on 2026-10-09] Two code paths need the change:
  - Top-level node: in `backend/infrahub/templates/node_applier.py::NodeTemplateApplier._handle_pool_relationship`, name a scoped pool with `from_pool` on the attribute instead of drawing the number, so the pool applier reads the division once every field is set and the mutation locks on the division.
  - Component created from a subtemplate: `backend/infrahub/core/node/create.py::allocate_from_resource_pools` calls `get_resource` without a division. Pass the pool applier that `create_node` builds down through `create_components` and `create_component`, and apply the pool through it for a scoped pool, instead of building a division reader inside the helper.
  - Not covered by this task: a component's pool is not in the lock names the parent's preview computes, so only the short lock inside `get_resource` protects it, for scoped and unscoped pools alike. Two concurrent creates can read the same free number before either commits.
  - Tests in `backend/tests/component/core/resource_manager/test_number_pool_scope_allocation.py`: a device created from a template whose pool is scoped receives the first number of its site and takes its site's lock; a component created from a subtemplate does the same, which needs a test schema with a parent and a component kind (depends on T020). Jira: none

**Checkpoint**: A scoped pool allocates per division through the API; unscoped pools are unchanged.

---

## Phase 4: User Story 2 - View how full each division is and which numbers it holds (Priority: P2)

**Goal**: The three dedicated queries of `contracts/graphql-number-pool-queries.md` answer from the database, and the fixed dataset of PR #10932 is deleted.

**Independent Test**: `uv run pytest backend/tests/component/graphql/queries/test_number_pool_surface.py backend/tests/component/core/resource_manager/test_number_pool_scope.py`

### Tests for User Story 2

- [ ] T022 [P] [US2] Component tests for the queries in `backend/tests/component/core/resource_manager/test_number_pool_scope.py`: `NumberPoolGetDivisions` returns one row per division read on the request branch with `used`, `used_default_branch`, `used_branches`, omits a division with no value, handles an empty value, reports D1 under site C on `b1` and under site A on the default branch; `NumberPoolGetAllocated` with the division subset, range bounds, branch and provenance filters, the provenance of a record without the property reads as `allocated`, and the count before pagination (depends on T004). Jira: IFC-3329
- [ ] T023 [P] [US2] Replace the fixed-dataset cases of `backend/tests/component/graphql/queries/test_number_pool_surface.py` by real-data cases with the dataset of the contract's example: each of the three queries on the scoped pool and on the unscoped pool, `allocation_scope` as `{id, name}` objects, entries with `id`, display labels and `peer_kind` of relationship entries, ordering of the divisions and of the rows, the read on `b1` and on the default branch, every refusal of the contract including the stale-branch one, `pool_id: "mock-unscoped"` refused, and a query-count assertion with `backend/tests/helpers/db_query_counter.py` on the divisions and allocations resolvers (depends on T004). Jira: IFC-3329

### Implementation for User Story 2

- [ ] T024 [US2] Add `NumberPoolGetDivisions` to `backend/infrahub/core/query/resource_manager.py`: groups the tracked values of the pool's space by division tuple read on the request branch, returns a frozen `NumberPoolDivisionResult` (values, used, used_default_branch, used_branches) per division; add `NumberPoolRepository.get_divisions` in `backend/infrahub/pools/number_pool_repository.py` (depends on T016). Jira: IFC-3329
- [ ] T025 [US2] Extend `NumberPoolGetAllocated` in `backend/infrahub/core/query/resource_manager.py` with the optional filters `division` (subset allowed, read on the request branch), `ranges` (bounds), `branch_name` and `provenance`, project `coalesce(ir.provenance, "allocated")`, extend `order_by` to value, branch, holding object id, add `provenance` to `NumberPoolAllocatedResult`, keep the default rendering for `NumberUtilizationGetter` and `resolve_number_pool_allocation` (depends on T016). Jira: IFC-3329
- [ ] T026 [US2] Extend `NumberUtilizationGetter` in `backend/infrahub/pools/number.py` with an optional division passed to `NumberPoolGetAllocated`; keep `resolve_number_pool_utilization` in `backend/infrahub/graphql/queries/resource_manager.py` unchanged in behaviour (depends on T025). Jira: IFC-3329
- [ ] T027 [US2] Make the three resolvers of `backend/infrahub/graphql/queries/number_pool.py` read the database: division filter parsed with `Division.from_entries(entries, scope, allow_subset)` in `backend/infrahub/pools/scope.py`, which refuses an unknown or repeated path with the contract's message and compares each value with the type the element stores (unit tests in `backend/tests/unit/pools/test_scope.py`), refusals with the contract's messages, holding objects resolved in one `NodeManager.get_many` per branch, peers resolved in one batched lookup, display labels joined with " / ", figures from `NumberUtilizationGetter` and `NumberPoolRepository.get_divisions`; delete `backend/infrahub/pools/number_pool_mock.py` (depends on T002, T024, T025, T026). Jira: IFC-3329
- [ ] T028 [US2] Verify that the descriptions of `InfrahubResourcePoolUtilization` and `InfrahubResourcePoolAllocated` in `backend/infrahub/graphql/queries/resource_manager.py` (added by PR #10932) say that, for a number pool, they ignore the allocation scope and point to the dedicated queries; regenerate `schema/schema.graphql` if a description changed (depends on T027). Jira: IFC-3329

**Checkpoint**: The pool page can be built on the three queries; the queries keep the contract of `contracts/graphql-number-pool-queries.md`.

---

## Phase 5: User Story 3 - Declare the scope of a schema-defined pool (Priority: P3)

**Goal**: `parameters.allocation_scope` on a number-pool attribute creates the pool with that scope, validated against the default branch, compared by id afterwards.

**Independent Test**: `uv run pytest backend/tests/component/pools/test_schema_number_pool_scope.py backend/tests/integration/schema_lifecycle/test_number_pool_scope_schema.py -k declared`

### Tests for User Story 3

- [ ] T029 [P] [US3] Component tests in `backend/tests/component/pools/test_schema_number_pool_scope.py` using `backend/tests/helpers/number_pool.py::register_and_provision_number_pools`: a declared scope is stored as ids and names on the created pool; nodes in two sites each receive 1; a declaration naming an optional, many, path or absent element fails `SchemaBranch.validate_attribute_parameters` with the attribute and the element named; a declaration on an inherited attribute resolves on the generic (depends on T004). Jira: IFC-3351 (to reopen)
- [ ] T030 [P] [US3] Integration tests in `backend/tests/integration/schema_lifecycle/test_number_pool_scope_schema.py` (declared part, pattern of `test_number_pool_parameters_update.py`): loading a schema that declares another element, or clears the declaration, for an attribute whose pool exists is refused with the attribute named; loading on a branch a scope that names an element absent from the default branch is refused; renaming the element (id kept in the file) with the declaration unchanged is refused naming the old and the new name; renaming it with the declaration updated is accepted and the pool reads the new name. Jira: IFC-3351 (to reopen)

### Implementation for User Story 3

- [ ] T031 [US3] In `backend/infrahub/core/schema/schema_branch.py::_validate_number_pool_parameters`, apply the rules of `data-model.md` to `parameters.allocation_scope` with `AllocationScopeResolver` against the candidate schema (the default branch's schema when the load runs on a branch), requiring every name to resolve when `number_pool_id` is unset and leaving an unresolved name to the checker when it is set, raising `ValidationError` with `<kind>.<attribute>: allocation_scope: <reason>`; update the description of `NumberPoolParameters.allocation_scope` in `backend/infrahub/core/schema/attribute_parameters.py` (names resolved against the default branch, compared by id afterwards), move its update marker from `UpdateSupport.NOT_SUPPORTED` to `UpdateSupport.VALIDATE_CONSTRAINT`, add `ATTRIBUTE_PARAMETERS_ALLOCATION_SCOPE_UPDATE = "attribute.parameters.allocation_scope.update"` to `ConstraintIdentifier` in `backend/infrahub/core/validators/enum.py`, and regenerate the generated files with the commands of T007. [CLAUDE RECOMMENDED – based on how a schema load assigns ids] The candidate schema of a load holds no id for a field that the same load adds, and the resolver refuses a field with no id as not saved; so a load that adds a field and names it in `allocation_scope` would be refused, and this task must resolve such a name without an id. (depends on T008). Jira: IFC-3351 (to reopen)
- [ ] T032 [US3] In `backend/infrahub/pools/schema_number_pool_upserter.py::upsert_number_pool`, create the pool with the resolved scope in its stored form; in `backend/infrahub/pools/schema_number_pool_synchronizer.py::_update_pool_from_schema`, leave the scope untouched (depends on T031). Jira: IFC-3351 (to reopen)
- [ ] T033 [US3] In `backend/infrahub/core/validators/pool/scope.py::NumberPoolScopeChecker` (created in T037), for `attribute.parameters.allocation_scope.update`, `attribute.name.update` and `relationship.name.update` on a kind with a schema-created pool: resolve the declared names on the candidate schema, compare the ids with the stored scope, accept an equal list, refuse a cleared or different list with "can't be changed after the pool is created", and refuse an unresolved name whose stored id now carries another name with "`<old>` was renamed to `<new>`; update allocation_scope" (depends on T037). Jira: IFC-3351 (to reopen)

**Checkpoint**: A schema-created pool is scoped from its declaration and survives a rename declared under the new name.

---

## Phase 6: User Story 4 - Keep a scoped pool valid when the schema changes (Priority: P4)

**Goal**: Breaking schema changes are refused on every branch with the pool named; a rename is allowed and the stored name follows.

**Independent Test**: `uv run pytest backend/tests/unit/core/validators/test_number_pool_scope_checker.py backend/tests/component/core/constraint_validators/test_number_pool_scope.py backend/tests/integration/schema_lifecycle/test_number_pool_scope_schema.py`

### Tests for User Story 4

- [ ] T034 [P] [US4] Unit tests in `backend/tests/unit/core/validators/test_number_pool_scope_checker.py` for the checker's `supports` and its decision table against a `SchemaConstraintValidatorRequest`, without a database: each supported constraint name, a kind without a scoped pool returning no violation. Jira: IFC-3352
- [ ] T035 [P] [US4] Component tests in `backend/tests/component/core/constraint_validators/test_number_pool_scope.py` (pattern of `test_attribute_numberpool_constraints.py`): making the scoped relationship optional, changing its cardinality to many, removing it, making the scoped attribute optional, removing it, and setting `unique: true` on the tracked attribute are each refused with the pool and the element named; the generic case (the element on the generic refused, an element an implementing kind declares on its own ignored); renaming the relationship accepted (depends on T004). Jira: IFC-3352
- [ ] T036 [P] [US4] Integration tests in `backend/tests/integration/schema_lifecycle/test_number_pool_scope_schema.py` (checker part): the same refusals through the schema load API on the default branch and on a branch; renaming the relationship succeeds, the user-created pool reads the new name, and a new node still allocates per site; the schema check endpoint reports the same refusal without loading. Jira: IFC-3352

### Implementation for User Story 4

- [ ] T037 [US4] Create `backend/infrahub/core/validators/pool/scope.py` with `NumberPoolScopeChecker` (name `number_pool.scope`), supporting `attribute.optional.update`, `relationship.optional.update`, `relationship.cardinality.update`, `attribute.unique.update`, `node.attribute.remove`, `node.relationship.remove`, `attribute.name.update`, `relationship.name.update` and `attribute.parameters.allocation_scope.update`: loads the scoped pools of the kind and of the generics it inherits from in one query, indexes element ids to pools, reads the element from `request.schema_path` (never from `request.node_schema`, which may no longer hold it), and returns one `GroupedDataPaths` violation per dependent pool naming the pool and the element; create its dependency builder `backend/infrahub/dependencies/builder/constraint/schema/number_pool_scope.py` and add it to the list of `backend/infrahub/dependencies/builder/constraint/schema/aggregated.py` (depends on T005). Jira: IFC-3352
- [ ] T038 [US4] Register the new constraint names in `CONSTRAINT_VALIDATOR_MAP` of `backend/infrahub/core/validators/__init__.py` (`node.attribute.remove`, `node.relationship.remove`, `attribute.name.update`, `relationship.name.update`, `ConstraintIdentifier.ATTRIBUTE_PARAMETERS_ALLOCATION_SCOPE_UPDATE`); move the relationship `name` field of `backend/infrahub/core/schema/definitions/internal.py` from `UpdateSupport.ALLOWED` to `UpdateSupport.VALIDATE_CONSTRAINT` and regenerate `backend/infrahub/core/schema/generated/relationship_schema.py` with `uv run invoke backend.generate`; run `backend/tests/unit/core/validators` and `backend/tests/component/core/constraint_validators` to confirm the existing checkers are unaffected (depends on T037). Jira: IFC-3352
- [ ] T039 [US4] Add a `_refresh_scope_names` step to `backend/infrahub/pools/schema_number_pool_synchronizer.py::run` that, on the default branch, rewrites the stored name of each element whose name changed, for user-created and schema-created pools, using `AllocationScopeResolver.refresh_names` (depends on T008). Jira: IFC-3352

**Checkpoint**: The scope survives a rename and refuses a breaking change.

---

## Phase 7: Final testing (two branches, the known limitation, measurements)

**Purpose**: The branch seam proven end to end, and the figures of SC-005.

- [ ] T040 Functional tests in `backend/tests/functional/pools/test_numberpool_scoped_branch.py` (merge and rebase through the workflow): D1 moved to site C on `b1` counts under C on `b1` and under A on the default branch, under C only after the merge; a device created on `b2` in site A receives the lowest number free as read on `b2`; the known limitation of decision 7 asserted (R1 on `b2` and R2 on `b1`, both in site A, receive the same number and both keep it after the merges); a branch created before a scope element was added refuses the allocation naming the element and the branch, and accepts it after a rebase (depends on T021). Jira: IFC-3354
- [ ] T041 Run the manual and two-branch scenarios of `quickstart.md` on a live stack built from the branch, and the measurement table; record the ratios in `dev/specs/ifc-3185-number-pool-scopes/measurements.md`; if the Cypher order anchored on the holding objects is clearly faster, switch `reserved_values_query()` to it and update `plan.md` and `research.md` (depends on T021, T027, T040). Jira: IFC-3354

---

## Phase 8: Polish and cross-cutting work

**Purpose**: Documentation, the changelog, the SDK, and the checks before the pull request.

- [ ] T042 [P] Add a "Scope a pool" section to `docs/docs/resource-manager/allocate-number.mdx` (the three input forms, the refusal list, the refusal of `List`, `JSON` and `Any` elements, the immutability, the stale-branch refusal and the rebase) and write the guide `docs/docs/resource-manager/scoped-number-pools.mdx`: declare the scope in the schema and rename an element under its new name, read a pool with the three queries, replace per-site pools with one scoped pool, and the known limitation of decision 7 with its two-branch example; add it to `docs/sidebars.ts` after `resource-manager/allocate-number`; add an allocation-scope paragraph to the "Number pools" section of `docs/docs/resource-manager/overview.mdx`; run `uv run invoke docs.lint`. Jira: IFC-3356
- [ ] T043 [P] Extend the "Resource Pool Reservations" section of `dev/knowledge/backend/database-schema.md` with how a record's division is derived from its holding object on the request branch, why a holding object that exists only on another branch is not counted (the known limitation of decision 7), and the lock key per pool and division, without spec or ticket references. Jira: IFC-3356
- [ ] T044 Write the changelog fragments with the `creating-changelog-entries` skill: the allocation scope stored as `{id, name}` elements and fixed at creation, the scoped allocation and the lock per pool and division, the three dedicated queries, the generic queries' description notes, the pool-save refusals, the declared scope compared by id on load, the schema refusal when a scoped element would break, and the rename of a scoped element followed by the stored name; one fragment per user-visible change, at the end of the work (depends on T041). Jira: IFC-3356
- [ ] T045 SDK: infrahub-sdk-python #1371 (protocols of `CoreNumberPoolRange`, base `feature-number-pools-1.12`, merged 2026-10-08) and #1402 (`allocation_scope` as a list of strings in `infrahub_sdk/schema/generated/{contract,read,write}.py` and `infrahub_sdk/protocols.py`, base `pmi-number-pool-range-protocols`, merged 2026-10-08) are merged on the SDK side; the `allocation_scope` types do not change here (a `List` attribute on the pool, names in the parameters). PR #10949 points the `python_sdk` submodule at SDK commit `1bd89c8` (#1402, on the SDK branch `feature-number-pools-1.12`), which carries both. What remains: merge that SDK commit into `infrahub-develop`, then point the submodule at the merged commit before the feature branch merges into the release branch (depends on T007). Jira: IFC-3356
- [ ] T046 Run `/pre-ci` (format, lint, `ty`, mypy over `backend/`, generated-file and generated-doc validation) and fix what it reports; confirm `tests/e2e/resource-manager/test_number_pool.py` still passes against a stack built from the branch (depends on T044). Jira: IFC-3356

---

## Dependencies and execution order

### Phase dependencies

- **Setup (Phase 1)**: T001 first; T002, T003 after it; T004 after T003; T005 in parallel with everything
- **Foundational (Phase 2)**: depends on Phase 1; blocks every user story
- **User Story 1 (Phase 3)**: depends on Phase 2
- **User Story 2 (Phase 4)**: depends on T002 (the contract on the mock) and T016 (the division fragment) from User Story 1; otherwise independent of the rest of Phase 3
- **User Story 3 (Phase 5)**: depends on T008 (the resolver) and T037 (the checker); the allocation test of T029 needs User Story 1
- **User Story 4 (Phase 6)**: depends on T005 and T008; independent of Stories 2 and 3
- **Final testing (Phase 7)**: depends on Stories 1 and 2 (T040 on T021; T041 on T027)
- **Polish (Phase 8)**: depends on every story being complete

### User story dependencies

- **User Story 1**: starts after Phase 2; no dependency on another story
- **User Story 2**: starts once T002 and T016 exist; testable on its own with the fixtures of T004
- **User Story 3**: starts once T008 and T037 exist; testable on its own through the schema load
- **User Story 4**: starts once T008 exists; testable on its own through the schema load and check endpoints

### Within each user story

- Tests first, failing before the implementation
- Queries before node methods, node methods before GraphQL resolvers and mutations
- The existing number-pool suites run green before the story is called complete

### Parallel opportunities

- T003, T004, T005 together once T001 lands; T011 to T014 together; T022 and T023 together; T029 and T030 together; T034 to T036 together; T042 and T043 together
- Once T016 lands, User Story 2's queries (T024, T025) can proceed while User Story 1 finishes T017 to T021
- User Story 4 can be developed in parallel with Stories 2 and 3 by a second developer; User Story 3's T033 waits for T037

---

## Parallel example: User Story 1

```bash
# The four test files of User Story 1 together:
Task: "Rewrite the scope mutation tests in backend/tests/component/graphql/resource_manager/number_pools/test_pool_allocation_scope.py"
Task: "Component tests of the scoped free and used queries in backend/tests/component/core/resource_manager/test_number_pool_scope.py"
Task: "Rendering test of the shared fragment in backend/tests/unit/core/test_resource_manager_query.py"
Task: "Component tests of allocation per division in backend/tests/component/core/resource_manager/test_number_pool_scope_allocation.py"
```

---

## Implementation strategy

### First deliverable (User Story 1 only)

1. Phase 1 and Phase 2
2. Phase 3
3. Stop and validate: a scoped pool allocates per division through the API, unscoped pools unchanged

### Incremental delivery

1. Phase 1 and 2: the mock carries the final contract; the scope exists in its stored shape and validates
2. User Story 1: scoped allocation and locks
3. User Story 2: the three queries read the database, which unblocks the frontend page on real data
4. User Story 3: the declared scope
5. User Story 4: the schema checker and the rename follow-up
6. Phase 7: two-branch tests and measurements
7. Phase 8: documentation, changelog, SDK

### Not in this task list

- The frontend pool form and pool page (IFC-3363).
- Search, pagination and other sort orders of the divisions list (Jira IFC-3329, out of scope).

---

## Jira tickets

| Ticket | Tasks |
|--------|-------|
| IFC-3347 (mock of the three queries) | T001, T002 |
| IFC-3348 (refuse a scope that cannot divide the pool) | T005, T008, T009, T011, T015 |
| IFC-3349 (allocate within the writer's division) | T010, T012, T013, T014, T016 to T021 |
| IFC-3329 (show usage per division) | T022 to T028 |
| IFC-3352 (refuse a schema change that breaks a scoped field) | T034 to T039 |
| IFC-3354 (final testing) | T040, T041 |
| IFC-3356 (wrap up) | T042 to T046 |
| IFC-3351 (declare the scope in the schema; to reopen and reword to decision 9) | T029 to T033 |
| No ticket | T003, T004, T006, T007 (fixtures and generated files) |
| Follow-up pull request, no ticket yet | T047 (template pools that name a scoped pool) |

Tickets of the epic with no task: IFC-3334 (done, the attribute and the parameter), IFC-3346 (the Speckit documents, this spec set), IFC-3353, IFC-3355, IFC-3357, IFC-3358 (closed as "Won't Do").

---

## Notes

- [P] tasks touch different files and do not depend on an unfinished task
- Each task names its files; a site in a file is named by its symbol
- Commit after each task or logical group; changelog fragments are written once, in T044
- Generated files are regenerated with the listed commands and committed with the change that caused them
