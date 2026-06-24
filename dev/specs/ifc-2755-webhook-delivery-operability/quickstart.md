# Quickstart: Validating Webhook Delivery Operability

How to exercise each user story end-to-end. Assumes a running Infrahub dev stack with the task-manager (Prefect) worker active.

## Prerequisites

```bash
uv sync --all-groups
cd frontend/app && pnpm install
```

Set up a target you control to observe deliveries — a request bin, a local echo server, or an endpoint you can take up/down to drive failures.

## Setup: a webhook to exercise

1. In the UI, create a Standard or Custom webhook pointing at your test endpoint. Optionally add a shared key (to exercise signature redaction) and an ENVIRONMENT-sourced custom header (to exercise secret redaction).
2. Trigger the webhook's event (e.g. create/update the watched node kind) to produce a delivery.
3. Open the webhook → **Tasks** tab. Each delivery is a `webhook_send` run row.

## US1 — Inspect what a delivery sent and received (P1)

1. Click a delivery to open its detail.
2. Verify the **payload** (from run parameters), **request** (URL + headers), **response** (status, body, latency) are shown.
3. Verify redaction: the ENVIRONMENT-sourced header and `webhook-signature` are masked; `Accept`, `Content-Type`, `webhook-id`, `webhook-timestamp`, and STATIC custom headers are verbatim.
4. Point the webhook at an endpoint that returns an error; trigger again; confirm the captured request/response are still present and reflect the **last attempt**.

Backend check: the run carries one `http` artifact (key `infrahub-webhook-http`); no raw secret appears in the artifact.

## US2 — Understand why a delivery failed (P2)

Drive each failure class and confirm the classified reason + remediation hint (no stacktrace), and the retry behavior:

| Target | Expected class | Retried? |
|---|---|---|
| Unreachable host | CONNECTION | yes (3 attempts, ~2m apart) |
| Endpoint returning 404 | HTTP_CLIENT_ERROR | no (immediate fail) |
| Endpoint returning 500 | HTTP_SERVER_ERROR | yes |
| Endpoint with invalid TLS cert (validate_certificates on) | TLS | no |
| Slow endpoint past timeout | TIMEOUT | yes |
| Webhook config that cannot resolve | CONFIG | no |

Confirm per-attempt progress is visible in the delivery **logs**, and the final reason reflects the settling attempt.

## US3 — Resend a delivery (P3)

1. Trigger a delivery against a **down** endpoint so it fails. Bring the endpoint up.
2. On the failed delivery, click **Resend**, confirm in the dialog → a **new** delivery row appears, carries the same payload, recomputes its signature, and succeeds. The original failed row is unchanged.
3. On a **succeeded** delivery, click Resend → the confirmation explicitly calls out re-delivering an already-processed event; on confirm, a new delivery is produced.
4. On an **in-progress / awaiting-retry** delivery, confirm Resend is disabled with a reason.
5. (Retention) For a delivery whose run has aged out, confirm Resend reports "delivery no longer available".

GraphQL check:
```graphql
mutation { InfrahubTaskResend(data: {id: "<run-id>"}) { ok task { id state } } }
```

## US4 — Cancel an in-progress delivery (P4)

1. Trigger a delivery against a slow/failing endpoint so it enters AwaitingRetry.
2. Click **Cancel** → the delivery transitions to cancelled and no further attempts are made.
3. Confirm Cancel is disabled (with a reason) on already-settled deliveries.
4. Confirm a cancelled delivery can then be **resent** (cancel→resend is the two-step restart).

GraphQL check:
```graphql
mutation { InfrahubTaskCancel(data: {id: "<run-id>"}) { ok task { id state } } }
```

## Authorization

As an account **without** update permission on the webhook node, confirm Resend/Cancel are rejected at the API layer with a clear permission error.

## Automated tests

```bash
uv run invoke backend.test-unit            # classifier, CapturedHeaders redaction, available-actions gating
uv run invoke backend.test-integration     # capture, resend resubmit, cancel state flip, task typing
cd frontend/app && pnpm test               # mutation hooks / rendering
cd frontend/app && pnpm test:e2e           # resend + cancel happy paths
```

## Regenerate artifacts after schema changes

```bash
uv run invoke backend.generate                 # protocols / generated backend
uv run invoke schema.generate-graphqlschema    # schema/schema.graphql
cd frontend/app && pnpm codegen                # frontend GraphQL types
uv run invoke docs.generate                    # reference docs (events/schema/etc.)
```

Run `/pre-ci` before pushing to catch generated-file drift.
