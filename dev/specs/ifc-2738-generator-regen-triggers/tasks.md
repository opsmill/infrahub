---

description: "Task list for Precise Regeneration Triggers for Generators in the Pipeline Based on Git"
---

# Tasks: Precise Regeneration Triggers for Generators in the Pipeline Based on Git

**Input**: Design documents from `specs/ifc-2738-generator-regen-triggers/` (symlink: `specs` -> `dev/specs`)
**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/definition-protocol.md, contracts/generator-watch-config.md, quickstart.md
**Jira**: [IFC-2738](https://opsmill.atlassian.net/browse/IFC-2738) | **Implements (JPD)**: [INFP-607](https://opsmill.atlassian.net/browse/INFP-607)

**Tests**: Included — FR-011 explicitly requires predicate unit tests, a `PythonClosure` generator-config support test, a generator-selection component test, a generator-import closure test, and SDK `watch`-field tests.

**Design invariant (inherited verbatim from INFP-409)**: over-execution is acceptable, under-execution is not. Every fallback path errs toward running the generator.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies on incomplete tasks)
- **[Story]**: Which user story this task belongs to (US1..US7)
- All paths are repository-relative.

## Why Foundational is heavy and the story phases are thin

This feature is parallel wiring into the already-shipped INFP-409 machinery, not new design. Precise triggering does not work until the *entire* shared chain is in place: the schema attributes (FR-001), the closure-builder widening (FR-002), the SDK `watch` field (FR-014 — a prerequisite because `union_watch_files` reads `.watch`), the predicate generalization (FR-005), the pipeline-model fields (FR-004), and the integrator persistence (FR-003). All of that is **Phase 2: Foundational** and blocks every user story. The user-story phases are then the two gate swaps (FR-006 in US1, FR-007 in US2) plus the per-story test coverage that proves each specific behavior on top of the shared mechanism.

---

## Phase 1: Setup (orientation only — the project already exists)

**Purpose**: Pin the exact INFP-409 patterns this feature replicates so every later task mirrors a known-good reference.

- [X] T001 Read the shipped INFP-409 artifact reference implementation: the predicates `_query_changed` / `_definition_changed` / `_transform_changed`, `PredicateOutcome`, and `DefinitionSelect` in backend/infrahub/proposed_change/tasks.py (~1286-1475); the artifact transform closure-build call sites in backend/infrahub/git/integrator.py (~385, ~1117, ~1135); and the artifact regression surface in backend/tests/component/proposed_change/test_artifact_regen_selection.py, backend/tests/unit/proposed_change/test_predicates.py, backend/tests/unit/proposed_change/test_predicate_logging.py.
- [X] T002 [P] Locate the generator fixtures to reuse: the existing backend/tests/component/proposed_change/test_request_generator_definition_check.py fixtures, the conftest helpers (make_node_diff, query constants) under backend/tests/component/proposed_change/, and the generator fixture repositories (e.g. car-dealership, 4 generators).

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Stand up the full shared chain. No user story can be delivered until this phase is complete.

**⚠️ CRITICAL**: No gate swap (US1/US2) produces correct behavior until all of Phase 2 lands.

