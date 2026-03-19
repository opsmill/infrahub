# Tasks: Delete Branch After Merge

**Input**: Design documents from `specs/infp-389-branch-merge-delete/`
**Prerequisites**: plan.md ✅ | spec.md ✅ | research.md ✅ | data-model.md ✅ | contracts/ ✅ | quickstart.md ✅

**Tests**: Not included (not explicitly requested in spec). Constitution-mandated tests are expected alongside implementation but are not broken out as discrete tasks.

**Organization**: Tasks are grouped by user story (US1 → US2 → US3 → US4) to enable independent implementation and testing of each story. US1 and US2 are both P1 and form the MVP.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel with other [P]-marked tasks in the same phase (different files, no dependencies between them)
- **[Story]**: Which user story this task belongs to (US1–US4)
- Exact file paths are included in every task description

---

## Phase 1: Setup

**Purpose**: Cross-cutting housekeeping before any story work begins.

- [ ] T001 Create Towncrier changelog fragment file in `changelog/` describing the new auto-delete-after-merge feature (filename: `<issue-number>.feature.md`, content: one sentence describing user-visible behavior)

---

## Phase 2: Foundational

**Purpose**: No new dependencies, no schema migrations, no new project infrastructure required. This phase is satisfied by the existing codebase.

*No tasks — proceed directly to User Story phases.*

---

## Phase 3: User Story 1 — Global Configuration (Priority: P1) 🎯 MVP

**Goal**: Expose two new boolean settings in the Infrahub configuration file so administrators can opt in to automatic branch deletion behavior. Both settings default to `false` (opt-in, non-breaking).

**Independent Test**: Set `delete_branch_after_merge = true` in `[main]` of `infrahub.toml`, restart, call `GET /api/config`, confirm both `main.delete_branch_after_merge` and `git.delete_git_branch_after_merge` fields are present with their configured values.

### Implementation for User Story 1

- [ ] T002 [US1] Add `delete_branch_after_merge: bool = Field(default=False, description="When enabled, branches are automatically deleted from Infrahub after a successful merge.")` to the `MainSettings` class in `backend/infrahub/config.py` (alongside the existing `diff_update_after_merge` field; env var: `INFRAHUB_DELETE_BRANCH_AFTER_MERGE`)
- [ ] T003 [US1] Add `delete_git_branch_after_merge: bool = Field(default=False, description="When enabled, the Git branch is automatically deleted from linked repositories after the Infrahub branch is deleted following a merge. Requires delete_branch_after_merge=true to have any effect.")` to the `GitSettings` class in `backend/infrahub/config.py` (alongside the existing `use_explicit_merge_commit` field; env var: `INFRAHUB_GIT_DELETE_GIT_BRANCH_AFTER_MERGE`)
- [ ] T004 [P] [US1] Find the REST config response model (search for the Pydantic model or dict that backs `GET /api/config` in `backend/infrahub/api/config.py` or the router that serves it) and add `main.delete_branch_after_merge` and `git.delete_git_branch_after_merge` to the serialized response so the frontend can read them

**Checkpoint**: `GET /api/config` response includes both new boolean fields. Setting them via `infrahub.toml` or environment variables takes effect on service restart.

---

## Phase 4: User Story 2 — Automatic Branch Deletion After Merge (Priority: P1)

**Goal**: When `main.delete_branch_after_merge` is enabled, branches are automatically deleted from Infrahub after a successful merge (both standard branch merge and proposed-change merge paths).

**Independent Test**: Enable `INFRAHUB_DELETE_BRANCH_AFTER_MERGE=true`, merge a branch, confirm the branch no longer appears in the branch list. Disable the config, merge another branch, confirm it remains as `MERGED`.

### Implementation for User Story 2

- [ ] T005 [US2] In the `merge_branch()` Prefect flow in `backend/infrahub/core/branch/tasks.py`, immediately after the block that sets `obj.status = BranchStatus.MERGED` and calls `await obj.save(db=db)`, add: if `config.SETTINGS.main.delete_branch_after_merge` is `True`, call `await get_workflow().submit_workflow(workflow=BRANCH_DELETE, context=context, parameters={"branch": obj.name})` — this reuses the full existing deletion path (graph cleanup + event + proposed-change cancellation) asynchronously so the merge caller is not blocked

**Checkpoint**: With config enabled, merging a branch via `BranchMerge` mutation or via a proposed-change merge results in the branch being deleted from Infrahub. With config disabled, the branch remains with status `MERGED`.

---

## Phase 5: User Story 3 — Automatic Git Branch Deletion After Merge (Priority: P2)

**Goal**: When both `main.delete_branch_after_merge` and `git.delete_branch_after_merge` are enabled and a branch has `sync_with_git=True`, the corresponding Git branch is deleted from all linked `CoreRepository` objects after the Infrahub branch is deleted. Failures are logged per-repository and do not block Infrahub branch deletion.

**Independent Test**: Enable both config flags, merge a branch that is synced with a Git repository, confirm the branch is gone from both Infrahub and the Git remote. Check that a remote push failure is recorded in the task log and does not prevent Infrahub deletion.

