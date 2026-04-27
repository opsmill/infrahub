# Phase 1 Data Model: Prefect Client Port & Adapter

This document enumerates the entities that cross the port boundary (request/response shapes) and the in-memory test adapter's internal state. Production code never sees any raw `prefect` type except through the re-exports listed here.

---

## Entities crossing the port (request/response types)

All re-exported from `backend/infrahub/services/adapters/prefect_client/types.py`. Production callers import from there, never from `prefect.*`.

| Entity | Source | Crosses port as |
|---|---|---|
| `Automation` | `prefect.events.schemas.automations.Automation` | response |
| `AutomationCore` | `prefect.automations.AutomationCore` | request |
| `EventTrigger` | `prefect.events.schemas.automations.EventTrigger` | part of `AutomationCore` |
| `Posture` | `prefect.events.schemas.automations.Posture` | part of `AutomationCore` |
| `ResourceSpecification` | `prefect.events.schemas.events.ResourceSpecification` | part of `AutomationCore` and `Event` |
| `DeploymentResponse` | `prefect.client.schemas.responses.DeploymentResponse` | response |
| `DeploymentFilter` | `prefect.client.schemas.filters.DeploymentFilter` | request |
| `DeploymentScheduleCreate` | `prefect.client.schemas.actions.DeploymentScheduleCreate` | request |
| `FlowRun` | `prefect.client.schemas.objects.FlowRun` | response |
| `FlowRunFilter` | `prefect.client.schemas.filters.FlowRunFilter` | request |
| `FlowRunSort` | `prefect.client.schemas.sorting.FlowRunSort` | request |
| `State` | `prefect.client.schemas.objects.State` | request + response (flow-run state transitions) |
| `StateType` | `prefect.client.schemas.objects.StateType` | part of `State` |
| `Log` | `prefect.client.schemas.objects.Log` | response |
| `Event` | `prefect.events.schemas.events.Event` | request (emit) + response (filter/wait) |
| `EventFilter` | `prefect.events.filters.EventFilter` | request |
| `EventNameFilter` | `prefect.events.filters.EventNameFilter` | part of `EventFilter` |
| `EventIDFilter` | `prefect.events.filters.EventIDFilter` | part of `EventFilter` |
| `EventOccurredFilter` | `prefect.events.filters.EventOccurredFilter` | part of `EventFilter` |
| `Resource` | `prefect.events.schemas.events.Resource` | part of `Event` |
| `RelatedResource` | `prefect.events.schemas.events.RelatedResource` | part of `Event` |
| `WorkPool` | `prefect.client.schemas.objects.WorkPool` | response |
| `WorkPoolCreate` | `prefect.client.schemas.actions.WorkPoolCreate` | request |
| `ConcurrencyLimitStrategy` | `prefect.client.schemas.objects.ConcurrencyLimitStrategy` | part of deployment schedule |
| `CronSchedule` | `prefect.client.schemas.schedules.CronSchedule` | part of deployment schedule |
| `ChangeFlowRunState` | Prefect automation-action type (exact import path confirmed during T004) | request — trigger model |
| `RunDeployment` | Prefect automation-action type (exact import path confirmed during T004) | request — trigger model |

All of these are Pydantic v2 models already, so validation at the port boundary (R-7) is free.

### Identity and uniqueness

- `Automation.id`, `FlowRun.id`, `Event.id`, `DeploymentResponse.id`, `WorkPool.id` — `uuid.UUID`
- Uniqueness for automations within a name: `read_automations_by_name(name)` may return multiple; callers de-duplicate by id.
- Flow-run state transitions follow Prefect's state machine (`Pending → Scheduled → Running → Completed`/`Failed`/`Crashed`/`Cancelled`); the in-memory test adapter does **not** enforce these transitions in v1 (FR-017). A programmable stateful test adapter that models them is deferred to FR-018.

---

## Adapter-owned entities (not re-exports)

Defined in `backend/infrahub/services/adapters/prefect_client/__init__.py` (ABCs + exception types) and `backend/infrahub/services/adapters/prefect_client/_testing.py` (test-only concretes).

### `PrefectClientAdapter` (ABC — the production port)

- Abstract. See `contracts/prefect_client_adapter.py` for the full signature.
- 18 concrete Prefect client operations (automations, deployments, events emit/filter/count, flow runs, work pools).
- What production code type-hints against. Does not include `wait_for_event`.

### `PrefectClientTestAdapter(PrefectClientAdapter)` (ABC — the test port)

