# Implementation Plan: Delete Branch After Merge

**Branch**: `infp-389-branch-merge-delete` | **Date**: 2026-03-19 | **Spec**: [spec.md](spec.md)
**Input**: Feature specification from `specs/infp-389-branch-merge-delete/spec.md`

## Summary

Add configuration-driven automatic deletion of Infrahub branches (and optionally their linked Git branches) after a successful merge. Merges can happen via standard branch merge or proposed change merge. A manual override is also available in the UI for users who prefer per-branch control. All behavior is opt-in (disabled by default).

---

## Technical Context

**Language/Version**: Python 3.12 (backend), TypeScript 5.9 (frontend)
**Primary Dependencies**: FastAPI 0.121.1, graphene (GraphQL), Prefect (workflows), gitpython (Git operations), React 19.2, TanStack Query
**Storage**: Neo4j 5.28 (no schema changes required)
**Testing**: pytest 9.0 (unit + functional), Playwright 1.56 (E2E)
**Target Platform**: Linux server (backend), browser (frontend)
**Project Type**: Web application (backend + frontend)
**Performance Goals**: Deletion is async and non-blocking; merge response time unaffected
**Constraints**: Git deletion failures must not block Infrahub deletion; default `false` for all new settings (opt-in); `git.delete_git_branch_after_merge` has no effect unless `main.delete_branch_after_merge` is also `true` (structural dependency — Git deletion only fires inside `delete_branch()`, which is only reached when the main setting triggers it)
**Scale/Scope**: Affects every branch merge; one `GIT_REPOSITORY_DELETE_BRANCH` task per linked `CoreRepository` per deletion

---

## Constitution Check

### I. Schema-Driven Integrity ✅

No new schema nodes or relationships. No generated files require modification. Config fields are Python application-level settings.

### II. Branch-Safe by Default ✅

The feature operates on the completed-merge state (`BranchStatus.MERGED`). Deletion only triggers after a successful merge. The existing `Branch.delete()` method already handles the branch-safe deletion path (sets `DELETING`, removes relationships). No cross-branch side effects beyond the deletion itself.

### III. Type Safety & Explicit Contracts ✅

- New config fields: `MainSettings.delete_branch_after_merge` and `GitSettings.delete_git_branch_after_merge`, typed Pydantic `Field(default=False)`
- New workflow model: `GitRepositoryDeleteBranch` as a typed Pydantic `BaseModel`
- New mutation argument: `Boolean` (GraphQL type system)
- Frontend: no `any` types; config fields exposed as typed REST response

### IV. Test Discipline ✅

- Unit tests: config loading, `delete_branch_in_git()` logic, mutation argument handling
- Functional tests: end-to-end merge → deletion flow (both standard and proposed change merge)
- E2E tests: Playwright for US4 manual delete UI flow
- Git deletion: functional tests using a test Git repository

### V. Query Performance & Efficiency ✅

- No new Neo4j queries introduced beyond reuse of `Branch.get_by_name()` and existing repository queries
- No N+1 patterns: repository list is fetched once, then one workflow submitted per repo

### VI. Security & Input Boundaries ✅

- Config values are loaded from trusted config file / env vars; no user input
- `delete_git_branch: Boolean` mutation argument is validated by GraphQL type system
- Default-branch protection guard in `delete_branch_in_git()` prevents accidental deletion of `main`/`master`

### VII. Simplicity & Maintainability ✅

- Reuses the existing `BRANCH_DELETE` workflow; no new graph cleanup code
- Follows the `GIT_REPOSITORIES_MERGE` pattern exactly for per-repo Git tasks
- Config split mirrors the existing `diff_update_after_merge` / `use_explicit_merge_commit` precedent; `delete_git_branch_after_merge` is intentionally inert without `delete_branch_after_merge=true` — no extra runtime guard needed
- Frontend change is isolated to `BranchDeleteButton` — no new components

---

## Project Structure

### Documentation (this feature)

```text
specs/infp-389-branch-merge-delete/
├── plan.md              # This file
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 output
├── quickstart.md        # Phase 1 output
├── contracts/
│   ├── graphql-branch-delete.md
│   ├── rest-config-response.md
│   └── workflow-git-branch-delete.md
└── tasks.md             # Phase 2 output (from /speckit.tasks)
```

### Source Code Layout

