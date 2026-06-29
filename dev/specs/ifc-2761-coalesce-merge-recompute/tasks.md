---
description: "Task list for: Coalesce merge and rebase recompute fan-out"
---

# Tasks: Coalesce merge and rebase recompute fan-out

**Input**: Design documents from `specs/ifc-2761-coalesce-merge-recompute/`
**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/coalesced-recompute.md, quickstart.md

**Tests**: Included. Correctness is the gate (FR-002 / SC-003: no stale value, verified against a from-scratch recompute), so component and integration_docker tests are first-class, not optional.

**Branch**: `coalesce-merge-recompute-ifc-2761`

## Story → delivery mapping

The shippable increments are by **capability**, not strictly by user story: the perf win (US1) and the correctness guarantee (US2) are both delivered by the same coalesced merge path, on top of a shared coordinator and the new display/HFID derivers.

- **US1** (P1) — fast return to service after a large merge (perf)
- **US2** (P1) — no stale derived values after merge/rebase (correctness)
- **US3** (P2) — same improvement for rebase
- **US4** (P3) — no regression for small changes

## Conventions

- Per `dev/rules/code-doc-style.md`: no spec IDs (IFC-2761, FR-xxx) in source or test names or docstrings.
- Keyword arguments; type hints; frozen dataclasses for the metric/selection records (Constitution III). No mocks — adapter pattern; the real stack for correctness/perf (Constitution IV).
- File paths assume the branch has been **rebased onto current develop** (T001); the integration points (`core/merge/post_merge.py`, the Jinja2 loop) live there, not on this older spec branch.
- `[P]` = parallelizable (different files, no incomplete dependency).
- Behavior-preserving: identical final derived values; only the work changes.

---

## Phase 1: Setup

- [X] T001 Rebased `coalesce-merge-recompute-ifc-2761` onto current develop (`f1e69c9dd`). The integration points are now real (`backend/infrahub/core/merge/post_merge.py`, the per-family triggers). No conflicts. The harness builds and the counting layer passes on develop after one adaptation: develop's merge/rebase path reads a Redis-backed write blocker, so the counting driver injects the in-memory cache adapter. The stable→develop merge is identical to develop across the merge/recompute area (see research R9).
- [X] T002 [P] Spike (gates T009/T012): mapped consumers of the per-node `NodeMutatedEvent`s. Decision = keep emission, stamp a merge/rebase-origin label, and add a negative match to only the three coalesced families' triggers; user action rules and webhooks consume the same events and must keep firing. Recorded in `research.md` (R3).
- [X] T003 [P] Spike (gates T019): traced source-vs-destination reader redundancy. Decision = recompute-all on the correct branch; the skip optimization is deferred and likely not worth it. Recorded in `research.md` (R5).
- [X] T004 [P] Pinned the reuse points in `reuse-points.md`: the computed-attribute data-change deriver (`get_impacted_jinja2_targets`, the right reuse rather than the schema-change `RecomputeScoper`), the display-label/HFID metadata facades and their per-family difference, the reader `@filters` query and union-query coalescing, the per-family process/update flows plus batching, the change set at the emission points, and the no-double-processing precedent.

---

## Phase 2: Foundational — derivers, coordinator, suppression (BLOCKING)

**Purpose**: the shared selection + submission machinery every user story depends on. **Blocks Phases 3 and 4.**

