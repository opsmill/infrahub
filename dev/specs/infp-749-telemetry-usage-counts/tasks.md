# Tasks: Usage counts in the daily telemetry report

**Input**: Design documents from `dev/specs/infp-749-telemetry-usage-counts/` (`specs/` is a symlink to `dev/specs/`)

**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/telemetry-payload.md, quickstart.md

**Tests**: Included. The acceptance scenarios of the specification and Constitution IV (Test Discipline) require them. Component tests run against the testcontainers Neo4j and the test task manager. No mocking library is used; a failing read is made with a failing database or a scripted HTTP transport ([research R16](research.md)).

**Organization**: Grouped by user story. User Story 4 (a failed read) and User Story 2 (existing models keep working) are checks across the values that the other stories add, so their phases come after those stories, although their priority is higher.

**State of the tasks**: the change was written in the working tree of the feature branch before this list was generated. A checked task was compared with the working tree on 2026-11-26: the code or test it names exists there, uncommitted, and the telemetry tests passed before this list was written. An unchecked task is open. The critique of 2026-11-26 added T034 and T037 to T040 and changed T023 and T027. T010, T023 to T027, T029, T030 and T034 were done later on 2026-11-26, also in the working tree and uncommitted.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies on incomplete tasks)
- **[Story]**: US1 to US6 for user-story tasks; omitted for Setup, Foundational and Polish

## Path Conventions

Single backend project. Source under `backend/infrahub/telemetry/`, tests under `backend/tests/unit/telemetry/` and `backend/tests/component/telemetry/`.

---

## Phase 1: Setup

**Purpose**: A feature branch on the current `stable` branch that can run the telemetry tests.

- [x] T001 Bring the feature branch up to date with `origin/stable`, check out the `python_sdk` submodule and install the dependencies with `uv sync --all-groups`

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: The payload models that every user story writes into.

- [x] T002 Extend the payload models in `backend/infrahub/telemetry/models.py`: add `TelemetryWorkflowRunData` (`workflow: str`, `state: WorkflowRunState | None = None`, `runs: int | None = None`, `run_seconds: int | None = None`; `state` was `str | None` until the review of 2026-11-27); add `validators_started: dict[str, int | None] | None = None` and `workflow_runs: list[TelemetryWorkflowRunData] | None = None` to `TelemetryActivity24hData`; widen `TelemetryData.features` from `dict[str, int]` to `dict[str, int | None]`. Additions only: no existing field is renamed, removed or retyped, and `constants.py::TELEMETRY_VERSION` stays `20260628`

**Checkpoint**: The models accept the new values. User stories can start.

---

## Phase 3: User Story 1 - Count the daily runs of generators, artifact generations, checks, transformations and pipelines (Priority: P1)

**Goal**: `activity_24h.workflow_runs` holds one row per workflow and end state for the 8 named workflows and the previous full UTC day.

**Independent Test**: Record runs of the named workflows in several end states on one UTC day, gather the run rows for that day, and confirm one row per workflow and end state with the expected number of runs and a whole number of run seconds.

### Tests for User Story 1

- [x] T003 [P] [US1] Unit test `test_build_workflow_run_rows` in `backend/tests/unit/telemetry/test_task_manager.py`, parametrized: no run gives no row; two entries of one state type are added up before rounding (1.4 s + 1.4 s gives 3 s, not 2 s); states that are not end states are left out; rows follow the order `COMPLETED`, `FAILED`, `CRASHED`, `CANCELLED`
- [x] T004 [P] [US1] Component test `test_gather_workflow_runs_rows_per_workflow_and_end_state` in `backend/tests/component/telemetry/test_task_manager.py`, with the helper `_seed_run` that creates a run with a chosen expected start time: two state names of one state type are one row; a run that has not ended is in no row; the window includes its first instant and excludes its last; a workflow that is not reported gets no row; `run_seconds` is an `int`. The 8 workflow names are pinned as literal strings in `_REPORTED_WORKFLOW_NAMES`

### Implementation for User Story 1

