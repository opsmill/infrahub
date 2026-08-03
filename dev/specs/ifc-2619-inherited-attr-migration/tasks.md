# Tasks: Inherited-Attribute Migration Fix and Healing Migration

**Input**: Design documents from `dev/specs/ifc-2619-inherited-attr-migration/`

**Prerequisites**: plan.md (post-critique), spec.md, research.md, data-model.md, quickstart.md

**Tests**: Included — the spec's Testing Decisions explicitly define the test suites, and Constitution IV mandates test-first/alongside development. Component tests run against the local test DB (`uv run pytest -x -v backend/tests/component/...`); write tests first and watch them fail before implementing.

**Organization**: Tasks are grouped by user story. US1 = PR 1 (forward fix). US2 + US3 = PR 2 (healing migration) — US2/US3 depend on US1's machinery by design (research R11); this cross-story dependency is intentional and mirrors the two-PR packaging.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: US1 (forward fix), US2 (healing, default branch), US3 (healing, branch-side)

## Phase 1: Setup

**Purpose**: Confirm a green baseline so regressions introduced by the two-phase batching change are attributable.

- [x] T001 Run the existing migration component suite and branch-merge suite green before any change: `uv run pytest -x backend/tests/component/core/migrations/schema/ backend/tests/component/core/test_branch_merge.py`; record the baseline result in the PR description draft
  - Baseline recorded 2026-07-31: 56 passed in 2m14s (local dev DB container). Post-implementation rerun: 62 passed (56 baseline + 6 new component tests).

## Phase 2: Foundational

No foundational phase: the feature modifies existing migration infrastructure, and every prerequisite (migration framework, query layer, test harnesses) already exists. US1 itself is the foundation that US2/US3 reuse.

---

## Phase 3: User Story 1 — Forward fix: new inheritance creates attribute rows (Priority: P1) 🎯 MVP — PR 1

**Goal**: Loading a schema where a kind newly inherits a generic creates real attribute rows on all pre-existing nodes (incl. profile/template instances, NumberPool allocation), and schema-migration execution is two-phase and race-free.

**Independent Test**: Load schema v1 → create nodes → load v2 adding `inherit_from` → read returns non-null `id`, update persists with `is_default: false`, filter matches. Runs entirely without the healing migration (quickstart.md §PR 1).

### Tests for User Story 1 (write first, watch fail)

