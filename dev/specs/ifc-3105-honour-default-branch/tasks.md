# Tasks: Honour the Configured Repository Default Branch

**Input**: Design documents from `dev/specs/ifc-3105-honour-default-branch/` (reachable as
`specs/ifc-3105-honour-default-branch/` through the repo-root symlink)

**Prerequisites**: [plan.md](./plan.md), [spec.md](./spec.md), [research.md](./research.md),
[data-model.md](./data-model.md), [contracts/](./contracts/), [quickstart.md](./quickstart.md)

**Tests**: Included. The spec's FR "Verify" clauses and research.md D7 name a test per requirement,
and D7's ⭐ rows are the outcome-level evidence each headline requirement rests on. The warm-clone
reproduction is written first and must fail before the contract change lands.

**Organization**: Tasks are grouped by user story. US1 and US2 land together (spec US2 rationale:
"it lands with User Story 1"), so the requiredness *mechanism* is implemented in US1 and its
*enforcement coverage* lives in US2.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies on incomplete tasks)
- **[Story]**: `[US1]`–`[US4]` map to the four user stories in spec.md
- Sites inside a file are cited by symbol, never by line number

## Path Conventions

Backend-only change. Source under `backend/infrahub/`, tests under `backend/tests/{unit,component,functional,integration,integration_docker}/`,
internal docs under `dev/`, user docs under `docs/docs/`, changelog fragments under `changelog/`.

## PR breakdown

Four PRs. The boundaries follow the dependency rules below, not task count. Two of them are forced:
T009-T028 cannot be split, because making `default_branch` and `internal_status` required reaches 64
construction sites across 23 test files in one go (see plan.md Scale/Scope for the grep that
reproduces the count); and the plan requires the code and the docs describing it to ship together so
a revert is clean.

| PR | Tasks | Scope | Review weight |
|---|---|---|---|
| **1. Spec artifacts** | T070, plus the `dev/specs/ifc-3105-honour-default-branch/` directory itself | Docs only: the spec set and the `infp-546` Story 6 correction | Small. No code, no CI risk |
| **2. The trunk is resolved once (US1 + US2)** | T001, T002, T003-T044, T006a and T033a included, plus T068a | The defect fix and its enforcement: the baseline and worklists, the resolver, the object contract, all 16 `get_initialized_repo` call sites, the 14 direct factory callers (5 needing an explicit branch), the 23-file test migration, the evidence tests | Large and atomic. ~20 source files, ~25 test files |
| **3. Connect-time trunk validation (US3)** | T045-T053 | `git/remote_refs.py`, the connectivity message field, the flow, the Gogs integration test, `connect-repository.mdx` | Medium. One new module, one message field, one flow branch |
| **4. Skipped-branch task log (US4)** | T054-T067, T054a and T057a included, plus T068 | `BranchSkipReason`, `SyncReport`, the pre-fetch head capture, the two carriers and the sync carrier's two triggers, the component and functional coverage, `overview.mdx` | Medium. Confined to `git/{repository,models,sync,tasks}.py` |

**T071 and T072 are deliberately not in PR 1.** Both are tracker work that produces no repo artifact,
so neither can be "in" a PR. T071 (the PRD amendment) rides with T073, where the same reasoning gets
written for the PR description. T072 (three follow-ups to file) happens whenever, and the sooner the
better while the findings are fresh — note that its first item belongs on the existing INFP-672 card
rather than as a new ticket.

**T001 and T002 open PR 2, not PR 1.** They were originally scoped to PR 1, which was wrong on both
counts. T001's baseline records the git suites' pass/fail counts so T005 is provably a new failure;
that comparison is only valid against the base PR 2 is actually built on, so taking it in an earlier
PR against an earlier base proves nothing. T002's worklist is ticked off *as* the tasks in PR 2 land,
so it belongs in the PR that consumes it. They are PR 2's first two commits.

PRs 3 and 4 are independent of each other and both only need PR 2 merged, so they can be open for
review at the same time. PR 3 also edits `git/base.py` (T047 removes `check_connectivity`), which
PR 2 edits heavily — sequence it after PR 2 rather than in parallel.

### Gates that repeat on every PR

T042 (carrier greps), T044 (mypy), T069 (`docs.generate` + `docs.validate`), T073 (PR description)
and T074 (local gate plus `/pre-ci`) are **per-PR gates, not one-off tasks**. T069 in particular
must run in PR 2 (for `GitFileGet.branch_name`) and again in PR 3 (for
`GitRepositoryConnectivity.default_branch`): CI's `validate-generated-documentation` job fails on a
stale `docs/docs/reference/message-bus-events.mdx`.

The FR-011 documentation splits across two PRs and two pages. T068a writes the repository-object
lifecycle in PR 2, into `git-integration.md` if PR #10525 has merged by then and into `git-sync.md` if
it has not. T068 refreshes `git-sync.md`'s branch-import section in PR 4, unconditionally, because
T055 and T062 make it wrong either way. T075 splits the same way — quickstart Scenarios 1, 2, 3, 6
and 7 after PR 2, Scenario 4 after PR 3, Scenario 5 after PR 4.

### Making PR 2 reviewable

It cannot be made smaller without inventing a decomposition the plan does not have, so make it
walkable instead. Order the commits so a reviewer can take them one at a time:

1. `git/graph_settings.py` and its unit tests (T003-T004)
2. The failing reproduction (T005-T006) — a reviewer can see it fail at this commit
3. The object contract: base, both kinds, the factories, the factory task (T007-T012)
4. Call sites and carrier removal (T013-T024) — mechanical, one added argument per site
5. The test migration (T025-T028) — mechanical, the bulk of the line count
6. The added coverage (T029-T034 including T033a, T006a, T036-T041)
7. Changelog, knowledge page, generated docs (T035, T068, T069)

