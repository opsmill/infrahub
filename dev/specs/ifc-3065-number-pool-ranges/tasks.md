# Tasks: Number Pools P1 — Weighted Ranges

**Input**: Design documents from `dev/specs/ifc-3065-number-pool-ranges/`

**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/

**Tests**: Included. The constitution requires tests at the matching level for every feature; each phase lists its tests before its implementation tasks.

**Organization**: One phase per pull request of a `gh stack`, bottom to top. Each phase is green and coherent on its own, and each becomes one Jira sub-task of Epic IFC-3065. User-story labels are kept for traceability to spec.md.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: US1 to US5 from spec.md
- Paths are repository-relative

## Stack overview

| PR | Phase | Delivers | Frontend impact |
|----|-------|----------|-----------------|
| 1 | GraphQL contract and core schema | Range kind, `ranges` relationship, deprecated shorthand, `@deprecated` propagation, one utilization entry per range | Full contract available; frontend work can start against this branch |
| 2 | Migration and shorthand mirror | One range per existing pool, shorthand kept in sync | none |
| 3 | Allocation over ranges | Calculator, range-list queries, weighted fall-through, effective-space utilization | Utilization figures become exact |
| 4 | User pool mutations | Shorthand rules by range count, range mutation class, pool lock, overlap refusals | Refusal messages final |
| 5 | Schema-created pools and published contract | `parameters.ranges`, constraint validation, upserter, synchronizer, guards, warnings, SDK contract | REST types and `parameters.ranges` in the schema |
| 6 | Finishing | Frontend guard, docs, benchmark, changelog | Attribute display renders ranges |

PR 2 must land before PR 3: without the migration, allocation over ranges would see empty pools. PR 1 ships the generated range mutations without the schema-pool guard; the guard arrives in PR 5.

---

## Phase 1: PR 1 — GraphQL contract and core schema

**Goal**: publish the whole GraphQL surface so the frontend can start; no change to allocation behaviour

**Independent Test**: `cd backend && uv run pytest tests/component/graphql/test_manager.py tests/component/graphql/resource_manager/ tests/component/core/resource_manager/test_number_pool.py -k "deprecat or utilization or range"`

### Tests

- [ ] T001 [P] [US5] Component test in `backend/tests/component/graphql/test_manager.py`: an attribute and a relationship with `deprecation` set produce `deprecation_reason` on the object type field, the interface field, the relationship field, and the create/update/upsert input fields
- [ ] T002 [P] [US1] Adjust `test_resource_utilization` in `backend/tests/component/core/resource_manager/test_number_pool.py` to the new shape: one edge per range (`kind: CoreNumberPoolRange`, `display_label "<start>-<end>"`, `weight`), `count` = number of ranges, pool totals unchanged
- [ ] T003 [P] [US3] Component test in new `backend/tests/component/graphql/resource_manager/test_number_pool_range.py`: a `CoreNumberPoolRange` is created through the generated mutation with a `pool` parent and appears under the pool's `ranges`; the pool still reads its shorthand

### Implementation

