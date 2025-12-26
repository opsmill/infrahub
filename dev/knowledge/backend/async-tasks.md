# Asynchronous Tasks System

> Part of: `dev/knowledge/backend/` | Related: [ADR-0003](../../adr/0003-asynchronous-tasks.md), [Creating Workflows Guide](../../guides/backend/creating-async-tasks.md)

Infrahub uses Prefect as its asynchronous task orchestration framework for workflow execution, scheduling, and observability.

## Architecture Overview

```
Application Code
       │
       ▼
WorkflowDefinition (catalogue.py)
       │
       ▼
Workflow Adapter
       ├──► WorkflowWorkerExecution ──► Prefect Server ──► Workers
       │                                      │
       │                                      └──► Prefect UI/API
       │
       └──► WorkflowLocalExecution (tests)
```

## Workflow Types

| Type | Constant | Purpose | Examples |
|------|----------|---------|----------|
| CORE | `WorkflowType.CORE` | Infrastructure operations | Branch merge, schema migration |
| USER | `WorkflowType.USER` | User-defined workflows | Transforms, generators |
| INTERNAL | `WorkflowType.INTERNAL` | System maintenance | Telemetry, cleanup, git sync |

### CORE Workflows

Core workflows handle trusted infrastructure operations that are part of Infrahub itself. They have full access to internal services and the registry. These workflows are visible in the Infrahub UI and can be triggered via API.

### USER Workflows

User workflows execute untrusted code provided by users (transforms, generators, checks). They are designed with isolation in mind:

- Should not have access to internal registry or privileged services
- Future goal: Execute in a separate, sandboxed system
- Focus on running user-provided code safely

These workflows are visible to end users in the Infrahub UI.

### INTERNAL Workflows

Internal workflows handle system maintenance tasks that users should not interact with directly:

- Not visible to end users in the Infrahub UI
- Used for background operations (telemetry, cleanup, scheduled sync)
- Have full access to internal services

## Core Components

### WorkflowDefinition

Declarative configuration for a workflow registered in the catalogue:

```python
WorkflowDefinition(
    name="branch-merge",
    type=WorkflowType.CORE,
    module="infrahub.core.branch.tasks",
    function="merge_branch",
    tags=[WorkflowTag.DATABASE_CHANGE],
    cron=None,  # Optional: "* * * * *" for scheduled
    concurrency_limit=1,  # Optional
    concurrency_limit_strategy=ConcurrencyLimitStrategy.CANCEL_NEW,
)
```

### Flow Functions

Async functions decorated with `@flow` containing business logic:

```python
@flow(name="branch-merge", flow_run_name="Merge branch {branch}")
async def merge_branch(branch: str, context: InfrahubContext) -> None:
    database = await get_database()
    # ... implementation
```

### Task Functions

Discrete work units decorated with `@task` for granular tracking:

```python
@task(name="validate-schema")
async def validate_schema(db: InfrahubDatabase, branch: Branch) -> bool:
    # ... implementation
```

## Naming Conventions

### Workflow and Task Names

Names must use **lowercase with dashes** (not underscores):

- Good: `branch-merge`, `schema-validate`, `artifact-generate`
- Bad: `branch_merge`, `BranchMerge`, `branchMerge`

All flows and tasks must have an explicit `name` parameter in their decorator.

### Flow Run Names

The `flow_run_name` is visible to users in the Infrahub UI and should be:

- **Clear and concise**: Users should immediately understand what the flow does
- **Short**: Avoid lengthy descriptions
- **Non-redundant**: Do not include information already available in the flow context

**Do not include in `flow_run_name`:**
- Branch name (except for branch creation workflows)
- Node IDs of related objects
- Information already visible in the UI context

**Good examples:**
```python
@flow(name="branch-create", flow_run_name="Create branch {branch}")  # Branch name OK here
@flow(name="artifact-generate", flow_run_name="Generate artifact {artifact_name}")
@flow(name="schema-migrate", flow_run_name="Apply schema migrations")
```

**Bad examples:**
```python
# Too much context duplication
@flow(name="branch-merge", flow_run_name="Merge branch {branch} (id: {branch_id}) into main")
# Node IDs not useful to users
@flow(name="node-update", flow_run_name="Update node {node_id} on branch {branch}")
```

## Tagging System

Workflows receive metadata tags for organization and filtering:

| Tag | Format | Purpose |
|-----|--------|---------|
| Namespace | `infrahub.app` | Base namespace for all tags |
| Branch | `infrahub.app/branch/{name}` | Associate with specific branch |
| Node | `infrahub.app/node/{id}` | Associate with specific node |
| Workflow Type | `infrahub.app/workflow-type/{type}` | Categorize by type |
| Database Change | `infrahub.app/database-change` | Flag database-modifying workflows |

## Execution Flow

1. **Registration**: Workflows defined in `catalogue.py` are registered on startup
2. **Deployment**: Task manager creates Prefect deployments for each workflow
3. **Triggering**: Workflows triggered via API, events, or cron schedules
4. **Execution**: Workers pick up and execute flows
5. **Tracking**: State and logs aggregated in Prefect

## Concurrency Control

Workflows can specify concurrency limits:

- `concurrency_limit`: Maximum concurrent executions
- `concurrency_limit_strategy`: Behavior when limit reached
  - `CANCEL_NEW`: Reject new executions
  - `ENQUEUE`: Queue for later execution

Example: `GIT_REPOSITORIES_SYNC` uses `concurrency_limit=1` with `CANCEL_NEW` to prevent overlapping sync operations.

## Dependency Injection

Services are injected into flows using `fast-depends`:

```python
from infrahub.workers.dependencies import get_database, get_workflow

database = await get_database()
workflow = await get_workflow()
```

Available dependencies:
- `get_database()`: Database connection
- `get_workflow()`: Workflow service for submitting child flows
- `get_event_service()`: Event emission service
- `get_component()`: Component registry access

## Key Locations

| Component | Location |
|-----------|----------|
| Workflow catalogue | `backend/infrahub/workflows/catalogue.py` |
| Workflow models | `backend/infrahub/workflows/models.py` |
| Constants & types | `backend/infrahub/workflows/constants.py` |
| Initialization | `backend/infrahub/workflows/initialization.py` |
| Branch tasks | `backend/infrahub/core/branch/tasks.py` |
| Git tasks | `backend/infrahub/git/tasks.py` |
| Schema tasks | `backend/infrahub/core/migrations/schema/tasks.py` |

## See Also

- [ADR-0003: Asynchronous Tasks](../../adr/0003-asynchronous-tasks.md) - Why we use Prefect
- [Creating Workflows Guide](../../guides/backend/creating-async-tasks.md) - How to create a new workflow
- [Events System](events.md) - Event-driven workflow triggers
- [Backend Architecture](architecture.md) - Overall backend structure
