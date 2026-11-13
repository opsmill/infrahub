# Implementation report: User Story 4, deleting a branch-agnostic node checks every live branch

| | |
|---|---|
| Feature | Branch-agnostic reads, User Story 4 (PR 4), [IFC-3512](https://opsmill.atlassian.net/browse/IFC-3512), epic [IFC-3508](https://opsmill.atlassian.net/browse/IFC-3508) |
| Spec directory | `dev/specs/ifc-3508-branch-agnostic-reads/` |
| Scope of this run | Phase 6 of [tasks.md](tasks.md): T051 to T059 |
| Code branch | `agnostic-delete-check-ifc-3508`, in the worktree `.claude/worktrees/agnostic-delete-check-ifc-3508`. Pushed to `origin` at `ec178f999`; `ff2f87474` is not pushed |
| Base commit of the code branch | `11928e7c4` on `origin/stable`, the merge of PR 3 ([#11433](https://github.com/opsmill/infrahub/pull/11433)). The branch was first built on PR 3's tip `956c9aa27`; see "Changes after the report" |
| Head commit of the code branch | `ff2f87474` |
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
- Found while testing this change: after the delete, a node on another branch keeps its optional link to the deleted branch-agnostic node, and resolving that link raises `NodeNotFoundError`. The check on `stable` does not look at other branches, so this predates this PR, and it applies to every optional link, not only to cascades. User Story 5 (PR 5) fixes it:
  - FR-021 (T075): the delete writes a `deleted` edge on each user branch whose own latest edge for the link is `active`;
  - FR-018 (T069): a read of a branch-aware relationship whose peer kind is branch-agnostic returns the peer only if it exists in the read's view.
- After a second review (`/code-review high`), at the user's request, the delete check was replaced by two queries (commits `dd5ab349b`, `d6e753fe6`, `2fe20baea`, `e3dd82f68` and `ec178f999`, by a subagent). The window path took 389 s for a cascade of 10,101 nodes, did not check a branch-agnostic node reached by a cascade from a branch-aware node, and used the request branch's schema for every branch. The design was chosen from measurements of four approaches, recorded in [delete-check-measurements.md](delete-check-measurements.md). FR-014, FR-017, scenarios 5 to 7 of User Story 4, the assumption on branch schemas, the contract, the data model, research R5, T053 and T054 were updated to match.
- After the user's review of `ec178f999`, commit `ff2f87474` adds the relationship direction to the links both queries match. A kind can declare an inbound and an outbound relationship with the same identifier and peer kind, and the queries matched the links of both. A cascade then also deleted the peers of the relationship that does not cascade, and a delete was refused when the peer held the node only through the optional relationship. `stable` matches these links without direction too. The core schema has no kind affected: every pair sharing an identifier there is a hierarchy `parent`/`children` pair, and both are optional and do not cascade. The same commit computes another branch's required links with the index instead of a module function that repeated its logic. Three component tests were added for this commit and have not been run.

## Behavior on the head commit

- Every delete runs `NodeDeleteCascadeQuery` (`backend/infrahub/core/query/node_delete.py`). It follows the cascade in the request branch's window, with one subquery per cascade level, and returns the delete set, whether each node is branch-agnostic, and the required peers outside the delete set on the request branch. A request on `-global-` uses the default branch's window.
- The number of levels is the longest chain in the cascade kind graph. When that graph has a loop, which an explicit `on_delete: cascade` can create, each query follows 10 levels and the query runs again from the last level while that level finds new nodes. The required peers are read only once the cascade is complete.
- When the delete set holds a branch-agnostic node, whether the delete names it or a cascade reaches it, `NodeDeleteOtherBranchesQuery` reads the required links to those nodes in every other live branch's window. Each branch's own schema decides which relationships are required. Branch-aware nodes of the delete set are deleted on the request branch only (FR-016), so on other branches they count as peers that remain.
- One error is raised per blocking link. When the delete set holds a branch-agnostic node, the error names every branch where the link blocks the delete, including the request branch, sorted by name: `Cannot delete <kind> '<id>'. It is linked to mandatory relationship <rel> on node <peer kind> '<peer id>' on branch '<b>'`, or `on branches '<b1>', '<b2>'`. Otherwise the error is the same as on `stable` and names no branch.
- Both queries follow or report a link only when its kind, relationship identifier, direction and peer kind match a relationship that cascades or is required. The direction is seen from the deleted node and is derived from the link's two edges.
- `RelationshipGetByIdentifierInWindowsQuery`, `RelationshipWindowPeersData` and the Python walk are removed. `RelationshipGetByIdentifierQuery` is unchanged from `stable` and is still used by `graphql/queries/relationship.py`.

## Performance, measured locally

No benchmark test was committed. The full measurements, with the setup and every scenario, are in [delete-check-measurements.md](delete-check-measurements.md). Database hits of the delete check, with 50 live branches, 10,000 group memberships and 1,000 `CoreGroupAction` nodes:

| Delete | `stable` | Head (`ec178f999`) |
|---|---|---|
| `CoreStandardGroup` (branch-aware) | 72,424 hits, 43.7 ms | 188 hits, 4.0 ms |
| `CoreAccountGroup` (branch-agnostic) | 72,424 hits, 40.6 ms | 697 hits in 2 queries, 8.3 ms |
| `CoreAccountGroup` with 20 required peers (refused) | 72,424 hits, 34.5 ms | 3,317 hits in 2 queries, 28.3 ms |
| Branch-aware cascade of 51 nodes over 100,000 paths | 702,027 hits, 141.8 ms | 54,976 hits, 23.1 ms |
| Branch-aware cascade of 10,101 nodes, 10,000 of them branch-agnostic | 1,422,153 hits, 442 ms | 1,559,323 hits in 2 queries, 538.6 ms |

The check on `stable` reads every link of the indexed relationship identifiers in the database. The check on the head commit reads only the links of the nodes it reaches. In the last row, the head commit also checks the 10,000 branch-agnostic nodes on the 49 other branches, which `stable` does not.

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
| `test_relationship_query.py::test_query_RelationshipGetByIdentifierQuery_returns_each_window_holding_the_link` (removed with the window query in the redesign) | component | verification run | 2026-11-12T06:43:50Z | testcontainers Neo4j | `PASSED tests/component/core/test_relationship_query.py::test_query_RelationshipGetByIdentifierQuery_returns_each_window_holding_the_link` |
| `test_node_manager_delete_agnostic.py::test_delete_refused_when_a_branch_aware_cascade_reaches_a_branch_agnostic_node_another_branch_requires` | component | `uv run pytest <the three new tests> tests/unit/core/node/test_delete_validator.py -v -p no:cacheprovider` (redesign subagent) | 2026-11-12T22:09:54Z (start of run) | testcontainers Neo4j | `PASSED [ 14%]` |
| `test_node_manager_delete_agnostic.py::test_delete_refused_when_a_relationship_required_only_in_another_branch_schema_holds_the_node` | component | same run | 2026-11-12T22:09:54Z (start of run) | testcontainers Neo4j | `PASSED [ 28%]` |
| `test_node_manager_delete.py::test_delete_cascades_through_a_chain_of_kinds_that_cascade_to_each_other` | component | same run | 2026-11-12T22:09:54Z (start of run) | testcontainers Neo4j | `PASSED [ 42%]` |
| `tests/unit/core/node/test_delete_validator.py` (4 tests, changed to read the cascade triples) | unit | same run | 2026-11-12T22:09:54Z (start of run) | n/a | `7 passed, 17 warnings in 32.07s` |
| Both delete files, `test_delete_validator.py` and `test_relationship_query.py` after the redesign | component and unit | `uv run pytest <paths> -q -p no:cacheprovider` (redesign subagent) | 2026-11-12T22:00:57Z | testcontainers Neo4j | `81 passed, 17 warnings in 134.34s` |
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
| Medium | `delete_validator.py` | The relationships to check come from the request branch's schema, so a kind or required relationship that exists only on another branch's schema is not checked | Fixed by the redesign: each branch's own schema |
| Medium | tests | Cascades are tested one level deep only; the window query test does not cover a peer or link deleted on a branch | Deferred |
| Medium | tests | "Peer also being deleted" has no dedicated test in the window path | Deferred (scenario 4 covers a peer moved off the node) |
| Low | `delete_validator.py` | A branch-aware start node that cascades into a branch-agnostic node uses the single-branch path, so that branch-agnostic node is not checked against other branches (found by the fix subagent) | Fixed by the redesign |
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

1. Run the tests for `ff2f87474`: the unit tests in `tests/unit/core/node/test_delete_validator.py` and the component tests in `tests/component/core/test_node_manager_delete.py` and `tests/component/core/test_node_manager_delete_agnostic.py`.
2. Review the redesign, in particular the error that now names the request branch when a branch-aware delete reaches a branch-agnostic node.
3. Run `/pre-ci` in the code worktree.
4. Push `ff2f87474` and open the PR as a draft against `stable`, with the tables of [delete-check-measurements.md](delete-check-measurements.md) in the description.
