# Tasks: Enhanced Search Results

**Input**: Design documents from `/specs/2026-02-enhanced-search-results/`
**Prerequisites**: plan.md (required), spec.md (required for user stories), research.md, data-model.md, contracts/

**Tests**: Test tasks are included per Infrahub constitution (Principle IV: Test Discipline).

**Organization**: Tasks are grouped by user story to enable independent implementation and testing of each story.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (e.g., US1, US2, US3)
- Include exact file paths in descriptions

---

## Phase 1: Setup

**Purpose**: No new project setup needed — this feature modifies an existing codebase. Phase 1 is a no-op.

---

## Phase 2: Foundational (Backend API Changes)

**Purpose**: Backend changes that MUST be complete before any frontend user story work can begin. The search GraphQL resolver needs `offset` support and correct total count behavior.

- [x] T001 Add `offset: int = 0` parameter to `search_resolver()` and register it as a GraphQL field argument in `backend/infrahub/graphql/queries/search.py`
- [x] T002 Add input validation for `offset` (non-negative) and `limit` (default to 10 if negative) in `backend/infrahub/graphql/queries/search.py`
- [x] T003 Add component tests for offset pagination: verify offset skips results, verify offset=0 behaves as before, verify negative offset treated as 0 in `backend/tests/component/graphql/queries/test_search.py`

**Checkpoint**: Backend API now supports `offset` param. Existing search behavior unchanged when offset=0.

---

## Phase 3: User Story 4 - Reliable Backend Pagination (Priority: P1) 🎯 Foundation

**Goal**: Unify case-sensitive and case-insensitive search paths into a single Cypher query with native SKIP/LIMIT, true total count via `query.count()`, and deterministic ordering.

**Independent Test**: Make API calls with different offset/limit combinations → page 1 + page 2 results cover all matches without duplicates, total count is stable across pages, case-insensitive matches all case combinations.

### Implementation for User Story 4

- [x] T004 [US4] Add `case_insensitive: bool = False` parameter to `NodeGetListByAttributeValueQuery.__init__` in `backend/infrahub/core/query/node.py`
- [x] T005 [US4] In `query_init`, when `case_insensitive=True`: use `toLower(toString(av.value)) CONTAINS toLower(toString($search_value))`. When `False`: keep existing 4-variation approach in `backend/infrahub/core/query/node.py`
- [x] T006 [US4] Add `WITH DISTINCT n` after main query body to ensure `get_count_query()` counts distinct nodes and remove `DISTINCT` from `return_labels` in `backend/infrahub/core/query/node.py`
- [x] T007 [US4] Unify `search_resolver` to use single `NodeGetListByAttributeValueQuery` call for both paths, passing `case_insensitive=not case_sensitive`, `offset=offset`, `limit=limit` in `backend/infrahub/graphql/queries/search.py`
- [x] T008 [US4] Replace `response["count"] = len(results)` with `response["count"] = await query.count(db=graphql_context.db)` for true total count in `backend/infrahub/graphql/queries/search.py`
- [x] T009 [US4] Remove Python-side `results[offset : offset + limit]` slice (Cypher handles pagination natively) in `backend/infrahub/graphql/queries/search.py`
- [x] T010 [US4] Update `test_search_anywhere_count_reflects_fetched_results` to assert true total (count=2 even with limit=1) in `backend/tests/component/graphql/queries/test_search.py`
- [x] T011 [US4] Add `test_search_anywhere_pagination_consistency` test: page 1 + page 2 cover all results without duplicates, count stable across pages in `backend/tests/component/graphql/queries/test_search.py`

**Checkpoint**: Both search paths use a single Cypher query. Pagination is correct: true total count, no duplicates across pages, deterministic ordering. 42 tests passing.

---

## Phase 4: User Story 1 - Scrollable Search Results Dropdown (Priority: P1) 🎯 MVP

**Goal**: Increase the dropdown result limit from 4 to 10 and make the results list scrollable with a visible scrollbar.

