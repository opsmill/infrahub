# Implementation Plan: Prefect Client Port & Adapter (with Test Adapters)

**Branch**: `ifc-2499-prefect-test-adapter` | **Date**: 2026-04-23 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/ifc-2499-prefect-test-adapter/spec.md`

## Summary

Introduce two domain-owned ports: `PrefectClientAdapter` (production — 18 concrete Prefect client operations: automation CRUD + read, deployment read/run, event emission/filter/count, flow-run read/state/logs, work-pool read/create; `emit_event` mirrors Prefect's native signature exactly, no test-only parameters) and `PrefectClientTestAdapter(PrefectClientAdapter)` (test — adds three primitives in v1: `wait_for_event` keyed on Prefect's native `Event.id`, sync `checkpoint() -> Checkpoint` watermark, and async `captured_emits() -> AbstractAsyncContextManager[EmitCapture]`; FR-018 follow-ups later). Ship three concrete classes:

1. `RealPrefectClientAdapter` (production) — wraps `prefect.client.orchestration.PrefectClient` and the one remaining Prefect SDK call path (`prefect.events.emit_event`).
2. `RealPrefectClientTestAdapter(RealPrefectClientAdapter, PrefectClientTestAdapter)` — inherits every production operation; adds `wait_for_event` as a bounded polling loop with **server-side filtering only** via `EventFilter` (`id=EventIDFilter`, `event=EventNameFilter`, `occurred=EventOccurredFilter(since=...)`); implements `checkpoint()` via wall-clock instant and `captured_emits()` by intercepting its own `emit_event` to mirror returned events into active captures.
3. `InMemoryPrefectClientTestAdapter(PrefectClientTestAdapter)` — implements every production operation against in-memory state (event log, seed registry, call log); implements `wait_for_event` via condition-variable observation of the log (no polling); `checkpoint()` records the log length; `captured_emits()` appends every emission to active `EmitCapture` instances; exposes in-memory-specific concrete helpers (`seed_return`, `recorded`, `call_count`, `recorded_calls`, `unused_seeds`, `reset`) that are **not** on any ABC.

Migrate all production callers to the production port, enforce the boundary with a ruff `banned-api` rule (Prefect imports allowed only inside the adapter module, the test conftests that boot `prefect_test_harness`, and the `@flow`/`@task` runtime-decorator surface — see research R-1), and add a contract test suite whose assertions are authored once in a shared helpers module and invoked from two thin twin test packages — `InMemoryPrefectClientTestAdapter`-backed under `backend/tests/unit/prefect_client/` (unit/component CI job) and `RealPrefectClientTestAdapter`-backed under `backend/tests/integration/prefect_client/` (integration CI job, reusing the existing `prefect_test_fixture`). v1 carries a recorder-only in-memory test adapter; a programmable stateful test adapter is an explicit follow-up (FR-018).

## Technical Context

**Language/Version**: Python 3.12 (backend)  
**Primary Dependencies**: Prefect 3.x (existing, pinned — FR-024), `prefect.client.orchestration.PrefectClient`, `pytest` 9.0, `pytest-asyncio`  
**Storage**: N/A (adapter is stateless in the real impls; the in-memory test adapter holds per-test state in memory)  
**Testing**: pytest (unit, component, functional, contract, integration); existing fixtures in `backend/tests/helpers/test_app.py`  
**Target Platform**: Linux server (Infrahub backend)  
**Project Type**: Single backend Python package (`backend/infrahub/`)  
**Performance Goals**: Unit tests that inject the in-memory test adapter execute in <10ms median (SC-009); event-wait primitive returns as soon as the event is observable (SC-005)  
**Constraints**: 
- Zero Prefect-attributable flakes on unit/component suites over rolling 30-day window (SC-010)
- No `prefect.*` imports outside the adapter module and integration tests, except the runtime-decorator surface whitelisted in R-1 (FR-015, refined)
- Interface stable across Prefect version pins; signature deltas absorbed inside the real adapter (FR-024)  
**Scale/Scope**: 30 production files currently invoke Prefect client operations (audit in research R-2); 172 total `prefect` imports across 70 files (most of which are the runtime-decorator surface and remain direct)

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

Gates derived from `dev/constitution.md`:

| Principle | Gate | Status |
|---|---|---|
| III. Type Safety & Explicit Contracts | All public adapter methods carry type hints; real Prefect response types are returned (no untyped dicts, no `Any`) | PASS — FR-005 & FR-002 mandate this |
| IV. Test Discipline — "Prefer adapter/protocol patterns over mocking" | Feature *is* the adapter; direct enablement of the principle | PASS — the feature exists to satisfy this |
| IV. Test Discipline — test level | Unit (`InMemoryPrefectClientTestAdapter`-backed), component, contract (twin packages sharing helpers per FR-021), integration (`RealPrefectClientTestAdapter`-backed, separate CI job) — all levels planned | PASS — see Phase 1 test layout |
| VII. Simplicity & Maintainability — YAGNI | v1 is a recorder only; stateful test adapter deferred (FR-017, FR-018); surface limited to what production code currently uses (FR-019); `wait_for_event` kept off the production port (test port only) so production code can't reach it | PASS — scope pruned during `/speckit.clarify` |
| VII. Simplicity — "Follow established project patterns" | Adapter lives next to existing `InfrahubWorkflow` / `InfrahubEventService` adapters, same naming, parallel in-memory-vs-real split for the test adapters | PASS — see R-3 |
| II. Branch-Safe by Default | Adapter does not touch branch/temporal state; Prefect data is branch-agnostic | N/A |
| V. Query Performance | No new DB queries; adapter wraps existing Prefect API calls | N/A |
| VI. Security & Input Boundaries | No new user-input surface; adapter is internal | N/A |

No violations. No entries needed in Complexity Tracking.

## Project Structure

### Documentation (this feature)

```text
specs/ifc-2499-prefect-test-adapter/
├── plan.md              # This file
├── research.md          # Phase 0 output — surface audit, boundary rule, structure decision
├── data-model.md        # Phase 1 output — interface entities and shapes
├── quickstart.md        # Phase 1 output — how to write a test using the adapters
├── contracts/           # Phase 1 output — interface definitions
│   └── prefect_client_adapter.py  # the port, expressed as abstract Python
├── checklists/
│   └── requirements.md  # from /speckit.specify
└── tasks.md             # Phase 2 output (/speckit.tasks command — NOT created here)
```

### Source Code (repository root)

New and modified paths under the existing backend layout:

```text
backend/infrahub/services/adapters/prefect_client/
├── __init__.py                 # exports PrefectClientAdapter (production port)
│                               # and PrefectClientTestAdapter (test port)
│                               # plus EventNotObservedError + EventNotObservedReason
├── real.py                     # RealPrefectClientAdapter (production)
│                               # wraps prefect.client.orchestration.PrefectClient
├── _testing.py                 # Test-only concrete classes:
│                               #   - RealPrefectClientTestAdapter
│                               #     (inherits RealPrefectClientAdapter, adds polling wait_for_event)
│                               #   - InMemoryPrefectClientTestAdapter
│                               #     (in-memory; implements all production ops + wait_for_event via
│                               #     condition variable; carries recorder helpers)
│                               # Underscore prefix signals "not for production imports".
└── types.py                    # Re-exports of the Prefect response/request types that cross the port boundary
                                # (Automation, Deployment, FlowRun, Event, WorkPool, StateType, etc.)
                                # This is the ONLY other production module permitted to import from `prefect`.