- Abstract. See `contracts/prefect_client_adapter.py` for the full signature.
- Extends the production port with test-oriented primitives. v1 adds three:
  - `checkpoint() -> Checkpoint` — sync watermark; pair with `wait_for_event(since=...)` for the simple "next event after my action" case.
  - `captured_emits() -> AbstractAsyncContextManager[EmitCapture]` — async context manager that records every emission inside its scope; pair with `wait_for_event(event_id=cap.only(name=...).id)` for strict per-emission matching.
  - `wait_for_event(*, name=None, event_id=None, since=None, timeout_seconds=10.0) -> Event` — bounded async wait keyed on Prefect's native `Event.id` (preferred), or by `name` + `since=` checkpoint.
- FR-018 additions (controllable clock, injectable errors, callbacks) land here later.
- Test code type-hints against this class; production code does not. The type system enforces the boundary.

### `RealPrefectClientAdapter(PrefectClientAdapter)`

- Production real implementation. Lives in `prefect_client/real.py`.
- Wraps `prefect.client.orchestration.PrefectClient` and `prefect.events.emit_event`; the only production module permitted to import from `prefect.*` (per FR-014/FR-015 + R-1 whitelist).
- No test capabilities — no `wait_for_event`, no recorder helpers.

### `RealPrefectClientTestAdapter(RealPrefectClientAdapter, PrefectClientTestAdapter)`

- Real-backed test implementation. Lives in `prefect_client/_testing.py`.
- Inherits every production operation from `RealPrefectClientAdapter`.
- Implements `wait_for_event` as a bounded polling loop (default 250 ms interval, 10 s total timeout) over `filter_events` with **server-side filtering only** via Prefect's `EventFilter(id=EventIDFilter(...), event=EventNameFilter(...), occurred=EventOccurredFilter(since=since.occurred))` after narrowing `since` with `isinstance(since, _OccurredCheckpoint)` (research R-6).
- Implements `checkpoint()` by returning `_OccurredCheckpoint(occurred=datetime.now(UTC))` (no I/O).
- Implements `captured_emits()` by overriding the inherited `emit_event` to forward to Prefect, then appending the returned `Event` to every active capture in `self._captures`.
- Used by the integration-lane contract tests (`backend/tests/integration/prefect_client/`) and by functional tests that need a live Prefect server (e.g., `test_thread_events` after migration).

### `InMemoryPrefectClientTestAdapter(PrefectClientTestAdapter)`

- In-memory test implementation. Lives in `prefect_client/_testing.py`.
- Implements every production operation against in-memory state (event log, call log).
- Implements `wait_for_event` via an `asyncio.Event`/condition variable signalled by every `emit_event` — no polling, no latency.
- Implements `checkpoint()` by returning `_LogIndexCheckpoint(log_index=len(self._emit_log))` — events at index `≥ log_index` were emitted after the checkpoint.
- Implements `captured_emits()` by appending every `Event` returned from `emit_event` to all `EmitCapture` instances currently registered on `self._captures`.
- Additionally exposes in-memory-specific concrete helpers (`recorded`, `call_count`, `recorded_calls`, `reset`) that are **not** on any ABC — no real backend can deliver them.
- Usable without Docker, a Prefect server, or network (FR-023).
- Reset per test via the fixture in `backend/tests/helpers/prefect_client.py` (FR-010).

### `EventNotObservedReason(StrEnum)`

Value class for the `reason` field on `EventNotObservedError`. `StrEnum` (Python 3.11+) so instances serialise as their string value in logs and test diagnostics without an explicit `.value`.

- `NOT_EMITTED = "not_emitted"` — the adapter observed no event matching the wait criteria (`name`, `event_id`, `since`) in its visible window. Definitive for `InMemoryPrefectClientTestAdapter`.
- `NOT_OBSERVABLE = "not_observable"` — the wait timed out while the event may have been emitted but not yet indexed by Prefect's events pipeline. Default for the real adapter.

### `EventNotObservedError(Exception)`

Raised by `wait_for_event` when the bounded timeout elapses.

- `name: str | None` — the event name being waited on (when matching by name)
- `event_id: UUID | None` — Prefect's native event id being waited on (when matching by id)
- `elapsed_seconds: float` — wall-clock wait time
- `reason: EventNotObservedReason` — where the wait bottomed out. `InMemoryPrefectClientTestAdapter` always raises with `EventNotObservedReason.NOT_EMITTED`; `RealPrefectClientTestAdapter` raises with `EventNotObservedReason.NOT_OBSERVABLE` by default and may distinguish via a `count_events` check before timeout (deferred).

### `Checkpoint`