**Independent Test**: Type a search query that matches more than 5 items → dropdown shows scrollable list of up to 10 results with a visible scrollbar. Keyboard navigation still works.

### Implementation for User Story 1

- [x] T012 [US1] Change GraphQL query limit from 4 to 10 in `frontend/app/src/entities/navigation/api/search.ts`
- [x] T013 [US1] Add max-height constraint and `overflow-y: auto` to the `Command.List` container to create a scrollable area in `frontend/app/src/entities/navigation/ui/search-anywhere/search-anywhere.tsx`
- [x] T014 [US1] No internal cap exists in `SearchNodes` — it renders all results from the query. No changes needed.
- [x] T015 [US1] cmdk natively handles scroll-into-view for focused items. No additional changes needed.

**Checkpoint**: Dropdown now shows up to 10 scrollable results. Existing search UX (keyboard nav, result display, click-to-navigate) preserved.

---

## Phase 5: User Story 2 - Total Match Count and "View All Results" Link (Priority: P1)

**Goal**: Display total match count at the bottom of the dropdown and provide a "View all X results" link that navigates to the full search results page.

**Independent Test**: Perform a search → bottom of dropdown shows "View all X results" with correct total count. Click it → navigates to `/search?q=<query>`. For 0 results, show "No results found" without a link.

### Implementation for User Story 2

- [x] T016 [US2] Create `SearchAnywhereFooter` component — self-contained with cmdk state, React Query hook, and Link in `frontend/app/src/entities/navigation/ui/search-anywhere/search-anywhere-footer.tsx`
- [x] T017 [US2] Integrate `SearchAnywhereFooter` into search-anywhere.tsx below Command.List, inside Command wrapper for cmdk state access
- [x] T018 [US2] Edge cases handled: footer returns null when count <= 0 or no query; "No results found" via existing SearchAnywhereEmpty
- [x] T019 [US2] closeDialog called on Link onClick — dialog closes before navigation
- [x] T020 [US2] Tighten footer visual balance: reduce padding (`py-2` → `py-1`), use smaller text (`text-sm` → `text-xs`), compact icon size in `frontend/app/src/entities/navigation/ui/search-anywhere/search-anywhere-footer.tsx`

**Checkpoint**: Dropdown shows accurate total count with compact "View all" link. Link navigates to `/search?q=<query>`.

---

## Phase 6: User Story 3 - Full Search Results Page with Table View (Priority: P2)

**Goal**: Create a dedicated `/search` page that displays all matching results grouped by node type in sortable tables, ordered by group count descending, with an editable search bar.

**Independent Test**: Navigate to `/search?q=<query>` directly in the browser → page shows grouped results by node type in sortable tables. Modify the query in the search bar → results update. Share the URL → same results appear.

### Implementation for User Story 3

- [x] T021 [P] [US3] Create TypeScript type definitions for search results page: `SearchResultsGroup` (kind, label, count, results), page state types in `frontend/app/src/entities/search-results/types.ts`
- [x] T022 [P] [US3] Create GraphQL query function for paginated search (reusing `InfrahubSearchAnywhere` with offset support) in `frontend/app/src/entities/search-results/api/search-results.ts`
- [x] T023 [P] [US3] Create query key factory for search results cache management (include branch, date, query, offset) in `frontend/app/src/entities/search-results/domain/search-results.query-keys.ts`
- [x] T024 [US3] Create React Query hook that fetches search results and groups them by `kind` field, sorted by group count descending in `frontend/app/src/entities/search-results/domain/search-results.query.ts`
- [x] T025 [US3] Create `SearchResultsHeader` component with editable search input (pre-filled from URL query param), total result count badge, auto-focus on mount, and `/` keyboard shortcut to focus input in `frontend/app/src/entities/search-results/ui/search-results-header.tsx`
- [x] T026 [US3] Create `SearchResultsGroup` component that renders a collapsible section with type name heading, result count badge, and DataTable in `frontend/app/src/entities/search-results/ui/search-results-group.tsx`
- [x] T027 [US3] Create `SearchResultsPage` component that orchestrates header + groups list, handles loading/empty states, expand/collapse all, and manages URL query param sync in `frontend/app/src/entities/search-results/ui/search-results-page.tsx`
- [x] T028 [US3] Create route page component that exports `Component` for lazy loading in `frontend/app/src/pages/search-results/index.tsx`
- [x] T029 [US3] Add `/search` route to the router configuration (within authenticated routes, after schema provider) in `frontend/app/src/app/router.tsx`

