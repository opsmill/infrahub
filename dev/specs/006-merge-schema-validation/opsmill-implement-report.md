# Implementation report: schema validation at merge and rebase (first pull request)

- Feature: validate schema changes against both branches at merge and rebase
- Spec directory: `dev/specs/006-merge-schema-validation`
- Scope: tasks T001–T038 (phases 1–8, the first pull request). Phase 9 (T039–T041) is the second pull request and
  was not run.
- Base commit: `83cada8fc`
- Head commit before this report: `3cd80edf8` (22 commits)
- Wall-clock time: about 6 hours 15 minutes (2026-11-03, 03:58Z to 10:15Z)
- Status: DONE. All T001–T038 are ticked, and every test that was added or changed has local-pass evidence.
- Commit IDs in this report refer to the local branch `merge-schema-validation`, which was later split into three
  stacked pull requests (see "Decisions after the run").

## Chunk ledger

| # | Chunk | Tasks | Done / partial / blocked | Commits | Points raised |
|---|---|---|---|---|---|
| 1 | Phase 1: Setup | T001–T002 | 2 / 0 / 0 | `e37a7fb31` | The orchestrator ran T001 itself, because it only prepares the environment. T002 (load the guidelines) was added to every later subagent brief. |
| 2 | Phase 2: view option | T003–T008 | 6 / 0 / 0 | `4a13d9278` | Three other places that build `SchemaValidateMigrationData` got `is_isolated=True` as placeholders until T019, T021 and T031 replaced them. |
| 3 | Phase 2: merged schema | T009–T010 | 2 / 0 / 0 | `982dfb199` | New method `SchemaBranch.apply_changes_since(base, schema)` and new exception `SchemaDiffApplyError`. |
| 4 | Phase 2: analyzer | T011–T012 | 2 / 0 / 0 | `1a427812f` | Gate method `has_schema_changes_on_either_branch()`. `get_candidate_schema` is async, and its two callers await it. |
| 5 | Phase 3: validator queries | T013–T015, T017, T018 | 5 / 0 / 0 | `123eba6ef` | The `EXPLAIN` plan for the new query matches the plan of the existing optional query once statistics exist. |
| 6 | Phase 3: wiring and integration | T016, T019–T022 | 5 / 0 / 0 | `97500c278`, `c9eed3ab8` | Added one rebase test outside the task list, because no T016 test failed with T021 reverted. |
| 7 | Phase 4: user story 2 | T023–T026 | 4 / 0 / 0 | `5a3e94585` | T025 answer was no: the worker did not reload either branch's schema before the checks. The analyzer now reloads both. `plan.md` and research R4 were updated. No test can tell the rebase gate from the old flag after that reload. |
| 8 | Phase 5: accepted merges | T027–T028 | 2 / 0 / 0 | `a5cadacba` | None. |
| 9 | Phase 6: proposed change | T030–T031 | 2 / 0 / 0 | `55addbd0d` | The schema integrity check now uses the analyzer and sends `is_isolated=False`. |
| 10 | Phase 7: suspected gaps | T032–T033 | 2 / 0 / 0 | `c52c325aa`, `149ce5bec` | Both gaps confirmed. The relationship check flagged every node of the kind; now fixed. The default-value gap is marked as a strict xfail, and a draft issue was written but not opened. |
| 11 | Phase 5: local matrix | T029 | 1 / 0 / 0 | `753ef7095`, `32fc43f94` | 49 of 51 runs as expected. R7 and R10 through the proposed change exposed an existing pipeline condition (see "Autonomous decisions"); marked as a strict xfail. |
| 12 | Phase 8: delivery | T034–T038 | 5 / 0 / 0 | `5ef2fcbbe`, `ec1d424f6`, `1ea4535d9` | `invoke lint` reports 130 `ty` unresolved-import errors in files outside this feature. They come from the local editable install of `python_sdk`. The pull request description was written to a local file; no pull request was opened. |
| R-A | Review fixes: code | review findings | 4 fixed, 1 explained | `ab0540eed`, `eed93ed15`, `fb780fdf4` | See "Review findings". |
| R-B | Review fixes: tests and docs | review findings | 12 fixed | `a3a6f3b85`, `3cd80edf8` | A possible bug outside this feature: when both branches remove the same attribute, the merge fails in the schema migrations and is rolled back. |

## Tasks not completed

None in scope. T039–T041 (phase 9, second pull request) are still open, as planned.

## Local-pass evidence

All runs were on 2026-11-03, from `backend/`, on Linux with Python 3.14. Component and integration tests used
testcontainers with `neo4j:2026.05.0-enterprise`. Each time is the last passing run on the code the test now covers.

