---
description: "Task list for branch-agnostic vertex metadata correctness (IFC-3032)"
---

# Tasks: Branch-Agnostic Vertex Metadata Correctness

**Input**: Design documents from `dev/specs/ifc-3032-vertex-metadata-correctness/`

**Prerequisites**: [plan.md](plan.md), [spec.md](spec.md), [research.md](research.md),
[data-model.md](data-model.md), [contracts/vertex-metadata-invariant.md](contracts/vertex-metadata-invariant.md),
[quickstart.md](quickstart.md)

**Tests**: Test tasks are included and are **not optional here** — SC-001 and SC-002 are release gates,
and Constitution IV requires tests written before or alongside implementation. Tasks are ordered so
each fix's tests land in the same phase as the fix.

**Organization**: Grouped by user story. Each story is an independently shippable commit, matching the
spec's six-part sub-task breakdown.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependency on an incomplete task)
- **[Story]**: `[US1]`–`[US4]`, mapping to the user stories in spec.md
- Code sites are named by module and symbol, never by line number

## Path Conventions

Backend-only. Production code under `backend/infrahub/core/`, tests mirroring it under
`backend/tests/component/core/`. See plan.md § Project Structure.

## Commit Mapping

| Story | Requirements | Spec sub-task | Ships as |
|---|---|---|---|
| US1 + US2 | FR-001, FR-002 | 1 | `Node._update` gate + `_save_metadata` branch |
| US3 | FR-007 | 2 | Three schema-migration queries |
| US1 + US2 (create path) | FR-003 | 3 | `NodeCreateAllQuery` per-field gating |
| US2 (peers) | FR-004 | 4 | Relationship peer guard — independently revertible |
| US4 | FR-005 | 5 | Repair migration |
| — | FR-006 | 6 | Knowledge-doc correction |

---

## Phase 1: Setup

**Purpose**: Confirm the environment can run database-backed component tests before any code changes.

- [ ] T001 Verify the component-test environment runs: `uv run pytest -x backend/tests/component/core/migrations/graph/test_050.py`. If Docker is unavailable, set `INFRAHUB_USE_TEST_CONTAINERS=false` and point at a running dev database per `quickstart.md`
- [ ] T002 [P] Record the current highest graph migration number by listing `backend/infrahub/core/migrations/graph/` — the repair migration in Phase 7 takes the next free number against `develop` at merge time (m075 is highest as of writing)

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: The shared recompute oracle. Every story's assertions and the Phase 7 repair migration
must derive metadata the same way; if they derive it separately they can agree with each other while
both being wrong (critique E1).

**⚠️ CRITICAL**: No user story work can begin until T003–T006 are complete.

- [ ] T003 Add a `recompute_vertex_metadata()` helper to `backend/tests/component/core/migrations/schema/metadata_helpers.py` implementing the recompute table in `contracts/vertex-metadata-invariant.md`: per-vertex `created_at` / `updated_at` from level-1 edges, and `created_by` / `updated_by` from the `from_user_id` / `to_user_id` of the edge that supplied each timestamp
- [ ] T004 In the same helper module, restrict the `:Node` recompute to vertices holding an **active** `branch_level = 1` `IS_PART_OF` edge, while keeping the uuid-wide `min(from)` for `created_at` so a surviving twin still reports the original creation time (contract § Scope of the `:Node` rows)
- [ ] T005 [P] Add a twin-aware node-metadata helper to `backend/tests/component/core/migrations/schema/metadata_helpers.py` — `get_node_vertex_metadata` asserts exactly one Node vertex per uuid and explicitly defers duplicate cases to the caller, which FR-002's twin pin needs (critique E8)
- [ ] T006 Add an assertion helper that compares a vertex's stored metadata against `recompute_vertex_metadata()` and reports the mismatched field, so SC-001 assertions never hard-code a timestamp
- [ ] T007 [P] Extend `backend/tests/component/core/migrations/graph/test_050.py`'s schema fixtures, or add a sibling fixture module, providing a **branch-aware kind with a branch-agnostic attribute** — mismatch #2 has no live instance and every one of its SC-001 cells needs it (Constitution IV permits a new inline schema only when no fixture suffices; none does)

