# Phase 0 Research: Prefect Client Port & Adapter

All `NEEDS CLARIFICATION` items in the Technical Context resolved below. Each research item follows the format **Decision / Rationale / Alternatives**.

---

## R-1 — Boundary refinement: what exactly does "no `import prefect` outside the adapter" mean?

**Decision.** The boundary in FR-015 applies only to the Prefect **client-API** surface. The **runtime-decorator surface** — `@flow`, `@task`, `get_run_logger`, `flow_run` context, `cache_policies`, `Completed`/`Failed` state constructors used inside flows, and `Flow`/`Task` type imports used for typing task signatures — is **not** wrapped and is not subject to the ban. These decorators *are* the runtime; code that uses them is task code that runs under Prefect, not code that calls Prefect to do something.

The ruff `flake8-tidy-imports.banned-api` rule will ban:

- `prefect.client.*`
- `prefect.events.*` (except `prefect.events.emit_event` — see migration path)
- `prefect.automations.*`
- `prefect.server.*`
- `prefect.blocks.*`
- `prefect.states.*` (when imported outside of a `@flow`/`@task` module)
- `prefect.exceptions.*`

It will **not** ban:

- `from prefect import flow, task, get_run_logger, Flow, Task, State`
- `from prefect.cache_policies import NONE`
- `from prefect.logging import get_run_logger`
- `from prefect.runtime import flow_run`
- `from prefect.testing import prefect_test_harness` (tests only)

**Rationale.** The audit (R-2) shows 172 `prefect` imports across 70 files. Most are the decorator/runtime surface. Wrapping those would produce a meaningless abstraction: you cannot make `@flow` into an adapter method without re-implementing Prefect's task runtime. The spec's intent (IFC-2499, the recap) is clearly about the **client API** — `PrefectClient`, `emit_event`, automation CRUD, deployment runs, flow-run queries — where wrapping has real value (SDK churn insulation, contract tests, fake substitution). The original FR-015 wording was too broad; this research pins the scope.

**Alternatives considered.**

- *Ban all `prefect` imports uniformly.* Rejected: forces wrapping the decorator runtime, which is ~80 files of zero-value churn and loses type-checker support on `@task` return types.
- *Ban on a per-module basis only when that module migrates.* Rejected: the constitutional principle VII and the recap both call for a global boundary check in CI so new code doesn't re-introduce violations. The whitelist approach delivers both: strict global ban with a small, explicit whitelist for the runtime surface.

---

## R-2 — Concrete Prefect client surface used by production code

**Decision.** The v1 `PrefectClientAdapter` interface covers the following operations, derived from grepping `backend/infrahub/` for direct Prefect client API usage:

### Automations

- `create_automation(automation: AutomationCore) -> UUID`
- `update_automation(automation_id: UUID, automation: AutomationCore) -> None`
- `delete_automation(automation_id: UUID) -> None`
- `read_automations_by_name(name: str) -> list[Automation]`
- `read_automations() -> list[Automation]`

Callers: `backend/infrahub/trigger/setup.py`, `backend/infrahub/webhook/models.py`, `backend/infrahub/webhook/tasks/configure.py`.

### Deployments

- `read_deployment_by_name(name: str) -> DeploymentResponse | None`
- `read_deployments(filter: DeploymentFilter | None = None) -> list[DeploymentResponse]`
- `run_deployment(name: str, parameters: dict, ...) -> FlowRun`

Callers: `backend/infrahub/trigger/setup.py`, `backend/infrahub/workflows/utils.py`, `backend/infrahub/workflows/initialization.py`. Note overlap with existing `InfrahubWorkflow.execute_workflow`: the adapter owns the Prefect-layer call; the workflow adapter continues to own the Infrahub-layer dispatch semantics.

### Events

- `emit_event(*, event: str, resource: dict, related: list[dict] | None = None, payload: dict | None = None, id: UUID | None = None) -> Event | None` — mirrors `prefect.events.emit_event` exactly (caller-providable id; returns the emitted `Event` or `None` when emission is gated off)
- `filter_events(filter: EventFilter, limit: int | None = None) -> list[Event]`
- `count_events(filter: EventFilter) -> int`
- `wait_for_event(*, name: str | None = None, event_id: UUID | None = None, since: Checkpoint | None = None, timeout_seconds: float = 10.0) -> Event` — test-only (lives on `PrefectClientTestAdapter`); deterministic (FR-008, R-6). Companion test-port helpers: `checkpoint() -> Checkpoint` (sync watermark) and `captured_emits() -> AbstractAsyncContextManager[EmitCapture]` (async context manager).

