# Phase 0 Research: Priority-aware API backpressure (server-side)

**Feature**: IFC-2886 | **Date**: 2026-07-10

All decisions below are grounded in the current Infrahub backend. File references use repo-relative paths.

## R1. Middleware integration point & style

**Decision**: Implement the admission layer as a **pure-ASGI middleware** (subclassing nothing, `async def __call__(self, scope, receive, send)`), modelled on `ConditionalGZipMiddleware` in `backend/infrahub/middleware.py`. Register it in `backend/infrahub/server.py` as the **last** `add_middleware(...)` call so it becomes the **outermost** middleware (Starlette inserts at the front of `user_middleware`; last-registered runs first).

**Rationale**:
- Shedding must happen as early as possible, before any downstream work (CORS, telemetry, routing, auth dependency). Outermost placement satisfies FR-007 ("no handler work performed") most cleanly.
- Pure ASGI avoids the well-known `BaseHTTPMiddleware` pitfalls (it buffers responses and interferes with background tasks / streaming). The `ConditionalGZipMiddleware` precedent (`middleware.py:21-42`) shows the project already uses raw-ASGI middleware for path-conditional behaviour.
- Auth in Infrahub is a **FastAPI dependency** (`Depends(get_current_user)` in `backend/infrahub/api/dependencies.py`), resolved per-route *after* all middleware. So the admission middleware runs pre-auth and can only classify origin-blind on the header — which is exactly what FR-006 mandates ("classify solely on `X-Priority`"). No auth interaction is required.

**Alternatives considered**:
- `@app.middleware("http")` decorator (used by 3 existing middlewares): rejected — it wraps `BaseHTTPMiddleware`, which fully buffers the response and is a poor fit for a hot admission path.
- A FastAPI dependency instead of middleware: rejected — dependencies run after routing/auth and per-route wiring; a middleware gives one uniform admission point across all endpoints.

**Path exclusions**: The middleware MUST bypass admission for `/health` and `/metrics` (liveness and scraping must never be shed) and SHOULD bypass static/docs paths (`/assets`, `/favicons`, `/docs`, `/api/schema`) to match the existing `ConditionalGZipMiddleware` skip set. Non-`http` scopes (WebSocket, lifespan) pass through untouched.

**CORS preflight bypass**: A CORS preflight (`OPTIONS` carrying `Access-Control-Request-Method`) MUST also bypass the gate. It carries no `X-Priority` and would classify as `normal`; shedding it under load would strip the CORS response and break every cross-origin request precisely when the backend is busy. Preflights therefore pass straight through to the downstream CORS middleware and are never counted as offered load.

## R2. Concurrency primitive — priority slot pool

**Decision**: Implement a custom async **PrioritySlotPool**: a bounded counter of `max_concurrency` slots with **one FIFO waiter queue per priority class**. On release, hand the freed slot to the highest-priority non-empty queue, FIFO within that class. Cancellation-safe: model the acquire path on CPython's `asyncio.Semaphore` (each waiter is a `Future`; on cancellation the waiter deregisters and, if it was already handed a slot in the same tick, re-releases it so no slot leaks and no waiter deadlocks).

**Rationale**:
- FR-004 (highest-priority waiter first, FIFO within class) and FR-008 (cancellation-safe, no leaked slots) cannot be met by a plain `asyncio.Semaphore` (single FIFO queue, no priority). A small purpose-built primitive is the simplest correct option (Constitution VII).
- The `asyncio.Semaphore._acquire`/`release` cancellation handling is the reference model the PRD explicitly names; replicating its "on cancel, wake the next waiter" logic per-class avoids the classic leaked-permit bug.

**Alternatives considered**:
- `asyncio.PriorityQueue` of waiters: rejected — awkward to make cancellation-safe and to guarantee within-class FIFO plus strict cross-class priority simultaneously; three explicit `collections.deque` queues (one per class) are clearer and directly testable.
- Three independent semaphores (one per class) sharing a global counter: rejected — coordinating a single shared capacity across three semaphores re-introduces the same hand-off/cancellation complexity without simplifying it.

## R3. Shedding algorithm — per-class CoDel controller

**Decision**: Implement a pure **CoDelController** state machine, one instance per priority class, with an **injected clock** (`Callable[[], float]` returning monotonic seconds). It consumes the measured **sojourn time** (how long a request waited to acquire a slot, FR-002) and decides admit/shed using the CoDel `target`/`interval` algorithm: it enters the "dropping" state only when sojourn has stayed above `target` for a full `interval`, so a burst shorter than `interval` is never shed (FR-003). A single below-`target` sample exits the dropping state (bounded recovery, SC-005).

