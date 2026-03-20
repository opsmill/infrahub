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

> ⬜ Not yet done.

---

## Phase 2: Foundational

**Purpose**: No new dependencies, no schema migrations, no new project infrastructure required. This phase is satisfied by the existing codebase.

*No tasks — proceed directly to User Story phases.*

---

## Phase 3: User Story 1 — Global Configuration (Priority: P1) 🎯 MVP

**Goal**: Expose two new boolean settings in the Infrahub configuration file so administrators can opt in to automatic branch deletion behavior. Both settings default to `false` (opt-in, non-breaking).

**Independent Test**: Set `delete_branch_after_merge = true` in `[main]` of `infrahub.toml`, restart, call `GET /api/config`, confirm both `main.delete_branch_after_merge` and `git.delete_git_branch_after_merge` fields are present with their configured values.

### Implementation for User Story 1

- [x] T002 [US1] Add `delete_branch_after_merge: bool = Field(default=False, ...)` to `MainSettings` in `backend/infrahub/config.py` — **Done**
- [x] T003 [US1] Add `delete_git_branch_after_merge: bool = Field(default=False, ...)` to `GitSettings` in `backend/infrahub/config.py` — **Done**. Config validation requires `main.delete_branch_after_merge=True` when `git.delete_git_branch_after_merge=True`.
- [x] T004 [P] [US1] Exposed both fields in the `/api/config` response — **Done**

**Checkpoint**: `GET /api/config` response includes both new boolean fields. Setting them via `infrahub.toml` or environment variables takes effect on service restart.

---

## Phase 4: User Story 2 — Automatic Branch Deletion After Merge (Priority: P1)

**Goal**: When `main.delete_branch_after_merge` is enabled, branches are automatically deleted from Infrahub after a successful merge (both standard branch merge and proposed-change merge paths).

**Independent Test**: Enable `INFRAHUB_DELETE_BRANCH_AFTER_MERGE=true`, merge a branch, confirm the branch no longer appears in the branch list. Disable the config, merge another branch, confirm it remains as `MERGED`.

### Implementation for User Story 2

- [x] T005 [US2] `merge_branch()` submits `BRANCH_DELETE` when `config.SETTINGS.main.delete_branch_after_merge` is `True` — **Done**. Implemented in `backend/infrahub/core/branch/tasks.py`.

**Checkpoint**: With config enabled, merging a branch via `BranchMerge` mutation or via a proposed-change merge results in the branch being deleted from Infrahub. With config disabled, the branch remains with status `MERGED`.

---

## Phase 5: User Story 3 — Automatic Git Branch Deletion After Merge (Priority: P2)

**Goal**: When both `main.delete_branch_after_merge` and `git.delete_branch_after_merge` are enabled and a branch has `sync_with_git=True`, the corresponding Git branch is deleted from all linked `CoreRepository` objects after the Infrahub branch is deleted. Failures are logged per-repository and do not block Infrahub branch deletion.

**Independent Test**: Enable both config flags, merge a branch that is synced with a Git repository, confirm the branch is gone from both Infrahub and the Git remote. Check that a remote push failure is recorded in the task log and does not prevent Infrahub deletion.

### Implementation for User Story 3

