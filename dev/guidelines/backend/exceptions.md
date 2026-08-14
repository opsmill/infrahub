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

## Best-effort side effects degrade to a safe fallback

A second broad-catch case is a best-effort side effect whose failure must not abort a primary
operation that has already succeeded: a cache write for an optimization, an observability emit, a
capture step feeding later work. Here the broad `except Exception` deliberately does not re-raise,
because propagating would undo committed, correct work. This is not silencing, and it is legitimate
only when all of the following hold:

- The failure is logged.
- It is converted into an explicit, documented fallback that is at least as safe as the side effect
  never having run, never a silently narrower result. When the side effect feeds a later selection
  or dispatch, the fallback must over-execute, not under-execute.
- It is positioned so the failure cannot corrupt the primary operation's committed result (do the
  best-effort work either fully before the point of no return or fully after it, never straddling
  it).

```python
# ✅ Good - a best-effort capture that must never fail the committed operation
try:
    summary = serialize_diff(branch_diff)
    cache.set(key, summary)          # only after the operation has committed
except Exception as exc:
    log.warning("Merge diff capture failed; falling back to full regeneration", error=str(exc))
    key = None                        # explicit, safe (over-executing) fallback signal
```

## `# noqa: BLE001`

Narrowing is the default answer when ruff flags a broad `except Exception` — most call sites raise a
knowable set of types (see above). Suppress the rule only when catching everything is deliberate, and
name which case it is in the comment above it:

- a top-level boundary (worker loop, request handler) that must not let one failure take down the process
- a loop that turns a per-item failure into a reported result instead of aborting the whole run
- a best-effort side effect that must not fail the primary operation (see above) — after checking the
  catch is needed at all

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

## `log.exception` vs `log.error`

Inside an `except` block, default to `log.exception` so the traceback reaches whoever debugs the
failure later. Keep `log.error` only when the traceback would be actively harmful or worthless, and
say which in a comment next to the suppression:

- **Worthless** — the exception is a routine, expected condition (a client disconnecting mid-request,
  a cancellation), so the traceback shows only plumbing and adds no diagnostic value.
- **Harmful** — logging the exception object feeds machinery that reacts to its type, e.g. a
  registered exception type a log filter uses to drop or redact the record; attaching it changes
  *what* gets logged, not just how much (see `dev/knowledge/backend/webhooks.md` for a concrete
  filter that does this).

```python
# ❌ Bad - a client aborting mid-request is routine; the traceback is non-actionable noise
except ClientDisconnect as exc:
    log.exception("Exception ClientDisconnect in handler")

# ✅ Good - the worthless traceback is named, not just suppressed
except ClientDisconnect as exc:
    # A client aborting mid-request is routine; its traceback is non-actionable noise.
    log.error("Exception ClientDisconnect in handler")  # noqa: TRY400
```

Being inside an `except` block is not by itself a reason to suppress — justify each site on its own.

## See Also

- [Python Standards](python.md) - Typing, imports, data structures, call style
- [Async Tasks](../../knowledge/backend/async-tasks.md) - Workflow and task contracts, including best-effort follow-up work