backend/tests/helpers/prefect_client.py
    # pytest fixture(s) that build an InMemoryPrefectClientTestAdapter, wire it into the
    # existing service locator when production-code tests need it, and reset state between
    # tests (FR-010). Also exposes a fixture that builds a RealPrefectClientTestAdapter
    # on top of the existing prefect_test_fixture for integration and functional tests.

backend/tests/helpers/prefect_client_contracts.py
    # Single source of truth for contract assertions (FR-021, "authored once").
    # Exposes async helpers of the form `assert_<behavior>(adapter: PrefectClientAdapter)`
    # that both the in-memory-backed and real-backed test packages below invoke.

backend/tests/unit/prefect_client/
├── __init__.py
├── conftest.py                 # re-exposes the function-scoped in_memory_prefect_test_adapter
│                               # fixture from backend/tests/helpers/prefect_client.py (FR-010)
├── test_automations.py
├── test_deployments.py
├── test_events.py
├── test_flow_runs.py
└── test_work_pools.py
    # Each test function imports an assert_* helper and runs it against the
    # InMemoryPrefectClientTestAdapter. Runs in the unit/component CI job (FR-021, FR-022).

backend/tests/integration/prefect_client/
├── __init__.py
├── conftest.py                 # depends explicitly on the existing `prefect_test_fixture`
│                               # from backend/tests/integration/conftest.py and builds a
│                               # RealPrefectClientTestAdapter against it; fails loudly if
│                               # the fixture is unavailable (SC-012, FR-022).
├── test_automations.py
├── test_deployments.py
├── test_events.py
├── test_flow_runs.py
└── test_work_pools.py
    # Mirrors the unit tree structure — same test names, same helper calls, but wired to
    # the RealPrefectClientTestAdapter. Runs in the existing integration CI job (no marker
    # needed). Both the unit/component job and the integration job gate merges (FR-021);
    # integration failures are analyzed before relaunch, never auto-skipped or configured
    # non-blocking.

