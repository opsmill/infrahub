# Tasks: Number pool create and edit forms with weighted ranges

**Input**: [spec.md](spec.md), [plan.md](plan.md), [data-model.md](data-model.md), [research.md](research.md), [contracts/graphql-operations.md](contracts/graphql-operations.md), [quickstart.md](quickstart.md), [critiques/critique-20261008.md](critiques/critique-20261008.md)

**Tests**: requested (FR-014, constitution IV). Within each task, write the test first and see it fail, then implement.

Paths without a prefix are under `frontend/app/src/entities/resource-manager/`.

Rules for every task: follow `frontend/app/AGENTS.md`, `dev/guidelines/frontend/*.md`, `dev/knowledge/frontend/entities-structure.md`; component tests follow `dev/guides/frontend/writing-component-tests.md` (one GIVEN/WHEN/THEN each, query by role or label); e2e follows `dev/guides/frontend/writing-e2e-tests.md`. No manual memoization (React Compiler). Comments only for a non-obvious why, one sentence.

## Phase 1: Setup

- [X] T001 Create the domain types `RangeRow`, `StoredRange`, `RangeUpdate`, `RangeInput`, `RangeChanges`, `RangeRowErrors` and `NumberPoolForEditing` in `domain/model/number-pool-range.ts`, and `ScopeCandidate` in `domain/model/scope-candidate.ts`, exactly as described in data-model.md "Domain types"

## Phase 2: Foundational (blocks all user stories)

- [X] T002 [P] Write `domain/rules/validate-range-rows.test.ts` then implement `validateRangeRows` and `getRangeClipHint` in `domain/rules/validate-range-rows.ts` per data-model.md: whole-number parsing (`^-?\d+$`, safe integer; reject `"1e3"`, `"1.0"`, `""`), negative bounds allowed, end lower than start, weight empty or integer ≥ 0, overlap naming the other range "Overlaps <start> – <end>" on both rows including identical bounds, clip hint text "Clipped to <a> – <b> by the <attribute> limits" with thousands separators, `null` when inside limits or when limits are absent
- [X] T003 [P] Write `domain/rules/plan-range-changes.test.ts` then implement `sortStoredRanges`, `diffRanges` and `matchRowsToStored` in `domain/rules/plan-range-changes.ts` per data-model.md: sort weight descending with `null` last then start; diff groups deletes, smaller (new bounds inside old, including weight-only), larger, creates; unchanged rows produce nothing; empty weight becomes `null`; cases include 1–10/11–20 becoming 1–15/16–20; `matchRowsToStored` links unlinked rows to stored ranges with equal bounds and leaves other values as typed
- [X] T004 [P] Add the typed query `GetNumberPoolForEditing` in `api/get-number-pool-for-editing-from-api.ts` per contracts/graphql-operations.md (confirm field names and the `ranges` page size in `schema/schema.graphql`; pass an explicit limit if the default can truncate), the mapper `toNumberPoolForEditing` in `api/number-pool.mappers.ts` with `api/number-pool.mappers.test.ts` (test first), the use-case `domain/use-cases/get-number-pool-for-editing.ts`, the query hook `ui/queries/get-number-pool-for-editing.query.ts`, and the key in `ui/queries/resource-manager.query-keys.ts`; run `cd frontend/app && pnpm codegen` if the typed document requires it
- [X] T005 [P] Add `api/create-number-pool-range-from-api.ts`, `api/update-number-pool-range-from-api.ts` and `api/delete-number-pool-range-from-api.ts` that pass a `processErrorMessage` which does not toast (pattern: `entities/tasks/api/retry-task-from-api.ts`); write `domain/use-cases/apply-number-pool-range-changes.test.ts` (mocked api: calls in the order deletes, smaller, larger, creates; stops at the first rejection of any kind; returns the count applied and the message, a generic message for non-GraphQL errors) then implement `applyNumberPoolRangeChanges` in `domain/use-cases/apply-number-pool-range-changes.ts`; add `ui/queries/apply-number-pool-range-changes.mutation.ts` that invalidates once after the last call: the editing query key, `objectQueryKeys.all` and the pool utilization query key (check which key the hook around `api/get-pool-utilization-from-api.ts` uses in `ui/queries/resource-manager.query-keys.ts`; add one there if none exists)