- [ ] T004 Read `dev/guidelines/backend/python.md`, `dev/guidelines/backend/exceptions.md`, `dev/knowledge/backend/query-pattern.md` and `dev/knowledge/backend/code-generation.md` before touching backend code
- [ ] T005 Add `InfrahubKind.NUMBERPOOLRANGE = "CoreNumberPoolRange"` in `backend/infrahub/core/constants/infrahubkind.py`
- [ ] T006 Define `core_number_pool_range` (`NumberPoolRange`, `Core`, `AGNOSTIC`, inherits `WEIGHTED_POOL_RESOURCE`, attributes `start`/`end`, relationship `pool` cardinality one kind `PARENT` identifier `numberpool__range`, `include_in_menu=False`, `generate_profile=False`, display labels start/end) in `backend/infrahub/core/schema/definitions/core/resource_pool.py` and register it in `backend/infrahub/core/schema/definitions/core/__init__.py`
- [ ] T007 On `core_number_pool` in `resource_pool.py`: add `ranges` relationship (peer `NUMBERPOOLRANGE`, many, optional, `COMPONENT`, agnostic, identifier `numberpool__range`); set `start_range` and `end_range` `optional=True` with a `deprecation` message pointing at `ranges`
- [ ] T008 In `InfrahubNumberPoolMutation.mutate_create` (`backend/infrahub/graphql/mutations/resource_manager.py`): replace the unconditional `data["start_range"]` reads with a `ValidationError` when either bound is missing, so the now-optional inputs cannot crash the mutation (relaxed in PR 4)
- [ ] T009 [US5] Pass `deprecation_reason=attr.deprecation` / `rel.deprecation` in `generate_graphql_object`, `generate_interface_object`, the relationship field construction in `generate_object_types`, and `generate_graphql_mutation_create_input` / `_update_input` / `_upsert_input` in `backend/infrahub/graphql/manager.py`
- [ ] T010 [US1] Update `resolve_number_pool_utilization` in `backend/infrahub/graphql/queries/resource_manager.py` to return one edge per range with per-range figures computed by filtering the existing allocated values on the range bounds; pool totals as today; `count` = number of ranges; an empty range set returns no edge and the pool totals
- [ ] T011 Regenerate `backend/infrahub/core/protocols.py` (`uv run invoke backend.generate`), `schema/schema.graphql` (`uv run invoke schema.generate-graphqlschema`) and `frontend/app/src/shared/api/graphql/generated/` (`cd frontend/app && pnpm codegen`); confirm `@deprecated` on the shorthand in the object type, interface and inputs

**Checkpoint**: frontend has the final GraphQL contract; existing pools behave as before (zero ranges, shorthand drives allocation)

---

## Phase 2: PR 2 — Migration and shorthand mirror

**Goal**: every existing pool gets one range; the shorthand becomes a mirror of the range set

**Independent Test**: `cd backend && uv run pytest tests/component/core/migrations/graph/m079_number_pool_ranges && uv run pytest tests/unit/core/graph/test_graph_version.py`

### Tests

- [ ] T012 [P] [US2] Component tests in `backend/tests/component/core/migrations/graph/m079_number_pool_ranges/test_migration.py`: pre-79 fixture with a user pool and a schema pool holding allocations; after the run each pool has one range with the old bounds and no weight, allocated values and utilization unchanged, shorthand still populated; second run creates no range; `validate_migration` passes; the range kind and the `ranges` relationship exist in the database schema
- [ ] T013 [P] [US2] Component test in `backend/tests/component/core/resource_manager/test_number_pool.py`: `sync_shorthand_from_ranges` sets the bounds for one range and `None` for zero or two ranges

### Implementation

- [ ] T014 [US2] Add `load_ranges(db) -> list[PoolRange-like]` and `sync_shorthand_from_ranges(db, pool, ranges)` on `CoreNumberPool` in `backend/infrahub/core/node/resource_manager/number_pool.py` (the single writer of the shorthand)
- [ ] T015 [US2] Create `backend/infrahub/core/migrations/graph/m079_number_pool_ranges/` (`__init__.py`, `migration.py`) as an `ArbitraryMigration`: bootstrap the range kind and the `ranges` relationship into the database schema when absent (m073 pattern), create one range per live pool without ranges through the Node API, call the shorthand sync, `validate_migration` counts pools without ranges, `minimum_version = 78`
- [ ] T016 [US2] Bump `GRAPH_VERSION = 79` in `backend/infrahub/core/graph/__init__.py`

**Checkpoint**: upgrade path verified; allocation still reads the shorthand, which the mirror keeps correct

---

## Phase 3: PR 3 — Allocation over ranges

**Goal**: allocation, size, utilization and fullness come from the effective space

**Independent Test**: `cd backend && uv run pytest tests/unit/pools/test_number_ranges.py tests/component/core/resource_manager/ -k "ranges or query"`

### Tests

