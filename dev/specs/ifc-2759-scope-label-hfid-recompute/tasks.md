---
description: "Task list for: Scope display label and HFID recompute on schema updates"
---

# Tasks: Scope display label and HFID recompute on schema updates

**Input**: Design documents from `specs/ifc-2759-scope-label-hfid-recompute/`
**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/recompute-scoping.md, quickstart.md

**Tests**: Included — the spec and the project constitution (Principle IV) require unit + component + integration coverage.

**Branch**: `scope-label-hfid-recompute-ifc-2759`

## Story → delivery mapping

The spec's user stories are behavioral (US1 skip-unrelated, US2 recompute-related, US3 fallback). They are **not** independently shippable: shipping US1 without US2 would skip needed recomputes (unsafe). The safe, independently-shippable increments are by subsystem — display-label scoping, then HFID scoping — each delivering US1 + US2 + US3 together. Phases below follow those increments; tasks carry the `[US#]` they primarily serve.

- **US1** (P1) — unrelated change → zero recompute (FR-001/002, SC-001)
- **US2** (P1) — read element / definition change → still recompute (FR-003/004/005, SC-003)
- **US3** (P2) — no change set → full fallback unchanged (FR-006, SC-005)

## Conventions

- Per `dev/rules/code-doc-style.md`: **no spec IDs (IFC-2759, FR-xxx) in source or test names or docstrings.** They live here and in the commit/PR only. (Changelog filename may use the bare issue number per project convention.)
- All Python calls use keyword arguments; type hints on all new code; frozen dataclasses for internal data (Constitution III). New components use required constructor injection (`dev/rules/backend-component-design.md`).
- `[P]` = parallelizable (different files, no incomplete dependency).

---

## Phase 1: Setup (baseline guard)

**Purpose**: Capture the green baseline that the Phase 2 refactor must preserve.

- [ ] T001 Run and record green baseline for the regression + fallback guards: `uv run pytest backend/tests/unit/computed_attribute/test_scoping.py backend/tests/component/computed_attribute backend/tests/functional/display_labels/test_display_label_task_optimization.py backend/tests/functional/hfid/test_hfid_task_optimization.py -q`. These must stay green through Phase 2.

---

## Phase 2: Foundational — extract & generalize the shared scoping core (BLOCKING)

**Purpose**: Move the scoping core to `core/schema/` and generalize it over a candidate type, behavior-preserving. **Blocks all subsystem work.**

**⚠️ CRITICAL**: No display-label or HFID task may begin until this phase is complete and the Phase 1 guards are still green.

