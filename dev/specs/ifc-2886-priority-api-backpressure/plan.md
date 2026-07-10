# Implementation Plan: Priority-aware API backpressure (server-side)

**Branch**: `dga/feat-rate-limiting-api-zb38x` | **Date**: 2026-07-10 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `specs/ifc-2886-priority-api-backpressure/spec.md` (Jira IFC-2886)

## Summary

Add a per-worker, in-process **admission layer** to Infrahub's FastAPI backend that sheds load by priority. Requests declare priority via an `X-Priority` header (`high`/`normal`/`low`, default `normal`). A **priority slot pool** bounds concurrent in-handler requests to a `max_concurrency` derived from the process's own Neo4j connection-pool size; the time a request waits for a slot (**sojourn**) feeds a **per-class CoDel controller** that adaptively sheds — `low` first, `normal` next, `high` last. Shed requests get a fast `429 + Retry-After` with no handler work. Per-class Prometheus metrics are exported on the existing `/metrics` endpoint. No database schema, GraphQL, or persistence change; no new hard dependency.

Technical approach (from research): pure-ASGI middleware registered outermost in `server.py`; custom cancellation-safe `PrioritySlotPool`; pure `CoDelController` with an injected clock; capacity derived from a new `INFRAHUB_DB_MAX_CONNECTION_POOL_SIZE` setting; admission tuning knobs on `ApiSettings`; a new `infrahub_admission_*` metrics module on the default Prometheus registry.

## Technical Context

**Language/Version**: Python 3.14 (backend)

**Primary Dependencies**: FastAPI 0.131 / Starlette (ASGI middleware), `prometheus_client` 0.25 (already imported directly in-tree; transitive pin), Neo4j async driver 6.2, Pydantic 2.12 / pydantic-settings. No new hard dependency (CoDel + slot pool are custom, stdlib `asyncio`/`collections`/`time.monotonic`).

**Storage**: N/A — the admission layer is fully in-memory, per worker process. No persistence, no schema, no migration.

**Testing**: pytest 9 with `pytest-asyncio` in `asyncio_mode = "auto"`; no mocking (adapter/injected-clock pattern); unit + component tiers. Deterministic concurrency tests via injected fake clock and asyncio event logs.

**Target Platform**: Linux server; gunicorn + 4 uvicorn workers in production (`serve/gunicorn_config.py`), single-process uvicorn in dev.

**Project Type**: Web-service backend (single backend project; frontend untouched in this feature).

**Performance Goals** (from Success Criteria): under sustained overload, `high` shed rate ~= 0% while `low`/`normal` absorb shedding (SC-002); sub-`interval` bursts shed zero (SC-003); shed path does no handler work and returns immediately (SC-004); shedding self-terminates within a bounded window after overload ends (SC-005). SC-001 headline latency bound is discovery-measured.

**Constraints**: The admission decision is on the hot path of every request — it MUST be cheap (a header read, a slot acquire attempt, a CoDel evaluation) and MUST NOT block liveness/scrape paths (`/health`, `/metrics`). Per-worker only; no cross-process/replica coordination.

**Scale/Scope**: 3 priority classes; per-worker `max_concurrency` typically = Neo4j pool size (default 100); 4 workers/process default; ~7 new source modules + settings edits; 8 metric families.

## Constitution Check

*GATE: evaluated pre-Phase 0 and re-checked post-design.*

| Principle | Assessment |
|-----------|------------|
| **I. Schema-Driven Integrity** | N/A — no schema, node, or generated-file change. |
| **II. Branch-Safe by Default** | N/A — admission is transport-layer, pre-routing; it performs no DB reads/writes and touches no branch/temporal data. |
| **III. Type Safety & Explicit Contracts** | PASS — Full type hints; `str \| None` style; frozen dataclasses for internal state (priority enum, CoDel state, decisions); Pydantic settings at the config boundary. The `X-Priority` header + `429` contract are documented in `contracts/` before implementation. |
| **IV. Test Discipline** | PASS — Unit tests (CoDel fake-clock, slot-pool ordering/cancellation, capacity derivation, parser) written alongside implementation; component tests for the middleware end-to-end + metrics. No mocking — injected clock/adapters. |
| **V. Query Performance & Efficiency** | PASS — Directly serves this principle: protects contended API/Neo4j capacity under load. No new queries; the added `max_connection_pool_size` setting only makes an existing implicit default explicit. |
| **VI. Security & Input Boundaries** | PARTIAL/ACCEPTED — `X-Priority` is untrusted client input. v1 accepts a cooperative first-party trust model (any caller may claim `high`); enforcement is explicitly deferred (spec Out of Scope). The parser validates/normalizes the header (invalid → `normal`) so malformed input cannot crash the path. No auth logic changes. Flagged as a borderline governance gate. |
| **VII. Simplicity & Maintainability** | PASS — Per-worker, coordination-free (no Redis/global limiter) — the deliberately simple choice. Custom primitives are small and single-purpose; no new dependency; follows existing `metrics.py`/`ApiSettings`/ASGI-middleware patterns. |

