---
description: "Task list for Scope Computed-Attribute Recompute to Actual Schema Changes"
---

# Tasks: Scope Computed-Attribute Recompute to Actual Schema Changes

**Input**: Design documents from `dev/specs/001-scope-computed-attr-recompute/`
**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/recompute-scoping.md, quickstart.md

**Tests**: INCLUDED. Constitution Principle IV (Test Discipline) requires integration_docker coverage for features involving computed attributes; component + unit tests cover the scoping logic. Constitution Principle II requires the merge/rebase path and cross-branch isolation to be **specified and tested before complete** — those tests (T025, T034) are mandatory, not optional. Write tests first within each story and confirm they fail before implementing.

**Organization**: Tasks are grouped by user story (US1, US2, US3 from spec.md) so each story can be implemented and tested independently.

> Regenerated 2026-06-03 from the clarified spec + plan: full-depth dependency traversal with conservative fallback (FR-002/Q-B), any-edit-counts changed set (FR-004/Q-D), per-attribute opaque → recompute that attribute only (FR-013/Q-C), observability via task logs (FR-012/Q-A), and the mandatory branch-safety tests flagged by `/speckit-analyze` (C1 merge, C2 isolation, V1 branch-deletion, V2 scaling, V3 non-escalation).

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies on incomplete tasks)
- **[Story]**: US1 / US2 / US3 (user-story phases only)
- Exact file paths are included in every task

## Path Conventions

Single backend project. Source under `backend/infrahub/`, tests under `backend/tests/`. Spec/design docs under `dev/specs/001-scope-computed-attr-recompute/`.

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Create the module and test scaffolding the rest of the work hangs off.

- [X] T001 Create `backend/infrahub/computed_attribute/scoping.py` with a module docstring and placeholder imports (no logic yet) so incremental imports resolve
- [X] T002 [P] Create the unit test module `backend/tests/unit/computed_attribute/test_scoping.py` skeleton (imports + empty test stubs)
- [X] T003 [P] Create the component test module `backend/tests/component/computed_attribute/test_scoped_recompute_jinja2.py` skeleton, importing the existing `schema_with_jinja2` fixture from `backend/tests/component/computed_attribute/test_local_computation.py`

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: The changed-element plumbing and the kind-agnostic scoping component that ALL three stories depend on.

**⚠️ CRITICAL**: No user story work can begin until this phase is complete.

- [X] T004 Define `ChangedElementsPayload` (Pydantic, JSON-serializable: `added_kinds`, `removed_kinds`, `changed_fields`) and add optional `changed_elements: ChangedElementsPayload | None = None` to `SchemaUpdatedEvent` in `backend/infrahub/events/schema_action.py` (remove the stale NOTE about adding the diff)
- [X] T005 Define the internal `ChangedElementSet` frozen dataclass and a `from_schema_diff(...)` builder in `backend/infrahub/computed_attribute/scoping.py`; it carries every element the diff reports as changed — no value-affecting/cosmetic filtering (so cosmetic edits to a read element still count)
- [X] T006 Define `ComputedAttributeRef`, `DependencySet` (with `read_kinds`, `read_fields`, `depends_on_everything`), `SkippedAttribute`, and `RecomputeScopingReport` (with `fallback_full_recompute`) frozen dataclasses per data-model.md in `backend/infrahub/computed_attribute/scoping.py`
- [X] T007 Define the `ComputedAttributeDependencyDeriver` Protocol (`derive(*, schema_branch, computed_attribute) -> DependencySet`) in `backend/infrahub/computed_attribute/scoping.py`
- [X] T008 Implement `RecomputeScoper.scope(...)` kind-agnostic intersection logic in `backend/infrahub/computed_attribute/scoping.py`: `changed_elements is None` → `fallback_full_recompute=True` (all selected); `depends_on_everything` → selected WITHOUT setting `fallback_full_recompute` (per-attribute, no branch-wide escalation); `read_kinds ∩ (added ∪ removed)`; `read_fields ∩ changed_fields`; own `(owner_kind, attribute_name)` in `changed_fields`; else skip with reason. Enforce the selected/skipped disjoint-and-complete invariant
- [X] T009 [P] Unit-test `RecomputeScoper.scope()` with a fake deriver in `backend/tests/unit/computed_attribute/test_scoping.py`: intersection hits, skip on no-dependency, `None` → full-recompute fallback, and the FR-013 non-escalation case (one `depends_on_everything` attribute selected while an unrelated attribute is skipped and `fallback_full_recompute is False`), plus disjoint+complete invariant
- [X] T010 Populate `changed_elements` from the computed `SchemaDiff` when emitting `SchemaUpdatedEvent` on `backend/infrahub/api/schema.py` (schema load) and `backend/infrahub/graphql/mutations/schema.py` (interactive edit) — the only two emitters. Merge/rebase-applied schema changes flow through these emitters (`core/merge/branch_merger.py` does not emit the event), and the branch-deletion path leaves it `None`
- [X] T011 Thread `changed_elements` from the event payload into the workflow parameters of both `COMPUTED_ATTRIBUTE_SETUP_JINJA2` and `COMPUTED_ATTRIBUTE_SETUP_PYTHON` actions in `backend/infrahub/computed_attribute/triggers.py`
- [X] T012 Add `changed_elements: ChangedElementsPayload | None = None` parameter to `computed_attribute_setup_jinja2` and `computed_attribute_setup_python` in `backend/infrahub/computed_attribute/tasks.py` and parse it into a `ChangedElementSet` (no scoping wired yet — behavior unchanged this phase)

