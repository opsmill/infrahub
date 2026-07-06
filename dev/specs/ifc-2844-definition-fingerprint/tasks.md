---
description: "Task list for Definition Fingerprint Foundation (IFC-2844)"
---

# Tasks: Definition Fingerprint Foundation

**Input**: Design documents from `/specs/ifc-2844-definition-fingerprint/`

**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/fingerprint-composition.md, quickstart.md

**Tests**: Included. The spec, plan, and quickstart explicitly require unit tests (pure composers, blob resolver, watch-state discrimination, canonicalisation) and integration tests (import-and-store, re-import stability, closure/query/param/group scenarios, branch diff).

**Organization**: Tasks are grouped by user story. Priority order from spec.md: US1 (P1), US5 (P1), US2 (P1), US3 (P2), US4 (P2). US5 is sequenced before US2 because the watch three-state discriminator is a prerequisite of the first stable transformation fingerprint.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies on incomplete tasks)
- **[Story]**: Which user story this task belongs to (US1-US5)
- All paths are repository-root relative

## Conventions (from AGENTS.md / research.md)

- Hash: SHA-256 hex digest over a canonical UTF-8 tuple serialisation (`hashlib`, no new dep).
- Fingerprint logic lives in a new `backend/infrahub/git/fingerprint/` package with small, constructor-injected components.
- No Jira/spec/FR IDs in source comments, docstrings, or test names (repo convention).
- Generated files are regenerated offline, never hand-edited.

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Create the new package and test-directory skeletons.

- [X] T001 Create the `backend/infrahub/git/fingerprint/` package with an empty `__init__.py` and empty stub modules `composer.py`, `blob_resolver.py`, `registry.py`, `hasher.py` (or `canonical.py` for canonicalisation helpers), each with module docstring only.
- [X] T002 [P] Create the unit test package `backend/tests/unit/git/fingerprint/` with an empty `__init__.py`.
- [X] T003 [P] Create the changelog fragment `changelog/+ifc-2844.added.md` describing the new nullable branch-aware `fingerprint` attribute on `CoreGraphQLQuery`, `CoreTransformation`, `CoreArtifactDefinition`, and `CoreGeneratorDefinition`.

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: The schema field must exist (and be regenerated) before any fingerprint can be stored, and the shared hashing/registry/blob-resolver components must exist before any composer can be written.

**⚠️ CRITICAL**: No user story work can begin until this phase is complete.

### Schema attributes (FR-001 - FR-004)

- [X] T004 [P] Add the `fingerprint` `Text` attribute (optional=True, `branch=BranchSupportType.AWARE`, read_only=False, unique=False) to `CoreGraphQLQuery` in `backend/infrahub/core/schema/definitions/core/graphql_query.py`.
- [X] T005 [P] Add the same `fingerprint` attribute to the `CoreTransformation` generic in `backend/infrahub/core/schema/definitions/core/transform.py` (declared once; inherited by `CoreTransformPython`/`CoreTransformJinja2`).
- [X] T006 [P] Add the same `fingerprint` attribute to `CoreArtifactDefinition` in `backend/infrahub/core/schema/definitions/core/artifact.py`.
- [X] T007 [P] Add the same `fingerprint` attribute to `CoreGeneratorDefinition` in `backend/infrahub/core/schema/definitions/core/generator.py`.
- [X] T008 Regenerate backend generated files (depends on T004-T007): run `uv run invoke backend.generate` and confirm `fingerprint` appears in `backend/infrahub/core/protocols.py` and `backend/infrahub/core/schema/generated/`.
- [X] T009 Regenerate schema/frontend exports (depends on T008): run `uv run invoke schema.generate-graphqlschema`, `uv run invoke schema.generate-jsonschema`, and `cd frontend/app && pnpm codegen`; confirm `fingerprint` in `schema/schema.graphql`, `schema/openapi.json`, and `frontend/app/src/shared/api/graphql/generated/`.

### Shared fingerprint components

