# Tasks: Licensing Resource-Allocation Telemetry

**Input**: Design documents from `dev/specs/infp-589-resource-telemetry/` (`specs/` is a symlink to `dev/specs/`)

**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/telemetry-resources.md, quickstart.md

**Tests**: Included — the spec's acceptance scenarios and Constitution IV (Test Discipline) require them. Pure-logic tests (cgroup parsing, aggregation) are written TDD-first; component tests use the testcontainers stack with synthesized heartbeats (no mocking, per the adapter/protocol rule).

**Organization**: Grouped by user story (US1 → US2 → US3) so each is an independently testable increment.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies on incomplete tasks)
- **[Story]**: US1/US2/US3 for user-story tasks; omitted for Setup/Foundational/Polish

## Path Conventions

Single backend project. Source under `backend/infrahub/`, tests under `backend/tests/`.

---

## Phase 1: Setup

**Purpose**: Create the one new module the feature adds.

- [ ] T001 Create the resource-reader module scaffold at `backend/infrahub/telemetry/resources.py` (module docstring + typed stub signatures for the reader and aggregation functions; no logic yet)

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: The shared plumbing every user story builds on — payload models, the host/cgroup reader, the aggregation function, and the heartbeat self-report. **No user story can start until this phase is complete.**

- [ ] T002 Add Pydantic models in `backend/infrahub/telemetry/models.py`: `TelemetryComponentResources` (cores_available/cores_assigned/ram_available/ram_used, all `int | None`, with a `default()`), `TelemetryWorkerResources` (adds `count: int = 0`), `TelemetryResourcesData` (database/server/workers), and add `resources: TelemetryResourcesData` to `TelemetryData` with a default factory — additive only, no existing field touched
- [ ] T003 [P] Unit test the reader in `backend/tests/unit/telemetry/test_resources.py`: cgroup v2 limited/unlimited (`cpu.max`), v1 limited/unlimited (`cpu.cfs_quota_us`/`cfs_period_us`, `-1` sentinel, memory near-`INT64_MAX` sentinel), fractional quota rounds up, missing files → `None`, `cores_available` always logical (`os.cpu_count()`). Write against fixture files; assert before implementation
- [ ] T004 Implement the reader in `backend/infrahub/telemetry/resources.py`: logical cores (`os.cpu_count()`), cgroup CPU quota (v2 `cpu.max` then v1, unlimited → `None`, round up), host memory (`psutil` total/used), cgroup memory (`memory.max`/`memory.current`), host id (`socket.gethostname()`); expose a per-process `ProcessResources` reader that **reads the static fields once and caches them, refreshing only `ram_used`** (research D12)
- [ ] T005 [P] Unit test aggregation in `backend/tests/unit/telemetry/test_aggregation.py`: dedup identical readings by host, sum across distinct hosts, undercount when a host is missing, `count` reflects all active processes, zero-workers → `0`, active-but-none-reported → `None`, any contributing host unbounded → aggregate field `None` (research D8/D9). Assert before implementation
- [ ] T006 Implement the aggregation function in `backend/infrahub/telemetry/resources.py`: `aggregate(readings) -> TelemetryComponentResources` (+ worker variant returning `TelemetryWorkerResources` with `count`), applying the dedup/sum/null rules — a pure function taking the list of per-process readings (depends on T005)
- [ ] T007 Extend the heartbeat in `backend/infrahub/services/component.py`: at `refresh_heartbeat`, write `workers:resources:{component}:worker:{WORKER_IDENTITY}` with this process's reading (static cached, `ram_used` refreshed), TTL `KVTTL.FIFTEEN`; add a **new** `read_worker_resources()` method that scans `workers:resources:*` and returns readings grouped by component + host. **Do NOT modify `list_workers` / `WorkerInfo`** — existing `workers.total`/`active` logic stays untouched (critique E1)

**Checkpoint**: Models, reader, aggregation, and heartbeat self-report exist and are unit-tested.

---

## Phase 3: User Story 1 — Audit a deployment against its tier (Priority: P1) 🎯 MVP

**Goal**: The daily snapshot carries a populated `resources` block — cores/RAM available for database, server, and workers, with `cores_assigned` live-read (null today) — so a reviewer can compare against the contracted tier.

**Independent Test**: Run the gather on the testcontainers stack with synthesized worker heartbeats; assert `resources.{database,server,workers}` are present with `cores_available`/`ram_*` populated, `cores_assigned` null, and the server row not multiplied by gunicorn process count.

- [ ] T008 [P] [US1] Component test in `backend/tests/component/telemetry/test_resources.py`: seed api_server + git_agent `workers:active:*` and `workers:resources:*` keys (two worker hosts, one api_server host), run the gather, assert the block is populated, server counts each container once, `workers.count == 2`, aggregates equal the host sum, and `database.cores_assigned is None`. Assert before implementation
- [ ] T009 [US1] Database row in `backend/infrahub/telemetry/database.py`: build `resources.database` reusing the existing JMX `get_system_info` numbers (cores_available ← `AvailableProcessors`, ram_available ← `TotalMemorySize`, ram_used ← `TotalMemorySize − FreeMemorySize`) and read `server.cypher.parallel.worker_limit` via `SHOW SETTINGS YIELD name, value` for `cores_assigned` (`0`/auto → `None`); **leave the existing `database` block and `system_info` unchanged** (parallel field, minor redundancy)
- [ ] T010 [US1] Gather wiring in `backend/infrahub/telemetry/tasks.py`: assemble `TelemetryResourcesData` inside `gather()` — database row (T009), plus `server`/`workers` from `component.read_worker_resources()` (T007) fed through `aggregate()` (T006) — each block wrapped in `safe_metric`; set `resources` on the built `TelemetryData`
- [ ] T011 [US1] Additive-safety test in `backend/tests/component/telemetry/test_resources.py`: assert `TELEMETRY_VERSION` is unchanged (version bump is deferred — research D13) and every field the payload emitted before this feature is still present and unchanged (SC-005)