**Checkpoint**: the oracle exists and is shared. Story phases can begin.

---

## Phase 3: User Story 2 — Metadata does not move for invisible changes (Priority: P1) 🎯 MVP

**Goal**: A branch-aware field changed on a branch-agnostic object from a feature branch leaves the
default-branch `updated_at` / `updated_by` untouched.

**Why first**: This is the over-set half of the same gate as US1 and it is live in the core schema
(`CoreReadOnlyRepository` is agnostic, `ref` and `commit` are aware), so it needs no custom schema and
is the cheapest anchor for the FR-001/FR-002 fix. Shipping it also ships US1's under-set half, since
both are the one gate.

**Independent test**: Update `CoreReadOnlyRepository.ref` on a feature branch; read the repository on
the default branch and assert value and metadata are both unchanged.

### Tests for User Story 2

- [ ] T008 [P] [US2] Add `backend/tests/component/core/test_vertex_metadata_invariant.py` with the SC-001 Mechanism A skeleton: parametrised over the four mismatches × {create, update, delete} × {default, user} write branch, asserting against `recompute_vertex_metadata()`
- [ ] T009 [P] [US2] In that module, add the mismatch #3 update cells (`CoreReadOnlyRepository.ref` / `.commit`): update on a feature branch, assert the default-branch read shows the unchanged value **and** unchanged `updated_at` / `updated_by`. Expected to fail before T012
- [ ] T010 [P] [US2] Add the FR-002 delete pin: delete a node on the default branch, change an agnostic field from a branch created before the delete, assert no bump
- [ ] T011 [US2] Add the FR-002 twin pin using the T005 twin-aware helper: with a kind-migrated twin pair present, assert only the vertex holding an active level-1 `IS_PART_OF` is considered

### Implementation for User Story 2

- [ ] T012 [US2] In `backend/infrahub/core/node/__init__.py::Node._update`, replace the `self.get_branch_based_on_support_type()` gate with a per-changed-field decision: stamp the Node vertex when **any** field recorded on the `NodeChangelog` has `get_branch_based_on_support_type().hierarchy_level == 1` (plan D1, research R1/R2)
- [ ] T013 [US2] In `backend/infrahub/core/node/__init__.py::Node._save_metadata`, pass the **default** branch to `NodeUpdateMetadataQuery` instead of the node's support branch, so the existing delete-edge guard looks on the branch where deletions and kind migrations are recorded (plan D2)
- [ ] T014 [US2] Run `uv run pytest -x backend/tests/component/core/test_vertex_metadata_invariant.py backend/tests/component/core/test_node_manager_prefetch_metadata.py` and confirm T009–T011 now pass with no regression

**Checkpoint**: FR-001 and FR-002 complete — spec sub-task 1. Commit before proceeding.

---

## Phase 4: User Story 1 — Metadata reflects agnostic changes made from a branch (Priority: P1)

**Goal**: A branch-agnostic field changed on a branch-aware object from a feature branch advances the
default-branch `updated_at` / `updated_by`.

**Why here**: The under-set half of the gate fixed in Phase 3. The production change already landed in
T012; this phase proves it against the mismatches that have no core-schema instance.

**Independent test**: Update the agnostic attribute of the T007 test kind from a feature branch; read
on the default branch and assert both the new value and matching metadata.

### Tests for User Story 1