- [ ] T002 Create `backend/infrahub/core/schema/recompute_scoping.py` and move `ChangedElementSet`, `DependencySet`, `RecomputeScopingReport`, `SkippedCandidate` (renamed from `SkippedAttribute`), `RecomputeScoper`, and `_resolve_changed_elements` from `backend/infrahub/computed_attribute/scoping.py`; relocate `IMPRECISE_READ_FIELDS` from `backend/infrahub/core/schema/schema_branch_computed/python_transform.py` into this module.
- [ ] T003 In `recompute_scoping.py`, add the generic `RecomputeCandidate` frozen dataclass (`branch`, `kind`, `name`, `deriver_key`) and the generalized `DependencyDeriver` Protocol (`derive(*, candidate) -> DependencySet`); generalize `DependencySet` (`attribute_name` → `name`; drop the computed-attribute `kind` enum field) per `data-model.md`.
- [ ] T004 In `recompute_scoping.py`, generalize `RecomputeScoper.__init__(*, derivers: Mapping[str, DependencyDeriver])` and `scope(*, candidates: Sequence[RecomputeCandidate], changed_elements: ChangedElementSet | None)`, preserving the decision logic (own-field, read_fields∩changed_fields, read_kinds∩added/removed, depends_on_everything, None→fallback) exactly per `contracts/recompute-scoping.md` §2.
- [ ] T005 Add `DerivedFieldLookup` frozen dataclass (`computed_attributes: frozenset[tuple[str,str]]`, `imprecise_read_fields=IMPRECISE_READ_FIELDS`, `is_derived(*, kind, field)`) in `recompute_scoping.py`.
- [ ] T006 Update `backend/infrahub/computed_attribute/scoping.py`: keep `Jinja2DependencyDeriver` and `PythonTransformDependencyDeriver`, import moved types from `core.schema.recompute_scoping`, adapt `ComputedAttributeRef` to satisfy the `RecomputeCandidate` shape (expose `name` and `deriver_key`), and key its derivers by the `computed_attribute.jinja2` / `computed_attribute.python` strings.
- [ ] T007 [P] Update `backend/infrahub/computed_attribute/tasks.py` and `backend/infrahub/computed_attribute/triggers.py` to the generalized scoper API and import paths (behavior-preserving; no change to submitted workflows).
- [ ] T008 [P] Update `backend/infrahub/core/schema/schema_branch_computed/python_transform.py` to import `IMPRECISE_READ_FIELDS` from `core.schema.recompute_scoping` (re-export there if any other module imports it from the old location).
- [ ] T009 Update `backend/tests/unit/computed_attribute/test_scoping.py` to the new import paths and candidate shape; assertions unchanged. Confirm it passes (regression guard).
- [ ] T010 Relocate `ScopedRecomputeTestBase` from `backend/tests/component/computed_attribute/_base.py` to a shared location (e.g. `backend/tests/component/recompute/_base.py`), generalize its submission helper to take the workflow + parameter key (today it hard-codes `computed_attribute_name`; display labels and HFID submit on `kind`), update the computed-attribute component tests' import, and confirm they stay green — so the display-label and HFID component tests reuse it without a cross-test-package import.
- [ ] T011 Run the Phase 1 guard command again; confirm computed-attribute unit + component scoping tests and the task-optimization tests are still green (behavior-preserving checkpoint).

**Checkpoint**: Shared scoping core lives in `core/schema/`, generalized, with all pre-existing computed-attribute behavior intact, and a shared component test base ready for both subsystems.

---

## Phase 3: Display-label scoping (Priority: P1) 🎯 MVP

**Goal**: A schema update recomputes a kind's display label only when the change touches an element that display label reads (or its own definition, or a derived read).

**Independent Test**: Apply an unrelated schema change → zero `TRIGGER_UPDATE_DISPLAY_LABELS` submissions; change a read field (incl. across a relationship) or the `display_labels` definition → the affected kind is submitted; invoke with no change set → every candidate submitted (fallback).

**Covers**: US1, US2, US3 for display labels.

### Tests (write first, ensure they fail)

- [ ] T012 [P] [US2] Unit tests in `backend/tests/unit/display_labels/test_scoping.py` for the display-label deriver + scoper: select via own definition (`display_labels` token present in `changed_fields`), via owner attribute, via relationship peer field, via added/removed peer kind; skip on no overlap; `depends_on_everything` when a read resolves to a derived value (peer `display_label`/`hfid` or a computed attribute); empty change set → skip; **independence — for a kind with both a display label and an HFID, a change touching only the HFID's dependency does not select the display-label candidate.**
- [ ] T013 [P] [US1] Component test in `backend/tests/component/display_labels/test_scoped_recompute.py` reusing the shared `ScopedRecomputeTestBase` + `WorkflowRecorder` (`WORKFLOW = TRIGGER_UPDATE_DISPLAY_LABELS`): assert the set of submitted kinds for unrelated-change (empty), owner-field change, relationship-peer change, and `changed_elements=None` (all candidates).

### Implementation

