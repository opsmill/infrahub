# Data Model: Artifacts rendered by an external engine

**Spec**: [spec.md](spec.md) | **Research**: [research.md](research.md)

## CoreTransformExternal (new node kind)

Inherits `CoreTransformation` (`core/schema/definitions/core/transform.py::core_transform`). That gives it `name` (unique), `label`, `description`, `timeout`, `fingerprint`, `dependencies`, `dependencies_complete`, `query` (required), `repository` (required), `tags` and `artifact_definitions`.

| Attribute | Kind | Required | Notes |
|-----------|------|----------|-------|
| `version` | Text | yes | Value declared in `.infrahub.yml`. Part of the fingerprint (research R8). |

- **Branch support**: same as the other transformation kinds (`aware`).
- **Created by**: repository import only (spec FR-006). It is not created through UI forms in this version.
- **Dependency closure**: always `dependencies = []` and `dependencies_complete = true`, so selection relies on the fingerprint only.
- **Timeout**: the generic default is 60 seconds. The SDK config default for external transforms is 600 seconds and is written on import (FR-015).
- **New constant**: `InfrahubKind.TRANSFORMEXTERNAL`.

## CoreArtifact (existing kind, two new attributes)

| Attribute | Kind | Required | Notes |
|-----------|------|----------|-------|
| `render_request_id` | Text | no | ID of the only render request whose result is accepted. Empty for internal artifacts. |
| `render_deadline` | DateTime | no | Time after which the timeout sweep sets the artifact to `Error`. Empty when no external request is pending. |

`CoreArtifact` has `branch = local`, so both values are per branch, the same as `status` and `storage_id`.

### Status transitions for an external artifact

```text
              render request emitted
  (any) ─────────────────────────────────► Pending
                                            │  render_request_id = R, render_deadline = T
          ┌─────────────────────────────────┼───────────────────────────────┐
          │ callback with content, id = R   │ callback with failure, id = R  │ now > T (sweep)
          ▼                                 ▼                                ▼
        Ready                             Error (engine message)           Error ("no response from engine")
  render_deadline cleared           render_deadline cleared           render_deadline cleared
```

- A new request while `Pending` overwrites `render_request_id` and `render_deadline`. The earlier token is then refused (FR-009, FR-013).
- A callback with an ID other than the current `render_request_id`, or after `render_deadline` is cleared, is refused and changes nothing.
- If the query result is too large for an event (research R9), the artifact goes straight to `Error` and no request is emitted.

## ArtifactRenderRequestedEvent (new event)

- **Name**: `infrahub.artifact.render_requested`, a new `EventType` member. Webhooks can subscribe to it.
- **Base**: `events/artifact_action.py::ArtifactEvent`.
- **Webhook node-kind filter**: `infrahub_node_kind_event = True`, so a webhook can filter by target kind.

Payload fields, which go in the event's `data`:

| Field | Type | Notes |
|-------|------|-------|
| `render_id` | str (UUID) | Equal to the artifact's `render_request_id`. |
| `callback_url` | str | `<main.public_url>/api/artifact/render/<render_id>`. |
| `deadline` | datetime | Equal to `render_deadline`. |
| `artifact_id`, `artifact_name` | str | |
| `artifact_definition_id`, `artifact_definition_name` | str | |
| `transformation_name`, `transformation_version` | str | Lets the engine select its template. |
| `content_type` | str | Required content type of the result. |
| `target_id`, `target_kind`, `target_name` | str | |
| `branch` | str | |
| `query_result` | dict | The full GraphQL query result for the target (spec FR-002). |

The token is **not** a payload field (research R3).

## CoreArtifactCheck (existing kind, no schema change)

For an external definition, a proposed change creates the check with `conclusion = unknown` and the message "waiting for external engine". The callback or the timeout sweep sets `conclusion`, `severity`, `message`, `changed`, `checksum` and `storage_id` later, then recomputes the validator (research R6).

## Repository configuration (`.infrahub.yml`)

New section `external_transforms`. Entries are referenced by name from `artifact_definitions[].transformation`. Schema: [contracts/infrahub-yml.md](contracts/infrahub-yml.md).