### Implementation for User Story 3

- [ ] T006 [P] [US3] Add `GitRepositoryDeleteBranch(BaseModel)` to `backend/infrahub/git/models.py` with fields: `repository_id: str`, `repository_name: str`, `repository_kind: str`, `branch_name: str`, `default_branch: str | None = None`, `context: InfrahubContext` — follow the style of the existing `GitRepositoryMerge` model immediately above it
- [ ] T007 [P] [US3] Add `GIT_REPOSITORY_DELETE_BRANCH = WorkflowDefinition(name="git-repository-delete-branch", type=WorkflowType.INTERNAL, module="infrahub.git.tasks", function="delete_git_repository_branch")` to `backend/infrahub/workflows/catalogue.py` and include it in the `ALL_WORKFLOWS` list (alongside `GIT_REPOSITORIES_MERGE`)
- [ ] T008 [P] [US3] Add `async def delete_branch_in_git(self, branch_name: str) -> None` method to `InfrahubRepositoryBase` in `backend/infrahub/git/base.py`: (1) guard — if `branch_name` equals `self.default_branch_name` or is `"main"` or `"master"`, raise `ValidationError`; (2) check if branch worktree exists via `self.has_worktree(identifier=branch_name)` — if not, log a warning and return (idempotent); (3) get the worktree via `self.get_worktree(identifier=branch_name)` and remove it with `self.get_git_repo_main().git.worktree("remove", "--force", str(worktree.directory))`; (4) delete local branch ref via `self.get_git_repo_main().git.branch("-D", branch_name)`; (5) if `self.has_origin`, delete the remote branch via `self.get_git_repo_main().git.push("origin", "--delete", branch_name)`
- [ ] T009 [US3] Implement `async def delete_git_repository_branch(model: GitRepositoryDeleteBranch) -> None` task in `backend/infrahub/git/tasks.py` (follow the style of `merge_git_repository()`): initialize `InfrahubRepository` for `model.repository_id`, call `await repo.delete_branch_in_git(branch_name=model.branch_name)` inside a try/except — on any exception, call `log.error(...)` including `model.repository_name` and the exception message, then return without re-raising
- [ ] T010 [US3] Extend the `delete_branch()` Prefect flow in `backend/infrahub/core/branch/tasks.py` to: after the graph deletion completes (after `await query.execute(db=db)` and `await super().delete(db=db)`), check if `obj.sync_with_git` is `True` AND `config.SETTINGS.main.delete_branch_after_merge` is `True` (this auto-delete path requires the outer flag) AND `config.SETTINGS.git.delete_git_branch_after_merge` is `True`; if all three are true, query all `CoreRepository` nodes from the database (use `registry.manager.all(db=db, kind=InfrahubKind.REPOSITORY)` or the equivalent pattern used in nearby tasks), then for each repo call `await get_workflow().submit_workflow(workflow=GIT_REPOSITORY_DELETE_BRANCH, context=context, parameters={"model": GitRepositoryDeleteBranch(repository_id=..., repository_name=..., repository_kind=..., branch_name=branch, context=context).model_dump()})` — note: `delete_branch()` must also accept an optional `delete_git_branch: bool | None = None` parameter to support the US4 manual override (implement the parameter plumbing but leave override logic for T012)

**Checkpoint**: With both config flags enabled, merging a Git-synced branch results in both the Infrahub branch and the remote Git branch being deleted. A simulated remote failure (e.g., by pointing to a non-existent remote) logs an error but does not prevent the Infrahub branch from being deleted.

---

## Phase 6: User Story 4 — Manual Branch Deletion with Git Option (Priority: P3)

**Goal**: When auto-delete is disabled, a user viewing a merged branch's detail page sees a delete button. If the branch is Git-synced and the global Git-deletion setting is off, the delete confirmation dialog includes a checkbox to also delete the Git branch. The choice is sent to the backend via the existing `BranchDelete` mutation.

**Independent Test**: With `INFRAHUB_DELETE_BRANCH_AFTER_MERGE=false` and `INFRAHUB_GIT_DELETE_GIT_BRANCH_AFTER_MERGE=false`, merge a branch, navigate to branch detail, click Delete, confirm the Git deletion checkbox is visible and functional (selectable checkbox deletes Git branch; unselected leaves it).

### Implementation for User Story 4

