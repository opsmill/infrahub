# Research: Re-enable ruff BLE (blind-except) rule

**Date**: 2026-07-22 | **Plan**: [plan.md](plan.md)

All Technical Context unknowns resolved. Every decision below was verified against the working tree on branch `pha/INBOX-19` (commands run 2026-07-22).

## R1. Rule semantics (`ruff rule BLE001`)

**Decision**: Treat BLE001 as flagging `except Exception:` and `except BaseException:` handlers, with two built-in exemptions that require no code change: handlers whose body re-raises (`raise`), and handlers that call stdlib `logging.exception(...)` / log with `exc_info=True` (recognized only for `lint.logger-objects`, which this repo does not configure).

**Rationale**: Verified via `uv run ruff rule BLE001`. The repo logs through structlog (`infrahub.log.get_logger()`), which ruff does not recognize as a logger object here — so `log.exception(...)` at a flagged site does *not* exempt it. All 78 flagged sites are therefore genuine work items; none can be resolved by "it already logs".

**Alternatives considered**: Configuring `lint.logger-objects` to teach ruff about structlog loggers, auto-exempting `log.exception` handlers. Rejected: it silently weakens the rule repo-wide (any future `except Exception: log.exception(...)` would pass without justification), diverges from the card's per-site auditability requirement, and would be a semantic lint-config change beyond the card's scope.

## R2. Enforcement gates and verification commands

**Decision**: Verify against four gates, in this order: (1) `uv run ruff check --select=BLE .` (card acceptance, repo root), (2) `uv run ruff check . --exclude python_sdk` (the exact CI lint command, `.github/workflows/ci.yml:326`), (3) `uv run invoke backend.lint` (ruff `--diff` + format check + ty + mypy over `backend/`, card acceptance), (4) `uv run ruff format --check --diff --exclude python_sdk .` (CI format step; touched files must stay format-clean).

**Rationale**: `invoke backend.lint`'s ruff step runs `ruff check --diff backend`, which only surfaces *fixable* diagnostics — BLE001 has no autofix, so gate (3) alone would not prove BLE cleanliness; gate (2) is the gate that actually fails CI on any missed site anywhere in the repo (including `tasks/`, `utilities/`, `tests/e2e/`). Verified that the CLI `--select=BLE` overrides the config ignore list, so gate (1) works both before the config flip (inventory: 78) and after (must be 0).

**Alternatives considered**: Relying only on the card's two acceptance commands. Rejected: they under-test — CI's full-repo `ruff check` is stricter than both.

## R3. Site inventory (ground truth)

**Decision**: Scope = the 78 BLE001 sites across 46 files measured on this branch (77 × `except Exception`, 1 × `except BaseException` in `backend/tests/helpers/test_worker.py:107`), re-measured at final verification. Full per-site inventory with treatments: [data-model.md](data-model.md).

**Rationale**: The card's "~32 sites" dates from the 2026-02-18 analysis; graph migrations added since (m043–m074) contribute ~20 new sites. Counted via `ruff check --select=BLE --output-format=concise .` → 78 matches, 46 unique files.

**Alternatives considered**: Fixing only the original ~32. Rejected: the config flip is all-or-nothing — CI runs repo-wide, so every current site must be resolved.

## R4. Treatment policy (narrow vs. suppress)

**Decision**: Two treatments, assigned per site in data-model.md:

- **NARROW** — replace `Exception` with the specific type(s) the guarded block realistically raises (project base `infrahub.exceptions.Error` counts as a legitimate narrowing when the try block only raises Infrahub errors). Only where the raisable set is identifiable with high confidence AND letting unexpected types propagate is acceptable at that boundary.
- **SUPPRESS** — keep `except Exception` byte-identical, append `# noqa: BLE001` on the except line, add a one-line justification comment. Mandatory for hard-constraint areas (all of `backend/infrahub/core/migrations/`, and `backend/infrahub/api/{auth,oauth2,oidc}.py` + `backend/infrahub/auth/`); default for keep-alive boundaries (worker/task loops, telemetry, webhook dispatch, best-effort cleanup, per-item migration continuation) and for load-test statistics loops.

Never widen; never introduce bare `except:` (E722 guards that anyway); the single `BaseException` site is resolved per its harness-isolation purpose (analysis in data-model.md) — either justified as-is or reduced to `Exception` only if that provably cannot change what the test harness intercepts.

