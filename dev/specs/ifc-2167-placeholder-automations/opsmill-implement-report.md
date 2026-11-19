# Implementation report: Record template fingerprints in the database instead of placeholder automations

- **Status**: INCOMPLETE (tasks T038 and T041 are still unticked in `tasks.md`)
- **Spec directory**: `dev/specs/ifc-2167-placeholder-automations/`
- **Base commit**: `0d36b64bd9b8b031cf8fe84b613fb8d905a811ba`
- **Head commit**: `bc21bc7c65d37a87eba8960763cebf0e00c90280`

## Chunk-by-chunk ledger

### Phase 1: Setup

- Tasks: 2 (✅ 2 / ⚠️ 0 / ❌ 0)
- Commits: `f4a65de670`, `872aa5bf32`
- Decisions flagged:
  - `backend/tests/component/hfid/` did not exist before and was created; the other parent packages already had an `__init__.py`.

### Phase 2: Foundational (fingerprint store, collector and decision)

- Tasks: 8 (✅ 8 / ⚠️ 0 / ❌ 0)
- Commits: `e5edec7245`, `c6ee99819d`
- Decisions flagged:
  - The decision function is `decide_fingerprint_changes` in `core/template_fingerprint/decision.py`; it returns `to_recompute` and `to_record` sorted by kind.
  - The read query filters on `family` and returns only `branch`, `kind` and `fingerprint`. The explicit skip of a record whose `family` is not a `TemplateFamily` value (T008) was not written, because it cannot trigger after the filter.
  - The read query orders by `branch, kind`, because `Query.execute` reads a READ query in pages.
  - `insert_missing` counts the created vertices in Cypher through a fresh uuid per entry, not through query statistics, which can omit a zero counter. The repository removes duplicate keys from its input.
  - The delete-branch Query class takes `branch_name`, because `branch` is a parameter of the `Query` base constructor.
  - The collector is split into `fingerprints_from_schema_branches` (no registry read) and `collect_schema_fingerprints` (reads the registry).
  - T009 asked to reuse existing schema fixtures; the tests build `DisplayLabels` and `HFIDs` directly, because no fixture builds a processed `SchemaBranch` without a database.
  - The md5 values in `test_collector.py` are pinned literals, so that a change of the hashing shows up as a test failure.

### Phase 3: User Story 1 - Keep the task manager free of automations that never run (P1), Jinja2 computed attributes

- Tasks: 6 (✅ 6 / ⚠️ 0 / ❌ 0)
- Commits: `f55b27d25b`, `c7308ee8b5`
- Decisions flagged:
  - T011 renamed `test_gather_trigger_computed_attribute_jinja2_only_main` to `..._skips_template_reading_only_its_node`; the gather now returns an empty list for that template. The branch test keeps only the `TestPerson` peer automation.
  - T013 cases pass on the code before T015 too; they pin the submissions that T015 must keep (FR-012).
  - T015 compares with the default branch in `_has_default_branch_template` in `computed_attribute/tasks.py`; it returns false when the default branch lacks the kind, the attribute or its computed attribute. A `BranchDeletedEvent` now empties the candidate list after scoping.
  - `uv run mypy tests/component/computed_attribute/test_gather.py` reported 6 errors on lines this chunk did not change; the full `backend.mypy` run in T040 passed.

### Phase 4: User Story 2 - Stored values are recomputed exactly when a template changes (P1), display labels and HFIDs

- Tasks: 8 (✅ 8 / ⚠️ 0 / ❌ 0)
- Commits: `9a1aae8326` (WIP), `fa7f6bfe96`, `1fbd9675f9`
- Decisions flagged:
  - The steps shared by both setup flows (decision, delete, submit, record) are in a new component, `TemplateFingerprintRefresher` in `core/template_fingerprint/refresher.py`.
  - `SchemaFingerprints.as_records()` was added.
  - T024 departs from the task text: the first-start seed is `seed_template_fingerprints(db)` in `workflows/initialization.py`, called by `WorkflowWorkerExecution.initialize` after `setup_task_manager_identifiers`, because opening a database session inside `setup_task_manager_identifiers` creates an import cycle. `InfrahubServices.initialize_workflow` now takes a required `database` parameter. No test exercises `WorkflowWorkerExecution.initialize` itself.
  - The T024 test is in `backend/tests/component/core/template_fingerprint/test_seed.py`, not in `backend/tests/component/core/test_initialization.py`, because that module resets the shared database.
  - The display label and HFID scenarios are shared in `backend/tests/helpers/template_fingerprint.py` (`TemplateSetupScenarios`) with a small test schema.
  - T017 now compares gathered trigger names with the peer triggers instead of counting one trigger per node with a display label.
  - The HFID tests were not run against the previous HFID code (no bite check for HFIDs).
  - `setup_triggers_specific` is still used by the computed attribute flows and was kept.