- [X] T010 [P] Implement the SHA-256 hasher and canonicalisation helpers in `backend/infrahub/git/fingerprint/hasher.py`: a function that hashes an ordered tuple of canonicalised inputs to a hex digest, plus `parameters` canonicalisation via `json.dumps(..., sort_keys=True, separators=(",", ":"))` (FR-014).
- [X] T011 [P] Implement the blob-SHA resolver in `backend/infrahub/git/fingerprint/blob_resolver.py`: resolve `{repo_relative_path: git_blob_sha}` from the git tree at the imported commit (GitPython `Repo(worktree).commit(commit).tree`), reading git metadata only, never file contents (FR-009b). Constructor-injected worktree/commit.
- [X] T011a [P] Implement a closure-path selector helper (in `backend/infrahub/git/fingerprint/composer.py` or `hasher.py`) that, given the stored `dependencies`, returns the paths to hash with `.infrahub.yml` (`closure_builder.post_processing.MANIFEST_PATH`) EXCLUDED. RATIONALE (verified against the codebase): `append_manifest_path` merges `.infrahub.yml` into every transform/generator's stored `dependencies`, so hashing all pairs verbatim would change the fingerprint on any comment-only or unrelated `.infrahub.yml` edit and violate SC-005 / the "comment-only manifest edit" edge case. The manifest's output-affecting fields are folded in separately as parsed scalars (`class_name`, `template_path`, `parameters`, ...), not as bytes. The definition's own source file and any `watch:` files MUST remain in the hashed set. This selector is shared by the transformation (US2) and generator (US4) composers.
- [X] T012 [P] Implement the per-import fingerprint registry in `backend/infrahub/git/fingerprint/registry.py`: an in-memory `{(kind, name): fingerprint_hexdigest}` snapshot with set/get, so higher layers read the freshly-computed lower-level value and never a stored graph value (FR-015a).
- [X] T013 Define the layered composer skeleton in `backend/infrahub/git/fingerprint/composer.py` (depends on T010-T012, T011a): a class with constructor-injected hasher, blob resolver, registry, and closure-path selector, exposing `compose_query`, `compose_transformation`, `compose_artifact_definition`, `compose_generator_definition` entry methods (bodies stubbed/`NotImplementedError`, filled in per story). Registry lookups for cross-references use the referenced definition's name (artifact def -> transform by `transformation` name across both transform kinds; artifact/generator def -> target group by `targets` name resolved to id); ensure the registry key scheme supports these name-based lookups.

### Integrator sequencing scaffold (FR-015a)

- [X] T014 In `backend/infrahub/git/integrator.py`, introduce the per-import fingerprint registry instance and sequence the import phases in dependency order (queries -> transformations/generator-definitions -> artifact-definitions) threading the registry through, WITHOUT yet computing any fingerprint value (no behaviour change, FR-020). This establishes the ordering the composers plug into.

**Checkpoint**: Schema field exists and is regenerated; shared components and integrator ordering are in place. User stories can now begin.

---

## Phase 3: User Story 1 - GraphQL Query fingerprint primitive (Priority: P1) 🎯 MVP

**Goal**: An imported `CoreGraphQLQuery` carries a `fingerprint` = `H(stored fragment-inlined query text)`, written via the SDK-over-GraphQL mutation path.

**Independent Test**: Import a repo with a query -> non-null fingerprint. Re-import byte-identical -> unchanged. Edit query text -> changes. Edit unrelated file -> query fingerprint unchanged.

### Tests for User Story 1

- [X] T015 [P] [US1] Unit test `compose_query` in `backend/tests/unit/git/fingerprint/test_composer_query.py`: deterministic digest over stored inlined query text; identical text -> identical digest; different text -> different digest; edit-then-revert net-zero (SC-004).
- [X] T016 [P] [US1] Integration test in `backend/tests/integration/git/test_fingerprint_query.py` (model on `test_generator_import_closure.py`, reuse `car-dealership` fixture + `FileRepo`/`MultipleStagesFileRepo`): import -> query `fingerprint` non-null (SC-001); no-op re-import unchanged (SC-002); query-text edit changes it (SC-003); unrelated-file edit leaves it unchanged.

