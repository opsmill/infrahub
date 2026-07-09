# Contract: Workflow Adapter Dispatch Interface

**Feature**: `ifc-2859-priority-work-queues` | **Scope**: internal Python interface — no client-facing API, GraphQL, REST, or SDK surface changes.

## `InfrahubWorkflow` (abstract interface)

**Location**: `backend/infrahub/services/adapters/workflow/__init__.py`

Both entry points gain one optional parameter. Existing call sites (all keyword-argument based) are source-compatible without modification.

```python
class InfrahubWorkflow(ABC):
    @abstractmethod
    async def execute_workflow(
        self,
        workflow: WorkflowDefinition,
        expected_return: type[Return] | None = None,
        context: InfrahubContext | EventContext | None = None,
        parameters: dict[str, Any] | None = None,
        tags: list[str] | None = None,
        priority: WorkflowPriority | None = None,   # NEW
    ) -> Any: ...

    @abstractmethod
    async def submit_workflow(
        self,
        workflow: WorkflowDefinition,
        context: InfrahubContext | EventContext | None = None,
        parameters: dict[str, Any] | None = None,
        tags: list[str] | None = None,
        priority: WorkflowPriority | None = None,   # NEW
    ) -> WorkflowInfo: ...
```

The `@overload` stubs on `execute_workflow` (typed/untyped `expected_return`) are extended with the same parameter.

## Semantics

| Guarantee | Detail |
|-----------|--------|
| Backward compatibility | `priority=None` is the default; every existing caller is unaffected and follows the exact pre-change code path (no added API calls) |
| Routing | `priority=<tier>` routes the flow run to the work queue named `tier.queue_name` on the `infrahub-worker` pool |
| Default lane | With no priority anywhere, the run lands in the deployment's own queue — `medium` via catalogue default |
| Graceful degradation | If the tier queue is missing at dispatch: warning logged (naming queue and workflow), run dispatched without override into the deployment's own queue. Dispatch never raises due to queue layout |
| Local adapter | `WorkflowLocalExecution` accepts `priority` and ignores it (inline execution) |
| Type safety | `priority` is `WorkflowPriority | None` — never a raw string |

## Implementations bound by this contract

- `WorkflowWorkerExecution` (`worker.py`) — production, Prefect-backed.
- `WorkflowLocalExecution` (`local.py`) — test/local, inline.
- `infrahub-enterprise` adapters, if any, that subclass `InfrahubWorkflow` must add the parameter (defaulted, so a plain signature extension).

## Deployment payload contract (Prefect)

`WorkflowDefinition.to_deployment()` additionally emits:

```python
{"work_queue_name": "<default_priority.queue_name>"}  # e.g. "medium"
```

consumed by `client.create_deployment(...)` at task-manager initialization.
