---
description: "Task list for branch-agnostic vertex metadata correctness (IFC-3032)"
---

# Tasks: Branch-Agnostic Vertex Metadata Correctness

**Input**: Design documents from `dev/specs/ifc-3032-vertex-metadata-correctness/`

**Prerequisites**: [plan.md](plan.md), [spec.md](spec.md), [research.md](research.md),
[data-model.md](data-model.md), [contracts/vertex-metadata-invariant.md](contracts/vertex-metadata-invariant.md),
[quickstart.md](quickstart.md)

**Tests**: Test tasks are included and are **not optional here** — SC-001 and SC-004 are release
gates (SC-002 gates the optional Phase 6), and Constitution IV requires tests written before or
alongside implementation. Tasks are ordered so each fix's tests land in the same phase as the fix.

**Environment**: component tests run locally against the dev database; set
`INFRAHUB_USE_TEST_CONTAINERS=false` to reuse a running one instead of starting testcontainers.

**Organization**: Grouped by user story. Each story is an independently shippable commit, matching the
spec's seven-part sub-task breakdown. Phase 6 (US4) is optional — see its header.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependency on an incomplete task)
- **[Story]**: `[US1]`–`[US5]`, mapping to the user stories in spec.md
- Code sites are named by module and symbol, never by line number

## Path Conventions

Backend-only. Production code under `backend/infrahub/core/`, tests mirroring it under
`backend/tests/component/core/`. See plan.md § Project Structure.

## Commit Mapping

| Story | Requirements | Spec sub-task | Ships as |
|---|---|---|---|
| US1 + US2 | FR-001, FR-002, FR-008 | 1 | `Node._update` + `Node.delete` gates, `_save_metadata` branch |
| US3 | FR-007 | 2 | Three schema-migration queries |
| US1 + US2 (create path) | FR-003 | 3 | `NodeCreateAllQuery` per-field gating |
| US2 (peers) | FR-004 | 4 | Relationship peer guard — independently revertible |
| US4 | FR-005 | 5 | Repair migration — **optional**, repairs already-damaged graphs |
| US5 | FR-009 | 6 | Rollback reach for globally-published merge writes |
| — | FR-006 | 7 | Knowledge-doc correction |
| US2 (retirement) | FR-010 | 8 | Retirement stamps Node and field vertices |

---

## Phase 1: Foundational (Blocking Prerequisites)

**Purpose**: The shared recompute oracle. Every story's assertions — and the repair migration in
Phase 6, if that phase is taken — must derive metadata the same way; if they derive it separately they
can agree with each other while both being wrong (critique E1).

**⚠️ CRITICAL**: No user story work can begin until T001–T004 are complete.

- [X] T001 Add a `recompute_vertex_metadata()` helper to `backend/tests/helpers/vertex_metadata.py` implementing the recompute table in `contracts/vertex-metadata-invariant.md`: per-vertex `created_at` / `updated_at` from level-1 edges, and `created_by` / `updated_by` from the `from_user_id` / `to_user_id` of the edge that supplied each timestamp
- [X] T002 In the same helper module, keep the `:Node` recompute **total**: derive `created_at` from the uuid-wide `min(from)` over `branch_level = 1` `IS_PART_OF` edges so a surviving twin still reports the original creation time, and answer for any vertex carrying a level-1 edge — including one whose own existence is branch-local, so a stamp that no level-1 write justifies is reported rather than hidden. Scoping the derivation to vertices holding an active level-1 `IS_PART_OF`, as this task first read, would make the oracle silent on exactly the vertices the create-path gate has to be judged on (contract § Scope of the `:Node` rows)
- [X] T003 [P] Add a twin-aware node-metadata helper to `backend/tests/helpers/vertex_metadata.py` — `get_node_vertex_metadata` asserts exactly one Node vertex per uuid and explicitly defers duplicate cases to the caller, which FR-002's twin pin needs (critique E8)
- [X] T004 Add an assertion helper that compares a vertex's stored metadata against `recompute_vertex_metadata()` and reports the mismatched field, so SC-001 assertions never hard-code a timestamp
- [X] T005 [P] Provide a **branch-aware kind with a branch-agnostic attribute** for mismatch #2 and every one of its SC-001 cells. Satisfied by reuse: `tests/helpers/schema/agnostic_retirement.py`'s `AgnosticretireWidget` is an aware kind declaring both an agnostic attribute (`serial`) and an agnostic relationship (`gadget`), so it also supplies the mismatch #1 shape. `tests/helpers/schema/branch_support_mismatch.py` registers it alongside the agnostic-kind schemas, which have no live instance