- [ ] T017 [P] [US1] Unit tests for the calculator in `backend/tests/unit/pools/test_number_ranges.py`: ordering by weight then start, `None` weight as 0, clipping, exclusions splitting a range, exclusions outside every range subtract nothing, range clipped to nothing yields no segment, zero ranges gives size 0, `range_for`
- [ ] T018 [P] [US1] Component tests for the range-list queries in `backend/tests/component/core/resource_manager/test_number_pool_query.py`: used/allocated/taken filtered by a two-range list, values in the gap excluded, empty list never queried
- [ ] T019 [P] [US1] Component test class `TestNumberPoolRangesAllocation` in `backend/tests/component/core/resource_manager/test_number_pool.py`: pool 100-200 (weight 10) + 205-300, 101 allocations ascending from 100-200, nothing in 201-204, utilization 101 of 197, next is 205, not full until 300; equal weights lowest start first; weight raised on a partially drained pool redirects the next allocation; exhausted space raises `PoolExhaustedError`
- [ ] T020 [P] [US1] Component test in the same file: excluded values outside every range leave size unchanged; excluded values inside a range are skipped and subtracted; `min_value`/`max_value` clip a range and a range clipped to nothing counts as exhausted; no `ZeroDivisionError`; zero ranges gives 0 of 0
- [ ] T021 [P] [US1] Component test: hand-set values on a unique attribute are skipped across both ranges (generalised `get_taken`)

### Implementation

- [ ] T022 [P] [US1] Create `backend/infrahub/pools/number_ranges.py` with frozen `PoolRange`, `EffectiveSegment`, and `EffectiveSpace` (clip to `[min_value, max_value]`, subtract excluded singles and ranges, order `(-weight, start)`, `segments`, `size`, `as_query_ranges()`, `contains()`, `range_for()`, `is_empty`) per data-model.md
- [ ] T023 [P] [US1] Replace `$start_range`/`$end_range` with `$ranges: list[list[int]]` and `any(r IN $ranges WHERE v >= r[0] AND v <= r[1])` in `NumberPoolGetUsed`, `NumberPoolGetAllocated`, `NumberPoolGetTaken` in `backend/infrahub/core/query/resource_manager.py`; make both bounds required on `NumberPoolGetFree`
- [ ] T024 [US1] Add `build_effective_space(db, attribute)` on `CoreNumberPool`; `get_used`/`get_taken` pass `space.as_query_ranges()` and return early on an empty space; rewrite `get_next` to walk `space.segments` with `NumberPoolGetFree(cursor, segment.end)`, skipping hand-set values by advancing the cursor, falling through on `None`, raising `PoolExhaustedError` when no segment yields; delete the `skip_excluded` closure and `get_attribute_nb_excluded_values`
- [ ] T025 [US1] Rework `NumberUtilizationGetter` in `backend/infrahub/pools/number.py` to take the `EffectiveSpace`: `total_pool_size = space.size`, ratios return `0.0` on size 0, used values grouped by `space.range_for`
- [ ] T026 [US1] Replace the bounds filter of T010 in `resolve_number_pool_utilization` with the getter's per-range figures; `weight = allocation_weight or 0`

**Checkpoint**: multi-range allocation and exact utilization on pools created through the Node API

---

## Phase 4: PR 4 — User pool mutations

**Goal**: ranges and the shorthand are manageable through GraphQL with the specified refusals

**Independent Test**: `cd backend && uv run pytest tests/component/graphql/resource_manager/ tests/functional/pools/test_numberpool_ranges.py`

### Tests

