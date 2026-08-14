# Implementation Plan: Re-enable ruff TRY400 so error logs carry tracebacks

**Branch**: `pha/INBOX-29` | **Date**: 2026-08-11 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `dev/specs/005-ruff-try400-tracebacks/spec.md`

## Summary

Enable ruff's TRY400 (`error-instead-of-exception`) repo-wide via `extend-select`, leaving the
rest of the suppressed `TRY` family — TRY004 included — untouched, then resolve all 36 flagged
sites: **27 converted** to `log.exception`, **7 kept as `log.error` with a justified
`# noqa: TRY400`**, and **2 suppressed by file** because they live in
`backend/infrahub/auth/auth.py`, which this pipeline may not edit. Per-site decisions and their
reasoning are in [research.md](./research.md) §R4.

## Technical Context

**Language/Version**: Python 3.14

**Primary Dependencies**: ruff 0.15.0 (lint gate), structlog (`structlog.stdlib.BoundLogger` via
`infrahub.log.get_logger`), Prefect run loggers, stdlib `logging`

**Storage**: N/A

**Testing**: pytest 9.0 — `uv run invoke backend.test-unit` for the touched modules

**Target Platform**: Linux server (backend) + repo tooling under `utilities/`

**Project Type**: Backend service + repo tooling; lint-configuration change

**Performance Goals**: N/A — no hot path touched. `log.exception` formats a traceback only when a
handler actually emits the record.

**Constraints**: No behavioural change. Same log level, same message, same keyword fields, same
control flow. No DB schema/migration, GraphQL/REST contract, auth, dependency, CI, or generated-file
changes.

**Scale/Scope**: 1 config file + 12 source files; 36 TRY400 sites (27 conversions, 7 in-line
suppressions, 2 file-level suppressions).

## Constitution Check

*GATE: evaluated before Phase 0 research and re-checked after design.*

| Principle | Assessment |
|-----------|-----------|
| I. Schema-Driven Integrity | **PASS** — no schema, no generated files. `core/schema/` is explicitly excluded (it only holds TRY004 sites). |
| II. Branch-Safe by Default | **PASS** — no queries, no branch/temporal logic touched. |
| III. Type Safety & Explicit Contracts | **PASS** — no signatures or types change. Strengthens observability of the existing contracts. |
| IV. Test Discipline | **PASS with note** — a logging-call substitution has no new behaviour to test; the guard is the lint gate itself (SC-001/002) plus the existing unit suite proving no regression. Adding tests that assert on log internals at 27 sites would be test-for-test's-sake. Recorded in Complexity Tracking. |
| V. Query Performance & Efficiency | **PASS** — no query changes. |
| VI. Security & Input Boundaries | **PASS** — `auth/` is untouched by construction (FR-006). No new data enters a log record beyond the traceback of an already-caught exception. |
| VII. Simplicity & Maintainability | **PASS** — net simplification: removes a category-wide suppression for one rule and replaces implicit traceback loss with either a traceback or an explicit justified exception. |

No violations requiring justification beyond the Test Discipline note below.

## Project Structure

### Documentation (this feature)

```text
dev/specs/005-ruff-try400-tracebacks/
├── spec.md                 # Phase -1 output
├── plan.md                 # This file
├── research.md             # Phase 0 output — per-site decision table
├── tasks.md                # Phase 2 output (/speckit-tasks)
└── checklists/
    └── requirements.md     # Spec quality checklist
```

`data-model.md`, `contracts/`, and `quickstart.md` are **N/A** for this feature — there is no
data model, no API surface, and no user-facing flow to walk through. See research.md
"Not applicable". They are deliberately not created rather than filled with invented content.

### Source Code (repository root)

```text
pyproject.toml                                  # [tool.ruff.lint] extend-select + per-file-ignores

backend/infrahub/
├── core/
│   ├── branch/tasks.py                         # 1 convert
│   └── merge/orchestrator.py                   # 1 convert
├── database/__init__.py                        # 1 convert
├── git/
│   ├── base.py                                 # 2 convert
│   ├── integrator.py                           # 9 convert + 4 noqa
│   ├── repository.py                           # 1 convert
│   └── tasks.py                                # 1 convert
├── graphql/app.py                              # 1 convert + 1 noqa (ASGI error handling only)
├── services/scheduler.py                       # 1 convert
├── webhook/tasks/process.py                    # 1 noqa     (see research.md §R3)
├── workers/infrahub_async.py                   # 1 convert + 1 noqa
└── auth/auth.py                                # NOT MODIFIED — 2 sites suppressed by file

utilities/infrahub_load_tester.py               # 8 convert

changelog/                                      # towncrier fragment
```

