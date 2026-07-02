# Feature Specification: Webhook Delivery Operability

**Feature Branch**: `pmi-20260624-speckit-end-of-webhooks`
**Created**: 2026-06-24
**Status**: Draft
**Input**: IFC-2753 (manual cancel), IFC-2755 (task typing + HTTP capture/display), IFC-2119 (manual retry), IFC-2754 (enhanced logs + error classification); design: "Webhooks Delivery Operability" and "Webhook Delivery Operability: Prefect-native design"

## Overview

A webhook delivery is currently process exhaust: a background run plus log lines. When a delivery fails, an operator sees a raw stacktrace, no record of what was sent or what came back, no classified reason, and has no way to replay or stop it. The only recovery is to re-fire the original business event — impossible once the source node is deleted.

This feature makes a delivery a first-class, inspectable, and recoverable object surfaced in the Tasks tab: operators can see the payload, the request and response, a clean classified failure reason with a remediation hint, and can retry or cancel a delivery. Recovery actions (retry, cancel) are exposed as **generic task actions** — any task carries them, and webhook deliveries are the first task type to populate them — rather than as webhook-specific operations.

## Clarifications

### Session 2026-06-24

- Q: Retry policy — backoff strategy and attempt count? → A: Fixed delay (~2 min), transient-only, bounded to 3 attempts. Exponential backoff is rejected because a long back-off would leave many flow runs parked, waiting on a delayed retry attempt to resolve.
- Q: Retry confirmation scope — confirm only on succeeded deliveries, or on every retry? → A: Confirm on every retry; each retry spawns a new independent flow run that warrants a deliberate acknowledgment. Re-delivering a succeeded delivery remains the higher-stakes case and is called out explicitly in the confirmation.
- Q: Who may retry or cancel a delivery? → A: Require the existing webhook-management permission — whoever can configure a webhook can operate its deliveries. No new or dedicated permission concept is introduced.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Inspect what a delivery sent and received (Priority: P1)

An operator opens a webhook delivery in the Tasks tab and sees the delivered payload, the request as sent (URL and headers, with secrets masked), and the response received (status code, body, latency). This works for any delivery in the retention window, whether it succeeded or failed, and reflects the last attempt made.

**Why this priority**: Without a record of the request and response, an operator cannot answer the first question of any webhook integration problem — "what did we actually send, and what came back?" Every other recovery action depends on first being able to see this. It is the foundation the rest of the feature builds on.

**Independent Test**: Configure a webhook against a test endpoint, trigger it, open the delivery, and confirm the payload, request headers (with environment-sourced headers and the signature masked), response status, response body, and latency are all visible. Verify a delivery to an endpoint returning an error still shows the captured request and response.

**Acceptance Scenarios**:

1. **Given** a delivery that completed successfully, **When** the operator opens it, **Then** the delivered payload, the request URL and headers, the response status code and body, and the latency are displayed.
2. **Given** a delivery whose request included an environment-sourced custom header and a signature header, **When** the operator views the captured request headers, **Then** those values are shown masked and no raw secret is exposed anywhere in the view.
3. **Given** a delivery that was retried before settling, **When** the operator views the request/response, **Then** the captured request/response reflects the last attempt.
4. **Given** a static (non-secret) custom header and the delivered payload, **When** the operator views the delivery, **Then** those are shown verbatim.

---

### User Story 2 - Understand why a delivery failed (Priority: P2)

When a delivery fails, the operator sees a short, classified reason (for example: a connection problem, a TLS problem, a timeout, a client-side 4xx, a server-side 5xx, a configuration error) accompanied by a remediation hint, instead of a raw stacktrace. Every failing delivery goes through the same bounded, fixed-delay auto-retry cycle; the classified reason is what tells the operator whether waiting on that cycle can help (a timeout or 5xx may clear on its own; a 4xx or configuration error needs a fix first).

**Why this priority**: A classified reason turns an opaque failure into an actionable one and tells the operator whether to fix the target, fix the configuration, or simply retry. Because the auto-retry cycle is uniform and bounded, the classification — not a retry gate — is what steers the operator's response.