- [ ] T014 [US2] Build the per-branch `DerivedFieldLookup` + relationship peer-kind resolution helper from the active `SchemaBranch` (computed-attribute `(kind, attr)` set + peer-kind map), as a factory in `core/schema/recompute_scoping.py`. Serves both subsystems.
- [ ] T015 [US1] Create `backend/infrahub/display_labels/scoping.py`: `DisplayLabelDependencyDeriver` mapping `TemplateLabel` → `DependencySet` (own `display_labels` token in `read_fields[owner_kind]`; attributes; relationships + `relationship_fields` peer reads with peer-kind resolution; `depends_on_everything` via `DerivedFieldLookup`), plus a candidate builder from `DisplayLabels.get_template_nodes()`.
- [ ] T016 [US2] Add the `changed_elements` Prefect parameter to `TRIGGER_DISPLAY_LABELS_ALL_SCHEMA` in `backend/infrahub/display_labels/triggers.py`, mirroring `TRIGGER_COMPUTED_ATTRIBUTE_ALL_SCHEMA` (contracts §5).
- [ ] T017 [US2] In `backend/infrahub/display_labels/tasks.py`, add `changed_elements: ChangedElementsPayload | None = None` to `display_labels_setup_jinja2`, normalize via `_resolve_changed_elements`, build candidates + deriver, call `RecomputeScoper.scope(...)`, and gate the existing per-kind hash check + node sweep on `report.selected`.
- [ ] T018 [US1] Add the scoping observability log to `display_labels_setup_jinja2` (info: selected count, total candidate count, `fallback_full_recompute`; debug: skipped + reasons).
- [ ] T019 [US1] Run T012 + T013 green; run the display-label task-optimization fallback test to confirm the `None` path is unchanged.

**Checkpoint**: Display-label scoping works end-to-end — MVP shippable on its own.

---

## Phase 4: HFID scoping (Priority: P1)

**Goal**: Same scoping for HFIDs, including the divergence case where an HFID path component resolves to a computed attribute.

**Independent Test**: As Phase 3 but for `TRIGGER_UPDATE_HFID` and the `human_friendly_id` definition token; plus an HFID reading a computed attribute → always recomputes.

**Covers**: US1, US2, US3 for HFIDs.

### Tests (write first, ensure they fail)

- [ ] T020 [P] [US2] Unit tests in `backend/tests/unit/hfid/test_scoping.py` for the HFID deriver + scoper: select via own definition (`human_friendly_id` token), owner attribute, relationship peer field, added/removed kind; skip on no overlap; **`depends_on_everything` when an HFID path component resolves to a computed attribute or a peer `display_label`/`hfid`** (the documented divergence); empty change set → skip; **independence — for a kind with both an HFID and a display label, a change touching only the display label's dependency does not select the HFID candidate.**
- [ ] T021 [P] [US1] Component test in `backend/tests/component/hfid/test_scoped_recompute.py` reusing the shared `ScopedRecomputeTestBase` (`WORKFLOW = TRIGGER_UPDATE_HFID`): submitted-kind assertions for unrelated, owner-field, relationship-peer, and `None` (fallback) cases.

### Implementation

- [ ] T022 [US1] Create `backend/infrahub/hfid/scoping.py`: `HFIDDependencyDeriver` mapping `HFIDDefinition` → `DependencySet` (own `human_friendly_id` token; attributes; `relationship_fields` peer reads; `depends_on_everything` via `DerivedFieldLookup`, which here must catch reads of computed attributes, not just `display_label`/`hfid`), plus a candidate builder from `HFIDs.get_template_nodes()`.
- [ ] T023 [US2] Add the `changed_elements` Prefect parameter to `TRIGGER_HFID_ALL_SCHEMA` in `backend/infrahub/hfid/triggers.py`.
- [ ] T024 [US2] In `backend/infrahub/hfid/tasks.py`, add `changed_elements: ChangedElementsPayload | None = None` to `hfid_setup`, normalize, build candidates + deriver, call `RecomputeScoper.scope(...)`, and gate the existing per-kind hash check + node sweep on `report.selected`.
- [ ] T025 [US1] Add the scoping observability log to `hfid_setup` (same shape as T018).
- [ ] T026 [US1] Run T020 + T021 green; run the HFID task-optimization fallback test to confirm the `None` path is unchanged.

**Checkpoint**: Both display-label and HFID scoping work independently.

---

## Phase 5: Polish & cross-cutting concerns