- [ ] T011 [US4] Add optional `delete_git_branch: Boolean` argument to the `BranchDelete.Arguments` inner class in `backend/infrahub/graphql/mutations/branch.py`; update `BranchDelete.mutate()` to accept `delete_git_branch: bool | None = None` and pass it as a parameter to both `execute_workflow` and `submit_workflow` calls as `parameters={"branch": obj.name, "delete_git_branch": delete_git_branch}`
- [ ] T012 [US4] Update the `delete_branch()` Prefect flow signature in `backend/infrahub/core/branch/tasks.py` to accept `delete_git_branch: bool | None = None`; in the Git deletion check block (added in T010), change the condition to: `(delete_git_branch is True) or (delete_git_branch is None and config.SETTINGS.git.delete_git_branch_after_merge)` — the outer guard `config.SETTINGS.main.delete_branch_after_merge` check from T010 still applies when triggering from the auto-delete path, but for the manual path (T011) the caller explicitly opted in so the outer guard is not needed
- [ ] T013 [US4] Update the `deleteBranch` domain function in `frontend/app/src/entities/branches/domain/delete-branch.ts` to accept an optional `deleteGitBranch?: boolean` parameter and include it as `delete_git_branch` in the GraphQL mutation variables when provided
- [ ] T014 [US4] Update `BranchDeleteButton` in `frontend/app/src/entities/branches/ui/branch-delete-button.tsx`: (1) fetch the global config (use an existing config query hook or TanStack Query call to `GET /api/config`) to read `git.delete_git_branch_after_merge`; (2) add local boolean state `deleteGitBranch` initialized to `false`; (3) inside `ModalDelete`, when `branch.sync_with_git === true` AND `config.git.delete_git_branch_after_merge === false`, render a checkbox labelled "Also delete from Git repository" bound to `deleteGitBranch` state; (4) pass `deleteGitBranch` to `deleteBranch({ name: branch.name, deleteGitBranch })` in the `onDelete` handler
- [ ] T015 [P] [US4] Regenerate frontend GraphQL and REST types by running `cd frontend/app && npm run codegen` so that `frontend/app/src/shared/api/graphql/` types include the new `delete_git_branch` argument on the `BranchDelete` mutation; commit the updated generated files

**Checkpoint**: With auto-delete disabled, a user can manually delete a merged branch with or without the Git branch via a checkbox in the UI confirmation dialog. The checkbox is hidden when global Git deletion is already enabled (no need to offer what will happen automatically).

---

## Phase 7: Polish & Cross-Cutting Concerns

**Purpose**: Documentation, code quality, and final verification across all stories.

- [ ] T016 Add documentation for the two new configuration options in `docs/docs/reference/configuration.mdx` (or the equivalent config reference page): document `[main] delete_branch_after_merge` (env: `INFRAHUB_DELETE_BRANCH_AFTER_MERGE`) and `[git] delete_git_branch_after_merge` (env: `INFRAHUB_GIT_DELETE_GIT_BRANCH_AFTER_MERGE`) with their default values and a note that the Git setting has no effect unless the main setting is also enabled

---

## Dependencies

```
T001 (changelog)          → independent, do first

US1: T002 → T003 → T004
     T002 and T003 are sequential (same file, different class)
     T004 [P] can start after T002+T003 (different file)

US2: T005 depends on T002 (needs config.SETTINGS.main.delete_branch_after_merge)

US3: T006 [P], T007 [P], T008 [P] → all independent, run in parallel
     T009 depends on T006, T007, T008
     T010 depends on T007, T009; also introduces the delete_git_branch param (T012 completes the logic)

US4: T011 depends on T010 (adds delete_git_branch param to mutation → flow)
     T012 depends on T010, T011
     T013 depends on T011 (schema change) or can be done speculatively
     T014 depends on T013
     T015 depends on T011 (schema must be updated before codegen)

Polish: T016 → independent, do last
```

**Story completion order**:
1. US1 (T002–T004) — required before US2, US3, US4
2. US2 (T005) — required before US3 (Git deletion builds on the Infrahub deletion path)
3. US3 (T006–T010) — independent of US4
4. US4 (T011–T015) — independent of US3 (but T012 extends T010's work)

US3 and US4 can be developed in parallel by two developers after US1+US2 land.

---

## Parallel Execution Examples

### Single developer (sequential)

```
T001 → T002 → T003 → T004 → T005 → T006 → T007 → T008 → T009 → T010 → T011 → T012 → T013 → T014 → T015 → T016
```

### Two developers (after US1 + US2 complete)

```
Developer A (backend): T001 → T002 → T003 → T004 → T005 → T006 + T007 + T008 (parallel) → T009 → T010
Developer B (frontend/mutation): T011 → T012 → T013 → T014 → T015
Both: T016 (whoever is available last)
```

### Three developers (US3 parallel tasks)

```
Dev A: T001 → T002 → T003 → T005 → T009 → T010
Dev B: T004 (after T002+T003) → T006 [P]
Dev C: T007 [P] → T008 [P]
Converge at T009 (needs T006, T007, T008)
```

---

## Implementation Strategy

**MVP Scope**: US1 (T002–T004) + US2 (T005) = 4 tasks. Delivers the primary value proposition (auto-cleanup of merged branches) with zero risk (opt-in, `false` by default). Can be shipped and tested independently.

**Increment 2**: US3 (T006–T010). Adds Git branch cleanup for teams using Git-synced repositories.

**Increment 3**: US4 (T011–T015). Adds manual control via the UI for teams who prefer per-branch cleanup decisions.

**Polish**: T016 should accompany whichever increment is shipped to users first.
