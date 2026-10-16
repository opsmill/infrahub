---
paths:
  - "backend/tests/unit/**/*.py"
  - "backend/tests/component/**/*.py"
  - "backend/tests/functional/**/*.py"
  - "backend/tests/integration/**/*.py"
  - "backend/tests/integration_docker/**/*.py"
  - "python_testcontainers/tests/**/*.py"

---

# Python test isolation and concurrency

Full reference: `dev/guidelines/backend/testing.md`

## Don't leak process-global state

Every test in an xdist worker shares one interpreter. Change `logging` levels/handlers/filters, `structlog` config, module-level registries/singletons, class attributes (your own or a third-party library's), `sys.path`/`sys.modules` or env vars only through a save/restore fixture (change it, `yield`, restore it), or `monkeypatch` where it applies. Never call an application startup routine such as `infrahub.log.configure_logging` from a test — it owns the whole process and undoes nothing, so it reconfigures every later test in the worker. Install only the piece under test and remove it after the `yield`. Never call `dependency_provider.scope` around code that may raise: it skips its cleanup on an exception, so a `pytest.raises` around the call leaks the double to every later test on the worker. Use `backend/tests/helpers/dependency_override.py::override_dependency`, or `backend/tests/helpers/workflow_override.py::override_workflow` for a workflow double; both restore in a `finally`. See `dev/guidelines/backend/testing.md` §"Leave process-global state as you found it".

## One database session per concurrent path

A Neo4j session carries a single connection and cannot serve two coroutines at once, and the module-scoped `db` fixture hands the same session to every test in a module. Give each racing call its own `db.start_session()`. Sharing one wedges the connection, and every later test in the module then dies on `read() called while another coroutine is already waiting for incoming data`. Flows and GraphQL open their own session, so racing those is safe; a component a test calls directly is not. Full guidance in `dev/guidelines/backend/testing.md` §"One database session per concurrent path".

## Prefect task manager setup

Never call `setup_task_manager()` from a test or fixture; call `tests.helpers.task_manager.setup_task_manager_once()`. The raw setup re-registers every block, pool, deployment and trigger against the worker's Prefect server with no timeout, and under CI load that hangs until pytest-timeout kills the whole class. The helper runs it once per server URL, bounded, and fails fast for that server afterwards. The only test allowed to call the raw function is the one that tests the setup itself. Mechanism in `dev/knowledge/backend/testing.md` §"Prefect Testing Patterns".


## Async tests

- Write `async def test_...` and `await`; never `asyncio.run(...)` inside a sync test, since pytest runs in `asyncio_mode=auto`.
- Poll for the exact expected state with a deadline instead of a fixed `asyncio.sleep(n)` before an assertion.
- Bound every `await event.wait()` with `asyncio.wait_for(timeout=...)`. Such a deadline bounds a wait and is not a timing assertion.
