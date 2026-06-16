# Tasks: Local Telemetry Storage

**Input**: Design documents from `/specs/fac-001-local-telemetry-storage/`
**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/rest-api.md

**Organization**: Tasks are grouped by user story to enable independent implementation and testing of each story.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (e.g., US1, US2, US3)
- Include exact file paths in descriptions

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Add constants and configuration shared across all user stories

- [X] T001 Add telemetry snapshot constants (REMOTE_SEND_STATUS values: pending/sent/skipped/failed, default PAYLOAD_FORMAT version string) to backend/infrahub/telemetry/constants.py

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Core model and permission infrastructure that MUST be complete before ANY user story can be implemented

**CRITICAL**: No user story work can begin until this phase is complete

- [X] T002 Create TelemetrySnapshot StandardNode model with fields (kind, payload_format, deployment_id, infrahub_version, data, checksum, remote_send_status) and validation rules in backend/infrahub/telemetry/snapshot.py
- [X] T003 [P] Add READ_TELEMETRY to GlobalPermissions enum in backend/infrahub/core/constants/__init__.py
- [X] T004 [P] Add READ_TELEMETRY denial message and permission description to backend/infrahub/permissions/constants.py

**Checkpoint**: TelemetrySnapshot model and permissions exist — user story implementation can begin

---

## Phase 3: User Story 1 — Automatic Daily Telemetry Persistence (Priority: P1) MVP

**Goal**: The daily telemetry workflow always stores a snapshot locally in Neo4j, regardless of opt-out setting. Remote send is conditional. Each snapshot tracks its remote send status.

**Independent Test**: Configure telemetry opt-out, trigger the daily collection (or wait for the cron cycle), and verify a TelemetrySnapshot node exists in Neo4j with correct payload, checksum, and remote_send_status.

### Tests for User Story 1

- [X] T005 [P] [US1] Create unit tests for TelemetrySnapshot model serialization, checksum computation (SHA-256 of JSON-serialized data), and field validation in backend/tests/unit/telemetry/test_snapshot.py
- [X] T006 [P] [US1] Create component tests for TelemetrySnapshot StandardNode CRUD (create, get by UUID, get_list, update remote_send_status) using TestContainers in backend/tests/component/telemetry/test_snapshot_db.py

### Implementation for User Story 1

- [X] T007 [US1] Modify send_telemetry_push flow in backend/infrahub/telemetry/tasks.py to: (1) always gather telemetry data, (2) compute checksum and create TelemetrySnapshot with remote_send_status="pending", (3) save to DB, (4) check opt-out flag — if opted out update status to "skipped", (5) if opted in POST to remote and update status to "sent" or "failed", (6) ensure local storage failure does not block remote send and vice versa
- [X] T008 [US1] Create functional tests for modified workflow covering: opted-out stores locally with status "skipped", opted-in stores locally and sends with status "sent"/"failed", air-gapped handles network failure gracefully in backend/tests/functional/telemetry/test_workflow.py

**Checkpoint**: Daily telemetry always persists locally. US1 is fully functional and independently testable.

---

## Phase 4: User Story 2 — Manual Telemetry Export via CLI (Priority: P2)

**Goal**: Administrators and support engineers can retrieve and export stored telemetry snapshots via a REST API and CLI commands, with date-range filtering and permission enforcement.

**Independent Test**: Run `infrahubctl telemetry list` to see stored snapshots in a Rich table. Run `infrahubctl telemetry export --output file.json --start-date 2025-01-01 --end-date 2026-01-01` and verify the output JSON contains the expected snapshots.

### Tests for User Story 2

- [X] T017 [P] [US2] Create component tests for TelemetrySnapshotGetListQuery date-range filtering (no dates, start only, end only, both, empty result) in backend/tests/component/telemetry/test_snapshot_db.py (extend T006 file)
- [X] T018 [P] [US2] Create unit tests for REST API endpoint (permission enforcement, query parameter validation, response serialization) in backend/tests/unit/api/test_telemetry.py
- [X] T019 [P] [US2] Create functional tests for CLI export and list commands (output format, date filtering, no-data exit code) in backend/tests/functional/telemetry/test_cli.py