backend/infrahub/services/adapters/event/__init__.py
    # Existing InfrahubEventService — `_send_prefect` migrates to call the adapter
    # interface instead of importing `prefect.events.emit_event` directly.

# Migrations (no new files; FR-015/FR-016 enforced per subsystem):
backend/infrahub/trigger/setup.py          # PrefectClient usage → adapter
backend/infrahub/trigger/tasks.py          # get_client() → adapter
backend/infrahub/webhook/tasks/configure.py # get_client() → adapter
backend/infrahub/webhook/models.py         # PrefectClient, AutomationCore → adapter + types re-export
backend/infrahub/task_manager/event.py     # event filter/query → adapter
backend/infrahub/task_manager/task.py      # flow-run queries → adapter
backend/infrahub/task_manager/models.py    # Log/EventFilter response types → adapter/types
backend/infrahub/workflows/initialization.py # PrefectClient → adapter
backend/infrahub/workflows/utils.py         # deployment/automation ops → adapter
backend/infrahub/workflows/models.py        # response/request types → adapter/types
backend/infrahub/workers/dependencies.py    # client wiring → adapter factory
# ...full list derived from research R-2 surface audit; see tasks.md (Phase 2)

# Runtime-decorator surface (remains direct, per R-1):
# Any file using `from prefect import flow, task`, `from prefect.cache_policies import NONE`,
# `from prefect.logging import get_run_logger`, `from prefect.runtime import flow_run`.
# These are task-authoring primitives, not client calls; wrapping them would be mis-scoped.

# Boundary enforcement:
pyproject.toml
    # Add ruff flake8-tidy-imports `banned-api` or equivalent per-file-ignore
    # so that `prefect.*` imports are forbidden outside the whitelist.