Callers: `backend/infrahub/services/adapters/event/__init__.py` (emission), `backend/infrahub/task_manager/event.py` (filter/count), and `backend/tests/helpers/events.py` (test helper, superseded by the adapter).

### Flow runs

- `read_flow_run(flow_run_id: UUID) -> FlowRun`
- `read_flow_runs(filter: FlowRunFilter | None = None, sort: FlowRunSort | None = None) -> list[FlowRun]`
- `set_flow_run_state(flow_run_id: UUID, state: State) -> None`
- `read_flow_run_logs(flow_run_id: UUID, limit: int | None = None) -> list[Log]`

Callers: `backend/infrahub/task_manager/task.py`, `backend/infrahub/task_manager/event.py`.

### Work pools

- `read_work_pools() -> list[WorkPool]`
- `read_work_pool(name: str) -> WorkPool`
- `create_work_pool(work_pool: WorkPoolCreate) -> WorkPool`

Callers: `backend/infrahub/workflows/initialization.py`. Work queues are explicitly out of scope for v1 per FR-019 (no production caller).

**Rationale.** FR-019 requires coverage of "every Prefect surface currently imported from `prefect` in production code". Grepping for client-API invocations (not runtime imports per R-1) yields the list above. Each item maps to an existing production caller, so no method is speculative. Response and request types (`Automation`, `AutomationCore`, `DeploymentResponse`, `FlowRun`, `Event`, `State`, `Log`, `WorkPool`, etc.) are re-exported from `backend/infrahub/services/adapters/prefect_client/types.py` so consumers don't need to import `prefect` directly.

**Alternatives considered.**

- *Wrap only `PrefectClient` (skip events).* Rejected: events is exactly where Story 2 lives, and the wait primitive is a core feature of this adapter.
- *Define only the coarsest operations (e.g., `dispatch`) and hide CRUD details.* Rejected: contract tests need method-level parity; coarsening hides the contract.
- *Include `prefect.blocks.redis` / `prefect.workers.base` used in `backend/infrahub/workers/base.py`.* Rejected: those are Prefect **worker** framework extensions (custom worker type registration), same class as `@flow`/`@task` runtime per R-1. Kept in the whitelist, not wrapped.

---

## R-3 — Adapter module structure, naming, and port split

**Decision.** Create `backend/infrahub/services/adapters/prefect_client/` with two ABCs (a production port and a test port extending it) and three concrete classes, organised as follows:

```text
prefect_client/
├── __init__.py     # PrefectClientAdapter        (production port, ABC — 18 ops)
│                   # PrefectClientTestAdapter    (test port, ABC — extends with wait_for_event
│                   #                              in v1; FR-018 additions later)
│                   # EventNotObservedError       (exception)
│                   # EventNotObservedReason      (StrEnum)
├── real.py         # RealPrefectClientAdapter    (production; wraps PrefectClient)
├── _testing.py     # RealPrefectClientTestAdapter      (inherits real production + test port;
│                   #                                    adds polling wait_for_event)
│                   # InMemoryPrefectClientTestAdapter  (in-memory production ops + test port;
│                   #                                    condition-variable wait_for_event;
│                   #                                    carries recorder helpers)
└── types.py        # Re-exports of Prefect response/request types
```

Class names:
- Production port: `PrefectClientAdapter`
- Test port: `PrefectClientTestAdapter`
- Production real impl: `RealPrefectClientAdapter`
- Real-backed test impl: `RealPrefectClientTestAdapter`
- In-memory test impl: `InMemoryPrefectClientTestAdapter` (formerly "Fake"; retired that naming in favour of a name that says what it is)