- [x] T005 [US1] In `backend/infrahub/telemetry/task_manager.py`, add `RUN_HISTORY_PATH`, `REPORTED_WORKFLOW_NAMES` (built from the 8 catalogue definitions of [research R5](research.md)), `REPORTED_RUN_STATES`, the response models `RunHistoryState` and `RunHistoryInterval`, and the pure function `build_workflow_run_rows(workflow, states)` that adds up the entries per state type and rounds the run seconds after the sum
- [x] T006 [US1] In `backend/infrahub/telemetry/task_manager.py`, add `read_workflow_run_history(client, workflow, window_start, window_end)`, which posts to the run history route with `flows.name.any_` set to the workflow and one interval for the whole window, and `gather_workflow_runs(client, window_start, window_end)`, which reads every workflow of `REPORTED_WORKFLOW_NAMES` through `safe_metric` and adds one row with `None` figures for a workflow whose read failed (depends on T005)
- [x] T007 [US1] Set `workflow_runs` in `task_manager.py::gather_activity_24h` from `gather_workflow_runs` with the window of `utils.py::get_activity_window` (depends on T006)

**Checkpoint**: The report contains the run rows. This is the smallest change that answers the questions about generator runs, artifact generations, checks, transformations and pipeline runs.

---

## Phase 4: User Story 3 - Count the nodes that have an artifact or a generator instance (Priority: P2)

**Goal**: `database.node_count` holds `artifact_target`, `with_artifact`, `with_generated_artifact`, `generated_artifact` and `with_generator_instance` for the default branch.

**Independent Test**: On a test database, create nodes with artifacts and generator instances in the states of the acceptance scenarios, gather the database information, and confirm the five totals.

### Tests for User Story 3

- [x] T008 [P] [US3] Component test `test_gather_database_information_artifact_totals` in `backend/tests/component/telemetry/test_database.py`, with the fixtures `target_group` and `artifact_definition` and the helpers `_create_artifact`, `_create_generated_artifact` and `_delete`: every total is `0` before an artifact exists; two artifacts with stored content on one node count as one node and two artifacts; an artifact with no stored content counts in `with_artifact` only; a deleted artifact, an artifact on another branch only and a deleted node are not counted; `artifact_target` is the number of nodes whose kind inherits from `CoreArtifactTarget`
- [x] T009 [P] [US3] Component test `test_gather_database_information_generator_instance_total` in `backend/tests/component/telemetry/test_database.py`, with the fixture `generator_definitions` and the helper `_create_generator_instance`: instances of two generator definitions for one node count as one node; an instance in status `Error` counts; a deleted instance and an instance on another branch only are not counted
- [x] T010 [US3] Add to `test_gather_database_information_artifact_totals` in `backend/tests/component/telemetry/test_database.py` an artifact in status `Error` whose `storage_id` is set, and assert that it is counted in `generated_artifact` and its node in `with_generated_artifact` (acceptance scenario 3 of User Story 3)

### Implementation for User Story 3

- [x] T011 [US3] In `backend/infrahub/telemetry/queries.py`, add the frozen dataclass `NodesWithOutputCount` (`nodes`, `nodes_with_content`, `outputs_with_content`) and the read query `CountNodesWithOutputQuery` (`name = "count-nodes-with-output"`), built in `__init__(output_kind, relationship_identifier, content_attribute=None)`: active output nodes of the kind on the query's branch, the active relationship to an active target node, and, with a content attribute, the latest value of that attribute, which counts as set when it is not null and not `NULL_VALUE`. Every edge is filtered with `Branch.get_query_filter_path` and resolved with `branch_level DESC, from DESC, status ASC`; the relationship identifier, the attribute name and the null value are parameters
- [x] T012 [US3] In `backend/infrahub/telemetry/database.py`, add `OUTPUT_TARGET_RELATIONSHIP = "object"`, `ARTIFACT_CONTENT_ATTRIBUTE = "storage_id"`, `count_artifact_targets(db)` (`NodeManager.count` on `CoreArtifactTarget`) and `count_nodes_with_output(db, output_kind, content_attribute=None)`, which reads the relationship identifier from the schema of the default branch and runs the query of T011 (depends on T011)
- [x] T013 [US3] In `database.py::gather_database_information`, set the five keys of `node_count`, each read through `safe_metric`: `artifact_target`; `with_artifact`, `with_generated_artifact` and `generated_artifact` from one read with the output kind `CoreArtifact`; `with_generator_instance` from one read with the output kind `CoreGeneratorInstance` (depends on T012)

**Checkpoint**: The report contains the five node totals.

---

## Phase 5: User Story 5 - Count the started validators per validator kind (Priority: P3)

**Goal**: `activity_24h.validators_started` holds the number of started validators per validator kind for the previous full UTC day.

**Independent Test**: Record validator-started events of two kinds on the previous UTC day, gather the activity, and confirm the count per kind and `0` for a kind with no event.

