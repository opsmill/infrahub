# Feature Specification: Re-enable ruff TRY400 so error logs carry tracebacks

**Feature Branch**: `pha/INBOX-29`

**Created**: 2026-08-11

**Status**: Draft

**Input**: Engineering Inbox card INBOX-29 — "Re-enable ruff TRY004 + TRY400 (~56 violations) to restore tracebacks". Scoped down to TRY400 only; see Out of Scope.

## Context

`pyproject.toml` selects every ruff rule (`select = ["ALL"]`) and then suppresses the whole
`TRY` (tryceratops) family in the global `ignore` list, under the "Rules below needs to be
Investigated" banner. The team's suppression-analysis thread ranked re-enabling two of those
rules as priority #4:

- **TRY400** (`error-instead-of-exception`) — `log.error(...)` called inside an `except` block.
  The handler reports that something failed but discards the traceback, so a production error
  log names the symptom with no stack to locate the cause.
- **TRY004** (`type-check-without-type-error`) — an `isinstance`-style guard raising something
  other than `TypeError`.

Ground truth measured on this branch (2026-08-11, ruff 0.15.0, `origin/develop` @ `7d3f48635`):
**76 violations — 36 TRY400 + 40 TRY004**. The card's "~56" estimate is stale.

TRY400 distribution (36 sites):

| File | Sites |
|------|-------|
| `backend/infrahub/git/integrator.py` | 13 |
| `utilities/infrahub_load_tester.py` | 8 |
| `backend/infrahub/workers/infrahub_async.py` | 2 |
| `backend/infrahub/graphql/app.py` | 2 |
| `backend/infrahub/git/base.py` | 2 |
| `backend/infrahub/auth/auth.py` | 2 |
| `backend/infrahub/webhook/tasks/process.py` | 1 |
| `backend/infrahub/services/scheduler.py` | 1 |
| `backend/infrahub/git/tasks.py` | 1 |
| `backend/infrahub/git/repository.py` | 1 |
| `backend/infrahub/database/__init__.py` | 1 |
| `backend/infrahub/core/merge/orchestrator.py` | 1 |
| `backend/infrahub/core/branch/tasks.py` | 1 |

This mirrors the already-merged BLE re-enable (card INBOX-19, PR #10002, spec dir
`dev/specs/002-ruff-ble-reenable/`), which used the same shape: remove the suppression, fix
every site, keep a small number of justified `# noqa` escapes.

## Out of Scope — TRY004

TRY004 is deliberately **not** part of this change. Its fix changes the *exception type* a guard
raises (`ValueError`/`Exception` → `TypeError`) at 40 sites, and those sites sit on surfaces this
automated pipeline may not alter without human design review:

- `backend/infrahub/core/schema/schema_branch.py` — 5 sites (schema surface)
- `backend/infrahub/graphql/mutations/*` and `backend/infrahub/graphql/types/node.py` — 14 sites
  (the exception type is caller-visible in GraphQL error responses)

Changing what a caller catches is a behavioural change, not a lint cleanup. TRY004 stays
suppressed and is escalated to a human on INBOX-29. Splitting it out keeps this change
reviewable as pure logging enrichment.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - An error log names the failure *and* locates it (Priority: P1)

As an engineer debugging a production incident, when a caught exception is logged by any of the
converted handlers, the log record carries the exception and its traceback, so I can see where
the failure originated instead of only that it happened.

**Why this priority**: This is the card's stated value — restoring debuggability of production
errors. It is delivered by the site conversions alone, independent of the rule being enforced.

**Independent Test**: Trigger any converted handler (e.g. force a failure in the git
integrator), inspect the emitted log record, and confirm it contains exception/traceback
information that the pre-change `log.error` call did not emit.

**Acceptance Scenarios**:

1. **Given** a handler converted to `log.exception`, **When** it runs with an active exception,
   **Then** the emitted record carries the exception info (traceback) at the same `error` level
   and with the same message and keyword fields as before.
2. **Given** any converted site, **When** the surrounding code path is exercised, **Then**
   control flow is unchanged — nothing is newly raised, suppressed, or re-ordered.

---

### User Story 2 - TRY400 enforcement is active for future code (Priority: P2)

As an Infrahub developer, when I add a new `log.error(...)` inside an `except` block, the lint
gate rejects it, so this class of traceback-losing handler cannot re-accumulate.

**Why this priority**: Without turning the rule on, today's 36 fixes silently regress. The
durable value is the gate, but it depends on Story 1 being complete first.

