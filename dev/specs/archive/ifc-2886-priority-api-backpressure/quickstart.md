# Quickstart & Validation: Priority-aware API backpressure

**Feature**: IFC-2886 | This guide proves the feature works end-to-end. It references [contracts/](./contracts/) and [data-model.md](./data-model.md) rather than restating them. Implementation code lives in tasks.md / the implementation phase, not here.

## Prerequisites

- Backend deps installed: `uv sync --all-groups`
- Working from repo root.

## 1. Unit tests (deterministic, no services, seconds to run)

```bash
uv run pytest backend/tests/unit/api/admission/ -q
```

Expected — all pass:
- **CoDel** (`test_codel.py`, fake clock): a burst shorter than `interval` yields **zero** drops (SC-003/FR-003); sustained above-`target` sojourn enters dropping after one `interval`; a single below-`target` sample exits dropping (SC-005); `high` (target × multiplier) drops later than `normal`/`low` given the same sojourn (FR-005).
- **Slot pool** (`test_slot_pool.py`): a freed slot goes to the highest-priority waiter, FIFO within a class (FR-004); a cancelled queued waiter leaks no slot and does not deadlock (FR-008); `_available + in_flight` accounting holds.
- **Capacity** (`test_capacity.py`): `max_concurrency` derives from `max_connection_pool_size × factor` with no hard-coded constant (FR-009).
- **Parser** (`test_priority.py`): `high/normal/low` map correctly; missing/empty/invalid → `normal` and flagged non-explicit (FR-006/FR-OBS-7).

## 2. Component test — middleware end-to-end

```bash
uv run pytest backend/tests/component/api/test_admission_middleware.py -q
```

Validates against a minimal `FastAPI()` app (via `TestClient` / `httpx.AsyncClient` + `ASGITransport`):
- **Classification** — a request's `X-Priority` selects its class; no header → `normal` and served (C-1, C-2).
- **Shed shape** — a forced shed returns `429` with a `Retry-After` header and the handler body never ran (C-3, SC-004, FR-007).
- **Excluded paths** — `/health` and `/metrics` are never shed (C-6).
- **Metrics** — `infrahub_admission_offered_total`, `_admitted_total`, `_rejected_total{reason}`, `_in_flight`, `_waiters`, `_sojourn_seconds`, `_max_concurrency`, `_missing_priority_total` increment as specified; the M-1 accounting invariant holds (`offered == admitted + rejected`).
- **Gradient** — under a saturating `low` stream + interactive `high` stream, `high` admits throughout while `low` absorbs the sheds (C-4, SC-002).

## 3. Manual smoke test against a running instance

Start a dev server (single-process uvicorn):

```bash
uv run infrahub server start   # or the project's dev entrypoint
```

Confirm the layer is inert under normal load (SC-006):

```bash
# No X-Priority — treated as normal, served normally
curl -s -o /dev/null -w '%{http_code}\n' http://localhost:8000/api/schema/summary

# Explicit high — served
curl -s -o /dev/null -w '%{http_code}\n' -H 'X-Priority: high' http://localhost:8000/api/schema/summary
```

Both return `200` on an unloaded instance.

Inspect the new metric families:

```bash
curl -s http://localhost:8000/metrics | grep infrahub_admission_
```

Expect to see the eight families from [contracts/metrics.md](./contracts/metrics.md), including `infrahub_admission_max_concurrency` (a positive number equal to the derived cap) and `infrahub_admission_offered_total{priority="normal"}` incrementing as you send traffic.

## 4. Overload / gradient demonstration (SC-001, SC-002)

Lower the cap to make overload easy to reach on a laptop, then drive mixed load:

```bash
# Make the cap small so contention is trivial to induce
export INFRAHUB_DB_MAX_CONNECTION_POOL_SIZE=4
export INFRAHUB_API_BACKPRESSURE_CODEL_TARGET_SECONDS=0.005
export INFRAHUB_API_BACKPRESSURE_CODEL_INTERVAL_SECONDS=0.1
# restart the server so the derived max_concurrency picks these up
```

Drive a saturating `low` background stream plus a steady `high` interactive stream (any load tool; e.g. two parallel loops of `curl` with `-H 'X-Priority: low'` and `-H 'X-Priority: high'`, or a small `httpx` script). Then scrape `/metrics` and confirm:

- `infrahub_admission_rejected_total{priority="low"}` climbs while `infrahub_admission_rejected_total{priority="high"}` stays ≈ 0 (SC-002).
- `infrahub_admission_sojourn_seconds` P99 for `high` stays low relative to `low` (the gradient; SC-001 is quantified from this measurement).
- After stopping the `low` stream, `rejected_total` stops climbing within a bounded window and all classes serve again (SC-005).

## 5. Kill-switch

```bash
export INFRAHUB_API_BACKPRESSURE_ENABLED=false   # restart
```

With the switch off, every request passes straight through (no admission, no `429`, metrics static) — the safe rollback.

## Success signals (map to spec Success Criteria)

| Signal | Criterion |
|--------|-----------|
| Unit suite green (fake-clock CoDel, slot-pool, capacity, parser) | FR-002/003/004/006/008/009 |
| `429 + Retry-After`, handler not run | SC-004 / FR-007 |
| `high` ≈0% shed, `low` first, `normal` second under overload | SC-002 / FR-005 |
| Sub-`interval` burst → zero sheds | SC-003 / FR-003 |
| Shedding self-terminates after overload | SC-005 |
| Eight `infrahub_admission_*` families present, M-1 holds | FR-OBS-1..8 |
| Inert on default deployment | SC-006 |