### Implementation for User Story 2

- [X] T009 [P] [US2] Add TelemetrySnapshotGetListQuery subclass with created_at date-range filtering (start_date, end_date) via raw_filter WHERE clauses and parameterized Cypher in backend/infrahub/telemetry/snapshot.py
- [X] T010 [P] [US2] Create CLI telemetry sub-app with export command (--output, --start-date, --end-date, --config-file) and list command (--start-date, --end-date, --limit, --config-file) using AsyncTyper, Rich table output, and initialize_client() for authenticated API access in python_sdk/infrahub_sdk/ctl/telemetry.py
- [X] T011 [US2] Implement GET /api/telemetry/snapshots REST endpoint with Pydantic response models (TelemetrySnapshotResponse, TelemetrySnapshotListResponse), query parameters (start_date, end_date, limit, offset), get_current_user + get_permission_manager dependency injection, and READ_TELEMETRY permission check in backend/infrahub/api/telemetry.py
- [X] T012 [US2] Register telemetry API router in backend/infrahub/api/__init__.py
- [X] T013 [US2] Register telemetry CLI sub-app via app.add_typer() in python_sdk/infrahub_sdk/ctl/cli_commands.py

**Checkpoint**: REST API and CLI export/list commands are fully functional. US2 is independently testable.

---

## Phase 5: User Story 3 — Telemetry Included in Database Backups (Priority: P3)

**Goal**: Stored telemetry snapshots are automatically included in standard database backups (neo4j-admin backup) and restored correctly, with no additional configuration.

**Independent Test**: Perform a neo4j-admin backup on an instance with stored snapshots, restore to a fresh instance, and verify all TelemetrySnapshot nodes are present.

### Implementation for User Story 3

- [X] T014 [US3] Validate that TelemetrySnapshot nodes (StandardNode with IS_PART_OF relationship to Root) are included in neo4j-admin backup and survive restore cycle — no code changes expected, document verification results as a test or in quickstart.md

**Checkpoint**: Backup/restore verified. All three user stories are independently functional.

---

## Phase 6: Polish & Cross-Cutting Concerns

**Purpose**: End-to-end validation and code quality checks

- [X] T015 [P] Run quickstart.md end-to-end validation scenarios (verify storage, export, list, permission enforcement, backup inclusion)
- [X] T016 Run formatting (uv run invoke format) and linting (uv run invoke lint) checks across all modified and new files
- [X] T020 [P] Create Towncrier changelog fragment in changelog/ describing the new local telemetry storage feature (changed behavior: telemetry now always stored locally regardless of opt-out setting, new CLI commands: infrahubctl telemetry export/list)
- [X] T021 Create user-facing documentation in docs/ covering: feature overview, CLI command usage (infrahubctl telemetry export, infrahubctl telemetry list), REST API endpoint, permission setup (telemetry:read), and backup inclusion behavior

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies — can start immediately
- **Foundational (Phase 2)**: Depends on Phase 1 — BLOCKS all user stories
- **US1 (Phase 3)**: Depends on Phase 2 (TelemetrySnapshot model + constants)
- **US2 (Phase 4)**: Depends on Phase 2 (model + permissions). Does NOT depend on US1 workflow changes — can proceed in parallel with US1
- **US3 (Phase 5)**: Depends on Phase 2 (model must exist to create test data). Can proceed in parallel with US1 and US2
- **Polish (Phase 6)**: Depends on all desired user stories being complete

### User Story Dependencies

- **US1 (P1)**: Requires Phase 2 only — no cross-story dependencies
- **US2 (P2)**: Requires Phase 2 only — independent of US1 (API reads existing snapshots, doesn't depend on how they're created)
- **US3 (P3)**: Requires Phase 2 only — independent of US1 and US2 (backup includes any StandardNode data)