```

**Structure Decision**: Follow the existing Infrahub adapter convention — place the new adapter package under `backend/infrahub/services/adapters/prefect_client/` alongside `workflow/`, `event/`, `message_bus/`, `cache/`, and `http/`. This matches the constitutional requirement to "Follow established project patterns" (Principle VII) and keeps the port/adapter pattern uniform across the codebase. Within the package, separate the two production-facing modules (`__init__.py` for the ABCs, `real.py` for `RealPrefectClientAdapter`) from the test-only concretes (`_testing.py` for `RealPrefectClientTestAdapter` and `InMemoryPrefectClientTestAdapter`); the underscore prefix signals "not for production imports" and the colocation keeps the test classes close to the production code they shadow. Use `services/adapters/prefect_client/types.py` as the single escape hatch for re-exporting Prefect SDK types that legitimately cross the port (Automation, FlowRun, StateType, Event, etc.); this is the one additional module, beyond the adapter itself, allowed to import from `prefect`.

## Complexity Tracking

No constitution violations. No justifications needed.

---

## Phase 0 — Research

See [research.md](./research.md) for full findings. Summary of decisions:

- **R-1** Scope refinement of FR-015: `prefect` runtime-decorator surface (`@flow`, `@task`, `get_run_logger`, `flow_run`, `cache_policies`) is **not** wrapped; the ban applies only to the client-API surface.
- **R-2** Concrete client-surface enumeration derived from auditing all `prefect.client.*` and `prefect.events.*` usages in `backend/infrahub/`.
- **R-3** Adapter module location and naming aligned with existing `InfrahubWorkflow` / `InfrahubEventService`. Two ABCs (production + test port) and three concrete classes (`RealPrefectClientAdapter`, `RealPrefectClientTestAdapter`, `InMemoryPrefectClientTestAdapter`) with the test-only classes colocated under `_testing.py`.
- **R-4** Boundary enforcement via ruff `flake8-tidy-imports.banned-api` with a narrow whitelist (adapter module, types module, test conftests that boot `prefect_test_harness`, runtime-decorator files). Complements the type-system boundary between `PrefectClientAdapter` and `PrefectClientTestAdapter`.
- **R-5** Contract-test structure — assertions authored once in `backend/tests/helpers/prefect_client_contracts.py`; invoked from twin test packages at `backend/tests/unit/prefect_client/` (`InMemoryPrefectClientTestAdapter`-backed) and `backend/tests/integration/prefect_client/` (`RealPrefectClientTestAdapter`-backed, reusing the existing `prefect_test_fixture`). Directory-based CI lane split, no pytest marker.
- **R-6** Event-wait primitives — three test-only primitives live on `PrefectClientTestAdapter` (never reachable from production): `wait_for_event(*, name=None, event_id=None, since=None, timeout_seconds=10.0)`, sync `checkpoint() -> Checkpoint`, and async `captured_emits() -> AbstractAsyncContextManager[EmitCapture]`. Matching is keyed on Prefect's native `Event.id` whenever possible; the production-port `emit_event` mirrors Prefect's signature exactly (no `correlation_id` parameter, no payload pollution). `InMemoryPrefectClientTestAdapter` observes its own in-memory log via an `asyncio.Event`/condition variable signalled by every `emit_event` (no polling). `RealPrefectClientTestAdapter` polls `POST /events/filter` at a bounded interval with server-side filtering only — Prefect 3.6.13's `EventFilter` exposes first-class `id`, `event`, and `occurred` filter fields, so id-based wait resolves at the API rather than after a client-side scan (replacing the test-owned `assert_event` retry loop).
- **R-7** Argument validation in the in-memory test adapter — at class build time, walk the production ABC's abstract methods with `inspect.signature(...)`, build a `pydantic.TypeAdapter` per parameter annotation, wrap each concrete method so every kwarg bundle is validated on entry. Prefect upgrades surface as signature changes at the adapter layer (SC-007).

## Phase 1 — Design & Contracts

See [data-model.md](./data-model.md), [contracts/prefect_client_adapter.py](./contracts/prefect_client_adapter.py), and [quickstart.md](./quickstart.md).

- **data-model.md** enumerates the entities that cross the port (request args, response objects re-exported from Prefect types) and the in-memory test adapter's internal state shape (recorded calls, seeded returns, observed events).
- **contracts/prefect_client_adapter.py** expresses both ports (production + test) as abstract Python classes with typed signatures — the plan artifact mirrors the runtime module that will live at `backend/infrahub/services/adapters/prefect_client/__init__.py`.
- **quickstart.md** shows a developer the minimal path: (a) how to write a new unit test against the in-memory test adapter (FR-001–FR-007, SC-001), (b) how to seed a return value, (c) how to use the event-wait primitive, and (d) how to add a contract test for a newly-wrapped operation.

## Post-design Constitution Re-check

After Phase 1 artifacts are written, re-check:

- **Principle III** — All contract signatures carry type hints, all response types are the real Prefect types (not untyped dicts). ✔ enforced by `contracts/prefect_client_adapter.py`.
- **Principle IV** — Each user story in the spec has a concrete test-level home (Story 1 → unit + in-memory-backed contract; Story 2 → functional + in-memory-backed contract; contract tests exercise both `InMemoryPrefectClientTestAdapter` and `RealPrefectClientTestAdapter`). ✔
- **Principle VII** — No speculative surface; the in-memory test adapter is a recorder (FR-017); the production port is the smallest shape that covers R-2's audit; test-only primitives live on the test port so production callers can't reach them. ✔

## Stop Point

Planning ends after Phase 1 artifact generation (`research.md`, `data-model.md`, `contracts/`, `quickstart.md`). Task decomposition (`tasks.md`, the Phase 2 output) is produced by `/speckit.tasks`, not by this command.
