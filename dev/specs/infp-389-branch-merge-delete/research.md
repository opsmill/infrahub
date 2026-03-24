# Research: Delete Branch After Merge

**Branch**: `infp-389-branch-merge-delete` | **Date**: 2026-03-19
**Input**: Feature spec from `specs/infp-389-branch-merge-delete/spec.md`

## Summary

All implementation unknowns have been resolved through codebase analysis. No external research was required. Key decisions are documented below.

---

## Decision 1: Configuration Location

**Decision**: Add `delete_branch_after_merge: bool = False` to `MainSettings` and `delete_git_branch_after_merge: bool = False` to `GitSettings`.

**Rationale**: The existing `diff_update_after_merge` flag lives in `MainSettings` (env prefix `INFRAHUB_`). Git-specific behavior (e.g., `use_explicit_merge_commit`) lives in `GitSettings` (env prefix `INFRAHUB_GIT_`). Keeping this split mirrors the existing pattern: Infrahub-level behavior in `MainSettings`, Git repository behavior in `GitSettings`.

**Alternatives considered**:
- Add to `PolicySettings`: Rejected because the two existing policy settings are enterprise-only; branch cleanup is a community feature.
- Create new `BranchSettings` class: Rejected per Principle VII (YAGNI) — no second caller exists yet.

**Resulting env vars**:
- `INFRAHUB_DELETE_BRANCH_AFTER_MERGE` (default: `false`) → `MainSettings.delete_branch_after_merge`
- `INFRAHUB_GIT_DELETE_GIT_BRANCH_AFTER_MERGE` (default: `false`) → `GitSettings.delete_git_branch_after_merge`

**Dependency rule**: `delete_git_branch_after_merge` has no effect unless `delete_branch_after_merge` is also `true`. Git deletion triggers only through the `delete_branch()` flow, which is only reached when `delete_branch_after_merge` (or the manual override) is active.

---

## Decision 2: Post-Merge Trigger Point

**Decision**: In `backend/infrahub/core/branch/tasks.py`, the `merge_branch()` flow already sets `obj.status = BranchStatus.MERGED` and sends `BranchMergedEvent`. The deletion trigger is added immediately after `obj.save(db=db)` (line ~361) by submitting the existing `BRANCH_DELETE` workflow asynchronously. This reuses the full existing deletion code path (which already handles graph cleanup, event emission, and proposed-change cancellation).

**Rationale**: The `BRANCH_DELETE` workflow already does everything needed. Calling it post-merge avoids duplicating graph cleanup logic. Using `submit_workflow` (async, non-blocking) ensures the merge completes and the caller receives a successful response before deletion starts.

**Alternatives considered**:
- Trigger from `BranchMergedEvent` handler: Rejected because it introduces async event coupling for a deterministic, config-driven action; harder to reason about and test.
- Trigger Git deletion separately from Infrahub deletion: Rejected because `BRANCH_DELETE` already emits `BranchDeletedEvent` with `sync_with_git`, which is the right hook point.

---

## Decision 3: Git Branch Deletion Architecture

**Decision** (as implemented): Add two methods to `InfrahubRepositoryBase` (`backend/infrahub/git/base.py`):
- `origin_has_branch(branch_name: str) -> bool` — synchronous check: returns `True` if the branch exists as a remote ref on `origin`
- `delete_remote_branch(branch_name: str) -> None` — async: calls `git push origin --delete <branch>` and removes the local tracking ref

Add `GIT_REPOSITORIES_DELETE_BRANCH` (plural, `WorkflowType.CORE`) to `backend/infrahub/workflows/catalogue.py`, pointing to `infrahub.git.tasks.delete_git_branch`.

Implement as a two-level Prefect fan-out in `backend/infrahub/git/tasks.py`:
- `delete_git_branch(branch: str)` flow — fetches all `CoreRepository` nodes, creates a batch, submits one `git_branch_delete` task per repo
- `git_branch_delete(client, branch, repository_id, repository_name, repository_location)` task — calls `origin_has_branch` (early return if absent), then `delete_remote_branch` inside a per-repo try/except