| Test id | Type | Run command | Passed at | Environment context | Verbatim pass line |
|---|---|---|---|---|---|
| `tests/component/core/constraint_validators/test_models.py::test_schema_validate_migrations` | component | `uv run pytest tests/component/core/constraint_validators/test_models.py tests/component/core/constraint_validators/test_task_schema_validate_migrations.py -q -rA` | 2026-11-03T04:08:47Z | testcontainers Neo4j | `PASSED tests/component/core/constraint_validators/test_models.py::test_schema_validate_migrations` |
| `tests/component/core/constraint_validators/test_task_schema_validate_migrations.py::test_schema_validate_migrations` | component | same as above | 2026-11-03T04:08:47Z | testcontainers Neo4j | `PASSED tests/component/core/constraint_validators/test_task_schema_validate_migrations.py::test_schema_validate_migrations` |
| `tests/unit/core/schema/test_schema_branch.py::TestApplyChangesSince` (14 tests: `test_keeps_a_property_changed_on_the_destination_only`, `test_keeps_a_kind_changed_on_the_destination_only`, `test_rebuilds_an_attribute_whose_kind_changed_on_the_source`, `test_applies_the_value_of_the_source_when_both_branches_change_a_property`, `test_keeps_the_attributes_added_on_either_branch`, `test_leaves_out_an_attribute_removed_on_the_destination_and_unchanged_on_the_source`, `test_leaves_out_a_kind_removed_on_the_destination_and_unchanged_on_the_source`, `test_follows_an_attribute_renamed_on_the_destination`, `test_keeps_the_change_the_destination_made_to_an_inherited_attribute`, `test_applies_the_change_of_a_node_to_its_profile_kind`, `test_keeps_the_source_version_of_an_attribute_removed_on_the_destination_and_changed_on_the_source`, `test_keeps_the_source_version_of_a_kind_removed_on_the_destination_and_changed_on_the_source`, `test_lists_the_nodes_both_branches_added_in_the_used_by_of_a_generic`, `test_leaves_out_of_the_used_by_of_a_generic_the_nodes_either_branch_removed`) | unit | `uv run pytest tests/unit/core/schema/test_schema_branch.py -q -rA -p no:randomly` | 2026-11-03T10:12:35Z | n/a | `PASSED tests/unit/core/schema/test_schema_branch.py::TestApplyChangesSince::<name>` for each of the 14; `30 passed, 17 warnings in 15.37s` |
| `tests/component/core/test_branch_merge.py::test_merge_validations_include_the_validators_of_the_schema_migrations_of_both_branches` | component | `uv run pytest tests/component/core/test_branch_merge.py -n 4 -p no:cacheprovider -rA` | 2026-11-03T09:17:33Z | testcontainers Neo4j | `10 passed` (suite summary of run 09:14:28Z–09:17:33Z) |
| `tests/component/core/test_branch_merge.py::test_schema_change_gate_opens_when_only_the_default_branch_changed_the_schema` | component | same as above | 2026-11-03T09:17:33Z | testcontainers Neo4j | `10 passed` (suite summary) |
| `tests/component/core/test_branch_merge.py::test_schema_analyzer_loads_a_default_branch_schema_that_the_registry_has_not_loaded_yet` | component | same as above | 2026-11-03T09:17:33Z | testcontainers Neo4j | `10 passed` (suite summary) |
| `tests/component/core/test_branch_merge.py::test_merge_of_data_changes_without_schema_changes_checks_no_schema_constraint` | component | same as above | 2026-11-03T09:17:33Z | testcontainers Neo4j | `10 passed` (suite summary) |
| `tests/component/core/test_branch_merge.py::test_merge_checks_an_attribute_the_default_branch_removed_and_the_branch_changed` | component | same as above | 2026-11-03T09:17:33Z | testcontainers Neo4j | `PASSED tests/component/core/test_branch_merge.py::test_merge_checks_an_attribute_the_default_branch_removed_and_the_branch_changed` |
| `tests/component/core/constraint_validators/test_attribute_optional.py::test_validator_on_branch_reads_the_requested_view_of_main[branch-view]` and `[merge-view]` | component | `uv run pytest tests/component/core/constraint_validators/test_attribute_optional.py -n 4` | 2026-11-03T10:11:11Z | testcontainers Neo4j | `11 passed` (file summary); individually `PASSED ...[branch-view]`, `PASSED ...[merge-view]` at 04:33:57Z |
| `tests/component/core/constraint_validators/test_attribute_optional.py::test_validator_in_merge_view_skips_a_node_from_main_that_the_branch_deleted` | component | same as above | 2026-11-03T10:11:11Z | testcontainers Neo4j | `11 passed` (file summary) |
| `tests/component/core/constraint_validators/test_attribute_kind_update.py::test_validator_on_branch_reads_the_requested_view_of_main[branch-view]` and `[merge-view]` | component | `uv run pytest tests/component/core/constraint_validators -n 4 -p no:cacheprovider -rA` | 2026-11-03T09:24:30Z | testcontainers Neo4j | `476 passed, 6 skipped` (suite summary) |
| `tests/component/core/constraint_validators/test_node_attribute_add.py` (`test_query_finds_every_node_before_the_attribute_exists`, `test_query_on_branch_skips_nodes_with_a_value_and_deleted_nodes`, `test_validator_on_branch_reads_the_requested_view_of_main[branch-view]` and `[merge-view]`) | component | same as above | 2026-11-03T09:24:30Z | testcontainers Neo4j | `476 passed, 6 skipped` (suite summary) |
| `tests/component/core/constraint_validators/test_node_attribute_add.py::test_number_pool_size_is_checked_against_the_nodes_of_the_requested_view_of_main[branch-view]` and `[merge-view]` | component | same as above | 2026-11-03T09:24:30Z | testcontainers Neo4j | `PASSED tests/component/core/constraint_validators/test_node_attribute_add.py::test_number_pool_size_is_checked_against_the_nodes_of_the_requested_view_of_main[merge-view]` |
| `tests/component/core/constraint_validators/test_node_relationship_add.py` (`test_check_accepts_branch_nodes_that_set_the_new_relationship[branch-view]` and `[merge-view]`, `test_check_on_branch_flags_nodes_without_the_relationship_in_the_requested_view_of_main[branch-view]` and `[merge-view]`) | component | same as above | 2026-11-03T09:24:30Z | testcontainers Neo4j | `476 passed, 6 skipped` (suite summary); individually `PASSED` at 06:41:16Z |
| `tests/component/message_bus/operations/requests/test_proposed_change.py::test_schema_integrity_checks_the_branch_data_against_the_default_branch_schema_changes` | component | `uv run pytest tests/component/message_bus/operations/requests/test_proposed_change.py -n 4 -p no:cacheprovider -rA` | after 2026-11-03T09:24:30Z (run 9:24–9:30) | testcontainers Neo4j | `5 passed in 75.67s` (file summary) |
| `tests/component/message_bus/operations/requests/test_proposed_change.py::test_schema_integrity_checks_the_default_branch_data_against_the_branch_schema_changes` | component | same as above | same as above | testcontainers Neo4j | `5 passed in 75.67s` (file summary) |
| `tests/integration/schema_lifecycle/test_schema_validator_stored_data.py::TestSchemaChangeRefusedByStoredData` (17 passing tests: the merge and rebase refusals of user stories 1 and 2, the accepted merges, the unique-on-main refusals with retry, and the pool scoped by an attribute made optional) | integration | `uv run pytest tests/integration/schema_lifecycle/test_schema_validator_stored_data.py -rA` | 2026-11-03T09:58:05Z | testcontainers Neo4j | `17 passed, 1 xfailed` |
| `tests/integration/schema_lifecycle/test_schema_validator_stored_data.py::TestSchemaChangeRefusedByStoredData::test_merge_stores_the_default_value_of_an_attribute_added_on_main_on_the_nodes_of_the_branch` | integration (strict xfail) | same as above | 2026-11-03T09:58:05Z | testcontainers Neo4j | `XFAIL` (in `17 passed, 1 xfailed`) |
| `tests/integration/proposed_change/test_proposed_change_schema_integrity_recheck.py::TestProposedChangeSchemaIntegrityRecheck::test_schema_integrity_check_fails_for_a_node_on_the_branch_lacking_a_mandatory_attribute_added_on_main` | integration | `uv run pytest tests/integration/proposed_change/test_proposed_change_schema_integrity_recheck.py -rA` | 2026-11-03T10:08:25Z | testcontainers Neo4j, Prefect, Redis | `1 passed, 1 xfailed` |
| `tests/integration/proposed_change/test_proposed_change_schema_integrity_recheck.py::TestProposedChangeSchemaIntegrityRecheck::test_merge_is_accepted_after_the_branch_node_is_deleted_and_checks_run_again` | integration (strict xfail) | same as above | 2026-11-03T10:08:25Z | testcontainers Neo4j, Prefect, Redis | `XFAIL` (in `1 passed, 1 xfailed`) |
| `tests/integration_docker/test_schema_merge_validation.py` (5 tests: kind change refused at merge and at rebase in both directions; compliant data merges) | e2e (Docker stack) | `GIT_CONFIG_GLOBAL=/dev/null INFRAHUB_TESTING_IMAGE_VER=local-msv-t4 uv run pytest tests/integration_docker/test_schema_merge_validation.py` | 2026-11-03T10:05:07Z | image `registry.opsmill.io/opsmill/infrahub:local-msv-t4` built from this worktree; compose project `infrahub-test-<auto>`, torn down | `5 passed` |

