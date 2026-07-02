# Implementation Plan: Priority Work Queue Foundation for the Task Worker

**Branch**: `priority-work-queues-ifc-2859` | **Date**: 2026-07-02 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `dev/specs/ifc-2859-priority-work-queues/spec.md`

## Summary

Add three priority lanes (`high`, `medium`, `low`) to the existing `infrahub-worker` Prefect work pool, give every `WorkflowDefinition` in the catalogue a `default_priority` field (medium everywhere), attach deployments — including cron workflows — to the queue matching their default priority, and add an optional `priority` override to both dispatch entry points of the workflow adapter with a check-first graceful fallback. Zero behavior change in this slice: everything runs on `medium`, and the seam is ready for follow-up classification work under INFP-635.

Technical approach (full details in [research.md](research.md)): a `WorkflowPriority` string enum in `workflows/constants.py` is the single source of truth for tier names, queue names, and Prefect queue precedence; a new `setup_work_queues` task in task-manager initialization converges the queue layout idempotently on every startup (create-or-update); dispatch routes via `run_deployment(work_queue_name=...)` after verifying queue existence, falling back to the deployment's own queue with a warning when the queue is missing.

## Technical Context

**Language/Version**: Python 3.14 (backend only)

**Primary Dependencies**: Prefect 3.7.5 (existing — no new dependencies), Pydantic 2.12

**Storage**: None — no database schema or migration changes; queue layout lives in the Prefect server (task manager)

**Testing**: pytest 9.0 — unit (`backend/tests/unit/workflows/`) and integration (`backend/tests/integration/services/adapters/workflow/` on the `TestWorkerInfrahubAsync` harness)

**Target Platform**: Linux server (Infrahub backend + task worker containers)

**Project Type**: Backend service extension (task execution layer)

**Performance Goals**: No new hot-path cost — the no-priority dispatch path is unchanged (zero extra API calls); the override path adds one Prefect API read and has no production callers in this slice

**Constraints**: Zero behavior change (SC-003); no worker launch-configuration changes (FR-007); dispatch must never fail due to queue layout (FR-006); idempotent startup convergence (FR-001)

**Scale/Scope**: ~4 backend source files touched, ~90 workflow definitions in the catalogue unchanged except an inherited default, 1 knowledge doc updated

## Constitution Check

*GATE: evaluated against `.specify/memory/constitution.md` v1.0.0.*

| Principle | Assessment |
|-----------|------------|
| I. Schema-Driven Integrity | ✅ N/A — no node/attribute/relationship schema involvement; no generated files touched |
| II. Branch-Safe by Default | ✅ N/A — queue routing is branch-agnostic infrastructure; no database queries added or modified |
| III. Type Safety & Explicit Contracts | ✅ `WorkflowPriority` is a typed `InfrahubStringEnum` at every boundary (FR-008); adapter interface change is fully type-hinted; no untyped dicts |
| IV. Test Discipline | ✅ Unit tests for pure logic (enum, payload); integration tests for queue wiring on the existing Prefect test harness; no mocks (check-first fallback design chosen specifically for mock-free testability — research D5); upstream orchestrator ordering deliberately not re-tested (SC-004) |
| V. Query Performance & Efficiency | ✅ No Cypher/database queries. One extra Prefect API read only on the override path (no callers this slice) |
| VI. Security & Input Boundaries | ✅ No user input, no API surface, no auth changes; `priority` is internal plumbing typed as an enum |
| VII. Simplicity & Maintainability | ⚠️ Justified violation — plumbing with no production caller is nominally YAGNI. Accepted per PRD: follow-up slices under INFP-635 are committed work; rationale restated in Complexity Tracking and to be restated in the PR |

**Post-design re-check**: no new violations introduced by the design; the single ⚠️ is tracked below.

## Project Structure

### Documentation (this feature)

```text
dev/specs/ifc-2859-priority-work-queues/
├── plan.md              # This file
├── research.md          # Phase 0 output — verified Prefect behavior + decisions D1-D6
├── data-model.md        # Phase 1 output — entities and field changes
├── quickstart.md        # Phase 1 output — validation guide
├── contracts/
│   └── workflow-adapter.md  # Internal adapter interface contract
└── tasks.md             # Phase 2 output (/speckit-tasks — NOT created by /speckit-plan)
```

### Source Code (repository root)

```text
backend/infrahub/
├── workflows/
│   ├── constants.py         # + WorkflowPriority enum (tier ↔ queue name ↔ precedence)
│   ├── models.py            # + WorkflowDefinition.default_priority; to_deployment() carries work_queue_name
│   ├── initialization.py    # + setup_work_queues task; wired into setup_task_manager flow
│   └── catalogue.py         # unchanged definitions (all inherit medium); WORKER_POOLS unchanged
├── services/adapters/workflow/
│   ├── __init__.py          # InfrahubWorkflow interface: + priority param on both entry points
│   ├── worker.py            # WorkflowWorkerExecution: queue routing + check-first fallback + warning
│   └── local.py             # WorkflowLocalExecution: accepts and ignores priority

backend/tests/
├── unit/workflows/
│   ├── test_constants.py    # NEW — WorkflowPriority values, queue names, precedence mapping
│   ├── test_models.py       # + default_priority default; deployment payload carries work_queue_name
│   └── test_catalogue.py    # + every catalogue workflow carries a valid default priority
└── integration/services/adapters/workflow/
    └── test_workflow_priority.py  # NEW — provisioning idempotency, dispatch routing, fallback, cron

dev/knowledge/backend/
└── async-tasks.md           # + priority lanes section (documentation gate)
```