### Implementation for User Story 1

- [X] T017 [US1] Implement `compose_query` in `backend/infrahub/git/fingerprint/composer.py` (FR-008): `H(query_text)` over the stored fragment-inlined `query` attribute; populate the registry under the query key.
- [X] T018 [US1] In `backend/infrahub/git/integrator.py`, compute the query fingerprint during the query import phase and pass it into the SDK create/update payload for `CoreGraphQLQuery` (FR-005, FR-006, FR-007: overwrite every import via the standard mutation path).

**Checkpoint**: Query fingerprint works end to end and is stored via the mutation path.

---

## Phase 4: User Story 5 - Watch-driven fingerprint stability (Priority: P1)

**Goal**: The watch config distinguishes three states - absent (`None`), explicit empty (present, no files), populated - and fingerprint computation folds a commit-id placeholder **iff** `watch is None` (FR-016/017/018/019). This must be correct before the first stable (transformation) fingerprint lands.

**Independent Test**: For each of the three watch states, the fold-commit-id decision is: absent -> fold (unstable every commit); present-empty -> omit (stable); populated -> omit + declared files join closure. The unit-level discrimination is fully testable standalone; end-to-end watch behaviour is asserted once US2/US4 transforms/generators exist.

### Tests for User Story 5

- [X] T019 [P] [US5] Unit test the watch three-state discriminator in `backend/tests/unit/git/fingerprint/test_watch_state.py`: `watch is None` -> fold commit id; `InfrahubWatchConfig` present with empty files -> omit; present with files -> omit and files contribute to the closure input. Confirm parsed config represents `None` vs present as distinct states (FR-019).

### Implementation for User Story 5

- [X] T020 [US5] Confirm (and if needed adjust) `python_sdk/infrahub_sdk/schema/repository.py` so the parsed `watch` config distinguishes absent (`None`) from present-but-empty for Jinja2, Python, and generator configs (research Decision 4: `watch: InfrahubWatchConfig | None`, expected no shape change - verify, do not rebuild).
- [X] T021 [US5] Add the commit-id fold helper to `backend/infrahub/git/fingerprint/composer.py` (or `hasher.py`): given the imported commit id and the config's `watch`, return the commit-id term iff `watch is None`, else omit it (FR-016/017). This helper is consumed by `compose_transformation` (US2) and `compose_generator_definition` (US4).

**Checkpoint**: The watch discriminator and commit-id fold are implemented and unit-tested for all three states.

---

## Phase 5: User Story 2 - Transformation fingerprint (Priority: P1)

**Goal**: `CoreTransformation` (Python + Jinja2) carries a fingerprint composing its connected query's fingerprint (from the same-import registry), the sorted `(path, blob_sha)` closure incl. its own source file, manifest config (`class_name`/`convert_query_response` for Python, `template_path` for Jinja2), and a commit-id iff `watch is None`. Excludes `timeout` and `description`.

**Independent Test**: Python + Jinja2 transforms non-null. With `watch` declared: no-op re-import unchanged; changes on connected-query fingerprint, closure blob SHA, `class_name`/`convert_query_response` (Py) or `template_path` (J2); unchanged on `timeout`-only edit; changes on own-`.py`/template edit even with `watch: {}`.

**Depends on**: US1 (query fingerprint in registry), US5 (watch fold), Foundational (blob resolver, registry).

### Tests for User Story 2