- [ ] T015 [P] [US1] In `backend/tests/component/core/test_vertex_metadata_invariant.py`, add the mismatch #2 update cells using the T007 fixture: update the agnostic attribute on a feature branch, assert the default-branch read shows the new value **and** advanced `updated_at` / `updated_by`
- [ ] T016 [P] [US1] Add the mismatch #1 update cells (`BuiltinIPPrefix.resource_pool`, an agnostic relationship on an aware node)
- [ ] T017 [P] [US1] Add the mismatch #4 update cells (`CoreGenericRepository.internal_status`, `CoreRepository.commit`), asserting the metadata matches whichever level the **update** path writes — the create/update split for `local`-on-`agnostic` is a separate defect (spec Out of Scope), and the oracle is edge-derived so it is correct either way
- [ ] T018 [US1] Add the mixed-update edge case: touch both an aware and an agnostic field on an aware node from a branch in one save, assert the default-branch `updated_at` advances

### Implementation for User Story 1

- [ ] T019 [US1] Fix any gaps T015–T018 expose in the T012 gate — in particular confirm fields added by `_recompute_local_jinja2`, `_recompute_hfid` and `_recompute_display_label` reach the changelog and are considered by the gate
- [ ] T020 [US1] Run the full SC-001 Mechanism A set and confirm all 24 cells pass

**Checkpoint**: SC-001 Mechanism A complete for the update and delete operations.

---

## Phase 5: User Story 3 — Schema migrations set metadata for rows they publish globally (Priority: P1)

**Goal**: A schema migration on a feature branch that writes level-1 edges also writes the matching
vertex metadata — the only finding merge can never repair.

**Independent test**: Add a branch-agnostic attribute to a branch-aware kind on a feature branch;
assert the new Attribute vertex has `created_at` / `created_by` and the owning Node's `updated_at`
advanced, both read on the default branch.

### Tests for User Story 3

- [ ] T021 [P] [US3] Add SC-001 Mechanism B cells for `AttributeAddQuery` to `backend/tests/component/core/test_vertex_metadata_invariant.py`: mismatches #2, #3, #4 × {default, user} write branch. #1 is N/A — `attribute_add` never creates a relationship
- [ ] T022 [P] [US3] Add Mechanism B cells for `NodeDuplicateQuery`: mismatches #1–#4 × {default, user}
- [ ] T023 [P] [US3] Add Mechanism B cells for `NodeRemoveMigrationQueryIn` / `NodeRemoveMigrationQueryOut`: mismatches #1–#4 × {default, user}
- [ ] T024 [P] [US3] Add the FR-007 regression pin: a schema migration on a feature branch writing only `branch_level = 2` edges must write **no** vertex metadata
- [ ] T025 [US3] Add the FR-007 snapshot pin: after a user-branch migration writes global rows, assert `previous_updated_at` / `previous_updated_by` on the affected vertices are untouched (critique E3)

### Implementation for User Story 3

- [ ] T026 [US3] In `backend/infrahub/core/migrations/query/attribute_add.py::AttributeAddQuery`, carry `on_global_branch` and the matched `is_part_of_e` through the `WITH` clauses that currently drop them before the metadata `CALL`
- [ ] T027 [US3] In the same query, gate the Attribute vertex's metadata on `$set_metadata OR on_global_branch`, and the Node vertex's on that **and** `is_part_of_e.branch_level = 1`, so a node existing only on a branch is not stamped (plan D3)
- [ ] T028 [US3] In `backend/infrahub/core/migrations/query/node_duplicate.py::NodeDuplicateQuery`, return the matched `IS_PART_OF` edge from the existing `CALL (node)` subquery (which today returns only `node` and `is_active`), and gate the metadata on `$set_metadata OR <that edge is on `-global-`>`. Gating on the edge's *level* would be wrong for aware nodes, whose `IS_PART_OF` resolves to a level-1 default-branch edge while the migration writes new edges at level 2
- [ ] T029 [US3] In `backend/infrahub/core/migrations/schema/node_remove.py`, move the `WITH` that calls `_branch_from_existing` above each metadata `CALL` in `NodeRemoveMigrationQueryIn` and `NodeRemoveMigrationQueryOut`, then gate on `$set_metadata OR new_branch_level = 1`
- [ ] T030 [US3] Across T027–T029, keep the `previous_updated_at` / `previous_updated_by` `SET`s behind the **unchanged** `$set_metadata` scalar — only the `updated_at` / `updated_by` `SET`s move behind the new edge-level gate (spec FR-007, plan D3, critique E3)
- [ ] T031 [US3] Confirm `attribute_remove`, `attribute_rename`, `attribute_kind_update` and `node_relationship_remove` are left untouched — they write no `-global-` edges, so their `set_metadata` scalar is already self-consistent
- [ ] T032 [US3] Run `uv run pytest -x backend/tests/component/core/migrations/schema/` and confirm the existing suite passes **unchanged** — this is the regression pin for T029's reorder (critique E4)

