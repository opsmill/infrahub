# Tasks: GraphQL Fragment Inlining at Import

**Input**: Design documents from `/specs/infp-496-graphql-fragment-inlining/`
**Prerequisites**: plan.md ✓, spec.md ✓, research.md ✓, data-model.md ✓, contracts/ ✓, quickstart.md ✓
**SDK Spec**: `python_sdk/dev/specs/infp-496-graphql-fragment-inlining/tasks.md` (SDK-scoped task view)

**Organization**: Tasks grouped by user story to enable independent implementation and testing.
Primary implementation is in **`python_sdk/`**; backend integration is additive only.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (e.g., US1, US2, US3)
- Include exact file paths in descriptions

---

## Phase 1: Setup (Fixture Repository)

**Purpose**: Create the fixture repository used by all unit and component tests. These files are
needed before any test can run.

- [X] T001 Create fixture repo directory structure at `python_sdk/tests/fixtures/repos/fragment_inlining/`
- [X] T002 [P] Create fragment files `interfaces.gql` (defines `interfaceFragment`, `portFragment`) and `devices.gql` (defines `deviceFragment` that spreads `...interfaceFragment`, and `chassisFragment`) in `python_sdk/tests/fixtures/repos/fragment_inlining/fragments/`
- [X] T003 [P] Create query files `query_two_files.gql`, `query_no_fragments.gql`, `query_transitive.gql`, `query_missing_fragment.gql` in `python_sdk/tests/fixtures/repos/fragment_inlining/queries/`
- [X] T004 Create `.infrahub.yml` declaring `graphql_fragments` (both fragment files) and `graphql_queries` (all four query files) in `python_sdk/tests/fixtures/repos/fragment_inlining/`

---

## Phase 2: Foundational (SDK Core — Blocking Prerequisites)

**Purpose**: The exception types, config model, and renderer must exist before any user story
implementation or test can proceed.

**⚠️ CRITICAL**: No user story work can begin until this phase is complete.

- [X] T005 Add `GraphQLQueryError` base class plus five typed exception classes (`QuerySyntaxError`, `FragmentNotFoundError`, `DuplicateFragmentError`, `CircularFragmentError`, `FragmentFileNotFoundError`) to `python_sdk/infrahub_sdk/exceptions.py`; update `handle_exception()` in `ctl/utils.py` to catch `GraphQLQueryError`
- [X] T006 Add `InfrahubRepositoryFragmentConfig` model with `name`, `file_path`, and `load_fragments()` method to `python_sdk/infrahub_sdk/schema/repository.py`
- [X] T007 Add `graphql_fragments: list[InfrahubRepositoryFragmentConfig]` field to `InfrahubRepositoryConfig` in `python_sdk/infrahub_sdk/schema/repository.py`
- [X] T008 Create `python_sdk/infrahub_sdk/graphql/query_renderer.py` with public functions `build_fragment_index` and `collect_required_fragments`
- [X] T009 Add `render_query_with_fragments(query_str, fragment_files) -> str` low-level entry point and `render_query(name, config, relative_path) -> str` high-level entry point to `python_sdk/infrahub_sdk/graphql/query_renderer.py`

**Checkpoint**: SDK core complete — all user story phases and CLI integration can now proceed

---

## Phase 3: User Story 1 — Import Query with Fragment Spreads Resolved Across Multiple Files (Priority: P1) 🎯 MVP

**Goal**: A repository with multiple declared fragment files syncs correctly — only required fragment
definitions are inlined into each stored query; unreferenced definitions are excluded.

**Independent Test**: Push a repo with two fragment files and a query using one fragment from each.
After sync, retrieve the stored query and verify it contains exactly those two fragment definitions
and executes without error (see quickstart.md Verify Your Work section).

- [X] T010 [P] [US1] Write unit tests for direct fragment spread (single-file, multi-file), no-spread passthrough, and deduplication in `python_sdk/tests/unit/sdk/graphql/test_fragment_renderer.py`
- [X] T011 [P] [US1] Write unit tests for `InfrahubRepositoryFragmentConfig` YAML parsing, `load_fragments()` for file and directory paths, and `FragmentFileNotFoundError` in `python_sdk/tests/unit/sdk/test_schema_repository.py`
- [X] T012 [US1] Update `import_all_graphql_query()` in `backend/infrahub/git/integrator.py` to call `render_query()` per query instead of `load_query()`; catch `InfrahubSdkError`, log with the query name, and re-raise — any fragment error fails the sync (FR-009)
- [X] T013 [US1] Write component tests for US1 scenarios (two fragment files, exact two definitions stored; no-spread query stored unchanged) in `backend/tests/component/git/test_graphql_query_import.py`

