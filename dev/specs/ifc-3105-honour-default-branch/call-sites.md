# Migration worklist

Every site that must change, enumerated before the contract changes so a missed one is caught by a
list rather than by review. Ticked off as the owning task lands.

Reproduced from `develop` at `0a9cf432a` with:

```bash
grep -rn "get_initialized_repo\|InfrahubRepository.init\|InfrahubRepository.new\|InfrahubRepository(\|InfrahubReadOnlyRepository(" backend/infrahub backend/tests
```

Line numbers are the pre-change positions and go stale as soon as the first task lands; the symbol
is the durable identifier.

## 1. Production `get_initialized_repo` call sites (16)

`await get_initialized_repo(` only — the `def`, and the `_get_initialized_repo` delegation inside
`git/repository.py`, are not call sites.

| # | Module | Symbol | Branch it passes | Done |
|---|---|---|---|---|
| 1 | `message_bus/operations/git/file.py` | `get` | `message.branch_name` (new field, T016) | [x] |
| 2 | `message_bus/operations/git/repository.py` | `fetch` | `message.infrahub_branch_name` | [x] |
| 3 | `message_bus/operations/git/repository.py` | `branch_deleted` | `registry.default_branch` **explicit** — the branch the message names has just been deleted | [x] |
| 4 | `artifacts/tasks.py` | `generate_artifact_flow` | `model.branch_name` | [x] |
| 5 | `transformations/tasks.py` | `transform_python` | `message.branch` | [x] |
| 6 | `transformations/tasks.py` | `transform_render_jinja2_template` | `message.branch` | [x] |
| 7 | `proposed_change/branch_diff.py` | `BranchDiffCalculator._collect_repository_files` | the source branch it is diffing | [x] |
| 8 | `proposed_change/tasks.py` | `run_generators` | `model.source_branch` | [x] |
| 9 | `proposed_change/tasks.py` | `run_proposed_change_repository_checks` | the check's branch | [x] |
| 10 | `computed_attribute/tasks.py` | `process_transform` | `transform.branch_name` | [x] |
| 11 | `generators/tasks.py` | `run_generator` | `model.branch_name` | [x] |
| 12 | `git/tasks.py` | `generate_artifact` | `model.branch_name` | [x] |
| 13 | `git/tasks.py` | `import_objects_from_git_repository` | `model.infrahub_branch_name` | [x] |
| 14 | `git/tasks.py` | `git_repository_diff_names_only` | `model.infrahub_branch_name`, a new required field on `GitDiffNamesOnly`: the flow had no branch of its own, and its producer already holds one | [x] |
| 15 | `git/tasks.py` | `run_check_merge_conflicts` | `model.source_branch`. Only active read-write repositories reach this check, so the node is readable there | [x] |
| 16 | `git/tasks.py` | `run_user_check` | `model.branch_name`, **and `repository_kind=model.repository_kind`** rather than a hard-coded read-write kind — see below | [x] |

**One defect this list surfaced.** `run_user_check` hard-coded `repository_kind=InfrahubKind.REPOSITORY`
while user checks also run for read-only repositories. Harmless while construction read nothing from
the graph; fatal once it reads the node by kind. The kind is threaded from the proposed change's
repository list (which carries `read_only`) through `TriggerRepositoryUserChecks`,
`UserCheckDefinitionData` and `UserCheckData`. Caught by two existing functional tests in
`backend/tests/functional/convert_object_type/test_convert_repositories.py`.

## 2. Direct factory call sites outside `git/repository.py` (14)

The two inside `git/repository.py` are the factory task delegating to the classes and are not in
this list.

| # | Module | Symbol | Kind | Change | Done |
|---|---|---|---|---|---|
| 1 | `webhook/models.py` | `TransformWebhook.compute_payload` (read-only arm) | read-only | pass the computed Infrahub branch | [x] |
| 2 | `webhook/models.py` | `TransformWebhook.compute_payload` (read-write arm) | read-write | **explicit**: `context.branch or registry.default_branch`, never `repo.default_branch` (T015) | [x] |
| 3 | `proposed_change/tasks.py` | `_validate_repository_merge_conflicts` | read-write | pass the source branch | [x] |
| 4 | `git/sync.py` | `RepositoryAdder.add` | read-write | drop `internal_status` / `default_branch_name`, pass `model.infrahub_branch_name` | [x] |
| 5 | `git/tasks.py` | `add_git_repository_read_only` | read-only | unchanged (read-only factory keeps its signature) | [x] |
| 6 | `git/tasks.py` | `sync_git_repo_with_origin_and_tag_on_failure` | read-write | drop both carriers, move construction inside the `try`, pass `infrahub_branch` (T020) | [x] |
| 7 | `git/tasks.py` | `bootstrap_local_repository` (`.init`) | read-write | stop forwarding node values, pass `infrahub_branch` | [x] |
| 8 | `git/tasks.py` | `bootstrap_local_repository` (`.new`) | read-write | same | [x] |
| 9 | `git/tasks.py` | `git_branch_create` | read-write | **explicit** `registry.default_branch` | [x] |
| 10 | `git/tasks.py` | `git_branch_delete` | read-write | **explicit** `registry.default_branch`, with a why: its fan-out runs after the Infrahub branch is gone | [x] |
| 11 | `git/tasks.py` | `pull_read_only` (`.init`) | read-only | unchanged | [x] |
| 12 | `git/tasks.py` | `pull_read_only` (`.new`) | read-only | unchanged | [x] |
| 13 | `git/tasks.py` | `merge_git_repository` | read-write | **explicit** `model.destination_branch`; drops `default_branch_name=model.default_branch` (T019) | [x] |
| 14 | `git/tasks.py` | `import_read_only_repository_last_commit` | read-only | unchanged | [x] |

