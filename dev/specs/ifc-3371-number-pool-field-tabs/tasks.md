# Tasks: Number attribute — set a number or take it from a number pool

**Input**: Design documents from `dev/specs/ifc-3371-number-pool-field-tabs/`

**Prerequisites**: [plan.md](plan.md), [spec.md](spec.md), [research.md](research.md),
[data-model.md](data-model.md), [contracts/form-submission.md](contracts/form-submission.md)

**Tests**: Required. FR-020 asks for a test per row of the submission table, and the constitution
requires an e2e test for a user-facing feature.

All source paths are under `frontend/app/src/` unless they start with `tests/` or `changelog/`.
Row IDs (C1, E5, …) refer to [contracts/form-submission.md](contracts/form-submission.md).

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story the task belongs to (US1–US4)

---

## Phase 1: Setup

- [ ] T001 Confirm the backend on this branch accepts `{ value: null, from_pool: { id } }` on a
  create mutation and `{ value: n, from_pool: null }` on an update mutation, by reading
  `backend/infrahub/pools/intent.py::FromPoolIntentResolver` and its unit tests; record any gap in
  `dev/specs/ifc-3371-number-pool-field-tabs/research.md` before continuing

---

## Phase 2: Foundational (blocks every user story)

- [ ] T002 Add `number?: number | null` to `AttributeValueFromPool["value"]["from_pool"]` in
  `shared/components/form/type.ts`, with a one-line doc comment saying it applies only to a
  `CoreNumberPool` source
- [ ] T003 Add a number-pool helper to
  `shared/components/form/utils/mutations/buildFromPoolMutationValue.ts` that returns
  `{ value: number ?? null, from_pool: { id } }` for a staged number pool; keep
  `buildFromPoolPayload` unchanged for IP pools
- [ ] T004 [P] Unit-test the helper in
  `shared/components/form/utils/mutations/buildFromPoolMutationValue.test.ts` (number given,
  number `null`, number absent)

**Checkpoint**: types and payload helper ready.

---

## Phase 3: User Story 1 — Allocate the next free number from a pool (P1)

**Goal**: Picking a pool and leaving the number empty sends `value: null` with the pool.

**Independent test**: Rows C2 and C5.

- [ ] T005 [P] [US1] Add failing tests for rows C2 and C5 in
  `shared/components/form/utils/mutations/getCreateMutationFromFormData.test.ts`
- [ ] T006 [US1] In `shared/components/form/utils/mutations/getCreateMutationFromFormData.ts::getCreateMutationFromFormData`,
  use the T003 helper in the pool branch when `fieldData.source.kind` is `CoreNumberPool` and the
  field has no `fromPoolRelationshipName`; leave the template and IP paths as they are
- [ ] T007 [US1] Add `PoolNumberField` to `shared/components/inputs/pool-select.tsx`: registered at
  `${name}.value.from_pool.number` with `shouldUnregister={false}` (same reason as
  `PoolPrefixLengthField`), rendered only when `getPendingFromPool(value)` is true and the pool
  kind is `CoreNumberPool`; label "Number", description "Leave empty to allocate the next free
  number from the pool."; whole numbers only; uses `usePreventScrollOnNumberInput`
- [ ] T008 [US1] Render `PoolNumberField` below the pool picker in
  `shared/components/form/pool-allocation-panel.tsx::PoolAllocationPanel` when
  `canOverrideAllocation` is true; the IP override row stays as is
- [ ] T009 [P] [US1] Component test in `shared/components/form/fields/number.field.test.tsx`: the
  number input is absent before a pool is picked and present after, and is absent for a
  template-backed field (`fromPoolRelationshipName` set)

**Checkpoint**: allocation from the pool tab works on create.

---

## Phase 4: User Story 2 — Set a specific number and have the pool record it (P1)

**Goal**: Picking a pool and typing a number sends both.

**Independent test**: Row C3.

- [ ] T010 [P] [US2] Add a failing test for row C3 in
  `shared/components/form/utils/mutations/getCreateMutationFromFormData.test.ts`
- [ ] T011 [US2] Make row C3 pass; it should need no code beyond T003 and T006 — if it does,
  fix the helper rather than the caller
- [ ] T012 [P] [US2] Component test in `shared/components/form/fields/number.field.test.tsx`:
  typing 42 in the pool tab stores `value.from_pool.number === 42`

**Checkpoint**: attach on create works.

---

## Phase 5: User Story 3 — Set a number without any pool (P2)

**Goal**: The Value tab and untabbed fields behave as today.

**Independent test**: Rows C1 and E1.

- [ ] T013 [P] [US3] Add regression tests for rows C1 and E1 in
  `getCreateMutationFromFormData.test.ts` and `getUpdateMutationFromFormData.test.ts` under
  `shared/components/form/utils/mutations/`, asserting no `from_pool` key is sent
- [ ] T014 [P] [US3] Regression test in `shared/components/form/fields/number.field.test.tsx`: a
  Number attribute with no pool renders without tabs

**Checkpoint**: no regression for numbers without a pool.

---

## Phase 6: User Story 4 — Edit a node whose number a pool tracks (P2)

