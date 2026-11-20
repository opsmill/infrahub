# Research: Artifacts rendered by an external engine

**Spec**: [spec.md](spec.md) | **Plan**: [plan.md](plan.md)

Each section records a decision, why it was chosen, and the alternatives considered. Code references use `module::symbol`.

## R1. Where the render path branches on transformation kind

**Findings**: Five places assume every transformation is Jinja2 or Python and lives in a Git repository:

- `git/tasks.py::generate_request_artifact_definition` builds `transform_location` and `convert_query_response` with `if/elif` on `transform.typename`.
- `git/integrator.py::InfrahubRepositoryIntegrator.render_artifact` dispatches the render with `if/elif` and no `else`. A third kind would leave the content unset.
- `message_bus/types.py::ProposedChangeArtifactDefinition.transform_location` raises `ValueError` for any other kind.
- `core/regeneration/definitions.py` has one GraphQL fragment per kind and requires `repository_id`.
- `git/fingerprint/composer.py::FingerprintComposer.compose_transformation` is an exhaustive `match` ending in `assert_never`.

`git/integrator.py::InfrahubRepositoryIntegrator.artifact_generate` duplicates the dispatch. Its docstring says nothing calls it.

**Decision**: Add an external branch at each of these five places. The external branch replaces only the render step. Selecting definitions and targets, running the query, and storing content stay shared with the internal path.

**Alternatives considered**: A separate pipeline for external definitions. Rejected because selection must match internal artifacts exactly (SC-001), and a second pipeline would drift from the first.

## R2. Running the query for the target

**Findings**: `render_artifact` calls `sdk.query_gql_query(name=query_id, variables=..., update_group=True, subscribers=[artifact.id], branch_name=..., timeout=...)`. The `update_group` and `subscribers` arguments register the artifact as a subscriber of the query's group. Impact analysis later reads that group to decide which artifacts to render again.

**Decision**: The external render request runs the same `query_gql_query` call, with the same `update_group` and `subscribers` arguments, before it emits the event. Skipping them would break FR-001 and SC-001.

## R3. Keeping the render token out of stored data

**Findings**:
- Every field of an event goes into the Prefect event payload (`events/models.py::InfrahubEvent.get_event_payload`).
- Payloads are stored in the Prefect events table, and anyone who can run the GraphQL `Events` query can read them (`task_manager/event/query.py::to_graphql`). The only permission filter hides `infrahub.account.*` events.
- The webhook flows receive the payload as flow-run parameters: `event_payload` on `webhook_process` and `payload` on `webhook_send`. The `Task` query exposes those parameters.
- `webhook/log_formatter.py::WebhookLogFormatter` logs the first 2048 characters of the request body at INFO.

**Decision**: The token is never placed in the event, in flow parameters or in logs.
- `webhook/tasks/process.py::webhook_send` mints the token on each delivery attempt, from the render ID in the payload.
- The token is sent in the `X-Infrahub-Render-Token` header. The webhook header redaction already masks header values in logs.
- Engines that can only read the body, for example an AWX job launch where the token must go into `extra_vars`, use the placeholder `${INFRAHUB_RENDER_TOKEN}` in the body their webhook transformation produces. `webhook_send` replaces the placeholder just before sending and redacts the token from the logged body.

**Alternatives considered**:
- Token in the event payload. Rejected because the token would be readable through the `Events` and `Task` queries and the Prefect UI for at least the event retention period.
- The engine exchanges the render ID for a token with its own API token. Rejected because it brings back the long-lived engine credential that the user ruled out (spec FR-009).

## R4. Token format and replacement

**Findings**:
- `auth/auth.py` signs HS256 JWTs with `SecuritySettings.secret_key`.
- The existing validators reject any `type` other than their own, so a token with a new type cannot be used as an access or refresh token.
- No scoped or single-use token exists today.

**Decision**: The render token is a JWT with `type: "render"`. Its claims are `render_id`, `artifact_id`, `branch` and `exp`. `exp` is the render deadline: request time plus the transformation timeout.

Replacement uses state stored on the artifact (data-model.md). Each new request writes a new `render_request_id` on the artifact, and the callback refuses a token whose `render_id` does not match. A single-use or revocation list is not needed: the artifact holds the one valid render ID.

**Alternatives considered**: An opaque random token stored in the cache. Rejected because it needs a cache lookup and its own expiry, and a JWT plus the render ID on the artifact gives the same guarantees.

## R5. Callback endpoint and its limits

**Findings**:
- `POST /api/storage/upload/content` has no size limit.
- `StorageSettings.max_file_size` (50 MB by default) is applied only to file-object uploads.
- `api/admission/middleware.py::AdmissionMiddleware` can shed any non-excluded request with HTTP 429.
- `backend/AGENTS.md` lists new REST endpoints under "Ask First".

**Decision**: Add one REST endpoint, `POST /api/artifact/render/{render_id}`.
- It authenticates only with the render token. It does not accept account sessions or API keys.
- It accepts either content or a failure message (contracts/callback-api.md).
- The maximum content size is `StorageSettings.max_file_size`. This answers the spec assumption about content size by reusing the existing limit.
- Engines must retry on 429, and the quickstart's reference engine does.

**Alternatives considered**: A GraphQL mutation. Rejected because GraphQL authentication is built on account sessions, and a mutation would have to accept a credential type no other mutation uses. It would also mean sending large content through GraphQL. This is the "Ask First" item to confirm with the user.

## R6. Proposed-change checks that complete later

