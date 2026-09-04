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
| `middleware.py` | `AdmissionMiddleware`, the pure-ASGI gate, outermost but for CORS |
| `controller.py` | `AdmissionController`, the admit/shed decision |
| `factory.py` | `build_admission_controller`, the settings-reading wiring of the object graph |
| `slot_pool.py` | `PrioritySlotPool`, bounded concurrency with per-class FIFO waiter queues |
| `codel.py` | `CoDelController`, the pure CoDel state machine |
| `capacity.py` | `derive_max_concurrency`, the slot-cap derivation |
| `priority.py` | the `Priority` enum and `X-Priority` header parsing |
| `constants.py` | the `RejectionReason` enum, which doubles as the `reason` metric label |
| `retry_policy.py` | `RetryAfterPolicy`, the adaptive `Retry-After` computation |
| `metrics.py` | the `infrahub_admission_*` Prometheus families |
| `observers.py` | the sinks that publish the live gauges |

The database-stress signal it consumes lives in `backend/infrahub/database/load_signal.py`, with its
metrics sink in `load_signal_metrics.py` and the process-global instance in `load_signal_registry.py`.

## Where metrics attach

Four components feed metrics: the admission controller, the slot pool, the retry policy, and the
stress tracker. None of them imports a metrics module. Each takes `observers` as a required
constructor argument and *pushes* values to them — decision events, counts, a duration, the derived
signal — so a sink never reads back into the component it observes.

`AdmissionObserver` is one interface with four events (`on_offered`, `on_admitted`, `on_rejected`,
`on_sojourn`) rather than one interface per metric: they describe a single request's passage through
one decision, so a sink implements them together. Separate interfaces belong to separate components,
which is why the pool, the policy, and the tracker each have their own.

The events are named methods rather than a callable protocol, so a sink can carry several of them
and each one says which event fired. Each component confines its fan-out to sinks behind private
methods where the per-observer failure containment also lives — a single `_notify` in the slot
pool, the retry policy, and the load tracker, and one `_observe_*` method per event in the
admission controller.

The concrete sinks in `observers.py` are named only where the object graph is wired: `server.py`
passes them to `build_admission_controller`, which takes them as arguments rather than choosing them,
and `load_signal_registry` wires the tracker's. Nothing under `api/admission/` outside that entry
point imports them, which is what keeps the sinks out of the primitives' import chain and makes every
gauge visible at the point of construction.

Observer failures are contained per observer, so one broken sink can neither skip the sinks behind
it, corrupt admission state, shed a request that would have been admitted, nor fail the database
query that fed an observation.

The one metric still incremented outside a sink is `missing_priority_total`, in `middleware.py`
where the header is parsed.

This is the worked example of two general rules — collaborators arrive through the constructor
rather than a later registration call, and a `Protocol` keeps an out-of-domain dependency out of the
logic's import chain. Both, and when to apply them elsewhere, are in
[Backend Component Design](../../../.agents/rules/backend-component-design.md).

## The request path

`AdmissionMiddleware` is registered **second to last** in `server.py`, so Starlette runs it first
after CORS. Load is shed before any downstream work — auth, routing, DB — runs. A shed request is
answered with a `429` error envelope carrying `Retry-After` and never reaches the app.

Only `InfrahubCORSMiddleware` sits outside it, and it has to: a shed response that skips CORS
carries no `Access-Control-Allow-Origin`, so a cross-origin browser blocks it outright and the
client sees an opaque network error rather than a `429` it can act on. `Retry-After` is not a
CORS-safelisted response header either, so `cors_expose_headers` (default `retry-after`) is what
lets a browser read the advised wait. CORS costs header handling and no I/O, so a shed request
still pays nothing that matters.

Pass-through cases that bypass admission entirely:

- Non-`http` scopes (WebSocket, lifespan).
- The kill-switch: when `backpressure_enabled` is false, every request passes through.
- Excluded paths — liveness/scrape/probe/static/docs: `/health`, `/metrics`, `/api/config`,
  `/assets`, `/favicons`, `/docs`, `/api/schema`. Liveness, scraping, and the config probe must
  never be shed.
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

## The `Retry-After` hint

<!-- Extracted from specs/ifc-2886-priority-api-backpressure on 2026-07-26 -->

Every shed response carries a `Retry-After`, computed by `RetryAfterPolicy` (`retry_policy.py`) on
two axes and clamped to a maximum kept below the SDK's per-retry cap so first-party clients honour
it verbatim.

- **Intensity** — the same `stress_tier(ratio, threshold)` primitive that drives the graduated shed
  fraction returns `0/1/2/3` at `1×/2×/5×` of the class's own trigger, and the tier maps to a
  configured base (`1s`/`5s`/`10s`). Because the trigger is per class, the advised wait tracks the
  class. A backstop shed is treated as the top tier; any shed floors at level 1.
- **Persistence** — a per-worker episode clock counts how long the stress ratio has *continuously*
  stayed at or above a significant-load line (default `20.0`). Ratios below it are a warm-up zone
  that never accrues time. The base is multiplied by `×1/×2/×3` as the episode passes `0/60s/300s`.

