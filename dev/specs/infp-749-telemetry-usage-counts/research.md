# Research: Usage counts in the daily telemetry report

**Date**: 2026-11-26 | **Plan**: [plan.md](plan.md) | **Spec**: [spec.md](spec.md)

Each entry gives the decision, the reason and the alternatives that were rejected. Entries R1 to R15 come from the design doc and from checks that were run on 2026-11-26 with Prefect 3.8.6 and a test Neo4j. Each entry says whether a fact was run or only read in the code. R8 and R16 contain proposals that the design doc does not decide; they are labelled.

The Technical Context of the plan has no open clarification.

## R1. The run figures come from the task manager's run history, one call per workflow

- **Decision**: read `POST /flow_runs/history` once per named workflow, with `flows.name.any_` set to the workflow name and one interval that covers the whole day (`history_interval_seconds` equal to the length of the window).
- **Rationale**: the route returns, per state, the number of runs (`count_runs`) and the summed run time (`sum_estimated_run_time`). The route groups by state and never by flow, so one response cannot be split by workflow. A workflow with no run and a workflow name that the task manager does not know both return an empty list of states with HTTP status 200.
- **Checked**: run on Prefect 3.8.6 with SQLite and with PostgreSQL 18.6.
- **Alternatives considered**:
  - One call without a flow filter: the response has no flow name, so the rows cannot be made.
  - Reading the runs 200 at a time and counting them in Infrahub: more calls, and more data read than needed.
  - One named field per figure, the way webhook deliveries are counted: each new question needs a new field and a release.

## R2. Rows are added up by state type, and seconds are rounded after the sum

- **Decision**: add up the entries of one state type into one row, then round the summed run time to whole seconds. The pure function `task_manager.py::build_workflow_run_rows` does this and makes no call.
- **Rationale**: the task manager returns one entry per state name, so one state type can come back in several entries. Seeded runs returned `FAILED/Failed` and `FAILED/TimedOut` as two entries. `sum_estimated_run_time` is a decimal number: PostgreSQL returned `3.519877` for runs that SQLite reported as `3.0`. Rounding each entry first would lose up to half a second per entry.
- **Checked**: run on Prefect 3.8.6.
- **Alternatives considered**: one row per state name. The state names are Prefect's own detail and would change the row key that the data warehouse reads.

## R3. Only the four end states are reported

- **Decision**: report rows for `COMPLETED`, `FAILED`, `CRASHED` and `CANCELLED`, in that order, and leave out every other state type.
- **Rationale**: the response also contains states that are not end states, for example `RUNNING`. For a run that has not ended, the run time is the time up to the moment of the report, so `run_seconds` would mean a different thing per state.
- **Consequence**: a run that has not ended when the report runs is never counted, in that report or a later one.

## R4. A run belongs to the day it was expected to start

- **Decision**: pass the window of `utils.py::get_activity_window` as `history_start` and `history_end`.
- **Rationale**: the run history assigns a run to an interval by its expected start time, and the interval includes its start and excludes its end. This was read in the Prefect 3.8.6 source (`server/api/run_history.py`) and confirmed by the component test, which seeds runs at the first instant of the day, at the first instant of the next day and one minute before the day.
- **Consequence**: the existing webhook counts (`task_manager.py::count_webhook_runs`) use the start time of a run, and events use the time they occurred. A figure that combines run rows with event counts can be off by a few for one day.

## R5. The 8 workflow names come from the workflow catalogue