- [X] T003 [P] Add `watch: InfrahubWatchConfig | None = None` (with the FR-014 description) to `InfrahubGeneratorDefinitionConfig` in python_sdk/infrahub_sdk/schema/repository.py, reusing the existing `InfrahubWatchConfig` (no new type). This is a hard prerequisite: `union_watch_files` reads `transform_config.watch` and would `AttributeError` for generators without it (research Decision 8). (FR-014)
- [X] T004 [P] Widen the `TransformConfig` union to include `InfrahubGeneratorDefinitionConfig` in backend/infrahub/git/closure_builder/protocols.py. (FR-002)
- [X] T005 [P] Widen `PythonClosure.supports()` to accept `InfrahubGeneratorDefinitionConfig` in backend/infrahub/git/closure_builder/python_closure.py (`build()` already reads only `file_path` and `name`, both present). (FR-002)
- [X] T006 Add two optional, nullable attributes to `CoreGeneratorDefinition` in backend/infrahub/core/schema/definitions/core/generator.py: `dependencies` (List) and `dependencies_complete` (Boolean), `BranchSupportType.AWARE`, mirroring the INFP-409 attributes on `CoreTransformation`. (FR-001)
- [X] T007 Regenerate offline backend artifacts after T006: `uv run invoke backend.generate` (updates backend/infrahub/core/protocols.py and backend/infrahub/core/schema/generated/). Do not hand-edit. (FR-001) (depends on T006)
- [X] T008 Regenerate the schema exports after T006: `uv run invoke schema.generate-graphqlschema` and `uv run invoke schema.generate-jsonschema` (updates schema/schema.graphql, schema/openapi.json). (FR-001) (depends on T006)
- [X] T009 Regenerate frontend GraphQL types: `cd frontend/app && pnpm codegen` (updates frontend/app/src/shared/api/graphql/generated/). No UI work. (FR-001) (depends on T008)
- [X] T010 Introduce the `RegenerationDefinition` structural `Protocol` (fields: `definition_id`, `definition_name`, `query_id`, `query_name`, `dependencies`, `dependencies_complete`; properties: `source_noun`, `instance_noun`) in backend/infrahub/proposed_change/tasks.py and retype `_query_changed` / `_definition_changed` / `_transform_changed` from `ProposedChangeArtifactDefinition` to it. Declare only fields the predicates read. (FR-005; contracts/definition-protocol.md)
- [X] T011 Parametrize the predicate reason strings to interpolate `source_noun` / `instance_noun` off the definition, so logs read correctly for both callers — and so that with `source_noun="transform"` / `instance_noun="artifacts"` every artifact reason string is byte-for-byte unchanged, in backend/infrahub/proposed_change/tasks.py. (FR-005, FR-013) (depends on T010)
- [X] T012 Add `source_noun` ("transform") and `instance_noun` ("artifacts") properties to `ProposedChangeArtifactDefinition` (per research Decision 1, backend/infrahub/message_bus/types.py — confirm location) so it continues to satisfy `RegenerationDefinition`. (FR-005, FR-013) (depends on T010)
- [X] T013 Add `query_id: str`, `dependencies: list[str] | None = None`, `dependencies_complete: bool | None = None`, and `source_noun` ("generator source") / `instance_noun` ("instances") properties to `ProposedChangeGeneratorDefinition` in backend/infrahub/generators/models.py so it satisfies `RegenerationDefinition`. (FR-004, FR-005) (depends on T010)
- [X] T014 Populate `query_id = generator.query.peer.id` (peer already prefetched), `dependencies = generator.dependencies.value`, and `dependencies_complete = generator.dependencies_complete.value` at the `run_generators` construction site (~354) in backend/infrahub/proposed_change/tasks.py. (FR-004) (depends on T013; same file as T010/T011)
- [X] T015 [P] Populate `query_id = generator.query.peer.id` at the second construction site `run_generator_definition` (~156) in backend/infrahub/generators/tasks.py, or model validation fails on the post-merge path. (FR-004, research Decision 5) (depends on T013)
- [X] T016 Build each generator's dependency closure in `_build_generator_definitions` (~979) in backend/infrahub/git/integrator.py via the existing aggregator (`build_default_closure_builder(...).build(...)`), using `Path(branch_wt.directory)` as `worktree_root`, and thread the resulting `ClosureResult` to `_apply_generator_definitions` (the downstream apply/create/update functions have no worktree in scope). (FR-003, research Decision 7) (depends on T003, T004, T005, T006)
- [X] T017 Persist `result.dependencies` -> `dependencies` and `result.complete` -> `dependencies_complete` onto the node payload in `_create_generator_definition` and `_update_generator_definition` in backend/infrahub/git/integrator.py, exactly as the existing fields (`file_path`, `class_name`) are written. (FR-003) (depends on T016)
- [X] T018 Extend `_generator_requires_update` in backend/infrahub/git/integrator.py to compare the stored closure against the freshly built one, so a content change that alters dependencies but leaves other compared fields equal still triggers a node update (prevents stale `dependencies`). (FR-003, research Decision 7) (depends on T016)