If reviewers still balk, the one available lever is to split commits 6 and 7 into a follow-up
tests-and-docs PR, keeping T005-T006 and T036-T038 in the first so the mechanism never lands
without the tests that prove it. The other conceivable lever — landing
`get_initialized_repo(infrahub_branch_name=None)` as optional first, updating call sites, then
tightening it — is rejected: an optional trunk parameter with a silent default is the exact shape
FR-002 and FR-003 exist to delete, and a stalled second PR would leave it shipped.

---

## Phase 1: Setup

**Purpose**: Establish the pre-change baseline and the call-site worklist, so a missed site (the
plan's widest-blast-radius risk) is caught by a list rather than by review.

- [ ] T001 Capture the pre-change baseline into `dev/specs/ifc-3105-honour-default-branch/baseline.md`: run `uv run pytest backend/tests/unit/git backend/tests/functional/git` and `uv run pytest backend/tests/component/git/test_git_repository.py backend/tests/component/git/test_sync_repository.py`, and record pass/fail counts so the reproduction test added in T005 is provably new
- [ ] T002 [P] Record the migration worklist in `dev/specs/ifc-3105-honour-default-branch/call-sites.md` from `grep -rn "get_initialized_repo\|InfrahubRepository.init\|InfrahubRepository.new\|InfrahubRepository(\|InfrahubReadOnlyRepository(" backend/infrahub backend/tests`. Four lists, each ticked off as its task lands:
  1. **16** production `get_initialized_repo` call sites (`await get_initialized_repo(` — do not count the `def` or the internal `_get_initialized_repo` delegation)
  2. **14** direct factory call sites outside `git/repository.py`, including the 5 that need their Infrahub branch named explicitly per research.md D4
  3. the **23** test files that construct a repository object (64 sites: 61 through `.init(`/`.new(`, 3 direct instantiation). Use the grep in plan.md Scale/Scope verbatim — a narrower pattern gives a smaller number and a false sense of completeness
  4. the test call sites of the two methods whose contract changes, which no construction grep finds: `grep -rn "check_connectivity\|validate_remote_branch" backend/tests`. T047 removes the first and T055 changes the second's return type, so their existing tests break or become dead and need porting, not just re-constructing

**Checkpoint**: Baseline recorded; every site that must change is enumerated.

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: The single resolution point every read-write construction will go through. Nothing in
US1, US2 or US4 can be built before the resolver exists.

**⚠️ CRITICAL**: T003–T004 block Phase 3 onwards.

- [ ] T003 Write unit tests in `backend/tests/unit/git/test_graph_settings.py` for `resolve_graph_settings`: returns the node's `default_branch`, `internal_status` and `location`; a stub client asserts *which* Infrahub branch it queried; the SDK's `NodeNotFoundError` and `BranchNotFoundError` come back as `RepositoryError` with the cause preserved (`__cause__`). No repository object is constructed (research.md D7, D1 error contract). Fails until T004
- [ ] T004 Create `backend/infrahub/git/graph_settings.py`: frozen `RepositoryGraphSettings` dataclass (`default_branch`, `internal_status`, `location`) and module-level `async def resolve_graph_settings(*, client, repository_id, repository_name, infrahub_branch_name)` doing one SDK `get` of `CoreRepository` by id on that branch with `raise_when_missing=True`, catching the SDK's base `Error` and re-raising `RepositoryError(identifier=repository_name, message=...) from exc`. Module, not a method on the pydantic model, per `.agents/rules/backend-component-design.md`

**Checkpoint**: The resolver exists and is tested in isolation.

---

## Phase 3: User Story 1 - A non-default-trunk repository works on every worker (Priority: P1) 🎯 MVP

**Goal**: The configured trunk is resolved once, at every construction, on the Infrahub branch the
operation runs on, and every downstream operation targets it regardless of how warm the worker's
clone is.

**Independent Test**: Connect a repository whose trunk is `develop` to an Infrahub whose default
branch is `main`, let a worker clone it, then trigger a second operation on the same worker
(artifact regeneration) and assert the transform read the remote `develop` tree with no re-clone and
no fallback to `main`.

### Tests for User Story 1

> Write T005 and T006 FIRST and confirm T005 FAILS before T007–T012.

- [ ] T005 [US1] ⭐ **Evidence for FR-001.** Add the warm-clone reproduction to `backend/tests/functional/git/test_repository_default_branch.py`: a repository node whose `default_branch` is not the platform default, a `file://` remote on disk, one construction that clones, then a second construction on the same worktree that must target the configured trunk. Assert on the tree the operation read, not on a property's return value. Must fail against the current code
- [ ] T006 [P] [US1] Add the staging-plus-non-default-trunk case (US1 scenario 3, FR-006) to the same file: a repository node existing only on a non-default Infrahub branch with a non-default trunk resolves and behaves as one where neither differs
- [ ] T006a [P] [US1] ⭐ **Evidence for US1 scenario 2, proposed-change half.** Add the proposed-change check case to the same file: on a repository whose trunk is not the platform default, a proposed change whose validation includes merge-conflict checking compares against the configured trunk. Assert on what the check compared, not that it completed. This is the matrix flow whose branch choice is least obvious — `_validate_repository_merge_conflicts` constructs with the source branch, and `run_check_merge_conflicts` / `run_user_check` take theirs from a check model — so a wrong-branch bug here survives every other test in the set (research.md D7)

### Implementation for User Story 1

- [ ] T007 [US1] `backend/infrahub/git/base.py`: remove the `default_branch_name` field, the `default_branch` property and `internal_status` from `InfrahubRepositoryBase`; declare `_get_mapped_remote_branch`, `_get_mapped_target_branch` and `_resolve_worktree_identifier` as abstract; express `get_filtered_remote_branches`' always-imported set as `{registry.default_branch, self._get_mapped_remote_branch(registry.default_branch)}`
- [ ] T008 [US1] `backend/infrahub/git/base.py`: `create_locally` takes a required `checkout_ref: str` and records the commit against `infrahub_branch_name` when given, otherwise against `registry.default_branch`; `_raise_enriched_error` passes `branch_name` through unchanged including `None`, and `_raise_enriched_error_static` omits the branch from the two messages that name one when it is `None` (contracts/repository-object.md, error path)
- [ ] T009 [US1] `backend/infrahub/git/repository.py`: `InfrahubRepository` declares `default_branch: str` and `internal_status: RepositoryInternalStatus` as required pydantic fields with no defaults, implements the three mapping hooks against `self.default_branch`, and `resolve_checkout_ref` returns `self.default_branch` with no graph read; the two comparisons that read the status switch from `.value` strings to enum members
- [ ] T010 [US1] `backend/infrahub/git/repository.py`: `InfrahubReadOnlyRepository` implements all three hooks as identity and its `resolve_checkout_ref` raises when the node carries no `ref` (the dead fallback to a trunk is gone). No trunk field, no staging status
- [ ] T011 [US1] `backend/infrahub/git/repository.py`: `InfrahubRepository.init` and `.new` take a required `infrahub_branch_name`, call `resolve_graph_settings` exactly once, construct with its `default_branch`/`internal_status`/`location` (a caller-supplied `location` wins), and set `infrahub_branch_name` on the instance from their parameter
- [ ] T012 [US1] `backend/infrahub/git/repository.py`: `get_initialized_repo` and `_get_initialized_repo` gain a required `infrahub_branch_name: str`, forwarded to the factory and added to the 30 s cache key
- [ ] T013 [P] [US1] Pass the operation's Infrahub branch at the four downstream flow call sites: `backend/infrahub/artifacts/tasks.py`, `backend/infrahub/transformations/tasks.py` (both flows), `backend/infrahub/generators/tasks.py`, `backend/infrahub/computed_attribute/tasks.py`
- [ ] T014 [P] [US1] Pass the branch in the proposed-change paths: both `get_initialized_repo` sites in `backend/infrahub/proposed_change/tasks.py`, the site in `backend/infrahub/proposed_change/branch_diff.py`, and `_validate_repository_merge_conflicts`, which constructs through the factory with the source branch
- [ ] T015 [P] [US1] `backend/infrahub/webhook/models.py`: `TransformWebhook.compute_payload` computes the Infrahub branch as `context.branch or registry.default_branch` and passes that value both to the factory and to `get_commit_value`; it must never read `repo.default_branch`, which now means the trunk. Apply the same to the read-only path
- [ ] T016 [P] [US1] Add `branch_name: str` (required) to `backend/infrahub/message_bus/messages/git_file_get.py`, populate it in `backend/infrahub/api/file.py` from the endpoint's existing branch parameter, and forward it to the factory in `backend/infrahub/message_bus/operations/git/file.py`
- [ ] T017 [P] [US1] `backend/infrahub/message_bus/operations/git/repository.py`: the fetch flow passes the branch its message carries, and the `branch_deleted` refresh flow passes `registry.default_branch` explicitly, because the branch the message names has just been deleted
- [ ] T018 [US1] `backend/infrahub/git/tasks.py`: `git_branch_create` and `git_branch_delete` pass `registry.default_branch` explicitly, with a one-line why on `git_branch_delete` (its fan-out runs after the Infrahub branch is gone, so reading the node on that branch would raise `BranchNotFoundError`). Then pass the branch each operates on at all **five** `get_initialized_repo` sites in the module, named so none is missed: `generate_artifact`, `import_objects_from_git_repository`, `git_repository_diff_names_only`, `run_check_merge_conflicts` and `run_user_check`. The last two are proposed-change check paths, so apply the three-question table from `contracts/repository-object.md` to each rather than passing whichever branch the model happens to expose
- [ ] T019 [US1] `backend/infrahub/git/tasks.py::merge_git_repository`: stop passing `default_branch_name=model.default_branch` to `InfrahubRepository.init` and pass `infrahub_branch_name=model.destination_branch` instead. This is the fifth direct factory caller and does not go through `get_initialized_repo`
- [ ] T020 [US1] `backend/infrahub/git/tasks.py`: drop `default_branch_name` and `internal_status` from `sync_git_repo_with_origin_and_tag_on_failure`'s signature, make `infrahub_branch` required, move the repository construction **inside** the flow's existing `try` so a failing node read is still tagged with the repository node, and stop `bootstrap_local_repository` forwarding node values into the factory
- [ ] T021 [US1] `backend/infrahub/git/sync.py::RepositoryAdder.add`: stop passing `internal_status` and `default_branch_name` into the factory; pass the Infrahub branch the add runs on
- [ ] T022 [US1] `backend/infrahub/git/models.py`: remove `GitRepositoryAdd.default_branch_name` and `GitRepositoryMerge.default_branch`. Keep `GitRepositoryAdd.internal_status` — it is the staging early-return's flow control, not a carrier of the object's field (contracts/repository-object.md, "Deliberately kept")
- [ ] T023 [P] [US1] `backend/infrahub/repositories/create_repository.py::RepositoryFinalizer.post_create`: stop setting `default_branch_name` on the add model
- [ ] T024 [P] [US1] `backend/infrahub/core/merge/repository_merge_dispatcher.py::RepositoryMergeDispatcher.merge_core_repositories`: stop setting `default_branch` on the merge model
- [ ] T025 [US1] Migrate the unit-tier construction sites: `backend/tests/unit/git/test_git_repository.py` and `backend/tests/unit/git/test_tasks.py` construct directly with explicit `default_branch` and `internal_status` values
- [ ] T026 [P] [US1] Migrate the component-tier construction sites: `backend/tests/component/git/conftest.py` (10 sites), `test_git_repository.py`, `test_graphql_query_import.py`, `test_repository_config.py`, `test_git_read_only_repository.py`, `test_artifact_composition.py`, `test_sync_repository.py`, and `backend/tests/component/conftest.py`. Decide per file: explicit values, or a client that answers the resolver
- [ ] T027 [P] [US1] Migrate the integration-tier construction sites: `backend/tests/integration/git/{test_auth_and_access,test_closure_failure_isolation,test_git_live_remote,test_git_repository,test_sync_branch_flag,test_sync_merged_branch}.py`, `backend/tests/integration/proposed_change/{test_artifact_regen_e2e,test_artifact_regen_watch,test_merge_selective_regen}.py`, `backend/tests/integration/transform/test_transform.py`, `backend/tests/integration/message_bus/operations/request/test_proposed_change.py`
- [ ] T028 [P] [US1] Migrate the remaining sites: `backend/tests/conftest.py` and `backend/tests/functional/convert_object_type/test_convert_repositories.py`
- [ ] T029 [P] [US1] Unit tests in `backend/tests/unit/git/test_git_repository.py` for the mapping hooks on both kinds (D3 semantics table): the read-write mapping for the three input classes, and identity for the read-only kind
- [ ] T030 [P] [US1] Unit test (FR-004, US1 scenario 6): a read-only repository whose remote disappears still raises its classified error from `fetch`, with the original Git error preserved and no crash inside the handler
- [ ] T031 [P] [US1] Unit test (D4): the factory populates `infrahub_branch_name`, and `_update_operational_status` names that branch in its mutation for an operation running on a non-default Infrahub branch. This pins the one operator-visible move riding along with the fix
- [ ] T032 [P] [US1] Unit test (D4): a transform webhook with no context branch resolves Infrahub's default branch, not the trunk, on a repository whose trunk is not the platform default
- [ ] T033 [P] [US1] Unit test (D3): the worktree identifier when Infrahub's default branch is not `main` and the remote has a literal `main`. Documents current behaviour; the collision itself is a filed follow-up (T072), not fixed here
- [ ] T033a [P] [US1] Unit tests closing the last two gaps in the SC-001 matrix: the generator flow and the computed-attribute flow each pass the Infrahub branch the operation runs on to `get_initialized_repo`, on a repository whose trunk is not the platform default. Assert the branch the factory received, which is the residual risk once the trunk is resolved in one place — standing up a real generator run or computed-attribute recompute would re-test the shared resolver at far higher cost (research.md D7)
- [ ] T034 [US1] ⭐ **Evidence for SC-006, and for SC-001's artifact and transform half.** Extend `backend/tests/integration_docker/test_artifact_composition.py` (already uses `initial_branch=SECTION_GIT_DEFAULT_BRANCH`) with a warm-clone regeneration step, and assert the regenerated artifact's **content** matches what the trunk's tree produces and differs from what a branch named like Infrahub's default produces. An assertion that regeneration merely completed is not evidence. This file covers artifacts and transforms on a real worker pool; the rest of the SC-001 matrix is carried by T039/T040 (merge write-back), T063 (sync), T006a (proposed-change checks) and T033a (generators, computed attributes)
- [ ] T035 [P] [US1] Add `changelog/+ifc-3105-warm-clone-default-branch.fixed.md` describing the warm-clone defect fix in operator terms

**Checkpoint**: US1 is complete. T005 passes, the full read-write matrix works on a non-default
trunk, and no flow supplies a trunk.

---

## Phase 4: User Story 2 - The broken state cannot be reintroduced (Priority: P1)

**Goal**: The contract cannot be bypassed by the next call site, and the previously fixed
non-default-trunk push cannot silently regress.

**Independent Test**: A construction-level test asserts that omitting the trunk (and, separately,
the staging status) when building a read-write repository object is rejected. A second test reverts
the push refspec behaviour and asserts the non-default-trunk push regression test fails.

**Note**: The mechanism (required pydantic fields) lands in T009. This phase is the coverage and the
verification that make the fix structural.

- [ ] T036 [P] [US2] Unit tests in `backend/tests/unit/git/test_git_repository.py` (FR-002, FR-005): constructing `InfrahubRepository` without `default_branch` raises `pydantic.ValidationError`, and separately without `internal_status`
- [ ] T037 [P] [US2] Unit test (FR-004, US2 scenario 3): a constructed `InfrahubReadOnlyRepository` has no `default_branch` attribute at all — the base model config drops a stray keyword rather than rejecting it, so assert on the instance
- [ ] T038 [P] [US2] Unit test (FR-003, US2 scenario 5): `"default_branch_name" not in GitRepositoryAdd.model_fields` and `"default_branch" not in GitRepositoryMerge.model_fields`. The quickstart grep is a manual recipe and cannot enforce this in CI
- [ ] T039 [US2] ⭐ **Evidence for FR-009.** Adapt `backend/tests/component/git/test_git_repository.py::test_merge_writes_back_to_non_main_default_branch` to construct with the trunk instead of assigning `repo.default_branch_name` after construction. The assertion stays on the remote ref the push advanced, which is what the pre-fix refspec got wrong
- [ ] T040 [US2] ⭐ **Evidence for US1 scenario 5.** Add a merge write-back case to the same file: with `GitRepositoryMerge.default_branch` gone, the remote trunk ref still advances, and the node was read on `model.destination_branch`
- [ ] T041 [US2] Run the FR-009 mutation check by hand: revert `InfrahubRepository.push`'s refspec to the bare branch name, confirm `uv run pytest backend/tests/component/git/test_git_repository.py -k non_main_default_branch` fails, restore the refspec, confirm it passes. Record the outcome in the PR description
- [ ] T042 [US2] Verify the carriers are gone (FR-003) with `grep -rn "default_branch_name" backend/infrahub/git backend/infrahub/repositories backend/infrahub/core/merge` and `grep -n "default_branch" backend/infrahub/git/models.py`, both returning nothing, and `grep -rn "resolve_graph_settings\|list_remote_refs\|ensure_branch_exists" backend/infrahub/git/base.py backend/infrahub/git/repository.py` returning only call sites, never a `def`
- [ ] T043 [US2] Correct the carrier-check recipe in `quickstart.md` Scenario 3 and in `contracts/repository-object.md` ("Removed carriers"): both claim `grep -rn "default_branch_name" backend/infrahub/` returns nothing, but the name is used for unrelated things across `core/migrations/`, `permissions/`, `graphql/` and `core/query/`. Scope both to the packages this feature touches, as in T042
- [ ] T044 [US2] Type-check gate (FR-004, D9): `uv run invoke backend.mypy` (or the project's mypy entry point) passes with the existing per-module `disable_error_code` entries unchanged and no new suppressions. `attr-defined` staying enabled for `infrahub.git.base` is what proves no base-class code reads a trunk; fix any error that surfaces in touched code rather than re-suppressing it

**Checkpoint**: US1 and US2 are both complete. The contract is enforced at construction and the
regression is pinned.

---

## Phase 5: User Story 3 - A misconfigured trunk is rejected when the repository is connected (Priority: P2)

**Goal**: Connecting a repository whose configured trunk is absent from the remote is rejected with
a message naming the trunk and the remote's actual default branch, from the reference listing the
connectivity check already performs, with no clone and no repository left behind.

**Independent Test**: Attempt to connect a remote whose default branch is `stable` and which has no
`main`, leaving the trunk at its default of `main`, and assert the request is rejected with an error
stating that `main` is absent and that the remote's default branch is `stable`, and that no
repository was created.

### Tests for User Story 3

- [ ] T045 [P] [US3] Write `backend/tests/unit/git/test_remote_refs.py` against local `file://` remotes: `list_remote_refs` parses a populated remote whose default branch is not `main`, an empty bare remote (no output, exit 0 → `RemoteRefs(default_branch=None, branches=frozenset())`) and a remote with branches but a detached `HEAD`; `ensure_branch_exists` raises with each verbatim message from contracts/connect-time-trunk-validation.md, and raises nothing when the trunk exists but is not the remote's default (FR-010). **Port the neutral-working-directory case** from the existing `backend/tests/unit/git/test_git_repository.py::test_check_connectivity_ignores_cwd_git_pointer`: `list_remote_refs` must run `git` from a directory that is not itself a git repository, so a `.git` pointer in the process's cwd cannot be read instead of the remote. T046 specifies that behaviour and this is currently its only regression test, which T047 deletes. No repository object constructed. Fails until T046

### Implementation for User Story 3

- [ ] T046 [US3] Create `backend/infrahub/git/remote_refs.py`: frozen `RemoteRefs(default_branch: str | None, branches: frozenset[str])`, `list_remote_refs(name, url)` running `git ls-remote --symref <url> HEAD refs/heads/*` from a neutral working directory and parsing line by line (`ref: refs/heads/<name>\tHEAD` sets the default; `<sha>\trefs/heads/<name>` adds a branch; other lines ignored), and `ensure_branch_exists(refs, branch_name, repository_name, location)` raising `RepositoryInvalidBranchError(identifier=repository_name, branch_name=branch_name, location=location, message=...)`. `location` is the remote URL and is **required**: `RepositoryInvalidBranchError.__init__` takes it as a required positional parameter, and `RemoteRefs` deliberately holds no URL. A `GitCommandError` goes to the existing static classifier with no branch name and nothing is parsed
- [ ] T047 [US3] Remove `check_connectivity` from `backend/infrahub/git/base.py`; the static error classifier it delegated to stays on the base. Its one production caller is `message_bus/operations/git/repository.py::connectivity` (T050) and its one test is `backend/tests/unit/git/test_git_repository.py::test_check_connectivity_ignores_cwd_git_pointer`; delete that test only once T045 has ported its assertion to `test_remote_refs.py`, so the behaviour is never uncovered
- [ ] T048 [P] [US3] Add `default_branch: str | None = None` to `backend/infrahub/message_bus/messages/git_repository_connectivity.py`
- [ ] T049 [US3] `backend/infrahub/repositories/create_repository.py::RepositoryFinalizer.post_create`: set `default_branch` on the connectivity message from `obj.default_branch.value` for the read-write kind only, leaving it `None` for read-only. `ValidateRepositoryConnectivity` in `backend/infrahub/graphql/mutations/repository.py` keeps sending `None`, so trunk edits after connection stay unvalidated (US3 scenario 5)
- [ ] T050 [US3] `backend/infrahub/message_bus/operations/git/repository.py::connectivity`: call `list_remote_refs`, mapping a `RepositoryError` exactly as today (`ERROR_CONNECTION`, `ERROR_CRED`, else `ERROR`); when `message.default_branch` is set, call `ensure_branch_exists(refs, message.default_branch, message.repository_name, message.repository_location)` — the same `repository_location` given to `list_remote_refs` — and map `RepositoryInvalidBranchError` to `success=False`, `message=exc.message`, `operational_status=ERROR`; reply as today
- [ ] T051 [US3] ⭐ **Evidence for FR-007 and SC-003.** Add the connect-time cases to `backend/tests/integration/git/test_git_live_remote.py` against a Gogs remote whose default branch is `master` and which has no `main`: the create mutation is rejected with the exact operator-facing message, no repository remains afterwards, a retry with the trunk set to `master` succeeds and synchronises, and an unreachable remote still reports the existing connectivity error rather than a trunk message
- [ ] T052 [P] [US3] Document the connect-time rejection and its message in `docs/docs/git-integration/connect-repository.mdx`, and add the trunk-edit limitation the spec's edge cases and quickstart's SC-005 table both point at this page for: a trunk edited after connection is not validated, nothing re-clones or reconciles branches imported under the old mapping, and the value is served from cache for a short interval after the edit
- [ ] T053 [P] [US3] Add `changelog/+ifc-3105-connect-time-trunk-validation.added.md`

**Checkpoint**: US1–US3 complete. A misconfigured trunk is caught at the cheapest point and leaves
nothing behind.

---

## Phase 6: User Story 4 - A skipped colliding branch is visible in the repository's task log (Priority: P3)

**Goal**: A remote branch skipped for colliding with Infrahub's default branch is recorded as a
warning in the task log of a task linked to the repository — once at connect, and thereafter by a
synchronisation run that either imported at least one branch or saw a commit arrive on the skipped
branch itself.

**Independent Test**: Connect a repository whose trunk is `develop` and whose remote also has `main`
to an Infrahub whose default branch is `main`; assert the task that added the repository, viewed from
the repository, contains a warning naming `main` as skipped. Let several synchronisation cycles pass
with no change on any branch and assert no further warning and no new task linked to the repository.
Then push a commit to `main` and assert the next cycle records the warning again.

### Tests for User Story 4

- [ ] T054 [P] [US4] Unit tests in `backend/tests/unit/git/test_git_repository.py`: `validate_remote_branch` returns `DEFAULT_BRANCH_COLLISION` for the collision, `INVALID_BRANCH_NAME` for a name pydantic rejects, and `None` otherwise; `collect_pending_imports` populates `skipped_branches` from the collision reason at **both** of its call sites (new branches and updated branches) and re-tests the predicate at neither. Update the existing `test_validate_remote_branch_allows_conflicting_branch`, which asserts `is True` and becomes `is None` under T055
- [ ] T054a [P] [US4] Unit tests in the same file for the advance detection (research.md D6, contracts/sync-task-log.md "Detecting that a skipped branch advanced"), against a `file://` remote and a warm clone: a skipped branch whose head did not move records nothing in `advanced_skipped_branches`; one that moved is recorded; and a clone with no prior remote-tracking ref for it records nothing. The third case pins the cold-clone rule, which is otherwise invisible until an operator sees a spurious warning from a fresh worker. Fails until T057a

### Implementation for User Story 4

- [ ] T055 [US4] `backend/infrahub/git/repository.py`: add the `BranchSkipReason` enum (`DEFAULT_BRANCH_COLLISION`, `INVALID_BRANCH_NAME`), move `validate_remote_branch` from `InfrahubRepositoryBase` to `InfrahubRepository`, and change its return type from `bool` to `BranchSkipReason | None` where `None` means "import it". The collision predicate stays at this single decision point
- [ ] T056 [P] [US4] `backend/infrahub/git/models.py`: add `skipped_branches: list[str] = []` and `advanced_skipped_branches: list[str] = []` to `CollectedImports`
- [ ] T057 [US4] `backend/infrahub/git/repository.py::collect_pending_imports`: both call sites skip on any reason and append to `CollectedImports.skipped_branches` when the reason is `DEFAULT_BRANCH_COLLISION`. The existing `Branch(name=...)` validation and conflict warning keep their behaviour
- [ ] T057a [US4] `backend/infrahub/git/repository.py::collect_pending_imports`: capture the remote heads as a `{branch: commit}` map by calling `get_branches_from_remote()` on the statement **before** `self.fetch()`, and after the fetch populate `CollectedImports.advanced_skipped_branches` with every entry of `skipped_branches` that is present in the capture and whose commit changed. A branch absent from the capture is omitted, which is the cold-clone rule. Local ref read only: no extra network call, and no state written anywhere
- [ ] T058 [US4] `backend/infrahub/git/sync.py`: add the frozen `SyncReport(skipped_branches: tuple[str, ...], imported_branches: tuple[str, ...], advanced_skipped_branches: tuple[str, ...])` and have `RepositorySyncer.sync` return it instead of `None`. `imported_branches` holds the Infrahub branch name of every import the run applied successfully; the two non-skipped tuples are the stateless signals that separate a cycle worth reporting from one where nothing moved
- [ ] T059 [US4] Make the report survive the failure path: introduce `RepositoryBranchesFailedError` as a `RepositoryError` subclass carrying the report (it does not exist yet — `InfrahubRepository.raise_if_branches_failed` currently raises a plain `RepositoryError`), build the `SyncReport` in `sync` before calling `raise_if_branches_failed`, and attach it to the raised error so a carrier's `except` block has the same report a successful run returns
- [ ] T060 [US4] Carrier 1, `backend/infrahub/git/tasks.py::add_git_repository`: emit one `prefect.logging.get_run_logger()` warning per entry in `report.skipped_branches`, unconditionally, on both the success and the failure path — wrap the sync call so a `RepositoryBranchesFailedError` still yields its report, log, then re-raise unchanged. The flow already tags itself with the repository node and already runs the first sync, so no tagging change is needed. The staging early return still reports nothing
- [ ] T061 [US4] Carrier 2, `backend/infrahub/git/tasks.py::sync_git_repo_with_origin_and_tag_on_failure`: emit the warnings only when `report.skipped_branches` is non-empty **and** at least one of `report.imported_branches` / `report.advanced_skipped_branches` is non-empty (failure path included). Warn for every entry in `skipped_branches`, not only the ones that advanced, so the operator sees the whole condition. Link the run to the repository with a **single** `add_tags(branches=[infrahub_branch], nodes=[repository_id])` issued once both conditions are known — a skipped-branch warning was emitted, or the sync raised while the repository was `ONLINE`. Mid-run tag updates rebuild from flow-start tags, so two calls would clobber each other. Re-raise the sync error afterwards
- [ ] T062 [US4] Use the verbatim warning text from contracts/sync-task-log.md in both carriers, one line per skipped branch: `Skipped remote branch '<branch>' of repository <name>: its name collides with the Infrahub default branch, which is mapped to this repository's default branch '<trunk>'.` The existing structlog "Ignoring import of mismatched default branch" line may stay for process logs but is not the operator-facing record
- [ ] T063 [US4] ⭐ **Evidence for FR-008 and SC-004.** Add component tests to `backend/tests/component/git/test_sync_repository.py` under `prefect_test_fixture`: exactly one warning in the add flow's run log at connect; a cycle where nothing moved on any branch records nothing and links no task (asserted through both discriminators being empty and through the run log); a cycle that imported a changed branch records one warning; **a cycle that saw a commit land on the colliding branch only records one warning and links the task, having imported nothing** (US4 scenario 5 — pair this with the preceding case so neither trigger can be dropped without a red test); a second cycle on the same clone with nothing further moved records nothing; no warning once the colliding branch is deleted, and separately once the trunk is changed to `main`; a repository with no colliding branch records nothing
- [ ] T064 [US4] Component test in the same file: a first sync at connect that fails on another branch still records the skipped-branch warning before the error is re-raised. This is the case that would silently lose FR-008's connect-time guarantee
- [ ] T065 [P] [US4] Functional tests in `backend/tests/functional/git/`: the sync child run is linked to the repository node only when a branch was skipped **and** something was imported, read from the run's tags through the Prefect harness client; and a failing node read in the sync child flow still links the run to the repository node, which proves the construction sits inside the flow's `try`
- [ ] T066 [P] [US4] Document where the skipped-branch warning appears in `docs/docs/git-integration/overview.mdx`, and when: at connect, and thereafter on a synchronisation that imports a branch or sees a commit arrive on the skipped branch. Say plainly that pushing to the skipped branch produces the warning rather than an import, and that a multi-worker deployment may record it once per worker
- [ ] T067 [P] [US4] Add `changelog/+ifc-3105-skipped-branch-task-log.added.md`

**Checkpoint**: All four user stories are independently functional.

---

## Phase 7: Polish & Cross-Cutting Concerns

- [ ] T068 FR-011, part 1 (unconditional): refresh `dev/knowledge/backend/git-sync.md`'s existing branch-import section, which names `validate_remote_branch` on the base and states that it "logs ... and returns `False`". Both are wrong after T055 and T062, whatever happens to PR #10525
- [ ] T068a FR-011, part 2 (**depends on merge order against PR #10525** — `pog-em/git-integration-doc`, the draft that adds `dev/knowledge/backend/git-integration.md`): document the repository object lifecycle — the trunk resolved once at construction by `git/graph_settings.py::resolve_graph_settings`, the factories setting `infrahub_branch_name` from the branch they read it on, the read-only kind carrying no trunk, and the base class answering the three questions through hooks. **If #10525 has merged**, put it in `git-integration.md` and fix everything this feature falsifies there, which is more than its volatile marker: its "Resolving the trunk on the repository object" section (T007 deletes both the optional field and the fallback property it quotes at `git/base.py:191-192`), all three rows of its "Which construction paths resolve it today" table, its `internal_status` default reference under "Staging repositories", its factory cache-key description (T012 adds `infrahub_branch_name` to the key), and its stale line-number citations. Reframe rather than delete its "A skipped branch is re-reported every cycle" limitation: T062 keeps the structlog line, so the process log still repeats — what changed is that an operator-facing record now exists. Leave its three INFP-670 volatile sections alone (post-merge ordering, push writeback, divergence detection). **If #10525 has not merged**, put the lifecycle content in `git-sync.md` and comment on #10525 that it needs revising before it merges, or it lands describing deleted code
- [ ] T069 Regenerate and validate the generated docs: `uv run invoke docs.generate` then `uv run invoke docs.validate`, and commit `docs/docs/reference/message-bus-events.mdx`, which changes because `GitRepositoryConnectivity` gained `default_branch` and `GitFileGet` gained `branch_name`
- [ ] T070 [P] Update `dev/specs/infp-546-git-solid-refactor/` Story 6: it plans an optional `default_branch_name` constructor parameter with a global fallback, which this feature supersedes with a required field; add the `BranchNameMapper` extraction (collapsing the three abstract hooks into one injected collaborator) to that spec's scope, since it is behaviour-preserving structural work
- [ ] T071 [P] Amend the PRD (Confluence Product page 858357761) and Jira IFC-3105 with the four verified corrections. The cheap form is a dated amendment banner at the top naming `dev/specs/ifc-3105-honour-default-branch/` as current, rather than editing the body in a dozen places; write it from T073's PR description so the reasoning is written once. The corrections: both open questions are closed (reject at connect; task-log warning); P3 adds no new repository surface, so the GraphQL "Ask First" gate the PRD declares CROSSED is not crossed; IFC-2870's "Deterministic reproduction" line names a test file, test and `xfail` marker that exist nowhere; and the PRD's Out of Scope entry for per-commit skipped-branch reporting rests on a false premise — it claims the last commit on a skipped branch would have to be remembered, when the unfiltered fetch already keeps it as a remote-tracking ref, so a commit arriving on the skipped branch is now a reporting trigger (FR-008) and only per-commit *granularity* stays excluded. Also **replace** PRD FR-008 and SC-004's "current repository state, visible for as long as it holds": the owner ruled a dedicated status surface for this condition overkill on 2026-09-04, so the task log is the intended design and nothing is outstanding against the old wording. Leaving it in place would have the next reader plan the surface this feature deliberately does not build
- [ ] T072 [P] File the three follow-ups: an on-demand configuration-validation action for a connected repository (INFP-672); connect-time validation of a read-only repository's `ref`, including tag and commit-SHA handling; and the worktree identifier collision when Infrahub's default branch is not `main` and the remote has a literal `main`
- [ ] T073 Write the PR description covering the two items the plan requires be raised there: `operational_status` now being written on the branch the operation ran on rather than always on Infrahub's default branch is an operator-visible change riding along with a bug fix; and the skipped-branch advance trigger is per worker, so one push to a skipped branch can produce one task-log entry per worker and will read as duplication to an operator. Also state, so a reviewer does not have to ask: no Playwright e2e test is added because this is a backend change with no frontend work and every operator-visible effect rides on existing UI (plan Constitution Check, Principle IV); and the PRD's persistent skipped-branch state is superseded by an owner decision rather than left undone
- [ ] T074 Run the full local gate from quickstart.md: `uv run invoke format`, `uv run invoke lint`, `uv run pytest backend/tests/unit/git`, `uv run pytest backend/tests/component/git/test_sync_repository.py backend/tests/component/git/test_git_repository.py`, `uv run pytest backend/tests/functional/git`, then `/pre-ci` for the whole-repo ruff check CI runs but `invoke lint` does not
- [ ] T075 Walk quickstart.md scenarios 1–7 against a dev stack with at least two task workers, and confirm every row of the SC-005 support-diagnosis table from the repository's detail page and Tasks tab alone

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: no dependencies
- **Foundational (Phase 2)**: after Setup. Blocks US1, US2 and US4
- **US1 (Phase 3)**: after Foundational. The MVP
- **US2 (Phase 4)**: mechanism lands in T009; this phase's tasks need T009, T022 and the T025–T028 migration
- **US3 (Phase 5)**: independent of the object contract except for the shared edit to `git/base.py` (T047 removes `check_connectivity`, T007–T008 edit the same file). Sequence after US1 to avoid a conflict, or coordinate the two edits
- **US4 (Phase 6)**: needs `self.default_branch` to be a required field (T009) and the sync-flow reshape (T020). Within the phase: T055 → T057 → T057a → T058 → T061; T054a fails until T057a; T063 needs T061
- **Polish (Phase 7)**: T068 needs T055 and T062; T068a needs T012 and T022, and its target page depends on whether PR #10525 has merged; T069 needs T016 and T048; T071 rides with T073; the rest is independent

### Within User Story 1

- T005 must fail before T007–T012 (evidence gate)
- T007–T008 (base) → T009–T011 (kinds and factories) → T012 (factory task)
- T012 → T013–T021 (call sites) and T025–T028 (test migration)
- T022–T024 (carrier removal) after T021
- T029–T033 and T033a after T012; T006a after T014 and T018 (it exercises those call sites); T034 after every call site lands
- Nothing in the suite runs green between T009 and T028: the required fields reach 64 construction
  sites across 23 test files. Treat T009–T028 as one landing

### Parallel Opportunities

- T002 alongside T001
- T013–T017 and T023–T024 are separate files: all parallel once T012 lands
- T025–T028 are separate test files: all parallel
- T029–T033, T033a and T036–T038 are separate additions to the unit suite: parallel, with light merge care on `test_git_repository.py`
- T045 alongside the rest of US3's implementation
- T052, T053, T066, T067, T070, T071, T072 are all docs/changelog/tracker work: fully parallel

---

## Parallel Example: User Story 1 call sites

```bash
# Once T012 has landed, these touch disjoint files:
Task: "Pass the branch at the four downstream flow call sites (T013)"
Task: "Pass the branch in the proposed-change paths (T014)"
Task: "Fix the webhook's Infrahub-branch resolution (T015)"
Task: "Add GitFileGet.branch_name and populate it (T016)"
Task: "Pass the branch in the connectivity and branch-deleted flows (T017)"
```

```bash
# Test migration, one task per tier, disjoint files:
Task: "Migrate unit-tier construction sites (T025)"
Task: "Migrate component-tier construction sites (T026)"
Task: "Migrate integration-tier construction sites (T027)"
Task: "Migrate the remaining conftest sites (T028)"
```

---

## Implementation Strategy

### MVP First (US1 + US2)

1. Phase 1 Setup, Phase 2 Foundational
2. Phase 3 US1, starting with the failing reproduction (T005)
3. Phase 4 US2 — it is the same landing as US1 and is what makes the fix structural rather than a patch
4. **STOP and VALIDATE**: quickstart Scenarios 1, 2, 3 and 6; T034's content assertion is the SC-006 gate
5. Everything after this point is visibility on a working baseline

### Incremental Delivery

1. Setup + Foundational → the single resolution point exists
2. US1 + US2 → the defect is fixed and cannot be reintroduced (MVP)
3. US3 → a misconfigured trunk is caught at connect, with no half-working repository left behind
4. US4 → a standing collision is visible from the repository's task history at one entry plus one per push to the skipped branch, not 1,440 a day

### Notes

- Apply the three-question table in `contracts/repository-object.md` to **every** touched call site,
  exhaustively. A `TypeError` catches an omitted branch; nothing catches passing the trunk where an
  Infrahub branch belongs. The webhook (T015) and `merge_git_repository` (T019) are the two known
  instances, and the second is the easiest to miss because it bypasses `get_initialized_repo`
- No schema, migration, GraphQL or REST change. If a task appears to need one, stop: none of
  `AGENTS.md`'s "Ask First" gates is meant to be crossed by this feature
- `git/base.py` and `git/repository.py` are also edited by `dev/specs/infp-546-git-solid-refactor`;
  whichever lands second rebases
