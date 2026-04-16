# Tasks: Search Anywhere Display Label Enrichment

**Input**: Design documents from `/specs/005-search-display-label/`
**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/

**Tests**: Included — the spec calls for backend test updates and new frontend component tests.

**Organization**: Tasks grouped by user story. US1 and US2 share the same backend/frontend infrastructure, so foundational work is in Phase 2.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (e.g., US1, US2, US3)
- Include exact file paths in descriptions

---

## Phase 1: Setup

**Purpose**: No new project setup needed — all changes are to existing files. This phase handles schema regeneration prerequisites.

- [ ] T001 Verify backend dev environment: `uv sync --all-groups`
- [ ] T002 Verify frontend dev environment: `cd frontend/app && npm install`

---

## Phase 2: Foundational (Backend API Changes)

**Purpose**: Backend GraphQL type and resolver changes that ALL user stories depend on. Must complete before any frontend work.

**CRITICAL**: No frontend tasks can begin until this phase is complete.

- [ ] T003 Add `display_label` field to `Node` ObjectType in `backend/infrahub/graphql/queries/search.py`
- [ ] T004 Remove Schema/Internal namespace filter from UUID search path in `backend/infrahub/graphql/queries/search.py`
- [ ] T005 Compute `display_label` via `node.get_display_label(db)` for UUID matches in `backend/infrahub/graphql/queries/search.py`
- [ ] T006 Update backend test: rename and rewrite `test_search_anywhere_by_uuid_excludes_internal_nodes` to verify Schema/Internal nodes ARE returned with `display_label` in `backend/tests/component/graphql/queries/test_search.py`
- [ ] T007 Add backend test: verify `display_label` field is present in UUID search results for regular nodes in `backend/tests/component/graphql/queries/test_search.py`
- [ ] T008 Add backend test: verify text-based search still excludes Schema/Internal nodes (no regression) in `backend/tests/component/graphql/queries/test_search.py`
- [ ] T009 Regenerate GraphQL schema: run `uv run invoke backend.generate` to update `schema/schema.graphql`
- [ ] T010 Run backend linting and formatting: `uv run invoke format && uv run invoke lint`

**Checkpoint**: Backend API returns `display_label` for UUID searches and no longer filters Schema/Internal nodes. All backend tests pass.

---

## Phase 3: User Story 1 — Look up Schema Node from pipeline error (Priority: P1) MVP

**Goal**: Searching for a SchemaNode UUID shows a result with human-readable label and links to `/schema?kind={kind}`.

**Independent Test**: Search for a known SchemaNode UUID → result appears with display label → click navigates to schema page with entry selected.

### Implementation for User Story 1

- [ ] T011 [P] [US1] Add `display_label` to GraphQL query selection set in `frontend/app/src/entities/navigation/api/search.ts`
- [ ] T012 [P] [US1] Add `display_label` to `ObjectResult` type and map it through in `frontend/app/src/entities/navigation/domain/search-anywhere.ts`
- [ ] T013 [US1] In `NodesOptions` component, when `useSchema(node.kind)` returns null, render a `SchemaNodeResult` component instead of returning null in `frontend/app/src/entities/navigation/ui/search-anywhere/search-nodes.tsx`
- [ ] T014 [US1] Implement `SchemaNodeResult` component: display `display_label` (fallback to kind), kind badge, link to `/schema?kind={kind}` in `frontend/app/src/entities/navigation/ui/search-anywhere/search-nodes.tsx`

### Tests for User Story 1

- [ ] T015 [P] [US1] Add test: Schema kind result renders simplified view with `display_label` and kind badge in `frontend/app/src/entities/navigation/ui/search-anywhere/search-nodes.test.tsx` (new file)
- [ ] T016 [P] [US1] Add test: Schema kind result links to `/schema?kind={kind}` in `frontend/app/src/entities/navigation/ui/search-anywhere/search-nodes.test.tsx`
- [ ] T017 [P] [US1] Add test: missing `display_label` falls back to showing kind in `frontend/app/src/entities/navigation/ui/search-anywhere/search-nodes.test.tsx`

**Checkpoint**: SchemaNode UUID search returns visible result with label. Click navigates to schema page. US1 fully functional.

---

## Phase 4: User Story 2 — Regular node search remains unchanged (Priority: P1)

