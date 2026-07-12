# Contract: Backpressure metrics on `/metrics`

**Feature**: IFC-2886 | Exported through the **existing** `/metrics` endpoint (`starlette_exporter.handle_metrics`, `backend/infrahub/server.py:222`) via the default Prometheus registry. **No new endpoint** (FR-OBS-8).

- **Module**: `backend/infrahub/api/admission/metrics.py`
- **Prefix**: `METRIC_PREFIX = "infrahub_admission"` (matches `database/metrics.py` / `graphql/metrics.py` convention).
- **Registration**: module-level `prometheus_client` singletons on the default registry — auto-exported, zero endpoint change.
- **`priority` label values**: `high`, `normal`, `low`.
- **Scope**: per worker process (each gunicorn/uvicorn worker exports its own series; this is by design — admission state is per-worker, FR-009). Operators read per-worker series; no cross-worker aggregation in v1.

## Metric families

| FR-OBS | Metric name | Type | Labels | Meaning |
|--------|-------------|------|--------|---------|
| 1 | `infrahub_admission_offered_total` | Counter | `priority` | Requests entering the admission layer, per class (offered load). |
| 5 | `infrahub_admission_admitted_total` | Counter | `priority` | Requests admitted (handler ran), per class. |
| 2 | `infrahub_admission_rejected_total` | Counter | `priority`, `reason` | Shed requests, per class, split by `reason` ∈ {`codel`, `backstop`}. |
| 3 | `infrahub_admission_in_flight` | Gauge | `priority` | Currently-running admitted requests, per class. |
| 3 | `infrahub_admission_waiters` | Gauge | `priority` | Requests currently queued waiting for a slot, per class. |
| 4 | `infrahub_admission_sojourn_seconds` | Histogram | `priority` | Distribution of slot-wait (sojourn) time per class; exposes P50/P99 and the gradient. |
| 6 | `infrahub_admission_max_concurrency` | Gauge | (none) | The effective derived per-worker slot cap. |
| 7 | `infrahub_admission_missing_priority_total` | Counter | (none) | Requests arriving with no/invalid `X-Priority` (adoption tracking). |

**Histogram buckets** (`infrahub_admission_sojourn_seconds`): `[0.001, 0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1, 5]` (seconds; fine at the low end where the CoDel `target` sits).

## Invariants (assertion-testable)

| ID | Invariant |
|----|-----------|
| M-1 | For each class, for every request the server adjudicates: `offered_total == admitted_total + rejected_total{codel} + rejected_total{backstop}`. A request whose client disconnects while it is still queued is counted in `offered_total` only — it is neither admitted nor shed by the server — so under in-flight cancellation `offered_total` may transiently exceed `admitted + rejected` by the number of abandoned waiters. The `waiters`/`in_flight` gauges stay accurate across that case (they are driven by the pool's own enqueue/dequeue transitions, including cancellation). |
| M-2 | `max_concurrency` gauge equals `derive_max_concurrency(pool_size, factor)` and is > 0 (no magic number; FR-009/FR-OBS-6). |
| M-3 | `in_flight{priority}` never exceeds `max_concurrency`; `sum(in_flight)` never exceeds `max_concurrency`. |
| M-4 | Every shed increments `rejected_total` with a valid `reason` label; no shed is uncounted (M-1 closes the accounting). |
| M-5 | `missing_priority_total` increments on exactly those requests with absent/empty/invalid `X-Priority`. |
| M-6 | A `sojourn_seconds` observation is recorded for every request that attempted a slot acquire (admitted or codel-shed); backstop-shed requests (no acquire attempt) are exempt. |

## Test approach

Assert **deltas** on module-level metric objects via `metric.labels(...)._value.get()` before/after driving traffic (the existing precedent, `backend/tests/unit/database/test_retry_db_transaction.py:150-161`) — absolute values are unreliable because the global registry persists across tests. Histogram counts via `histogram.labels(priority)._sum`/`._count` samples.
