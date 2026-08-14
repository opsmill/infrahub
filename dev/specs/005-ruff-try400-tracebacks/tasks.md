# Tasks: Re-enable ruff TRY400 so error logs carry tracebacks

**Feature**: `dev/specs/005-ruff-try400-tracebacks/` | **Branch**: `pha/INBOX-29`

**Input**: [spec.md](./spec.md), [plan.md](./plan.md), [research.md](./research.md),
[critiques/critique-2026-08-11.md](./critiques/critique-2026-08-11.md)

Per-site decisions are **research.md §R4** — that table is the authority for every edit below.
Do not re-derive it, and do not use `ruff --fix` (§R4, critique E4).

---

## Phase 1 — Turn the rule on (worklist generator)

### T001 — Enable TRY400 in `pyproject.toml`

- Add `extend-select = ["TRY400"]` under `[tool.ruff.lint]` with the comment
  `# error-instead-of-exception — enabled ahead of the rest of TRY (INBOX-29)`.
- Annotate the existing `"TRY"` entry in `ignore` so the pair does not read as contradictory
  (critique E5).
- Do **not** touch dependency lists (FR-002).
- **Verify**: `.venv/bin/ruff check --select TRY400 --no-cache .` reports 36 violations, and
  `--select TRY004` still reports 40 (FR-001, SC-003).

From here, `ruff check --select TRY400` is the worklist; Phase 2 is done when it reports 0.

---

## Phase 2 — Fix the sites (T002–T010 are independent; any order, parallelizable)

Each task: apply research.md §R4, preserve message text and all keyword arguments exactly
(FR-004), change no control flow (FR-005), and give every `# noqa: TRY400` a one-line reason
(SC-007, FR-003).

> Sites are identified by **enclosing function**, not line number. The conversions shift line
> numbers as they are applied, so absolute anchors written at plan time do not survive into the
> merged tree. To locate the current set at any time:
> `ruff check --select TRY400 .` before the change, and `grep -n 'noqa: TRY400'` after it.

### T002 [P] — `backend/infrahub/git/integrator.py` — 9 convert + 4 noqa

- **Convert**: `get_repository_config` (2 — YAML parse, Pydantic parse),
  `_build_graphql_query_definitions` (1), `get_check_definition` (1), `get_python_transforms` (1),
  `execute_python_check` (2), `execute_python_transform` (2).
- **noqa**: `_build_jinja2_transform_definitions` (2) and `_build_artifact_definitions` (2) — each
  is a per-error Pydantic validation loop plus the paired SDK `ValidationError` on user config.
- Largest single file (13 of 36 sites); do it first if serializing.

### T003 [P] — `utilities/infrahub_load_tester.py` — 8 convert

- `_create_one` (1), `_delete_branches` (2), `_delete_users` (2), `create_admin_branches` (1),
  `delete_admin_branches` (2). Stdlib `logging.Logger`; `.exception` exists.

### T004 [P] — `backend/infrahub/graphql/app.py` — 1 convert + 1 noqa