**Independent Test**: With the rule enabled, add a temporary `log.error` inside an `except`
block and run the lint gate — it must fail with TRY400; remove it — it must pass.

**Acceptance Scenarios**:

1. **Given** TRY400 is selected in `pyproject.toml`, **When** the repo lint gate runs, **Then**
   it reports zero TRY400 violations.
2. **Given** the rule is active, **When** a developer adds an unjustified `log.error` inside an
   `except` block, **Then** the lint gate fails pointing at that line.
3. **Given** TRY400 is selected, **When** lint runs, **Then** the other `TRY` rules — TRY004
   included — remain suppressed and report nothing.

### Edge Cases

- **A `log.error` inside an `except` block that is not reporting the active exception.** A
  validation branch can sit lexically inside a handler while describing a different condition;
  attaching a traceback there would be misleading. Such a site keeps `log.error` with a
  targeted `# noqa: TRY400` and a one-line reason rather than taking a wrong conversion.
- **A site in a module this pipeline may not edit.** `backend/infrahub/auth/auth.py` is an auth
  module and off-limits to the automated pipeline, so its 2 sites cannot be converted here;
  they are suppressed by file and handed to a human (see Assumptions).
- **Tests asserting on captured log records.** A test pinning a site's log level or absence of
  exception info could fail after conversion; such assertions are updated to match.
- **`ruff --fix` for this rule is unsafe-only.** Autofix is not trusted blind; every conversion
  is reviewed at its call site.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: TRY400 MUST be enforced repo-wide by the lint configuration, while every other
  `TRY` rule — including TRY004 — remains suppressed.
- **FR-002**: The configuration change MUST NOT touch dependency declarations in
  `pyproject.toml`.
- **FR-003**: Every TRY400 site outside `backend/infrahub/auth/auth.py` MUST either be converted
  to `log.exception` or carry a justified `# noqa: TRY400`.
- **FR-004**: A conversion MUST preserve the call's message text and all keyword fields exactly;
  these are structlog-style calls, not `%`-formatting.
- **FR-005**: A conversion MUST NOT alter control flow — no change to what is raised, caught,
  re-raised, or returned.
- **FR-006**: `backend/infrahub/auth/auth.py` MUST NOT be modified. Its 2 TRY400 sites MUST be
  suppressed via a commented `per-file-ignores` entry that names INBOX-29 and the reason.
- **FR-007**: The change MUST NOT touch DB schema or migrations, GraphQL/REST contract surfaces,
  auth behaviour, CI workflows, or any generated file.
- **FR-008**: A changelog fragment MUST be added if and only if the repo's towncrier conventions
  call for one for an internal lint/logging change.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: The repo lint gate reports **zero** TRY400 violations, down from 36.
- **SC-002**: The lint gate reports no new violations of any other rule — the only rule whose
  enforced set changes is TRY400.
- **SC-003**: TRY004 remains suppressed: its 40 pre-existing violations are unchanged, and no
  file it flags is touched by this change.
- **SC-004**: `uv run invoke format` and `uv run invoke lint` are both clean.
- **SC-005**: The changed-file list contains no path under `backend/infrahub/core/schema/`,
  `backend/infrahub/core/migrations/`, `backend/infrahub/auth/`, `.github/`, and no generated
  file listed in `AGENTS.md`.
- **SC-006**: Backend unit tests covering the touched modules pass.
- **SC-007**: Every remaining `# noqa: TRY400` in the tree carries a one-line justification.

## Assumptions

- **`extend-select` is the mechanism.** Adding `extend-select = ["TRY400"]` under
  `[tool.ruff.lint]` re-enables only TRY400 while the broad `"TRY"` entry in `ignore` keeps the
  rest suppressed — ruff resolves the more specific selector first. Verified empirically on this
  branch. Enumerating the individual TRY codes in `ignore` instead is **not** viable: `TRY200`
  is a removed rule and naming it breaks ruff.
- **`log.exception` is level-equivalent.** It emits at `error` level and attaches exception
  info; it does not change severity, so log-level-based alerting is unaffected.
- **The auth.py carve-out is a pipeline boundary, not a technical one.** Both sites are pure
  logging inside `except` blocks and would convert cleanly. The merged BLE precedent (PR #10002)
  *did* edit this same file, adding `# noqa: BLE001` at the very handlers holding these two
  sites — so a reviewer may reasonably prefer the 2-line inline fix and drop the per-file
  ignore. That call is left to a human because the automated pipeline is not permitted to edit
  auth modules unattended.
- **Only TRY400's enforced set changes.** No other suppression is added or removed, so the
  review surface stays proportionate to a logging cleanup.
