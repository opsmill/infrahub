# 9. Per-worker, coordination-free admission capacity

**Status:** Accepted
**Date:** 2026-07-26
**Author:** @opsmill-team

**Source:** `specs/archive/ifc-2886-priority-api-backpressure/research.md` (R4, R8)

## Context

The API runs as gunicorn with several uvicorn workers per container, and containers scale
horizontally. The admission layer needs a concurrency cap: how many requests a worker may have
in-flight before it starts queueing and then shedding.

Two questions had to be answered together, because the answer to one constrains the other: *where
does the cap live* (in each process, or shared across the fleet) and *where does its value come
from* (a configured number, or something derived).

A shared limiter is the conventional answer for fleet-wide rate limiting, and it is the answer
that is hardest to walk back into — it introduces an infrastructure dependency, a network round
trip on the hot path, and a failure mode of its own. A per-worker cap is the opposite: no new
moving parts, but no fleet-wide view either.

## Decision

**All admission state is in-process and per worker.** The slot pool, the per-class CoDel
controllers, the database-stress window, and the sustained-load episode clock are instantiated
once per process and live for the process lifetime. There is no shared limiter, no Redis, no
cross-worker or cross-replica coordination, and no attempt to compute an aggregate fleet capacity.

**The cap is derived from a real per-process signal**, not a constant: the worker's own Neo4j
connection-pool size (`INFRAHUB_DB_MAX_CONNECTION_POOL_SIZE`, now an explicit setting passed to
the driver rather than an implicit driver default) multiplied by a concurrency factor, with a
floor of one slot. The premise is roughly one database connection per in-flight request, so the
cap tracks the resource the process actually owns; the factor is the lever when a deployment
saturates the database before slot contention binds.

Consequently, provisioning the database for peak aggregate load (per-process cap × workers ×
replicas) is an operator responsibility, and every admission metric is a per-worker series.

## Consequences

### Positive

- Zero new infrastructure and zero hot-path coordination cost: the admission decision is a few
  in-memory operations, which is what makes it viable at the outermost gate on every request.
- The layer cannot fail in a new way. There is no limiter to be unreachable, no split brain, no
  stale shared counter.
- It scales without tuning: adding workers or replicas adds capacity proportionally, and each
  worker protects exactly the resource it holds. No per-deployment magic number.
- Each worker degrades on its own evidence — a worker whose queries are slow sheds, without
  waiting for a fleet-wide consensus that may never form.

### Negative

- **No fleet-wide guarantee.** The layer cannot enforce a global request rate or a global fair
  share; it can only keep each worker from overcommitting itself. Aggregate protection is
  emergent, not enforced.
- Uneven load balancing shows up as uneven shedding: a worker handed a burst sheds while its
  siblings idle.
- Operators must reason in per-worker terms. Gauges (`in_flight`, `waiters`, `max_concurrency`,
  `sustained_load_seconds`) are per-process series and are meaningless if naively summed; only the
  database-stress gauges are aggregated across workers, and deliberately so.
- Introducing coordination later is not a refactor — it changes the meaning of every metric, adds
  a dependency, and moves capacity planning off the operator.

### Neutral

- The cap's accuracy depends on the "one connection per in-flight request" premise. Where that
  does not hold, the concurrency factor is the calibration knob rather than a redesign.
- The `PROMETHEUS_MULTIPROC_DIR` path is intentionally not wired for the per-class admission
  gauges; doing so would require per-metric multiprocess modes and would blur the per-worker view
  this decision rests on.

## Alternatives Considered

### A shared/global limiter (Redis or similar)

Rejected. It buys a fleet-wide view at the cost of a network round trip on every request at the
outermost gate, a new hard dependency in the admission path, and a new class of outage. The
protection actually needed — a worker not admitting more work than its own database connections
can serve — is fully expressible per process.

### A hard-coded `max_concurrency`

Rejected. It is wrong at every deployment size but one, and it makes the "tuning-free across
deployments" goal unreachable. It also decouples the cap from the resource it is meant to protect,
so a change to the connection pool silently invalidates it.

### Reading the pool size from the Neo4j driver's internals

Rejected. `driver._pool.pool_config.max_connection_pool_size` is private API and would break on a
driver upgrade. Promoting the pool size to a first-class setting makes it explicit, documented,
testable, and reusable by the derivation.

### Deriving the cap from CPU count or a load average

Rejected. The binding constraint under Infrahub's workload is database concurrency, not CPU. A
CPU-derived cap would admit far past the point where queries start queueing inside Neo4j — the
exact silent saturation the layer exists to prevent.