### Tests for User Story 5

- [x] T014 [P] [US5] Component tests in `backend/tests/component/telemetry/test_task_manager.py`, with the helper `_validator_started_event` and labelled events in the fixture `seeded_activity`: `test_gather_activity_24h_validators_started_per_kind` (the count per kind, an event before the window is left out, a kind with no event is `0`, `checks_started` is unchanged) and `test_count_started_validators_reads_the_kind_of_the_validator_only` (an event that names the kind only on a related resource is not counted under it)
- [x] T015 [P] [US5] Component test `test_list_validator_kinds` in `backend/tests/component/telemetry/test_tasks.py`: the six validator kinds, pinned as literal strings

### Implementation for User Story 5

- [x] T016 [US5] In `backend/infrahub/telemetry/task_manager.py`, add the optional `resource_labels` parameter to `_windowed_event_filter` and `count_windowed_event` (it sets `filter.resource.labels`), the constant `NODE_KIND_LABEL = "infrahub.node.kind"`, and `count_started_validators(client, kinds, window_start, window_end)`, which counts `ValidatorStartedEvent` once per kind through `safe_metric`
- [x] T017 [US5] In `backend/infrahub/telemetry/tasks.py`, add `list_validator_kinds()`, which returns the sorted `used_by` of the generic `CoreValidator` in the schema of the default branch, and pass the kinds from `DefaultActivityGatherer.gather` into `task_manager.py::gather_activity_24h`, which sets `validators_started` (depends on T016)

**Checkpoint**: The report contains the started validators per kind.

---

## Phase 6: User Story 6 - Count the artifact, check and generator definitions (Priority: P3)

**Goal**: `features` holds `CoreArtifactDefinition`, `CoreCheckDefinition` and `CoreGeneratorDefinition`, counted as the nodes that exist on the default branch.

**Independent Test**: Create one check definition on the default branch, one that is then deleted and one on another branch only, gather the feature information, and confirm that the count of check definitions is 1.

### Tests for User Story 6

- [x] T018 [P] [US6] Component test `test_gather_feature_information_counts_definitions_on_the_default_branch` in `backend/tests/component/telemetry/test_tasks.py`, with the helper `_create_check_definition`: one kept, one deleted and one branch-only check definition give 1; the two other definition kinds are `0`; an existing key keeps its count of graph vertices

### Implementation for User Story 6

- [x] T019 [US6] In `backend/infrahub/telemetry/database.py`, add `DEFINITION_KINDS` and `count_definitions(db)`, which runs `queries.py::CountNodesByKindsQuery` once for the three kinds on the default branch and fills in `0` for a kind with no node
- [x] T020 [US6] In `tasks.py::gather_feature_information`, read `count_definitions` through `safe_metric` and set the three keys, to `None` together when the read failed; change the return type to `dict[str, int | None]` (depends on T019)

**Checkpoint**: The report contains the three definition counts.

---

## Phase 7: User Story 4 - Read a report in which one source failed (Priority: P2)

**Goal**: A failed read gives `null` for its own values only, and the report is still stored and sent.

**Independent Test**: Make one new read fail, gather the part of the report it belongs to, and confirm that only the values of that read are `None`.

### Tests for User Story 4

- [x] T021 [P] [US4] Component test `test_gather_workflow_runs_reports_each_failed_read` in `backend/tests/component/telemetry/test_task_manager.py`: a window that ends before it starts makes every read fail, and the result is one row with `None` figures for each of the 8 workflows
- [x] T022 [P] [US4] Component test `test_gather_database_information_survives_output_count_failure` in `backend/tests/component/telemetry/test_database.py`: with the query `count-nodes-with-output` failing, the four totals about artifacts and generator instances are `None`, and `artifact_target`, `corenode` and `user` keep their values
- [x] T023 [P] [US4] Unit tests in `backend/tests/unit/telemetry/test_task_manager.py` with a real `PrefectClient` built with `httpx_settings={"transport": httpx.MockTransport(handler)}`. The handler answers `GET /csrf-token` with status 404, answers status 500 for one workflow name or one kind label (the client tries again after 408, 429, 502 and 503), and answers a valid body for the others. `gather_workflow_runs` returns one row with `None` figures for the failed workflow and the rows of the others (acceptance scenario 1); `count_started_validators` returns `None` for the failed kind and the counts of the others (acceptance scenario 3). The code in the working tree already behaves this way; only the tests are missing
- [x] T024 [US4] Component test in `backend/tests/component/telemetry/test_task_manager.py`: `gather_activity_24h` with a reader of the validator kinds that raises returns `validators_started is None` and the seeded counts for the other fields, for example `checks_started` (acceptance scenario 4; depends on T027)
- [x] T025 [P] [US4] Component test in `backend/tests/component/telemetry/test_database.py`: the artifact read fails alone, with a subclass of `tests/helpers/db_query_failer.py::FailingQueryInfrahubDatabase` in the test module that fails `count-nodes-with-output` only when the parameters contain `content_attribute`; `with_artifact`, `with_generated_artifact` and `generated_artifact` are `None`, and `with_generator_instance` and `artifact_target` keep their values (acceptance scenario 5)
- [x] T026 [P] [US4] Component test in `backend/tests/component/telemetry/test_tasks.py`: with the query `count-nodes-by-kinds` failing, `gather_feature_information` returns `None` for the three definition keys and a count for an existing key such as `CoreRepository` (acceptance scenario 6). `gather_feature_information` takes its database from `workers/dependencies.py::get_database`, a process singleton, so the test registers a `FailingQueryInfrahubDatabase` as that singleton and restores it on teardown

