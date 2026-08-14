# Phase 0 Research: TRY400 re-enable

**Feature**: `dev/specs/005-ruff-try400-tracebacks/` | **Date**: 2026-08-11 | ruff 0.15.0

## R1 — How to enable TRY400 alone while the rest of `TRY` stays suppressed

**Decision**: add `extend-select = ["TRY400"]` under `[tool.ruff.lint]`, leaving the broad
`"TRY"` entry in `ignore` untouched.

**Why**: ruff resolves rule selection by specificity — a selector naming an exact code beats a
prefix-level `ignore`. Verified empirically on this branch: with `extend-select = ["TRY400"]` in
place, `ruff check backend/infrahub/git/integrator.py` reported its 13 TRY400 violations while
TRY004 (and every other `TRY` rule) stayed silent.

**Alternative rejected — enumerate the remaining `TRY` codes in `ignore`**: this reads more
explicitly but is not viable. ruff 0.15 lists `TRY200` as a removed rule; naming a removed rule
in the config is an error, so the enumeration would break the lint run. `extend-select` also
keeps the diff to a single added block.

## R2 — Is `log.exception` a safe substitution for `log.error` here?

`get_logger()` (`backend/infrahub/log.py:66`) returns a `structlog.stdlib.BoundLogger`; some
sites instead use a stdlib `logging.Logger` (`utilities/infrahub_load_tester.py`) or a Prefect
run logger (`get_run_logger()`). All three expose `.exception(...)`, which emits at **`error`**
level with `exc_info` attached. So the substitution:

- does not change severity — level-based alerting and log filters are unaffected;
- does not change control flow;
- adds the traceback of the currently-handled exception to the record.

**Keyword arguments are preserved verbatim.** These are structlog-style calls carrying
`repository=`, `error=`, `extra={...}` etc., not `%`-style formatting, so no format-string
rewriting is involved.

## R3 — The traceback-suppression filter makes one conversion actively harmful

`backend/infrahub/log.py` defines `suppress_traceback_in_logs` and
`TracebackSuppressionFilter`. Per the filter's own contract:

> Per the logging filter contract, returning `False` discards the whole record, not only its
> traceback.

The filter is installed on the Prefect run loggers (`log.py:93-95`,
`PREFECT_RUN_LOGGERS = ("prefect.flow_runs", "prefect.task_runs")`), and
`WebhookDeliveryError` is registered via `@suppress_traceback_in_logs`
(`backend/infrahub/webhook/classifier.py:65`).

`backend/infrahub/webhook/tasks/process.py:204` logs a curated, operator-facing
delivery-failure message (status class, message, remediation, attempt, elapsed) through
`log = get_run_logger()` inside `except WebhookDeliveryError`. Converting that call to
`log.exception` would attach a `WebhookDeliveryError` to the record, the filter would match it,
and **the whole record — the curated message included — would be dropped**. The failure would
silently stop being reported.

**Decision**: this site keeps `log.error` with `# noqa: TRY400`. This is precisely the failure
mode a blind `--fix --unsafe-fixes` run would have introduced, and it is invisible in a diff
review.

## R4 — Per-site decision: convert (28) vs. justified `# noqa` (6)

All 34 in-scope sites were read at their call site. The rule applied: **convert unless the
traceback would be actively harmful or worthless.**

### Keep `log.error` + `# noqa: TRY400` (7)

> Originally 6. `graphql/app.py` → `_handle_http_request` was added after review: it was converted
> in the first pass, and that was a misapplication of this section's own criterion. See the last
> row.

