# Tasks: Merge Failure Recovery

**Input**: Design documents from `dev/specs/ifc-2437-merge-failure-recovery/`
**Prerequisites**: `plan.md`, `spec.md`, `research.md`, `data-model.md`, `contracts/internal-api.md`, `quickstart.md`

**Tests**: Included — the project constitution (Principle IV) requires tests, and each user story in `spec.md` defines an independent test.

**Organization**: Tasks are grouped by user story. US1–US3 are P1 (US1 is the MVP); US4 is P2.

**Conventions** (no front-loaded scaffolding — YAGNI):
- Each primitive (status value, field, helper, component, config setting) is added by the **first task that needs it**, not as an upfront foundational stub.
- **Each shippable increment (user story) ships its own Towncrier changelog fragment** under `changelog/` — there is no single feature-wide changelog.
- Test directories/modules are created **on demand** with their first test (no empty `__init__.py` scaffolding).

> **Jira** — epic **IFC-2559**; **IFC-2437** is the umbrella bug. Full issue↔task mapping in the "Jira cross-reference" section. New issues IFC-2715/2716/2717 cover the [ASK-FIRST] index/migration/SDK work.

> **[ASK-FIRST]** (per AGENTS.md) — tasks changing **DB indexes/migrations**, the **GraphQL-exposed enum/schema**, the **SDK submodule**, or **schema-migration query** behavior need maintainer approval before implementation.

## Path Conventions

Infrahub backend monolith: `backend/infrahub/...`; tests under `backend/tests/{unit,component,functional,integration_docker}/`; SDK submodule at `python_sdk/`.

---

## Phase 1: User Story 1 — Default branch protected during a merge (P1) 🎯 MVP

**PRs**: **PR-1** = T005 (IPAM reorder, standalone) · **PR-2** = T001–T004, T006–T009 (write-block increment). Optional prep PR for the `BranchStatusChecker` async/`cache` change inside T003 if the caller set is wide. See **PR Plan** below.

**Goal**: Block API writes to the default branch (and the source branch) for the whole merge window via a shared `merge:protected` cache key; lift automatically on success.

**Independent Test**: Start (or pause) a merge into the default branch; writes to the default branch and the source branch are rejected with a transient "merge in progress, retry shortly" message, an unrelated branch is writable, a new merge/rebase is blocked, and the default-branch write succeeds once the merge completes.