- [ ] T027 [P] [US3] Confirm fallback equivalence: `backend/tests/functional/display_labels/test_display_label_task_optimization.py` and `backend/tests/functional/hfid/test_hfid_task_optimization.py` pass unchanged (no edits) — the mandatory fallback guard (Constitution II).
- [ ] T028 Add a no-cross-branch-broadening assertion (component) for both subsystems: a schema change on one branch submits no recompute for kinds on other branches (mandatory, Constitution II).
- [ ] T029 Add an `integration_docker` test asserting end-to-end that a scoped schema change refreshes only the affected kinds' display labels/HFIDs and leaves unaffected kinds untouched (mandatory for triggered-action paths, Constitution IV).
- [ ] T030 Update `dev/knowledge/backend/display-labels-and-hfid.md` to document that display-label and HFID recompute on schema updates is now scoped to changed elements (same dependency-intersection mechanism as computed attributes, with the conservative derived-read fallback) — Constitution Documentation Requirements (backend architecture change).
- [ ] T031 [P] Add a Towncrier changelog fragment for the change. Use the GitHub issue/PR number as the filename per project convention (e.g. `changelog/<gh-issue>.fixed.md`); if no GitHub issue exists, use a slug (`changelog/+scope-label-hfid-recompute.fixed.md`). Do **not** use the Jira `2759` number. No em dashes / code-overquoting in the text.
- [ ] T032 [P] Run `uv run invoke format` and `uv run invoke lint`; resolve `mypy` on all changed/new files.
- [ ] T033 Run `/pre-ci` (`dev/commands/pre-ci.md`) — the locally-executable CI gates including generated-file/doc validation (`docs.validate`).
- [ ] T034 Execute the `quickstart.md` validation scenarios A–J and confirm each passes.

---

## Dependencies & Execution Order

### Phase dependencies

- **Phase 1 (Setup)**: immediate.
- **Phase 2 (Foundational)**: after Phase 1; **blocks Phases 3 & 4**.
- **Phase 3 (Display label)**: after Phase 2. Independently shippable (MVP).
- **Phase 4 (HFID)**: after Phase 2. Independent of Phase 3 (different packages/files) — can run in parallel with Phase 3 once foundation lands.
- **Phase 5 (Polish)**: after Phases 3 & 4.

### Within a subsystem phase

- Tests (T012/T013, T020/T021) written first and failing → implementation → green.
- The deriver (T015/T022) depends on the shared `DerivedFieldLookup` + peer-kind helper (T014). The trigger param (T016/T023) and the setup-flow wiring (T017/T024) are paired.

### Parallel opportunities

- T007, T008 in Phase 2 are `[P]` (different files) once T002–T006 land.
- Once Phase 2 completes, **Phase 3 and Phase 4 can be developed in parallel** (display_labels/* vs hfid/* are disjoint), except both depend on T014.
- Test-authoring tasks within a phase (`[P]`) can be written together.
- Polish tasks T031, T032 are `[P]`.

---

## Parallel Example: after foundation lands

```bash
# Developer A — display-label increment (Phase 3)
Task: "Unit tests for display-label deriver in backend/tests/unit/display_labels/test_scoping.py"
Task: "Component scoped-recompute test in backend/tests/component/display_labels/test_scoped_recompute.py"

# Developer B — HFID increment (Phase 4)
Task: "Unit tests for HFID deriver in backend/tests/unit/hfid/test_scoping.py"
Task: "Component scoped-recompute test in backend/tests/component/hfid/test_scoped_recompute.py"
```

---

## Implementation Strategy

### MVP first

1. Phase 1 (baseline) → Phase 2 (foundation, behavior-preserving) → **STOP & VALIDATE**: all existing computed-attribute tests green.
2. Phase 3 (display-label scoping) → validate independently → shippable MVP.
3. Phase 4 (HFID scoping) → validate independently.
4. Phase 5 (cross-cutting tests, docs, changelog, pre-ci) → ship.

### Risk notes

- **Phase 2 is the riskiest mechanical step** — keep it a single behavior-preserving commit; the Phase 1 guard is the safety net.
- **T022 (HFID derived-read detection)** is the only genuinely new logic vs. the computed-attribute path and the documented split point if it proves harder than display labels.
- Confirm (research open item) how each registry resolves a relationship name → peer kind during T014/T015/T022.

---

## Notes

- `[Story]` labels map tasks to spec user stories for traceability only; the shippable increments are the subsystem phases.
- Commit after each task or logical group; do not force-push the branch.
- Verify each test fails before implementing it.
- No edits to generated files; no new external dependencies.
