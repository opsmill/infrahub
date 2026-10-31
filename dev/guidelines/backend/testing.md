# Python Testing Standards

> Part of: `dev/guidelines/backend/` | Related: [Python Standards](python.md)

Testing standards for the Python backend.

## Test Organization

Choose the smallest tier that can detect the failure you care about. Classify the behavior and the
collaborators it exercises, not the source module's name or the number of classes it calls.

| Tier | Behavior it proves |
|------|--------------------|
| Unit (`tests/unit/`) | In-memory decisions, parsing, validation, and transformations; no database or network access. Local files and injected recording/failing adapters are allowed. |
| Component (`tests/component/`) | A focused component working with real infrastructure: query results, persistence, constraints, cache operations, or lock coordination. |
| Functional (`tests/functional/`) | Several components working together in one process, with async tasks executed inline. |
| Integration Docker (`tests/integration_docker/`) | Behavior requiring the deployed services or separate workers. |

`tests/integration/` also contains older functional tests; see the
[infrastructure reference](../../knowledge/backend/testing.md#integration-tests-backendtestsintegration).

A database query and its result mapping belong in a component test against the real database,
directly or through their caller. Do not fabricate `QueryResult` rows to unit-test the mapping.
An independently complex transformation can have unit cases, with real query/result coverage retained.
A retry policy using scripted HTTP responses can be a unit test; the server's actual deletion and
transaction behavior require component coverage. SQLite is a real database even when embedded.

Remove unused database fixtures from a policy test instead of moving an expensive fixture into the
unit suite. Keep one real integration path when it verifies wiring that the adapters cannot prove.
For a worked decision process, see [Choosing tests](../../guides/backend/choosing-tests.md).

### Where a test goes

A unit test mirrors the source path: `backend/infrahub/core/node/standard.py` → `backend/tests/unit/core/node/test_standard.py`. A component test goes in the topic directory of its area — a node metadata query in `backend/tests/component/graphql/metadata/`, not appended to `test_graphql_query.py` — and starts a new module there when no module fits, so the next coverage check finds it beside the tests of the same feature.

For local Docker-suite setup, see
[Running integration_docker tests locally](../../guides/backend/choosing-tests.md#running-integration_docker-tests-locally).

## Test Documentation

Tests are behavioral specifications. Write them to describe **what the system should do**, not which bug prompted the test.

- **Do not reference issue numbers, GitHub URLs, or Jira tickets** in test code (names, comments, or docstrings). The git history links commits to issues.
- **Do not describe which bug a test prevents.** Describe the expected behavior instead.

## What not to test

Every test costs maintenance. Before adding one, ask whether it actually exercises behavior the project owns.

Skip tests that only assert third-party behavior:

- **Pydantic field constraints** (`ge`, `le`, `min_length`, `max_length`, etc.) — these are exercised by Pydantic's own test suite. Asserting that `Field(ge=1)` rejects `0` tests Pydantic, not us.
- **Pure assignment round-trips** — constructing a model with a value and asserting the attribute reads back the same value tests Python, not our code.
- **`SettingsConfigDict` plumbing** — asserting that an `env_prefix` exists or that `env_nested_delimiter` is set tests Pydantic Settings configuration, not behavior. Test the behavior you care about (an env var resolves to the right field) instead.
- **Plain `Enum` value checks** — asserting `MyEnum.FOO.value == "foo"` only tests that the enum literal matches itself.

Skip tests that test the framework rather than our integration:

- A test that only asserts a FastAPI route appears in `router.routes` duplicates `APIRouter`'s own contract — write it only when the registration goes through non-trivial conditional logic.
- A test that only asserts a Pydantic model has a particular field duplicates the type system.

A useful rule of thumb: if the test would still pass after we delete our implementation and reinstall the library, the test belongs to the library, not us.

**Skip tests that string-match a feature query's generated text.** A test asserting the built Cypher contains or equals a given string pins the implementation, not the behavior: it breaks on a harmless rewording and still passes on a query that is wrong in ways the string never captured. Assert the query's observable behavior (a component test against the database), and state the reasoning behind the query's shape in its own comments or docstring. Exact query-text assertions belong only where the string *is* the output contract — the query-building infrastructure itself (assembly, parameter interpolation).

**The exception is a bound that encodes a domain invariant.** `Field(ge=1)` on a multiplier that must never shrink the value it scales is not arbitrary tuning — it is a rule about how the feature behaves, and deleting it changes behavior with nothing failing. Assert those, but write the test against the invariant rather than the mechanism: name it for the rule, not for the constraint (`test_<what must hold>`, not `test_field_rejects_zero`), cover the boundary value that must stay legal, and add a test that the **shipped defaults** satisfy the invariant. Cross-field `model_validator` logic is ours outright and always warrants a test.

### Redundant coverage

Treat a test as redundant when removing it loses no distinct behavior, boundary, failure mode, or
useful focused diagnosis that the retained tests assert. Shared setup, similar names, or execution
of the same production lines do not establish redundancy.

Before adding or removing a test, trace the callers to existing assertions. A search for the class
name alone misses coverage through a resolver or manager. Name the retained test and the regression
it catches; if the scenario is missing, extend the existing test at the tier that owns the behavior.

- Keep unit policy cases and a component wiring case when they catch different failures. Do not
  repeat the whole policy matrix through every caller or through the full stack.
- Parameterize repeated setup and assertions when inputs exercise distinct cases. Parameterization
  removes duplicated code; it does not make equivalent cases useful.
- Remove a separate accessor test when a real query test already asserts that mapping. Add unit
  cases only for independently meaningful transformation logic.
- Keep client protocol assertions separate from CLI output/exit assertions: either can fail while
  the other remains correct. Assert exact requests when a scripted transport cannot reject a wrong
  method or URL by itself.

Use the [redundancy review procedure](../../guides/backend/choosing-tests.md#review-overlapping-tests)
to compare failure modes before deleting coverage. The rules for third-party behavior above and
[independent expected values](#assert-exact-expectations) still apply.

## Async tests

The project sets `asyncio_mode = "auto"` in `pyproject.toml`, so any `async def test_*` function is automatically driven by `pytest-asyncio`. **Do not** wrap async code in `asyncio.run(...)` inside synchronous tests — declare the test function `async` and `await` directly:

```python
# Good
async def test_returns_config() -> None:
    cfg = await get_config()
    assert cfg.ldap.enabled is False

# Bad — wraps the event loop unnecessarily
def test_returns_config() -> None:
    cfg = asyncio.run(get_config())
    assert cfg.ldap.enabled is False
```

## One database session per concurrent path

A Neo4j session carries a single connection and cannot serve two coroutines at once, and everything reached through one `InfrahubDatabase` shares its session. Racing two calls on the same one wedges the connection: one coroutine raises `read() called while another coroutine is already waiting for incoming data`, the other parks on the socket where `asyncio.wait_for` cannot cancel it. `db` is module-scoped, so the wedge takes every later test in the module with it.

```python
# Good - a session per racing call
async with db.start_session() as db_1, db.start_session() as db_2:
    await asyncio.gather(build_coordinator(db_1).update(), build_coordinator(db_2).update())

# Bad - both calls queue on the module's one connection
coordinator = build_coordinator(db)
await asyncio.gather(coordinator.update(), coordinator.update())
```

Code that opens a session of its own is safe to race: flows do, pinned by [`test_flow_session_convention.py`](../../../backend/tests/unit/workflows/test_flow_session_convention.py), and so do GraphQL query resolvers (see [GraphQL Execution Paths](../../knowledge/backend/graphql-execution.md#a-query-resolver-opens-its-own-database-session)). A component a test calls directly does not.

## Test Schemas

Search for an existing schema before defining one in a test, and search by the shape the test needs (an optional cardinality-one relationship to a generic, a hierarchy), not by name. Shared schemas live in two places:

- [`tests/helpers/schema/`](../../../backend/tests/helpers/schema/): node and generic constants (`CAR`, `DEVICE`, `TAG`, `PERSON`) and `SchemaRoot` bundles (`CAR_SCHEMA`, `DEVICE_SCHEMA`, `LOCATION_SCHEMA`), registered with the `load_schema` helper
- the schema fixtures in `backend/tests/conftest.py` and `backend/tests/component/conftest.py`, such as `car_person_schema`, `generic_car_person_schema` and `hierarchical_location_schema`

```python
# ❌ Bad - a new inline schema for an optional cardinality-one relationship to a generic
raw_schema = {"generics": [{"name": "Vehicle", ...}], "nodes": [{"name": "Rider", ...}]}

# ✅ Good - generic_car_person_schema already has one: TestPerson.car -> TestCar
async def test_person_without_car(db: InfrahubDatabase, default_branch: Branch, generic_car_person_schema: None) -> None: ...
```

When a shared schema almost fits, `deepcopy` it and change the copy (`car_with_mileage = deepcopy(CAR)`, then append the attribute). Never modify a shared schema for one test, because every test that uses it changes too. Keep a schema that only one module needs in that module, and promote it to `tests/helpers/schema/` or a `conftest.py` only when several modules use it.

Give a branch a divergent schema in production order. Register an edited schema the way the API path does: `schema_branch.process()`, then `registry.schema.set_schema_branch(...)`, `branch.update_schema_hash()` and `await branch.save(db=db)`. Hashing before processing persists a hash of a schema nothing serves, and skipping the save leaves the divergence in the registry only, invisible to anything that reads the stored hash.

## Share one schema and data load across a class

When several tests or parametrized cases read the same schema and data, put them in a class and build that data once in `@pytest.fixture(scope="class")` fixtures on the `_scope_class` fixture variants, then vary the query per method or case. A function-scoped schema or data fixture runs again for every test and every parametrized case. A class-scoped fixture cannot request a function-scoped one, so a schema fixture without a `_scope_class` variant needs one added beside it. `backend/tests/component/graphql/metadata/test_graphql_query_metadata.py::TestMetadataFilters` follows this pattern; the fixture chain is in [Backend Testing — Schema Fixtures](../../knowledge/backend/testing.md#schema-fixtures).

## Pin settings the test depends on

`config.SETTINGS` is populated from `INFRAHUB_*` environment variables at process start, so values exported in the developer's shell leak into the test process. Any test whose behavior depends on a settings field must pin it in a save/restore fixture (set the value, `yield`, restore the original) — see `import_every_remote_branch` in `backend/tests/integration/git/conftest.py`. Never assume a field holds its default.

## Leave process-global state as you found it

Under `pytest-xdist` every test in a worker shares one interpreter, so whatever a test changes outside
its own fixtures stays changed for every test that follows it there. Touch global state only through a
save/restore fixture (change it, `yield`, restore the original). Pinning a setting, above, is one case
of that rule; it also covers:

- the `logging` module — root and per-logger levels, handlers, filters
- `structlog` configuration
- module-level registries, caches and singletons
- environment variables (prefer `monkeypatch.setenv`, which restores on teardown)
- `sys.path`, `sys.modules`, warning filters

**Never call an application startup routine from a test.** `infrahub.log.configure_logging` is the
example to learn from: it runs once at process start and owns the process when it does — setting the
root log level, replacing the root handler and reconfiguring structlog — so, being startup code, it has
no counterpart that undoes any of that. Called from a fixture it silently reconfigures every later test
in the worker. Install only the piece the test needs, extracting it from the startup routine when it is
not already reusable, and undo it after the `yield` — see `traceback_suppression` in
`backend/tests/helpers/log.py`, which the webhook suppression tests use to install the traceback
suppression filter alone rather than calling `configure_logging`.

Such a leak is invisible locally and expensive in CI. A root logger left at `DEBUG` overrides the
`WARNING` level `pytest_configure` pins, and the Neo4j driver then logs a line per Bolt message for
every test that follows in that worker: one job produced 185k lines of driver output and pushed three
unrelated tests past their 300s timeout.

## Dataclass Test Case Pattern

For parametrized tests with multiple scenarios, use dataclasses to define test cases. This pattern provides type safety, readable test IDs, and clear separation between test data and test logic.

### Basic Structure

```python
from dataclasses import dataclass

import pytest


@dataclass
class MyFunctionTestCase:
    name: str
    input_value: str
    expected: bool


MY_FUNCTION_TEST_CASES: list[MyFunctionTestCase] = [
    MyFunctionTestCase(
        name="empty_string_returns_false",
        input_value="",
        expected=False,
    ),
    MyFunctionTestCase(
        name="valid_string_returns_true",
        input_value="hello",
        expected=True,
    ),
]


@pytest.mark.parametrize(
    "test_case",
    [pytest.param(tc, id=tc.name) for tc in MY_FUNCTION_TEST_CASES],
)
def test_my_function(test_case: MyFunctionTestCase) -> None:
    result = my_function(value=test_case.input_value)
    assert result == test_case.expected
```

### Guidelines

1. **Always include a `name` field** as the first field in the dataclass. This becomes the test ID in pytest output, i.e. a meaningful name makes the output easier to read.

2. **Use descriptive names** that explain the scenario: `empty_dict_returns_false`, `nested_key_found_at_second_level`, `invalid_input_raises_error`.

3. **Leave a field undocumented when its name says what it holds.** An inline docstring below a
   field is for the one that needs explaining (see [Python standards](python.md#docstrings)):

   ```python
   @dataclass
   class QueryTestCase:
       name: str
       query: str
       params: dict[str, Any]
       expected_count: int
       """Rows visible on the branch, not rows matched before the branch filter."""
   ```

4. **Define test cases as module-level constants** with uppercase names and type hints
   (`QUERY_TEST_CASES: list[QueryTestCase] = [...]`), placed before the test function that uses them.

5. **Use keyword arguments** when constructing test cases —
   `MyTestCase(name="scenario_one", input_value="test", expected=True)`, never positionally.

### Complex Test Cases

Case fields can hold nested objects (a `SchemaRoot`, a list of expected error messages) — the
structure above scales unchanged; keep constructing them with keyword arguments.

### When to Use This Pattern

Reach for the dataclass test case pattern when several scenarios share one structure and only the data
varies — it keeps the pytest ids readable as the list grows.

Whichever you pick, the case data lives in the `parametrize` decorator. Don't parametrize over the keys of a module-level dict and look the values up inside the test — the reader has to hold two places in their head to see what a case actually asserts, and the pytest id no longer tells them.

For simpler cases with only 2-3 scenarios, standard `@pytest.mark.parametrize` with tuples may be sufficient:

```python
@pytest.mark.parametrize(
    ("input_value", "expected"),
    [
        ("", False),
        ("hello", True),
    ],
)
def test_simple_function(input_value: str, expected: bool) -> None:
    assert simple_function(input_value) == expected
```

## Caution against mocking

Avoid using `unittest.mock` or `pytest-mock` to patch functions, methods, or modules. Mocking creates a false sense of security: tests pass while the actual integration may be broken. When the real implementation changes, mocked tests continue to pass, hiding regression bugs.

### Prefer adapters and protocols

Instead of mocking, design code with explicit boundaries using adapters, interfaces, or protocols. This allows swapping implementations for testing without patching internals.

**Example:** The message bus uses this pattern:

- Production: [rabbitmq.py](../../../backend/infrahub/services/adapters/message_bus/rabbitmq.py) - Real RabbitMQ implementation
- Testing: [message_bus.py](../../../backend/tests/adapters/message_bus.py) - `BusRecorder` and `BusSimulator` test implementations

Both implement the same `InfrahubMessageBus` protocol. Tests inject the test adapter—no mocking required, and refactoring the RabbitMQ implementation won't silently break tests.

Two doubles are worth writing for any injected collaborator. A **recording** double — like `BusRecorder` — keeps what crossed the boundary, in order, so the test asserts the exact calls and values rather than "was called". A **failing** double raises on every call, to test the path a `Mock` never exercises: that a broken collaborator is handled the way the code claims — the operation still completes, state is intact, and anything queued behind it still runs. Keep both in the shared adapters package or a `helpers.py` beside the test package rather than redefining them per file.

### When mocking seems necessary

If you find yourself wanting to mock:

1. **Refactor for testability** - Extract the dependency behind an interface
2. **Move up the test pyramid** - A component test requiring extensive mocking to simulate an end-to-end flow is often better written as an integration or functional test
3. **Question the test scope** - If testing requires mocking half the system, the unit under test may be too large

### Don't shape production code to serve its own test

Production code must not change shape just so a test can observe it — no return value added to a
mutating method, no marker attribute stamped on a wrapper, no `type: ignore` absorbed to make a
hook attachable. If you need to verify a side effect happened, assert against the actual state it
changed — e.g. read the fake cache/store the method wrote to — rather than trusting a return value
added for that purpose.

To verify *wiring* — a convention held across a module, the right decorator applied — parse the
source instead of instrumenting it. `ast.parse` over `inspect.getsource`/`inspect.getsourcelines`
reads the shape off the tree with zero production hooks:
`backend/tests/unit/workflows/test_flow_session_convention.py` walks each registered flow's own
source for `service.database` session-opening calls, and the same technique reads decorator names
and arguments off a module tree. Behavioral coverage (does the decorator retry?) belongs on the
decorator's own tests; the wiring test only proves it is attached.

```python
# ❌ Bad - return value exists only so the test can assert on it
class StaleEntryCleaner:
    def __init__(self, cache: InfrahubCache) -> None:
        self._cache = cache

    async def clear_expired(self) -> list[str]:
        deleted = await self._cache.list_keys(filter_pattern="stale:*")
        for key in deleted:
            await self._cache.delete(key)
        return deleted          # nothing in production reads this

# ✅ Good - no return; the test asserts against the fake store it wrote to
class StaleEntryCleaner:
    def __init__(self, cache: InfrahubCache) -> None:
        self._cache = cache

    async def clear_expired(self) -> None:
        for key in await self._cache.list_keys(filter_pattern="stale:*"):
            await self._cache.delete(key)

async def test_clears_expired_entries() -> None:
    cache = MemoryCache()
    await cache.set(key="stale:1", value="value")
    cleaner = StaleEntryCleaner(cache=cache)

    await cleaner.clear_expired()

    assert cache.storage == {}   # seeded above, so an empty store is a real transition
```

### Acceptable exceptions

- External HTTP APIs with no test mode (use `responses` or `httpx_mock` sparingly)
- Prefect's `get_run_logger` when calling a `.fn` outside a flow context — patch it to return a stdlib `logging.getLogger(...)` so `caplog` can capture output. See [Backend Testing — Logging](../../knowledge/backend/testing.md#logging-use-caplog-instead-of-mocking-get_run_logger) for the pattern.

Even in these cases, prefer adapter patterns when the dependency is used widely.

### Time: inject a clock, don't freeze one

<!-- Extracted from specs/ifc-2886-priority-api-backpressure on 2026-07-26 -->

Time-dependent logic takes its clock as a constructor argument — a `Callable[[], float]`
defaulting to `time.monotonic` — and the test passes a fake it advances by hand. Do not reach for
`freezegun` (it is not a project dependency) and never `sleep()` in a test to let time pass.

```python
class RetryAfterPolicy:
    def __init__(self, *, clock: Callable[[], float] = time.monotonic) -> None:
        self._clock = clock
```

```python
class FakeClock:
    def __init__(self) -> None:
        self.now = 0.0

    def __call__(self) -> float:
        return self.now

    def advance(self, seconds: float) -> None:
        self.now += seconds
```

This keeps the unit under test a pure function of `(input, clock)`, so a state machine whose
behavior depends on elapsed time is tested exactly — cross an interval boundary, assert the
transition — with no wall-clock flakiness and no patching. Duration is a parameter of the logic,
not an ambient fact; treat it like any other injected collaborator (see
[Backend Component Design](component-design.md)).

Use monotonic time for durations. Wall-clock time (`datetime.now`) is for timestamps that get
stored or displayed, and it can jump backwards.

### Waiting on async effects: poll, don't sleep

In integration-tier tests the clock cannot be injected — a consumer or worker really does need
wall-clock time to act. Never guess that duration with a fixed `asyncio.sleep(n)` before
asserting: on a loaded CI runner the test flakes, and on a fast machine it wastes the time. Poll
the expected state in a small loop with a deadline, so the test waits exactly as long as the
outcome takes and fails with a timeout when it never arrives. Poll for the exact state the
assertion will check — the specific log line, the exact count — not for mere arrival: a loop that
exits as soon as anything shows up hands an unrelated first event to the assertion and the test
fails (or passes) spuriously.

The deadline applies to every wait, not only polls: wrap a bare `await event.wait()` in
`asyncio.wait_for(..., timeout=...)`, with margin for a loaded runner. An unbounded await turns a
regression into a whole-suite hang that only pytest-timeout ends, minutes later, with the cause
hidden.

### Never assert on elapsed time

`assert elapsed_seconds < N` encodes the speed of the machine that wrote it. It passes on a fast
runner with the regression present, flakes on a loaded one without it, and the margin narrows every
time the fixture grows, so it is both a weak guard and a source of flakes. This covers any assertion
whose outcome depends on how fast the host is, wall-clock gaps between events included.

A deadline that only bounds a wait is not such an assertion: it is a guard that turns a hang into a
fast failure, and nothing the test asserts depends on how long it took.

Hold the shape instead of the duration:

- Count the work. When a fix turns a scan into a lookup, assert the number of calls, queries or
  comparisons; a counting double fails identically on every machine.
- Keep the measurement out of the suite. The numbers that justified the change belong in the commit
  message or the pull request, where they are read once, not in an assertion CI re-runs forever.
- A `PROFILE` db-hit count is the same trap without the clock: it encodes the Neo4j planner's choice
  for the test database's statistics, not the code's behavior, so it flips when the planner replans.
  Counting the work means counting what the code under test does — calls, queries, submissions — not
  what the planner spends. Keep db-hit measurements in the pull request description, or in
  `backend/tests/query_benchmark/` when they must be tracked over time.

When the behavior under test genuinely is a schedule, inject the clock as above so the schedule
becomes a value the test reads exactly, rather than a duration it races.

## Exception Testing

When testing that code raises an exception, use the `match` parameter of `pytest.raises` to validate the error message:

```python
with pytest.raises(PoolExhaustedError, match=r"no more addresses available"):
    allocate_from_pool(pool_id=exhausted_pool.id)
```

`match` takes a regular expression — use a raw string.

## GraphQL Result Assertions

When testing GraphQL mutations or queries that return errors, always assert on the **specific error message** using an equality check. Vague assertions hide regressions — if the error changes (e.g., a different validation fires first), the test keeps passing silently.

```python
# Bad - only checks that some error occurred
assert result.errors

# Bad - a substring check passes for any error that mentions the text,
# even if the overall message changed
assert f"The template requested {{'id': '{TEMPLATE_ID}'}} was not found." in str(result.errors[0])

# Good - exact match on the error message
assert result.errors
assert str(result.errors[0].message) == f"The template requested {{'id': '{TEMPLATE_ID}'}} was not found."
```

## Assert exact expectations

The exact-match principle above is not limited to error messages — it applies to every assertion. A loose assertion passes for the wrong reason and hides regressions.

- **Assert the exact collection, not a subset or membership.** When a function returns a set/list/dict of results (deleted ids, affected targets, computed keys), assert full equality against the expected value. `assert x in result` / `assert expected.issubset(result)` pass even when the result grows or shrinks incorrectly. If the result is deterministic, `assert result == {…}` (or exact set equality) catches both missing and extra items.
- **Don't stop at non-emptiness when a specific result is expected.** `assert result` fits an existence-only contract only; otherwise assert the specific expected value. `assert result != frozenset()` is `True` for an empty `list`/`dict`, so it does not even establish non-emptiness.
- **Compare unordered results by key, and assert the row count.** Build a dict keyed by id on both sides instead of sorting both lists, and assert `len(result)` first: a dict comprehension silently collapses duplicate rows.
- **Assert a positive count where the number matters.** A test that only checks "no failures" can pass while measuring zero of the thing it claims to test — e.g. if a workflow/name string changes so nothing is counted. Assert that the expected count is `> 0` (or the exact number) so a silently-zero run fails.
- **Make the scenario actually hold.** A "missing row" test must not create the row; a "no second object" test must prove the count is one. Verify the setup produces the state under test. The fixture must also let each clause fail on its own: a secondary sort key is only exercised by cases that tie on the primary one, and a chunked read only covers the partial final chunk when the fixture size is not an exact multiple of the chunk constant — derive the size from that constant rather than hard-coding a round number.
- **Cover branch-scoped operations from a user branch too.** Running the operation only on the default branch cannot show cross-branch leakage. Add the user-branch case and assert the other branch is untouched — after a branch-side removal the default branch still resolves its value; after a default-branch change a pre-existing branch still sees its own.
- **Make removal assertions branch-attributable.** A "data is gone" check must read on the branch that held the data, and assert the data resolved *before* the operation as well as after — a read on the wrong branch raises the same not-found either way, so the assertion passes whether or not the code ran.
- **Denial tests must verify nothing changed.** When asserting an operation is rejected, also reload the target and assert its state is unchanged (or that no row was created/deleted). Asserting only that an error was returned does not prove the write was actually blocked.
- **When a result is reachable via more than one code path, assert an intermediate signal too.** If "the lookup was never attempted" and "the lookup ran and found nothing" converge on the same final value (e.g. both produce an empty filter), asserting only that final value can't tell a working implementation from a regressed one that silently skipped the lookup. Also assert what was queried or which branch ran — a signal only the intended path produces.
- **Assert persistence from storage, not from the layer the code wrote.** When the contract is that state reaches (or is restored in) the database, reload it from the DB (e.g. `Branch.get_by_name` and check `active_schema_hash`) instead of reading back the in-memory registry/cache the code under test updated — that assertion is self-confirming and cannot detect a failure to persist.
- **Pin literal expected values — don't derive them with the code's own logic.** Computing the expectation with the same serializer, formatter, or formula the implementation uses (`ujson.dumps`, `yaml.dump`, the function under test itself, a mirrored `min(...)`/hash expression, a baseline constant computed the same way as the code) makes the assertion a tautology: it moves with the bug and passes either way. Write the raw expected value into the test, or obtain the baseline from a source independent of the path under test.
- **A fixture copied from a live file needs a sync assertion.** When tests read expectations from a hand-maintained copy of a real config file, add one test asserting the copy equals the live file — otherwise the real file changes, the copy goes stale, and every test keeps passing.
- **A "does not raise" test still needs an assertion.** When the contract is that an exception is swallowed, also assert a side effect that only the guarded path produces (state set before the raiser was called). With no assertion, a regression that returns early before the guard passes identically.

## Graph integrity assertions

Tests that write to the graph — migrations, merges, deletes, rebases — should assert that the graph is
still structurally sound afterwards. `infrahub.database.validation` exposes a single entry point for that:

```python
from infrahub.database.validation import collect_graph_violations, verify_graph

await verify_graph(db=db)                      # raises GraphValidationError listing every violation found
await verify_graph(db=db, kinds=["TestCar"])   # only vertices carrying one of these labels
```

It runs every graph-integrity check (duplicate paths, duplicate relationships, duplicate attributes, edges
added after a node delete, orphaned active edges under a deleted parent, relationship edge counts) and
reports all violations together rather than stopping at the first failing check. Do not call the individual
checks — a suite that picks a subset silently stops covering the rest.

Use `kinds` to scope large-graph runs to the kinds a suite actually touches. Checks anchored on an
`Attribute` or `Relationship` vertex resolve the label through the `Node` the vertex hangs off.

When a test asserts that a damaged state *exists* (a migration's "before" state, for example), use
`collect_graph_violations(...)`, which returns the violations instead of raising, and assert on the exact
checks reported.

## See Also

- [Python Standards](python.md) - General Python coding standards
- [Backend Architecture](../../knowledge/backend/architecture.md) - Backend architecture overview
