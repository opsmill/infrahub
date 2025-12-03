# ADR-0006: Asynchronous Tasks Execution

## Status

Draft

## Context

Infrahub needs to execute long-running background tasks like branch merges, schema migrations, git operations, and validators. These tasks require orchestration, retry logic, state management, and observability. Tasks may depend on each other and need to be scheduled and monitored.

## Decision

We use Prefect for asynchronous task execution and workflow orchestration. Prefect was selected primarily because it is a pure Python implementation, which makes it easier to completely embed within the Infrahub application code and significantly simplifies testing.

Prefect fulfills three critical functions in Infrahub:

1. **Task Reporting and Execution Tracking**: Prefect provides centralized task reporting, execution state management, and log centralization. All flow runs, their states, progress, and logs are tracked and queryable through Prefect's API and UI, enabling observability and monitoring of asynchronous operations.

2. **Asynchronous Task Execution**: Prefect orchestrates the execution of tasks asynchronously on workers. It supports different types of workers (process-based, async-based, and in the future Kubernetes, Docker, or external workers), providing flexibility in deployment architectures. This allows Infrahub to scale task execution across different environments and infrastructure types.

3. **Event Management and Event-Driven Task Execution**: Prefect provides event storage, querying capabilities, and Prefect Automation to trigger workflows based on event patterns. Events are emitted when state changes occur (node mutations, branch operations, schema updates) and can trigger automated workflows. This enables reactive, event-driven automation where tasks execute in response to system events. See ADR-0009 for detailed information on the events system.

Prefect flows define task dependencies, handle retries, provide state management, and integrate seamlessly with async Python. The pure Python implementation enables the workflow adapter pattern (see Flow Execution Patterns), allowing flows to be executed either through Prefect workers or directly in-process for testing, without requiring Prefect infrastructure in unit and functional tests.

## Architecture Overview

### Components

1. **Prefect Server**: Centralized orchestration server that manages flow runs, deployments, and work pools
2. **Infrahub Workers**: Custom Prefect workers (`InfrahubWorkerAsync`) that execute flows in async event loops
3. **Workflow Definitions**: Declarative configuration for flows registered in `infrahub.workflows.catalogue`
4. **Flow Functions**: Async Python functions decorated with `@flow` that implement business logic
5. **Task Functions**: Async Python functions decorated with `@task` for discrete work units within flows

### Flow Types

Infrahub categorizes workflows into three types:

- **CORE**: Core Infrahub functionality (e.g., branch operations, schema migrations)
- **USER**: User-defined workflows (e.g., generators, transformations, webhooks)
- **INTERNAL**: Internal maintenance tasks (e.g., telemetry, cleanup, scheduled syncs)

## Flow Definition and Registration

### Workflow Catalogue

All workflows are registered in `backend/infrahub/workflows/catalogue.py` as `WorkflowDefinition` objects. Each definition specifies:

- `name`: Unique workflow identifier
- `type`: WorkflowType (CORE, USER, or INTERNAL)
- `module`: Python module path (e.g., `infrahub.git.tasks`)
- `function`: Flow function name
- `cron`: Optional cron schedule for periodic execution
- `tags`: List of workflow tags for filtering and organization
- `concurrency_limit`: Optional limit on concurrent executions
- `concurrency_limit_strategy`: Strategy for handling concurrency limits (e.g., `CANCEL_NEW`)

Example:

```python
BRANCH_MERGE = WorkflowDefinition(
    name="branch-merge",
    type=WorkflowType.CORE,
    module="infrahub.core.branch.tasks",
    function="merge_branch",
    tags=[WorkflowTag.DATABASE_CHANGE],
)
```

### Flow Function Declaration

Flows are defined as async functions decorated with `@flow`:

```python
@flow(
    name="branch-merge",
    flow_run_name="Merge branch '{source_branch}' into '{target_branch}'",
)
async def merge_branch(
    source_branch: str,
    target_branch: str,
    context: InfrahubContext,
    service: InfrahubServices,
) -> None:
    # Flow implementation
    pass
```

Key characteristics:

- Flow names must match the `WorkflowDefinition.name`
- `flow_run_name` supports f-string formatting for dynamic naming
- Flows can accept `InfrahubServices` and `InfrahubContext` parameters (injected by workers)
- Flows are async and can call other flows or tasks

### Task Function Declaration

Tasks are discrete work units within flows:

