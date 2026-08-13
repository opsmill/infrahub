# Asynchronous Tasks System

> Part of: `dev/knowledge/backend/` | Related: [ADR-0003](../../adr/0003-asynchronous-tasks.md), [Creating Workflows Guide](../../guides/backend/creating-async-tasks.md)

Infrahub uses Prefect as its asynchronous task orchestration framework for workflow execution, scheduling, and observability.

## Architecture Overview

```text
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

Async functions decorated with `@flow`. A flow function is a **composition root, not the home of business logic**: it resolves the singleton services (`get_database()`, `get_workflow()`, …), builds a component with those dependencies injected, and delegates to it. Keep the flow body thin — the logic lives in the component, where it is testable without a running worker (see `.agents/rules/backend-component-design.md`).

```python
@flow(name="branch-merge", flow_run_name="Merge branch {branch}")
async def merge_branch(branch: str, context: InfrahubContext) -> None:
    database = await get_database()
    async with database.start_session() as db:
        merger = BranchMerger(db=db, diff_coordinator=..., ...)  # collaborators injected here
        await merger.merge()
```

Singleton getters belong at this entry point only — do not call `get_database()`/`get_workflow()` inside helper functions or component internals; pass the resolved services down as constructor arguments.

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

**Reference workflow names via the catalogue, never as re-typed string literals.** When code outside the flow needs a workflow's name — dispatching it, filtering its flow runs, labelling metrics — import the `WorkflowDefinition` from `backend/infrahub/workflows/catalogue.py` and use it (e.g. pass `workflow=WEBHOOK_PROCESS`, or read `WEBHOOK_PROCESS.name`). A duplicated literal drifts silently when the flow is renamed.

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

Tags come from two moments, and the difference matters: tags present at run creation (the deployment's static tags plus any `tags=` passed to `submit_workflow`) survive for the run's lifetime, while tags added mid-run via `add_tags` are rebuilt from the tags known at flow start, so a later in-flow tag update drops anything another in-flow update added before it. A tag that filtering depends on (the branch tag for branch-filtered task queries, for example) must therefore be passed at submission, not added from inside the flow.

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

## Priority Lanes

Every workflow runs in one of three priority lanes, each backed by a Prefect work queue on the shared worker pool:

| Lane | Queue name | Queue precedence |
|------|------------|------------------|
| High | `high` | 1 (served first) |
| Medium | `medium` | 2 |
| Low | `low` | 3 (served last) |

The lanes are modeled by the `WorkflowPriority` enum (`backend/infrahub/workflows/constants.py`); `setup_work_queues` in `backend/infrahub/workflows/initialization.py` provisions the three queues idempotently at task-manager setup (creating missing queues, re-asserting precedence on existing ones). Workers drain all three queues; precedence only matters under contention — a lower number is served first, and nothing preempts a run that already started.

Each `WorkflowDefinition` declares a `default_priority` (defaults to `WorkflowPriority.MEDIUM`), which becomes the `work_queue_name` of its Prefect deployment. Both dispatch entry points of the workflow adapter (`execute_workflow`, `submit_workflow`) also accept an optional `priority` argument that overrides the resolved priority for that dispatch — and, because the value is stamped into an `InfrahubContext` when one is passed, re-roots the priority for the dispatched flow's whole subtree. Routing is a static tier-to-queue mapping — no per-dispatch queue lookup or existence check.

### Priority Inheritance

Priority is a property of the whole task tree, not of individual workflows: a tree runs at its root's effective priority, and catalogue defaults only ever seed tree roots.

**Context field.** `InfrahubContext` (`backend/infrahub/context.py`) carries an optional `priority: WorkflowPriority | None = None`. Because the context already travels from parent flow to child flow as a flow parameter, it is the vehicle that propagates the lane across dispatch hops. Context payloads serialized before the field existed deserialize with `priority=None`.

**Resolution chain.** At every dispatch, the effective priority is resolved by a strict precedence chain, implemented once in `resolve_priority()` (`backend/infrahub/services/adapters/workflow/priority.py`) and shared by both adapters:

1. The explicit `priority` argument at the call site, when given.
2. The `priority` carried by the dispatched `InfrahubContext`, when set.
3. The workflow's catalogue `default_priority`.

Inheritance is exact — the resolved value is never floored, capped, or combined with the child workflow's catalogue default. A low-priority tree dispatching a catalogue-high child runs that child low; anything else would let bulk background trees elbow into the interactive lane.

**Copy-and-stamp semantics.** The companion `prepare_dispatch()` helper stamps the resolved priority into a *copy* of the context (`context.model_copy(update={"priority": effective})`) and injects the copy into the child's flow parameters — the caller's context object is never mutated, so several sub-dispatches from the same context with different explicit overrides do not interfere. Stamping happens on every dispatch that carries an `InfrahubContext`, including when the value came from the catalogue default, so descendants at depth ≥ 2 inherit correctly. An explicit override mid-tree re-roots the priority for that subtree. The worker adapter routes the run explicitly (`work_queue_name`) only when the argument or the context supplied the value; when only the catalogue default applies, the run inherits its deployment's queue — same lane, no explicit routing instruction. The local (test) adapter applies the same resolution and stamping but performs no queue routing.

**Where the chain stops.** Inheritance ends at any hop that cannot carry the context forward:

- Flows that declare only an `EventContext` parameter: the context is converted via `to_event_context()`, which carries no priority. Events are a deliberate boundary — event-triggered workflows are new tree roots whose priority comes from their own classification, not from the emitting task's lane.
- Flows that declare no context parameter at all: the flow itself is routed correctly (its dispatch site resolved and routed the priority), but it has no context to forward, so its own sub-dispatches fall back to catalogue defaults.
- Cron-scheduled runs: created by the scheduler without passing through the dispatch path; their trees start at catalogue defaults.

**Operator visibility.** The stamped priority is visible in the task manager: for flows that declare an `InfrahubContext` parameter, the flow run's parameters include the injected context, whose `priority` field shows the effective lane the dispatch resolved — alongside the queue the run actually landed on. Flows that declare only an `EventContext` parameter receive a converted, priority-less context, so only the queue reveals their lane.

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

## Logging

Prefect only surfaces logs from its own run logger plus the loggers named in the worker's task-logger set — `DEFAULT_TASK_LOGGERS = ["infrahub.tasks"]` in `backend/infrahub/workers/infrahub_async.py`, extended by `config.SETTINGS.workflow.extra_loggers`. A bare `logging.getLogger(__name__)` sits outside that set, so its records never reach the task manager.

- **Inside a `@flow` or `@task` body**, use Prefect's `get_run_logger()`.
- **In a plain helper** that runs inside a flow but is not itself decorated — so it has no Prefect run context, and is typically also called directly from tests — use `infrahub.log.get_run_logger()`. It returns the `infrahub.tasks` stdlib logger, which the worker registers with Prefect and which is safe to call with no run context (Prefect's own `get_run_logger()` raises outside a run).

## Read Query Optimization in Prefect Tasks

When a flow only needs a few fields from a node (e.g. `id`, `name`, `status`), avoid `client.all()`, `client.filters()`, or `client.get(prefetch_relationships=True)` — they fetch the full object graph. Use a targeted `execute_graphql()` call instead.

### Pattern: typed query model

Each domain that needs optimized reads defines a Pydantic query model co-located in its `models.py` (or `queries.py` for large files):

```python
from typing import Any, ClassVar
from infrahub_sdk.graphql import Query
from pydantic import BaseModel, ConfigDict