- [x] T002 [P] [US1] Unit tests for `split_migrations_by_phase` (pure, no DB) in `backend/tests/unit/core/migrations/schema/test_tasks.py`: kind-update-backed names (`node.inherit_from.update`, `node.name.update`, `node.namespace.update`, derived from `MIGRATION_MAP` — not hard-coded in the test either), mixed batches, empty input, all-phase-1, all-phase-2
- [x] T003 [P] [US1] Component tests for the guard/bypass in `backend/tests/component/core/migrations/schema/test_node_attribute_add.py`: `force_inherited=True` executes for an inherited attribute; default `False` still returns an empty `MigrationResult` (protects #7407, FR-002)
- [x] T004 [P] [US1] Component tests in `backend/tests/component/core/migrations/schema/test_node_kind_update.py`: (a) previous schema without `inherit_from` → new schema inheriting a generic with a default-backed Dropdown: every duplicated node gets an `Attribute` vertex with the generic's default and `NodeManager` reads a non-null `id`; (b) pre-existing `Profile{kind}` and `Template{kind}` instances get the row; (c) `unique`/`read_only` inherited attribute lands on nodes but NOT profile/template vertices (support-predicate gating); (d) NumberPool attribute: each node gets a distinct allocated number and exactly one `CoreNumberPool` exists, registered against the generic's kind (FR-004); (e) name-update-only migration creates no attributes; (f) partial-failure rerun converges (rerun of a partially-completed kind-update produces the complete state with no duplicates — critique E3)
- [x] T005 [P] [US1] Integration test `backend/tests/integration/schema_lifecycle/test_schema_add_inherited_generic.py` following the `test_schema_attribute_remove_add.py` shape: load v1 → create object → load v2 adding generic + `inherit_from` → assert non-null `id`, update persists across re-read with `is_default: false`, attribute-value filter matches (SC-002 fresh-install half)

### Implementation for User Story 1

- [x] T006 [US1] Add `force_inherited: bool = False` field to `NodeAttributeAddMigration` in `backend/infrahub/core/migrations/schema/node_attribute_add.py`; change the guard to `if self.new_attribute_schema.inherited is True and not self.force_inherited: return MigrationResult()`; nothing in `backend/infrahub/core/models.py` changes
- [x] T007 [US1] Override `execute()` in `backend/infrahub/core/migrations/schema/node_kind_update.py` (do NOT hook `execute_post_queries` — nested-transaction failure, research R2): `super().execute()` first, bail on errors, then per attribute from `_newly_inherited_attributes()` (new-minus-previous attribute names, filtered to `inherited`, sorted — research R3) run `NodeAttributeAddMigration(force_inherited=True, ...)` with a `SchemaPath(path_type=ATTRIBUTE, schema_kind=new_schema.kind, field_name=...)`; accumulate errors and `nbr_migrations_executed`, stop on first error (depends on T006)
- [x] T008 [US1] Two-phase batching in `backend/infrahub/core/migrations/schema/tasks.py`: pure `split_migrations_by_phase(migrations) -> tuple[list, list]` (phase 1 = migrations whose `MIGRATION_MAP` entry is `NodeKindUpdateMigration`, derived from the map); extract the per-migration loop body into a helper that builds/executes one `InfrahubBatch`; `schema_apply_migrations` runs phase 1 to completion, skips phase 2 when phase 1 reported errors (FR-003, FR-012)
- [x] T009 [US1] Regression gates: run `backend/tests/component/core/migrations/schema/test_all_migrations_rollback.py` and `backend/tests/component/core/test_branch_merge.py` unchanged and green; run the full `backend/tests/component/core/migrations/schema/` suite
- [x] T010 [US1] Add towncrier fragment `changelog/9284.fixed.md`: attributes gained via new generic inheritance now materialize on pre-existing nodes (incl. profiles/templates, NumberPool allocation); schema migrations now run kind-updates before other migrations
- [x] T011 [US1] PR 1 gate: `uv run invoke format && uv run invoke lint`, then `/pre-ci`; quickstart.md §PR 1 manual verification against the dev stack with the two #9284 schema files

**Checkpoint**: US1 fully functional and testable on its own — fresh installs can never be damaged again. PR 1 opens here (governance flag: database-migration behavior change).

---

## Phase 4: User Story 2 — Healing: upgrade repairs damaged installs on the default branch (Priority: P2) — PR 2

**Goal**: One-shot upgrade-time migration m075 backfills every missing (active node, schema-defined attribute) row on the default branch with retroactively-timestamped default-valued rows (run-time NumberPool allocations), is a strict no-op on healthy data, idempotent, self-validating, and loud on failure.

**Independent Test**: Seed damaged graph state via raw graph writes, run m075, assert every pair has an active row (non-null `id` on read), rerun → zero writes (quickstart.md §PR 2).

**Depends on**: US1 complete (reuses `force_inherited` attribute-add machinery — research R11).

### Verification gate (before implementation)

- [ ] T012 [US2] Verify `CoreNumberPool.get_resource` (`backend/infrahub/core/node/resource_manager/number_pool.py`) uniqueness/reservation checks are correctly branch- and time-scoped for migration-run-time allocation (spec Assumption, FR-007); document the finding in `dev/specs/ifc-2619-inherited-attr-migration/research.md` (append to R10); if scoping is wrong, fix or wrap the allocation path first and add a regression test

### Tests for User Story 2 (write first, watch fail)

- [ ] T013 [P] [US2] Component tests for the detection query in `backend/tests/component/core/migrations/query/test_attribute_heal.py`: (a) detection completeness — seeded missing-row nodes found, healthy nodes not, deleted nodes skipped; (b) tombstone-only counts as damaged; (c) retroactive timestamp = later of "kind began inheriting" and "generic gained attribute", read across same-UUID duplicated schema vertices (kind renamed after gaining inheritance — critique E2); (d) timestamp never predates a tombstone (FR-006); (e) batched per-kind — no per-node round-trips (FR-011)
- [ ] T014 [P] [US2] Component tests for the migration in `backend/tests/component/core/migrations/graph/test_m075_heal_missing_attribute_rows.py` (default-branch scope): damaged default branch fully repaired at schema-default values with retroactive timestamps; mandatory-no-default healed as null-valued row; NumberPool damage healed with run-time allocations, no duplicate pools/allocations; healthy install → zero writes (assert via driver write-counter deltas — critique E5); second run → zero writes (SC-003); self-validation failure path surfaces per-kind actionable errors and fails the migration (FR-010); pre-existing branch (branched after damage) reads healed rows without rebase (SC-004); branch whose `branched_from` predates the damage window correctly sees no attribute (critique P2)

### Implementation for User Story 2

- [ ] T015 [US2] Damage-detection query module `backend/infrahub/core/migrations/query/attribute_heal.py` (the deep module): batched per-kind, parameterized Cypher, returns (node uuid, attribute name, derived retroactive timestamp) per damaged pair; tombstone-only treated as damaged with clamped timestamp; timestamp derivation resolves the edge timeline across the full same-UUID schema-vertex set (data-model.md rule; critique E2); results exposed via frozen-dataclass `get_data()` (Constitution III); review plan with `EXPLAIN` (Constitution V)
- [ ] T016 [US2] Create `backend/infrahub/core/migrations/graph/m075_heal_missing_attribute_rows.py` as `ArbitraryMigration` (`minimum_version: 74`), register it in `backend/infrahub/core/migrations/graph/__init__.py`, bump `GRAPH_VERSION` to 75 in `backend/infrahub/core/graph/__init__.py`; schema acquisition: load default-branch schema from the DB at migration time, pass schema objects (never registry state) to detection (critique E1)
- [ ] T017 [US2] Pass-1 repair in m075: per kind, detect (T015) → repair default-backed attributes via batched row creation at derived retroactive timestamps reusing PR 1's attribute-add machinery/queries with `force_inherited=True`; all repair queries idempotent (FR-005, FR-006, FR-008) (depends on T015, T016)
- [ ] T018 [US2] NumberPool repair in m075: per damaged pool-backed pair (the sanctioned per-node loop, FR-011), allocate at run time via the reservation-aware `CoreNumberPool.get_resource` path — rows carry run-time timestamps, not retroactive ones (FR-007) (depends on T012, T017)
- [ ] T019 [US2] Self-validation + observability in m075: re-run detection across the repaired scope, fail the migration with per-kind actionable errors when any pair remains (FR-010, SC-001); on success log per-kind repaired-row counts (critique P1); zero-count output doubles as the healthy no-op proof
- [ ] T020 [US2] Add towncrier fragment `changelog/+heal-missing-attribute-rows.fixed.md`: upgrading repairs nodes missing attribute rows caused by pre-fix inheritance changes, on the default branch and existing branches, without requiring rebases

**Checkpoint**: default-branch healing complete and independently testable (branch pass not yet wired — US3).

---

## Phase 5: User Story 3 — Healing: branch-side repair (Priority: P3) — PR 2

**Goal**: The same upgrade pass repairs branch-originated damage on all existing branches via branch-scoped detection — no rebase or merge required.

**Independent Test**: Seed a non-default branch where a kind gained inheritance on-branch pre-fix, run m075, assert branch-level rows exist and inherited attributes read back with non-null `id` on the branch.

**Depends on**: US2 (extends the same migration and query module).

### Tests for User Story 3 (write first, watch fail)

- [ ] T021 [P] [US3] Component tests in `backend/tests/component/core/migrations/graph/test_m075_heal_missing_attribute_rows.py` (branch scope): kind gained inheritance on-branch pre-fix → branch-scoped pass creates missing branch-level rows, attribute reads back with non-null `id` on the branch, default branch untouched; branch-scoped detection considers only data changed on the branch (default-branch-inherited visibility cases produce no branch-level writes); branch with no schema changes of its own → schema fallback to default works (empty-schema-branch gotcha, critique E1)

### Implementation for User Story 3

- [ ] T022 [US3] Branch-scoped detection variant in `backend/infrahub/core/migrations/query/attribute_heal.py`: same contract as default-branch detection but filters to branch-level data changes only (FR-009)
- [ ] T023 [US3] Pass-2 branch iteration in m075: iterate existing (non-deleted) branches; per branch, load the branch's own schema from the DB with fallback-to-default semantics when the branch has no schema changes (critique E1); branch-scoped detect → repair at branch level; include per-branch repaired counts in the audit log; self-validation (T019) extends across the branch scope (depends on T022)

**Checkpoint**: all three stories functional; m075 repairs default branch + all branches in one upgrade pass.

---

## Phase 6: Polish & Cross-Cutting Concerns

- [ ] T024 [P] Run quickstart.md end-to-end: automated suites (PR 1 + PR 2 sections) plus the manual damaged-install upgrade walk-through (seed damage on a pre-fix version, upgrade, verify reads/updates/filters on default branch and a pre-existing branch, rerun upgrade → zero writes) — SC-001..SC-004
- [ ] T025 [P] File the two follow-up issues from spec Out of Scope: (1) refactor the migration-within-a-migration pattern shared with `node_uniqueness_constraints_update.py`; (2) stale `Template{generic}` labels on pre-existing template vertices
- [ ] T026 PR 2 gate: `uv run invoke format && uv run invoke lint`, `/pre-ci`; PR 2 description records the governance flag (new numbered graph migration every install executes) and verifies PR 1 is in the same release milestone (critique X1)

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: none — start immediately
- **Foundational (Phase 2)**: n/a (empty by design)
- **US1 (Phase 3)**: after T001. Internally: T002–T005 (tests, parallel) → T006 → T007; T008 independent of T006/T007 (different file) but ordered before T009's full-suite gate; T009 → T010 → T011
- **US2 (Phase 4)**: after US1 complete (reuses its machinery). T012 gates T018. T013/T014 (tests, parallel) → T015 → T016 → T017 → T018 → T019 → T020
- **US3 (Phase 5)**: after US2. T021 → T022 → T023
- **Polish (Phase 6)**: after US3; T024/T025 parallel; T026 last

### Cross-story note

US2/US3 depend on US1 deliberately (two-PR packaging, research R11). US1 alone is the MVP and ships as PR 1; US2+US3 ship together as PR 2 — US3 is not independently deployable without US2 (same migration file), but is independently testable via its branch-scope test cases.

### Parallel Opportunities

- T002, T003, T004, T005 (US1 test authoring — four different files)
- T006 and T008 (different files) once tests exist
- T013 and T014 (US2 test authoring — two different files); T012 can run alongside test authoring
- T024 and T025 (polish)

## Parallel Example: User Story 1

```bash
# Author all US1 test files together (different files, no dependencies):
Task: "Unit tests for split_migrations_by_phase in backend/tests/unit/core/migrations/schema/test_tasks.py"
Task: "Guard/bypass tests in backend/tests/component/core/migrations/schema/test_node_attribute_add.py"
Task: "Kind-update tests in backend/tests/component/core/migrations/schema/test_node_kind_update.py"
Task: "Integration repro in backend/tests/integration/schema_lifecycle/test_schema_add_inherited_generic.py"
```

## Implementation Strategy

**MVP first (US1 = PR 1)**: T001 → US1 tests → T006–T008 → gates T009–T011 → open PR 1. Fresh installs are protected from this point.

**Incremental delivery (PR 2)**: T012 verification gate early (it can invalidate the NumberPool healing design); then US2 (default-branch healing, independently testable) → US3 (branch pass) → polish. PR 2 opens after T026 and must land in the same release as PR 1.

**Stop-and-validate checkpoints**: end of Phase 3 (PR 1 reviewable), end of Phase 4 (healing works on default branch), end of Phase 5 (full branch coverage), T024 (SC-001..004 all demonstrated).
