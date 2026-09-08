# Backend Testing

> Part of: `dev/knowledge/backend/` | Related: [backend/AGENTS.md](../../../backend/AGENTS.md)

Overview of the backend testing infrastructure, test types, and patterns.

## Testing Philosophy

Infrahub uses pytest with TestContainers to provide reproducible, isolated tests. The testing approach balances:

- **Speed**: Module-scoped containers minimize startup overhead
- **Realism**: Tests run against real Neo4j/Redis/NATS when needed
- **Debuggability**: Functional tests run in a single process for breakpoint debugging
- **Isolation**: Each test module gets a fresh database state

## Test Directory Types

### Unit Tests (`backend/tests/unit/`)

Fast unittests that require no external services to run. I.e. no database or network access. Tests in this directory can read from local folders and files.

**Characteristics:**

- Fast feedback loop
- Sanity checks

**When to use:** Pure logic — parsing, validation, transformation, data structures. No database, no network, no infrastructure. If the function under test doesn't need a DB connection or external service to do its job, it's a unit test.

**When NOT to use:** If reproducing the bug requires database state, concurrent writes, constraint enforcement, or infrastructure behavior (locks, caches, message buses). Use component or functional tests instead — do not mock infrastructure to force a unit test.

### Component Tests (`backend/tests/component/`)

Many tests leverage the database and use TestContainers for external dependencies.

**Characteristics:**

- Uses TestContainers for Neo4j, Redis, etc.
- Module-scoped containers for faster execution
- Tests individual components with database interaction
- Fast feedback loop