- [X] T005 [P] Built the display-label deriver in `backend/infrahub/display_labels/scoping.py` (`derive_display_label_targets`), reading `get_template_nodes` / `get_related_trigger_nodes`; maps a changed `(kind, fields)` to self and cross-relationship targets with their reader filter.
- [X] T006 [P] Built the human-friendly-id deriver in `backend/infrahub/hfid/scoping.py` (`derive_hfid_targets`); a self-only HFID has no related-trigger entry, so it never appears for a related-node change and only recomputes on its own creation. No special-casing; the metadata encodes the difference.
- [X] T007 Implemented `build_coalesced_recompute(*, changes, schema_branch, branch)` in `backend/infrahub/core/merge/recompute_coalescing.py`: records (`MergeChange`, `ChangeSignature`, `AffectedTarget`, `CoalescedRecompute`), groups by signature, reuses `get_impacted_jinja2_targets` plus the two derivers, dedups to the affected-target set with reader lookups unioned, tags the branch, marks precise vs bounded fallback. Pure, no DB/Prefect.
- [X] T008 Implemented the submission layer in `core/merge/recompute_coalescing.py`: `plan_coalesced_submissions` (pure) flattens the coalesced targets into one submission per `(family, target, source_kind)` carrying the union of changed ids, and `submit_coalesced_recompute` runs each through the existing per-family process flow (`computed_attribute_process_jinja2` / `display-label-process-jinja2` / `hfid-process`). The three flows gained a backward-compatible `object_ids` union parameter (the live single-id path is unchanged; `object_id` reordered to a keyword default, no positional callers exist), and their query renders accept a list filter. Component-tested via the workflow recorder (one submission per target, union ids, no per-node fan-out); end-to-end execution is integration_docker (T011).
- [X] T009 Implemented the no-double-processing mechanism (T002 decision): added an always-present `infrahub.node.origin` event label (`events/constants.py`, `events/node_action.py`, `events/models.py`) defaulting to `live`; stamped `merge`/`rebase` at the two build sites (`core/merge/post_merge.py`, `core/branch/tasks.py`); and added a negative match excluding replayed origins to the three coalesced families' trigger builders only (`computed_attribute/models.py` Jinja2, `display_labels/models.py`, `hfid/models.py`). Python-transform, profiles, action rules, and webhooks are untouched. Unit-tested (event label + the three triggers); end-to-end suppression is integration_docker (T011). The default-to-live label is required because a negative match never matches an absent label.

**Checkpoint**: derivers + coordinator + suppression ready; merge and rebase can integrate.

---

## Phase 3: Merge — perf (US1) + correctness (US2) 🎯 MVP

**Goal**: the merge path computes one coalesced recompute on the destination branch; recompute scales with affected derived values and no value is left stale.

**Independent Test**: a real merge on the full stack leaves every affected derived value equal to a from-scratch recompute, and the harness shows the recompute job count bounded by affected derived values with a shorter trailing window.

- [X] T010 [P] [US2] Component tests in `backend/tests/component/merge_recompute_coalescing/test_build_coalesced_recompute.py` for `build_coalesced_recompute`: cross-node update (coalesced to one union lookup), same-node update (no async targets), creation (all three families), reader-of-deleted-node, dedup, per-family scope (HFID no peer fan-out), bounded fallback. Real profile schema, no worker. 7 passing.
- [ ] T011 [P] [US2] integration_docker correctness test `backend/tests/integration_docker/test_merge_recompute_coalescing.py`: after a real merge, every affected computed attribute / display label / HFID equals a from-scratch recompute (cross-node, transitive, creation, deletion), on the destination branch.
- [X] T012 [US2] Integrated the coordinator into the merge post-process in `backend/infrahub/core/merge/post_merge.py`: `dispatch_events` builds `MergeChange`s from the diff changelog, runs `build_coalesced_recompute` on the destination branch, and submits via `submit_coalesced_recompute`. The per-node cross-node fan-out for the three families is stopped by T009's suppression; other consumers still get the events. Component-tested with a real cross-node merge: one computed + one display submission over the union of changed peers, no HFID fan-out.
- [ ] T013 [US1] Run the profiling harness before/after for merge at small/medium/large; confirm recompute jobs are bounded by affected derived values and the trailing window is cut versus the baseline; merged data identical.

**Checkpoint**: merge is correct and faster — shippable MVP.

---

## Phase 4: Rebase (US3)

**Goal**: rebase gets the same coalesced recompute, on the user branch.

- [X] T014 [US3] Integrated the coordinator into the rebase flow in `backend/infrahub/core/branch/tasks.py`: `rebase_branch` builds `MergeChange`s from the changelog and submits the coalesced recompute on the user branch (the per-node fan-out for the three families is suppressed by T009). Component-tested with a real cross-node rebase: one computed + one display submission over the union, on the user branch, no HFID fan-out.
- [ ] T015 [P] [US3] integration_docker correctness test for rebase (same from-scratch-recompute oracle, on the user branch).
- [ ] T016 [US3] Run the harness for rebase; confirm the reduction and correctness parity with merge.

