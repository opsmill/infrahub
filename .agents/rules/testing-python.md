---
paths:
  - "backend/tests/unit/**/*.py"
  - "backend/tests/component/**/*.py"
  - "backend/tests/functional/**/*.py"
  - "backend/tests/integration/**/*.py"
  - "backend/tests/integration_docker/**/*.py"
  - "python_testcontainers/tests/**/*.py"

---

# Python Testing Rules

Full reference: `dev/guidelines/backend/testing.md`

## No mocking

Do NOT use `unittest.mock`, `pytest-mock`, `MagicMock`, `patch`, or `Mock`.

Use adapter/protocol patterns instead. The message bus demonstrates this:

- Production: `backend/infrahub/services/adapters/message_bus/rabbitmq.py`
- Testing: `backend/tests/adapters/message_bus.py` (`BusRecorder` / `BusSimulator`)

Both implement `InfrahubMessageBus`. Tests inject the test adapter — no patching.

Two doubles are worth writing for an injected collaborator: a `Recording*` one that keeps the calls in order (assert the exact sequence and values, not "was called"), and — where the code claims to survive that collaborator failing — a `Failing*` one that raises, to prove the claim.

Acceptable exceptions only:

- External HTTP APIs with no test mode: use `httpx_mock` or `responses`
- Prefect's `get_run_logger`: when calling a Prefect-decorated function via `.fn` outside a flow context, patch `get_run_logger` to return a stdlib `logging.getLogger(...)` so `caplog` can capture output. See `dev/knowledge/backend/testing.md` for the full pattern.

Time-dependent logic takes its clock as a `Callable[[], float]` defaulting to `time.monotonic`, and the test passes a fake it advances; never reach for `freezegun`, which is not a project dependency. Full guidance in `dev/guidelines/backend/testing.md` §"Time: inject a clock, don't freeze one".

## Parametrized tests

Use the dataclass pattern, not tuples. First field must be `name` — it becomes the pytest ID. Always use keyword arguments when constructing test cases.

## Exception testing

Always use the `match` parameter of `pytest.raises`:

```python
with pytest.raises(SomeError, match=r"expected message"):
    call_function()
```

Make `match` cover the whole stable message (anchor with `^...$` where practical), not a short fragment of it. A fragment passes even when the rest of the wording regresses. Match only a substring when the message has a genuinely variable part (an id, a path, a count) that you cannot pin down.

## GraphQL error assertions

Assert on the exact message with `==`, not substring checks with `in`. Vague checks hide regressions when error wording changes. This covers a query result's `errors` list too, not only raised exceptions:

```python
# ❌ passes for any error — or, when data is also empty, for none at all
assert result.errors or result.data["edges"] == []
# ✅ pins exactly what the API returned
assert [error.message for error in result.errors] == ["You do not have the permission to update this preference"]
```

The full-message-over-fragment preference applies to any exception assertion, not just GraphQL; with `pytest.raises` express it through an anchored `match` (above) rather than `==`.

## Assert exact expectations

Exact-match is not only for error messages. Assert the exact collection (full set/dict equality, not `in`/`issubset`), never mere non-emptiness (`!= frozenset()`, `len() > 0`), and a positive count where the number matters (so a run that silently measures zero fails). Never `or` two acceptable outcomes in one assertion — if you cannot say which one the system produces, you do not yet know the behavior under test. A denial test must also reload the target and assert nothing changed. Pin literal expected values — never compute the expectation with the same serializer/library the implementation calls. Full guidance in `dev/guidelines/backend/testing.md` §"Assert exact expectations".

- A persistence check reloads from the database, not from the registry or cache the code wrote. A removal check reads on the right branch and first shows the data resolved before the operation.
- A "does not raise" test also asserts a side effect, and a setup produces the state under test (a "missing row" test does not create the row).
- When two code paths reach the same result ("lookup skipped" and "lookup found nothing"), also assert a signal that tells them apart.
- A test that writes to the graph (migration, merge, delete, rebase) checks integrity with `verify_graph(db=db)`, or `collect_graph_violations` for an expected-damage state, not individual checks.
- Share `Recording*`/`Failing*` doubles in `tests/adapters/` or a `helpers.py`; do not redefine them in each file.

