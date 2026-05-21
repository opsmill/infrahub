---
description: "Task list for SOLID restructuring of the `infrahub.git` module (INFP-546)"
---

# Tasks: SOLID Restructuring of `infrahub.git`

**Input**: Design documents from `dev/specs/infp-546-git-solid-refactor/`
**Prerequisites**: plan.md (required), spec.md (required), research.md, data-model.md, contracts/, quickstart.md

**Tests**: Tests are MANDATORY for this work. Spec Guiding Constraint 6 ("Tests first where behavior is at risk") and FR-022 (opportunistic mock removal) make test work a deliverable in every PR, not optional.

**Organization**: Tasks are grouped by user story (six stories from `spec.md`). Each task corresponds to a single PR or a discrete unit of PR-internal work. Per FR-017, no task touches more than one collaborator boundary, moved method, correctness contract, new protocol, or scenario family.

## Format: `[ID] [P?] [Story] Description`

- `[P]` = parallelizable (different files, no dependency on incomplete tasks).
- `[Story]` = which user story the task belongs to (`US1`–`US6`).
- File paths are exact.

## Path Conventions

Single-project monorepo under `backend/`. New module-level code lands in `backend/infrahub/git/`; tests in `backend/tests/unit/git/` and `backend/tests/integration/git/`.

---

## Phase 1: Setup

**Purpose**: Verify local pre-conditions and tooling before any structural change lands.

- [X] T001 Verify Gogs fixture starts cleanly: run `uv run pytest backend/tests/integration/git/test_delete_git_branch_gogs.py -v` and confirm Testcontainers can pull/start the Gogs image
- [X] T002 [P] Capture baseline type-checker suppression footprint by saving the current `pyproject.toml` mypy/ty override blocks (lines 358-374) plus a count of inline `# type: ignore` in `backend/infrahub/git/` to `dev/specs/infp-546-git-solid-refactor/baseline-suppressions.txt` — used by every PR to verify FR-018 union invariant
- [X] T003 [P] Capture public-symbol baseline by listing every name exported from `backend/infrahub/git/__init__.py`, `repository.py`, `base.py`, `integrator.py`, `tasks.py`, `models.py`, `utils.py` and saving to `dev/specs/infp-546-git-solid-refactor/baseline-symbols.txt` — used by every PR to verify FR-013 surface preservation

---

## Phase 2: Foundational

**Purpose**: None. This refactor has no globally-blocking foundational work — User Stories 1, 2, and 3 can start in parallel after Phase 1. Story 4 needs Stories 1 + 3 to land first; Story 5 needs Story 1; Story 6 needs Story 3. See `Dependencies & Execution Order` below.

---

## Phase 3: User Story 1 — Verifiable behavior under real Git failure conditions (P1) 🎯 MVP PREREQUISITE

**Goal**: Establish a real-remote safety net covering six scenario families before any structural change lands. Each family ships as one PR.

**Independent Test**: Run `uv run invoke backend.test-integration -- backend/tests/integration/git/` against the Gogs fixture. All new scenario tests pass against the current implementation, pinning behavior for later refactors.

**Note on test-design**: Each scenario asserts the *current* behavior, not a target behavior. Where current behavior is surprising or wrong, the test pins it as-is with a comment referencing the tracking ticket (per spec Edge Cases).

