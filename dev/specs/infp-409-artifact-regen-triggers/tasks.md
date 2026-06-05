# Tasks: Refactor When Artifacts Are Regenerated on Git Changes (INFP-409)

**Input**: Design documents from `dev/specs/infp-409-artifact-regen-triggers/`
**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/

**Tests**: Tests ARE in scope. The plan's Constitution Check IV (Test Discipline) explicitly commits to unit tests for closure builders / path normalizer / pipeline predicates, functional tests for selection + fan-out behavior, and integration_docker tests for end-to-end proposed-change flow against both `CoreRepository` and `CoreReadOnlyRepository`.

**Organization**: Tasks are grouped by user story (US1–US5 from spec.md) for independent implementation and testing. Stage 1 / Stage 2 (per plan.md and contracts/pipeline-predicates.md) are sub-divisions inside the US1 phase.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Different files, no dependencies on incomplete tasks — can run in parallel.
- **[Story]**: Maps the task to a spec.md user story (US1, US2, US3, US4, US5). Setup, Foundational, and Polish tasks have no story label.

## Path Conventions

Multi-package web service per plan.md "Source Code" tree:

- Backend: `backend/infrahub/`
- Backend tests: `backend/tests/`
- SDK (git submodule): `python_sdk/infrahub_sdk/`
- SDK tests: `python_sdk/tests/`
- Docs: `docs/docs/`
- Changelog: `changelog/`

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: New package directories and changelog scaffolding so subsequent tasks have a place to write files.

- [X] T001 Create new closure-builder package directory `backend/infrahub/git/closure_builder/` with an empty `__init__.py`.
- [X] T002 [P] Create test directory `backend/tests/unit/git/closure_builder/` with an empty `__init__.py`.
- [X] T003 [P] Ensure `backend/tests/unit/proposed_change/` exists for predicate unit tests; create with empty `__init__.py` if absent.
- [ ] T004 [P] Add Towncrier fragment `changelog/+infp-409-stage1.changed.md` describing the Stage 1 selection-gate refactor; a Stage 2 fragment is added in Phase 8 (T067).

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Shared types and the canonicalizer used by every closure builder and the pipeline predicate. Every user story imports these.

**CRITICAL**: No user-story work can begin until this phase is complete.

