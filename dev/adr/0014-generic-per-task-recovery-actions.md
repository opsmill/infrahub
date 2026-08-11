# 14. Generic per-task recovery actions with polymorphic task typing

**Status:** Accepted
**Date:** 2026-07-31
**Author:** @opsmill-team

**Source:** `specs/archive/ifc-2755-webhook-delivery-operability/research.md` (D6, D7, D8, D9) and
that spec's `spec.md` (FR-016, FR-017, FR-027).

## Context

Retry and cancel needed a GraphQL surface. They could be webhook-specific mutations, or a generic
capability carried by every task. Webhook deliveries are the first, and currently only, task type
that supports them, but other task types may follow, and the surface should not have to change when
they do.

## Decision

Expose recovery actions as a generic capability on every task. `available_actions` (server-computed
from the run's workflow name and current state, as the single source of truth) and the classified
`error` sit on a `TaskNodeInterface`. Concrete task types are discriminated by the run's workflow
name via `resolve_type` against a `TASK_TYPES` map, mirroring the events type hierarchy;
`WebhookDeliveryTask` is the first concrete type. Retry and cancel are generic, task-id-addressable
mutations (`InfrahubTaskRetry` / `InfrahubTaskCancel`, modeled on the bespoke `BranchCreate`
pattern), not webhook-specific. Genericity is confined to the interface: actual support is per task
type, so only `WEBHOOK_SEND` runs are actionable and any other task resolves the actions as
unavailable. Authorization reuses the existing object-level update permission on the target webhook
node; no new global permission is introduced.

The polymorphic task typing is documented in
[Async Tasks](../knowledge/backend/async-tasks.md), and the delivery-specific behavior in
[Webhooks](../knowledge/backend/webhooks.md).

## Consequences

### Positive

- A new actionable task type plugs in by adding a `TASK_TYPES` entry plus an availability rule, with
  no new mutation shape.
- `TaskNodes.node` becomes the interface, but `TaskNode` keeps its name, so existing selections, SDK
  usage, and `__typename` checks keep resolving with no backfill.

### Negative

- The generic surface can advertise actions a given task type does not support (they resolve
  unavailable), so callers must read availability rather than assume it.
- Delivery operability is tied to the webhook node's update permission rather than a dedicated
  permission concept.

### Neutral

- Availability is computed once server-side; the frontend renders it and disables controls, and the
  mutations re-check availability at execution time to reject a stale action rather than double-send.

## Alternatives Considered

### Webhook-specific mutations (`CoreWebhookRetry` / `CoreWebhookCancel`)

Rejected by the clarified genericity directive.

### A stored `task_type` enum or field, or a tag, as the discriminant

Rejected. The workflow name is intrinsic to every run, so historical runs type correctly with no
backfill and no extra stored field.

### A new `MANAGE_WEBHOOKS` global permission

Rejected. None exists today, and the spec forbids introducing a new permission model.
