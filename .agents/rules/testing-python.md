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
- Time-dependent behavior: `freezegun`
- Prefect's `get_run_logger`: when calling a Prefect-decorated function via `.fn` outside a flow context, patch `get_run_logger` to return a stdlib `logging.getLogger(...)` so `caplog` can capture output. See `dev/knowledge/backend/testing.md` for the full pattern.

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

Assert on the exact message with `==`, not substring checks with `in`. Vague checks hide regressions when error wording changes. The full-message-over-fragment preference applies to any exception assertion, not just GraphQL; with `pytest.raises` express it through an anchored `match` (above) rather than `==`.

## Assert exact expectations

Exact-match is not only for error messages. Assert the exact collection (full set/dict equality, not `in`/`issubset`), never mere non-emptiness (`!= frozenset()`, `len() > 0`), and a positive count where the number matters (so a run that silently measures zero fails). A denial test must also reload the target and assert nothing changed. Pin literal expected values — never compute the expectation with the same serializer/library the implementation calls. Full guidance in `dev/guidelines/backend/testing.md` §"Assert exact expectations".

## Don't test the framework

Skip tests that only exercise library behavior: plain `Enum` value/round-trip checks, Pydantic field constraints (`ge`, `min_length`, …), `SettingsConfigDict`/env plumbing, or "a model has field X". Rule of thumb: if the test would still pass after deleting our implementation and reinstalling the library, it belongs to the library. See `dev/guidelines/backend/testing.md` §"What not to test".

## Pick the cheapest test tier

If the logic needs only in-memory inputs (a `SchemaBranch`, a dataclass, a pure function), write a unit test without DB fixtures — don't default to a component test because a neighbor uses one. Use the database or containers only when behavior genuinely depends on them.

## Test file placement

Test files mirror source structure: `infrahub/core/node.py` → `tests/unit/core/test_node.py`

Do not reference issue numbers, GitHub URLs, or Jira tickets in test names, docstrings, or comments.

## Schema fixtures

Check `backend/tests/helpers/schema/` before defining test schemas inline. Use `deepcopy` to derive variants from existing helpers rather than writing new schemas from scratch.