### Phase 5: User Story 3 - Upgrade an existing instance without a full recompute (P2)

- Tasks: 5 (✅ 5 / ⚠️ 0 / ❌ 0)
- Commits: `7aa90f94de` (WIP), `f7c55ebef8`, `dc9e82a9f8`
- Decisions flagged:
  - The carry-over (`backend/infrahub/trigger/placeholder_carry_over.py`) takes a `Sequence[SchemaFingerprints]`; a branch is in scope only when it is in the `SchemaFingerprints` of the automation's family.
  - The "matches only `TRIGGER_PLACEHOLDER_FIELD`" condition is checked on the union of field names over every `match_related` entry, so branch exclusion entries do not affect it.
  - Skipped automations are logged at debug level through `infrahub.log.get_logger()`, because the function also runs outside a Prefect run context.
  - In `trigger_configure_all`, the carry-over runs after the Prefect client is closed and did not take the family locks. The review later changed this (see the review findings).

### Phase 6: User Story 4 - Branch lifecycle keeps the recorded fingerprints consistent (P3)

- Tasks: 3 (✅ 3 / ⚠️ 0 / ❌ 0)
- Commits: `0e3de8bfba` (WIP), `56707de6c7`, `fc5c900bcc`
- Decisions flagged:
  - `BranchDataDeleter.delete_branch_data` calls a new private step, `_delete_template_fingerprints`, first.
  - `TemplateFingerprintRepository.delete_branch` and its test were removed, because nothing called them. `contracts/fingerprint-store.md` was updated. `critiques/critique-20261119.md` and task T006 in `tasks.md` still name the removed method.
  - The "stale registry" case of T030 passes without the T032 change too, because repository writes require a `Branch` vertex.
  - T031 was not run against code without the out-of-scope deletion of the decision.
  - An untracked `backend/t031.log` was left in the worktree. It was later committed in `fc5c900bcc` (see the review findings).

### Phase 7: Polish and cross-cutting concerns

- Tasks: 9 (✅ 7 / ⚠️ 0 / ❌ 2: T038, T041)
- Commits: `e0f43c6e2a`, `cc49b0a087`
- Decisions flagged:
  - T033 describes the seed as running in `WorkflowWorkerExecution.initialize`, where Phase 4 placed it, not in `setup_task_manager_identifiers` as the task text said.
  - T034 states that Jinja2 computed attributes have no carry-over, because their decision reads no stored fingerprint.
  - T035 kept the existing family list in `events.md`, because the peer automations of those families still follow the per-branch scoping.
  - T036: a direct `vale` call needed an approval; `uv run invoke release.vale` reported 0 errors and no warning on `+ifc-2167.changed.md`.
  - T039 did not check whether the containers ran this branch's code or a published image (`INFRAHUB_TESTING_IMAGE_VER`).
  - T040: every command passed without a code change.

### Phase 7: Polish and cross-cutting concerns (second pass, T038 and T041)

- Tasks: 2 (✅ 0 / ⚠️ 1: T038 / ❌ 1: T041)
- Commits: `5e9108824b`, `7392bd4a78`
- Decisions flagged:
  - T038 measured the query plan on 480 synthetic records (2 families × 4 branches × 60 kinds) written through the repository, not on a loaded schema of 50 kinds. The plan is a `NodeByLabelScan` on `TemplateFingerprint` followed by a filter on `family`, about 4 database hits per record. This matches research Decision 3, so no index is proposed.
  - The empty scratch file `backend/tests/component/core/template_fingerprint/tmp_explain_check.py` could not be deleted and was committed.

### Review

- Commits: `2e1df23bbc`, `bc21bc7c65`

