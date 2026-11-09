# Phase 1 Data Model: Webhook Delivery Operability

No new Neo4j nodes, attributes, relationships, or migrations. All "entities" below are either GraphQL output types or in-process Python models projected from Prefect run data (parameters, tags, artifacts, state). Persistence is Prefect's; retention is Prefect's.

## GraphQL types

### TaskNodeInterface (new interface)

Carries every field currently on the task type, plus `available_actions`. All task results resolve to a concrete implementation of this interface.

| Field | Type | Notes |
|---|---|---|
| id | String! | Prefect flow-run id |
| title | String | Run name |
| conclusion | String | Derived SUCCESS/FAILURE mapping (existing) |
| state | TaskState | Raw Prefect state (existing, source of truth) |
| progress | Float | From the progress artifact (existing) |
| workflow | String | The run's workflow name — the type discriminant |
| branch | String | Originating branch (existing) |
| created_at / updated_at / start_time | DateTime | Existing |
| parameters | GenericScalar | Run parameters; carries the frozen payload for deliveries |
| tags | [String] | Related-node tags (existing) |
| related_nodes | [RelatedNode] | Existing |
| logs | TaskLogEdge | Existing; per-attempt progress visible here |
| available_actions | [TaskAction!]! | NEW — server-computed recovery actions (empty for non-actionable runs) |
| error | TaskError | NEW — classified failure reason + remediation hint; null unless the task failed with one. Deliveries populate it first; hidden by the UI when null |

### TaskNode (unchanged name, standard implementation)

`implements TaskNodeInterface`. Keeps its current name so existing queries / SDK / fragments / `__typename` are unaffected. The only schema change is that `TaskNodes.node` becomes the interface type instead of this object type.

**Derivation mechanism (mirror of events, not subclassing).** Today `TaskNode` derives by subclassing the `Task` ObjectType (`graphql/types/task.py:36`). The events-faithful form moves the common fields onto `TaskNodeInterface(Interface)` and declares each concrete type via `class Meta: interfaces = (TaskNodeInterface,)` — exactly as concrete event types declare `interfaces = (EventNodeInterface,)` (`graphql/types/event.py:101-103`). So:

```python
class TaskNodeInterface(Interface):
    # common fields + available_actions
    @classmethod
    def resolve_type(cls, instance: dict[str, Any], info) -> type[ObjectType]:
        return TASK_TYPES.get(instance["workflow"], TaskNode)

class TaskNode(ObjectType):
    class Meta:
        interfaces = (TaskNodeInterface,)
    # no fields of its own: the deprecated related_node / related_node_kind accessors sit on the
    # interface, because existing consumers select them directly on `node` (no inline fragment)
    # and backward compatibility requires those selections to keep resolving

class WebhookDeliveryTask(ObjectType):
    class Meta:
        interfaces = (TaskNodeInterface,)
    http_request = Field(HttpRequest)
    http_response = Field(HttpResponse)

TASK_TYPES: dict[str, type[ObjectType]] = {WEBHOOK_SEND.name: WebhookDeliveryTask}
```

The `parameters: GenericScalar` field stays on the interface; the frozen payload is read from it, so `WebhookDeliveryTask` adds no payload field of its own (it adds only what is specific to a delivery, mirroring how event concrete types add only their specifics).

### WebhookDeliveryTask (new concrete type)

`implements TaskNodeInterface`, reachable only via `resolve_type`. Adds the delivery-specific fields.

| Field | Type | Notes |
|---|---|---|
| http_request | HttpRequest | URL + redacted headers as sent (last attempt) |
| http_response | HttpResponse | Status, body, latency (last attempt) |

The classified `error` is NOT delivery-specific: it lives on the interface as a capability common to all tasks (same philosophy as `available_actions`), null unless the task failed with a classified reason. Webhook deliveries are the first type to populate it; the UI shows the error section only when it is non-null.

The delivered **payload** is not a field here — it is read from `parameters` (frozen).

### Supporting GraphQL types

```
type HttpRequest      { url: String!, headers: GenericScalar! }            # headers already redacted
type HttpResponse      { status_code: Int, body: String, latency_ms: Float }
type TaskError         { status_class: String!, message: String!, remediation: String! }
type TaskAction        { action: TaskActionName!, available: Boolean!, unavailability_reason: String }
enum TaskActionName    { RETRY, CANCEL }
```

### resolve_type / registration

