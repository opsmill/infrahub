# Feature Specification: Task History and Activity Log Retention

**Feature Branch**: `task-history-retention-infp-507`

**Created**: 2026-10-04

**Status**: Draft

**Input**: User description: "INFP-507 Task history and Activity log retention. Source of truth: the Notion design doc *Task history and Activity log retention* (sections 1 Context, 2 Behaviour, 3 Technical Decisions D1-D10, 4 Boundaries and follow-ups), hardened in a grilling session on 2026-10-04. Target release 1.13."

**Source of truth**: [Notion design doc](https://app.notion.com/p/opsmill/Task-history-and-Activity-log-retention-3dc228b830258012ba28dc3a23eece65). Where this spec and the design doc disagree, the design doc wins.

## Context

Each Infrahub instance keeps two kinds of records in its task manager:

- **Task history**: finished runs of background tasks, with their logs and artifacts. Today it is never deleted and grows until the task manager's database fills its disk, which stopped three customer instances.
- **Activity log**: the Infrahub events shown on the Activities page. Today every event disappears after 7 days, because the task manager's default event retention applies to all events, and the task manager's own internal events (run state changes, heartbeats), about 70 % of stored events, share that retention.

Product decided that each instance keeps both kinds of records for a configured period, deletes older records automatically without affecting the instance, keeps the activity log for its own retention whatever the task manager keeps of its own records, and gets the disk space back. Retention is configurable up to 365 days, with the same settings and range in Community and Enterprise. The activity log is kept for 7 days by default on Community and for 30 days on Enterprise, where OpsMill's Enterprise Docker Compose file and Helm chart set it.

The Activities page gets slower as the activity log grows: with a year of activity log, one page takes minutes today. The Activities page work therefore ships with this feature, ahead of the activity log retention.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Task history stops filling the disk (Priority: P1)

An operator upgrades an instance whose task history has grown for months. From then on the instance deletes finished runs older than the task history retention (30 days by default) on its own, so the task manager's storage levels off instead of growing without limit. On an instance that already holds a lot of task history, the upgrade deletes the old runs quickly and gives their disk space back as its last step. When the upgrade skips that step, for example through the Helm chart's upgrade hook, the operator runs the same cleanup once after the upgrade, with the instance running.

**Why this priority**: Unbounded task history is the incident: it stopped three customer instances. It is independent of the other stories and delivers value alone.

**Independent Test**: Seed an instance with finished, stuck and recent runs spanning more than the retention, at least 100,000 of them old, and run the upgrade; on a second instance with fewer old runs, run the upgrade, then the command for old runs with the rewrite option. Verify that each upgrade printed the task history size and the old runs, that the first one cleaned up and the second one printed why it skipped and the command, that only finished runs older than the retention are gone after each cleanup, that the task history storage shrank, and that the hourly cleanup keeps deleting runs as they age past the retention.

**Acceptance Scenarios**:

1. **Given** a Compose or Helm instance with at least 100,000 finished runs older than the task history retention, **When** the operator runs the upgrade, **Then** the upgrade prints, in its task manager step, how much disk space the task history takes and how many runs are older than the retention; and in its last step, after the branch rebase, it deletes those runs with their logs and artifacts, rewrites each task history and activity log table whose live rows hold less than half of its disk space, and prints its progress and the same summary as the command for old runs with the rewrite option.
2. **Given** an instance with fewer than 100,000 runs older than the retention, an upgrade run with `--no-task-history-cleanup`, or a task manager that does not report its task history (an older task manager, or one that cannot be reached), **When** the operator runs the upgrade, **Then** its last step deletes nothing and prints why it skipped and the command for old runs with the rewrite option.
3. **Given** an upgrade whose cleanup fails or cannot start, **When** its last step runs, **Then** it prints the error and what was deleted, then that the upgrade goes on without the cleanup with the command that finishes it, and the upgrade completes.
4. **Given** an instance whose upgrade skipped the cleanup, still running, **When** the operator runs the command for old runs with the rewrite option, **Then** the runs older than the retention, their logs and artifacts are deleted; each task history and activity log table whose live rows hold less than half of its disk space is rewritten; the command names the tables it rewrote, the tables it left as they are, the tables it could not lock, the tables whose rewrite it stopped at its time limit and the tables whose rewrite failed with a database error; and runs within the retention, unfinished runs and their logs are kept. The command is the same on Compose and Helm.
5. **Given** an upgraded instance, **When** a finished run becomes older than the task history retention, **Then** the automatic cleanup deletes it, with its logs and artifacts, within about an hour.
6. **Given** an operator who needs older runs, **When** they set a longer task history retention before upgrading, **Then** neither the automatic cleanup, the upgrade's cleanup nor the command for old runs deletes runs within that value. `--no-task-history-cleanup` keeps the upgrade from deleting, but the automatic cleanup still deletes the runs older than the retention.
7. **Given** a run that stays RUNNING or PENDING after a worker crashed, **When** an admin runs the documented command for stuck runs, **Then** the run is marked CRASHED and is deleted once it is older than the task history retention.
8. **Given** an operator who lowered the task history or the activity log retention, **When** the next automatic cleanup runs, **Then** the records older than the new value are deleted and the database grows much more slowly without shrinking, by an amount that was not measured, and the disk space comes back when the operator runs the command for old runs with the rewrite option, the same cleanup the upgrade runs, which rewrites each table that is mostly free space whoever deleted its rows.

---

### User Story 2 - The Activities page stays fast with a year of activity log (Priority: P2)

A user opens the Activities page on an instance that keeps a year of activity log and filters by account, branch, node or several filters at once, opens an activity's sub-activities, and scrolls back through older events. Pages load in about a second for single filters and within a few seconds for combined filters, the same events appear as today, and scrolling never repeats or skips events.

**Why this priority**: A longer activity log with today's queries makes the Activities page unusable (minutes per page), so this must land before User Story 3 raises what an instance can keep.

**Independent Test**: On a dataset with a year of activity log, compare every Activities filter against today's filters for identical results, and time the default view, single filters, combined filters, sub-activities and branch-name filters.

**Acceptance Scenarios**:

1. **Given** a year of activity log, **When** a user opens the default view or filters by account, branch or node, **Then** the page loads in about 1 s on a repeat load and up to about 3 s on the first load.
2. **Given** a year of activity log, **When** a user combines level, account, branch and event-type filters, **Then** the page loads in 3 to 6 s, and never more than 10 s.
3. **Given** any Activities filter, **When** its results are compared with today's filters over the same data, **Then** both return the same events.
4. **Given** a branch that was deleted, **When** a user filters by its name through an old link or the API, **Then** the page shows that branch's events, and a name that was deleted and created again shows only the current branch's events.
5. **Given** an activity a year old, **When** a user opens its details page, **Then** its sub-activities load in under a second.
6. **Given** a user scrolling the Activities page while new events arrive, **When** they load more events, **Then** the next page continues from the oldest event shown, with no event repeated or skipped.
7. **Given** an activity log retention longer than 180 days, **When** a user scrolls past 180 days, **Then** events up to the retention are returned.

---

### User Story 3 - Operators keep the activity log for a configured period (Priority: P3)

An operator who needs more activity log than the default (7 days on Community, 30 days on Enterprise) raises the activity log retention, for example to a year. Infrahub events stay on the Activities page for that period, while the task manager's own internal events are still deleted after their own, shorter retention, so the extra storage goes only to the events users read.

**Why this priority**: It closes the 7-day loss of history. On Community the default stays at 7 days, so there it only takes effect once an operator raises the setting; on Enterprise, OpsMill's Docker Compose file and Helm chart set 30 days. It depends on User Story 2 shipping first.

**Independent Test**: Raise the activity log retention, generate Infrahub and task-manager events over a period longer than the task manager's own-event retention, and verify that no Infrahub event is deleted before the activity log retention, every task-manager event type is deleted after its own retention, and no related item is left behind.

**Acceptance Scenarios**:

1. **Given** an activity log retention of a year, **When** Infrahub events are older than 7 days, **Then** they are kept and shown on the Activities page until they are older than a year.
2. **Given** the default retentions of the Infrahub configuration, **When** the instance is upgraded, **Then** Infrahub activity remains available for 7 days and listed Prefect internal events become eligible for deletion after 2 days, including the existing backlog. PostgreSQL can reuse the deleted rows' space; deletion alone does not shrink its files.
3. **Given** the task manager's own events, **When** they are older than the own-event retention (2 days by default), **Then** they are deleted, whatever the activity log retention.
4. **Given** a task-manager event type missing from Infrahub's list, **When** it is older than the own-event retention, **Then** it is kept for the activity log retention instead, and no Infrahub event is ever deleted because of the list.
5. **Given** a retention above 365 days, **When** an operator configures the instance, **Then** startup fails with an error naming the setting, in both editions.
6. **Given** an Enterprise instance deployed with OpsMill's Enterprise Docker Compose file or Helm chart that sets no activity log retention of its own, **When** it is upgraded, **Then** Infrahub activity remains available for 30 days. An Enterprise instance deployed without them keeps 7 days unless it sets `INFRAHUB_TASK_MANAGER_RETENTION_ACTIVITY_LOG`.

---

### User Story 4 - One place to configure retention (Priority: P4)

An operator sets how long task history, the activity log and the task manager's own events are kept, once, in the Infrahub configuration, Helm values or compose environment, using the configuration reference, and the values apply wherever the task manager's background services run.

**Why this priority**: Today retention means finding undocumented task-manager environment variables. The settings are delivered with User Stories 1 and 3; this story covers their single entry point, validation and documentation.

**Independent Test**: Set each value through the configuration and through environment variables, in the default deployment and with the background services in their own deployment, and verify that the cleanups use those values and that an invalid combination is rejected at start.

**Acceptance Scenarios**:

1. **Given** the three retention settings, **When** the task manager starts, **Then** its cleanups use them, without the operator setting any task-manager-specific variable.
2. **Given** the task manager's background services in their own deployment (a Helm option), **When** they start, **Then** they use the same retention values, because Infrahub's command starts them.
3. **Given** a retention shorter than 1 day, **When** the task manager starts, **Then** it refuses to start and names the setting.
4. **Given** an own-event retention longer than the activity log retention, **When** the task manager starts, **Then** it refuses to start and names both settings, because when the task manager sets the event retention, every event older than the activity log retention is deleted, so a longer own-event retention would have no effect.

---

### Edge Cases

- **Cleanup step interrupted** (stopped session, timeout, crash): the cleanup keeps running in the task manager or can be re-run, and a re-run continues where the first one stopped, because it commits at most 1,000 runs at a time, oldest first, and logs its progress.
- **Upgrade run against a task manager that does not answer the task history size**, for example one that is still the previous version during the Helm upgrade hook: the upgrade waits at most 10 s for the size, prints that it could not read it with the error type, and continues; its last step skips the cleanup, because the task manager did not report its task history, and prints the command for old runs. The command for old runs against such a task manager reports that the cleanup is not available and exits successfully.
- **Upgrade through the Helm chart's pre-upgrade hook** (the chart's optional upgrade Job): the hook runs before Helm replaces the task manager, so on the first upgrade to this release it reaches the previous task manager and the cleanup is skipped, as in the case above. The chart passes `--no-task-history-cleanup` to the hook (prepared in [opsmill/infrahub-helm#100](https://github.com/opsmill/infrahub-helm/pull/100)), because Helm waits at most 5 minutes for a hook by default, so operators who use the hook run the command for old runs after the upgrade.
- **Upgrade with `kubectl exec` after `helm upgrade`**, the documented Helm path: the upgrade reaches the new task manager only after the task manager's rollout has finished, so the operator waits for it (`kubectl rollout status` on the task manager deployment) before running the upgrade.
- **Upgrade on Docker Compose**: the upgrade runs with the instance stopped (`docker compose run`), so its cleanup adds to the time the instance is down. On a restored backup with 7.3 GB of task history (private-tests run 41706228147, 3 Nov), the cleanup deleted 422,735 runs and returned 6 GB in about 5 min 40 s, about 1,250 runs a second; deletes slow down on a larger task history: on 25.8 GB, the upgrade's cleanup step took about 14 to 16 minutes and the command 17 to 20 minutes, with the instance running, so the downtime it adds on Docker Compose is an estimate. An operator can instead pass `--no-task-history-cleanup` and run the command for old runs later, with the instance up.
- **Cleanup already running when the upgrade starts its own**: a cleanup on the task manager replica that the upgrade reaches is followed to its end. When the task manager answers that a cleanup runs on another replica, no longer knows the job or cannot be reached, the upgrade waits at most 2 minutes for a cleanup to follow, then prints the error and the command that finishes the cleanup, and completes.
- **Little to delete** (a new or small instance, or the step run again): the command deletes what is older than the retention and rewrites only the tables whose live rows hold less than half of their disk space. A small table can count as mostly free, because disk space is counted in whole pages and the upgrade replaces Prefect's scheduled runs; its rewrite takes milliseconds.
- **Lowering a retention**: the automatic cleanup deletes the old records before the operator runs the step, so the command for old runs deletes little or nothing; with the rewrite option it still rewrites each table that is mostly free space, because it measures the free space whoever freed it.
- **The task manager's own cleanup of old runs runs at the same time** (it is on, and runs during the cleanup step): both finish and leave the same runs; neither fails.
- **Several task-manager replicas**: only one cleanup runs at a time; the command waits and continues when another replica runs one.
- **A table is locked by something else during the rewrite**: the rewrite waits up to 3 s for its lock, retries up to 4 times, then skips that table and reports it, and the command completes. While the rewrite waits for its lock, other queries on that table wait behind it, for at most those 3 s.
- **A run to delete, or a record of it, is locked by another session**: a locked run is skipped and stays for a later cleanup. On Postgres, a locked task run, state, log or artifact of a run makes the delete wait at most a minute; then the command stops with an error that names the day those runs ended. The runs deleted before stay deleted, and a re-run continues from that day.
- **A table takes too long to rewrite**, for example on a slow disk: the rewrite is stopped at a time limit, which leaves the table as it was, and the command reports it and goes on with the next table.
- **A table mostly holds live rows** (for example the activity log tables with a long activity log retention): the command leaves it as it is and says so.
- **Existing scripts call the command for old runs with `--days-to-keep` or `--batch-size`**: those options are removed (the command reads the retention setting); the changelog flags it as a breaking change.
- **Rewrite during operation**: the command for old runs, and the upgrade run inside a running instance as on Helm, run with the instance up, and tasks that read or write a table wait while it is rewritten: up to 21 s measured behind a table rewrite with the instance running on 25.8 GB of task history, and about 20 s for the slowest table on 100 GB in a local benchmark of an earlier version. How long a rewrite of the activity log tables takes after a long retention was lowered was not measured.
- **Prefect's vacuum switch keeps old task runs** (`PREFECT_SERVER_SERVICES_DB_VACUUM_ENABLED` set to a value without `flow_runs`): the command for old runs deletes and rewrites nothing and fails with the reason; the upgrade's task manager step says that old task runs are not deleted, and why, and its last step skips the cleanup with that reason, without the command.
- **Prefect's vacuum switch keeps old events** (`PREFECT_SERVER_SERVICES_DB_VACUUM_ENABLED` set to a value without `events`): a query without a start reads back the activity log retention or 180 days, whichever is longer, so it never returns fewer events than Prefect's 180-day default.
- **Not enough free disk for the rewrite**: the rewrite needs free space for a new copy of the table and its indexes, and the command does not check the free disk space before it rewrites a table. In two CI runs on 25.8 GB of task history, the files of the task-manager database took up to 0.7 GB and 1.1 GB more than at the start of the upgrade, write-ahead log included; an earlier local benchmark gave 2.2 GB for 100 GB. The upgrade guide states this. The rewrite of a table whose copy does not fit fails and leaves that table as it was, and the command names it and goes on with the next table. When the write-ahead log is on the same disk, which is the Postgres default, and it has no room either, Postgres ends every session and restarts instead: the command fails, the tables after that one are not tried, and the unfinished copy can stay on disk.
- **PENDING runs that never started**: they have no start time, so the command for stuck runs selects them by their expected start time and marks them CRASHED once that time is more than 2 days old.
- **Runs stuck in SCHEDULED, LATE, PAUSED or CANCELLING**: not covered; whether they accumulate is an open question.
- **Branch deleted**: finished runs tagged with the branch are deleted as today, unchanged.
- **Branch name that matches no existing branch and has no "branch deleted" event inside the activity log retention** (at least 180 days when the task manager does not delete old events): the activity log filter returns no events straight away.
- **Two events with exactly the same time at a page boundary**: kept once, by identifier.
- **The newest Infrahub events are older than the widest time window** (a restored backup, or an instance with no activity for more than 30 days): the first page is read in the window that ends at the newest of them, as a later page is, instead of in the whole range.
- **New task-manager event type after a task-manager upgrade**: an automated check fails in CI; until it is listed, the type is kept for the activity log retention (disk cost only).
- **Lowering the activity log retention**: events older than the new value are deleted by the next cleanup; the event storage does not shrink, which is accepted because lowering is rare.
- **API clients paging the activity log by position**: deep pages of combined filters stay slow (about 70 s at offset 2,000); the Activities page pages by time instead.
- **Activity already lost to the 7-day limit before the upgrade**: not recovered.

## Requirements *(mandatory)*

### Functional Requirements

**Settings**

- **FR-001**: System MUST provide three retention settings: task history (default 30 days), activity log (default 7 days, 30 days on Enterprise as FR-005 describes) and the task manager's own events (default 2 days), settable in the Infrahub configuration, Helm values and compose environment.
- **FR-002**: System MUST apply the three settings to the task manager's cleanups at start, without the operator setting task-manager-specific variables.
- **FR-003**: System MUST apply the same settings when the task manager's background services run in their own deployment, by starting that deployment through an Infrahub command.
- **FR-004**: System MUST refuse to start the task manager, naming the setting, when a retention is shorter than 1 day or longer than 365 days; it MUST also refuse to start, naming both settings, when the own-event retention is longer than the activity log retention.
- **FR-005**: Community and Enterprise MUST have the same retention settings with the same range, 1 to 365 days, and no edition gate. The activity log default MUST stay 7 days in the Infrahub configuration, which Community uses; OpsMill's Enterprise Docker Compose file and Enterprise Helm chart MUST set it to 30 days. An Enterprise setup that does not use them keeps 7 days unless it sets `INFRAHUB_TASK_MANAGER_RETENTION_ACTIVITY_LOG`.

**Task history**

- **FR-006**: System MUST automatically delete, about every hour, finished runs (completed, failed, cancelled, crashed) whose end time is older than the task history retention, together with their logs and artifacts.
- **FR-007**: System MUST NOT delete runs that are not finished through the automatic cleanup or the command for old runs.
- **FR-008**: The existing operator command for old runs MUST delete the same runs, logs and artifacts as the automatic cleanup, using the task history retention setting.
- **FR-009**: The command for old runs MUST offer a rewrite option, off by default, that returns disk space; with the option it MUST rewrite each task history and activity log table whose live rows hold less than half of its disk space, whoever deleted its rows, because the automatic cleanup may already have deleted them, and MUST name the tables it rewrote, the tables it left because their live rows hold at least half of their disk space, the tables it could not lock, the tables whose rewrite it stopped at its time limit, and the tables whose rewrite failed with a database error. The command MUST read the task history retention setting and no longer take a number of days or a batch size.
- **FR-010**: The command for old runs MUST commit its work in steps, log its progress, keep running if the caller disconnects, and be safe to re-run after an interruption.
- **FR-011**: In its task manager step the upgrade MUST print how much disk space the task history takes and how many runs are older than the retention (counted up to 100,000), and, when Prefect's vacuum switch keeps old task runs, that they are not deleted and why; reading them MUST NOT fail the upgrade or hold it up for more than 10 s, also against a task manager that does not answer, for which it names the error. In its last step, after the branch rebase, the upgrade MUST run the same cleanup as the command for old runs with the rewrite option, and print its progress and summary, only when the task manager reported at least 100,000 finished top-level runs older than the task history retention. Otherwise it MUST print why it skipped and, except when the vacuum switch keeps old task runs, the command for old runs with the rewrite option. It skips when:
  - `--no-task-history-cleanup` is given;
  - the task manager did not report its task history, for example an older task manager without the cleanup, or one that cannot be reached;
  - Prefect's vacuum switch keeps old task runs;
  - fewer than 100,000 runs are older than the retention, which Prefect's hourly cleanup deletes.

  A cleanup that fails or cannot start MUST NOT fail the upgrade: the upgrade prints the error, what was deleted and the command that finishes the cleanup, and completes. It waits at most 2 minutes without a cleanup to follow, for example while another replica runs one.
- **FR-012**: The command for old runs MUST NOT fail when the task manager it reaches does not yet provide the cleanup; it MUST report that the cleanup was not run.
- **FR-013**: The command for old runs MUST be the same on Compose and Helm and MUST NOT need the instance stopped. The upgrade MUST offer `--no-task-history-cleanup`, which skips its cleanup; the Helm chart's optional pre-upgrade hook passes it ([opsmill/infrahub-helm#100](https://github.com/opsmill/infrahub-helm/pull/100)), because Helm waits at most 5 minutes for a hook by default.
- **FR-014**: The command for stuck runs MUST be documented, including that it marks runs RUNNING or PENDING for more than 2 days as CRASHED, measured from the start time, or from the expected start time for a PENDING run that never started.
- **FR-015**: Branch deletion MUST keep deleting the finished runs tagged with the branch, as today.

**Activity log**

- **FR-016**: System MUST keep Infrahub events for the activity log retention and MUST NOT delete an Infrahub event earlier.
- **FR-017**: System MUST delete the task manager's own events once they are older than the own-event retention, through a list of the task manager's event types that Infrahub maintains for the task-manager version it ships with.
- **FR-018**: System MUST delete an event's related items together with the event, leaving none behind.
- **FR-019**: The Activities page and the activity log API MUST return events up to the activity log retention, including events older than 180 days.

**Activities page**

- **FR-020**: The account, branch, node and parent-event filters, and the branch-name filter for merges, rebases and migrations, MUST return the same events as today's filters.
- **FR-021**: A branch-name filter MUST resolve to the current branch of that name; when no branch has that name, it MUST resolve to the branch named in the most recent "branch deleted" event with that name, and MUST return no events when there is none inside the activity log retention (at least 180 days when the task manager does not delete old events).
- **FR-022**: The Activities page MUST load events newest first, reading the most recent time window first and widening it only while a page is not full, with the windows counted back from the newest stored event of the requested event types at or before the oldest event shown (or now, on the first page), so that the first window holds events however old the newest one is.
- **FR-023**: The Activities page MUST load more events by continuing from the time of the oldest event shown, so that no event is repeated or skipped when new events arrive, keeping events with the same time at a page boundary once. When the events of one time fill a whole page, the page MUST continue inside that time by skipping the events of that time already shown, instead of stopping. The task manager MUST order the events of one time by their identifier, so that this skip neither repeats nor leaves out an event.
- **FR-024**: The activity log API MUST compute the total count only when a request asks for it.
- **FR-025**: The Activities page MUST keep not asking for the total count. (The page's query already omits it on `stable` and `develop`; today's cost comes from the server counting regardless, which FR-024 removes.)
- **FR-026**: Activities queries MUST keep their performance when the same query is repeated many times on one connection.

**Guards**

- **FR-027**: An automated check in CI MUST fail when a stored task-manager event type is missing from Infrahub's list.
- **FR-028**: An automated check in CI MUST fail when the command for old runs leaves different runs, logs or artifacts than the task manager's own cleanup on the same data.
- **FR-029**: An automated check in CI MUST fail when a new Activities filter returns different events than today's filter on the same data.

**Documentation**

- **FR-030**: The configuration reference MUST list the three retention settings and their defaults.
- **FR-031**: The upgrade guide MUST state:
  - that the upgrade, when at least 100,000 runs are older than the retention, and after it the automatic cleanup delete task history older than the retention, and that the deletion cannot be undone;
  - that operators who need older runs set a longer retention before upgrading, and that `--no-task-history-cleanup` does not keep them, because the automatic cleanup deletes the same runs after the upgrade;
  - that on Docker Compose the upgrade runs with the instance stopped, so its cleanup adds to the time the instance is down, with its expected duration;
  - that on Helm the operator waits for the task manager's rollout (`kubectl rollout status`) before running the upgrade with `kubectl exec`, and that the chart's pre-upgrade hook skips the cleanup, so operators who use it run the command for old runs after the upgrade;
  - when to run the command for old runs: after an upgrade through the Helm chart's pre-upgrade hook, after any other upgrade that skipped the cleanup or did not finish it, and after lowering a retention; new and small instances never need it;
  - that the command is the same on Compose and Helm and runs with the instance up;
  - the free disk needed for the rewrite, and that on very large instances tasks may pause for a few seconds while task history tables are rewritten with the instance up.
- **FR-032**: The documentation MUST state that lowering a retention frees disk only after running the command for old runs with the rewrite option, the same cleanup the upgrade runs, because the hourly cleanup deletes the records but does not return their disk space. It MUST give sizing guidance for the activity log (5.7 to 8.1 GiB per million stored events), state that the Enterprise default of 30 days keeps about 4 times as many Infrahub events as 7 days, and state that a list of the operator's own in `prefect-server.global.prefect.env` (Infrahub Helm chart) or `infrahub.prefect-server.global.prefect.env` (Enterprise Helm chart) replaces the chart's list as a whole, so it must set all three retention values.

### Key Entities

- **Run (task history)**: one execution of a background task, with a state, an end time once finished, task runs, logs and artifacts. Finished runs older than the task history retention are deleted.
- **Infrahub event (activity log)**: a change recorded by Infrahub and shown on the Activities page, with related items (account, branch, node, parent event). Kept for the activity log retention.
- **Task-manager event**: an internal event of the task manager (run state changes, heartbeats, worker and deployment events). Never shown; kept for the own-event retention.
- **Retention settings**: the three durations above, owned by the Infrahub configuration; OpsMill's Enterprise Docker Compose file and Helm chart set the activity log to 30 days.
- **Command for old runs**: the existing operator command, reimplemented to delete like the automatic cleanup, with a rewrite option that rewrites each task history and activity log table that is mostly free space; the upgrade prints the task history size, runs the same cleanup as its last step when at least 100,000 runs are older than the retention, and otherwise prints this command.

## Success Criteria *(mandatory)*

Timings are indicative: they come from local benchmarks, not a production contract. Every criterion is evidenced by the private performance tests (opsmill/infrahub-private-tests) on restored production-scale backups, on Postgres 14 and 18, before each part ships.

### Measurable Outcomes

- **SC-001**: With a constant workload, the task manager's storage grows by less than 10 % over a second full task history retention period after the upgrade.
- **SC-002**: After the cleanup, in the upgrade or through the command for old runs, the task history storage is no larger than what the runs within the retention need. An upgrade that skips the cleanup takes no longer than before. On a restored backup with 7.3 GB of task history (private-tests run 41706228147, 3 Nov, PostgreSQL 18, instance running), the cleanup deleted 422,735 runs in about 5 min 40 s and took the task history to 1.3 GB, with at most 0.4 GB extra disk, a longest lock wait of 4.2 s and no deadlock. The earlier local benchmark (about 8.5 minutes on 25 GB, about 2 hours 20 minutes on 100 GB) was measured before the deletes were limited to 1,000 runs per transaction.
- **SC-003**: Operators set all retention in one place: 3 settings, zero task-manager-specific variables.
- **SC-004**: With a year of activity log, the Activities default view and the account, branch and node filters load in about 1 s on a repeat load and up to about 3 s on the first load; combined filters load in 3 to 6 s and never more than 10 s.
- **SC-005**: With a year of activity log, sub-activities, branch-name filters and deleted-branch filters load in under 1 s (against 40 s to 5 minutes today).
- **SC-006**: 100 % of Activities filters return the same events as today's filters on the same data.
- **SC-007**: Zero Infrahub events are deleted before the activity log retention, and zero related items are left behind by any cleanup.
- **SC-008**: With the default retentions, Infrahub activity remains available for 7 days, or 30 days with OpsMill's Enterprise Docker Compose file or Helm chart, and listed Prefect internal events are removed after 2 days. Existing PostgreSQL files need not shrink after deletion.

## Clarifications

### Session 2026-10-04 (grilling of the design doc)

- Q: Target release? → A: 1.13, not 1.12.
- Q: Is the first upgrade's deletion safe by default? → A: Yes; it cannot be undone, operators who need older runs set a longer retention before upgrading. No skip option, no "keep everything" value. (Changed on 3 Nov, see below: `--no-task-history-cleanup` skips the upgrade's cleanup; the hourly cleanup still deletes the old runs.)
- Q: How is disk reclaimed after lowering a retention? → A: The existing command for old runs with its rewrite option. The same cleanup the upgrade runs; the option rewrites whatever the deletes freed, since the automatic cleanup deletes first. Event storage has no reclaim; lowering is rare. (Changed on 8 and 11 Oct, see below: no maintenance window, and the rewrite covers the event tables.)
- Q: Guard against running the rewrite on a live instance? → A: No; operators who run these commands know what they do. The rewrite is off by default.
- Q: Are the behaviour-table timings a contract? → A: No, indicative; 1 or 2 seconds either way is fine.
- Q: What happens to the existing command for old runs? → A: It is reused with the new implementation.
- Q: How do retention settings reach a separate background-services deployment? → A: A thin Infrahub command starts it after applying the same settings.
- Q: Are the SQL cleanup and the new filters checked on task-manager upgrades? → A: Yes, by CI equivalence checks.
- Q: Fallback if product refuses to remove the total count? → A: None; argue for removal. (Later found moot: the page never asked for the count; the design doc dropped D7 and Q2.)
- Q: Values accepted by the settings? → A: Durations of at least 1 day, refuse to start otherwise; an own-event retention longer than the activity log is refused at startup, as design doc D5 records.
- Q: Activity log default? → A: Stays 7 days; retention can be configured up to 365 days, subject to the pending edition decision. (Changed on 3 Nov, see below: 7 days on Community, 30 days on Enterprise.)
- Q: Helm upgrade? → A: The pre-upgrade hook does not run the cleanup; a maintenance step after the rollout does. (Changed on 11 Oct, see below: the upgrade runs no cleanup on Compose either. Changed again on 3 Nov, see below: the upgrade cleans up a large backlog, and the chart passes `--no-task-history-cleanup` to its hook.)
- Q: Load more by time and time windows? → A: Windows count back from the oldest event shown.
- Q: Auth on the cleanup endpoint? → A: Not added; out of scope.

### Session 2026-10-11 (design doc changes for implementation)

From the design doc's "Design changes for implementation" list, entries of 8 and 11 Oct. The design doc no longer has this list.

- Q: Does the upgrade run the one-off task history cleanup? → A: No. The upgrade deletes nothing and prints how much disk space the task history takes and the command to run; that hint must never fail or slow the upgrade, also against an older task manager. Existing instances with a lot of task history run the cleanup step once after the upgrade, the same on Compose and Helm, with the instance running. New and small instances never need it. The `--no-task-history-cleanup` option and the upgrade's rewrite rule are removed. (Changed on 3 Nov, see below: the upgrade cleans up a backlog of at least 100,000 old runs, and `--no-task-history-cleanup` is back.)
- Q: Which tables does the rewrite cover, and when? → A: The six task history tables and the activity log's two tables, each table only when its live rows hold less than half of its disk space, instead of always and the task history tables only.
- Q: What does the command report about tables it does not rewrite? → A: It names each table it skipped and why: mostly live rows, or locked by other sessions (a suggestion in the design doc, implemented).
- Q: Does the hint or the command report how many old runs are left? → A: The hint does (asked for on 11 Oct, after the suggestion in the design doc): it counts the runs older than the retention up to 100,000 and says "more than 100,000" beyond that, so the count stays fast on millions of runs. With no old runs left, the cleanup step is mostly the rewrite. (Since 3 Nov the count also decides whether the upgrade cleans up, see below.)
- Q: Decision numbers? → A: The design doc renumbered its decisions on 11 Oct in page order: the Activities page is D4, editions D6, getting disk space back D7 and default values D8. This spec set keeps the numbers it was written with (D6, D8, D9, D10). The design doc no longer notes this difference.

### Session 2026-11-03 (product decisions)

- Q: Which source wins for these answers? → A: They are product decisions of 3 Nov and take precedence over the design doc's earlier entries on the same points; the design doc records them under D6 (editions) and D7 (getting disk space back).
- Q: Does the upgrade clean up a large task history? → A: Yes, as its last step, "Task history cleanup" (step 7 of 7), after the branch rebase. When the task manager reports at least 100,000 finished top-level runs older than the task history retention, the upgrade runs the same cleanup as `infrahub tasks flush flow-runs --rewrite`: it deletes those runs with their logs and artifacts, then rewrites each task history and activity log table that is mostly free space, and prints its progress and a summary. Otherwise it prints why it skipped and the command: `--no-task-history-cleanup` given, the task history not reported, Prefect's vacuum switch keeping old runs (without the command), or fewer than 100,000 old runs, which Prefect's hourly cleanup deletes. The task manager step prints the task history size and the old runs, or why it could not read them. A cleanup that fails or cannot start never fails the upgrade, and the upgrade waits at most 2 minutes without a cleanup to follow. The deletion cannot be undone: operators who need older runs set a longer retention before upgrading, or pass `--no-task-history-cleanup`. (In the code, the option only skips the upgrade's cleanup: the hourly cleanup deletes the same runs after the upgrade, so only a longer retention keeps them.) This reverses the answers of 4 and 11 Oct that the upgrade deletes no task runs, that there is no skip option and that `--no-task-history-cleanup` is removed.
- Q: How does the upgrade's cleanup work on Docker Compose and Helm? → A: Docker Compose runs the upgrade with the instance stopped (`docker compose run`), so the cleanup adds to the time the instance is down. On Helm, the documented upgrade runs `kubectl exec ... infrahub upgrade` after `helm upgrade`; it reaches the new task manager only after the task manager's rollout has finished, so the guide says to wait for it. The chart's optional pre-upgrade hook runs before Helm replaces the task manager, so on the first upgrade to this release it reaches the previous task manager and the cleanup is skipped; the chart passes `--no-task-history-cleanup` to the hook ([opsmill/infrahub-helm#100](https://github.com/opsmill/infrahub-helm/pull/100)), because Helm waits at most 5 minutes for a hook by default. Helm operators therefore run the command for old runs after the upgrade.
- Q: When do operators still run the command for old runs? → A: In three cases:
  - on Helm, after an upgrade through the chart's pre-upgrade hook, which skips the cleanup;
  - after any other upgrade that skipped the cleanup or did not finish it;
  - after lowering a retention, because the hourly cleanup deletes the records but does not return their disk space.
- Q: Editions? → A: The activity log default is 7 days on Community and 30 days on Enterprise. OpsMill's Enterprise Docker Compose file (opsmill/infrahub-private, change prepared) and Enterprise Helm chart ([opsmill/infrahub-helm#100](https://github.com/opsmill/infrahub-helm/pull/100)) set it, as they set `INFRAHUB_WORKFLOW_DEFAULT_WORKER_TYPE`; the Infrahub code default stays 7 days. Both editions have the same settings and the same range (1 to 365 days), with no edition gate, and nothing stops a Community operator from raising the activity log retention. An Enterprise setup that does not use OpsMill's Compose file or Helm chart keeps 7 days unless it sets `INFRAHUB_TASK_MANAGER_RETENTION_ACTIVITY_LOG`. 30 days keeps about 4 times as many Infrahub events as 7 days. This settles the pending edition decision.

## Assumptions

- The task manager is the only component that connects to its own database, so the cleanup used by the command for old runs runs inside the task manager.
- The task manager's built-in cleanup of old runs follows the same rules in the pinned version as measured (finished top-level runs by end time, logs and artifacts with their runs).
- Infrahub sets no custom run-state names, so the task manager's state events come only from its built-in states.
- The command for old runs runs with the instance up, so tasks that read or write a table wait while it is rewritten. The upgrade's cleanup runs with the instance stopped on Docker Compose and with the instance up on Helm.
- Nothing in Infrahub reads runs older than 30 days except to show them; whether customer tooling reads old runs through the task manager's API is unknown and is covered in the release notes.
- Production installs may run a database version OpsMill does not choose, so the Activities queries must work on the oldest supported version (Postgres 14) and later.

## Dependencies & Open Questions

- **Q1 (blocks the release notes)**: how long the cleanup step takes on a large instance. Measured about 8.5 minutes on 25 GB and about 2 h 20 min on 100 GB, almost all of it the deletes; why 100 GB is about 4 times slower per run is not confirmed. Both were measured before 28 Oct, when the deletes were limited to 1,000 runs per transaction; since then, they were measured in CI on 25.8 GB of task history with PostgreSQL 18: the upgrade's cleanup step took 13 min 52 s and 15 min 56 s (private-tests runs 42025227297 and 42016409033), and the command run by hand took 17 to 20 minutes (runs 42013835783, 42213633937 and 42013854499). Both were also measured without the pauses between rewritten tables, which add at most 60 s per table after the first. Known instances hold about 20 to 35 GB. Since 3 Nov the upgrade includes it again when at least 100,000 runs are old, so on Docker Compose it adds to the time the instance is down. Measured on 3 Nov on a restored backup with 7.3 GB of task history: 422,735 runs deleted in about 5 min 40 s, about 1,250 runs a second (private-tests run 41706228147); 100 GB was not re-measured.
- **Deep scrolling by time**: scrolling far down a combined filter, on both supported database versions, was not measured.
- **Activities requests that still match a label with no index**: a node filter with no event type, which is what the Activities page sends, and the branch-name option of merges and rebases listed with other event types. SC-004 and SC-005 are not shown for these two requests, and how long they take is not known. Tests that time them are prepared for opsmill/infrahub-private-tests#62 and have not run. Not decided for the node filter: a separate read for the three event types that keep the node only in a label, or recording the node in their resource ID.
- **Edition availability**: decided on 3 Nov (see Clarifications): the same settings and range in both editions, and a 30-day activity log default on Enterprise, set by OpsMill's Enterprise Docker Compose file and Helm chart.
- **Changes outside this repository, in the same release**: the Enterprise Docker Compose file in opsmill/infrahub-private (30-day activity log; prepared, and waits until its pointer to this repository includes [opsmill/infrahub#11289](https://github.com/opsmill/infrahub/pull/11289)), and the Helm chart in [opsmill/infrahub-helm#100](https://github.com/opsmill/infrahub-helm/pull/100) (30-day activity log in the Enterprise chart, `--no-task-history-cleanup` in the pre-upgrade hook).
- Non-blocking: whether runs accumulate in SCHEDULED, LATE, PAUSED or CANCELLING, and whether runs legitimately stay RUNNING more than 2 days.
- **Release evidence**: the private performance tests (Activities queries, task history retention, the cleanup step, activity log retention, cleanups under load, database size and dead space) must pass and be attached to each part's PR and to INFP-507; PR #33 in opsmill/infrahub-private-tests lands first.
- Delivery order: part 1 task history (User Story 1, with the background-services command of User Story 4), part 2 Activities page (User Story 2), part 3 activity log retention (User Story 3), part 4 documentation with parts 1 and 3. Part 2 lands before part 3.

## Out of Scope

- Tasks page performance at 1M+ runs, latency targets and an Infrahub-owned activity-log store (INFP-727).
- Memory growth from task-manager cache keys that never expire.
- An edition gate on the retention settings: both editions have the same settings and range (decided on 3 Nov).
- New indexes or tables in the task manager's database, a capped total count, and the newest-events shortcut query (rejected in the design doc).
- Upstream task-manager changes (prefix keys in per-type retention, faster per-type cleanup).
- Keeping activity beyond the retention for audit (log forwarding, unchanged).