- [ ] T027 [P] [US2] Component tests in `backend/tests/component/graphql/resource_manager/test_resource_manager.py`: read of a single-range pool returns the shorthand; shorthand write on a 1-range pool rewrites in place (same range id, weight kept); shorthand write on a 0-range pool creates the range; create with neither spelling yields a zero-range pool; update `test_test_number_pool_creation_errors` and `test_test_number_pool_update` for the optional shorthand
- [ ] T028 [P] [US3] Component tests in `backend/tests/component/graphql/resource_manager/test_number_pool_range.py`: create a second range on a live pool (size grows, allocations untouched); remove 205-300 holding 250 (succeeds, utilization 101 of 101, 250 never handed out); re-add (250 counts, 102 of 197); overlap and backwards range refused with named ranges; two pools on one attribute may overlap; last range removed leaves a legal pool
- [ ] T029 [P] [US3] Component tests in the same file: shorthand write on a 2-range pool refused with a message listing both ranges by bounds and id, pool untouched; shorthand plus `ranges` in one write refused; `ranges` supplied without shorthand accepted
- [ ] T030 [P] [US3] Component test asserting the shorthand mirror invariant after range create, update, delete, pool shorthand write and pool `ranges` edit
- [ ] T031 [P] [US3] Functional test `backend/tests/functional/pools/test_numberpool_ranges.py` (`TestInfrahubApp`): user pool created with two ranges through GraphQL, allocation via the SDK across the fall-through, range removed and re-added, figures checked through the utilization query

### Implementation

- [ ] T032 [US3] Add `InfrahubNumberPoolRangeMutation` in `backend/infrahub/graphql/mutations/resource_manager.py`: pool lock (`resource_pool.<pool_id>`), parent pool lookup, `start <= end`, overlap check naming clashing ranges, `sync_shorthand_from_ranges` after create/update/delete; register it under `InfrahubKind.NUMBERPOOLRANGE` in the `mutation_map` of `backend/infrahub/graphql/manager.py`
- [ ] T033 [US2] In `InfrahubNumberPoolMutation.mutate_create`: drop the T008 guard; accept shorthand, `ranges`, or neither; refuse shorthand combined with `ranges`; create the single range from the shorthand; keep the existing bound checks; take the pool lock when the shorthand or `ranges` is present
- [ ] T034 [US3] In `InfrahubNumberPoolMutation.mutate_update`: pool lock; range-count rule for the shorthand (0 creates, 1 rewrites in place, more than 1 refused with the range list per contract); refuse shorthand combined with `ranges`; overlap validation after a `ranges` edit; `sync_shorthand_from_ranges`

**Checkpoint**: user-created pools fully manageable through GraphQL

---

## Phase 5: PR 5 — Schema-created pools and published contract

**Goal**: `parameters.ranges` end to end, both write surfaces guarded, deprecation warnings, SDK contract

**Independent Test**: `cd backend && uv run pytest tests/unit/core/schema/test_number_pool_parameters.py tests/component/pools tests/component/core/constraint_validators/test_attribute_numberpool_constraints.py tests/component/core/schema/test_attribute_parameters.py && uv run pytest tests/integration/schema_lifecycle/test_attribute_parameters_update.py`

### Tests

- [ ] T035 [P] [US2] Unit tests in `backend/tests/unit/core/schema/test_number_pool_parameters.py`: shorthand-only declaration yields one effective range; one bound resolves the other to `1` / `sys.maxsize`; neither yields `[]`; both spellings refused; `start > end` refused; overlap refused; `get_pool_size()` sums ranges; fields not rewritten by validation
- [ ] T036 [P] [US5] Unit test (same file or a schema warnings test): `SchemaRoot.gather_warnings` emits one `DEPRECATION` warning per NumberPool attribute using the shorthand and none for `ranges`
- [ ] T037 [P] [US4] Component tests in `backend/tests/component/core/constraint_validators/test_attribute_numberpool_constraints.py`: value outside every declared range refused with the object identified; value inside a second range accepted; zero ranges with held values refused; constraint name `attribute.parameters.ranges.update` resolves to the checker
- [ ] T038 [P] [US4] Component tests in `backend/tests/component/pools/test_schema_number_pool_upserter.py`: pool created from `parameters.ranges` has the range nodes with weights; from the shorthand has one range; from neither has zero ranges; shorthand synced
- [ ] T039 [P] [US4] Component tests in new `backend/tests/component/pools/test_schema_number_pool_synchronizer.py`: default-branch declaration adds, removes and reweights ranges; matched range updated in place (same id); records retained; zero ranges legal
- [ ] T040 [P] [US4] Component tests in `backend/tests/component/graphql/resource_manager/test_number_pool_range.py`: range create/update/delete on a schema pool refused pointing at the default-branch schema; pool update carrying `ranges` refused; shorthand on a multi-range schema pool gets the schema-pool message first
- [ ] T041 [P] [US4] Extend `backend/tests/component/core/schema/test_attribute_parameters.py`: both spellings refused at load; single bound loads with the old meaning; `ranges` declaration loads
- [ ] T042 [P] [US4] Extend `backend/tests/integration/schema_lifecycle/test_attribute_parameters_update.py`: a schema load that moves a range so a held value falls outside is refused; a safe range change reconciles the pool
- [ ] T043 [P] [US4] Extend `backend/tests/component/core/migrations/schema/test_node_attribute_add.py` with a `ranges` declaration: the pool is materialised with ranges and existing nodes receive values
- [ ] T044 [P] [US5] Extend `backend/tests/unit/core/schema/test_write_json_schema.py`: `start_range` / `end_range` marked `deprecated: true` with a message pointing at `ranges`