**Checkpoint**: Full search results page is functional at `/search?q=<query>`. Results grouped by type, sortable tables, editable search bar with keyboard focus, URL bookmarkable.

---

## Phase 7: User Story 5 - Permission-Aware Search Filtering (Priority: P2)

**Goal**: Filter search results by the requesting user's model-level read permissions so that restricted users only see results for node types they are authorized to view. Admin/unrestricted users bypass the filter entirely (zero overhead).

**Independent Test**: Configure a user with restricted model-level read permissions → search as that user → verify only permitted node types appear in results and count reflects only permitted results. Search as admin → verify identical behavior to current (no regression).

### Implementation for User Story 5

- [x] T030 [US5] Add `allowed_kinds: list[str] | None = None` parameter to `NodeGetListByAttributeValueQuery.__init__` in `backend/infrahub/core/query/node.py`
- [x] T031 [US5] In `query_init`, when `allowed_kinds` is provided: add `AND n.kind IN $allowed_kinds` filter after existing kind filter. Set `self.params["allowed_kinds"] = self.allowed_kinds` in `backend/infrahub/core/query/node.py`
- [x] T032 [US5] Add helper function `compute_allowed_search_kinds` to `backend/infrahub/graphql/queries/search.py` that: checks `is_super_admin()` (return None for skip), enumerates schemas via `registry.get_full_schema()`, checks `resolve_object_permission()` per kind, returns `list[str]` of allowed kinds or None
- [x] T033 [US5] Call `compute_allowed_search_kinds` in `search_resolver` before query execution. If result is empty list, short-circuit with count=0, edges=[]. Otherwise pass `allowed_kinds` to `NodeGetListByAttributeValueQuery` in `backend/infrahub/graphql/queries/search.py`
- [x] T034 [US5] Add component test: restricted user searching returns only permitted node types in results and count in `backend/tests/component/graphql/queries/test_search.py`
- [x] T035 [US5] Add component test: admin/super-admin user sees all results (no regression, no `allowed_kinds` filter applied) in `backend/tests/component/graphql/queries/test_search.py`
- [x] T036 [US5] Add component test: user with no read permissions for any type gets empty results (count=0, edges=[]) in `backend/tests/component/graphql/queries/test_search.py`

**Checkpoint**: Search results respect model-level read permissions. Admin users have zero overhead. Restricted users see only permitted results with correct count. Empty permissions return empty results.

---

## Phase 8: Polish & Cross-Cutting Concerns

**Purpose**: Final integration, testing, and quality assurance across all stories.

- [x] T037 [P] Add Playwright E2E test: type query in search anywhere → verify scrollable dropdown with >5 results → click "View all" → verify full results page loads with grouped tables in `frontend/app/tests/e2e/search-results.spec.ts`
- [x] T038 [P] Add Vitest unit tests for search results grouping logic (group by kind, sort by count desc, empty groups filtered) in `frontend/app/src/entities/search-results/domain/search-results.query.test.ts`
- [x] T039 Add Towncrier changelog fragment for the enhanced search feature in `changelog/`
- [x] T040 Add Towncrier changelog fragment for permission-aware search filtering in `changelog/`
- [x] T041 Run `uv run invoke format` and `cd frontend/app && npm run biome:fix` to ensure code passes formatting gates
- [x] T042 Run `uv run invoke lint` and `uv run mypy backend/infrahub/graphql/queries/search.py` to verify type safety
- [ ] T043 Run quickstart.md verification checklist to validate all acceptance scenarios (requires running dev environment for manual verification)