**Governance gates crossed** (require review heads-up, no redesign):
- API / public interface change — new `X-Priority` request header + `429 + Retry-After` behaviour across endpoints.
- Authentication / authorization change (borderline) — middleware sits in the admission path and consumes a client-controlled header; no auth logic changed.
- Database settings change — a new **setting** (`max_connection_pool_size`) is added and passed to the driver; this is a config addition, **not** a DB schema/migration change. Per AGENTS.md "Ask First" on DB config: called out explicitly; default (100) preserves current driver behaviour exactly.

No unjustified violations → **Constitution Check PASSES**. Complexity Tracking table not required.

## Project Structure

### Documentation (this feature)

```text
specs/ifc-2886-priority-api-backpressure/
├── spec.md              # Specify phase output
├── plan.md              # This file
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 output
├── quickstart.md        # Phase 1 output
├── contracts/           # Phase 1 output
│   ├── x-priority-header.md
│   └── metrics.md
├── checklists/
│   └── requirements.md
└── tasks.md             # Phase 2 output (/speckit-tasks — not created here)
```

### Source Code (repository root)

```text
backend/infrahub/
├── api/
│   └── admission/               # NEW package — the admission layer
│       ├── __init__.py
│       ├── priority.py          # Priority enum + X-Priority header parser (FR-006)
│       ├── slot_pool.py         # PrioritySlotPool: per-class FIFO queues, priority release, cancellation-safe (FR-001, FR-004, FR-008)
│       ├── codel.py             # CoDelController: pure per-class state machine, injected clock (FR-002, FR-003, FR-005)
│       ├── capacity.py          # max_concurrency derivation from Neo4j pool size (FR-009)
│       ├── controller.py        # AdmissionController: wires slot pool + per-class CoDel + backstop; admit/shed decision (FR-005, FR-007)
│       ├── metrics.py           # infrahub_admission_* Prometheus families (FR-OBS-1..8)
│       └── middleware.py        # AdmissionMiddleware (pure ASGI): parse → decide → serve or 429+Retry-After
├── config.py                    # EDIT: DatabaseSettings.max_connection_pool_size; ApiSettings backpressure_* knobs
├── database/__init__.py         # EDIT: pass max_connection_pool_size into AsyncGraphDatabase.driver(...) (~line 549)
└── server.py                    # EDIT: register AdmissionMiddleware outermost (last add_middleware, ~line 205)

backend/tests/
├── unit/api/admission/
│   ├── test_priority.py         # header → class mapping incl. missing/invalid → normal
│   ├── test_codel.py            # fake-clock: sub-interval burst = 0 drops; gradient; bounded recovery
│   ├── test_slot_pool.py        # priority ordering, within-class FIFO, cancellation cleanup / no leak / no deadlock
│   └── test_capacity.py         # derivation from settings, no magic number
└── component/api/
    └── test_admission_middleware.py  # end-to-end: classification, 429+Retry-After, no handler work, metrics increment, shed gradient
```

**Structure Decision**: A dedicated `backend/infrahub/api/admission/` package holds all new code (substantial and cohesive), following the repo convention of a per-subsystem package with its own `metrics.py`. Only three existing files are edited (`config.py`, `database/__init__.py`, `server.py`), each a minimal additive change. Tests mirror source under `backend/tests/unit/api/admission/` and `backend/tests/component/api/`.

## Design Notes (Phase 1 summary)

- **Request flow** (per worker): request enters `AdmissionMiddleware` (outermost) → skip-path check (`/health`, `/metrics`, static/docs) → parse `X-Priority` → `AdmissionController.admit(priority)`:
  1. If the backstop cap for the class is already exceeded → `429 reason=backstop` immediately (no slot attempt).
  2. Else attempt to acquire a slot from `PrioritySlotPool`, measuring sojourn.
  3. Feed sojourn to the class's `CoDelController`; if it decides to drop → release the slot, `429 reason=codel`.
  4. Else admit: run the downstream app inside the slot; release the slot in a `finally` (FR-008).
- **Handoff on release**: a freed slot goes to the highest-priority non-empty waiter queue, FIFO within class (FR-004).
- **Cancellation**: if a queued waiter is cancelled (client disconnect), it deregisters; if it had just been handed a slot in the same tick, the slot is re-released to the next waiter (no leak, no deadlock) — mirrors `asyncio.Semaphore`.
- **Inert-by-default**: with no caller sending `X-Priority`, everything is `normal`; under normal load nothing is shed (SC-006). The `backpressure_enabled` kill-switch bypasses the layer entirely when off.
- Data structures, fields, and state transitions are detailed in [data-model.md](./data-model.md); external contracts in [contracts/](./contracts/).

## Complexity Tracking

No constitution violations requiring justification. (Table intentionally omitted.)
