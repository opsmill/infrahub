# Implementation ledger: ifc-2167-placeholder-automations

## Chunk: Phase 1: Setup

| Task | Outcome | Reason when not done |
|------|---------|----------------------|
| T001 | ✅ done | |
| T002 | ✅ done | |

Decisions worth flagging: T001 read the named sections of `display-labels-and-hfid.md`, `computed-attributes.md` and `events.md` in full, and the sections of `query-pattern.md`, `database-schema.md` and `testing.md` that apply to later tasks (query lifecycle and naming, parameter binding, return labels, the `Branch` vertex, test tiers, the Prefect test servers and swapping the workflow adapter for a test double). `backend/tests/component/hfid/` did not exist before; the other parent packages already had an `__init__.py`.
Lint and format: `uv run ruff check` and `uv run ruff format --check` on the four new packages passed ("All checks passed!", "4 files already formatted"). The four packages import through `uv run python -c "import ..."` ("imports ok").

No new or modified tests in this chunk.

## Chunk: Phase 2: Foundational (fingerprint store, collector and decision)

| Task | Outcome | Reason when not done |
|------|---------|----------------------|
| T003 | ✅ done | |
| T004 | ✅ done | |
| T005 | ✅ done | |
| T006 | ✅ done | |
| T007 | ✅ done | |
| T008 | ✅ done | |
| T009 | ✅ done | |
| T010 | ✅ done | |

Decisions worth flagging:

- The decision function is `decide_fingerprint_changes` in `core/template_fingerprint/decision.py`. It returns `to_recompute` and `to_record` sorted by kind.
- The read query filters on `family` and returns only `branch`, `kind` and `fingerprint`, as the contract states. The repository builds each `RecordedFingerprint` with the `TemplateFamily` it was called with, so a vertex whose `family` is not a `TemplateFamily` value is never returned. T008 asked for an explicit skip of such a record: after a filter on a `TemplateFamily` value that check cannot trigger, so it was not written.
- The read query orders by `branch, kind`, because `Query.execute` reads a READ query in pages of `query_size_limit` rows.
- `insert_missing` counts the created vertices in Cypher: each entry carries a fresh uuid, and `sum(CASE WHEN f.uuid = r.uuid ...)` counts the vertices that hold it after the `MERGE`. Query statistics were not used, because a counter that is zero may be missing from them. The repository removes duplicate keys from its input so that a key is not counted twice.
- The delete-branch Query class takes `branch_name` rather than `branch`, because `branch` is a parameter of the `Query` base constructor.
- The collector has two functions: `fingerprints_from_schema_branches(family, schema_branches)` computes the fingerprints without reading the registry, and `collect_schema_fingerprints(family)` reads `registry.default_branch`, `registry.get_altered_schema_branches()` and `registry.schema.get_schema_branch()` and calls it. The unit tests replace `registry.branch` and `registry._schema` with `monkeypatch`.
- T009 asked to reuse existing schema fixtures. The tests build `DisplayLabels` and `HFIDs` directly instead, because no existing fixture builds a processed `SchemaBranch` without a database. The comparison with the trigger definitions uses the peer automation of `TestPerson`, which carries the `TestCar` hash and stays after T020 removes the placeholder definitions. The test reads the refreshed kind from the automation name, because `target_kind` is `None` on peer definitions.
- The md5 values in `test_collector.py` are pinned literals: a change of the hashing would make the first schema update after an upgrade recompute every kind.
- To check that the empty-list test can fail, the early return of `delete` was removed and the test was run. It failed with `assert 1 == 0`, then the early return was put back.

Lint and format: `uv run ruff format` (1 file reformatted) and `uv run ruff check --fix` ("All checks passed!") on the new modules and tests. `uv run ty check` on the same paths printed "All checks passed!". `uv run mypy` on the same files printed "Success: no issues found in 10 source files". The full `uv run invoke lint` and `uv run invoke backend.mypy` were not run in this chunk (T040 runs them).

