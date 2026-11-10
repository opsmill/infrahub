---
paths:
  - "backend/infrahub/**/*.py"
  - "python_testcontainers/infrahub_testcontainers/**/*.py"
  - "tasks/**/*.py"
---

# Python exceptions and correctness

Ruff's BLE and TRY rules are disabled, so exception handling is checked in review. Full reference: `dev/guidelines/backend/exceptions.md`.

## Exceptions

- Catch the narrowest types the call raises, grouped as a tuple, not `except Exception` or a bare `except:`. Infrahub errors are mostly siblings: `QueryTimeoutError` is not a `DatabaseError`.
- A broad catch is legitimate only at a top-level boundary (worker loop, request handler), in a per-item loop that reports each failure, around a best-effort side effect after the primary work committed, or to add context and `raise`. A comment names which case it is.
- Do not wrap code that cannot raise anything the caller must handle, such as building objects from validated data or putting a message on an internal queue. Move non-critical side effects such as telemetry off the request path instead of silencing them.
- Every handler logs, records or re-raises; never `except ...: pass`.
- A best-effort fallback is at least as safe as the side effect never running: it does not narrow the result or do less work.
- A `try` body covers only the statement that can raise.
- Do not swallow cancellation: no `isinstance(r, Exception)` filter over `gather(return_exceptions=True)`, and no `CancelledError` counted as success.
- Do not catch and return inside `async with db.start_transaction()`, which commits the partial work; put the `try` outside the block.
- In an `except` block, log with `log.exception`. Use `log.error` only with a comment saying why the traceback is useless (a routine disconnect) or harmful (a log filter keys on the exception type).
- Raise a new error from inside `except` with `from exc`.

## Correctness

- No blocking synchronous I/O inside `async def`.
- Pass values to Cypher as `$params`, never by interpolation.
- No N+1 patterns (per-node loads in a loop, fetch then mutate each); use a set-based query.
- Test optional numbers with `is not None`, not truthiness (`if offset:`).
- Match a path against an allow-list or exclusion with `path == p or path.startswith(f"{p}/")`; a bare `startswith` lets `/healthcheck` match `/health`.

## Not violations

- A broad `except Exception` that logs and re-raises, or that names its case.
- `infrahub.exceptions` errors such as `PoolExhaustedError` propagating to the API as intended responses.
- No transaction in a function that takes `db`: the caller owns the transaction boundary. Cascading deletes are committed separately on purpose.
- Temporal edge cases in migrations and retention queries, which run at the current time with the system down.
- Orphaned attributes (attributes with no node) not handled by queries; they are not supposed to exist.
- Function-local imports in `tasks/*.py`, which keep `invoke` light.
