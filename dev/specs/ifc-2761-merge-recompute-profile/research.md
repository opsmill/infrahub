# Phase 0 Research: Profile merge and rebase recompute cost at scale

**Date**: 2026-06-22 · **Spec**: [spec.md](./spec.md) · **Plan**: [plan.md](./plan.md)

Grounded in the current `develop` tree. File:line anchors are pointers, not contracts; the two marked OPEN items are confirmed during implementation.

## R1. Counting vs timing must be two harnesses (the central decision)

**Decision**: build two layers — a deterministic counting layer and a real-stack timing layer. Do not try to get both from one setup.

**Rationale**: `WorkflowRecorder` (`backend/tests/adapters/workflow.py`) records every `submit_workflow` call and returns a fake `WorkflowInfo` **without submitting to Prefect** — so it counts submissions precisely but the recompute never runs, and no flow-run timing exists. Conversely, real wall-clock requires a running task worker, which makes counts non-deterministic (timing, retries, ordering). So:
- Counting layer uses an event-service recorder → exact counts of emitted node events (plus an in-process derived recompute estimate), deterministic, no worker. It does **not** observe Prefect-submitted recompute (see R5).
- Timing layer uses the real stack → real wall-clock and the authoritative executed-recompute count, attributed from Prefect flow-run timestamps.

**Alternatives considered**: a single full-stack run that both counts and times — rejected: counts become flaky and the worker adds latency that pollutes the cardinality signal, which is the most decisive finding.

## R2. Driving merge and rebase

**Decision**: invoke the flows directly — `merge_branch(branch=..., context=...)` and `rebase_branch(...)` from `backend/infrahub/core/branch/tasks.py` — for the counting layer; use the GraphQL `BranchMerge`/`BranchRebase` mutations for the timing layer on the real stack.

**Evidence**: the real pre-compute-diff-then-merge pattern is in `backend/tests/component/core/changelog/test_diff.py` and `test_branch_merge.py` (compute the enriched diff via `diff_coordinator.update_branch_diff`, then merge). **Caution (was F2)**: `backend/tests/component/core/diff/test_merge_task_lock.py` MOCKS `_do_merge_branch` (`patch("...tasks._do_merge_branch")`) — it does not drive a real merge and must not be used as the model. GraphQL mutation driving is the integration pattern (`backend/tests/integration/diff/test_diff_rebase.py`, `BranchMerge`/`BranchRebase`). Merge emits the per-node events at `tasks.py:313-327`; rebase at `:259-275`.

**Feasibility note (was F5)**: running `merge_branch` without a task worker requires the enriched branch diff to be tracked first (it loads `diff_repository.get_one(tracking_id=BranchTrackingId(name=branch.name))`, `tasks.py:402-403`), so the harness must compute the tracked diff via `diff_coordinator.update_branch_diff` before calling the flow — it is not "seed and call merge." No existing test drives the real `merge_branch` flow end-to-end with real events, so this is first-time wiring: confirm a data-only merge completes with `WorkflowRecorder` neutralizing the orchestration submissions and `MemoryInfrahubEvent` (R4) recording the node events without dispatching them.

## R3. Seeding a synthetic branch at scale

**Decision**: seed N nodes on a branch then mutate them so they appear in the merge diff, parameterizing N across the chosen scales. In the counting layer (graph DB only, no API server) use async `Node.new/save` against the `db` fixture; the timing layer (full stack) may use the SDK batch (`client.create_batch()`, as in `backend/tests/benchmark/intensive/test_batch_create.py`). The sync Locust scale stagers (`backend/tests/scale/common/stagers.py`) are a reference only.

**Rationale**: these are the existing bulk-seed patterns; building a third would violate Constitution VII. The changed-node count is the independent variable, so the dataset must let "nodes created" and "nodes changed on the branch" vary.

**Note (was F4/F7)**: `stagers.py` uses the **synchronous** client (Locust). The component counting layer has only the graph `db` fixture (no API server), so `client.create_batch()` is not available there either — seed via async `Node.new/save` against `db` (as component tests do). Reserve `client.create_batch()` for the timing layer (full stack).

**Schema (was F3)**: assemble the fixture; do not assume an existing one fits. The `tshirt.py` helper has a computed attribute + display_label but **no HFID**, and the all-three `TestingTShirt` (`test_files/computed_tshirt.yml`) uses a `TransformPython` computed attribute that needs the worker/repo (full stack) — unusable in the no-worker counting layer. Build a Python `NodeSchema` carrying a **Jinja2** computed attribute + display label + HFID + a relationship peer read so cross-node automations are exercised without a transform.

## R4. Counting node events emitted by a merge — use the event-service recorder, not the bus

**Decision**: capture emitted events with the **event-service recorder** `MemoryInfrahubEvent` (`backend/tests/adapters/event.py`), which appends every event to `self.events`; count `NodeCreated/Updated/DeletedEvent` by type.

**Why not `BusRecorder` (corrects an earlier wrong assumption)**: node events carry **no bus messages**. `NodeMutatedEvent` does not override `get_messages()` and the base returns `[]` (`events/node_action.py:16`, `events/models.py:183`), so `InfrahubEventService._send_bus` is a no-op for them; they reach only Prefect via `_send_prefect` → `emit_event` (`services/adapters/event/__init__.py`). A `BusRecorder` would record nothing. The event-service tap is required.

