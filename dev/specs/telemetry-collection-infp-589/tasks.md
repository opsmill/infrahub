---
description: "Task list for Phase 1 Telemetry Collection"
---

# Tasks: Phase 1 Telemetry Collection

**Input**: Design documents from `specs/telemetry-collection-infp-589/`

**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/telemetry-payload.md

**Tests**: Included — Constitution IV requires component tests for SC-001/SC-002/SC-003 and a
unit test for the degradation helper. TDD: write each test first and confirm it fails before
implementing.

**Organization**: Tasks are grouped by user story. The degradation helper, the additive model
changes, and the `payload_format` bump are genuinely shared, so they live in Foundational
(Phase 2). US4 (resilient payload, P1) is realized by that shared mechanism plus a
full-payload resilience test that runs last, since it asserts every in-scope field is present.

## Conventions & Guardrails

- **No work-item / requirement IDs in source.** Do NOT write `FR-xxx`, `SC-xxx`, `IFC-xxxx`,
  `INFP-589`, or task IDs in code, docstrings, comments, or test names
  (`.agents/rules/code-doc-style.md`). Those IDs stay in this file and in commit messages.
- **No mocking.** No `unittest.mock` / `MagicMock` / `patch`. Use plain coroutines as test
  doubles for the degradation helper; use real fixtures/`prefect_test_fixture` for component
  tests. `freezegun` is the allowed tool for pinning time; `get_run_logger` may be handled per
  the allowed `testing-python.md` pattern when calling `@task`/`@flow` via `.fn`.
- **Branch-safe counts.** Node/account counts go through `NodeManager.count` on the default
  branch — never raw `count_nodes(label=...)` for `corenode`.
- **Additive only.** Never change an existing field's name/type/meaning (the sole exception is
  widening the `node_count` value type so the new `corenode` key may be `null`).
- **Keyword arguments** for all calls; full type hints; `str | None` style.
- Commit after each task or logical group.

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Pre-flight; the telemetry module already exists, so setup is minimal.

- [X] T001 [P] Add a Towncrier changelog fragment under `changelog/` (e.g. `+telemetry-phase1.added.md`) describing the new additive telemetry fields and the `payload_format` bump.
- [X] T002 [P] Confirm the telemetry test layout exists and create empty skeletons where missing: `backend/tests/unit/telemetry/test_degradation.py`, `backend/tests/component/telemetry/test_tasks.py` (mirror source structure; no assertions yet).

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Shared payload contract + degradation mechanism that every metric depends on.

**⚠️ CRITICAL**: No user story metric can be wired until this phase is complete.

- [X] T003 Bump `TELEMETRY_VERSION` in `backend/infrahub/telemetry/constants.py` from `"20250318"` to `"20260628"` (this also advances `DEFAULT_PAYLOAD_FORMAT`).
- [X] T004 In `backend/infrahub/telemetry/models.py`, add the additive payload models:
  - `TelemetryAccountData` with `active: int | None` and `groups: int | None`.
  - `TelemetryActivity24hData` with `logins`, `unique_logins`, `checks_started`, `checks_passed`, `checks_failed`, `artifacts_created`, `artifacts_updated`, `branches_created`, `branches_merged`, `branches_deleted`, `webhooks_fired_success`, `webhooks_fired_failure`, all `int | None`.
  - Extend `TelemetryBranchData` with `active: int | None = None` (keep `total: int`).
  - Widen `TelemetryDatabaseData.node_count` value type to `dict[str, int | None]`.
  - Add `accounts: TelemetryAccountData` and `activity_24h: TelemetryActivity24hData` to `TelemetryData` (always-present objects; per-field nullability).
- [X] T005 [P] Write the degradation-helper unit test in `backend/tests/unit/telemetry/test_degradation.py` (TDD — must fail first): a coroutine that raises → helper returns `None`; a coroutine returning `0` → `0`; a coroutine returning `N` → `N`. No DB, no mock (plain coroutines as doubles).
- [X] T006 Implement the async graceful-degradation helper in `backend/infrahub/telemetry/tasks.py`: runs a metric coroutine, returns its result, and on any exception logs a warning and returns `None`. Make T005 pass.