**Checkpoint**: US1 fully functional — basic multi-file fragment sync works end-to-end

---

## Phase 4: User Story 2 — Transitive Fragment Dependencies Resolved Automatically (Priority: P2)

**Goal**: When fragment A spreads `...B` and `B` is in a different file, both definitions are
included in the rendered output even though the query only references `A` directly.

**Independent Test**: Sync a query that uses only `...deviceFragment`; verify the stored query
also contains `interfaceFragment` (transitively required by `deviceFragment`).

- [X] T014 [P] [US2] Write unit tests for transitive resolution (A→B across files, multi-hop) and surplus-fragment exclusion in `python_sdk/tests/unit/sdk/graphql/test_fragment_renderer.py`
- [X] T015 [US2] Write component test for transitive dependency sync (query spreads `...deviceFragment` only, stored query contains both `deviceFragment` and `interfaceFragment`) in `backend/tests/component/git/test_graphql_query_import.py`

**Checkpoint**: US1 + US2 both independently testable

---

## Phase 5: User Story 4 — Query Import Fails Gracefully When Fragment Is Unresolved (Priority: P2)

**Goal**: A query referencing an undeclared fragment produces a clear error identifying the
missing fragment name and query file; other queries in the same repo still import successfully.

**Independent Test**: Import a repo containing `query_missing_fragment.gql`; verify that query
fails with a `FragmentNotFoundError` naming the missing fragment, and the other three queries
succeed.

- [X] T016 [P] [US4] Write unit tests for `FragmentNotFoundError`, `DuplicateFragmentError` (cross-file and within-file), and `CircularFragmentError` (A→B→A cycle) in `python_sdk/tests/unit/sdk/graphql/test_fragment_renderer.py`
- [X] T017 [US4] Write component tests for US4 (unresolved fragment → sync raises `FragmentNotFoundError`; missing fragment file → sync raises `FragmentFileNotFoundError` with file path) in `backend/tests/component/git/test_graphql_query_import.py`

**Checkpoint**: US1 + US2 + US4 all independently testable

---

## Phase 6: User Story 5 — Re-sync Updates Dependent Queries When Fragment File Changes (Priority: P2)

**Goal**: After a fragment definition is updated in the repository, re-syncing causes all queries
that used that fragment to be re-rendered and updated in the database.

**Independent Test**: Sync a repo, update a fragment file, re-sync, and verify the stored query
text reflects the updated field selection.

- [X] T018 [US5] Write component test for re-sync (sync → update fragment → re-sync → stored query reflects new definition) in `backend/tests/component/git/test_graphql_query_import.py`

**Checkpoint**: US1 + US2 + US4 + US5 all independently testable

---

## Phase 7: infrahubctl CLI Integration (enables US1 + US4 for local workflows)

**Goal**: `infrahubctl` local execution paths apply the same fragment rendering so local queries
with fragment spreads work without a server import step (FR-016).

**Independent Test**: Run `infrahubctl run` with a query that uses fragment spreads from declared
`graphql_fragments` entries; verify the query executes without unresolved-spread errors.

- [X] T019 [P] [US1] Update `execute_graphql_query()` in `python_sdk/infrahub_sdk/ctl/utils.py` to call `render_query(name=query, config=repository_config)` instead of `query_object.load_query()`
- [X] T020 [P] [US1] Update `transform()` in `python_sdk/infrahub_sdk/ctl/cli_commands.py` to call `render_query(name=transform.query, config=repository_config)` instead of `get_query(...).load_query()`

**Checkpoint**: Both server sync and infrahubctl CLI paths apply fragment rendering

---

## Phase 8: User Story 3 — Fragment File Scoped Per Repository (Priority: P3)

**Goal**: Fragment files from one repository are not accessible when importing queries from a
different repository. The same fragment name in two repos resolves to each repo's own definition.

**Independent Test**: Sync two repositories each declaring `deviceFragment` with different field
selections; verify each stored query uses the fragment from its own repository.

- [X] T021 [US3] Write component test for per-repository fragment isolation (two repos, same fragment name, different definitions → each uses own definition) in `backend/tests/component/git/test_graphql_query_import.py`

**Checkpoint**: All user stories independently testable and complete

---

## Phase 9: Polish & Cross-Cutting Concerns

**Purpose**: Documentation, changelog, and final validation across all components.