### Within Each User Story

- Tests should be written before implementation where possible (TDD)
- Models/queries before services/endpoints
- Core implementation before integration points
- Story complete before moving to next priority (sequential) or stories in parallel (team)

### Parallel Opportunities

- **Phase 2**: T003 and T004 (permissions) can run in parallel with each other and after T002
- **Phase 3 (US1)**: T005 and T006 (tests) can run in parallel
- **Phase 4 (US2)**: T017, T018, T019 (tests) can run in parallel; T009 (query) and T010 (CLI) can run in parallel (different repos, CLI uses REST contract)
- **Phase 6**: T015, T016, T020 can run in parallel
- **Cross-story**: US1, US2, and US3 can all proceed in parallel after Phase 2 completes

---

## Parallel Example: User Story 1

```bash
# Launch tests in parallel (different files, no dependencies):
Task T005: "Unit tests for TelemetrySnapshot model in backend/tests/unit/telemetry/test_snapshot.py"
Task T006: "Component tests for TelemetrySnapshot CRUD in backend/tests/component/telemetry/test_snapshot_db.py"

# Then implement workflow (depends on model from Phase 2):
Task T007: "Modify send_telemetry_push in backend/infrahub/telemetry/tasks.py"

# Then functional tests (depends on T007):
Task T008: "Functional tests for workflow in backend/tests/functional/telemetry/test_workflow.py"
```

## Parallel Example: User Story 2

```bash
# Launch in parallel (different repos, CLI uses REST contract not implementation):
Task T009: "Query subclass in backend/infrahub/telemetry/snapshot.py"
Task T010: "CLI commands in python_sdk/infrahub_sdk/ctl/telemetry.py"

# Then REST endpoint (depends on T009 query):
Task T011: "REST endpoint in backend/infrahub/api/telemetry.py"

# Then register router and CLI (depends on T011, T010 respectively):
Task T012: "Register router in backend/infrahub/api/__init__.py"
Task T013: "Register CLI sub-app in python_sdk/infrahub_sdk/ctl/cli_commands.py"
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1: Setup (T001)
2. Complete Phase 2: Foundational (T002, T003, T004) — CRITICAL, blocks all stories
3. Complete Phase 3: User Story 1 (T005-T008)
4. **STOP and VALIDATE**: Trigger daily telemetry, verify snapshot stored in DB
5. Deploy/demo if ready — core data retention is operational

### Incremental Delivery

1. Setup + Foundational -> Foundation ready
2. Add US1 -> Test independently -> Deploy (MVP — daily snapshots always stored)
3. Add US2 -> Test independently -> Deploy (CLI export + REST API available)
4. Add US3 -> Validate independently -> Deploy (backup inclusion confirmed)
5. Each story adds value without breaking previous stories

### Parallel Team Strategy

With multiple developers after Phase 2 completes:

- **Developer A**: US1 (workflow modification + tests)
- **Developer B**: US2 (REST API + CLI)
- **Developer C**: US3 (backup validation)

Stories complete and integrate independently.

---

## Notes

- [P] tasks = different files, no dependencies on incomplete tasks
- [Story] label maps task to specific user story for traceability
- Query names must use lowercase-with-dashes per dev/knowledge/backend/query-pattern.md
- Query result types must use @dataclass(frozen=True), NOT Pydantic per dev/knowledge/backend/query-pattern.md
- Workflow/task names must use lowercase-with-dashes with explicit name parameter per dev/knowledge/backend/async-tasks.md
- Return only needed properties in Cypher queries, never entire nodes per dev/knowledge/backend/query-pattern.md
- Use .fn for calling Prefect flows in unit tests per dev/knowledge/backend/testing.md
- Use caplog pattern for testing Prefect logging per dev/knowledge/backend/testing.md
- python_sdk is a Git submodule — CLI changes (T010, T013) require commits in that submodule
