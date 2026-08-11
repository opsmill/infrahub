# Implementation Report: Re-enable ruff TRY400 (INBOX-29)

**Branch**: `pha/INBOX-29` | **Date**: 2026-08-11 | **Status**: DONE

## Outcome

TRY400 is enforced repo-wide. All 36 flagged sites resolved: **28 converted** to `log.exception`,
**6** kept as `log.error` with a justified `# noqa: TRY400`, **2** suppressed by file in
`backend/infrahub/auth/auth.py` (not edited). TRY004 remains suppressed and is handed back to a
human.

15 files changed, +80 / −45.

## Tasks

| Task | Status | Note |
|------|--------|------|
| T001 Enable TRY400 in `pyproject.toml` | ✅ | `extend-select = ["TRY400"]`; `"TRY"` ignore annotated |
| T002 `git/integrator.py` (9 convert + 4 noqa) | ✅ | |
| T003 `utilities/infrahub_load_tester.py` (8 convert) | ✅ | |
| T004 `graphql/app.py` (2 convert) | ✅ | incl. redundant `exc_info` removal |
| T005 `git/base.py` (2 convert) | ✅ | |
| T006 `workers/infrahub_async.py` (1 convert + 1 noqa) | ✅ | |
| T007 `webhook/tasks/process.py` (1 noqa) | ✅ | the dropped-record case |
| T008 `core/` (2 convert) | ✅ | |
| T009 `git/repository.py`, `git/tasks.py` (2 convert) | ✅ | |
| T010 `database/__init__.py`, `services/scheduler.py` (2 convert) | ✅ | |
| T010b auth carve-out (config only) | ✅ | `auth/auth.py` never opened for edit |
| T011a Changelog fragment | ✅ | `+ruff-try400-error-instead-of-exception.housekeeping.md` |
| T012 Lint + format gates | ✅ | see Verification |
| T013 Tests + governance diff | ✅ | 2233 unit tests pass |
| T014/T015 Deliver | ✅ | PR opened, Jira comment posted |

## Verification (all success criteria)

| Criterion | Result |
|-----------|--------|
| SC-001 zero TRY400 (was 36) | ✅ `ruff check --select TRY400` → All checks passed |
| SC-002 no new violations of any other rule | ✅ `ruff check --no-cache .` → clean, 0 errors |
| SC-003 TRY004 untouched | ✅ still exactly **40**; no file it flags was modified |
| SC-004 format + lint clean | ✅ `invoke format` clean; `invoke lint` → ruff + **ty** + **mypy** all pass (mypy: 1610 files, no issues) |
| SC-005 no gated path in the diff | ✅ no `core/schema/`, `core/migrations/`, `auth/`, `.github/`, no generated file |
| SC-006 unit tests pass | ✅ `invoke backend.test-unit` → **2233 passed** |
| SC-007 every `noqa: TRY400` justified | ✅ all 6 carry a reason comment |

Also run green: `invoke main.lint`, `uv lock --check`, `invoke backend.validate-generated`,
`invoke docs.validate`, `invoke schema.validate-graphqlschema`,
`invoke schema.validate-jsonschema` — **no generated-file drift**.

