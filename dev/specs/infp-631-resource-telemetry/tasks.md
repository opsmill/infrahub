# Tasks: Licensing Resource-Allocation Telemetry

**Input**: Design documents from `dev/specs/infp-631-resource-telemetry/` (`specs/` is a symlink to `dev/specs/`)

**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/telemetry-resources.md, quickstart.md

**Tests**: Included — the spec's acceptance scenarios and Constitution IV (Test Discipline) require them. Pure-logic tests (cgroup parsing, and first the aggregation, since replaced by the per-worker share in T023) are written TDD-first; component tests use the testcontainers stack with synthesized heartbeats (no mocking library, per the adapter/protocol rule; see Notes for the two `monkeypatch.setattr` uses).

**Organization**: Grouped by user story (US1 → US2 → US3) so each is an independently testable increment.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies on incomplete tasks)
- **[Story]**: US1/US2/US3 for user-story tasks; omitted for Setup/Foundational/Polish

## Path Conventions

Single backend project. Source under `backend/infrahub/`, tests under `backend/tests/`.

---

## Phase 1: Setup

**Purpose**: Create the reader module the rest of the feature builds on. A `probe-resources` command was added later in review (T020) and removed again (T025).

- [x] T001 Create the resource-reader module scaffold at `backend/infrahub/telemetry/resources.py` (module docstring + typed stub signatures for the reader and aggregation functions; no logic yet). The aggregation was later replaced by the per-worker share (T023)

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: The shared plumbing every user story builds on — payload models, the host/cgroup reader, the aggregation function (replaced by the per-worker share in T023), and the heartbeat self-report. **No user story can start until this phase is complete.**

- [x] T002 Extend the payload models in `backend/infrahub/telemetry/models.py`: add `processor_assigned: int | None = None` to `TelemetryDatabaseSystemInfoData`; add `processor_available`/`processor_assigned`/`memory_total`/`memory_available` (`int | None = None`) to `TelemetryWorkerData`; add a new `TelemetryServerData` (same four fields) and a `server: TelemetryServerData` field (default factory) on `TelemetryData` — additive only, no existing field renamed/removed/retyped. Superseded in part by T021 and T023 (research D15, D16): `TelemetryServerData` also carries `total`/`active`, and on both blocks the four fields moved under a `per_worker` object (`TelemetryPerWorkerData`). Superseded in part by T024 (research D17): `TelemetryWorkerData` is unchanged from before this feature, and `TelemetryServerData` became `TelemetryComponentData`, used by both the `server` and the new `task_workers` field on `TelemetryData`
- [x] T003 [P] Unit test the reader in `backend/tests/unit/telemetry/test_resources.py`: cgroup v2 limited/unlimited (`cpu.max`), v1 limited/unlimited (`cpu.cfs_quota_us`/`cfs_period_us`, `-1` sentinel, memory near-`INT64_MAX` sentinel), a fractional quota rounds `processor_assigned` up and `processor_available` down (minimum 1), missing files → `processor_assigned is None` with memory from psutil's whole-host figures, `processor_available` logical and capped by the quota and by the CPU-affinity mask (the host's `psutil.cpu_count(logical=True)` when nothing restricts it). Write against fixture files; assert before implementation. The same reader is also run against real kernel control groups, in containers, by `backend/tests/component/telemetry/test_cgroup_kernels.py`
- [x] T004 Implement the reader in `backend/infrahub/telemetry/resources.py`: logical cores (`psutil.cpu_count(logical=True)`) capped by the CPU quota rounded down (minimum 1) and by the CPU-affinity mask, cgroup CPU quota (v2 `cpu.max` then v1, unlimited → `None`, rounded up for `processor_assigned`), host memory (`psutil.virtual_memory()` total + available), cgroup memory (the most restrictive `memory.max` → `memory_total`, the smallest `max(0, limit − usage)` across limited levels → `memory_available`), host id (`socket.gethostname()` followed by the PID namespace from `/proc/self/ns/pid`, research D7); expose a per-process `ProcessResources` reader that **caches the host identity, resolved cgroup path, and host's logical CPU count once, and re-reads the CPU quota, `processor_available`/`processor_assigned`, `memory_total`, and `memory_available` on every call** (research D12)
- [x] T005 [P] Unit test aggregation in `backend/tests/unit/telemetry/test_aggregation.py`: dedup identical readings by host, sum across distinct hosts, undercount when a host is missing, no host reported a field → `None`, any contributing host unbounded → that field `None` (research D8/D9). The aggregate returns only the four fields — the worker count stays the existing `workers.total`/`active`, not part of the aggregate. Assert before implementation. Superseded by T023 (research D16): `test_aggregation.py` was removed, replaced by the parametrized `test_per_worker_share` in `backend/tests/unit/telemetry/test_tasks.py`
- [x] T006 Implement the aggregation function in `backend/infrahub/telemetry/resources.py`: `aggregate(readings)`, returning the four fields (`processor_available`/`processor_assigned`/`memory_total`/`memory_available`), applying the dedup/sum/null rules — a pure function over the per-process readings, whose result is applied to the new `server` block and to the extended `workers` fields (depends on T005). Superseded by T023 (research D16): `aggregate()` and `ResourceAggregate` were removed in favour of `_per_worker_share()` in `backend/infrahub/telemetry/tasks.py`
- [x] T007 Extend the heartbeat in `backend/infrahub/services/component.py`: at `refresh_heartbeat`, write `workers:resources:{component}:worker:{WORKER_IDENTITY}` with this process's reading (re-read on every heartbeat; only host identity, cgroup path and host CPU count are cached — research D12), TTL `KVTTL.FIFTEEN`; on exhausted retries, log a warning carrying the component type + worker identity + error text before writing `null` (FR-005 traceability); add a **new** `read_worker_resources()` method that scans `workers:resources:*` and returns readings grouped by component + host. **Do NOT modify `list_workers` / `WorkerInfo`** — existing `workers.total`/`active` logic stays untouched (critique E1). Superseded in part by research D15 (T021): `WorkerInfo` gains a `component` attribute, set by `add_key`. Since T024 (research D17) that attribute feeds only the `server` and `task_workers` counts, and `workers.total`/`active` are counted as before. Superseded in part by T022: the reading is taken by a 10-second main-loop schedule, and the 5-second heartbeat thread writes the latest published reading. Superseded in part by T023: `read_worker_resources()` returns every reading per component, no longer one per host