| Test id | Type (unit/integration/e2e) | Run command | Passed at (ISO 8601) | Environment context | Verbatim pass line |
|---------|-----------------------------|-------------|----------------------|---------------------|--------------------|
| backend/tests/unit/core/template_fingerprint/test_decision.py (12 tests) | unit | `cd backend && uv run pytest tests/unit/core/template_fingerprint/ tests/component/core/template_fingerprint/ -v` | 2026-11-19T14:49:57Z | macOS, Python 3.14 | `======================= 25 passed, 17 warnings in 17.39s =======================` |
| backend/tests/unit/core/template_fingerprint/test_collector.py (6 tests) | unit | same command | 2026-11-19T14:49:57Z | macOS, Python 3.14 | `======================= 25 passed, 17 warnings in 17.39s =======================` |
| backend/tests/component/core/template_fingerprint/test_repository.py (7 tests) | integration (component, Neo4j) | same command | 2026-11-19T14:49:57Z | Neo4j started by testcontainers through the local Docker daemon | `======================= 25 passed, 17 warnings in 17.39s =======================` |

## Chunk: Phase 3: User Story 1 - Keep the task manager free of automations that never run (Priority: P1), Jinja2 computed attributes

| Task | Outcome | Reason when not done |
|------|---------|----------------------|
| T011 | ✅ done | |
| T012 | ✅ done | |
| T013 | ✅ done | |
| T014 | ✅ done | |
| T015 | ✅ done | |
| T016 | ✅ done | |

Decisions worth flagging:

- T011: `test_gather_trigger_computed_attribute_jinja2_only_main` became `..._skips_template_reading_only_its_node` (the `car_person_schema_computed_attr` template reads only its own node, so the gather now returns an empty list). The branch test keeps only the `TestPerson` peer automation, and asserts its field filter `["name", "owner"]`, which is what the gather produced before this change for that peer.
- T013: the new cases are in `TestScopedRecomputeJinja2`: a `BranchDeletedEvent` run, a branch that does not own its schema (`same-schema`), and a branch that loads the same schema with another `local_tag` template (`diverging-tag`). The diverging case covers scenarios 5 and 6 in one run: `local_label` and `remote_label` have the default branch template and are not submitted, `local_tag` is submitted on that branch only. These cases passed on the code before T015 too; they pin the submissions that T015 must keep (FR-012). The two `changed_elements` cases already existed (`JINJA2_CASES`) and were kept.
- T015: the default-branch comparison is `_has_default_branch_template` in `computed_attribute/tasks.py`. It returns false when the default branch lacks the kind, the attribute or its computed attribute, so the attribute is submitted, as before when the default branch had no automation for it. A `BranchDeletedEvent` now empties the candidate list after scoping instead of being checked inside the submission loop; the submissions are the same.
- T016 is in `TestPlaceholderRemoval` and uses the `COLOR`/`TSHIRT` schema (a template that reads its own node and a peer). It creates the previous-release state with `setup_triggers` (peer automation + placeholder built with `TRIGGER_PLACEHOLDER_FIELD`), runs the setup flow, and asserts that only the peer automation remains and that `description` is submitted once.
- Bite checks: T011 and T012 failed on the code before T014 (3 failures, run at 2026-11-19 around 14:58Z). T016 was run with the previous `gather.py` restored from git: it failed with the placeholder automation `computed_attr_jinja2::main::TestingTShirt_description::kind::TestingTShirt` still present, then `gather.py` was restored.
- A WIP commit was made before the bite check (to protect the work); `git reset --soft` needed an approval that nobody could give in this run, so the checkpoint commit amends or follows it.

