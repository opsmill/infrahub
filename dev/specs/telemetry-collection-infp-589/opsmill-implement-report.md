# Implementation Report: Phase 1 Telemetry Collection

## 1. Header

- **Feature**: Phase 1 Telemetry Collection
- **Spec dir**: `specs/telemetry-collection-infp-589` (real path `dev/specs/telemetry-collection-infp-589`)
- **Base commit**: `802234224`
- **Head commit**: `829197d1a`
- **Branch**: `telemetry-collection-infp-589`
- **Run status**: ✅ COMPLETE (all code tasks done; local-pass evidence has no MISSING rows). One **process** task (T030 governance gate) remains open as an external pre-merge dependency.
- **Mode**: interactive, clean-context subagent per chunk; path-scoped commits (the working tree had unrelated pre-existing dirty files, which were kept out of every commit).

## 2. Chunk-by-chunk ledger

| # | Chunk (phase) | Tasks | Outcome | Commit | Notes flagged upward |
|---|---------------|-------|---------|--------|----------------------|
| 1 | Setup | T001–T002 | 2 ✅ | `5b9622599` | Changelog `added` category; test skeletons collect cleanly. |
| 2 | Foundational | T003–T006 | 4 ✅ | `0805c3658` | Helper named `safe_metric` (PEP 695 generic); `node_count` widened to `dict[str,int\|None]`; placeholder `accounts`/`activity_24h` left at call site for later wiring. |
| 3 | US1 activity_24h enabler | T007–T014 (+T009b) | 9 ✅ | `2656de3c8` | **Prefect is 3.7.5** (not 2026.05 as AGENTS.md claims). **`TIMEDOUT` is not a real StateType** → failure = `FAILED`+`CRASHED`. Flow-run `start_time` not client-settable. `freezegun` not installed → window helper takes explicit `now`; `safe_metric` moved to `utils.py` (import-cycle) and re-exported. |
| 4 | US2 accounts/branches | T015–T018 | 4 ✅ | `5931d35a0` | Status filter `status__value="active"`. Subagent omitted its evidence block; orchestrator **independently re-ran** the tests to capture it (below). |
| 5 | US3 corenode | T019–T021 | 3 ✅ | `6dde986c2` | Independent oracle = raw label count (distinct path from `NodeManager.count`); TDD red `KeyError: 'corenode'` → green. |
| 6 | US5 checks/artifacts/branches | T022–T023 | 2 ✅ | `f5f839f38` | Real event-name constants; removed 8 now-stale `None` assertions from the US1 test. |
| 7 | US4 resilience | T024–T026 | 3 ✅ | `b1da82dbf` | No-mock seam = 3 optional injected async callables with prod defaults; T026 audit wrapped orchestrator-level assembler calls in `safe_metric`; caught a real cross-test flake + a `registry.id` teardown leak via self-review. |
| 8 | Polish + review fix | T027–T030 | 3 ✅, 1 open | `829197d1a` | Suite green, lint clean, local simulation done. **Review fix applied** (webhook count — see §5). T030 governance gate open. |

## 3. Tasks not completed

- **T030 — Governance gate (GR-001)**: confirm the cloud-processor + data-mart owners tolerate the `payload_format` bump, ignore unknown fields, and tolerate `null` values (incl. `corenode` in `node_count`). This is an explicit **process/external** task, not code; it must be done before merge/release. No code or test depends on it.

All implementation tasks T001–T029 are `[X]`.

## 4. Local-pass evidence

All tests run with `DOCKER_HOST=unix:///Users/Dimitris/.docker/run/docker.sock` (component tests use testcontainers Neo4j + ephemeral Prefect; unit tests need neither). Authoritative post-everything run: **`62 passed`** at `2026-06-29T08:25:08Z` (`uv run pytest backend/tests/unit/telemetry backend/tests/component/telemetry -q`).

