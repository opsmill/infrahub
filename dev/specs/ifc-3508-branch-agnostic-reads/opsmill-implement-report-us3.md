# Implementation report: User Story 3, IP pools never hand out a value still in use on a live branch

| | |
|---|---|
| Feature | Branch-agnostic reads, User Story 3 (PR 3), [IFC-3511](https://opsmill.atlassian.net/browse/IFC-3511), epic [IFC-3508](https://opsmill.atlassian.net/browse/IFC-3508) |
| Spec directory | `dev/specs/ifc-3508-branch-agnostic-reads/` |
| Scope of this run | Phase 5 of [tasks.md](tasks.md): T028 to T050 |
| Code branch | `branch-windows-ip-pools-ifc-3508`, local only, in the worktree `.claude/worktrees/branch-windows-ip-pools-ifc-3508`, with no upstream |
| Base commit of the code branch | `17e898643` (`origin/release-1.12`, fetched 2026-11-04T00:44Z) |
| Head commit of the code branch | `4e1b8d2ba` (`1d4399593` at the end of the first run, before the performance follow-up) |
| Base commit of `branch-agnostic-reads` | `43e6266bc` |
| Wall-clock time | 2026-11-04T00:44Z to 2026-11-04T02:40Z, about 2 hours, then the performance follow-up from about 04:15Z to 05:10Z |
| Status | Complete for T028 to T049. T050 is partly done: the pre-push checks pass, but the PR is not opened, because the user asked for a local branch. Nothing is pushed. One decision is still open: whether the remaining cost of an allocation is acceptable (T046, see "Cost of an allocation"). |

## Chunk ledger

The orchestrator created the worktree (T028) before the first chunk. After each chunk, the orchestrator committed the task ticks in `tasks.md` on `branch-agnostic-reads`: `847e89357`, `c1f75d941`, `25faf58bd` and `a9760d342`.

### Chunk A: tests and benchmarks (T029 to T033)

- Tasks: 5. Outcomes: 5 done.
- Commits: `07f61e9e7` (benchmarks) and `3d27515cb` (component tests).
- On the base, the 8 moved IP pool tests fail and the 4 moved number pool tests pass, as `quickstart.md` expects.
- T032: acceptance scenarios 3 and 4 fail on the base, as expected. Scenarios 5 and 6 already pass on the base: a `resources` read on the default branch already leaves out a prefix that exists only on another branch.
- T029: `test_node_list_filter.py` from `7015435c4` runs on `release-1.12` with no change.
- The benchmark reloads the pool before each call, because the relationship manager caches peers. Without the reload, the base numbers would leave out the reads that the fix adds.

### Chunk B: the shared branch window module (T034 to T038)

- Tasks: 5. Outcomes: 5 done.
- Commit: `666571dce`.
- The module adds `render_branch_windows_clause`, which the contract does not list. It returns the clause without parameters. The retention predicate and the deleted-branch query are module-level strings that already set `$at` and `$global_branch_name`, so they cannot call `build_branch_windows_query`.
- The retention and retirement queries render the same Cypher text as before.
- T038: `_live_on_some_branch` does not exist on `release-1.12`. The fragments renamed from `fork_at` to `origin_at` are `EDGE_BRANCHES`, `HELD_BRANCH`, `LIVE_ATTRIBUTE_VALUES_QUERY` and `INHERITED_OPEN_VALUES_QUERY`.
- Number pool results do not change for a read at the current time. One result changes for a read at a past time. The case needs all three of these conditions:
  - the pool has divisions;
  - a branch was created after the read time;
  - an edge on the default branch was open at the read time and closed before that branch was created.

  That branch now counts the node as part of its division. No test covers this case. See "Autonomous decisions".

### Chunk C: the IP pool fix (T039 to T044)

- Tasks: 6. Outcomes: 6 done.
- Commits: `3e1a249e5` (queries and `branch_windows.py`) and `9637a6159` (pool classes and `test_prefix_pool.py`).
- The four `…FetchFree` queries share `_build_allocated_values_query`. Each query keeps its own search for a free range.
- `render_window_filter` returned NULL, not false, for the default branch's window. Inside `none()`, that dropped every child. The filter now also requires `window.origin_name IS NOT NULL`. Only `ipam.py` calls this filter, so the retention and number pool Cypher does not change.
- A first version ran five `NOT EXISTS` subqueries in each window and cost about 10 times the base database hits. The final version reads each edge and its competing edges once per row, then tests the windows in memory.
- Without `branch_agnostic` (the GraphQL query for the next available address), the queries keep the branch filter. In both modes, a missing namespace now returns no row.
- The new module `backend/infrahub/core/node/resource_manager/ip_pool_branch.py` reads the namespace and the resources on the allocating branch and holds both error messages. `get_next` takes an optional `branch`.
- A full prefix pool now raises `PoolExhaustedError` instead of `IndexError`. 7 assertions in `test_prefix_pool.py` changed to match.

### Chunk D: verification, documentation and pre-push checks (T045 to T050)

- Tasks: 6. Outcomes: 5 done, 1 partial (T050).
- Commit: `2e7c97273` (docs, knowledge doc, changelog).
- T046 measured the base and the head one after the other, on the same machine. The approach is not changed: whether the cost is acceptable is for the user to decide.
- T047: `dev/knowledge/backend/query-pattern.md` already had 540 lines on the base, above the range of 200 to 400 lines for `knowledge/`. It now has 554 lines. Splitting the file is left to a separate change.
- T049: the fragments are `changelog/+ip-pool-branch-held-values.fixed.md` and `changelog/+ip-pool-branch-allocation-errors.changed.md`. They use orphan names because no GitHub issue exists.
- T050: the pre-push checks pass. The PR is not opened. A draft PR description is in `branch-agnostic-wip/notes/pr3-description-notes.md` under "Draft PR description".
- `docs.lint` finds `markdownlint-cli2` only after `npm ci` in `docs/` and with `docs/node_modules/.bin` on `PATH`.

### Review fix (after Phase 6)

- Commit: `1d4399593`. It changes only the test file and one changelog fragment. `backend/infrahub` does not change.
- It adds 12 tests in `TestIPPoolReleaseAcrossBranches` (prefix and address pools, IPv4 and IPv6):
  - a value deleted on the default branch and then on branch B is free again;
  - a value held only by a branch whose status is `DELETING` is free on the default branch;
  - a value deleted only on B is not allocated again on B.
- Two deliberate breaks showed that the tests catch a regression. Both files were restored, and `git diff` showed no change:
  - Removing the outranks check in `ipam.py` made the 4 tests of the first case fail.
  - Removing the `DELETING` filter in `branch_windows.py` made the 4 tests of the second case fail.
- The changelog fragment now says that a full prefix pool raises the same error type as an address pool. It no longer says "the same error", because the two messages differ.

### Performance follow-up (after the report, at the user's request)

- Commits: `80919766b` (query) and `4e1b8d2ba` (tests and benchmark).
- A candidate value whose five edges are all on the default branch and still open is kept as taken without the competing-edge reads or the window test. The query splits the two cases with `UNION ALL` inside a nested `CALL`. The default branch is the window whose `origin_name` is NULL.
- The query does not decide this from the code alone. It relies on how writes behave: a write closes the open edge it replaces on the same branch, and the `prefix` and `address` attributes and the `ip_namespace` relationship cannot have `-global-` edges. The subagent checked this in the write code, at these places:
  - attribute value update and delete: `attribute.py:86` and `:348`;
  - node delete: `node.py:703-711`;
  - relationship delete: `relationship.py:620-632`, `:1378`, `:1408` and `:1428`;
  - a peer change creates a new `Relationship` vertex: `relationship/model.py:478` and `:1537`;
  - merge: `bulk_merge.py`;
  - the branch support of a field cannot change: `internal.py:412`, `:746` and `:990`.

  After the follow-up, the orchestrator checked the two remaining write paths:

  - **Writes with an earlier `at`.** A GraphQL request that contains a mutation always writes at the current time (`graphql/app.py:222-224`). An earlier `at` comes only from internal code.
    - An attribute value update closes every open active edge on its branch, whatever the `at` (`core/query/attribute.py:84-86`).
    - A relationship delete closes every open edge on its branch, whatever the `at` (`core/query/relationship.py:620-632`).
    - A node delete closes only the edge it reads at `at` (`core/query/node.py:690-711`). With an earlier `at`, a newer open edge on the same branch stays open, and the new `deleted` edge starts before it. A normal read and the full check both treat that node as existing, and so does the shortcut.
  - **Rollback (`core/rollback.py`, `core/query/rollback.py`).** A rollback first reopens the edges closed in its window, then deletes the edges created in it, in two separate queries. In two cases one branch can hold two open edges for the same field:
    - **Between the two queries.** For that time, the reopened edge and the edge not yet deleted are both open. Merge rollback uses `SINCE_TIMESTAMP` while writes to the branch are blocked (`core/diff/merger/merger.py:249`).
    - **After a schema update rollback that uses `AT_TIMESTAMP`** (`core/schema/update_coordinator.py:384-394`). Suppose another writer changed the same field after the rolled-back write. The rollback reopens the edge from before that write, and the other writer's newer edge also stays open.

    In both cases, a normal read keeps the newest edge, while the shortcut counts both values as taken.
  - **Effect on allocation.** The shortcut only adds rows to the set of taken values, and every other row still goes through the full check. When two edges are open on one branch, the pool can skip a value that is free. In the worst case, it reports a pool with one value left as exhausted. It never hands out a value that a live branch holds. The free-value query on the base read each edge on its own, with no ranking, so it already counted both values as taken in this state.
- Each of the five edges now has its own filter, which includes a test that some branch can see the edge. `PROFILE` shows each filter runs right after the edge is matched. The plan still starts from the `binary_address` index, so competing edges are read only for values in the pool's range.
- The benchmark gained a second dataset, `churn`. It has one old branch, 300 allocated values, and 2,000 values per pool that were created and then deleted on the default branch after that branch was created. The data is built through the node API. The test ids of the first dataset changed to `branches-…`.
- New tests: `TestIPPoolValueChangedOnBranch`, 16 cases for prefix and address pools on IPv4 and IPv6. They cover a value changed on a branch, then deleted or moved on the default branch.
- Two deliberate breaks were caught by the tests:
  - removing `to IS NULL` from the shortcut: 8 failed;
  - removing the default-branch condition: 4 failed.

  `git status` is clean after both.

## Tasks not completed

- T050: the PR against `release-1.12` is not opened, because the user asked for a local branch only. The pre-push checks of T050 are done.

## Cost of an allocation

T046 says to change the approach before review if allocation is significantly slower. The first run measured about 2.3 times the base database hits for a lookup and did not change the approach. The performance follow-up reduced the cost.

Database hits of the free-value query, with the whole lookup in brackets. The figures were the same within 100 hits across two rounds run in opposite order:

| Dataset and pool | Base `17e898643` | After the first run `1d4399593` | After the follow-up `4e1b8d2ba` |
|---|---|---|---|
| 50 live branches, 1,050 values, prefix pool | 52,016 (67,540) | 134,937 (150,482) | 78,291 (93,736) |
| 50 live branches, 1,050 values, address pool | 50,150 (65,607) | 132,525 (148,003) | 73,115 (88,497) |
| One old branch, 2,000 deleted values, prefix pool | 362,626 (416,550) | 829,892 (883,735) | 64,203 (118,048) |
| One old branch, 2,000 deleted values, address pool | 360,844 (414,701) | 958,047 (1,011,827) | 63,611 (117,393) |

- With 50 live branches, a lookup now costs about 1.4 times the base, down from about 2.3 times.
- With one old branch and many deleted values, a lookup now costs about 0.28 times the base. On that dataset, the filter on the `HAS_VALUE` edge drops 4,000 of 4,301 rows, so the other four edges are matched for 300 rows only.
- Why the base costs about 360,000 hits on this dataset was not investigated.
- The number of queries per lookup does not change.

Median wall time in ms (base / first run / follow-up), lookup on the default branch: 33.6 / 90.9 / 76.2 for the prefix pool with 50 branches, and 72.8 / 215.9 / 33.9 with one old branch. Another session was running component tests on the machine at the same time (load average 2.9 to 7.6), so wall time is approximate. Compare database hits instead. Full tables are in `branch-agnostic-wip/notes/pr3-description-notes.md` under "Database hits after the fast path and the per-edge check".

## Local-pass evidence

Every run started from `backend/` in the code worktree. Component tests used testcontainers with `neo4j:2026.05.0-enterprise`, except the 01:20Z and 01:21Z runs of chunk B, which used `neo4j:2026.05.0-community`.

| Test id | Type | Run command | Passed at (ISO 8601) | Environment context | Verbatim pass line |
|---|---|---|---|---|---|
| `tests/unit/core/query/test_branch_windows.py` (13 tests) | unit | `uv run --no-sync pytest tests/unit/core/query/test_branch_windows.py -p no:randomly -q -rA` | 2026-11-04T01:21:47Z | n/a | `13 passed, 17 warnings in 0.05s` |
| `tests/component/core/resource_manager/test_ip_pool_branch_windows.py::TestIPPoolAllocationAcrossBranches` (8 tests, IPv4 and IPv6) | component | `uv run --no-sync pytest tests/component/core/resource_manager/test_ip_pool_branch_windows.py tests/component/core/resource_manager/test_ip_pool_allocation_on_branch.py -p no:randomly -q -rA` | 2026-11-04T02:35:36Z | testcontainers Neo4j | `28 passed, 17 warnings in 60.09s (0:01:00)` |
| `tests/component/core/resource_manager/test_ip_pool_branch_windows.py::TestIPPoolReleaseAcrossBranches` (12 tests) | component | same run as the row above | 2026-11-04T02:35:36Z | testcontainers Neo4j | `28 passed, 17 warnings in 60.09s (0:01:00)` |
| `tests/component/core/resource_manager/test_ip_pool_allocation_on_branch.py::TestIPPoolAllocationOnBranch` (8 tests) | component | same run as the row above | 2026-11-04T02:35:36Z | testcontainers Neo4j | `28 passed, 17 warnings in 60.09s (0:01:00)` |
| `tests/component/core/resource_manager/test_number_pool_branch_windows.py::TestNumberPoolAllocationAcrossBranches` (4 tests) | component | `uv run --no-sync pytest tests/unit/core/query/test_branch_windows.py tests/component/core/resource_manager/ tests/component/core/ipam/ tests/component/graphql/resource_manager/ tests/component/graphql/queries/test_resource_pool.py tests/component/core/agnostic_retirement/ tests/component/core/migrations/graph/m078_retire_agnostic_property_edges/ -p no:randomly -q -n 4` | 2026-11-04T02:14:21Z | testcontainers Neo4j | `785 passed, 2 xfailed, 85 warnings in 371.95s (0:06:11)` |
| `tests/component/core/resource_manager/test_number_pool_query.py::TestNumberPoolReadsWithTwoLiveBranches` (9 new tests; 28 in the file) | component | same run as the row above | 2026-11-04T02:14:21Z | testcontainers Neo4j | `785 passed, 2 xfailed, 85 warnings in 371.95s (0:06:11)` |
| `tests/component/core/resource_manager/test_prefix_pool.py` (20 tests, 7 assertions changed) | component | same run as the row above | 2026-11-04T02:14:21Z | testcontainers Neo4j | `785 passed, 2 xfailed, 85 warnings in 371.95s (0:06:11)` |
| `tests/benchmark/test_node_list_filter.py` (5 cases) | benchmark | `INFRAHUB_LOG_LEVEL=CRITICAL uv run --no-sync pytest tests/benchmark/test_node_list_filter.py -p no:randomly -q --dist=no --benchmark-group-by=name` | 2026-11-04T00:47:32Z | testcontainers Neo4j | `5 passed, 17 warnings in 66.64s (0:01:06)` |
| `tests/benchmark/test_ip_pool_allocation.py::test_ip_pool_next_free` (4 cases) | benchmark | `INFRAHUB_LOG_LEVEL=CRITICAL uv run --no-sync pytest tests/benchmark/test_ip_pool_allocation.py -p no:randomly -q --dist=no --benchmark-group-by=name` | 2026-11-04T02:22:07Z | testcontainers Neo4j, AMD EPYC 9R45 | `4 passed, 17 warnings in 48.51s` |

Runs of the performance follow-up, at `4e1b8d2ba`:

| Test id | Type | Run command | Passed at (ISO 8601) | Environment context | Verbatim pass line |
|---|---|---|---|---|---|
| `tests/component/core/resource_manager/test_ip_pool_branch_windows.py::TestIPPoolValueChangedOnBranch` (16 cases), with `tests/component/core/resource_manager/`, `tests/component/core/ipam/`, `tests/component/graphql/resource_manager/`, `tests/component/graphql/queries/test_resource_pool.py` and `tests/unit/core/query/test_branch_windows.py` | component and unit | `uv run --no-sync pytest tests/component/core/resource_manager/ tests/component/core/ipam/ tests/component/graphql/resource_manager/ tests/component/graphql/queries/test_resource_pool.py tests/unit/core/query/test_branch_windows.py -p no:randomly -q -n 4 -rA` | 2026-11-04T04:53:19Z | testcontainers Neo4j | `781 passed, 2 xfailed, 85 warnings in 398.18s (0:06:38)` |
| `tests/benchmark/test_ip_pool_allocation.py::test_ip_pool_next_free` (8 cases, `branches` and `churn`) | benchmark | `INFRAHUB_LOG_LEVEL=CRITICAL uv run --no-sync pytest tests/benchmark/test_ip_pool_allocation.py -p no:randomly -q --dist=no --benchmark-group-by=name` | 2026-11-04T05:00:12Z | testcontainers Neo4j | `8 passed, 17 warnings in 149.55s` |

The run of 781 tests leaves out `agnostic_retirement/` (27 tests) and `m078` (5 tests), which the run of 785 included. Neither directory changed in the follow-up.

Notes on the evidence:

- The run at 02:14:21Z was made at `9637a6159`. The two later commits change docs, the changelog and `test_ip_pool_branch_windows.py` only. The run at 02:35:36Z covers that test file at its final content, except a docstring change made after that run.
- The 2 `xfailed` tests carry `xfail` markers on the base, in `test_number_pool_attribute_rename.py`.
- The run at 02:14:21Z, by suite: unit `test_branch_windows` 13 passed; `resource_manager/` 263 passed and 2 xfailed; `ipam/` 55 passed; `graphql/resource_manager/` 410 passed; `test_resource_pool.py` 12 passed; `agnostic_retirement/` 27 passed; `m078` 5 passed.
- On the base, the moved IP pool tests and scenarios 3 and 4 failed as expected: `12 failed, 36 passed, 17 warnings in 89.59s` at 2026-11-04T01:06:26Z.

Pre-push checks, all passing on `2e7c97273`:

- `uv run invoke format`
- `uv run invoke lint` (ruff, ty, mypy)
- `uv run ruff check . --exclude python_sdk`
- `uv run ruff format --check --exclude python_sdk .`
- `uv run invoke docs.validate`
- `uv run invoke docs.lint`

The review fix in `1d4399593` passed `uv run invoke format` and `uv run invoke lint`.

## Review findings

Two reviewers ran on `17e898643..2e7c97273`. One covered code, error handling, types and comments. The other covered tests and simplification. No finding was rated critical.

| Severity | File | Finding | Action |
|---|---|---|---|
| high | `test_ip_pool_branch_windows.py` | No test checked that a value becomes free once no live branch holds it. | Fixed in `1d4399593` |
| medium | `test_ip_pool_branch_windows.py` | No IP pool test covered a branch whose status is `DELETING`. | Fixed in `1d4399593` |
| medium (not confirmed) | `ip_pool_branch.py:35-39` | When the pool's link to its namespace still exists but the namespace exists on no live branch, the error label code calls `get_peer`, which raises `NodeNotFoundError`. The user then receives that error instead of `ResourceNotFoundError`. No test covers this case. | Deferred |
| medium | `test_ip_pool_allocation_on_branch.py:55` | Scenarios 3 to 6 run on IPv4 only. | Deferred |
| medium | `ipam.py:132` | The query path without `branch_agnostic` changed (an `OPTIONAL MATCH`, grouping by namespace). No test checks that the GraphQL next-available query ignores a value held only on another branch. | Deferred |
| low | `ipam.py:504, 618, 847` | When the namespace is not active, the GraphQL next-available address query now raises "No addresses available" instead of returning an address. The changelog does not say this. | Deferred |
| low | `resource_manager.py:778-779` | The read at a past time described under chunk B. | Deferred; see "Autonomous decisions" |
| low | `ipam.py:178` | No IP pool test reads at a past time. | Deferred |
| low | `test_branch_windows.py:84` | No unit test checks the `origin_name IS NOT NULL` guard directly. | Deferred |
| low | `test_number_pool_branch_windows.py:75,90` | Two tests repeat tests in `test_number_pool_branch_liveness.py`. | Deferred |
| low | `benchmark/test_ip_pool_allocation.py:259` | The benchmark does not check the value it returns. | Deferred |
| low | `ip_address_pool.py`, `ip_prefix_pool.py` | The `Raises:` sections of `get_next` leave out `ValidationError` and `NodeNotFoundError`. | Deferred |
| low (not confirmed) | `branch_windows.py:19-20` | The comment says importing the branch status enum would cause an import cycle. `core/query/branch.py` imports it at module level. | Deferred |
| low | `m082_reanchor_number_pool_reservations/queries.py:54-59` | A fifth copy of the window logic stays in a shipped migration. The PR description should say so. | Deferred |
| low | `changelog/+ip-pool-branch-allocation-errors.changed.md` | The fragment said the prefix pool raises the same error as the address pool. Only the type is the same. | Fixed in `1d4399593` |
| low (simplification) | `branch_windows.py`, `ipam.py`, `ip_prefix_pool.py`, `ip_address_pool.py`, `ip_pool_branch.py` | The reviewer listed five possible simplifications. Two examples: one entry point for building the windows instead of two, and one helper for the duplicated `_get_next_on_branch` setup in the two pool classes. | Deferred; advisory only |

## Autonomous decisions

- IFC-3511 is not named in `tasks.md`. The Jira ticket describes PR 3, User Story 3, so this run took Phase 5 (T028 to T050).
- The code branch was created in a separate worktree from the latest `origin/release-1.12`, as T028 says. Its upstream is not set.
- This report is written to `opsmill-implement-report-us3.md`, so that the US1 and US2 reports are kept.
- Phase 5 has 23 tasks. After T028, it ran in four chunks: tests (T029 to T033), the shared module (T034 to T038), the IP pool fix (T039 to T044), and verification and documentation (T045 to T050).
- The subagents ticked `tasks.md` but did not commit in the spec worktree. The orchestrator committed the ticks after each chunk, to keep the untracked `branch-agnostic-wip/` folder out of commits.
- The `speckit-checkpoint-commit` skill is not available in this environment. The subagents committed with `git commit` after running the formatters and linters.
- The `after_implement` hooks of `speckit-implement` were skipped inside the chunks. The orchestrator ran the review once at the end.
- The review ran as two reviewers in parallel instead of six in sequence. The reviews only read files, so they cannot conflict.
- **The query approach was not changed after T046 in the first run.** An allocation cost about 2.3 times the database hits of the base. The user then asked for the shortcut for values held on the default branch and the per-edge filter, which brought the cost to about 1.4 times the base. Reading the competing edges one edge at a time, with a shrinking list of branches, was not done: the orchestrator recommended against it because it saves reads only in a rare case, and the user accepted that recommendation.
- **The read at a past time for number pools with divisions now gives a different result** (chunk B). FR-012 requires no change in what number pools allocate. Allocation reads at the current time, where results are the same. The change was accepted as it is, because the result now agrees with what the value fragments already report for such a branch.
- Only the high finding and the factual error in the changelog were fixed. The medium `DELETING` test gap was closed by the same tests. Every other medium and low finding is deferred.

## Suggested next steps

1. Review the free-value query for cost during code review. The user considers about 1.4 times the base database hits with 50 live branches probably acceptable (T046). With one old branch and many deleted values, the query costs less than the base.
2. Decide whether the shortcut may skip a free value after a rollback, as described under "Performance follow-up". It never hands out a value that a live branch holds.
3. Decide whether to fix the medium finding in `ip_pool_branch.py`: a namespace that exists on no live branch can raise `NodeNotFoundError` instead of `ResourceNotFoundError`.
4. Decide whether the change to the number pool read at a past time is acceptable under FR-012, and whether to add a test for it.
5. Run `/pre-ci` in the code worktree, then push `branch-windows-ip-pools-ifc-3508` and open the PR against `release-1.12` (T050). Use the draft in `branch-agnostic-wip/notes/pr3-description-notes.md`. Add the fifth copy of the window logic in migration `m082` and the review fix to that draft.
6. Consider the deferred test gaps: IPv6 for scenarios 3 to 6, the GraphQL next-available query on a branch, and an IP pool read at a past time.