**Checkpoint**: Payload models, version bump, and degradation helper ready. Stories can begin.

---

## Phase 3: User Story 1 — Activity 24h enabler (Priority: P1) 🎯 MVP

**Goal**: Emit `activity_24h` (logins, unique_logins, webhooks success/failure) over the
trailing 24h via a NEW windowed Prefect path, without touching the existing unwindowed event
tally; wire it into the daily payload with per-field degradation.

**Independent Test**: Seed login + webhook-process records inside and outside the trailing 24h;
the gathered `activity_24h` reflects exactly the in-window records, `unique_logins` collapses
repeat logins per account, and the existing `prefect.events.*` output is unchanged.

### Tests for User Story 1 (write first, must fail) ⚠️

- [X] T007 [P] [US1] Component test for windowed logins + unique_logins in `backend/tests/component/telemetry/test_task_manager.py`: with `freezegun` pinning "now" to an off-midnight time (e.g. 02:37 UTC), seed `account.logged_in` events placed relative to the previous-UTC-day boundary — inside the window, just before `window_start`, and just after `window_end` (and repeat logins from one account); assert in-window-only `logins`, distinct-account `unique_logins`, and that the boundary records are excluded (proves the window is anchored to midnight, not to `now`).
- [X] T008 [P] [US1] Component test for webhook success/failure split over 24h in `backend/tests/component/telemetry/test_task_manager.py`: seed terminal `webhook-process` flow runs (completed + failed) in- and out-of-window; assert correct counts and that non-terminal runs are excluded.
- [X] T009 [P] [US1] Regression test asserting `gather_prefect_events` output is unchanged (existing unwindowed tally still present and untouched).

### Implementation for User Story 1

- [X] T009b [US1] In `backend/infrahub/telemetry/task_manager.py` (or a small `telemetry/window.py` helper), add a deterministic window function returning `[window_start, window_end)` where `window_end = floor_to_midnight_utc(now)` and `window_start = window_end - 24h` (previous full UTC calendar day). All activity_24h queries use this — never raw `now`.
- [X] T010 [US1] In `backend/infrahub/telemetry/task_manager.py`, add a NEW windowed event counter that posts to `/events/count-by/event` with an `occurred` window (`since = window_start`, `until = window_end` from T009b) plus the `event.name` filter — separate from `gather_prefect_events`, which stays untouched.
- [X] T011 [US1] In `task_manager.py`, add a windowed unique-account counter posting to `/events/count-by/resource` over the same `account.logged_in` window; the number of resource buckets (keyed by `infrahub.account.{account_id}`) is `unique_logins`.
- [X] T012 [US1] In `task_manager.py`, add a `webhook-process` flow-run query over the same `[window_start, window_end)` window (T009b), splitting terminal states into success (`COMPLETED`) and failure (`FAILED`/`CRASHED`/`TIMEDOUT`); non-terminal runs counted in neither.
- [X] T013 [US1] In `task_manager.py`, add `gather_activity_24h(client) -> TelemetryActivity24hData` assembling the login + webhook counts (US1 fields), each obtained through the degradation helper so one failing source nulls only its own field. (US5 extends this same function with the check/artifact counts.)
- [X] T014 [US1] In `backend/infrahub/telemetry/tasks.py`, wire `activity_24h` into `gather_anonymous_telemetry_data` (gather via the Prefect client path; the object is always present).

**Checkpoint**: `activity_24h` present and windowed; existing event output intact. MVP testable.

---

## Phase 4: User Story 2 — Accounts & branches adoption (Priority: P2)

**Goal**: Emit `accounts.active`, `accounts.groups`, and `branches.active`.

**Independent Test**: Seed known active/inactive accounts, account groups, and
open/system branches; assert each reported count matches the fixture exactly.

### Tests for User Story 2 (write first, must fail) ⚠️

