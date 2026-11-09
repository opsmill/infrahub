# Data Model: Priority-aware API backpressure (server-side)

**Feature**: IFC-2886 | **Date**: 2026-07-10

All entities are **in-memory, per worker process**. Nothing is persisted; there is no database schema, node, or migration. "Data model" here means the internal runtime state objects and their transitions.

## Entity: Priority (class enum)

- **What it is**: The three admission priority classes.
- **Representation**: `IntEnum` where a lower value = higher priority, so numeric ordering gives priority ordering.
  - `HIGH = 0`, `NORMAL = 1`, `LOW = 2`.
- **Header wire values**: `"high"` → `HIGH`, `"normal"` → `NORMAL`, `"low"` → `LOW`.
- **Validation** (FR-006): case-insensitive match on the trimmed header value; **any** missing, empty, or unrecognized value → `NORMAL`. Parsing never raises.
- **Label value**: `.name.lower()` is used as the Prometheus `priority` label (`high`/`normal`/`low`).

## Entity: PriorityHeaderParseResult

- **What it is**: The outcome of parsing the `X-Priority` header, kept distinct from `Priority` so the middleware can record adoption (FR-OBS-7) without a second parse.
- **Fields** (frozen dataclass):
  - `priority: Priority` — resolved class (never null; defaults to `NORMAL`).
  - `was_explicit: bool` — `True` iff a valid `high`/`normal`/`low` value was present. `False` for missing/empty/invalid.
- **Use**: when `was_explicit` is `False`, increment `infrahub_admission_missing_priority_total`.

## Entity: CoDelController (per class)

- **What it is**: A pure CoDel state machine deciding admit vs shed from observed sojourn. One instance per `Priority`. Deterministic given its injected clock.
- **Construction inputs**:
  - `target: float` (seconds) — sojourn tolerance. For `HIGH`, the effective target is `base_target * high_target_multiplier`.
  - `interval: float` (seconds) — window sojourn must exceed `target` before dropping begins.
  - `clock: Callable[[], float]` — injected monotonic clock (defaults to `time.monotonic`; tests pass a fake).
- **State fields** (mutable, private):
  - `dropping: bool` — whether currently in the dropping state.
  - `first_above_time: float | None` — timestamp when sojourn first went above `target` in the current excursion (`None` when below target).
  - `drop_next: float` — scheduled time of the next drop while dropping.
  - `count: int` — drops in the current dropping episode (controls the CoDel inverse-sqrt cadence).
  - `last_count: int` — count carried across episodes for fast re-entry.
- **Operation** `should_drop(sojourn: float) -> bool`:
  - If `sojourn < target` (or the pool is idle): reset `first_above_time = None`, leave/expire the dropping state, return `False`.
  - If sojourn has been above `target` continuously for ≥ `interval`: enter/continue `dropping` and return `True` on the CoDel drop schedule (`now >= drop_next`), spacing drops by `interval / sqrt(count)`.
  - A burst shorter than `interval` never reaches the drop condition → returns `False` throughout (FR-003, SC-003).
  - Exit: a single sample with `sojourn < target` clears `dropping` (bounded recovery, SC-005).
- **Invariants**: pure function of (sojourn samples, clock); no wall-clock reads except via `clock`; no I/O. Thread-confined to the worker's event loop.

## Entity: PrioritySlotPool

- **What it is**: A bounded concurrency primitive with per-class FIFO waiter queues and priority-ordered hand-off. Cancellation-safe. One instance per worker.
- **Fields**:
  - `max_concurrency: int` — total slots (derived; see Capacity).
  - `_available: int` — free slots (starts at `max_concurrency`).
  - `_waiters: dict[Priority, deque[Future]]` — one FIFO queue per class.
  - `_in_flight: dict[Priority, int]` — admitted-and-running count per class (for FR-OBS-3).
- **Operation** `acquire(priority) -> Acquisition`:
  - Fast path: if `_available > 0`, decrement, record sojourn = 0, return an `Acquisition`.
  - Slow path: create a `Future`, append to `_waiters[priority]`, record enqueue time from the clock, `await` it. On wake, sojourn = `clock() - enqueue_time`.
  - Cancellation (FR-008): on `CancelledError`, remove the waiter from its deque; if the waiter had already been handed a slot in the same tick (future resolved but not yet consumed), re-release that slot to the next eligible waiter. Never leak a slot; never deadlock.
