# Quickstart: validate artifacts rendered by an external engine

These scenarios prove the spec's user stories from start to finish. Contracts: [callback-api.md](contracts/callback-api.md), [render-request.md](contracts/render-request.md), [infrahub-yml.md](contracts/infrahub-yml.md).

## Prerequisites

- A running Infrahub (`uv run invoke dev.start`) with `INFRAHUB_PUBLIC_URL` set to an address the reference engine can reach.
- A repository connected to Infrahub that declares:
  - a query on `DcimDevice`;
  - an external transformation `ext-config`, version `1.0.0`;
  - an artifact definition `startup-config` that uses `ext-config`, targeting group `edge-routers` with three devices.
- A reference engine: a plain HTTP script that uses no Infrahub libraries (SC-002). For each request it:
  1. reads `data.callback_url`, `data.query_result` and the `X-Infrahub-Render-Token` header;
  2. renders `hostname <name>` followed by the interface descriptions;
  3. calls the callback, and retries on 429.

  An environment variable sets its mode: `ok`, `fail`, or `silent` (never answers).
- A `CoreStandardWebhook` subscribed to `infrahub.artifact.render_requested`, pointing at the reference engine.

## Scenario 1: data change in a proposed change (User Story 1)

1. Create branch `change-123` and change one interface description on `edge-01`.
2. Open a proposed change.
3. **Expect**:
   - the engine receives exactly one request, with `target_name = edge-01`;
   - while it waits, the artifact on `change-123` is `Pending` and the check shows conclusion `unknown`;
   - after the callback, the artifact is `Ready`, the check is `success`, the validator is `completed`, and the artifact diff shows the new description.
4. Merge the proposed change. **Expect** one more request, with `branch = main`, and the artifact on `main` becomes `Ready`.

## Scenario 2: template release (User Story 2)

1. On branch `template-1-1`, change `version` to `1.1.0` in `.infrahub.yml`, commit, and let the repository synchronize.
2. **Expect** three render requests on `template-1-1`, one per device in `edge-routers`.
3. Commit a change to an unrelated file on the same branch. **Expect** no render request.
4. Trigger generation of the definition manually with `POST /api/artifact/generate/{definition_id}`. **Expect** three render requests.

## Scenario 3: failure and timeout (User Story 3)

1. With the engine in `fail` mode, repeat scenario 1. **Expect** the artifact to be `Error` and the check to fail with the engine's message.
2. With the engine in `silent` mode and `timeout: 60`, repeat scenario 1. **Expect**, within 2 minutes, the artifact to be `Error` and the check to fail with "no response from engine".
3. Send the callback for the request that timed out. **Expect** `401`, because the render token expires at the deadline, and the artifact stays unchanged.

## Scenario 4: token rules (SC-005)

| Action | Expected response |
|--------|-------------------|
| Callback with no token | `401` |
| Token for render A sent to the path of render B | `403` |
| Change the data again while render A is pending, then send A's token | `409` |
| A normal API key in `X-INFRAHUB-KEY` | `401` |

## Scenario 5: no token in stored data

After scenario 1:
- Run the GraphQL `Events` query for `infrahub.artifact.render_requested`.
- Run the `Task` query for the webhook flow runs.
- Read the webhook run logs.

**Expect** the token value to appear in none of them.

## Automated coverage

- **Component tests** (`backend/tests/component/`): the callback endpoint rules, the status transitions, the timeout sweep and the validator recomputation.
- **Integration test** (`backend/tests/integration/`): scenarios 1 to 3, with an in-process reference engine.
- **Unit tests**: the fingerprint, which changes with the version and does not change with an unrelated commit, and the token claims.