- [X] T001 [US1] Add `merge_started_at` to `Branch` in `backend/infrahub/core/branch/models.py` (persisted via `StandardNode.save()`; written once at `OPEN→MERGING`, never cleared — see data-model invariants). **Stored as `Optional[str]` (ISO timestamp string), not `Timestamp | None`**: a `Timestamp` field cannot serialize through `StandardNode` (pydantic rejects it without `arbitrary_types_allowed`, and `to_db()` fails on `ujson.dumps`), so it mirrors the existing `branched_from` string pattern with a normalizing validator.
- [X] T002 [US1] Create `backend/infrahub/core/merge/write_blocker.py` with the `MergeWriteBlocker` DI component (`__init__(cache)`, entry points `set`/`get`/`delete`, private `_serialize`/`_parse` of `"{branch}::{state}"`, state ∈ `MERGING`/`MERGE_FAILED`) owning the `merge:protected` cache key — this new module is introduced here at first use (research R11). (The PR-3 detection/recovery `MergeFailureRecovery` component lives separately in `failure_recovery.py`.)
- [X] T003 [US1] In `backend/infrahub/branch/status_checker.py`: constructor is `__init__(db, merge_write_blocker)` (**`db` required, first arg**); make `check()` **async**, and implement async `check_merging_status` — read the `merge:protected` key; **source gate** (key's branch == branch being written) → branch-specific read-only message (`"Branch '{name}' is being merged and is read-only…"`, mirroring `MERGED`); **target gate** (default branch while key present) → transient "retry shortly" message. **If the cache is unreachable, log the exception and fall back to the durable DB branch status** (`Branch.get_list(status=MERGING)`) so a cache outage blocks writes only when a merge is genuinely in progress. Update call sites (`backend/infrahub/graphql/middleware.py` → `info.context.db`; `backend/infrahub/api/schema.py`, `backend/infrahub/api/artifact.py` → the `db` dependency) to build `MergeWriteBlocker(cache=service.cache)`, pass `db`, and `await` (contracts §5). Checker unit tests live in `backend/tests/component/branch/test_status_checker.py` (component — the checker now requires a real `db`; data loaded once per class).
- [X] T004 [US1] In `backend/infrahub/core/branch/tasks.py` `_do_merge_branch`: at `OPEN→MERGING` (right after acquiring the `MergeLocker` lock, before any graph write) persist `merge_started_at = merge_at` and set `merge:protected = "{branch}::MERGING"`; **delete** the key at the `MERGED` transition and in `_rollback_merge` (leave `merge_started_at`).
- [X] T005 [US1] In `backend/infrahub/core/branch/tasks.py`: **MANDATORY reorder** — move the `IPAM_RECONCILIATION` submission to *after* the `branch.status = MERGED` save (compute `ipam_node_details` before the diff freeze; defer `submit_workflow(...)` until after `MERGED`). Load-bearing for US3 recovery (research R12).
- [X] T005a [US1] In `backend/infrahub/core/merge/branch_merger.py` + `backend/infrahub/core/branch/tasks.py`: defer `merge_repositories()` out of `BranchMerger.merge()` to the post-`MERGED` follow-on section (best-effort `_merge_repositories_after_merge`, before `BRANCH_DELETE`). The repository sync issues a `CoreRepositoryUpdate` (GraphQL) on the default branch and was the one non-IPAM pre-`MERGED` follow-on the §2 audit identified — without this it self-blocks on the write protection (`test_repository_branch.py::TestCreateRepository::test_merge_branch`).
- [X] T006 [US1] Block new merge/rebase operations (incl. proposed-change merges) while `merge:protected` is present (FR-004) at the merge/rebase entry points in `backend/infrahub/core/branch/tasks.py` and the proposed-change merge path.
- [X] T007 [P] [US1] Component tests in `backend/tests/component/branch/test_status_checker.py`: with a branch hand-set to `MERGING` + `merge:protected` set, assert source-branch writes rejected (read-only message) and default-branch writes rejected (transient message), unrelated branch writable, and clearing the key lifts the block (SC-001, US1 #1–4); plus the cache-unreachable DB fallback (blocks via the durable `MERGING` status; does not freeze the default branch when no merge is in progress). Component (not unit) because `BranchStatusChecker` now requires a real `db`; data loaded once per class. The integrated flow-level merge/rebase rejection (SC-002) is covered by the functional test T008.
- [X] T008 [P] [US1] Functional test in `backend/tests/functional/merge/test_merge_in_progress_block.py`: drive a paused merge → transient block during `MERGING`, lifted on successful completion (SC-001).
- [X] T009 [US1] Add a Towncrier changelog fragment for **write protection during merge** under `changelog/`.

**Checkpoint**: A healthy merge blocks default/source writes and new merges, and lifts on completion — independently shippable.

---

## Phase 2: User Story 2 — Failed merge detected & protection held (P1)

**PRs**: **PR-3** = T010, T012–T024 (incl. T020a) (+ schema regen T046) — the detection increment, incl. the enum and the `MERGE_RECOVERY_REQUIRED` catalogue code · **PR-4** = T011 (SDK enum, [ASK-FIRST] submodule; may land with PR-8). Optional split of PR-3: *3a* detection logic (T010, T012–T016, T020, T020a, T021, T022) / *3b* recurring scan + startup + SIGKILL test (T017–T019, T023) — note US2's independent test needs 3b. See **PR Plan** below.

**Goal**: Deterministically flip a dead merge `MERGING → MERGE_FAILED` (recurring scan + startup + on-write/on-merge fast paths), hold the default-branch protection with a "contact an administrator" message, and survive restarts.

**Independent Test**: SIGKILL the merge worker mid-merge, leave the system idle; within grace + one scan interval the branch is `MERGE_FAILED` and default-branch writes are rejected with the recovery message and the `MERGE_RECOVERY_REQUIRED` code (not the transient `MERGE_IN_PROGRESS` one); a healthy merge is never flipped.

- [ ] T010 [US2] **[ASK-FIRST]** Add `MERGE_FAILED = "MERGE_FAILED"` to `BranchStatus` in `backend/infrahub/core/branch/enums.py` (not in `TERMINAL_BRANCH_STATUSES`). Auto-exposed to GraphQL via `Enum.from_enum` → changes `schema/schema.graphql` (regen in T046); confirm the additive enum value is acceptable.
- [ ] T011 [US2] **[ASK-FIRST]** Mirror `MERGE_FAILED` into the SDK enum in `python_sdk/infrahub_sdk/branch.py` (submodule change + bump) so SDK clients can read it (FR-025). **Jira IFC-2717**.
- [ ] T012 [US2] Add a configurable merge-failure **grace period** setting in `backend/infrahub/config.py` (pick a concrete default ~2–3 min) — added here, where detection first consumes it.
- [ ] T013 [US2] Add a read-side helper in `backend/infrahub/core/merge/merge_locker.py` returning the current `all_branches` lock holder's `worker_id` (from the `timestamp::worker_id` token) or `None` if absent — without acquiring.
- [ ] T014 [US2] Add the pure predicate `is_failed_merge(status, lock_token, active_worker_ids, merge_started_at, now, grace_period) -> bool` in `backend/infrahub/core/merge/failure_recovery.py` = `status==MERGING AND lock present AND token worker_id ∉ active set AND now-merge_started_at > grace_period` (research R2).
- [ ] T015 [P] [US2] Unit test the predicate in `backend/tests/unit/core/merge/test_failed_merge_predicate.py` (lock present/absent, worker active/inactive, within/after grace).
- [ ] T016 [US2] In `backend/infrahub/core/merge/failure_recovery.py`, create the `MergeFailureRecovery` DI component (`__init__(db, diff_merger, cache, component, merge_locker)`) with `RecoveryReport`/`RecoveryOutcome`, and implement `detect_and_mark` (predicate over `MERGING` branches → set DB `MERGE_FAILED` + update `merge:protected` to `"{branch}::MERGE_FAILED"`; idempotent) (contracts §4).
- [ ] T017 [US2] Create the recurring detector flow `detect_failed_merges(service)` in `backend/infrahub/tasks/merge_watcher.py` — calls `detect_and_mark` **and reconciles** `merge:protected` against the durable DB status (set if missing for a `MERGING`/`MERGE_FAILED` branch; delete if none protected) (research R11/R4).
- [ ] T018 [US2] Register `MERGE_WATCHER` (`type=INTERNAL`, `cron="* * * * *"`, `concurrency_limit=1`, `ConcurrencyLimitStrategy.CANCEL_NEW`, module `infrahub.tasks.merge_watcher`, function `detect_failed_merges`) in `backend/infrahub/workflows/catalogue.py`.
- [ ] T019 [US2] Add the startup detection call in `backend/infrahub/core/initialization.py` after `initialize_registry()` — applies the **full FR-007 condition** so a restarting worker never mis-flags a merge running on another live worker (clarification 2026-06-09).
- [ ] T020 [US2] Add the on-write/on-merge fast paths (FR-011b/c) in `backend/infrahub/branch/status_checker.py` + merge entry points (escalate `MERGING`→`MERGE_FAILED` via the predicate; `MERGE_FAILED` read from the key is the steady-state fast path, FR-012), and add a **distinct recovery exception** `MergeRecoveryRequiredError(BranchStatusError)` in `backend/infrahub/exceptions.py` carrying the recovery message (names `infrahub recover` + "contact an administrator") and a `merging_branch` attribute. It must be a **sibling** of `MergeInProgressError`, **not** a subclass — a subclass would resolve to the `MERGE_IN_PROGRESS` catalogue code via the formatter's MRO walk and be indistinguishable to clients. Wire it into `check_merging_status` so the `MERGE_FAILED` case raises `MergeRecoveryRequiredError` while `MERGING` keeps raising `MergeInProgressError` (FR-002 vs FR-009). NB: the name `MergeFailedError` is already taken (HTTP 500, raised synchronously inside the merge task in `core/merge/branch_merger.py`) — do not reuse it.
- [ ] T020a [US2] Add `MergeRecoveryRequiredError` to the GraphQL error catalogue as its own code `MERGE_RECOVERY_REQUIRED` (HTTP 423, stability `evolving`, payload `{branch_name, merging_branch}`) — a recovery-needed merge must raise a different code than a transient merge-in-progress (decided 2026-06-15). Follow the add-a-code procedure in `dev/specs/infp-468-graphql-error-catalogue/quickstart.md` §1 (payload model → catalogue entry → formatter arm → `frontend.regenerate-error-bindings` → barrel re-export → unit + exhaustiveness tests). No E2E retry-predicate change needed: it only retries `MERGE_IN_PROGRESS`, so `MERGE_RECOVERY_REQUIRED` fails fast by construction.
- [ ] T021 [P] [US2] Component test in `backend/tests/component/core/merge/test_failure_detection.py`: dead lock holder + elapsed grace → `detect_and_mark` sets `MERGE_FAILED` + updates key; active holder or within-grace **not** flipped (SC-006).
- [ ] T022 [P] [US2] Functional test in `backend/tests/functional/merge/test_failed_merge_protection.py`: after detection, default-branch + failed-source writes rejected with the recovery message **and the `MERGE_RECOVERY_REQUIRED` error code (HTTP 423, distinct from `MERGE_IN_PROGRESS`)**, unrelated branch writable, protection persists across a simulated restart (SC-005, FR-013).
- [ ] T023 [US2] Integration-docker test (detection half) in `backend/tests/integration_docker/test_merge_kill_recovery.py`: SIGKILL mid-merge, idle, assert `MERGE_FAILED` within grace + one scan interval (SC-003, SC-004).
- [ ] T024 [US2] Add a changelog fragment for **failed-merge detection & protection** under `changelog/`.

**Checkpoint**: A dead merge is detected and the default branch stays protected with the recovery message; healthy merges are never mis-flagged.

---

## Phase 3: User Story 3 — Administrator recovers with `infrahub recover` (P1)

**PRs**: **PR-5** = T025–T027a, T028–T034, T038 (+ doc T045) — recovery core (range rollback + in-process unify + recover component + CLI + delete block + tests) · **PR-6** = T035, T036 ([ASK-FIRST] indexes + graph migration, Jira IFC-2715) · **PR-7** = T037 ([ASK-FIRST] schema-migration `previous_*` co-write, Jira IFC-2716). T031 (delete block) only needs the `MERGE_FAILED` state and could land earlier with US2. See **PR Plan** below.

**Goal**: A single operator-confirmed CLI command reverses the partial merge (graph + in-window schema migrations, incl. per-node metadata), resets the branch and any proposed change to `OPEN`, and lifts the protection — idempotently.

**Independent Test**: Produce a failed merge, run `infrahub recover` (confirm or `--yes`); the default branch equals its pre-merge snapshot (graph diff empty, node metadata restored), the branch and PC are `OPEN`, default-branch writes succeed again, and a re-run reports nothing to recover.

- [ ] T025 [US3] Rewrite `RollbackQuery` in `backend/infrahub/core/query/rollback.py` into the **range rollback** scoped to the default branch: **per-edge-type subqueries** over the 8 `DatabaseEdgeType`s reopening edges with `to >= $merge_at` and deleting edges with `from >= $merge_at`, plus orphaned-vertex cleanup (research R8, contracts §3). The structural revert is already timestamp-keyed (`to = $at` / `from = $at`), so this is an exact-→range widening of existing phases, not a new mechanism. **Shared-caller warning:** `RollbackQuery` has **two** callers — `DiffMerger.rollback()` (`merger.py:204`, merge in-process, passes `node_uuids`) and `SchemaUpdateCoordinator._rollback()` (`update_coordinator.py:332`, rebase, no `node_uuids`). Widening `= $at` → `>= $merge_at` lands on the rebase path too; confirm it is safe there (rebase runs all ops at a single `rebase_at` under `global_graph_lock`, so no writes exist `> rebase_at` to over-revert) or give the coordinator an exact-timestamp mode.
- [ ] T026 [US3] Add the **metadata-restore** phase to the range rollback: for vertices connected to reverted edges where `updated_at >= $merge_at`, restore `previous_updated_at/by` (clear optional) — covers merge-diff + migration collateral (research R8). This replaces the current `node_uuids`-scoped metadata phase (rollback.py:56-57) — that `WHERE n.uuid IN $node_uuids` selection is the **only** use of `_affected_node_uuids` in rollback; the edge-derived selection retires it (see T027a). **Behavior change for the rebase coordinator caller:** it passes no `node_uuids` today, so it restores **no** metadata; after this change it would restore metadata on the rebase path too, which is only correct once T037 has migrations co-writing `previous_*`. Ensure ordering (T037 before this is relied on for rebase) or scope the metadata phase to the recovery/merge entry.
- [ ] T027 [US3] Expose a recovery rollback entry on `DiffMerger` (`backend/infrahub/core/diff/merger/merger.py`) running the range query from `(default branch, merge_started_at)` with **no** `get_affected_node_uuids` list (contracts §3/§4).
- [ ] T027a [US3] **Unify the in-process rollback onto the range query** (contracts §3 "Decision — unify both paths"). Point `MergeRollbackHandler` (`backend/infrahub/core/merge/rollback_handler.py`) at the T027 range entry keyed on `(destination_branch, merge_started_at)` instead of the UUID-scoped `GraphMerger.rollback()`; keep the handler's in-memory restore (schema registry + branch object + write-blocker, which out-of-process recovery does not need because it reloads from DB). Then **delete** the now-dead UUID-scoped paths: `GraphMerger.rollback()` (`graph_merger.py`), the old `DiffMerger.rollback()` and its `self._affected_node_uuids` instance field (`merger.py:202`, set at `:111`) — **keep** `get_affected_node_uuids` / the local list, still used for the in-merge metadata update (`merger.py:104-124`). The orchestrator already has the only rollback trigger (its `except` → handler); the inner `GraphMerger.merge()` self-rollback was already removed on the refactor branch. **Test impact:** `backend/tests/integration/diff/test_merge_rollback.py` — `BrokenGraphMerger.rollback()` forwarding becomes irrelevant once `GraphMerger.rollback()` is gone; the test must still drive a partial merge and assert the (now range-based) rollback restores pre-merge state. Covers the post-migration in-process-failure gap noted in contracts §3.
- [ ] T027b [US3] Restore the destination branch's pre-merge `schema_changed_at` during in-process rollback in `backend/infrahub/core/merge/rollback_handler.py`. Today the handler resets the registry schema to `pre_merge_schema` then calls `destination_branch.update_schema_hash()` (no `at`), which — because the in-merge schema update already bumped the branch's hash to the post-merge value — stamps `schema_changed_at` to *rollback time* rather than restoring the pre-merge value (the schema content is correctly restored; only the timestamp is wrong). Capture the pre-merge `schema_changed_at` (and `schema_hash`) at the same point `pre_merge_schema` / `pre_merge_branched_from` are captured in the orchestrator, pass them into `rollback()`, and restore them literally — symmetric with the existing `pre_merge_branched_from` restore. `pre_merge_schema` can also recompute its own hash, so no extra schema load is needed. Low impact (the only consumer, the GraphQL schema-staleness check in `graphql/app.py`, just triggers a harmless reload of the restored schema), so deferred — not blocking the refactor. NB: the analogous pre-existing path `SchemaUpdateCoordinator._restore_registry_state` (`update_coordinator.py`) has the same behavior and should be fixed alongside.
- [ ] T028 [US3] Implement `MergeFailureRecovery.recover(confirmed)` in `backend/infrahub/core/merge/failure_recovery.py`: detect **both** a `MERGE_FAILED` branch **and** a stuck-`MERGING` branch with a dead/absent lock holder (FR-016, clarification) → range rollback → reset branch to `OPEN` → reset PC to `OPEN` → delete `merge:protected`; return a `RecoveryReport`; handle no-failure (FR-023), orphaned/branch-removed (FR-024), idempotent re-run (FR-022).
- [ ] T029 [US3] In `recover()`, find/reset the associated proposed change via node-manager filter (`source_branch__value == <branch>`, `state__value == "merging"`) → `state = "open"` + save; proceed without one for a direct branch merge (FR-020; research R7).
- [ ] T030 [US3] Create the `infrahub recover` CLI in `backend/infrahub/cli/recover.py` (AsyncTyper, mirrors `cli/db.py`): config load → init_db → initialize_registry → build `MergeFailureRecovery` → `rich.Console` report → `typer.confirm` unless `--yes/-y` → print `RecoveryOutcome`; close DB in `finally`. Register in `backend/infrahub/cli/__init__.py` (FR-015/016/017).
- [ ] T031 [US3] Enforce the `MERGE_FAILED` **delete block at the mutation gate** in `backend/infrahub/graphql/middleware.py` (`MERGE_FAILED` granted no mutation exception, incl. `BranchDelete`); leave `Branch.delete()` unchanged (FR-014).
- [ ] T032 [P] [US3] Component test in `backend/tests/component/core/merge/test_recovery_rollback.py`: drive a merge, hand-set the marker, run `recover()` → graph diff vs pre-merge empty **and** touched-node `updated_at/by` restored; a variant that raises mid-`merge_graph` recovers the partial graph; re-run is idempotent (SC-008, SC-010).
- [ ] T033 [P] [US3] Component test in `backend/tests/component/core/merge/test_recovery_edge_cases.py`: no-failure → nothing to recover (FR-023); orphaned/branch-removed → cleared without crashing (FR-024); stuck-`MERGING`-dead-lock → recovered under confirmation (FR-016); declined → no changes (US3 #3); **delete of a `MERGE_FAILED` branch rejected, then allowed after recovery** (SC-007).
- [ ] T034 [US3] Integration-docker test (recovery half) in `backend/tests/integration_docker/test_merge_kill_recovery.py`: after `MERGE_FAILED`, `infrahub recover --yes` → default-branch writes succeed, branch re-merges (SC-009).
- [ ] T035 [US3] **[ASK-FIRST]** Add RANGE `IndexItem` entries for edge `from`/`to` + a node `updated_at` index in `backend/infrahub/core/graph/index.py` (research R8). **Jira IFC-2715**.
- [ ] T036 [US3] **[ASK-FIRST]** Add the graph migration creating the new indexes (under `backend/infrahub/core/migrations/graph/`), bumping the graph version. **Jira IFC-2715**.
- [ ] T037 [US3] **[ASK-FIRST]** Update schema-migration queries that bump vertex `updated_at/by` (e.g. `core/migrations/schema/attribute_kind_update.py`, `core/migrations/query/attribute_add.py`, `node_duplicate.py`, `node_remove.py`, …) to co-write `previous_updated_at/by`, mirroring `DiffMergeMetadataQuery` (research R8). **Jira IFC-2716**.
- [ ] T038 [US3] Add a changelog fragment for **`infrahub recover`** under `changelog/`.

**Checkpoint**: An operator can fully recover a failed merge and re-merge; metadata is restored; recovery is idempotent.

---

## Phase 4: User Story 4 — Visibility into failed & recovered merges (P2)

**PRs**: **PR-8** = T039–T043 (visibility & logging). Alternatively fold T039 into PR-3 and T040 into PR-5 (log where the code lives) and ship only the visibility tests + changelog here. T041 depends on PR-4 (SDK enum). See **PR Plan** below.

**Goal**: Operators can see `MERGE_FAILED` on a branch and find structured log entries for both detection and recovery.

**Independent Test**: Force a failed merge then recover it; the `MERGE_FAILED` state is visible via branch inspection, and the failure and the recovery each produce a locatable structured log entry.

- [ ] T039 [US4] Emit the `merge.failure.detected` **structured log entry** (branch, `merge_started_at`, proposed_change, worker_id, source) from `detect_and_mark` in `backend/infrahub/core/merge/failure_recovery.py` (FR-026).
- [ ] T040 [US4] Emit `merge.recovery.started`/`completed`/`failed` **structured log entries** (not message-bus events — the CLI has no bus) from `recover()`/the CLI in `failure_recovery.py` + `backend/infrahub/cli/recover.py` (FR-027, contracts §9).
- [ ] T041 [P] [US4] Functional test in `backend/tests/functional/merge/test_merge_failed_visibility.py`: `MERGE_FAILED` observable via branch inspection (GraphQL enum auto-exposed; SDK mirror from T011) (FR-025, US4 #1).
- [ ] T042 [P] [US4] Functional test in `backend/tests/functional/merge/test_merge_recovery_logging.py`: detection and recovery each produce a log entry locatable by branch name (SC-011, US4 #2/#3).
- [ ] T043 [US4] Add a changelog fragment for **failed/recovered-merge visibility** under `changelog/`.

**Checkpoint**: The failed state and its resolution are observable.

---

## Phase 5: Polish & Cross-Cutting Concerns

**PRs**: these distribute rather than forming one PR — T046 regen rides with **PR-3** (the enum); T044 audit rides with **PR-2** or a small follow-up hardening PR; T045 dev/knowledge note rides with **PR-5**; T047 test runs are per-PR CI; T048 `.spec-context` rides with the final PR.

- [ ] T044 Audit that **every** mutating API path funnels through `BranchStatusChecker.check` (GraphQL mutations, REST writes incl. `api/schema.py`, `api/artifact.py`); add coverage for any path that bypasses it (FR-001/009).
- [ ] T045 [P] Add a `dev/knowledge/backend/` note documenting recovery's dependency on the merge architecture (lock lifetime, bulk-merge `$at`, `previous_*` snapshots, IPAM reorder) so future merge-architecture changes re-evaluate it (contracts §10).
- [ ] T046 Regenerate offline artifacts touched by the enum (`uv run invoke backend.generate` → `schema/schema.graphql`; `cd frontend/app && pnpm codegen` only if the GraphQL schema changed) and run `uv run invoke format` + `uv run invoke lint`.
- [ ] T047 Run unit + component + functional suites (`uv run invoke backend.test-unit`; targeted `uv run pytest backend/tests/component/core/merge backend/tests/functional/merge`) and the integration-docker SIGKILL test; fix failures.
- [ ] T048 Update `.spec-context.json` step state.
- [ ] T049 Consolidate the merge components' logger type onto the structlog-shaped `InfrahubLogger` **Protocol**, removing the `Logger | LoggerAdapter | BoundLogger` union alias in `backend/infrahub/log.py`. Today the merge components accept the union because `core/branch/tasks.py` injects a Prefect flow-run logger (`get_run_logger()` → stdlib `logging.Logger`), which does **not** structurally satisfy the structlog Protocol (verified with mypy: stdlib `Logger.info` has no `**kwargs` catch-all, so a Protocol with `**kw: Any` is unsatisfiable; and a Protocol narrowed enough to admit `Logger` would reject structlog's idiomatic `log.info("event", key=val)` calls — ~73 such sites in `backend/infrahub`). The union is type-safe but reduces every component to the lowest common denominator (plain message + `extra=`) and loses structlog's structured logging. Fix by adapting at the wiring boundary: add a `StdlibToStructlogAdapter` (wraps a stdlib/Prefect logger, exposes the structlog method shape, renders structured kwargs into the message) in `backend/infrahub/log.py`; in `build_branch_merge_orchestrator` (`core/merge/builder.py`) wrap an injected logger once (`StdlibToStructlogAdapter(logger) if logger is not None else get_logger()`) and pass it to every component; then type all merge-component `logger` params against the **Protocol** alone. Entails: (a) moving/defining the `InfrahubLogger` Protocol in `log.py` (low-level, no heavy deps) and re-exporting from `services/protocols.py` to avoid the `infrahub.services` import cycle; (b) switching the merge components' `log.error("msg", extra={...})` calls (~3–4 sites in `orchestrator.py`/`update_coordinator.py`) to structlog-style `log.error("msg", error=...)`. Tradeoff to accept: through the stdlib sink, structured kwargs flatten into the message string rather than staying first-class fields. Deferred follow-up — separable from the merge-flow-refactor PR.

---

## Dependencies & Execution Order

- **US1 (Phase 1)** is the MVP: it introduces the `merge_started_at` field, the `merge:protected` cache-key helpers + module, the cache-aware async `BranchStatusChecker`, the merge-window marker, and the mandatory IPAM reorder (T005, load-bearing for US3).
- **US2 (Phase 2)** depends on US1's marker/gate; it adds the `MERGE_FAILED` enum, the grace setting, the predicate, the `MergeFailureRecovery` component (`detect_and_mark`), the recurring scan, the startup hook, and the fast paths/message.
- **US3 (Phase 3)** depends on US2 (`MERGE_FAILED` + `MergeFailureRecovery`) and on US1's T005 reorder; the range rollback (T025–T027) ‖ indexes/migration (T035/T036) ‖ migration co-write (T037) ‖ CLI/component (T028–T031). T027a (in-process unify) depends on T027 (the range entry must exist before the in-process path can switch onto it) and is **not** parallel with it.
- **US4 (Phase 4)** depends on US2/US3 emitting logs and on the enum (T010/T011).
- **Polish (Phase 5)** last.

Story chain: **US1 → US2 → US3 → US4**.

## Parallel Execution Examples

- **US2**: T010/T011 (enum + SDK) ‖ T012 (config) ‖ T013 (lock helper) ‖ T014/T015 (predicate + test) — separate files.
- **US3**: T025/T026 (rollback) ‖ T035/T036 (indexes/migration) ‖ T037 (migration co-write); component tests T032/T033 ‖ once targets exist.
- `[P]` tests within a story touch separate files and run together.

## Implementation Strategy

- **MVP = US1**: write protection during a healthy merge — deliverable and testable on its own, with its own changelog.
- **Increment 2 = US2**: deterministic detection + held protection.
- **Increment 3 = US3**: the `infrahub recover` path (gated by the **[ASK-FIRST]** approvals).
- **Increment 4 = US4**: observability.

## PR Plan

Each PR is sized to be independently reviewable, to leave the system in a working state, and to ship with its own tests + changelog. The three **[ASK-FIRST]** items are isolated into their own PRs so the DB/SDK approvals don't block feature review.

| PR | Tasks | Scope | Depends on | Notes |
|----|-------|-------|-----------|-------|
| **PR-1** | T005 | IPAM reorder (defer submit until after `MERGED`) | — | Standalone; safe to land first (no observable change for a successful merge). |
| **PR-2** | T001–T004, T006–T009 | US1 write-block: `merge_started_at` + `merge:protected` key + async cache-aware gate + merge/rebase block + tests + changelog | — | Pieces are inert apart — ship together. *Optional prep PR*: isolate the `BranchStatusChecker` async + `cache` injection (mechanical) if the caller set is wide. |
| **PR-3** | T010, T012–T024 (incl. T020a) (+ regen T046) | US2 detection: enum, predicate, `MergeFailureRecovery.detect_and_mark`, recurring merge-watcher, startup hook, fast paths, recovery exception + `MERGE_RECOVERY_REQUIRED` catalogue code, tests, changelog | PR-2 | Includes the GraphQL schema regen for the enum ([ASK-FIRST] additive value) and the error-catalogue bindings regen. *Optional split* 3a/3b (see Phase 2); US2's idle-SIGKILL independent test needs 3b. |
| **PR-4** | T011 | SDK `MERGE_FAILED` enum mirror | PR-3 | **[ASK-FIRST]** submodule bump (Jira IFC-2717). May land with PR-8. |
| **PR-5** | T025–T034, T038 (+ doc T045) | US3 recovery: range `RollbackQuery` + metadata restore + recover component + CLI + delete-block + tests + changelog | PR-3 | T031 (delete block) needs only `MERGE_FAILED` and could land earlier with US2. |
| **PR-6** | T035, T036 | Range-rollback edge `from`/`to` + node `updated_at` indexes + graph migration | pairs with PR-5 | **[ASK-FIRST]** DB change (Jira IFC-2715). Rollback works without it, just slower. |
| **PR-7** | T037 | Schema-migration queries co-write `previous_*` | pairs with PR-5 | **[ASK-FIRST]** migration change (Jira IFC-2716). Enables the SC-008 migration-collateral metadata restore. |
| **PR-8** | T039–T043 | US4 visibility & logging (+ tests) | PR-3, PR-5 | Small; or fold T039→PR-3 and T040→PR-5. T041 depends on PR-4 (SDK). |

**Merge order**: PR-1 (anytime) → PR-2 → PR-3 → PR-5 → PR-8; **PR-4 / PR-6 / PR-7** ([ASK-FIRST]) land in parallel once approved (PR-6/PR-7 alongside PR-5, PR-4 alongside PR-3 or PR-8).

**Per-PR changelog**: PR-1 (optional one-liner; no-op for successful merges), PR-2 (T009 write-protection), PR-3 (T024 detection), PR-5 (T038 recover), PR-8 (T043 visibility).

## Jira cross-reference — epic IFC-2559

| Jira | Type / Status | Summary | Maps to |
|---|---|---|---|
| **IFC-2437** | Bug · In Progress | Catastrophic merge failure leaves branch partially merged | Umbrella for **US2 + US3**. Update its scope to this spec. |
| **IFC-2562** | Task · Draft | Prevent writes to merging/default branch during merge | **US1** (T001–T009). ⚠️ reconcile with the existing `branch-merge-locking-ifc-2562` branch. |
| **IFC-2563** | Task · Draft | Wait to start merge until in-flight writes are done | **Out of scope** (decided 2026-06-09); stays tracked separately. |
| **IFC-2565** | Task · Draft | Surface error to user/admin on a crashed merge worker | **US2 + US4** (T020 message; T039/T041 visibility + logs). |
| **IFC-2566** | Task · Draft | Tool to reset the app to pre-merge state | **US3** — `infrahub recover` (T025–T038). |
| **IFC-2438** | Bug · ✅ Done | Move merge logic to the database level | **Prerequisite, done** — the bulk-merge architecture this builds on. |
| **IFC-2564** | Bug · ✅ Done | Reset Proposed Change on a failed merge (caught-exception path) | **Related, done**; the crash-recovery PC reset is T029. |
| **IFC-2560 / IFC-2561** | Task · Draft | Merge **performance** testing/validation | **Out of scope** (performance workstream). |

**New issues created (2026-06-09, under IFC-2559)** — descriptions reference these task numbers:

| Jira | Summary | Spec tasks |
|---|---|---|
| **IFC-2715** | graph indexes + migration for range-based rollback | T035, T036 |
| **IFC-2716** | schema migrations co-write `previous_updated_at/by` | T037 |
| **IFC-2717** | `MERGE_FAILED` in the Python SDK `BranchStatus` enum | T011 |