- **Operation** `release()`:
  - Choose the highest-priority non-empty queue (`HIGH` → `NORMAL` → `LOW`); pop its **oldest** waiter (within-class FIFO, FR-004) and resolve its future (hand off the slot).
  - If all queues empty, increment `_available`.
- **`Acquisition`** (context-manager / handle): carries `priority` and measured `sojourn`; its `release()` returns the slot in a `finally` (FR-008). Increments/decrements `_in_flight[priority]`.
- **Invariants**: `0 <= _available <= max_concurrency`; `_available + sum(_in_flight) + <handed-off-not-yet-consumed> == max_concurrency` at rest; a freed slot always reaches the highest-priority waiter first.

## Entity: AdmissionController

- **What it is**: The composition object that turns a `Priority` into an admit/shed decision. Wires the slot pool, the three CoDel controllers, and the backstop. One instance per worker.
- **Fields**:
  - `slot_pool: PrioritySlotPool`
  - `codel: dict[Priority, CoDelController]`
  - `backstop_max_waiters: int`
  - `metrics` handle (module-level Prometheus objects).
- **Operation** `admit(priority) -> AdmissionDecision`:
  1. `offered_total{priority}` += 1.
  2. Backstop: if `len(slot_pool._waiters[priority]) >= backstop_max_waiters` → `Rejected(reason="backstop")`, `rejected_total{priority,backstop}` += 1.
  3. `acquire(priority)`; observe `sojourn_seconds{priority}`.
  4. `codel[priority].should_drop(sojourn)`? → release slot, `Rejected(reason="codel")`, `rejected_total{priority,codel}` += 1.
  5. Else `Admitted(acquisition)`, `admitted_total{priority}` += 1, `in_flight{priority}` set from pool.
- **`AdmissionDecision`** (frozen): a tagged union — `Admitted(acquisition: Acquisition)` or `Rejected(reason: Literal["codel","backstop"], retry_after: int)`.

## Entity: Capacity derivation

- **What it is**: Pure function `derive_max_concurrency(pool_size: int, factor: float) -> int` returning `max(1, int(pool_size * factor))`.
- **Inputs**: `pool_size = config.SETTINGS.database.max_connection_pool_size` (new setting, default 100); `factor = config.SETTINGS.api.backpressure_max_concurrency_factor` (default 1.0).
- **Output**: the `max_concurrency` passed to `PrioritySlotPool` and exported via `infrahub_admission_max_concurrency` (FR-OBS-6). No magic constant (FR-009).

## Configuration additions (Pydantic settings)

**`DatabaseSettings`** (`INFRAHUB_DB_` prefix):
| Field | Type | Default | Notes |
|-------|------|---------|-------|
| `max_connection_pool_size` | `int` (ge=1) | `100` | Matches Neo4j driver default; now explicit and passed into `AsyncGraphDatabase.driver(...)`. |

**`ApiSettings`** (`INFRAHUB_API_` prefix):
| Field | Type | Default | Notes |
|-------|------|---------|-------|
| `backpressure_enabled` | `bool` | `True` | Kill-switch; off = pass every request through. |
| `backpressure_codel_target_seconds` | `float` (gt=0) | `0.005` | CoDel target sojourn. |
| `backpressure_codel_interval_seconds` | `float` (gt=0) | `0.1` | CoDel interval. |
| `backpressure_high_target_multiplier` | `float` (ge=1) | `4.0` | `HIGH` target = target × this (extra protection, FR-005). |
| `backpressure_backstop_max_waiters` | `int` (ge=1) | `1000` | Per-class hard waiter cap → `reason=backstop`. |
| `backpressure_retry_after_seconds` | `int` (ge=0) | `1` | `Retry-After` header value. |
| `backpressure_max_concurrency_factor` | `float` (gt=0) | `1.0` | Scales derived cap. |

## State transition summary (per request)

```text
REQUEST
  → skip-path? ──yes──▶ PASS THROUGH (no admission)
  → disabled?  ──yes──▶ PASS THROUGH
  → parse X-Priority ─▶ Priority (default NORMAL); record adoption
  → backstop full? ──yes──▶ 429 (reason=backstop)
  → acquire slot (measure sojourn)
        └─ cancelled (disconnect) ─▶ deregister, re-release if handed, END (no leak)
  → CoDel should_drop(sojourn)? ──yes──▶ release slot ─▶ 429 (reason=codel)
  → ADMIT: run downstream app inside slot
  → finally: release slot ─▶ hand to highest-priority waiter (FIFO in class)
```