```text
backend/infrahub/
├── config.py                                   # [US1 ✅] 2 new config fields added
├── api/
│   └── config.py                               # [US1 ✅] New fields exposed in /api/config
├── core/branch/
│   └── tasks.py                                # [US2 ✅] merge_branch() trigger; [US3 ✅] delete_branch() git hook
├── git/
│   ├── base.py                                 # [US3 ✅] origin_has_branch() + delete_remote_branch()
│   └── tasks.py                                # [US3 ✅] delete_git_branch() flow + git_branch_delete task
├── graphql/mutations/
│   └── branch.py                               # [US4 ⬜] BranchDeleteInput + delete_from_git arg
└── workflows/
    └── catalogue.py                            # [US3 ✅] GIT_REPOSITORIES_DELETE_BRANCH (plural)

tests/
├── unit/
│   └── test_config.py                          # [US1 ✅] Config loading unit tests
├── component/git/
│   └── test_delete_git_branch.py               # [US3 ✅] origin_has_branch / delete_remote_branch (4 tests)
├── functional/branch/
│   ├── test_branch_delete_after_merge.py       # [US2 ✅] merge → auto-delete functional flow
│   └── test_delete_git_branch.py               # [US3 ✅] workflow submit/skip assertions (3 tests)
└── integration/git/
    ├── conftest.py                             # [US3 ✅] Gogs Docker fixture + helpers
    └── test_delete_git_branch_gogs.py          # [US3 ✅] Full-chain Gogs integration tests (2 tests)

changelog/
└── <fragment>.feature.md                       # [ALL ⬜] Towncrier changelog fragment

docs/
└── docs/reference/configuration.mdx           # [US1 ⬜] Document new config options

frontend/app/src/
├── entities/branches/
│   ├── domain/
│   │   └── delete-branch.ts                   # [US4 ⬜] Add delete_from_git param
│   └── ui/
│       ├── branch-delete-button.tsx            # [US4 ⬜] Add Git deletion checkbox
│       └── queries/
│           └── delete-branch.mutation.ts       # [US4 ⬜] Pass delete_from_git to mutation
└── shared/api/rest/
    └── types.generated.ts                      # [US1 ⬜] Regenerated (new config fields)

frontend/app/tests/e2e/
└── branch-delete-after-merge.spec.ts           # [US4 ⬜] Playwright E2E for manual delete UI
```

> **Implementation divergences from original plan (US3)**:
> - No `GitRepositoryDeleteBranch` model in `git/models.py` — parameters passed directly to the workflow
> - Workflow name is `GIT_REPOSITORIES_DELETE_BRANCH` (plural) — a Prefect flow that fans out to one `git_branch_delete` task per repo
> - `InfrahubRepositoryBase` gained `origin_has_branch()` + `delete_remote_branch()` instead of a single `delete_branch_in_git()`
> - `delete_branch()` checks only `git.delete_git_branch_after_merge and obj.sync_with_git` (the `main.delete_branch_after_merge` guard is structural — git deletion only fires inside `delete_branch()` which is already gated by the main flag)

---

## Complexity Tracking

No constitution violations. All deviations from default patterns are justified:

| Decision | Why |
|----------|-----|
| Git deletion as separate workflow (not inline) | Follows `GIT_REPOSITORIES_MERGE` pattern; isolates per-repo failure handling |
| Two config fields (not one) | Git deletion is a separate opt-in — users may want Infrahub cleanup without Git cleanup; the dependency (`delete_git_branch_after_merge` requires `delete_branch_after_merge=true`) is structural, not enforced by an extra runtime check |

---

## Implementation Strategy

### MVP Scope (US1 + US2 only)

Deliver US1 (config) and US2 (auto-delete after merge) first. These have zero risk (opt-in, default disabled) and deliver the primary value. US3 (Git deletion) and US4 (UI) follow as independent increments.

### Phase ordering

1. **US1** ✅: Config fields + `/api/config` exposure — fully testable with unit tests
2. **US2** ✅: `merge_branch()` hook + functional tests — fully testable without Git repos
3. **US3** ✅: Git deletion workflow, method, task — tested with component, functional, and Gogs integration tests
4. **US4** ⬜: Frontend delete button + E2E tests — requires US1 config endpoint changes
5. **Polish** ⬜: Changelog fragment, documentation

### Dependency graph

```
US1 (config) → US2 (auto-delete) → Polish
US1 (config) → US4 (frontend) → Polish
US2 (auto-delete) → US3 (git delete) [US3 also depends on US2 trigger path]
US1 (config) → US3 (git config check)
```

US1, US2, and US3 are purely backend. US4 is purely frontend plus the mutation change. US3 can be parallelized with US4 after US1 is complete.