Suite runs on the final code (from the review fixes): `tests/unit/core/schema` 345 passed; `test_branch_rebase.py` 12
passed; `tests/component/core/merge/` 45 passed; `tests/component/tasks/test_registry.py` with
`tests/component/core/migrations/schema/test_node_attribute_add.py` 26 passed. In chunk 12, before the review fixes:
`tests/unit/core` 1193 passed; `tests/integration/schema_lifecycle` and `tests/integration/proposed_change` 326 passed
and 2 xfailed.

## Review findings

The review ran six areas (code, tests, comments and docs, error handling, types, simplification) over
`83cada8fc..3cd80edf8` minus the fix commits.

| Severity | File | Finding | Status |
|---|---|---|---|
| High | `backend/infrahub/core/schema/schema_branch.py` | The merged schema kept the default branch's `used_by` for each generic, so a uniqueness check on a generic missed node kinds that the branch added | Fixed in `ab0540eed` |
| High | `backend/infrahub/core/schema/schema_branch.py`, `backend/infrahub/exceptions.py` | When the default branch removed an element that the branch changed, the merge and rebase failed with HTTP 500 instead of checking the branch's version, as the spec requires | Fixed in `ab0540eed` |
| High | `docs/docs/branches/merge.mdx`, `rebase.mdx` | The docs gave two fixes that do not work: adding a default value on the default branch (the default-value gap) and running the proposed change's checks again (the check does not run when the branch has no changes) | Fixed in `a3a6f3b85` |
| High | `backend/tests/integration/proposed_change/test_proposed_change_schema_integrity_recheck.py` | The assertion on the refusal sat in a fixture used only by an xfail test, so a regression would still report XFAIL | Fixed in `3cd80edf8` |
| High | `backend/tests/integration/schema_lifecycle/test_schema_validator_stored_data.py` | Three spec scenarios had no automated test: the number pool case, the unique-on-main case and a retry after a fix | Fixed in `3cd80edf8` |
| High (types) | `backend/infrahub/core/validators/attribute/{regex,enum,length,choices}.py` | These checks ignore `is_isolated` | Deferred: planned as T039–T041 (second pull request); the docs state the limit |
| Medium | `backend/infrahub/core/merge/schema_analyzer.py` | The schema reload bypassed the injected schema manager, did not hold the local schema lock, and could leave stale cached copies | Fixed in `eed93ed15` |
| Medium | `docs/docs/branches/*.mdx`, `docs/docs/proposed-changes/overview.mdx` | Mandatory relationship fix, scope of the regex, enum, length and choices checks, removed-versus-changed case | Fixed in `a3a6f3b85` |
| Medium | `backend/tests/component/core/constraint_validators/test_attribute_optional.py` | No merge-view test for a node deleted on the branch | Fixed in `3cd80edf8` |
| Medium | `backend/tests/component/core/test_branch_merge.py` | Unexplained `node.hierarchical.update CoreGroup` entry in the expected list | Explained: a test fixture loads `CoreGroup` without `hierarchical`; production loads it from the database |
| Medium (types) | `backend/infrahub/core/validators/shared.py` | The `is_isolated=True` default lets a checker that forgets to pass the flag read the branch view without an error | Deferred |
| Medium (simplify) | `graph_merger.py`, `proposed_change/tasks.py`, `branch/tasks.py` | The same gate check is written in three places; it could move into `calculate_validations` | Deferred |
| Medium (simplify) | `backend/infrahub/core/validators/query.py` | `NodeNotPresentValidatorQuery` and its test are no longer used by production code | Deferred |
| Low | `backend/infrahub/core/validators/node/attribute.py` | The size check for a new NumberPool attribute counted nodes in the branch view only | Fixed in `fb780fdf4` |
| Low | several docstrings | "when the branch was created" should say "or last rebased"; registry docstring | Fixed in `a3a6f3b85` |
| Low | `backend/tests/integration_docker/test_schema_merge_validation.py` | The accepted merge did not assert the response or the branch status | Fixed in `3cd80edf8` |
| Low | other simplification and type suggestions (shared Cypher block, keyword-only parameters, `Literal` element type, duplicate helpers) | | Deferred |

