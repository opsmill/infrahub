---
description: "Task list for the number pool create and edit form"
---

# Tasks: Number pool create and edit form

**Input**: Design documents from `specs/ifc-3365-number-pool-form/`

**Prerequisites**: [plan.md](plan.md), [spec.md](spec.md), [research.md](research.md), [data-model.md](data-model.md), [contracts/number-pool-form.md](contracts/number-pool-form.md), [quickstart.md](quickstart.md)

**Tests**: Included.
- SC-005 requires every acceptance scenario to pass as an end-to-end test.
- Constitution IV requires unit, component and e2e tests for user-facing features.
- Write each test before the code it covers, and see it fail first.

**Organization**: Tasks are grouped by user story. Both stories ship in the same release (spec), but each phase can be tested on its own.
- During User Story 1, only *create* goes to the new form. The old form keeps handling edit.
- User Story 2 moves edit to the new form and deletes the old one.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependency on an unfinished task)
- **[Story]**: The user story the task belongs to (US1, US2)

## Path Conventions

- Frontend paths are relative to `frontend/app/`. `RM` stands for `frontend/app/src/entities/resource-manager`.
- Tests sit next to their source as `*.test.ts` or `*.test.tsx`. Test data comes from the factories in `frontend/app/tests/fake/`.
- E2E paths are relative to the repository root.
- Follow:
  - `dev/guides/frontend/writing-unit-tests.md`;
  - `dev/guides/frontend/writing-component-tests.md` (`render` from `tests/components/render.tsx`, bare `// GIVEN` / `// WHEN` / `// THEN` markers, at most one of each per test);
  - `dev/guidelines/frontend/object-forms.md`.
- Code style:
  - Import React as `import React from "react"` and call `React.useState` and the other hooks through it. No named imports from `"react"`.
  - No manual `useMemo` or `useCallback`: the React Compiler is enabled.
  - Import remeda as `import * as R from "remeda"`.
  - Use lucide-react icons.

---

## Phase 1: Setup

**Purpose**: Separate the existing details page components from the new form, and clear prototype wiring out of the API files.

- [X] T001 Move the seven details page components and their tests from `RM/ui/number-pool/` to `RM/ui/number-pool/details/` with `git mv`, without editing their content:
  - `number-pool-actions-menu`
  - `number-pool-allocation-filters-bar`
  - `number-pool-allocations-card`
  - `number-pool-allocations-table`
  - `number-pool-header`
  - `number-pool-ranges-card`
  - `number-pool-usage-bar`

  Then update every import of them: the moved files' imports of each other, `src/pages/resource-manager/number-pool-details.tsx` and `src/pages/resource-manager/number-pool-details.test.tsx`.
- [X] T002 Run `pnpm test src/entities/resource-manager src/pages/resource-manager` and `pnpm knip` from `frontend/app/`, and confirm that every test passes and no unused file is reported. Commit T001 on its own, so the move is reviewed apart from new code.
- [X] T003 (Skipped: the user chose to keep the edits.) Ask the user before reverting the uncommitted `poolId: "mock-unscoped"` edits. They are the user's local changes, in:
  - `RM/api/get-number-pool-utilization-from-api.ts`
  - `RM/api/get-number-pool-allocations-from-api.ts`
  - `RM/api/get-number-pool-allocation-count-from-api.ts`

  Once the user agrees, restore the committed `poolId` variable in each file.

**Checkpoint**: The details page works from its new folder, and the API files read real pools.

---

## Phase 2: Foundational

**Purpose**: The toast setting on the generic save path, and the three number pool rules. Both stories depend on them.

### Toast setting on the generic object save (contract: "Frontend interface: toast setting on the generic object save")

- [X] T004 [P] Write a test in `src/entities/nodes/object/api/create-object-from-api.test.ts`:
  - When `createObjectFromApi` gets a `processErrorMessage` function, the request it sends to `graphqlClient.mutate` carries it on `context`, next to `branch`.
  - Without the function, `context` holds only `branch`.

  Mock `graphqlClient` as the existing tests in `src/shared/api/graphql/client.test.ts` do.