**Goal**: The edit form opens on the pool tab for a tracked number, sends the right payload for
rows E2–E10, and detaches from the Value tab.

**Independent test**: Rows E2–E10.

- [ ] T015 [P] [US4] Add failing tests for rows E2–E10 in
  `shared/components/form/utils/mutations/getUpdateMutationFromFormData.test.ts`
- [ ] T016 [P] [US4] Add a failing test in `shared/components/form/utils/getFieldDefaultValue.test.ts`:
  a Number attribute whose source is a `CoreNumberPool` yields
  `{ source: <number pool source>, value: { from_pool: { id, number: <current> } } }`; update any
  existing assertion that expected the raw number
- [ ] T017 [US4] In `shared/components/form/utils/getFieldDefaultValue.ts::getDefaultValueFromPool`,
  build the number-pool value as `{ from_pool: { id, number: currentField.value } }` for a
  `CoreNumberPool` source instead of casting the raw value
- [ ] T018 [US4] Check every consumer of `source.type === "pool"` under
  `shared/components/form/` and `shared/components/inputs/pool-select.tsx` for code that read the
  number-pool value as a raw number, and fix it (critique E2)
- [ ] T019 [US4] In `shared/components/form/utils/mutations/getUpdateMutationFromFormData.ts::getUpdateMutationFromFormData`:
  (a) in the "same pool as the default" early return, also compare `from_pool.number` for number
  pools so row E5 and E6 are sent and E4 is not; (b) use the T003 helper in the `pool` branch for
  number pools without `fromPoolRelationshipName`; (c) in the `user` branch, add
  `from_pool: null` to the attribute payload when the field is a Number attribute without
  `fromPoolRelationshipName` and `field.defaultValue?.source?.type === "pool"` (row E9)
- [ ] T020 [US4] Add an `initialTab` prop (`"value" | "from-pool"`, default `"value"`) to
  `shared/components/form/pool-backed-field.tsx::PoolBackedField` and use it as the initial
  `activeTab`
- [ ] T021 [US4] In `shared/components/form/fields/number.field.tsx::NumberField`: pass
  `initialTab="from-pool"` when `defaultValue?.source?.type === "pool"` and its kind is
  `CoreNumberPool`; show the current number as the Value tab input placeholder when the field
  holds that pool default (plan D8)
- [ ] T022 [US4] Pre-fill the number when a pool is picked (plan D6, FR-014): in
  `shared/components/form/fields/number.field.tsx::NumberField`'s `onPoolChange`, carry the staged
  `from_pool.number`, else the number the node holds when the default source is `user` or `pool`,
  into the new value; leave it empty for schema, profile or template defaults. Put the selection
  logic in `shared/components/form/utils/updateFormFieldValue.ts` if it needs a pure helper, and
  unit-test it in `updateFormFieldValue.test.ts`
- [ ] T023 [US4] Change the pool badge text in
  `shared/components/form/fields/common.tsx::PoolSourceBadge` to "This number is recorded in the
  pool:" when the source kind is `CoreNumberPool` (plan D9)
- [ ] T024 [P] [US4] Component tests in `shared/components/form/fields/number.field.test.tsx`:
  tracked field opens on the "From pool" tab with pool and number shown; untracked field opens on
  "Value"; Value tab placeholder shows the current number; visiting Value and returning leaves the
  field equal to its default

**Checkpoint**: edit journeys pass row by row.

---

## Phase 7: Polish & cross-cutting

- [ ] T025 Extend `tests/e2e/resource-manager/test_number_pool.py`: create with a pool and a typed
  number (C3) and check the node holds it; reopen the node and check the "From pool" tab is
  active with the pool and number; switch to "Value", type a number, save, and check the pool
  badge is gone (E9). Reuse the existing `number_pool_branch` fixture and the pools it creates
- [ ] T026 [P] Add a towncrier fragment `changelog/+number-pool-field-attach.added.md` describing,
  from the user's side, that a number can be set by hand and recorded in a number pool from the
  object form
- [ ] T027 Run `cd frontend && node_modules/.bin/biome ci .`, `cd frontend/app && pnpm knip`,
  `pnpm betterer ci` and `pnpm vitest run src/shared/components/form`; fix any failure
- [ ] T028 Walk [quickstart.md](quickstart.md) on a local instance and tick each manual scenario

---

## Dependencies & execution order

- Phase 1 → Phase 2 → user stories.
- US1 (Phase 3) before US2 (Phase 4): US2 reuses T006 and T007.
- US3 (Phase 5) can run after Phase 2, in parallel with US1.
- US4 (Phase 6) after US1: it needs `PoolNumberField` (T007) and the create helper (T003).
  Within US4, T017 before T018 and T019; T020 before T021.
- Phase 7 after all stories.

## Parallel examples

- After T003: T004, T005, T010, T013, T014 touch different files or only add tests.
- In US4: T015 and T016 together, then T017; T023 is independent of T019–T022.

## Implementation strategy

1. MVP = Phases 1–4 (US1 and US2): the create form can allocate or attach.
2. Add US3 regression tests.
3. Add US4: edit-form behaviour and detach.
4. Polish: e2e, changelog, CI gate, quickstart walk.