**Checkpoint**: FR-007 complete — spec sub-task 2. SC-001 Mechanism B green. Commit before proceeding.

---

## Phase 6: Create-path and relationship-peer gating (Priority: P1/P2)

**Goal**: Close the two remaining write paths — node creation and relationship create/delete. Both
findings are latent or self-healing, so this phase is independently droppable without weakening
Phases 3–5 (critique P2).

### FR-003 — `NodeCreateAllQuery` per-field gating (spec sub-task 3)

- [ ] T033 [P] [US1] Add the SC-001 create cells for all four mismatches × {default, user} to `backend/tests/component/core/test_vertex_metadata_invariant.py`
- [ ] T034 [US1] In `backend/infrahub/core/query/node.py::NodeCreateAllQuery.query_init`, move the `created_at` / `created_by` / `updated_at` / `updated_by` properties out of the single `if self.branch.is_default or self.branch.is_global` guard on `attr_vertex_prop_str` / `rel_vertex_prop_str` and into the per-field data, so each vertex is stamped iff its own `branch_level` is 1
- [ ] T035 [US1] Confirm this gate follows the **create** path (`core/attribute.py::BaseAttribute.get_create_data`, which downgrades `local`-on-`agnostic` to level 1) rather than the update path used in T012 — the two genuinely disagree for mismatch #4 and each gate must mirror the edges its own path writes (plan D4, research R3)
- [ ] T036 [US1] Run the SC-001 create cells and confirm all 8 pass

### FR-004 — Relationship peer guard (spec sub-task 4)

- [ ] T037 [P] [US2] Add to `backend/tests/component/core/test_relationship_metadata.py`: create an agnostic relationship between two aware nodes that exist only on a feature branch, assert neither peer's vertex metadata changed
- [ ] T038 [P] [US2] Add the split-peer edge case: an agnostic relationship where one peer is on the default branch and the other only on a branch — assert exactly one peer is stamped
- [ ] T039 [US2] In `backend/infrahub/core/query/relationship.py`, replace the bare `SET s.updated_at` / `SET d.updated_at` in `RelationshipCreateQuery.query_init`, `RelationshipDeleteQuery.query_init` and `RelationshipDeleteAllQuery.query_init` with the guard already used by `RelationshipUpdatePropertyQuery`: require a level-1 active `IS_RELATED` **and** a level-1 active `IS_PART_OF` on the peer
- [ ] T040 [US2] Leave the `rl` (Relationship vertex) stamp in the delete queries on its existing gate — the relationship's own branch level is the correct gate for its own vertex, and applying the peer guard to it would reintroduce an under-set (plan D5, critique E2)
- [ ] T041 [US2] Run `EXPLAIN` on the three modified relationship queries per Constitution V and record the plans; confirm only the aware-peer case adds an `OPTIONAL MATCH`, since `RelationshipCreateQuery.add_source_match_to_query` already proves a level-1 `IS_PART_OF` for level-1 peers
- [ ] T042 [US2] Run `uv run pytest backend/tests/query_benchmark/ -k relationship` before and after T039 and record the delta for SC-003. A measurable regression means the guard is in the wrong place — revert this sub-task alone rather than weakening it

