# Branch details scenarios (infp-671)

Seeds a local Infrahub with `scn-*` branches, Git repositories and tasks, so every state of the
branch details page can be tried by hand. Everything it creates is named `scn-*`.

```bash
cd dev/specs/infp-671-branch-details-repos/scenarios
uv run --no-project seed.py up                     # create or complete the seed (idempotent)
uv run --no-project seed.py up --with-unreachable  # also add unreachable repositories (global: every branch shows them)
uv run --no-project seed.py status                 # sync_status per branch, operational_status, task states
uv run --no-project seed.py down                   # delete every scn- branch and repository, stop the local servers
PLAYWRIGHT_MODULE=/path/to/frontend/app/node_modules/playwright/index.js \
  SCN_UNREACHABLE=1 node verify.mjs /tmp/scn-shots  # screenshots + checks (SCN_UNREACHABLE=1 after --with-unreachable)
```

`up` converges: run without `--with-unreachable` and it removes the unreachable repositories again.
Environment overrides: `INFRAHUB_ADDRESS`, `INFRAHUB_USERNAME`, `INFRAHUB_PASSWORD`, `SCN_STATE_DIR`,
`SCN_GIT_HOST`, `SCN_GIT_BIND`, `SCN_TIMEOUT`, `FRONTEND_URL`.

The fixture servers have no authentication and accept pushes, so they listen on `127.0.0.1` only
(`SCN_GIT_BIND`). Docker Desktop forwards `host.docker.internal` to the host's loopback, so the task
workers still reach them. On Docker Engine on Linux `host.docker.internal` is the bridge gateway:
set `SCN_GIT_BIND` to that address (for example `172.17.0.1`), not `0.0.0.0`, which would expose
writable repositories to your network.

## How it works

- Bare fixture repositories live in `~/.cache/scn-infp-671/git` (`SCN_STATE_DIR`) and are served by
  `git daemon` on `127.0.0.1:9418`; the task workers reach them as `git://host.docker.internal/<repo>.git`.
- `scn-fixtures` and `scn-repo-01`…`scn-repo-11` are read-write repositories with an empty
  `.infrahub.yml`, so importing them creates nothing; `scn-readonly` is read-only. With the demo's
  `demo-edge` that is 14 repositories (16 with `--with-unreachable`), so the table always paginates.
- Branches are created in Infrahub first. Infrahub pushes each Sync-with-Git branch to every
  read-write remote; the script then pushes a commit from `fixtures/<overlay>` onto that Git branch,
  one Infrahub branch at a time, and the periodic sync imports it on that branch only:
  - `broken`: `.infrahub.yml` declares a query whose file is missing → `error-import`.
    (A missing schema file is only a warning and leaves the repository in sync.)
  - `generators`: a query plus two generator definitions on the demo's `edge_router` group
    (10 devices); `scn-gen-fail` raises `KeyError`, `scn-gen-ok` succeeds.
- A failing periodic sync is tagged with the default branch only, so the page can't find its log.
  The script therefore runs "Import current commit" (`InfrahubRepositoryProcess`) on the branch for
  each broken repository, which gives a failed import task tagged with the branch and the repository.
  `scn-repo-02` on `scn-many-errors` is left out on purpose.
- `--with-unreachable` adds two read-write repositories (the periodic sync that records
  `operational_status` skips read-only ones). Infrahub refuses to create a repository it can't clone,
  so `githttp.py` serves them over HTTP while they are created, then `scn-unreachable` (port 9420)
  is no longer served → `error-connection`, and `scn-badcreds` (port 9419) answers 401 →
  `error-cred`. `scn-repo-04` stops being served by the git daemon → `error`.

## Branches

| Branch | Shows | URL |
|---|---|---|
| `scn-all-clear` | Every repository in sync, Read-only tag, repositories pager (page 2: `?repos_page=2`) | http://localhost:8080/branches/scn-all-clear |
| `scn-import-error` | One red band `scn-fixtures — import failed`, raw error line, View task log | http://localhost:8080/branches/scn-import-error |
| `scn-many-errors` | Five import errors first in the table: 3 bands, "N more repositories with errors", Show all / Collapse; `scn-repo-02` says the error details couldn't be found | http://localhost:8080/branches/scn-many-errors |
| `scn-generator-failed` | 20 generator runs, the 10 `scn-gen-fail` ones FAILED, "11 failed" in the header, tasks pager | http://localhost:8080/branches/scn-generator-failed |
| `scn-many-tasks` | Tasks table over 10 rows (12 Validate runs), tasks pager (`?tasks_page=2`) | http://localhost:8080/branches/scn-many-tasks |
| `scn-no-git` | Sync with Git off: only the read-only repository is listed | http://localhost:8080/branches/scn-no-git |

With `--with-unreachable`, every branch also shows amber bands for `scn-badcreds` (Credential
Error), `scn-unreachable` (Connectivity Error) and `scn-repo-04` (Error), with a warning icon on the
rows and no commit on the `scn-` branches. On `scn-many-errors`, `scn-repo-04` is both in Import
Error and unreachable: one red band, warning icon on its row.

## Not covered

- "Not synchronised with Git" and "No Git repositories" empty states: repositories are global, so
  `scn-readonly` and `demo-edge` are always listed. Only reachable on an instance without them.
- Exactly 10 repositories (no pager): the instance already has more.
- A repository stuck in `syncing`, and the no-access state (needs a restricted account and role):
  component tests only.
- Tasks stay in the task manager after `down`; it has no delete.
