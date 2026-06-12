---
paths:
  - "backend/tests/unit/**/*.py"
  - "backend/tests/component/**/*.py"
  - "backend/tests/functional/**/*.py"
  - "backend/tests/integration/**/*.py"
  - "backend/tests/integration_docker/**/*.py"
---

# Python Testing Rules

Full reference: `dev/guidelines/backend/testing.md`

## Import at the top

All imports should be at the top of the test file. Do not import inside of test functions or classes.

## No mocking

Do NOT use `unittest.mock`, `pytest-mock`, `MagicMock`, `patch`, or `Mock`.

Use adapter/protocol patterns instead. The message bus demonstrates this:

- Production: `backend/infrahub/services/adapters/message_bus/rabbitmq.py`
- Testing: `backend/tests/adapters/message_bus.py` (`BusRecorder` / `BusSimulator`)

Both implement `InfrahubMessageBus`. Tests inject the test adapter — no patching.

Acceptable exceptions only:

- External HTTP APIs with no test mode: use `httpx_mock` or `responses`
- Time-dependent behavior: `freezegun`

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

Assert on the exact message with `==`, not substring checks with `in`. Vague checks hide regressions when error wording changes. This applies to any exception assertion, not just GraphQL.

## Test file placement

Test files mirror source structure: `infrahub/core/node.py` → `tests/unit/core/test_node.py`

Do not reference issue numbers, GitHub URLs, or Jira tickets in test names, docstrings, or comments.

## Schema fixtures

Check `backend/tests/helpers/schema/` before defining test schemas inline. Use `deepcopy` to derive variants from existing helpers rather than writing new schemas from scratch.