**Injection**: there is **no** `config.OVERRIDE.event_service` (`config.Override` exposes only `message_bus`, `cache`, `workflow`, `config.py:1495`) and `build_event_service()` ignores overrides (`workers/dependencies.py:121-124`). Inject through the dependency-provider scope — `dependency_provider.scope(build_event_service, lambda: recorder)` — the same mechanism `WorkflowRecorder` uses for `build_workflow`. `merge_branch` resolves the service via `get_event_service()` DI (`tasks.py:325`), so the scope applies. `MemoryInfrahubEvent.send` does not forward to Prefect, so recompute is not triggered in this layer (correct for counting).

## R5. What the counting layer can and cannot measure

**Decision**: the counting layer's deterministic signal is **emitted node events, by type and changed field** (via `MemoryInfrahubEvent`, R4). `WorkflowRecorder` is retained only to neutralize the merge's own orchestration workflows (post-process, IPAM reconciliation), which the merge submits directly; it does **not** see the per-node recompute.

**The raw event count is largely known a priori**: merge emits exactly one node event per changed node (`tasks.py:313-323`), so node events ≈ changed-node count by construction. That is a useful sanity check and gives the per-field breakdown, but it is not itself a new finding.

**The recompute multiplier is the real unknown** (emitted events × matching automations → recompute runs) and is **not** observable in this layer: recompute is dispatched by Prefect automations reacting to the events, and `MemoryInfrahubEvent` swallows the events (no Prefect emit). Two ways to obtain it:
- **Derived (in-process)** — apply the same dependency/automation match logic to the emitted events to predict recompute targets per family. Cheap and deterministic, but reimplements Prefect matching (divergence risk). This is the counting layer's real value-add — an estimate, cross-checked by the timing layer, which remains authoritative.
- **Executed (timing layer, R6)** — the authoritative count from Prefect flow-runs.

**Alternative to evaluate during implementation**: record events **and** forward them (a `MemoryInfrahubEvent` subclass calling `super().send()`) against a real Prefect server with automations configured but **no task worker** — Prefect then *creates* the recompute flow-runs (the multiplier) without executing them, yielding the submission count cheaply and deterministically without reimplementing matching. Heavier than graph-DB-only, lighter than the full timing stack.

**Consequence**: the counting layer is not solely decisive. It gives cardinality + a derived (or no-worker-observed) recompute estimate; the timing layer remains the authority on executed counts and wall-clock. The findings must keep the three quantities distinct: emitted events, derived expected recompute, executed recompute.

## R6. Attributing wall-clock on the real stack

**Decision**: in the timing layer, measure:
- **Merge critical path**: `time.perf_counter()` around the merge mutation/flow (the synchronous, in-transaction cost).
- **Trailing recompute**: query Prefect flow runs via the task-manager flow-run API (`read_flow_runs` with `FlowRunFilterStartTime`/state filters, `backend/infrahub/task_manager/task.py`), filtered by the merge's **branch tag + recompute deployment names + start-time window**; sum their durations and record count and span (first start to last finish = the degraded-instance window). Note (was F4): the API supports only one related-node tag and AND-only tag matching (`task_manager/task.py:226-232`), so filtering by a seeded-node-id *set* is not possible — branch + deployment + window is the workable filter.
- **Schema migrations**: isolate by comparing a schema-changing merge against a data-only merge of the same size (the diff is the migration cost), since both run through the same path.
- **Database commit / merge internals**: use the existing DB query profiler (`InfrahubDatabaseProfiler`) and the lock-duration metric (`infrahub_lock_*`) where finer attribution is needed.

**Evidence**: the integration_docker suite already waits on recompute terminal state via `client.task.count(TaskFilter(workflow=[...], related_node__ids=[...], state=terminal))` (`backend/tests/integration_docker/test_display_label_backfill.py`, `test_computed_attributes.py`, bound `PREFECT_EVENT_WAIT_SECONDS=60`). The same task/flow-run query surface yields the timings.

**Resolved + residual risk**: the flow-run query cannot target a node-id set (single related node, AND-only tags), so use branch + deployment + start-time window. To avoid double-counting concurrent activity, run the timed merge on a dedicated branch with no other workflow traffic. Validating this filter is still the riskiest measurement step.

## R7. Reporting and reproducibility

**Decision**: each run emits a structured record (R-data-model); the harness aggregates runs across scales into `findings.md` under the spec dir (a table of counts and timings per scale plus the growth classification). The counting layer is deterministic and can assert exact counts at each scale (regression guard); the timing layer reports with a stated tolerance and does not assert hard thresholds (stack-relative).

**Rationale**: makes the counting layer a CI-able regression guard and keeps the timing layer an on-demand investigation, matching how `backend/tests/benchmark/intensive/` is gated.

## R8. No behavior change (the invariant)

**Decision**: the harness must not alter recompute output. The counting layer asserts that derived values produced by a merge are identical with and without the harness wiring; the timing layer relies on the existing recompute tests staying green.

## Open items carried into tasks

- R5: decide between the in-process derived multiplier and the Prefect-no-worker variant for the recompute estimate.
- R6: validate the branch + deployment + start-time-window flow-run filter on a dedicated branch (a node-id-set filter is not supported).

Resolved:
- R2: drive via the real `diff_coordinator.update_branch_diff` + merge pattern (`test_merge_task_lock.py` mocks the merge — do not copy it); no existing test drives the real flow end-to-end, so budget for first-time wiring.
- R3: assemble a Jinja2-only `NodeSchema` (computed attr + display label + HFID + relationship peer); existing all-three fixtures use a transform that needs the full stack.
- R4: event-service recorder `MemoryInfrahubEvent` via dependency-provider scope; `BusRecorder` does not work for node events.
- Placement: counting layer under `tests/component/merge_recompute/` (CI-collected), shared code under `tests/helpers/merge_recompute/`; `tests/scale/` is Locust, not CI.