- [X] T015 [P] [US2] Component test for `accounts.active` / `accounts.groups` in `backend/tests/component/telemetry/test_tasks.py`: seed a known mix of active/inactive `CoreAccount` and a known number of `CoreAccountGroup`; assert exact counts via the gather.
- [X] T016 [P] [US2] Test for `branches.active` (registry-based) in `backend/tests/component/telemetry/test_tasks.py`: with open + system branches present, assert the count excludes the default (`main`) and global (`-global-`) branches.

### Implementation for User Story 2

- [X] T017 [US2] Add `gather_account_information(db) -> TelemetryAccountData` (in `backend/infrahub/telemetry/tasks.py`, or a small `backend/infrahub/telemetry/accounts.py` if cohesion warrants): `active` via `NodeManager.count(CoreAccount, filters={"status__value": "active"})`, `groups` via `NodeManager.count(CoreAccountGroup)`, both on the default branch, each through the degradation helper.
- [X] T018 [US2] In `gather_anonymous_telemetry_data` (`tasks.py`), wire `accounts` (from T017) and compute `branches.active` from `registry.branch.values()` excluding `is_default` and `is_global`, via the degradation helper; keep `branches.total` unchanged.

**Checkpoint**: Account + branch adoption metrics present and exact; `branches.total` untouched.

---

## Phase 5: User Story 3 — Branch-correct node counts: `corenode` + `user` (Priority: P2)

**Goal**: Emit `database.node_count.corenode` (all managed nodes) and `database.node_count.user`
(user/business nodes in user-defined namespaces) via the branch/temporal-correct count path,
leaving `node_count.total` (raw vertices) unchanged.

**Independent Test**: Seed a known number of managed nodes, independently compute the expected
count, and assert `node_count["corenode"]` matches exactly (±0); seed user-defined + `Core` nodes
and assert `node_count["user"]` counts only the user-defined ones with `user ⊆ corenode ⊆ total`.

### Tests for User Story 3 (write first, must fail) ⚠️

- [x] T019 [P] [US3] Component test in `backend/tests/component/telemetry/test_datatabase.py`: seed N managed nodes via existing schema fixtures (`backend/tests/helpers/schema/`), independently compute N, assert `node_count["corenode"] == N` exactly and that `node_count["total"]` (raw) is unchanged and `>= N`.

### Implementation for User Story 3

- [x] T020 [US3] In `backend/infrahub/telemetry/database.py`, set `node_count["corenode"]` via `NodeManager.count(db, schema=InfrahubKind.NODE, branch=<default>)`, wrapped so a failure sets `corenode=None` without affecting `node_count["total"]` or the existing graph-label keys (do NOT use raw `count_nodes(label=...)`).
- [x] T021 [US3] Add/extend a docstring or module note distinguishing the three node metrics at the namespace level: `total` (raw vertices), `corenode` (all managed nodes — `Core` + `Builtin` + user-defined namespaces), and `user` (customer-facing subset excluding the `Core` management namespace), noting they nest `user ⊆ corenode ⊆ total`. No tickets/IDs in source.
- [ ] T021b [US3] Component test in `backend/tests/component/telemetry/test_datatabase.py`: seed user-defined nodes (`Test` namespace via `car_person_schema`) + at least one `Core` node (a `CoreAccount`); assert `node_count["user"]` equals the user-defined count exactly (Core node excluded) and `user <= corenode <= total`, with `user < corenode` when a Core node exists.
- [ ] T021c [US3] In `backend/infrahub/telemetry/database.py`, set `node_count["user"]` = sum of `NodeManager.count` over concrete node kinds in user-editable namespaces (`SchemaNamespace.user_editable`, i.e. `namespace not in RESTRICTED_NAMESPACES`), excluding group-generic kinds; wrapped so a failure sets only `user=None`. Update `test_tasks.py` full-payload presence test to assert `node_count["user"]` is present.

**Checkpoint**: `corenode` + `user` exact and branch-correct; `user` excludes `Core`/`Builtin`; raw `total` preserved.

---

## Phase 6: User Story 5 — Depth-of-adoption: checks, artifacts & branch lifecycle (Priority: P2)

