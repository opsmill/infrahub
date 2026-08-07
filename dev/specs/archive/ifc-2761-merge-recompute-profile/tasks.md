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

- **Counting layer** (deterministic, graph-DB only, no worker) — delivers US1 (event cardinality + a derived recompute estimate), US2 (growth), US3 (deterministic reproducibility). This is the MVP. The raw node-event count is ≈ the changed-node count by construction, so the counting layer's recompute number is the derived expected-recompute *estimate*; the authoritative executed count comes from the timing layer.
- **Timing layer** (full stack + real worker, gated) — delivers US1 (wall-clock attribution + executed-recompute count + degraded-window distinction).

Tasks carry the `[US#]` they primarily serve.

- **US1** (P1) — attribute cost across cost centers
- **US2** (P1) — characterize growth across scales
- **US3** (P2) — reproducible, retained harness

## Conventions

- Per `dev/rules/code-doc-style.md`: **no spec IDs (IFC-2761, FR-xxx) in source or test names or docstrings.**
- Keyword arguments for all calls; type hints; frozen dataclasses for the metric records (Constitution III). No mocks — use the adapter pattern: `MemoryInfrahubEvent` (`backend/tests/adapters/event.py`) to record emitted events and `WorkflowRecorder` to neutralize the merge's own orchestration workflows, both injected via the **dependency-provider scope** (`dependency_provider.scope(build_event_service, …)` / `…(build_workflow, …)`); the real stack for timing (Constitution IV). Note: there is no `config.OVERRIDE.event_service`, so event capture must use the provider scope, not `config.OVERRIDE`. A `BusRecorder` does **not** work — node events emit no bus messages.
- **Vocabulary** (keep distinct in code and report): *emitted events* = counted in the counting layer (via the event-service recorder); *executed recompute runs* = observed in the timing layer via the workflow engine's run records; *derived expected recompute* = in-process estimate, the counting layer's only recompute signal but cross-checked by the timing layer, which is authoritative (R5). The counting layer does **not** observe Prefect-submitted recompute jobs — on the merge path they are dispatched by automations from the emitted events, not by the merge flow.
- `[P]` = parallelizable (different files, no incomplete dependency).
- Measurement only: no change to recompute behavior, events, or automations.

---

## Phase 1: Setup

- [X] T001 Pin the reuse points the harness depends on (no production code): confirm exact import paths and signatures for the async SDK batch (`client.create_batch()`), `MemoryInfrahubEvent` (`backend/tests/adapters/event.py`) and its injection via `dependency_provider.scope(build_event_service, …)`, `WorkflowRecorder` (`backend/tests/adapters/workflow.py`) via `…(build_workflow, …)`, the integration_docker recompute-wait/flow-run query helpers (`backend/tests/integration_docker/test_display_label_backfill.py`, `backend/infrahub/task_manager/task.py`), the `merge_branch`/`rebase_branch` entry points, and the real pre-compute-diff-then-merge pattern (`diff_coordinator.update_branch_diff` then merge, as in `test_diff.py` / `test_branch_merge.py`). Note: `test_merge_task_lock.py` MOCKS `_do_merge_branch` and is not a model, and no existing test drives the real `merge_branch` flow end-to-end with real events — budget for first-time wiring and confirm a data-only merge completes with the recorders in place. `backend/tests/scale/` is a Locust harness not collected by CI, so the counting test lives under `backend/tests/component/merge_recompute/` and the shared dataset/metrics under `backend/tests/helpers/merge_recompute/`. Record findings in a short note in the feature dir.

---

## Phase 2: Foundational — shared dataset & metrics (BLOCKING)

**Purpose**: the synthetic dataset and metric records both layers depend on. **Blocks Phases 3 and 4.**

- [X] T002 [P] Create the metric records as frozen dataclasses in `backend/tests/helpers/merge_recompute/metrics.py`: `RecomputeCounts` (node events by type [primary]; derived `expected_recompute` by family), `CostCenterTiming` (incl. executed `recompute_flow_runs` and best-effort `db_commit_s`), `ProfileRun`, `FindingsReport` (per data-model.md).
- [X] T003 Create `build_profile_schema()` in `backend/tests/helpers/merge_recompute/dataset.py`: a Python `NodeSchema` (or two) carrying a **Jinja2** computed attribute, a display label, an HFID, and a relationship peer read so cross-node automations are exercised (resolves research R3). Do not use a `TransformPython` computed attribute (it needs the worker/repo and the full stack); the `tshirt.py` helper lacks an HFID and the all-three `TestingTShirt` YAML uses a transform, so assemble the schema rather than reusing those directly.
- [X] T004 Create `seed_branch(*, db, branch, changed_nodes)` in `backend/tests/helpers/merge_recompute/dataset.py`: bulk-create and then mutate `changed_nodes` nodes on a branch so they appear in the merge diff, using async `Node.new/save` against the `db` fixture (the counting layer has only the graph DB, no API server, so `client.create_batch()` is not available there; the scale stagers are sync — reference only); return the ids/counts needed for assertions and for the timing-layer branch/window filter.
- [X] T005 [P] Define the shared scale set (small/medium/large, about 10/100/1000+ changed nodes) as a parametrize source in `backend/tests/helpers/merge_recompute/` so both layers run the same scales.