| Site | Reason |
|------|--------|
| `webhook/tasks/process.py:204` | Traceback attachment makes `TracebackSuppressionFilter` drop the entire record — see R3. |
| `git/integrator.py:456` | Inside `for error in exc.errors():` — one line per Pydantic validation error in a user's `.infrahub.yml`. The traceback would repeat identically for every error and adds nothing to actionable user-facing validation feedback. |
| `git/integrator.py:638` | Same per-error validation loop, artifact-definition variant. |
| `git/integrator.py:459` | `log.error(exc.message)` for the SDK `ValidationError` paired with 456's handler; user-config validation feedback, then `continue`. |
| `git/integrator.py:641` | Same as 459, artifact-definition variant. |
| `workers/infrahub_async.py:194` | "missing configuration for internal_address" then a clean `typer.Exit(1)`. A pure configuration error — there is nothing in the traceback to diagnose. |
| `graphql/app.py` → `_handle_http_request` | `ClientDisconnect` is raised whenever a client aborts while its request body is being read — a routine operating event, not an exceptional one. The traceback only shows the body-read path and is non-actionable, so an ERROR-level stack trace per aborted request is pure log noise. **Added after review**; the original decision to convert it contradicted this section's stated criterion. |

### Convert to `log.exception` (27)

| Site | Handled exception | Note |
|------|-------------------|------|
| `core/branch/tasks.py:119` | `MigrationFailureError` | re-raises; traceback locates the failing migration |
| `core/merge/orchestrator.py:152` | `BaseException` | rollback path — highest-value traceback in the set |
| `database/__init__.py:446` | `ServiceUnavailable` | wraps into `DatabaseError` |
| `git/base.py:619` | `GitCommandError` (unexpected status) | the expected status-1 case already returns earlier |
| `git/base.py:902` | `GitCommandError` | proceeds after reporting |
| `git/integrator.py:810` | `yaml.YAMLError` | traceback carries the parse position |
| `git/integrator.py:825` | `PydanticValidationError` | single report, then raises |
| `git/integrator.py:947` | `InfrahubSdkError` | re-raises |
| `git/integrator.py:1568` | `Exception` | re-raises; broad catch — traceback essential |
| `git/integrator.py:1608` | `Exception` | as above |
| `git/integrator.py:1896`, `:1903` | `ModuleNotFoundError`, `AttributeError` | loading a user check module → `CheckError` |
| `git/integrator.py:1968`, `:1975` | `ModuleNotFoundError`, `AttributeError` | loading a user transform → `TransformError` |
| `git/repository.py:416` | `GitCommandError` | nested ref lookup, then raises |
| `git/tasks.py:1217` | `CheckError` | check failed to run |
| `graphql/app.py:535` | `Exception` (non-`GraphQLError`) | see R5 |
| `services/scheduler.py:91` | `Exception` (keep-alive) | currently logs only `str(exc)`; a failing recurring task was undiagnosable |
| `workers/infrahub_async.py:202` | `SdkError` | a communication failure — traceback distinguishes refused / timeout / TLS |
| `utilities/infrahub_load_tester.py:49, 72, 88, 113, 119, 145, 156, 174` (8) | `Exception` (best-effort loops) | stdlib logger; load-test tooling |

## R5 — `graphql/app.py:535` already passes `exc_info`

The call is `self.logger.error("An exception occurred in resolvers", exc_info=error)` — it
already preserves the traceback, so TRY400 is flagging the idiom rather than a real loss. Inside
`except Exception as error`, `error` **is** the active exception, so
`self.logger.exception("An exception occurred in resolvers")` is equivalent and drops a now
redundant keyword.

**Decision**: convert and remove the redundant `exc_info=error`. This is the one site where an
argument is deliberately not preserved verbatim; the emitted record is unchanged.

## R6 — Changelog convention

`changelog/` holds towncrier fragments named `<issue>.<type>.md`. The merged BLE precedent
(INBOX-19, PR #10002) added a fragment for the equivalent internal lint change, so this change
follows suit for consistency. Confirmed against `changelog/` contents and towncrier config at
implementation time.

## R7 — Test exposure

`log.exception` vs `log.error` can matter to a test asserting on captured log records (level,
or the absence of `exc_info`). Both remain `error` level, so a level assertion still holds; a
test asserting no exception info at a converted site would need updating. Checked during
implementation via the backend unit suite for the touched modules.

## Not applicable

- **`data-model.md`** — N/A. No entities, no persisted state, no schema.
- **`contracts/`** — N/A. No API surface changes; that is the explicit reason TRY004 was scoped out.
- **`quickstart.md`** — N/A. Verification is `uv run invoke lint` plus the unit suite; there is
  no user-facing flow to walk through.