Lint and format: `uv run ruff format` (1 file reformatted) and `uv run ruff check --fix` ("All checks passed!") on the 6 changed files. `uv run ty check` on the same files: "All checks passed!". `uv run mypy` on `computed_attribute/gather.py`, `computed_attribute/tasks.py`, `test_scoped_recompute_jinja2.py` and `test_placeholder_removal.py`: "Success: no issues found in 4 source files". `uv run mypy tests/component/computed_attribute/test_gather.py` reports 6 `union-attr`/`attr-defined` errors on lines this chunk did not change (212, 258, 287, 337, 516, 563); the full `uv run invoke backend.mypy` with the project configuration runs in T040.

| Test id | Type (unit/integration/e2e) | Run command | Passed at (ISO 8601) | Environment context | Verbatim pass line |
|---------|-----------------------------|-------------|----------------------|---------------------|--------------------|
| backend/tests/component/computed_attribute/test_gather.py (jinja2 tests modified) | integration (component, Neo4j) | `cd backend && uv run pytest tests/component/computed_attribute/ tests/functional/computed_attributes/test_local_computation.py -q` | 2026-11-19T15:15:31Z | Neo4j and Prefect test server started by testcontainers through the local Docker daemon, macOS, Python 3.14 | `================= 70 passed, 17 warnings in 662.21s (0:11:02) ==================` |
| backend/tests/functional/computed_attributes/test_local_computation.py::TestJinja2ComputedAttributeWithRelationship (2 tests modified) | integration (functional) | same command | 2026-11-19T15:15:31Z | same | `================= 70 passed, 17 warnings in 662.21s (0:11:02) ==================` |
| backend/tests/component/computed_attribute/test_placeholder_removal.py::TestPlaceholderRemoval::test_setup_deletes_placeholder_and_keeps_peer_automation | integration (component, Prefect test server) | same command | 2026-11-19T15:15:31Z | same | `================= 70 passed, 17 warnings in 662.21s (0:11:02) ==================` |
| backend/tests/component/computed_attribute/test_scoped_recompute_jinja2.py (3 new tests; file edited after the run above for a mypy fix) | integration (component, Prefect test server) | `cd backend && uv run pytest tests/component/computed_attribute/test_scoped_recompute_jinja2.py -q` | 2026-11-19T15:18:32Z | same | `================== 8 passed, 17 warnings in 167.42s (0:02:47) ==================` |

## Chunk: Phase 4: User Story 2 - Stored values are recomputed exactly when a template changes (Priority: P1), display labels and HFIDs

| Task | Outcome | Reason when not done |
|------|---------|----------------------|
| T017 | ✅ done | |
| T018 | ✅ done | |
| T019 | ✅ done | |
| T020 | ✅ done | |
| T021 | ✅ done | |
| T022 | ✅ done | |
| T023 | ✅ done | |
| T024 | ✅ done | |

Decisions worth flagging:

