# ruff: noqa: INP001
"""
Port contracts for all Prefect client-API usage in Infrahub backend code.
Spec: ../spec.md, research: ../research.md, data model: ../data-model.md.

This module is a **plan artifact**, not a runtime module. The runtime home
for these ABCs is:
    backend/infrahub/services/adapters/prefect_client/__init__.py

The signatures here are authoritative for Phase 1; `/speckit.tasks` will
generate implementation tasks from them. Response/request types are the
real Prefect Pydantic models, re-exported from
`backend/infrahub/services/adapters/prefect_client/types.py` so consumers
never import `prefect.*` directly (FR-014, FR-015, research R-1).

Two ABCs live here:
  * `PrefectClientAdapter` — the **production port**. Every concrete Prefect
    client operation Infrahub uses. `emit_event` mirrors Prefect's native
    signature exactly (caller-providable `id: UUID | None`, returns
    `Event | None`); no test-only parameters leak into the production port.
    Production code type-hints against this class and receives
    `RealPrefectClientAdapter` via DI.
  * `PrefectClientTestAdapter(PrefectClientAdapter)` — the **test port**.
    Extends the production port with test-oriented primitives:
      - `wait_for_event(*, name=None, event_id=None, since=None, ...)`
      - `checkpoint() -> Checkpoint`  — sync watermark
      - `captured_emits()` — async context manager yielding an `EmitCapture`
    All scoping is done by Prefect's native `Event.id` (or by a `Checkpoint`
    watermark, or by an `EmitCapture` recording) — never by stamping a
    custom token into `payload`. Production code cannot reach these
    methods because it depends on the narrower port — the boundary is
    enforced by the type system, not by convention.

Concrete implementations in the runtime tree:
  * `RealPrefectClientAdapter(PrefectClientAdapter)` — production; wraps
    `prefect.client.orchestration.PrefectClient`; the only production module
    that imports `prefect.*`.
  * `RealPrefectClientTestAdapter(RealPrefectClientAdapter, PrefectClientTestAdapter)`
    — real adapter for tests; inherits every production operation from
    `RealPrefectClientAdapter`; adds `wait_for_event` as a bounded polling
    loop (server-side filter on `EventFilter.id` / `EventFilter.event` /
    `EventFilter.occurred`). Implements `checkpoint()` with a wall-clock
    watermark and `captured_emits()` by intercepting its own `emit_event`.
  * `InMemoryPrefectClientTestAdapter(PrefectClientTestAdapter)` — in-memory
    test adapter; implements every production operation against an in-memory
    event log + seed registry + call log; implements `wait_for_event` via
    condition-variable observation of the log (no polling); `checkpoint()`
    captures the log index; `captured_emits()` records every emission.
    Additionally exposes in-memory-specific concrete helpers (`seed_return`,
    `recorded`, `call_count`, `recorded_calls`, `unused_seeds`, `reset`)
    that are **not** on any ABC — no real Prefect backend can deliver them.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import StrEnum
from typing import TYPE_CHECKING
from uuid import UUID  # noqa: TC003  # used at runtime in method signatures

if TYPE_CHECKING:
    from contextlib import AbstractAsyncContextManager
    from datetime import datetime

    # Re-exported Prefect types; in the runtime module these imports live
    # in `prefect_client/types.py`.
    from prefect.automations import AutomationCore
    from prefect.client.schemas.actions import (
        DeploymentScheduleCreate,
        WorkPoolCreate,
    )
    from prefect.client.schemas.filters import DeploymentFilter, FlowRunFilter
    from prefect.client.schemas.objects import (
        FlowRun,
        Log,
        State,
        WorkPool,
    )
    from prefect.client.schemas.responses import DeploymentResponse
    from prefect.client.schemas.sorting import FlowRunSort
    from prefect.events.filters import EventFilter
    from prefect.events.schemas.automations import Automation
    from prefect.events.schemas.events import Event


# --------------------------------------------------------------------------
# Adapter-owned exceptions
# --------------------------------------------------------------------------


class EventNotObservedReason(StrEnum):
    """Why `wait_for_event` gave up.

    Values are strings (StrEnum) so the enum serialises directly in error
    messages, logs, and test diagnostics without an explicit `.value`
    hop — while still carrying a concrete type.
    """

    NOT_EMITTED = "not_emitted"
    """The adapter observed no matching event in its visible window.

    Definitive for the in-memory test adapter: if its in-memory log has no
    entry matching the wait criteria (`name`, `event_id`, `since`) by the
    timeout, no such event was emitted during this test.
    """

    NOT_OBSERVABLE = "not_observable"
    """The wait timed out while the event may have been emitted but not
    yet indexed by Prefect's events pipeline.

    Default for the real test adapter: Prefect's events API is eventually
    consistent, so timing out at the real adapter does not prove the
    event was never emitted — only that it was not queryable within the
    bound.
    """


class EventNotObservedError(Exception):
    """Raised by `wait_for_event` when the bounded timeout elapses."""

    def __init__(
        self,
        *,
        name: str | None,
        event_id: UUID | None,
        elapsed_seconds: float,
        reason: EventNotObservedReason,
    ) -> None:
        self.name = name
        self.event_id = event_id
        self.elapsed_seconds = elapsed_seconds
        self.reason = reason
        criteria = f"name={name!r}" if name is not None else f"event_id={event_id}"
        super().__init__(f"Event ({criteria}) not observed after {elapsed_seconds:.2f}s (reason={reason})")


# --------------------------------------------------------------------------
# Test-port helper types: Checkpoint + EmitCapture
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class Checkpoint:
    """Opaque watermark created by `PrefectClientTestAdapter.checkpoint()`.

    Pass to `wait_for_event(since=...)` to scope the search to events
    emitted after this point. Internal representation differs by adapter:
    `InMemoryPrefectClientTestAdapter` records a log index;
    `RealPrefectClientTestAdapter` records a wall-clock timestamp. Treat
    as opaque — only pass back to the same adapter instance that produced
    it.
    """

    _log_index: int | None = None
    _occurred: datetime | None = None


@dataclass
class EmitCapture:
    """Recording of every event emitted within a `captured_emits()` block.

    Tests use the captured ids/events for strict per-emission matching:

        async with adapter.captured_emits() as cap:
            await production_code()
        event = await adapter.wait_for_event(event_id=cap.only(name="X").id)

    The `events` list is appended to in the order emits happen. Helper
    accessors (`ids`, `last`, `last_id`, `by_name`, `only`) are convenience
    wrappers around that list.
    """

    events: list[Event] = field(default_factory=list)

    @property
    def ids(self) -> list[UUID]:
        return [e.id for e in self.events]

    @property
    def last(self) -> Event:
        if not self.events:
            raise AssertionError("captured_emits: no events emitted in this block")
        return self.events[-1]

    @property
    def last_id(self) -> UUID:
        return self.last.id

    def by_name(self, name: str) -> list[Event]:
        return [e for e in self.events if e.event == name]

    def only(self, *, name: str | None = None) -> Event:
        """Assert exactly one matching event was captured; return it.

        Fails with `AssertionError` if zero or more than one event matches.
        Use this when the test expects a single emission of the named
        event during the captured block.
        """
        candidates = self.events if name is None else self.by_name(name)
        if len(candidates) != 1:
            criteria = f"name={name!r}" if name is not None else "any"
            raise AssertionError(f"captured_emits.only({criteria}): expected 1 event, got {len(candidates)}")
        return candidates[0]


# --------------------------------------------------------------------------
# Production port
# --------------------------------------------------------------------------


class PrefectClientAdapter(ABC):
    """Production port for every Prefect client operation Infrahub uses.

    This is what production code type-hints against. Method names mirror
    Prefect operations (FR-020). `emit_event` mirrors Prefect's native
    signature exactly so the production port stays free of test-only
    concepts. Test-only primitives (`wait_for_event`, `checkpoint`,
    `captured_emits`, FR-018 additions) are **not** on this ABC — they
    live on the `PrefectClientTestAdapter` subclass so the type system,
    not convention, keeps production code from calling them.
    """

    # ---- Automations -----------------------------------------------------

    @abstractmethod
    async def create_automation(self, *, automation: AutomationCore) -> UUID: ...

    @abstractmethod
    async def update_automation(self, *, automation_id: UUID, automation: AutomationCore) -> None: ...

    @abstractmethod
    async def delete_automation(self, *, automation_id: UUID) -> None: ...

    @abstractmethod
    async def read_automations_by_name(self, *, name: str) -> list[Automation]: ...

    @abstractmethod
    async def read_automations(self) -> list[Automation]: ...

    # ---- Deployments -----------------------------------------------------

    @abstractmethod
    async def read_deployment_by_name(self, *, name: str) -> DeploymentResponse | None: ...

    @abstractmethod
    async def read_deployments(self, *, filter: DeploymentFilter | None = None) -> list[DeploymentResponse]: ...

    @abstractmethod
    async def run_deployment(
        self,
        *,
        name: str,
        parameters: dict | None = None,
        tags: list[str] | None = None,
        schedule: DeploymentScheduleCreate | None = None,
    ) -> FlowRun: ...

    # ---- Events ----------------------------------------------------------

    @abstractmethod
    async def emit_event(
        self,
        *,
        event: str,
        resource: dict,
        related: list[dict] | None = None,
        payload: dict | None = None,
        id: UUID | None = None,
    ) -> Event | None:
        """Emit a Prefect event. Wraps `prefect.events.emit_event`.

        Mirrors Prefect's native signature exactly:
          * `id: UUID | None` — the sender-provided event id; defaults to
            a fresh UUID (Prefect's own behavior).
          * Returns the emitted `Event` (with `Event.id`), or `None` when
            Prefect's `should_emit_events()` is `False` — same return
            contract as `prefect.events.emit_event`.

        Production callers that don't care about the returned event simply
        ignore the return value. Tests that need the id can either capture
        it from the return (`event = await adapter.emit_event(...)`) or
        pre-mint a UUID and pass it as `id=...`. Tests that exercise
        production code paths (where the production code is the thing
        calling `emit_event`) use `PrefectClientTestAdapter.captured_emits()`
        to harvest the ids without modifying production signatures.
        """

    @abstractmethod
    async def filter_events(self, *, filter: EventFilter, limit: int | None = None) -> list[Event]: ...

    @abstractmethod
    async def count_events(self, *, filter: EventFilter) -> int: ...

    # ---- Flow runs -------------------------------------------------------

    @abstractmethod
    async def read_flow_run(self, *, flow_run_id: UUID) -> FlowRun: ...

    @abstractmethod
    async def read_flow_runs(
        self,
        *,
        filter: FlowRunFilter | None = None,
        sort: FlowRunSort | None = None,
        limit: int | None = None,
    ) -> list[FlowRun]: ...

    @abstractmethod
    async def set_flow_run_state(self, *, flow_run_id: UUID, state: State) -> None: ...

    @abstractmethod
    async def read_flow_run_logs(self, *, flow_run_id: UUID, limit: int | None = None) -> list[Log]: ...

    # ---- Work pools ------------------------------------------------------

    @abstractmethod
    async def read_work_pools(self) -> list[WorkPool]: ...

    @abstractmethod
    async def read_work_pool(self, *, name: str) -> WorkPool: ...

    @abstractmethod
    async def create_work_pool(self, *, work_pool: WorkPoolCreate) -> WorkPool: ...


# --------------------------------------------------------------------------
# Test port
# --------------------------------------------------------------------------


class PrefectClientTestAdapter(PrefectClientAdapter):
    """Test port. Extends the production port with test-oriented primitives.

    Three test-only primitives in v1:
      * `checkpoint()` — sync watermark for "wait for events emitted after
        this point".
      * `captured_emits()` — async context manager that records every event
        emitted within its scope, exposing them as an `EmitCapture` for
        strict per-emission matching by `Event.id`.
      * `wait_for_event()` — bounded async wait keyed on Prefect's native
        `Event.id` (preferred) or by `name` + `since` (when an id is not
        available).

    Implementations:
      * `RealPrefectClientTestAdapter` — inherits the production real impl
        and adds a bounded polling loop for `wait_for_event` that uses
        Prefect's `EventFilter(id=EventIDFilter(...), event=EventNameFilter(...),
        occurred=EventOccurredFilter(...))` for server-side filtering.
        `checkpoint()` records a wall-clock timestamp; `captured_emits()`
        intercepts its own `emit_event`.
      * `InMemoryPrefectClientTestAdapter` — in-memory implementation of the
        production port plus a condition-variable fast path for
        `wait_for_event`. `checkpoint()` records the log length;
        `captured_emits()` appends every emission to all active captures.
        Also exposes in-memory-specific concrete helpers (`seed_return`,
        `recorded`, `call_count`, `recorded_calls`, `unused_seeds`, `reset`)
        that are not on any ABC.

    Production code type-hints against `PrefectClientAdapter`, not this class,
    so production callers cannot reach `wait_for_event`, `checkpoint`, or
    `captured_emits`.
    """

    @abstractmethod
    def checkpoint(self) -> Checkpoint:
        """Record a watermark at the current point in time.

        Sync (no I/O): in-memory captures the log length; real captures the
        wall-clock instant. Pass the returned `Checkpoint` to
        `wait_for_event(since=...)` to scope the search to events emitted
        after this point. Cheaper alternative to `captured_emits()` when
        the test only needs "wait for the next event of this name after
        the action" rather than per-emission id capture.
        """

    @abstractmethod
    def captured_emits(self) -> AbstractAsyncContextManager[EmitCapture]:
        """Async context manager that records every event emitted in scope.

        Usage::

            async with adapter.captured_emits() as cap:
                await production_code_that_emits()

            event = await adapter.wait_for_event(event_id=cap.last_id)
            # or, for strict 1:1:
            event = await adapter.wait_for_event(
                event_id=cap.only(name="infrahub.node.created").id,
            )

        Multiple `captured_emits()` blocks may be active at once (nested or
        in parallel async tasks); every emission is appended to every
        active capture. Each capture holds its own `EmitCapture` instance,
        so blocks see a clean, independent recording.
        """

    @abstractmethod
    async def wait_for_event(
        self,
        *,
        name: str | None = None,
        event_id: UUID | None = None,
        since: Checkpoint | None = None,
        timeout_seconds: float = 10.0,
    ) -> Event:
        """Block until a matching event is observable.

        At least one of `name` or `event_id` must be supplied.

        Matching semantics:
          * `event_id` — preferred. Globally unique (Prefect's native
            `Event.id`); no watermark needed because the id resolves at
            most one event ever. Server-side filterable on the real
            adapter via `EventFilter(id=EventIDFilter(id=[event_id]))`.
          * `name` — match by event name. Combine with `since=` to scope
            to events emitted after a checkpoint, or with the per-test
            adapter-instance scope on the in-memory adapter (its log is
            fresh per test by FR-010, so cross-test bleed is impossible).
          * `name` + `event_id` — both must match (rarely needed; prefer
            id alone).
          * `since` — narrows to events emitted after the checkpoint.

        In-memory test adapter: returns as soon as the criteria are met
        against its in-memory log (resolved via an `asyncio.Event`/condition
        variable signalled by every `emit_event`; no polling latency).

        Real test adapter: polls Prefect's `POST /events/filter` at a
        bounded interval (default 250 ms → ~40 polls per default 10 s
        timeout) using the corresponding fields on `EventFilter`. All
        filtering is server-side.

        Raises `EventNotObservedError` at timeout. Scoped per-test by
        construction (FR-009, FR-010): the in-memory adapter's log is
        per-instance; the real adapter requires `since` (or `event_id`)
        to scope to the test's emissions.
        """
