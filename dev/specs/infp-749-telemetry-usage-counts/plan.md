# Implementation Plan: Usage counts in the daily telemetry report

**Branch**: `telemetry-usage-counts-infp-749` | **Date**: 2026-11-26 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `dev/specs/infp-749-telemetry-usage-counts/spec.md`

## Summary

The daily anonymous telemetry report gains four groups of values, so that an analyst counts what a deployment does each day without contacting the customer:

- `activity_24h.workflow_runs`: one row per workflow and end state, with the number of runs and the run seconds, for 8 named workflows and the previous full UTC day
- `activity_24h.validators_started`: the number of started validators per validator kind for the same day
- `features.CoreArtifactDefinition`, `features.CoreCheckDefinition` and `features.CoreGeneratorDefinition`: the definitions that exist on the default branch
- `database.node_count.artifact_target`, `with_artifact`, `with_generated_artifact`, `generated_artifact` and `with_generator_instance`: five node totals for the default branch

Technical approach: add the values beside the existing ones, inside the three functions that already gather activity, features and database information, and run each new read through the existing degradation helper `utils.py::safe_metric`. The run rows come from the task manager's run history route, one call per workflow. The validator counts come from the event count that `activity_24h` already uses, with a filter on the kind label of the event's own resource. The definition counts reuse the existing query `queries.py::CountNodesByKindsQuery`. The node totals need one new query class, used once for artifacts and once for generator instances. The payload format version stays `20260628`, and every addition is a new key.

The change needs no graph schema change, no migration, no new index, no GraphQL or REST change, no new dependency, no new setting and no generated file.

## Technical Context

**Language/Version**: Python 3.14 (backend)

**Primary Dependencies**: Pydantic 2 (payload models and the run history response), Prefect 3.8.6 (task manager client, run history route `POST /flow_runs/history`, event count route `POST /events/count-by/event`), Neo4j driver 6 (one new read query)

**Storage**: none added. The report is stored by the existing snapshot repository, and the stored body contains the new values

**Testing**: pytest. Unit tests in `backend/tests/unit/telemetry/` for the function that turns run history states into rows. Component tests in `backend/tests/component/telemetry/` against the testcontainers Neo4j and the test task manager for the run rows, the validator counts, the node totals, the definition counts and the failure cases

**Target Platform**: Linux server (the task worker that runs the `anonymous_telemetry_send` workflow)

**Project Type**: Single backend service. The change is inside `backend/infrahub/telemetry/`

**Performance Goals**: the report runs once a day and is not on a request path. Each day it makes 8 calls to the run history route, one event count per validator kind (six today), and four reads of the graph database: one count of artifact targets, one count of the three definition kinds, and the new query twice

**Constraints**:

- A failing read never fails the report: it reports `null` for its own values only
- Additions only: no existing field is renamed, removed or changed, and `TELEMETRY_VERSION` stays `20260628`
- Every new number is a whole number or `null`, because a float with a whole-number value fails the checksum check of the receiving endpoint
- No name that a customer defined: rows are keyed by workflow name, never by run name, and the node values are totals
- The change adds about 3.6 KB at most to the request body: 7,489 bytes for the largest body measured, against 3,892 bytes before the change ([research R13](research.md))
- The report code keeps its structure: no change to `tasks.py::AnonymousTelemetryGatherer` or its constructor

**Scale/Scope**: five source files, four test modules, one internal knowledge doc, two public pages and one changelog fragment. About 350 added lines of code

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Verdict | Notes |
|-----------|---------|-------|
| I. Schema-Driven Integrity | Pass | The report is not graph data. No node, attribute or relationship is added, and no generated file changes. The relationship identifier and the validator kinds are read from the schema, not hard-coded. |
| II. Branch-Safe by Default | Pass | The three reads of the graph run on the default branch at the time of the report. The new query filters every edge with `Branch.get_query_filter_path` and resolves it with `branch_level DESC, from DESC, status ASC`. The reads write nothing. Counting only the default branch is a stated limit of the totals ([research R10](research.md)). |
| III. Type Safety & Explicit Contracts | Pass | New payload values are typed Pydantic fields. The run history response is validated with Pydantic models. The new query exposes a frozen dataclass through `get_data()`. |
| IV. Test Discipline | Pass | Unit test for the pure function, component tests against the real task manager and Neo4j for each acceptance scenario, with the failure cases. No end-to-end test: the change has no user-facing page. |
| V. Query Performance & Efficiency | Pass | The new query is parameterized, returns three numbers, and starts from the artifact or generator instance nodes by label, so its cost follows their number. The three definition counts share one query. The time on a large graph is not measured yet; the measurement is a check before the pull request is merged ([research R10](research.md)). |
| VI. Security & Input Boundaries | Pass | No user input reaches the new reads. The kind label placed in the query text is a constant of Infrahub's own code; the relationship identifier, the attribute name and the values of the branch filter are parameters. The report sends no name that a customer defined. |
| VII. Simplicity & Maintainability | Pass | Reuses `safe_metric`, the windowed event count, `CountNodesByKindsQuery` and `NodeManager.count`. One new query class with two callers. No new abstraction for the 1.13 framework. |