class MyNodeResult(BaseModel):
    model_config = ConfigDict(frozen=True)
    id: str
    name: str


class MyNodeQuery(BaseModel):
    query_name: ClassVar[str] = "MyFetchNodes"
    kind: str  # or hardcoded if always the same type

    def render_query(self) -> str:
        query = Query(
            name=self.query_name,
            query={self.kind: {"edges": {"node": {"id": None, "name": {"value": None}}}}},
        )
        return query.render()

    def parse_response(self, response: dict[str, Any]) -> list[MyNodeResult]:
        result: list[MyNodeResult] = []
        if kind_payload := response.get(self.kind):
            for edge in kind_payload.get("edges", []):
                if node := edge.get("node"):
                    node_id = node.get("id")
                    name = (node.get("name") or {}).get("value")
                    if node_id and name:
                        result.append(MyNodeResult(id=node_id, name=name))
        return result
```

Call it in the flow:

```python
client = get_client()
q = MyNodeQuery(kind="CoreTag")
response = await client.execute_graphql(query=q.render_query(), branch_name=branch_name)
nodes = q.parse_response(response=response)
```

### When to use each approach

| Situation | Approach |
|-----------|----------|
| Need only `id` (fan-out pattern) | Subclass `NodeIDQuery` from `infrahub.core.query.node_query` |
| Need a few scalar/relationship fields, read-only | Standalone query model with `execute_graphql()` |
| Need to mutate the fetched node afterwards | Keep `client.get()` / `client.filters()` with `include=[...]` to narrow fetched fields; use `do_full_update=False` on `.update()` |

### Existing query model base

`NodeIDQuery` in `backend/infrahub/core/query/node_query.py` is the base class for queries that only need the `id` field. Subclass it with a unique `query_name: ClassVar[str]` for each domain:

```python
from infrahub.core.query.node_query import NodeIDQuery

class DisplayLabelNodeIDQuery(NodeIDQuery):
    query_name: ClassVar[str] = "DisplayLabelFetchNodeIDs"