## Autonomous decisions

- The orchestrator ran T001 itself and put T002 in every subagent brief, because loading guidelines in a subagent
  that then exits has no effect.
- Phase 2 (10 tasks) was split into three chunks: view option, merged schema, analyzer. Phase 3 was split into the
  validator queries (T013–T015, T017, T018) and the wiring with the integration tests (T016, T019–T022), so T016
  ran after T017 and T018. T016 still failed before T019–T021.
- T029 (the local matrix) ran after phases 6 and 7 instead of in phase 5, so that it covered the final code of the
  first pull request, including the proposed-change change in T031.
- The `speckit-checkpoint-commit` skill is not available in this session; subagents committed with `git commit`.
- The six review areas were run in parallel, because they only read code.
- T025 changed production code: the analyzer reloads both branches' schemas before the checks. This was not in the
  original plan; `plan.md` and research R4 were updated.
- The review fix in `ab0540eed` changed `data-model.md`, research R5, `plan.md` and the T009 wording: the merged
  schema keeps the branch's version of an element that the default branch removed, and `SchemaDiffApplyError` now
  only covers an internal inconsistency. The proposed change no longer catches it.
- T033: the GitHub issue for the default-value gap was not opened. The draft is in the session scratchpad
  (`pr-notes/draft-issue-t033.md`).