**Checkpoint**: the oracle exists and is shared. Story phases can begin.

---

## Phase 2: User Story 2 — Metadata does not move for invisible changes (Priority: P1) 🎯 MVP

**Goal**: A branch-aware field changed on a branch-agnostic object from a feature branch leaves the
default-branch `updated_at` / `updated_by` untouched — on the update path **and** the delete path.

**Why first**: This is the over-set half of the same gate as US1 and it is live in the core schema
(`CoreReadOnlyRepository` is agnostic, `ref` and `commit` are aware), so it needs no custom schema and
is the cheapest anchor for the FR-001/FR-002 fix. Shipping it also ships US1's under-set half, since
both are the one gate.

**Independent test**: Update `CoreReadOnlyRepository.ref` on a feature branch; read the repository on
the default branch and assert value and metadata are both unchanged.

### Tests for User Story 2

- [X] T006 [P] [US2] Add `backend/tests/component/core/test_vertex_metadata_invariant.py` with the SC-001 Mechanism A skeleton: a `Mismatch` enum, and one parametrised cell per written runner × {default, user} write branch, asserting against `recompute_vertex_metadata()`. Cells for unwritten mismatch/operation pairs are not generated — the remaining ones are tracked by the tasks below, not by skips
- [X] T007 [P] [US2] In that module, add the mismatch #3 update cells (`CoreReadOnlyRepository.ref` / `.commit`): update on a feature branch, assert the default-branch read shows the unchanged value **and** unchanged `updated_at` / `updated_by`. Expected to fail before T012
- [X] T008 [P] [US2] Add the FR-002 delete pin: delete a node on the default branch, change an agnostic field from a branch created before the delete, assert no bump
- [X] T009 [US2] Add the FR-002 twin pin using the T003 twin-aware helper: with a kind-migrated twin pair present, assert only the vertex holding an active level-1 `IS_PART_OF` is considered
- [X] T010 [P] [US2] Add the FR-008 delete cells for an **aware** node carrying an agnostic attribute: deleting from the default branch records the deletion on the Node vertex, deleting from a feature branch leaves it untouched. Both arms assert against the recompute
- [X] T011 [P] [US2] Add the FR-008 over-set pin: delete an **agnostic** node carrying an aware attribute from a feature branch, assert the default-branch `updated_at` did **not** move

### Implementation for User Story 2

- [X] T012 [US2] In `backend/infrahub/core/node/__init__.py::Node._update`, replace the `self.get_branch_based_on_support_type()` gate with a per-changed-field decision: stamp the Node vertex when **any** field recorded on the `NodeChangelog` has `get_branch_based_on_support_type().hierarchy_level == 1` (plan D1, research R1/R2)
- [X] T013 [US2] In `backend/infrahub/core/node/__init__.py::Node._save_metadata`, pass the **default** branch to `NodeUpdateMetadataQuery` instead of the node's support branch, so the existing delete-edge guard looks on the branch where deletions and kind migrations are recorded (plan D2)
- [X] T014 [US2] In `backend/infrahub/core/query/node.py::NodeDeleteQuery`, replace the `if self.branch.is_global or self.branch.is_default` gate with the same per-deleted-field decision: stamp the Node vertex when any deleted field wrote a `branch_level = 1` edge (FR-008, plan D1b, research R11)
- [X] T015 [US2] In `backend/infrahub/core/node/__init__.py::Node.delete`, stop letting the single `self.get_branch_based_on_support_type()` result decide the Node-vertex gate. Leave the branch it passes to `RelationshipDeleteAllQuery` alone — that is a separate concern handled by FR-004
- [X] T016 [US2] Run `uv run pytest -x backend/tests/component/core/test_vertex_metadata_invariant.py backend/tests/component/core/test_node_manager_prefetch_metadata.py backend/tests/component/core/test_node_manager_delete.py` and confirm T007–T011 now pass with no regression

**Checkpoint**: FR-001, FR-002 and FR-008 complete — spec sub-task 1. Commit before proceeding.

### Recorded after the rebase onto `retire-agnostic-edges-ifc-2843-to-user-id`