**Checkpoint**: rules, api, use-cases and queries exist and are unit tested.

## Phase 3: User Story 1 - Create a number pool with several ranges (P1) 🎯 MVP

**Goal**: create a pool with kind, attribute, name, description and several weighted ranges.
**Independent test**: create a pool with two ranges of different weights and view both on the pool.

- [X] T006 [P] [US1] Write `ui/number-pool-form/ranges-field.test.tsx` (using `tests/components/form.story.tsx` `TestForm`) then implement `ui/number-pool-form/ranges-field.tsx` with `useFieldArray` (`rangeId` in the row value; field array key left to the library): add and remove rows, labelled Start, End and Weight inputs, errors from `validateRangeRows` shown on the row after blur or submit and blocking submit, clip hint from `getRangeClipHint` for the currently selected attribute's `min_value`/`max_value` (non-blocking), the no-range hint (non-blocking), new rows appended and no reorder while typing; layout and texts from the prototype `editor.tsx` `RowsEditor` and `RangesSectionHeader` (`git show origin/bab-proto-number-pool:frontend/app/src/pages/proto/number-pool/editor.tsx`); a one-sentence why-comment on the plain-string row shape
- [X] T007 [P] [US1] Write `ui/number-pool-form/allocates-block.test.tsx` then implement `ui/number-pool-form/allocates-block.tsx`: one layout ("What it allocates": Node, Attribute, Scoped by) with an input variant (existing node and number-attribute comboboxes moved out of `NodeAttributesSelects` in `ui/number-pool-form.tsx`) and a read-only variant (text and badges, no controls, labels without the required asterisk); changing the kind clears attribute and scope; leave a slot for the scope field (filled in T011)
- [X] T008 [US1] Rewrite the create path of `ui/number-pool-form.tsx` with `ui/number-pool-form.test.tsx` written first (mock the generic create hook and `apply-number-pool-range-changes.mutation.ts`): remove `start_range`/`end_range` (FR-013); remove `ranges` from the data passed to `getCreateMutationFromFormDataOnly`; create the pool, then apply the range creates; empty weight sent as `null`; on success call `onSuccess`; keep the file under about 300 lines
- [X] T009 [US1] FR-015 in `ui/number-pool-form.tsx`: on a range refusal after the pool was created, keep `createdPoolId` in component state, derive `poolId = currentObject?.id ?? createdPoolId`, refetch with `get-number-pool-for-editing.query.ts`, link rows with `matchRowsToStored`, keep every row as typed, show one inline alert above the ranges, and make the next save take the edit path; tests in `ui/number-pool-form.test.tsx`: second save does not create a second pool and sends only the remaining ranges, message shown once

**Checkpoint**: User Story 1 works on its own.

## Phase 4: User Story 2 - Change the ranges of an existing pool (P1)

**Goal**: edit name, description and ranges; kind, attribute and scope read-only.
**Independent test**: open a pool with one range, add a second, change the first weight, save, view both.

- [X] T010 [US2] Edit path in `ui/number-pool-form.tsx` with tests first in `ui/number-pool-form.test.tsx` (mock the generic update hook, the editing query and the range mutation): load with `get-number-pool-for-editing.query.ts` and `sortStoredRanges`; read-only allocates block (T007) in the same layout as create; update name and description only when changed; remove the early return that skipped a save with no pool field change; apply `diffRanges` through the range mutation; refused save (FR-009) keeps rows as typed, refetches, links applied rows, shows one alert, next save sends only what remains; test cases: name-only change sends no range call, only changed ranges sent in order, refusal mid-sequence, delete of a range that no longer exists (stale baseline)

**Checkpoint**: User Stories 1 and 2 work.

## Phase 5: User Story 3 - Set the allocation scope when creating a pool (P2)

**Goal**: choose required fields of the kind as the allocation scope at creation; view it as badges in edit.
**Independent test**: create a pool scoped by a required relationship and view the scope in edit.