**Governance Ask-First gates**: database schema or migration: none. GraphQL schema: none. New dependency: none. CI/CD workflow: none. Authentication or authorization: none.

**Guideline that the design does not follow**: `dev/guidelines/backend/checklist.md`, section Telemetry, says to put new information in new blocks. The owner of the telemetry code decided to put the new values inside `activity_24h`, `features` and `database.node_count` (design doc D14). The cost is recorded in [research R9](research.md) and [research R11](research.md): `features` holds two ways of counting and can hold `null`, and `activity_24h` holds one list and one map beside its whole numbers.

Post-design re-check: no change. The design adds no entity to the graph and no interface other than the payload keys in [contracts/telemetry-payload.md](contracts/telemetry-payload.md).

## Project Structure

### Documentation (this feature)

```text
dev/specs/infp-749-telemetry-usage-counts/
├── spec.md              # the input to this plan
├── plan.md              # this file
├── research.md          # decisions and their reasons
├── data-model.md        # payload models and the rules for null, 0 and empty
├── quickstart.md        # how to validate the change
├── contracts/
│   └── telemetry-payload.md   # the new payload keys, as the data warehouse reads them
├── checklists/
│   └── requirements.md
└── tasks.md             # created by /speckit-tasks
```

### Source Code (repository root)

```text
backend/infrahub/telemetry/
├── models.py            # TelemetryWorkflowRunData; validators_started and workflow_runs on
│                        # TelemetryActivity24hData; features allows null values
├── task_manager.py      # label filter on the windowed event count; started validators per kind;
│                        # run history read and rows; both wired into gather_activity_24h
├── queries.py           # CountNodesWithOutputQuery and its result NodesWithOutputCount
├── database.py          # count_definitions, count_artifact_targets, count_nodes_with_output;
│                        # five totals in gather_database_information
└── tasks.py             # three definition keys in gather_feature_information;
                         # list_validator_kinds; DefaultActivityGatherer passes the reader of the kinds

backend/tests/unit/telemetry/
└── test_task_manager.py # build_workflow_run_rows

backend/tests/component/telemetry/
├── test_task_manager.py # run rows, validator counts, failed reads
├── test_database.py     # five node totals, failed read
└── test_tasks.py        # validator kinds, definition counts, payload fields

dev/knowledge/backend/telemetry.md                   # new values, two ways of counting, null row
docs/docs/deploy-manage/run-observe/telemetry.mdx    # size of a daily report
docs/docs/faq/faq.mdx                                # what telemetry Infrahub sends
changelog/+telemetry-usage-counts.added.md           # changelog fragment
```

**Structure Decision**: the change stays inside the existing telemetry module and its mirrored test directories. Each new value is gathered in the function that already owns its payload block: `task_manager.py::gather_activity_24h` for `activity_24h`, `tasks.py::gather_feature_information` for `features` and `database.py::gather_database_information` for `database.node_count`. No new module is added, so the 1.13 framework can move the additions into its own pattern without undoing a structure made for this patch release.

## State of the working tree when this plan was written

The change was written before this plan, in the working tree of the feature branch, and is not committed. The plan describes the design as built, with one difference:

- Not built: the rule of FR-014 that a failed read of the validator kinds makes only `validators_started` `null`. In the working tree, `tasks.py::DefaultActivityGatherer.gather` reads the kinds before it gathers the activity, so a failed read makes every value of `activity_24h` `null`. [Research R8](research.md) gives the change that closes this.

- Not built: `tasks.py::list_validator_kinds` reads the schema through `registry`. [Research R8a](research.md) moves the read to `db.schema`.
- Not yet in the working tree: the sentences that the critique of 2026-11-26 asked for in `dev/knowledge/backend/telemetry.md`, about the end state of the three workflows that run inside a proposed change and about `with_generator_instance` ([research R5](research.md), [research R10](research.md)).

Some acceptance scenarios have no test of their own yet; [research R16](research.md) lists them. `tasks.md` marks what is built and what is open.

Later on 2026-11-26 the three differences above and the missing tests were closed by tasks T010, T023 to T027, T029, T030 and T034. `tasks.md` has the current state.

## Complexity Tracking

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|--------------------------------------|
| A change with a changelog fragment of type `added` targets `stable`. `dev/constitution.md` (Git Workflow) and `dev/guidelines/git-workflow.md` say that feature branches are created from `develop`. | The owner of the telemetry code decided that the counts ship in a 1.12 patch release (design doc D8). | A pull request to `develop` ships the counts in 1.13 at the earliest. |
