# Data Model: Priority Work Queue Foundation

**Feature**: `ifc-2859-priority-work-queues` | **Date**: 2026-07-02

No database (Neo4j) entities are involved — no schema or migration changes. The "data" of this feature is Python-level vocabulary plus Prefect server objects (work queues, deployments) managed at task-manager initialization.

## WorkflowPriority (new enum)

**Location**: `backend/infrahub/workflows/constants.py`

| Member | Value | `queue_name` | `queue_priority` (Prefect precedence) |
|--------|-------|--------------|----------------------------------------|
| `HIGH` | `"high"` | `high` | 1 (highest) |
| `MEDIUM` | `"medium"` | `medium` | 2 |
| `LOW` | `"low"` | `low` | 3 |

- Base class: `InfrahubStringEnum` (same as `WorkflowType`, `WorkflowTag`).
- Single source of truth for the tier-to-queue mapping (FR-008): queue names and precedence integers are derived properties, never duplicated elsewhere.
- Deliberately priority-semantic vocabulary (not interactive/deferred intent taxonomy — that remains in discovery under INFP-635).

**Validation rules**:

- Values are lowercase single words (workflow naming convention).
- `queue_priority` integers are unique and strictly ordered: `HIGH < MEDIUM < LOW` numerically (lower = higher precedence in Prefect).

## WorkflowDefinition (extended)

**Location**: `backend/infrahub/workflows/models.py`

| Field | Type | Default | New? |
|-------|------|---------|------|
| `default_priority` | `WorkflowPriority` | `WorkflowPriority.MEDIUM` | ✅ new |
| (all existing fields) | — | — | unchanged |

**Behavior changes**:

- `to_deployment()` payload gains `"work_queue_name": self.default_priority.queue_name`.
- Cron workflows need no special handling: `schedules` and `work_queue_name` are part of the same deployment payload, so scheduled runs inherit the deployment's queue (FR-003).

**State/lifecycle**: deployments are re-saved on every task-manager initialization (existing behavior), so an upgraded instance converges all deployments onto their tier queue at first startup.

## Work queues (Prefect server objects)

**Managed by**: `setup_work_queues` task in `backend/infrahub/workflows/initialization.py`

| Queue | Pool | Precedence | Created by |
|-------|------|-----------|------------|
| `high` | `infrahub-worker` | 1 | this feature (startup, idempotent) |
| `medium` | `infrahub-worker` | 2 | this feature (startup, idempotent) |
| `low` | `infrahub-worker` | 3 | this feature (startup, idempotent) |
| `default` | `infrahub-worker` | 4 (bumped by server) | Prefect (pool built-in) — legacy/fallback lane |

**Convergence rules** (FR-001):

- Create with explicit precedence; on `ObjectAlreadyExists`, update precedence in place.
- Runs every startup; heals queues auto-created at arbitrary precedence by the server's missing-queue auto-create.
- Queues are never deleted by Infrahub (deleting would orphan queued runs).

## Dispatch routing (adapter parameter)

**Location**: `backend/infrahub/services/adapters/workflow/` (`InfrahubWorkflow`, `WorkflowWorkerExecution`, `WorkflowLocalExecution`)

| Input | Routing outcome |
|-------|-----------------|
| `priority=None` (default) | Deployment's own queue (tier default → medium everywhere this slice) — unchanged code path, zero extra API calls (FR-005) |
| `priority=<tier>`, queue exists | `run_deployment(work_queue_name=tier.queue_name)` → run lands in tier queue (FR-004) |
| `priority=<tier>`, queue missing | Warning logged naming the missing queue; dispatch without override → run lands in deployment's own queue (FR-006) |
| Local execution adapter | `priority` accepted and ignored (inline run, no queues) |

## Relationships

```text
WorkflowPriority ──(queue_name)──► Prefect WorkQueue (per pool)
        ▲                                   ▲
        │ default_priority                  │ work_queue_name
WorkflowDefinition ──(to_deployment)──► Prefect Deployment ──(schedules)──► cron flow runs
                                            ▲
InfrahubWorkflow.execute/submit ──(priority override)──► flow run work_queue_name
```