### Implementation

- [ ] T045 [US2] Change `NumberPoolParameters` in `backend/infrahub/core/schema/attribute_parameters.py`: `start_range`/`end_range` `int | None = None` with deprecation in the description, new `NumberPoolRangeParameters(HashableModel)` (`start`, `end`, `weight`, `_sort_by = ["start", "end"]`), `ranges` with `update: VALIDATE_CONSTRAINT`, `validate_ranges` rules, `effective_ranges()`, `get_pool_size()`
- [ ] T046 [US4] Add `ConstraintIdentifier.ATTRIBUTE_PARAMETERS_RANGES_UPDATE = "attribute.parameters.ranges.update"` in `backend/infrahub/core/validators/enum.py`; register `AttributeNumberPoolChecker` for it in `backend/infrahub/core/validators/__init__.py`; extend `supports()`
- [ ] T047 [US4] Rewrite `AttributeNumberPoolUpdateValidatorQuery` in `backend/infrahub/core/validators/attribute/number_pool.py` to bind `$ranges` from `effective_ranges()` and return values where `none(r IN $ranges WHERE value >= r[0] AND value <= r[1])`
- [ ] T048 [US4] In `SchemaNumberPoolUpserter.upsert_number_pool` (`backend/infrahub/pools/schema_number_pool_upserter.py`): create range nodes from `effective_ranges()` after the pool, same lock and timestamp, then sync the shorthand
- [ ] T049 [US4] In `SchemaNumberPoolSynchronizer._update_pool_from_schema` (`backend/infrahub/pools/schema_number_pool_synchronizer.py`): positional reconciliation of declared versus existing ranges (update in place, create, delete), then sync the shorthand
- [ ] T050 [US4] Extend the schema-pool guard in `InfrahubNumberPoolMutation.mutate_update` to `ranges`, and make `InfrahubNumberPoolRangeMutation` refuse create/update/delete when the parent pool is `pool_type: Schema`, both with the existing default-branch message
- [ ] T051 [US5] Add the shorthand `DEPRECATION` warning to `SchemaRoot.gather_warnings` in `backend/infrahub/core/schema/__init__.py`
- [ ] T052 [US5] Add `start_range` / `end_range` to `DEPRECATED_MESSAGES` in `backend/infrahub/core/schema/write_json_schema.py`
- [ ] T053 Extend `tasks/backend.py`: `NumberPoolRange` family (`start`, `end` required Number, `weight` optional Number), `number_pool_parameters_fields` with optional deprecated `start_range`/`end_range` and `ranges` as a list of the family through `_sdk_extension_field`; adjust `tasks/docs.py` so an absent default renders blank
- [ ] T054 Regenerate the SDK models in `python_sdk/infrahub_sdk/schema/generated/` and `python_sdk/infrahub_sdk/protocols.py`; update `python_sdk/tests/unit/test_schema_offline_validation.py`; push the submodule commit and open the SDK PR against `opsmill/infrahub-sdk-python` `stable`; bump the submodule pointer here once it is merged
- [ ] T055 Regenerate and commit `schema/openapi.json`, `frontend/app/src/shared/api/rest/types.generated.ts`, `docs/docs/snippets/attribute-kind-params.mdx` and the reference docs (`uv run invoke schema.generate-jsonschema`, `docs.generate`, `cd frontend/app && pnpm codegen`); run `uv run invoke docs.validate`