**Checkpoint**: Models, reader, aggregation (replaced by the per-worker share in T023), and heartbeat self-report exist and are unit-tested.

---

## Phase 3: User Story 1 — Audit a deployment against its tier (Priority: P1) 🎯 MVP

**Goal**: The daily snapshot carries per-component CPU/RAM — `processor_available` + `memory_total`/`memory_available` for database, server, and task workers, with `processor_assigned` live-read (null wherever its limit is unset) — extended in place on `system_info`, plus new `server` and `task_workers` blocks (the task-worker figures sat on `workers` until T024), so a reviewer can compare against the contracted tier.

**Independent Test**: Run the gather on the testcontainers stack with synthesized worker heartbeats; assert `database.system_info.processor_assigned` and the new `server` and `task_workers` blocks are populated, and the server's per-worker figure is its container divided between the gunicorn processes that share it (T023).

- [x] T008 [P] [US1] Component test in `backend/tests/component/telemetry/test_resources.py`: seed api_server + git_agent `workers:active:*` and `workers:resources:*` keys (two git_agent hosts, one api_server host), run the gather, assert `workers.processor_*`/`memory_*` equal the git_agent host sum, the new `server` block reflects the one api_server host (counted once, not per gunicorn process), `workers.total == 2` is unchanged, and `database.system_info.processor_assigned is None`. Assert before implementation. Superseded in part by T023: the test now asserts each block's `per_worker` share — one git_agent container's figures, and a third of an api_server container shared by three processes. Superseded in part by T024: the task-worker figures and counts are asserted on `task_workers`, and `workers` counts every worker process, including a seeded process known only by its presence key
- [x] T009 [US1] Database field in `backend/infrahub/telemetry/database.py`: in `get_system_info`, read `server.cypher.parallel.worker_limit` via `SHOW SETTINGS YIELD name, value` and set `processor_assigned` on the returned `TelemetryDatabaseSystemInfoData` (`0`/auto → `None`); the existing `processor_available` / `memory_*` already carry DB cores-available and memory — no new DB block, no duplication
- [x] T010 [US1] Gather wiring in `backend/infrahub/telemetry/tasks.py`: from `component.read_worker_resources()` (T007), aggregate git_agent hosts into the new `workers` resource fields and api_server hosts into a `TelemetryServerData`, via `aggregate()` (T006), each wrapped in `safe_metric`; populate the extended `workers` block and set `server` on `TelemetryData`. DB `processor_assigned` flows in through `gather_database_information` (T009). Superseded in part by T023: the gather fills each block's `per_worker` through `_per_worker_share()`, and only the `read_worker_resources()` scan is `safe_metric`-wrapped. Superseded in part by T024: the task-worker share goes to the new `task_workers` block, not `workers`
- [x] T011 [US1] Additive-safety test in `backend/tests/component/telemetry/test_resources.py`: assert `TELEMETRY_VERSION` is unchanged (version bump is deferred — research D13) and every key the payload emitted before this feature is still present (SC-005): the test compares the key sets of `data`, `workers`, `server`, `task_workers`, and `system_info`, and checks that `workers.total`/`active` are still integers. Since T024, `workers` has exactly its earlier keys, `total` and `active`, with their earlier meaning; T021 had changed which processes they count

