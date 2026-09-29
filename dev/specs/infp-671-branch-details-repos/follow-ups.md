# Follow-ups: INFP-671 branch details repositories

Backend asks found while building this frontend-only feature. None of them blocks it.

## Worker-bootstrap import failures can't be found as tasks

**Where**: `backend/infrahub/git/tasks.py::bootstrap_local_repository`, called from the `git_repositories_sync` flow.

**Problem**: when a worker has to re-clone a repository, it imports the default branch directly inside the parent `git_repositories_sync` flow run. If that import fails, `build_import_plan`/`apply_import_plan` set `sync_status = error-import` on the default branch. The failure is then logged at `info` (`log.info(exc.message)`) and swallowed. The result:

- the branch details band finds no task: `git_repositories_sync` isn't an import workflow, and it ends `Completed`
- no `error` line records the cause.

**Ask** (either one):

1. Run the bootstrap import in its own subflow (e.g. reuse `git-repository-import-object`, or `sync-git-repo-with-origin`), so it gets its own tagged, `Failed` run.
2. At minimum, log the failure at `error` instead of `info`.

## Structured "last import" on the repository

**Problem**: the frontend finds an import failure indirectly. It looks up the latest import flow run by tags, then takes the last `error`/`critical` log line, which is Prefect's `Finished in state Failed('Flow run encountered an exception: …')` wrapper. A periodic-sync failure message also lists every failing branch, not only the one being viewed.

**Ask**: expose the latest import task and its error message per branch on `CoreGenericRepository`, e.g. a `last_import_task` field (the handoff's system gap). The UI could then link to it and show it without log parsing.

## Newest logs first for `InfrahubTask`

**Where**: `backend/infrahub/task_manager/flow_run/reader.py::read_logs`, `backend/infrahub/graphql/queries/task.py` (`log_limit` / `log_offset`).

**Problem**: logs come back oldest first, with no sort option, and `logs.count` is the number returned rather than the total. To read the last error line of an import, the frontend has to ask for up to `NB_LOGS_LIMIT` (10,000) lines, and a longer log still loses its tail.

**Ask**: a log order argument (e.g. `log_order: DESC`) or a "last N logs" option on `InfrahubTask`, so the band can ask for the last few lines.
