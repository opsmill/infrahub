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

**Goal**: One-shot upgrade-time migration m076 backfills every missing (active node, schema-defined attribute) row on the default branch with retroactively-timestamped default-valued rows (run-time NumberPool allocations), is a strict no-op on healthy data, idempotent, self-validating, and loud on failure.

**Independent Test**: Seed damaged graph state via raw graph writes, run m076, assert every pair has an active row (non-null `id` on read), rerun → zero writes (quickstart.md §PR 2).

**Depends on**: US1 complete (reuses `force_inherited` attribute-add machinery — research R11).

### Verification gate (before implementation)

- [X] T012 [US2] Verify `CoreNumberPool.get_resource` (`backend/infrahub/core/node/resource_manager/number_pool.py`) uniqueness/reservation checks are correctly branch- and time-scoped for migration-run-time allocation (spec Assumption, FR-007); document the finding in `dev/specs/ifc-2619-inherited-attr-migration/research.md` (append to R10); if scoping is wrong, fix or wrap the allocation path first and add a regression test

### Tests for User Story 2 (write first, watch fail)

- [X] T013 [P] [US2] Component tests for the detection query in `backend/tests/component/core/migrations/query/test_attribute_heal.py`: (a) detection completeness — seeded missing-row nodes found, healthy nodes not, deleted nodes skipped; (b) tombstone-only counts as damaged; (c) retroactive timestamp = later of "kind began inheriting" and "generic gained attribute", read across same-UUID duplicated schema vertices (kind renamed after gaining inheritance — critique E2); (d) timestamp never predates a tombstone (FR-006); (e) batched per-kind — no per-node round-trips (FR-011)
- [X] T014 [P] [US2] Component tests for the migration in `backend/tests/component/core/migrations/graph/test_m076_heal_missing_attribute_rows.py` (default-branch scope): damaged default branch fully repaired at schema-default values with retroactive timestamps; mandatory-no-default healed as null-valued row; NumberPool damage healed with run-time allocations, no duplicate pools/allocations; healthy install → zero writes (asserted via full-graph snapshot equality, strictly stronger than critique E5's write-counter deltas); second run → zero writes (SC-003); self-validation failure path surfaces per-kind actionable errors and fails the migration (FR-010); pre-existing branch (branched after damage) reads healed rows without rebase (SC-004); branch whose `branched_from` predates the damage window correctly sees no attribute (critique P2)

### Implementation for User Story 2

- [X] T015 [US2] Damage-detection query module `backend/infrahub/core/migrations/query/attribute_heal.py` (the deep module): batched per-kind, parameterized Cypher, returns (node uuid, attribute name, derived retroactive timestamp) per damaged pair; tombstone-only treated as damaged with clamped timestamp; timestamp derivation resolves the edge timeline across the full same-UUID schema-vertex set (data-model.md rule; critique E2); results exposed via frozen-dataclass `get_data()` (Constitution III); review plan with `EXPLAIN` (Constitution V)
- [X] T016 [US2] Create `backend/infrahub/core/migrations/graph/m076_heal_missing_attribute_rows.py` as `ArbitraryMigration` (`minimum_version: 74`), register it in `backend/infrahub/core/migrations/graph/__init__.py`, bump `GRAPH_VERSION` to 75 in `backend/infrahub/core/graph/__init__.py`; schema acquisition: load default-branch schema from the DB at migration time, pass schema objects (never registry state) to detection (critique E1)
- [X] T017 [US2] Pass-1 repair in m076: per kind, detect (T015) → repair default-backed attributes via batched row creation at derived retroactive timestamps reusing PR 1's attribute-add machinery/queries with `force_inherited=True`; all repair queries idempotent (FR-005, FR-006, FR-008) (depends on T015, T016)
- [X] T018 [US2] NumberPool repair in m076: per damaged pool-backed pair (the sanctioned per-node loop, FR-011), allocate at run time via the reservation-aware `CoreNumberPool.get_resource` path — rows carry run-time timestamps, not retroactive ones (FR-007) (depends on T012, T017)
- [X] T019 [US2] Self-validation + observability in m076: re-run detection across the repaired scope, fail the migration with per-kind actionable errors when any pair remains (FR-010, SC-001); on success log per-kind repaired-row counts (critique P1); zero-count output doubles as the healthy no-op proof
- [X] T020 [US2] Add towncrier fragment `changelog/+heal-missing-attribute-rows.fixed.md`: upgrading repairs nodes missing attribute rows caused by pre-fix inheritance changes, on the default branch and existing branches, without requiring rebases

**Checkpoint**: default-branch healing complete and independently testable (branch pass not yet wired — US3).

---

## Phase 5: User Story 3 — Healing: branch-side repair (Priority: P3) — PR 2

**Goal**: The same upgrade pass repairs branch-originated damage on all existing branches via branch-scoped detection — no rebase or merge required.

**Independent Test**: Seed a non-default branch where a kind gained inheritance on-branch pre-fix, run m076, assert branch-level rows exist and inherited attributes read back with non-null `id` on the branch.

**Depends on**: US2 (extends the same migration and query module).

### Tests for User Story 3 (write first, watch fail)

- [X] T021 [P] [US3] Component tests in `backend/tests/component/core/migrations/graph/test_m076_heal_missing_attribute_rows.py` (branch scope): kind gained inheritance on-branch pre-fix → branch-scoped pass creates missing branch-level rows, attribute reads back with non-null `id` on the branch, default branch untouched; branch-scoped detection considers only data changed on the branch (default-branch-inherited visibility cases produce no branch-level writes); branch with no schema changes of its own → schema fallback to default works (empty-schema-branch gotcha, critique E1)

### Implementation for User Story 3

- [X] T022 [US3] Branch-scoped detection variant in `backend/infrahub/core/migrations/query/attribute_heal.py`: same contract as default-branch detection but filters to branch-level data changes only (FR-009)
- [X] T023 [US3] Pass-2 branch iteration in m076: iterate existing (non-deleted) branches; per branch, load the branch's own schema from the DB with fallback-to-default semantics when the branch has no schema changes (critique E1); branch-scoped detect → repair at branch level; include per-branch repaired counts in the audit log; self-validation (T019) extends across the branch scope (depends on T022)

**Checkpoint**: all three stories functional; m076 repairs default branch + all branches in one upgrade pass.

---

## Phase 6: Polish & Cross-Cutting Concerns

- [X] T024 [P] Run quickstart.md end-to-end: automated suites (PR 1 + PR 2 sections) plus the manual damaged-install upgrade walk-through (seed damage on a pre-fix version, upgrade, verify reads/updates/filters on default branch and a pre-existing branch, rerun upgrade → zero writes) — SC-001..SC-004
  - 2026-08-03: all automated suites green against the local dev DB — unit test_tasks 6 passed; kind-update 11 passed; attribute-add 9 passed; full migrations/schema/ 57 passed; branch_merge 5 passed; attribute_heal 5 passed; m076 10 passed; integration #9284 repro (`test_schema_add_inherited_generic.py`) 12 passed. **Manual damaged-install upgrade walk-through deferred**: requires booting a pre-fix versioned stack and running `infrahub upgrade` across versions (plus the known Prefect param-size upgrade blocker), not practical in a local-only session; SC-001..SC-004 are otherwise demonstrated by the m076 component suite (self-validation, no-rebase branch visibility, zero-writes snapshot equality) and the integration repro.
- [X] T025 [P] File the three follow-up issues from spec Out of Scope: (1) refactor the migration-within-a-migration pattern shared with `node_uniqueness_constraints_update.py`; (2) stale `Template{generic}` labels on pre-existing template vertices; (3) consolidate the Cypher graph-validation helpers (`verify_no_duplicate_relationships`, `verify_no_edges_added_after_node_delete`, `validate_no_duplicate_attributes`) into one `verify_graph()` entry point with an optional kind filter and adopt it at all existing call sites
  - 2026-08-03: issues drafted locally in followup-issues.md (title + context + proposed work + acceptance criteria each), pending filing with `gh issue create` — no external actions from this session per policy.
- [X] T026 PR 2 gate: `uv run invoke format && uv run invoke lint`, `/pre-ci`; PR 2 description records the governance flag (new numbered graph migration every install executes) and verifies PR 1 is in the same release milestone (critique X1)
  - 2026-08-03: `invoke format` clean; `invoke main.lint` + `invoke backend.lint` (ruff, ty, mypy) clean; `invoke docs.validate` clean; `invoke backend.test-unit` 1407 passed / 3 failed — the 3 failures are `test_git_repository.py` only, caused by local git 2.34.1 lacking `git merge-tree --write-tree` (needs ≥ 2.38), unrelated to this feature (no git-layer files in the diff). PR 2 description drafted locally in pr2-description.md with the governance flag and the same-release-milestone merge checklist; no PR opened from this session per policy.

---

## Phase 7: Post-review redesign of m076 (added 2026-08-04, supersedes the 2026-08-03 rebase-marking task)

**Context**: design review of the implemented m076 settled on a redesign: schema-graph-driven discovery instead of `SchemaBranch` loads (the per-kind × per-scope × per-branch detection sweep and the double schema load between execute and validate are the dominant upgrade-time cost), direct `AttributeAddQuery` usage instead of `NodeAttributeAddMigration`, `MigrationRequiringRebase` with a pool-only branch pass at rebase time, and no user-schema registry dependencies anywhere in the migration (`NodeManager.get_one/get_many` is acceptable only against internal-schema kinds — SchemaNode/SchemaGeneric/SchemaAttribute — and core-models kinds like CoreNumberPool, both registerable from memory). The previous T027 (conditional rebase marking) is superseded: `infrahub upgrade` already marks every stale-`graph_version` branch `NEED_UPGRADE_REBASE` unconditionally (Step 6/6), and the `MigrationRequiringRebase` branch pass covers the rest.

- [X] T027 Branch-agnostic attribute support in `AttributeAddQuery` (`backend/infrahub/core/migrations/query/attribute_add.py`): edges are currently always written with `branch: <query branch>`; when the attribute's `branch_support` is AGNOSTIC they must land on the global branch (`-global-`, branch_level 1) — this also fixes the forward path, which uses the same query. Component tests: healing an AGNOSTIC-support attribute creates edges on the global branch, readable from the default branch and from a branch forked before the heal; AWARE behavior unchanged
- [X] T028 Deleted-attribute regression tests (m076-level behavior, current implementation): (a) attribute removed from a generic schema (rows tombstoned by the remove migration) → m076 neither re-adds rows nor reports damage; (b) attribute removed then re-added to the generic (new SchemaAttribute uuid) → healed at the new linkage time, never before the tombstone. These tests pin end-behavior and must stay green through T029–T031
- [X] T029 Schema-graph-driven discovery, no `SchemaBranch` loads: two lean Cypher discovery queries inlined in the m076 module — (a) default branch: every Node schema inheriting from any generic, with SchemaNode/SchemaGeneric/SchemaAttribute uuids and `inherit_from`/attribute linkage timestamps resolved across same-UUID vertex sets; (b) per user branch: Node schemas whose `inherit_from` attribute value carries a branch-level update, restricting the audit to those kinds. Attribute properties (name, kind, branch_support, default_value, unique/read_only/optional for profile/template gating) hydrated via `NodeManager.get_many` on the SchemaAttribute ids against the audited branch — internal schema + core models registered in the registry from memory (`SchemaRoot(**internal_schema)` + `SchemaRoot(**core_models)`), never `load_schema_from_db`. Detection (`AttributeHealDetectionQuery`) folded into the m076 module (single-consumer, repo convention per m073) and driven by discovery output; `attribute_heal.py` deleted. Existing m076 component tests stay green; detection-module tests move/adapt alongside
  - 2026-08-04: implemented — discovery query (one class, two Cypher shapes via `branch_scoped`) + `NodeManager.get_many` hydration inlined in m076; detection moved into m076 with a per-target `heal_floor` so heal timestamps are the LATER of (kind began inheriting) and (generic gained the attribute); `attribute_heal.py` deleted, detection tests relocated to `test_m075_attribute_heal_detection.py` (all cases survive + new floor test); scope intentionally narrowed to generic-inherited attributes (local-attribute audit tests adapted, `_build_targets` unit tests removed); pool repair registers the minimal reconstructed schemas in the registry (bridge until T030). m076 17 passed, detection 8 passed, migrations/schema 57 passed, unit migrations 16 passed; format/ruff/ty/mypy clean
- [X] T030 Repair rework — drop `NodeAttributeAddMigration` from the heal path: default-backed repairs call `AttributeAddQuery` directly (explicit node_kinds/attribute params from discovery data, `uuids` + `write_at` as today); pool-backed repairs become a per-damaged-uuid loop — `get_one` the `CoreNumberPool` node (core models in memory), `get_resource(identifier=<node uuid>, attribute=<hydrated AttributeSchema>, at=<run time>)`, then write the row via a new pool-row write query (allocated value on an `is_default: false` value vertex + `HAS_SOURCE` edge to the pool; follow the per-node value-map pattern in `m044_backfill_hfid_display_label_in_db.py` — `$values_by_id[n.uuid]`, edge close/create with branch props; assert the produced row shape matches what the runtime write path produces). Skip `SchemaNumberPoolUpserter` and `update_branch_registry` entirely (the pool must already exist; fail loudly if not). Revert the now-unneeded `NodeAttributeAddMigration`/`AttributeSchemaMigration` plumbing (`uuids`/`write_at` fields, model_validator, Query01 pass-through) to PR 1 state — `AttributeAddQuery` keeps its `uuids`/`write_at` parameters
  - 2026-08-04: implemented — default-backed repair calls `AttributeAddQuery` directly (audit-scope-gated node_kinds via new `_repair_node_kinds`, one transaction per write_at batch, same error annotation); pool-backed repair is a per-uuid `get_resource` → `PoolAttributeRowAddQuery` loop inside one transaction per attribute (new query inlined in m076: per-node `$values_by_id[n.uuid]` map, `is_default: false` value vertex, `HAS_SOURCE` to the pool, AttributeAddQuery's idempotency guard incl. tombstone close, agnostic global-branch placement); pool looked up by (generic kind, attribute, SCHEMA type) with a loud migration-failing error when absent — no upserter, no `update_branch_registry`, registry bridge (`_register_schemas_for_pool_machinery`) deleted so m076 performs zero user-schema registry writes (`_ensure_runtime_context` additionally maps `registry.node[CoreNumberPool]`); `shared.py` `write_at` field dropped and `node_attribute_add.py` restored to PR 1 state (`uuids` model field kept — it predates the feature, m043 uses it); obsolete validator unit tests deleted. New component tests: missing-pool loud failure, healed-vs-runtime pool row shape equality (structure identical modulo allocated number). m076 19 passed + detection 8 passed (combined 27), migrations/schema 57 passed, unit migrations 13 passed; invoke format + backend.lint (ruff, ty, mypy) clean
- [X] T031 `MigrationRequiringRebase` conversion: `execute()` heals all default-backed damage everywhere (default branch unscoped + branch-scoped retroactive passes, as today) plus pool damage on the default branch only; `execute_against_branch()` (run per branch by `MigrationRunner` during that branch's rebase) heals only branch-level pool-backed damage — discovery restricted to pool-backed candidates on the branch, allocate at run time post-rebase so branch allocations follow default-branch ones. Validation split: upgrade-time `validate_migration` covers default-backed damage on all branches + pool damage on the default branch (must NOT fail on branch pool damage deferred to rebase); `execute_against_branch` validates its own branch's pool scope before returning. Component tests: branch pool damage untouched by `execute()`, healed by `execute_against_branch()` (invoked directly, post-simulated-rebase state), no duplicate/overlapping allocations vs default-branch pools; upgrade-time validation passes with deferred branch pool damage present
  - 2026-08-04: implemented — base class swapped to `MigrationRequiringRebase`; branch-scoped passes in `execute()`/`validate_migration` drop pool-backed pairs via `_split_out_deferred_pool_pairs` (deferral logged with counts, never reported as damage); new `execute_against_branch` runs pool-only branch discovery (`_pool_backed_audited_kinds`), repairs via the existing per-uuid allocate-at-run-time loop, logs per-kind counts, and re-detects its own pool scope inline, returning per-kind errors for any remaining pair (MigrationRunner's follow-up `validate_migration` call stays correct: deferred pools on other unrebased branches are excluded by design, the just-healed branch was validated inline). New component tests: `test_branch_pool_damage_deferred_to_rebase_then_healed` (untouched by execute, validation passes with deferred damage, healed + idempotent at rebase time), `test_branch_pool_allocations_follow_default_branch_allocations` (same pool, 3 distinct values across default+branch heals); `test_branch_without_own_inheritance_changes_is_not_audited` extended with a zero-write `execute_against_branch` pass; no existing tests needed adapting (none healed branch pools via `execute()`). m076 21 + detection 8 = 29 passed, migrations/schema 57 passed, unit migrations + graph_version 16 passed, runner component 3 passed; invoke format + backend.lint (ruff, ty, mypy) clean
- [X] T032 Doc sync + gates: update spec.md (SC-004 wording — branch-originated pool values materialize at rebase time; performance follow-up bullet superseded by T029), data-model.md, plan.md, quickstart.md, pr2-description.md (governance: migration now `MigrationRequiringRebase`), changelog fragment wording; mark followup-issues.md Issue 4 superseded by T029 and Issue 1 partially delivered by T030; re-run full gates (`invoke format`, lint, m076 + detection + migrations/schema + branch-merge suites, integration repro, `docs.validate`)
  - 2026-08-04: docs synced to the redesigned m076 — spec.md (SC-001/SC-004, FR-005/006/007/009, US3 + Problem Statement + Key Entities, new edge cases for missing pools and removed attributes, perf follow-up bullet marked superseded), data-model.md (audit scope + no-SchemaBranch note, heal-floor timestamp rule, pool lookup/loud-failure + deferred branch pools, MigrationRequiringRebase, state transitions incl. rebase pass), plan.md (summary, scale, source tree, PR 2 design section rewritten to discovery/detection-inlined + direct-query repair + rebase-time pool pass), quickstart.md (detection suite command, rebase-time pool verification step), pr2-description.md (architecture summary, files table, MigrationRequiringRebase governance bullet, 2026-08-04 test evidence: 29 m076 component tests across two files), changelog fragment (branch pool values assigned at post-upgrade rebase), followup-issues.md (Issue 4 SUPERSEDED by T029; Issue 1 partially delivered by T030). Gates: format + main.lint + backend.lint (ruff, ty, mypy) clean; m076 29 passed; migrations/schema 57 passed (one order-dependent flake when run immediately after the m076 suite in the same DB — rotating victim, each passes in isolation and the suite passes standalone repeatedly; disregarded per test-in-isolation rule); branch_merge 5 passed; integration repro 12 passed; unit migrations + graph_version + runner 19 passed; docs.validate clean.

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: none — start immediately
- **Foundational (Phase 2)**: n/a (empty by design)
- **US1 (Phase 3)**: after T001. Internally: T002–T005 (tests, parallel) → T006 → T007; T008 independent of T006/T007 (different file) but ordered before T009's full-suite gate; T009 → T010 → T011
- **US2 (Phase 4)**: after US1 complete (reuses its machinery). T012 gates T018. T013/T014 (tests, parallel) → T015 → T016 → T017 → T018 → T019 → T020
- **US3 (Phase 5)**: after US2. T021 → T022 → T023
- **Polish (Phase 6)**: after US3; T024/T025 parallel; T026 last
- **Redesign (Phase 7)**: T027/T028 first, in parallel (independent correctness fixes + regression nets that must survive the redesign) → T029 (discovery foundation) → T030 (repair rework, consumes discovery output) → T031 (rebase conversion, moves the pool path T030 built) → T032 (doc sync + gates, last)

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