**Independent Test**: Point a webhook at (a) an unreachable host, (b) an endpoint returning 404, (c) an endpoint returning 500, and (d) an endpoint with an invalid certificate; trigger each and confirm the displayed reason is correctly classified, a remediation hint matching the class is shown, and no stacktrace appears in the delivery's logs.

**Acceptance Scenarios**:

1. **Given** a delivery to an unreachable target, **When** it fails, **Then** the operator sees a connection-class reason with a hint pointing at target reachability, and no stacktrace.
2. **Given** a delivery that receives a 4xx response, **When** it fails, **Then** the reason points the operator at the URL or authentication, making clear a retry cannot succeed until the target or configuration is fixed.
3. **Given** a delivery that receives a 5xx response or times out, **When** it fails an attempt, **Then** it is retried before settling as failed.
4. **Given** a delivery whose configuration cannot be resolved, **When** it fails, **Then** it is classified as a configuration error with a hint pointing at the webhook's configured headers.
5. **Given** any failed delivery, **When** the operator inspects it, **Then** per-attempt progress is visible in the logs.
6. **Given** a delivery that fails with a classified reason, **When** the operator reads the delivery's logs, **Then** the failure appears as the clean classified message with no traceback, while an unexpected (unclassified) crash retains its full traceback.

---

### User Story 3 - Retry a delivery (Priority: P3)

An operator retrys a settled delivery. The retry replays the original frozen payload against the webhook's current configuration, producing a new delivery with a freshly computed signature. Retry is available on any delivery that has reached a terminal state — including one that previously succeeded — so an operator can re-deliver an event on demand (for example after fixing a downstream system, or to re-trigger a handler during integration testing). Retry is not available while a delivery is still in progress or auto-retrying, because that would race the pending attempt and double-send.

**Why this priority**: Retry is the long-standing recovery gap: today the only way to retry is to re-create the original event, which is impossible once the source node is gone. It depends on the delivery record (US1) existing to retry from. Allowing retry from any terminal state — not only failures — lets operators re-deliver and test on demand.

**Independent Test**: Trigger a delivery against an endpoint that is down so it fails; bring the endpoint up; retry the delivery from the UI; confirm a new delivery is created, carries the same payload, recomputes its signature, and succeeds. Separately, retry a previously succeeded delivery and confirm a new delivery is produced.

**Acceptance Scenarios**:

1. **Given** a failed delivery whose target is now reachable, **When** the operator retrys it and confirms, **Then** a new delivery is created with the same payload and a fresh signature, and it succeeds.
2. **Given** a delivery that succeeded, **When** the operator retrys it, **Then** the confirmation calls out that this re-delivers an already-processed event, and on confirming, a new delivery is created and delivered.
3. **Given** a delivery still in progress or awaiting an auto-retry, **When** the operator views it, **Then** the retry action is unavailable with a reason indicating the delivery is still in progress.
4. **Given** a delivery whose original run has aged out of the retention window, **When** the operator attempts to retry, **Then** the system reports the delivery as no longer available rather than producing a broken retry.
5. **Given** a delivery whose webhook configuration no longer resolves (the webhook was deleted), **When** the operator retrys, **Then** the retried delivery is created and fails at runtime with a clear configuration-class reason.
6. **Given** the original delivery, **When** it is resent, **Then** the original record is left unchanged as an immutable record and the retry appears as a new delivery.

---

### User Story 4 - Cancel an in-progress delivery (Priority: P4)

An operator cancels a delivery that is still in progress or awaiting an auto-retry, stopping its remaining auto-retry cycle. Cancellation is best-effort for an attempt already in flight — if the HTTP request has already left, it is not recalled — but it prevents any further scheduled attempts. A delivery that has already settled cannot be cancelled.

**Why this priority**: Cancel gives an operator closure on a delivery that is uselessly retrying against a target known to be down or misconfigured, and is the natural counterpart to retry. It is lowest priority because the auto-retry window is bounded, so the cost of not cancelling is limited.

**Independent Test**: Trigger a delivery against a slow/failing endpoint so it enters its auto-retry cycle; cancel it from the UI; confirm it transitions to a cancelled state and no further attempts are made.

**Acceptance Scenarios**:

