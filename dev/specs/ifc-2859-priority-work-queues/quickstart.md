# Quickstart: Validating the Priority Work Queue Foundation

**Feature**: `ifc-2859-priority-work-queues`

Runnable scenarios proving the feature end-to-end. Contracts: [contracts/workflow-adapter.md](contracts/workflow-adapter.md); entities: [data-model.md](data-model.md).

## Prerequisites

```bash
uv sync --all-groups
```

Integration scenarios use the Prefect test harness (`TestWorkerInfrahubAsync`) via testcontainers — Docker must be available.

## Scenario 1 — Unit: vocabulary and payload (fast, no services)

```bash
uv run pytest backend/tests/unit/workflows/ -v
```

**Expected**: all pass, including new assertions that

- `WorkflowPriority` exposes `high`/`medium`/`low` with queue precedence 1/2/3,
- `WorkflowDefinition.default_priority` defaults to `MEDIUM`,
- `to_deployment()` carries `work_queue_name` matching the tier,
- every catalogue workflow carries a valid priority.

## Scenario 2 — Integration: provisioning, routing, cron

```bash
uv run pytest backend/tests/integration/services/adapters/workflow/test_workflow_priority.py -v
```

**Expected**:

- After `setup_task_manager`, the `infrahub-worker` pool has `high`/`medium`/`low` queues at precedence 1/2/3 (SC-001); re-running setup changes nothing (idempotent).
- Dispatch with each explicit priority: `flow_run.work_queue_name` equals the tier queue (SC-002); dispatch without priority lands in `medium` (FR-005).
- The cron workflow's deployment is attached to its tier queue with its schedule intact (FR-003).

## Scenario 3 — Zero behavior change (SC-003)

```bash
uv run invoke backend.test-unit
```

**Expected**: existing suite passes unmodified — no test outside this feature's new files needed changes.

## Scenario 4 — Manual smoke on the dev stack (optional)

```bash
uv run invoke dev.start           # or the task-manager-enabled dev stack
uv run infrahub tasks init        # runs setup_task_manager
```

Then open the task-manager UI (Prefect) → Work Pools → `infrahub-worker`:

- **Expected**: queues `high`, `medium`, `low` (and `default`) visible with priorities 1/2/3 — User Story 4.
- Trigger any workflow (e.g. create a branch in the Infrahub UI) → its flow run shows `work_queue: medium`.

## Documentation check

`dev/knowledge/backend/async-tasks.md` contains the new priority-lanes section (documentation gate):

```bash
grep -i "priority" dev/knowledge/backend/async-tasks.md
```
