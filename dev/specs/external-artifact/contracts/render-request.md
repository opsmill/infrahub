# Contract: Render request delivered to the engine

Infrahub emits `infrahub.artifact.render_requested` once per artifact to render. A `CoreStandardWebhook` or `CoreCustomWebhook` subscribed to exactly that event type delivers it to the engine. A webhook subscribed to `all` also receives the event, but without a render token, and does not count as a render engine. A webhook with a `node_kind` receives only render requests whose target is of that kind.

## Body without a webhook transformation

This is the standard webhook body (`webhook/models.py::Webhook.compute_payload`). The event fields are under `data`, and the fields are listed in [data-model.md](../data-model.md#artifactrenderrequestedevent-new-event).

```json
{
  "data": {
    "render_id": "1a2b...",
    "callback_url": "https://infrahub.example.com/api/artifact/render/1a2b...",
    "deadline": "2026-11-20T10:10:00Z",
    "artifact_id": "...",
    "artifact_name": "startup-config",
    "artifact_definition_id": "...",
    "artifact_definition_name": "startup-config",
    "transformation_name": "ansible-startup-config",
    "transformation_version": "1.5.0",
    "content_type": "text/plain",
    "target_id": "...",
    "target_kind": "DcimDevice",
    "target_name": "edge-01",
    "branch": "change-123",
    "query_result": { "DcimDevice": { "edges": [ ... ] } }
  },
  "id": "<event id>",
  "branch": "change-123",
  "account_id": "...",
  "occured_at": "...",
  "event": "infrahub.artifact.render_requested"
}
```

The `Events` GraphQL query returns this event without `data.query_result`, so the query data stays behind object permissions.

## Headers

| Header | Value |
|--------|-------|
| `X-Infrahub-Render-Token` | Render token, minted on each delivery attempt and valid until `deadline`. Sent only by a webhook whose `event_type` is exactly `infrahub.artifact.render_requested`. |
| `webhook-id`, `webhook-timestamp`, `webhook-signature` | Existing signature headers, present when the webhook has a `shared_key`. |
| Custom headers | Existing `CoreWebhook.headers`. |

## Body with a webhook transformation

`CoreCustomWebhook.transformation` runs a `CoreTransformPython` on the event data, and its output becomes the body. This works unchanged for the new event type.

The transformation cannot see the token, because the token does not exist when the transformation runs. To place the token in the body, the transformation writes the literal string `${INFRAHUB_RENDER_TOKEN}` where the token belongs. Just before sending, Infrahub replaces every occurrence of that string in the serialized body.

Example: an AWX job launch body produced by a transformation:

```json
{
  "extra_vars": {
    "infrahub_callback_url": "https://infrahub.example.com/api/artifact/render/1a2b...",
    "infrahub_render_token": "${INFRAHUB_RENDER_TOKEN}",
    "device": { "...": "query_result" }
  }
}
```

## Delivery

- Delivery uses the existing webhook retries: 3 retries, 120 seconds apart.
- With the default timeout of 600 seconds, the deadline outlasts the delivery attempts.
- When the delivery fails after its last attempt, crashes or is cancelled, the artifact is set to `Error` and the waiting checks fail with `render request could not be delivered: <reason>`, without waiting for the deadline.
