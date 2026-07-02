# GraphQL Contract: Webhook Delivery Operability

The authoritative schema is generated (`schema/schema.graphql`, frontend codegen). This file is the design-time contract the implementation must produce. SDL is illustrative — field names are normative, exact Graphene wiring follows the events/branch precedents.

## Query — task typing (object → interface)

`InfrahubTask` already exists; the change makes its node a polymorphic interface.

```graphql
interface TaskNodeInterface {
  id: String!
  title: String
  conclusion: String
  state: TaskState
  progress: Float
  workflow: String          # discriminant (run's workflow name)
  branch: String
  created_at: DateTime
  updated_at: DateTime
  start_time: DateTime
  parameters: GenericScalar  # carries the frozen payload for deliveries
  tags: [String]
  related_nodes: [RelatedNode!]
  logs(...): TaskLogEdge
  available_actions: [TaskAction!]!   # NEW — empty list for non-actionable runs
  error: TaskError                    # NEW — classified failure reason; null unless the task failed with one
}

type TaskNode implements TaskNodeInterface { ...all interface fields... }

type WebhookDeliveryTask implements TaskNodeInterface {
  # ...all interface fields...
  http_request: HttpRequest
  http_response: HttpResponse
}

type HttpRequest  { url: String!, headers: GenericScalar! }   # headers already redacted at capture
type HttpResponse { status_code: Int, body: String, latency_ms: Float }
type TaskError    { status_class: String!, message: String!, remediation: String! }

type TaskAction { action: TaskActionName!, available: Boolean!, unavailability_reason: String }
enum TaskActionName { RETRY, CANCEL }
```

**Backward compatibility**: `TaskNodes.node` changes from `TaskNode` (object) to `TaskNodeInterface`. Existing selections of common fields continue to resolve. `TaskNode` keeps its name, so SDK / fragments / `__typename` checks for `TaskNode` are unaffected. `WebhookDeliveryTask` is reachable only through `resolve_type` and must be registered explicitly.

### Example consumer query

```graphql
query GET_TASK_DETAILS($ids: [String], $relatedNodeIds: [String]) {
  InfrahubTask(ids: $ids, related_node__ids: $relatedNodeIds) {
    count
    edges {
      node {
        id
        title
        state
        conclusion
        workflow
        updated_at
        available_actions { action available unavailability_reason }
        error { status_class message remediation }
        ... on WebhookDeliveryTask {
          http_request  { url headers }
          http_response { status_code body latency_ms }
        }
      }
    }
  }
}
```

## Mutations — generic task actions

Bespoke (non-CRUD) mutations modeled on `BranchCreate`, registered as direct fields on the base mutation. The interface is generic (task id); only webhook deliveries are actionable.

```graphql
input TaskActionInput { id: String! }

type TaskRetry {
  ok: Boolean!
  task: TaskNodeInterface     # the NEW delivery produced by the retry
}

type TaskCancel {
  ok: Boolean!
  task: TaskNodeInterface     # the cancelled (now non-terminal→cancelling) delivery
}

extend type Mutation {
  InfrahubTaskRetry(data: TaskActionInput!): TaskRetry
  InfrahubTaskCancel(data: TaskActionInput!): TaskCancel
}
```

### Behavioral contract

**InfrahubTaskRetry(id)**
- Auth: requires update permission on the target webhook node (resolved from the run's `webhook_id`). Mutating op ⇒ authentication required.
- Precondition: target is a `WEBHOOK_SEND` run in a **terminal** state (any, including COMPLETED). Otherwise → error "retry unavailable: delivery still in progress".
- Not found: original run purged from retention → error "delivery no longer available" (FR-020).
- Effect: read frozen `parameters` by id; resubmit `WEBHOOK_SEND` with the same `{webhook_id, webhook_kind, webhook_name, payload}`; new standalone run re-tags + re-resolves config + re-signs. Original unchanged. Returns the new task.
- Re-validates availability at execution (rejects a stale action, FR-026).

**InfrahubTaskCancel(id)**
- Auth: same as retry.
- Precondition: target is a `WEBHOOK_SEND` run in a **non-terminal** state. Otherwise → error "cancel unavailable: delivery already settled".
- Effect: set run state to CANCELLING. Stops further scheduled auto-retries. Best-effort for an in-flight request (not recalled). Returns the task.

### Error surface

Errors are returned as GraphQL errors with clean messages (no stacktrace, Principle VI). Classified delivery failures are surfaced on the run's `error` field, not as mutation errors — a resubmitted run that later fails carries its `TaskError` like any delivery.

## Non-goals (contract scope)

- No change to existing task list filters/pagination.
- No new global permission type.
- No webhook-specific mutation names (`CoreWebhookRetry`/`CoreWebhookCancel` are explicitly **not** introduced).