**Goal**: Emit `activity_24h.checks_started/passed/failed`,
`activity_24h.artifacts_created/updated`, and
`activity_24h.branches_created/merged/deleted` from events that already flow today, reusing the
US1 windowed event path unchanged.

> Rides entirely on US1's windowed counter (T009b/T010). Each metric is one more event name in
> the same query — verified present via `get_all_events()`: `validator.started/passed/failed`,
> `artifact.created/updated`, `branch.created/merged/deleted`. Branch *lifetime* (duration) is
> NOT included — it needs per-branch correlation (Phase 2).

**Independent Test**: Seed `validator.*`, `artifact.*`, and `branch.*` events in- and
out-of-window; assert each count reflects exactly the in-window events; assert genuine-empty → `0`.

### Tests for User Story 5 (write first, must fail) ⚠️

- [X] T022 [P] [US5] Component test in `backend/tests/component/telemetry/test_task_manager.py` (parametrized off the US1 windowing fixture): seed `validator.started/passed/failed`, `artifact.created/updated`, and `branch.created/merged/deleted` events in- and out-of-window; assert `checks_*`, `artifacts_*`, and `branches_*` equal the in-window counts and that out-of-window events are excluded.

### Implementation for User Story 5

- [X] T023 [US5] Extend the windowed event counter (T010) to also count `validator.started`, `validator.passed`, `validator.failed`, `artifact.created`, `artifact.updated`, `branch.created`, `branch.merged`, `branch.deleted`, and extend `gather_activity_24h` (T013) to populate the eight new fields, each through the degradation helper (per-field null isolation). No change to `gather_prefect_events`.

**Checkpoint**: Depth-of-adoption check/artifact/branch metrics present and windowed.

---

## Phase 7: User Story 4 — Resilient payload (Priority: P1)

**Goal**: Guarantee the cross-cutting resilience contract end-to-end: every in-scope field is
present; a failing source yields `null` (not a dropped payload); a genuine empty yields `0`.

> The mechanism (degradation helper) is delivered in Foundational and consumed by each story
> above. This phase validates the whole payload, so it runs after US1–US3 and US5 are wired.

**Independent Test**: Run the gather flow; assert all in-scope fields present. Force one source
to fail (inject a failing collaborator/fixture — no mock); assert that field is `null`, all
others populated, and the payload is still built and stored. Assert genuine-empty → `0`.

### Tests for User Story 4 (write first, must fail) ⚠️

- [X] T024 [US4] Component test in `backend/tests/component/telemetry/test_tasks.py`: run `gather_anonymous_telemetry_data` on a healthy stack and assert presence of `accounts.{active,groups}`, `branches.active`, `database.node_count.corenode`, and all `activity_24h` fields (`logins`, `unique_logins`, `checks_started/passed/failed`, `artifacts_created/updated`, `branches_created/merged/deleted`, `webhooks_fired_success/failure`).
- [X] T025 [US4] Resilience test in `backend/tests/component/telemetry/test_tasks.py`: make one source fail via an injected failing collaborator/fixture (no mock); assert that field is `null`, every other field is populated, and the snapshot is still stored. Add a genuine-empty case asserting `0`, not `null`.

### Implementation for User Story 4

- [X] T026 [US4] Audit `gather_anonymous_telemetry_data` in `backend/infrahub/telemetry/tasks.py` to ensure every new metric (accounts, branches.active, corenode, each activity_24h field incl. checks/artifacts) is gathered through the degradation helper — no new metric can raise out of the orchestrator. If the current wiring doesn't expose a clean no-mock failure seam for T025, introduce one (e.g. an injectable gather collaborator) following backend component-design DI rules.

**Checkpoint**: Whole payload resilient; one failing source never drops the rest.

---

## Phase 8: Polish & Cross-Cutting Concerns