- `TASK_TYPES: dict[str, type] = { WEBHOOK_SEND.name: WebhookDeliveryTask }` (key = catalogue constant name).
- `TaskNodeInterface.resolve_type(instance, info)`: return `TASK_TYPES.get(instance["workflow"], TaskNode)`.
- The instance dict must carry `workflow` (already serialized) so the discriminant is present.
- GraphQL manager registers each concrete task type (mirror `_load_event_types`).

## In-process Python models (frozen / Pydantic)

### CapturedHeaders

Redaction domain object built at capture time.

| Field | Rule |
|---|---|
| standard headers (`Accept`, `Content-Type`) | verbatim |
| `webhook-id`, `webhook-timestamp` | verbatim (signature inputs, not secret) |
| `webhook-signature` | masked |
| custom header, kind = STATIC | verbatim |
| custom header, kind = ENVIRONMENT | masked |

Entry: `CapturedHeaders.from_resolved(headers_with_kind) -> dict[str, str]` (redacted). Redaction happens before any artifact write, so no raw secret is persisted.

### ClassifiedFailure

| Field | Type | Notes |
|---|---|---|
| status_class | StatusClass (enum) | CONFIG / CONNECTION / TLS / TIMEOUT / HTTP_CLIENT_ERROR / HTTP_SERVER_ERROR / UNKNOWN |
| message | str | Clean, no stacktrace |
| remediation | str | Hint by class (4xx→URL/auth; CONNECTION→reachability; TIMEOUT/5xx→retry/target; CONFIG→webhook config) |
| transient | bool | True for TIMEOUT/CONNECTION/HTTP_SERVER_ERROR; drives `retry_condition_fn` |

Produced by `WebhookFailureClassifier.classify(exc, response) -> ClassifiedFailure` (pure, injected).

### CapturedHttp (artifact payload)

JSON-serializable dict written as the single `http` artifact (key `infrahub-webhook-http`), reflecting the last attempt:

```
{ request:  { url, headers },          # headers redacted
  response: { status_code, body, latency_ms } | null,
  error:    { status_class, message, remediation } | null }
```

Read back via `read_artifacts(ArtifactFilter(key=...), FlowRunFilter(id=...))` (mirrors `read_progress`) and projected onto `http_request` / `http_response` / `error`, gated on GraphQL selection.

### AvailableActions (server computation)

Pure function of `(workflow_name, prefect_state)`:

| Run type | Action | available iff | unavailability_reason |
|---|---|---|---|
| WEBHOOK_SEND | RETRY | state is terminal (COMPLETED / FAILED / CRASHED / CANCELLED) | "Delivery still in progress" |
| WEBHOOK_SEND | CANCEL | state is non-terminal (RUNNING / SCHEDULED / PENDING / AwaitingRetry) | "Delivery already settled" |
| any other | — | (empty list) | — |

RETRY is available on **any terminal state including COMPLETED** (FR-018).

## State model (delivery lifecycle)

Raw Prefect states; the frontend maps presentation labels over them (no backend status enum).

```
            ┌────────────┐  attempt fails (transient, <3)   ┌──────────────┐
 SCHEDULED→ │  RUNNING    │ ───────────────────────────────▶ │ AwaitingRetry │
            └────┬───┬────┘ ◀─────────────── retry fires ─────└──────────────┘
   success ┌─────┘   └────┐ non-transient OR attempts exhausted
           ▼              ▼
      COMPLETED        FAILED ───┐
           │            │        │  (genuine infra crash) → CRASHED
   CANCEL  │            │        │
 (non-term)│            ▼        ▼
           └────────▶ CANCELLING → CANCELLED
```

- Non-terminal: SCHEDULED, PENDING, RUNNING, AwaitingRetry, CANCELLING.
- Terminal: COMPLETED, FAILED, CRASHED, CANCELLED.
- CANCEL: allowed only from non-terminal; flips toward CANCELLED (best-effort for an in-flight request).
- RETRY: allowed only from terminal; produces a **new** run (does not transition the original).
- `status_class` exists only when conclusion is FAILURE.

## Relationships & identity

- A delivery is identified by its Prefect flow-run id (the GraphQL task `id`).
- A delivery references its webhook via the `webhook_id` run parameter and the related-node tag (drives Tasks-tab visibility and authorization).
- A retry produces a new delivery with no parent link; it carries the same `payload` parameter and re-tags itself. Original and retry are independent records.
- Validation rules enforced at boundaries: retry/cancel re-validate `available_actions` server-side at execution (reject stale, FR-026); retry re-checks the original run still exists in retention (FR-020).
