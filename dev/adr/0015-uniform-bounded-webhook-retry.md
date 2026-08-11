# 15. Uniform bounded fixed-delay auto-retry for webhook deliveries

**Status:** Accepted
**Date:** 2026-07-31
**Author:** @opsmill-team

**Source:** `specs/archive/ifc-2755-webhook-delivery-operability/research.md` (D2) and that spec's
`spec.md` (FR-012, FR-012a, SC-004).

## Context

A failing delivery auto-retries. Two policy choices were open: the backoff shape (fixed versus
exponential), and whether to gate retries by failure class (transient-only versus uniform).

## Decision

Retry every failing delivery uniformly: a fixed delay of about 120s, bounded to 3 retries (4 sends
total), regardless of failure class. No exponential backoff, and no transient-only gating. The
classified failure reason and its per-class remediation hint, not a retry gate, are what tell the
operator whether waiting on the cycle can help. The `transient` flag once carried on the classifier
result was removed; each status class now owns its remediation hint directly.

The retry behavior and its relation to zombie detection are documented in
[Webhooks](../knowledge/backend/webhooks.md) and
[Async Tasks](../knowledge/backend/async-tasks.md).

## Consequences

### Positive

- One flow-level retry policy, with no attempt-level conditional machinery.

### Negative

- A 4xx or configuration failure that cannot succeed on retry still consumes its bounded attempts
  before settling.
- A run parks in `AwaitingRetry` between attempts, holding an execution slot; the bounded fixed delay
  caps how long.

### Neutral

- The zombie-detection window is sized above this fixed backoff, a relationship that holds because
  the delay is fixed and known.

## Alternatives Considered

### Exponential backoff with jitter (the design-doc original)

Rejected. A long back-off parks many runs holding execution slots while waiting on a delayed attempt.

### Transient-only gating (retry timeout / connection / 5xx, fail 4xx / configuration immediately)

Rejected. It requires attempt-level retry-condition machinery whose complexity outweighs the cost of
the bounded extra attempts.