- [X] T011 [P] [US3] Write `domain/rules/get-scope-candidates.test.ts` then implement `getScopeCandidates(schema: ModelSchema, nodeAttribute)` in `domain/rules/get-scope-candidates.ts` per data-model.md, using fake schemas from `frontend/app/tests/fake/schema.ts`: required attribute pickable; optional, List and JSON attributes, cardinality-many relationships, optional cardinality-one relationships and the pool's own attribute not pickable, each with its reason; a node schema and a generic schema; no paths into related nodes; all scope rules in this one file
- [X] T012 [US3] Write `ui/number-pool-form/scope-field.test.tsx` then implement `ui/number-pool-form/scope-field.tsx` composed from `@infrahub/ui` parts as in the prototype `scope-field.tsx` `ScopeField` (layout only; its `KINDS` data is not used): schema from `useSchema(kind)` for node or generic kinds, candidates from `getScopeCandidates`, disabled options with reasons, warning when the attribute is unique on its own and a scope is chosen, empty state when no field is pickable, stores bare field names; plug it into the slot of `ui/number-pool-form/allocates-block.tsx` (input variant) and render the read-only badges in the read-only variant; send `allocation_scope` on create in `ui/number-pool-form.tsx`; changing the attribute removes it from the chosen scope

## Phase 6: User Story 4 - View the ranges of a pool defined in the schema (P3)

**Goal**: ranges of a schema pool are read-only with a note; name and description stay editable.
**Independent test**: open the `service_identifier` pool and view its ranges as text.

- [X] T013 [US4] In `ui/number-pool-form/ranges-field.tsx` and `ui/number-pool-form.tsx`, when `poolType` is "Schema", render the ranges as read-only text with the note that they are changed in the schema on the default branch, and send no range call on save; tests first in `ui/number-pool-form/ranges-field.test.tsx` and `ui/number-pool-form.test.tsx`

## Phase 7: Polish & cross-cutting

- [ ] T014 [P] Update e2e tests that fill "Start range *"/"End range *": `tests/e2e/resource-manager/test_number_pool.py` (`test_create_number_pool_for_generic_schema`, `test_create_number_pool_for_node_schema`; make `test_update_form_should_not_include_node_and_attribute_selects` open the edit form and assert read-only node and attribute text), `tests/e2e/object-template/test_template_with_number_pool.py` (one row 100–200) and `tests/e2e/tutorial/guides/test_resource_manager_guide.py::test_number_pool` (one row 100–1000)
- [X] T015 [P] Add e2e tests in `tests/e2e/resource-manager/test_number_pool.py`: `test_create_pool_with_several_ranges_then_edit` (FR-014) and `test_schema_defined_pool_ranges_are_read_only` (the `service_identifier` pool from `models/base/service.yml`); each test creates its own data, no serial mode, no `time.sleep`
- [X] T016 [P] Add a towncrier fragment in `changelog/` (use the `creating-changelog-entries` skill) describing the multi-range create and edit forms and the allocation scope picker
- [X] T017 (after T014) Update the web-interface steps in `docs/docs/resource-manager/allocate-number.mdx` (ranges instead of "Start range") and refresh the screenshot `docs/docs/media/guides/resources-manager/resource_manager_pool_vlan.png` produced by the tutorial e2e test; written through the `opsmill-docs-writing-infrahub-docs` skill in phase 4.6
- [ ] T018 Run the quickstart checks: `pnpm vitest run src/entities/resource-manager`, `node_modules/.bin/biome ci .` from `frontend/`, `pnpm knip`, `pnpm exec betterer ci`, and the e2e files from T014/T015

## Dependencies

- T001 → T002–T005 and T011 (parallel) → T006, T007 (parallel) → T008 → T009 → T010 → T012 → T013 → T014–T016 (parallel) → T017 → T018.
- `ui/number-pool-form.tsx` is touched by T008, T009, T010, T012 and T013: these run in sequence.
- US2 depends on US1's form rewrite; US3 and US4 depend on the allocates block and the ranges field.

## Parallel examples

- Wave 1: T002, T003, T004, T005, T011 (no shared file).
- Wave 2: T006 and T007.
- Wave 4: T014, T015, T016; then T017 (needs the screenshot from T014).

## Implementation strategy

MVP is User Story 1 (T001–T009): a pool can be created with several ranges. User Story 2 completes the P1 scope; Stories 3 and 4 follow; Phase 7 is required before the PR (e2e tests break as soon as the old fields disappear).
