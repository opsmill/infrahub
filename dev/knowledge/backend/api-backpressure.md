# API Backpressure (Priority-Aware Load Shedding)

> Part of: `dev/knowledge/backend/` | Related: [architecture.md](architecture.md), [Frontend request priority](../frontend/request-priority.md)

How the server keeps the frontend responsive under heavy background load by shedding requests
by priority, and how it gauges database stress to decide when to shed.

## Why it exists

Background work (generators, artifacts, diffs, repository syncs, computed attributes) and
interactive frontend traffic share one finite uvicorn worker pool and one Neo4j connection pool.
Without prioritization the API is origin-blind: under background overload it can no longer serve
the frontend and the app appears to hang. The admission layer sheds low-priority work first so
interactive requests stay fast, with no per-customer tuning.

It is **per worker process and coordination-free** — no shared limiter, no Redis. Each worker
protects the capacity it actually owns.

## Request priority

Callers declare priority with an `X-Priority` header: `high`, `medium`, or `low`. A missing or
invalid value resolves to `medium`, so the layer is safe to deploy before any caller is updated.
The class is derived solely from the header.

The priority enum is ordered so a lower value means a higher priority (`HIGH < MEDIUM < LOW`);
iterating it yields HIGH, MEDIUM, LOW, which the slot pool relies on for wake ordering.

The frontend is the first-class emitter of this header — see
[Frontend request priority](../frontend/request-priority.md). Background flows propagate their
task priority as the header on their own SDK calls.

## Components

Everything lives in `backend/infrahub/api/admission/`:

| File | Responsibility |
|---|---|
| `middleware.py` | `AdmissionMiddleware`, the outermost pure-ASGI gate |
| `controller.py` | `AdmissionController`, the admit/shed decision, and its settings-reading factory |
| `slot_pool.py` | `PrioritySlotPool`, bounded concurrency with per-class FIFO waiter queues |
| `codel.py` | `CoDelController`, the pure CoDel state machine |
| `capacity.py` | `derive_max_concurrency`, the slot-cap derivation |
| `priority.py` | the `Priority` enum and `X-Priority` header parsing |
| `metrics.py` | the `infrahub_admission_*` Prometheus families |

The database-stress signal it consumes lives in `backend/infrahub/database/load_signal.py`.

## The request path

`AdmissionMiddleware` is registered **outermost** (added last in `server.py`, so Starlette runs
it first). Load is shed before any downstream work — auth, routing, DB — runs. A shed request is
answered with a `429` error envelope carrying `Retry-After` and never reaches the app.

Pass-through cases that bypass admission entirely:

- Non-`http` scopes (WebSocket, lifespan).
- The kill-switch: when `backpressure_enabled` is false, every request passes through.
- Excluded paths — liveness/scrape/static/docs: `/health`, `/metrics`, `/assets`, `/favicons`,
  `/docs`, `/api/schema`. Liveness and scraping must never be shed.