```python
@task(
    name="git-branch-create",
    task_run_name="Create branch '{branch}' in repository {repository_name}",
    cache_policy=NONE,
)
async def git_branch_create(
    client: InfrahubClient,
    branch: str,
    repository_name: str,
) -> None:
    # Task implementation
    pass
```

Task characteristics:

- Tasks can have retry policies, cache policies, and timeouts
- Tasks are async and can be awaited within flows
- Tasks can call other tasks or flows

## Worker Configuration and Execution

### Custom Worker Implementation

Infrahub implements a custom Prefect worker (`InfrahubWorkerAsync`) that:

- Extends `BaseWorker` from Prefect
- Executes flows in async event loops (not subprocesses)
- Injects `InfrahubServices` into flow parameters automatically
- Configures logging to forward logs to Prefect API
- Initializes Infrahub services (database, cache, message bus) at startup

### Worker Setup

During worker initialization:

1. Loads Infrahub configuration
2. Initializes database connection and validates schema version
3. Sets up component registry
4. Initializes lock system
5. Configures Git global settings
6. Starts metric endpoint (Prometheus)
7. Configures Prefect settings (polling interval, result storage)

### Result Storage

Flow results are stored in Redis using Prefect's `RedisStorageContainer` block:

- Block name: `infrahub-storage`
- Configured during task manager initialization
- Results persist by default (`PREFECT_RESULTS_PERSIST_BY_DEFAULT=True`)

## Flow Execution Patterns

### Workflow Adapter Pattern

Infrahub uses an adapter pattern for workflow execution, allowing flows to be executed through different implementations without changing the calling code. Flows are never called directly; instead, they are executed through the `InfrahubWorkflow` adapter interface.

#### Adapter Interface

The `InfrahubWorkflow` abstract base class defines two methods:

- `execute_workflow()`: Execute a workflow synchronously and wait for completion
- `submit_workflow()`: Submit a workflow asynchronously and return immediately

#### Adapter Implementations

Two adapter implementations are available:

1. **`WorkflowWorkerExecution`** (Production):
   - Submits flows to Prefect server via `run_deployment()`
   - Flows execute on Prefect workers
   - Provides full Prefect features (monitoring, retries, state management)
   - Used in production and integration tests

2. **`WorkflowLocalExecution`** (Testing):
   - Executes flows directly in the same process
   - No Prefect server required
   - Loads flow function and calls it synchronously
   - Used in unit tests and functional tests for easier troubleshooting

#### Adapter Selection

The adapter is selected during service initialization:

```python
from infrahub.services.adapters.workflow.local import WorkflowLocalExecution
from infrahub.services.adapters.workflow.worker import WorkflowWorkerExecution

# For tests - local execution
service = await InfrahubServices.new(workflow=WorkflowLocalExecution())

# For production - Prefect worker execution
service = await InfrahubServices.new(workflow=WorkflowWorkerExecution())
```

#### Benefits

- **Testability**: Unit and functional tests can run without Prefect infrastructure
- **Troubleshooting**: Local execution provides direct stack traces and easier debugging
- **Flexibility**: Easy to switch between execution modes
- **Consistency**: Same API regardless of execution backend
- **Performance**: Local execution avoids network overhead in tests

#### Usage Pattern

Code using workflows accesses them via `get_workflow()` dependency:

```python
from infrahub.workers.dependencies import get_workflow

workflow = get_workflow()
result = await workflow.execute_workflow(
    workflow=BRANCH_MERGE,
    parameters={"source_branch": "feature", "target_branch": "main"},
)
```

The adapter pattern ensures that the same code works in both test and production environments, with the appropriate execution backend selected at initialization time.

## Task Patterns

### Dependency Injection

Flows receive `InfrahubServices` and `InfrahubContext` through parameter injection:

- `InfrahubServices`: Injected by worker based on flow function signature
- `InfrahubContext`: Injected when provided during workflow submission

The worker uses `inject_service_parameter()` to automatically inject these dependencies.

### Dependency Access

Within flows, dependencies are accessed via dependency functions:

- `get_client()`: Infrahub SDK client
- `get_database()`: Database connection
- `get_cache()`: Redis cache
- `get_message_bus()`: Message bus adapter
- `get_workflow()`: Workflow execution adapter
- `get_http()`: HTTP client adapter

### Error Handling

Prefect provides built-in retry mechanisms:

- Task-level retries via `@task(retries=N)`
- Flow-level error handling through Prefect state management
- Failed flows can be retried through Prefect UI or API (not available to the end user)

## Tagging and Filtering

### Tag System

