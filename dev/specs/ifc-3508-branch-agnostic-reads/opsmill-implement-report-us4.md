# Implementation report: User Story 4, deleting a branch-agnostic node checks every live branch

| | |
|---|---|
| Feature | Branch-agnostic reads, User Story 4 (PR 4), [IFC-3512](https://opsmill.atlassian.net/browse/IFC-3512), epic [IFC-3508](https://opsmill.atlassian.net/browse/IFC-3508) |
| Spec directory | `dev/specs/ifc-3508-branch-agnostic-reads/` |
| Scope of this run | Phase 6 of [tasks.md](tasks.md): T051 to T059 |
| Code branch | `agnostic-delete-check-ifc-3508`, local only, in the worktree `.claude/worktrees/agnostic-delete-check-ifc-3508`, with no upstream |
| Base commit of the code branch | `11928e7c4` on `origin/stable`, the merge of PR 3 ([#11433](https://github.com/opsmill/infrahub/pull/11433)). The branch was first built on PR 3's tip `956c9aa27`; see "Changes after the report" |
| Head commit of the code branch | `0934010e0` |
| Base commit of `branch-agnostic-reads` | `4e344f789` |
| Wall-clock time | 2026-11-12T05:45Z to about 06:55Z |
| Status | DONE for T051 to T058. T059 is partly done: the pre-push checks pass for this PR's code, and the PR is not opened. Nothing is pushed. |

## Instructions from the user that change the tasks

- The PR targets `stable`. PR 3 now targets `stable` too, so this branch is stacked on PR 3 instead of on `release-1.12`.
- No benchmark test is committed. T057 is replaced by a local measurement with a scratch script that stays outside the repository.
- The work is in a new worktree. If a PR is opened, it must be a draft.

## Chunk ledger

The orchestrator created the worktree (T051) before the first chunk. After each chunk, the orchestrator committed the task ticks in `tasks.md` on `branch-agnostic-reads`: `f0dd74d6f`, `da7fe4516` and `dfb985cb4`.

### Chunk 1: tests (T052)

- Tasks: 1. Outcome: 1 done.
- Commit: `034a06bb9`.
- No existing schema fixture had a required link from a branch-aware kind to a branch-agnostic kind together with a cascade. The chunk added `AGNOSTIC_DELETE_SCHEMA` to `backend/tests/helpers/schema/agnostic_retirement.py` and left `AGNOSTIC_RETIREMENT_SCHEMA` unchanged.
- Scenarios 1 to 3 failed on the base with `DID NOT RAISE <class 'infrahub.exceptions.ValidationError'>`. Scenarios 4 and 5 passed.

### Chunk 2: the delete check (T053 to T057)

- Tasks: 5 (T057 replaced by a local measurement). Outcomes: 5 done.
- Commits: `966834af6` (window mode of the query) and `4c1ff0cc2` (validator).
- `NodeManager.delete` needs no change (T055).
- The window mode starts from the ids of the delete set. It reads each group of edges once per row and tests the windows in memory, as PR 3 does for IP pools.
- The first version raised one error per branch and per peer. With 20 required peers inherited by 50 branches, it raised 1,020 errors. The review changed this (see "Review findings").

### Chunk 3: changelog and pre-push checks (T058 and T059)

- Tasks: 2. Outcomes: 1 done, 1 partial (T059: the PR is not opened).
- Commit: `4fb189cc1`. The review fixes rewrote the fragment in `2acbbce84`.
- Pre-push checks:
  - `uv run invoke format` passes.
  - `uv run invoke lint` passes (ruff, ty and mypy).
  - `uv run invoke docs.validate` passes.
  - The whole-repo `uv run ruff check . --exclude python_sdk` and `uv run ruff format --check --exclude python_sdk .` fail only on scripts in `.specify/extensions/`, which commit `76e23741d` already put on `stable`. This PR changes no file there.

### Review fixes

- Commits: `cbaf4acb2` (tests), `cbb9b29a1` (query class and validator), `2acbbce84` (changelog).
- The spec documents were updated to match in `34a6b50cb`:
  - `contracts/user-visible-behavior.md`
  - `research.md` R5
  - `data-model.md`
  - `tasks.md`

## Changes after the report

- The branch was rebased onto `origin/stable` at `11928e7c4`, after PR 3 was merged. Two import conflicts in `delete_validator.py` came from `aff8c6ba2`, which moved `Iterable` to `collections.abc`, and were resolved by keeping both changes. The earlier commits now have new ids:
  - `034a06bb9` is `9cd03ae67`;
  - `966834af6` is `bf634cfe8`;
  - `4c1ff0cc2` is `dfe94156c`;
  - `4fb189cc1` is `9d9dd79bc`;
  - `cbaf4acb2` is `50a38af9e`;
  - `cbb9b29a1` is `09ca2bbdf`;
  - `2acbbce84` is `7607c75e2`.
- At the user's request, a cascade on another branch no longer blocks the delete by itself. Only a required relationship blocks it, on every branch (commit `0934010e0`). The cascade error message is removed. Scenario 3 of the spec, FR-014, the contract, research R5 and T054 were updated to match.
- Known limit found while testing this change: after the delete, a node on another branch keeps its optional link to the deleted branch-agnostic node, and resolving that link raises `NodeNotFoundError`. The check on `stable` does not look at other branches, so this predates this PR. It applies to every optional link, not only to cascades.

## Behavior on the head commit

- Deleting a branch-agnostic node runs the existing walk in the request branch's window. That walk decides which nodes are deleted.
- In every other live branch's window, only the branch-agnostic nodes of that delete set count as deleted, because a cascade removes a branch-aware node on the request branch only (FR-016). The delete is refused when a node with a required relationship to a deleted node remains on that branch.
- One error is raised per blocking link. It names every branch where the link blocks the delete, sorted by name: `Cannot delete <kind> '<id>'. It is linked to mandatory relationship <rel> on node <peer kind> '<peer id>' on branch '<b>'`, or `on branches '<b1>', '<b2>'`.
- Deleting only branch-aware nodes runs the same query and walk as before (FR-017).
- The window mode is its own query class, `RelationshipGetByIdentifierInWindowsQuery`, with rows of type `RelationshipWindowPeersData`. The single-branch `RelationshipGetByIdentifierQuery` renders the same Cypher as on the base.

## Performance, measured locally

No benchmark test was committed. Scratch script: `/tmp/claude-1000/-home-ubuntu-opsmill-infrahub--claude-worktrees-branch-agnostic-reads/42e02d1b-d373-40d7-b9c8-a83a314574aa/scratchpad/test_zz_scratch_delete_perf.py`. Results: `perf.json` in the same folder.

Setup: 50 live branches, 10,000 group memberships (100 standard groups with 100 tags each) and 1,000 `CoreGroupAction` nodes. Database hits come from `PROFILE`, summed over the queries of the check. Time is the median of 5 runs. The base is `034a06bb9`.

| Delete | Base | Head |
|---|---|---|
| `CoreAccountGroup` (branch-agnostic) | 72,424 hits, 44.6 ms | 359 hits, 2.5 ms |
| Branch-agnostic node with 20 required peers (refused) | 72,424 hits, 39.4 ms, 20 errors | 1,380 hits, 20 errors |
| `CoreStandardGroup` (branch-aware) | 72,424 hits | 72,424 hits (same query) |

The window mode costs less than the base because it starts from the ids being deleted. The base reads every link of the indexed relationships.

## Tasks not completed

- T059: the pre-push checks pass, but the PR is not opened, because this run does not push. If it is opened, it must be a draft against `stable`.

## Local-pass evidence

After the rebase and the cascade change, all of `test_node_manager_delete_agnostic.py`, `test_node_manager_delete.py` and `test_relationship_query.py` were run from the repository root with `uv run pytest <the three files> -q -p no:cacheprovider -rA`. The run ended at 2026-11-12T16:49:45Z with `75 passed, 17 warnings in 115.95s (0:01:55)`, and every test of `test_node_manager_delete_agnostic.py` is listed as PASSED.

All runs were from `backend/`, against Neo4j 2026.05.0-enterprise started by testcontainers.

The command for the orchestrator's verification run was `uv run --no-sync pytest tests/component/core/test_node_manager_delete_agnostic.py tests/component/core/test_node_manager_delete.py tests/unit/core/node/test_delete_validator.py tests/component/core/test_relationship_query.py -k "not RelationshipGetPeer or RelationshipGetByIdentifier" -p no:randomly -q -rA`. It started at 2026-11-12T06:43:50Z and ended with `62 passed, 17 deselected, 17 warnings in 110.97s (0:01:50)`. The output filter kept the last 60 lines only, so three tests show only the summary line from that run. The fix subagent's run at 06:39:11Z (`36 passed`) lists them as PASSED.

| Test id | Type | Run command | Passed at (ISO 8601) | Environment context | Verbatim pass line |
|---|---|---|---|---|---|
| `test_node_manager_delete_agnostic.py::test_delete_refused_when_a_branch_holds_a_required_peer` | component | verification run | 2026-11-12T06:43:50Z (06:39:11Z by the fix subagent) | testcontainers Neo4j | `62 passed, 17 deselected, 17 warnings in 110.97s (0:01:50)` |
| `test_node_manager_delete_agnostic.py::test_delete_refused_when_a_branch_inherits_the_required_link_from_before_it_was_created` | component | verification run | 2026-11-12T06:43:50Z (06:39:11Z by the fix subagent) | testcontainers Neo4j | `62 passed, 17 deselected, 17 warnings in 110.97s (0:01:50)` |
| `test_node_manager_delete_agnostic.py::test_delete_keeps_a_cascade_target_with_an_optional_link_back_on_another_branch` | component | run after the rebase | 2026-11-12T16:49:45Z (end of run) | testcontainers Neo4j | `PASSED backend/tests/component/core/test_node_manager_delete_agnostic.py::test_delete_keeps_a_cascade_target_with_an_optional_link_back_on_another_branch` |
| `test_node_manager_delete_agnostic.py::test_delete_succeeds_and_cascades_only_on_the_request_branch` | component | verification run | 2026-11-12T06:43:50Z | testcontainers Neo4j | `PASSED tests/component/core/test_node_manager_delete_agnostic.py::test_delete_succeeds_and_cascades_only_on_the_request_branch` |
| `test_node_manager_delete_agnostic.py::test_delete_of_a_branch_aware_node_checks_only_the_request_branch` | component | verification run | 2026-11-12T06:43:50Z | testcontainers Neo4j | `PASSED tests/component/core/test_node_manager_delete_agnostic.py::test_delete_of_a_branch_aware_node_checks_only_the_request_branch` |
| `test_node_manager_delete_agnostic.py::test_delete_refused_when_a_cascade_target_with_a_required_link_back_stays_on_another_branch` | component | verification run | 2026-11-12T06:43:50Z | testcontainers Neo4j | `PASSED tests/component/core/test_node_manager_delete_agnostic.py::test_delete_refused_when_a_cascade_target_with_a_required_link_back_stays_on_another_branch` (failed before the fix at 06:29:33Z with `DID NOT RAISE`) |
| `test_node_manager_delete_agnostic.py::test_delete_ignores_a_required_link_to_a_branch_aware_cascade_target_on_another_branch` | component | verification run | 2026-11-12T06:43:50Z | testcontainers Neo4j | `PASSED tests/component/core/test_node_manager_delete_agnostic.py::test_delete_ignores_a_required_link_to_a_branch_aware_cascade_target_on_another_branch` |
| `test_node_manager_delete_agnostic.py::test_delete_checks_a_branch_aware_node_deleted_with_a_branch_agnostic_one_on_the_request_branch_only` | component | verification run | 2026-11-12T06:43:50Z | testcontainers Neo4j | `PASSED tests/component/core/test_node_manager_delete_agnostic.py::test_delete_checks_a_branch_aware_node_deleted_with_a_branch_agnostic_one_on_the_request_branch_only` |
| `test_node_manager_delete_agnostic.py::test_delete_on_a_user_branch_refused_when_the_default_branch_holds_a_required_peer` | component | verification run | 2026-11-12T06:43:50Z | testcontainers Neo4j | `PASSED tests/component/core/test_node_manager_delete_agnostic.py::test_delete_on_a_user_branch_refused_when_the_default_branch_holds_a_required_peer` |
| `test_node_manager_delete_agnostic.py::test_delete_refused_names_every_blocking_branch_in_one_error` | component | verification run | 2026-11-12T06:43:50Z | testcontainers Neo4j | `PASSED tests/component/core/test_node_manager_delete_agnostic.py::test_delete_refused_names_every_blocking_branch_in_one_error` |
| `test_node_manager_delete_agnostic.py::test_delete_keeps_a_cascade_target_that_does_not_declare_the_relationship_on_another_branch` | component | run after the rebase | 2026-11-12T16:49:45Z (end of run) | testcontainers Neo4j | `PASSED backend/tests/component/core/test_node_manager_delete_agnostic.py::test_delete_keeps_a_cascade_target_that_does_not_declare_the_relationship_on_another_branch` |
| `test_relationship_query.py::test_query_RelationshipGetByIdentifierQuery_returns_each_window_holding_the_link` | component | verification run | 2026-11-12T06:43:50Z | testcontainers Neo4j | `PASSED tests/component/core/test_relationship_query.py::test_query_RelationshipGetByIdentifierQuery_returns_each_window_holding_the_link` |
| `tests/component/graphql/mutations/ -k delete` (existing suite) | component | `uv run --no-sync pytest tests/component/graphql/mutations/ -k delete -p no:randomly -q` | 2026-11-12T06:41:12Z (fix subagent) | testcontainers Neo4j | `15 passed, 173 deselected` |

No E2E test was added. The user approved the E2E exception for this feature on 2026-10-30 (T014).

## Review findings

The review ran the six aspects of `speckit-review-run` (code, tests, errors, comments, types, simplify) in four parallel agents over `956c9aa27..4fb189cc1`.

| Severity | File | Finding | Status |
|---|---|---|---|
| High | `delete_validator.py` | In another branch's window, a branch-aware node reached by a cascade counted as deleted, so its required link to the deleted node on that branch was not checked | Fixed in `cbb9b29a1`, test in `cbaf4acb2` |
| High | `delete_validator.py` | One error per branch and per peer: 10,000 required peers on 50 branches would build about 510,000 errors | Fixed: one error per link, listing the branches |
| High | `delete_validator.py` | A cascade block said "mandatory relationship" for an optional relationship, and named a path the peer kind does not have | Fixed: separate cascade message, path `<kind>.<rel>`. The cascade error was later removed at the user's request (see "Changes after the report") |
| High | `query/relationship.py` | `window_source_ids=None` switched between two queries, so `window_name` was optional, and `get_as_type` would turn a null into `"None"` | Fixed: separate query class with a required `window_name` |
| High | tests | The fallback to the deleted node's relationship and a delete requested on a user branch were not tested | Fixed: tests added |
| High | `errors/validation.py` (GraphQL) | A delete mutation keys errors by path, so two blocking peers of the same kind through the same relationship show as one error | Deferred: the single-branch delete already behaves this way; the grouping per link reduces it to one entry per peer |
| Medium | `delete_validator.py` | A mixed delete set checked its branch-aware node against other branches | Fixed |
| Medium | `delete_validator.py` | `defaultdict` fields annotated as `dict`; the cascade check repeated in two places | Fixed |
| Medium | changelog | "on any other branch" did not match the code | Fixed |
| Medium | tests | No test with two blocking branches | Fixed |
| Medium | `delete_validator.py` | The relationships to check come from the request branch's schema, so a kind or required relationship that exists only on another branch's schema is not checked | Deferred |
| Medium | tests | Cascades are tested one level deep only; the window query test does not cover a peer or link deleted on a branch | Deferred |
| Medium | tests | "Peer also being deleted" has no dedicated test in the window path | Deferred (scenario 4 covers a peer moved off the node) |
| Low | `delete_validator.py` | A branch-aware start node that cascades into a branch-agnostic node uses the single-branch path, so that branch-agnostic node is not checked against other branches (found by the fix subagent) | Deferred |
| Low | `query/relationship.py` | Two `Node` vertices with the same uuid in one window could return a duplicate row | Deferred: no write path is known to create this |
| Low | tests, docstrings | `# type: ignore[attr-defined]` in tests, repeated identifier strings, vague wording in one comment | Deferred |

## Autonomous decisions

- The code branch is based on PR 3's branch, not on bare `stable`, because this story needs `branch_windows.py`, which only PR 3 adds. PR 3 targets `stable` and its branch has no commit behind `origin/stable`, so this PR targets `stable` and is stacked on PR 3.
- The orchestrator created the worktree (T051) itself and ticked the tasks in `tasks.md` on `branch-agnostic-reads`, because the spec directory is not on the code branch.
- Phase 6 was split into three chunks: tests, implementation with measurement, then changelog with checks.
- The review agents were run in parallel, two aspects per agent for errors with comments and for types with simplify.
- High findings were fixed by one subagent. The tests subagent's two "High" gaps were fixed in the same pass. The GraphQL error flattening was deferred because it predates this change.
- Behavior change from the review fix: a branch-agnostic node cannot be deleted while another live branch holds one of its branch-aware cascade targets whose relationship back to it is required. The cascade removes that target on the request branch only, so the target would keep an empty required relationship on the other branch.
- The error contract changed from one error per branch and peer to one error per link naming all its branches. `contracts/user-visible-behavior.md` was updated to match.

## Suggested next steps

1. Review the behavior change and the grouped error format above.
2. Decide whether to address the deferred findings in this PR, in particular the schema of other branches and the branch-aware start node that cascades into a branch-agnostic node.
3. Run `/pre-ci` in the code worktree.
4. Push the branch and open the PR as a draft against `stable`, with the performance table above in the description.