1. **Given** a delivery that is in progress or awaiting an auto-retry, **When** the operator cancels it, **Then** it transitions to a cancelled state and no further auto-retry attempts are made.
2. **Given** a delivery that has already settled (succeeded, failed, crashed, or already cancelled), **When** the operator views it, **Then** the cancel action is unavailable with a reason indicating the delivery is already settled.
3. **Given** a cancelled delivery, **When** the operator views it later, **Then** it can be resent (cancel then retry is the two-step way to restart a delivery during its auto-retry window).

---

### Edge Cases

- A custom header key appears more than once: the delivery proceeds; behavior on duplicates is deterministic and does not break capture.
- An environment-sourced header references a variable that is not set: the delivery proceeds without that header and this is surfaced in the logs, not as a crash.
- The same delivery is resent twice in quick succession: each retry produces its own independent new delivery.
- A delivery is cancelled at the exact moment an attempt's HTTP request is already in flight: the in-flight request is not recalled, but no further attempts are scheduled.
- A non-webhook task is viewed: it carries the generic action list (empty when no actions apply) and does not expose webhook-specific request/response fields.
- An operator attempts an action that has become unavailable since the page was loaded (for example, retrying a delivery that has since started auto-retrying again): the action is rejected server-side with a clear reason rather than silently double-sending.

## Requirements *(mandatory)*

### Functional Requirements

#### Delivery as a first-class object

- **FR-001**: The system MUST represent each webhook delivery as a distinct, inspectable object surfaced in the Tasks tab, decoupled from the internal orchestration that triggered it.
- **FR-002**: The system MUST classify a delivery as a webhook delivery automatically from intrinsic run information, so that historical deliveries are recognized without any backfill.
- **FR-003**: A webhook delivery MUST expose, in addition to the fields common to all tasks, its request, its response, and its error.
- **FR-004**: Tasks that are not webhook deliveries MUST continue to behave exactly as before, with no change to their existing fields or queries.

#### Capture and display

- **FR-005**: The system MUST capture the delivered payload, the request as sent (URL and headers), and the response received (status code, body, and latency) for a delivery, on both success and failure.
- **FR-006**: The captured request/response MUST reflect the last attempt made for the delivery.
- **FR-007**: The system MUST mask, at the point of capture, every header whose value is secret by design (environment-sourced headers and the request signature), so that no raw secret is ever persisted with the delivery.
- **FR-008**: The system MUST preserve non-secret headers and the delivered payload verbatim in the captured record.
- **FR-009**: The operator-facing view MUST present the payload, request, response, latency, target URL, last-attempt timestamp, HTTP status code, and (on failure) the classified reason.

#### Failure classification and retry

- **FR-010**: When a delivery fails, the system MUST present a short classified reason drawn from a small fixed set of failure classes, instead of a raw stacktrace.
- **FR-011**: Each classified failure reason MUST be accompanied by a remediation hint appropriate to its class.
- **FR-012**: The system MUST automatically retry a failing delivery within the bounded fixed-delay cycle, regardless of failure class. Transient-only gating (retrying only timeout/connection/5xx and failing 4xx/configuration immediately) was evaluated and rejected: it requires conditional retry machinery at the attempt level whose complexity outweighs the cost of the bounded extra attempts. The classified reason and its remediation hint (FR-010, FR-011) are what tell the operator whether waiting on the retry cycle is useful.
- **FR-012a**: Auto-retry MUST use a fixed delay between attempts (approximately 2 minutes) and MUST be bounded to 3 attempts. A growing (exponential) back-off is explicitly rejected, because a long back-off would leave many deliveries parked in an awaiting-retry state, holding execution slots while waiting on a delayed attempt.
- **FR-013**: The final classified reason MUST reflect the failure that settles the delivery after auto-retries are exhausted, not an intermediate attempt.
- **FR-014**: An unexpected (non-delivery) error MUST remain distinguishable from an expected delivery failure, retaining its diagnostic detail rather than being flattened into a clean message.
- **FR-015**: Per-attempt progress MUST remain visible in the delivery's logs.
- **FR-015a**: Each delivery attempt MUST log the outgoing request — target URL, headers, and payload — together with the attempt number and the attempt bound (attempt N of M), so the delivery's logs show what was sent on every attempt. The payload MAY be truncated at the default log level, with the full payload available at debug level.
- **FR-015b**: Header values that are secret by design — environment-sourced values, the request signature, and well-known credential headers (matched case-insensitively) — MUST be masked in the logged request; static custom headers and standard headers are logged verbatim. This extends the capture-time redaction guarantee (FR-007) to the log channel.
- **FR-015c**: An expected, classified delivery failure MUST NOT emit a stacktrace into the delivery's logs; it MUST appear as the clean classified message. Unexpected (unclassified) errors MUST retain their full traceback (consistent with FR-014).