- [X] T005 Define `ClosureResult` and `UnresolvedRef` frozen dataclasses in `backend/infrahub/git/closure_builder/result.py` per data-model.md §3 (`kw_only=True`, `slots=True`, deterministic `dependencies: tuple[str, ...]`, `complete: bool`, `unresolved: tuple[UnresolvedRef, ...]`).
- [X] T006 Implement the path canonicalizer in `backend/infrahub/git/closure_builder/canonicalizer.py` per data-model.md §4 (repo-relative, POSIX `/`, strip leading `./`, strip trailing `/`, no symlink resolution, case-preserving, idempotent). Leading `/` is treated as repo root and stripped (matches the `.gitignore` convention) so the same canonicalizer can later be reused on `watch.files` SDK input without rejecting user input.
- [X] T007 [P] Unit tests for the canonicalizer in `backend/tests/unit/git/closure_builder/test_canonicalizer.py`: idempotency, leading-`./` strip, trailing-`/` strip, Windows-style `\` to POSIX conversion, symlinks not resolved, leading `/` normalized to repo-root (not rejected), empty / repo-root-collapsing inputs rejected.
- [X] T008 Define a `ClosureBuilder` Protocol in `backend/infrahub/git/closure_builder/protocols.py` with a single entry method `build(transform_config, worktree_root) -> ClosureResult` per the component-design note in contracts/pipeline-predicates.md. (Deviation from the original "in `__init__.py`" instruction: code lives in a named sibling module per the repo convention — `__init__.py` stays empty. Matches the existing `backend/infrahub/services/protocols.py` pattern.)

**Checkpoint**: Foundation ready — every user story can now begin.

---

## Phase 3: User Story 1 — Stop regenerating artifacts for unrelated commits (Priority: P1) 🎯 MVP

**Goal**: Replace the blunt `has_file_modifications` selection gate with three precise per-definition predicates (`_query_changed`, `_definition_changed`, `_transform_changed`) so unrelated edits (README, helper files outside any transform closure) cause zero regeneration, and edits inside a definition's closure regenerate only that definition's artifacts.

**Independent Test**: Open a PC whose only repo change is a `README.md` edit → no artifact regenerates (SC-001). Open a PC editing one `.gql` file → only that definition's artifacts regenerate. Open a PC editing one transform source file (or a sibling helper in the same package directory, or a transitive Jinja2 include) → only the owning definition's artifacts regenerate (SC-002).

### Stage 1 — Pipeline predicates (no schema work, no SDK)

#### Tests for Stage 1 (write first, expect failures)

- [X] T009 [P] [US1] Unit tests for `_query_changed` in `backend/tests/unit/proposed_change/test_predicates.py`: returns True iff a `diff_summary` entry's `id` matches `definition.query_id`; False on empty diff; False on mismatched id; covers fragment-edit case (stored query text changes → node modification → predicate True) per contracts/pipeline-predicates.md "Why this works".
- [X] T010 [P] [US1] Unit tests for `_definition_changed` in `backend/tests/unit/proposed_change/test_predicates.py`: returns True iff a `diff_summary` entry's `id` matches `definition.node_id`; covers attribute change, `targets` repoint, `transformation` repoint, `query` repoint (FR-007).

#### Implementation

- [X] T011 [US1] Implement `_query_changed(definition, diff_summary) -> bool` in `backend/infrahub/proposed_change/tasks.py` per contracts/pipeline-predicates.md.
- [X] T012 [US1] Implement `_definition_changed(definition, diff_summary) -> bool` in `backend/infrahub/proposed_change/tasks.py` per contracts/pipeline-predicates.md.
- [X] T013 [US1] Replace the `FILE_CHANGES` selection gate at `refresh_artifacts` in `backend/infrahub/proposed_change/tasks.py` (≈ lines 1363–1382 per contracts/pipeline-predicates.md "Call-site replacement matrix") with `_query_changed OR _definition_changed`, OR-ed with the existing `MODIFIED_KINDS` clause and a residual legacy `has_file_modifications` clause (kept temporarily per spec's "Stage 1 / Stage 2 interim behavior"; removed in T030).
- [X] T014 [US1] In `validate_artifacts_generation` in `backend/infrahub/proposed_change/tasks.py` (≈ lines 805–807), flip `managed_branch = True` conditionally on `_query_changed OR _definition_changed` rather than unconditionally on `FILE_CHANGES`; preserve the residual `has_file_modifications` short-circuit until T031 removes it.

### Stage 2 — Schema, closure builders, transform predicate

#### Schema additions

- [X] T015 [US1] Add `dependencies` (`List` of `Text`, optional, default `null`) and `dependencies_complete` (`Boolean`, optional, default `null`) attributes to the `CoreTransformation` generic in `backend/infrahub/core/schema/definitions/core/transform.py` per data-model.md §1. `BranchSupportType.AWARE` inherited from the generic.
- [X] T016 [US1] Run `uv run invoke backend.generate` to regenerate `backend/infrahub/core/schema/generated/` and `backend/infrahub/core/protocols.py` from the schema change. Commit the regenerated files; do not hand-edit.
- [X] T017 [P] [US1] Regenerate frontend types via `cd frontend/app && pnpm codegen` and export the GraphQL/OpenAPI schemas (`uv run infrahub dev export-graphql-schema` against a running instance); commit updates to `frontend/app/src/shared/api/graphql/generated/`, `schema/schema.graphql`, and `schema/openapi.json`.
- [X] T018 [US1] Add a schema-level write-time validator on `CoreTransformation.dependencies` asserting each entry is the canonicalizer's fixed point (data-model.md §1 "Validation rules": `canonicalize(p) == p`). (Realized as a `ClosureResult.__post_init__` invariant in `backend/infrahub/git/closure_builder/result.py`; the integrator only writes `dependencies` from a `ClosureResult`, so the schema boundary is enforced by construction.)

#### Closure builders

- [X] T019 [P] [US1] Unit tests for `Jinja2Closure` in `backend/tests/unit/git/closure_builder/test_jinja2_closure.py`: static `{% include %}`, `{% import %}`, `{% extends %}` resolved transitively; dynamic `{% include some_var %}` produces an `UnresolvedRef` and `complete=False`; multiple unresolved sites are *all* recorded (FR-023a); paths canonicalized; result `dependencies` sorted lexicographically (data-model.md §3 invariants).
- [X] T020 [US1] Implement `Jinja2Closure` in `backend/infrahub/git/closure_builder/jinja2_closure.py` using `jinja2.Environment.parse()` with a `FileSystemLoader` rooted at the commit worktree (FR-016) and `jinja2.meta.find_referenced_templates` (Decision 5). Continue walking past `None` references (FR-023a) and record every unresolved site.
- [X] T021 [P] [US1] Unit tests for `PythonClosure` in `backend/tests/unit/git/closure_builder/test_python_closure.py`: package-directory floor includes all `.py` siblings (FR-006); excludes `.pyc`, `__pycache__/`, and gitignored entries; `complete=True` always. (Symlink-skip test omitted: enumeration via `git ls-files` is path-only and never reads through links, so the spec's symlink concern does not materialize at this layer.)
- [X] T022 [US1] Implement `PythonClosure` in `backend/infrahub/git/closure_builder/python_closure.py` per Decision 6 (package-directory floor; no AST import analysis). Tracking via `git ls-files` so gitignored paths are naturally absent.
- [X] T023 [US1] Append the canonical `.infrahub.yml` path to every transform's `dependencies` list in the closure-builder result post-processing (Decision 7 / FR-021) and sort the final list lexicographically before storage (data-model.md §3 invariants). (Implemented in `backend/infrahub/git/closure_builder/post_processing.py::append_manifest_path`; invoked by the dispatcher.)

#### Integrator wiring

- [X] T024 [US1] In `backend/infrahub/git/integrator.py`, dispatch to the correct closure builder via a `match` on the transform's `InfrahubKind` with `typing.assert_never` in the catch-all (per backend conventions: prefer exhaustive `match` + `assert_never` over `getattr`): `CoreTransformJinja2` → `Jinja2Closure`, `CoreTransformPython` → `PythonClosure`. Call the builder after parsing each transform from `.infrahub.yml` and persist `dependencies` + `dependencies_complete` on the `CoreTransformation` node at import time per data-model.md §1 "State transitions". (Match is on the SDK config type union rather than `InfrahubKind` directly — same exhaustiveness, more idiomatic in Python; dispatch lives in `backend/infrahub/git/closure_builder/dispatcher.py::build_transform_closure`.)
- [X] T025 [US1] In `backend/infrahub/git/integrator.py`, wrap the per-transform closure-builder call in a try/except boundary per Decision 9 / FR-023: on failure, emit a Prefect-logger error with the transform's identity and failure mode, set `dependencies_complete=False` (and any best-effort partial `dependencies`), and continue importing the remaining transforms in the repository. (Isolation lives in the dispatcher with a typed catch tuple `(ValueError, OSError, TemplateError, GitCommandError)` rather than bare `Exception`, so genuine bugs still surface.)

#### Pipeline plumbing

- [X] T026 [US1] Extend `ProposedChangeArtifactDefinition` in `backend/infrahub/message_bus/types.py` with four fields per data-model.md §2 and contracts/pipeline-predicates.md "Inputs already in the pipeline": `dependencies: list[str] | None = None`, `dependencies_complete: bool | None = None`, `repository_id: str` (needed by `_transform_changed` to select the right per-repo diff via `transformation.repository`), and `query_name: str` (needed by `_query_changed`'s diagnostic log entry per FR-022). (`repository_id` and `query_name` were already present on the model.)
- [X] T027 [US1] Extend the `GATHER_ARTIFACT_DEFINITIONS` GraphQL query feeding `_gather_artifact_definitions` (locate the `.gql` source under `backend/infrahub/proposed_change/` or `backend/infrahub/generators/graphql_queries/` — pin the path during implementation) to additionally select `transformation { node { dependencies { value } dependencies_complete { value } repository { node { id } } } }` and `query { node { name { value } } }`. (Query lives inline in `backend/infrahub/proposed_change/tasks.py` as `GATHER_ARTIFACT_DEFINITIONS`, not a `.gql` source — no Pydantic regen needed. `repository` and `query.name` selections were already present; added `dependencies` and `dependencies_complete`. Propagated into `_parse_artifact_definitions`.)

#### `_transform_changed` predicate

- [X] T028 [P] [US1] Unit tests for `_transform_changed` in `backend/tests/unit/proposed_change/test_predicates.py` covering every row of the behavior table in contracts/pipeline-predicates.md: `None/None` → legacy fallback returns True iff any file changed; `*/False` → incomplete fallback returns True iff any file changed; `[]/True` → always False; non-empty/`True` → set-intersection True/False cases. Verify the canonicalizer is applied symmetrically to both sides.
- [X] T029 [US1] Implement `_transform_changed(definition, repo_diff) -> bool` in `backend/infrahub/proposed_change/tasks.py` per contracts/pipeline-predicates.md (canonicalize both sides; set intersection on the non-empty/`True` path; null/incomplete fallbacks as specified).
- [X] T030 [US1] Update the `refresh_artifacts` selection gate (T013 site) to OR-in `_transform_changed(definition, repo_diff_for_this_definition)` (look up `repo_diff` by `definition.repository_id` from T026/T027) and **remove** the residual legacy `has_file_modifications` clause.
- [X] T031 [US1] Update `validate_artifacts_generation` (T014 site) to additionally flip `managed_branch` on `_transform_changed`; remove the legacy `has_file_modifications` short-circuit.

#### End-to-end tests for US1

- [X] T032 [P] [US1] Functional test covering quickstart.md Scenarios 1–5 + 8: README-only PC → zero regenerations; `.gql`-only PC → only owning definition; transform-source-only PC → only owning definition; sibling `.py` inside package directory → owning definition (heuristic floor); Jinja2 `partials/header.j2` edit → owning definition (transitive include); definition relationship repoint → all owning artifacts regenerate (`_definition_changed`). (Placement deviation: realized at `backend/tests/component/proposed_change/test_artifact_regen_selection.py`, not `functional/`. The selection gate is driven directly via the `refresh_artifacts` flow with a `WorkflowRecorder`, asserting which definitions get a `RequestArtifactDefinitionCheck` submitted — the exact pattern of the sibling `test_validate_artifacts_generation.py` component test for this feature, reusing its `conftest.make_node_diff`. A `functional/` placement would require either duplicating that infra or a full SDK-driven pipeline that cannot cleanly assert per-definition selection without the real-repo e2e of T033. Closure contents are set on the `CoreTransformation` nodes to mirror integrator output; the closure builders themselves are unit-tested in T019–T022.)
- [ ] T033 [US1] Integration_docker test in `backend/tests/integration_docker/proposed_change/test_artifact_regen_e2e.py`: end-to-end PC against a `CoreRepository` with a real git worktree replaying the same scenario set as T032. **DEFERRED** — a literal replay needs follow-up-commit-on-a-branch plumbing that no test helper provides today (`infrahub_sdk.testing.repository.GitRepo` does one initial commit + import only); the nearest existing PC-against-repo integration test (`backend/tests/integration/proposed_change/test_proposed_change_repository.py`) is already `xfail` in CI. Confirmed independent of the `watch:` SDK work (T045/T046/T073): the closure builders do pure auto-detection and never reference `watch`. To be scoped separately once git-branch-commit test infrastructure exists.
- [X] T034 [US1] Edge-case functional test covering spec.md "Edge Cases": (a) edit-then-revert within the same branch → empty net diff → no regeneration; (b) `.infrahub.yml` edit → every transform in that repo regenerates per FR-021 (verifies T023 manifest-in-closure wiring); (c) both query and transform changed in the same PC → owning definition regenerates exactly once (no double fan-out); (d) two definitions sharing one query → query edit selects both definitions; (e) new artifact definition that exists only on the source branch → `_definition_changed` selects it (verifies the gather query picks up source-branch-only definitions). (Placement deviation, same rationale as T032: realized at `backend/tests/component/proposed_change/test_artifact_regen_edge_cases.py`.)

**Checkpoint**: SC-001, SC-002, SC-004 satisfied for `CoreRepository`. US1 demonstrable via spec.md User Story 1's Independent Test.

---

## Phase 4: User Story 2 — Diagnostic visibility for regeneration decisions (Priority: P1)

**Goal**: Every "all artifacts regenerated for definition X" decision and every closure-builder failure or unresolved reference at import time produces a Prefect-logger entry naming the triggering file path, query, definition attribute, or unresolved Jinja2 site (FR-022, FR-023, FR-023a).

**Independent Test**: Edit one transform file in a PC → pipeline task log contains an entry naming the file and the affected definition. Repeat with a `.gql` query edit → log identifies the query by name. Edit the definition's `targets` relationship → log identifies the attribute that changed. Trigger an unresolved Jinja2 include at import time → log records every unresolved site.

### Tests

- [X] T035 [P] [US2] Unit tests in `backend/tests/unit/proposed_change/test_predicate_logging.py` asserting that each predicate's match branch produces the diagnostic matching the format in contracts/pipeline-predicates.md "Diagnostic log" stanzas. (Per PR-9442 review feedback - Pol's single-responsibility note and Aaron/Pol's explicit-DI preference - the predicates were kept pure: each returns a `PredicateOutcome(matched, reason)` rather than taking a logger and emitting as a side effect. The selection gate owns logging (emits `outcome.reason` when set), so these tests assert the exact `reason` string directly with no `caplog`/logger; non-match cases assert `reason is None`. ASCII hyphens replace the contract's em dashes per repo convention.)
- [X] T036 [P] [US2] Unit tests in `backend/tests/unit/git/closure_builder/test_jinja2_closure_logging.py` asserting the Jinja2 walker emits an info log per unresolved reference, even when several appear in the same template (FR-023a). (`UnresolvedRef` carries `file` + a descriptive `location` rather than a line number, so the log names the file and location string; "file + line" from the task is approximated by file + location.)

### Implementation

- [X] T037 [US2] Surface the diagnostic for `_query_changed` (format per contracts/pipeline-predicates.md: definition name/id, query name, query id). `query_name` is plumbed via T026/T027 — no further gather-query work needed here. (Predicate returns the reason on `PredicateOutcome`; the `refresh_artifacts` selection gate - the canonical decision site - emits it. `validate_artifacts_generation` consumes only `.matched` and keeps its existing generic log, so the granular why-trail is emitted once at the gate.)
- [X] T038 [US2] Surface the diagnostic for `_definition_changed`, naming the specific attribute or relationship that changed (read from the matching `diff_summary` entry's per-field detail). (Names the changed element names whose action is added/updated; falls back to a generic "definition node was modified" when no per-field detail is present on the matching entry.)
- [X] T039 [US2] Surface the diagnostic for `_transform_changed`: name the intersecting file path on the precise-closure path; on the `dependencies_complete=False` fallback path the incomplete-closure explanation; on the `dependencies=null` legacy fallback path the per-transform legacy-fallback explanation from contracts/pipeline-predicates.md. (Deviation: the contract's "Unresolved references: [...]" suffix on the incomplete path is omitted — unresolved refs are recorded only at import time and are not plumbed onto the pipeline model, which carries only `dependencies` + `dependencies_complete`. The two fallback branches are distinguished so each carries its own reason; boolean behavior is unchanged.)
- [X] T040 [US2] Emit a Prefect-logger info entry from `Jinja2Closure` for each unresolved reference encountered during the walk (FR-023a). Continue walking after each. (Required `logger` injected on `Jinja2Closure`, threaded from `build_default_closure_builder`; logs are emitted from a `_log_unresolved` helper over the collected refs at both return points, so every site in a template is reported. The walk never aborts on an unresolved ref. Per PR-9442 review feedback - Aaron/Pol's explicit-DI preference - the test-only no-logger path was removed: `logger` is now required and non-`None` on `Jinja2Closure`, `AggregatedTransformClosureBuilder`, and `build_default_closure_builder`; tests inject a real `logging.getLogger(__name__)` read back via `caplog`, so the obsolete `test_no_logger_is_safe` / `test_logging_is_optional` were dropped.)
- [X] T041 [US2] Confirm the integrator's closure-builder failure-isolation path (T025) emits the per-transform Prefect-logger error with identity and failure mode (FR-023). (Already satisfied by `AggregatedTransformClosureBuilder.build`'s `logger.exception(...)`, which logs the transform name plus the traceback; asserted by `test_dispatcher.py::test_jinja2_failure_is_isolated_and_logged`. No code change.)

### Functional test

- [X] T042 [US2] Test asserting log content for quickstart.md Scenarios 2, 3, 5, 8, and the pipeline half of 10. Reads captured Prefect flow-run-logger output and matches the expected format strings. (Placement deviation, same rationale as T032/T034: realized at `backend/tests/component/proposed_change/test_artifact_regen_logging.py`, driving `refresh_artifacts` with a `WorkflowRecorder`. Prefect's `prefect.flow_runs` logger does not propagate to root by default, so a class fixture forces propagation to let `caplog` observe the task-log entries. Scenario 11's failure-isolation log and Scenario 10's import-time per-unresolved-reference log occur in the closure builder, not the pipeline gate, and are asserted by T036 / `test_dispatcher.py`; they are not re-driven here because a literal replay needs the deferred git-branch-commit integration_docker infra of T033.)

**Checkpoint**: SC-003, SC-008 satisfied. Users can answer "why did these artifacts regenerate?" from the task log alone.

---

## Phase 5: User Story 3 — User-declared dependencies via `watch:` (Priority: P2)

**Goal**: Users can declare `watch: { files: [...] }` on Jinja2/Python transform entries in `.infrahub.yml` to extend the auto-detected closure. Strict object form only (no list/object union). Directory entries match recursively. When non-empty, `dependencies_complete=True` even if auto-detection had unresolved references (FR-014).

**Independent Test**: Author a Jinja2 transform with a dynamic include and declare `watch.files: [templates/partials/]`. After re-import, edits inside `templates/partials/` regenerate the affected artifacts; edits outside both the watch list and the auto-detected closure do not.

### Tests

- [ ] T043 [P] [US3] SDK unit tests for `InfrahubWatchConfig` under `python_sdk/tests/unit/schema/test_repository_watch_config.py` (or the existing repository-schema test path): object form parses with `files: list[str]`; list form `watch: [a, b]` rejected (FR-011); unknown keys rejected (`extra="forbid"`); string form rejected; empty `watch: {}` accepted as no-op; embedded on both `InfrahubJinja2TransformConfig` and `InfrahubPythonTransformConfig`.
- [ ] T044 [P] [US3] Integrator unit tests in `backend/tests/unit/git/closure_builder/test_watch_union.py`: directory entries in `watch.files` expanded recursively (FR-010); files unioned with the auto-detected closure (FR-012); `dependencies_complete` flips to True when `watch.files` is non-empty even after unresolved auto-detection (FR-014); each `watch.files` entry passes through the canonicalizer; symlinks skipped (Decision 8); `.gitignore`d / `.pyc` / `__pycache__` excluded.

### Implementation

- [ ] T045 [US3] Add `InfrahubWatchConfig` Pydantic model in `python_sdk/infrahub_sdk/schema/repository.py` per data-model.md §5: `model_config = ConfigDict(extra="forbid")`, `files: list[str] = Field(default_factory=list, description=...)`.
- [ ] T046 [US3] Add `watch: InfrahubWatchConfig | None = None` field on `InfrahubJinja2TransformConfig` and `InfrahubPythonTransformConfig` in the same file.
- [ ] T047 [US3] In `backend/infrahub/git/integrator.py`, read `watch.files` from each parsed transform config; expand directory entries recursively (skipping symlinks per Decision 8 and `.gitignore`d / `__pycache__` / `.pyc` per FR-006); canonicalize each resulting entry; union with the auto-detected closure before storing.
- [ ] T048 [US3] Compute the final stored `dependencies_complete` value per contracts/watch-config.md "Completeness rule": `True` if either auto-detection had zero unresolved references OR `watch.files` is non-empty.

### End-to-end tests

- [ ] T049 [US3] Functional test in `backend/tests/functional/proposed_change/test_artifact_regen_watch.py` mirroring quickstart.md Scenario 6: declares `watch.files: [templates/partials/]` on a Jinja2 transform; asserts regeneration on declared-closure-file edit and non-regeneration on unrelated-file edit.
- [ ] T050 [US3] Integration_docker test in `backend/tests/integration_docker/proposed_change/test_artifact_regen_watch_e2e.py` exercising `watch.files` on a Python transform that imports from a sibling top-level package (US3 acceptance 3).

### Documentation

- [ ] T051 [P] [US3] Add the `watch:` schema reference under `docs/docs/reference/infrahub-yml/` per spec.md "Documentation Deliverables": strict object form with the `files:` key, recursive directory matching, note that future keys (`strict:`, `exclude:`) will live under `watch:`, one Python and one Jinja2 worked example.

**Checkpoint**: SC-007 satisfied. Users with dynamic-include transforms have a precise opt-in.

---

## Phase 6: User Story 4 — Safe rollout without operator intervention (Priority: P2)

**Goal**: Pre-feature transforms (imported before Stage 2 deployed; `dependencies = null`) keep working without operator action; closure-builder failure on one transform does not block import of others in the same repo; the precise gate self-heals per transform on its next natural re-import (FR-024, FR-025, US4 acceptance 1–3).

**Independent Test**: Run a PC against a DB containing transforms imported under the pre-feature code — pipeline behaves as it did before the upgrade. Commit a change that triggers re-import of one transform → that transform switches to the precise gate on the next PC; the others stay on the legacy fallback.

### Tests

- [X] T052 [P] [US4] Unit coverage that `_transform_changed` matches on any non-empty `repo_diff` when `dependencies=None`/`dependencies_complete=None`, and carries the legacy-fallback diagnostic (FR-024). (Satisfied by existing `test_predicates.py` cases `null_null_with_no_file_changes_is_false` / `null_null_with_any_file_change_is_true` for the verdict, plus `test_predicate_logging.py::test_transform_changed_reason_explains_the_legacy_fallback` for the reason. Under the Option-3 design the predicate returns the reason rather than emitting a log, so no new test was added to avoid duplicating the existing cases.)
- [X] T053 [P] [US4] Unit test that one transform with a build failure yields `complete=False` and a logged error while sibling well-formed transforms still produce fully-populated closures (FR-023, US4 acceptance 3). (Placement deviation: realized at `backend/tests/unit/git/closure_builder/test_dispatcher.py::test_closure_failure_does_not_poison_well_formed_siblings`, not an `integrator/` unit test. Per work-division-plan correction #2 the integrator import path is only exercisable through a real git worktree + DB - i.e. integration_docker - so the isolation contract is unit-tested at the dispatcher where it actually lives: independent `build()` calls mean one failure cannot affect a sibling's closure.)

### Implementation

- [X] T054 [US4] Confirm `_transform_changed`'s null-handling branch carries the per-transform legacy-fallback diagnostic and the gate emits it. (Predicate returns the legacy reason on `PredicateOutcome`; the gate logs it. Driven end-to-end by `test_artifact_regen_logging.py::test_legacy_closure_log_explains_the_self_heal`, which adds a `dependencies=null` transform/definition to the dataset and asserts the self-heal message reaches the flow-run log.)
- [X] T055 [US4] Confirm the closure-failure isolation path records `complete=False` and continues; regression-guard added in T053. (`AggregatedTransformClosureBuilder.build`'s typed-failure catch returns a `complete=False` fallback and logs; the T053 sibling test guards that a failure does not poison subsequent builds.)

### End-to-end tests

- [ ] T056 [US4] Functional test in `backend/tests/functional/proposed_change/test_legacy_fallback.py` mirroring quickstart.md Scenario 9: pre-feature transform, no re-import, PC runs and behaves as it would have pre-feature; log records the per-transform legacy-fallback explanation. **DEFERRED** (same rationale as T033): a literal PC-against-repo replay needs follow-up-commit-on-a-branch test infrastructure that no helper provides today. The pipeline-half behavior (legacy-fallback selection + diagnostic) is covered by `test_artifact_regen_logging.py::test_legacy_closure_log_explains_the_self_heal` and the predicate unit tests.
- [ ] T057 [US4] Integration_docker test in `backend/tests/integration_docker/proposed_change/test_closure_failure_isolation_e2e.py` mirroring quickstart.md Scenario 11: one malformed Jinja2 template alongside several well-formed transforms; verifies import isolation, `dependencies_complete=False` on the malformed transform, well-formed transforms imported successfully. **DEFERRED** to the integration_docker pass (needs the docker stack). The isolation contract is unit-covered by T053.

### Documentation

- [X] T058 [P] [US4] Per-transform rollout note in the changelog. (Realized as a single consolidated fragment `changelog/+infp-409.changed.md` covering the feature as it ships to `develop` - precise per-affected-transform regeneration, the per-decision task-log trail, and the safe per-transform self-heal rollout - rather than the stage1/stage2 split of T004/T067, which assumed separate releases. T004/T067 are superseded by this fragment; reconcile if a staged release is reintroduced.)
- [ ] T059 [P] [US4] Add `dependencies_complete = False` user guidance to the proposed-change/artifacts docs per spec.md Documentation Deliverables: what it means, the two fixes (rewrite the include with a literal name, or declare a covering `watch.files` list), and how to use the unresolved-reference log entries. **DEFERRED** to the docs pass after US3: the primary fix it must document (`watch.files`) is the US3 feature and is not in this PR, so the guidance would reference a capability that does not yet exist. The original target `docs/docs/topics/proposed-change.mdx` has also been restructured (now `docs/docs/proposed-changes/overview.mdx`); placement should be reconciled with T066 in the same pass.

**Checkpoint**: SC-005, SC-008, SC-009 satisfied. Upgrade is safe with no operator action.

---

## Phase 7: User Story 5 — Read-only repositories participate fully (Priority: P2)

**Goal**: Per-repo file diff is computed for every linked repository, every branch pair, regardless of the source branch's `sync_with_git` attribute (FR-017). `CoreReadOnlyRepository` diffs between pinned commits on the source vs destination Infrahub branches (FR-019); `CoreRepository` diffs between tracked Git branch tips (FR-018). Empty diff → no file-change-driven regeneration (FR-020).

**Independent Test**: Set `sync_with_git=False` on a branch. Bump a `CoreReadOnlyRepository`'s pinned commit on the source branch to one that modifies a `.gql` query referenced by definition `B`. Open PC → definition `B`'s artifacts regenerate.

### Tests

- [X] T060 [P] [US5] Unit test in `backend/tests/unit/proposed_change/test_branch_diff.py`: per-repo file diff for a `CoreRepository` is computed regardless of `source_branch.sync_with_git` (FR-017, FR-018); empty diff returned when tracked branch tips did not move (FR-020). (`populate_repository_file_diffs` takes no `sync_with_git` argument - it diffs purely from the per-branch commit values - so the decoupling is structural; tests assert the managed repo is diffed with its source/destination commits and `CoreRepository` kind, and that equal/missing commits skip the diff. Git IO is injected via the `RepositoryFileDiffer` protocol and exercised end-to-end in T065.)
- [X] T061 [P] [US5] Unit test in `backend/tests/unit/proposed_change/test_branch_diff.py`: per-repo file diff for a `CoreReadOnlyRepository` uses each Infrahub branch's pinned commit (FR-019); diff source is the pinned-commit-to-pinned-commit `git diff`. (Investigation per Notes: `CoreReadOnlyRepository.commit` is `BranchSupportType.AWARE`, so the existing `SOURCE_READONLY_REPOSITORIES` gather query already yields the per-branch pinned commit into `source_commit`/`destination_commit` - no new pinned-commit helper was needed. The kind dispatch in T063 reuses `get_initialized_repo(repository_kind=...)`. Test asserts the read-only repo is diffed with its pinned commits and `CoreReadOnlyRepository` kind.)

### Implementation

- [X] T062 [US5] Refactor `backend/infrahub/proposed_change/branch_diff.py` (or the function populating `ProposedChangeRepository.files_added`/`files_changed`/`files_removed`) to compute file diffs per linked repository for every branch pair, decoupled from `source_branch.sync_with_git`. (The populator moved from `proposed_change/tasks.py::_gather_repository_repository_diffs` into `branch_diff.py::populate_repository_file_diffs`, gated on the new `ProposedChangeRepository.has_file_diff` property - both commits present and differing - rather than `has_diff` which excluded read-only repos. Git access is behind a `RepositoryFileDiffer` protocol with a production `GitRepositoryFileDiffer` and an in-memory test adapter, per the backend-component-design and no-mock testing rules; `has_diff` is retained unchanged for merge-conflict validation. The dead `else: list_all_files` branch was unreachable under the old gate and was dropped.)
- [X] T063 [US5] In the same module, branch on repository kind per data-model.md §6: `CoreRepository` → diff between source vs destination branches' tracked Git branch tips; `CoreReadOnlyRepository` → diff between source vs destination branches' pinned commits. (Realized by passing `repo.kind` to the existing `get_initialized_repo` dispatcher, which loads the correct repository class; the source/destination commits already hold tracked tips for managed repos and per-branch pinned commits for read-only repos, so the single `calculate_diff_between_commits` call is correct for both kinds.)

### End-to-end tests

- [ ] T064 [US5] Functional test in `backend/tests/functional/proposed_change/test_readonly_repo_diff.py` mirroring quickstart.md Scenario 7: `sync_with_git=False` branch, ReadOnly repo commit bump modifies a `.gql` query → affected definition regenerates.
- [ ] T065 [US5] Integration_docker test in `backend/tests/integration_docker/proposed_change/test_readonly_repo_e2e.py`: end-to-end PC against a `CoreReadOnlyRepository` with two pinned commits across branches.

**Checkpoint**: SC-006 satisfied. Read-only repositories participate in the precise regeneration gate.

---

## Phase 8: Polish & Cross-Cutting Concerns

- [ ] T066 [P] Add the "Where to find the why trail" section to `docs/docs/topics/proposed-change.mdx` per spec.md Documentation Deliverables: points users at the repository task log as the canonical place to see which file/query/relationship change caused a regeneration; includes one example log line.
- [ ] T067 [P] Write the Stage 2 Towncrier fragment `changelog/+infp-409-stage2.changed.md` covering schema additions, `watch:` SDK schema, closure builders, read-only-repo decoupling, and per-transform self-heal rollout.
- [ ] T068 Run `uv run invoke format` and `uv run invoke lint` over all changed Python; resolve any new ruff/mypy violations introduced by closure_builder, predicates, or integrator changes.
- [ ] T069 Run `uv run invoke docs.lint` against `docs/` changes from T051, T059, T066. (`dev/specs/` is out of docs-lint scope per project memory.)
- [ ] T070 Walk through `dev/specs/infp-409-artifact-regen-triggers/quickstart.md` Scenarios 1–12 manually against a built dev instance (`uv run invoke dev.build && uv run invoke dev.start`); record pass/fail in a checklist comment on the PR.
- [ ] T071 [P] Verify generated files are in sync after final rebase: `git status` shows expected updates under `backend/infrahub/core/schema/generated/`, `backend/infrahub/core/protocols.py`, `frontend/app/src/shared/api/graphql/generated/`, `schema/schema.graphql`, and `schema/openapi.json`, and nothing else generated is stale.
- [ ] T072 [P] Remove the dead `FILE_CHANGES` selection-gate constant from `backend/infrahub/proposed_change/tasks.py` (its only consumers were the gates T013/T014 replaced, then T030/T031 removed the residual `has_file_modifications` clause). Before deleting, run `git grep FILE_CHANGES` to verify no other consumers remain; also remove any helper functions (e.g. `has_file_modifications`) whose only callers are now gone.
- [ ] T073 SDK release coordination for the `watch:` schema (T045/T046). The SDK is a git submodule at `python_sdk/`. Process: (1) land T045/T046 in the SDK repo on its target branch; (2) cut an SDK release containing those changes; (3) bump the submodule pointer in this repo to the release commit; (4) verify Stage 2 integration_docker tests (T050, T057, T065) consume the released SDK and not a local working copy. Coordinate timing so no PR in this repo depends on an unreleased SDK pin.

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: no dependencies — start immediately.
- **Foundational (Phase 2)**: depends on Setup. Blocks every user story.
- **US1 (Phase 3)**: depends on Phase 2. Implements the regeneration gate end-to-end across Stage 1 + Stage 2. Its schema additions (T015–T018), pipeline plumbing (T026–T027), and integrator wiring (T024, T025) are prerequisites for US2, US3, and US4.
- **US2 (Phase 4)**: depends on US1 (predicates and integrator paths must exist before logging can be added/asserted at those sites; `query_name` plumbing from T026/T027 is required by T037).
- **US3 (Phase 5)**: depends on US1 Stage 2 (schema + integrator path) and on T073's SDK release pipeline.
- **US4 (Phase 6)**: depends on US1 Stage 2 (null-fallback in `_transform_changed`, integrator failure isolation).
- **US5 (Phase 7)**: depends on Phase 2. Its full benefit lands once US1 Stage 2's `_transform_changed` is also live, but the diff-decoupling work is independent of US1 and can land in parallel.
- **Polish (Phase 8)**: depends on US1–US5. T072 (dead-code cleanup) requires T030/T031 to have landed. T073 (SDK release) can begin as soon as T045/T046 are merged in the SDK repo.

### User Story Dependencies

- US1 is the trunk: Stage 1 (T009–T014) and Stage 2 (T015–T034) deliver the core regeneration gate.
- US2 piggybacks on US1's call sites — log emission is added inside the predicates and the integrator. Cannot start meaningfully until US1's predicate/integrator skeletons exist.
- US3, US4, US5 are independent of each other and depend only on US1's Stage 2 surface. They can be worked in parallel after US1 Stage 2 lands.

### Within Each User Story

- Tests written first (Constitution IV / Test Discipline).
- Schema change → regenerate generated files → wire predicate / closure-builder consumers.
- Closure-builder unit tests → builder implementation → integrator wiring.
- Functional and integration_docker tests last in each story (they exercise the assembled stack).

### Parallel Opportunities

- T002, T003, T004 in parallel within Phase 1.
- T007 in parallel with T006 (test in a different file).
- T009, T010, T019, T021, T028 are independent test files within US1 and can be authored in parallel.
- T035, T036 in parallel within US2.
- T043, T044 in parallel within US3.
- T052, T053 in parallel within US4.
- T060, T061 in parallel within US5.
- T066, T067, T071, T072 in parallel within Phase 8.

---

## Parallel Example: User Story 1 (Stage 2 closure builders)

```bash
# Tests authored in parallel (different files, no dependencies):
Task: "Unit tests for Jinja2Closure in backend/tests/unit/git/closure_builder/test_jinja2_closure.py"
Task: "Unit tests for PythonClosure in backend/tests/unit/git/closure_builder/test_python_closure.py"
Task: "Unit tests for _transform_changed in backend/tests/unit/proposed_change/test_predicates.py"