**Rationale**:
- CoDel is the algorithm named in the PRD and is the right fit: it keys off *delay* (sojourn), self-adapts with no hand-tuned queue-length threshold (FR-009 / User Story 4), and has a well-defined recovery. The controller is a pure function of (sojourn, clock) → decision, so it is unit-testable with a fake clock and zero real sleeps (Constitution IV; the project has no `freezegun` usage and prefers injected clocks, per `backend/tests/adapters/lock/timeline.py`).
- Per-class controllers with different `target`s give the shed gradient (FR-005): `high` gets a larger effective target (via a multiplier) so it sheds last; `low` and `normal` shed first/second.

**Parameters** (classic CoDel defaults, tuned via settings — see R4):
- `target` = 5 ms (default sojourn tolerance).
- `interval` = 100 ms (window over which sojourn must stay high before dropping).
- `high` class multiplies `target` by a `high_target_multiplier` (default 4×) for extra protection.

**Alternatives considered**:
- Fixed queue-length threshold: rejected — needs per-deployment tuning, violating the "no hand-tuned limits" goal (User Story 4).
- Token bucket / leaky bucket: rejected — rate-based, not delay-based; does not react to actual capacity contention (sojourn) and needs a hand-picked rate.

## R4. Capacity derivation & settings

**Decision**:
1. Add `max_connection_pool_size: int` to `DatabaseSettings` (`backend/infrahub/config.py`, env `INFRAHUB_DB_MAX_CONNECTION_POOL_SIZE`, default `100` to match the Neo4j driver default) and pass it into the `AsyncGraphDatabase.driver(...)` call at `backend/infrahub/database/__init__.py:549`. Today the pool size is never set, so the effective size is the implicit driver default of 100 and nothing reads it back.
2. Derive per-worker `max_concurrency` from that configured pool size (FR-009). Default derivation: `max_concurrency = max_connection_pool_size` (each admitted request may hold one DB connection), optionally scaled by a `backpressure_max_concurrency_factor` (default `1.0`). No replica-aware coordination — the value is per-process.
3. Add admission settings to `ApiSettings` (`backend/infrahub/config.py`, env prefix `INFRAHUB_API_`), the natural home alongside CORS:
   - `backpressure_enabled: bool = True` — operational kill-switch (when off, the middleware passes every request straight through). Default on; does **not** change behaviour under normal load because the mechanism only sheds when the derived cap is exceeded.
   - `backpressure_codel_target_seconds: float = 0.005`
   - `backpressure_codel_interval_seconds: float = 0.1`
   - `backpressure_high_target_multiplier: float = 4.0`
   - `backpressure_backstop_max_waiters: int = 1000` — hard cap on queued waiters per class; beyond it, immediate `429` with `reason=backstop`.
   - `backpressure_retry_after_seconds: int = 1` — value for the `Retry-After` header.
   - `backpressure_max_concurrency_factor: float = 1.0`

**Rationale**:
- Deriving the cap from a real per-process signal (the Neo4j pool the process actually owns) rather than a magic constant is the literal requirement of FR-009 and keeps the layer tuning-free across deployment sizes (User Story 4).
- `ApiSettings` is the established group for API-facing config (`config.py:526`, prefix `INFRAHUB_API_`), matching `config.SETTINGS.api.<field>` access used elsewhere.
- The kill-switch is a standard operational safety for an admission layer that can reject traffic; it is an implementation-level toggle, not a new user-facing requirement, and defaults to on so the PRD's "ships inert under normal load" behaviour is preserved.

**Alternatives considered**:
- Reading `driver._pool.pool_config.max_connection_pool_size` (private neo4j internals) instead of a first-class setting: rejected — brittle dependency on driver private API; an explicit setting is testable and documented.
- Hard-coded `max_concurrency`: rejected — violates FR-009 directly.

## R5. Metrics module & `/metrics` export

**Decision**: Add `backend/infrahub/api/admission/metrics.py` with `METRIC_PREFIX = "infrahub_admission"` and module-level `prometheus_client` singletons, matching `database/metrics.py` / `graphql/metrics.py`. Because all metrics register against the default global registry and `/metrics` is served by `starlette_exporter.handle_metrics` (`server.py:222`), new module-level metrics are auto-exported with no endpoint change (FR-OBS-8).

**Metric families** (names under the `infrahub_admission_` prefix):
| FR-OBS | Metric | Type | Labels |
|--------|--------|------|--------|
| 1 | `..._offered_total` | Counter | `priority` |
| 5 | `..._admitted_total` | Counter | `priority` |
| 2 | `..._rejected_total` | Counter | `priority`, `reason` (`codel`/`backstop`) |
| 3 | `..._in_flight` | Gauge | `priority` |
| 3 | `..._waiters` | Gauge | `priority` |
| 4 | `..._sojourn_seconds` | Histogram | `priority` |
| 6 | `..._max_concurrency` | Gauge | (none) |
| 7 | `..._missing_priority_total` | Counter | (none) |