#### Generic task actions: retry and cancel

- **FR-016**: The system MUST expose the available recovery actions for a task as a generic capability carried by every task, computed server-side as the single source of truth, with an availability state and a reason when unavailable.
- **FR-017**: The retry and cancel mutations MUST present a generic interface addressable by task identifier (not a webhook-specific mutation shape). Genericity is confined to the query/mutation surface: it does NOT imply that every task type supports these actions. Actual support is determined per task type, and webhook deliveries are the only type that supports retry and cancel in this feature; for any other task type the actions resolve as unavailable.
- **FR-018**: Retry MUST be available for a delivery in any terminal state — including one that succeeded — and MUST be unavailable while a delivery is in progress or awaiting an auto-retry.
- **FR-019**: Retrying a delivery MUST replay its original frozen payload against the webhook's current configuration, producing a new independent delivery with a freshly computed signature, and MUST leave the original delivery unchanged.
- **FR-020**: Retrying a delivery whose underlying record has aged out of retention MUST fail with a clear "no longer available" result rather than producing a broken retry.
- **FR-021**: Every retry MUST require an explicit confirmation before it proceeds, because each retry spawns a new independent delivery. The confirmation for a succeeded delivery MUST additionally call out that it re-delivers an event the target has already processed.
- **FR-022**: Cancel MUST be available only while a delivery is non-terminal, and MUST stop any further scheduled auto-retry attempts.
- **FR-023**: Cancellation MUST be best-effort for an attempt already in flight; an HTTP request already sent is not recalled.
- **FR-024**: A delivery that has settled MUST NOT be cancellable; the cancel action MUST report it as already settled.
- **FR-025**: The frontend MUST drive the retry and cancel controls from the server-computed availability, disabling each control and showing its unavailability reason when the action does not apply.
- **FR-026**: Any action attempted after it has become unavailable MUST be rejected server-side with a clear reason rather than performed.
- **FR-027**: Retry and cancel MUST be authorized against the existing webhook-management permission; an operator who can configure a webhook can operate its deliveries, and no new or elevated permission is introduced.

### Key Entities *(include if feature involves data)*

- **Delivery**: A single attempt-set to send one frozen payload to one webhook target, surfaced as a task. Carries state, payload, request, response, latency, classified failure reason (when failed), and available actions. Lives within the background system's retention window.
- **Captured request**: The URL and headers as sent on the last attempt, with secret-by-design values masked.
- **Captured response**: The status code, body, and latency of the last attempt's response.
- **Classified failure reason**: One of a small fixed set of failure classes plus a remediation hint; present only when the delivery failed.
- **Available actions**: The generic, per-task set of recovery actions (retry, cancel) with, for each, whether it is currently available and, if not, why.
- **Webhook configuration**: The target URL, custom headers, certificate-validation setting, and signing key, resolved per attempt (not frozen with the payload), so that fixing a misconfiguration and retrying works.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: For any delivery within the retention window, an operator can determine what was sent and what came back without leaving the delivery view and without consulting raw logs — in 100% of cases the payload, request, response, and latency are present.
- **SC-002**: No raw secret value (environment-sourced header or signing material) is ever exposed in the delivery view or the persisted delivery record.
- **SC-003**: 100% of delivery failures presented to the operator are a classified reason with a remediation hint; 0% present a raw stacktrace.
- **SC-004**: 100% of delivery failures carry a remediation hint matching their class — 4xx and configuration failures direct the operator at the target or configuration, while timeout, connection, and 5xx failures indicate the bounded auto-retry cycle may resolve them; the cycle stays bounded to 3 fixed-delay attempts for every class.
- **SC-005**: An operator can recover a failed delivery against a now-healthy target in under one minute, using only the delivery view, without re-creating the original business event.
- **SC-006**: An operator can stop a uselessly retrying delivery from the delivery view, after which no further attempts are made.
- **SC-007**: The change introduces no data migration and no new persisted domain schema; existing task queries continue to work unchanged.