# Then implementations in parallel (different files):
Task: "Implement Jinja2Closure in backend/infrahub/git/closure_builder/jinja2_closure.py"
Task: "Implement PythonClosure in backend/infrahub/git/closure_builder/python_closure.py"
```

---

## Implementation Strategy

### MVP First (US1 Stage 1 only)

1. Phase 1 + Phase 2 (Setup + Foundational).
2. US1 Stage 1 only: T009–T014. Schema work (T015–T018) deferred.
3. **STOP and VALIDATE**: README-only and unrelated-Python-only PCs no longer regenerate artifacts on the data-change path. Transform-file edits still over-regenerate (residual `has_file_modifications` clause is intentionally retained per spec's "Stage 1 / Stage 2 interim behavior").
4. Ship Stage 1 as its own release/PR if the team wants to stage; otherwise continue.

### Incremental Delivery

1. US1 Stage 1 → MVP per above.
2. US1 Stage 2 (T015–T034) → closes the spec's interim fallback; full US1 satisfied.
3. US2 (T035–T042) → lands alongside Stage 2 so the precise decisions are debuggable from day one.
4. US3 (T043–T051), US4 (T052–T059), US5 (T060–T065) → ship in parallel after US1 Stage 2. US3 requires SDK release coordination per plan.md "Constraints" (T073).
5. Phase 8 → polish, changelog, manual quickstart sweep, dead-code cleanup, SDK release coord.

### Parallel Team Strategy

After Phase 2 lands:

- Developer A: US1 Stage 1 (T009–T014) → US1 Stage 2 closure builders + integrator wiring (T019–T025).
- Developer B: starts US1 Stage 2 schema + plumbing once T013/T014 are merged (T015–T018, T026–T031).
- Developer C: US5 branch_diff decoupling (T060–T065) — independent of US1 plumbing.

After US1 Stage 2 lands:

- Developer A: US3 SDK schema + integrator union (T043–T051) → kicks off T073 SDK release.
- Developer B: US2 logging polish (T035–T042) followed by US4 rollout safety (T052–T059).

---

## Notes

- The `_transform_changed` null-handling branch (T029) implements both US1 (the path) and US4 (the fallback semantics). US4 tasks (T052, T054, T056) verify the behavior is correct; they do not re-implement it.
- The integrator's closure-failure isolation path (T025) implements both US1 (the path) and US4 acceptance 3 (the isolation semantics). T053/T057 verify it.
- `.infrahub.yml` whole-file conservatism (FR-021) is implemented in T023 (manifest path appended to every transform's closure) and asserted end-to-end in T034 (edge case b).
- Symlink skipping (Decision 8) is implemented in both T022 (Python closure) and T047 (watch.files directory expansion); both surfaces are tested in T021 and T044 respectively.
- No new mocks are introduced beyond the existing Prefect logger surface (Constitution IV). Functional and integration_docker tests use a real DB and a real git worktree.
- Frontend has no scope per plan.md "Frontend principles" — regenerated GraphQL types (T017) are mechanical schema-export updates only.
- **Pre-implementation investigation for T061/T063**: the design docs do not describe the existing helper for "pinned commit on Infrahub branch X" for `CoreReadOnlyRepository`. Before T063 can be sized, identify the helper (or write one) and confirm the diff target (commit SHA vs ref) lines up with what `branch_diff` consumes today.
- **T027 generated-file impact**: the `GATHER_ARTIFACT_DEFINITIONS` query is likely a `.gql` source whose typed Python wrapper lives under `backend/infrahub/generators/graphql_queries/` (AGENTS.md "Generated Files"). Re-running `uv run invoke backend.generate` after editing the `.gql` is required; do not hand-edit the generated wrapper.