### Implementation for User Story 4

- [x] T027 [US4] Make a failed read of the validator kinds null only `validators_started` ([research R8a](research.md)). In `backend/infrahub/telemetry/task_manager.py`, `count_started_validators` takes `read_kinds: Callable[[], list[str]]` and calls it before it counts, and `gather_activity_24h` takes `read_validator_kinds: Callable[[], list[str]]` and runs `count_started_validators` through `safe_metric`. In `backend/infrahub/telemetry/tasks.py`, `list_validator_kinds` takes `db` and reads the schema with `db.schema.get_schema_branch(...)` instead of `registry.schema`, `DefaultActivityGatherer` takes `db` in its constructor and passes the reader instead of its result, and the factory `build_anonymous_telemetry_gatherer` passes the database. (T042 later moved the building of the reader into the factory.) `AnonymousTelemetryGatherer` and its constructor stay as they are. Update the calls in `backend/tests/component/telemetry/test_task_manager.py` and `backend/tests/component/telemetry/test_tasks.py` (`_build_gatherer`, `test_list_validator_kinds`)

**Checkpoint**: Every failure case of the specification has a test, and a failed read of the validator kinds no longer removes the other values of `activity_24h`.

---

## Phase 8: User Story 2 - Read the reports of an upgraded deployment with no change to existing models (Priority: P1)

**Goal**: The full report keeps every existing field and the payload format version, contains the new values, and contains no name that a customer defined.

**Independent Test**: Produce a full report on a schema with customer-defined kinds, and confirm the version, the presence of every new key and the absence of the customer's names.

### Tests for User Story 2

- [x] T028 [US2] In `backend/tests/component/telemetry/test_tasks.py`, add `validators_started` and `workflow_runs` to `_ACTIVITY_FIELDS`, so that `test_gather_full_payload_fields_present` asserts that both are set in the full report and the tests of a failed activity gather assert that both are `None`
- [x] T029 [US2] Extend `test_gather_full_payload_fields_present` in `backend/tests/component/telemetry/test_tasks.py`: the full report contains the five new `database.node_count` keys and the three new `features` keys, each set, and `workflow_runs` is a list (acceptance scenarios 1 and 3)
- [x] T030 [US2] Component test in `backend/tests/component/telemetry/test_tasks.py`: a full report gathered on a schema with customer-defined kinds (the car and person schema of the fixture `car_person_data_generic`) that have an artifact and a generator instance; the JSON of the report contains none of the names of those kinds and none of the names of their nodes (acceptance scenario 2, SC-004). The fixtures `target_group`, `artifact_definition` and `generator_definitions` and the helpers that create an artifact or a generator instance moved from `test_database.py` to `backend/tests/component/telemetry/conftest.py`, so that both test modules use them

**Checkpoint**: The contract in [contracts/telemetry-payload.md](contracts/telemetry-payload.md) is checked on the full report.

---

## Phase 9: Polish & Cross-Cutting Concerns

**Purpose**: Documentation, changelog and the checks before a pull request.