**Checkpoint**: FR-003 and FR-004 complete — spec sub-tasks 3 and 4. Commit each separately.

---

## Phase 7: User Story 4 — Existing graphs are repaired (Priority: P2)

**Goal**: A repair migration brings every already-wrong vertex into agreement with its level-1 edges,
including the permanently-NULL attributes F6 leaves that no later write repairs.

**Independent test**: Seed a graph with known-wrong metadata, run the migration, assert every affected
vertex matches the recompute; run it again and assert zero changes.

### Tests for User Story 4

- [ ] T043 [P] [US4] Add `backend/tests/component/core/migrations/graph/test_repair_vertex_metadata.py`, seeding both damage shapes: NULL metadata on globally-published attributes (F6) and advanced `updated_at` from an invisible change (F1b)
- [ ] T044 [P] [US4] Assert every affected vertex equals `recompute_vertex_metadata()` after one run, covering `:Node`, `:Attribute` and `:Relationship`
- [ ] T045 [US4] Add the SC-002 idempotency assertion: a second run reports **zero** changed vertices
- [ ] T046 [P] [US4] Assert the migration does not touch `previous_updated_at` / `previous_updated_by` — snapshotting them would break idempotency and corrupt the merge-rollback pair that owns them
- [ ] T047 [P] [US4] Assert a migrated-out twin and a node deleted on the default branch are **not** recompute targets, while the surviving twin's `created_at` still reflects the uuid-wide `min()`
- [ ] T048 [US4] Assert the reported per-label changed counts match the vertices actually changed (spec FR-005, critique P5)

### Implementation for User Story 4

- [ ] T049 [US4] Create `backend/infrahub/core/migrations/graph/mNNN_repair_vertex_metadata.py` (next free number per T002), following the m050 structure: three `Query` subclasses ordered Attribute, then Relationship, then Node, batched `IN TRANSACTIONS`
- [ ] T050 [US4] Implement the recompute in Cypher matching `contracts/vertex-metadata-invariant.md`, with m050's `IS NULL` guard **dropped** so wrong values are corrected as well as NULLs filled
- [ ] T051 [US4] Extend the derivation to `created_by` / `updated_by`, taking the `from_user_id` (or `to_user_id`, where a `to` supplied the winning timestamp) of the edge that produced each timestamp — m050 never set these, and SC-001 asserts on them
- [ ] T052 [US4] Scope the sweep with `field.branch_support <> n.branch_support`, read from properties already stored on the vertices — no schema load, since a graph migration may run against a database predating the current models (research R5)
- [ ] T053 [US4] Restrict `:Node` targets to vertices with an active level-1 `IS_PART_OF`, keeping the uuid-wide `min(from)` inside the `created_at` derivation
- [ ] T054 [US4] Return the count of changed vertices per label from the migration result
- [ ] T055 [US4] Register the migration in the graph-migration list and set its `minimum_version` to the preceding migration's number
- [ ] T056 [US4] Run `uv run pytest -x backend/tests/component/core/migrations/graph/` and confirm the new suite and the existing m050 suite both pass

**Checkpoint**: FR-005 complete — spec sub-task 5. SC-002 green.

---

## Phase 8: Documentation, Polish & Cross-Cutting