**Checkpoint**: MVP — the snapshot carries the new resource fields (DB `processor_assigned`, task-worker and server CPU/RAM); tier audit is possible from one snapshot.

---

## Phase 4: User Story 2 — Audit an offline / air-gapped deployment (Priority: P2)

**Goal**: The new resource fields are in the locally stored snapshot even when the deployment has opted out of remote transmission.

**Independent Test**: Set `telemetry_optout = true`, run the flow, confirm the locally stored snapshot contains the new resource fields and nothing is transmitted.

- [x] T012 [P] [US2] Component test in `backend/tests/component/telemetry/test_resources.py`: with `telemetry_optout = true`, run `send_telemetry_push`, assert the stored snapshot carries the new resource fields (`workers.processor_*`/`memory_*` — `per_worker` on `workers` and `server` since T023, and on `task_workers` instead of `workers` since T024 — the `server` block, `system_info.processor_assigned`) and `remote_send_status == SKIPPED` (no POST)
- [x] T013 [US2] Verify in `backend/infrahub/telemetry/tasks.py` that the resource fields are assembled during `gather()` (before the storage + opt-out branch) so they are always in the local snapshot; adjust ordering only if the test in T012 shows a gap

**Checkpoint**: Air-gapped deployments carry the metrics locally with no transmission.

---

## Phase 5: User Story 3 — Preserve the audit when a source cannot be read (Priority: P3)

**Goal**: A failing source nulls only the figures that depend on it; a worker that does not report is still counted while the per-worker share comes from one that did (T023); the snapshot is produced whenever the database's existing system-information read succeeds.

**Independent Test**: Force a single source to raise and confirm only the figures depending on it are null, the rest intact, snapshot produced; drop one worker's resource key and confirm the count still includes it while the share comes from the worker that reported.

- [x] T014 [P] [US3] Component test in `backend/tests/component/telemetry/test_resources.py`: (a) force the `server.cypher.parallel.worker_limit` read to raise → `system_info.processor_assigned is None`, snapshot still produced; (b) one active git_agent worker with no `workers:resources` key → the `workers` resource fields sum the reporters (undercount) while `workers.total` still counts it; (c) one worker host unbounded → `workers.processor_assigned is None`; (d) assert a warning is logged (with component + error context, via `caplog`) when a self-read fails after its bounded retries (FR-005). Superseded in part by T023 and T024: (b) now asserts the reporting worker's share is used while `task_workers.total` still counts the silent worker, and (c) was removed with the aggregation's all-or-null rule. A separate test covers a corrupted cache entry, which is dropped
- [x] T015 [US3] Harden `backend/infrahub/telemetry/tasks.py` and `resources.py` so every block/field is independently `safe_metric`-wrapped and the aggregation applies the D9 null-vs-zero/undercount rules exactly; confirm no single failure in the *resource* fields can raise out of `gather()`. One exception remains outside this feature's scope: `gather_database_information`/the JMX `get_system_info` are not `safe_metric`-wrapped (pre-existing), so a DB/JMX failure still aborts the snapshot — tracked as a follow-up rather than fixed here. Superseded in part by T023: the D9 rules went with the aggregation; per-field failures are caught inside the reader, and only the database `processor_assigned` read and the `read_worker_resources()` scan are `safe_metric`-wrapped