- [x] T031 [P] Update `dev/knowledge/backend/telemetry.md`: the new values in the category table and the activity field table, the two ways of counting in `features` and `database.node_count`, the day a run belongs to, the exception to the `null` rule for run rows, and the key locations
- [x] T032 [P] Update the size of a daily report in `docs/docs/deploy-manage/run-observe/telemetry.mdx` ("approximately 4-8 KB") and the daily activity line of the entry "What telemetry does Infrahub send?" in `docs/docs/faq/faq.mdx`
- [x] T033 [P] Create the changelog fragment `changelog/+telemetry-usage-counts.added.md` with `uv run towncrier create`
- [x] T034 Correct `dev/knowledge/backend/telemetry.md`: in the row `workflow_runs` of the table "Activity (24h) field semantics", say that for the three workflows that run inside a proposed change a failed generator, artifact generation or check ends the run in `COMPLETED` ([research R5](research.md)); in the section "Two ways of counting in `features` and `database.node_count`", say that `with_generator_instance` leaves out the nodes of a generator definition with `execute_after_merge: false` ([research R10](research.md)); after T027, say in the degradation section what a failed read of the validator kinds does
- [x] T035 Run `uv run invoke format`, `uv run invoke backend.lint` and the telemetry tests of [quickstart.md](quickstart.md) after the open tasks are done. Run on 2026-11-26: the formatter changed no file, `ruff`, `ty` and `mypy` reported no error, and the 140 telemetry tests passed
- [x] T036 Run `uv run invoke docs.lint` with Vale and `markdownlint-cli2` installed, and `uv run invoke docs.validate` on a tree with the docs changes committed. Run on 2026-11-26: Vale 3.12.0 on the two public pages and the changelog fragment, and `markdownlint-cli2` 0.24.1 on the two public pages, with no issue; `docs.validate` passed on the committed tree. The two linters were run directly on the changed files and not through `docs.lint`, because neither is installed on the machine
- [ ] T037 Run the workflows once for real on a local deployment, with work that succeeds and work that fails, inside and outside a proposed change, and record the rows in research R5 (step 5 of [quickstart.md](quickstart.md)); read a stored report and compare its new keys with [contracts/telemetry-payload.md](contracts/telemetry-payload.md) (step 4)
- [ ] T038 Run the two reads of `database.py::count_nodes_with_output` and the read of `database.py::count_artifact_targets` with `PROFILE` on the largest dataset available, and record the time and the database hits in research R10. The owner of the telemetry code decides whether the reads get a time limit
- [ ] T039 Before the pull request is merged, the owner of the telemetry code confirms that the telemetry endpoint accepts a report with the new values: a body with 32 run rows, a list and a map inside `activity_24h`, and `null` inside `features`
- [ ] T040 Write the design doc text of 2026-11-26, with the correction about end states, to the design doc page, then end the `Sources` line of `dev/specs/infp-749-telemetry-usage-counts/spec.md` after the link

---

## Phase 10: Fixes from the speckit review of 2026-11-27

**Purpose**: The findings of the five review aspects (code, comments, tests, errors, types) that were fixed. The findings that need a decision are in [research.md](research.md) under "Questions for the owner of the telemetry code".

