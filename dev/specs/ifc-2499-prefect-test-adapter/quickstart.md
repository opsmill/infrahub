# Quickstart: Writing tests against the Prefect Client Adapter

This is a developer-facing one-pager. It covers the four things you are most likely to do during v1 migration and afterward.

## 1. Write a unit test that exercises Prefect-touching code

Before:

```python
# backend/tests/unit/webhook/test_webhook_automation.py (the old world)
from unittest.mock import create_autospec
from prefect.client.orchestration import PrefectClient

@pytest.fixture
def prefect_client() -> PrefectClient:
    client = create_autospec(PrefectClient, spec_set=True, instance=True)
    client.create_automation.return_value = AUTOMATION_ID
    return client
```

After:

```python
# backend/tests/unit/webhook/test_webhook_automation.py (new world)
from infrahub.services.adapters.prefect_client import PrefectClientAdapter
from infrahub.services.adapters.prefect_client._testing import (
    InMemoryPrefectClientTestAdapter,
)

# `in_memory_prefect_test_adapter` is discovered automatically from
# backend/tests/helpers/prefect_client.py — no import needed.

@pytest.fixture
async def prefect_client(
    in_memory_prefect_test_adapter: InMemoryPrefectClientTestAdapter,
) -> PrefectClientAdapter:
    in_memory_prefect_test_adapter.seed_return("create_automation", AUTOMATION_ID)
    return in_memory_prefect_test_adapter  # production code sees it as PrefectClientAdapter
```

Note: the fixture returns the in-memory test adapter, but code under test receives it as `PrefectClientAdapter` (the production port). Production code cannot reach `wait_for_event` or any other test-only primitive — those live on `PrefectClientTestAdapter`, a narrower type that production code never depends on.

No `AsyncMock`. No `create_autospec`. The seeded return value is typed. A malformed call from the code under test fails at the adapter layer with a clear message.

Assertions on what happened:

```python
assert in_memory_prefect_test_adapter.recorded("create_automation")
assert in_memory_prefect_test_adapter.recorded("create_automation", kwargs={"automation": expected})
assert in_memory_prefect_test_adapter.call_count("create_automation") == 1
```

No `mock.create_automation.assert_called_once_with(...)` — the adapter owns its own assertion helpers (FR-007). These recorder helpers (`recorded`, `call_count`, `seed_return`, `recorded_calls`, `unused_seeds`, `reset`) are **concrete methods on `InMemoryPrefectClientTestAdapter`**, not on any ABC — no real Prefect backend can deliver them, so they don't belong on a shared port.

## 2. Seed a specific return value for one call

```python
in_memory_prefect_test_adapter.seed_return(
    "read_automations_by_name",
    value=[existing_automation],
    where={"name": "my-automation"},  # only match calls with this kwarg (shallow dict match)
)
# `where` also accepts a callable: where=lambda kwargs: kwargs["name"].startswith("my-")
```

