---
description: "Task list for: Profile merge and rebase recompute cost at scale"
---

# Tasks: Profile merge and rebase recompute cost at scale

**Input**: Design documents from `specs/ifc-2761-merge-recompute-profile/`
**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/profile-harness.md, quickstart.md

**Tests**: This feature *is* measurement/test code — the harness is the deliverable. There are no separate "tests for the feature"; verification is the determinism guard (T012), the no-behavior-change guard (T013), and the existing-recompute regression guard (T021).

**Branch**: `merge-recompute-profile-ifc-2761`

## Story → delivery mapping

The shippable increments are by **layer**, not by user story, because US1 spans both layers (it needs counts *and* wall-clock):

- **Counting layer** (deterministic, graph-DB only, no worker) — delivers US1 (event cardinality), US2 (growth), US3 (deterministic reproducibility). This is the MVP and likely answers the cardinality question on its own.
- **Timing layer** (full stack + real worker, gated) — delivers US1 (wall-clock attribution + executed-recompute count + degraded-window distinction).

Tasks carry the `[US#]` they primarily serve.

- **US1** (P1) — attribute cost across cost centers
- **US2** (P1) — characterize growth across scales
- **US3** (P2) — reproducible, retained harness

## Conventions

- Per `dev/rules/code-doc-style.md`: **no spec IDs (IFC-2761, FR-xxx) in source or test names or docstrings.**
- Keyword arguments for all calls; type hints; frozen dataclasses for the metric records (Constitution III). No mocks — use the adapter pattern (`BusRecorder`, `WorkflowRecorder`) and the real stack for timing (Constitution IV).
- **Vocabulary** (keep distinct in code and report): *emitted events* = counted in the counting layer; *executed recompute runs* = observed in the timing layer via the workflow engine's run records; *derived expected recompute* = optional in-process prediction. The counting layer does **not** observe Prefect-submitted recompute jobs — on the merge path they are dispatched by automations from the emitted events, not by the merge flow.
- `[P]` = parallelizable (different files, no incomplete dependency).
- Measurement only: no change to recompute behavior, events, or automations.

---

## Phase 1: Setup

- [ ] T001 Pin the reuse points the harness depends on (no production code): confirm exact import paths and signatures for the scale stagers (`backend/tests/scale/common/stagers.py`), SDK batch creation (`client.create_batch()`), `BusRecorder` (`backend/tests/adapters/message_bus.py`), `WorkflowRecorder` (`backend/tests/adapters/workflow.py`), the integration_docker recompute-wait/flow-run query helpers (`backend/tests/integration_docker/test_display_label_backfill.py`, `backend/infrahub/task_manager/task.py`), and the `merge_branch`/`rebase_branch` entry points. Also confirm whether `backend/tests/scale/` is collected by CI; if it is not, decide where the deterministic counting test (T012) must live so it actually guards in CI. Record findings in a short note in the feature dir to unblock the OPEN research items.

---

## Phase 2: Foundational — shared dataset & metrics (BLOCKING)

**Purpose**: the synthetic dataset and metric records both layers depend on. **Blocks Phases 3 and 4.**

- [ ] T002 [P] Create the metric records as frozen dataclasses in `backend/tests/scale/merge_recompute/metrics.py`: `RecomputeCounts` (node events by type [primary]; optional derived `expected_recompute` by family), `CostCenterTiming` (incl. executed `recompute_flow_runs` and best-effort `db_commit_s`), `ProfileRun`, `FindingsReport` (per data-model.md).
- [ ] T003 Create `build_profile_schema()` in `backend/tests/scale/merge_recompute/dataset.py`: one or more kinds carrying a computed attribute, a display label, and an HFID, plus a relationship peer read so cross-node automations are exercised (resolves research R3). Reuse/extend an existing fixture rather than authoring a new schema from scratch.
- [ ] T004 Create `seed_branch(*, db, branch, changed_nodes)` in `backend/tests/scale/merge_recompute/dataset.py`: bulk-create and then mutate `changed_nodes` nodes on a branch so they appear in the merge diff, reusing the scale stagers / SDK batch; return the ids/counts needed for assertions.
- [ ] T005 [P] Define the shared scale set (small/medium/large, about 10/100/1000+ changed nodes) as a parametrize source in `backend/tests/scale/merge_recompute/` so both layers run the same scales.

