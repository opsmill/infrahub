# Infrahub backend test review

Flag violations of these Infrahub conventions in `backend/tests/**` and `python_testcontainers/tests/**`. Ruff already enforces annotations, `pytest.raises` breadth (PT011) and the parametrize types, and bans `setup_task_manager`, so do not repeat those. Review only added or changed lines.

## No mocking

- Flag new `unittest.mock`, `MagicMock`, `Mock`, `patch` and `mocker` usage. Inject an adapter or protocol double instead (see `BusRecorder`/`BusSimulator` in `tests/adapters/`). The only exceptions are an external HTTP API with no test mode (`httpx_mock`/`responses`) and patching Prefect's `get_run_logger` when calling `.fn` outside a flow.
- Flag a "was called" check on a double. A `Recording*` double should assert the exact calls and values, in order.
- Flag code that claims to survive a collaborator failing but has no `Failing*` double test proving it.
- Flag production code changed so a test can observe it: a return value added to a mutating method, a marker attribute, or a `type: ignore` added for a hook. Assert on the state the code changed. To check wiring (which decorator is applied, with which arguments), parse the source with `ast` + `inspect.getsource`.
- Flag `freezegun` and `time.sleep`/`asyncio.sleep` used to make time pass. Inject a clock (`Callable[[], float]`, default `time.monotonic`) and advance a fake one.

## Assertions

- Flag `pytest.raises` with no `match`, or a `match` that pins only a fragment of a stable message. Anchor it with `^...$`, and match a substring only when part of the message genuinely varies.
- Flag GraphQL error checks that use truthiness or `in`. Compare exact messages:
  ✅ `assert [e.message for e in result.errors] == ["You do not have the permission ..."]`
- Flag `x in result`, `issubset`, `len(x) > 0`, `assert result` or `!= frozenset()` when the result is deterministic. Assert full equality.
- Flag an assertion that joins two acceptable outcomes with `or`. It means the behavior is not known.
- Flag a "no failures" check that passes when zero items were processed. Assert the exact or a positive count.
- Flag an expected value computed with the same serializer the code uses (`ujson.dumps`, `yaml.dump`, the function under test). Pin a literal.
- Flag a denial or permission test that only checks the error. It must also reload the target and assert it is unchanged.
- Flag a persistence check that reads back the in-memory registry or cache the code wrote. Reload from the database.
- Flag a removal check that reads on the wrong branch, or does not show the data resolved before the operation.
- Flag a "does not raise" test with no assertion on a side effect.
- Flag a setup that does not produce the state under test (a "missing row" test that creates the row).
- Flag a result reachable by two code paths ("lookup skipped" and "lookup found nothing") where the test checks only the final value. Also assert an intermediate signal.
- Flag `assert elapsed < N`, or any assertion on wall-clock gaps. Count the work instead (calls, queries).
- Flag a regression-guard test whose PR gives no evidence it fails when the fix is reverted. Flag a `strict=True` xfail that holds invariants which should pass today.
- Flag graph-writing tests (migrations, merges, deletes, rebases) that call individual integrity checks. Use `verify_graph(db=db)`, or `collect_graph_violations` for an expected-damage state.

## What not to test

- Flag tests that only exercise a library: Pydantic `ge`/`min_length`, an assignment round-trip, `SettingsConfigDict`/`env_prefix`, `MyEnum.FOO.value == "foo"`, "a model has field X", or "a route is in `router.routes`". The test is: if it would still pass with our implementation deleted, it is testing the library.
- A bound that encodes a domain invariant is the exception. It needs a test named for the rule, covering the legal boundary value and the shipped defaults. `@model_validator` logic always gets a test.

## Tier, async and concurrency

- Flag a component or integration test (DB fixtures, containers) for logic that works on in-memory inputs (a `SchemaBranch`, a dataclass, a pure function). Use a unit test, extracting a pure function if needed.
- Flag `asyncio.run(...)` inside a sync test. Pytest runs in `asyncio_mode=auto`, so write `async def test_...` and `await`.
- Flag `asyncio.gather` that races calls sharing one `db`. Give each call its own `db.start_session()`, since sharing wedges the module-scoped session. Flows and GraphQL open their own sessions and are safe to race.
- Flag a fixed `asyncio.sleep(n)` before an assertion. Poll with a deadline for the exact expected state.
- Flag an unbounded `await event.wait()`. Wrap it in `asyncio.wait_for(timeout=...)`.

## Global state and fixtures

- Flag changes to `logging` levels, handlers or filters, `structlog` config, module registries or singletons, class attributes, `sys.path`/`sys.modules`, or env vars that are not undone by a save/`yield`/restore fixture or `monkeypatch`. Under xdist, leaked state reaches every later test in the worker.
- Flag calls to application startup code (`configure_logging`) from tests. Install only the piece under test, then remove it after the `yield`.
- Flag `dependency_provider.scope` around code that may raise. Use `override_dependency` or `override_workflow` from `tests/helpers/`.
- Flag tests that read a `config.SETTINGS` field without pinning it in a save/restore fixture. `INFRAHUB_*` values from the developer's shell leak in.
- Flag a new inline test schema when a helper in `tests/helpers/schema/` fits. Derive variants with `deepcopy`, and flag edits to a shared helper made for a single test.
- Flag SDK-driven tests that use `cast()`, `getattr()` or `type: ignore` to reach node attributes. Generate protocols for the test schema. Don't copy the `tests/e2e` ty opt-out.
- Flag `Recording*`/`Failing*` doubles redefined in each file. Share them in `tests/adapters/` or a `helpers.py`.

## Parametrize and naming

- Flag multi-scenario parametrize written as tuples. Use a dataclass test case whose first field is `name`, fed through `pytest.param(tc, id=tc.name)`, with cases kept in a typed, uppercase module constant placed before the test.
- Flag test cases constructed with positional arguments.
- Flag parametrizing over a dict's keys and looking the values up inside the test.
- Flag vague case names. A name should describe the scenario, such as `empty_dict_returns_false`.
- Flag issue numbers, Jira keys, GitHub URLs or spec IDs in test names, docstrings or comments, and wording that describes the bug fixed instead of the behavior expected.
- Flag test files that don't mirror their source path (`infrahub/core/node.py` → `tests/unit/core/test_node.py`).

## Do NOT flag

- Existing mock usage on unchanged lines. About 88 legacy files use it.
- Plain tuple parametrize for 2-3 simple scenarios.
- `asyncio.wait_for` deadlines, which bound a wait and are not timing assertions.
- `match=` on a substring when the message contains an id, path or count.
- Tests of Pydantic bounds that encode a named domain invariant, or of shipped defaults.
- The one test that calls the raw `setup_task_manager` to test the setup itself.

Sources: dev/guidelines/backend/testing.md, .agents/rules/testing-python.md, dev/guidelines/backend/python.md, backend/AGENTS.md, AGENTS.md, pyproject.toml