**Structure Decision**: All changes extend existing modules in the task-execution layer — `backend/infrahub/workflows/` (vocabulary, provisioning, catalogue model) and `backend/infrahub/services/adapters/workflow/` (dispatch). Test files mirror source structure per the testing guidelines. No new packages, no frontend, no SDK.

## Design Overview

### 1. Priority vocabulary (`workflows/constants.py`) — research D1, D2

```python
class WorkflowPriority(InfrahubStringEnum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"

    @property
    def queue_name(self) -> str: ...     # == self.value (D1: queues named high/medium/low)

    @property
    def queue_priority(self) -> int: ... # Prefect precedence: high=1, medium=2, low=3
```

Single source of truth for tier-to-queue mapping (FR-008). Lives beside `WorkflowType`/`WorkflowTag` on the same base class.

### 2. Catalogue default priority (`workflows/models.py`) — research D3

- `WorkflowDefinition.default_priority: WorkflowPriority = WorkflowPriority.MEDIUM` (FR-002).
- `to_deployment()` adds `"work_queue_name": self.default_priority.queue_name` — deployment creation carries the queue assignment, and cron schedules ride on the same deployment payload, so scheduled runs inherit the queue with no special handling (FR-003).
- No catalogue entry sets the field in this slice — all ~90 workflows inherit medium (SC-003).

### 3. Queue provisioning (`workflows/initialization.py`) — research D4

New task `setup_work_queues(client)` invoked from `setup_task_manager()` between `setup_worker_pools` and `setup_deployments`:

- For each pool in `WORKER_POOLS` × each `WorkflowPriority`: `create_work_queue(name, priority, work_pool_name)`; on `ObjectAlreadyExists` → read queue, `update_work_queue(id, priority=...)`.
- Create-or-**update** (not skip) makes every startup converge the layout (FR-001), healing both fresh upgrades and queues auto-created at wrong precedence by the Prefect server's missing-queue auto-create (verified server behavior — research table).
- Converged layout: `high=1, medium=2, low=3, default=4` (server bumps `default`; lower number = higher precedence). Legacy runs stranded in `default` still execute since workers poll all pool queues (FR-007, upgrade edge case).

### 4. Priority-aware dispatch (`services/adapters/workflow/`) — research D5

- `InfrahubWorkflow.execute_workflow` and `.submit_workflow` gain `priority: WorkflowPriority | None = None` (interface + overloads + both adapters).
- `WorkflowWorkerExecution`: when `priority` is set, verify the queue via `read_work_queue_by_name(name, work_pool_name)`; present → dispatch with `run_deployment(..., work_queue_name=...)`; missing (`ObjectNotFound`) → log a warning naming the missing queue and dispatch without the override, landing the run in the deployment's own queue (FR-004, FR-006).
- When `priority` is `None`: identical code path to today — no extra API call, run inherits the deployment's queue (medium by default, FR-005).
- `WorkflowLocalExecution`: accepts and ignores `priority` (inline execution, no queues).
- Race safety: if the queue vanishes between check and dispatch, the Prefect server auto-creates it and the run still executes; the next startup convergence repairs its precedence. Dispatch can never fail because of queue layout.
- Fallback warning (critique E3): emitted via the adapter's standard structlog logger (`infrahub.log.get_logger()`), and must name the missing queue, the workflow being dispatched, and the fallback taken (deployment's own queue). This is the operator's only drift signal and the anchor for the integration test's log assertion.
- Downgrade safety (critique P4): rolling back to a pre-priority release is naturally safe — old code re-saves all deployments without `work_queue_name` (back onto the pool's default queue), the orphaned tier queues sit empty and harmless, and workers keep polling every queue in the pool. No cleanup required.

### 5. Documentation gate

`dev/knowledge/backend/async-tasks.md` gains a "Priority lanes" section (queue layout, `WorkflowPriority`, `default_priority`, dispatch override, fallback semantics) in the same PR.

## Testing Plan

| Level | Location | Coverage |
|-------|----------|----------|
| Unit | `backend/tests/unit/workflows/test_constants.py` (new) | Enum members/values; `queue_name` mapping; `queue_priority` precedence (high < medium < low numerically) |
| Unit | `backend/tests/unit/workflows/test_models.py` | `default_priority` defaults to medium; `to_deployment()` payload carries the matching `work_queue_name`; explicit non-default priority carries through |
| Unit | `backend/tests/unit/workflows/test_catalogue.py` | Parametrized: every catalogue workflow has a valid `WorkflowPriority` (guards the catalogue as classification begins later) |
| Integration | `backend/tests/integration/services/adapters/workflow/test_workflow_priority.py` (new, on `TestWorkerInfrahubAsync`) | Three queues exist with converged precedence after setup — assert absolute precedence (1/2/3) only for the three pinned queues and **relative** order for `default` (greater than `low`'s), since its absolute value is a Prefect bump-algorithm side effect (critique E6); idempotent re-run; dispatch with each explicit priority lands in the matching queue (assert `flow_run.work_queue_name`); no-priority lands in medium; missing-queue fallback (delete queue → warning emitted + run in default lane); one cron workflow's deployment attached to its tier queue with schedule intact |

Not tested (SC-004): Prefect's native queue-priority ordering under load — upstream behavior assumed correct.

## Complexity Tracking

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|-------------------------------------|
| Constitution VII (YAGNI): priority override parameter has no production caller in this slice | The seam is the deliverable — follow-up slices under INFP-635 (workflow classification, client priority signal) are committed work and need a tested routing structure to land in | Building the seam together with the first classification would couple an infrastructure change to a behavior change, defeating the PRD's zero-risk foundation requirement (SC-003) |