**Checkpoint**: Shared chain complete — closures persist on import, the model carries them, the predicates accept generators. Before starting the gate swaps, confirm the artifact predicate/selection/logging suites (test_predicates.py, test_predicate_logging.py, test_artifact_regen_selection.py) still pass after the Protocol retype and noun parametrization (FR-013).

---

## Phase 3: User Story 1 - Stop running generators for unrelated commits (Priority: P1) 🎯 MVP

**Goal**: A proposed change whose only repository change is unrelated (e.g. a README edit) dispatches zero generators.

**Independent Test**: Open a proposed change whose only repository change is a `README.md` edit and verify zero generators are dispatched.

### Implementation for User Story 1

- [X] T019 [US1] Replace the `DefinitionSelect.FILE_CHANGES` clause in `run_generators` (backend/infrahub/proposed_change/tasks.py) with `_query_changed OR _definition_changed OR _transform_changed(repo_diff)`, evaluated against the per-definition repo diff via `_repo_diff_or_none(...)`; keep the `MODIFIED_KINDS` clause unchanged; log each `PredicateOutcome.reason` at INFO. (FR-006, FR-010; contracts/definition-protocol.md call-site matrix)

### Tests for User Story 1

- [X] T020 [P] [US1] Create backend/tests/component/proposed_change/test_generator_regen_selection.py (mirror test_artifact_regen_selection.py; reuse conftest helpers + test_request_generator_definition_check fixtures): a PC whose only repo change is `README.md` dispatches zero generators; a `.py` edit outside every package floor and unread by any query also dispatches zero. Also assert that the `MODIFIED_KINDS` data-change path still selects the generator exactly as before this feature (SC-008), and that a generator definition present on the source branch but not the destination branch is selected and runs for every target-group member (spec Edge Case: new definition on source branch). (SC-001, SC-008, US1 acceptance 1 & 2)
- [X] T021 [P] [US1] Unit test in backend/tests/unit/proposed_change/ for generator-model predicate variants: `_transform_changed` yields `matched=False` for an unrelated-file diff when `dependencies` is non-empty and `dependencies_complete=True`; and `_definition_changed` yields `matched=True` when `diff_summary` contains an entry whose `id == definition.definition_id` (definition node modified, e.g. an attribute change or `targets` repoint). (US1, FR-005, FR-011)

**Checkpoint**: MVP — unrelated commits no longer trigger generators.

---

## Phase 4: User Story 2 - Re-run only the generators whose source changed (Priority: P1)

**Goal**: Editing a generator's source file (or a sibling in its package directory) re-runs only that generator's instances.

**Independent Test**: Edit the source file of exactly one generator and verify only that generator's instances re-run.

### Implementation for User Story 2

- [X] T022 [US2] Swap the per-member gate in `request_generator_definition_check` / `_run_generator` (~1256) in backend/infrahub/proposed_change/tasks.py: compute `managed_branch = (_query_changed OR _definition_changed OR _transform_changed(repo_diff)).matched` instead of unconditional `source_branch_sync_with_git`; everything else in `_run_generator` unchanged. **Primary risk area** — preserve the never-under-run invariant in the interaction with `impacted_instances`. (FR-007, research Decision 4; contracts/definition-protocol.md never-under-run proof)

### Tests for User Story 2

