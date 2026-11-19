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