**When to use:** Testing individual components that require external services — database state, cache behavior, lock coordination, message bus interactions, or any business logic that depends on infrastructure. See the [Key Root Fixtures](#key-root-fixtures) and [Test Adapters](#test-adapters) sections below for available test infrastructure.

### Functional Tests (`backend/tests/functional/`)

Multi-component tests running in a single thread/process. Async tasks execute inline without separate workers.

**Characteristics:**

- Single thread/process execution
- Async tasks run inline (no separate workers needed)
- Full debuggability with breakpoints
- Uses `prefect_test_harness` for Prefect integration

**When to use:** Features that span multiple components, including async workflows, event-driven behavior, or end-to-end flows that cross service boundaries.

### Integration Tests (`backend/tests/integration/`)

> **Note:** Currently contains tests that should be migrated to `functional/`. The directory is being transitioned to hold only true distributed integration tests.

### Integration Docker Tests (`backend/tests/integration_docker/`)

True distributed tests with multiple Docker containers running the full Infrahub stack.

**Characteristics:**

- Uses SDK's `TestInfrahubDockerClient` base class
- Starts full Infrahub environment (server, workers, database)
- Slowest but most realistic testing
- Tests real distributed behavior

**When to use:** Testing behavior that requires actual distributed execution, like [computed attributes](computed-attributes.md), triggered actions, or schema migrations in production-like environments.

```python
from infrahub_sdk.testing.docker import TestInfrahubDockerClient

class TestComputedAttributes(TestInfrahubDockerClient):
    @pytest.fixture(scope="class")
    def infrahub_version(self) -> str:
        return "local"

    async def test_load_schema(self, client: InfrahubClient) -> None:
        # Full distributed environment available
        ...
```

### Benchmark Tests (`backend/tests/benchmark/`)

Performance testing using `pytest-benchmark`. CI integration with CodSpeed tracks performance over time.

**Characteristics:**

- Uses `pytest-benchmark` fixtures
- Special `aio_benchmark` fixture for async functions
- Results tracked in CodeSpeed CI

```python
@pytest.fixture
async def aio_benchmark(benchmark: BenchmarkFixture, event_loop) -> Callable:
    def _wrapper(func, *args, **kwargs):
        if asyncio.iscoroutinefunction(func):
            @benchmark
            def _():
                return event_loop.run_until_complete(func(*args, **kwargs))
        else:
            return benchmark(func, *args, **kwargs)
    return _wrapper

# Usage
async def test_query_performance(aio_benchmark, db):
    await aio_benchmark(expensive_query, db=db)
```

**The benchmark's input must actually exercise what it claims to measure.** When a performance
change is conditional on a specific input shape (a particular field selection, a branch of an
`if`, a fast path), add or update a benchmark whose input takes that path. A benchmark that takes a
different path measures the neighbour instead and honestly reports "no change" — so on a perf PR,
check that the input drives the changed code before reading anything into the result, either way.

### Query Benchmark Tests (`backend/tests/query_benchmark/`)

Dedicated database query performance testing. Measures query execution time and efficiency using database snapshots for comparison.

### Scale Tests (`backend/tests/scale/`)

Large dataset testing to verify system behavior under load. Uses heavy data fixtures to test performance at scale.

## Test Infrastructure

### TestContainers Setup

Controlled by environment variable `INFRAHUB_USE_TEST_CONTAINERS=true`.

[TestContainers](https://testcontainers.com/) is a library that manages Docker containers for tests. Key benefits:

- **Lifecycle management**: Automatically starts containers before tests and stops them after
- **Port allocation**: Dynamically assigns available ports to avoid conflicts
- **Parallel execution**: Multiple test sessions can run simultaneously without port collisions
- **Isolation**: Each test session gets its own container instances

**Session-scoped container fixtures:**

| Fixture | Purpose |
|---------|---------|
| `neo4j_container` | Graph database |
| `memgraph_container` | Alternative graph database |
| `redis_container` | Cache |
| `rabbitmq_container` | Message broker |
| `nats_container` | Event streaming |
| `prefect_container` | Workflow engine |

```python
# Session-scoped container creation
@pytest.fixture(scope="session")
def neo4j(request, load_settings_before_session) -> dict[int, int] | None:
    if not INFRAHUB_USE_TEST_CONTAINERS:
        return None

    container = start_neo4j_container(NEO4J_IMAGE)
    request.addfinalizer(container.stop)

    return {
        PORT_BOLT_NEO4J: get_exposed_port(container, PORT_BOLT_NEO4J),
        PORT_HTTP_NEO4J: get_exposed_port(container, PORT_HTTP_NEO4J),
    }
```

### Parallel execution and database isolation

Component, core, functional and integration tests run under pytest-xdist (`-n <workers>`, see
`tasks/backend.py`); unit tests do not. Each xdist worker is a separate process running its own
pytest session, so the session-scoped container fixtures above execute **once per worker** — four
workers means four Neo4j containers, each with its own graph.

That per-worker isolation is what makes the destructive fixtures safe. `empty_database` runs
`delete_all_nodes`, which is a bare `MATCH (n) DETACH DELETE n` over the entire graph, and several
tests assert on global counts rather than on nodes they can identify as their own. Both are only
correct while a worker owns its database outright.

Two consequences worth remembering:

- Do not introduce cross-worker container sharing (for example testcontainers' `reuse` support, or
  keying a container off `PYTEST_XDIST_WORKER`) without first removing the whole-graph wipes.
  Sharing one database between workers makes every `empty_database` test hostile to whatever else
  is running.
- Test ordering under `--dist loadscope` (set in `addopts`) is not stable across pytest-xdist
  releases — scopes are sorted largest-first, so which modules run concurrently can change on an
  upgrade. Tests must not depend on what else is or is not running.

### One process, several Prefect servers

A test process does not keep one Prefect server. The session-scoped `prefect_test_fixture` starts
an ephemeral one for the whole session. The module-scoped `prefect` fixture reuses the
session-scoped `prefect_container`, while the class-scoped `prefect_class` starts a container per
class; both re-point `PREFECT_API_URL` at their server for the scope, so a test can end up on a
different server than the one before it. Each orchestration client a test builds reads the setting
when it is built, so it follows.

Prefect's background queue services do not. `EventsWorker` and `APILogWorker` are process-wide
`QueueService` singletons, memoized on `hash((cls, *args))`, and `EventsWorker.instance()` passes
no API URL in that key; the websocket and orchestration clients it builds in `_lifespan` read
`PREFECT_API_URL` once. Left alone it therefore stays bound to the first server of the process,
and every event after that goes to a server the process has moved off — silently while that server
is up, then as a wall of `Service 'EventsWorker' failed to process item` once it is torn down. The
backlog is expensive too: a stale queue drains at about one event per 60s client request timeout,
and `prefect_test_harness` ends the session in `drain_workers()`, which blocks with no timeout.

`prefect` and `prefect_class` handle this through `prefect_api_target()` from
`tests/helpers/prefect_services.py`, which drains the queue services on **both** sides of the
change of server: on the way in while the old URL still resolves, so queued items reach the server
they were meant for, and on the way out before the new container is stopped. Anything else that
re-points `PREFECT_API_URL` must go through it rather than calling `temporary_settings` directly.

Within a single module or class, however, pytest runs tests in definition order and
`--dist loadscope` keeps the whole scope on one worker — so the sequential, stateful `test_stepNN`
pattern used across `backend/tests/integration/` (and in component migration suites) is deliberate
and safe. Do not rewrite step tests to be order-independent; the rule above is about dependence
*across* modules, not within one.

### Base Test Classes

Located in `backend/tests/helpers/test_app.py`:

| Class | Purpose | Key Fixtures |
|-------|---------|--------------|
| `TestInfrahub` | Basic tests with DB and storage | `local_storage_dir`, `default_branch` |
| `TestInfrahubApp` | API/HTTP tests with full app context | `test_client`, `bus_simulator`, `memory_cache` |
| `TestWorkerInfrahubAsync` | Worker/Prefect tests | `prefect_server`, `prefect_client`, `work_pool` |

```python
from tests.helpers.test_app import TestInfrahubApp

class TestMyFeature(TestInfrahubApp):
    async def test_create_node(self, client: InfrahubClient, db: InfrahubDatabase):
        # Full app context available
        node = await client.create(kind="CoreTag", data={"name": "test"})
        await node.save()
```

### Test Adapters

Located in `backend/tests/adapters/`:

**Message Bus Adapters:**

```python
class BusRecorder(InfrahubMessageBus):
    """Records all messages without executing handlers"""
    messages: list[InfrahubMessage]
    messages_per_routing_key: dict[str, list[InfrahubMessage]]

class BusSimulator(InfrahubMessageBus):
    """Records messages AND executes their handlers"""
    # Same as BusRecorder plus handler execution
```

Usage example:

```python
async def test_message_sent(bus_simulator: BusSimulator, ...):
    # Perform action that should send a message
    await some_action()

    # Verify message was sent
    assert "event.branch.created" in bus_simulator.seen_routing_keys
    messages = bus_simulator.messages_per_routing_key["event.branch.created"]
    assert len(messages) == 1
```

**Other Adapters:**

- `MemoryCache` - In-memory cache for fast tests
- `FakeLogger` - Captures log output for assertions
- `RecordingLockRegistry` / `LockTimeline` - Records lock acquire/release order so tests can assert what runs inside versus outside a critical section

## Supporting Directories

### Fixtures (`backend/tests/fixtures/`)

Test data and fixture files:

- `schemas/` - JSON schema definitions (15+ directories)
- `repos/` - Git repository fixtures
- `infrahub-demo-edge` - Complete demo repository
- `*.tar.gz` - Pre-built fixture archives

### Helpers (`backend/tests/helpers/`)

| File | Purpose |
|------|---------|
| `test_app.py` | Base test classes |
| `test_worker.py` | Worker test base class |
| `test_client.py` | HTTP test client wrapper |
| `utils.py` | Container utilities |
| `constants.py` | Port numbers, image names |
| `prefect_services.py` | Rebinds Prefect's process-wide queue services when the test process changes Prefect server (`prefect_api_target`). See [One process, several Prefect servers](#one-process-several-prefect-servers). |
| `file_repo.py` | Builds throwaway on-disk Git "remote" repos from `repos/` fixtures (`FileRepo`). The remotes accept pushes to their checked-out branch, so tests exercise push and write-back like a hosted remote would. |

### Test Data (`backend/tests/test_data/`)

Reusable datasets:

- `dataset01.py` - Basic test dataset (Person, Car, Group)
- `dataset03.py` - Complex schema dataset
- `dataset04.py` - Additional test data

## Fixture Patterns

### Fixture Scoping Flow

```text
Container (session)
    └── Config (module)
        └── DB connection (module)
            └── Empty database (function)
                └── Default branch (function)
                    └── Schema registration (function)
                        └── Test
```

### Key Root Fixtures

| Fixture | Scope | Purpose |
|---------|-------|---------|
| `neo4j` | session | Neo4j container and port mapping |
| `db` | module | InfrahubDatabase connection |
| `empty_database` | function | Clears DB, creates root node |
| `default_branch` | function | Creates default + global branches |
| `register_core_models_schema` | function | Registers core schema |

### Schema Fixtures

Registered schemas come from fixtures in `backend/tests/conftest.py`. Derive a variant the way
`dev/guidelines/backend/testing.md` §"Test Schemas" prescribes for the `tests/helpers/schema/`
constants: `deepcopy` the unregistered fixture, never edit a shared one, and promote to
`conftest.py` only what several modules need.

| Fixture | Description |
|---------|-------------|
| `car_person_schema` | Basic registered schema with TestCar and TestPerson nodes |
| `car_person_schema_unregistered` | Unregistered version for custom modifications |
| `car_person_schema_branch_local` | Schema with branch-local support |
| `register_core_models_schema` | Core Infrahub models only |
| `register_core_models_schema_scope_class` | Class-scoped variant of the above |

When several tests share an expensive schema/data load, group them in a class and use the
`_scope_class` variant with `@pytest.fixture(scope="class")` fixtures for the data; methods run in
definition order and may build on accumulated state.

JSON schemas under `backend/tests/fixtures/schemas/` load through the test helper:

```python
schema_dict = helper.schema_file("infra_simple_01.json")
await client.schema.load(schemas=[schema_dict])
```

## Prefect Testing Patterns

### Calling Flows in Unit Tests (`.fn`)

`@flow`-decorated functions are wrapped in a Prefect `Flow` object. Calling them directly would create an actual Prefect flow run. Use `.fn` to access the original unwrapped coroutine:

```python
from infrahub.webhook.tasks.invalidate import invalidate_webhook_headers

# .fn bypasses Prefect orchestration — calls the plain async function
await invalidate_webhook_headers.fn(event_type="infrahub.node.updated", event_data={"node_id": "kv-123"})
```

Note: `.fn` is a dynamic attribute set at runtime by Prefect's decorator — IDEs and type checkers cannot resolve it.

### Logging: Use `caplog` Instead of Mocking `get_run_logger`

Prefect's `get_run_logger()` returns a Prefect-specific logger. In unit tests (via `.fn`), patch it to return a standard `logging.getLogger()` and use pytest's `caplog` for assertions:

```python
import logging
from unittest.mock import patch

import pytest

LOGGER_NAME = "infrahub.my_module.tasks"

@pytest.fixture(autouse=True)
def _patch_prefect_logger():
    with patch(
        "infrahub.my_module.tasks.get_run_logger",
        return_value=logging.getLogger(LOGGER_NAME),
    ):
        yield

async def test_logs_warning(caplog: pytest.LogCaptureFixture) -> None:
    with caplog.at_level(logging.WARNING, logger=LOGGER_NAME):
        await my_flow.fn(...)
    assert "expected message" in caplog.text
```

### Prefect Server State Outlives the Test Class

The Prefect test server is session-scoped — one per xdist worker — while the database and the
fixtures that populate it are class-scoped, so whatever a class registers on that server survives
it. Two rules follow:

- Delete the automations a class created at its teardown. A surviving all-branches webhook
  automation turns every event any later test emits into a scheduled flow run — no worker runs in
  the functional suite, so nothing executes them — filling the server's SQLite database.
- Never assert on a flow-run count. `read_flow_runs()` returns at most `PREFECT_API_DEFAULT_LIMIT`
  (200) rows and the API rejects a larger `limit`, so once that page is full a before/after
  comparison saturates and can never be true again. Read newest-first
  (`FlowRunSort.EXPECTED_START_TIME_DESC`) and identify the run by its id or parameters instead.

### A Component Test Process Talks to Two Prefect Servers

There is no single "the Prefect server" in a component test process. Two fixtures each provide one,
and which is current depends on the fixtures the test asked for:

| Fixture | Scope | Server |
|---------|-------|--------|
| `prefect_test_fixture` (autouse, `component/conftest.py`) | session | ephemeral `prefect_test_harness` subprocess |
| `prefect` (`tests/conftest.py`) | **module** | `prefect_container`, via a `temporary_settings` override of `PREFECT_API_URL` |

The `prefect` override lasts only as long as the module that requested it. A test that does not
depend on `prefect` therefore falls back to the harness server, even in a process where the
container is running — `component/api/conftest.py::workflow_local` and
`TestInfrahubApp.workflow_local` sit on opposite sides of this line.

**Tests register the task manager through `setup_task_manager_once()`, never the raw
`setup_task_manager()`.** The raw call redoes every block, worker pool, deployment and builtin
trigger against the current server with no timeout of its own; under CI load it hangs until
pytest-timeout kills the whole class. The helper runs the registration once per server, bounded,
and fails fast for that server afterwards.

**Never memoize server-side registration per process.** The registration goes to whichever server is
current, so a process-wide "already done" flag lets the first server's setup satisfy fixtures pointing
at the second, which then has no deployments and fails far from the cause. The helper keys its memo
on `get_current_settings().api.url`; anything else cached against a Prefect server needs the same key.

### Swapping the Workflow Adapter for a Test Double

Every class-scoped fixture that installs a `WorkflowLocalExecution` or a `WorkflowRecorder` goes
through `tests/helpers/workflow_override.py::override_workflow`. It sets both places a lookup can
come from — `config.OVERRIDE.workflow` and the `build_workflow` override in the dependency
provider — and puts the *previous* values back in a `finally`. Do not hand-roll a class-scoped swap
with `dependency_provider.scope`: that context manager pops its override instead of restoring the
one it replaced, and neither it nor `config.OVERRIDE` is restored when the fixture is finalised
through an exception, so the double leaks into whatever the next class builds.

A per-test swap of any dependant (`build_workflow`, `build_database`, `build_cache`, …) goes through
`tests/helpers/dependency_override.py::override_dependency` when anything can raise inside the block —
a `pytest.raises` around the call under test, or an assertion inside it. `dependency_provider.scope`
pops its override on the statement after its `yield`, with no `finally`, so an exception thrown
through it leaves the double installed for the rest of the xdist worker process. The next class on
that worker whose app resolves `get_workflow()` before its own override is in place then starts with
a `WorkflowRecorder` as its workflow and every one of its tests errors at `client` setup with
`These tests are currently meant to run with a local worker`; which class that is depends on how
xdist split the suite, so the failure moves between runs while the message stays the same. A
`dependency_provider.scope` whose body cannot raise is still fine: it leaves `config.OVERRIDE.workflow`
alone, so once it pops, lookups fall back to the adapter the class installed.

The app built by `test_client` resolves its workflow once, during `lifespan`. pytest orders autouse
fixtures by name, so `service` (and with it `test_client`) would otherwise run before
`workflow_local`; `TestInfrahubApp.service` therefore depends on `workflow_local` explicitly, and a
subclass that swaps in a different adapter must do the same for the app to see it.

### Functional Tests with `TestInfrahubApp`

`TestInfrahubApp` provides a `memory_cache` fixture (class-scoped) that injects a `MemoryCache` via `dependency_provider.scope(build_cache, ...)`. Use it in functional tests to pre-fill and assert on cache state:

```python
from tests.helpers.test_app import TestInfrahubApp

class TestMyFeature(TestInfrahubApp):
    async def test_cache_cleared(self, memory_cache: MemoryCache, ...) -> None:
        await memory_cache.set(key="webhook:abc", value='{"cached": true}')
        # ... trigger invalidation ...
        assert await memory_cache.get(key="webhook:abc") is None
```

## Running Tests

```bash
# Unit tests
uv run invoke backend.test-unit

# Integration tests
uv run invoke backend.test-integration

# Run specific test file
uv run pytest backend/tests/unit/path/to/test.py -v
```

## See Also

- [Backend Architecture](architecture.md) - Overall backend structure
- [Python Coding Standards](../../guidelines/backend/python.md) - Code style requirements
- [Backend AGENTS.md](../../../backend/AGENTS.md) - Commands reference