**Findings**: `core/validators/checks_runner.py::run_checks_and_update_validator` awaits every check coroutine and marks the validator `completed` when all of them return. The artifact check flow (`artifacts/tasks.py::create`) returns a conclusion synchronously. `CoreCheck.conclusion` defaults to `unknown`, and a check node can be updated afterwards.

**Decision**:
- For an external definition, the check flow emits the render request, writes the check with conclusion `unknown` and returns a pending result.
- `run_checks_and_update_validator` leaves the validator `in_progress` when any result is pending.
- The callback handler and the timeout sweep (R7) update the check under the per-artifact lock (R11), then call one shared function that recomputes the validator state and conclusion from all its checks and sends the existing passed or failed validator events.

**Alternatives considered**: The check flow waits by polling until the artifact is `Ready` or `Error`. Rejected because it holds a flow run for up to the timeout (10 minutes) per target, and for a 500-device group that would occupy the workers for the whole time.

## R7. Timeout without a reply

**Findings**: No mechanism schedules a single delayed run. Cron workflows exist, for example `CRASH_ZOMBIE_FLOW_RUNS` every 5 minutes and `MERGE_WATCHER` every minute, in `workflows/catalogue.py`.

**Decision**: Add a cron workflow that runs every minute with `concurrency_limit=1`. It finds artifacts whose status is `Pending` and whose `render_deadline` has passed, sets them to `Error`, and completes their checks with the message "no response from engine". This meets SC-004 (timeout plus 1 minute).

**Alternatives considered**: A delayed Prefect run per request with `scheduled_time`. Rejected because the adapter does not support it, and it would create one scheduled run per artifact.

## R8. Declaring external transformations and the fingerprint

**Findings**:
- The SDK model `InfrahubRepositoryConfig` (`python_sdk/infrahub_sdk/schema/repository.py`) holds the `.infrahub.yml` sections.
- The import plan in `git/integrator.py` creates, updates and deletes one kind per section.
- Artifact definitions resolve `transformation` by unique name through the `CoreTransformation` generic, so they need no change.
- Without a `watch` block, `FingerprintComposer` folds the commit ID into the fingerprint, so every commit would change it.
- An incomplete or null dependency closure makes selection fall back to every target.

**Decision**:
- **SDK:** a new `external_transforms` section with `name`, `query`, `version`, `description` and `timeout` (default 600 seconds).
- **Backend:** a new `CoreTransformExternal` kind that inherits `CoreTransformation` and adds `version`. Its dependency closure is empty and complete.
- **Fingerprint:** a new `ExternalTransformationFingerprintInput` case. It hashes the name, the query fingerprint and the version, and does not fold in the commit ID. The fingerprint therefore changes exactly when the version or the query changes (FR-007).
- The SDK change lands as a separate pull request in `infrahub-sdk-python` (branch `infrahub-develop`) before the submodule pointer is updated here.

**Alternatives considered**: Reusing the Python transform path. Rejected because it folds in the commit ID, so every commit would select every target.

## R9. Size of the render-request event

**Findings**: Prefect's `emit_event` raises `EventTooLarge` above `PREFECT_SERVER_EVENTS_MAXIMUM_SIZE_BYTES`. The research read that limit from Prefect 3.7.5, where the default is 1,500,000 bytes. It is not confirmed for the locked 3.8.6. The payload is also stored twice as flow-run parameters.

**Decision**: Keep the full query result in the event, as the user decided. Before emitting, measure the serialized payload. If it exceeds the Prefect limit, mark the artifact `Error` with the message "query result too large for a render request (N bytes, limit M)", and do not emit.

**Permissions** (critique E5): query results would otherwise be readable through the `Events` query by users who may not be allowed to read every field the query returns. So:
- `task_manager/event/query.py` leaves `query_result` out of the payload it returns for `infrahub.artifact.render_requested`;
- the `Task` query does the same for the webhook flow-run parameters of these events.

The Prefect UI and API remain reachable only by operators of the deployment.

## R10. Merge regeneration

**Findings**: Post-merge regeneration goes through `PostMergeRegenerationDispatcher` to `REQUEST_ARTIFACT_DEFINITION_GENERATE` and then `git/tasks.py::generate_artifact`.

**Decision**: No change to selection. `generate_artifact` takes the external branch from R1 and emits a render request for the destination branch (spec FR-001, User Story 1 scenario 4).

## R11. Concurrent changes to render state

**Findings**: A callback, a new render request and the timeout sweep can change the same artifact at the same time. Without serialization, a callback that validated render ID R can store its content after a new request has set R2. `infrahub.lock` provides named locks (`InfrahubLockRegistry`) that the backend already uses.

**Decision**: Every read-check-write of `render_request_id`, `render_deadline` and the render status runs under the lock `artifact-render:<branch>:<artifact_id>`. The render ID and the deadline are checked inside that lock. Validator recomputation runs under `validator:<validator_id>` and reads the stored checks, not the caller's result.

**Alternatives considered**: An optimistic compare-and-set in Cypher. Rejected because node saves go through the node manager, and a dedicated Cypher write would bypass it.

## R12. Failing before emitting

**Decision**: Before emitting, the render request sets the artifact to `Error` with a specific message, and emits nothing, in these cases:
- No active webhook has `event_type` exactly `infrahub.artifact.render_requested`, a branch scope that matches, and a `node_kind` that is empty or equal to the target kind. A webhook subscribed to `all` does not count, because it gets no render token. Message: "no webhook subscribed to infrahub.artifact.render_requested".
- `main.public_url` is not set. Message: "main.public_url must be set for external transformations".
- The serialized event exceeds the size limit (R9).

**Rationale**: Otherwise each of these would show as "no response from engine" after the full timeout, which hides the cause (critique P4, P5, X1).