- [X] T023 [P] [US2] Extend test_generator_regen_selection.py: editing `generators/a/a.py` re-runs gen_a's instances only (gen_b untouched); editing the sibling `generators/a/helpers.py` re-runs gen_a (package-directory floor includes the sibling). (SC-002, US2 acceptance 1 & 2)
- [X] T024 [P] [US2] Unit test for `_transform_changed` generator variant in backend/tests/unit/proposed_change/: a diff file inside the package floor intersects the closure -> `matched=True`; a sibling module in the same package -> `matched=True`. (US2)
- [X] T025 [P] [US2] Unit test asserting the never-under-run proof for `_run_generator` after the swap: new member (`instance_id is None`) runs regardless of `managed_branch`; a data-changed instance in `impacted_instances` runs regardless; a legacy/failed-closure generator yields `managed_branch=True` on any file change. (FR-007, spec Edge Cases)
- [X] T026 [P] [US2] `PythonClosure` generator-config support test in backend/tests/unit/git/closure_builder/: `supports()` returns True for `InfrahubGeneratorDefinitionConfig` and `build()` produces the package-directory floor from `file_path` + `name`. (FR-002, FR-011) (pulled forward into the foundation PR: it guards code that ships there - T004/T005)
- [X] T027 [P] [US2] Generator-import closure test in backend/tests/component/ (or git integration tests): importing a repository builds and persists `dependencies` / `dependencies_complete` on `CoreGeneratorDefinition` for each generator. (FR-003, FR-011) (pulled forward into the foundation PR: it guards code that ships there - T016/T017, and adds a re-import case covering the `_generator_requires_update` closure comparison - T018)

**Checkpoint**: Source/package-floor edits precisely target the affected generator's instances.

---

## Phase 5: User Story 3 - Re-run only the generators using a changed query (Priority: P1)

**Goal**: Editing a `.gql` query re-runs only the generators that use it.

**Independent Test**: Edit one `.gql` query used by exactly one generator and verify only that generator re-runs.

**Note**: Delivered by `_query_changed` in the T019 gate swap; this phase is the targeted test coverage.

### Tests for User Story 3

- [X] T028 [P] [US3] Extend test_generator_regen_selection.py: editing a `.gql` query used by exactly one generator re-runs only that generator; a query used by two generators selects both when changed; editing both a generator's query and source dispatches it once (no double-dispatch). (SC-003, US3 acceptance + edge cases)
- [X] T029 [P] [US3] Unit test for `_query_changed` generator variant in backend/tests/unit/proposed_change/: a `diff_summary` entry whose `id == definition.query_id` -> `matched=True`; an unresolvable query peer never matches here but the other signals still cover it. (US3, spec Edge Cases)

**Checkpoint**: Query edits precisely target the consuming generators.

---

## Phase 6: User Story 5 - Diagnostic visibility for every run decision (Priority: P1)

**Goal**: The task log states exactly which file, query, or definition change triggered each run/skip decision, in generator-correct wording.

**Independent Test**: Open a PC editing one generator's source and verify the task log names that file as the trigger.

### Tests for User Story 5

- [X] T030 [P] [US5] Predicate-logging unit test in backend/tests/unit/proposed_change/ asserting the generator reason strings render with `source_noun="generator source"` / `instance_noun="instances"` for each predicate (query matched, definition matched, precise transform match, legacy `dependencies=null` fallback, incomplete `dependencies_complete=False` fallback), and that both gates (`run_generators`, `request_generator_definition_check`) emit each `PredicateOutcome.reason` at INFO with a non-triggered generator reflected as not-run. (FR-010, SC-006; contracts/definition-protocol.md reason templates)
- [X] T031 [P] [US5] Extend backend/tests/unit/proposed_change/test_predicate_logging.py to assert artifact reason strings remain byte-for-byte identical (`source_noun="transform"` / `instance_noun="artifacts"`). (FR-013, SC-007)

**Checkpoint**: Every generator run/skip decision is explained in the log.

---

## Phase 7: User Story 4 - Read-only repositories participate (Priority: P2)

**Goal**: A read-only repository commit bump that modifies a generator's closure re-runs it even when the consuming branch has `sync_with_git = False`.

**Independent Test**: Advance a read-only repo's commit to one that modifies a generator's closure with `sync_with_git = False` and verify the generator re-runs.

**Note**: Falls out of the gates keying on `_transform_changed(repo_diff)` instead of `sync_with_git` (FR-008, INFP-409 US5 machinery). This is verification, not new construction.

### Tests for User Story 4

