# Implementation report: User Story 4, convergence after the cascade decision

| | |
|---|---|
| Feature | Branch-agnostic reads, User Story 4 (PR 4, [IFC-3512](https://opsmill.atlassian.net/browse/IFC-3512)) |
| Spec directory | `dev/specs/ifc-3508-branch-agnostic-reads` on `branch-agnostic-reads` |
| Code branch | `agnostic-delete-check-ifc-3508`, in the worktree `.claude/worktrees/agnostic-delete-check-ifc-3508`. Not pushed after `ec178f999` |
| Base commit | `9272f01fb` |
| Head commit | `ed16104a3` |
| Scope | Phase 11 of [tasks.md](tasks.md), T136 to T141, from the decision recorded in the Clarifications session of 2026-11-13 in [spec.md](spec.md) |
| Status | Done |

## Chunk ledger

| Chunk | Tasks | Done / partial / blocked | Commits | Flagged by the subagent |
|---|---|---|---|---|
| Phase 11: Convergence | 6 (T136-T141) | 6 / 0 / 0 | `6c982b779`, `7d81fdbc7`; task ticks `14b653c12` on `branch-agnostic-reads` | See below |

What the subagent flagged:

- `NodeDeleteIndex.index_dependent_links` takes a `skip_cascading` flag. Only the per-branch patterns of other branches pass it, so the request branch's patterns are unchanged.
- The core schema yields a required pattern whose peer kind is the generic `CoreTransformation`, as the task expected.
- With the exclusion, `CoreRepositoryGroup` no longer blocks a repository delete on other branches, because the repository cascades on that relationship. `CoreRepositoryValidator`, `CoreUserValidator` and `CoreFileThread` still block.
- T139 passed before the change, so it works as a guard against a later change that takes the cascade from the request branch's schema.
- T139 adds `AGNOSTIC_TEAM_WITHOUT_CERTIFICATE_CASCADE_SCHEMA` to `backend/tests/helpers/schema/agnostic_retirement.py`.
- T138 creates the repository, GraphQL query, check definitions and transform directly, without git.

## Tasks not completed

None. T136 to T141 are `[X]`.

## Local-pass evidence

All component tests ran against testcontainers Neo4j from the code worktree root. Command for the last run, after the review fix: `uv run pytest backend/tests/component/core/test_node_manager_delete_agnostic.py backend/tests/component/core/test_node_manager_delete.py backend/tests/unit/core/node/test_delete_validator.py -p no:randomly -v`. It started at 2026-11-14T00:32:16Z and ended at 2026-11-14T00:34:17Z: `47 passed, 17 warnings in 114.16s`.

| Test id | Type | Run command | Passed at (ISO 8601) | Environment context | Verbatim pass line |
|---|---|---|---|---|---|
| `test_node_manager_delete_agnostic.py::test_delete_keeps_a_cascade_target_with_a_required_link_back_on_another_branch` (T136, reversed and renamed) | component | as above | 2026-11-14T00:34:17Z (end of run) | testcontainers Neo4j | `PASSED [  8%]` |
| `test_node_manager_delete_agnostic.py::test_delete_keeps_a_peer_created_on_another_branch_through_a_relationship_the_node_cascades_on` (T137) | component | as above | 2026-11-14T00:34:17Z (end of run) | testcontainers Neo4j | `PASSED [ 10%]` |
| `test_node_manager_delete_agnostic.py::test_delete_refused_when_another_branch_schema_does_not_cascade_on_a_required_relationship` (T139) | component | as above | 2026-11-14T00:34:17Z (end of run) | testcontainers Neo4j | `PASSED [ 12%]` |
| `test_node_manager_delete_agnostic.py::test_delete_of_a_repository_keeps_its_imported_nodes_on_another_branch` (T138) | component | as above | 2026-11-14T00:34:17Z (end of run) | testcontainers Neo4j | `PASSED [ 14%]` |
| `test_delete_validator.py::test_repository_imported_nodes_require_their_repository` (T140) | unit | as above | 2026-11-14T00:34:17Z (end of run) | n/a | `PASSED [ 95%]` |
| `test_delete_validator.py::test_dependent_links_skip_the_relationships_a_repository_cascades_on` (T140) | unit | as above | 2026-11-14T00:34:17Z (end of run) | n/a | `PASSED [ 97%]` |
| `test_delete_validator.py::test_dependent_links_keep_another_kind_that_reuses_the_identifier_of_a_cascade` (review fix) | unit | as above | 2026-11-14T00:34:17Z (end of run) | n/a | `PASSED [100%]` |

Failures observed before the change, at 2026-11-14T00:22:04Z, with the same command:

- T136: `ValidationError: Cannot delete AgnosticretireTeam '…'. It is linked to mandatory relationship team on node AgnosticretireCertificate '…' on branch 'branch-keeps-certificate'`.
- T137: the same error on branch `branch-holds-certificate`.
- T138: `ValidationError: Cannot delete CoreRepository '…'. It is linked to mandatory relationship repository on node CoreCheckDefinition …`, naming both check definitions and the `CoreTransformPython` on branch `branch-imports-check`.
- Both T140 unit tests: `TypeError: NodeDeleteIndex.index_dependent_links() got an unexpected keyword argument 'skip_cascading'`.
- T139 passed before the change.
- The review-fix unit test, run against `7d81fdbc7`: `AssertionError: assert set() == {'TestreuseBadge'}`.

`ruff format`, `ruff check` and `mypy` are clean on the changed files. The repo-wide `uv run ruff check . --exclude python_sdk` reports errors in `.specify/extensions/` scripts that this change does not touch.

## Review findings

The review ran four of the six aspects, in two agents: code with comments, and tests with simplify. Errors and types did not apply, because the diff adds no error handling and no new type.

| Severity | File | Finding | Outcome |
|---|---|---|---|
| Low | `delete_validator.py` | The cascade skip ignored the peer kind, so a required link from another kind that reuses the identifier of a cascading relationship was skipped on other branches, although the cascade does not reach that kind. FR-014 refuses that delete. The core schema has no such reuse. | Fixed in `ed16104a3`: the skip compares the peer kind too, listing a generic peer with each kind that uses it, plus a unit test |
| Low | `delete_validator.py` | The docstring said the peer kind is ignored because a required relationship can be declared on a generic. A pattern with a generic peer kind never matches a node, because the query compares the concrete `kind`. | Fixed in `ed16104a3` |
| Low | `delete_validator.py` | `skip_cascading` was a positional flag with a default; `dev/guidelines/backend/python.md` makes such a flag keyword-only. | Fixed in `ed16104a3` |
| Low | tests | Every test schema's cascading relationship is bidirectional, so dropping the direction from the match would pass every test. | Deferred |
| Low | tests | No test where branch B's schema cascades and the request branch's does not (the reverse of scenario 10). | Deferred |
| Low | tests | No-write checks on branch B compare edge counts only; an update that only sets `to` on an edge of B keeps the count. | Deferred |
| Low | `test_delete_validator.py` | The core-schema setup is repeated in two helpers. | Deferred |

## Autonomous decisions

- One chunk for the six tasks, because Phase 11 touches five files.
- The review's first low finding was fixed instead of deferred, because it allowed a delete that FR-014 refuses.
- The report is named after the story, like the reports of user stories 2 to 4, because `opsmill-implement-report.md` holds an earlier run.

## Suggested next steps

1. Run `/pre-ci` in the code worktree.
2. Push `agnostic-delete-check-ifc-3508` and open PR 4 as a draft against `stable`, with the tables of [delete-check-measurements.md](delete-check-measurements.md) in the description. The pull request description should say that this PR lets a repository delete through while other branches hold its imported nodes, and link the follow-ups [IFC-3611](https://opsmill.atlassian.net/browse/IFC-3611), [IFC-3612](https://opsmill.atlassian.net/browse/IFC-3612) and [IFC-3613](https://opsmill.atlassian.net/browse/IFC-3613).
3. Decide whether to add the deferred test findings before review.