## Tasks not completed

- **T038** (⚠️ partial): the query plan was measured (recorded in the ledger and in the Phase 7 second pass above), but it cannot be recorded in the PR description because no PR exists for this branch. The database held synthetic records, not a loaded schema of 50 kinds with 3 diverging branches.
- **T041** (❌ blocked): needs a local stack built from this branch, a second stack on the previous release for the SC-005 comparison, and a PR description to record the results in. Not runnable inside the unattended chunk.

## Local-pass evidence

| Test id | Type (unit/integration/e2e) | Run command | Passed at (ISO 8601) | Environment context | Verbatim pass line |
|---------|-----------------------------|-------------|----------------------|---------------------|--------------------|
| backend/tests/unit/core/template_fingerprint/test_decision.py (12 tests) | unit | `cd backend && uv run pytest tests/unit/core/template_fingerprint/ tests/component/core/template_fingerprint/ -v` | 2026-11-19T14:49:57Z | macOS, Python 3.14 | `======================= 25 passed, 17 warnings in 17.39s =======================` |
| backend/tests/unit/core/template_fingerprint/test_collector.py (6 tests) | unit | same command | 2026-11-19T14:49:57Z | macOS, Python 3.14 | `======================= 25 passed, 17 warnings in 17.39s =======================` |
| backend/tests/component/core/template_fingerprint/test_repository.py (7 tests) | integration (component, Neo4j) | same command | 2026-11-19T14:49:57Z | Neo4j started by testcontainers through the local Docker daemon | `======================= 25 passed, 17 warnings in 17.39s =======================` |
| backend/tests/component/computed_attribute/test_gather.py (jinja2 tests modified) | integration (component, Neo4j) | `cd backend && uv run pytest tests/component/computed_attribute/ tests/functional/computed_attributes/test_local_computation.py -q` | 2026-11-19T15:15:31Z | Neo4j and Prefect test server started by testcontainers through the local Docker daemon, macOS, Python 3.14 | `================= 70 passed, 17 warnings in 662.21s (0:11:02) ==================` |
| backend/tests/functional/computed_attributes/test_local_computation.py::TestJinja2ComputedAttributeWithRelationship (2 tests modified) | integration (functional) | same command | 2026-11-19T15:15:31Z | same | `================= 70 passed, 17 warnings in 662.21s (0:11:02) ==================` |
| backend/tests/component/computed_attribute/test_placeholder_removal.py::TestPlaceholderRemoval::test_setup_deletes_placeholder_and_keeps_peer_automation | integration (component, Prefect test server) | same command | 2026-11-19T15:15:31Z | same | `================= 70 passed, 17 warnings in 662.21s (0:11:02) ==================` |
| backend/tests/component/computed_attribute/test_scoped_recompute_jinja2.py (3 new tests) | integration (component, Prefect test server) | `cd backend && uv run pytest tests/component/computed_attribute/test_scoped_recompute_jinja2.py -q` | 2026-11-19T15:18:32Z | same | `================== 8 passed, 17 warnings in 167.42s (0:02:47) ==================` |
| backend/tests/component/display_labels/test_gather.py (2 tests modified) | integration (component, Neo4j) | `cd backend && uv run pytest tests/component/display_labels/ -q` | 2026-11-19T15:59:30Z | Neo4j and Prefect test server started by testcontainers through the local Docker daemon, macOS, Python 3.14 | `================= 10 passed, 17 warnings in 285.04s (0:04:45) ==================` |
| backend/tests/component/display_labels/test_setup.py::TestDisplayLabelSetup (8 tests) | integration (component, Prefect test server) | same command | 2026-11-19T15:59:30Z | same | `================= 10 passed, 17 warnings in 285.04s (0:04:45) ==================` |
| backend/tests/component/hfid/test_setup.py::TestHFIDSetup (10 tests) | integration (component, Prefect test server) | `cd backend && uv run pytest tests/component/hfid/test_setup.py tests/component/core/template_fingerprint/test_seed.py -q` | 2026-11-19T15:54:30Z | same | `================= 11 passed, 17 warnings in 414.08s (0:06:54) ==================` |
| backend/tests/component/core/template_fingerprint/test_seed.py::TestTemplateFingerprintSeed::test_first_start_records_every_template_and_next_update_submits_nothing | integration (component, Prefect test server) | same command | 2026-11-19T15:54:30Z | same | `================= 11 passed, 17 warnings in 414.08s (0:06:54) ==================` |
| backend/tests/helpers/template_fingerprint.py (shared scenarios, run through the two setup classes above) | integration (component) | covered by the commands above | 2026-11-19T15:59:30Z | same | see the rows above |
| backend/tests/unit/trigger/test_placeholder_carry_over.py::test_parse_placeholder_automation (14 cases) | unit | `cd backend && uv run pytest tests/unit/trigger/ tests/component/trigger/test_placeholder_carry_over.py tests/component/display_labels/test_setup.py tests/component/hfid/test_setup.py -q` | 2026-11-19T16:26:22Z | macOS, Python 3.14 | `================= 58 passed, 17 warnings in 556.74s (0:09:16) ==================` |
| backend/tests/component/trigger/test_placeholder_carry_over.py::TestPlaceholderCarryOver::test_upgrade_carries_placeholder_fingerprints_over | integration (component, Prefect test server and Neo4j) | same command | 2026-11-19T16:26:22Z | Neo4j and Prefect test server started by testcontainers through the local Docker daemon, macOS, Python 3.14 | `================= 58 passed, 17 warnings in 556.74s (0:09:16) ==================` |
| backend/tests/component/trigger/test_placeholder_carry_over.py::TestPlaceholderCarryOver::test_second_upgrade_keeps_existing_records | integration (component, Prefect test server and Neo4j) | same command | 2026-11-19T16:26:22Z | same | `================= 58 passed, 17 warnings in 556.74s (0:09:16) ==================` |
| backend/tests/component/branch/test_template_fingerprint_cleanup.py::TestTemplateFingerprintCleanup (3 tests) | integration (component, Prefect test server and Neo4j) | `cd backend && uv run pytest tests/component/branch/ tests/component/display_labels/ tests/component/core/template_fingerprint/test_repository.py -q` | 2026-11-19T17:04:51Z | Neo4j and Prefect test server started by testcontainers through the local Docker daemon, macOS, Python 3.14 | `================= 36 passed, 17 warnings in 493.70s (0:08:13) ==================` |
| backend/tests/component/display_labels/test_setup.py::TestDisplayLabelSetup::test_branch_that_stops_owning_its_schema_loses_its_records | integration (component, Prefect test server and Neo4j) | same command | 2026-11-19T17:04:51Z | same | `================= 36 passed, 17 warnings in 493.70s (0:08:13) ==================` |
| backend/tests/component/core/template_fingerprint/test_repository.py (one test removed, rest unchanged) | integration (component, Neo4j) | same command | 2026-11-19T17:04:51Z | same | `================= 36 passed, 17 warnings in 493.70s (0:08:13) ==================` |
| backend/tests/integration_docker/test_computed_attributes.py (T039 regression, not modified) | integration (docker stack) | `uv run pytest backend/tests/integration_docker/test_computed_attributes.py -q` | 2026-11-19T17:11:26Z | Infrahub stack started by testcontainers through the local Docker daemon, macOS, Python 3.14; image from `INFRAHUB_TESTING_IMAGE_VER`, not checked against this branch's code | `================= 11 passed, 17 warnings in 225.51s (0:03:45) ==================` |

