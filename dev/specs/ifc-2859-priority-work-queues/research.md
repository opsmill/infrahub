# Research: Priority Work Queue Foundation for the Task Worker

**Feature**: `ifc-2859-priority-work-queues` | **Date**: 2026-07-02

All findings below were verified directly against the codebase and the installed Prefect 3.7.5 package (`.venv`), not the changelog or docs alone.

## Current State of the Task Execution Layer

- **Orchestrator**: Prefect 3.7.5 (`pyproject.toml`), per ADR-0003. Knowledge doc: `dev/knowledge/backend/async-tasks.md`.
- **Worker pool**: a single pool, `INFRAHUB_WORKER_POOL = WorkerPoolDefinition(name="infrahub-worker")` (`backend/infrahub/workflows/catalogue.py:9`), exported as `WORKER_POOLS = [INFRAHUB_WORKER_POOL]` (line 665).
- **Provisioning**: `setup_task_manager()` flow (`backend/infrahub/workflows/initialization.py:106`) runs `setup_blocks` → `setup_worker_pools` → `setup_deployments` → `setup_triggers`. `setup_worker_pools` uses `client.create_work_pool(work_pool=wp, overwrite=True)`; queues are separate entities and survive pool overwrite.
- **Deployments**: `setup_deployments` calls `WorkflowDefinition.save(client, work_pool=WORKER_POOLS[0])` for every workflow from `get_workflows()`. `save()` → `client.create_deployment(flow_id, **to_deployment(), work_pool_name=...)`. Cron schedules ride on the deployment (`to_deployment()` adds `schedules` when `cron` is set), so scheduled runs inherit whatever queue the deployment is attached to.
- **Dispatch**: `WorkflowWorkerExecution.execute_workflow` / `.submit_workflow` (`backend/infrahub/services/adapters/workflow/worker.py`) both call `prefect.deployments.run_deployment(...)`. The abstract interface is `InfrahubWorkflow` (`backend/infrahub/services/adapters/workflow/__init__.py`); `WorkflowLocalExecution` (tests) runs the flow function inline.
- **Worker process**: `prefect worker start --type infrahubasync --pool infrahub-worker --with-healthcheck` (`development/docker-compose.yml:236`). `BaseWorker.__init__(work_pool_name, work_queues: list[str] | None = None, ...)` — when `work_queues` is not given, the worker polls **all** queues in the pool. FR-007 (no worker launch-config change) is therefore satisfied natively.

## Verified Prefect 3.7.5 Behavior

| Question | Finding | Evidence |
|----------|---------|----------|
| Can a flow run be routed to a queue at dispatch? | Yes — `run_deployment(..., work_queue_name=...)` | `inspect.signature(run_deployment)` includes `work_queue_name: str | None` |
| Can a deployment be pinned to a queue? | Yes — `client.create_deployment(..., work_queue_name=...)` | signature inspected |
| Can queues be created with an explicit priority? | Yes — `client.create_work_queue(name, priority, work_pool_name)`; raises `ObjectAlreadyExists` on rerun; `client.update_work_queue(id, priority=...)` for convergence | signatures inspected |
| Queue priority semantics | Lower number = higher precedence. The server keeps priorities sequential and unique per pool by bumping others when an explicit priority is inserted (`prefect/server/models/workers.py:518-575`, `bump_work_queue_priorities`) | server source read |
| What happens when dispatch targets a **missing** queue? | The server **auto-creates** the queue: `create_flow_run_from_deployment` resolves `work_queue_name` with `create_queue_if_not_found=True` (`prefect/server/api/deployments.py:946-951`). Dispatch never fails on a missing queue; the auto-created queue gets the next free (lowest-precedence) priority | server source read |
| Do workers pick up auto-created queues? | Yes — workers poll every queue in the pool | `BaseWorker` behavior + FR-007 evidence above |

## Decisions

### D1 — Queue names: `high`, `medium`, `low`

**Decision**: The three work queues are named exactly `high`, `medium`, `low`, created on the `infrahub-worker` pool. Queue names are pool-scoped in Prefect, so no `infrahub-` prefix is needed; short names read best in the task-manager UI queue list.

**Rationale**: Matches the workflow naming convention (lowercase, no underscores). The pool's built-in `default` queue remains as the legacy/fallback lane.

**Alternatives considered**: `priority-high`/... (redundant prefix inside a single-purpose pool); reusing `default` as the medium lane (rejected: conflates "no routing decision" with "explicitly medium", and the upgrade story needs `default` free to drain legacy runs).

### D2 — Priority vocabulary: `WorkflowPriority` enum in `workflows/constants.py`

**Decision**: New `WorkflowPriority(InfrahubStringEnum)` with members `HIGH = "high"`, `MEDIUM = "medium"`, `LOW = "low"`, plus two derived accessors that make the enum the single source of truth (FR-008):

- `queue_name` property → the enum value (D1 keys queue names to tier names 1:1).
- `queue_priority` property → Prefect queue precedence integer: high=1, medium=2, low=3.

**Rationale**: `workflows/constants.py` already holds `WorkflowType` and `WorkflowTag` on `InfrahubStringEnum` — same home, same base class. Typed enum at every boundary per Constitution III. Name is priority-semantic (not `WorkflowLane`/`WorkflowClass`) per the PRD's deliberate choice to avoid the intent-based taxonomy still in discovery under INFP-635.

