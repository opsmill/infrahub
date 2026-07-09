# Webhooks

> Part of: `dev/knowledge/backend/` | Related: [Events](events.md), [Async Tasks](async-tasks.md)

Infrahub webhooks deliver HTTP notifications to external systems when events occur. They use Prefect automations for event matching and trigger a delivery pipeline that supports raw payloads, optional HMAC signing, and user-defined Python transforms.

## Architecture Overview

```text
GraphQL Mutation (create/update/delete webhook)
       │
       ▼
Built-in Trigger (TRIGGER_WEBHOOK_CONFIGURE)
       │
       ▼
configure_webhook flow
       │
       ├─ WebhookAction.CONFIGURE ──► _configure_one()
       │     ├──► Creates/updates Prefect Automation
       │     └──► Clears Redis cache
       │
       ├─ WebhookAction.DELETE ──► _delete_automation()
       │     ├──► Deletes Prefect Automation
       │     └──► Clears Redis cache
       │
       └─ WebhookAction.RECONCILE_ALL ──► _reconcile_all()
             └──► Full sync via setup_triggers_specific()

KeyValue update (header value changed)
       │
       ▼
Built-in Trigger (TRIGGER_KEYVALUE_WEBHOOK_INVALIDATE)
       │
       ▼
invalidate_webhook_headers flow
       └──► Queries webhooks referencing the changed KeyValue
       └──► Invalidates their cache entries

                                          ┌─────────────────────┐
Application Event (e.g. node.created) ──► │ Prefect Automation   │
                                          │ (event matching)     │
                                          └────────┬────────────┘
                                                   │
                                                   ▼
                                          webhook_process flow
                                                   │
                                          ┌────────┴────────┐
                                          │ Load webhook     │
                                          │ (cache or DB)    │
                                          └────────┬────────┘
                                                   │
                                          ┌────────┴────────┐
                                          │ Compute payload  │
                                          └────────┬────────┘
                                                   │
                                                   ▼
                                          webhook_send subflow
                                                   │
                                          ┌────────┴────────┐
                                          │ Build headers    │
                                          │ + HMAC signing   │
                                          └────────┬────────┘
                                                   │
                                                   ▼
                                          HTTP POST to target URL
```

## Webhook Types

Three webhook types form a class hierarchy inheriting from the `Webhook` base class:

| Type | Class | Payload Behavior | Signing |
|------|-------|------------------|---------|
| Standard | `StandardWebhook` | Raw event data + context | Required (`shared_key` is mandatory) |
| Custom | `CustomWebhook` | Raw event data + context | Optional |
| Transform | `TransformWebhook` | Runs a `CoreTransformPython` from a Git repo | Optional |

- **StandardWebhook** and **CustomWebhook** both send `{"data": <event_data>, ...context}` as payload. The difference is schema-level: `CoreCustomWebhook` has an optional `transformation` relationship.
- **TransformWebhook** is instantiated when a `CoreCustomWebhook` has a linked `CoreTransformPython`. It checks out the transform's Git repository, executes the Python class, and uses the transform output as the payload.

## Data Models

### `WebhookTriggerDefinition`

Bridges Infrahub webhooks to Prefect automations. Extends `TriggerDefinition` with webhook-specific name generation (`webhook:<id>`). `WebhookTriggerDefinitionBuilder.build()` converts a `CoreWebhook` node into a `WebhookTriggerDefinition`, including:

- Event pattern matching (`infrahub.*` for "all", or specific event type)
- Branch filtering via `match_related` (default branch, other branches, or all)
- Node kind filtering via `match` (only for node-level events)