- The steps shared by both setup flows (decision, delete, submit, record) are in a new component, `TemplateFingerprintRefresher` in `core/template_fingerprint/refresher.py`. The flow builds it at its top with the repository, the workflow adapter and the recompute workflow, takes the family lock, runs `setup_triggers` for the peer automations, then calls `refresher.refresh(...)` inside the lock. T029 adds the carry-over between `setup_triggers` and `refresh`.
- `SchemaFingerprints.as_records()` was added to turn the collector output into records (used by the first-start seed and by the tests).
- T024 departs from the task text. `setup_task_manager_identifiers` cannot open a database session: `workers/dependencies.py` imports `services/adapters/workflow/worker.py`, which imports `workflows/initialization.py`, so importing `get_database` there creates an import cycle, and the guidelines forbid a function-local import to break one. The seed is a plain function, `seed_template_fingerprints(db)` in `workflows/initialization.py`. `WorkflowWorkerExecution.initialize` calls it right after `setup_task_manager_identifiers`, with a session of the service database, which `InfrahubServices.initialize_workflow` now passes as a new required `database` parameter. The seed is therefore not part of the `task-manager-identifiers` flow run.
- The T024 test is in `backend/tests/component/core/template_fingerprint/test_seed.py`, not in `backend/tests/component/core/test_initialization.py`. Function tests in that module run `delete_all_nodes_in_db` and `first_time_initialization` on the shared database, and the testing rules ask for a test to go in the topic directory of its area. The test calls `setup_task_manager_identifiers()` and then `seed_template_fingerprints(db)` directly; `WorkflowWorkerExecution.initialize` itself is not exercised by a test.
- The display label and HFID scenarios are written once in `backend/tests/helpers/template_fingerprint.py` (`TemplateSetupScenarios`), with a small test schema (`TestingFpOwner`, `TestingFpDevice`, `TestingFpTag`). `TestDisplayLabelSetup` and `TestHFIDSetup` subclass it, and `TestHFIDSetup` adds the "HFID added" and "both families in one update" cases. Every test starts with the records that match the current schema (an autouse fixture deletes all `TemplateFingerprint` vertices and writes them again). The "submission raises" case uses a `FailingWorkflow` test adapter that records the call and then raises.
- The default-branch change test loads the changed schema on the default branch and loads the original schema back in a `finally` block.
- Kinds without an explicit display label still have a default display label template, and a kind with a unique attribute gets a derived HFID. So `TestingFpTag` has no unique attribute, which leaves it with no HFID until a branch adds one.
- T017: `test_gather_trigger_gather_trigger_display_labels_jinja2_default` now compares the gathered trigger names with the peer triggers built from `get_related_trigger_nodes()`, instead of counting one trigger per node with a display label.
- Bite check: with the previous `display_labels/models.py` and `display_labels/tasks.py` restored from the parent commit, `tests/component/display_labels/` gave "9 failed, 1 passed". The test that passed on both is `test_second_run_for_same_change_submits_nothing`, because the previous placeholder automations also stopped a second submission. The new code was restored from the WIP commit afterwards. The HFID tests were not run against the previous HFID code.
- `setup_triggers_specific` is still used by the computed attribute flows and was kept.

Lint and format: `uv run ruff format` and `uv run ruff check --fix` on the changed modules and tests ("All checks passed!"). `uv run ty check` on the same paths: "All checks passed!". `uv run mypy` on the 12 changed source and test files: "Success: no issues found in 17 source files". `uv run pytest tests/unit/trigger/ -q`: "24 passed". The full `uv run invoke lint` and `uv run invoke backend.mypy` run in T040.

| Test id | Type (unit/integration/e2e) | Run command | Passed at (ISO 8601) | Environment context | Verbatim pass line |
|---------|-----------------------------|-------------|----------------------|---------------------|--------------------|
| backend/tests/component/display_labels/test_gather.py (2 tests modified) | integration (component, Neo4j) | `cd backend && uv run pytest tests/component/display_labels/ -q` | 2026-11-19T15:59:30Z | Neo4j and Prefect test server started by testcontainers through the local Docker daemon, macOS, Python 3.14 | `================= 10 passed, 17 warnings in 285.04s (0:04:45) ==================` |
| backend/tests/component/display_labels/test_setup.py::TestDisplayLabelSetup (8 tests) | integration (component, Prefect test server) | same command | 2026-11-19T15:59:30Z | same | `================= 10 passed, 17 warnings in 285.04s (0:04:45) ==================` |
| backend/tests/component/hfid/test_setup.py::TestHFIDSetup (10 tests) | integration (component, Prefect test server) | `cd backend && uv run pytest tests/component/hfid/test_setup.py tests/component/core/template_fingerprint/test_seed.py -q` | 2026-11-19T15:54:30Z | same | `================= 11 passed, 17 warnings in 414.08s (0:06:54) ==================` |
| backend/tests/component/core/template_fingerprint/test_seed.py::TestTemplateFingerprintSeed::test_first_start_records_every_template_and_next_update_submits_nothing | integration (component, Prefect test server) | same command | 2026-11-19T15:54:30Z | same | `================= 11 passed, 17 warnings in 414.08s (0:06:54) ==================` |
| backend/tests/helpers/template_fingerprint.py (new shared scenarios, run through the two classes above) | integration (component) | covered by the commands above | 2026-11-19T15:59:30Z | same | see the rows above |