- **Decision**: build the list `task_manager.py::REPORTED_WORKFLOW_NAMES` from the catalogue definitions `REQUEST_GENERATOR_RUN`, `RUN_GENERATOR_AS_CHECK`, `REQUEST_ARTIFACT_GENERATE`, `GIT_REPOSITORIES_CHECK_ARTIFACT_CREATE`, `GIT_REPOSITORY_USER_CHECK_RUN`, `TRANSFORM_PYTHON_RENDER`, `TRANSFORM_JINJA2_RENDER` and `REQUEST_PROPOSED_CHANGE_PIPELINE`. The component test pins the 8 names as literal strings.
- **Rationale**: the workflow name in the catalogue equals the flow name in the task manager; an existing unit test requires it (`backend/tests/unit/workflows/test_catalogue.py`). The data warehouse reads the rows by name, so a renamed workflow must fail a test.
- **What one run means** (read in the code, not run):
  - `git-repository-run-user-check` is one check definition for one target. The workflow before it starts one `CoreUserValidator` per check definition, then runs the check once per member of the definition's target group, or once when the definition has no target group (`git/tasks.py::trigger_repository_user_checks_definitions`).
  - `generator-run` and `run-generator-as-check` are each one generator definition for one target. Neither starts the other.
  - `artifact-generate` and `git-repository-check-artifact-create` are each one artifact generation. Neither starts the other.
  - `proposed-changed-pipeline` starts the next workflows with `submit_workflow` and does not wait for them (`proposed_change/tasks.py::run_proposed_change_pipeline`).
  - Only the REST endpoints `/api/transform/python/{transform_id}` and `/api/transform/jinja2/{transform_id}` start the two transformation workflows.
- **Which state a run ends in when the work fails** (read in the code; a short script on Prefect 3.8.6 confirmed that a flow that returns a failure conclusion ends in `COMPLETED` and that a flow that raises ends in `FAILED`; no real workflow was run):
  - `generator-run` (`generators/tasks.py::run_generator`) and `artifact-generate` (`git/tasks.py::generate_artifact`) raise the exception again, so the run ends in `FAILED`. The two transformation workflows do not catch exceptions.
  - `git-repository-check-artifact-create` (`artifacts/tasks.py::create`) catches every exception of the render, saves a check with the conclusion `failure` and returns, so the run ends in `COMPLETED`.
  - `run-generator-as-check` (`proposed_change/tasks.py::run_generator_as_check`) catches the exception, sets the conclusion to `failure` and returns, so the run ends in `COMPLETED`.
  - `git-repository-run-user-check` (`git/tasks.py::run_user_check`) catches `CheckError`, saves the check with the conclusion `failure` and returns, so the run ends in `COMPLETED`.
- **Consequence**: for the three workflows that run inside a proposed change, the rows do not separate failed work from successful work. A failed artifact generation sends no created or updated event, so the number of unchanged artifact generations that the reader computes also contains the artifact generations that failed inside a proposed change. The design doc states in its behaviour rows that a failed artifact generation appears in a failed row for both workflows; this entry corrects that for `git-repository-check-artifact-create`.
- **Alternatives considered**:
  - Rows for every workflow of the catalogue: 93 workflows in Community, 93 calls a day and a largest request body of about 41 KB.
  - Four grouped rows, one per figure: the reader loses the split inside a group, and the grouping is fixed in Infrahub's code.

## R6. A failed read gives one row with null figures, and every read is always made

- **Decision**: run the read of each workflow through `utils.py::safe_metric`. When it returns `None`, add one row with the workflow name and `state`, `runs` and `run_seconds` set to `None`. Make the read for all 8 workflows whatever the number of failures.
- **Rationale**: the reader keeps the rows of the reads that worked and can tell which workflow could not be read. This is the one exception to the rule that a failed source is one `null` value.
- **Consequence**: a read that gets no answer takes about 7 minutes: 6 attempts of 60 seconds and 62 seconds of waits between them (`request_timeout` of 60 seconds, `max_retries` of 5, and waits of 2, 4, 8, 16 and 32 seconds in the Prefect 3.8.6 client). These are Prefect's defaults; Infrahub sets no shorter limit. The 8 run history reads and the 6 validator counts can delay the report by about 100 minutes. The times are computed from the settings and were not measured. When the task manager answers no call at all, the report is not stored, as before the change: `tasks.py::AnonymousTelemetryGatherer.gather` reads the work pools, the event totals and the automations with no protection.
- **For the owner to decide**: whether this delay is accepted, or whether the two new reads pass a shorter timeout to the client. A shorter timeout is not a limit on the number of failed reads.
- **Alternatives considered**:
  - `null` for the whole list when one call fails: one failed call discards the results of the others.
  - Stopping after 3 failed calls in a row: rejected by the owner of the telemetry code.
  - A first call that finds which workflows had a run, then one call for each of those only: rejected by the owner of the telemetry code, who chose to always make every call.