**Goal**: Verify zero regressions in regular node search behavior (UUID and text).

**Independent Test**: Search for a regular node by UUID → full object details render → click navigates to object detail page. Search by text → same behavior as before.

### Implementation for User Story 2

No new implementation needed — the `NodesOptions` component already handles regular nodes via `useSchema` + `useGetObject`. The foundational changes (Phase 2) preserved this path.

### Tests for User Story 2

- [ ] T018 [P] [US2] Add test: regular kind result still renders via full detail path (calls `useGetObject`) in `frontend/app/src/entities/navigation/ui/search-anywhere/search-nodes.test.tsx`

**Checkpoint**: Regular node search is confirmed unchanged. US2 verified.

---

## Phase 5: User Story 3 — Internal namespace node search (Priority: P2)

**Goal**: Internal namespace node UUIDs behave identically to Schema nodes in search.

**Independent Test**: Search for an Internal namespace node UUID → result with display label → click navigates to schema page.

### Implementation for User Story 3

No additional implementation needed — the `SchemaNodeResult` component from US1 handles any kind not in the frontend schema registry, which includes both Schema and Internal namespace nodes. The backend changes in Phase 2 already removed the filter for both namespaces.

### Tests for User Story 3

- [ ] T019 [US3] Add test: Internal namespace kind result renders same simplified view as Schema kind in `frontend/app/src/entities/navigation/ui/search-anywhere/search-nodes.test.tsx`

**Checkpoint**: Internal namespace nodes render and navigate correctly. US3 verified.

---

## Phase 6: Polish & Cross-Cutting Concerns

**Purpose**: Lint, format, betterer, and final validation.

- [ ] T020 Run frontend linting and formatting: `cd frontend/app && npm run biome:fix`
- [ ] T021 Run betterer and update results if needed: `cd frontend/app && npx betterer`
- [ ] T022 Commit updated `.betterer.results` if changed in `frontend/app/.betterer.results`
- [ ] T023 Run full frontend test suite: `cd frontend/app && npm run test`
- [ ] T024 Run quickstart.md verification commands

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies — can start immediately
- **Foundational (Phase 2)**: Depends on Setup — BLOCKS all frontend work
- **US1 (Phase 3)**: Depends on Phase 2 completion
- **US2 (Phase 4)**: Depends on Phase 2 completion, can run in parallel with US1
- **US3 (Phase 5)**: Depends on US1 implementation (reuses SchemaNodeResult component)
- **Polish (Phase 6)**: Depends on all user stories being complete

### User Story Dependencies

- **US1 (P1)**: Can start after Phase 2 — no dependencies on other stories
- **US2 (P1)**: Can start after Phase 2 — independent of US1 (tests only, no new code)
- **US3 (P2)**: Depends on US1 (reuses the SchemaNodeResult component)

### Within Each Phase

- T003, T004, T005 must be sequential (same file, dependent changes)
- T006, T007, T008 can run in parallel (independent test functions, same file but no conflicts)
- T011, T012 can run in parallel (different files)
- T013 depends on T011, T012 (needs updated types)
- T014 depends on T013 (extends the component)
- T015, T016, T017 can run in parallel (independent test cases)

### Parallel Opportunities

```text
# After Phase 2, these can run in parallel:
T011 (api/search.ts) || T012 (domain/search-anywhere.ts)

# After T014, all test tasks can run in parallel:
T015 || T016 || T017 || T018 || T019
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1: Setup verification
2. Complete Phase 2: Backend API changes (T003-T010)
3. Complete Phase 3: US1 frontend + tests (T011-T017)
4. **STOP and VALIDATE**: Search for a SchemaNode UUID — should show result and navigate to schema page
5. Deploy/demo if ready

### Incremental Delivery

1. Phase 2 → Backend ready, all namespaces returned with display_label
2. Phase 3 (US1) → Schema node search works → MVP
3. Phase 4 (US2) → Regression tests confirm no breakage
4. Phase 5 (US3) → Internal namespace coverage
5. Phase 6 → Polish and ship

---

## Notes

- [P] tasks = different files, no dependencies
- [Story] label maps task to specific user story for traceability
- US2 and US3 require no new implementation — just test verification
- Total: 24 tasks across 6 phases
- The backend changes (Phase 2) are the critical path — frontend is blocked until those land
