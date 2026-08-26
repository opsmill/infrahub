# Creating Asynchronous Workflows

> Part of: `dev/guides/backend/` | Related: [Async Tasks Knowledge](../../knowledge/backend/async-tasks.md), [ADR-0003](../../adr/0003-asynchronous-tasks.md)

Step-by-step guide for creating a new asynchronous workflow in the Infrahub task system.

## When to Create a Workflow

Create a new workflow when you need to:

- Execute long-running operations asynchronously
- Schedule recurring tasks (cron-based)
- Track execution state and logs via Prefect UI
- Trigger operations from events or API calls
- Execute operations that may modify the database

If your operation is quick and synchronous, consider whether a workflow is necessary.

## Prerequisites

- Understanding of async Python and `asyncio`
- Familiarity with Prefect concepts (flows, tasks, deployments)
- Knowledge of the workflow system (see [Async Tasks Knowledge](../../knowledge/backend/async-tasks.md))

## Steps

### Step 1: Choose the Workflow Type

Determine which type fits your workflow:

| Type | Use When | Visible to Users |
|------|----------|------------------|
| `CORE` | Infrastructure operations, branch/schema changes | Yes (Infrahub UI) |
| `USER` | User-provided code (transforms, generators, checks) | Yes (Infrahub UI) |
| `INTERNAL` | System maintenance, scheduled cleanup | No |