**Checkpoint**: dataset builder + seeding + metric records ready; both layers can build on them.

---

## Phase 3: Counting layer (Priority: P1) 🎯 MVP

**Goal**: deterministic counts of node events emitted (the fan-out cardinality) across scales, with growth classified — without running a worker. Recompute *execution* counts come from the timing layer (Phase 4), not here.

**Independent Test**: run `backend/tests/scale/merge_recompute/test_merge_recompute_counts.py` and get exact node-event counts per scale plus a linear/super-linear classification, reproducibly.

**Covers**: US1 (event cardinality), US2 (growth), US3 (deterministic reproducibility).

- [ ] T006 [US1] Implement the counting driver in `backend/tests/scale/merge_recompute/test_merge_recompute_counts.py`: inject `BusRecorder` (and `WorkflowRecorder` only to neutralize the merge's own orchestration workflows), run a real `merge_branch` over a seeded branch, and collect `RecomputeCounts` — node events by type, the primary signal. State explicitly in the code/report that per-node derived-value recompute on merge is dispatched by Prefect automations from the emitted events, not synchronously by the merge flow, so it is NOT counted here — the executed count comes from the timing layer (T015). Choose and document the event-recording tap (resolves research R4).
- [ ] T007 [P] [US1] Optionally compute a `derived expected-recompute` count by applying the dependency/automation match logic to the emitted events in-process (per family: computed attribute, display label, HFID); populate `RecomputeCounts.expected_recompute`. If deferred, leave it zero and note it. This is the in-process stand-in for the executed count when the worker is not running.
- [ ] T008 [US1] Extend the counting driver to also profile `rebase_branch` over an equivalent dataset (edge: merge vs rebase), recording counts for both operations.
- [ ] T009 [US2] Parametrize the counting layer across the shared scale set (T005); produce one `RecomputeCounts` per scale per operation.
- [ ] T010 [US2] Compute and record the growth classification (linear vs super-linear vs flat) of node events (and any derived expected-recompute) against `changed_nodes` across the scales.
- [ ] T011 [US1] Assert the no-behavior-change invariant: the derived values produced by the merge are identical with the harness wiring present vs absent (measurement does not alter output).
- [ ] T012 [US3] Assert determinism: the same scale yields identical counts across repeated runs; pin expected counts per scale as a regression guard. Ensure this test runs where CI collects it (per the T001 finding); relocate if `tests/scale/` is not in CI.
- [ ] T013 [US1] Run the counting layer green at all three scales for both merge and rebase.

**Checkpoint**: counting layer answers the cardinality + growth question deterministically — shippable MVP on its own.

---

## Phase 4: Timing layer (Priority: P1)

**Goal**: real wall-clock attribution across cost centers on the full stack for **merge** (the headline path), separating in-transaction cost from the trailing recompute window, and producing the authoritative executed-recompute count. Rebase wall-clock is deferred (counting layer covers rebase cardinality); add it only if merge timing proves insufficient.

**Independent Test**: run `backend/tests/integration_docker/test_merge_recompute_timing.py` on the full stack and get a `CostCenterTiming` with the dominant cost center identifiable.

**Covers**: US1 (wall-clock + executed recompute count).

- [ ] T014 [US1] Implement the timing driver in `backend/tests/integration_docker/test_merge_recompute_timing.py`: drive the merge on the full distributed stack with a real task worker, seed via the shared dataset, and measure the merge critical path with a monotonic clock.
- [ ] T015 [US1] Count and time the executed recompute: query Prefect flow runs created in the merge's window, filtered to this run's recompute deployments and branch/related-node tags; record `recompute_flow_runs` (the authoritative FR-004 count), `recompute_total_s`, and `recompute_window_s` (first start to last finish). Resolves research R6 — precise per-run attribution; the riskiest measurement step, validate the filter before trusting numbers.
- [ ] T016 [US1] Isolate schema-migration cost by differencing a schema-changing merge against a data-only merge of equal size (edge F); record `schema_migration_s`.
- [ ] T017 [US1] Attribute the database commit / merge internals best-effort (DB query profiler or lock-duration metric); populate `db_commit_s`, allowing `None` when finer attribution is unavailable.
- [ ] T018 [US1] Gate the timing layer like the intensive benchmarks (explicit label + long timeout); report timings with a stated tolerance and assert no hard wall-clock thresholds.
- [ ] T019 [US1] Run the timing layer at the medium (~100 changed nodes) scale on the full stack; capture `CostCenterTiming` and confirm the dominant cost center is identifiable.

**Checkpoint**: wall-clock attribution, executed-recompute count, and the degraded-instance window are measured for merge.

---

## Phase 5: Findings & cross-cutting

- [ ] T020 [US3] Aggregate the runs into a `FindingsReport` and write `dev/specs/ifc-2761-merge-recompute-profile/findings.md`: per-scale table (event counts + timings), the dominant cost center, the growth classification, and the tolerance note. This is the deliverable that gates the coalescing redesign. An interim version MAY be written from the counting layer alone.
- [ ] T021 Confirm the existing recompute tests stay green (no behavior disturbed): `backend/tests/integration_docker/test_computed_attributes.py` and `backend/tests/integration_docker/test_display_label_backfill.py`.
- [ ] T022 [P] Run `uv run invoke format` and `uv run invoke lint`; resolve `mypy` on all new files.
- [ ] T023 Run `/pre-ci` (`dev/commands/pre-ci.md`). Confirm whether a changelog fragment is required — this is test/measurement-only with no user-facing change, so likely not; verify against project convention. Optionally add a brief `dev/knowledge/backend/` pointer on how to run the profile, or rely on quickstart.md (not blocking).

---

## Dependencies & Execution Order

### Phase dependencies

- **Phase 1 (Setup)**: immediate.
- **Phase 2 (Foundational)**: after Phase 1; **blocks Phases 3 and 4**.
- **Phase 3 (Counting)**: after Phase 2. Independently shippable (MVP).
- **Phase 4 (Timing)**: after Phase 2. Independent of Phase 3 (different tree/stack) but shares the dataset/metrics — can run in parallel with Phase 3 once foundation lands.
- **Phase 5 (Findings)**: after Phase 3 (interim report) and Phase 4 (full report).

### Within a layer

- Counting: T006 (driver) → T007 (optional derived count) → T008 (rebase) → T009 (scales) → T010 (growth) → T011/T012 (guards) → T013 (green).
- Timing: T014 (critical path) → T015 (executed recompute) → T016 (migration isolation) → T017 (best-effort commit) → T018 (gating) → T019 (run).

### Parallel opportunities

- T002 and T003 are different files (`metrics.py` vs `dataset.py`) — T002 is `[P]`. T005 and T007 are `[P]`.
- Once Phase 2 lands, **Phase 3 and Phase 4 can proceed in parallel** (different trees), both importing `scale/merge_recompute/`.
- T022 is `[P]`.

---

## Implementation Strategy

### MVP first (recommended)

1. Phase 1 → Phase 2 (dataset + metrics).
2. Phase 3 (counting layer) → **STOP & VALIDATE**: node-event cardinality + growth, deterministic and cheap, plus the optional derived expected-recompute. Write an interim `findings.md`.
3. Decide based on the counting result whether the full-stack timing layer (Phase 4) is still needed to choose the redesign, or whether the cardinality finding is already decisive.

### Incremental delivery

- Counting layer is the shippable MVP and a CI-able regression guard.
- Timing layer is a separable second increment (heavier, gated); it confirms where wall-clock goes, gives the authoritative executed-recompute count, and quantifies the degraded-instance window.
- Findings report is updated as each layer lands.

### Risk notes

- **T015 (per-run flow-run attribution)** is the riskiest measurement step — filtering Prefect flow runs to exactly one merge's recompute without double-counting concurrent activity. Validate the filter before trusting the timing numbers.
- Keep the vocabulary distinct in the report (emitted events vs executed runs vs derived expected): the counting layer measures emission cardinality; only the timing layer observes executed recompute. Do not present a counting-layer number as a recompute-execution count.

---

## Notes

- `[Story]` labels are for traceability; the shippable increments are the layers.
- Commit after each task or logical group; do not force-push the branch.
- No edits to generated files; no new external dependencies; reuse existing scale/benchmark/adapter infrastructure.