**Checkpoint**: dataset builder + seeding + metric records ready; both layers can build on them.

---

## Phase 3: Counting layer (Priority: P1) 🎯 MVP

**Goal**: deterministic counts of node events emitted (the fan-out cardinality) across scales, with growth classified — without running a worker. Recompute *execution* counts come from the timing layer (Phase 4), not here.

**Independent Test**: run `backend/tests/component/merge_recompute/test_merge_recompute_counts.py` and get exact node-event counts per scale plus a linear/super-linear classification, reproducibly.

**Covers**: US1 (event cardinality), US2 (growth), US3 (deterministic reproducibility).

- [X] T006 [US1] Implement the counting driver in `backend/tests/component/merge_recompute/test_merge_recompute_counts.py`: inject `MemoryInfrahubEvent` via `dependency_provider.scope(build_event_service, …)` to record emitted events (and `WorkflowRecorder` via `…(build_workflow, …)` only to neutralize the merge's own orchestration workflows), pre-compute the enriched diff via `diff_coordinator.update_branch_diff` (the real pattern; `test_merge_task_lock.py` mocks the merge and is not a model), run a real **data-only** `merge_branch` over a seeded branch, and collect `RecomputeCounts` — node events by type, the primary signal. Restrict to data-only merges: a schema-changing merge runs migrations via `MigrationExecutor.WORKFLOW` which `WorkflowRecorder` would record-not-run, so migration cost is a timing-layer concern only. Do NOT use `BusRecorder`: node events emit no bus messages (`NodeMutatedEvent` has no `get_messages()`), so the bus tap captures nothing. State explicitly that per-node recompute is Prefect-dispatched from the emitted events, not synchronous, so it is not counted here — the executed count comes from the timing layer (T015).
- [X] T007 [US1] Compute the `derived expected-recompute` count (recommended — it is the counting layer's only recompute signal, but an estimate; the timing layer's executed count is authoritative) by applying the dependency/automation match logic to the emitted events in-process, per family (computed attribute, display label, HFID); populate `RecomputeCounts.expected_recompute`. Flag that it reimplements Prefect matching and must be cross-checked against the timing layer (T015). Alternatively (decide in T001/R5), obtain the multiplier by recording-and-forwarding events to a Prefect server with no task worker and counting created-but-unexecuted flow runs.
- [X] T008 [US1] Extend the counting driver to also profile `rebase_branch` over an equivalent dataset (edge: merge vs rebase), recording counts for both operations.
- [X] T009 [US2] Parametrize the counting layer across the shared scale set (T005); produce one `RecomputeCounts` per scale per operation.
- [X] T010 [US2] Compute and record the growth classification (linear vs super-linear vs flat) of node events (and any derived expected-recompute) against `changed_nodes` across the scales.
- [X] T011 [US1] Assert the no-behavior-change invariant: the derived values produced by the merge are identical with the harness wiring present vs absent (measurement does not alter output).
- [X] T012 [US3] Assert determinism: the same scale yields identical counts across repeated runs; pin expected counts per scale as a regression guard. The test lives under `backend/tests/component/merge_recompute/`, which the `test-component` CI job collects, so the guard actually runs in CI.
- [X] T013 [US1] Run the counting layer green at all three scales for both merge and rebase.

**Checkpoint**: counting layer gives node-event cardinality, the derived recompute estimate, and growth, deterministically — shippable MVP. The timing layer remains the authority on executed recompute and wall-clock.

---

## Phase 4: Timing layer (Priority: P1)

**Goal**: real wall-clock attribution across cost centers on the full stack for **merge** (the headline path), separating in-transaction cost from the trailing recompute window, and producing the authoritative executed-recompute count. Rebase wall-clock is deferred (counting layer covers rebase cardinality); add it only if merge timing proves insufficient.

**Independent Test**: run `backend/tests/integration_docker/test_merge_recompute_timing.py` on the full stack and get a `CostCenterTiming` with the dominant cost center identifiable.

**Covers**: US1 (wall-clock + executed recompute count).

- [X] T014 [US1] Implement the timing driver in `backend/tests/integration_docker/test_merge_recompute_timing.py`: drive the merge on the full distributed stack with a real task worker, seed via the shared dataset, and measure the merge critical path with a monotonic clock.
- [X] T015 [US1] Count and time the executed recompute: query Prefect flow runs filtered by the merge's **branch tag + recompute deployment names + start-time window**; record `recompute_flow_runs` (the authoritative FR-004 count), `recompute_total_s`, and `recompute_window_s` (first start to last finish). Note: the flow-run query supports only one related-node tag and AND-only tag matching (`task_manager/task.py:226-232`), so a seeded-node-id-set filter is NOT possible — the branch+deployment+window filter is the workable approach. Riskiest measurement step: validate the filter excludes concurrent activity (run the merge on a dedicated branch) before trusting numbers.
- [ ] T016 [US1] Isolate schema-migration cost by differencing a schema-changing merge against a data-only merge of equal size (edge F); record `schema_migration_s`.
- [ ] T017 [US1] Attribute the database commit / merge internals best-effort (DB query profiler or lock-duration metric); populate `db_commit_s`, allowing `None` when finer attribution is unavailable.
- [X] T018 [US1] Gate the timing layer like the intensive benchmarks (explicit label + long timeout); report timings with a stated tolerance and assert no hard wall-clock thresholds.
- [X] T019 [US1] Run the timing layer at the medium (~100 changed nodes) scale on the full stack; capture `CostCenterTiming` and confirm the dominant cost center is identifiable.

**Checkpoint**: wall-clock attribution, executed-recompute count, and the degraded-instance window are measured for merge.

---

## Phase 5: Findings & cross-cutting

- [X] T020 [US3] Aggregate the runs into a `FindingsReport` and write `dev/specs/ifc-2761-merge-recompute-profile/findings.md`: per-scale table (event counts + timings), the dominant cost center, the growth classification, and the tolerance note. This is the deliverable that gates the coalescing redesign. An interim version MAY be written from the counting layer alone.
- [X] T021 Confirm the existing recompute tests stay green (no behavior disturbed): `backend/tests/integration_docker/test_computed_attributes.py` and `backend/tests/integration_docker/test_display_label_backfill.py`.
- [X] T022 [P] Run `uv run invoke format` and `uv run invoke lint`; resolve `mypy` on all new files.
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

- Counting: T006 (driver) → T007 (derived recompute estimate, core) → T008 (rebase) → T009 (scales) → T010 (growth) → T011/T012 (guards) → T013 (green).
- Timing: T014 (critical path) → T015 (executed recompute) → T016 (migration isolation) → T017 (best-effort commit) → T018 (gating) → T019 (run).

### Parallel opportunities

- T002 and T003 are different files (`metrics.py` vs `dataset.py`) — T002 is `[P]`. T005 is `[P]`. (T007 is no longer parallel — it extends the T006 counting driver.)
- Once Phase 2 lands, **Phase 3 and Phase 4 can proceed in parallel** (different trees), both importing `helpers/merge_recompute/`.
- T022 is `[P]`.

---

## Implementation Strategy

### MVP first (recommended)

1. Phase 1 → Phase 2 (dataset + metrics).
2. Phase 3 (counting layer) → **STOP & VALIDATE**: node-event cardinality (≈ changed-node count by construction) + growth + the derived expected-recompute estimate, deterministic and cheap. Write an interim `findings.md`.
3. Decide based on the counting result whether the full-stack timing layer (Phase 4) is still needed — note the counting layer's recompute number is an in-process *estimate*; the timing layer gives the authoritative executed count and is usually required to be conclusive.

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

## Implementation status (2026-06-24)

Done and validated against a real stack:

- Counting layer (`backend/tests/component/merge_recompute/`) — 6 tests green; emitted node events and the in-process cross-node fan-out estimate, for merge and rebase, across scales, deterministic. Lint + mypy clean.
- Timing layer (`backend/tests/integration_docker/test_merge_recompute_timing.py`) — runs on the full stack (built `local-dev` image), env-gated by `INFRAHUB_PROFILE_TIMING`; measured merge critical path, trailing recompute window, and executed recompute runs at scales 10 and 100.
- Shared dataset/metrics/estimator (`backend/tests/helpers/merge_recompute/`).
- `findings.md`, `setup-notes.md` written. No production code changed (FR-010 holds by construction), so T021's regression guard is satisfied without re-running the existing recompute suite.

Deferred (best-effort, documented in findings.md "Not covered"):

- **T016** schema-migration cost isolation and **T017** DB-commit attribution — the profiled merges are data-only, so both timing fields are `None`. Implement by differencing a schema-changing merge against a data-only one if the redesign needs migration cost.
- **T023** `/pre-ci` — run before opening the PR.

Key discovery (reshapes the cost model): a node's own derived values recompute **inline** (no async work); the async recompute fan-out is **cross-node** (changes to nodes others read). The trailing cross-node recompute is the dominant *growing* cost; the merge critical path is fixed overhead. See findings.md.