**Alternatives considered**: a separate `TIER_TO_QUEUE` dict mapping (second source of truth to drift); reusing Prefect's `WorkQueue.priority` ints directly in signatures (stringly/int-typed API, fails Constitution III).

### D3 — Catalogue field name: `default_priority`

**Decision**: `WorkflowDefinition` gains `default_priority: WorkflowPriority = WorkflowPriority.MEDIUM`. `to_deployment()` adds `"work_queue_name": self.default_priority.queue_name` to the deployment payload.

**Rationale**: The PRD names the concept "default priority" throughout; the field name matches. Putting `work_queue_name` in `to_deployment()` (rather than `save()`) keeps the payload assembly in one method and makes the unit test a pure-payload assertion. Cron workflows need nothing extra: schedules are part of the same deployment payload, so scheduled runs inherit the deployment's queue (FR-003).

**Alternatives considered**: `priority` (ambiguous with a future per-run priority field); `work_queue` (leaks the queue concept into the catalogue, breaking the single-source-of-truth mapping in the enum).

### D4 — Queue provisioning: new `setup_work_queues` task, create-then-update convergence

**Decision**: New Prefect task `setup_work_queues(client)` in `initialization.py`, called from `setup_task_manager()` between `setup_worker_pools` and `setup_deployments`. For each pool in `WORKER_POOLS` × each `WorkflowPriority`: try `create_work_queue(name, priority, work_pool_name)`; on `ObjectAlreadyExists`, read the queue and `update_work_queue(id, priority=...)`.

**Rationale**: Create-or-update (not create-or-skip) is what makes startup **converge**: it heals both upgrades (queues absent) and drift (a queue auto-created by a missing-queue dispatch received an arbitrary precedence — see D5). Priority bumping server-side yields the stable converged layout `high=1, medium=2, low=3, default=4`; legacy runs stranded in `default` still execute (workers poll all queues). Mirrors the `ObjectAlreadyExists` handling pattern already used in `setup_worker_pools`/`setup_blocks`.

**Alternatives considered**: skip-if-exists (never repairs drift); deleting and recreating queues (would orphan queued runs).

### D5 — Dispatch override: static tier-to-queue mapping (revised 2026-07-03)

**Decision (revised)**: `InfrahubWorkflow.execute_workflow` and `.submit_workflow` (interface + both adapters) gain `priority: WorkflowPriority | None = None` (keyword-only in practice — all call sites use kwargs). In `WorkflowWorkerExecution`, when `priority` is set: pass `work_queue_name=priority.queue_name` to `run_deployment` directly — the enum property is the static tier-to-queue mapping, and queue existence is assumed (it is a startup-provisioning invariant, D4). No per-dispatch existence check. When `priority` is `None`, nothing changes: run inherits the deployment's queue (medium by catalogue default — FR-005). `WorkflowLocalExecution` accepts and forwards the parameter internally but executes inline (no queues).

*Revision note*: the original decision was check-first (verify the queue via `read_work_queue_by_name`, warn and drop the override on `ObjectNotFound`). Revised on user direction: the check added a Prefect API read per prioritized dispatch and a TLS-context asymmetry in `submit_workflow`, for a failure mode that is already safe — Prefect auto-creates a queue named at dispatch, and D4's create-or-update convergence repairs its precedence at the next startup.

**Rationale**:
- *Testability without mocks* (testing rule: adapter/protocol patterns, no `unittest.mock`): routing is asserted directly on `flow_run.work_queue_name` in integration tests; there is no fallback branch left to test — Prefect auto-creates missing queues, so dispatch never raises regardless.
- *Race safety*: if the queue disappears between check and dispatch, the server auto-creates it (`create_queue_if_not_found=True`) — the dispatch still never fails, and the next startup convergence (D4) repairs the auto-created queue's precedence. FR-006's "never fail" holds in both orderings.
- *Cost*: zero extra API calls on any dispatch path.

**Alternatives considered**: try/except retry-without-override (untestable without mocks; the exception path is unreachable under normal server behavior since the server auto-creates queues); passing `work_queue_name` blindly and relying on auto-create (violates FR-006's warning requirement and silently runs at wrong precedence until next restart).

### D6 — No config, no infra, no client surface

**Decision**: No new settings, env vars, compose/helm changes, or client-facing parameters. The worker command (`prefect worker start --pool infrahub-worker`) is untouched (FR-007). The `priority` parameter stops at the adapter interface.

**Rationale**: Verified that workers poll all pool queues by default; PRD explicitly scopes the client signal out.

## Testing Strategy (grounded in existing suites)

- **Unit** — `backend/tests/unit/workflows/`: extend `test_models.py` (deployment payload carries `work_queue_name`; `default_priority` defaults to medium) and add enum/mapping assertions (values, queue names, precedence ints). Existing `test_catalogue.py` parametrized-per-workflow pattern is prior art.
- **Integration** — `backend/tests/integration/services/adapters/workflow/` on the `TestWorkerInfrahubAsync` harness (`backend/tests/helpers/test_worker.py`), which provides `prefect_client`, `work_pool`, and deployment fixtures: queue provisioning + idempotent re-run; dispatch routing per priority and no-priority; one cron workflow's deployment attached to its tier queue.
- **Not tested**: Prefect's queue-priority ordering waterfall (upstream behavior, SC-004).

## Open Items Resolved from the PRD

| PRD open question | Resolution |
|---|---|
| Exact queue-name strings | `high` / `medium` / `low` (D1) |
| Catalogue field name | `default_priority` (D3) |