## R7. Started validators are counted per kind with a label filter on the event's own resource

- **Decision**: reuse `task_manager.py::count_windowed_event` and add an optional `resource_labels` filter. Count the `ValidatorStartedEvent` once per validator kind with `{"infrahub.node.kind": [kind]}`.
- **Rationale**: `POST /events/count-by/event` accepts `filter.resource.labels` beside the event name and the time window. The label is set on the event's own resource (`events/validator_action.py`). A filter on `any_resource.labels` also matches related resources, so it would count an event under the kind of a node it only relates to.
- **Checked**: run on Prefect 3.8.6. The filter returned 3 for 3 seeded events, 2 for a second kind and an empty list for a kind with no event.
- **Consequence**: one call to the task manager per validator kind each day.

## R8. The validator kinds are read from the schema of the default branch

- **Decision**: the kinds are the `used_by` list of the generic `CoreValidator` in the schema of the default branch, sorted (`tasks.py::list_validator_kinds`). No namespace filter.
- **Rationale**: a validator kind that Infrahub adds later is counted with no code change. The generic has `restricted_namespaces=["Core"]`, so the schema accepts a kind that inherits from it only in the Core namespace, and no kind with a customer-defined name can appear. A test that registered a kind outside Core failed with `Generic node 'CoreValidator' has restricted namespaces: ['Core']`.
- **Alternatives considered**: a fixed list of the six kinds. A kind added later would be counted only after the list is updated.

### R8a. A failed read of the kinds must null only `validators_started`

[CLAUDE RECOMMENDED – based on FR-014 and on how `utils.py::safe_metric` is used for every other value]

- **Problem**: in the working tree, `tasks.py::DefaultActivityGatherer.gather` calls `list_validator_kinds()` before it gathers the activity. `tasks.py::AnonymousTelemetryGatherer.gather` runs the whole activity gatherer through `safe_metric`, so a failed read of the kinds makes every value of `activity_24h` `null`, including the logins and the branch counts that existed before the change. FR-014 and SC-005 require that only `validators_started` is `null`.
- **Decision**: pass the reader of the kinds into the activity gather instead of its result. `task_manager.py::gather_activity_24h` takes `read_validator_kinds: Callable[[], list[str]]`, and `task_manager.py::count_started_validators` takes the same reader, calls it first, then counts each kind. `gather_activity_24h` runs `count_started_validators` through `safe_metric`, so a failed read of the kinds gives `None` for the map and the other values are gathered as before. A failed count of one kind still gives `None` for that kind only.
- **Where the reader reads the schema**: through the database object, which is the rule for new code on a daily task (`dev/knowledge/backend/query-pattern.md`, section "Accessing schema"). `tasks.py::DefaultActivityGatherer` takes `db` in its constructor, as `tasks.py::DefaultAccountGatherer` does, and `tasks.py::list_validator_kinds` takes `db` and calls `db.schema.get_schema_branch(...)`. The factory `tasks.py::build_anonymous_telemetry_gatherer` passes the database. `tasks.py::AnonymousTelemetryGatherer` and its constructor stay as they are.
- **Alternatives considered**:
  - A `try`/`except` around `list_validator_kinds()` with named exceptions: a second place that decides what a failure looks like, with its own list of exceptions to keep current.
  - `safe_metric(asyncio.to_thread(list_validator_kinds))`: runs an in-memory read in a thread only to make it awaitable.
  - Leaving the code as it is and removing the rule from the specification: a failure of a new read would then remove values that the report sent before the change.

## R9. The three definition counts come from one existing query on the default branch