- [x] T041 Type the end state of a run row as the string enum `constants.py::WorkflowRunState`, and make `models.py::TelemetryWorkflowRunData` reject a row that sets only some of `state`, `runs` and `run_seconds`, and a negative `runs` or `run_seconds`. `task_manager.py::REPORTED_RUN_STATES` maps the state type of the task manager to the enum and keeps the order of the rows. The JSON of the report does not change
- [x] T042 Name the type of the reader of the validator kinds (`task_manager.py::ValidatorKindReader`), build the reader in `tasks.py::build_anonymous_telemetry_gatherer`, and pass it to `tasks.py::DefaultActivityGatherer`, which no longer takes the database
- [x] T043 Add the type of the exception to the log line of a failed read in `utils.py::safe_metric`, so that an exception with no text, such as a read that gets no answer, still says what failed
- [x] T044 Correct the docstrings and comments that the review found wrong or stale in `models.py`, `queries.py`, `database.py`, `task_manager.py` and the telemetry tests, and remove five test comments that restate the code under them
- [x] T045 Correct `dev/knowledge/backend/telemetry.md`, [spec.md](spec.md), [research.md](research.md), [data-model.md](data-model.md) and [contracts/telemetry-payload.md](contracts/telemetry-payload.md): a trigger rule can also start a generator on the default branch; a generator instance is created before the generator's code runs and not at the start of the run; the five node totals are protected; an unanswered read of the task manager takes about 7 minutes
- [x] T046 Component test `test_gather_activity_24h_workflow_runs_cover_the_previous_utc_day` in `backend/tests/component/telemetry/test_task_manager.py`: the run rows that the activity gather returns are those of the previous full UTC day
- [x] T047 Component test `test_gather_database_information_output_totals_after_a_kind_migration` in `backend/tests/component/telemetry/test_database.py`: a node and its outputs are counted once after a kind migration of the node kind and, later, of the output kinds
- [x] T048 Component test `test_gather_database_information_failed_node_count_keeps_the_output_totals` in `backend/tests/component/telemetry/test_database.py`, and one more case in `test_gather_database_information_artifact_totals`: an artifact that is created without content and gets its content in a later update
- [x] T049 Unit tests in `backend/tests/unit/telemetry/test_models.py` (a partly filled row is rejected; the JSON of a row) and `backend/tests/unit/telemetry/test_utils.py` (the log line of a failed read). In `backend/tests/unit/telemetry/test_task_manager.py`, the failing read comes first, so a loop that stops at the first failure fails the test
- [x] T050 Run the telemetry tests and the new tests against code with the guarded behaviour removed. Run on 2026-11-27: the 149 telemetry unit and component tests pass. Each of the new or changed guards fails when its behaviour is removed: the window passed to the run rows (two mutations), the same-UUID filter and the status tie-breaker of `queries.py::CountNodesWithOutputQuery`, the protected count of artifact targets, the rule of the row model, the exception type in the log line, a run row loop that stops at the first failed read, and a content read that takes the first value with no time filter. The case with content stored in a later update still passes when only the order of the content read is reversed, because the time filter already removes the earlier value

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: no dependencies
- **Foundational (Phase 2)**: depends on Setup; blocks every user story
- **User Stories 1, 3, 5 and 6 (Phases 3 to 6)**: each depends only on Foundational and can be built in any order
- **User Story 4 (Phase 7)**: its tests fail the reads that User Stories 1, 3, 5 and 6 add, so it comes after them
- **User Story 2 (Phase 8)**: its tests read the full report, so it comes after every story that adds a value
- **Polish (Phase 9)**: after all stories

### Open tasks and their order

- T027 before T024, and before the last part of T034
- T010, T023, T025, T026, T029 and T030 depend on no open task
- T035 and T036 after every change to code, tests and docs
- T037, T038 and T039 need a local deployment, a large dataset and the receiving service; they depend on no other open task and must be done before the pull request is merged
- T040 needs the connection to the design doc page

### Parallel Opportunities

- T023 (unit test module), T025 (`test_database.py`) and T026 (`test_tasks.py`) change different files and can run in parallel
- T010 changes the same test module as T025, and T029 and T030 change the same test module as T026, so they run one after the other
- T024 changes the component test module of the task manager, after T027

---

## Parallel Example: open tasks

```bash
# Different files, no dependency between them:
Task: "T023 unit tests of a single failed read in backend/tests/unit/telemetry/test_task_manager.py"
Task: "T025 component test of a failed artifact read in backend/tests/component/telemetry/test_database.py"
Task: "T026 component test of a failed definition read in backend/tests/component/telemetry/test_tasks.py"
```

---

## Implementation Strategy

### What is built

Phases 1 to 6 are built in the working tree: the four groups of values, their tests on the main path, two failure tests, the documentation and the changelog fragment.

### What was done after this list was generated

1. T027: a failed read of the validator kinds nulls only `validators_started`, and the kinds are read through `db.schema`.
2. T010, T023 to T026, T029 and T030: tests for the acceptance scenarios that had no test of their own. Seven of the eight new or extended tests were run against code with the behaviour removed, and each failed. The case added by T010 was not run against changed code.
3. T034: three corrections to the knowledge doc.
4. T041 to T050: the fixes from the speckit review of 2026-11-27.

### What is open

1. T037 to T039: the checks before the pull request is merged.
2. T040: the design doc page.

### Suggested order

1. T037, T038 and T039 before the merge
2. T040 when the page can be written

---

## Notes

- [P] tasks change different files and depend on no open task
- A checked task records what exists in the working tree; its test was not run again for this list
- The questions for the owner of the telemetry code are in [research.md](research.md); none of them is a task
- The review of the pull request on 2026-11-26 found that the ended runs of a deleted branch are missing from the run rows. [Research R17](research.md) states the limit and the options; the specification, the contract and the knowledge doc state the limit
- Cite a place in a file by its function or symbol, never by a line number
- Commit the code of the checked tasks before the open tasks are started, so that their changes can be reviewed apart