- **noqa** in `_handle_http_request` (`ClientDisconnect`) — a client aborting mid-request is a
  routine operating event and the traceback only shows the body-read path, so it is
  non-actionable noise. *(Converted in the first pass, then reverted after review — it failed
  research.md §R4's own "worthless traceback" test.)*
- **Convert** in `_observe_subscription` — **and remove the now-redundant `exc_info=error`**
  (research.md §R5). This is the only site where an argument is intentionally not preserved;
  verify the `error` reassignment still happens after the log call (critique E2).
- Leave the `_log_error` helper alone: it runs outside any `except` block and must keep passing
  `exc_info` explicitly. Ruff does not flag it.
- ASGI error handling only — **not** the GraphQL contract surface. Called out in the PR body
  (T014).

### T005 [P] — `backend/infrahub/git/base.py` — 2 convert

- `has_conflicting_changes`, `validate_remote_branch` (both `GitCommandError`).

### T006 [P] — `backend/infrahub/workers/infrahub_async.py` — 1 convert + 1 noqa

Both sites are in `_init_infrahub_client`:

- **noqa** the `InitializationError` handler — a pure configuration error ("missing configuration
  for internal_address") followed by a clean `typer.Exit(1)`; nothing in a traceback to diagnose.
- **Convert** the `SdkError` handler — a communication failure; the traceback distinguishes
  refused / timeout / TLS.

### T007 [P] — `backend/infrahub/webhook/tasks/process.py` — 1 noqa

- In `webhook_send`, the `except WebhookDeliveryError` handler: keep `log.error`, add
  `# noqa: TRY400` whose reason states that attaching the exception makes
  `TracebackSuppressionFilter` drop the whole record, because `WebhookDeliveryError` is registered
  via `@suppress_traceback_in_logs` and `log` is a Prefect run logger. **Do not convert this one**
  (research.md §R3 — the highest-consequence decision in the change).

### T008 [P] — `backend/infrahub/core/` — 2 convert

- `branch/tasks.py` → `migrate_branch` (`MigrationFailureError`);
  `merge/orchestrator.py` → `merge` (`BaseException`, rollback path — note this module has other,
  pre-existing `log.exception` calls that are not part of this change).

### T009 [P] — `backend/infrahub/git/` remainder — 2 convert

- `repository.py` → `update_latest_commit`; `tasks.py` → `run_user_check` (again, other
  `log.exception` calls in `tasks.py` are pre-existing).

### T010 [P] — remaining single sites — 2 convert

- `database/__init__.py` → `run_query` (`ServiceUnavailable`); `services/scheduler.py` →
  `run_schedule` (keep-alive loop — the change's clearest win, critique P4).

### T010b — auth carve-out (config only; `auth/auth.py` MUST NOT be edited)

- Add a `[tool.ruff.lint.per-file-ignores]` entry for `"backend/infrahub/auth/auth.py"` listing
  `"TRY400"`, commented with the INBOX-29 deferral reason (FR-006, plan.md Step 3).
- **Verify**: `git diff --name-only` never lists `backend/infrahub/auth/auth.py` (SC-005).

---

## Phase 3 — Changelog

### T011a — Towncrier fragment

- Inspect `changelog/` and the towncrier config; add a fragment matching the convention the BLE
  precedent (PR #10002) used for an equivalent internal lint change. Skip only if the convention
  genuinely excludes internal-only changes (FR-008, research.md §R6).

---

## Phase 4 — Verify (gates; all must pass before delivery)

### T012 — Lint and format gates

- `.venv/bin/ruff check --no-cache .` → **zero** TRY400, no new violations of any other rule
  (SC-001, SC-002).
- `.venv/bin/ruff check --select TRY004 --no-cache .` → still **40**, unchanged (SC-003,
  critique E6).
- `uv run invoke format` and `uv run invoke lint` → clean (SC-004).
- `grep -rn 'noqa: TRY400'` → every occurrence carries a justification (SC-007).

### T013 — Tests and governance diff check

- `uv run invoke backend.test-unit` for the touched modules; update any assertion pinning log
  level or exception info at a converted site (SC-006, research.md §R7, critique E8).
- `git diff --name-only origin/develop...HEAD` → contains no path under
  `backend/infrahub/core/schema/`, `backend/infrahub/core/migrations/`, `backend/infrahub/auth/`,
  `.github/`, and no generated file listed in `AGENTS.md` (SC-005, FR-007).

---

## Phase 5 — Deliver

### T014 — Open the PR (honest framing required)

Per critique P2/P3/P4, the PR body MUST:

- state **27 of 36** sites converted, not a clean sweep — 7 justified in-line `# noqa` + 2
  deferred in `auth/auth.py`;
- lead with the `webhook/tasks/process.py:204` finding (converting it would have silently
  deleted the delivery-failure log record) — it is the reason this was not an autofix;
- name `services/scheduler.py:91` as the concrete debuggability win;
- explicitly flag the `backend/infrahub/graphql/app.py` touch (2 log lines in ASGI error
  handling, not the GraphQL contract) and the new `auth/auth.py` per-file ignore, with the
  PR #10002 precedent that lets a reviewer ask for the 2-line inline fix instead;
- link `INBOX-29`.

### T015 — Jira comment (critique P1 — do not let the card close silently)

Comment on INBOX-29 stating that this PR addresses **only the TRY400 half**, that the 40 TRY004
violations remain suppressed and need a human decision (caller-visible exception-type changes on
`core/schema/` and GraphQL mutation surfaces), and that a follow-up card should be split off
rather than letting a merge mark INBOX-29 Done. Also note the 2 deferred `auth/auth.py` sites.

---

## Dependencies

```text
T001 ──▶ T002..T010, T010b  (all [P], independent of each other)
                │
                ▼
            T011a ──▶ T012, T013 ──▶ T014 ──▶ T015
```

**Total**: 15 tasks. T002–T010 are parallelizable across files; the config tasks (T001, T010b)
both touch `pyproject.toml` and must not run concurrently with each other.
