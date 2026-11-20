# External Artifacts

An artifact definition whose transformation is a `CoreTransformExternal` is rendered by an engine outside Infrahub. Infrahub keeps everything it does for internal artifacts — target selection, fingerprints, artifact checks on proposed changes, regeneration after merge — and replaces the render step with a request/callback exchange. User documentation: `docs/docs/transformations/external.mdx`.

## Flow

```text
selection (generate / proposed-change check / post-merge)
  -> request_external_render: query, artifact Pending, emit infrahub.artifact.render_requested
  -> webhook_process / webhook_send: mint render token per attempt, POST to engine
  -> engine POST /api/artifact/render/{render_id} with X-Infrahub-Render-Token
  -> RenderResultAcceptor: store content, artifact Ready or Error, conclude waiting checks
  (no answer) -> expire-artifact-renders cron: artifact Error, check fails "no response from engine"
```

## Request

`artifacts/render_request.py::request_external_render` runs for both entry points: `git/tasks.py::generate_artifact` (manual generation, post-merge regeneration, version change) and `artifacts/tasks.py::_request_external_render` (proposed-change artifact check).

- The check path writes the check with conclusion `unknown` and message `waiting for external engine` *before* emitting, so the callback always finds it. The check returns `CheckPending.PENDING`, and `core/validators/checks_runner.py::run_checks_and_update_validator` leaves the validator in progress; the callback or the sweep completes it through `recompute_validator`.
- The artifact is set to `Error` without emitting when no active `CoreWebhook` on the default branch has event type `infrahub.artifact.render_requested` (or `all`) and a `branch_scope` covering the artifact's branch, when `main.public_url` is not set, or when the serialized event exceeds Prefect's `server.events.maximum_size_bytes`. Prefect refuses a larger event, so the check is done before sending.
- The deadline is `now + transformation timeout`. The SDK default for `external_transforms[].timeout` is 600 s; internal transformations default to 60 s.
- `render_request_id` and `render_deadline` on `CoreArtifact` identify the one request the artifact accepts a result for. A newer request overwrites both, which invalidates the previous one.

## Delivery and token

- The token is a JWT (`artifacts/render_token.py::mint_render_token`) signed with `security.secret_key`, with claims `type=render`, `render_id`, `artifact_id`, `branch` and `exp = deadline`.
- Mint the token inside `webhook/tasks/process.py::webhook_post`, once per delivery attempt, never earlier: flow-run parameters, events and logs are stored and readable, so the token must not exist before the HTTP send. The flow receives only the non-secret `RenderTokenRequest`.
- The token goes in the `X-Infrahub-Render-Token` header, and replaces every `${INFRAHUB_RENDER_TOKEN}` in the serialized body (`RENDER_TOKEN_PLACEHOLDER`), which is how a `CoreCustomWebhook` transformation places it in an engine-specific body.
- `query_result` can hold data a reader has no permission to view, so `task_manager/event/query.py::PrefectEventData._readable_payload` drops it from the `Events` query, and `graphql/queries/task.py::_readable_parameters` drops it, at any depth, from the `Task` query parameters of render-request webhook runs.
- Delivery uses the normal webhook retries (`WEBHOOK_SEND_RETRIES = 3`, 120 s apart). A timeout shorter than about 7 minutes can expire before the last attempt.

## Callback

`api/artifact.py::submit_render_result` authenticates with the render token only. The token is validated before the body is parsed, so a request without a valid token gets 401, not 400.

| Response | Raised by |
|----------|-----------|
| 401 | Missing, badly signed, wrong `type` or expired token (`AuthorizationError`). A callback after the deadline lands here, because `exp` is the deadline |
| 403 | Token `render_id` differs from the path (`check_render_id`) |
| 400 | Invalid body, or `content_type` differs from the definition (`RenderResultInvalidError`) |
| 413 | Content above `storage.max_file_size` MB (`RenderResultTooLargeError`) |
| 409 | Token valid, but the artifact's `render_request_id` differs or `render_deadline` is cleared — replaced, or already concluded by an earlier callback or by the sweep (`RenderRequestNotActiveError`) |
| 429 | Admission control sheds the request like any other API call |

`artifacts/render_result.py::RenderResultAcceptor.accept_render_result` checks and writes under `artifact_render_lock(branch, artifact_id)` in one transaction, so a reader never sees `Ready` with the previous checksum. Writes are attributed to `SYSTEM_USER_ID` because the engine has no account. It then concludes the checks waiting on that artifact (`conclude_waiting_checks`) and recomputes their validators under `validator_lock`.

## Timeout

`EXPIRE_ARTIFACT_RENDERS` (`artifacts/timeouts.py::expire_artifact_renders`) runs every minute with `CANCEL_NEW` concurrency. It lists `Pending` artifacts per branch, default branch first, and skips a `(artifact_id, render_request_id)` already seen: a branch reads the artifacts of the default branch that it did not change, so a request seen first on the default branch belongs to it and is not written again on other branches. Under the render lock it re-reads the deadline, because a callback or a new request may have replaced it, then sets `Error` and fails the waiting checks with `no response from engine`. An artifact therefore reaches `Error` up to about a minute after its deadline.

## Fingerprint and regeneration

- `git/closure_builder/external_closure.py::ExternalClosure` returns an empty, complete closure: no file in the repository affects the output.
- `git/fingerprint/composer.py::ExternalTransformationFingerprintInput` adds `version=<version>` to the fingerprint and does not require `watch`. A `version` change re-renders every target; an unrelated commit re-renders nothing. On a branch, a version change renders each target at import and again when a proposed change opens.
- Template changes in the engine without a version change are invisible to Infrahub; users trigger generation manually.

## Key Locations

| Purpose | Location |
|---------|----------|
| Schema | `core/schema/definitions/core/transform.py::core_transform_external`, `core/schema/definitions/core/artifact.py` |
| Import from `.infrahub.yml` | `git/integrator.py::InfrahubRepositoryIntegrator._build_external_transform_definitions` |
| Event | `events/artifact_action.py::ArtifactRenderRequestedEvent` |
| Request | `artifacts/render_request.py` |
| Token | `artifacts/render_token.py`, `webhook/tasks/process.py::webhook_post` |
| Callback | `api/artifact.py::submit_render_result`, `artifacts/render_result.py` |
| Timeout sweep | `artifacts/timeouts.py`, `workflows/catalogue.py::EXPIRE_ARTIFACT_RENDERS` |
| Integration test | `backend/tests/integration/artifacts/test_external_artifact.py` |
| Component tests | `backend/tests/component/api/test_artifact_render_callback.py`, `backend/tests/component/artifacts/` |

## See Also

- [Webhooks](webhooks.md) — delivery, retries and header redaction used for render requests
- [Selective Merge Regeneration](selective-merge-regeneration.md) — target selection after merge, shared with internal artifacts
- [Code Generation](code-generation.md) — fingerprints and dependency closures