**Checkpoint**: The resource fields degrade gracefully and never block a snapshot.

---

## Phase 6: Polish & Cross-Cutting Concerns

- [x] T016 [P] Regression test in `backend/tests/component/telemetry/test_resources.py`: adding the `workers:resources:*` heartbeat key leaves `workers.total` and `workers.active` unchanged versus a baseline without it (critique E1). It checks the `server` and `task_workers` counts the same way
- [x] T017 [P] Add a Towncrier changelog fragment `changelog/+resource-telemetry.added.md` describing the new per-component CPU/memory fields (the extended `system_info` plus the new `server` and `task_workers` blocks) (Constitution: user-facing telemetry change). Review added three more fragments, for the control-group path resolution, the `probe-resources` command (T020) and the count change in T021. The count change was undone by T024 and the command removed by T025. The path-resolution fragment was merged into `+resource-telemetry.added.md`, because the feature has never shipped
- [x] T018 [P] Update the telemetry FAQ in `docs/docs/faq/faq.mdx` to mention the per-component cores/RAM fields for the database, the API server and the workers
- [x] T020 Add the `infrahub telemetry probe-resources` command in `backend/infrahub/cli/telemetry.py`, which reports the reading alongside the control-group evidence behind it, with `backend/tests/unit/cli/test_telemetry.py` and the generated reference page `docs/docs/reference/infrahub-cli/infrahub-telemetry.mdx` (plus its `docs/sidebars.ts` entry). Added during review, not planned up front: the reader's figures are unexplainable from the payload alone, so an environment reporting a surprising number had no way to show its own evidence. Removed by T025
- [x] T021 Scope each block's count to its own component (research D15): `WorkerInfo` gains a `component` attribute, set by `add_key` from the process's own keys, the gather splits `workers.total`/`active` to task-workers and adds `server.total`/`active`, with unit tests for the attribution and the component tests updated. Added in review; it narrows the meaning of an existing field, the one recorded exception to FR-008's additive-only rule. Reversed by T024: `workers.total`/`active` count every worker process again. The `component` attribute and its unit tests stay, and now feed the `server` and `task_workers` counts
- [x] T022 After rebasing onto the heartbeat that runs on its own thread: move the resource read to a 10-second main-loop schedule that publishes the latest reading, and have the liveness beat write that reading beside its active key, so the beat keeps touching only the cache (research D6). Unit tests cover the beat carrying a published reading and writing none before the first. Superseded in part by a review finding: the schedule and the startup heartbeat run the read on a separate thread, so a slow read cannot hold up the main loop
- [x] T023 Replace the fleet totals with a per-worker share (research D16): on `workers` and `server` the four resource figures move under `per_worker` (`TelemetryPerWorkerData`; processor figures `float` rounded to two decimals, memory in whole bytes rounded down), computed by `_per_worker_share()` in `backend/infrahub/telemetry/tasks.py` from the most complete healthy reading divided by every reading from the same host, failed ones included. `read_worker_resources()` returns every reading per component. `aggregate()`, `ResourceAggregate`, the gather's `_build_worker_data()`/`_build_server_data()` and `backend/tests/unit/telemetry/test_aggregation.py` are removed; the parametrized `test_per_worker_share` in `backend/tests/unit/telemetry/test_tasks.py` covers the share, and the component tests assert `per_worker`. The three existing `system_info` figures keep their plain `int` type without a non-negative constraint, since a failed constraint would abort the unguarded database gather. Added in review. Superseded in part by T024: the task workers' `per_worker` moved from `workers` to the new `task_workers` block
- [x] T024 Keep `workers` unchanged and break it down in new blocks (research D17): `TelemetryWorkerData` goes back to `total`/`active` only, counting every worker process as before this feature. `TelemetryServerData` is renamed `TelemetryComponentData` and used for two fields on `TelemetryData`: `server` and a new `task_workers`, each with `total`, `active` and `per_worker`. The `+telemetry-worker-count-scope.changed.md` fragment is deleted. The gather component test seeds a process known only by its presence key and asserts that `workers` counts it while neither new block does; the payload test asserts that `workers` has exactly `total` and `active`. Added in review; it reverses T021, so FR-008 holds with no exception
- [x] T025 Remove the `probe-resources` command (T020): the command and its registration, its unit tests, its generated reference page, sidebar entry and generator entry, the reader code only it used (`diagnose()`, `ResourceDiagnostics`, `CgroupLevel`) with its four unit tests, and the spelling exceptions added for its docs. The reader's own tests, including the real-kernel cases, cover the figures it explained
- [x] T019 Run the quickstart validation (`uv run invoke backend.test-unit`; component tests via testcontainers) and `uv run invoke format` + `uv run invoke lint`; fix any failures

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (T001)**: no dependencies.
- **Foundational (T002–T007)**: after Setup; **blocks all user stories**. Within it: T003→T004 (reader TDD), T005→T006 (aggregation TDD, superseded by T023), T007 depends on T004.
- **US1 (T008–T011)**: after Foundational. T009 depends on T002; T010 depends on T006, T007, T009; T008/T011 are the story's tests.
- **US2 (T012–T013)**: after US1 (needs the block assembled).
- **US3 (T014–T015)**: after US1.
- **Polish (T016–T025)**: after all desired stories.

