# Implementation report: store schema changes and query the schema change history of a branch

- **Feature**: IFC-3614, stored schema changes and the `InfrahubSchemaChange` history query
- **Spec directory**: `dev/specs/ifc-3614-store-schema-changes/`
- **Base commit**: `78e6a0c1b15a4c020f2c20c63b0d33423e5903d0`
- **Head commit**: `1a612aaf6c` (before this report's commit)
- **Wall-clock time**: 2026-11-17T02:59:23Z to 2026-11-17T18:47Z, about 15 h 48 min, including time spent waiting
  for the user's decisions
- **Status**: DONE. All 65 tasks are `[X]`, §4 has no `MISSING` row, and the review ran in `command` mode.

## 1. Run summary

- 20 chunks from `tasks.md`, one added chunk (T065, decided by the user during the run), one
  review pass and one fix pass, each in a clean-context subagent, one after the other.
- 30 commits on top of the base commit.
- The user accepted the GraphQL contract gate at the start of the run ("Accepted, run all").

## 2. Chunk ledger

| # | Chunk | Tasks | Outcome | Commits | Decisions or surprises flagged |
| --- | --- | --- | --- | --- | --- |
| 1 | Phase 1 Setup | T001–T002 (2) | ✅ 2 | `502d0f6d87` | Edge type names are an enumeration, `SchemaChangeEdgeType`. Named the page-size and format constants. |
| 2 | Phase 2 Foundational | T003–T005 (3) | ✅ 3 | `0c865ea814` | "Not set" kept apart from JSON `null` through `model_fields_set`. The validator refuses `id` and `parameters.number_pool_id` keys even with a null value. The summary of an element property change uses the element name (recorded in R10). |
| 3 | Phase 3 equivalence suite | T006–T010 (5) | ✅ 5 (test-first) | `0c4585cfee` | Two cases moved to other elements because today's load refuses them as written. |
| 4 | Phase 3 builder, applier and known-bug tests | T011–T014 (4) | ✅ 4 (test-first) | `6bee87f94e` | Recorded today's behaviour for the four known bugs. The profile-rename strict xfail does not detect a fix made inside the rename query. |
| 5 | Phase 3 builder, applier, gate | T015–T017 (3) | ✅ 3, gate green | `c3c935efc0` | `element_add` values hold `order_weight` (format change, spec files updated). Two tests corrected to typed attribute classes. All four FR-025 cases are strict expected failures. |
| 6 | Phase 3 candidate and wiring | T018–T020 (3) | ✅ 3 | `15914a1916` | The comparer parses a kind again before naming it, so plain against typed attribute classes is not a difference. Assertions on `SchemaUpdatedEvent.changed_elements` added to three mutation tests. |
| 7 | Phase 3 regression sweep, timing | T021–T022 (2) | ✅ 2 | `67e1d04763`, `abf263969e` | The sweep found two builder gaps (number pool ranges, `state: absent` on an override); both fixed with equivalence cases. Benchmark ratio 2.00. |
| 8 | Phase 4 component tests | T023–T026 (4) | ✅ 4 (test-first) | `2fdef2c0be` | `mark_failed` moved from phase 5 into T030/T032. The repository, reader and seeding interfaces were written into the contract. |
| 9 | Phase 4 functional tests | T027–T028 (2) | ✅ 2 (test-first) | `7c43232774` | Ordered class with `test_stepNN_` methods. |
| 10 | Phase 4 records, queries, repository, resolver, recorder | T029–T033 (5) | ✅ 5 | `0ce35194c3` | `SchemaChangeRecording` holds `at`. A history page is two queries. |
| 11 | Phase 4 migration recorder and flow | T034–T036 (3) | ✅ 3 | `121487d38f` | The flow builds the recorder on its own session. The recorder catches database, timeout and Neo4j errors. |
| 12 | Phase 4 runner and load wiring | T037–T038 (2) | ✅ 2 | `dd1d168f27` | `fail` was left out of the `ApplicationRecorder` protocol until T049. Each record write commits on its own. |
| 13 | Phase 4 single-pass load (added by the user's decision) | T065 (1) | ✅ 1 | `5736e6aa90` | Benchmark ratio from 2.00 to 1.00. The replay check runs only in the test suites, through `config.OVERRIDE.schema_operations_check`. Spec decision 8 added. |
| 14 | Phase 4 GraphQL query | T039–T043 (5) | ✅ 5 | `ccdc618ab7` | Added `count_schema_changes`. Step 10 corrected: migration positions follow the order of a set, so they can change between runs. |
| 15 | Phase 5 failed loads | T044–T049 (6) | ✅ 6 | `b44956c091` | `MigrationError` has an empty `str()`; the runner stores `exc.message`. |
| 16 | Phase 6 mutation history | T050–T051 (2) | ✅ 2 | `c7578b88b1` | Stored choice lists include `id: None` and `state`. `update_schema_hash()` is still called without `at`. |
| 17 | Phase 7 branch deletion | T052–T055 (4) | ✅ 4 | `8be84871b6` | A batch is up to `batch_size` schema changes, each with all its records; a schema change with many operations makes one large transaction. |
| 18 | Phase 8 tests | T056–T057 (2) | ✅ 2 | `97ec191eff` | A merge and a rebase store no record. A local image `registry.opsmill.io/opsmill/infrahub:local-ifc3614` was built and left on the machine. |
| 19 | Phase 8 documentation | T058–T060 (3) | ✅ 3 | `03179b95b2` | After the run, the user dropped the changelog fragment of T058 and the user documentation of T059 because the epic will change the query and the records; both were removed. The knowledge document of T060 remains. |
| 20 | Phase 8 validation | T061–T064 (4) | ✅ 3, ⚠️ 1 | `645e6c2e68`, `a47e6c86ec` | T063: quickstart section 6 was checked against the code and the Docker integration test, not run. The replay check found two failures, fixed in the review pass. |
| R | Review fixes | — | ✅ 7 fixes | `d45772b250`, `9f4a728516`, `71ccf91104`, `c37ebabeec`, `5801f3b409`, `00d55f8849`, `897e0b5307`, `1a612aaf6c` | See §5. |

## 3. Tasks not completed

None. Every task of `tasks.md`, T001 to T065, is `[X]`.

## 4. Local-pass evidence

Environment for every row: Linux, 8 vCPU, Python 3.12.13 virtual environment from `uv`. "testcontainers"
means a Neo4j container started by the test session, one Docker-backed pytest command at a time. The
row gives the last passing run of the test as it is on the head commit.

### Unit tests

| Test id | Type | Run command | Passed at | Environment | Verbatim pass line |
| --- | --- | --- | --- | --- | --- |
| `backend/tests/unit/core/schema_change/test_operations.py` (32 tests: `test_operation_is_refused[14 cases]`, `test_operation_is_accepted[4]`, `test_null_value_is_kept_apart_from_a_value_that_is_not_set`, `test_summary[8]`, `test_summary_of_no_operation_is_refused`, `test_name[4]`) | unit | `uv run pytest backend/tests/unit/core/schema_change/` | 2026-11-17T18:18:56Z | n/a | `125 passed, 4 xfailed` |
| `backend/tests/unit/test_exceptions.py::test_error_pickle_round_trip[schema_operation_target_not_found]`, `::test_schema_operation_target_not_found_names_the_operation_and_the_target[missing_kind\|missing_attribute\|missing_relationship]` | unit | `uv run invoke backend.test-unit` | 2026-11-17T18:19:48Z | n/a | `5439 passed, 4 xfailed, 3 warnings in 282.80s` |
| `test_equivalence_helpers.py::test_direct_load_of_the_base_schema_file_changes_nothing`, `::test_comparison_names_the_kind_whose_hash_differs` | unit | `uv run pytest backend/tests/unit/core/schema_change/` | 2026-11-17T18:18:56Z | n/a | `125 passed, 4 xfailed` |
| `test_applier_equivalence.py::test_applied_operations_give_the_direct_load_result[7 cases]` | unit | same | 2026-11-17T18:18:56Z | n/a | `125 passed, 4 xfailed` |
| `test_applier_equivalence_relationships.py::test_applied_relationship_operations_give_the_direct_load_result[7 cases]` | unit | same | 2026-11-17T18:18:56Z | n/a | `125 passed, 4 xfailed` |
| `test_applier_equivalence_kinds.py::test_applied_kind_operations_give_the_direct_load_result[4 cases]` | unit | same | 2026-11-17T18:18:56Z | n/a | `125 passed, 4 xfailed` |
| `test_applier_equivalence_fields.py::test_applied_field_operations_give_the_direct_load_result[16 cases, including absent_node_with_absent_attribute]` | unit | `uv run pytest backend/tests/unit/core/schema_change/test_applier_equivalence_fields.py -k absent_node` (new case), then the directory | 2026-11-17T18:01:16Z (new case), 18:18:56Z (directory) | n/a | `1 passed`; `125 passed, 4 xfailed` |
| `test_applier_equivalence_fields.py::TestNumberPoolParametersEquivalence::test_applied_number_pool_operations_give_the_direct_load_result[3 cases]`, `::TestInheritedAttributeOverrideEquivalence::test_removed_override_gives_the_direct_load_result` | unit | `uv run pytest backend/tests/unit/core/schema_change/` | 2026-11-17T18:18:56Z | n/a | `125 passed, 4 xfailed` |
| `test_applier_known_bugs.py::test_a_relationship_changed_to_component_keeps_the_on_delete_of_the_file` | unit | same | 2026-11-17T18:18:56Z | n/a | `125 passed, 4 xfailed` |
| `test_applier_known_bugs.py`: `test_turning_unique_off_removes_the_calculated_uniqueness_constraint`, `test_a_relationship_changed_to_component_without_on_delete_cascades`, `test_a_rename_on_a_generic_migrates_the_profiles_of_the_inheriting_kinds`, `test_an_attribute_kind_change_on_a_generic_alone_reaches_the_inheriting_kinds` | unit (strict xfail) | same | 2026-11-17T18:18:56Z | n/a | `XFAIL` ×4 (in `125 passed, 4 xfailed`) |
| `test_operation_builder.py` (12 tests, including the modified `TestOperationsOfAFileWithEveryOperationType::test_operations_come_in_a_fixed_order_whatever_the_order_of_the_file`) | unit | `uv run pytest backend/tests/unit/core/schema_change/test_operation_builder.py` | 2026-11-17T18:03:25Z | n/a | `12 passed` |
| `test_applier.py` (11 tests: `test_an_operation_on_a_missing_target_is_refused[6 cases]`, `test_an_element_removed_by_an_earlier_operation_is_missing_for_a_later_one`, `test_apply_leaves_the_target_schema_unchanged`, `test_properties_that_no_operation_names_keep_their_value`, `test_the_same_target_and_operations_give_the_same_hash`, `test_the_shared_schema_is_unchanged_after_the_module`) | unit | `uv run pytest backend/tests/unit/core/schema_change/` | 2026-11-17T18:18:56Z | n/a | `125 passed, 4 xfailed` |
| `test_applier_changed_target.py::test_an_attribute_added_to_a_generic_reaches_a_kind_that_the_target_gained`, `::test_a_label_change_keeps_a_change_that_the_target_made_to_the_same_kind` | unit | same | 2026-11-17T18:18:56Z | n/a | `125 passed, 4 xfailed` |
| `test_candidate.py` (7 tests, including `test_a_schema_file_gives_the_processed_schema_of_the_file_without_applying_its_operations` and `test_operations_are_applied_once_and_not_checked`) | unit | same | 2026-11-17T18:18:56Z | n/a | `125 passed, 4 xfailed` |
| `test_candidate_comparer.py` (5 tests, including `test_a_kind_that_cannot_be_parsed_again_is_returned`) | unit | same | 2026-11-17T18:18:56Z | n/a | `125 passed, 4 xfailed` |
| `test_operations_check.py` (5 tests, including `test_the_replay_check_accepts_a_file_that_gives_an_existing_kind_an_unknown_id`) | unit | `uv run pytest backend/tests/unit/core/schema_change/test_operations_check.py` | 2026-11-17T18:08:45Z | n/a | `5 passed` |
| `test_migration_recorder.py` (unit, including `test_register_logs_a_failure_to_create_the_records_and_does_not_raise[query_error_when_the_application_is_missing]`) and `test_application_runner.py` (6 tests, including `test_run_returns_the_hash_and_logs_when_recording_the_application_fails` and `test_run_applies_a_candidate_without_operations_without_recording_it_and_logs_a_warning`) | unit | `uv run pytest backend/tests/unit/core/schema_change/test_application_runner.py` | 2026-11-17T18:15:15Z | n/a | `6 passed` |
| `backend/tests/unit/core/migrations/schema/test_tasks.py`: the two modified `split_migrations_by_phase` tests and `test_split_keeps_the_position_of_each_migration_in_the_message` | unit | `uv run invoke backend.test-unit` | 2026-11-17T18:19:48Z | n/a | `5439 passed, 4 xfailed, 3 warnings in 282.80s` |
| `backend/tests/benchmark/test_schema_candidate_builder.py::test_direct_load_of_device_schema`, `::test_candidate_of_device_schema` | unit (benchmark) | `INFRAHUB_LOG_LEVEL=CRITICAL uv run pytest backend/tests/benchmark/test_schema_candidate_builder.py --dist=no -p no:randomly` | 2026-11-17T15:16:10Z | n/a, no Docker running | `2 passed` |

### Component tests

| Test id | Type | Run command | Passed at | Environment | Verbatim pass line |
| --- | --- | --- | --- | --- | --- |
| `backend/tests/component/core/schema_change/test_repository.py` (5), `test_history_reader.py::TestSchemaChangeHistoryReader` (6), `test_version_resolver.py::TestSchemaChangeVersionResolver` (7), `test_recorder.py` (8), `test_migration_recorder.py` (7, including `test_recorder_of_a_missing_application_creates_no_record_and_does_not_raise`), `test_delete_by_branch.py::TestDeleteSchemaChangesByBranch` (4) | integration (component) | `uv run pytest backend/tests/component/core/schema_change/` | 2026-11-17T18:24:45Z | testcontainers Neo4j | `37 passed` |
| `backend/tests/component/graphql/queries/test_schema_change.py` (13), `backend/tests/component/graphql/mutations/test_schema_dropdown_and_enum_history.py::TestDropdownAndEnumMutationHistory` (9), `backend/tests/component/graphql/mutations/test_schema.py` (14; modified: `test_add_enum_option_success`, `test_remove_enum_option_success`, `test_add_dropdown_option_does_not_corrupt_schema_cache`) | integration (component) | `uv run pytest` on the three modules | 2026-11-17T18:25:17Z | testcontainers Neo4j | `36 passed in 63.50s` |
| `backend/tests/component/core/constraint_validators/test_number_pool_scope.py`, `test_number_pool_rename.py`, `backend/tests/component/pools/test_schema_number_pool_scope.py` (the five changed calls) | integration (component) | `uv run pytest` on the three modules | 2026-11-17T15:20:23Z | testcontainers Neo4j | `25 passed, 1 warning in 146.67s` |
| `backend/tests/component/core/migrations/schema/test_models.py::test_SchemaApplyMigrationData_serializer` | integration (component) | `uv run pytest backend/tests/component/core/migrations/schema/test_models.py -q -p no:randomly` | 2026-11-17T14:43:40Z | testcontainers Neo4j | `1 passed, 1 warning` |
| `backend/tests/component/core/schema_manager/test_schema_rollback.py` (two changed calls of `execute`) | integration (component) | `uv run pytest backend/tests/component/core/schema_manager/test_schema_rollback.py -q -p no:randomly` | 2026-11-17T14:39:03Z | testcontainers Neo4j | `2 passed, 1 warning in 98.52s` |
| `backend/tests/component/api/test_40_schema.py` (regression for the load and the check) | integration (component) | `uv run pytest backend/tests/component/api/test_40_schema.py` | 2026-11-17T18:26:30Z | testcontainers Neo4j | `30 passed, 2 warnings in 111.65s` |

### Functional and Docker integration tests

| Test id | Type | Run command | Passed at | Environment | Verbatim pass line |
| --- | --- | --- | --- | --- | --- |
| `backend/tests/functional/schema_change/test_schema_change_history.py::TestSchemaChangeHistory` (`test_step01_` to `test_step19_`), `test_schema_change_records_untouched.py::TestSchemaChangeRecordsUntouched` (3 steps) | e2e (functional) | `uv run pytest backend/tests/functional/schema_change/` | 2026-11-17T18:28:38Z | testcontainers Neo4j | `22 passed in 143.67s` |
| `backend/tests/functional/api/test_load_schema.py::TestLoadSchemaAPI::test_schema_load_with_absent_schema` (regression; failed under the replay check before fix 4) | e2e (functional) | `uv run pytest backend/tests/functional/schemas/ backend/tests/functional/api/test_load_schema.py` | 2026-11-17T18:31:13Z | testcontainers Neo4j | `26 passed in 228.95s` |
| `backend/tests/integration/schema_lifecycle/test_schema_load_fake_id.py::…::test_reload_with_fake_id_for_existing_schema_is_rejected` (regression; failed under the replay check before fix 5) and the rest of `schema_lifecycle` | integration | `uv run pytest backend/tests/integration/schema_lifecycle/ -n 4` | 2026-11-17T18:35:14Z | testcontainers Neo4j, 4 xdist workers | `280 passed, 17 warnings in 663.60s` |
| `backend/tests/integration_docker/test_schema_migration.py::TestSchemaMigrations::test_schema_load_and_delete` (assertion added) | e2e (Docker stack with task workers) | `INFRAHUB_TESTING_IMAGE_VER=local-ifc3614 INFRAHUB_TESTING_DOCKER_PULL=false uv run pytest backend/tests/integration_docker/test_schema_migration.py`, after `INFRAHUB_IMAGE_VER=local-ifc3614 uv run invoke dev.build` | 2026-11-17T17:08:41Z | local Docker stack, image `local-ifc3614` built after the last backend source change of chunk 20. The review fixes came after this run, and this test was not run again. | `2 passed, 1 xfailed` (the xfail, `test_update_schema`, is on the base commit) |

## 5. Review findings

Review mode: command (/code-review)

The review ran at effort level `high` over `78e6a0c1b1..HEAD` (98 files). Its ten findings are listed
with the two failures that the test-only replay check found in chunk 20 (A and B).

| # | Severity | File | Summary | Handling |
| --- | --- | --- | --- | --- |
| 1 | high | `backend/infrahub/core/schema_change/application_runner.py:106` | `complete` ran outside the `try`, so a failed record write after a successful update returned a 500 and skipped the hash refresh and the event | Fixed in `5801f3b409`: the error is logged, the load returns the hash, and the record stays `running` |
| 2 | high | `backend/infrahub/api/schema.py:466` | A load whose diff is not empty but gives no operation failed in `recorder.start` | Fixed in `00d55f8849`: the runner applies it with no application ID, stores no record and logs a warning |
| 3 | high | `backend/infrahub/core/schema_change/application_migration_recorder.py:20` | `QueryError` was not caught, so a missing application stopped the migration flow | Fixed in `c37ebabeec`: the runner and the migration recorder catch one shared set of errors, `RECORD_WRITE_ERRORS` |
| A | high | `backend/infrahub/core/schema_change/operation_builder.py` | `state: absent` on a node that also marks elements absent: the operations did not rebuild the loaded schema | Fixed in `d45772b250`, with a new equivalence case |
| B | high (tests only) | `backend/tests/helpers/schema_change.py` | The replay check raised before the load was refused, for a file that gives an existing kind an unknown ID | Fixed in `9f4a728516`: the check skips that case; production is unchanged |
| 4 | medium | `backend/infrahub/core/migrations/schema/tasks.py:243` | After an early return or a raised migration, records stay `waiting` or `running` | Deferred: spec decision 6 keeps those statuses on a failed application |
| 5 | medium | `backend/infrahub/core/migrations/schema/tasks.py:188` | `batch_started` marks a whole batch `running` although only 5 (or 1) run at a time | Deferred: T036 specifies this behaviour |
| 6 | medium | `backend/infrahub/graphql/mutations/schema.py:107` | The new list is calculated before the lock, so two concurrent mutations lose an update and store a misleading operation | Deferred: the lost update is on the base commit; only the stored operation is new |
| 7 | low | `backend/infrahub/core/query/schema_change.py:107` | A docstring named another class | Fixed in `897e0b5307` |
| 8 | low | `backend/infrahub/core/schema_change/constants.py:4` | `constants.py` held enumeration classes, against `.agents/rules/python-module-layout.md` | Fixed in `71ccf91104`: the enumerations are in `enums.py` |
| 9 | low | `backend/infrahub/core/query/schema_change.py:544` | Two highest-version queries are near copies | Deferred |
| 10 | low | `backend/infrahub/api/schema.py:506` | The schema check builds operations that it does not use | Deferred: the user said schema load time is not critical |

## 6. Autonomous decisions

- **Chunks.** Phase 3 (17 tasks) was split into five chunks, phase 4 into six, and phase 8 into
  three. The test-first chunks reported their tests as failing for the expected reason, and the
  implementing chunk supplied the pass evidence.
- **GraphQL gate.** The user accepted the contract at the start of the run.
- **Single-pass schema load (T065).** The user asked why a candidate took twice as long as a direct
  load. A read-only investigation measured `process` (218 ms) and `diff` (50 ms) running twice. The
  report is at
  `/tmp/claude-1000/-home-ubuntu-orca-workspaces-infrahub-ifc-3614-store-migrations/a50a3157-f8e6-4eff-9f77-f40da5c92ac7/scratchpad/perf/report.md`.
  The user decided that a schema file load uses the processed schema the operation builder already
  holds, and accepted the risk that the stored operations may not rebuild the saved schema. The
  orchestrator chose to keep that check in the test suites only, set through a new field
  `config.Override.schema_operations_check`, with no setting or environment variable. The check
  found two failures in chunk 20 (A and B above).
- **Spec documents changed during the run.** Chunks changed spec, research, plan, data model and
  contracts where the code differed (listed in §2). `alignment-check.md`, a dated snapshot, received
  one line that names the decision that supersedes one of its bullets.
- **Review triage.** Findings 4, 5, 6, 9 and 10 are deferred for the reasons in §5.
- **T063.** Quickstart section 6, which needs a running instance, was checked against the code and
  against `integration_docker/test_schema_migration.py`, not run.
- **Changelog fragment and user documentation dropped.** After the run, the user decided to drop
  the changelog fragment (T058) and the user documentation (T059), because they would not be
  accurate once the epic is complete. `changelog/+schema-change-history.added.md` and the section
  of `docs/docs/schema/create-and-load.mdx` were removed, and `tasks.md`, `plan.md` and research
  R15 say so. The internal knowledge document (T060) is kept.

## 7. Suggested next steps

1. Run `/pre-ci` for the backend, docs and frontend areas before pushing.
2. Decide the deferred findings 4, 5 and 6, and whether the deleter should bound the size of one
   transaction for a schema change with many operations (research R13).
3. Decide whether migration positions should be stable between runs. Today they follow the order
   of a set in the schema diff (research R9).
4. Write the changelog fragment and the user documentation of the history query when the epic is
   complete.
5. Remove the local Docker image `registry.opsmill.io/opsmill/infrahub:local-ifc3614`.
6. Open a pull request.
