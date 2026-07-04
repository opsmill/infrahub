# Contract: Workflow Adapter — Priority Resolution & Inheritance

**Feature**: [../spec.md](../spec.md) | Internal interface contract for `InfrahubWorkflow` implementations (`backend/infrahub/services/adapters/workflow/`).

The adapter signatures are unchanged from the foundation slice. This contract adds behavioral guarantees to both entry points.

## Signatures (unchanged)

```python
async def execute_workflow(workflow, expected_return=None, context=None, parameters=None, tags=None, priority=None) -> Any
async def submit_workflow(workflow, context=None, parameters=None, tags=None, priority=None) -> WorkflowInfo
```

`context: InfrahubContext | EventContext | None`, `priority: WorkflowPriority | None`.

## Resolution guarantee (both entry points, all implementations)

The effective priority of a dispatch is resolved as a strict precedence chain:

| Rank | Source | Applies when |
|------|--------|--------------|
| 1 | `priority` argument | argument is not `None` |
| 2 | `context.priority` | context is an `InfrahubContext` with `priority` set |
| 3 | `workflow.default_priority` | always defined (catalogue default) |

- Resolution is **exact**: the result is never floored, capped, or combined with the target workflow's catalogue default.
- `EventContext` and `None` contexts contribute no priority (rank 2 skipped).
- Implemented once in the shared `resolve_priority()` pure function; implementations MUST NOT re-implement the chain.

## Stamping guarantee (both entry points, all implementations)

When the dispatched context is an `InfrahubContext`:

- The implementation injects `context.model_copy(update={"priority": effective})` into the flow parameters — the child run always observes the resolved effective priority, even when it was supplied by the catalogue default (rank 3).
- The caller's context object is **never mutated** — two sub-dispatches from the same context with different explicit overrides do not interfere.

When the context is an `EventContext` or `None`: no stamping; the child receives what the caller passed.

## Routing guarantee (worker implementation)

- `work_queue_name = effective.queue_name` when the effective priority came from rank 1 or rank 2.
- `work_queue_name = None` (deployment default queue) when it came from rank 3 — the no-signal dispatch path is byte-identical to the foundation slice.
- No per-dispatch queue-existence check (foundation FR-006 unchanged).

## Local implementation parity

`WorkflowLocalExecution` applies the same resolution and stamping, performs no queue routing, and executes inline — a flow run locally observes the identical stamped context it would receive from the worker implementation.

## Boundary exclusions

- `InfrahubContext.to_event_context()` and `.to_request_context()` expose no priority.
- Cron-scheduled runs bypass the adapter entirely; their trees start at catalogue defaults.
