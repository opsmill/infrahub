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

**When to use:** Testing smaller functions that doesn't require network services.

### Component Tests (`backend/tests/component/`)

Many tests leverage the database and use TestContainers for external dependencies.

**Characteristics:**

- Uses TestContainers for Neo4j, Redis, etc.
- Module-scoped containers for faster execution
- Tests individual components with database interaction
- Fast feedback loop

**When to use:** Testing business logic that requires database state but doesn't need the full application context.

### Functional Tests (`backend/tests/functional/`)

Multi-component tests running in a single thread/process. Async tasks execute inline without separate workers.

**Characteristics:**

- Single thread/process execution
- Async tasks run inline (no separate workers needed)
- Full debuggability with breakpoints
- Uses `prefect_test_harness` for Prefect integration

**When to use:** Testing features that span multiple components, including async workflows, while maintaining the ability to debug.

### Integration Tests (`backend/tests/integration/`)

> **Note:** Currently contains tests that should be migrated to `functional/`. The directory is being transitioned to hold only true distributed integration tests.

### Integration Docker Tests (`backend/tests/integration_docker/`)

True distributed tests with multiple Docker containers running the full Infrahub stack.

**Characteristics:**

- Uses SDK's `TestInfrahubDockerClient` base class
- Starts full Infrahub environment (server, workers, database)
- Slowest but most realistic testing
- Tests real distributed behavior

**When to use:** Testing behavior that requires actual distributed execution, like computed attributes, triggered actions, or schema migrations in production-like environments.

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
