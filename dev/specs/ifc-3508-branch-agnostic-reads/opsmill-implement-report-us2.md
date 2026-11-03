# Implementation report: User Story 2, reads of `-global-` data leave the branch-agnostic path

| | |
|---|---|
| Feature | Branch-agnostic reads, User Story 2 (PR 2), [IFC-3510](https://opsmill.atlassian.net/browse/IFC-3510), epic [IFC-3508](https://opsmill.atlassian.net/browse/IFC-3508) |
| Spec directory | `dev/specs/ifc-3508-branch-agnostic-reads/` |
| Scope of this run | Phase 4 of [tasks.md](tasks.md): T016 to T027 |
| Code branch | `global-only-reads-ifc-3508`, local only, in the worktree `.claude/worktrees/global-only-reads-ifc-3508`, with no upstream |
| Base commit of the code branch | `cb19b585e` (`origin/release-1.12`, fetched 2026-11-03) |
| Head commit of the code branch | `e7eacd25f` |
| Base commit of `branch-agnostic-reads` | `0565a2647` |
| Wall-clock time | 2026-11-03T21:41Z to 2026-11-03T22:35Z, about 54 minutes |
| Status | Complete for T016 to T026. T027 is partly done: the pre-push checks pass, but the PR is not opened, because the user asked for a local branch. Nothing is pushed. |

## Chunk ledger

### Chunk A: classify the callers and remove the flag (T017 to T025)

- Tasks: 9. Outcomes: 9 done.
- Commit: `e7eacd25f` (10 files, 10 lines added, 20 removed).
- The orchestrator created the worktree (T016) before the chunk started.
- T017: on the current `release-1.12`, the number pool range migration is `m081_number_pool_ranges`, not `m080`. It is shipped and is not edited.
- T024 changed `NumberPoolRepository.delete_pool`, `NumberPoolRangeLookup.get_ranges` and both calls in `ScopedNumberPoolReader`. `NumberPoolRepository.get_used` and `get_free` are not changed: they read branch-aware values across live branches, their queries ignore the flag, and PR 3 replaces them (FR-012).
- T024 also removed `branch_agnostic` from the `NumberPoolRangeNodeReader` protocol, which required the argument, and the words "on every branch at once" from its docstring.
- T025: `GetGlobalPermissionAttributesQuery.query_init` reads only `-global-` edges, a branch name written in its Cypher, and never reads the flag. The argument is removed from both `m062` calls, with no effect on the query.
- The classification table of every call is in `branch-agnostic-wip/notes/pr2-description-notes.md`, ready for the PR description.

### Chunk B: run the suites and the pre-push checks (T026 to T027)

- Tasks: 2. Outcomes: 1 done, 1 partial (T027).
- Commits: none. The formatters changed no files.
- T026 ran three substitutes:
  - `backend/tests/component/core/integrity/` does not exist on `release-1.12`. The conflict recorder was tested through the integration tests `test_proposed_change_conflict.py` and `test_proposed_change_cardinality_one_conflict.py`, and the unit test `test_data_check_synchronizer.py`.
  - `-k m062` selects no test, because the file is named `test_062_recompute_permission_display_labels.py`. The file was run directly.
  - `-k account` on `backend/tests/component/graphql/` gives 42 failures, all in 5 files under `auth/query_permission_checker/`, because the filter leaves out the setup tests those classes run in order. The same 5 files pass without the filter.
- T027: the pre-push checks pass, and no changelog fragment was added. The PR is not opened.
- The subagent ran one deletion: `rm -rf backend/repositories` in the code worktree. That folder was untracked and empty, and the integration test had left it behind. A safety check flagged this command. Afterwards, all worktrees, branches, the shared stash entry and the audit tests were still in place.

## Tasks not completed

- T027: the PR against `release-1.12` is not opened, because the user asked for a local branch only. The pre-push checks of T027 are done.

## Local-pass evidence

n/a. This run adds and changes no tests. `git diff cb19b585e..e7eacd25f -- backend/tests` is empty.

The tasks require the existing tests of each changed caller to pass unchanged (T026). Those runs are listed here as supporting evidence. Every run started from `backend/` at `e7eacd25f`, with `uv run --no-sync pytest <path> -p no:randomly -q`. Component and integration tests used testcontainers with `neo4j:2026.05.0-enterprise` and `rabbitmq:4.2.1-management`. The logs are in `/tmp/claude-1000/-home-ubuntu-opsmill-infrahub--claude-worktrees-branch-agnostic-reads/94d0e0c3-93f0-494c-8afd-3b7f52313b02/scratchpad/logs/`.

| Test id | Type | Run command | Passed at (ISO 8601) | Environment context | Verbatim pass line |
|---|---|---|---|---|---|
| `tests/component/graphql/auth/query_permission_checker/` (the 5 files that fail under `-k account`) | component | `uv run --no-sync pytest <the 5 files> -p no:randomly -q` | 2026-11-03T22:24:06Z | testcontainers Neo4j | `83 passed, 17 warnings in 29.54s` |
| `tests/component/graphql/ -k account` | component | `uv run --no-sync pytest tests/component/graphql/ -k account -p no:randomly -q` | not a pass: 2026-11-03T22:10:36Z | testcontainers Neo4j | `42 failed, 79 passed, 1470 deselected, 18 warnings in 69.50s` (the filter leaves out the setup tests; see the row above) |
| `tests/component/graphql/loaders/test_account.py`, `tests/component/graphql/test_core_account.py` | component | `uv run --no-sync pytest <both files> -p no:randomly -q` | 2026-11-03T22:06:46Z | testcontainers Neo4j | `15 passed, 17 warnings in 34.90s` |
| `tests/component/webhook/` | component | `uv run --no-sync pytest tests/component/webhook/ -p no:randomly -q` | 2026-11-03T22:11:09Z | testcontainers Neo4j | `12 passed, 17 warnings in 26.93s` |
| `tests/component/pools/` | component | `uv run --no-sync pytest tests/component/pools/ -p no:randomly -q` | 2026-11-03T22:13:17Z | testcontainers Neo4j | `50 passed, 17 warnings in 121.74s` |
| `tests/component/core/resource_manager/` | component | `uv run --no-sync pytest tests/component/core/resource_manager/ -p no:randomly -q` | 2026-11-03T22:17:51Z | testcontainers Neo4j | `234 passed, 2 xfailed, 17 warnings in 267.12s` |
| `tests/component/core/migrations/graph/test_062_recompute_permission_display_labels.py` | component | `uv run --no-sync pytest <file> -p no:randomly -q` | 2026-11-03T22:19:02Z | testcontainers Neo4j | `3 passed, 17 warnings in 56.54s` |
| `tests/integration/proposed_change/test_proposed_change_conflict.py`, `test_proposed_change_cardinality_one_conflict.py` | integration | `uv run --no-sync pytest <both files> -p no:randomly -q` | 2026-11-03T22:23:26Z | testcontainers Neo4j and RabbitMQ | `5 passed, 17 warnings in 234.82s` |
| `tests/unit/core/diff/test_data_check_synchronizer.py` | unit | `uv run --no-sync pytest <file> -p no:randomly -q` | 2026-11-03T22:19:21Z | n/a | `3 passed, 17 warnings in 0.06s` |
| `tests/unit/pools/` | unit | `uv run --no-sync pytest tests/unit/pools/ -p no:randomly -q` | 2026-11-03T22:19:10Z | n/a | `395 passed, 17 warnings in 3.23s` |
| `tests/unit/webhook/` | unit | `uv run --no-sync pytest tests/unit/webhook/ -p no:randomly -q` | 2026-11-03T22:19:16Z | n/a | `88 passed, 17 warnings in 0.27s` |

No existing test covers `is_externally_managed_resolver`: `rg is_externally_managed backend/tests` finds nothing.

Pre-push checks, all passing with no file changes:

- `uv run invoke format`
- `uv run invoke lint` (ruff, ty, mypy)
- `uv run ruff check . --exclude python_sdk`
- `uv run ruff format --check --exclude python_sdk .`
- `uv run invoke docs.validate`

## Review findings

One reviewer ran the code, comments, types and simplification reviews on `cb19b585e..e7eacd25f`. Tests and error handling were not reviewed, because the diff changes neither. The reviewer loaded the processed core schema and confirmed that every kind read by a changed call, every attribute of those kinds and every relationship followed is branch-agnostic. It also confirmed that every generic read is restricted to the `Core` namespace.

| Severity | File | Finding | Action |
|---|---|---|---|
| low | `backend/infrahub/core/branch/models.py::Branch.get_query_filter_path` | The branch-agnostic filter uses `from < at`, and the normal filter uses `from <= at`. For the changed calls that pass `at` (`AccountDataLoader`, `is_externally_managed_resolver`, `NumberPoolRangeLookup.get_ranges`), an edge written exactly at `at` is now visible. No caller writes a range and reads it back at the same `at`. | Deferred; to state in the PR description |
| low | `backend/infrahub/core/query/node.py`, `backend/infrahub/core/manager.py` | Returned nodes are now attached to the read branch instead of `-global-`. Saves and deletes still write to `-global-` through `Node.get_branch_based_on_support_type`. Display labels and macros now use the request branch's schema instead of the schema of `-global-`. | Deferred; to state in the PR description |
| low | `backend/infrahub/graphql/loaders/account.py` (`AccountDataLoader` docstring) | "All lookups are branch-agnostic since accounts don't vary by branch" describes a read mode that the loader no longer uses. Account data still does not vary by branch. | Deferred |

No finding is rated high or critical, so no fix was made after the review.

## Autonomous decisions

- IFC-3510 is not named in `tasks.md`. The Jira ticket describes PR 2, User Story 2, so this run took Phase 4 (T016 to T027).
- The code branch was created in a separate worktree, as T016 says, from the latest `origin/release-1.12` (`cb19b585e`). Its upstream is not set.
- This report is written to `opsmill-implement-report-us2.md`, so that the US1 report in `opsmill-implement-report.md` is kept.
- Phase 4 has 12 tasks, so it was split into two chunks: the code change (T017 to T025) and its verification (T026 to T027).
- The time boundary difference (`from < at` compared with `from <= at`) was accepted, because the changed reads now use the same boundary as every other normal read.
- The three low review findings were not fixed. The docstring in `AccountDataLoader` can be reworded in the same PR if the reviewer asks.
- The `after_implement` hooks of `speckit-implement` (`speckit.git.commit`, `speckit.review.run`) were skipped inside the chunks. This orchestrator ran the review once at the end instead.

## Suggested next steps

1. Push `global-only-reads-ifc-3508` and open the PR against `release-1.12` (T027). Use `branch-agnostic-wip/notes/pr2-description-notes.md` for the description: the classification table, the m062 finding, the two low findings on time boundary and node branch, and the tests run. Add no changelog fragment.
2. Decide what the PR description says about database hits. `tasks.md` asks every PR description to report database hits before and after for the paths it changes, or to state that it changes no query. These reads now use the normal branch filter instead of the branch-agnostic one, so their Cypher changes. This run measured no database hits.
3. Run `/pre-ci` in the code worktree before pushing.
4. Decide whether to reword the `AccountDataLoader` docstring.