- [X] T004 [P] [US1] Create `backend/tests/integration/git/test_auth_and_access.py` covering: (a) wrong-credentials clone raises typed `RepositoryCredentialsError` with the remote response reachable on the chained `GitCommandError.stderr`; (b) no-write-access user push currently surfaces a bare `GitCommandError` carrying the server's HTTP 403 — pinned as-is per spec Edge Cases because no typed access-denied exception exists today. Adding a typed access-denied error is a behavior change out of scope for this refactor; surface it in the SC-010 audit (T068) so a follow-up PR can add the registry pattern and tighten this assertion in the same diff. — Story 1 family 1, spec acceptance 1-2, FR-001
- [X] T005 [P] [US1] Create `backend/tests/integration/git/test_push_failures.py` covering non-fast-forward rejection and protected-branch rejection — Story 1 family 2, spec acceptance 3-4
- [ ] T006 [P] [US1] Create `backend/tests/integration/git/test_merge_scenarios.py` covering real conflicting file changes (no mock or string-pattern shortcut) and merge of a commit not present locally — Story 1 family 3, spec acceptance 5-6
- [ ] T007 [P] [US1] Create `backend/tests/integration/git/test_readonly_repository_real.py` covering sync with branch churn (gained + deleted), tag-based ref checkout (existing/missing/deleted), and `update_latest_commit` against a force-pushed remote where the previously-known commit no longer exists — Story 1 family 4, spec acceptance 7-9
- [ ] T008 [P] [US1] Create `backend/tests/integration/git/test_repository_setup.py` covering `InfrahubRepository.new()` against a reachable URL with no repository (404 → typed not-found error) and clone of an empty repository — Story 1 family 5, spec acceptance 10-11
- [ ] T009 [P] [US1] Create `backend/tests/integration/git/test_sync_mismatches.py` covering `sync()` where remote commits conflict with a populated local worktree — Story 1 family 6, spec acceptance 12
- [ ] T010 [US1] Verify Story 1 CI gate: confirm `backend/tests/integration/git/` runs by default in the CI configuration that gates merges to `develop`; if it doesn't, add it (FR-002, SC-005)

**Checkpoint**: Safety net in place. Stories 2, 4, 5 can now make structural changes against a verified baseline.

---

## Phase 4: User Story 2 — Correctness fixes (P1)

**Goal**: Three PRs that make declared contracts match runtime behavior — no behavior change, only annotation/contract/structure.

**Independent Test**: Reading the merge signature predicts the return type; reading the read-only commit-value method makes the network call explicit; adding a new error pattern is a one-line registry append.

### Merge return-type annotation (1 PR)

- [ ] T011 [US2] Update `backend/infrahub/git/repository.py:161` `merge` annotation from `-> bool` to `-> str | Literal[False]`; add `from typing import Literal` (FR-003, behavior unchanged — verified by Story 1 safety net)
- [ ] T012 [US2] Confirm mypy passes cleanly on the new annotation across all `merge` call sites; if any call site previously relied on the wrong type, document the existing call-site `isinstance` check (SC-006 follow-up tracks removal)

### Read-only `get_commit_value` contract (1 PR)

- [ ] T013 [US2] Tighten the docstring on `backend/infrahub/git/repository.py:230` `InfrahubReadOnlyRepository.get_commit_value` to explicitly state "always fetches from origin and returns the resolved commit; `branch_name` is preserved for interface compatibility and is ignored" (FR-004, D6)
- [ ] T014 [US2] Add `backend/tests/integration/git/test_readonly_get_commit_value.py` with a pinning test that asserts `git_repo.remotes.origin.fetch` is called exactly once per invocation of `get_commit_value` (FR-004 acceptance — call-count assertion is mandatory, not "returns successfully")

### Error-pattern registry (1 PR)