A single static value was tried first and failed: the SDK honours `Retry-After` verbatim, so a
fixed `1s` overrode its exponential backoff and collapsed a bounded retry budget to a few seconds —
background work *failed* under sustained load instead of being merely deprioritised. See
[ADR 0007](../../adr/0007-adaptive-retry-after-under-load.md).

## Metrics

All on the existing `/metrics` endpoint.

Admission (`infrahub_admission_*`): `offered_total`, `admitted_total`,
`rejected_total{priority,reason}` (reason is `stress`, `codel`, or `backstop`), `in_flight`,
`waiters`, `sojourn_seconds`, `max_concurrency`, `missing_priority_total` (adoption tracking),
`sustained_load_seconds` (how long this worker has continuously been at or above the
significant-load ratio — the exact signal driving `Retry-After` escalation, so it can be graphed
and alerted on).

Stress signal (`infrahub_db_reference_query_*`): `floor_seconds`, `window_min_seconds`,
`stress_ratio_median`. The floor and window-min gauges aggregate across workers as `min` and the
stress ratio as `max` under a `MultiProcessCollector` (when `PROMETHEUS_MULTIPROC_DIR` is set), so
the scraped values are meaningful cross-worker figures.

## Configuration

All knobs are `INFRAHUB_API_BACKPRESSURE_*` plus `INFRAHUB_DB_MAX_CONNECTION_POOL_SIZE`; see the
[configuration reference](../../../docs/docs/reference/configuration.mdx) for names and defaults.
`backpressure_enabled` is the kill-switch (default on) and the instant rollback. The slot cap
follows from the DB pool size × the concurrency factor. The `Retry-After` knobs are the per-tier
bases, the clamp, the significant-load ratio, and the two sustained-load thresholds.

## Why it's built this way

<!-- Extracted from specs/ifc-2886-priority-api-backpressure on 2026-07-26 -->

The two decisions that are hard to walk back — client-declared priority and per-worker,
coordination-free capacity — have their own ADRs (see [Design record](#design-record)). The
choices below are rationale rather than constraint: each is swappable behind `AdmissionController`
without disturbing the rest of the layer, and this section exists so a future change knows what
was already ruled out.

**Pure-ASGI middleware, registered outermost but for CORS.** Shedding must happen before any
downstream work — telemetry, routing, and the auth dependency all cost something, and a shed
request should cost none of it. CORS is the one exception, because a shed response that never
passes back through it is unreadable to a cross-origin browser. Auth in Infrahub is a FastAPI dependency resolved per route, well after
middleware, which is *why* the gate can only classify on the header: nothing else is known yet.
The alternatives were a `@app.middleware("http")` decorator, rejected because it wraps
`BaseHTTPMiddleware`, which buffers the whole response and interferes with streaming and
background tasks — a poor fit for a hot admission path; and a FastAPI dependency, rejected because
it runs after routing and needs per-route wiring instead of one uniform admission point.

**The `429` is built in the middleware, not raised.** Registered exception handlers cannot attach
`Retry-After`, and the gate sits outside the exception-handler scope anyway. The
middleware constructs the response directly, matching the existing error envelope so the wire
contract stays consistent.

**Delay-based (CoDel) shedding, not a queue-length threshold.** CoDel keys off how long requests
actually wait, which is the thing that hurts, and it self-adapts with no per-deployment number to
pick. A fixed queue-length threshold was rejected precisely because it needs that number. Token or
leaky buckets were rejected as rate-based: they cap throughput at a hand-picked rate rather than
reacting to real capacity contention, so they shed while the server is idle and admit while it
drowns.

**A purpose-built slot pool, not a semaphore.** `asyncio.Semaphore` has a single FIFO queue and no
notion of class, so it cannot hand a freed slot to the highest-priority waiter. An
`asyncio.PriorityQueue` of waiters was rejected as awkward to make cancellation-safe while also
guaranteeing within-class FIFO; three semaphores over a shared counter re-introduce the same
hand-off and cancellation complexity without simplifying anything. Three explicit deques — one per
class — are clearer and directly testable, with the cancellation path modelled on CPython's
`asyncio.Semaphore` so a cancelled waiter cannot leak a slot or deadlock the pool.

## Known limitations

- **CORS preflight** — a cross-origin `OPTIONS` preflight carries no `X-Priority`, so were it
  classified it could be shed under load, breaking every cross-origin request precisely when the
  backend is busy. CORS now answers preflights before the gate sees them, but the exemption is
  kept so the guarantee does not rest on middleware ordering. Only genuine preflights (`OPTIONS`
  with `access-control-request-method`) are exempt.
- **Metrics accounting on client disconnect** — `offered_total` is incremented before a request
  acquires a slot, but a client that disconnects while queued produces neither an admission nor a
  rejection. So `offered_total == admitted_total + rejected_total` holds only absent cancellations;
  expect a small standing gap under churn.

## Design record

- [ADR 0007](../../adr/0007-adaptive-retry-after-under-load.md) — adaptive `Retry-After`.
- [ADR 0008](../../adr/0008-client-declared-request-priority.md) — why the caller declares
  priority and why the claim is trusted.
- [ADR 0009](../../adr/0009-per-worker-coordination-free-admission.md) — why capacity is
  per-worker and derived from the DB pool.

The originating spec is archived at
`dev/specs/archive/ifc-2886-priority-api-backpressure/`. The database-stress signal was added
after that spec and is documented here rather than there.
