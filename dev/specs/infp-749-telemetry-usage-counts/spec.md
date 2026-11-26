# Feature Specification: Usage counts in the daily telemetry report

**Feature Branch**: `telemetry-usage-counts-infp-749`

**Created**: 2026-11-26

**Status**: Draft

**Input**: User description: "The design doc for INFP-749 (usage counts in the telemetry report for 1.12, and a framework for adding metrics for 1.13), as updated on 2026-11-26. This specification covers the 1.12 change only: the behaviour rows 1 to 17, 22 and 23 and the decisions D1 to D10 and D14 to D18 of the design doc. The 1.13 framework (rows 18 to 21, decisions D11 to D13) gets its own specification."

**Sources**: [INFP-749](https://opsmill.atlassian.net/browse/INFP-749) and the [design doc](https://app.notion.com/p/423228b83025817eb529daa8c8912843). On 2026-11-26 the design doc page still held the text of 2026-11-25. This specification was written from the text updated on 2026-11-26.

## User Scenarios & Testing *(mandatory)*

An analyst at OpsMill reads the daily anonymous telemetry reports in the data warehouse to learn how much each deployment uses generators, artifacts, checks and transformations. Today the report counts, for the previous day, logins, started and finished validators, created and updated artifacts, branch operations and webhook deliveries, and it sends three node totals. It sends nothing about generator runs, failed artifact generations, the checks that a customer wrote, transformations rendered on demand, or the number of nodes that have an artifact.

These journeys add those counts in a 1.12 patch release. They change no field that the data warehouse already reads, and they send no name that a customer defined.

### User Story 1 - Count the daily runs of generators, artifact generations, checks, transformations and pipelines (Priority: P1)

An analyst opens the report of one deployment for one day. For each of 8 named workflows and each end state, they read how many runs ended in that state and how many seconds those runs spent running. They add up the rows of the workflows that make one figure:

- Generator runs: `generator-run` (outside a proposed change) plus `run-generator-as-check` (inside a proposed change). Neither workflow starts the other, so no run is counted twice.
- Artifact generations: `artifact-generate` (outside a proposed change) plus `git-repository-check-artifact-create` (inside a proposed change). Neither workflow starts the other.
- Checks that the customer wrote: `git-repository-run-user-check`. One run is one check definition for one target.
- Transformations rendered on demand through the REST API: `transform_render_python` plus `transform_render_jinja2_template`.
- Pipeline runs of proposed changes: `proposed-changed-pipeline`. The pipeline starts the next workflows without waiting for them, so its run seconds do not include theirs.

The end state is the state of the workflow run, and for three workflows it is not the result of the work:

- `generator-run`, `artifact-generate`, `transform_render_python` and `transform_render_jinja2_template`: when the generator, the artifact generation or the transformation fails, the run ends in `FAILED`.
- `run-generator-as-check`, `git-repository-check-artifact-create` and `git-repository-run-user-check`, the three workflows that run inside a proposed change: a failed generator, a failed artifact generation or a failed check is recorded as a check with the conclusion `failure`, and the run ends in `COMPLETED`. Their `FAILED` and `CRASHED` rows count only the runs in which the workflow itself stopped. The report does not count the failed generators, artifact generations or checks inside a proposed change.

The analyst computes two more figures in the data warehouse:

- The average run time of a workflow in an end state: run seconds divided by runs.
- The largest possible number of artifact generations that left the content unchanged: the completed runs of the two artifact generation workflows, minus `artifacts_created`, minus `artifacts_updated`. The result also contains the artifact generations that failed inside a proposed change, because those runs end in `COMPLETED` and send no event.

**Why this priority**: These run counts are the reason for the change, and no other field of the report carries them. A report with only this list already answers the questions about generator runs, artifact generations, checks, transformations and pipeline runs, and about the runs that failed outside a proposed change.

**Independent Test**: Record runs of the named workflows in several end states on the previous UTC day, produce a report, and confirm that the report contains one row per workflow and end state with the expected number of runs and run seconds.

**Acceptance Scenarios**:

1. **Given** a deployment where `generator-run` had 120 completed runs and 2 failed runs on the previous UTC day, **When** the daily report is produced, **Then** it contains one row for `generator-run` and `COMPLETED` with 120 runs and one row for `generator-run` and `FAILED` with 2 runs, and each row carries the time its runs spent running in whole seconds.
2. **Given** a run of `artifact-generate` whose artifact generation failed on the previous UTC day, **When** the report is produced, **Then** the run is counted in the `FAILED` row of `artifact-generate`.
3. **Given** a run of `git-repository-check-artifact-create` whose artifact generation failed on the previous UTC day, **When** the report is produced, **Then** the run is counted in the `COMPLETED` row of `git-repository-check-artifact-create`, and no row separates it from an artifact generation that succeeded.
4. **Given** a named workflow with no run in an end state on the previous UTC day, **When** the report is produced, **Then** the report contains no row for that workflow, and the list of rows is empty when no named workflow had such a run.
5. **Given** a run that is still running, or is scheduled and not started, when the report is produced, **When** the report is produced, **Then** no row counts that run.
6. **Given** one run that was expected to start on the previous UTC day and one run that was expected to start on the current UTC day, **When** the report is produced, **Then** only the first run is counted.
7. **Given** two runs of one workflow that the task manager records under two names of the same end state, for example a failed run and a timed-out run, **When** the report is produced, **Then** both runs are counted in one `FAILED` row, and the run seconds are added up before they are rounded.
8. **Given** a workflow that is not one of the 8 named workflows, for example `webhook-process`, **When** the report is produced, **Then** the report contains no row for it.

---

### User Story 2 - Read the reports of an upgraded deployment with no change to existing models (Priority: P1)

The analyst's existing data warehouse models keep reading the reports after a deployment upgrades. The payload format version is the same, every field that existed before has the same name, type and meaning, and the analyst finds the reports that contain the new values by the Infrahub version. An administrator of a deployment that opted out of sending telemetry exports the stored reports as before, and the exported reports contain the new values.

**Why this priority**: The reports of every deployment land in one table that existing models read. A change that broke those models, or that sent a name from a customer's schema, would cost more than the new counts are worth.

**Independent Test**: Produce a report on an upgraded deployment whose schema contains kinds that a customer defined, and confirm that the version is unchanged, that every field of the earlier report is present with the same type, and that the report contains no name from the customer's schema.

**Acceptance Scenarios**:

1. **Given** an upgraded deployment, **When** the daily report is produced, **Then** its payload format version is `20260628`, and every field of the earlier report is present with the same name, type and meaning.
2. **Given** a deployment whose schema contains kinds that a customer defined, with artifacts, generators and checks that have run for nodes of those kinds, **When** the report is produced, **Then** the report contains no kind name, run name or other name that the customer defined. The only names in the new values are workflow names and validator kind names that Infrahub defines.
3. **Given** a deployment that opted out of sending telemetry, **When** the daily report is produced, **Then** the report is stored in the deployment with the new values and is not sent, and `infrahubctl telemetry export` returns it with the new values.
4. **Given** a deployment that was upgraded today, **When** the first report after the upgrade is produced, **Then** the new values cover the previous full UTC day and the current state, and the report contains no value for an earlier day.

---

### User Story 3 - Count the nodes that have an artifact or a generator instance (Priority: P2)

An analyst reads five totals for the default branch of a deployment:

- `artifact_target`: the nodes whose kind inherits from `CoreArtifactTarget`. These are the nodes that can have an artifact.
- `with_artifact`: the nodes with at least one artifact node.
- `with_generated_artifact`: the nodes with at least one artifact that has stored content.
- `generated_artifact`: the artifacts that have stored content.
- `with_generator_instance`: the nodes with at least one generator instance. Infrahub creates the instance when a generator first runs for a node.

The analyst uses the totals to compare the number of nodes that can have an artifact with the number that have one, and to find deployments that run generators and use no artifacts.

**Why this priority**: The totals describe the size of what a deployment generates, which the run counts do not. They are independent of the run counts and need three reads of the graph database, so they come second.

**Independent Test**: On a test database, create nodes with artifacts and generator instances in the states listed in the scenarios, produce the database part of the report, and confirm the five totals.

**Acceptance Scenarios**:

1. **Given** a node with two artifacts that both have stored content, **When** the report is produced, **Then** the node is counted once in `with_artifact` and once in `with_generated_artifact`, and both artifacts are counted in `generated_artifact`.
2. **Given** a node whose only artifact has no stored content, because Infrahub created the artifact node and no generation has stored content yet, **When** the report is produced, **Then** the node is counted in `with_artifact` and not in `with_generated_artifact`.
3. **Given** an artifact whose latest generation failed and that still holds the content of an earlier generation, **When** the report is produced, **Then** the artifact is counted in `generated_artifact` and its node in `with_generated_artifact`.
4. **Given** a deleted artifact, a deleted generator instance or a deleted node, **When** the report is produced, **Then** none of them is counted in the five totals.
5. **Given** an artifact or a generator instance that exists only on a branch other than the default branch, **When** the report is produced, **Then** it is not counted.
6. **Given** a node with generator instances of two generator definitions, **When** the report is produced, **Then** the node is counted once in `with_generator_instance`.
7. **Given** a node whose only generator run failed or has not finished, **When** the report is produced, **Then** the node is counted in `with_generator_instance`, because the instance exists from the start of the first run.
8. **Given** a deployment with no artifact and no generator instance, **When** the report is produced, **Then** the four totals about artifacts and generator instances are `0` and not `null`.
9. **Given** a deployment in which no kind inherits from `CoreArtifactTarget`, **When** the report is produced, **Then** `artifact_target` is `0`.

---

### User Story 4 - Read a report in which one source failed (Priority: P2)

When one read fails, the analyst still receives every other value of the report and can tell a value that could not be read from a value of zero. A failed read is reported as `null`. A read with nothing to count is reported as `0` or as an empty list.

**Why this priority**: The new values come from the task manager and the graph database, and each read can fail on its own. A failure of one new read must not cost the analyst the rest of the report.

**Independent Test**: Make one new read fail, produce a report, and confirm that the report is still stored and sent, that only the values of the failed read are `null`, and that every other value is intact.

**Acceptance Scenarios**:

1. **Given** the read of the run history fails for one named workflow, **When** the report is produced, **Then** the report contains one row for that workflow with `state`, `runs` and `run_seconds` set to `null`, and it keeps the rows of the other workflows.
2. **Given** the read of the run history fails for every named workflow, **When** the report is produced, **Then** the report has made the read for all 8 workflows, contains 8 rows with `null` figures, and is still stored and sent.
3. **Given** the count of started validators fails for one validator kind, **When** the report is produced, **Then** that kind has the value `null` and the other kinds keep their counts.
4. **Given** the validator kinds cannot be read from the schema, **When** the report is produced, **Then** `validators_started` is `null` as a whole and the other values of `activity_24h` keep their counts.
5. **Given** the read behind the three artifact totals fails, **When** the report is produced, **Then** `with_artifact`, `with_generated_artifact` and `generated_artifact` are `null` together, and `artifact_target` and `with_generator_instance` keep their values.
6. **Given** the read behind the three definition counts fails, **When** the report is produced, **Then** the three new `features` keys are `null` together and the existing `features` keys keep their values.

---

### User Story 5 - Count the started validators per validator kind (Priority: P3)

An analyst reads, for the previous UTC day, how many validators of each validator kind started on proposed changes. Today `checks_started` gives one number for all kinds. With the count per kind, the analyst separates the validators that run the checks a customer wrote (`CoreUserValidator`) from the validators that Infrahub runs on every proposed change. One started `CoreUserValidator` is one check definition in one pipeline run.

**Why this priority**: The run rows of User Story 1 already count the checks a customer wrote, per target. This count gives a second figure for the same question, per pipeline run, and the analyst chooses which of the two to use.

**Independent Test**: Record validator-started events of two validator kinds on the previous UTC day, produce the activity part of the report, and confirm the count per kind.

**Acceptance Scenarios**:

1. **Given** 2 started validators of one kind and 1 started validator of a second kind on the previous UTC day, **When** the report is produced, **Then** `validators_started` has the value 2 for the first kind, 1 for the second kind and `0` for every other validator kind.
2. **Given** an event for a validator of one kind that names a node of another kind as a related resource, **When** the report is produced, **Then** the event is counted only under the kind of the validator itself.
3. **Given** the schema of the default branch, **When** the report is produced, **Then** the keys of `validators_started` are the kinds that inherit from `CoreValidator` in that schema. Today these are `CoreArtifactValidator`, `CoreDataValidator`, `CoreGeneratorValidator`, `CoreRepositoryValidator`, `CoreSchemaValidator` and `CoreUserValidator`.
4. **Given** the report of an upgraded deployment, **When** the analyst reads `checks_started`, **Then** it still counts every started validator of all kinds, as before.

---

### User Story 6 - Count the artifact, check and generator definitions (Priority: P3)

An analyst reads how many artifact definitions, check definitions and generator definitions exist on the default branch of a deployment. The three numbers are exact: a deleted definition is not counted, and a definition that exists only on another branch is not counted.

**Why this priority**: The definition counts tell whether a deployment has set up artifacts, checks or generators at all. They add context to the run counts and are not needed to read them.

**Independent Test**: Create one check definition on the default branch, one that is then deleted and one on another branch only, produce the feature part of the report, and confirm that the count of check definitions is 1.

**Acceptance Scenarios**:

1. **Given** one check definition on the default branch, one deleted check definition and one check definition that exists only on another branch, **When** the report is produced, **Then** `features.CoreCheckDefinition` is 1.
2. **Given** a deployment with no artifact definition, **When** the report is produced, **Then** `features.CoreArtifactDefinition` is `0` and not `null`.
3. **Given** the report of an upgraded deployment, **When** the analyst reads the `features` keys that existed before, **Then** each of them has the value it had before the upgrade, counted the same way as before.

---

### Edge Cases

- **A run that has not ended when the report is produced**: the report runs between 02:00 and 02:59 UTC for the previous day. A run that has not ended by then is never counted, in that report or a later one.
- **A run that crosses midnight UTC**: the task manager assigns a run to the day it was expected to start, and an event to the time it occurred. The number of unchanged artifact generations that the analyst computes can therefore be off by a few for one day.
- **A branch is deleted before the report runs**: when a branch is deleted, Infrahub deletes the ended workflow runs of that branch from the task manager. Seven of the 8 workflows record the branch on their run; `proposed-changed-pipeline` does not. The runs of a branch that is deleted before the report for that day runs are in no row, in that report or a later one. This affects most the three workflows that run inside a proposed change, when the branch is deleted after the merge. The counts that come from events (`validators_started`, `artifacts_created`, `artifacts_updated`) are not affected, so the number of unchanged artifact generations that the analyst computes can be below zero.
- **A day whose report does not run**: the counts of that day are lost. The next report covers only its own previous day.
- **The run history or the event count of the task manager does not answer**: with the default settings of the task manager client, one read waits up to 60 seconds and is tried 6 times, so one read takes about 7 minutes before it is reported as failed. The change adds 14 reads, so the report can be later by about 100 minutes. These times are computed from the settings and were not measured. The report is still stored and sent when the other calls to the task manager succeed. When the task manager answers no call at all, the report fails as it did before the change, because the work pools, the event totals and the automations are read with no protection.
- **A workflow name that the task manager does not know**: the read returns no run, so the workflow gets no row. This is the case on a deployment where a named workflow has never run.
- **A long run among short runs**: the report sends the sum of run seconds and no median, so a few long runs can distort the average that the analyst computes.
- **An Infrahub release adds a validator kind**: the new kind appears as a new key of `validators_started` with no change to the report.
- **No core kind inherits from `CoreArtifactTarget`**: `artifact_target` counts only nodes of kinds that a customer defined, and the report still sends only the total.
- **A generator ran only on another branch**: generator instances and artifacts are branch-local. They stay on the branch where the run created them, and a merge does not copy them to the default branch. A node is counted in `with_generator_instance` only after a generator has run for it on the default branch. A generator definition with `execute_after_merge: false` does not run after a merge, so its nodes are counted only when someone runs the generator on the default branch by hand, although the merge brings the nodes that the generator created to the default branch. For such a deployment, the analyst reads the runs of `run-generator-as-check`.
- **`features` holds two kinds of count**: the three new keys count the nodes that exist on the default branch. The existing keys count graph vertices on every branch, deleted nodes included.

## Requirements *(mandatory)*

### Functional Requirements

#### Run rows

- **FR-001**: The daily report MUST contain a list `activity_24h.workflow_runs` with one row per workflow and end state, for the previous full UTC day and for these 8 workflows: `generator-run`, `run-generator-as-check`, `artifact-generate`, `git-repository-check-artifact-create`, `git-repository-run-user-check`, `transform_render_python`, `transform_render_jinja2_template` and `proposed-changed-pipeline`.
- **FR-002**: Each row MUST carry the workflow name (`workflow`), the end state (`state`), the number of runs (`runs`) and the time those runs spent running in whole seconds (`run_seconds`).
- **FR-003**: The report MUST contain rows only for the end states `COMPLETED`, `FAILED`, `CRASHED` and `CANCELLED`. A run in any other state MUST NOT be counted.
- **FR-004**: A workflow with no run in an end state MUST get no row. The list MUST be empty when no named workflow had such a run.
- **FR-005**: Rows MUST be keyed by workflow name and never by run name, because a run name can contain a name that the customer chose.
- **FR-006**: A run MUST be counted in the UTC day in which it was expected to start. The day includes its first instant and excludes its last.
- **FR-007**: Runs that the task manager records under several names of one end state MUST be added into one row for that end state. The run seconds MUST be added up before they are rounded to whole seconds.
- **FR-008**: The report MUST NOT send an average or a median run time.
- **FR-009**: When the read of the run history fails for one workflow, the report MUST contain one row for that workflow with `state`, `runs` and `run_seconds` set to `null`, and MUST keep the rows of the other workflows.
- **FR-010**: The report MUST make the read for every named workflow, with no limit on the number of failed reads.

#### Started validators per kind

- **FR-011**: The daily report MUST contain a map `activity_24h.validators_started` from validator kind to the number of validators of that kind that started in the previous full UTC day.
- **FR-012**: The keys of the map MUST be every kind that inherits from `CoreValidator` in the schema of the default branch when the report is produced. A kind with no started validator MUST have the value `0`.
- **FR-013**: A started validator MUST be counted under its own kind only. An event that names a validator of that kind only as a related resource MUST NOT be counted under that kind.
- **FR-014**: A kind whose count fails MUST have the value `null`, and the other kinds MUST keep their counts. The map as a whole MUST be `null` when the validator kinds cannot be read from the schema, and the other values of `activity_24h` MUST keep their counts.

#### Definition counts

- **FR-015**: `features` MUST contain the keys `CoreArtifactDefinition`, `CoreCheckDefinition` and `CoreGeneratorDefinition`. Each MUST count the nodes of that kind that exist on the default branch: a deleted node and a node that exists only on another branch MUST NOT be counted.
- **FR-016**: The three keys MUST be `null` together when their read fails, and the existing `features` keys MUST keep their values.
- **FR-017**: The existing `features` keys MUST keep the way they are counted today.

#### Node totals

- **FR-018**: `database.node_count` MUST contain `artifact_target`: the number of nodes on the default branch whose kind inherits from `CoreArtifactTarget`. The value MUST be `0` when no kind inherits from it.
- **FR-019**: `database.node_count` MUST contain, for the default branch:
  - `with_artifact`: the number of nodes with at least one artifact node
  - `with_generated_artifact`: the number of nodes with at least one artifact that has stored content
  - `generated_artifact`: the number of artifacts that have stored content
- **FR-020**: An artifact MUST count as having stored content when its `storage_id` is set, whatever its status. An artifact whose latest generation failed and that holds earlier content MUST be counted.
- **FR-021**: `database.node_count` MUST contain `with_generator_instance`: the number of nodes on the default branch with at least one generator instance, whatever the status of the instance.
- **FR-022**: In the totals of FR-019 and FR-021, a node MUST be counted once whatever the number of its artifacts or generator instances. A deleted artifact, a deleted generator instance, a deleted node, and an artifact or generator instance that exists only on another branch MUST NOT be counted.
- **FR-023**: Each of the five totals MUST be `null` when its read fails. `with_artifact`, `with_generated_artifact` and `generated_artifact` come from one read and MUST be `null` together. A failed read MUST NOT change the other totals.

#### Rules for every new value

- **FR-024**: The report MUST NOT contain a name that a customer defined. The only names in the new values are workflow names and validator kind names that Infrahub defines.
- **FR-025**: The payload format version MUST stay `20260628`. No existing field may be renamed or removed, or change its type or meaning. Every addition MUST be a new key.
- **FR-026**: Every new number MUST be a whole number or `null`.
- **FR-027**: A read with nothing to count MUST report `0` or an empty list, and a read that fails MUST report `null`. A failure of one new read MUST NOT prevent the report from being stored and sent.
- **FR-028**: The report that a deployment stores MUST contain the new values, also when the deployment opted out of sending telemetry, and the export of stored reports MUST return them.
- **FR-029**: The values for the previous day MUST cover the previous full UTC day only. The report MUST NOT send an earlier day.

#### Documentation

- **FR-030**: The internal telemetry knowledge doc MUST describe the new values, the two kinds of count in `features`, and the exception to the `null` rule for run rows.
- **FR-031**: The public telemetry page MUST state the size of a daily report with the new values, and the public FAQ entry about what telemetry Infrahub sends MUST list the new run counts.
- **FR-032**: The change MUST have a changelog fragment.

### Key Entities *(include if feature involves data)*

- **Daily telemetry report**: the anonymous report that a deployment produces once a day, stores, and sends unless it opted out. It holds values for the previous full UTC day (`activity_24h`) and values for the current state (`features`, `database`).
- **Run row**: the runs of one workflow that ended in one state on the previous UTC day. It holds the workflow name, the end state, the number of runs and the run seconds. A row with only the workflow name set means that the read for that workflow failed.
- **Started validators per kind**: a map from validator kind to the number of validators of that kind that started on the previous UTC day.
- **Definition counts**: the number of artifact definitions, check definitions and generator definitions that exist on the default branch.
- **Node totals**: five whole numbers for the default branch: the nodes that can have an artifact, the nodes that have one, the nodes that have a generated one, the generated artifacts, and the nodes that have a generator instance.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: From the report of one deployment for one day, an analyst computes the number of runs of each of these five figures per end state of the workflow run, with no further data: generator runs, artifact generations, checks the customer wrote, transformations rendered through the REST API, and pipeline runs of proposed changes. The report separates failed work from successful work for generator runs and artifact generations outside a proposed change and for transformations. It does not separate them inside a proposed change.
- **SC-002**: From the same report, an analyst reads the number of nodes that can have an artifact, the number that have a generated artifact, and the number that have a generator instance.
- **SC-003**: Every field that the report contained before the change is present after it with the same name, type and meaning, and the payload format version is the same. The existing data warehouse models read the reports of an upgraded deployment with no change.
- **SC-004**: A report from a deployment with a customer-defined schema contains zero names that the customer defined.
- **SC-005**: When any single new read fails, the report is still stored and sent, and only the values of that read are `null`.
- **SC-006**: The change adds about 3.6 KB at most to the request body of a daily report. Measured with made-up values, the largest body with the new values is 7,489 bytes, against 3,892 bytes before the change. The size of the existing blocks differs per deployment.
- **SC-007**: Each day the report makes 8 new reads of the run history, one new event count per validator kind, and four new reads of the graph database.

## Assumptions

- The change ships in a 1.12 patch release and targets the `stable` branch.
- The owner of the data warehouse adds a table for the run rows and columns for the other new values. That work is outside this repository.
- The telemetry endpoint accepts a report with the new values: the larger request body, a list and a map inside `activity_24h`, and `null` inside `features`. This is not yet confirmed. A report that the endpoint rejects reaches the data warehouse with none of its values, so [research.md](research.md) lists the confirmation as a check before the pull request is merged.
- The task manager keeps the runs of the previous UTC day until the report runs, except the ended runs of a branch that was deleted (Edge Cases).
- The schema accepts a kind that inherits from `CoreValidator` only in the Core namespace, so no validator kind has a name that a customer defined.
- The report code keeps its structure: the new values are gathered beside the existing ones, with no new top-level block in the payload.
- The rules for `null` in `validators_started` and in the five node totals were proposed in the design doc and follow the rule of the existing values. The rules for the run rows and for the three definition counts were decided by the owner of the telemetry code.
- The time of the two new reads of the graph database on a large deployment is not measured. The reads start from the artifact nodes and the generator instance nodes, so their cost follows the number of those nodes and not the number of all nodes.

## Out of Scope

- One row per kind with the kind name and the number of nodes, and a count of devices. Both need the names of kinds that a customer defined. A later release can add them at `database.nodes_by_kind`.
- Fixed counts for named device kinds. A customer can name these kinds differently.
- API reads per day.
- A median or an average run time.
- The number of failed generators, failed artifact generations and failed checks inside a proposed change. The three workflows that run inside a proposed change end in `COMPLETED` when the work fails, and the report adds no other count for them.
- A backport to 1.11.
- Rows for every Infrahub workflow.
- A new payload format version.
- Runs of Python computed attributes. One run recomputes one attribute for a batch of nodes, so the number of runs is not the number of executions.
- A new event for an artifact generation that left the content unchanged.
- Past days in the report.
- The 1.13 framework for adding metrics: a daily count of every Infrahub event, a list of gatherers, and a guide and a skill for adding a metric.
- Distinct API tokens per day, proposed changes merged with and without a review, and branch lifetime.
- The changes to the data warehouse models.
- A restructuring of the existing `features` counts, and a change to the kinds that `node_count.user` leaves out.
