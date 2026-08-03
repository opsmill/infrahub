---

description: "Task list for renaming the misleading has_schema_changes branch field"
---

# Tasks: Rename the misleading `has_schema_changes` branch field

**Input**: Design documents from `/specs/ifc-2281-schema-differs-from-default/`

**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/graphql-branch-field.md, quickstart.md

**Tests**: Included - the spec explicitly requires test coverage and parity verification (FR-010, SC-001/SC-004).

**Organization**: Tasks are grouped by user story. US1 and US2 are both P1 and both edit the backend
GraphQL branch types; they are separately testable but share one file, so their implementation tasks
are sequenced rather than parallel.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies on incomplete tasks)
- **[Story]**: US1, US2, US3 map to the spec's user stories
- Exact file paths are included in each task

## Path Conventions

Web application monorepo: backend at `backend/infrahub/`, frontend at `frontend/app/src/`, generated
schema at `schema/`, changelog fragments at `changelog/`.

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Confirm the working environment is ready. No project init needed (existing repo).

- [X] T001 Confirm the feature branch is checked out and dependencies are installed: `uv sync --all-groups` and `cd frontend/app && pnpm install`

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: The backend model property is the single source of the value that every GraphQL field,
mutation payload, and the frontend read from. It must exist before any story work.

**⚠️ CRITICAL**: No user story can be completed until this phase is done.

- [X] T002 Add a `schema_differs_from_default_branch` `@property` (typed `-> bool`) holding the existing divergence computation to the `Branch` model in `backend/infrahub/core/branch/models.py`, and rewrite the existing `has_schema_changes` property to `return self.schema_differs_from_default_branch` (delegation, no logic change; keep it for the deprecation window)
- [X] T003 Repoint the two internal backend readers from `has_schema_changes` to `schema_differs_from_default_branch` in `backend/infrahub/core/branch/tasks.py` (the two `if user_branch.has_schema_changes:` gates in the `rebase_branch()` flow, ~L204 and ~L232)

**Checkpoint**: The value is available under the new property name and internal consumers use it. GraphQL/frontend story work can begin.

---

## Phase 3: User Story 1 - Query branch schema-divergence with an honest name (Priority: P1) 🎯 MVP

**Goal**: Expose a new `schema_differs_from_default_branch` GraphQL field on both branch query types
(and, via the shared `BranchType`, in mutation payloads) returning the same value as today.

**Independent Test**: Query `schema_differs_from_default_branch` on a branch whose schema matches the
default (expect `false`), on a branch that changed its own schema (expect `true`), and on an untouched
branch after the default changed (expect `true`); query both fields together and confirm equal values.

### Tests for User Story 1 ⚠️ (write first, expect failure before T006)

- [X] T004 [P] [US1] Add a component GraphQL test asserting `schema_differs_from_default_branch` returns `false`/`true` across the three branch states (contract C1-C3) in `backend/tests/component/graphql/queries/test_branch.py`
- [X] T005 [P] [US1] Add a component GraphQL test asserting `has_schema_changes` and `schema_differs_from_default_branch` return identical values in one query (contract C4, SC-001) in `backend/tests/component/graphql/queries/test_branch.py`

### Implementation for User Story 1

- [X] T006 [US1] Add the `schema_differs_from_default_branch` graphene field to both `BranchType` (`Boolean(required=False)`) and `InfrahubBranch` (`Field(NonRequiredBooleanValueField, required=False)`) in `backend/infrahub/graphql/types/branch.py`
- [X] T007 [US1] Regenerate the GraphQL schema artifact with `uv run invoke schema.generate-graphqlschema` and confirm `schema/schema.graphql` gains `schema_differs_from_default_branch` on both `Branch` and `InfrahubBranch`

**Checkpoint**: New field resolves correctly on both query types and in mutation payloads, and is present in the generated schema.

---

## Phase 4: User Story 2 - Existing consumers keep working during deprecation (Priority: P1)

**Goal**: Mark `has_schema_changes` deprecated (machine-readable, on both types) with a single message
naming the replacement and the 1.14.0 removal version, while it keeps returning the correct value.

**Independent Test**: Introspect the schema and confirm `has_schema_changes` on both `Branch` and
`InfrahubBranch` is flagged deprecated with a reason naming `schema_differs_from_default_branch` and
Infrahub 1.14.0; query the old field and confirm it still returns the correct value.

### Tests for User Story 2 ⚠️ (write first, expect failure before T010)

- [X] T008 [P] [US2] Add a test verifying `has_schema_changes` is deprecated on both `Branch` and `InfrahubBranch` via introspection, with a reason naming the replacement and Infrahub 1.14.0 (contract C6, SC-002) in `backend/tests/component/graphql/queries/test_branch.py`
- [X] T009 [P] [US2] Add/extend a test confirming `has_schema_changes` still returns its correct value after the change (contract C5, SC-004) in `backend/tests/component/graphql/queries/test_branch.py`

### Implementation for User Story 2