See [Async Tasks Knowledge](../../knowledge/backend/async-tasks.md#workflow-types) for detailed descriptions of each type.

### Step 2: Create the Flow Function

Create or add to a `tasks.py` file in your module:

```python
from __future__ import annotations

from prefect import flow, get_run_logger

from infrahub.context import InfrahubContext  # noqa: TC001
from infrahub.workers.dependencies import get_database


@flow(name="my-workflow", flow_run_name="Process {resource_id}")
async def my_workflow(resource_id: str, branch: str, context: InfrahubContext) -> None:
    log = get_run_logger()
    log.info(f"Starting workflow for {resource_id} on branch {branch}")

    database = await get_database()
    async with database.start_session() as db:
        # Your implementation here
        pass

    log.info(f"Completed workflow for {resource_id}")
```

Key requirements:

- Use `@flow` decorator with `name` matching the `WorkflowDefinition.name`
- Names must be **lowercase with dashes** (e.g., `my-workflow`, not `my_workflow`)
- Use `flow_run_name` for human-readable run names (see naming guidelines below)
- Accept `context: InfrahubContext` parameter (injected automatically)
- Use `get_run_logger()` for logging — the stdlib default logger never surfaces in Prefect's UI/logs
- Keep the flow body a thin composition root: resolve singletons (`get_database()`, `get_workflow()`, …) at the top of the flow only, build a component with those dependencies injected, and delegate to it. Business logic lives in the component, not the flow function — see `.agents/rules/backend-component-design.md`

**`flow_run_name` guidelines:**

The `flow_run_name` is visible to users in the Infrahub UI. Keep it clear and short:

- Do not include branch name (except for branch creation workflows)
- Do not include node IDs (already visible in UI context)
- Focus on what the workflow does, not redundant context

```python
# Good: Clear and concise
@flow(name="artifact-generate", flow_run_name="Generate {artifact_name}")
@flow(name="schema-migrate", flow_run_name="Apply schema migrations")

# Bad: Redundant context
@flow(name="branch-merge", flow_run_name="Merge branch {branch} on {branch_id}")
```

### Logging inside flows, tasks, and their helpers

- Inside a `@flow` or `@task` body, use Prefect's `get_run_logger()`.
- In a plain helper called from within a flow (no run context, also called from tests), use
  `infrahub.log.get_run_logger()` — the `infrahub.tasks` logger.

A bare `logging.getLogger(__name__)` will not surface in Prefect. See the Logging section of
`dev/knowledge/backend/async-tasks.md` for why.

### Step 3: Register the WorkflowDefinition

Add your workflow to `backend/infrahub/workflows/catalogue.py`:

```python
from .constants import WorkflowTag, WorkflowType
from .models import WorkflowDefinition

MY_WORKFLOW = WorkflowDefinition(
    name="my-workflow",
    type=WorkflowType.CORE,
    module="infrahub.mymodule.tasks",
    function="my_workflow",
    tags=[WorkflowTag.DATABASE_CHANGE],  # If it modifies the database
)
```

Then add it to the `WORKFLOWS` list in **alphabetical order** for readability:

```python
WORKFLOWS = [
    # ... existing workflows (alphabetically ordered)
    MY_WORKFLOW,
]
```

### Step 4: Add Optional Configuration

#### Cron Scheduling

For recurring workflows, add a cron expression:

```python
MY_SCHEDULED_WORKFLOW = WorkflowDefinition(
    name="my-scheduled-workflow",
    type=WorkflowType.INTERNAL,
    module="infrahub.mymodule.tasks",
    function="my_scheduled_workflow",
    cron="0 * * * *",  # Every hour
)
```

#### Concurrency Limits

For workflows that should not run in parallel:

```python
from prefect.client.schemas.objects import ConcurrencyLimitStrategy

MY_EXCLUSIVE_WORKFLOW = WorkflowDefinition(
    name="my-exclusive-workflow",
    type=WorkflowType.CORE,
    module="infrahub.mymodule.tasks",
    function="my_exclusive_workflow",
    concurrency_limit=1,
    concurrency_limit_strategy=ConcurrencyLimitStrategy.CANCEL_NEW,
)
```

### Step 5: Add Tags for Context

Use tags to associate workflows with branches or nodes:

```python
from infrahub.workflows.utils import add_tags

@flow(name="my-workflow")
async def my_workflow(branch: str, node_id: str, context: InfrahubContext) -> None:
    await add_tags(branches=[branch], nodes=[node_id])
    # ... rest of implementation
```

`add_tags()` is enough for tags that only annotate a run for a human reading the task list. A tag
another system *filters* on must also be passed at submission — see the caution below and Step 6.

**Caution:** `add_tags()` rebuilds the tag list from the tags present at flow start, not from
what an earlier `add_tags()` call in this same run just set — so if this flow (or a shared helper
it calls, e.g. a recompute dispatcher) calls `add_tags` more than once, only the last call's own
additions survive. Any tag another system filters on (the branch tag, for branch-filtered task
queries) must be passed as a *creation* tag — via `tags=` on `submit_workflow`/`ExecuteWorkflow`,
or the deployment's static `tags=` — not solely through an in-flow `add_tags()` call. See
[Tagging System](../../knowledge/backend/async-tasks.md#tagging-system).

### Step 6: Invoke the Workflow

Trigger the workflow from application code:

```python
from infrahub.workers.dependencies import get_workflow
from infrahub.workflows.catalogue import MY_WORKFLOW
from infrahub.workflows.constants import WorkflowTag

workflow = await get_workflow()
await workflow.submit_workflow(
    workflow=MY_WORKFLOW,
    context=context,
    parameters={"resource_id": "abc123", "branch": branch},
    # Creation tag: branch-scoped task queries filter on this, and a tag added from
    # inside the run does not reach that filter.
    tags=[WorkflowTag.BRANCH.render(identifier=branch)],
)
```

## Using Tasks Within Flows

For granular tracking, break work into tasks:

```python
from prefect import flow, task

@task(name="validate-resource")
async def validate_resource(db: InfrahubDatabase, resource_id: str) -> bool:
    # Validation logic
    return True

@task(name="process-resource")
async def process_resource(db: InfrahubDatabase, resource_id: str) -> None:
    # Processing logic
    pass

@flow(name="my-workflow")
async def my_workflow(resource_id: str, context: InfrahubContext) -> None:
    database = await get_database()
    async with database.start_session() as db:
        is_valid = await validate_resource(db=db, resource_id=resource_id)
        if is_valid:
            await process_resource(db=db, resource_id=resource_id)
```

## Complete Example

Here is a complete example based on branch creation:

```python
# backend/infrahub/mymodule/tasks.py
from __future__ import annotations

from prefect import flow, get_run_logger

from infrahub.context import InfrahubContext  # noqa: TC001
from infrahub.workers.dependencies import get_database, get_event_service
from infrahub.workflows.utils import add_tags


@flow(name="my-resource-process", flow_run_name="Process resource {resource_id}")
async def process_resource(
    resource_id: str,
    branch: str,
    context: InfrahubContext,
) -> None:
    await add_tags(branches=[branch])

    log = get_run_logger()
    log.info(f"Processing resource {resource_id} on branch {branch}")

    database = await get_database()
    async with database.start_session() as db:
        # Load and process the resource
        resource = await load_resource(db=db, resource_id=resource_id)
        await perform_operation(db=db, resource=resource)

    log.info(f"Completed processing resource {resource_id}")
```

```python
# backend/infrahub/workflows/catalogue.py
MY_RESOURCE_PROCESS = WorkflowDefinition(
    name="my-resource-process",
    type=WorkflowType.CORE,
    module="infrahub.mymodule.tasks",
    function="process_resource",
    tags=[WorkflowTag.DATABASE_CHANGE],
)

WORKFLOWS = [
    # ... existing workflows
    MY_RESOURCE_PROCESS,
]
```

## Quality Checklist

Before submitting your workflow:

- [ ] Flow function uses `@flow` decorator with matching `name`
- [ ] Name uses lowercase with dashes (not underscores)
- [ ] `flow_run_name` is clear, short, and user-friendly
- [ ] `flow_run_name` does not duplicate context (branch name, node IDs)
- [ ] `WorkflowDefinition` registered in `catalogue.py`
- [ ] Workflow added to `WORKFLOWS` list
- [ ] Correct `WorkflowType` selected (CORE/USER/INTERNAL)
- [ ] `DATABASE_CHANGE` tag added if workflow modifies database
- [ ] Logs use a Prefect-visible logger (`get_run_logger()` in flows/tasks; `infrahub.log.get_run_logger()` in helpers), never a bare module logger
- [ ] Flow body is a thin composition root — singletons resolved at the flow entry, logic in a dependency-injected component
- [ ] Any other code that needs the workflow's name imports its `WorkflowDefinition` from `catalogue.py` instead of re-typing the string
- [ ] Tests cover workflow execution (using local execution mode)
- [ ] Code passes `uv run invoke lint`

## Related Resources

- [Async Tasks Knowledge](../../knowledge/backend/async-tasks.md) - How the task system works
- [ADR-0003: Asynchronous Tasks](../../adr/0003-asynchronous-tasks.md) - Architectural decision
- [Events System](../../knowledge/backend/events.md) - Event-driven workflow triggers
- [Python Coding Standards](../../guidelines/backend/python.md) - Code style requirements