## Assumptions

- The structural foundation — splitting the orchestrator that freezes the payload from the user-visible `webhook_send`, which carries its own fixed-delay bounded auto-retries — is already in place on the current branch (see the Implementation Sync revisions below); this feature adds the operability layer (capture, classification, typing, retry, cancel) on top. The landed retry policy retries on every failure, and FR-012 records the decision to keep it that way (transient-only gating was evaluated and rejected).
- Delivery data lives in the background execution system and is subject to its retention window (default 30 days); deliveries older than the window are not inspectable or retryable. This is an accepted trade for requiring no new domain schema or migration.
- Retry replays the frozen payload against the *current* configuration with a fresh signature; it deliberately does not replay a byte-for-byte frozen request, so that fixing a misconfiguration and retrying succeeds.
- The payload is frozen once at delivery creation; headers, signature, and configuration are recomputed per attempt and per retry.
- Whether the captured request/response is stored as one grouped record or as separate request and response records is an implementation detail not visible to the operator; the operator-facing requirement is only that both are shown.
- Permission to retry or cancel a delivery is the existing webhook-management permission (see FR-027); this feature introduces no new permission model.
- Retry and cancel are state-gated rather than coordinated through locking; concurrent or stale attempts are resolved by the server-side availability check at execution time (FR-026).
- "Terminal" means a delivery has settled (succeeded, failed, crashed, or cancelled); "non-terminal" means it is in progress or awaiting an auto-retry.

## Revision: Implementation Sync — 2026-06-26

Reason: Reconcile the specification with foundation work that has merged ahead of the operability layer, so the spec reflects shipped reality rather than a greenfield baseline. Documentation-only sync; no constitution, `dev/guidelines/`, or `dev/adr/` conflict.

Landed prerequisites (structural; out of this spec's scope but the layer it builds on):

| Change | Bearing on this spec |
|---|---|
| `webhook_send` split into its own flow (#9672) | The delivery this spec makes a first-class object (FR-001) already exists as a standalone run. |
| Fixed-delay bounded retry policy on `webhook_send` (#9676) | FR-012a's retry mechanism (3 attempts, ~120s fixed delay) is implemented. It retries on every failure today; the transient-only gating in FR-012 is the remaining operability layer. |
| Webhook flow runs tagged with the webhook node id | Underpins the per-delivery, object-level authorization in FR-027 and node-scoped lookup. |

Outstanding (this feature's scope): capture and redaction (FR-005–FR-009), failure classification with remediation hints (FR-010–FR-014), polymorphic task typing (FR-001–FR-004), and the generic retry/cancel actions (FR-016–FR-027).

## Revision: Implementation Sync — 2026-07-02

Reason: Reconcile the specification with the operability work landed since the previous sync (IFC-2711 epic: classification IFC-2754, retry/cancel IFC-2119/IFC-2753, log visibility IFC-2832/IFC-2833, traceback suppression IFC-2846). Documentation-only sync; no constitution, `dev/guidelines/`, or `dev/adr/` conflict.

| Change | Bearing on this spec |
|---|---|
| Failure classification with clean, user-facing reasons (#9718) | FR-010, FR-011, FR-013, FR-014 implemented; remediation hints are owned per failure class. |
| Transient-only retry gating rejected (decision) | FR-012 rewritten: the bounded fixed-delay cycle applies uniformly; the classification steers the operator instead of a retry gate. SC-004 and US2 scenarios amended accordingly. |
| Outgoing request logged per attempt with redacted headers, truncated payload, and attempt number | New FR-015a/FR-015b. Log-channel visibility landed ahead of the persisted `http` artifact; FR-005–FR-009 (capture + GraphQL/UI display) remain outstanding. |
| Traceback suppression for classified delivery failures | New FR-015c and US2 acceptance scenario 6: classified failures appear in the run logs as the clean message only; unexpected crashes keep their traceback. |
| Generic retry/cancel actions and Tasks-tab surfacing | FR-016–FR-027 substantially implemented (see tasks.md for what remains, e.g. E2E coverage). |