- [X] T032 [P] [US4] Extend test_generator_regen_selection.py: a read-only-repository commit bump modifying a generator's closure with `sync_with_git=False` re-runs the generator; a bump touching only files outside any generator's closure runs no generator. (SC-004, US4 acceptance 1 & 2; FR-008) — Kept `test_read_only_repo_closure_change_selects_without_git_sync` (the closure-touching bump with `sync=False`), which is the only test exercising the selection gate with `sync=False` and guards against re-coupling selection to `source_branch_sync_with_git`. Dropped the "bump outside every closure" negative during the maintainability review: at the `run_generators` selection layer `read_only`/`sync_with_git` are inert, so that case returned `[]` under every implementation and duplicated `test_readme_edit_dispatches_nothing` with no distinct guard.

**Checkpoint**: Read-only repositories participate in precise triggering.

---

## Phase 8: User Story 6 - Backward compatibility and self-healing (Priority: P2)

**Goal**: Generators with `dependencies = null` (imported before this ships) keep working with no error and self-heal on the next re-import.

**Independent Test**: Evaluate a PC against a generator with `dependencies = null`; verify it runs under the legacy gate with no error, then re-import and verify precise triggering.

### Tests for User Story 6

- [X] T033 [P] [US6] Unit test for `_transform_changed` fallback in backend/tests/unit/proposed_change/: `dependencies=None` -> `matched = repo_diff.has_modifications`; `dependencies_complete` not `True` -> the same fallback. (FR-009, SC-005)
- [X] T034 [P] [US6] Extend test_generator_regen_selection.py: a generator with `dependencies=null` runs under the legacy gate on any file change with no error; after re-import its `dependencies` / `dependencies_complete` are populated and subsequent PCs use precise triggering. (FR-009, SC-005) — Kept `TestGeneratorRegenLegacyFallback::test_legacy_generator_runs_on_any_file_change`, the only test flowing a real `null` `dependencies` attribute through the DB gather → model → select path end-to-end (self-heal-on-re-import is covered by the import-closure integration test). Dropped the "not selected without any change" negative during the maintainability review: it duplicated the T033 predicate-level `legacy_null_dependencies_with_no_modifications_is_false` case at a slower component layer with no distinct guard.

**Checkpoint**: Existing installations are safe and self-heal on re-import.

---

## Phase 9: User Story 7 - Declare extra dependencies via `watch:` (Priority: P2)

**Goal**: A generator can declare files outside its package directory via `watch.files` and have edits to them trigger re-runs.

**Independent Test**: Declare a sibling-package path under `watch.files`, then verify edits to it re-run the generator while unrelated edits do not.

**Note**: The SDK field itself (FR-014) landed in Phase 2 (T003) because the aggregator needs it. This phase is the `watch`-specific behavior, validation, and tests.

### Tests for User Story 7