- [X] T022 [P] Add user-facing changelog fragment in `changelog/` describing `graphql_fragments` support (Towncrier format)
- [X] T023 [P] Update `.infrahub.yml` reference page in `docs/` to document the `graphql_fragments` section with `name` and `file_path` fields and YAML examples
- [ ] T024 Run `uv run invoke docs-generate` in `python_sdk/` to regenerate SDK CLI + config docs after docstring changes
- [ ] T025 [P] Run `uv run invoke format lint-code` in `python_sdk/` and `uv run invoke format lint` in backend to verify no linting violations

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies — can start immediately
- **Foundational (Phase 2)**: Depends on Phase 1 completion — BLOCKS all user stories
- **US1 (Phase 3)**: Depends on Phase 2 — **also required before Phases 4–7**
- **US2 (Phase 4)**: Depends on Phase 2 (renderer already handles transitive resolution, Phase 3 backend integration already in place)
- **US4 (Phase 5)**: Depends on Phase 2 (error types already in renderer)
- **US5 (Phase 6)**: Depends on Phase 3 backend integration (re-sync uses existing sync loop)
- **CLI Integration (Phase 7)**: Depends on Phase 2 — **independent of Phases 3–6**
- **US3 (Phase 8)**: Depends on Phase 3 backend integration
- **Polish (Phase 9)**: Depends on all desired phases being complete

### User Story Dependencies

- **US1 (P1)**: Start after Foundational (Phase 2) — no story dependencies
- **US2 (P2)**: Start after Foundational — renderer transitive logic already implemented in T008/T009
- **US4 (P2)**: Start after Foundational — error types already in T005, renderer error handling in T008
- **US5 (P2)**: Start after US1 backend integration (T012) — re-sync is the existing sync loop
- **US3 (P3)**: Start after US1 backend integration (T012) — scoping is inherent in the per-repo design
- **CLI Integration**: Start after Foundational (Phase 2) — independent of backend phases

### Within Each Phase

- Tasks within a phase with [P] labels can run in parallel
- T006 and T007 can be done together (same file) but must follow T005
- T008 must follow T005 (uses exception types); T009 follows T008
- T010 and T011 are independent [P] — different test files
- T019 and T020 are independent [P] — different CLI files
- T022, T023, T025 are independent [P] within Phase 9

---

## Parallel Execution Examples

### Phase 1 Parallel

```bash
# Run in parallel after T001:
Task T002: Create fragment files in python_sdk/tests/fixtures/repos/fragment_inlining/fragments/
Task T003: Create query files in python_sdk/tests/fixtures/repos/fragment_inlining/queries/
```

### Phase 3 Parallel

```bash
# Run in parallel after Phase 2 complete:
Task T010: Unit tests for renderer (basic scenarios) in test_fragment_renderer.py
Task T011: Unit tests for repository config in test_repository.py
```

### Phase 7 Parallel

```bash
# Run in parallel after Phase 2 complete (independent of Phase 3):
Task T019: Update execute_graphql_query() in ctl/utils.py
Task T020: Update transform() in ctl/cli_commands.py
```

### Phase 9 Parallel

```bash
# Run in parallel after all implementation phases:
Task T022: Add changelog fragment in changelog/
Task T023: Update docs in docs/
Task T025: Run linting in python_sdk/ and backend/
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1: Setup (fixture repo)
2. Complete Phase 2: Foundational SDK — exceptions, config, renderer
3. Complete Phase 3: US1 — unit tests + backend integration + component tests
4. **STOP and VALIDATE**: `cd python_sdk && uv run pytest tests/unit/sdk/graphql/test_fragment_renderer.py -v`
5. **STOP and VALIDATE**: `uv run pytest backend/tests/component/git/test_graphql_query_import.py -v -k us1`
6. Demo: sync a repo with fragment files and verify stored queries

### Incremental Delivery

1. Phase 1 + Phase 2 → SDK core ready
2. Phase 3 → US1 end-to-end (MVP — core sync path works)
3. Phase 7 → CLI path works (infrahubctl integration)
4. Phase 4 + Phase 5 + Phase 6 → US2, US4, US5 test coverage
5. Phase 8 → US3 isolation test
6. Phase 9 → Docs + changelog

### SDK-First Strategy

Phases 1–2 + T010, T011, T019, T020 can all be completed and validated **entirely within
`python_sdk/`** before touching the backend. Run `cd python_sdk && uv run pytest tests/unit/`
to verify the core SDK work before wiring up the backend.

---

## Notes

- All fragment logic lives in `python_sdk/` — the backend only calls SDK functions (FR-015)
- `python_sdk/` is a git submodule — changes there must be committed separately
- See `python_sdk/dev/specs/infp-496-graphql-fragment-inlining/tasks.md` for the SDK-scoped view
- Backend component tests require a running Neo4j + Infrahub instance (see backend/AGENTS.md)
- Linting: `uv run invoke format lint-code` (SDK) and `uv run invoke format lint` (backend)
