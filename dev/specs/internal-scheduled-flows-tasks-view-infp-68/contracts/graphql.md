# Contract: GraphQL surface delta

**Feature**: `internal-scheduled-flows-tasks-view-infp-68`

**Date**: 2026-09-24

This is the complete public-API change. Everything below is additive — no field
is removed, renamed, or has its type or default changed, so no existing query
breaks.

> **Governance note.** `AGENTS.md` lists GraphQL schema modifications under
> **Ask First**, and no human is available during this pipeline. The change is
> therefore stated in full here and in `plan.md` → Assumptions (A1, A2) instead
> of blocking. A reviewer rejecting it can drop the `InfrahubScheduledFlows`
> query (Slice A) or the `workflow_type` argument (Slice B) independently; the
> spec's Delivery Independence section keeps the two separable.

After implementation, regenerate and commit:

```bash
uv run invoke schema.generate-graphqlschema   # schema/schema.graphql
cd frontend/app && pnpm codegen               # generated TS types
```

---

## 1. New enum — `WorkflowTypeEnum`

Built with `Enum.from_enum(WorkflowType)`, the same mechanism `TaskState`
already uses for Prefect's `StateType`
(`backend/infrahub/graphql/types/task.py`). Values follow graphene's convention
of upper-casing member names.

```graphql
enum WorkflowTypeEnum {
  INTERNAL
  CORE
  USER
}
```

The underlying string values stay `internal` / `core` / `user` (spec
Assumption 5 — the API keeps `internal`; only the UI says "System").

---

## 2. Changed — `InfrahubTask(workflow_type: [WorkflowTypeEnum])`

One optional argument added to the existing query (FR-007).

```graphql
InfrahubTask(
  limit: Int
  offset: Int
  related_node__ids: [String]
  branch: String
  state: [StateType]
  workflow: [String]
  workflow_type: [WorkflowTypeEnum]   # NEW
  ids: [String]
  q: String
  log_limit: Int
  log_offset: Int
): Tasks!
```

### Behavioural contract

| Argument value | Selection |
|---|---|
| omitted / `null` | **Unchanged from today**: every run carrying `infrahub.app`. Includes the eight internal workflows that tag themselves at run time (FR-003). |
| `[INTERNAL]` | Runs carrying `infrahub.app/workflow-type/internal`. The namespace tag is **not** additionally required, so runs that ended before reaching `add_tags()` are included (FR-002). |
| `[CORE, USER, INTERNAL]` | Runs carrying any of the three type tags. A strict superset of the omitted case — **not** equivalent to it (FR-004). |
| `[]` (empty list) | `ValidationError`. Not coerced to "unset"; see `data-model.md` §1. |

Composition (FR-005): `workflow_type` AND-s with `branch`, `state`,
`related_node__ids`, `workflow`, `ids`, `q`, and honours `limit`/`offset`.
Multiple types OR together.

Counting (FR-006): `InfrahubTask { count }` applies the identical filter, since
both paths share `FlowRunFilterBuilder.build_flow_run_filter`.

`InfrahubTaskBranchStatus` is untouched — it passes no `workflow_type`, so it
keeps today's namespace-tag selection.

---

## 3. New query — `InfrahubScheduledFlows`

Satisfies FR-009, FR-009a, FR-010, FR-011, FR-012. Takes no arguments: FR-012
requires one request, and FR-009a requires it to cover every scheduled workflow,
so there is nothing to filter by.

```graphql
type Query {
  InfrahubScheduledFlows: ScheduledFlows!
}

type ScheduledFlows {
  "Ordered unhealthy-first, then by name."
  edges: [ScheduledFlowNode!]!
  count: Int!
  "Catalogue workflows that declare a cron but have no registered deployment."
  catalogue_only: [String!]!
}

type ScheduledFlowNode {
  node: ScheduledFlow!
}

type ScheduledFlow {
  deployment_id: String!
  name: String!
  "Null when the deployment carries no Infrahub workflow-type tag."
  workflow_type: WorkflowTypeEnum
  cron: String!
  timezone: String
  "Seconds between consecutive fire times; null when it cannot be derived."
  interval_seconds: Int
  next_run_at: String
  "False when the schedule or the deployment itself is paused."
  active: Boolean!
  concurrency_limit: Int
  "e.g. CANCEL_NEW, ENQUEUE. Explains a CANCELLED verdict."
  collision_strategy: String
  latest_run: ScheduledFlowLatestRun
  recent_outcomes: ScheduledFlowOutcomes!
  health: ScheduledFlowHealthEnum!
  deployment_created_at: String
}

type ScheduledFlowLatestRun {
  id: String!
  state: StateType
  state_name: String
  "Set even for a run that never started — the sort key."
  expected_start_time: String
  "Null for a run cancelled by a CANCEL_NEW collision before it began."
  start_time: String
  end_time: String
}

type ScheduledFlowOutcomes {
  window_hours: Int!
  total: Int!
  counts: [ScheduledFlowOutcomeCount!]!
}

type ScheduledFlowOutcomeCount {
  state: StateType!
  count: Int!
}

enum ScheduledFlowHealthEnum {
  HEALTHY
  FAILED
  CANCELLED
  OVERDUE
  NEVER_RUN
  NO_RECENT_RUNS
  PAUSED
}
```

`counts` is a list of pairs rather than a map because GraphQL has no map type
and the codebase reserves `GenericScalar` for genuinely unstructured payloads
(flow parameters, HTTP headers). A typed list keeps Constitution III's
"no untyped dictionaries for structured data".

Timestamps are ISO-8601 `String`, matching every existing timestamp on
`TaskNodeInterface` (`created_at`, `updated_at`, `start_time`).

### Error contract (FR-013)

Prefect unreachable or erroring ⇒ the exception propagates and the response
carries `errors[]` with `data.InfrahubScheduledFlows = null`. There is no
partial-success shape and no empty-list-on-failure path. The frontend
distinguishes this from "no scheduled flows" and renders the error state
(FR-019).

---

## 4. Frontend query documents

New/changed documents under `frontend/app/src/entities/tasks/api/`:

| File | Change |
|---|---|
| `get-task-list-from-api.ts` | add `$workflowType: [WorkflowTypeEnum]` variable, pass as `workflow_type`; add `tags` to the selection only if needed for the type column — otherwise derive the type column from the new `workflow_type` scalar below |
| `get-task-count-from-api.ts` | add the same variable (FR-022) |
| `get-scheduled-flows-from-api.ts` | **new** — the `InfrahubScheduledFlows` document |

### Also changed — `workflow_type` on `TaskNodeInterface`

FR-025 requires the Tasks list to display each run's workflow type when a Type
filter is active or internal runs are present. The run's type is already present
in `tags` as `infrahub.app/workflow-type/{t}`, but making the client parse a tag
string is exactly the untyped-contract the constitution rejects.

```graphql
interface TaskNodeInterface {
  # ...existing fields unchanged...
  "The run's workflow type, decoded from its workflow-type tag. Null if absent."
  workflow_type: WorkflowTypeEnum
}
```

Resolved by extending `WorkflowTagDecoder`
(`backend/infrahub/task_manager/flow_run/tags.py`) alongside its existing
`branch_name()`, and surfaced through `EnrichedFlowRun.workflow_type`. It is a
pure tag decode — no extra Prefect round-trip, so it costs nothing on the
default list.