- [X] T027 [P] Run the telemetry suites: `uv run pytest backend/tests/unit/telemetry backend/tests/component/telemetry -q` (set `DOCKER_HOST` for component tests). — 62 passed.
- [X] T028 [P] `uv run invoke format lint` and resolve any findings in the telemetry module. — ruff format/check + mypy clean (scoped to telemetry).
- [X] T029 Run the `quickstart.md` validation steps end-to-end and confirm `payload_format == "20260628"` in a stored snapshot. — verified via a full local collection simulation (real gather + all new fields populated; `TELEMETRY_VERSION == "20260628"`).
- [ ] T030 **Governance gate (GR-001)** — before merge/release, confirm with the cloud-processor owner and the data-mart owner that the receiver tolerates the `payload_format` bump, ignores unknown fields, and tolerates `null` values (including `corenode` inside `node_count`). Record the confirmation on the PR / tracking ticket. (Process task, not code — remains OPEN, external dependency.)

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: no dependencies.
- **Foundational (Phase 2)**: depends on Setup; **blocks all stories** (models, helper, version).
- **US1 (Phase 3)**, **US2 (Phase 4)**, **US3 (Phase 5)**: each depends only on Foundational; mutually independent (different gather functions / files), so parallelizable across developers.
- **US5 (Phase 6)**: depends on US1 (reuses its windowed counter); otherwise independent.
- **US4 (Phase 7)**: depends on US1–US3 and US5 being wired (it asserts the full payload).
- **Polish (Phase 8)**: depends on all desired stories complete.

### Within Each User Story

- Tests are written first and must fail before implementation.
- US1: window helper (T009b) → windowed counters (T010–T012) → assembler (T013) → orchestrator wiring (T014).
- US2: gather function (T017) → orchestrator wiring (T018).
- US3: db count (T020) → docs note (T021).
- US5: extend the windowed counter + assembler (T023) after US1's T010/T013 exist.

### Parallel Opportunities

- T001 / T002 (Setup) in parallel.
- T005 (helper test) parallel with T003/T004 (constant + models).
- US1 test tasks T007/T008/T009 in parallel; US2 T015/T016 in parallel.
- With capacity: US1, US2, US3 proceed in parallel once Foundational is done; US5 follows US1.
- Polish T027/T028 in parallel.

---

## Parallel Example: User Story 1

```bash
# Write US1 tests together (they must fail first):
Task: "Component test windowed logins/unique_logins in backend/tests/component/telemetry/test_task_manager.py"
Task: "Component test webhook success/failure split in backend/tests/component/telemetry/test_task_manager.py"
Task: "Regression test gather_prefect_events unchanged"
```

---

## Implementation Strategy

### MVP First (User Story 1)

1. Phase 1 Setup → Phase 2 Foundational (CRITICAL).
2. Phase 3 US1 (activity_24h enabler).
3. **STOP and VALIDATE**: windowing + existing-output-untouched, independently.
4. Demo the new `activity_24h` object.

### Incremental Delivery

1. Setup + Foundational → contract + mechanism ready.
2. US1 → calendar-day-windowed activity (MVP).
3. US2 → account/branch adoption.
4. US3 → branch-correct scaling count.
5. US5 → depth-of-adoption checks/artifacts (rides on US1).
6. US4 → full-payload resilience guarantee.
7. Polish → suite green, lint clean, GR-001 governance confirmed.

---

## Notes

- `[P]` = different files, no incomplete-task dependency.
- `[Story]` label maps each task to a user story for traceability (this file only — never in source).
- Verify each test fails before implementing.
- US4's value is P1, but its full-payload assertion depends on US1–US3 + US5, so it is scheduled last.
- US5 (checks/artifacts/branch-lifecycle counts) is a user-directed pull-in from Phase 2 —
  cheap because the events already flow; see `alignment-check.md` §6 for the
  sanctioned-scope-expansion record.
- Out of scope (do not implement): branch *lifetime*
  (duration — needs correlation); PR "merged-without-review" (needs correlation); node churn
  (`node.*` — machine-dominated, noisy); branch `rebased`/`migrated` counts (low-signal);
  remaining Phase 2 metrics (generators/transforms, tokens, CLI/MCP/Sync, licensing);
  dashboards; redefining `node_count.total`; persisting logins in Neo4j.