| Test id | Type | Run command | Passed at (ISO 8601) | Env | Verbatim pass line |
|---------|------|-------------|----------------------|-----|--------------------|
| `test_degradation.py::test_raising_coroutine_degrades_to_none`, `::test_zero_result_is_preserved`, `::test_non_zero_result_is_preserved` | unit | `uv run pytest backend/tests/unit/telemetry/test_degradation.py -v` | 2026-06-28T21:36:07Z | n/a (no DB/mock; plain coroutines) | `3 passed, 16 warnings in 0.11s` |
| `test_task_manager.py::test_window_is_previous_full_utc_day`, `::test_floor_to_midnight_utc`, `::test_windowed_logins_count`, `::test_windowed_unique_logins_count`, `::test_windowed_logins_exclude_out_of_window`, `::test_webhook_success_failure_split`, `::test_webhook_split_excludes_out_of_window`, `::test_gather_activity_24h_logins`, `::test_gather_prefect_events_unchanged` | component | `uv run pytest backend/tests/component/telemetry/test_task_manager.py -v -p no:randomly` | 2026-06-28T21:53:06Z | testcontainers Neo4j + prefect_test_fixture | `10 passed, 16 warnings in 10.95s` (incl. `test_gather_prefect_information`) |
| `test_task_manager.py::test_gather_activity_24h_checks_artifacts_branches[checks_started\|checks_passed\|checks_failed\|artifacts_created\|artifacts_updated\|branches_created\|branches_merged\|branches_deleted]` | component | `uv run pytest backend/tests/component/telemetry/test_task_manager.py -v -p no:randomly` | 2026-06-29T00:00:00Z | testcontainers Neo4j + prefect_test_fixture | `18 passed, 16 warnings in 12.01s` |
| `test_tasks.py::test_gather_account_information_counts`, `::test_active_branches_excludes_default_and_global` | component | `uv run pytest backend/tests/component/telemetry/test_tasks.py -v -p no:randomly` | 2026-06-28T22:05:50Z (orchestrator-captured) | testcontainers Neo4j + registry | `2 passed, 16 warnings in 21.04s` |
| `test_tasks.py::test_gather_full_payload_fields_present`, `::test_gather_genuine_empty_activity_is_zero`, `::test_gather_one_source_fails_others_populated_and_stored`, `::test_gather_activity_source_fails_only_activity_null`, `::test_gather_branch_source_fails_only_branch_active_null` | component | `uv run pytest backend/tests/component/telemetry/test_tasks.py -v -p no:randomly` | 2026-06-29T08:10:25Z | testcontainers Neo4j + MemoryCache + BusSimulator | `7 passed, 16 warnings in 53.54s` |
| `test_datatabase.py::test_gather_database_information_corenode_matches_seeded` | component | `uv run pytest backend/tests/component/telemetry/test_datatabase.py -v -p no:randomly` | 2026-06-28T22:10:20Z | testcontainers Neo4j (2026.05.0-enterprise) | `4 passed, 16 warnings in 22.63s` |

No E2E tests are part of this feature (producer-only backend; no UI). No row is `MISSING`.

## 5. Review findings

| Severity | File | Finding | Disposition |
|----------|------|---------|-------------|
| 🔴 Medium-High | `telemetry/task_manager.py` | `count_webhook_runs` used `len(read_flow_runs(...))`, which caps at the Prefect server default page size (`PREFECT_API_DEFAULT_LIMIT = 200`) — a deployment with >200 webhook successes/day would silently report exactly 200. | **Fixed inline** in `829197d1a` — switched to `client.count_flow_runs(...)` (exact, unpaginated). Webhook tests + full suite re-run green. |
| 🟡 Low (verify) | `telemetry/task_manager.py` | `count_windowed_unique_resources` returns `len(buckets)` from `/events/count-by/resource`; if that endpoint caps the number of buckets returned, `unique_logins` could undercount on very-high-cardinality days. (count-by/**event** is safe — it returns a server-side aggregate `count`, not a list length.) | **Deferred** — lower confidence, and the metric is an explicit best-effort trend signal. Worth confirming the count-by/resource bucket limit before relying on `unique_logins` at scale. |
| 🟡 Low (doc) | spec/contract/data-model/research | Docs list webhook failure as `FAILED`/`CRASHED`/`TIMEDOUT`, but `TIMEDOUT` is not a Prefect 3.7.5 `StateType`; the code correctly uses `FAILED`+`CRASHED`. | **Deferred doc fix** — implementation is correct; the design docs should drop `TIMEDOUT` to match reality. |
| 🔵 Observation | `telemetry/database.py` (corenode) | Live simulation showed `corenode` excludes account **groups** (`get_labels()` doesn't apply the `CoreNode` label to group-generic nodes). This is faithful to the documented "CoreNode-generic" definition, not a bug — but if the product wants groups counted as "managed nodes," that is a definitional choice tied to the parked `user` metric (IFC-2825). | **No change** — surfaced for product awareness. |

## 6. Autonomous decisions

- **Dirty-tree handling**: the working tree had many pre-existing unrelated changes. With user approval, every subagent committed by **explicit path only** (never `git add -A`); verified after every chunk that the feature diff stayed within `telemetry/**`, `tests/**/telemetry/**`, `changelog/`, and the spec dir. No unrelated file was committed.
- **Chunking**: one chunk per `tasks.md` phase (8 chunks); US1 kept as a single 9-task chunk (tightly coupled windowed-path work in 3 files).
- **Chunk-4 evidence gap**: that subagent omitted its mandatory evidence block; rather than accept the claim, the orchestrator re-ran the two tests itself to capture verbatim evidence.
- **No-mock resilience seam (US4)**: accepted the optional-injection compromise (3 injected callables with prod defaults) over a larger DI refactor, per the backend-component-design "existing code" exception.
- **Review fix applied inline** (webhook count) rather than deferred, given it's a real accuracy bug with a small localized fix.
- **`speckit-review-run` / `speckit-critique-run` not installed** → review performed directly on the committed diff.
- **Simulation** delivered as a removable demo (kept in scratchpad, not committed) — it hardcodes a scratchpad path and would add ~46s to the component suite, so it does not belong in the committed test set.

## 7. Suggested next steps

1. **Resolve the governance gate (T030)** — confirm with the cloud-processor + data-mart owners (the one open item; gates merge/release).
2. **Decide the two deferred review findings**: (a) verify the count-by/resource bucket limit for `unique_logins` at scale; (b) drop `TIMEDOUT` from the design docs to match the implementation.
3. **Open a PR** from `telemetry-collection-infp-589` once T030 is confirmed.
4. Optionally fold the local-collection simulation into a committed smoke test if a repeatable end-to-end demo is wanted (parameterize the scratchpad path first).