- [ ] T057 [P] In `dev/knowledge/backend/database-schema.md`, replace *"When added to default/global branch"* / *"When last updated on default/global branch"* in the vertex-property tables with the level-1-edge invariant from `contracts/vertex-metadata-invariant.md`. This wording is the buggy proxy stated as fact and is the likely origin of every site that implemented it (FR-006, spec sub-task 6)
- [ ] T058 [P] In the same document, note the cross-branch side effect Constitution II requires be documented: a write on a user branch can move default-branch metadata whenever the field's branch support differs from its node's
- [ ] T059 [P] Add a Towncrier changelog fragment under `changelog/` — wrong `updated_at` / `updated_by` on the default branch is user-visible (use the `creating-changelog-entries` skill)
- [ ] T060 [P] File a follow-up issue for the `local`-on-`agnostic` create/update split: `get_create_data` downgrades a `LOCAL` attribute on an `AGNOSTIC` node to level 1 while `get_branch_based_on_support_type` does not, so mismatch #4 is created at level 1 and updated at level 2 and the default branch keeps showing the creation-time value (spec Out of Scope)
- [ ] T061 [P] File a follow-up issue for `attribute_kind_update`, `attribute_rename` and `node_relationship_remove`: applied to an agnostic field they write level-2 edges for data living at level 1, so the change is invisible on the default branch where the data lives (spec Out of Scope)
- [ ] T062 Run `uv run invoke format` and `uv run invoke lint`
- [ ] T063 Run the full metadata surface per `quickstart.md`: `uv run pytest -x backend/tests/component/core/test_relationship_metadata.py backend/tests/component/core/test_node_manager_prefetch_metadata.py backend/tests/component/core/test_vertex_metadata_invariant.py backend/tests/component/core/migrations/`
- [ ] T064 Run `/pre-ci` before pushing

---

## Dependencies

```text
Phase 1 (Setup)
    ↓
Phase 2 (Foundational: shared recompute oracle) ← BLOCKS EVERYTHING
    ↓
Phase 3 (US2: FR-001 + FR-002) ← MVP; also delivers US1's production change
    ↓
Phase 4 (US1: proves the same gate on the non-core mismatches)
    ↓
Phase 5 (US3: FR-007) ← highest severity remaining; independent of Phase 6
    ↓
Phase 6 (FR-003, FR-004) ← both independently droppable
    ↓
Phase 7 (US4: FR-005) ← depends on Phases 3–6 defining correct-going-forward
    ↓
Phase 8 (FR-006, changelog, follow-ups)
```

**Hard dependencies**:

- T003–T006 block every test task — the oracle must exist first
- T007 blocks T015 and T021 (mismatch #2 has no live fixture)
- T012 blocks T014, T019, T020
- T026 blocks T027; T029 blocks T032
- T049 blocks T050–T055; all of them block T056
- Phase 7 should follow Phases 3–6 so the repair is not chasing a moving definition of correct

**Soft ordering**: Phase 5 and Phase 6 touch disjoint files and could run in parallel, but the spec
stages them as separate commits in this order by severity.

---

## Parallel Execution Examples

**Phase 2**: T005 and T007 are independent of T003/T004 and of each other.

**Phase 3**: T008, T009 and T010 write to the same new file — write T008's skeleton first, then
T009/T010 in parallel. T011 depends on T005.

**Phase 5**: T021, T022, T023 and T024 target different migration queries and can be written in
parallel; T026–T029 likewise touch three different modules.

**Phase 7**: T043, T044, T046 and T047 are independent assertions over the same seeded graph.

**Phase 8**: T057–T061 are all independent.

---

## Implementation Strategy

**MVP scope**: Phases 1–3. That delivers the FR-001/FR-002 gate fix, which closes both live
core-schema defects (the `CoreReadOnlyRepository` over-set and the agnostic-field under-set) and is
independently shippable.

**Incremental delivery**: each checkpoint is a commit. The spec's staging is deliberate — Phase 6's
FR-004 is isolated so it can be reverted alone if SC-003 shows a real cost, and Phase 6 as a whole can
be dropped without weakening Phases 3–5, since both its findings are latent or self-healing.

**Gates before merge**: SC-001 (Phases 3–6) and SC-002 (Phase 7) are release gates. SC-003 (T042) is a
check, not a gate — but a measurable regression is evidence the guard is misplaced, not a reason to
lower the bar.