- [X] T005 [P] Write the same test for `updateObjectFromApi` in `src/entities/nodes/object/api/update-object-from-api.test.ts`.
- [X] T006 Add an optional `processErrorMessage?: (message: string) => void` to `CreateObjectFromApiParams` in `src/entities/nodes/object/api/create-object-from-api.ts`, and to `UpdateObjectFromApiParams` in `src/entities/nodes/object/api/update-object-from-api.ts`. Pass it into the `context` of `graphqlClient.mutate` only when it is set. T004 and T005 pass.
- [X] T007 Pass `processErrorMessage` through the use cases `src/entities/nodes/object/domain/use-cases/create-object.ts` (`CreateObjectParams`) and `src/entities/nodes/object/domain/use-cases/update-object.ts` (`UpdateObjectParams`). The two mutation hooks need no change if their `mutationFn` already spreads the params into the use case: check `useCreateObjectMutation` in `src/entities/nodes/object/ui/queries/create-object.mutation.ts` and `useUpdateObjectMutation` in `update-object.mutation.ts`.

### Number pool rules (`RM/domain/rules/`, see research R7 and data-model "Domain rules")

- [X] T008 [P] Write tests in `RM/domain/rules/can-number-pool-allocate-to.test.ts`, using `generateAttributeSchema`:
  - true for a `Number` attribute that is not read-only;
  - false for a read-only `Number` attribute;
  - false for a `Text` attribute.
- [X] T009 [P] Write tests in `RM/domain/rules/can-number-pool-be-scoped-by.test.ts`, using `generateAttributeSchema` and `generateRelationshipSchema`:
  - true for a required `Dropdown` attribute;
  - true for a required relationship with cardinality one;
  - false for an optional attribute;
  - false for an optional relationship;
  - false for a relationship with cardinality many;
  - false for an attribute of kind `List`, `JSON` and `Any`.
- [X] T010 [P] Write tests in `RM/domain/rules/find-overlapping-ranges.test.ts`:
  - no overlap for 1–10 and 11–20;
  - overlap for 1–10 and 10–20, which share 10;
  - one range that overlaps two others is reported against both;
  - entries out of numeric order (40–50 before 1–19) still compare correctly.
- [X] T011 [P] Implement `canNumberPoolAllocateTo(attribute: AttributeSchema): boolean` in `RM/domain/rules/can-number-pool-allocate-to.ts`. Use `ATTRIBUTE_KIND.NUMBER` from `src/entities/schema/domain/model/attribute-kind.ts`. T008 passes.
- [X] T012 [P] Implement `canNumberPoolBeScopedBy(field: AttributeSchema | RelationshipSchema): boolean` in `RM/domain/rules/can-number-pool-be-scoped-by.ts`.
  - It mirrors the per-field checks of `backend/infrahub/pools/scope.py::AllocationScopeValidator.check_element`, except "not the allocated attribute", which the caller applies.
  - Tell the two kinds of field apart with a type guard, not `as`.
  - T009 passes.
- [X] T013 [P] Implement `findOverlappingRanges<K>(ranges: Array<{ key: K; start: number; end: number }>): Map<K, Array<{ start: number; end: number }>>` in `RM/domain/rules/find-overlapping-ranges.ts`. For each key, return the bounds of every other range it overlaps. T010 passes.
- [X] T014 [P] (Reverted at the user's request: a type used in one place does not belong in the model; the form reads each stored entry's `name` directly.) Add `export interface AllocationScopeElement { id: string; name: string }` to `RM/domain/model/number-pool.ts`.

**Checkpoint**: The generic save path can return errors to the caller, and the rules are tested.

---

## Phase 3: User Story 1 - Create a scoped pool with several ranges (Priority: P1) 🎯 MVP

**Goal**: From the object list, the resource manager or a relationship's "+ Add new", the user creates a pool with a node, an attribute, an optional scope and weighted ranges in one save.