- [X] T010 [US2] Define a shared module-level deprecation-reason constant (message: `Use schema_differs_from_default_branch instead. has_schema_changes is scheduled for removal in Infrahub 1.14.0.`) and apply `deprecation_reason=` to `has_schema_changes` on both `BranchType` and `InfrahubBranch` in `backend/infrahub/graphql/types/branch.py` (depends on T006 - same file)
- [ ] T011 [P] [US2] DEFERRED to T023 (blocked on the SDK query change). The schema-lifecycle integration tests (`backend/tests/integration/schema_lifecycle/test_migration_relationship_branch.py`, `test_schema_migration_branch.py`, `test_migration_attribute_branch.py`, `test_unique_field_updates.py`) and the branch fixtures in `backend/tests/conftest.py` read branch data through the SDK client, whose `BranchData` only carries a value for `schema_differs_from_default_branch` once the SDK query (`BRANCH_DATA`) selects it. Until then they keep asserting `has_schema_changes` still returns `True` (SC-004); new-field parity is already covered by the component tests (T005)
- [X] T012 [US2] Regenerate the GraphQL schema with `uv run invoke schema.generate-graphqlschema` and confirm `schema/schema.graphql` shows `@deprecated(reason: ...)` on `has_schema_changes` for both types (depends on T007 - same generated file)

**Checkpoint**: Old field works unchanged and is discoverably deprecated with replacement + removal version; both P1 stories complete (backend MVP).

---

## Phase 5: User Story 3 - The Infrahub web UI uses the new field and clearer copy (Priority: P2)

**Goal**: Migrate the frontend to consume `schema_differs_from_default_branch` and replace the
misleading badge/label copy, keeping the same positions.

**Independent Test**: Load the branch list and branch detail views for branches in both states; the
indicator appears in the same positions with clarified wording, and requests select the new field only.

### Tests for User Story 3 ⚠️ (write first)

- [X] T013 [P] [US3] Update frontend fixtures/tests to the new field name in `frontend/app/tests/fake/branch.ts` and `frontend/app/src/shared/components/form/utils/getFormFieldsFromSchema.test.ts`

### Implementation for User Story 3

- [X] T014 [P] [US3] Request `schema_differs_from_default_branch` instead of `has_schema_changes` in the four branch operations: `frontend/app/src/entities/branches/api/get-branches-from-api.ts`, `get-branch-details-from-api.ts`, `create-branch-from-api.ts`, `rebase-branch-from-api.ts`
- [X] T015 [P] [US3] Rename the field through the data layer in `frontend/app/src/entities/branches/api/branch.mappers.ts`, `domain/model/branch.ts` (BranchListItem, BranchDetail), `domain/use-cases/create-branch.ts` (default value), and `ui/branches-to-select-options.ts`
- [X] T016 [US3] Replace the badge copy `schema updated` with `schema differs from default` (proposed default wording; fits the existing badge layout per FR-006) in `frontend/app/src/entities/branches/ui/branch-list-item/branch-schema-changes-badge.tsx`, and update its field references in `ui/branch-list-item/branch-list-item.tsx` and `ui/branches-table/cells/branch-name-cell.tsx`
- [X] T017 [US3] Replace the detail label `Has schema changes` with `Schema differs from default branch` (proposed default wording; fits the existing label layout per FR-006) and update the field reference in `frontend/app/src/entities/branches/ui/branch-details/branch-attributes.tsx`
- [X] T018 [US3] Update the E2E assertions of the detail label to the new T017 copy in `frontend/app/tests/e2e/branches/branch-details.spec.ts` (two assertions asserting `Has schema changes`) and `tests/e2e/branches/test_branch_details.py` (two assertions asserting `Has schema changes`); the string must match exactly what T017 chose (depends on T017)
- [X] T019 [US3] Regenerate frontend GraphQL types with `cd frontend/app && pnpm codegen` (reads the updated `schema/schema.graphql`; depends on T012 and T014)
- [X] T020 [US3] Run frontend unit tests with `cd frontend/app && pnpm test` and confirm branch fixtures/tests pass with the new field

**Checkpoint**: UI consumes only the new field and shows clarified copy in the same positions (SC-003, SC-006).

---

## Phase 6: Polish & Cross-Cutting Concerns

**Purpose**: Documentation, changelog, follow-up tracking, and final gates.