Not violations: mock usage on unchanged lines (about 88 legacy files use it); a plain tuple `parametrize` for two or three simple scenarios; `match=` on a substring when the message contains an id, path or count; tests of Pydantic bounds that encode a named domain invariant or the shipped defaults.

## Don't test the framework

Skip tests that only exercise library behavior: plain `Enum` value/round-trip checks, Pydantic field constraints (`ge`, `min_length`, …), `SettingsConfigDict`/env plumbing, or "a model has field X". Rule of thumb: if the test would still pass after deleting our implementation and reinstalling the library, it belongs to the library. See `dev/guidelines/backend/testing.md` §"What not to test".

## Pick the cheapest test tier

If the logic needs only in-memory inputs (a `SchemaBranch`, a dataclass, a pure function), write a unit test without DB fixtures — don't default to a component test because a neighbor uses one. Use the database or containers only when behavior genuinely depends on them. When the changed logic seems to need the full integration fixture, first check whether it can be extracted as a pure function over directly-constructible data and unit-tested there. The converse holds for a `Query` subclass: the rows it reads back are database behavior, so it is covered at the component layer against the real database — directly or through its caller — never by a unit test that hand-builds `QueryResult` rows.

## Check existing coverage before adding a test

Trace the code's callers to the test that asserts their output; a grep for the class or method name is not a coverage check, because the component suite drives most core classes through the resolver or manager that calls them. If that test already asserts the behavior, do not add a second test for it; if it leaves a case unasserted, add the case there. See `dev/guidelines/backend/testing.md` §"What not to test".

## Wiring tests parse source, never instrument it

Never add a marker, attribute, or `type: ignore` to production code so a test can observe it. To assert wiring or a convention (the right decorator applied, with the right arguments), parse the module with `ast` + `inspect.getsource` — see `backend/tests/unit/workflows/test_flow_session_convention.py`.

## A regression guard must be shown to bite

Before trusting a test that pins a fix or an optimization, run it against the code without the change (revert it, or reintroduce the old call) and watch it fail — a guard that passes on both sides asserts nothing, and several have. State the check in the PR ("fails with X when the fix is reverted"). A `strict=True` xfail swallows every assertion in its body, so it holds only the expected failure; invariants that must hold today go in a passing test.

## Never assert on elapsed time

No `assert elapsed_seconds < N`, and no assertion on wall-clock gaps between events: the threshold encodes the speed of the machine that wrote it, so it passes on a fast runner with the regression present and flakes on a loaded one without it. Guard a complexity fix by counting the work (calls, queries, comparisons) instead, and put the measurement in the commit message or PR rather than the suite. When the behavior really is a schedule, inject the clock. Full guidance in `dev/guidelines/backend/testing.md` §"Never assert on elapsed time".

## Test file placement

Test files mirror source structure: `infrahub/core/node.py` → `tests/unit/core/test_node.py`

Do not reference issue numbers, GitHub URLs, or Jira tickets in test names, docstrings, or comments.

## Schema fixtures

Check `backend/tests/helpers/schema/` before defining test schemas inline. Use `deepcopy` to derive variants from existing helpers rather than writing new schemas from scratch.

## Generate protocols for test schemas

The typing rules in `python-typing.md` apply to tests too. When a test drives an SDK client with kind strings, node attribute access resolves to un-narrowable unions and tempts a new `type: ignore`, `cast()`, or `getattr()`. The way to avoid introducing one is to generate the protocol classes for the test schema and type the nodes against them, so the real types flow through. `tests/e2e` deliberately opts out via a ty override — do not copy that pattern into new tests.