- **Decision**: `database.py::count_definitions` runs `queries.py::CountNodesByKindsQuery` once for `CoreArtifactDefinition`, `CoreCheckDefinition` and `CoreGeneratorDefinition` on the default branch, and fills in `0` for a kind that the query returns no row for. `tasks.py::gather_feature_information` runs it through `safe_metric` and sets the three keys to `None` together when it fails.
- **Rationale**: the owner of the telemetry code chose exact numbers for the new keys. One query for three kinds of one shape follows the rule that several queries of one shape are merged into one.
- **Consequence**: `features` holds two kinds of count. The existing keys use `utils.py::count_nodes`, which counts the graph vertices with the label on every branch, deleted nodes included. The type of `features` widens from a map of whole numbers to a map of whole numbers or `null`; no existing key can be `null`, because the existing counts are not run through `safe_metric`: a failure in one of them stops the whole report, as before the change.
- **Alternatives considered**:
  - The label count that the existing keys use: not exact, and it does not go down after a deletion.
  - Changing every key in `features` to the count on the default branch: changes values that the data warehouse already stores.

## R10. The node totals use one count of artifact targets and one new query used twice

- **Decision**:
  - `artifact_target`: `NodeManager.count` on the generic `CoreArtifactTarget` (`database.py::count_artifact_targets`). It returns `0` when no kind inherits from the generic.
  - `with_artifact`, `with_generated_artifact`, `generated_artifact`: `queries.py::CountNodesWithOutputQuery` with the output kind `CoreArtifact` and the content attribute `storage_id`.
  - `with_generator_instance`: the same query with the output kind `CoreGeneratorInstance` and no content attribute.
- **How the query works**: it starts from the nodes with the label of the output kind, keeps the ones that are active on the branch, follows the relationship to the target node, keeps the active relationship and the active target, and, when a content attribute is given, reads the latest value of that attribute. It returns three numbers: the targets, the targets with at least one output that has content, and the outputs that have content. The relationship identifier is read from the schema: the `object` relationship of the output kind (`artifact__node` for artifacts, `generator__node` for generator instances). An attribute counts as set when its value is not null and not the constant `NULL_VALUE`.
- **Rationale**:
  - Infrahub creates the artifact node with status `Pending` before the first generation runs, so an artifact node can exist with no generated content. A test on `storage_id` separates the two cases.
  - A test on the status `Ready` would miss an artifact whose latest generation failed: it has status `Error` and still holds the content of an earlier run.
  - Infrahub keeps one generator instance per generator definition and target and creates it the first time the generator runs for that target (`generators/tasks.py::_define_instance`), so the instance marks the nodes a generator has run for.
- **Checked**: the query was run on a test Neo4j and returned the expected counts in 16 checks: two artifacts on one node, an artifact with no stored content, a deleted artifact, a deleted generator instance, a deleted node, a node with instances of two generator definitions, an instance in status `Pending` or `Error`, and an artifact or instance created on another branch. A first version of the query, for artifacts only, also passed checks for stored content that a later generation replaced, for content stored after the artifact was created, and for an artifact deleted on another branch only.
- **Not measured**: the time on a large graph. The read starts from the artifact nodes or the generator instance nodes by label, so its cost follows their number and not the number of all nodes.
- **Consequence**: artifacts and generator instances are branch-local (`BranchSupportType.LOCAL`), so only the ones created on the default branch are counted, and a merge does not copy them. The total of nodes with a generator instance includes a node whose only run failed or has not finished. It leaves out the nodes of a generator definition with `execute_after_merge: false`: such a generator runs only inside proposed changes (`generators/tasks.py::run_generator_definition` skips it after a merge), so its instances stay on the source branches. This was read in the code and not run.
- **Alternatives considered**:
  - One row per concrete kind with the kind name: needs names that a customer defined.
  - Fixed counts for named device kinds: customers can name these kinds differently.
  - Two query classes, one per output kind: the two reads differ only by the kind, the relationship identifier and the content attribute.