- [X] Retirement closures recorded no actor. `RetireNodeAgnosticFieldsQuery`,
  `RetireBranchAgnosticFieldsQuery` and the shared `CLOSE_UNRETAINED_AGNOSTIC_FIELDS` fragment closed
  level-1 edges with `SET e.to = $at` and no `to_user_id`, unlike every other closure in the codebase —
  and unlike the edge contract `dev/knowledge/backend/database-schema.md` already documents. That left
  the recompute deriving `updated_by = None` for a default-branch delete of an aware node carrying an
  agnostic attribute, and the production read path (`NodeListGetInfoQuery`, `RelationshipGetPeerQuery`)
  reading the same null. **Fixed on the base**, not in this slice: `retire-agnostic-edges-ifc-2843-to-user-id`
  threads `user_id` through the closures, the `m078` repair migration, and the merge / rebase /
  branch-delete callers. This slice now consumes it.
- Discovered while fixing the above, and also resolved on the base: `closed_edge_count` on both batched
  closures read Neo4j's `properties_set`, which was right only while a closure stamped exactly one
  property, so stamping `to_user_id` doubled it (`m078`'s repair test: 27 expected, 54 reported). The
  base returns `count(edge_to_close)` from inside the `CALL … IN TRANSACTIONS` and sums it, counting
  edges rather than inferring them from a property arity.
- [X] **T002's wording was the defect, not the derivation.** The task specified restricting the `:Node`
  recompute to vertices holding an active level-1 `IS_PART_OF`. Implemented literally, that makes
  `recompute_vertex_metadata` return `None` for a node created and deleted entirely on one feature
  branch — which removes any way to assert that such a node correctly carries no level-1-derived
  metadata, and hides the create path stamping a vertex no level-1 write justifies, which is the
  defect FR-003 exists to fix. The derivation stays total and T002 now describes it.
- **Open — now FR-010, T077-T083.** The retirement closes level-1 edges on Node and field vertices
  without stamping their `updated_at` / `updated_by`. First recorded here as belonging to FR-004, which
  was wrong: FR-004 is scoped to the peer stamps in `core/query/relationship.py` and never touches the
  retirement queries. No cell covers it yet — the mismatch #2 delete-on-default cell asserts the Node
  vertex only.

---

## Phase 3: User Story 1 — Metadata reflects agnostic changes made from a branch (Priority: P1)

**Goal**: A branch-agnostic field changed on a branch-aware object from a feature branch advances the
default-branch `updated_at` / `updated_by`.

**Why here**: The under-set half of the gate fixed in Phase 2. The production change already landed in
T012; this phase proves it against the mismatches that have no core-schema instance.

**Independent test**: Update the agnostic attribute of the T005 test kind from a feature branch; read
on the default branch and assert both the new value and matching metadata.

### Tests for User Story 1

- [X] T017 [P] [US1] In `backend/tests/component/core/test_vertex_metadata_invariant.py`, add the mismatch #2 update cells using the T005 fixture: update the agnostic attribute on a feature branch, assert the default-branch read shows the new value **and** advanced `updated_at` / `updated_by`
- [ ] T018 [P] [US1] Add the mismatch #1 update cells (`BuiltinIPPrefix.resource_pool`, an agnostic relationship on an aware node)
- [ ] T019 [P] [US1] Add the mismatch #4 update cells (`CoreGenericRepository.internal_status`, `CoreRepository.commit`), asserting the metadata matches whichever level the **update** path writes — the create/update split for `local`-on-`agnostic` is a separate defect (spec Out of Scope), and the oracle is edge-derived so it is correct either way
- [ ] T020 [US1] Add the mixed-update edge case: touch both an aware and an agnostic field on an aware node from a branch in one save, assert the default-branch `updated_at` advances

### Implementation for User Story 1

- [ ] T021 [US1] Fix any gaps T017–T020 expose in the T012 gate — in particular confirm fields added by `_recompute_local_jinja2`, `_recompute_hfid` and `_recompute_display_label` reach the changelog and are considered by the gate
- [ ] T022 [US1] Run the full SC-001 Mechanism A set and confirm all 24 cells pass

**Checkpoint**: SC-001 Mechanism A complete for the update and delete operations.

---

## Phase 4: User Story 3 — Schema migrations set metadata for rows they publish globally (Priority: P1)

**Goal**: A schema migration on a feature branch that writes level-1 edges also writes the matching
vertex metadata — the only finding merge can never repair.

**Independent test**: Add a branch-agnostic attribute to a branch-aware kind on a feature branch;
assert the new Attribute vertex has `created_at` / `created_by` and the owning Node's `updated_at`
advanced, both read on the default branch.

### Tests for User Story 3

- [ ] T023 [P] [US3] Add SC-001 Mechanism B cells for `AttributeAddQuery` to `backend/tests/component/core/test_vertex_metadata_invariant.py`: mismatches #2, #3, #4 × {default, user} write branch. #1 is N/A — `attribute_add` never creates a relationship
- [ ] T024 [P] [US3] Add Mechanism B cells for `NodeDuplicateQuery`: mismatches #1–#4 × {default, user}
- [ ] T025 [P] [US3] Add Mechanism B cells for `NodeRemoveMigrationQueryIn` / `NodeRemoveMigrationQueryOut`: mismatches #1–#4 × {default, user}
- [ ] T026 [P] [US3] Add the FR-007 regression pin: a schema migration on a feature branch writing only `branch_level = 2` edges must write **no** vertex metadata
- [ ] T027 [US3] Add the FR-007 snapshot pin: after a user-branch migration writes global rows, assert `previous_updated_at` / `previous_updated_by` on the affected vertices are untouched (critique E3)

### Implementation for User Story 3

- [ ] T028 [US3] In `backend/infrahub/core/migrations/query/attribute_add.py::AttributeAddQuery`, carry `on_global_branch` and the matched `is_part_of_e` through the `WITH` clauses that currently drop them before the metadata `CALL`
- [ ] T029 [US3] In the same query, gate the Attribute vertex's metadata on `$set_metadata OR on_global_branch`, and the Node vertex's on that **and** `is_part_of_e.branch_level = 1`, so a node existing only on a branch is not stamped (plan D3)
- [ ] T030 [US3] In `backend/infrahub/core/migrations/query/node_duplicate.py::NodeDuplicateQuery`, return the matched `IS_PART_OF` edge from the existing `CALL (node)` subquery (which today returns only `node` and `is_active`), and gate the metadata on `$set_metadata OR <that edge is on `-global-`>`. Gating on the edge's *level* would be wrong for aware nodes, whose `IS_PART_OF` resolves to a level-1 default-branch edge while the migration writes new edges at level 2
- [ ] T031 [US3] In `backend/infrahub/core/migrations/schema/node_remove.py`, move the `WITH` that calls `_branch_from_existing` above each metadata `CALL` in `NodeRemoveMigrationQueryIn` and `NodeRemoveMigrationQueryOut`, then gate on `$set_metadata OR new_branch_level = 1`
- [ ] T032 [US3] Across T029–T031, keep the `previous_updated_at` / `previous_updated_by` `SET`s behind the **unchanged** `$set_metadata` scalar — only the `updated_at` / `updated_by` `SET`s move behind the new edge-level gate (spec FR-007, plan D3, critique E3)
- [ ] T033 [US3] Confirm `attribute_remove`, `attribute_rename`, `attribute_kind_update` and `node_relationship_remove` are left untouched — they write no `-global-` edges, so their `set_metadata` scalar is already self-consistent
- [ ] T034 [US3] Run `uv run pytest -x backend/tests/component/core/migrations/schema/` and confirm the existing suite passes **unchanged** — this is the regression pin for T031's reorder (critique E4)

**Checkpoint**: FR-007 complete — spec sub-task 2. SC-001 Mechanism B green. Commit before proceeding.

---

## Phase 5: Create-path and relationship-peer gating (Priority: P1/P2)

**Goal**: Close the two remaining write paths — node creation and relationship create/delete. Both
findings are latent or self-healing, so this phase is independently droppable without weakening
Phases 3–5 (critique P2).

### FR-003 — `NodeCreateAllQuery` per-field gating (spec sub-task 3)

- [ ] T035 [P] [US1] Add the SC-001 create cells for all four mismatches × {default, user} to `backend/tests/component/core/test_vertex_metadata_invariant.py`
- [ ] T036 [US1] In `backend/infrahub/core/query/node.py::NodeCreateAllQuery.query_init`, move the `created_at` / `created_by` / `updated_at` / `updated_by` properties out of the single `if self.branch.is_default or self.branch.is_global` guard on `attr_vertex_prop_str` / `rel_vertex_prop_str` and into the per-field data, so each vertex is stamped iff its own `branch_level` is 1
- [ ] T037 [US1] Confirm this gate follows the **create** path (`core/attribute.py::BaseAttribute.get_create_data`, which downgrades `local`-on-`agnostic` to level 1) rather than the update path used in T012 — the two genuinely disagree for mismatch #4 and each gate must mirror the edges its own path writes (plan D4, research R3)
- [ ] T038 [US1] Run the SC-001 create cells and confirm all 8 pass

### FR-004 — Relationship peer guard (spec sub-task 4)

- [ ] T039 [P] [US2] Add to `backend/tests/component/core/test_relationship_metadata.py`: create an agnostic relationship between two aware nodes that exist only on a feature branch, assert neither peer's vertex metadata changed
- [ ] T040 [P] [US2] Add the split-peer edge case: an agnostic relationship where one peer is on the default branch and the other only on a branch — assert the peer that is visible on the default branch is stamped and the other is not. A peer is stamped for a change to the relationship it holds, never for a *release* of one (see FR-010)
- [ ] T041 [US2] In `backend/infrahub/core/query/relationship.py`, replace the bare `SET s.updated_at` / `SET d.updated_at` in `RelationshipCreateQuery.query_init`, `RelationshipDeleteQuery.query_init` and `RelationshipDeleteAllQuery.query_init` with the guard already used by `RelationshipUpdatePropertyQuery`: require a level-1 active `IS_RELATED` **and** a level-1 active `IS_PART_OF` on the peer
- [ ] T042 [US2] Leave the `rl` (Relationship vertex) stamp in the delete queries on its existing gate — the relationship's own branch level is the correct gate for its own vertex, and applying the peer guard to it would reintroduce an under-set (plan D5, critique E2)
- [ ] T043 [US2] Run `EXPLAIN` on the three modified relationship queries per Constitution V and record the plans; confirm only the aware-peer case adds an `OPTIONAL MATCH`, since `RelationshipCreateQuery.add_source_match_to_query` already proves a level-1 `IS_PART_OF` for level-1 peers
- [ ] T044 [US2] Run `uv run pytest backend/tests/query_benchmark/ -k relationship` before and after T041 and record the delta for SC-003. A measurable regression means the guard is in the wrong place — revert this sub-task alone rather than weakening it

### FR-010 — Retirement writes vertex metadata (spec sub-task 8)

Releasing a branch-agnostic field closes its global edges at branch level 1, but stamps nothing.
`updated_at` / `updated_by` are to be set on the Node and field vertices whenever they take a global
write, so a release has to move them like any other level-1 write. Reachable today:
`BuiltinIPPrefix.resource_pool` and `InternalIPPrefixAvailable.resource_pool` are branch-agnostic
relationships on branch-aware kinds, so deleting the last prefix holding a pool value releases it at
level 1 and records nothing.

Four call sites close these edges and all four must agree, or the invariant holds on some deletion
paths and not others.

- [ ] T077 [P] [US2] Add cells to `backend/tests/component/core/test_vertex_metadata_invariant.py` for the final delete of a branch-aware object holding an agnostic relationship: assert the deleted object's Node vertex **and** its Relationship vertex match the recompute afterwards, and that the peer on the far side does not move
- [ ] T078 [US2] In `backend/infrahub/core/query/node_agnostic_retirement.py`, stamp `updated_at` / `updated_by` on the field vertices the run closes and on the Node vertices owning them. **Co-write `previous_updated_at` / `previous_updated_by`**: this query runs inside the merge window at the merge `$at` (`DiffMerger._retire_agnostic_fields_of_deleted_nodes`), and a merge-window writer that bumps `updated_at` without the snapshot makes the range rollback restore garbage — see `dev/knowledge/backend/merge-failure-recovery.md`
- [ ] T079 [US2] Same for `backend/infrahub/core/query/branch_agnostic_retirement.py`, whose writes are batched `IN TRANSACTIONS`, so the stamp has to happen inside the same `CALL` as the edge close
- [ ] T080 [US2] Same for the shared `CLOSE_UNRETAINED_AGNOSTIC_FIELDS` fragment in `backend/infrahub/core/query/agnostic_field_closure.py`; both consumers already carry `$user_id` in their params
- [ ] T081 [US2] Restrict the `:Node` arm of `recompute_vertex_metadata` to links the vertex owns. It matches `(v)-[link]-(field)` undirected, so a peer on the far side of a retired relationship currently gets a recomputed `updated_at` the write path is not meant to produce
- [ ] T082 [US2] Decide whether the repair migration must back-date the same stamps for graphs whose edges were closed before this landed, and record the answer — it back-dates closures to the moment reachability was lost, so a stamp would have to use that time, not the upgrade's. Overlaps FR-005
- [ ] T083 [US2] Run `EXPLAIN` on the modified retirement queries per Constitution V and record the plans
- [ ] T084 [P] [US2] Widen `branch_metadata_fingerprint` in `backend/tests/helpers/vertex_metadata.py` to include the vertices a branch reaches only over `-global-` edges. It matches edges carrying the requested branch name, so a rollback that changes the metadata of a branch-agnostic field is invisible to it — which is exactly the metadata a retirement stamp will start moving
- [ ] T085 [P] [US2] Widen `branch_edge_fingerprint` in the same module to carry `branch_level`, `from_user_id` and `to_user_id`. It keys on endpoints, timestamps and status only, so two snapshots compare equal across a change to an edge's level or to who opened or closed it, and the retirement stamps `to_user_id`

**Checkpoint**: FR-003, FR-004 and FR-010 complete — spec sub-tasks 3, 4 and 8. Commit each separately.

---

## Phase 6: User Story 4 — Existing graphs are repaired (Priority: P2) — OPTIONAL

**Optional**: this phase repairs graphs *already* damaged by the defect. Phases 2–5 make every write
correct going forward and are complete without it, so this phase can be deferred to a follow-up ticket
or dropped without weakening any of them. Nothing in Phases 2–5, 7 or 8 depends on it.

Deferring it means shipping the fix while leaving existing wrong values in place — including the
Attribute vertices F6 leaves with permanently NULL metadata, which no later write repairs. That is a
scoping decision, not a correctness one.

**Goal**: A repair migration brings every already-wrong vertex into agreement with its level-1 edges,
including the permanently-NULL attributes F6 leaves that no later write repairs.

**Independent test**: Seed a graph with known-wrong metadata, run the migration, assert every affected
vertex matches the recompute; run it again and assert zero changes.

### Tests for User Story 4

- [ ] T045 [P] [US4] Add `backend/tests/component/core/migrations/graph/test_repair_vertex_metadata.py`, seeding both damage shapes: NULL metadata on globally-published attributes (F6) and advanced `updated_at` from an invisible change (F1b)
- [ ] T046 [P] [US4] Assert every affected vertex equals `recompute_vertex_metadata()` after one run, covering `:Node`, `:Attribute` and `:Relationship`
- [ ] T047 [US4] Add the SC-002 idempotency assertion: a second run reports **zero** changed vertices
- [ ] T048 [P] [US4] Assert the migration does not touch `previous_updated_at` / `previous_updated_by` — snapshotting them would break idempotency and corrupt the merge-rollback pair that owns them
- [ ] T049 [P] [US4] Assert a migrated-out twin and a node deleted on the default branch are **not** recompute targets, while the surviving twin's `created_at` still reflects the uuid-wide `min()`
- [ ] T050 [US4] Assert the reported per-label changed counts match the vertices actually changed (spec FR-005, critique P5)

### Implementation for User Story 4

- [ ] T051 [US4] Create `backend/infrahub/core/migrations/graph/m079_repair_vertex_metadata.py`, following the m050 structure: three `Query` subclasses ordered Attribute, then Relationship, then Node, batched `IN TRANSACTIONS`
- [ ] T052 [US4] Implement the recompute in Cypher matching `contracts/vertex-metadata-invariant.md`, with m050's `IS NULL` guard **dropped** so wrong values are corrected as well as NULLs filled
- [ ] T053 [US4] Extend the derivation to `created_by` / `updated_by`, taking the `from_user_id` (or `to_user_id`, where a `to` supplied the winning timestamp) of the edge that produced each timestamp — m050 never set these, and SC-001 asserts on them
- [ ] T054 [US4] Scope the sweep with `field.branch_support <> n.branch_support`, read from properties already stored on the vertices — no schema load, since a graph migration may run against a database predating the current models (research R5)
- [ ] T055 [US4] Restrict `:Node` targets to vertices with an active level-1 `IS_PART_OF`, keeping the uuid-wide `min(from)` inside the `created_at` derivation
- [ ] T056 [US4] Return the count of changed vertices per label from the migration result
- [ ] T057 [US4] Register the migration in the graph-migration list and set its `minimum_version` to the preceding migration's number
- [ ] T058 [US4] Run `uv run pytest -x backend/tests/component/core/migrations/graph/` and confirm the new suite and the existing m050 suite both pass

**Checkpoint**: FR-005 complete — spec sub-task 5. SC-002 green.

---

## Phase 7: User Story 5 — A failed merge leaves no orphaned metadata (Priority: P2)

**Goal**: A rollback of a failed merge reverses the rows the merge published on `-global-` and restores
the vertex metadata they bumped — today it reaches neither.

**Independent test**: Merge a schema change that adds a branch-agnostic attribute to a branch-aware
kind, force the merge to fail, and assert the rollback restored both the edges and the metadata.

### Tests for User Story 5

- [ ] T059 [P] [US5] In `backend/tests/component/core/merge/test_recovery_rollback.py`, add the SC-004 add-case: a merge into the default branch whose schema portion adds a branch-agnostic attribute to a branch-aware kind, forced to fail; assert the `-global-` edges are reversed and every bumped vertex is back to its pre-merge metadata
- [ ] T060 [P] [US5] Add the SC-004 remove-case: the same merge removing an agnostic field instead of adding one
- [ ] T061 [P] [US5] In `backend/tests/component/core/test_rollback.py`, add the over-reach pin: an unrelated **third** branch's `-global-` write inside the rollback window must **survive** a `SINCE_TIMESTAMP` rollback of the merge. This is the pin for the one real hazard FR-009 introduces — the merge write-block leaves every branch but the source and the default free to write globally

### Implementation for User Story 5

- [ ] T062 [US5] **Before writing any query**, verify that the merge's schema-migration portion stamps its `-global-` writes at the merge timestamp. FR-009's safety argument depends on it; if it does not hold, stop and revisit FR-009's scope rather than widening the query anyway
- [ ] T063 [US5] In `backend/infrahub/core/query/rollback.py::RollbackReopenEdgesQuery`, widen the opening `MATCH (src)-[edge {branch: $target_branch}]->(dst)` to match the target branch **or** `-global-`, and only when the target branch is the default branch
- [ ] T064 [US5] Apply exact-timestamp semantics to the `-global-` half **regardless of the caller's `RollbackScope`**, keeping the caller's scope for the target-branch half. `SINCE_TIMESTAMP`'s ownership argument does not hold for `-global-`, which `core/branch/status_checker.py::BranchStatusChecker._raise_if_blocked` leaves writable by every branch except the merge's source and the default (plan D6b, critique E12)
- [ ] T065 [US5] Apply the same widening and the same exact-timestamp rule to `backend/infrahub/core/query/rollback.py::RollbackDeleteEdgesQuery`
- [ ] T066 [US5] Leave the two-pass reopen-then-delete ordering and `_render_restore_metadata_pipeline` unchanged, and leave the **target-branch** half's timestamp window and scope operator exactly as they are. Only the branch set widens, and only the `-global-` half's operator is pinned to exact-match (plan D6b, research R10)
- [ ] T067 [US5] Confirm the existing guard in `backend/infrahub/core/rollback.py::GraphRollbacker.rollback` still carries the safety argument: it raises unless the target branch is default or global, so `-global-` is only ever added where a merge could have made level-1 global writes
- [ ] T068 [US5] Run `uv run pytest -x backend/tests/component/core/test_rollback.py backend/tests/component/core/merge/`

**Checkpoint**: FR-009 complete — spec sub-task 6. SC-004 green.

---

## Phase 8: Documentation, Polish & Cross-Cutting

- [ ] T069 [P] In `dev/knowledge/backend/database-schema.md`, replace *"When added to default/global branch"* / *"When last updated on default/global branch"* in the vertex-property tables with the level-1-edge invariant from `contracts/vertex-metadata-invariant.md`. This wording is the buggy proxy stated as fact and is the likely origin of every site that implemented it (FR-006, spec sub-task 7)
- [ ] T070 [P] In the same document, note the cross-branch side effect Constitution II requires be documented: a write on a user branch can move default-branch metadata whenever the field's branch support differs from its node's
- [ ] T071 [P] Add a Towncrier changelog fragment under `changelog/` — wrong `updated_at` / `updated_by` on the default branch is user-visible (use the `creating-changelog-entries` skill)
- [ ] T072 [P] File a follow-up issue for the `local`-on-`agnostic` create/update split: `get_create_data` downgrades a `LOCAL` attribute on an `AGNOSTIC` node to level 1 while `get_branch_based_on_support_type` does not, so mismatch #4 is created at level 1 and updated at level 2 and the default branch keeps showing the creation-time value (spec Out of Scope)
- [ ] T073 [P] File a follow-up issue for `attribute_kind_update`, `attribute_rename` and `node_relationship_remove`: applied to an agnostic field they write level-2 edges for data living at level 1, so the change is invisible on the default branch where the data lives (spec Out of Scope)
- [ ] T074 Run `uv run invoke format` and `uv run invoke lint`
- [ ] T075 Run the full metadata surface per `quickstart.md`: `uv run pytest -x backend/tests/component/core/test_relationship_metadata.py backend/tests/component/core/test_node_manager_prefetch_metadata.py backend/tests/component/core/test_vertex_metadata_invariant.py backend/tests/component/core/migrations/`
- [ ] T076 Run `/pre-ci` before pushing

---

## Dependencies

```text
Phase 1 (Foundational: shared recompute oracle) ← BLOCKS EVERYTHING
    ↓
Phase 2 (US2: FR-001 + FR-002 + FR-008) ← MVP; also delivers US1's production change
    ↓
Phase 3 (US1: proves the same gate on the non-core mismatches)
    ↓
Phase 4 (US3: FR-007) ← highest severity remaining
    ↓
Phase 5 (FR-003, FR-004) ← both independently droppable
    ↓
Phase 6 (US4: FR-005) ← OPTIONAL; if taken, after 2–5 so the repair is not chasing a moving
    ↓                    definition of correct
Phase 7 (US5: FR-009) ← independent of 2–6; touches only the rollback path
    ↓
Phase 8 (FR-006, changelog, follow-ups)
```

**Hard dependencies**:

- T001–T004 block every test task — the oracle must exist first
- T005 blocks T017 and T023 (mismatch #2 has no live fixture)
- T012 and T013 close the update-path pins T007–T009; T014 and T015 close the FR-008 delete pins T010 and T011; all four block T016
- T028 blocks T029; T031 blocks T034
- T051 blocks T052–T057; all of them block T058
- T063–T065 block T068; T062 gates all of them — if its verification fails, Phase 7 stops rather than proceeding
- Phase 6, if taken, should follow Phases 2–5 so the repair migration is not chasing a definition of correct that is still moving

**Optional phase**: Phase 6 (US4) repairs already-damaged graphs. No other phase depends on it, and
Phases 2–5 are correct and shippable without it. Skipping it leaves existing wrong values — including
F6's permanently-NULL Attribute vertices — in place.

**Independent phases**: Phase 7 (US5) touches only `backend/infrahub/core/query/rollback.py` and the
rollback test suites. It shares no file with Phases 2–6 and can be developed in parallel with them or
deferred without affecting them.

**Soft ordering**: Phases 4 and 5 touch disjoint files and could run in parallel, but the spec stages
them as separate commits in this order by severity.

---

## Parallel Execution Examples

**Phase 1**: T003 and T005 are independent of T001/T002 and of each other.

**Phase 2**: T006–T011 write to the same new test file — write T006's skeleton first, then T007, T008,
T010 and T011 in parallel. T009 depends on T003.

**Phase 4**: T023–T027 target different migration queries and pins, and can be written in parallel;
T029, T030 and T031 likewise touch three different modules.

**Phase 6**: T046, T048, T049 and T050 are independent assertions over the graph T045 seeds.

**Phase 7**: T059, T060 and T061 are independent. T062 must complete before any of T063–T065, which
touch two classes in one file.

**Phase 8**: T069–T073 are all independent.

---

## Implementation Strategy

**MVP scope**: Phases 1–2. That delivers the FR-001 / FR-002 / FR-008 gate fix across the update and
delete paths, closing both live core-schema defects, and is independently shippable.

**Incremental delivery**: each checkpoint is a commit, matching the spec's seven-part sub-task
breakdown. The staging is deliberate — Phase 5's FR-004 is isolated so it can be reverted alone if
SC-003 shows a real cost, and Phase 5 as a whole can be dropped without weakening Phases 2–4, since
both its findings are latent or self-healing. Phase 6 is optional outright.

**Gates before merge**: SC-001 (Phases 2–5) and SC-004 (Phase 7) are release gates. SC-002 gates
Phase 6 **only if that phase is taken** — spec.md still lists FR-005 as a requirement and SC-002 as a
release gate, so deferring Phase 6 means deferring FR-005 to a follow-up ticket rather than dropping
it silently. SC-003 (T044) is a check, not a gate — but a measurable regression is evidence the guard
is misplaced, not a reason to lower the bar.

**Migration number**: Phase 6 creates `m079_repair_vertex_metadata.py`. The base carries
`m077_delete_orphaned_account_children` and `m078_retire_agnostic_property_edges` at `GRAPH_VERSION`
78 — 077 was briefly claimed by both until the base renumbered the second to 078. Re-check the highest
number before merge; a migration landing on the base first forces a renumber (the
`rebase-current-branch` skill handles this).