---

## Dependencies & Execution Order

### Phase Dependencies

- **Phase 1 (Setup)**: No-op for this feature
- **Phase 2 (Foundational)**: Backend offset param — BLOCKS all frontend work ✅ DONE
- **Phase 3 (US4)**: Backend pagination fix — BLOCKS reliable count/pagination ✅ DONE
- **Phase 4 (US1)**: Depends on Phase 2/3 — scrollable dropdown ✅ DONE
- **Phase 5 (US2)**: Depends on US1 (modifies same dialog component) ✅ DONE
- **Phase 6 (US3)**: Depends on Phase 2/3 — full results page ✅ DONE
- **Phase 7 (US5)**: Depends on Phase 3 (US4) — extends the unified query with permission filter. **NEXT**
- **Phase 8 (Polish)**: Depends on all user stories being complete

### User Story Dependencies

- **User Story 4 (P1)**: Backend-only, no frontend dependencies ✅ DONE
- **User Story 1 (P1)**: Depends on backend foundational (Phase 2) only ✅ DONE
- **User Story 2 (P1)**: Depends on US1 (modifies the same dialog component) ✅ DONE
- **User Story 3 (P2)**: Depends on backend foundational (Phase 2); independently testable via direct URL ✅ DONE
- **User Story 5 (P2)**: Depends on US4 (extends unified query); backend-only changes **PENDING**

### Within User Story 5

- T030-T031: Sequential (add param first, then use it in query_init)
- T032-T033: Sequential (create helper, then integrate into resolver)
- T030-T031 and T032 can run in parallel (different files)
- T034-T036: Parallel (independent test cases in same file, but different test functions)

### Parallel Opportunities

- **Phase 7**: T030-T031 (node.py) and T032 (search.py) can run in parallel (different files)
- **Phase 7**: T034, T035, T036 can all run in parallel (different test functions)
- **Phase 8**: T037, T038 already done; T040-T042 can run in parallel

---

## Implementation Strategy

### Completed Work

1. ✅ Phase 2: Backend offset param (T001-T003)
2. ✅ Phase 3 (US4): Backend pagination fix — unified query, true count, WITH DISTINCT (T004-T011)
3. ✅ Phase 4 (US1): Scrollable dropdown (T012-T015)
4. ✅ Phase 5 (US2): Total count + "View all" link + visual tightening (T016-T020)
5. ✅ Phase 6 (US3): Full results page with keyboard navigation (T021-T029)

### Remaining Work

6. **Phase 7 (US5)**: Permission-aware filtering (T030-T036) — **7 tasks**
7. **Phase 8**: Polish — changelog, format, lint, verify (T040-T043) — **4 tasks**

### Next Steps

1. Implement T030-T033 (query + resolver changes for permission filtering)
2. Implement T034-T036 (component tests for permission filtering)
3. Complete T040-T043 (polish)
4. **VALIDATE**: Full end-to-end flow including permission checks

---

## Notes

- [P] tasks = different files, no dependencies
- [Story] label maps task to specific user story for traceability
- US4 (backend pagination) was a prerequisite fix that enabled reliable count/pagination for US1-US3
- US5 (permissions) extends the unified query from US4 — it adds `allowed_kinds` parameter without changing existing behavior
- Admin fast-path (`is_super_admin()`) ensures zero overhead for unrestricted users
- All frontend components follow Feature-Sliced Design: `api/` → `domain/` → `ui/`
- Reuse existing `DataTable`, `getObjectTableColumns()`, `useSchema()` — do not create new abstractions
- Permission helper uses existing `PermissionManager`, `ObjectPermission`, `extract_camelcase_words` — no new dependencies