- [X] T021 [P] Add a changelog `added` fragment `changelog/+schema-differs-from-default-branch.added.md` describing the new field (no ticket IDs in the body)
- [X] T022 [P] Add a changelog `deprecated` fragment `changelog/+schema-differs-from-default-branch.deprecated.md` noting `has_schema_changes` is deprecated and will be removed in Infrahub 1.14.0
- [X] T023a Add `schema_differs_from_default_branch: bool | None = None` to `BranchData` in the `python_sdk` submodule (`infrahub_sdk/branch.py`). Forward-compatible, model-only: the SDK branch query (`BRANCH_DATA`) is intentionally left unchanged, so the field parses as `None` until the query switch. No SDK changelog fragment until that behaviour change lands. Lands via a separate `python_sdk` PR, then the submodule pointer bump here
- [ ] T023 [P] Create a follow-up ticket for full SDK adoption of `schema_differs_from_default_branch` (OOS-001): the `BranchData` model field is already added (T023a); the follow-up covers switching the SDK branch query (`BRANCH_DATA`) to select the field - deferred until the SDK's minimum supported server exposes it - plus its changelog fragment and any downstream SDK consumers, then unblocking the integration parity assertions (T011). Must exist before this feature is considered done
- [ ] T024 [P] Create a follow-up ticket to remove `has_schema_changes`, pinned to the Infrahub 1.14.0 milestone (OOS-005) - must exist before this feature is considered done
- [ ] T025 Run `uv run invoke format lint` and `cd frontend/app && pnpm biome:fix` and resolve any findings
- [ ] T026 Run `/pre-ci` and walk through `quickstart.md` to validate all success criteria (SC-001 through SC-006)

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies.
- **Foundational (Phase 2)**: Depends on Setup. BLOCKS all user stories.
- **US1 (Phase 3)**: Depends on Foundational.
- **US2 (Phase 4)**: Depends on Foundational; its implementation (T010, T012) follows US1's T006/T007 because they edit the same `branch.py` and the same generated `schema.graphql`.
- **US3 (Phase 5)**: Depends on Foundational; the E2E copy update (T018) follows the label change (T017); T019 (codegen) additionally depends on the backend schema regeneration (T012) and the query edits (T014).
- **Polish (Phase 6)**: Depends on the desired stories being complete.

### User Story Dependencies

- **US1 (P1)**: Independently testable once Foundational is done.
- **US2 (P1)**: Independently testable; shares `branch.py`/`schema.graphql` with US1 so sequence the file edits.
- **US3 (P2)**: Independently testable in the UI; needs the regenerated backend schema for `pnpm codegen`.

### Within Each User Story

- Tests are written first and expected to fail before the implementation task in that story.
- Backend field edits precede schema regeneration.
- Frontend query/type edits precede `pnpm codegen`, which precedes running frontend tests.

### Parallel Opportunities

- T004 and T005 (US1 tests) can run in parallel.
- T008 and T009 (US2 tests) and T011 (integration test updates) can run in parallel with each other.
- T013, T014, T015 (US3, different files) can run in parallel; T016 and T017 touch shared/adjacent UI and follow, then T018 (E2E copy) follows T017.
- T021, T022, T023, T024 (Polish) can all run in parallel.

---

## Parallel Example: User Story 1

```bash
# US1 tests (different assertions, same test module - stage together, review before implementing):
Task: "Component test: schema_differs_from_default_branch across three states (C1-C3) in backend/tests/component/graphql/queries/test_branch.py"
Task: "Component test: both fields return identical values (C4/SC-001) in backend/tests/component/graphql/queries/test_branch.py"
```

---

## Implementation Strategy

### MVP First (backend: US1 + US2)

1. Complete Phase 1 (Setup) and Phase 2 (Foundational).
2. Complete US1 (new field) → validate the new field resolves and is in `schema.graphql`.
3. Complete US2 (deprecation) → validate old field still works and is discoverably deprecated with the 1.14.0 message.
4. **STOP and VALIDATE**: The backend is a shippable, non-breaking increment (SC-001/002/004).

### Incremental Delivery

1. Foundational → backend property ready.
2. US1 → new field (MVP for API consumers).
3. US2 → deprecation of old field (safe migration window).
4. US3 → frontend migration + copy fix.
5. Polish → changelog, follow-up tickets, final gates.

### Parallel Team Strategy

Once Foundational is done, one developer can take the backend (US1 → US2) while another starts US3's
non-generated frontend edits; US3's `pnpm codegen` and tests wait for the backend schema regeneration.

---

## Notes

- [P] = different files, no dependency on an incomplete task.
- Do not rename `SchemaAnalyzer.has_schema_changes()` or touch its callers (OOS-004); it is unrelated.
- In the Python SDK, add only the forward-compatible `BranchData` model field (T023a); defer the SDK query change and full adoption to the follow-up (T023, OOS-001).
- Do not change the divergence computation itself (OOS-003) - delegation only.
- The mock GraphQL branch responses in `backend/tests/component/git/conftest.py` keep `has_schema_changes` unchanged: the old field is retained so those fixtures stay valid, and they are intentionally not migrated.
- If US1 and US2 land together (the recommended MVP path), a single `uv run invoke schema.generate-graphqlschema` run after T010 produces both the new field and the `@deprecated` annotation - T007 and T012 collapse into one regeneration rather than two.
- Regenerated files (`schema/schema.graphql`, `frontend/app/src/shared/api/graphql/generated/`) must be committed; CI fails if stale.
- Keep ticket IDs out of source/comments/changelog bodies per the repo's code-doc-style rule.
- Commit after each task or logical group.