- [ ] T015 [US2] Create `backend/infrahub/git/errors.py` with `ErrorContext`, `ErrorRule`, matchers (`any_substring`, `any_substring_ci`, `all_substrings`), named builders (`_connection_error`, `_credentials_error`, `_invalid_branch_error`, `_merge_repository_error`), `ERROR_RULES` tuple (preserving today's order), and `raise_enriched` — see `contracts/error-registry.md` (FR-005)
- [ ] T016 [US2] Convert `backend/infrahub/git/base.py:1083-1115` `_raise_enriched_error_static` to a one-line shim that delegates to `errors.raise_enriched(...)`; in-tree behavior is unchanged (FR-014)
- [ ] T017 [US2] Add `backend/tests/unit/git/test_errors.py` covering each rule (substring match → expected typed exception with preserved message + `__cause__`), the fallthrough generic `RepositoryError`, and a parity test asserting `_raise_enriched_error_static` and `raise_enriched` produce equivalent exceptions for the same input (until shim is removed)

**Checkpoint**: Declared contracts honest; error registry data-driven; no behavior change.

---

## Phase 5: User Story 3 — Stable abstraction boundary for repository consumers (P2)

**Goal**: Introduce `ReadOnlyRepositoryProtocol` and `RepositoryProtocol` as the consumer-facing interface; migrate at least one caller.

**Independent Test**: Both concrete classes (`InfrahubRepository`, `InfrahubReadOnlyRepository`) structurally satisfy both protocols; at least one in-tree consumer types its parameter against the protocol; no existing import is broken.

- [ ] T018 [P] [US3] FR-020 caller audit: grep every reference to `InfrahubRepository` and `InfrahubReadOnlyRepository` in `backend/` (excluding `backend/infrahub/git/` itself); produce `dev/specs/infp-546-git-solid-refactor/caller-audit.md` listing each call site and the methods it invokes — this finalizes the protocol method set
- [ ] T019 [US3] Create `backend/infrahub/git/protocols.py` with `ReadOnlyRepositoryProtocol` and `RepositoryProtocol(ReadOnlyRepositoryProtocol, Protocol)`; method set derived from T018's audit and `contracts/protocols.md`
- [ ] T020 [US3] Re-export `ReadOnlyRepositoryProtocol` and `RepositoryProtocol` from `backend/infrahub/git/repository.py`; update `__all__` if defined; do NOT change `backend/infrahub/git/__init__.py` unless explicitly desired (FR-013)
- [ ] T021 [P] [US3] Add `backend/tests/unit/git/test_protocols.py` with structural-typing assertions: a typed variable of each protocol type is assigned each concrete class; mypy run on the test catches a missing method — see `contracts/protocols.md` "Verification"
- [ ] T022 [US3] Migrate at least one consumer identified in T018 to type its repository parameter against `ReadOnlyRepositoryProtocol` (pick the smallest single-caller PR); tests still pass; opportunistically remove any mock the migration makes unnecessary per FR-022
- [ ] T023 [US3] Narrow or remove any `infrahub.git.base` `attr-defined` mypy override that the protocol introduction makes redundant; verify via T002's baseline (FR-018, FR-019)

**Checkpoint**: Protocol surface exists, consumers can depend on it, suppression union has not grown.

---

## Phase 6: User Story 4 — Separable file-import responsibility (P2)

**Goal**: Extract `RepositoryFileImporter` collaborator; move each of the seven `import_*` lifecycles into its own handler.

**Independent Test**: Each `import_*` integrator method becomes a one-line delegate to the importer; adding a new object type is one new handler file + one constructor registration line — no edit to `import_objects_from_files` or any other integrator method.

**Order**: T024 first (collaborator). Handlers (T025-T038) all touch `integrator.py` (constructor + delegate), so they are sequential, not parallel. Each handler's per-type test file (T039-T045) IS parallel-safe with later handlers. Final cleanup (T046) runs after every caller has migrated.

### Collaborator (1 PR)

- [ ] T024 [US4] Create `backend/infrahub/git/importer/__init__.py` with `RepositoryFileImporter`, `FileImportHandler` protocol, and `DiscoveredFile` dataclass (per `contracts/file-importer.md`); instantiate `self.file_importer = RepositoryFileImporter(repository=self)` in `InfrahubRepositoryIntegrator` constructor; add `backend/tests/unit/git/test_importer.py` round-trip test with a no-op `FileImportHandler` registered and called via `import_all`

### Per-type handler extraction (7 PRs — each PR = a handler file + register + delegate + unit test)

- [ ] T025 [US4] Create `backend/infrahub/git/importer/schema.py` with `SchemaFileHandler` carrying the body of today's `import_schema_files` (integrator.py:513) — split into `discover` + `reconcile`; preserve behavior verbatim (FR-014)
- [ ] T026 [US4] Register `SchemaFileHandler` in `InfrahubRepositoryIntegrator` constructor; convert `import_schema_files` to a one-line delegate per FR-016 — `return await self.file_importer.import_one(handler_name="schema", ...)`; FR-020 audit: grep `patch("infrahub.git.integrator.InfrahubRepositoryIntegrator.import_schema_files"` and update any affected tests in the same PR
- [ ] T027 [P] [US4] Add `backend/tests/unit/git/test_schema_handler.py` exercising `SchemaFileHandler.discover` and `reconcile` against a `FakeRepositoryProtocol`
- [ ] T028 [US4] Create `backend/infrahub/git/importer/graphql_query.py` with `GraphqlQueryHandler` from `import_all_graphql_query` (integrator.py:585); register + delegate; FR-020 audit
- [ ] T029 [P] [US4] Add `backend/tests/unit/git/test_graphql_query_handler.py`
- [ ] T030 [US4] Create `backend/infrahub/git/importer/python_check.py` with `PythonCheckHandler` from `import_python_check_definitions` (integrator.py:657); register + delegate; FR-020 audit
- [ ] T031 [P] [US4] Add `backend/tests/unit/git/test_python_check_handler.py`
- [ ] T032 [US4] Create `backend/infrahub/git/importer/generator.py` with `GeneratorHandler` from `import_generator_definitions` (integrator.py:728); register + delegate; FR-020 audit
- [ ] T033 [P] [US4] Add `backend/tests/unit/git/test_generator_handler.py`
- [ ] T034 [US4] Create `backend/infrahub/git/importer/python_transform.py` with `PythonTransformHandler` from `import_python_transforms` (integrator.py:820); register + delegate; FR-020 audit
- [ ] T035 [P] [US4] Add `backend/tests/unit/git/test_python_transform_handler.py`
- [ ] T036 [US4] Create `backend/infrahub/git/importer/jinja2_transform.py` with `Jinja2TransformHandler` from `import_jinja2_transforms` (integrator.py:241); register + delegate; FR-020 audit
- [ ] T037 [P] [US4] Add `backend/tests/unit/git/test_jinja2_transform_handler.py`
- [ ] T038 [US4] Create `backend/infrahub/git/importer/artifact_definition.py` with `ArtifactDefinitionHandler` from `import_artifact_definitions` (integrator.py:346); register + delegate; FR-020 audit
- [ ] T039 [P] [US4] Add `backend/tests/unit/git/test_artifact_definition_handler.py`

### Cleanup (1 PR)

- [ ] T040 [US4] Final cleanup: grep the codebase for any remaining caller of the delegated `import_*` methods on the integrator; once all callers use the importer directly (or stay on the delegate intentionally), remove the delegate methods per FR-016 — DO NOT remove if any in-tree caller still uses them (FR-023)

**Checkpoint**: Integrator no longer owns per-type lifecycle logic; a new object type lands as one handler file + one register line (SC-001).

---

## Phase 7: User Story 5 — Domain logic that runs without the workflow engine (P2)

**Goal**: Split every Prefect-decorated method into a private `_impl` + public decorated wrapper. Unit tests exercise `_impl` without workflow-engine initialization.

**Independent Test**: For each of the 17 decorated methods (16 on the integrator + 1 in `repository.py`), a unit test calls `_impl` directly and passes without `prefect` runtime setup; the public wrapper is unchanged from a caller's perspective (FR-013).

**Order**: All split tasks touch `integrator.py` (or `repository.py` for T056). They are sequential within a file. Unit-test additions (under `backend/tests/unit/git/`) are parallel-safe with later splits.

**Per-method PR shape**: each task below is one PR that (a) extracts the body of the decorated method into `_<name>_impl`, (b) leaves the wrapper as `return await self._<name>_impl(...)`, (c) adds a unit test exercising `_impl`, (d) removes any newly-obsoleted `# type: ignore[call-overload]` in the same PR (FR-019).

- [ ] T041 [US5] FR-020 mock audit: grep every `unittest.mock.patch(...)` call site in `backend/tests/` that references the public name of any of the 17 decorated methods; produce `dev/specs/infp-546-git-solid-refactor/mock-audit-story5.md` mapping each patch to its destination — informs per-method PRs
- [ ] T042 [US5] Split `import_objects_from_files` (integrator.py:184, `@flow`) into `_import_objects_from_files_impl` + decorated wrapper; add `backend/tests/unit/git/test_import_objects_from_files_impl.py`; remove obsoleted `# type: ignore[call-overload]` (FR-021: in-process callers go through the wrapper, not `_impl`)
- [ ] T043 [US5] Split `import_jinja2_transforms` (integrator.py:241, `@task`) into `_impl` + wrapper; add `test_import_jinja2_transforms_impl.py`; remove ignores
- [ ] T044 [US5] Split `import_artifact_definitions` (integrator.py:346, `@task`); add `test_import_artifact_definitions_impl.py`; remove ignores
- [ ] T045 [US5] Split `get_repository_config` (integrator.py:446, `@task`); add `test_get_repository_config_impl.py`; remove ignores
- [ ] T046 [US5] Split `import_schema_files` (integrator.py:513, `@task`); add `test_import_schema_files_impl.py`; remove ignores — NOTE: post-Story-4 the body of `import_schema_files` is the one-line delegate to `file_importer.import_one`; the `_impl` is similarly thin and the test verifies it; if Story 5 lands BEFORE Story 4 for this method, the `_impl` carries the full original body
- [ ] T047 [US5] Split `import_all_graphql_query` (integrator.py:585, `@task`); add `test_import_all_graphql_query_impl.py`; remove ignores
- [ ] T048 [US5] Split `import_python_check_definitions` (integrator.py:657, `@task`); add `test_import_python_check_definitions_impl.py`; remove ignores
- [ ] T049 [US5] Split `import_generator_definitions` (integrator.py:728, `@task`); add `test_import_generator_definitions_impl.py`; remove ignores
- [ ] T050 [US5] Split `import_python_transforms` (integrator.py:820, `@task`); add `test_import_python_transforms_impl.py`; remove ignores
- [ ] T051 [US5] Split `import_objects` (integrator.py:949, `@task`); add `test_import_objects_impl.py`; remove ignores
- [ ] T052 [US5] Split `get_check_definition` (integrator.py:969, `@task`); add `test_get_check_definition_impl.py`; remove ignores
- [ ] T053 [US5] Split `get_python_transforms` (integrator.py:1009, `@task`); add `test_get_python_transforms_impl.py`; remove ignores
- [ ] T054 [US5] Split `import_all_python_files` (integrator.py:1221, `@flow`); add `test_import_all_python_files_impl.py`; remove ignores
- [ ] T055 [US5] Split `jinja2_template_render` (integrator.py:1231, `@task`); add `test_jinja2_template_render_impl.py`; remove ignores
- [ ] T056 [US5] Split `python_check_execute` (integrator.py:1253, `@task`); add `test_python_check_execute_impl.py`; remove ignores
- [ ] T057 [US5] Split `python_transform_execute` (integrator.py:1317, `@task`); add `test_python_transform_execute_impl.py`; remove ignores
- [ ] T058 [US5] Split `get_initialized_repo` (repository.py:315, `@task`) into `_get_initialized_repo_impl` + decorated wrapper; add `test_get_initialized_repo_impl.py`; remove ignores
- [ ] T059 [US5] Story 5 wrap-up verification: confirm `grep -r "type: ignore\[call-overload\]" backend/infrahub/git/` returns zero matches; if any remain, identify why and either fix in a same-PR follow-up or document — also confirm FR-021 by grepping for `self._*_impl(` references in `backend/infrahub/git/` and verifying every match is in a wrapper or a test, not a sibling business method

**Optional follow-up (decide before T042 lands)**: T060 — add a CI check (small AST script) that scans `backend/infrahub/git/` for `self._<anything>_impl(` calls outside the wrapper method itself; fails if found, enforcing FR-021 mechanically rather than by discipline. This was discussed during plan review; decide whether to schedule or skip.

**Checkpoint**: Every unit test for business logic runs without Prefect initialization (SC-002).

---

## Phase 8: User Story 6 — Substitutable global dependencies (P3)

**Goal**: Make the default-branch name and the SDK client injectable at construction time. Two PRs.

**Independent Test**: A test constructs a repository with a custom `default_branch_name` without touching `registry.default_branch`; reading `repo.client` twice does not mutate the repository's persisted state.

### Default-branch override (1 PR)

- [ ] T061 [US6] Verify that `InfrahubRepositoryBase.default_branch_name` (already a Pydantic field on `base.py`) is honored end-to-end; the `default_branch` property at `base.py:190-192` already falls back to `registry.default_branch` when the field is `None`, so this PR may be annotation/test-only (FR-009)
- [ ] T062 [US6] Add `backend/tests/unit/git/test_constructor_injection.py::test_default_branch_override` constructing an integrator with `default_branch_name="trunk"` and asserting `repo.default_branch == "trunk"` without patching `registry`

### SDK-client lifecycle (1 PR)

- [ ] T063 [US6] Replace `@property sdk` lazy-init at `backend/infrahub/git/base.py:183-188` with a Pydantic `@model_validator(mode="after")` that initializes `self.client = get_client()` exactly once at construction when `client is None`; the public attribute name `sdk` may stay or be replaced by direct `self.client` access — preserve any public access path per FR-013 (D2 of `data-model.md` covers the two acceptable shapes)
- [ ] T064 [US6] Add `backend/tests/unit/git/test_constructor_injection.py::test_sdk_client_no_mutation_on_read` constructing a repository, snapshotting its Pydantic state, reading `repo.client` twice, and asserting state is unchanged between snapshots (FR-010)
- [ ] T065 [US6] Narrow or remove any `infrahub.git.base` mypy override entries that the lazy-init removal makes redundant (FR-018, FR-019)

**Checkpoint**: Tests can substitute the SDK client and default branch via construction; no monkey-patching of `registry` or `get_client` required (SC-002).

---

## Phase 9: Polish & Cross-Cutting Concerns

- [ ] T066 [P] Final FR-018 invariant check: diff `pyproject.toml` mypy/ty override blocks plus inline `# type: ignore` count against T002's baseline; assert the union has not grown
- [ ] T067 [P] Final FR-013 invariant check: diff the public-symbol set of every `backend/infrahub/git/` module against T003's baseline; new symbols allowed, removed/renamed symbols are a regression
- [ ] T068 SC-010 mock-residue audit: for every file under `backend/tests/unit/git/` and `backend/tests/integration/git/`, enumerate every remaining `unittest.mock.patch` and categorize as "intentional" (e.g., simulating network timeouts, third-party failures) or "follow-up candidate"; deliverable is `dev/specs/infp-546-git-solid-refactor/mock-residue-audit.md` attached to the Jira epic
- [ ] T069 Produce a single towncrier changelog fragment in `changelog/` summarizing the structural refactor for release notes (per spec Assumptions — one fragment for the whole work, not per-PR)
- [ ] T070 Run quickstart.md validation end-to-end: pretend to be a new developer following the "add a new repository-defined object type", "add a new typed exception", and "write a read-only consumer" sections; if any instruction is unclear, fix the quickstart in the same PR
- [ ] T071 Mark the work complete in Jira epic IFC-2533 with links to all merged PRs and the audit documents (T068)

---

## Dependencies & Execution Order

### Phase Dependencies

- **Phase 1 (Setup)**: No dependencies — runs first.
- **Phase 2 (Foundational)**: Empty for this work — no globally-blocking content.
- **Phase 3 (Story 1, P1)**: Depends on Phase 1. **MVP prerequisite** — every later structural change is grounded against this safety net.
- **Phase 4 (Story 2, P1)**: Depends on Phase 1 only for the read-only commit-value pinning test (T014); the annotation-only and registry PRs are otherwise independent of Story 1.
- **Phase 5 (Story 3, P2)**: Independent of Phases 3 + 4 — purely additive (protocols, no body change). Can run in parallel with Stories 1 + 2.
- **Phase 6 (Story 4, P2)**: Depends on Phases 3 + 5. Needs the safety net for behavior parity and the protocols so the collaborator can depend on an abstraction.
- **Phase 7 (Story 5, P2)**: Depends on Phase 3 (safety net for parity). Otherwise independent of Stories 2, 3, 4 — touches a different concern (decorator placement) than handlers.
- **Phase 8 (Story 6, P3)**: Depends on Phase 5. Constructor changes land against the stable protocol surface, not the concrete classes.
- **Phase 9 (Polish)**: Depends on all desired story phases being complete.

### Story Independence

- **Story 1**: Independent. Run first.
- **Story 2**: Independent except T014 (needs Story 1 fixture).
- **Story 3**: Independent.
- **Story 4**: Needs Stories 1 + 3.
- **Story 5**: Needs Story 1.
- **Story 6**: Needs Story 3.

### Within Each User Story

- Story 1: All six family files are `[P]`-marked — no dependency between families.
- Story 2: Three PRs are largely independent (different files); within a PR, the docstring/annotation change ships with its test.
- Story 3: T018 audit precedes T019/T020 protocol creation; T022 consumer migration runs last.
- Story 4: Handler creation (T024) precedes per-type extraction; per-type extractions are sequential within `integrator.py` but per-type tests are `[P]`-safe.
- Story 5: T041 audit precedes splits; splits are sequential within `integrator.py`; tests are `[P]`-safe.
- Story 6: T061 (default branch) and T063 (SDK client) are independent; can run in parallel.

### Parallel Opportunities

- **All Phase 1 setup tasks T002, T003** can run in parallel.
- **All Story 1 scenario families T004-T009** can run in parallel (each is a different test file).
- **Story 2's three PRs** can run in parallel (different files).
- **Story 3 can run in parallel with Stories 1, 2** entirely (purely additive).
- **Story 6's two PRs** can run in parallel.
- **Within Story 4 and Story 5**, handler/method extractions touch `integrator.py` so they serialize there; the matching test files are `[P]`-safe.

---

## Parallel Example: Story 1 scenario families

```bash
# All six families are independent test files — open six PRs simultaneously:
Task T004: "Create test_auth_and_access.py — auth/access scenario family"
Task T005: "Create test_push_failures.py — push-failure scenario family"
Task T006: "Create test_merge_scenarios.py — merge scenario family"
Task T007: "Create test_readonly_repository_real.py — read-only scenario family"
Task T008: "Create test_repository_setup.py — repository-setup scenario family"
Task T009: "Create test_sync_mismatches.py — sync-mismatch scenario family"
```

## Parallel Example: Story 3 protocol introduction

```bash
# After T018 audit lands, the protocol module + tests + consumer migration can run on parallel branches:
Task T019: "Create infrahub/git/protocols.py with both protocols"
Task T021: "Add tests/unit/git/test_protocols.py with structural-typing assertions"
# T022 (consumer migration) waits for T019+T020 to land.
```

---

## Implementation Strategy

### MVP First — Story 1 only

Story 1 IS the MVP for this work: it ships the safety net that every later story depends on. Land Phase 1 + Phase 3, then STOP and validate.

1. Complete Phase 1 (T001-T003) — local pre-conditions verified, baselines captured.
2. Complete Phase 3 (T004-T010) — six scenario families landed on `develop`, CI gate confirmed.
3. **Validate**: integration suite runs cleanly on the gate.
4. Demo: the test count delta is the deliverable.

### Incremental Delivery

After Story 1 ships:

1. **Stories 2 + 3 in parallel** (both P1/P2, both independent of each other). Story 2 cleans up declared contracts; Story 3 introduces the protocol surface. Each ships independently.
2. **Story 5 starts** (depends only on Story 1). 17 small PRs in series within `integrator.py`; each one shrinks the inline `# type: ignore[call-overload]` count.
3. **Story 4 starts** once Stories 1 + 3 are in. 1 + 7 + 1 = 9 PRs. Each handler extraction is independently revertable.
4. **Story 6 lands last** once Story 3 has stabilized the protocol surface.
5. **Polish (Phase 9)** closes the work with audit documents and the towncrier fragment.

### Parallel Team Strategy

With multiple developers:

- Dev A: Story 1 scenario families T004-T009 (one each, six PRs in parallel).
- Dev B: Story 2 three PRs (in parallel with Story 1).
- Dev C: Story 3 audit + protocols (in parallel with Stories 1 + 2).
- Once Stories 1 + 3 land, Devs A + B can pick up Story 4 handlers and Story 5 method splits in parallel (they touch the same `integrator.py` so coordinate the constructor edits, but per-handler / per-method work is otherwise independent).

---

## Notes

- `[P]` = different files, no incomplete-task dependency. Same-file edits (especially to `integrator.py`) serialize.
- `[Story]` label maps task to its user story for traceability and partial-revert safety.
- Every structural task ships its test in the same PR (FR-022). No "tests follow in a later PR."
- Every task that obsoletes a type-checker suppression removes it in the same PR (FR-019); the union never grows (FR-018).
- FR-021: in-process callers go through the decorated wrapper, NOT the `_impl`. T059 verifies this; if it becomes a frequent regression, T060 adds a CI check.
- Per FR-016 + FR-023: a delegate that stays in place across releases is acceptable; two divergent implementations of the same method in two locations is not.
- Per the spec Edge Cases: behavioral bugs discovered while writing tests are pinned as-is with a tracking-ticket comment, not fixed here.
- Per spec Assumptions: one towncrier fragment for the whole work, not per-PR.