**Structure Decision**: no structural change. The edit set is the union of TRY400's current
violation sites plus the lint config, and nothing else.

## Implementation Approach

### Step 1 — Turn the rule on first

Add to `[tool.ruff.lint]` in `pyproject.toml`:

```toml
extend-select = [
    "TRY400",   # error-instead-of-exception — enabled ahead of the rest of TRY (INBOX-29)
]
```

and annotate the existing `"TRY"` ignore entry so the two are not read as contradictory. Turning
the rule on *before* fixing sites makes ruff the worklist: the remaining violation count is the
progress meter, and reaching zero is the completion signal.

### Step 2 — Fix sites file by file, following research.md §R4

Each file is independent, so files can be done in any order. For every site: read the handler,
apply the §R4 decision, preserve message and keyword arguments exactly. `ruff --fix` for TRY400
is **unsafe-fix-only** and is not used — the 7 noqa sites and the `_observe_subscription`
`exc_info` removal are exactly the judgements an autofix gets wrong (see §R3, §R5).

Each `# noqa: TRY400` carries a one-line reason on the same line or immediately above, so SC-007
holds and the next reader does not have to re-derive the call.

### Step 3 — Suppress the auth carve-out by file

Add to `[tool.ruff.lint.per-file-ignores]`:

```toml
"backend/infrahub/auth/auth.py" = [
    # TRY400 deferred to a human (INBOX-29): both sites are pure logging inside except blocks
    # and would convert cleanly, but the automated pipeline may not edit auth modules.
    "TRY400",
]
```

**This is the one part of the plan a reviewer is most likely to want changed**, and that is
deliberate: the merged BLE precedent (PR #10002) edited this same file, adding `# noqa: BLE001`
at the very handlers holding these two sites. Dropping this entry and converting the two calls
inline is a ~2-line follow-up. The plan defers rather than decides because an unattended agent
should not be the one to touch auth code.

### Step 4 — Changelog fragment

Add a towncrier fragment following whatever `changelog/` and the towncrier config establish for
an internal lint/logging change, matching what the BLE precedent did (research.md §R6).

### Step 5 — Verify against the success criteria

```bash
.venv/bin/ruff check --no-cache .                       # SC-001, SC-002: zero TRY400, nothing new
.venv/bin/ruff check --select TRY004 --no-cache .       # SC-003: still 40, unchanged
uv run invoke format && uv run invoke lint              # SC-004
git diff --name-only origin/develop...HEAD              # SC-005: no gated path
uv run invoke backend.test-unit                         # SC-006 (touched modules)
grep -rn 'noqa: TRY400'                                 # SC-007: every one justified
```

## Risks

| Risk | Mitigation |
|------|-----------|
| A conversion silently drops a log record via `TracebackSuppressionFilter` | Identified at `webhook/tasks/process.py:204` and excluded (research.md §R3). The registered-type set was enumerated — `WebhookDeliveryError` is the only member, and that site is its only catch site. |
| A blind autofix mangles a call | Autofix not used; all 36 sites read individually. |
| A test asserts on log level or exception info | Level is unchanged (`.exception` emits at `error`). Unit suite for touched modules is run; any assertion on exception info is updated (research.md §R7). |
| `extend-select` does not override the prefix `ignore` | Verified empirically before planning (research.md §R1). |
| Scope creep into TRY004 | The `ignore` entry for `TRY` stays; SC-003 asserts TRY004's 40 violations are untouched. |

## Complexity Tracking

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|-------------------------------------|
| No new tests for 27 changed call sites (Principle IV) | The change is a level-preserving logging substitution with no new behaviour. The lint gate (SC-001/002) is the durable regression guard, and the existing unit suite proves nothing broke. | Asserting on captured log records at each site would pin implementation detail of logging calls, be brittle to message edits, and test structlog rather than Infrahub. |
| A new `per-file-ignores` entry added by a change whose purpose is *removing* a suppression | `backend/infrahub/auth/auth.py` is off-limits to the automated pipeline, but the rule must still be enforceable repo-wide. | Editing the 2 auth sites inline is the better end state and is what the reviewer will likely ask for — but it requires a human to own the auth-module change. Leaving the rule fully off instead would forfeit the other 34 sites. |