**Checkpoint**: MVP — the snapshot carries the full resources block; tier audit is possible from one snapshot.

---

## Phase 4: User Story 2 — Audit an offline / air-gapped deployment (Priority: P2)

**Goal**: The `resources` block is in the locally stored snapshot even when the deployment has opted out of remote transmission.

**Independent Test**: Set `telemetry_optout = true`, run the flow, confirm the locally stored snapshot contains a fully-formed `resources` block and nothing is transmitted.

- [ ] T012 [P] [US2] Component test in `backend/tests/component/telemetry/test_resources.py`: with `telemetry_optout = true`, run `send_telemetry_push`, assert the stored snapshot's `data.resources` is fully formed and `remote_send_status == SKIPPED` (no POST)
- [ ] T013 [US2] Verify in `backend/infrahub/telemetry/tasks.py` that the resources block is assembled during `gather()` (before the storage + opt-out branch) so it is always in the local snapshot; adjust ordering only if the test in T012 shows a gap

**Checkpoint**: Air-gapped deployments carry the metrics locally with no transmission.

---

## Phase 5: User Story 3 — Preserve the audit when a source cannot be read (Priority: P3)

**Goal**: A failing source nulls only its own field; partial worker reporting undercounts while `count` stays truthful; the snapshot is always produced.

**Independent Test**: Force a single source to raise and confirm only that field is null, the rest intact, snapshot produced; drop one worker's resource key and confirm undercount with `count` unchanged.

- [ ] T014 [P] [US3] Component test in `backend/tests/component/telemetry/test_resources.py`: (a) force the DB JMX read to raise → `resources.database` fields null, snapshot still produced; (b) one active git_agent worker with no `workers:resources` key → worker aggregate sums the reporters, `count` includes the non-reporter; (c) one worker host unbounded → aggregate `cores_assigned is None`
- [ ] T015 [US3] Harden `backend/infrahub/telemetry/tasks.py` and `resources.py` so every block/field is independently `safe_metric`-wrapped and the aggregation applies the D9 null-vs-zero/undercount rules exactly; confirm no single failure can raise out of `gather()`

**Checkpoint**: The resources block degrades gracefully and never blocks a snapshot.

---

## Phase 6: Polish & Cross-Cutting Concerns

- [ ] T016 [P] Regression test in `backend/tests/component/telemetry/test_resources.py`: adding the `workers:resources:*` heartbeat key leaves `workers.total` and `workers.active` unchanged versus a baseline without it (critique E1)
- [ ] T017 [P] Add a Towncrier changelog fragment `changelog/+resource-telemetry.added.md` describing the new per-component `resources` block (Constitution: user-facing telemetry change)
- [ ] T018 [P] Update the telemetry FAQ in `docs/docs/faq/faq.mdx` to mention the per-component cores/RAM (`resources`) block
- [ ] T019 Run the quickstart validation (`uv run invoke backend.test-unit`; component tests via testcontainers) and `uv run invoke format` + `uv run invoke lint`; fix any failures

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (T001)**: no dependencies.
- **Foundational (T002–T007)**: after Setup; **blocks all user stories**. Within it: T003→T004 (reader TDD), T005→T006 (aggregation TDD), T007 depends on T004.
- **US1 (T008–T011)**: after Foundational. T009 depends on T002; T010 depends on T006, T007, T009; T008/T011 are the story's tests.
- **US2 (T012–T013)**: after US1 (needs the block assembled).
- **US3 (T014–T015)**: after US1.
- **Polish (T016–T019)**: after all desired stories.

### Within Each User Story

- Pure-logic tests (T003, T005) are written first and must fail before their implementation.
- Models before reader/aggregation; reader/aggregation before gather wiring; gather wiring before the opt-out and degradation guarantees.

### Parallel Opportunities

- T003 and T005 (different test files) can run in parallel.
- Foundational done → the three story test skeletons (T008, T012, T014) can be drafted in parallel.
- Polish T016/T017/T018 are independent files → parallel.

## Parallel Example: Foundational tests

```bash
# The two pure-logic test files have no shared state:
Task: "Unit test the reader in backend/tests/unit/telemetry/test_resources.py"
Task: "Unit test aggregation in backend/tests/unit/telemetry/test_aggregation.py"
```

## Implementation Strategy

### MVP First (User Story 1)

1. Phase 1 (Setup) → Phase 2 (Foundational) → Phase 3 (US1).
2. **STOP and VALIDATE**: the snapshot carries a populated `resources` block; the tier audit is possible. This is the shippable MVP.

### Incremental Delivery

- MVP (US1) → add US2 (air-gapped guarantee, mostly a test) → add US3 (degradation hardening) → Polish.
- Each increment is additive and cannot regress the previous one (the whole feature is additive to the payload).

## Notes

- **No version bump in this phase**: `TELEMETRY_VERSION` is intentionally left unchanged (research D13); the bump is a gated follow-up once the receiving service confirms tolerance. Nothing in these tasks edits `constants.py`.
- **No mocking**: component tests drive the real gather against testcontainers Neo4j with synthesized cache keys (adapter/protocol rule). Unit tests use fixture cgroup files, not patches.
- **Code-doc style**: the "how it's supposed to work" comments on the `assigned` reads explain the mechanism (Neo4j setting / container CPU quota, `0`/unlimited → `None`); they must not cite Jira/spec IDs or name other functions.
- Commit after each task or logical group; each story is independently testable at its checkpoint.