Five of these need their branch named explicitly rather than taken from a model field: rows 2, 9, 10
and 13, plus row 3 of list 1 (`branch_deleted`) and row 1 of list 1 (`GitFileGet.branch_name`).

## 3. Test files constructing a repository object (23 files, 64 sites)

Reproduced with the plan's Scale/Scope grep verbatim — a narrower pattern gives a smaller number and
a false sense of completeness:

```bash
grep -rn "InfrahubRepository(\|InfrahubReadOnlyRepository(\|InfrahubRepository\.init(\|InfrahubRepository\.new(\|InfrahubReadOnlyRepository\.init(\|InfrahubReadOnlyRepository\.new(" backend/tests
```

61 go through `.init(`/`.new(`; 3 are direct instantiation
(`unit/git/test_tasks.py`, and two in `functional/convert_object_type/test_convert_repositories.py`).

| File | Sites | Task | Done |
|---|---|---|---|
| `unit/git/test_git_repository.py` | 5 | T025 | [x] |
| `unit/git/test_tasks.py` | 1 | T025 | [x] |
| `component/git/conftest.py` | 10 | T026 | [x] |
| `component/git/test_git_repository.py` | 13 | T026 | [x] |
| `component/git/test_graphql_query_import.py` | 4 | T026 | [x] |
| `component/git/test_repository_config.py` | 4 | T026 | [x] |
| `component/git/test_git_read_only_repository.py` | 3 | T026 | [x] |
| `component/git/test_artifact_composition.py` | 1 | T026 | [x] |
| `component/git/test_sync_repository.py` | 1 | T026 | [x] |
| `component/conftest.py` | 1 | T026 | [x] |
| `integration/git/test_auth_and_access.py` | 2 | T027 | [x] |
| `integration/git/test_closure_failure_isolation.py` | 1 | T027 | [x] |
| `integration/git/test_git_live_remote.py` | 5 | T027 | [x] |
| `integration/git/test_git_repository.py` | 2 | T027 | [x] |
| `integration/git/test_sync_branch_flag.py` | 1 | T027 | [x] |
| `integration/git/test_sync_merged_branch.py` | 1 | T027 | [x] |
| `integration/proposed_change/test_artifact_regen_e2e.py` | 1 | T027 | [x] |
| `integration/proposed_change/test_artifact_regen_watch.py` | 2 | T027 | [x] |
| `integration/proposed_change/test_merge_selective_regen.py` | 1 | T027 | [x] |
| `integration/transform/test_transform.py` | 1 | T027 | [x] |
| `integration/message_bus/operations/request/test_proposed_change.py` | 1 | T027 | [x] |
| `conftest.py` | 1 | T028 | [x] |
| `functional/convert_object_type/test_convert_repositories.py` | 2 | T028 | [x] |

Total: **64 sites across 23 files**.

**How they were migrated.** Two shared helpers in `backend/tests/helpers/git.py`:

- `clone_repository` / `open_repository` construct the object with its graph-held configuration
  supplied directly. For tiers whose SDK client cannot answer a node query, that is the only option —
  the production factory now reads the node.
- `build_repository_client` returns a client that *does* answer that one read, its schema taken from
  the live registry so it cannot drift. Used wherever the code under test builds the repository
  object itself (the sync flow, the merge flow, the transform flows), so the real resolution path
  runs rather than being bypassed.

The integration tier needed neither: it has a real client and a real node, so those sites just gained
`infrahub_branch_name=`.

## 4. Tests of the two methods whose contract changes

No construction grep finds these, so they need porting rather than just re-constructing:

```bash
grep -rn "check_connectivity\|validate_remote_branch" backend/tests
```

| Site | Change | Task | Done |
|---|---|---|---|
| `unit/git/test_git_repository.py::test_check_connectivity_ignores_cwd_git_pointer` | T047 removes `check_connectivity`; its neutral-working-directory assertion is ported to `test_remote_refs.py` first (T045), then this test is deleted | T045, T047 | [ ] |
| `unit/git/test_git_repository.py::test_validate_remote_branch_allows_conflicting_branch` | asserts `is True`; becomes `is None` once the return type is `BranchSkipReason \| None` | T054, T055 | [ ] |

Rows in this section are US3/US4 work and stay open until those PRs land.
