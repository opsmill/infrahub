# Quickstart: Validating Priority Inheritance

**Feature**: [spec.md](spec.md) | **Contract**: [contracts/workflow-adapter.md](contracts/workflow-adapter.md)

## Prerequisites

```bash
uv sync --all-groups
```

## Fast validation (unit, no Prefect server)

```bash
uv run pytest backend/tests/unit/test_context.py -v          # context field, payload compat, conversion boundaries
uv run pytest backend/tests/unit/services/adapters/workflow -v  # resolution matrix, local-adapter stamping
```

Expected: `priority` defaults to `None`; a payload dict without the key deserializes; `resolve_priority` honors override → context → default; the local adapter injects a stamped copy and leaves the caller's context unmutated.

## Full validation (integration, testcontainers Prefect)

```bash
uv run pytest backend/tests/integration/services/adapters/workflow/test_workflow_priority.py -v
```

Expected (extended cases of this slice, on top of the foundation cases):

1. Root dispatched `priority=HIGH` → its context-only sub-dispatch lands in the `high` queue (assert `flow_run.work_queue_name`).
2. Depth-2 descendant also lands in `high`.
3. Low root dispatching a catalogue-high workflow → child runs `low` (exact inheritance).
4. Mid-tree explicit override re-roots its subtree.
5. Dispatch with no priority anywhere still lands in `medium` (unchanged foundation behavior).

## Zero-behavior-change check (SC-002)

```bash
uv run invoke backend.test-unit
```

Expected: existing suite passes unmodified.

## Manual smoke (optional, running stack)

Trigger any interactive operation (e.g. branch create) and inspect the flow run's parameters in the Prefect UI: the injected context of sub-flows carries `priority: "medium"` (stamped catalogue default), and all runs sit in the `medium` queue.