## Chunk: Phase 5: User Story 3 - Upgrade an existing instance without a full recompute (Priority: P2)

| Task | Outcome | Reason when not done |
|------|---------|----------------------|
| T025 | ✅ done | |
| T026 | ✅ done | |
| T027 | ✅ done | |
| T028 | ✅ done | |
| T029 | ✅ done | |

Decisions worth flagging:

- `backend/infrahub/trigger/placeholder_carry_over.py` has `parse_placeholder_automation(automation, schemas)` and `carry_over_placeholder_fingerprints(deleted, schemas, repository)`. The contract describes the schema input as "`SchemaFingerprints` per family"; it is a `Sequence[SchemaFingerprints]`, and a branch is in scope only when it is in the `SchemaFingerprints` of the automation's family. The setup flows pass their own family; `trigger_configure_all` passes both.
- Condition 2 ("trigger matches only `TRIGGER_PLACEHOLDER_FIELD`") is checked on the union of the `infrahub.field.name` values over every `match_related` entry, so the branch exclusion entries added by `exclude_branches` do not affect it. A trigger on the placeholder and a real field is skipped.
- Skipped automations are logged at debug level through `infrahub.log.get_logger()`, because the function also runs outside a Prefect run context.
- The setup flows now compute the schema fingerprints once and pass them to both the carry-over and `refresher.refresh`. The repository is built once at the top of each flow and given to both.
- In `trigger_configure_all`, the carry-over runs after the Prefect client is closed, with the flow's database session. It does not take the family locks (the contract allows it, since `insert_missing` never overwrites).
- T026: the shared autouse fixture writes the records of the current schema before each test, so the test deletes the records of `TestingFpOwner` and `TestingFpDevice` (both families, on `main`, `carry-over-a` and `carry-over/b`) and installs one placeholder per deleted record, 12 in total. The hand-deleted automation is the display label placeholder of `TestingFpOwner` on `main`; the setup flows then submit exactly `("main", TestingFpOwner)` for display labels and nothing for HFIDs. The branch `carry-over/b` checks the parse from the right on a branch name with `/` and `-`.
- T026, "second run creates or overwrites nothing": the test installs placeholders whose hash is `stale-template` over records that already exist, runs `trigger_configure_all`, and checks that the records still hold the schema fingerprints.
- Bite check: with `insert_missing(records=records[:0])` in the carry-over, the first component test failed with `assert {} == {...}` ("Right contains 11 more items"). The edit was reversed and `git diff` showed no change against the WIP commit.
- PLR0911 (too many returns) was fixed by splitting the name and hash parsing into two helpers.

Lint and format: `uv run ruff format` and `uv run ruff check --fix` on the changed modules and tests ("All checks passed!"). `uv run ty check` on the same paths: "All checks passed!". `uv run mypy` on the 6 changed files: "Success: no issues found in 6 source files". The full `uv run invoke lint` and `uv run invoke backend.mypy` run in T040.