- The existing pipeline condition found by the matrix (the proposed change runs Schema Integrity only when the branch
  has data changes) was recorded as a strict xfail and not changed. Changing it is a product decision: either always
  run the check, or clear an earlier failure.
- No E2E test was deferred. The Docker test ran locally on images built from this worktree. The images
  `local-msv-us2`, `local-msv-final` and `local-msv-t4` are still on the machine.

## Suggested next steps

1. Review the pull request description in the session scratchpad (`pr-notes/pr-description.md`), then open the pull
   request against `release-1.12`. Run `/pre-ci` first.
2. Decide on the proposed-change pipeline condition (Schema Integrity not run again when the branch has no data
   changes), and on opening the issue for the default-value gap.
3. Check whether the merge failure when both branches remove the same attribute predates this feature; if so, open
   an issue.
4. Consider the deferred review suggestions: remove the `is_isolated=True` default from `SchemaValidatorQuery`,
   move the gate into `calculate_validations`, delete `NodeNotPresentValidatorQuery`.
5. After the first pull request merges, run phase 9 (T039–T041).
6. Drop the stash `migration-validators-wip-2026-11-03` only after you confirm.

## Decisions after the run

The user made these decisions on 2026-11-03, after the report above was written.

1. Schema Integrity failure that stays after the fix: the pipeline keeps the condition on the branch's diff. When
   the condition skips the check, and when the check finds nothing to validate, Infrahub now replaces an earlier
   failure of the Schema Integrity validator with a passing result
   (`ObjectConflictValidatorRecorder.clear_failure`). The recheck integration test is no longer an xfail.
   `docs/docs/branches/merge.mdx` no longer suggests a direct merge as the workaround, and
   `changelog/+schema-integrity-stale-failure.fixed.md` records the fix.
2. Default value not stored at merge (T033): tracked in [IFC-3558](https://opsmill.atlassian.net/browse/IFC-3558),
   assigned to the user. The strict xfail stays.
3. Merge failure when the default branch removed an attribute and the branch changed the schema: reproduced on this
   branch and on the base commit `83cada8fc`, so it predates this feature. It also occurs when the branch only adds
   an unrelated node kind. Tracked in [IFC-3559](https://opsmill.atlassian.net/browse/IFC-3559), assigned to the
   user. The two strict xfails that reproduce it
   (`backend/tests/integration/schema_lifecycle/test_merge_attribute_removed_on_both_branches.py`) are kept on the
   local branch `ifc-3559-merge-attribute-removed-tests`, for the pull request that fixes IFC-3559.
4. The schema reload before the checks (T025) and the merged schema keeping the branch's version of an element that
   the default branch removed both stay, in `merge-schema-validation-2-merge-checks` (see item 5).
5. The work of T001–T038 is split into three stacked pull requests:
   - `merge-schema-validation-1-validators`: the validators read the requested view of the default branch, the
     merged schema builder, and the check of a new mandatory relationship. Merge, rebase and the proposed change
     still read the branch's view.
   - `merge-schema-validation-2-merge-checks`: merge, rebase and the proposed change check schema changes from
     either branch against the merged data.
   - `merge-schema-validation-3-stale-schema-integrity`: the replacement of an earlier Schema Integrity failure
     (decision 1).
