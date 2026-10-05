# Follow-ups: INFP-671 branch details repositories

Backend asks found while building this frontend-only feature, then frontend alignments with other open work. None of them blocks it.

## Worker-bootstrap import failures can't be found as tasks

**Where**: `backend/infrahub/git/tasks.py::bootstrap_local_repository`, called from the `git_repositories_sync` flow.

**Problem**: when a worker has to re-clone a repository, it imports the default branch directly inside the parent `git_repositories_sync` flow run. If that import fails, `build_import_plan`/`apply_import_plan` set `sync_status = error-import` on the default branch. The failure is then logged at `info` (`log.info(exc.message)`) and swallowed. The result:

- the branch details band finds no task: `git_repositories_sync` isn't an import workflow, and it ends `Completed`
- no `error` line records the cause.

**Ask** (either one):

1. Run the bootstrap import in its own subflow (e.g. reuse `git-repository-import-object`, or `sync-git-repo-with-origin`), so it gets its own tagged, `Failed` run.
2. At minimum, log the failure at `error` instead of `info`.

## Failed periodic syncs are tagged with the default branch only

**Where**: the `sync-git-repo-with-origin` subflow of `git_repositories_sync` (`backend/infrahub/git/tasks.py`).

**Problem**: on the `scenarios/` seed, a periodic sync that fails to import a branch's commit leaves a
failed task tagged with the default branch (`main`) only. The branch's `sync_status` is
`error-import`, but `InfrahubTask(branch: <branch>, related_node__ids: [<repo>])` finds no task, so
the band says the error details couldn't be found. Research R2 expected `build_import_plan` to add
the branch tag; the live result says otherwise, and the cause isn't traced yet. "Import current
commit" on the branch does produce a findable task.

**Ask**: tag the sync run with every branch it imports, before the import can fail, or run each
branch's import in its own tagged subflow.

## Tag the repository at the start of every repository flow

_Added 2026-10-02 (restructure)._

**Where**: `backend/infrahub/git/tasks.py::import_objects_from_git_repository` (`git-repository-import-object`) and `sync_git_repo_with_origin_and_tag_on_failure` (`sync-git-repo-with-origin`); `backend/infrahub/workflows/utils.py::add_tags`.

**Problem**: the band looks up `InfrahubTask(branch, related_node__ids: [repository], workflow, state: [FAILED, CRASHED])`. `git-repository-import-object` tags only the branch at start (`add_branch_tag`); the repository tag is added later, in `InfrahubRepositoryIntegrator.build_import_plan`. A run that fails before that (for example in `get_initialized_repo`) has no repository tag, so the band can't find it and says the error details couldn't be found. `sync-git-repo-with-origin` adds the repository tag on failure only when the repository was `online` beforehand. The frontend could match `TaskNode.parameters` instead, but that couples it to each flow's parameter shape; not done (research § "Restructure (2026-10-02)" D3).

**Ask**: call `add_tags(branches=[<branch>], nodes=[<repository id>])` as the first statement of every flow that imports or syncs a repository, so every failure is findable by branch and repository.

## Fill `TaskError` for git imports (IFC-3034)

_Added 2026-10-02 (restructure)._

**Problem**: the band takes the last `error`/`critical` log line and unwraps Prefect's `Finished in state Failed('Flow run encountered an exception: …')` wrapper (`entities/repository/domain/rules/get-last-error-line.ts`). That parsing is a stopgap: it depends on Prefect's wording and on reading up to 10,000 log lines.

**Ask**: fill `TaskNode.error` (`TaskError`, today filled for webhook tasks only) for git import flows, as IFC-3034 plans. The band can then read the classified error and drop `getLastErrorLine`'s wrapper parsing and the log fetch.

## Structured "last import" on the repository

**Problem**: the frontend finds an import failure indirectly. It looks up the latest import flow run by tags, then takes the last `error`/`critical` log line, which is Prefect's `Finished in state Failed('Flow run encountered an exception: …')` wrapper. A periodic-sync failure message also lists every failing branch, not only the one being viewed.

**Ask**: expose the latest import task and its error message per branch on `CoreGenericRepository`, e.g. a `last_import_task` field (the handoff's system gap). The UI could then link to it and show it without log parsing.

## Newest logs first for `InfrahubTask`

**Where**: `backend/infrahub/task_manager/flow_run/reader.py::read_logs`, `backend/infrahub/graphql/queries/task.py` (`log_limit` / `log_offset`).

**Problem**: logs come back oldest first, with no sort option, and `logs.count` is the number returned rather than the total. To read the last error line of an import, the frontend has to ask for up to `NB_LOGS_LIMIT` (10,000) lines, and a longer log still loses its tail.

**Ask**: a log order argument (e.g. `log_order: DESC`) or a "last N logs" option on `InfrahubTask`, so the band can ask for the last few lines.

_(2026-10-02: since the restructure the log is fetched once per failed task and never polled, so the cost is one large read per band rather than one every 10 seconds. The ask stands.)_

## Frontend: align the import-error count with IFC-3199's `syncHealth`

_Added 2026-10-05._

**Where**: `frontend/app/src/entities/repository/domain/model/repository.ts` (`REPOSITORY_ERROR_IMPORT_FILTER`, used by the merged IFC-3199 `syncHealth` count through `get-repository-sync-counts-from-api.ts`) and `get-branch-repository-health-from-api.ts` (this PR).

**Problem**: IFC-3199 counts failing imports with `sync_status__value: "error-import"`, a substring match. This PR's health query uses `sync_status__values: ["error-import"]`, an exact match. Today no other `sync_status` value contains `error-import`, so the two agree, but a future value that contains it would be counted by the header and not by the card.

**Ask**: use one filter, the exact `sync_status__values`, for both, in a follow-up that touches IFC-3199's query.

## Frontend: changes to shared files that must also land in IFC-3130

_Added 2026-10-05._

This PR carries IFC-3130's shared pagination files. These changes to them must also land in IFC-3130, or be dropped here when IFC-3130 merges first:

- `TablePagination` (`shared/components/table/table-pagination.tsx`):
  - the `aria-label` prop, so the branch page's two pagers are distinct landmarks.
  - `focusVisibleStyle` on the native buttons (the focus ring).
  - the `text-base` size on the previous and next icons.
- `shared/api/graphql/error-handling.ts`: `hasOnlyThrownCatalogueCode` and `isThrownShed`. IFC-3130's `hasThrownCatalogueCode` matches when any error carries the code; `hasOnlyThrownCatalogueCode` matches only when every error does, which the repositories card needs to tell a permission denial from a mixed failure.

`getPageUrlKey`'s docstring in `shared/utils/table-pagination.ts` mentions a filter scope. It is verbatim from IFC-3130, where `entities/nodes/filters/ui/filter-scope-context.tsx` calls it, so it is left as is.