| Test id | Type (unit/integration/e2e) | Run command | Passed at (ISO 8601) | Environment context | Verbatim pass line |
|---------|-----------------------------|-------------|----------------------|---------------------|--------------------|
| backend/tests/unit/trigger/test_placeholder_carry_over.py::test_parse_placeholder_automation (14 cases) | unit | `cd backend && uv run pytest tests/unit/trigger/ tests/component/trigger/test_placeholder_carry_over.py tests/component/display_labels/test_setup.py tests/component/hfid/test_setup.py -q` | 2026-11-19T16:26:22Z | macOS, Python 3.14 | `================= 58 passed, 17 warnings in 556.74s (0:09:16) ==================` |
| backend/tests/component/trigger/test_placeholder_carry_over.py::TestPlaceholderCarryOver::test_upgrade_carries_placeholder_fingerprints_over | integration (component, Prefect test server and Neo4j) | same command | 2026-11-19T16:26:22Z | Neo4j and Prefect test server started by testcontainers through the local Docker daemon, macOS, Python 3.14 | `================= 58 passed, 17 warnings in 556.74s (0:09:16) ==================` |
| backend/tests/component/trigger/test_placeholder_carry_over.py::TestPlaceholderCarryOver::test_second_upgrade_keeps_existing_records | integration (component, Prefect test server and Neo4j) | same command | 2026-11-19T16:26:22Z | same | `================= 58 passed, 17 warnings in 556.74s (0:09:16) ==================` |

## Chunk: Phase 6: User Story 4 - Branch lifecycle keeps the recorded fingerprints consistent (Priority: P3)

| Task | Outcome | Reason when not done |
|------|---------|----------------------|
| T030 | ✅ done | |
| T031 | ✅ done | |
| T032 | ✅ done | |

Decisions worth flagging:

- T032: `BranchDataDeleter.delete_branch_data` calls a new private step, `_delete_template_fingerprints`, first, before the agnostic peer cleanup and the edge deletion. It builds `TemplateFingerprintDeleteBranchQuery` through its constructor, the pattern of the new Query classes, not through `.init()` like the deleter's older queries. No constructor parameter was added to `BranchDataDeleter`.
- T032: nothing else called `TemplateFingerprintRepository.delete_branch`, so the method and its component test `test_delete_branch_removes_only_that_branch` were removed. The deleter test in `test_template_fingerprint_cleanup.py` now covers the "only that branch" case. `contracts/fingerprint-store.md` was updated: the repository table no longer lists `delete_branch`, a paragraph states that `BranchDataDeleter` runs the query, and "Callers that write" names `BranchDataDeleter`. `critiques/critique-20261119.md` still names `delete_branch`; it records the critique as written and was not changed. Task T006 in `tasks.md` still describes the removed repository test.
- T030 is `TestTemplateFingerprintCleanup`, which reuses `TemplateSetupTestBase` and the display label setup flow. The "stale registry" case deletes the branch with `BranchDataDeleter` without purging the registry, checks that the branch is still returned by `get_altered_schema_branches()`, and runs the setup flow: no record is written for it. That case passes without the T032 change too, because the repository writes require a `Branch` vertex (Phase 2); it pins that guard.
- T031: the test realigns the branch by loading the original test schema on it, and checks that the branch is no longer returned by `get_altered_schema_branches()` before the second setup run. The first version asserted that only `main` and the test branch held records, which failed when run after the other tests of the class (they leave `dl-identical` and `dl-diverging`); the assertions now compare against the records of every other branch.
- Bite check: with the `_delete_template_fingerprints` call removed from `delete_branch_data`, `test_delete_removes_only_the_branch_records` failed with `assert {'fp-deleted', 'main'} == {'main'}` and `test_recreated_branch_with_same_template_is_recomputed` failed with `assert [] == [('fp-reused'...tingFpOwner')]`. The call was put back and `git diff HEAD` showed no change against the WIP commit. T031 was not run against code without the decision's out-of-scope deletion (Phase 2 code).
- An untracked `backend/t031.log` (pytest output) was left in the worktree because deleting it needed an approval nobody could give; it is not committed.

Lint and format: `uv run ruff format` (2 files reformatted) and `uv run ruff check --fix` on the 5 changed source and test files: "All checks passed!". `uv run ty check` on the same files: "All checks passed!". `uv run mypy` on the same files: "Success: no issues found in 5 source files". The full `uv run invoke lint` and `uv run invoke backend.mypy` run in T040.