- [x] T006 [P] [US3] ~~`GitRepositoryDeleteBranch` model in `git/models.py`~~ — **Skipped**. Parameters are passed directly; no typed model needed given the simpler fan-out design.
- [x] T007 [P] [US3] `GIT_REPOSITORIES_DELETE_BRANCH` workflow definition added to `backend/infrahub/workflows/catalogue.py` — **Done**. Name is plural (`GIT_REPOSITORIES_DELETE_BRANCH`), `type=WorkflowType.CORE`, points to `infrahub.git.tasks.delete_git_branch`.
- [x] T008 [P] [US3] ~~`delete_branch_in_git()`~~ — **Done with different API**. Added `origin_has_branch(branch_name) -> bool` (sync) and `delete_remote_branch(branch_name) -> None` (async) to `InfrahubRepositoryBase` in `backend/infrahub/git/base.py`. `delete_remote_branch` calls `git push origin --delete` and removes the local tracking ref.
- [x] T009 [US3] ~~`delete_git_repository_branch(model)`~~ — **Done with different design**. Implemented as a two-level Prefect fan-out in `backend/infrahub/git/tasks.py`: `delete_git_branch(branch: str)` flow fetches all `CoreRepository` nodes and fans out to one `git_branch_delete(...)` task per repo. `git_branch_delete` calls `origin_has_branch` (early return if absent) then `delete_remote_branch`, catching all exceptions per-repo (FR-007, FR-010).
- [x] T010 [US3] `delete_branch()` in `backend/infrahub/core/branch/tasks.py` submits `GIT_REPOSITORIES_DELETE_BRANCH` when `config.SETTINGS.git.delete_git_branch_after_merge and obj.sync_with_git` — **Done**. Note: the `delete_from_git` override parameter for US4 is **not yet added** — that will be handled in T011/T012.

> **US3 integration tests** (not originally in plan): `backend/tests/integration/git/test_delete_git_branch_gogs.py` — two Gogs Docker container tests verifying the full HTTP push-delete chain. Shared fixtures in `backend/tests/integration/git/conftest.py`.

**Checkpoint**: With both config flags enabled, merging a Git-synced branch results in both the Infrahub branch and the remote Git branch being deleted. A simulated remote failure (e.g., by pointing to a non-existent remote) logs an error but does not prevent the Infrahub branch from being deleted.

---

## Phase 6: User Story 4 — Manual Branch Deletion with Git Option (Priority: P3)

**Goal**: When auto-delete is disabled, a user viewing a merged branch's detail page sees a delete button. If the branch is Git-synced and the global Git-deletion setting is off, the delete confirmation dialog includes a checkbox to also delete the Git branch. The choice is sent to the backend via the existing `BranchDelete` mutation.

**Independent Test**: With `INFRAHUB_DELETE_BRANCH_AFTER_MERGE=false` and `INFRAHUB_GIT_DELETE_GIT_BRANCH_AFTER_MERGE=false`, merge a branch, navigate to branch detail, click Delete, confirm the Git deletion checkbox is visible and functional (selectable checkbox deletes Git branch; unselected leaves it).

### Implementation for User Story 4

- [ ] T011 [US4] Add `BranchDeleteInput(InputObjectType)` with `name` and `delete_from_git: Boolean` to `backend/infrahub/graphql/mutations/branch.py`; switch `BranchDelete.Arguments.data` from `BranchNameInput` to `BranchDeleteInput`; update `mutate()` to pass `parameters={"branch": obj.name, "delete_from_git": bool(data.delete_from_git)}` to both workflow call sites
- [ ] T012 [US4] Update `delete_branch()` in `backend/infrahub/core/branch/tasks.py` to accept `delete_from_git: bool = False`; update `should_delete_git` condition to `(config.SETTINGS.git.delete_git_branch_after_merge or delete_from_git) and obj.sync_with_git`
- [ ] T013 [US4] Update the `deleteBranch` domain function in `frontend/app/src/entities/branches/domain/delete-branch.ts` to accept an optional `deleteFromGit?: boolean` parameter and include it as `delete_from_git` in the GraphQL mutation variables when provided
- [ ] T014 [US4] Update `BranchDeleteButton` in `frontend/app/src/entities/branches/ui/branch-delete-button.tsx`: (1) fetch `GET /api/config` to read `git.delete_git_branch_after_merge`; (2) add `deleteFromGit` boolean state; (3) render "Also delete from Git repository" checkbox when `branch.sync_with_git === true` AND `config.git.delete_git_branch_after_merge === false`; (4) pass `deleteFromGit` to `deleteBranch` in the `onDelete` handler
- [ ] T015 [P] [US4] Regenerate frontend GraphQL and REST types: `cd frontend/app && npm run codegen`; commit updated generated files

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