- CORS preflights (`OPTIONS` advertising `access-control-request-method`) — see
  [Known limitations](#known-limitations).

## The admission decision

`AdmissionController.admit()` turns a priority class into admit or shed. Three independent
mechanisms can shed; none is a precondition of another:

1. **Backstop** — an unconditional per-class cap on queued waiters. It is the memory-safety
   bound: a class whose waiter queue is already at its cap is rejected immediately
   (`reason="backstop"`), before acquiring a slot. HIGH gets a larger cap than MEDIUM/LOW.
2. **Database stress** — sheds a growing *fraction* of a class as the database gets slower (see
   [below](#the-database-stress-signal)). Reported as `reason="stress"`.
3. **CoDel** — sheds when a class's slot-wait (sojourn) overruns, independent of database
   stress. Reported as `reason="codel"`.

Both the stress draw and the CoDel decision are evaluated on every admitted-slot request, so
CoDel keeps observing sojourn continuously. When both fire the shed is attributed to `stress`,
so that dimension stays visible in the metrics.

### Priority slot pool

`PrioritySlotPool` holds `max_concurrency` slots shared across the classes, with a per-class FIFO
waiter queue. A freed slot is handed to the highest-priority non-empty queue first, FIFO within a
class. The acquire path is cancellation-safe (modeled on `asyncio.Semaphore`): a cancelled waiter
deregisters itself and re-releases any slot handed to it in the same tick, so no slot leaks. The
time a request spends waiting is its **sojourn**.

`max_concurrency` is derived (`derive_max_concurrency`) from the worker's own Neo4j pool size
times a factor, floored at 1 — no hard-coded constant.

### CoDel

`CoDelController` (one instance per class) keys off sojourn rather than a queue-length threshold,
so it needs no per-deployment tuning. Once sojourn stays above `target` continuously for a full
`interval` it enters the dropping state and sheds on an inverse-square-root cadence; a single
sub-target sample exits the state (bounded recovery); a burst shorter than `interval` never
drops. HIGH gets a larger effective target (a multiplier), so it sheds last.

## The database stress signal

The admission layer decides *when* the database is stressed from one reference query rather than
guessing from queue depth. `ReferenceQueryLoadTracker` (`database/load_signal.py`) is a per-worker
singleton, fed from the query-execution path in `database/__init__.py`.

- **Reference query** — the global permission query (`account_global_permissions`), which runs
  once on essentially every authenticated request with no caching, so its timing is an
  always-present proxy for overall database load. Only **read** executions feed the signal, so a
  write sharing the name cannot pollute it.
- **Measurement** — the query's own execution time (submission through draining the result),
  timed in-process. Sub-resolution timings are clamped up to a small floor so a near-zero
  measurement cannot pin the baseline at zero.
- **Floor** — the all-time minimum observed execution time: the best the database has
  demonstrated. It is an absolute running minimum (it never rises), so a spurious fast outlier
  lowers it until the process restarts.
- **Window** — a rolling window (default 20s) of recent observations, held in one list kept
  sorted so the minimum and the **median** are both O(1). The median, not the mean, is the
  central-tendency measure: with sparse idle traffic a single slow sample (a GC pause, a
  scheduling blip) would dominate a mean but barely moves a median.
- **Stress ratio** — the window median divided by the floor. A ratio of `5` means the database is
  currently ~5× slower than at its best.

### Tiered, graduated shedding

Each class has a **trigger** (a stress ratio, configurable per class) at which it starts shedding,
ordered so low-priority traffic sheds first and interactive traffic is protected until extreme
load: LOW at the lowest ratio, MEDIUM higher, HIGH highest.

Past a class's trigger, the *fraction* of that class shed escalates with how far the ratio has
climbed past the trigger — a graduated response rather than shedding the whole class at once:

| Multiple of the trigger | Fraction shed |
|---|---|
| below 1× | 0% |
| 1× – 2× | 20% |
| 2× – 5× | 50% |
| 5× and beyond | 80% |

The fraction is applied as a per-request random draw. Until the window holds a minimum number of
samples the signal is treated as unstressed, so a cold or outlier floor cannot shed traffic.

## Metrics

All on the existing `/metrics` endpoint.

Admission (`infrahub_admission_*`): `offered_total`, `admitted_total`,
`rejected_total{priority,reason}` (reason is `stress`, `codel`, or `backstop`), `in_flight`,
`waiters`, `sojourn_seconds`, `max_concurrency`, `missing_priority_total` (adoption tracking).

Stress signal (`infrahub_db_reference_query_*`): `floor_seconds`, `window_min_seconds`,
`stress_ratio_median`. The floor and window-min gauges aggregate across workers as `min` and the
stress ratio as `max` under a `MultiProcessCollector` (when `PROMETHEUS_MULTIPROC_DIR` is set), so
the scraped values are meaningful cross-worker figures.

## Configuration

All knobs are `INFRAHUB_API_BACKPRESSURE_*` plus `INFRAHUB_DB_MAX_CONNECTION_POOL_SIZE`; see the
[configuration reference](../../../docs/docs/reference/configuration.mdx) for names and defaults.
`backpressure_enabled` is the kill-switch (default on) and the instant rollback. The slot cap
follows from the DB pool size × the concurrency factor.

## Known limitations

- **CORS preflight** — because the middleware is outermost, a cross-origin `OPTIONS` preflight
  would be classified and could be shed under load, breaking every cross-origin request precisely
  when the backend is busy. Preflights therefore bypass the gate and reach the downstream CORS
  middleware. Only genuine preflights (`OPTIONS` with `access-control-request-method`) are
  exempt.
- **Metrics accounting on client disconnect** — `offered_total` is incremented before a request
  acquires a slot, but a client that disconnects while queued produces neither an admission nor a
  rejection. So `offered_total == admitted_total + rejected_total` holds only absent cancellations;
  expect a small standing gap under churn.

## Design record

The design and its rejected alternatives (CoDel vs a fixed threshold, ASGI middleware vs a FastAPI
dependency, per-worker vs a shared limiter) are captured in the spec at
`dev/specs/ifc-2886-priority-api-backpressure/`. The database-stress signal was added after that
spec and is documented here rather than there.