**Checkpoint**: Changed-element set flows end-to-end into the setup flows (incl. the merge path); the scoper is unit-tested in isolation. User stories can now begin.

---

## Phase 3: User Story 1 - Unrelated schema change does not recompute everything (Priority: P1) 🎯 MVP

**Goal**: A schema change touching a model none of the computed attributes read produces zero recompute jobs for those attributes (Jinja2 path), and recompute work scales with the number of impacted attributes.

**Independent Test**: On a branch with several Jinja2 computed attributes, apply a schema change to an unrelated model; verify zero `process_jinja2` jobs are submitted, and that the submitted-job count does not grow with the number of unrelated attributes.

### Tests for User Story 1 ⚠️ (write first, confirm they fail)

- [X] T013 [P] [US1] Unit test that `Jinja2DependencyDeriver.derive()` produces a `DependencySet` excluding unrelated kinds/fields (local-only attribute) in `backend/tests/unit/computed_attribute/test_jinja2_deriver.py`
- [X] T014 [P] [US1] Component test that `computed_attribute_setup_jinja2` submits no recompute jobs when the change touches an unrelated kind, in `backend/tests/component/computed_attribute/test_scoped_recompute_jinja2.py` (reuse `schema_with_jinja2`)

### Implementation for User Story 1

- [X] T015 [US1] Implement `Jinja2DependencyDeriver.derive()` using `Jinja2ComputedRegistry` `local_fields` (owner kind + locally-read fields, always include the attribute's own `(owner_kind, attribute_name)`) in `backend/infrahub/computed_attribute/scoping.py`
- [X] T016 [US1] Wire `RecomputeScoper` into `computed_attribute_setup_jinja2`: build `candidate_attributes` from gathered triggers, call `scope(...)`, and submit `TRIGGER_UPDATE_JINJA_COMPUTED_ATTRIBUTES` only for `report.selected`, in `backend/infrahub/computed_attribute/tasks.py`
- [X] T017 [US1] Add info-level summary log (count + selected identities) and debug-level skipped-with-reason log in `computed_attribute_setup_jinja2` in `backend/infrahub/computed_attribute/tasks.py`
- [X] T018 [US1] Integration test: applying an unrelated schema change submits zero `process_jinja2` jobs / leaves values unchanged, in `backend/tests/integration_docker/test_computed_attributes.py` (`test_jinja2_scoped_recompute_on_read_field_change` unrelated branch)
- [ ] T019 [US1] Integration test (scaling, SC-003): on a branch with many unrelated Jinja2 computed attributes, changing one read field submits jobs only for the impacted attribute and the job count is independent of the total attribute count, in `backend/tests/integration_docker/test_computed_attributes.py`

**Checkpoint**: MVP delivered — unrelated schema changes no longer fan out Jinja2 recompute (SC-001), and recompute scales with impact (SC-003).

---

## Phase 4: User Story 2 - Recompute when a depended-on field changes, including across relationships (Priority: P1)

**Goal**: A Jinja2 computed attribute is recomputed when the schema change affects any field/type it reads — locally, across a relationship at any depth, on its own definition, on an added/removed type, or (conservatively) on a related type whose display label it reads — without broadening recompute across branches.

**Independent Test**: Define an attribute reading a field on a related type (including multi-hop); apply a schema change to that related field; verify the attribute is recomputed. Apply an unrelated change; verify it is not. Apply a change on another branch; verify this branch is untouched.

### Tests for User Story 2 ⚠️ (write first, confirm they fail)

- [X] T020 [P] [US2] Unit tests that `Jinja2DependencyDeriver` includes relationship-reached peer kinds/fields at the depth the registry exposes, sets `depends_on_everything` for a related type read via display-label/hfid, and sets `depends_on_everything` when traversal depth/precision cannot be determined, in `backend/tests/unit/computed_attribute/test_jinja2_deriver.py`
- [X] T021 [P] [US2] Component tests for the four acceptance scenarios (relationship-field change recomputes; own-definition edit recomputes; related-type add/remove recomputes; `changed_elements=None` → full recompute fallback) in `backend/tests/component/computed_attribute/test_scoped_recompute_jinja2.py`

### Implementation for User Story 2

- [X] T022 [US2] Extend `Jinja2DependencyDeriver.derive()` to include `relationship_dependencies` (peer kinds + peer fields reached through relationships, following the chain to whatever depth the registry exposes), to set `depends_on_everything=True` when the value reads a related object's display label / hfid, and to set `depends_on_everything=True` when depth/precision cannot be determined, in `backend/infrahub/computed_attribute/scoping.py`
- [X] T023 [US2] Confirm/extend the scoper's handling of related-type add/remove and relationship-peer add/remove so a newly-added or removed peer kind selects the dependent attribute, in `backend/infrahub/computed_attribute/scoping.py`
- [X] T024 [US2] Integration test: a schema change to a field reached across a relationship recomputes the dependent attribute, while an unrelated change still skips it, in `backend/tests/integration_docker/test_computed_attributes.py` (`test_jinja2_scoped_recompute_on_read_field_change`; single-hop via the color relationship — multi-hop not yet asserted)
- [X] T025 [US2] Integration test (branch isolation, FR-010, Principle II — MANDATORY): a schema change on an isolated branch recomputes only that branch's attributes and leaves the default branch untouched, in `backend/tests/integration_docker/test_computed_attributes.py` (`test_branch_isolation_scopes_recompute_to_changed_branch`)

**Checkpoint**: Correctness preserved for Jinja2 attributes — no stale values when a depended-on element changes at any depth (SC-004); unrelated changes still skipped (SC-002); no cross-branch broadening (FR-010).

---

## Phase 5: User Story 3 - Template-based and transform-based attributes scoped consistently (Priority: P2)

**Goal**: Transform-based (Python) computed attributes are scoped by parsing their GraphQL query at full depth, so scoping behaves consistently across both kinds; a migration changing a field a template/transform reads (without changing the definition) recomputes the attribute, and unrelated changes do not. A single unanalyzable query recomputes only its own attribute (no branch-wide escalation).

**Independent Test**: Define a transform-based attribute whose query reads field X (and a template-based one reading field X). Apply a migration changing X but not the definition; verify both recompute. Apply a change touching only unread fields; verify neither recomputes. Add an unanalyzable transform query; verify it recomputes always while others stay scoped.

### Tests for User Story 3 ⚠️ (write first, confirm they fail)

- [X] T026 [P] [US3] Unit tests that `PythonTransformDependencyDeriver` parses a transform GraphQL query into read kinds/fields at full depth, returns `depends_on_everything` when the query is unanalyzable, and treats `display_label`/`hfid` reads conservatively, in `backend/tests/unit/computed_attribute/test_python_transform_deriver.py`
- [X] T027 [P] [US3] Component test that `computed_attribute_setup_python` selects only impacted transform attributes and skips unrelated ones, in `backend/tests/component/computed_attribute/test_scoped_recompute_python.py`

### Implementation for User Story 3

- [X] T028 [US3] Add transform-query dependency extraction (read kinds/attributes/relationships, at full traversal depth) using the SDK `GraphQLQueryAnalyzer` / `GraphQLQueryReport.requested_read` to `PythonTransformRegistry` in `backend/infrahub/core/schema/schema_branch_computed/python_transform.py`
- [X] T029 [US3] Implement `PythonTransformDependencyDeriver.derive()` with conservative fallbacks (unanalyzable query → `depends_on_everything`; `display_label`/`hfid` → depend on related type) in `backend/infrahub/computed_attribute/scoping.py`
- [X] T030 [US3] Wire `RecomputeScoper` (Python deriver) into `computed_attribute_setup_python` — submit `TRIGGER_UPDATE_PYTHON_COMPUTED_ATTRIBUTES` only for `report.selected`, plus info summary / debug skipped logging, in `backend/infrahub/computed_attribute/tasks.py`
- [ ] T031 [US3] Add a transform-based computed-attribute test schema/fixture (mirroring the `tshirt.py` pattern) in `backend/tests/helpers/schema/` for use by component and integration tests
- [X] T032 [US3] Integration test: a migration changing a field a template reads recomputes the template-based attribute, a transform-based attribute is scoped consistently, and an unrelated change skips both, in `backend/tests/integration_docker/test_computed_attributes.py` (`test_jinja2_scoped_recompute_on_read_field_change` + `test_python_scoped_recompute_on_read_field_change`)
- [X] T033 [US3] Test (FR-013 non-escalation, Scenario K): an unanalyzable transform attribute (`depends_on_everything`) is recomputed on an unrelated change while a normally-scoped attribute on the same branch is skipped and `fallback_full_recompute is False`, in `backend/tests/component/computed_attribute/test_scoped_recompute_python.py`

**Checkpoint**: Scoping is consistent across both computed-attribute kinds (FR-009); one opaque query does not disable scoping for the branch (FR-013); all three stories independently functional.

---

## Phase 6: Polish & Cross-Cutting Concerns

**Purpose**: Mandatory cross-cutting branch-safety/regression tests (Principle II), documentation, changelog, and final verification across all stories.

- [X] T034 [P] Integration test (merge/rebase path, Principle II — MANDATORY): merge/rebase emit `BranchMergedEvent`/`BranchRebasedEvent` plus node events, not `SchemaUpdatedEvent`, so this feature's schema-scoped recompute does not run on merge (unchanged from before the feature; merged data changes recompute via the data-change path). Characterization test asserts merging a branch schema change does not trigger schema-scoped recompute on the default branch, in `backend/tests/integration_docker/test_computed_attributes.py` (`test_merge_does_not_trigger_schema_scoped_recompute`)
- [ ] T035 [P] Integration test (branch-deletion fallback, FR-008/SC-005): a `BranchDeletedEvent` triggers full recompute with behavior identical to pre-change (no regression), in `backend/tests/integration_docker/test_computed_attributes.py`
- [ ] T036 [P] Document the scoped-recompute model and add Python-transform coverage in `dev/knowledge/backend/computed-attributes.md` (dependency set, changed-element set, full-depth + conservative fallback, per-attribute vs path-level fallback, observability)
- [X] T037 [P] Add a Towncrier changelog fragment `changelog/9415.fixed.md` describing the defect fix (no source-code IDs per `dev/rules/code-doc-style.md`)
- [ ] T038 Run `uv run invoke format` and `uv run invoke lint` (ruff + mypy) and fix any violations in the touched files (`backend/infrahub/computed_attribute/`, `backend/infrahub/events/schema_action.py`, `backend/infrahub/core/schema/schema_branch_computed/python_transform.py`)
- [ ] T039 Run quickstart.md validation (`uv run pytest backend/tests/unit/computed_attribute/`, `backend/tests/component/computed_attribute/`, then `uv run invoke backend.test-integration`) and confirm SC-001 through SC-006 plus Scenarios H, J, K, L

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies — start immediately.
- **Foundational (Phase 2)**: Depends on Setup. **BLOCKS all user stories** (changed-element plumbing incl. merge path + scoper).
- **User Stories (Phase 3–5)**: All depend on Foundational completion.
  - US1 (P1) is the MVP and should be completed first.
  - US2 (P1) extends the Jinja2 deriver file from US1; complete after US1.
  - US3 (P2) adds the independent Python-transform path; can proceed in parallel with US2 once Foundational is done (different files: `python_transform.py` + `setup_python`).
- **Polish (Phase 6)**: Depends on all targeted user stories. T034/T035 are mandatory completion gates (Principle II / no-regression), not optional.

### User Story Dependencies

- **US1 (P1)**: Foundational only. No dependency on other stories. Independently testable.
- **US2 (P1)**: Builds on US1's `Jinja2DependencyDeriver` (same file) but adds distinct relationship/conservative behavior with its own tests. Independently testable.
- **US3 (P2)**: Foundational only. Touches the Python-transform path (`python_transform.py`, `computed_attribute_setup_python`), disjoint from US1/US2's Jinja2 path. Independently testable and parallelizable with US2.

### Within Each User Story

- Tests written first and confirmed failing before implementation.
- Deriver logic (`scoping.py` / `python_transform.py`) before setup-flow wiring (`tasks.py`).
- Setup-flow wiring before integration tests.
- Note: integration tests share `backend/tests/integration_docker/test_computed_attributes.py`, so they are sequential with each other (not mutually `[P]`).

### Parallel Opportunities

- Setup: T002 and T003 in parallel (different files).
- Foundational: T009 (unit test) parallel with the emission/threading work once the scoper types exist.
- US1 tests T013/T014 in parallel; US2 tests T020/T021 in parallel; US3 tests T026/T027 in parallel.
- US3 (Python path) can run in parallel with US2 (Jinja2 path) — different files.
- Polish: T034, T035, T036, T037 touch different files (note T034/T035 share the integration file, so those two are sequential with each other but parallel with T036/T037).

---

## Parallel Example: User Story 1

```bash
# Launch US1 tests together (write first, expect failure):
Task: "Unit test Jinja2DependencyDeriver excludes unrelated kinds in backend/tests/unit/computed_attribute/test_jinja2_deriver.py"
Task: "Component test setup_jinja2 submits no jobs for unrelated change in backend/tests/component/computed_attribute/test_scoped_recompute_jinja2.py"
```

## Parallel Example: US2 and US3 after Foundational

```bash
# Different files / paths — safe to run concurrently:
Task: "US2: extend Jinja2DependencyDeriver for relationships (full depth) in backend/infrahub/computed_attribute/scoping.py"
Task: "US3: add transform-query dependency extraction in backend/infrahub/core/schema/schema_branch_computed/python_transform.py"
```

---

## Implementation Strategy

### MVP First (User Story 1 only)

1. Phase 1: Setup.
2. Phase 2: Foundational (changed-element plumbing + scoper) — **blocks everything**.
3. Phase 3: US1 — Jinja2 scoping that skips unrelated changes and scales with impact.
4. **STOP and VALIDATE**: unrelated schema change produces zero Jinja2 recompute jobs (SC-001); job count independent of total attributes (SC-003).
5. Ship the MVP — the headline defect (full fan-out on any schema change) is fixed for the Jinja2 path.

### Incremental Delivery

1. Setup + Foundational → plumbing ready.
2. US1 → unrelated changes skipped + scaling (MVP). Validate & demo.
3. US2 → correctness across relationships (any depth) / definition edits / type changes / display-label / branch isolation. Validate & demo.
4. US3 → transform-based path scoped consistently + template-migration coverage + FR-013 non-escalation. Validate & demo.
5. Polish → mandatory branch-safety/merge/branch-deletion tests, docs, changelog, lint/type, full quickstart run.

### Parallel Team Strategy

After Foundational completes: one developer takes US1→US2 (Jinja2 path, `scoping.py` + `setup_jinja2`), another takes US3 (Python path, `python_transform.py` + `setup_python`). The two paths touch disjoint files and integrate through the shared scoper. Reserve the integration-test file for sequential edits.

---

## Notes

- [P] = different files, no dependency on an incomplete task.
- [Story] label maps each task to a user story for traceability; Setup/Foundational/Polish carry no story label.
- Source code MUST NOT carry spec IDs (FR-xxx, T0xx) or cross-references to other code per `dev/rules/code-doc-style.md` — those belong here and in commit/PR messages.
- New components follow constructor-injection / single-entry-point design per `dev/rules/backend-component-design.md`.
- Recompute stays asynchronous; per-object flows (`process_jinja2`, `process_transform`) are unchanged.
- T025 (branch isolation) and T034 (merge/rebase) are mandatory under Constitution Principle II.
- Commit after each task or logical group; stop at any checkpoint to validate a story independently.