No test row is `MISSING` and no E2E test was deferred.

After the review fix, the ledger records one more run without a timestamp or a run command: the display label and HFID setup tests, the carry-over tests (unit and component), the seed test and the fingerprint unit tests ran with `78 passed, 17 warnings in 623.05s`. The computed attribute, branch cleanup and repository component tests were not run again after the review fix.

## Review findings

Review mode: command (/code-review)

The `pr-review-toolkit` agents were not among the available subagent types, so the review ran with `/code-review medium 0d36b64bd9b8b031cf8fe84b613fb8d905a811ba..HEAD`. The ledger maps the command's ratings (important, pre-existing, nit) to high, medium and low.

| Severity | File | Line | Summary | Fixed or deferred |
|----------|------|------|---------|-------------------|
| high | backend/infrahub/trigger/tasks.py | 52 | `trigger_configure_all` (run by `infrahub upgrade`) and the initial-setup seed wrote fingerprint records without the per-family configuration lock. A setup flow running during the upgrade could find neither a placeholder nor a record and recompute every kind, or two writers could create duplicate records. | Fixed: `template_fingerprint_locks()` in `trigger/setup.py` holds both family locks in a fixed order around the trigger setup and carry-over in `trigger_configure_all`, and around the identifier setup and seed in the worker's initial setup. No uniqueness constraint added (research Decision 3). |
| medium | backend/infrahub/core/template_fingerprint/decision.py | 26 | Deletions cover every branch of this worker's branch registry, but only the event branch's schema is waited on. A worker whose registry holds an old schema for another branch can delete that branch's records, which causes an extra recompute at that branch's next schema update, never a missed one. | Deferred |
| medium | backend/infrahub/core/template_fingerprint/refresher.py | 55 | The fingerprint is recorded when the recompute is submitted, not when it succeeds, so a recompute flow that fails is not retried by later schema updates. FR-006 asks for this behavior; the reviewer tagged it as pre-existing. | Deferred |
| low | backend/infrahub/display_labels/tasks.py | 124 | The configuration lock name was spelled out in three places. | Fixed: all three call `trigger_configuration_lock()` in `trigger/setup.py`. |
| low | backend/t031.log | 1 | A local pytest run log with absolute paths was committed in `fc5c900bcc`. | Deferred: delete it before opening the PR. |
| low | backend/tests/component/core/template_fingerprint/tmp_explain_check.py | 1 | An empty scratch module from the T038 query-plan check was committed. | Deferred: delete it before opening the PR. |

