# QA Checklist — Webhook Delivery Operability

**Generated**: 2026-07-20 16:26 local
**Feature**: specs/ifc-2755-webhook-delivery-operability
**Source**: speckit.opsmill.qa

## Scope

Verify that a webhook delivery is a first-class, inspectable, and recoverable object in the Tasks tab: the delivered payload, request, and response are captured (with secrets masked), failures show a short classified reason with a remediation hint instead of a stacktrace, and an operator can retry or cancel a delivery through the generic task actions. Out of scope: the automated test suite and internal orchestration wiring.

## Prerequisites

- [ ] Working copy is on `develop` (or a branch with the implementation merged), e.g. `pmi-webhook-qa-docs`.
- [ ] `uv sync --all-groups` and `cd frontend/app && pnpm install` completed cleanly.
- [ ] Local stack running with the task-manager (Prefect) worker active.
- [ ] A test HTTP target you control (request bin / local echo server) that you can take **up and down** to drive failures.

## Setup

```bash
uv run invoke demo.start
# note the ENV var you will reference from a webhook header, e.g.:
export WEBHOOK_TOKEN="Bearer test-secret"
```

1. In the UI, `Integrations` → `Webhooks` → **+ Add Webhook**; create a Standard webhook at your test URL, event `infrahub.node.updated`, node kind of a node you can edit.
2. Add a shared key (exercises signature redaction) and an ENVIRONMENT-sourced custom header referencing `WEBHOOK_TOKEN` (exercises secret redaction).
3. Update a matching node to fire a delivery, then open the webhook → **Tasks** tab; each `webhook_send` run is a delivery.

## Test Scenarios

### 1. Inspect what a delivery sent and received (US1)

**What this verifies**: The payload, request, and response are captured and shown, with secrets masked.

**Steps**:

- [ ] Open a delivery and confirm **payload**, **request** (URL + headers), and **response** (status, body, latency) are shown.
- [ ] Confirm masking: the ENV-sourced header, `webhook-signature`, and `Authorization`/`Cookie`/`X-API-Key` show `***`; `Accept`, `Content-Type`, `webhook-id`, `webhook-timestamp`, and non-credential static headers show verbatim.
- [ ] Point the webhook at an error endpoint, trigger again, reopen: request/response are still present and reflect the **last attempt**.

**Expected result**: No raw secret appears anywhere in the view; captured fields reflect the settling attempt.

### 2. Understand why a delivery failed (US2)

**What this verifies**: Failures are classified with a remediation hint, retried per class, and logged without a stacktrace.

**Steps**:

- [ ] Drive each target and confirm the class + retry behavior:
  - Unreachable host → `CONNECTION`, retried (3 attempts ~2m apart)
  - 404 → `HTTP_CLIENT_ERROR`, no retry
  - 500 → `HTTP_SERVER_ERROR`, retried
  - Invalid TLS cert (validate certificates on) → `TLS`, no retry
  - Slow past timeout → `TIMEOUT`, retried
- [ ] Confirm per-attempt progress is visible in the delivery **logs** and the final reason reflects the settling attempt; no traceback for a classified failure.

**Expected result**: Each failure shows the correct class and a matching hint; only an unexpected crash keeps a full traceback.

### 3. Retry a delivery (US3)

**What this verifies**: Retry replays the frozen payload as a new delivery against current config; the original is immutable.

**Steps**:

- [ ] Fail a delivery against a **down** endpoint, bring it up, click **Retry** and confirm → a **new** row appears, carries the same payload, re-signs, and succeeds; the original row is unchanged.
- [ ] Retry a **succeeded** delivery → the confirmation calls out re-delivering an already-processed event; on confirm a new delivery is produced.
- [ ] On an in-progress / awaiting-retry delivery, confirm Retry is disabled with a reason.
- [ ] Optional GraphQL: `mutation { InfrahubTaskRetry(data: {id: "<run-id>"}) { ok task { id } } }`.

**Expected result**: Retry is available only from a terminal state and always creates a new, independent delivery.

### 4. Cancel an in-progress delivery (US4)

**What this verifies**: Cancel stops the remaining auto-retry cycle; settled deliveries cannot be cancelled.

**Steps**:

- [ ] Trigger a delivery against a slow/failing endpoint so it enters awaiting-retry, click **Cancel** → it transitions to cancelled and no further attempts run.
- [ ] Confirm Cancel is disabled (with a reason) on already-settled deliveries.
- [ ] Confirm a cancelled delivery can then be **retried** (cancel→retry is the two-step restart).
- [ ] Optional GraphQL: `mutation { InfrahubTaskCancel(data: {id: "<run-id>"}) { ok task { id } } }`.

**Expected result**: Cancel halts scheduled attempts (in-flight request not recalled) and only applies to non-terminal deliveries.

### 5. Authorization

**What this verifies**: Recovery actions require webhook-management permission.

**Steps**:

- [ ] As an account **without** update permission on the webhook, attempt Retry and Cancel → both are rejected at the API with a clear permission error.

**Expected result**: No new permission concept; existing webhook-management permission gates both actions.

## Edge Cases

- [ ] ENV header referencing an unset variable → delivery fails with a `CONFIG` reason naming the webhook and header, not a crash.
- [ ] View a non-webhook task → generic `available_actions` (empty) and no request/response fields.
- [ ] Retry a delivery whose run aged out of retention → "delivery no longer available", no broken retry.
- [ ] Retry/Cancel an action that became unavailable since page load → rejected server-side, no silent double-send.

## Teardown

```bash
uv run invoke demo.destroy
```

Delete the test webhook and its key-value headers if the stack is kept; take down the test endpoint.

## Sign-off

- [ ] All scenarios above pass.
- [ ] No unexpected output, warnings, or errors observed.
- [ ] Tester: ______________________  Date: __________