No `GitRepositoryDeleteBranch` Pydantic model was created — parameters are passed directly as kwargs.

**Rationale**: The fan-out flow pattern (fetch all repos → batch tasks) is cleaner than one `submit_workflow` call per repo from `delete_branch()`. Splitting `origin_has_branch` from `delete_remote_branch` gives a cheap pre-check that avoids a push attempt when the remote branch is already gone.

**Original plan divergence**: The original design called for `delete_branch_in_git()` (single method, worktree removal + local branch removal + push), a typed `GitRepositoryDeleteBranch` model, and per-repo `submit_workflow` calls from `delete_branch()`. The implemented design uses a separate fan-out flow instead, which keeps `delete_branch()` simpler.

**Alternatives considered**:
- Trigger from `BranchDeletedEvent` with event handler: The event already has `sync_with_git=True`. Could add an event handler. Rejected because the `delete_branch()` task already runs after the graph deletion; adding the Git deletion directly there is simpler and avoids hidden event coupling.

---

## Decision 4: Error Handling for Git Deletion

**Decision**: Per spec US3 scenario 3 and 4, Git branch deletion failures MUST NOT block Infrahub branch deletion. Failures are recorded in the repository's task log. Implementation: wrap each `delete_branch_in_git()` call in a try/except inside `delete_git_repository_branch()`; on failure, `log.error()` with the repository name and error message (the Prefect task log serves as the "task log of the repository" per spec language).

**Rationale**: Spec explicitly states "failure is recorded in the task log of the repository… and the Infrahub branch deletion still proceeds." The existing `merge_git_repository()` task follows the same pattern: it logs errors without re-raising them when individual repos fail.

---

## Decision 5: Manual Delete UI (US4)

**Decision**: Add a new `BranchDeleteInput` GraphQL input type with `name` and `delete_from_git: Boolean` fields. Switch `BranchDelete.Arguments.data` from the shared `BranchNameInput` to the new `BranchDeleteInput`. When `delete_from_git=true` while the global config has it disabled, Git deletion is triggered anyway via `should_delete_git = (config.SETTINGS.git.delete_git_branch_after_merge or delete_from_git) and obj.sync_with_git`. Update `BranchDeleteButton` to show a checkbox "Also delete from Git repository" when: (a) the branch has `sync_with_git=true`, (b) the global `delete_git_branch_after_merge` config is disabled, and (c) the branch is in MERGED status.

> Note: The original plan used a flat `delete_git_branch: Boolean` argument directly on `BranchDelete.Arguments`. The implemented design uses a separate `BranchDeleteInput` type (so `BranchNameInput` remains unchanged for other mutations), and the parameter is named `delete_from_git`.

**Rationale**: Adding an argument to the existing mutation is non-breaking (it's optional). The `BranchDeleteButton` already exists at `frontend/app/src/entities/branches/ui/branch-delete-button.tsx`. The frontend needs to query the current global config setting to conditionally render the checkbox.

**Config API access**: The frontend retrieves config via REST (`GET /api/config`). The new settings will be added to the config response model.

---

## Decision 6: No New Schema Changes

**Decision**: This feature requires no Infrahub schema changes. The `Branch` node model (`backend/infrahub/core/branch/models.py`) requires no new fields. All behavior is driven by application config and existing branch properties (`sync_with_git`, `status`).

**Rationale**: The spec describes configuration-file-based settings, not per-branch metadata. Per-branch overrides were explicitly excluded from scope in the spec clarification session.

---

## Dependency on INFP-407

Per spec: this feature depends on INFP-407. The spec clarification noted this as a dependency. Implementation should confirm INFP-407 is merged before starting US3 (Git branch deletion) testing against live repositories.
