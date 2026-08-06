# Python Exception Handling

> Part of: `dev/guidelines/backend/` | Related: [Python Standards](python.md)

Catching, scoping, and suppressing exceptions in the Python backend.

## Catch only what you expect

Do not use bare `except:` or a broad `except Exception` to wrap code you haven't verified can raise something you can recover from — it swallows `KeyboardInterrupt`/`SystemExit` intent, hides bugs (typos, `AttributeError`, misconfiguration) behind the same handler as the error you meant to catch, and makes failures silent.

```python
# ❌ Bad - swallows everything, including programming errors
try:
    node = await get_node(db=db, node_id=node_id)
except Exception:
    node = None

# ✅ Good - catch only what get_node is documented to raise
try:
    node = await get_node(db=db, node_id=node_id)
except NodeNotFoundError:
    node = None
```

Guidelines:

- **Ask whether you need a `try`/`except` at all.** A catch earns its place only around a call that can raise in a way the caller must handle. There is nothing to catch when the guarded step is entirely in your control (assembling an object from already-validated data) or when its failure cannot reach the caller (handing a message to an internal queue). If the concern is a non-critical side effect like telemetry or a notification, move it off the request path — a background task that runs after the response — instead of silencing it in place; see [Post-commit follow-up work is best-effort](../../knowledge/backend/async-tasks.md#post-commit-follow-up-work-is-best-effort).
- **Name the exceptions.** Catch the narrowest type(s) that the called code actually raises. If several are handled the same way, group them: `except (NodeNotFoundError, BranchNotFoundError):`.
- **Check the hierarchy before narrowing.** Infrahub's exception types are mostly direct `Error` subclasses, not a tree — `QueryTimeoutError` is a *sibling* of `DatabaseError`, so catching `DatabaseError` does not cover query timeouts. Verify in `backend/infrahub/exceptions.py` which types the call path actually raises before writing the tuple.
- **Keep the `try` body small.** Wrap only the statement that can raise, not a whole block, so an unexpected error elsewhere isn't caught by accident.
- **Never silence.** A bare `except Exception: pass` hides real failures. If there is genuinely nothing to do, comment why, and at minimum `log.debug(...)`.
- **Re-raise what you can't handle.** If you must catch broadly to add context or clean up, re-raise afterwards (`raise` to preserve the traceback, or `raise NewError(...) from exc` to chain).

```python
# ✅ Good - broad catch is acceptable only to add context, then re-raise
try:
    await run_migration(db=db)
except Exception as exc:
    log.error("Migration failed", error=str(exc))
    raise
```

## `# noqa: BLE001`

Narrowing is the default answer when ruff flags a broad `except Exception` — most call sites raise a
knowable set of types (see above). Suppress the rule only when catching everything is deliberate, and
name which case it is in the comment above it:

- a top-level boundary (worker loop, request handler) that must not let one failure take down the process
- a loop that turns a per-item failure into a reported result instead of aborting the whole run
- a side effect that must not fail the primary operation — after checking the catch is needed at all

All three still log or record the failure; none discards it.

Inside a transaction, catching and returning commits the partial work: `__aexit__` rolls back only
when an exception leaves the `async with` block. Re-raise inside and convert outside, and write what
the code does rather than what it was meant to do.

```python
# ❌ Bad - the comment claims a clean failure, but the transaction commits whatever step_one wrote
async with db.start_transaction() as dbt:
    try:
        await step_one(dbt)
        await step_two(dbt)
    # Failures become MigrationResult errors so the runner reports them
    except Exception as exc:  # noqa: BLE001
        return MigrationResult(errors=[str(exc)])

# ✅ Good - the exception leaves the block, so it rolls back before being reported
try:
    async with db.start_transaction() as dbt:
        await step_one(dbt)
        await step_two(dbt)
except Exception as exc:  # noqa: BLE001
    return MigrationResult(errors=[str(exc)])
```

If a suppression exposes a pre-existing bug, file it separately; see
[Pull Requests](../git-workflow.md#pull-requests).

## See Also

- [Python Standards](python.md) - Typing, imports, data structures, call style
- [Async Tasks](../../knowledge/backend/async-tasks.md) - Workflow and task contracts, including best-effort follow-up work