Sojourn histogram buckets follow the seconds-suffix convention with fine low-end buckets: `[0.001, 0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1, 5]`.

**Dependency note**: `prometheus_client` (0.25.0) is currently a *transitive* pin (via prefect / starlette-exporter) yet imported directly in four existing modules. Adding one more direct importer is consistent with current practice. Declaring `prometheus-client` as an explicit direct dependency in `pyproject.toml` is a low-risk improvement but is **optional** and out of the required scope; note it for review rather than treating it as a new dependency (Governance gate: not crossed).

**Rationale**: Follows the single dominant convention exactly; zero-touch export; per-worker gauges are correct because each process serves its own `/metrics`.

**Multiprocess caveat**: Under gunicorn (4 workers) each process exports its own registry; the custom `InfrahubUvicorn` worker clears `PROMETHEUS_MULTIPROC_DIR` on init. Gauges are per-process — this is acceptable and expected (the admission state is per-worker by design, FR-009/Assumptions). No aggregation is required for v1; operators read per-worker series.

## R6. 429 + Retry-After response construction

**Decision**: The middleware constructs the shed response **directly** as a Starlette `JSONResponse` (or `Response`) with `status_code=429`, a `Retry-After` header, and a body matching the existing REST/GraphQL error envelope shape from `backend/infrahub/api/exception_handlers.py` (`{"data": null, "errors": [{"message": ..., "extensions": {"code": 429}}]}`). It does **not** raise through the exception-handler path, because that handler does not set custom headers and the middleware sits outside the exception-handler scope anyway.

**Rationale**:
- FR-007 requires the shed to short-circuit before the handler; building the response in the middleware is the direct way to do that.
- Matching the existing error envelope keeps the wire contract consistent for clients. Path-based envelope selection (REST vs GraphQL) mirrors `exception_handlers.py:34-39`.

**Alternatives considered**:
- Add a `Backpressure429Error(Error)` with `HTTP_CODE = 429` and raise it: rejected for the middleware path — the registered handlers can't attach `Retry-After`, and raising from outermost ASGI middleware wouldn't hit FastAPI's handler registry. (A 429 error class may still be added for completeness/reuse but is not the shed mechanism.)

## R7. Testing strategy

**Decision** (matching `dev/guidelines/backend/testing.md` and `.agents/rules/testing-python.md`):
- **Unit** (`backend/tests/unit/api/admission/`): CoDel controller with an **injected fake clock** advanced manually (no real sleeps, no `freezegun`); slot pool priority ordering, within-class FIFO, and cancellation cleanup (no leaked slots / no deadlock) using `asyncio` primitives and event logs (à la `backend/tests/unit/test_lock.py`); capacity derivation from settings; `X-Priority` parser mapping (incl. missing/invalid → `normal`).
- **Component** (`backend/tests/component/api/`): admission middleware end-to-end against a minimal `FastAPI()` app via `fastapi.testclient.TestClient` (header classification → class; shed → `429` + `Retry-After`; handler not executed) and, for concurrency, `httpx.AsyncClient` + `httpx.ASGITransport` firing many in-flight requests to observe the shed gradient.
- **Metrics assertions**: read module-level metric objects' `.labels(...)._value.get()` deltas before/after (the one existing precedent, `test_retry_db_transaction.py:150-161`).
- **No mocking**: use injected clocks / small test adapters, never `unittest.mock` (project rule). Parametrized cases use the `name`-first dataclass pattern; `pytest.raises` uses `match=`.

**Rationale**: Deterministic concurrency tests without wall-clock flakiness are mandated (FR-003, FR-008; Constitution IV). The injected-clock + event-log patterns already exist in the repo and are the sanctioned approach.

## R8. Worker model implications

**Finding**: Production runs gunicorn with 4 uvicorn workers (`docker-compose.yml`, `serve/gunicorn_config.py`), each a separate process with its own `app`, middleware instance, slot pool, and CoDel controllers. All admission state is therefore **per-worker**, which is exactly the PRD's design ("in-process, per worker", FR-009, Assumptions — no replica-aware coordination). Aggregate capacity across workers/replicas is an operator provisioning concern, not computed by the middleware.

**Consequence for the plan**: The slot pool and controllers are instantiated once per process (at app startup / first request) and live for the process lifetime. `max_concurrency` is derived per process from that process's Neo4j pool size. No shared state, no Redis, no coordination.