- [X] T035 [P] [US7] SDK parsing/rejection tests in python_sdk/tests/: `watch: { files: ["a", "dir/"] }` parses; `watch: [a, b]` (list form) rejected; `watch: { fles: [...] }` (unknown key, `extra="forbid"`) rejected; `watch: { files: "a" }` (string not list) rejected. (FR-015, SC-009)
- [X] T036 [P] [US7] Closure-union test for recursive directory expansion in backend/tests/unit/git/closure_builder/: a directory entry in `watch.files` expands to every tracked file beneath it via `union_watch_files` (`git ls-files`), skipping `.pyc` / `__pycache__` / symlinks, for a generator config. (FR-016, FR-011) — Covered by `test_generator_config_flows_through_watch_union` in test_watch_union.py: a generator-config directory entry expands recursively and skips `.pyc`/`__pycache__`/symlinks. During the maintainability review the three separate generator-config tests were collapsed into this one: `union_watch_files` reads `watch` off whichever config it is given, so the recursion/exclusion/completeness behavior is the shared code already exercised by the transform variants; the only generator-specific risk is that the generator config is accepted at all, which one combined test proves.
- [X] T037 [P] [US7] Test that a non-empty `watch.files` forces `dependencies_complete=True` (trusting the declaration) and that a no-match entry is logged as a warning without aborting the import of that generator or the others. (FR-016, FR-017) — The completeness flip for a generator config is asserted by `test_generator_config_flows_through_watch_union` (an incomplete closure becomes `complete=True` once `watch.files` is declared). The separate generator "no-match entry warns without aborting" test was dropped during the maintainability review as redundant: that warning path is type-agnostic code already guarded by the transform variant `test_entry_matching_no_tracked_file_is_warned_and_keeps_completeness`.
- [X] T038 [P] [US7] Extend test_generator_regen_selection.py: a generator declaring `watch: { files: ["shared/"] }` re-runs when a file under `shared/` changes and does not re-run for edits outside both `shared/` and its package floor. (SC-009, US7 acceptance 1 & 2) — Removed during the maintainability review. At the `run_generators` selection layer a `watch`-declared out-of-package path is just another entry in the stored `dependencies` list, so both scenarios exercised the same set-intersection already guarded by `test_source_edit_selects_only_owning_generator` and `test_readme_edit_dispatches_nothing`; no watch-specific code runs at this layer. The watch mechanism that produces the `shared/` closure entry (union, recursion, completeness) is guarded by the `union_watch_files` unit test above. The whole `TestGeneratorRegenWatchClosure` component class and its dataset fixture were dropped for no loss of distinct coverage.

**Checkpoint**: Generators with cross-package dependencies opt into precise triggering.

---

## Phase 10: Polish & Cross-Cutting Concerns

**Purpose**: Final regression guard, documentation, changelog, submodule update, and validation.

- [X] T039 [P] FR-013 final regression guard: run the full artifact suite (backend/tests/component/proposed_change/test_artifact_regen_selection.py + test_predicates.py + test_predicate_logging.py) and confirm artifact selection and log wording are byte-for-byte unchanged. (FR-013, SC-007)
- [X] T040 [P] Documentation (FR-012): extend the dependency-closure / why-trail topic docs to mention generators, and add a generator `watch:` entry to the repository-config schema reference, mirroring the transform `watch:` reference shipped by INFP-409, under docs/docs/.
- [X] T041 Regenerate reference docs and validate: `uv run invoke docs.generate` then `uv run invoke docs.validate` (renders the repository-config / dotinfrahub reference that surfaces the new generator `watch:` field). (FR-012) (depends on T003, T040) — `docs.generate` produced no stale generated content (the `generator_definitions` `watch` entry in `docs/docs/reference/dotinfrahub.mdx` was already committed with the T003 SDK field). `docs.validate` (`git diff --exit-code docs`) reports only the two intentional prose edits below and passes once they are committed.
- [X] T042 [P] Add a Towncrier changelog fragment changelog/+ifc-2738.*.md. (FR-012) — `changelog/+ifc-2738.changed.md`.
- [X] T043 [P] Mark/confirm the GitHub-Actions `xfail` on the e2e test that already runs generators (test_proposed_change_repository.py), mirroring the INFP-409 deferral. (FR-011) — Confirmed the deferral is no longer needed: INFP-409 removed the `@pytest.mark.xfail(reason="Works locally but it's failing in GitHub Actions")` marker in commit `27b0183d7` and fixed the underlying nondeterminism (the fixture reliably reselects a generator by touching `john.description` on the branch). The test carries no xfail marker and passes; re-adding one would regress the INFP-409 resolution.
- [X] T044 Commit the `python_sdk` submodule update explicitly (the `watch` field on `InfrahubGeneratorDefinitionConfig`) per the git workflow. (FR-014) (depends on T003) — Already landed: the field is committed inside the submodule (`9b91729 Add watch for generators`, merged as `38216f3`) and the superproject gitlink already points at `38216f3` with a clean working tree.
- [X] T045 Run the quickstart.md manual verification (Scenarios 1-7 + the artifact regression check) against a build from this branch. (SC-001..SC-009) — Executed via the quickstart's "Automated equivalents" (the automated proxy for each scenario), all green: Scenarios 1-3 and the data-change/new-definition edges (test_generator_regen_selection.py), Scenario 4 read-only participation (test_read_only_repo_* in the same file), Scenario 5 diagnostics (test_generator_predicate_logging.py), Scenario 6 backward-compat/self-heal (legacy-fallback class + test_generator_import_closure.py re-import), Scenario 7 watch (test_watch_union.py generator variants + test_generator_regen_selection.py watch class), and the artifact regression check (T039 suite). The live UI-driven walk-through against `dev.build && dev.start` was not run in this session (no browser / running stack); the automated equivalents are the CI-enforced verification of SC-001..SC-009.
- [X] T046 Run `/pre-ci` (format, lint, unit tests, generated-file and generated-doc validation) before pushing. — Python format (1 test file reformatted), docs format (0 errors), `main.lint` + `backend.lint` (ruff + ty + mypy, 1366 files, all pass), `docs.lint` (0 errors; the edited docs are clean), backend unit tests (1386 passed). `docs.validate` shows only the two intentional uncommitted prose edits and passes once committed; no schema/frontend/generated-backend changes were made this session.

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies — orientation only.
- **Foundational (Phase 2)**: Blocks all user stories. Internal order: T003 / T004 / T005 (parallel) and T006 -> T007/T008 -> T009 first; T010 -> T011/T012/T013 -> T014/T015; T016 (needs T003+T004+T005+T006) -> T017/T018. Close the phase by confirming the artifact regression suites stay green (FR-013).
- **User Stories (Phases 3-9)**: All require Phase 2 complete.
  - US1 (T019) is the keystone definition-level gate swap and the MVP.
  - US2 (T022) is the per-member gate swap (primary risk).
  - US3, US5, US4, US6, US7 are delivered by the foundation + the two gate swaps; their phases are targeted test coverage / verification.
