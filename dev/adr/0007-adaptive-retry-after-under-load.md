# 7. Adaptive Retry-After under sustained load

**Status:** Accepted
**Date:** 2026-07-24
**Author:** @opsmill-team

## Context

The priority-aware API backpressure layer sheds requests with `429 Too Many Requests` and a
`Retry-After` header. First-party clients honour that header: the Python SDK retries a shed
request with backoff, and the frontend stamps `X-Priority: high` so interactive traffic is
protected while background traffic (generators, artifacts, diffs, repository syncs — all
unprioritised, so `MEDIUM`) is shed first.

The header was a single static value (`1s`). Two problems followed:

- The SDK honours `Retry-After` verbatim when present, so a fixed `1s` **overrode the SDK's own
  exponential backoff** — every retry waited exactly one second. With a bounded retry count the
  client's whole budget collapsed to a few seconds.
- Under the sustained background load of a normal run, that budget was exhausted before the load
  cleared, so background work *failed* rather than being merely deprioritised — the opposite of
  the feature's intent, and enough to break the end-to-end suite.

The signal needed is one the server already has: how *hard* it is loaded right now, and how
*long* the load has persisted. A short slowdown (a cache warming, a GC pause) should not be
treated the same as ten minutes of genuine overload.

## Decision

The `Retry-After` for a shed request is computed on two axes and clamped to a maximum kept below
the SDK's per-retry cap so the client honours it verbatim.

- **Intensity — per priority.** The value reuses the *same* tiering that drives the graduated
  shed fraction: a shared `stress_tier(ratio, threshold)` returns `0/1/2/3` (none/mild/moderate/
  severe) at `1x/2x/5x` of that class's own trigger. The tier maps to a configured base
  (`1s / 5s / 10s` for levels 1/2/3). Because the trigger differs per class, the advised wait
  tracks the class, not a single global level; a backstop shed (waiter queue full) is treated as
  the top tier, and any shed floors at level 1.
- **Persistence — global.** A per-worker episode clock counts how long the database-stress ratio
  has *continuously* stayed at or above a significant-load line (`20.0` by default). Ratios below
  that line are a warm-up zone that never accrues time. The base is multiplied by `x1 / x2 / x3`
  as the episode passes `0 / 60s / 300s`, then clamped to the maximum (`30s`).

The sustained-load duration is exposed as `infrahub_admission_sustained_load_seconds` so operators
can graph and alert on the exact signal driving escalation. The logic lives in a dedicated,
dependency-injected `RetryAfterPolicy` component owned by the admission controller; the tiering
primitive is shared with the shed decision so a class's escalation is expressed once.

## Consequences

### Positive

- A client's bounded retry budget spans a proportionally longer real-time window exactly when
  overload is worst, so background work rides out a burst instead of failing.
- The `Retry-After` is a truthful backpressure signal: it reflects both current intensity and how
  long the server has been struggling.
- Reusing the shed tiering keeps one source of truth — the drop percentage and the retry hint move
  together, and a class's larger tolerance carries through to its retry hint.

### Negative

- More configuration surface (`…_retry_after_level1/2/3_seconds`, `…_retry_after_max_seconds`,
  `…_significant_load_stress_ratio`, `…_sustained_load_warn/high_seconds`).
- Correct end-to-end behaviour depends on clients honouring `Retry-After` and retrying long
  enough; a client with too small a retry budget still fails under long overload.
- The episode clock is per worker (no cross-worker view), consistent with the rest of the layer.

### Neutral

- The escalation is anchored to the database-stress signal; if that signal is miscalibrated the
  retry hint inherits the miscalibration.
- Clients that ignore `Retry-After` are unaffected — the header is advisory.

## Alternatives Considered

### A single larger fixed `Retry-After`

Simple, but it either over-waits under light load or under-waits under heavy load, and still
overrides the client's own backoff. It cannot distinguish a transient blip from sustained overload.

### Let the client's exponential backoff do all the work (send no `Retry-After`)

The server knows the load; the client does not. Dropping the header discards the best signal and
leaves every client to rediscover the load level independently, with no shared notion of severity.

### Intensity only, no persistence axis

Escalating by current intensity alone does not lengthen the budget for a load level that is mild
but unrelenting — precisely the case that exhausts a bounded retry count.

### Additive rather than multiplicative combination

Adding a per-duration bonus to the base was considered; multiplication was chosen because it keeps
the persistence penalty proportional to intensity (a severe level escalates faster than a mild one)
and stays within a single clamp.