The action parameters that carry event data to `webhook_process` (event id, occurred time, branch, payload) are rendered server-side by Prefect; see [Trigger action parameters](events.md#trigger-action-parameters) for how single-expression values are emitted as Jinja templates.

### `EventContext`

Normalized representation of the event extracted from Prefect's raw event payload. Contains `id`, `branch`, `account_id`, `occured_at`, and `event` type. Created via `from_event()` which parses the nested context structure from Prefect.

### `WebhookHeader`

Pydantic model for a custom HTTP header: `key` (str), `value` (str), `kind` (Literal `"static"` | `"environment"`). The `resolve()` method returns the header value — for `"static"` it returns the value directly, for `"environment"` it looks up the environment variable and raises `WebhookHeaderResolutionError` if the variable is missing, which fails the delivery with a configuration error rather than sending the request without that header.

### `Webhook` class hierarchy

`Webhook` (base) → `StandardWebhook`, `CustomWebhook`, `TransformWebhook`

The base class handles:

- Payload computation (`compute_payload`)
- Header construction with custom headers and optional HMAC signing (`build_headers`)
- Redaction of secret-bearing header values for logging (`redact_headers`)
- HTTP delivery of a precomputed payload via `send_payload()`, which builds the headers itself unless a caller passes a set already built for logging
- Cache serialization (`to_cache` / `from_cache`)

The `custom_headers: list[WebhookHeader]` field on the base `Webhook` class holds headers loaded from the `CoreWebhook.headers` relationship. During `build_headers()`, custom headers are applied after system defaults (Accept, Content-Type) but before HMAC signature headers. Static headers use the value directly; environment headers resolve from `os.environ` at send time. A missing variable fails the delivery with a configuration error (the `CONFIG` failure class) rather than being skipped.

## Schema (GraphQL)

Defined in `backend/infrahub/core/schema/definitions/core/webhook.py`:

- **`CoreWebhook`** (generic base, `GenericSchema`): shared attributes for all webhook types
- **`CoreStandardWebhook`** (`NodeSchema`): inherits `CoreWebhook` + `CoreTaskTarget`, adds required `shared_key`
- **`CoreCustomWebhook`** (`NodeSchema`): inherits `CoreWebhook` + `CoreTaskTarget`, adds optional `shared_key` and optional `transformation` relationship to `CoreTransformPython`

All webhooks are branch-agnostic (`BranchSupportType.AGNOSTIC`).

### Key Attributes

| Attribute | Kind | Default | Description |
|-----------|------|---------|-------------|
| `name` | Text | — | Unique identifier |
| `event_type` | Text | `"all"` | Specific event or `"all"` |
| `active` | Boolean | `true` | Enable/disable toggle |
| `branch_scope` | Dropdown | `"default_branch"` | `all_branches` / `default_branch` / `other_branches` |
| `node_kind` | Text | — | Optional node type filter (only valid for node-level events) |
| `description` | Text | — | Optional description |
| `url` | URL | — | Target delivery endpoint |
| `validate_certificates` | Boolean | — | TLS certificate validation |
| `shared_key` | Password | — | HMAC signing secret |

## Lifecycle

### 1. Registration

Webhooks are created via standard GraphQL mutations (`CoreStandardWebhookCreate`, `CoreCustomWebhookCreate`). The `InfrahubWebhookMutation` class validates:

- `node_kind` references a valid schema kind
- `node_kind` is only set for node-level event types (created, updated, deleted)

### 2. Trigger Setup

When a webhook node is created, updated, or deleted, the single built-in trigger `TRIGGER_WEBHOOK_CONFIGURE` fires, invoking the `configure_webhook` flow. The flow parses the event into a `WebhookConfigureParams` (using the `EVENT_TO_ACTION` mapping from `constants.py`) and routes to the appropriate handler:

- **`WebhookAction.CONFIGURE`** (node created/updated) → `_configure_one()`:
  1. Fetches the webhook node via the SDK
  2. Builds a `WebhookTriggerDefinition` from the node
  3. Queries existing Prefect automations for a matching name
  4. Creates or updates the Prefect automation
  5. Clears the Redis cache for that webhook
  6. If the webhook is inactive, deletes the automation instead

- **`WebhookAction.DELETE`** (node deleted) → `_delete_automation(webhook_id)`:
  1. Constructs the automation name from the webhook ID
  2. Deletes the Prefect automation if it exists
  3. Clears the Redis cache

- **`WebhookAction.RECONCILE_ALL`** (scheduled/no event) → `_reconcile_all()`:
  1. Queries all active webhooks from the database
  2. Delegates to `setup_triggers_specific()` for full sync

### 3. Event Matching

Prefect automations match events based on the trigger configuration:

- **Event type**: `infrahub.*` (all) or a specific event like `infrahub.node.created`
- **Branch scope**: uses `match_related` with `infrahub.resource.label` to filter by branch name (negation prefix `!` for "other branches")
- **Node kind**: uses `match` with `infrahub.node.kind` (only applies to node-level events)

### 4. Processing and Delivery

When a matched event fires, Prefect runs the `webhook_process` flow:

1. Checks Redis cache for webhook data (`webhook:<id>`, 2-hour TTL)
2. On cache miss, fetches the webhook node from the database and caches it
3. Deserializes the webhook using the `WEBHOOK_MAP` type registry
4. Builds `EventContext` from the raw event
5. Calls `webhook.compute_payload()` to build the payload
6. Hands the payload to the `webhook_send` subflow, which resolves the webhook config, builds the headers (with optional HMAC), and POSTs to the target URL

The `webhook_send` subflow has 3 retries configured and calls `response.raise_for_status()`. `webhook_process` invokes it directly as a subflow, and it is also registered in the workflow catalogue as `WEBHOOK_SEND` so a settled delivery can be re-submitted as an independent run when retried.

## Failure handling

When a delivery fails, `WebhookFailureClassifier.classify()` maps the cause (and any HTTP response) to a stable `StatusClass`, so the run surfaces a clean reason instead of a raw stacktrace:

| Class | Cause | Transient |
|-------|-------|-----------|
| `CONFIG` | A configured header value cannot be resolved (for example an unset environment variable) | No |
| `CONNECTION` | The target endpoint is unreachable | Yes |
| `TLS` | The target's certificate cannot be validated | No |
| `TIMEOUT` | The target did not respond within the configured timeout | Yes |
| `HTTP_CLIENT_ERROR` | The target returned a 4xx status | No |
| `HTTP_SERVER_ERROR` | The target returned a 5xx status | Yes |
| `UNKNOWN` | Any unexpected error | No |

Each class carries a clean message and a remediation hint. `webhook_send` classifies the failure, logs the outcome, and raises a `WebhookDeliveryError`; `webhook_process` settles a classified failure into a failed run state whose message is the classified reason. `WebhookDeliveryError` is registered with `@suppress_traceback_in_logs`, and `TracebackSuppressionFilter` (installed on the `prefect.flow_runs` and `prefect.task_runs` loggers in `backend/infrahub/log.py`) drops the traceback record Prefect's engine would otherwise log for a registered type, so the run logs carry only the classified reason. Matching is by exact type identity against the shared registry, so an unrelated exception cannot be silenced by accident. An `UNKNOWN` error is re-raised unregistered, so it keeps its traceback and surfaces as a genuine crash.

A `TLS` failure reaches this layer wrapped by httpx as a generic transport error, so the HTTP adapter's `SSLErrorExtractor` walks the exception chain to recognize the certificate problem and raise a TLS-specific error rather than a generic connection error.

The `transient` flag on `ClassifiedFailure` records whether a class could plausibly succeed on a retry. `webhook_send` currently retries every failure (3 attempts, fixed 120s delay); the flag is reserved for a future transient-only retry policy. The run is silent for the duration of each retry wait, so the zombie-detection window is sized above this backoff to avoid crashing a waiting delivery; see [Liveness and zombie detection](async-tasks.md#liveness-and-zombie-detection).

## Delivery operability

A delivery run exposes recovery actions through the GraphQL `Task` type. `TaskActionGenerator` derives the actions from the run's workflow name and current state. Only `WEBHOOK_SEND` runs expose actions today; any other task type exposes none.

| Action | Available when | Effect |
|--------|----------------|--------|
| `RETRY` | The delivery has settled (a terminal state) | Submits `WEBHOOK_SEND` again with the original run's frozen parameters, as a new independent run. The original run is left unchanged as a record. |
| `CANCEL` | The delivery has not settled | Requests the `CANCELLING` state without forcing it. A running delivery is torn down by its worker. A delivery waiting between attempts keeps its in-process wait, which nothing interrupts, so each attempt re-checks for a recorded cancellation before sending and stops the sequence once one is present. An in-flight HTTP request is not recalled, but no further attempts run. |

The `available_actions` field on the task query reports each action with whether it currently applies and, when it does not, the reason. Selecting `available_actions` forces resolution of the run's workflow name, since the field is derived from it.

`InfrahubTaskRetry` and `InfrahubTaskCancel` carry out the actions. Each loads the delivery through a query-only Prefect client (`DeliveryReader`), then authorizes it (`DeliveryActionAuthorizer`): the action must apply to the run's current state, and the caller must hold the `UPDATE` permission on the webhook's node kind. Loading is kept separate from authorization so the read uses the narrowest client capability it needs.

### Delivery logging

Each send attempt logs one line before the request is sent: the attempt number (`n/N`), the target URL, the request headers, and the payload. The payload is truncated inline (2048 characters) with the full body emitted only at debug level. Secret-bearing header values are masked in this log — see [Log redaction](#log-redaction) for the rule.

When an attempt fails, `webhook_send` logs one error line carrying the failure class, the attempt number (`n/N`), the elapsed time, the reason, and its remediation. While the flow run has attempts left it also states when the next one fires (`Retrying in 120s (attempt n+1/N).`); on the final attempt it states `No retries remaining.`. Outside a flow run, where no retry sequence drives the send, the line reads `outside a flow run` in place of the attempt number and carries no retry note.

## Security

HMAC-SHA256 signing is performed when a `shared_key` is set:

1. Generate a message ID: `msg_<uuid_hex>`
2. Capture the current timestamp
3. Serialize the payload as compact JSON
4. Compute: `HMAC-SHA256(shared_key, "{message_id}.{timestamp}.{payload}")`
5. Base64-encode the signature

Three headers are added to signed requests:

| Header | Value |
|--------|-------|
| `webhook-id` | `msg_<uuid_hex>` |
| `webhook-timestamp` | Unix timestamp |
| `webhook-signature` | `v1,<base64_signature>` |

### Log redaction

When a delivery request is logged, secret-bearing header values are masked as `***`. A header value is masked when the header is environment-sourced, is the signature header, or matches a well-known credential header name (`Authorization`, `Proxy-Authorization`, `Cookie`, `Set-Cookie`, `X-API-Key`). Matching is case-insensitive, since HTTP header names are, so a secret cannot slip through under a different casing. Standard and statically configured non-credential headers are logged verbatim so the record stays useful; the payload is logged in full only at debug level.

## Caching

- **Key format**: `webhook:<webhook_id>`
- **TTL**: 2 hours (`KVTTL.TWO_HOURS`)
- **Storage**: Redis via the cache service
- **Cache miss**: Falls back to fetching the webhook node from the database via SDK, then caches the result
- **Invalidation**: Three paths clear the cache:
  1. `_configure_one()` (on create/update) and `_delete_automation()` (on delete) invalidate a single webhook's cache via `invalidate_webhook_cache(webhook_ids=...)`
  2. `_reconcile_all()` invalidates caches for **updated** and **deleted** webhooks only (via `invalidate_webhook_cache(webhook_ids=...)`), extracted from the `TriggerSetupReport`. New webhooks have no cache entry, and unchanged webhooks need no invalidation.
  3. When a `CoreKeyValue` header is modified, `TRIGGER_KEYVALUE_WEBHOOK_INVALIDATE` fires `invalidate_webhook_headers`, which queries affected webhooks via `KeyValueGetWebhooksQuery` and deletes their cache entries

## Prefect Workflows

| Workflow | Type | Cron | Purpose |
|----------|------|------|---------|
| `WEBHOOK_PROCESS` | INTERNAL | — | Resolves the webhook, computes the payload, and invokes the `webhook_send` subflow on event match |
| `WEBHOOK_SEND` | CORE | — | Resolves the webhook config, builds headers (with optional HMAC), and POSTs the payload; invoked as a subflow and re-submitted on retry |
| `WEBHOOK_CONFIGURE` | INTERNAL | daily at 3 AM (random minute) | Unified webhook automation configuration (configure, delete, reconcile) |
| `WEBHOOK_INVALIDATE_HEADERS` | INTERNAL | — | Invalidates cached webhook data when a referenced KeyValue header changes |

## Built-in Triggers

Two built-in triggers in `triggers.py` react to webhook-related node lifecycle events:

- **`TRIGGER_WEBHOOK_CONFIGURE`**: Fires on `infrahub.node.created`, `infrahub.node.updated`, and `infrahub.node.deleted` for `CoreCustomWebhook` and `CoreStandardWebhook` nodes. Invokes `WEBHOOK_CONFIGURE` with the event type and node data. The `configure_webhook` flow uses `WebhookConfigureParams` and the `EVENT_TO_ACTION` mapping to route to the correct handler.

- **`TRIGGER_KEYVALUE_WEBHOOK_INVALIDATE`**: Fires on `infrahub.node.updated` for `CoreStaticKeyValue` and `CoreEnvironmentVariableKeyValue` nodes. Invokes `WEBHOOK_INVALIDATE_HEADERS` with the event type and node data. The `invalidate_webhook_headers` flow resolves which webhooks reference the changed KeyValue (via `NodeManager.query` with `headers__ids` filter) and clears their cache entries.

## Key Locations

| Component | Path |
|-----------|------|
| Models | `backend/infrahub/webhook/models.py` |
| Failure classifier | `backend/infrahub/webhook/classifier.py` |
| Traceback suppression filter | `backend/infrahub/log.py` |
| HTTP adapter (TLS handling) | `backend/infrahub/services/adapters/http/httpx.py` |
| Tasks/Workflows (configure) | `backend/infrahub/webhook/tasks/configure.py` |
| Tasks/Workflows (process) | `backend/infrahub/webhook/tasks/process.py` |
| Tasks/Workflows (invalidate) | `backend/infrahub/webhook/tasks/invalidate.py` |
| Cache invalidation task | `backend/infrahub/webhook/tasks/cache.py` |
| KeyValue→Webhook query | `backend/infrahub/webhook/query.py` |
| Built-in Triggers | `backend/infrahub/webhook/triggers.py` |
| Gathering | `backend/infrahub/webhook/gather.py` |
| Schema definitions | `backend/infrahub/core/schema/definitions/core/webhook.py` |
| GraphQL mutations | `backend/infrahub/graphql/mutations/webhook.py` |
| Delivery action generator | `backend/infrahub/graphql/queries/task_actions.py` |
| Delivery retry/cancel mutations | `backend/infrahub/graphql/mutations/task.py` |
| Workflow catalogue | `backend/infrahub/workflows/catalogue.py` |
| KeyValue schema | `backend/infrahub/core/schema/definitions/core/key_value.py` |
| Unit tests (models) | `backend/tests/unit/webhook/test_models.py` |
| Unit tests (classifier) | `backend/tests/unit/webhook/test_classifier.py` |
| Unit tests (triggers) | `backend/tests/unit/webhook/test_triggers.py` |
| Functional tests (configure) | `backend/tests/functional/webhook/test_configure.py` |
| Functional tests (process) | `backend/tests/functional/webhook/test_process.py` |
| Functional tests (retry) | `backend/tests/functional/webhook/test_retry.py` |
| Functional tests (cancel) | `backend/tests/functional/webhook/test_cancel.py` |
| Mutation tests | `backend/tests/component/graphql/mutations/test_webhook.py` |

## See Also

- [Events System](events.md) — How events are emitted and dispatched to Prefect
- [Async Tasks](async-tasks.md) — Prefect workflow and task infrastructure
- [Webhook Headers Spec](../../specs/infp-445-webhook-headers/spec.md) — Feature spec for webhook HMAC signing