No test asserts that `trigger_configure_all` or the seed hold the family locks.

## Autonomous decisions

- **Seed placement (T024)**: the first-start seed runs in `WorkflowWorkerExecution.initialize`, not in `setup_task_manager_identifiers` as the task text said, to avoid an import cycle. This added a required `database` parameter to `InfrahubServices.initialize_workflow`. No test exercises `WorkflowWorkerExecution.initialize`.
- **Repository method removed (T032)**: `TemplateFingerprintRepository.delete_branch` was removed; `BranchDataDeleter` runs the delete query directly. Task T006 in `tasks.md` and `critiques/critique-20261119.md` still name the removed method.
- **Carry-over without locks, then with locks**: Phase 5 ran the carry-over in `trigger_configure_all` without the family locks; the review's high-severity fix added them.
- **Skipped check in T008**: the explicit skip of a record whose `family` is not a `TemplateFamily` value was not written, because the query filter makes it unreachable.
- **Partial bite checks**: the HFID setup tests were not run against the previous HFID code, and T031 was not run against code without the out-of-scope deletion.
- **T039 image not checked**: the regression run did not confirm that the containers ran this branch's code.
- **Blocked tasks**: T038 (query plan measured on synthetic data, not recorded in a PR) and T041 (live scenarios and SC-005 measurement not run).
- **Review triage**: the reviewer's "important" deletion-scope finding in `decision.py` was rated medium and deferred, because it only causes extra recomputes. The submit-time recording finding was deferred because FR-006 asks for it. The two committed scratch files were deferred.
- **Review mode**: `command` (`/code-review`), because the `pr-review-toolkit` agents were not available. This mode does not block the run.

## Suggested next steps

1. Delete `opsmill-implement-ledger.md` from this spec directory: this report holds its content, but deleting it in this run needed an approval that nobody could give. Delete `backend/t031.log` and `backend/tests/component/core/template_fingerprint/tmp_explain_check.py`.
2. Complete T041: start a stack built from this branch, run scenarios 1 to 4 of `quickstart.md`, and measure SC-005 against the previous release.
3. Complete T038: run `EXPLAIN` on a database loaded with at least 50 kinds and 3 diverging branches, or accept the synthetic-data measurement.
4. Open a PR and record the T038 query plan and the T041 results in its description, then tick both tasks.
5. Re-run the computed attribute and branch cleanup component tests after the review fix, which were not run again.
6. Decide on the deferred medium finding about the deletion scope in `decision.py`.
7. Update task T006 in `tasks.md`, which still describes the removed `delete_branch` repository test.
8. Consider a test that asserts `trigger_configure_all` and the seed hold the family locks.
