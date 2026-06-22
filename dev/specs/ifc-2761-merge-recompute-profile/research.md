# Phase 0 Research: Profile merge and rebase recompute cost at scale

**Date**: 2026-06-22 · **Spec**: [spec.md](./spec.md) · **Plan**: [plan.md](./plan.md)

Grounded in the current `develop` tree. File:line anchors are pointers, not contracts; the two marked OPEN items are confirmed during implementation.

## R1. Counting vs timing must be two harnesses (the central decision)

**Decision**: build two layers — a deterministic counting layer and a real-stack timing layer. Do not try to get both from one setup.

**Rationale**: `WorkflowRecorder` (`backend/tests/adapters/workflow.py`) records every `submit_workflow` call and returns a fake `WorkflowInfo` **without submitting to Prefect** — so it counts submissions precisely but the recompute never runs, and no flow-run timing exists. Conversely, real wall-clock requires a running task worker, which makes counts non-deterministic (timing, retries, ordering). So:
- Counting layer uses recorders → exact counts of node events and recompute submissions, deterministic, no worker.
- Timing layer uses the real stack → real wall-clock, attributed from Prefect flow-run timestamps.

**Alternatives considered**: a single full-stack run that both counts and times — rejected: counts become flaky and the worker adds latency that pollutes the cardinality signal, which is the most decisive finding.

## R2. Driving merge and rebase

**Decision**: invoke the flows directly — `merge_branch(branch=..., context=...)` and `rebase_branch(...)` from `backend/infrahub/core/branch/tasks.py` — for the counting layer; use the GraphQL `BranchMerge`/`BranchRebase` mutations for the timing layer on the real stack.

**Evidence**: direct task invocation is the established component pattern (`backend/tests/component/core/diff/test_merge_task_lock.py`, `backend/tests/component/core/test_branch_rebase.py`); GraphQL mutation driving is the integration pattern (`backend/tests/integration/diff/test_diff_rebase.py`, `BranchMerge`/`BranchRebase`). Merge emits the per-node events at `tasks.py:313-327`; rebase at `:259-275`.

## R3. Seeding a synthetic branch at scale

**Decision**: reuse the scale stagers (`backend/tests/scale/common/stagers.py`) and/or SDK batch creation (`client.create_batch()`, as in `backend/tests/benchmark/intensive/test_batch_create.py`) to create N nodes on a branch, then mutate them so they appear in the merge diff. Parameterize N across the chosen scales.

**Rationale**: these are the existing bulk-seed patterns; building a third would violate Constitution VII. The changed-node count is the independent variable, so the dataset must let "nodes created" and "nodes changed on the branch" vary.

**Schema**: reuse a fixture carrying all three derived-value families. `backend/tests/integration_docker/test_computed_attributes.py` exercises a kind with computed attribute + display_label + hfid together (the `TestingTShirt` style); the `car`/`person` helpers (`backend/tests/helpers/schema/`) carry display_label and human_friendly_id; `car_person_schema_computed_attr` adds a computed attribute. **OPEN**: confirm or assemble one fixture kind that carries all three plus a relationship peer read, so cross-node automations are exercised too.

## R4. Counting node events emitted by a merge

**Decision**: capture emitted events with the message-bus recorder (`BusRecorder`, `backend/tests/adapters/message_bus.py`) injected via `config.OVERRIDE.message_bus`, and count `NodeCreated/Updated/DeletedEvent` by type. Merge sends events through `get_event_service().send()` (`tasks.py:325-327`), which publishes to the bus.

**OPEN**: confirm the cleanest recording point — the message-bus recorder vs an event-service-level recorder. The event service fans to both bus and Prefect (`services/adapters/event/__init__.py`); for counting we only need one faithful tap. Resolve during implementation; does not change the metric.

## R5. Counting recompute submissions

**Decision**: inject `WorkflowRecorder` (via `config.OVERRIDE.workflow` + the dependency provider, the established pattern) and count `submit_workflow` calls bucketed by workflow definition: the per-node compute workflows and the per-kind `TRIGGER_UPDATE_*` workflows for computed attributes, display labels, and HFIDs.

**Caveat (load-bearing)**: with the recorder in place the recompute does not execute, and crucially the **event-to-automation matching happens in Prefect**, not in `merge_branch`. So the counting layer measures the events emitted and any submissions made synchronously in the flow; the count of recompute flow-runs that Prefect's automations would spawn from those events is measured in the timing layer (R6). The counting layer's primary signal is therefore "node events emitted, by kind and field" — which is the fan-out cardinality — plus any direct submissions. This distinction must be stated explicitly in the findings so the two layers are not conflated.

## R6. Attributing wall-clock on the real stack

**Decision**: in the timing layer, measure:
- **Merge critical path**: `time.perf_counter()` around the merge mutation/flow (the synchronous, in-transaction cost).
- **Trailing recompute**: query Prefect flow runs created in the merge's time window via the task-manager flow-run API (`read_flow_runs` with `FlowRunFilterStartTime`/state filters, `backend/infrahub/task_manager/task.py`), filtered by the recompute deployment names and the branch/related-node tags; sum their durations and record count and span (first start to last finish = the degraded-instance window).
- **Schema migrations**: isolate by comparing a schema-changing merge against a data-only merge of the same size (the diff is the migration cost), since both run through the same path.
- **Database commit / merge internals**: use the existing DB query profiler (`InfrahubDatabaseProfiler`) and the lock-duration metric (`infrahub_lock_*`) where finer attribution is needed.

**Evidence**: the integration_docker suite already waits on recompute terminal state via `client.task.count(TaskFilter(workflow=[...], related_node__ids=[...], state=terminal))` (`backend/tests/integration_docker/test_display_label_backfill.py`, `test_computed_attributes.py`, bound `PREFECT_EVENT_WAIT_SECONDS=60`). The same task/flow-run query surface yields the timings.

**OPEN**: confirm the flow-run query can be filtered to exactly the recompute deployments for one merge run (by tag/time window) so concurrent activity is not double-counted. This is the riskiest measurement detail.

## R7. Reporting and reproducibility

**Decision**: each run emits a structured record (R-data-model); the harness aggregates runs across scales into `findings.md` under the spec dir (a table of counts and timings per scale plus the growth classification). The counting layer is deterministic and can assert exact counts at each scale (regression guard); the timing layer reports with a stated tolerance and does not assert hard thresholds (stack-relative).

**Rationale**: makes the counting layer a CI-able regression guard and keeps the timing layer an on-demand investigation, matching how `backend/tests/benchmark/intensive/` is gated.

## R8. No behavior change (the invariant)

**Decision**: the harness must not alter recompute output. The counting layer asserts that derived values produced by a merge are identical with and without the harness wiring; the timing layer relies on the existing recompute tests staying green.

## Open items carried into tasks

- R3: assemble/confirm a single synthetic kind carrying computed attribute + display label + HFID + a cross-node relationship read.
- R4: pick the event-recording tap (bus vs event-service).
- R6: confirm precise flow-run attribution for one merge run (tag/time-window filter).