Now Infrahub is using the system of tags internally for capturing additional contexts on the flows that are stored on the prefix hours. There are 5 different types of tags that are listed below that can be attached to a specific flow.
These tags are then used for bus tracking and also for filtering when accessing those flows into InfraHm.
Flows are tagged for organization and filtering:

- **Namespace**: All Infrahub flows tagged with `infrahub.app`
- **Branch Tags**: `infrahub.app/branch/{branch_name}` for branch-related flows
- **Node Tags**: `infrahub.app/node/{node_id}` for node-related flows
- **Database Change Tags**: `infrahub.app/database-change` for flows that modify the database
- **Workflow Type Tags**: `infrahub.app/workflow-type/{type}` for workflow categorization

### Tag Management

Tags are added dynamically within flows:

```python
from infrahub.workflows.utils import add_tags

@flow(name="example-flow")
async def example_flow(branch_name: str, node_id: str) -> None:
    await add_tags(
        branches=[branch_name],
        nodes=[node_id],
        db_change=True,
    )
```

### Flow Filtering

Flow runs can be filtered by:

- Flow name
- Tags (branch, node, workflow type)
- State (running, completed, failed, etc.)
- Time range
- Related nodes

## Deployment and Initialization

### Task Manager Setup

The task manager is initialized via `setup_task_manager()` flow:

1. **Setup Blocks**: Registers Redis storage container
2. **Setup Worker Pools**: Creates work pools (default: `infrahub-worker`)
3. **Setup Deployments**: Registers all workflows from catalogue as deployments
4. **Setup Triggers**: Configures Prefect automations for event-driven flows

### Deployment Registration

Each `WorkflowDefinition` is registered as a Prefect deployment:

- Flow is created/retrieved by name
- Deployment is created with entrypoint, tags, and work pool
- Entrypoint format: `backend/{module_path}:{function_name}` for internal flows
- Entrypoint format: `{module_path}:{function_name}` for user flows

### Scheduled Flows

Flows with `cron` schedules are automatically scheduled:

- Cron schedules parsed and registered with Prefect
- Examples: `git_repositories_sync` runs every minute, `clean_up_deadlocks` runs every minute

### Concurrency Control

Flows can specify concurrency limits:

- `concurrency_limit`: Maximum concurrent executions
- `concurrency_limit_strategy`: How to handle limit (e.g., `CANCEL_NEW` cancels new runs when limit reached)

## Consequences

### Positive

- Built-in retry and error handling
- Task dependencies and orchestration
- State persistence across restarts
- Observability and monitoring (Prefect UI)
- Integration with async Python
- Flow-based programming model
- Dynamic flow loading and execution
- Tag-based filtering and organization
- Event-driven automation via Prefect triggers
- Result persistence in Redis
- Concurrency control and rate limiting

### Negative

- Additional infrastructure (Prefect server)
- Learning curve for Prefect concepts
- Flow definitions add abstraction layer
- Requires Prefect server deployment
- Task state stored in Prefect database
- Worker initialization overhead (database, cache, message bus setup)
- Dynamic flow loading requires careful entrypoint management

## Implementation Details

### Key Files

- `backend/infrahub/workflows/catalogue.py`: Workflow definitions registry
- `backend/infrahub/workflows/models.py`: WorkflowDefinition and related models
- `backend/infrahub/workflows/initialization.py`: Task manager setup flows
- `backend/infrahub/workers/infrahub_async.py`: Custom Prefect worker implementation
- `backend/infrahub/workers/utils.py`: Flow loading and parameter injection utilities
- `backend/infrahub/services/adapters/workflow/worker.py`: Workflow execution adapter
- `backend/infrahub/task_manager/task.py`: Flow run querying and management
- `backend/infrahub/workflows/utils.py`: Tag management utilities
- `backend/infrahub/prefect_server/app.py`: Prefect server integration

### Flow Locations

Flows are organized by domain in task modules:

- `backend/infrahub/git/tasks.py`: Git repository operations
- `backend/infrahub/branch/tasks.py`: Branch operations
- `backend/infrahub/proposed_change/tasks.py`: Proposed change workflows
- `backend/infrahub/generators/tasks.py`: Generator execution
- `backend/infrahub/webhook/tasks.py`: Webhook processing
- `backend/infrahub/computed_attribute/tasks.py`: Computed attribute processing
- And many more...

### Testing

Prefect integration is tested using:

- `prefect_test_fixture`: Starts ephemeral Prefect server for tests
- Prefect test harness for isolated test execution
- Mocked Prefect clients for unit tests