| Test id | Type (unit/integration/e2e) | Run command | Passed at (ISO 8601) | Environment context | Verbatim pass line |
|---------|-----------------------------|-------------|----------------------|---------------------|--------------------|
| backend/tests/component/branch/test_template_fingerprint_cleanup.py::TestTemplateFingerprintCleanup (3 tests) | integration (component, Prefect test server and Neo4j) | `cd backend && uv run pytest tests/component/branch/ tests/component/display_labels/ tests/component/core/template_fingerprint/test_repository.py -q` | 2026-11-19T17:04:51Z | Neo4j and Prefect test server started by testcontainers through the local Docker daemon, macOS, Python 3.14 | `================= 36 passed, 17 warnings in 493.70s (0:08:13) ==================` |
| backend/tests/component/display_labels/test_setup.py::TestDisplayLabelSetup::test_branch_that_stops_owning_its_schema_loses_its_records | integration (component, Prefect test server and Neo4j) | same command | 2026-11-19T17:04:51Z | same | `================= 36 passed, 17 warnings in 493.70s (0:08:13) ==================` |
| backend/tests/component/core/template_fingerprint/test_repository.py (one test removed, rest unchanged) | integration (component, Neo4j) | same command | 2026-11-19T17:04:51Z | same | `================= 36 passed, 17 warnings in 493.70s (0:08:13) ==================` |

## Chunk: Phase 7: Polish and cross-cutting concerns

| Task | Outcome | Reason when not done |
|------|---------|----------------------|
| T033 | ✅ done | |
| T034 | ✅ done | |
| T035 | ✅ done | |
| T036 | ✅ done | |
| T037 | ✅ done | |
| T038 | ❌ blocked | Needs a database loaded with at least 50 kinds and 3 diverging branches, and a PR description to record the plan in; no PR exists for this branch and no such stack was started in this run. |
| T039 | ✅ done | |
| T040 | ✅ done | |
| T041 | ❌ blocked | Needs a local stack built from this branch, a second stack on the previous release for the SC-005 comparison, and a PR description to record the results in. Not runnable inside this unattended chunk. |

Decisions worth flagging:

- T033: `display-labels-and-hfid.md` gets a sub-section "Template fingerprints decide which kinds are recomputed" under "Async Backfill After Schema Changes". It lists the six steps the setup flows run under the family lock, the seed at the initial task manager setup, the placeholder carry-over, and the branch cleanup. The seed is described as `WorkflowWorkerExecution.initialize` with `is_initial_setup`, which is where Phase 4 placed it (not in `setup_task_manager_identifiers` as the task text said).
- T034: `computed-attributes.md` replaces the "neutralizes self-targeting triggers" paragraph: no automation for self-targeting trigger nodes, candidates from `get_jinja2_trigger_nodes()` of a branch that owns its schema, `RecomputeScoper` scoping, and the default-branch hash comparison. It states that this family has no carry-over, because its decision reads no stored fingerprint.
- T035: `events.md`, "Branch scoping of automations", gains a paragraph saying that the three families keep automations only for templates that read a peer. The existing family list was kept, because the peer automations of those families still follow the per-branch scoping it describes.
- T036: the fragment was created with `uv run towncrier create +ifc-2167.changed.md --content ...`, then reworded so that the carry-over is scoped to display labels and HFIDs. A direct `vale` call needed an approval nobody could give; `uv run invoke release.vale` (the project task, which lints every fragment) reported 0 errors and 4 warnings, none on `+ifc-2167.changed.md`.
- T037: `grep -rln TRIGGER_PLACEHOLDER_FIELD backend/infrahub backend/tests` lists `trigger/constants.py`, `trigger/placeholder_carry_over.py` and seven test files (including `tests/helpers/template_fingerprint.py`).
- T040: every command passed without a code change, so no suppression was added.

