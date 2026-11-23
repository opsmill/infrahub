# Design: one render request for several targets

Status: proposed, not built. Decide with the product owner before implementation.

## Problem

Infrahub sends one render request for each artifact. An engine that starts a job for each request, such as a CI pipeline or an AWX job template, then starts one job for each target. A change that affects 500 devices starts 500 pipelines, which exceeds the concurrency limits of most CI systems and costs time and money.

## What is needed

- An external Transformation can ask for requests that carry several targets, up to a size the user chooses.
- One request per target stays the default, so existing engines keep working without changes.
- Each artifact still gets its own status, its own result and its own proposed-change check, so a failure on one device does not hide the result of the others.
- A request stays under Prefect's event size limit (`server.events.maximum_size_bytes`), because Prefect refuses a larger event.

## Proposal

### Configuration

A new optional key on the external Transformation in `.infrahub.yml`:

```yaml
external_transforms:
  - name: ci-startup-config
    query: device_startup_config
    version: "2.0.0"
    timeout: 3600
    batch_size: 200   # default 1: one request per target
```

`batch_size` is part of the fingerprint, as `version` is, so changing it renders the definition's artifacts again.

### Grouping

- The targets that one selection run renders for one artifact definition on one branch are split into requests of at most `batch_size` targets, in a stable order.
- The selection rules do not change. A data change that affects 3 of 500 targets sends one request with 3 targets.
- When a request with its query results would exceed the event size limit, Infrahub splits it further. Only a single target above the limit fails with the existing "too large" error.

### Event

A new event type, `infrahub.artifact.batch_render_requested`, so that existing engines subscribed to `infrahub.artifact.render_requested` never receive a body they do not understand:

```json
{
  "batch_id": "...",
  "callback_url": "https://infrahub.example.com/api/artifact/render/batch/<batch_id>",
  "deadline": "...",
  "artifact_definition_name": "startup-config",
  "transformation_name": "ci-startup-config",
  "transformation_version": "2.0.0",
  "content_type": "text/plain",
  "branch": "change-123",
  "items": [
    {"render_id": "...", "artifact_id": "...", "target_id": "...", "target_name": "edge-01", "query_result": {}}
  ]
}
```

Each item keeps its own `render_id`, so each artifact keeps its own `render_request_id` and `render_deadline`, and the timeout sweep needs no change.

### Token and callbacks

- One render token for the request, with claims `type = "render_batch"`, `batch_id`, `branch` and the list of `artifact_id` values, and `exp = deadline`. It is minted and delivered as today.
- `POST /api/artifact/render/batch/{batch_id}` accepts `{"results": [{"render_id": "...", "status": "success", "content": "..."}, ...]}`. The engine can send all results at once or in several calls. Each result is applied as a single callback is today, and the response lists the outcome of each `render_id`, because some can be accepted while others are refused, for example with 409 when a newer request replaced them.
- `status: running` on the batch endpoint moves the deadline of every item of the request that is still waiting, and returns a new token.
- When the delivery fails after its last attempt, every item of the request is set to `Error`, as for a single request today.

### Proposed-change checks

Nothing changes for the user. Each target has its own check, which waits until its item gets a result, a delivery failure or a timeout. The validator completes when the last check concludes.

## Not decided

- Whether the batch endpoint is needed, or whether engines send each result to the existing per-artifact endpoint with the batch token. The second option has no new endpoint, but needs a token that is valid for several `render_id` values on that endpoint.
- Whether `batch_size` belongs on the external Transformation or on the artifact definition. Several definitions can use one Transformation, and the right size depends on the engine, which suggests the Transformation.
- Whether a request may contain targets of several artifact definitions that use the same Transformation. This proposal keeps one definition per request, so `content_type` and the query are the same for every item.
- Whether progress reports should be able to report progress for a single item of a request.
- How the event history and the task list show a request with several targets. The query results stay hidden, as for a single request.
