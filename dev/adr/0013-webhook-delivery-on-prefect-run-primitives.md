# 13. Webhook deliveries as retention-bounded Prefect-run objects

**Status:** Accepted
**Date:** 2026-07-31
**Author:** @opsmill-team

**Source:** `specs/archive/ifc-2755-webhook-delivery-operability/research.md` (D1, D3, supported by
D4, D5) and that spec's `spec.md` (SC-007, FR-001 through FR-009).

## Context

A webhook delivery was process exhaust: a background run plus log lines, with no record of what was
sent or received, no classified reason, and no way to replay or stop it. Operators needed the
delivery to be a first-class, inspectable, recoverable object. The open question was where a
delivery's state and captured request/response live.

## Decision

Model each delivery as the user-visible `webhook_send` flow run itself, promoted to a registered
CORE workflow so it is resubmittable by id and discriminable by name. All delivery data lives on
Prefect run primitives: frozen parameters (the payload), tags (the webhook node and branch), run
state (the lifecycle), and a single grouped `http` artifact (request, response, and classified error
together) written per run and reflecting the last attempt. No new Neo4j node, attribute,
relationship, or migration. Header redaction and failure classification happen in-process before the
artifact is written, so no raw secret is ever persisted.

The capture and read-back paths are documented in
[Webhooks](../knowledge/backend/webhooks.md).

## Consequences

### Positive

- No migration and no backfill: historical runs are inspectable because the delivery model is
  intrinsic to the run, not a separate stored record.
- Read-back mirrors the existing progress-artifact path (one batched read, gated on the GraphQL field
  selection), so there is no extra per-task query cost.

### Negative

- Delivery data is bounded by Prefect retention (about 30 days). Older deliveries are neither
  inspectable nor retryable, and a retry of an aged-out run fails with a clean "no longer available".
- The capture reflects only the settling (last) attempt, not per-attempt history.

### Neutral

- Delivery history is operational data on Prefect runs, not branch-versioned graph data.

## Alternatives Considered

### Keep `webhook_send` an inline subflow and retry by re-invoking `webhook_process`

Rejected. It re-runs the transform and re-derives the payload (not a frozen replay) and
re-introduces the orchestrator parent the design drops for retries.

### Persist deliveries as a domain node with a migration

Rejected. It adds schema and backfill for data whose lifetime is purely operational, contradicting
the no-migration goal.

### Separate request/response artifacts, or a per-attempt list artifact

Rejected. Two reads for no operator benefit, or unbounded artifact growth.