- **Polish (Phase 10)**: After all desired user stories.

### Critical-path note

Precise triggering is only correct once **all** of Phase 2 plus the two gate swaps (T019, T022) land. The split into stories reflects test/verification boundaries, not independently shippable code increments for US3-US6.

### Within-phase parallel opportunities

- **Phase 2**: T003, T004, T005 in parallel; after T006 the three regeneration tasks T007/T008 (T009 after T008); T015 parallel with T014's file (different module).
- **Phase 3+**: All `[P]` test tasks within a story run in parallel (distinct files). T020 creates test_generator_regen_selection.py; T023, T028, T032, T034, T038 each extend that one file, so coordinate or sequence those edits.

---

## Implementation Strategy

### MVP First (User Story 1)

1. Phase 1: Setup.
2. Phase 2: Foundational (the full shared chain — CRITICAL).
3. Phase 3: US1 — the definition-level gate swap (T019) + its tests.
4. **STOP and VALIDATE**: unrelated commits dispatch zero generators (SC-001).

### Incremental Delivery

1. Foundation -> US1 (MVP: unrelated commits filtered).
2. US2 -> per-member precision (primary risk; never-under-run proof).
3. US3 / US5 -> query targeting + diagnostics.
4. US4 / US6 -> read-only participation + backward-compat/self-heal.
5. US7 -> user-declared `watch:`.
6. Polish -> regression guard, docs, changelog, submodule commit, quickstart, pre-ci.

---

## Notes

- [P] = different files, no dependency on incomplete tasks.
- The two construction sites for `ProposedChangeGeneratorDefinition` (T014, T015) MUST both populate `query_id` or model validation fails on the post-merge path (research Decision 5).
- FR-013 (artifact regression safety) is enforced at the Phase 2 checkpoint, by the byte-for-byte logging assertion (T031), and by the final guard (T039). The shared predicate refactor must leave artifact behavior identical.
- Schema/GraphQL changes (FR-001) fall under the "ask first" boundary but are pre-authorized by this ticket as a direct mirror of the INFP-409 attributes; they must still be regenerated and committed (T007-T009).
- Generated files (T007/T008/T009) and reference docs (T041) are validated by CI — commit them or CI fails.