```

Existing examples: `DisplayLabelNodeIDQuery`, `HFIDNodeIDQuery`, `ComputedAttributeNodeIDQuery` (all-node fan-out); `GitRepositoryNodeQuery`, `GeneratorInstanceQuery`, `ComputedAttributeTransformQuery` (multi-field reads).

## Failure handling

### A subflow succeeds only when it is completed

When inspecting a subflow's terminal state, gate on `state.is_completed()`, not on the negation of `state.is_failed()`. `is_failed()` is only one terminal failure mode — a `CANCELLED` or `CRASHED` subflow is not failed but is also not a success, so `if not state.is_failed(): return` reports those as success. Treat "completed" as the only success and every other terminal state as a failure.

### Observability side-writes must never change the primary outcome

A write whose only purpose is observability — persisting a Prefect artifact that captures a request/response, emitting a metric, invoking a metrics-observer callback — is best-effort by definition. It must be exception-isolated (catch, log a warning, continue) so that its failure can never fail, retry, or alter the outcome of the operation it observes: a webhook delivery that succeeded must not be reported as failed because the capture artifact could not be written, and a metrics callback raising must not corrupt lock/pool state. The primary operation's result is decided before and independently of the telemetry write.

### Post-commit follow-up work is best-effort

Work dispatched *after* an operation has already committed — the recompute and event-send follow-ups after a merge, for example — must not be able to fail or roll back the committed operation. The contract to follow for such work is log-and-continue: catch per item, log the skipped item at exception level so a partial failure is greppable rather than silent, and carry on with the rest of the batch so one failed dispatch never aborts the others. Guaranteeing eventual consistency after a transient dispatch failure is the job of a separate reconciliation/backfill job, not of the best-effort path — do not bolt retries onto it. (Not every post-commit path enforces this yet — the merge recompute does per-item; verify before assuming a given caller isolates failures.)

### Transient database errors are retried at the transaction layer, not by task retry

A Prefect task retry re-runs the failed task and by default waits no time between attempts. When a batch of concurrent tasks contend for the same nodes, each deadlocking task retries at the same moment and deadlocks again. Transient database errors therefore belong to the transaction-layer retry (`retry_db_transaction`), which reopens a fresh transaction after an exponential backoff with jitter so contending writers separate; the task-level retry remains the outer fallback. A transaction-owning write path invoked from a task must carry `retry_db_transaction` and let retriable errors reach that owner. See [Database Schema — Transaction Retry](database-schema.md#transaction-retry).

## Recovery actions

A task run can expose recovery actions through the GraphQL `Task` type's `available_actions` field, gated by the run's current state. `TaskActionGenerator` derives the action set per workflow, and `InfrahubTaskRetry` and `InfrahubTaskCancel` carry the actions out. Only `WEBHOOK_SEND` runs expose actions today; see [Webhooks](webhooks.md) for the delivery-specific behavior.

## Task typing (polymorphic)

A task result is polymorphic by the run's workflow name, mirroring the events type hierarchy. `TaskNodeInterface` carries every field common to all tasks, including `available_actions` and the classified `error`, and each concrete type declares `interfaces = (TaskNodeInterface,)`. `TaskNodeInterface.resolve_type` returns `TASK_TYPES.get(instance["workflow"], TaskNode)`, so the discriminant is the run's workflow name (already serialized as the `workflow` field). `TASK_TYPES` maps a catalogue workflow name to its concrete type (`{WEBHOOK_SEND.name: WebhookDeliveryTask}`); anything unmapped resolves to `TaskNode`. Concrete types are registered in the GraphQL manager, mirroring `_load_event_types`.

Because the discriminant is intrinsic to every run, historical runs type correctly with no backfill and no stored `task_type` field. A concrete type adds only its own fields (`WebhookDeliveryTask` adds `http_request` / `http_response`; see [Webhooks](webhooks.md)); shared capabilities stay on the interface.

`TaskNodes.node` is the interface type, not a concrete object. The change is backward-compatible: `TaskNode` keeps its name, so existing selections of common fields, SDK usage, and `__typename` checks keep resolving. The deprecated `related_node` / `related_node_kind` accessors live on the interface rather than on `TaskNode`, because existing consumers select them directly on `node` without an inline fragment, and those selections must keep resolving.

## Liveness and zombie detection

A running flow emits a `prefect.flow-run.heartbeat` event on a fixed interval while it executes. The `crash-zombie-flows` system automation watches for the absence of these events: it keeps a per-run countdown that every expected event restarts, and marks a run `CRASHED` once the countdown lapses. This reaps runs whose worker process died without recording a terminal state, which would otherwise stay `RUNNING` indefinitely.

A run waiting out a retry backoff emits nothing while it waits. The retry-wait transition is therefore registered as an expected event, anchoring the countdown at the start of that silence, and the detection window is sized above the longest configured retry backoff so a run waiting between attempts is not mistaken for a dead process. The window is derived from the webhook send retry delay plus a margin rather than hardcoded, so the relationship holds if the backoff changes. A run whose process genuinely died still lapses the window and is crashed, at the cost of the widened detection latency.

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
| System automations | `backend/infrahub/trigger/system.py` |

## See Also

- [ADR-0003: Asynchronous Tasks](../../adr/0003-asynchronous-tasks.md) - Why we use Prefect
- [Creating Workflows Guide](../../guides/backend/creating-async-tasks.md) - How to create a new workflow
- [Events System](events.md) - Event-driven workflow triggers
- [Webhooks](webhooks.md) - Primary consumer of events and async tasks
- [Backend Architecture](architecture.md) - Overall backend structure
- [Computed Attributes](computed-attributes.md) - Jinja2 local recomputation is inline, not async