## R11. The new values go inside the existing blocks, under the same payload format version

- **Decision**: run rows and validator counts in `activity_24h`, node totals in `database.node_count`, definition counts in `features`. `constants.py::TELEMETRY_VERSION` stays `20260628`.
- **Rationale**: every addition is a new key, and no existing field is renamed, removed, or changes type or meaning. The last three additive changes to the report were sent the same way. The receiving endpoint has not been checked with a new version, and a flag in the data warehouse compares against exactly `20260628`.
- **Consequence**: `activity_24h` held only whole numbers and now also holds one list and one map. The reader finds the reports that contain the new values by `infrahub_version`.
- **Alternatives considered**: one new top-level block for all new values. It needs a block name chosen now that the 1.13 framework may rename, and it mixes values for the previous day with values for the current state.

## R12. Every new number is a whole number

- **Decision**: `runs` and `run_seconds` are integers; the report sends no average and no median.
- **Rationale**: an average is a float, and a float with a whole-number value fails the checksum check of the receiving endpoint. The task manager cannot sort or filter runs by run time, so a median would need every run of the day read 200 at a time. The reader computes the average from the two figures, and sums can be added up across days.

## R13. The change adds about 3.6 KB at most to the request body

- **Measured** with made-up values on the real report model. The existing blocks differ per deployment, for example the list of work pools and the list of database servers, so the sizes are those of one made-up report:
  - Before the change: 3,892 bytes
  - With the change and no run row: 4,342 bytes
  - With rows for 5 workflows in one end state and 2 in a second: 4,955 bytes
  - When all 8 calls fail: 5,018 bytes
  - Largest possible, 8 workflows each in 4 end states: 7,489 bytes
- **Open**: whether the telemetry endpoint accepts the report is not yet confirmed (see the checks before the pull request is merged). The same body is stored in each deployment every day.

## R14. Documentation that the change updates

- `dev/knowledge/backend/telemetry.md`: the new values, the two ways of counting in `features` and `database.node_count`, the day a run belongs to, and the exception to the `null` rule for run rows.
- `docs/docs/deploy-manage/run-observe/telemetry.mdx`: the size of a daily report, "approximately 4-8 KB" in place of "approximately 3-5 KB".
- `docs/docs/faq/faq.mdx`: the entry about what telemetry Infrahub sends lists generator runs, transformations rendered through the API and proposed change pipeline runs. It needs no line about names, because the report sends none.
- `changelog/+telemetry-usage-counts.added.md`: one fragment of type `added`.
- Not changed: the spec files of the earlier telemetry storage feature in `dev/specs/infp-471-local-telemetry-storage/` still state "3-5 KB". They are the record of that feature.

## R15. Existing behaviour that the change leaves as it is

- `tasks.py::gather_feature_information` does not run the existing counts through `safe_metric`, so a failure in one of them stops the whole report. Only the three new counts go through `safe_metric`.
- `database.py::count_user_nodes` leaves out the kinds that inherit from `CoreGroup`.
- `tasks.py::AnonymousTelemetryGatherer` and its constructor are not changed.

## R16. Acceptance scenarios that have no test of their own yet

[CLAUDE RECOMMENDED – based on the acceptance scenarios of the specification and on the tests in the working tree]

Closed on 2026-11-26, after this entry was written: tasks T010, T023 to T026, T029 and T030 added a test for each scenario below, and task T027 made the change of R8a. The entry is kept as the record of what was missing.

The tests in the working tree cover the run rows, the window, the validator counts, the five node totals, the definition counts and two failure cases (every run history read fails; the read of artifacts and generator instances fails). These scenarios are not covered:

- User Story 2, scenario 2: no test produces a report on a schema with customer-defined kinds and asserts that the serialized report contains none of their names.
- User Story 2, scenarios 1 and 3: `test_tasks.py::test_gather_full_payload_fields_present` asserts the two new `activity_24h` fields and does not assert the five new `node_count` keys or the three new `features` keys in the full report.
- User Story 3, scenario 3: no test has an artifact in status `Error` that holds stored content.
- User Story 4, scenario 1: the run history read fails for one workflow while the others succeed.
- User Story 4, scenario 3: the count fails for one validator kind while the others succeed.
- User Story 4, scenario 4: the read of the validator kinds fails. This also needs the change of R8a.
- User Story 4, scenario 5: the read behind the artifact totals fails alone. The existing test fails the artifact read and the generator instance read together, because both use the query name `count-nodes-with-output`.
- User Story 4, scenario 6: the read of the definition counts fails.

How to make one read fail without a mock:

- For the task manager: a unit test in `backend/tests/unit/telemetry/test_task_manager.py` builds a real `PrefectClient` with `httpx_settings={"transport": httpx.MockTransport(handler)}`. The handler answers `GET /csrf-token` with status 404, answers status 500 for one workflow name or one kind label, and answers a valid body for the others. The handler uses status 500 because the client tries a request again after status 408, 429, 502 or 503. A script run during the critique of 2026-11-26 built such a client and showed that the code in the working tree already returns the row with null figures for the failed workflow and `None` for the failed kind, so acceptance scenarios 1 and 3 of User Story 4 lack a test and not code.
- For the graph database: `tests/helpers/db_query_failer.py::FailingQueryInfrahubDatabase` fails a query by name. The definition counts use the query name `count-nodes-by-kinds`. To fail the artifact read alone, a subclass in the test module fails `count-nodes-with-output` only when the parameters contain `content_attribute`.

## Checks before the pull request is merged

[CLAUDE RECOMMENDED – based on the critique of 2026-11-26, `tasks.py::send_telemetry_push` and principle V of `dev/constitution.md`]

- The telemetry endpoint accepts a report with the new values: a body of the largest size (32 run rows), a list of rows and a map inside `activity_24h`, and `null` inside `features`. When the endpoint rejects a report, `tasks.py::send_telemetry_push` marks the stored report as failed, and the data warehouse receives none of its values, the existing ones included. No setting turns the new values off in a released version.
- The two reads of `database.py::count_nodes_with_output` and the read of `database.py::count_artifact_targets` are run with `PROFILE` on the largest dataset available, and the time and the database hits are recorded in R10. The reads have no time limit: `database.py::count_nodes_with_output` passes no `timeout_seconds` to the query. For the owner to decide: pass a time limit, so that a slow read is reported as `null` through `safe_metric`.
- The workflows are run once for real on a local deployment, with work that succeeds and work that fails, inside and outside a proposed change, and the rows are compared with R5 ([quickstart.md](quickstart.md)). R5 was read in the code and not run.

## Questions for the owner of the telemetry code

- Does the 1.12 change need the number of failed generators, failed artifact generations and failed checks inside a proposed change? None of the 8 run history reads returns them (R5). The existing `checks_failed` counts failed validators, and one validator covers every target of one definition. If the answer is yes, the design needs a new decision.
- The public FAQ entry about what telemetry Infrahub sends says: "This information is used as aggregated analysis to better understand what and how to improve the project." Does the sentence still describe how the new counts are used? FR-031 covers the list of values and not this sentence.
- Does Infrahub Enterprise call `task_manager.py::gather_activity_24h`, build its own activity gatherer, or run generators, artifact generations or checks through a flow with another name? `gather_activity_24h` gains a required parameter. No checkout of the Enterprise repository was available to check.
- Which of the two check figures does the analyst use: one run of `git-repository-run-user-check`, or one started `CoreUserValidator`? The report sends both.

## Open items that block nothing in this change

- Whether the 1.13 framework keeps the paths `activity_24h.workflow_runs` and `activity_24h.validators_started` and the new keys in `database.node_count`. If it moves a value, the data warehouse reads two paths for it.
- How long the task manager keeps flow runs. The knowledge doc says about 7 days; the only code found that deletes flow runs is the manual `infrahub tasks flush` command, which keeps 30 days by default. The report reads one day.