Not run: frontend Betterer / GraphQL codegen (no frontend file, GraphQL schema, or generated
frontend type is in the diff) and `invoke docs.format` (`markdownlint-cli2` is not installed in
this environment — the single added Markdown file is a one-line changelog fragment matching the
existing fragments' shape).

## What changed relative to the plan

1. **Nine redundant `# noqa: BLE001` suppressions dropped** (unplanned, correct). BLE001 does not
   flag a blind `except Exception` whose handler logs via `.exception()`, so converting those
   handlers made their suppressions unused — `RUF100` (unused-noqa) then failed the lint gate
   until they were removed. Net effect: this change **retires 9 suppressions beyond the one rule
   it enables**. Sites: `services/scheduler.py` (1), `utilities/infrahub_load_tester.py` (8).

2. **`FakeLogger.exception` now records** (`backend/tests/adapters/log.py`). It was a no-op stub,
   so `test_scheduler_task_with_error` — which asserts an error is reported — failed once the
   scheduler site converted. The fake was wrong, not the test: `.exception` emits at **error**
   level, so it now appends to `error_logs` and the existing assertion passes unmodified. This is
   the test exposure research.md §R7 predicted. Verified no other test is affected: the only
   other `error_logs` consumer (`test_rabbitmq.py`, including an `== []` assertion) exercises
   code with no `.exception()` calls.

3. **`integrator.py:825` line-wrapping reverted by the formatter** — it fits in 120 chars on one
   line. Cosmetic.

## The finding worth a reviewer's attention

`backend/infrahub/webhook/tasks/process.py:204` was **deliberately not converted**.
`WebhookDeliveryError` is registered via `@suppress_traceback_in_logs`, and
`TracebackSuppressionFilter` — installed on the Prefect run loggers that this site logs through —
**drops the entire record**, not just its traceback, for a registered exception type. Converting
it would have silently deleted the classified delivery-failure report (status class, message,
remediation, attempt, elapsed) from the run logs while leaving the lint gate green and the diff
looking innocuous. `ruff --fix --unsafe-fixes` would have made exactly this change.

**Durable hazard for the conventions pass**: `log.exception` at a broad-catch site behind a
Prefect run logger is only safe while the suppressed-type set stays narrow. Two *converted* sites
(`git/integrator.py:1568`, `:1608`) catch bare `Exception` through a run logger; they are safe
today only because `WebhookDeliveryError` is the sole registered type and is unreachable from
repository-integration code. Registering a second, more widely-raised type would silently mute
them.

## Deliberately left for a human

1. **TRY004 — 40 violations, still suppressed.** The fix changes caller-visible exception types on
   `core/schema/schema_branch.py` (5 sites) and `graphql/mutations/*` + `graphql/types/node.py`
   (14 sites). That is an API-behaviour decision, not a lint cleanup. **INBOX-29 asked for both
   rules, so merging this PR does not complete the card** — a follow-up card should be split off
   rather than letting the merge mark it Done.
2. **The 2 `auth/auth.py` sites.** Both are pure logging inside `except` blocks and would convert
   cleanly. They are suppressed by file because this pipeline may not edit auth modules. The
   merged BLE precedent (PR #10002) *did* edit this same file — adding `# noqa: BLE001` at the
   very handlers holding these two sites — so a reviewer may reasonably prefer the 2-line inline
   fix and drop the `per-file-ignores` entry.

## Notable autonomous decisions

- **Scoped the card down to TRY400 before planning**, on measuring that TRY004 lands on
  governance-gated surfaces. Recorded in spec.md "Out of Scope" and escalated on the card rather
  than silently half-delivering.
- **Per-site convert-vs-noqa rule**: convert unless the traceback is actively harmful (1 site) or
  worthless (5 sites: per-error user-config validation feedback ×4, a pure missing-configuration
  startup error ×1). Full table in research.md §R4.
- **`extend-select` over enumerating the TRY codes** in `ignore` — enumeration is impossible
  because `TRY200` is a removed rule and naming it breaks ruff.
- **Kept ticket refs out of Python comments** per `.agents/rules/code-doc-style.md`; the two
  `INBOX-29` references live in `pyproject.toml`, which has existing precedent (`INFP-566`).

## Incident during implementation

A first pass ran `ruff check --select RUF100 --fix .` to clear the 9 unused-noqa. Because
`--select` *replaces* the rule set, every noqa directive for every other rule became "unused" and
ruff stripped **870 directives across 388 files**. Caught immediately on the diff stat, reverted
with `git checkout -- .` (nothing had been committed), and the whole edit set was re-applied from
a scripted, assertion-checked list. Final state verified clean by full lint + mypy + ty + 2233
tests. Lesson: never `--select <rule> --fix` on a whole repo; scope the fix to the specific lines.

STATUS: DONE | SPEC_DIR: /home/ubuntu/projects/infrahub/dev/specs/005-ruff-try400-tracebacks | REASON: n/a