**Rationale**: Matches the card's suggested solution verbatim and the pre-existing house guideline `dev/guidelines/backend/python.md` §Exception Handling ("broad `except Exception` is justified only at a top-level boundary… log the exception… never discard it"). The hard-constraint mandate (suppression-only in migrations/auth) is the conservative reading of the card's "no DB schema or migration changes / no auth changes": narrowing changes which exception types propagate — a runtime behavior change — while comment + noqa additions are semantically inert.

**Alternatives considered**: (a) Narrowing migration handlers to `(Error, Neo4jError, …)` — rejected: any mis-enumeration alters migration failure behavior on real customer data; prohibited by constraint. (b) Adding `BLE001` to `per-file-ignores` for `backend/tests/**` or `backend/infrahub/core/migrations/**` — rejected: blanket suppression removes per-site auditability, re-creates the debt invisibly, and violates spec FR-001. (c) Wrapping broad catches in a shared helper (`with suppress_and_log(...)`) — rejected: behavior-affecting refactor, violates minimal-change method and constitution VII (premature abstraction).

## R5. Suppression style

**Decision**: Line-targeted `# noqa: BLE001` on the `except` line, with a brief justification comment immediately above the `except` line (or inline where the line stays ≤ line-length 120). Comment states *why arbitrary failures must be absorbed at that boundary* — not what the code does. Example:

```python
# Keep-alive boundary: one failing scheduled task must not kill the scheduler loop.
except Exception as exc:  # noqa: BLE001
```

**Rationale**: Ruff `noqa` must be on the diagnostic's line to take effect; rule-targeted form keeps every other rule active on that line. RUF100 (`unused-noqa`) is enabled via `select = ["ALL"]`, so any `noqa: BLE001` that stops matching a real diagnostic fails the lint gate — this keeps suppressions load-bearing (spec FR-010) with no extra tooling.

**Alternatives considered**: Bare `# noqa` (rejected: suppresses all rules on the line, RUF100-unfriendly); block-level `# ruff: noqa: BLE001` file pragmas (rejected: file-wide suppression, not auditable per site).

## R6. Batching, tests, and fix order

**Decision**: Execute in six batches — (A) migrations 30, (B) auth 8 (both suppression-only), (C) backend runtime 16, (D) backend tests 13, (E) tooling 11, then (F) flip the config (remove `"BLE"` from `ignore`) and run full verification. After each batch: `ruff check --select=BLE` on touched paths + `ruff format --check` on touched files. Local test obligation: `uv run invoke backend.test-unit` once after all code batches, plus module-scoped component tests for `backend/tests/component/core/schema/schema_branch/*` (the two component test files touched are themselves the tests to run — they are runnable locally with testcontainers when available; if the local environment cannot run them, record that and defer to CI).

**Rationale**: House `/fix-ruff-rule` method mandates ~10-file batches and validation between steps. Config flip goes last so the tree is never in a state where the active rule fails mid-work. Unit tests are the cheap tier proving no import-time or behavior regressions; the only *behavior-relevant* narrowings land in batches C–E, whose modules are covered by the unit suite where coverage exists.

**Alternatives considered**: Flipping the config first and fixing until green — rejected: leaves the working tree failing lint at every intermediate commit, breaking the checkpoint-commit convention.

## R7. Changelog fragment

**Decision**: Add a towncrier fragment `changelog/+ruff-ble-blind-except.housekeeping.md` (orphan `+` prefix — no GitHub issue; `housekeeping` type exists in `[tool.towncrier.type]` with existing precedent, e.g. `+downsize-docker-image.housekeeping.md`).

**Rationale**: Cheap, follows observed repo practice for internal improvements, and pre-empts review churn. Refines the spec assumption ("no fragment required") in the permitted direction — the spec explicitly allows adding one.

**Alternatives considered**: No fragment (spec default) — kept as fallback if towncrier lint rejects the orphan fragment for any reason.

## R8. Out-of-scope boundaries (verified)

- `python_sdk/` — git submodule, separate repo, excluded by the CI command. Untouched.
- `python_testcontainers/` — carries its own `[tool.ruff]` config (own select/ignore); repo-root ruff runs lint it under *its* config; it reports no BLE001 today. Untouched.
- `backend/tests/fixtures/repos/**` — fixture repos with their own `pyproject.toml`; not governed by the root config. Untouched.
- Generated dirs (`backend/infrahub/core/schema/generated/`, `protocols.py`, `*/graphql_queries/*.py`) — zero BLE001 sites there today; will not be edited.
- CI workflows — read for gate discovery only (`ci.yml:325-328`); no edits.