**Checkpoint**: merge and rebase both coalesced and correct.

---

## Phase 5: Polish & cross-cutting

- [ ] T017 [US4] No-regression: run the harness at the small scale before/after; confirm small merges are no slower within tolerance.
- [ ] T018 [P] Chunk the full-branch Jinja2 recompute loop (one workflow per node today, no chunking) to match the Python/transform paths.
- [ ] T019 Redundancy skip (T003 decision: deferred): keep recompute-all as the default; the source-branch skip is not implemented in this increment because proving a reader safe needs a source-vs-destination branch query plus a conflict-resolution check whose cost rivals the recompute, with the best-effort source fan-out as a correctness risk. Revisit only if the harness shows reader overlap is a measured hotspot after coalescing. Never under-recompute.
- [ ] T020 Confirm the existing recompute tests stay green: `backend/tests/integration_docker/test_computed_attributes.py`, `test_display_label_backfill.py`.
- [X] T021 [P] Added the changelog fragment `changelog/+ifc-2761-coalesce-merge-recompute.changed.md` (user-facing performance change), following the project's plain-prose convention. The optional `dev/knowledge/backend/` note is not added yet.
- [X] T022 Ran `ruff format` and `ruff check` (clean) and `mypy` (clean) across all 14 new and changed source files plus the test files. The full `uv run invoke lint` / `docs.format` sweep is deferred to `/pre-ci` (T023); `markdownlint-cli2` is not installed locally.
- [ ] T023 Run `/pre-ci` before opening the PR; coordinate with IFC-2758 (merge emits no schema-updated event) so the two changes do not double-process.

---

## Dependencies & Execution Order

### Phase dependencies

- **Phase 1 (Setup)**: T001 (rebase) first; T002 and T003 are spikes that gate design (T002 → T009/T012; T003 → T019).
- **Phase 2 (Foundational)**: after Phase 1; **blocks Phases 3 and 4**.
- **Phase 3 (Merge)**: after Phase 2. The MVP.
- **Phase 4 (Rebase)**: after Phase 2; shares the coordinator with Phase 3 — can follow merge or run in parallel once the coordinator is stable.
- **Phase 5 (Polish)**: after Phases 3 and 4.

### Within a phase

- Foundational: T005 and T006 are parallel (different families); T007 depends on T005/T006; T008 depends on T007; T009 depends on the T002 decision.
- Merge: T010/T011 (tests) before/with T012 (implementation) → T013 (perf).
- Rebase: T014 → T015 → T016.

### Parallel opportunities

- T002, T003, T004 are parallel spikes/notes.
- T005 and T006 are parallel (display vs HFID).
- T010 and T011 are parallel (component vs integration_docker).
- Once Phase 2 lands, Phase 3 and Phase 4 can proceed in parallel.
- T018 and T021 are parallel.

---

## Implementation Strategy

### MVP first

1. Phase 1 (rebase + the two spikes) → Phase 2 (derivers + coordinator + suppression).
2. Phase 3 (merge) → **STOP & VALIDATE**: correctness against a full recompute, and the harness reduction. This is the shippable MVP and covers US1 + US2.
3. Then Phase 4 (rebase), then Phase 5 (polish).

### Risk notes

- **T002 / T009 (no double processing)** is the correctness-critical decision; resolve the event-consumer question before integrating.
- **T003 / T019 (source-branch redundancy)** is a perf optimization, not a correctness requirement; default to recompute-all and only skip with the trace.
- **T012 / T014 branch difference**: merge recomputes on the destination branch, rebase on the user branch — do not conflate.
- A missed dependency is a silent stale value; build on the reused/derived-to-pattern derivation, never a parallel ad-hoc selection.

---

## Notes

- `[Story]` labels are for traceability; the shippable increments are the phases.
- Commit after each task or logical group; do not force-push the branch.
- No edits to generated files; no new external dependencies; reuse the existing scoping / per-family flows / batch infrastructure.
