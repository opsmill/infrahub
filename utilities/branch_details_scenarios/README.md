# Branch details scenarios (infp-671)

Seeds a local Infrahub with `scn-*` branches, Git repositories and tasks, so every state of the
branch details page can be tried by hand. Everything it creates is named `scn-*`. The feature's
spec is in `dev/specs/infp-671-branch-details-repos/`.

```bash
cd utilities/branch_details_scenarios
uv run --no-project seed.py up                     # create or complete the seed (idempotent)
uv run --no-project seed.py up --with-unreachable  # also add unreachable repositories (global: every branch shows them)
uv run --no-project seed.py up --with-unreachable --many-branches  # also add 11 scn-b-NN branches (QA seed)
uv run --no-project seed.py status                 # sync_status per branch, operational_status, task states
uv run --no-project seed.py down                   # delete every scn- branch and repository, stop the local servers
node verify.mjs                                    # screenshots + checks, written to ./screenshots (git-ignored)
SCN_UNREACHABLE=1 SCN_MANY_BRANCHES=1 node verify.mjs  # after up --with-unreachable --many-branches
```

`up` converges: run without `--with-unreachable` and it removes the unreachable repositories again;
run without `--many-branches` (or with a smaller `N`) and it deletes the `scn-b-NN` branches it no
longer wants. `--many-branches N` adds `N` branches instead of 11. When `up` has branches to create
and the unreachable repositories exist, it deletes them first and adds them back at the end:
Infrahub can't push a new branch to them, which would fail that branch's "Create branch in Git
Repositories" task.

`verify.mjs` loads Playwright from `frontend/app/node_modules` (run `pnpm install` there first), or
from `PLAYWRIGHT_MODULE`. Pass a directory as its first argument to write the screenshots elsewhere.

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
| `scn-all-clear` | Every repository in sync, Read-only tag, repositories pager (page 2: `?repositories_page=2`) | http://localhost:8080/branches/scn-all-clear |
| `scn-import-error` | One red band `scn-fixtures — import failed`, raw error line, View task log | http://localhost:8080/branches/scn-import-error |
| `scn-many-errors` | Five import errors: 3 bands (the table keeps name order), "N more repositories with errors", Show all / Collapse; `scn-repo-02` says the error details couldn't be found | http://localhost:8080/branches/scn-many-errors |
| `scn-generator-failed` | 20 generator runs, the 10 `scn-gen-fail` ones FAILED, "11 failed" in the header, tasks pager | http://localhost:8080/branches/scn-generator-failed |
| `scn-many-tasks` | Tasks table over 10 rows (12 Validate runs), tasks pager (`?tasks_page=2`) | http://localhost:8080/branches/scn-many-tasks |
| `scn-no-git` | Sync with Git off: only the read-only repository is listed | http://localhost:8080/branches/scn-no-git |

With `--many-branches`, `scn-b-01`…`scn-b-11` are Sync-with-Git branches that only change
`scn-fixtures`: `scn-b-04` and `scn-b-08` fail to import it (with an "Import current commit" task),
`scn-b-02`, `scn-b-06` and `scn-b-10` give it a commit of their own, the others keep main's commit.

With `--with-unreachable`, every branch also shows amber bands for `scn-badcreds` (Credential
Error), `scn-unreachable` (Connectivity Error) and `scn-repo-04` (Error), with a warning icon on the
rows and no commit on the `scn-` branches. On `scn-many-errors`, `scn-repo-04` is both in Import
Error and unreachable: one red band, warning icon on its row.

## Which page and feature each scenario serves

One load covers the four features of the INFP-671 epic. Pages:

- **Header**: the Git status indicator at the right of the app header (IFC-3199). It counts
  repositories in Import Error on the branch selected in the top bar; `operational_status` is ignored.
- **Branch details**: `/branches/<name>`, Git repositories and Tasks cards (INFP-671, #10779).
- **Repository page**: Integrations → Git Repositories → a repository, `/objects/CoreRepository/<id>`:
  the Branches card and the "On this branch" card (IFC-3130).
- **Branch list**: `/branches`, Repository, Git state and Commit columns (IFC-3201, not built yet).

| Scenario | Header | Branch details | Repository page | Branch list |
|---|---|---|---|---|
| `main` | all clear | default branch: Details card only | first row, `default` badge | first branch |
| `scn-all-clear` | all clear | everything in sync, both pagers | In Sync | sync on, all In Sync |
| `scn-import-error` | failing | one red band | `scn-fixtures`: Import Error row | Import Error row first |
| `scn-many-errors` | failing | 3 bands + Show all, details-not-found band | Import Error on 5 repositories | 5 Import Error rows first |
| `scn-generator-failed` | all clear | failed tasks, "11 failed" | `scn-fixtures`: own commit | sync on, own commit |
| `scn-many-tasks` | all clear | tasks pager | In Sync | sync on |
| `scn-no-git` | all clear | Sync with Git off: read-only only | absent for read-write, listed for `scn-readonly` | sync off, read-only rows only |
| `scn-b-01`…`11` (`--many-branches`) | failing on 04 and 08 | same states, one repository | `scn-fixtures` pages (17 rows); `scn-readonly` "Infrahub branches" pages (every branch) | more sync-on branches, mixed states |
| demo branches (`atl1-…`, …) | all clear | Sync with Git off | absent for read-write | sync off |
| `demo-git-failed` (demo data) | failing: `demo-edge` is in Import Error there | Sync with Git off, so `demo-edge` isn't listed | absent for read-write | sync off |
| `--with-unreachable` | no effect | amber bands, warning icons | Details card: `operational_status` error | no effect (row order only) |

## Not covered

- "Not synchronised with Git" and "No Git repositories" empty states: repositories are global, so
  `scn-readonly` and `demo-edge` are always listed. Only reachable on an instance without them.
- Exactly 10 repositories (no pager): the instance already has more.
- A repository stuck in `syncing`, and the no-access state (needs a restricted account and role):
  component tests only.
- Header: the "No Git repositories", loading and "could not be checked" states (block or throttle
  the GraphQL request in devtools for the last two).
- Repository page: branch statuses other than Open (Rebase needed, Merging, Merge failed) for the
  Status filter, and 21+ rows for the pager's ellipsis on `scn-fixtures` (`scn-readonly` has them).
- Branch list: more than 40 branches for its infinite scroll; use `--many-branches 30`.
- Tasks stay in the task manager after `down`; it has no delete.
