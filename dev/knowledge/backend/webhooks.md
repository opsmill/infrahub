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
                                          │ Prepare payload  │
                                          │ + HMAC headers   │
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

Bridges Infrahub webhooks to Prefect automations. Extends `TriggerDefinition` with webhook-specific name generation (`webhook:<id>`). The `from_object()` class method converts a `CoreWebhook` node into trigger configuration including:

- Event pattern matching (`infrahub.*` for "all", or specific event type)
- Branch filtering via `match_related` (default branch, other branches, or all)
- Node kind filtering via `match` (only for node-level events)

### `EventContext`

Normalized representation of the event extracted from Prefect's raw event payload. Contains `id`, `branch`, `account_id`, `occured_at`, and `event` type. Created via `from_event()` which parses the nested context structure from Prefect.

### `Webhook` class hierarchy

`Webhook` (base) → `StandardWebhook`, `CustomWebhook`, `TransformWebhook`

The base class handles:

- Payload preparation (`_prepare_payload`)
- Header assignment with optional HMAC signing (`_assign_headers`)
- HTTP delivery via `send()`
- Cache serialization (`to_cache` / `from_cache`)

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
5. Calls `webhook.send()` which prepares the payload, assigns headers (with optional HMAC), and POSTs to the target URL

The `webhook_send` task has 3 retries configured and calls `response.raise_for_status()`.

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

## Caching

- **Key format**: `webhook:<webhook_id>`
- **TTL**: 2 hours (`KVTTL.TWO_HOURS`)
- **Storage**: Redis via the cache service
- **Cache miss**: Falls back to fetching the webhook node from the database via SDK, then caches the result
- **Invalidation**: Cache is cleared by `_configure_one()` (on create/update) and `_delete_automation()` (on delete), both routed through the unified `configure_webhook` flow

## Prefect Workflows

| Workflow | Type | Cron | Purpose |
|----------|------|------|---------|
| `WEBHOOK_PROCESS` | USER | — | Delivers webhook payload on event match |
| `WEBHOOK_CONFIGURE` | INTERNAL | daily at 3 AM (random minute) | Unified webhook automation configuration (configure, delete, reconcile) |

## Built-in Triggers

A single built-in trigger in `triggers.py` reacts to all webhook node lifecycle events:

- **`TRIGGER_WEBHOOK_CONFIGURE`**: Fires on `infrahub.node.created`, `infrahub.node.updated`, and `infrahub.node.deleted` for `CoreCustomWebhook` and `CoreStandardWebhook` nodes. Invokes `WEBHOOK_CONFIGURE` with the event type and node data. The `configure_webhook` flow uses `WebhookConfigureParams` and the `EVENT_TO_ACTION` mapping to route to the correct handler.

## Key Locations

| Component | Path |
|-----------|------|
| Models | `backend/infrahub/webhook/models.py` |
| Tasks/Workflows | `backend/infrahub/webhook/tasks.py` |
| Built-in Triggers | `backend/infrahub/webhook/triggers.py` |
| Gathering | `backend/infrahub/webhook/gather.py` |
| Schema definitions | `backend/infrahub/core/schema/definitions/core/webhook.py` |
| GraphQL mutations | `backend/infrahub/graphql/mutations/webhook.py` |
| Workflow catalogue | `backend/infrahub/workflows/catalogue.py` |
| Unit tests | `backend/tests/unit/webhook/test_models.py` |
| Functional tests | `backend/tests/functional/webhook/test_task.py` |
| Mutation tests | `backend/tests/component/graphql/mutations/test_webhook.py` |

## See Also

- [Events System](events.md) — How events are emitted and dispatched to Prefect
- [Async Tasks](async-tasks.md) — Prefect workflow and task infrastructure
- [Webhook Headers Spec](../../specs/infp-445-webhook-headers/spec.md) — Feature spec for webhook HMAC signing