**Independent Test**: Create a pool on `InfraSubinterface.unit_id`, scoped by Device, with ranges 100–199 (weight 10) and 300–399. Its edit form then shows both ranges with their weights. (Updated during implementation: the details page cannot show a scoped pool's ranges.)

### Tests for User Story 1

- [X] T015 [P] [US1] (Revised during implementation: the checks became per-field react-hook-form rules, `validateRangeBound`, `validateRangeWeight` and `validateRangeOverlap`, in place of `validateRangeRows`.) Write unit tests in `RM/ui/number-pool/form/number-pool-form-values.test.ts` for `validateRangeRows` and `toNumberPoolCreateData` (see T021):
  - an empty start or end gives "Required";
  - `12a` gives "Whole number";
  - `9007199254740992` gives "Too large";
  - a non-empty weight that is not a whole number gives "Whole number";
  - overlapping rows each get "Overlaps \<start\> – \<end\>";
  - an empty weight becomes `allocation_weight: null`;
  - `start` and `end` become numbers, and rows keep the order entered;
  - an empty scope leaves `allocation_scope` out;
  - a scope is sent as `allocation_scope: { value: ["device"] }`.
- [X] T016 [P] [US1] Write component tests in `RM/ui/number-pool/form/number-pool-allocates-input.test.tsx`, with schemas from `generateNodeSchema` and `generateGenericSchema`:
  - Before a node is picked, only the Node select and the hint "Pick a node to choose its attribute and scope" show.
  - The Node list holds only schemas with a `Number` attribute that is not read-only.
  - After a node is picked, the Attribute list holds only its non-read-only `Number` attributes, each with its limits and "Unique" where it applies.
  - No attribute is preselected.
  - The "Scoped by" list leaves out the chosen attribute and the fields that `canNumberPoolBeScopedBy` refuses.
  - Picking a unique attribute disables "Scoped by" with "\<attribute\> is unique, so the pool has one sequence", and clears the scope.
  - Changing the node clears the attribute and the scope.
- [X] T017 [P] [US1] Write component tests in `RM/ui/number-pool/form/number-pool-ranges-input.test.tsx`:
  - "Add range" adds a row, and the trash button removes it.
  - Rows stay in the order entered after focus leaves a row.
  - With no rows, "No ranges. The pool can't hand out numbers until you add one." shows.
  - The header line reads "Highest weight is used first. Ranges with equal weight are used from the lowest start."
  - The Weight placeholder is "0".
- [X] T018 [P] [US1] Write component tests in `RM/ui/number-pool/form/number-pool-form.test.tsx` for create. Mock `useCreateObjectMutation` with `vi.mock`.
  - Saving a valid form calls the mutation once, with `objectKind: "CoreNumberPool"`, the payload from T015, and a `processErrorMessage` function.
  - Then `onSuccess` is called with the created node.
  - Saving with overlapping rows sends nothing.
  - When the mutation rejects with a message that names no field, the sheet keeps every value and shows the message in one alert above the footer.
  - (Removed during implementation: every refusal shows above the footer.) A message keyed `allocation_scope` shows under "Scoped by".
- [X] T019 [US1] Update `tests/e2e/resource-manager/test_number_pool.py::TestNumberPool`:
  - `test_create_number_pool_for_generic_schema` and `test_create_number_pool_for_node_schema` select the node, the attribute and one range through the new labels.
  - Add `test_create_scoped_number_pool_with_weighted_ranges`, covering acceptance scenario 1 of User Story 1. Assert the two ranges in the edit form. (Updated during implementation: the details page cannot show a scoped pool's ranges.)
  - Add `test_create_number_pool_flags_overlapping_ranges`, covering acceptance scenario 3.
  - Add `test_create_number_pool_shows_backend_refusal`, covering acceptance scenario 4: use a range outside `vlan_id`'s limits, and assert the alert above the footer.

  Keep the file's one `pytestmark` shard.
- [X] T020 [P] [US1] Update the labels in `tests/e2e/object-template/test_template_with_number_pool.py::TestTemplateWithNumberPool::test_create_a_number_pool_for_module_capacity` and in `tests/e2e/tutorial/guides/test_resource_manager_guide.py::test_number_pool`. Keep the latter's `save_screenshot_for_docs` call for `guides/resources-manager/resource_manager_pool_vlan`.

### Implementation for User Story 1

- [X] T021 [US1] Create `RM/ui/number-pool/form/number-pool-form-values.ts`:
  - the form value type from data-model "Form values";
  - `validateRangeRows(rows)`, which returns errors per row key, using `findOverlappingRanges` for the overlap message;
  - `toNumberPoolCreateData(values)`, which returns the create payload. (Revised during implementation: each form builds its payload inline, typed with `satisfies`, using the shared `toRangeInput` and `toTextValue`.)

  Type the payload as `Omit<CoreNumberPoolCreateInput, "ranges" | "start_range" | "end_range"> & { ranges: Array<{ start: number; end: number; allocation_weight: number | null }> }`, using the generated type from `src/shared/api/graphql/generated/types.ts` (research R4). T015 passes.
- [X] T022 [P] [US1] Create `NumberPoolNodeSelect` in `RM/ui/number-pool/form/number-pool-node-select.tsx`:
  - an `@infrahub/ui` `Select` with `Autocomplete` and `ListBox`, over `nodeSchemasAtom` and `genericSchemasAtom`, filtered with `canNumberPoolAllocateTo`;
  - each item shows the label and the kind, and is searchable by either.
- [X] T023 [P] [US1] Create `NumberPoolNodeAttributeSelect` in `RM/ui/number-pool/form/number-pool-node-attribute-select.tsx`:
  - it lists the chosen schema's attributes filtered with `canNumberPoolAllocateTo`;
  - each item shows the label, the limits (`parameters.min_value`–`parameters.max_value`, when set) and "Unique" when it applies;
  - it is disabled until a node is picked.
- [X] T024 [P] [US1] Create `NumberPoolAllocationScopeSelect` in `RM/ui/number-pool/form/number-pool-allocation-scope-select.tsx`:
  - the picked fields show as removable chips in a react-aria `TagGroup`, following `src/entities/nodes/filters/ui/active-filter-tags.tsx`, plus an add button that opens a `Popover` with an `Autocomplete` list;
  - the list holds the node's attributes and relationships, without the allocated attribute, filtered with `canNumberPoolBeScopedBy`;
  - with an `isDisabled` reason, it renders the disabled row with that text.

  Use the prototype's `src/pages/proto/number-pool/scope-field.tsx::ScopeField` for layout and copy only.
- [X] T025 [P] [US1] Create `NumberPoolRangesInput` in `RM/ui/number-pool/form/number-pool-ranges-input.tsx`:
  - Start, End and Weight per row, with "Add range" and a remove button;
  - errors from `validateRangeRows` show under each row;
  - the empty-list message and the header line from T017;
  - no re-sorting.

  Use the prototype's `src/pages/proto/number-pool/editor.tsx::RowsEditor` for layout and copy, without `useSortOnRowBlur` and without `clipHint`. T017 passes.
- [X] T026 [US1] Create `NumberPoolAllocatesInput` in `RM/ui/number-pool/form/number-pool-allocates-input.tsx`. It is the "What it allocates" box with the reveal layout from `src/pages/proto/number-pool/create-form.tsx::AllocatesBlock`, without `AllocatesStyleContext` and the other layouts.
  - It renders the three selects from T022–T024.
  - Choosing a node clears the attribute and the scope, in the change handler and not in an effect.
  - Choosing a unique attribute clears the scope and disables "Scoped by" with the reason text.

  T016 passes.
- [X] T027 [US1] Create `NumberPoolForm` in `RM/ui/number-pool/form/number-pool-form.tsx`:
  - It uses react-hook-form through `src/shared/components/ui/form.tsx`, with Name (required), Description, `NumberPoolAllocatesInput` and `NumberPoolRangesInput`, then Cancel and Save.
  - On submit:
    - It runs `validateRangeRows` and stops on errors.
    - It calls `useCreateObjectMutation().mutateAsync({ objectKind: NUMBER_POOL_KIND, data: toNumberPoolCreateData(values), processErrorMessage })`, then the caller's `onSuccess`.
    - On rejection, it shows the backend's message in one alert above the footer. (Revised during implementation: no field-keyed placement.)
  - It takes `ObjectFormProps`' `currentObject`, `isUpdate`, `onSuccess` and `onCancel`.

  T018 passes.
- [X] T028 [US1] In `src/shared/components/form/object-form.tsx::ObjectForm`, route `CoreNumberPool` with `!props.isUpdate` to the new `NumberPoolForm`, and keep the old `RM/ui/number-pool-form.tsx` for edit until T037. A prefilled `currentObject` from `AddRelationshipAction` opens the new form in create mode (research R2).
- [ ] T029 (Not run yet: needs a local image from `uv run invoke dev.build`) [US1] Run the US1 e2e tests from T019 and T020 with `uv run pytest -c tests/e2e/pytest.ini <node_id> -s --pdb` until they pass.

**Checkpoint**: Creating a pool works end to end. Edit still uses the old form.

---

## Phase 4: User Story 2 - Edit a pool's ranges (Priority: P2)

**Goal**: From a pool's details page, the user edits its name, description and ranges. Node, attribute and scope show as read-only text.

**Independent Test**: Edit a pool with range 100–199: change the end to 299 and add 500–599. The reopened edit form then shows 100–299 and 500–599, and assigned numbers stay assigned.

### Tests for User Story 2

- [X] T030 [P] [US2] Extend `RM/api/number-pool.mappers.test.ts`:
  - `mapToNumberPoolData` maps the new `ranges` edges to `{ start, end, allocation_weight }` with numbers;
  - a stored null weight maps to `null`, not `0`.
- [X] T031 [P] [US2] (Revised during implementation: the update payload is built inline in the edit form, and the edit component test checks it.) Extend `RM/ui/number-pool/form/number-pool-form-values.test.ts` for `toNumberPoolUpdateData(id, values)`:
  - it sends `id`, `name`, `description` and the complete `ranges` list;
  - it never sends `node`, `node_attribute` or `allocation_scope`;
  - an unchanged empty weight is sent as `null`;
  - `ranges: []` is sent when every row is removed.
- [X] T032 [P] [US2] Extend `RM/ui/number-pool/form/number-pool-allocates-input.test.tsx` for `isReadOnly`:
  - node, attribute and "Scoped by" show as text;
  - the scope reads from `[{ id, name }]` entries, with each field's label found by name, or the name when the field is missing;
  - "No scope" shows when the scope is empty.
- [X] T033 [P] [US2] Extend `RM/ui/number-pool/form/number-pool-form.test.tsx` for edit. Mock `useGetNumberPool` and `useUpdateObjectMutation`.
  - The rows start from the pool's stored ranges, with an empty Weight for a null weight.
  - Saving calls the update with the T031 payload and `processErrorMessage`, then `onSuccess`.
- [X] T034 [US2] In `tests/e2e/resource-manager/test_number_pool.py::TestNumberPool`:
  - update `test_update_form_should_not_include_node_and_attribute_selects` to assert the read-only node and attribute text;
  - add `test_edit_number_pool_ranges`, covering acceptance scenario 1 of User Story 2;
  - add `test_edit_form_shows_scope_read_only` for the pool created in `test_create_scoped_number_pool_with_weighted_ranges`, asserting "Scoped by: Device".

### Implementation for User Story 2

- [X] T035 [US2] Extend `GET_NUMBER_POOL` in `RM/api/get-number-pool-from-api.ts` to request `ranges { edges { node { start { value } end { value } allocation_weight { value } } } }`. Then:
  - add `ranges: Array<{ start: number; end: number; allocation_weight: number | null }>` to `NumberPoolData` in `RM/domain/model/number-pool.ts`;
  - map the ranges in `mapToNumberPoolData` in `RM/api/number-pool.mappers.ts`, reading the `BigInt` values as numbers (typed `number` once the scalar mapping changed);
  - add `ranges: []` to `generateNumberPoolData` in `frontend/app/tests/fake/number-pool.ts`.

  T030 passes. The details page tests still pass.
- [X] T036 [US2] (Revised during implementation: the update payload is built inline in the edit form.) Add `toNumberPoolUpdateData` to `RM/ui/number-pool/form/number-pool-form-values.ts` (T031 passes). Add the `isReadOnly` mode to `NumberPoolAllocatesInput`, as an early return (T032 passes).
- [X] T037 [US2] Add edit mode to `NumberPoolForm`:
  - with `isUpdate`, read the pool ID from `currentObject.id`;
  - load the ranges with `useGetNumberPool` from `RM/ui/queries/get-number-pool.query.ts`;
  - read the scope from `currentObject.allocation_scope.value`;
  - save with `useUpdateObjectMutation().mutateAsync({ objectKind: NUMBER_POOL_KIND, data: toNumberPoolUpdateData(...), processErrorMessage })`.

  T033 passes. Then route every `CoreNumberPool` case in `src/shared/components/form/object-form.tsx` to the new form, and delete `RM/ui/number-pool-form.tsx`.
- [ ] T038 (knip passes; the e2e part is not run yet, for the same reason as T029) [US2] Run `pnpm knip` from `frontend/app/` to confirm that nothing still references the deleted form. Then run the e2e tests from T034 until they pass.

**Checkpoint**: Create and edit both use the new form, and the old form is gone.

---

## Phase 5: Polish & Cross-Cutting

- [X] T039 (Done at the user's request, together with the mock-unscoped edits) [P] Delete `frontend/app/src/pages/proto/number-pool/` and the block between `// PROTO number-pool` and `// END PROTO number-pool` in `frontend/app/src/app/router.tsx`.
- [X] T040 (Done; docs lint not run because markdownlint and Vale are not installed locally) [P] Update "Step 1: Create a number pool" in `docs/docs/resource-manager/allocate-number.mdx`:
  - the Web interface tab lists Node, Attribute, the optional "Scoped by", and ranges with weights;
  - the GraphQL tab sends `ranges` in place of `start_range` and `end_range`.

  Run `uv run invoke docs.lint`, and fix spelling failures by rewording, not by adding exceptions.
- [X] T041 (Done) [P] Add the changelog fragment `changelog/+ifc-3365-number-pool-form.changed.md` with the `creating-changelog-entries` skill. In full sentences, it says the number pool form now:
  - creates a pool with several weighted ranges and an optional allocation scope in one save;
  - edits a pool's ranges.
- [X] T042 (biome, knip and the full test suite pass for the feature's files; biome and betterer still flag the uncommitted prototype and mock-unscoped files) Run the frontend CI gate from `frontend/` and `frontend/app/` (`pnpm exec biome ci .`, `pnpm knip`, `pnpm exec betterer ci`, `pnpm test`), and fix every failure.
- [X] T043 (Walked through create, overlap, backend refusal and edit against the local stack) Walk through `quickstart.md` by hand against a running stack, and record any difference from the expected results.

---

## Dependencies & Execution Order

### Phase dependencies

- **Setup (Phase 1)**: none. T002 depends on T001. T003 waits for the user's answer.
- **Foundational (Phase 2)**: T004–T007 depend on nothing in Phase 1. T008–T014 depend on nothing. Both groups block Phase 3.
- **User Story 1 (Phase 3)**: depends on Phase 2.
- **User Story 2 (Phase 4)**:
  - it depends on T021 and T026 from US1, because it extends those files;
  - T035 can start right after Phase 2.
- **Polish (Phase 5)**: depends on US1 and US2. T039 also depends on T024–T026, which read the prototype.

### Within each story

Write the tests, see them fail, then implement. Within US1, the order is:
1. Form values (T021).
2. The four inputs (T022–T025).
3. The allocates box (T026).
4. The form (T027).
5. The routing (T028).
6. The e2e tests (T029).

### Release

Both stories ship in the same release (spec, User Scenarios). US1 alone leaves edit on the old form, which is acceptable for testing but not for release.

## Parallel Examples

```text
# Phase 2: all rule tests together, then all rule implementations together
T008, T009, T010          (tests)
T011, T012, T013, T014    (implementations and model type)

# Phase 3: tests, then the four inputs
T015, T016, T017, T018, T020
T022, T023, T024, T025

# Phase 4: tests
T030, T031, T032, T033
```

## Implementation Strategy

1. **Setup:** Phase 1, with the move as its own commit.
2. **Foundational:** Phase 2.
3. **US1:** Phase 3. Stop and test creating a pool on its own.
4. **US2:** Phase 4. Stop and test editing on its own.
5. **Polish:** Phase 5, then `/pre-ci` before pushing.