### Within Each User Story

- Pure-logic tests (T003, T005) are written first and must fail before their implementation.
- Models before reader/aggregation; reader/aggregation before gather wiring; gather wiring before the opt-out and degradation guarantees. The aggregation was later replaced by the per-worker share (T023).

### Parallel Opportunities

- T003 and T005 (different test files) can run in parallel.
- Foundational done → the three story test skeletons (T008, T012, T014) can be drafted in parallel.
- Polish T016/T017/T018 are independent files → parallel.

## Parallel Example: Foundational tests

```bash
# The two pure-logic test files have no shared state:
Task: "Unit test the reader in backend/tests/unit/telemetry/test_resources.py"
Task: "Unit test aggregation in backend/tests/unit/telemetry/test_aggregation.py"
# test_aggregation.py was later removed by T023
```

## Implementation Strategy

### MVP First (User Story 1)

1. Phase 1 (Setup) → Phase 2 (Foundational) → Phase 3 (US1).
2. **STOP and VALIDATE**: the snapshot carries the populated `system_info`/`server`/`task_workers` resource fields; the tier audit is possible. This is the shippable MVP.

### Incremental Delivery

- MVP (US1) → add US2 (air-gapped guarantee, mostly a test) → add US3 (degradation hardening) → Polish.
- Each increment is additive and cannot regress the previous one (the whole feature is additive to the payload).

## Notes

- **No version bump in this phase**: `TELEMETRY_VERSION` is intentionally left unchanged (research D13); the bump is a gated follow-up once the receiving service confirms tolerance. Nothing in these tasks edits `constants.py`.
- **No mocking library**: component tests drive the real gather against testcontainers Neo4j with synthesized cache keys (adapter/protocol rule), and the failed self-read test injects a `ProcessResources` subclass that always raises. Two component tests use pytest's `monkeypatch.setattr`: one sets `telemetry_optout`, one replaces the worker-limit setting name so the database read fails. Unit tests use fixture cgroup files, not patches; the host's logical CPU count and CPU-affinity mask are still read live.
- **Code-doc style**: the "how it's supposed to work" comments on the `assigned` reads explain the mechanism (Neo4j setting / container CPU quota, `0`/unlimited → `None`); they must not cite Jira/spec IDs or name other functions.
- Commit after each task or logical group; each story is independently testable at its checkpoint.