At test teardown, a fixture-level check fails the test if any seed was never consumed (FR-012, SC-001's "no dead stubs" guarantee).

## 3. Wait deterministically for an emitted event

Replace the old 30-iteration polling helper. Two patterns — pick the lighter one for your test.

### 3a. Simple "wait for the next event of this name" — `checkpoint()`

For tests where the action emits a single event of interest:

```python
# OLD — tests/functional/proposed_change/test_thread_events.py
await self.assert_event(prefect_client, event_name="infrahub.proposed_change_thread.created")

# NEW
since = prefect_test_adapter.checkpoint()                # sync; no await
await code_under_test(...)
event = await prefect_test_adapter.wait_for_event(
    name="infrahub.proposed_change_thread.created",
    since=since,
    timeout_seconds=10.0,                                # or omit for the module default
)
```

`checkpoint()` records a watermark — log index for in-memory, wall-clock instant for real. `wait_for_event(name=..., since=...)` then matches the next event of that name emitted after the checkpoint, ignoring anything earlier (including events from prior tests in the same class — FR-009). No async-with, no extra indentation; the only cost vs. the old helper is one extra line.

### 3b. Strict per-emission matching — `captured_emits()`

For tests where the action emits multiple events and you want to assert on a specific one (or assert exactly-one-of-this-name):

```python
async with prefect_test_adapter.captured_emits() as cap:
    await code_under_test(...)

# Strictest: assert exactly one matching emission, then resolve via Prefect's events API
event = await prefect_test_adapter.wait_for_event(
    event_id=cap.only(name="infrahub.proposed_change_thread.created").id,
)

# Or pick a specific one when multiple are expected
target_id = cap.by_name("infrahub.node.created")[2].id
event = await prefect_test_adapter.wait_for_event(event_id=target_id)
```

`captured_emits()` records every `Event` emitted in the `async with` block. Matching by `event_id` uses Prefect's native `Event.id` (set on emit, returned from `emit_event`, server-side filterable on the real adapter via `EventFilter.id`). No payload pollution, no custom token threaded through production signatures.

### Adapter behavior

- Against the **`InMemoryPrefectClientTestAdapter`**: returns as soon as the code under test has called `emit_event` for the matched event. No sleeps, no timer — the log's condition variable wakes the waiter directly.
- Against the **`RealPrefectClientTestAdapter`** (integration / functional tests): polls `POST /events/filter` at 250 ms intervals with **server-side filtering only** via `EventFilter(id=EventIDFilter(...), event=EventNameFilter(...), occurred=EventOccurredFilter(since=...))`. Times out with `EventNotObservedError(name=..., event_id=..., elapsed_seconds=..., reason=EventNotObservedReason.NOT_OBSERVABLE)`.

Note: `wait_for_event`, `checkpoint`, and `captured_emits` are defined on `PrefectClientTestAdapter`, not on `PrefectClientAdapter`. Code under test (production) receives `PrefectClientAdapter` and cannot call them; test code holds a reference typed as `PrefectClientTestAdapter` (or the concrete test-adapter class) and can.

## 4. Add a contract test for a newly-wrapped operation

Every method on `PrefectClientAdapter` or `PrefectClientTestAdapter` must be backed by a contract assertion that runs against **both** test implementations (FR-021, SC-011). The assertion is authored **once** in a shared helpers module, type-hinted against `PrefectClientTestAdapter` (so `wait_for_event` is reachable), and invoked from two thin test packages — one per CI lane:

```python
# backend/tests/helpers/prefect_client_contracts.py
from infrahub.services.adapters.prefect_client import PrefectClientTestAdapter

async def assert_create_and_read_automation(adapter: PrefectClientTestAdapter) -> None:
    automation = AutomationCore(name="contract-test", ...)
    automation_id = await adapter.create_automation(automation=automation)

    results = await adapter.read_automations_by_name(name="contract-test")
    assert len(results) == 1
    assert results[0].id == automation_id
```

```python
# backend/tests/unit/prefect_client/test_automations.py  (fast lane)
async def test_create_and_read_automation(in_memory_prefect_test_adapter):
    await assert_create_and_read_automation(in_memory_prefect_test_adapter)

# backend/tests/integration/prefect_client/test_automations.py  (integration lane)
async def test_create_and_read_automation(real_prefect_test_adapter):
    await assert_create_and_read_automation(real_prefect_test_adapter)
```

- **Unit/component job** runs `backend/tests/unit/prefect_client/` (and the rest of the unit tree), backed by `InMemoryPrefectClientTestAdapter`. No Prefect server required.
- **Integration job** runs `backend/tests/integration/prefect_client/`, backed by `RealPrefectClientTestAdapter`; reuses the existing `prefect_test_fixture` from `backend/tests/integration/conftest.py` to stand up an ephemeral Prefect server. The sub-package's local `conftest.py` depends on that fixture explicitly so a missing/broken Prefect setup fails loudly rather than silently skipping.
- **Both jobs gate merges** (FR-021). Integration-job failures are analyzed before relaunch — never auto-skipped, never configured non-blocking.

No pytest marker is used — the CI lanes are selected by directory path, matching the repo convention (`backend/tests/unit/`, `backend/tests/component/`, `backend/tests/integration/`, `backend/tests/integration_docker/`, `backend/tests/functional/` are all directory-scoped).

## Boundary rule (FR-015, research R-1)

```
backend/infrahub/*                        # import from `prefect` is FORBIDDEN (ruff banned-api)
  ├── services/adapters/prefect_client/   # the ONE allowed package
  │   ├── __init__.py                     # ABCs: PrefectClientAdapter (production port)
  │   │                                   #       PrefectClientTestAdapter (test port)
  │   ├── real.py                         # RealPrefectClientAdapter (production)
  │   │                                   #   imports `prefect.client.orchestration.PrefectClient` etc.
  │   ├── _testing.py                     # RealPrefectClientTestAdapter + InMemoryPrefectClientTestAdapter
  │   │                                   #   (test-only; underscore prefix signals "not for production")
  │   └── types.py                        # re-exports Prefect Pydantic types for port consumers
  │
  └── anywhere/using/@flow/@task/         # whitelist: runtime-decorator surface remains direct
```

Type-system boundary: production code type-hints against `PrefectClientAdapter` and receives `RealPrefectClientAdapter`. It cannot see `wait_for_event` or any test-only primitive, because those live on `PrefectClientTestAdapter` — a subclass production code never depends on. The boundary is enforced by the compiler/type-checker, not by convention.

If you need a Prefect type (e.g., `Automation`, `FlowRun`, `State`), import it from `infrahub.services.adapters.prefect_client.types`, never from `prefect.*` directly. Adding a new type to `types.py` is part of migrating a caller to the port.

## Where things live

| Thing | Path |
|---|---|
| Production port (ABC) | `backend/infrahub/services/adapters/prefect_client/__init__.py` (`PrefectClientAdapter`) |
| Test port (ABC) | `backend/infrahub/services/adapters/prefect_client/__init__.py` (`PrefectClientTestAdapter`) |
| Exception + reason enum | `backend/infrahub/services/adapters/prefect_client/__init__.py` (`EventNotObservedError`, `EventNotObservedReason`) |
| Real production adapter | `backend/infrahub/services/adapters/prefect_client/real.py` (`RealPrefectClientAdapter`) |
| Real test adapter | `backend/infrahub/services/adapters/prefect_client/_testing.py` (`RealPrefectClientTestAdapter`) |
| In-memory test adapter | `backend/infrahub/services/adapters/prefect_client/_testing.py` (`InMemoryPrefectClientTestAdapter`) |
| Type re-exports | `backend/infrahub/services/adapters/prefect_client/types.py` |
| Test-adapter fixture wiring | `backend/tests/helpers/prefect_client.py` |
| Contract assertion helpers | `backend/tests/helpers/prefect_client_contracts.py` (authored once per FR-021) |
| Unit contract tests (in-memory) | `backend/tests/unit/prefect_client/` |
| Integration contract tests (real Prefect) | `backend/tests/integration/prefect_client/` — reuses the `prefect_test_fixture` already defined in `backend/tests/integration/conftest.py` |
| Boundary lint config | `pyproject.toml` (ruff `flake8-tidy-imports.banned-api`) |