Sealed base class returned by `PrefectClientTestAdapter.checkpoint()`. Opaque to callers — only pass it back to `wait_for_event(since=...)` on the same adapter instance that produced it.

The base class is empty; each adapter has its own frozen subtype with a single mandatory field:

- `_LogIndexCheckpoint(log_index: int)` — produced by `InMemoryPrefectClientTestAdapter`; `log_index = len(self._emit_log)` at checkpoint time.
- `_OccurredCheckpoint(occurred: datetime)` — produced by `RealPrefectClientTestAdapter`; `occurred = datetime.now(UTC)` at checkpoint time.

Subtypes are adapter-internal (leading underscore); only the base `Checkpoint` is re-exported from `prefect_client/types.py`. `wait_for_event` narrows the `since` argument with `isinstance` and raises `TypeError` (naming both adapter classes) if it receives a checkpoint subtype produced by the wrong adapter — a single guard replacing the prior "exactly one of two `| None` fields is populated" invariant.

### `EmitCapture`

Mutable dataclass yielded by the `PrefectClientTestAdapter.captured_emits()` async context manager. Records every `Event` emitted within the `async with` block.

- `events: list[Event]` — the recorded events, in emission order.
- Properties: `ids -> list[UUID]`, `last -> Event` (raises if empty), `last_id -> UUID`.
- Methods: `by_name(name: str) -> list[Event]`, `only(*, name: str | None = None) -> Event` (asserts exactly one match; raises with diagnostic on 0 or >1).

The capture object is alive only inside the context block; tests typically read from it after the block exits to feed an `event_id` into `wait_for_event`.

### `wait_for_event` signature and timeout default

- `wait_for_event(*, name: str | None = None, event_id: UUID | None = None, since: Checkpoint | None = None, timeout_seconds: float = 10.0) -> Event` — at least one of `name` or `event_id` must be supplied. The default timeout is 10 seconds (bounded per FR-008), expressed directly on the method signature rather than via a separate type alias. Callers override by passing `timeout_seconds=`.

---

## In-memory test adapter internal state

Held on instances of `InMemoryPrefectClientTestAdapter`. Reset per test (FR-010) via the helper in `backend/tests/helpers/prefect_client.py`.

### `RecordedCall`

Frozen dataclass. Contains everything needed to make assertions on interactions. Stored per-instance on `InMemoryPrefectClientTestAdapter`.

- `method: str` — the adapter method name (e.g., `"create_automation"`)
- `args: tuple[Any, ...]` — positional args (typically empty; all adapter methods are keyword-only)
- `kwargs: Mapping[str, Any]` — keyword args, validated against the method signature at entry
- `sequence: int` — monotonically increasing per-instance, used to assert invocation order
- `result: Any | None` — the value returned to the caller (re-exported Prefect type)
- `error: BaseException | None` — raised if the call failed

### `ObservedEvent`

Append-only per-test log. `InMemoryPrefectClientTestAdapter.emit_event` constructs and appends an `Event` (the real Prefect `Event` Pydantic model — FR-005); its `wait_for_event` reads. The list is the same list whose length `checkpoint()` records and whose new entries `captured_emits()` mirrors. Each entry is the full Prefect `Event` (carrying `id: UUID`, `event: str`, `resource: dict`, `payload: dict`, `occurred: datetime`, etc.) — no parallel custom record is kept.

### Invariants

- Every call into `InMemoryPrefectClientTestAdapter` validates kwargs against the declared signature using `pydantic.TypeAdapter(arg_type).validate_python(value)` before appending to the call log. A validation failure raises a descriptive `AssertionError` with the method name, argument name, and mismatch (SC-003).
- The call log preserves insertion order; assertions against it may slice by method or by `sequence` range.
- The event log is per-instance; tests that share a class-scoped adapter via the fixture wrapper still get per-test isolation because the fixture rebuilds the in-memory test adapter at function scope (FR-010).

---

## Migration touchpoint entities

These don't cross the port but are worth naming because the migration changes their surface:

- **`InfrahubEventService._send_prefect`** — currently calls `prefect.events.emit_event` directly; migrates to `self.prefect_client.emit_event(...)`. Its signature to callers is unchanged.
- **`backend/tests/helpers/events.query_events_by_name`** — current polling helper; superseded by `PrefectClientTestAdapter.wait_for_event` and removed after migration.
- **`backend/tests/helpers/test_app.TestInfrahubAppBase.assert_event`** — superseded by `PrefectClientTestAdapter.wait_for_event`; deleted after migration (this eliminates the 30-second polling loop referenced in Story 2).