- [X] T022 [P] [US2] Unit test `compose_transformation` (Python) in `backend/tests/unit/git/fingerprint/test_composer_transformation.py`: incorporates query fingerprint, sorted `(path, blob_sha)` closure, `class_name`, `convert_query_response`; excludes `timeout` and `description`; folds commit id only when `watch is None`; and asserts the manifest path (`.infrahub.yml`) is excluded from the hashed closure so its blob SHA does not affect the digest, while the own source file and `watch:` files remain included (guards SC-005 at the unit level).
- [X] T023 [P] [US2] Unit test `compose_transformation` (Jinja2) in the same or a sibling test file: incorporates query fingerprint, sorted closure (incl. template), `template_path`; excludes `timeout`/`description`; watch-driven commit id.
- [X] T024 [P] [US2] Integration test in `backend/tests/integration/git/test_fingerprint_transformation.py`: import Python + Jinja2 transforms -> non-null; no-op re-import unchanged with `watch` declared (SC-002); closure-file blob-SHA change -> changes (US2 #4); connected-query change -> changes (US2 #5); `class_name`/`convert_query_response`/`template_path` change -> changes; `timeout`-only change -> unchanged (US2 #3); `watch: {}` + own-source-file edit -> changes (US2 #6, FR-009a); and, for a transform with declared `watch`, a comment-only / unrelated-section `.infrahub.yml` edit -> fingerprint unchanged (SC-005, FR-022 edge case).

### Implementation for User Story 2

- [X] T025 [US2] Implement `compose_transformation` in `backend/infrahub/git/fingerprint/composer.py` (FR-009/009a/009b/010/015b): read connected query fingerprint from the registry; run the stored `dependencies` through the T011a selector (manifest excluded, own source file + `watch:` files retained) and resolve their blob SHAs; hash with `class_name`/`convert_query_response` (Python) or `template_path` (Jinja2), fold commit id via the US5 helper; register the result.
- [X] T026 [US2] In `backend/infrahub/git/integrator.py`, compute the transformation fingerprint during the transformation import phase (after queries) and pass it into the SDK create/update payload for `CoreTransformPython`/`CoreTransformJinja2` (FR-006/007).

**Checkpoint**: Transformation fingerprint works for both concrete kinds, composing the query fingerprint and honouring watch semantics.

---

## Phase 6: User Story 3 - Artifact Definition fingerprint (Priority: P2)

**Goal**: `CoreArtifactDefinition` carries a fingerprint composing its transformation's fingerprint (from the registry) with `parameters` (canonical JSON), `content_type`, `artifact_name`, and target-group **identity** (related group id). Group membership is excluded.

**Independent Test**: Non-null. Changes on transformation fingerprint, `parameters`, `content_type`, `artifact_name`, or target-group re-point. Unchanged on group membership churn.

**Depends on**: US2 (transformation fingerprint in registry).

### Tests for User Story 3

- [X] T027 [P] [US3] Unit test `compose_artifact_definition` in `backend/tests/unit/git/fingerprint/test_composer_artifact_definition.py`: incorporates transformation fingerprint, canonical `parameters`, `content_type`, `artifact_name`, target-group id; identical inputs -> identical digest regardless of `parameters` key ordering (FR-014).
- [X] T028 [P] [US3] Integration test in `backend/tests/integration/git/test_fingerprint_artifact_definition.py`: import -> non-null; changes on transformation-fingerprint / `parameters` / `content_type` / `artifact_name` change; re-point target group -> changes; add/remove group member -> unchanged (SC-007).

### Implementation for User Story 3

- [X] T029 [US3] Implement `compose_artifact_definition` in `backend/infrahub/git/fingerprint/composer.py` (FR-011/013): read transformation fingerprint from the registry; resolve target-group id from `targets`; hash with canonical `parameters`, `content_type`, `artifact_name`, group id; register the result.
- [X] T030 [US3] In `backend/infrahub/git/integrator.py`, compute the artifact-definition fingerprint during the artifact-definition phase (after transformations) and pass it into the SDK create/update payload for `CoreArtifactDefinition` (FR-006/007).

**Checkpoint**: Artifact-definition fingerprint composes the transformation fingerprint and honours group-identity-not-membership.

---

## Phase 7: User Story 4 - Generator Definition fingerprint (Priority: P2)

**Goal**: `CoreGeneratorDefinition` carries a fingerprint composing its connected query's fingerprint, the sorted `(path, blob_sha)` closure (incl. own `.py`), `parameters`, `class_name`, `convert_query_response`, target-group identity, and a commit-id iff `watch is None`. Excludes `execute_in_proposed_change`, `execute_after_merge`, and group membership.

**Independent Test**: Non-null. Changes on query fingerprint, closure, `parameters`, group identity; same watch semantics as transforms; `watch: {}` + `class_name`/`convert_query_response` change -> changes (FR-012a); group membership churn -> unchanged.

**Depends on**: US1 (query), US5 (watch fold), US3 (group-identity rule), Foundational (blob resolver, registry). Requires PR #9700 generator `dependencies`/`dependencies_complete`/`watch` fields (assumed landed).

### Tests for User Story 4

- [X] T031 [P] [US4] Unit test `compose_generator_definition` in `backend/tests/unit/git/fingerprint/test_composer_generator_definition.py`: incorporates query fingerprint, sorted `(path, blob_sha)` closure (incl. own `.py`), canonical `parameters`, `class_name`, `convert_query_response`, target-group id; folds commit id iff `watch is None`; excludes `execute_in_proposed_change`/`execute_after_merge`.
- [X] T032 [P] [US4] Integration test in `backend/tests/integration/git/test_fingerprint_generator_definition.py`: import -> non-null; changes on query fingerprint / closure / `parameters` / group re-point; `watch` absent -> changes on every commit (SC-006); `watch: {}` + `class_name` change (different class, same unchanged file) or `convert_query_response` toggle -> changes (US4 #4, FR-012a); `watch: {}` + comment-only / unrelated `.infrahub.yml` edit -> unchanged (SC-005); group membership churn -> unchanged (SC-007).

### Implementation for User Story 4

- [X] T033 [US4] Implement `compose_generator_definition` in `backend/infrahub/git/fingerprint/composer.py` (FR-012/012a/013): read connected query fingerprint from the registry; run the closure through the T011a selector (manifest excluded, own `.py` + `watch:` files retained) and resolve blob SHAs; resolve target-group id; hash with canonical `parameters`, `class_name`, `convert_query_response`, group id; fold commit id via the US5 helper; register the result.
- [X] T034 [US4] In `backend/infrahub/git/integrator.py`, compute the generator-definition fingerprint during the generator-definition phase (alongside transformations, after queries) and pass it into the SDK create/update payload for `CoreGeneratorDefinition` (FR-006/007).

**Checkpoint**: All four definition kinds carry a computed, stored fingerprint.

---

## Phase 8: Polish & Cross-Cutting Concerns

**Purpose**: Cross-cutting invariants, branch behaviour, no-consumer-change regression, and final generated-file validation.

- [X] T035 [P] Integration test for the consistent snapshot (FR-015a) in `backend/tests/integration/git/test_fingerprint_snapshot.py`: change a query and its dependent artifact definition in the *same* commit/import -> the artifact-definition fingerprint reflects the new query fingerprint in that same import (no one-import lag).
- [X] T036 [P] Integration test for branch behaviour (SC-010) in `backend/tests/integration/git/test_fingerprint_branch.py`: the `fingerprint` appears in a branch diff and survives rebase/merge as a normal branch-aware attribute.
- [X] T037 Verify no consumer behaviour changed (SC-008, FR-020): run the existing regeneration/recompute regression suites (generator/artifact/computed-attribute trigger tests) and confirm identical trigger counts, all green.
- [X] T038 Run `uv run invoke docs.validate` and confirm generated-file/doc validation passes with all regenerated artifacts committed (SC-009).
- [X] T039 Run `/pre-ci` (format, lint, unit tests) and the quickstart.md validation walkthrough end to end.

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies - start immediately.
- **Foundational (Phase 2)**: Depends on Setup. BLOCKS all user stories. T008 depends on T004-T007; T009 depends on T008; T013 depends on T010-T012 and T011a.
- **US1 (Phase 3)**: Depends on Foundational. MVP.
- **US5 (Phase 4)**: Depends on Foundational. Sequenced before US2 (provides the watch fold helper US2 consumes).
- **US2 (Phase 5)**: Depends on US1 (registry query value) + US5 (watch fold).
- **US3 (Phase 6)**: Depends on US2 (registry transformation value).
- **US4 (Phase 7)**: Depends on US1 + US5 + US3 (group-identity rule); requires PR #9700 generator fields.
- **Polish (Phase 8)**: Depends on all targeted user stories being complete.

### User Story Dependency Graph

```text
US1 (query) ──► US2 (transformation) ──► US3 (artifact def)
   │                     ▲                     │ (group-identity rule)
   │              US5 (watch fold)             ▼
   └──────────────┴────────────────────► US4 (generator def)
```

### Within Each User Story

- Tests are written first and expected to FAIL before implementation.
- Composer method before integrator wiring.
- Registry population (composer) before any higher layer reads it.

### Parallel Opportunities

- Setup: T002, T003 in parallel.
- Foundational schema edits: T004-T007 in parallel (four different files); T010-T012 in parallel (three different files) after Setup.
- Within each story, the `[P]` unit and integration test tasks can be authored in parallel (different files).
- Once Foundational is done, US1 and US5 can proceed in parallel (different files) since US5's unit deliverable does not need US1. US2 waits on both.

---

## Parallel Example: Foundational schema attributes

```bash
# Launch the four schema-attribute edits together (different files):
Task: "Add fingerprint attr to graphql_query.py"      # T004
Task: "Add fingerprint attr to transform.py"          # T005
Task: "Add fingerprint attr to artifact.py"           # T006
Task: "Add fingerprint attr to generator.py"          # T007
# Then T008 (backend.generate) -> T009 (schema/frontend exports) run sequentially.
```

---

## Implementation Strategy

### MVP First (User Story 1 only)

1. Phase 1: Setup.
2. Phase 2: Foundational (schema field + regeneration + shared components + integrator ordering).
3. Phase 3: US1 - query fingerprint stored end to end via the mutation path.
4. **STOP and VALIDATE**: import a repo, assert non-null query fingerprint, re-import stability, edit-changes-it.

### Incremental Delivery

1. Setup + Foundational -> field exists, regenerated, shared plumbing ready.
2. US1 (query primitive) -> validate -> the reusable primitive is proven.
3. US5 (watch fold) -> validate the three-state discriminator.
4. US2 (transformation) -> validate full composition + watch semantics.
5. US3 (artifact definition) -> validate group-identity-not-membership.
6. US4 (generator definition) -> validate completeness (FR-012a) + watch parity.
7. Polish -> snapshot, branch, no-consumer-change, generated-file validation.

---

## Notes

- `[P]` = different files, no dependencies on incomplete tasks.
- The four schema-attribute tasks are independent files but their regeneration (T008/T009) is a hard sequential gate: all four must land before regenerating, and the regenerated files must be committed (CI validates staleness).
- Every composer method must both return the digest and register it, so higher layers read the same-import value (FR-015a); this is the mechanism the snapshot test (T035) guards.
- `.infrahub.yml` (`MANIFEST_PATH`) is merged into every transform/generator's stored `dependencies` by `append_manifest_path`. The fingerprint MUST exclude it from the hashed closure (T011a) - otherwise a comment-only manifest edit changes a blob SHA and breaks SC-005. FR-022 (manifest stays in the closure for the existing closure-diff consumer) and SC-005 (manifest bytes must not move the fingerprint) are only consistent because the fingerprint hashes parsed manifest fields, not manifest bytes.
- No consumer is wired in this feature (FR-020); T037 exists specifically to prove that.
- Per repo convention, no Jira/spec/FR IDs appear in test names, docstrings, or source comments.