**Rationale — why two ports.** Test-oriented primitives (`wait_for_event` today; FR-018's controllable clock, injectable errors, callbacks later) are patterns that do not belong in production call paths. Polling for events with bounded timeout is a test pattern — Prefect's native production pattern for "react to event X" is automations (event trigger → action), not application-code polling. If these primitives sit on the same ABC that production depends on, the only thing keeping production code from calling them is convention or a lint rule. Splitting into a production port (`PrefectClientAdapter`) and a test port (`PrefectClientTestAdapter(PrefectClientAdapter)`) makes the boundary a **type-system invariant**: production code hints `PrefectClientAdapter` and literally cannot reach `wait_for_event`. No ruff rule needed, no drift possible.

**Rationale — why three concretes, not two.** With a single port, v1 had two concretes (real + fake). With the split, the test port needs an implementation that works against real Prefect (for integration contract tests + functional tests like `test_thread_events`) and one that works in memory (for unit contract tests + migrated unit tests). `RealPrefectClientTestAdapter` is a clean inheritance of `RealPrefectClientAdapter` (IS-A relationship; reuses every production op for free) that only has to implement `wait_for_event` itself. `InMemoryPrefectClientTestAdapter` stands alone — it implements the production ops in memory and the test ops against the same in-memory log, one cohesive object. Composition-over-inheritance was considered and rejected: the decorator-over-inner approach would have added 18 delegation stubs on the real side for zero benefit, and would have split the in-memory state from the test adapter that owns it.

**Rationale — why `_testing.py`, not a separate package.** The test-only concretes shadow the production `real.py`: a Prefect upgrade changes both together. Keeping them colocated means one import path per class of concern and one grep turns up every place that Prefect client code lives. The underscore prefix on `_testing.py` signals "not for production imports" — production code that tries `from .prefect_client._testing import ...` is a review smell that stands out. (Complemented by the ruff `banned-api` whitelist, which already forbids production code from reaching into anything outside the adapter's production-facing modules.)

**Rationale — directory convention.** Infrahub already owns a `services/adapters/` convention with siblings `workflow/` (has `local.py` + `worker.py`), `event/`, `message_bus/`, `cache/`, and `http/`. Following that directory shape satisfies Principle VII ("Follow established project patterns"). Naming mirrors the existing `InfrahubWorkflow` abstract base; the `Real*` / `*TestAdapter` pattern sits cleanly next to the `local.py` / `worker.py` split in `workflow/`, preserving review legibility.

**Alternatives considered.**

- *Single ABC, rename `wait_for_event` to `testing_wait_for_event` + ban-api rule.* Rejected: convention/lint-enforced boundary vs type-system-enforced boundary — the latter is stronger, has no drift risk, and doesn't add a lint rule we'd need to maintain.
- *Composition decorator (`PrefectClientTestAdapter(inner: PrefectClientAdapter)`).* Rejected: forces 18 delegation stubs on the real side, awkward two-object handling on the in-memory side (fake fixture must yield both the wrapper and the inner fake so tests can still call `seed_return`), and gains only marginal flexibility over inheritance for a class with a stable surface.
- *Place at `backend/infrahub/prefect/` or `backend/infrahub/adapters/prefect/`.* Rejected: breaks the existing `services/adapters/` convention.
- *Name the port `InfrahubPrefectService` (matching `InfrahubEventService`).* Rejected: this is structurally an *adapter* (matches `InfrahubWorkflow`, `InfrahubMessageBus`), not a composite domain service.

---

## R-4 — Boundary enforcement in CI

**Decision.** Use ruff `flake8-tidy-imports.banned-api` to forbid `prefect.client.*`, `prefect.events.*` (minus `emit_event` transitionally), `prefect.automations`, `prefect.server.*`, `prefect.blocks.*`, and `prefect.exceptions` outside the whitelist. The whitelist is expressed via ruff `per-file-ignores` keyed on:

- `backend/infrahub/services/adapters/prefect_client/real.py`
- `backend/infrahub/services/adapters/prefect_client/types.py`
- `backend/tests/integration/conftest.py` (already imports `prefect.testing.prefect_test_harness` to expose the existing `prefect_test_fixture` used by `backend/tests/integration/prefect_client/conftest.py`)
- `backend/tests/functional/conftest.py` (already imports `prefect.testing.prefect_test_harness` to expose the `prefect_test_fixture` used by `backend/tests/functional/proposed_change/test_thread_events.py` and other functional tests)

The runtime-decorator surface (R-1) is not a `banned-api` target, so it needs no whitelist.

**Rationale.** Ruff is already configured with `select = ["ALL"]` and is the project's Python lint tool (per `AGENTS.md`). `banned-api` provides the exact semantics required (ban specific modules globally with per-file overrides), is evaluated in CI via `uv run invoke lint`, and carries no new dependency. `import-linter` would work but adds a dependency for a single-purpose rule.

**Alternatives considered.**

- *`import-linter` (a.k.a. `importlinter`).* Rejected: extra dependency for one rule; ruff covers the same need.
- *Custom git pre-commit or bash grep script.* Rejected: not integrated with the existing lint gate; easy to bypass.
- *`tach`.* Rejected: heavier-weight boundary tool for a single adapter isolation rule.

---

## R-5 — Contract test structure

**Decision.** Assertions are authored **exactly once** in a shared helpers module and invoked from two thin test packages — one per CI lane, one per test-adapter implementation. Helpers type-hint against `PrefectClientTestAdapter` so they can exercise `wait_for_event`; the two lanes supply different concretes. The split is by directory, not by pytest marker, because `backend/tests/integration/` already maps 1:1 to the integration CI job and already provides `prefect_test_fixture` via its `conftest.py`.

```
backend/tests/helpers/prefect_client_contracts.py
    # One `async def assert_<behavior>(adapter: PrefectClientTestAdapter) -> None`
    # per contract case. The file contains no pytest functions and no fixtures — it
    # is plain async helpers, so it is trivially importable from either lane.

backend/tests/unit/prefect_client/
├── conftest.py                 # re-exposes the function-scoped
│                               # in_memory_prefect_test_adapter fixture from
│                               # backend/tests/helpers/prefect_client.py —
│                               # yields a fresh InMemoryPrefectClientTestAdapter
│                               # per test (FR-010).
├── test_automations.py         # test_<name>(in_memory_prefect_test_adapter):
│                               #     await assert_<name>(in_memory_prefect_test_adapter)
├── test_deployments.py
├── test_events.py
├── test_flow_runs.py
└── test_work_pools.py

backend/tests/integration/prefect_client/
├── conftest.py                 # real_prefect_test_adapter fixture built on the
│                               # existing `prefect_test_fixture` from
│                               # backend/tests/integration/conftest.py; constructs
│                               # a RealPrefectClientTestAdapter; errors loudly if
│                               # that fixture is unavailable (SC-012).
├── test_automations.py         # test_<name>(real_prefect_test_adapter):
│                               #     await assert_<name>(real_prefect_test_adapter)
├── test_deployments.py
├── test_events.py
├── test_flow_runs.py
└── test_work_pools.py
```

CI selects lanes by path (unit/component job runs `backend/tests/unit/` + `backend/tests/component/`; integration job runs `backend/tests/integration/`). No `-m "not integration_prefect"` filter, no marker registration.

**Rationale.** Satisfies FR-021 ("each contract assertion authored once") without duplicating assertion logic — each `assert_<behavior>` lives in exactly one file, type-hinted against `PrefectClientTestAdapter`; both test packages call the same function with their lane's concrete implementation. Satisfies FR-022 without inventing a marker: the integration lane already exists as a directory, already boots an ephemeral Prefect server via `prefect_test_fixture`, and the integration sub-package's `conftest.py` depends on that fixture explicitly so configuration errors fail loud instead of silent-skipping. Matches the existing repo convention (`backend/tests/integration_docker/`, `backend/tests/functional/`, etc. are directory-scoped, not marker-scoped).

**Alternatives considered.**

- *One parametrized test package with `pytest.param("real", marks=pytest.mark.integration_prefect)`.* Rejected: re-introduces a marker we don't need — `integration/` is already the dedicated integration lane. The marker would be pure bookkeeping.
- *Dedicated `backend/tests/integration_prefect/` sibling (mirroring `integration_docker/`).* Rejected: `backend/tests/integration/` already stands up the Prefect ephemeral server in its `conftest.py`; a root-level sibling would duplicate that setup for no gain. `integration_docker/` exists because Docker is a special runtime that `integration/` does not guarantee — Prefect is not in that category here.
- *Record-replay (capture real responses, replay in fake run).* Rejected during `/speckit.clarify` Q5; see spec.
- *Property-based via Hypothesis.* Rejected in Q5 as over-investment.

---

## R-6 — Event-wait primitive design

**Decision.** Three test-only primitives live on `PrefectClientTestAdapter` (never reachable from production code, which type-hints against `PrefectClientAdapter`):

```python
def checkpoint() -> Checkpoint                                  # sync watermark
def captured_emits() -> AbstractAsyncContextManager[EmitCapture] # async context manager
async def wait_for_event(
    *,
    name: str | None = None,
    event_id: UUID | None = None,
    since: Checkpoint | None = None,
    timeout_seconds: float = 10.0,
) -> Event
```

At least one of `name` or `event_id` must be supplied to `wait_for_event`. Matching is keyed on Prefect's native `Event.id` whenever possible — no custom token is stamped into `payload`. The production-port `emit_event` therefore mirrors Prefect's signature exactly: it takes an optional caller-providable `id: UUID | None` (Prefect's own behavior) and returns `Event | None`. Tests that need an id either capture it from the return value, pre-mint and pass `id=...`, or harvest it via `captured_emits()` when the production code under test is the one emitting.

### Two concrete implementations

- **`InMemoryPrefectClientTestAdapter`** — Maintains an append-only in-memory event log. `wait_for_event` awaits an `asyncio.Event`/condition variable signalled by every `emit_event` and resolves as soon as a matching entry appears. No polling latency. The log is per-instance (fresh per test via the function-scoped fixture — FR-010), so cross-test leakage (FR-009) is impossible by construction. `checkpoint()` returns `Checkpoint(_log_index=len(self._emit_log))`. `captured_emits()` registers an `EmitCapture` on a `_captures` list; `emit_event` appends every emitted `Event` to all active captures. If no match arrives before `timeout_seconds`, raises `EventNotObservedError(name=..., event_id=..., elapsed_seconds=..., reason=EventNotObservedReason.NOT_EMITTED)`.

- **`RealPrefectClientTestAdapter`** — Polls `POST /events/filter` at a bounded interval (default 250 ms → ~40 polls per default 10 s timeout) with **server-side filtering only** via `EventFilter`:

  ```python
  EventFilter(
      occurred=EventOccurredFilter(since=since._occurred) if since else EventOccurredFilter(),
      event=EventNameFilter(name=[name]) if name else None,
      id=EventIDFilter(id=[event_id]) if event_id else None,
  )
  ```

  Verified in Prefect 3.6.13 (`prefect/events/filters.py`): `EventFilter` exposes a first-class `id: EventIDFilter` field, so id-based wait resolves at the API rather than after a client-side scan. `checkpoint()` records `datetime.now(UTC)` (no I/O — the wall-clock instant is used as the `since` watermark; exact server-clock alignment is not required at test scale). `captured_emits()` overrides the inherited `emit_event` to forward to Prefect, then appends the returned `Event` to every active capture. Returns the first match; raises `EventNotObservedError(..., reason=EventNotObservedReason.NOT_OBSERVABLE)` at timeout. The watermark + name + id filtering replace the `assert_event` helper's naive "any event with this name" check, which is what the current spec flags as a false-positive risk when prior tests emit the same event name.

### Why three primitives, not one

Tests fall into two ergonomic camps:

1. **"Wait for the next event of name X after my action."** Cheap, no per-emission id needed. `checkpoint()` + `wait_for_event(name=..., since=cp)` — three lines, no indentation change. This is the migration default for `assert_event` callers.
2. **"My action emits multiple events; assert on a specific one."** Requires per-emission id capture. `async with captured_emits() as cap: ...` then `wait_for_event(event_id=cap.only(name=...).id)` (or `cap.by_name(...)[i].id`).

Offering both keeps the simple case ergonomic (no async-with, no extra indentation) while making the strict case expressible. The test port carries ~40 lines for both APIs combined; they share the same underlying watermark/log mechanism in each adapter.

### Why production-vs-test separation

`wait_for_event` is NOT a Prefect-native primitive — Prefect's `PrefectClient` has no such method. It is adapter-orchestrated behaviour: a polling loop on the real side, a condition-variable fast path on the in-memory side. Because polling is a test pattern (production code reacts to Prefect events via automation triggers, not application-code polling), placing `wait_for_event`, `checkpoint`, and `captured_emits` on the test-only port keeps this behaviour out of production reach by construction rather than by convention. The production-port `emit_event` carries no test concept (no `correlation_id` parameter, no payload stamping), so production signatures stay identical to Prefect's.

### Failure-mode reasons

`NOT_EMITTED` (no event matched the wait criteria in the adapter's visible window — definitive) vs. `NOT_OBSERVABLE` (adapter reached timeout while Prefect's events API may still catch up — real adapter default). The distinction between `NOT_EMITTED` and `NOT_OBSERVABLE` on the real side via a pre-timeout `count_events` check is conceivable but deferred — the baseline message is sufficient for the acceptance scenarios.

### Poll parameters (real test adapter)

Default interval 250 ms, default total timeout 10 s (= ~40 polls). Only the timeout is overridable via `timeout_seconds=` on the call; the interval is a class-level constant, not a caller parameter, so tests don't carry policy. The in-memory-backed lane does not poll at all (it's condition-variable-based), so per-test `wait_for_event` overhead is effectively the emission-to-signal round trip. On the real-backed lane, median wait resolves at ≤250 ms after emission + ingest-lag — inside the previous 30 s ceiling by two orders of magnitude, meeting SC-005 comfortably.

### Alternatives considered

- *Custom `correlation_id` stamped into `payload`.* Rejected: pollutes the production-port `emit_event` signature with a test-only parameter, requires adapter logic to stamp/extract a magic key, and forces client-side filtering on the real adapter (`EventFilter` exposes no payload-key filter). Native `Event.id` is already caller-providable, already returned by `emit_event`, and is server-side filterable via `EventFilter.id` — strictly cleaner.
- *Pre-mint pattern only (no `captured_emits`).* Rejected: requires production functions to grow a test-only `id`/`event_id` parameter that callers thread down to the `emit_event` call site, which is exactly the production-code intrusion the adapter is meant to avoid. Capture pattern leaves production signatures untouched.
- *`captured_emits` only (no `checkpoint`).* Rejected: every wait-for-event test grows an `async with` block and one indentation level. The 1:1 simple case (most migration targets — `assert_event`, `query_events_by_name`) doesn't need per-emission id capture; a pre-action checkpoint is cheaper. Offering both lets each test pick the lightest tool for its job.
- *Subscribe to Prefect's event stream via WebSocket.* Rejected: Prefect 3.x does expose this, but the ingest-lag problem is independent of transport. Polling with a watermark is simpler and covers the stated need.
- *`wait_for_event` on the production port (with lint ban or ugly rename).* Rejected per R-3: splitting into a production port and a test port makes the "production code can't reach wait_for_event" guarantee a type-system invariant rather than a convention.
- *Uniform polling on both the real and in-memory test adapters via a generic helper that polls `filter_events`.* Rejected: loses the in-memory adapter's condition-variable fast path. SC-009's <10ms budget tolerates it, but Story 2's migrated tests benefit more from a genuinely instantaneous event resolution on the fast lane.

---

## R-7 — In-memory test adapter: how argument validation works

**Decision.** `InMemoryPrefectClientTestAdapter` does not hand-write type guards per method. Instead, each adapter method signature on the production-port ABC uses Pydantic types (or `pydantic.BaseModel` subclasses from `prefect.client.schemas.*` which are already Pydantic v2). At class build time, the concrete class walks the ABC's abstract methods with `inspect.signature(...)`, builds a `pydantic.TypeAdapter` per parameter annotation, and wraps each concrete method so every incoming kwarg bundle is validated on entry — a validation failure raises a descriptive `AssertionError` naming the method, the parameter, and the mismatch (FR-002, SC-003). Return values are constructed using the real Prefect response classes, so callers receive real types (FR-005).

**Rationale.** Prefect's client schemas are Pydantic models; reusing them for validation is free and catches field-name drift automatically when Prefect upgrades. This satisfies SC-007 (a Prefect method signature change surfaces as a contract-test failure at the adapter layer). The validation wrapper is implemented via `__init_subclass__` on the production-port ABC (or via an explicit decorator in `_testing.py`), so the in-memory test adapter doesn't repeat validation logic per method.

**Alternatives considered.**

- *`create_autospec(PrefectClient)` under the hood.* Rejected (this is the pattern the feature is designed to replace).
- *Hand-written validators.* Rejected: duplicates what Pydantic already provides, drifts from Prefect upstream.

---

## Summary of resolved unknowns

| Technical Context field | Resolution |
|---|---|
| Language/Version | Python 3.12 (confirmed from `AGENTS.md`) |
| Primary Dependencies | Prefect 3.x (currently pinned in `pyproject.toml`; FR-024 governs upgrades) |
| Testing | pytest + pytest-asyncio; contract assertions authored once in `backend/tests/helpers/prefect_client_contracts.py` (type-hinted against `PrefectClientTestAdapter`); invoked from `backend/tests/unit/prefect_client/` (`InMemoryPrefectClientTestAdapter`-backed, fast lane) and `backend/tests/integration/prefect_client/` (`RealPrefectClientTestAdapter`-backed, reusing the existing `prefect_test_fixture` from `backend/tests/integration/conftest.py`) |
| Constraints (boundary scope) | R-1 refines FR-015: client API wrapped; runtime-decorator surface whitelisted |
| Scale/Scope | 30 production files with client-API usage (from R-2 audit); migration in per-subsystem PRs (FR-016) |

No outstanding `NEEDS CLARIFICATION` items.