**Checkpoint**: schema-created pools carry ranges end to end; published contract regenerated

---

## Phase 6: PR 6 — Finishing

**Goal**: consumer tolerance, docs, measurement, changelog

**Independent Test**: `cd frontend/app && pnpm test -- attribute-display && cd ../.. && uv run invoke docs.lint`

### Tests

- [ ] T056 [P] [US5] Frontend Vitest for `frontend/app/src/entities/schema/ui/attribute-display.tsx`: renders with `start_range`/`end_range` absent and with `ranges` present
- [ ] T057 [P] [US1] Benchmark `backend/tests/query_benchmark/test_number_pool_allocation.py`: 4094-number pool in four ranges fully allocated, one `get_next` with fall-through, `EXPLAIN` of `NumberPoolGetFree` on the last segment; record the figure for the PR description

### Implementation

- [ ] T058 [P] [US5] Null-guard and render `ranges` in `frontend/app/src/entities/schema/ui/attribute-display.tsx`; update the fixture in `frontend/app/src/entities/schema/ui/schema-viewer.test.tsx`; check the resource-manager utilization view against one edge per range
- [ ] T059 [P] [US5] Restrict the `process_deprecations` log in `backend/infrahub/core/schema/schema_branch.py` to kinds outside the `Core` namespace; keep forcing `optional=True`
- [ ] T060 [P] Update `docs/docs/schema/number-pool.mdx` (declare `parameters.ranges`, shorthand deprecated) and `docs/docs/resource-manager/allocate-number.mdx` (create a user pool with ranges, weights, per-range utilization) following `dev/guidelines/documentation.md`
- [ ] T061 Changelog fragments in `changelog/` with the `creating-changelog-entries` skill, one per row of the spec's changelog table; Vale-lint them
- [ ] T062 Run `/pre-ci` on the whole stack and every command in `quickstart.md`; record the outcomes and the approvals list from the spec in the PR descriptions

---

## Dependencies & Execution Order

### Between PRs

- PR 1 → PR 2 → PR 3 → PR 4 → PR 5 → PR 6, merged bottom to top with `gh stack`
- PR 2 before PR 3 is mandatory (migration before allocation reads ranges)
- The SDK PR (T054) is opened during PR 5 and must merge before PR 5's submodule pointer bump

### Within a PR

- Tests written first and failing before the implementation task they cover
- Schema definitions before Node API code; queries before allocation; allocation before resolvers

### Parallel Opportunities

- All `[P]` test tasks of a phase together
- PR 3: T022 and T023 in parallel, then T024
- PR 6: T056 to T060 in parallel

---

## Jira mapping

One sub-task of IFC-3065 per phase, scoped by the task identifiers of that phase:

| Sub-task | Tasks |
|----------|-------|
| PR 1 GraphQL contract and core schema | T001 to T011 |
| PR 2 Migration and shorthand mirror | T012 to T016 |
| PR 3 Allocation over ranges | T017 to T026 |
| PR 4 User pool mutations | T027 to T034 |
| PR 5 Schema-created pools and published contract | T035 to T055 |
| PR 6 Finishing | T056 to T062 |

---

## Notes

- Tasks touching generated files (T011, T054, T055) never hand-edit them
- Every `try`/`except` follows `dev/guidelines/backend/exceptions.md`
- Changelog fragments are written once, in PR 6, not per intermediate PR
- Stack operations follow `gh stack`; never a plain `gh pr create` on a stack branch