Lint and format: `uv run invoke format` ("3076 files left unchanged", "All checks passed!"). `uv run invoke lint`: ruff "All checks passed!", ty "All checks passed!", mypy "Success: no issues found in 2105 source files". `uv run invoke backend.mypy`: "Success: no issues found in 2105 source files". `uv run ty check`: "All checks passed!". `uv run invoke docs.validate`: no generated file changed (`git status` unchanged). `uv run invoke docs.lint`: 0 errors, 10 warnings, all in `docs/docs/` files this branch did not change.

No new or modified tests in this chunk.

T039 regression run (existing suite, not modified):

| Test id | Type (unit/integration/e2e) | Run command | Passed at (ISO 8601) | Environment context | Verbatim pass line |
|---------|-----------------------------|-------------|----------------------|---------------------|--------------------|
| backend/tests/integration_docker/test_computed_attributes.py | integration (docker stack) | `uv run pytest backend/tests/integration_docker/test_computed_attributes.py -q` | 2026-11-19T17:11:26Z | Infrahub stack started by testcontainers through the local Docker daemon, macOS, Python 3.14. The image comes from `INFRAHUB_TESTING_IMAGE_VER` (read in `python_sdk/infrahub_sdk/testing/docker.py`); this run did not check whether the containers ran this branch's code or a published image. | `================= 11 passed, 17 warnings in 225.51s (0:03:45) ==================` |

## Chunk: Phase 7: Polish and cross-cutting concerns (second pass, T038 and T041)

| Task | Outcome | Reason when not done |
|------|---------|----------------------|
| T038 | ⚠️ partial | The query plan was measured (below), but it cannot be recorded in the PR description because no PR exists for this branch. The database held synthetic records written through the repository, not a loaded schema of 50 kinds. |
| T041 | ❌ blocked | Needs a local stack built from this branch, a second stack on the previous release for the SC-005 comparison, and a PR description to record the results in. Not runnable inside this unattended chunk. |

Decisions worth flagging:

- T038 measurement: a throwaway component test on the testcontainers Neo4j (`neo4j:2026.10.1-enterprise`) created 3 branches besides `main`, wrote 480 `TemplateFingerprint` records through `TemplateFingerprintRepository.upsert` (2 families × 4 branches × 60 kinds), then ran `EXPLAIN` and `PROFILE` on the text and parameters rendered by `TemplateFingerprintGetByFamilyQuery(family="human_friendly_id").render()`, through the Neo4j driver session. Run at 2026-11-19T17:13:45Z, `1 passed, 17 warnings in 19.10s`.
- Rendered query:

  ```cypher
  MATCH (f:TemplateFingerprint { family: $family })
  RETURN f.branch AS branch,f.kind AS kind,f.fingerprint AS fingerprint
  ORDER BY branch,kind
  ```

- `PROFILE` plan, from the leaf up: `NodeByLabelScan f:TemplateFingerprint` (rows 480, dbHits 481), `Filter f.family = $family` (rows 240, dbHits 480), `CacheProperties cache[f.branch], cache[f.kind]` (rows 240, dbHits 480), `Projection` (dbHits 0), `Sort branch ASC, kind ASC` (dbHits 0), `Projection f.fingerprint` (rows 240, dbHits 480), `ProduceResults` (rows 240). The `EXPLAIN` plan has the same operators. The read scans every record of the label and filters on `family`, about 4 database hits per record. This is the label scan that research Decision 3 expects, so no index is proposed. An index on `family` would remove only the filter on the other family's records.
- The throwaway test file could not be deleted: `rm` and edits to git's exclude file need an approval nobody could give. Its content was replaced with an empty file, `backend/tests/component/core/template_fingerprint/tmp_explain_check.py`. Delete it before opening the PR; if the workflow commits it, remove it in a follow-up commit.

Lint and format: no source or test code changed in this pass; not run.

No new or modified tests in this chunk.
