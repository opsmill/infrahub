# Implementation report: pull request 1, storage, branch and upgrade

- **Feature**: owners and sources of nodes, attributes and relationships (advanced RBAC, phase P1), storage option E
- **Jira**: [IFC-3626](https://opsmill.atlassian.net/browse/IFC-3626), in the epic [IFC-3625](https://opsmill.atlassian.net/browse/IFC-3625)
- **Spec directory**: `dev/specs/infp-753-rbac-owners-option-e`
- **Branch**: `gma-20261117-ifc3626`, based on `gma-infp753-advanced-rbac`, which is based on `develop` (`ee2d2dc402`)
- **Base commit of the run**: `5293461a02` (the spec directory, with the tasks of this branch not ticked). This commit is the head of the feature branch.
- **Head commit**: the head of the branch. On 2026-11-18 the commits of the run and of the three review rounds were squashed into a few commits (section 6). The commit SHAs in sections 2 and 5 name the commits before the squash. They are not on the branch after the squash.
- **Date of the run**: 2026-11-17, 08:30 to 12:00 UTC
- **Scope**: the tasks of "1. Storage, branch and upgrade" in tasks.md ("Pull Request Split"). The run did not build pull requests 2 and 3.
- **State**: DONE for pull request 1, with 1 task open (T144) and 3 tasks partial. The findings of three review rounds are fixed or recorded (section 5).

The code comes from the local branch `rbac-owners-option-e-impl-infp-753`, which holds the whole feature. Each chunk took the final state of the files of its tasks, and cut the code of pull requests 2 and 3.

## 1. Outcome

| Item | Count |
|---|---|
| Tasks of pull request 1 | 71 |
| Done | 67 |
| Partial (code present, one test waits for a later pull request) | 3 |
| Open | 1 |
| Blocked | 0 |

## 2. Chunk ledger

Each chunk ran in a subagent with a clean context. The chunks ran one after the other.

| Chunk | Content | Tasks | Done / partial / blocked | Commits |
|---|---|---|---|---|
| 1 | Database layer: graph schema, owner states, queries, repository, writer, input | 13 | 13 / 0 / 0 | `f2ce844291` |
| 2 | Database layer: order of sources, resolver, node delete, filters | 8 | 7 / 1 / 0 | `823bcbe757` |
| 3 | Database layer: owners that profiles and object templates give | 7 | 5 / 2 / 0 | `c1fdfe109b` |
| 4 | Database layer: owners of single fields, node sources | 8 | 8 / 0 / 0 (T120 completed in chunk 5) | `c883a7b307` |
| 5 | Branch layer: diff, merge, rebase, conflicts, labels, changelog | 10 | 10 / 0 / 0 | `399340def1` |
| 6 | Branch layer: profiles, templates, field owners and sources in the diff and the merge | 6 | 6 / 0 / 0 | `93957d0968` |
| 7 | Upgrade: graph migrations, owner kind check, report command, kind change | 10 | 10 / 0 / 0 | `32b667ebb0`, `324cd82c56` |
| 8 | Upgrade: schema migrations of fields with owners, object conversion | 5 | 5 / 0 / 0 | `aaba630d87`, `9ca4da0b6e` |
| 9 | Polish: benchmarks, internal documentation, changelog, generated files, lint, full suites | 4 | 3 / 0 / 0, 1 open | `a49dd5afd9`, `9a66a3d280`, `9e620465b1` |
| Review | Check and fix of the review findings | | | `173f416e9b`, `5eb3d0d0ec`, `8d76e83f30` |

Points that the subagents reported:

- **Chunk 4**: after an attribute can have several owners, the existing test `test_merge_diff_changelogs` failed. Chunk 5 ported the owner diff, and the test passes again without a change to the test.
- **Chunk 5**: `conflicts_extractor.py` needs no change (T049). The owner list is one diff property, so the existing extractor reports the conflict.
- **Chunk 7**: the migrations need no register step. `GRAPH_VERSION` is 86. The owner kind check changed 11 existing test files, which now use an account as owner in place of a person.
- **Chunk 8**: for the object conversion, `store_owner_states` in `graphql/mutations/main.py` and `after_save` in `core/node/create.py` came with this pull request. Both have a caller.
- **Chunk 9**: two misses found by a comparison with the source branch and fixed. `test_graph_constraints.py` failed on Neo4j with the new index. `test_owner_lookup.py` was not ported.
- **All chunks**: the subagents ported the files directly and used plain `git commit`. They did not invoke the `speckit-implement` and `speckit-checkpoint-commit` skills.

## 3. Tasks not completed

| Task | State | Reason |
|---|---|---|
| T144 | Open | This pull request holds `test_no_owner_overhead.py` and `conftest.py`, and they pass. The spike test `test_plain_cypher.py` stays on the branch `rbac-owners-option-e-impl-infp-753`. `test_owner_queries.py` writes owners through the GraphQL owner API, and `test_change_check_overhead.py` needs the change check, so a later pull request adds them. The numbers in measurements.md come from the branch `rbac-owners-option-e-impl-infp-753` and are not measured again. |
| T053 | Partial, ticked | The code is present. Its only test reads `updated_at` through GraphQL. Pull request 2 adds the test. |
| T070 | Partial, ticked | All tests are ported. One of them came in chunk 5, with the owner diff. No test is left out. |
| T071 | Partial, ticked | `test_owners_of_the_create_win_over_the_owners_that_the_template_gives` needs the GraphQL create with owners. Pull request 2 adds it. |

T149, T150 and T151 stay open in tasks.md, because each pull request does its part. The part of this pull request is done, except the changelog (T149): the maintainer decided on 2026-11-17 that one consolidated changelog comes when all pull requests are in the feature branch, so this pull request holds no fragment. Done: no generated file changes except the CLI reference of `infrahub db`, and format and lint pass.

## 4. Local-pass evidence

One line is one test file, with the number of tests of the run. All component runs used a Neo4j testcontainer. The commands ran from the root of the worktree with `uv run pytest`. Times are UTC, on 2026-11-17.

| Test file (under `backend/tests/`) | Type | Run command (after `uv run pytest`) | Passed at | Verbatim pass line |
|---|---|---|---|---|
| `unit/core/ownership/test_input.py` | unit | `backend/tests/unit/core/ownership/test_input.py -q` | 08:37:27 | `40 passed, 1 warning in 0.29s` |
| `component/core/ownership/test_storage.py`, `test_owner_sets.py` | component | `backend/tests/component/core/ownership -q -n 2 -o session_timeout=7000` | 08:38:22 | `21 passed, 3 warnings in 47.68s` |
| `unit/core/ownership/test_resolution.py` | unit | `backend/tests/unit/core/ownership/test_resolution.py -q` | 08:42:26 | `29 passed, 1 warning in 0.06s` |
| `component/core/ownership/test_resolver.py`, `test_filter.py` | component | `backend/tests/component/core/ownership/ -n 2 -q -o session_timeout=7000` | 08:44:46 | `67 passed, 3 warnings in 129.76s (0:02:09)` |
| `component/core/ownership/test_profile_owners.py`, `component/templates/test_template_owners.py` | component | `backend/tests/component/core/ownership/test_profile_owners.py backend/tests/component/templates/test_template_owners.py backend/tests/unit/core/ownership/test_resolution.py -n 2 -o session_timeout=7000 -q` | 08:50:51 | `88 passed, 3 warnings in 96.92s (0:01:36)` |
| `component/core/ownership/test_attribute_owners_and_sources.py` | component | `backend/tests/component/core/ownership/test_attribute_owners_and_sources.py -q -p no:cacheprovider` | 08:58:26 | `4 passed, 1 warning in 33.23s` |
| `component/core/diff/merge/test_ownership_diff.py`, `test_ownership_merge.py`, `test_ownership_rebase.py`, helper `_ownership.py` | component | `backend/tests/component/core/diff/merge/test_ownership_diff.py backend/tests/component/core/diff/merge/test_ownership_merge.py backend/tests/component/core/diff/merge/test_ownership_rebase.py backend/tests/component/core/changelog -n 2 -o session_timeout=7000 -q` | 09:13:19 | `84 passed, 3 warnings in 109.71s (0:01:49)` |
| `component/core/diff/merge/test_sources_merge.py` | component | `backend/tests/component/core/diff/merge/test_sources_merge.py backend/tests/component/core/diff/merge/test_ownership_merge.py -n 2 -o session_timeout=7000 -q` | 09:27:55 | `42 passed, 3 warnings in 106.93s (0:01:46)` |
| `component/cli/test_ownership_report.py`, `component/core/migrations/graph/test_close_repository_owner_edges.py`, `test_create_no_owner_vertex.py`, `test_hide_replaced_branch_attribute_owners.py`, `component/core/migrations/schema/test_node_kind_update_owners.py`, `component/core/ownership/test_owner_kinds.py`, `unit/core/branch/test_tasks.py` | component, unit | these 7 files, `-n 2 -o session_timeout=7000 -q` | 09:31:45 | `41 passed, 3 warnings in 71.18s (0:01:11)` |
| Existing tests changed for the owner kind check: `component/core/changelog/test_diff.py`, `test_enrichment.py`, `test_models.py`, `component/core/diff/diff_calculator/test_base_updates.py`, `test_relationships.py`, `component/core/test_node.py`, `test_node_manager_prefetch_metadata.py`, `test_reads_by_value_on_branch.py`, `component/query/test_node_agnostic_retirement_query.py` | component | these files with `backend/tests/component/core/migrations backend/tests/component/cli backend/tests/unit/cli backend/tests/component/core/test_attribute.py backend/tests/component/core/test_relationship.py backend/tests/component/core/ownership backend/tests/component/templates`, `-n 2 -o session_timeout=7000 -q` | 09:44:33 | `813 passed, 2 skipped, 4 warnings in 693.02s (0:11:33)` |
| `integration/diff/test_diff_update.py`, users of `test_data/dataset04.py` | integration, component | the file list of chunk 7, `-n 2 -o session_timeout=7000 -q` | 09:50:00 | `447 passed, 3 warnings in 304.01s (0:05:04)` |
| `component/graphql/mutations/test_object_conversion.py`, `component/core/migrations/schema/test_owner_field_migrations.py`, `test_node_remove_owners.py` | component | `backend/tests/component/graphql/mutations/test_object_conversion.py backend/tests/component/core/migrations/schema/test_owner_field_migrations.py backend/tests/component/core/migrations/schema/test_node_remove_owners.py backend/tests/component/core/migrations/schema/test_node_kind_update_owners.py -n 2 -o session_timeout=7000` | 09:55:02 | `34 passed, 3 warnings in 73.69s (0:01:13)` |
| `query_benchmark/ownership/conftest.py`, `test_no_owner_overhead.py`, `test_plain_cypher.py` | benchmark | `INFRAHUB_OWNERSHIP_BENCHMARK_DEVICES=300 INFRAHUB_OWNERSHIP_BENCHMARK_GENERATOR_NODES=300 uv run pytest backend/tests/query_benchmark/ownership -o session_timeout=7000 -q -p no:cacheprovider` | 10:14:44 | `13 passed, 1 warning in 269.99s (0:04:29)` |
| `component/core/graph/test_graph_constraints.py` | component | `INFRAHUB_DB_TYPE=neo4j uv run pytest backend/tests/component/core/graph/test_graph_constraints.py -q -p no:cacheprovider -rs` | 10:18:53 | `5 passed, 2 skipped, 1 warning in 18.64s` |
| `component/core/ownership/test_owner_lookup.py` | component | `backend/tests/component/core/graph/test_graph_constraints.py backend/tests/component/core/ownership/test_owner_lookup.py -q -p no:cacheprovider` | 10:18:21 | `5 passed, 4 skipped, 1 warning in 22.66s` |
| Review fix: `test_ownership_merge.py::test_stored_conflict_with_one_owner_id_as_value_gives_that_owner_at_the_merge` | component | `backend/tests/component/core/diff/merge/test_ownership_merge.py -k "stored_conflict_with_one_owner" -o session_timeout=7000 -q` | 11:36:26 | `1 passed, 35 deselected, 1 warning in 32.20s` |
| Review fix: `test_ownership_rebase.py`, 2 tests with `no_owner_vertex` in the name | component | `backend/tests/component/core/diff/merge/test_ownership_rebase.py -k "no_owner_vertex" -o session_timeout=7000 -q` | 11:40:00 | `2 passed, 6 deselected, 1 warning in 25.18s` |
| Review fix: `test_owner_field_migrations.py::test_attribute_removal_closes_the_source_and_the_owner_that_are_the_same_node` | component | `backend/tests/component/core/migrations/schema/test_owner_field_migrations.py -k "removal_closes_the_source" -o session_timeout=7000 -q` | 11:46:59 | `1 passed, 11 deselected, 1 warning in 29.13s` |

Full suites, after chunk 9 and before the review fixes, with `INFRAHUB_DB_TYPE=neo4j`:

- `uv run pytest backend/tests/unit -n 2 -o session_timeout=7000 -q -p no:cacheprovider`, 10:21:23: `5382 passed, 6 warnings in 59.38s`
- `uv run pytest backend/tests/component -n 2 -o session_timeout=14000 -q -p no:cacheprovider`, 11:25:35: `5635 passed, 20 skipped, 6 xfailed, 1 xpassed, 14 warnings, 9 errors in 3830.72s (1:03:50)`
- The 9 errors are in `component/git` (import error `Too few arguments for typing.Generator`) and `component/test_lock.py` (`'Server' object has no attribute 'close_clients'`). This branch does not change these files. The subagent read the cause as the Python 3.12 virtual environment of the VM. Nobody confirmed this on another Python version.

Regression run after the review fixes, 11:53:06: `169 passed, 3 warnings in 295.87s (0:04:55)` (diff merge tests, attribute removal and rollback migration tests, branch, rebase, branch delete, merge rollback).

No E2E test is in this pull request. The E2E tests of the feature go through the GraphQL owner API, so they come with pull request 2.

## 5. Review findings

Review mode: command (/code-review), effort medium, on `5293461a02..9e620465b1`.

The review ran no test. A subagent then checked the 6 findings that can lose or corrupt owner data. A finding counts as confirmed only with a test that fails before the fix.

| # | Severity | File | Finding | Result |
|---|---|---|---|---|
| 1 | high | `core/diff/merger/exclusion_plan.py` | A stored diff from before the upgrade holds one owner ID as value. A conflict resolved to the diff branch then removed all owners at the merge. | Confirmed, fixed in `173f416e9b` |
| 2 | high | `core/diff/merger/merger.py` | The merge fails when the branch deleted a node and the default branch changed its owners. | Not real. The conflict enricher gives a node conflict that cannot be resolved, and the merge is refused before the write. |
| 3 | high | `core/ownership/queries.py`, `core/query/branch.py` | The `NoOwner` vertex can be deleted, and two later writes can create two vertices. | Confirmed by another path: the delete and the rebase of a branch deleted the vertex. Fixed in `5eb3d0d0ec`. No path found through the rollback. |
| 4 | high | `core/ownership/queries.py` | The node delete does not close the owner edges of a branch-agnostic attribute. | Not real. `RetireNodeAgnosticFieldsQuery` closes them after the delete. On a user branch, the `deleted` edge on that branch is the design. |
| 5 | high | `core/migrations/query/owner_set_attribute.py` | A schema change on the default branch does not close the owner set of a branch-agnostic profile or template. A rename leaves two sets active. | Confirmed, fixed in `feca42f7fe` with option B (section 6) |
| 6 | high | `core/migrations/query/attribute_remove.py` | The removal of an attribute closes one edge only when the same node is its owner and its source. | Confirmed, fixed in `8d76e83f30` |
| 7 | medium | `core/changelog/diff.py` | A bare owner ID of an old diff goes under `owners`, not `owner`, in the changelog. | Deferred |
| 8 | medium | `core/ownership/filter.py` | The "no owner" filter does a list lookup for each node of the kind. | Deferred. measurements.md gives the measured time of this filter. |
| 9 | low | `core/relationship/model.py` | A node create with N relationships that have an owner reads the owner kinds N more times. | Deferred |
| 10 | low | `core/migrations/schema/node_relationship_remove.py` | The list of profile and template kinds of a kind is built in three places. | Deferred |

Not built with finding 3: a uniqueness constraint on the `uuid` of the `NoOwner` vertex. It is a new database constraint.

### Second review, 2026-11-17

A separate review session gave 9 findings and a list of small fixes on commit `2dfe2e63c5`. Each finding has a test that failed before the fix. All 9 are real.

| # | Finding | Commit | Test |
|---|---|---|---|
| 1 | A branch that adds back an owner that it hid put that owner back on the default branch at the merge. | `47ceca7506` | `test_ownership_merge.py::test_owner_state_set_again_on_a_branch_does_not_return_after_the_default_branch_replaces_it` |
| 2 | The owner write of the merge did not save the earlier `updated_at` and `updated_by` of the attribute for the rollback. | `f62cddec06` | `test_ownership_merge.py::test_rollback_of_a_merge_that_wrote_the_owners_of_an_attribute_restores_the_audit_metadata` |
| 3 | The delete of a template did not close the `HAS_OWNER_SOURCE` mark. The maintainer decided that the code changes, not the spec. | `d2cf9f335f` | `test_ownership_merge.py`, 2 tests with `template_deleted` in the name |
| 4 | Only the `OwnerSet` path took the write lock on the node. Two open transactions could each create an edge to the same owner. | `5482a884ca` | `test_owner_sets.py::test_two_writes_of_one_owner_in_open_transactions_create_one_edge` |
| 5 | A branch made before the upgrade still read a repository as owner after m085. The maintainer decided that m085 adds `deleted` edges on these branches. | `50588d89db` | `test_close_repository_owner_edges.py::test_branch_made_before_the_upgrade_reads_no_repository_owner_after_the_upgrade` |
| 6 | m084 hid the owner of the default branch from the last branch write, not the first. | `f38d8a48f1` | `test_hide_replaced_branch_attribute_owners.py::test_default_branch_owner_is_hidden_from_the_first_of_two_branch_owner_writes` |
| 7 | The diff did not show a change of the template mark alone, but the merge copied it. | `0f07b6ac74` | `test_ownership_merge.py`, 4 cases with `template_mark` in the name |
| 8 | A stored owner conflict of a relationship that the branch removed later made the merge fail. The merge now skips it with a log line. | `39972731e1` | `test_owner_field_migrations.py::test_merge_skips_a_resolved_owner_conflict_of_a_relationship_that_the_branch_removed_later` |
| 9 | The walk and the resolver read the parents above a template copy. | `4eeb2aabc7` | `test_resolver.py::test_template_copy_is_read_without_its_parents` |
| Small fixes | One comment in `bulk_merge.py`, five points of `ownership.md`, T055 moved to pull request 1 and ticked (decision of the maintainer). | `2736e05235` | none |
| New defect, found during finding 8 | The default branch gave a new owner to an attribute after the start of a branch that removed the attribute. After the merge, the owner edge stayed active on the removed attribute. The merge of owners as a set caused it. | `b8d19ec6c6` | `test_owner_field_migrations.py::test_merge_closes_the_owner_that_the_default_branch_gave_to_an_attribute_that_the_branch_removed` |

Choices inside these fixes:

- Finding 4: the lock now covers the owners of a node and of an attribute, the sources of a node, and the close of owner edges at a node delete. Its cost on these writes is not measured.
- Finding 7: `ConflictsEnricher._have_same_value` has one new clause, so that an updated property with equal values at both ends gives no conflict. `HAS_OWNER_SOURCE` has no index on the branch.
- Finding 2: the test calls the rollback directly after the merge. It does not make a later merge step fail.

Limits found and not fixed, written in `dev/knowledge/backend/ownership.md`:

- A template mark on the global branch stays open after the delete of a branch-aware template.
- m084 skips an attribute whose branch owner was written and then cleared before the upgrade.
- The diff cannot show that the origin of the owners changed from template to own.

Not tested: two transactions that write owners on the same nodes in opposite order, the guard of the new defect fix for a kind migration, an attribute rename on a branch with a new owner on the default branch, and the diff of a branch made before the upgrade with the new `deleted` edges of m085.

Runs after the last fix, with testcontainers and without the `INFRAHUB_*` variables of the shell: `backend/tests/component/core/migrations` 348 passed, 2 skipped; `backend/tests/component/core/diff/merge` 94 passed; `backend/tests/component/core/merge` with `test_merge_failure_rollback.py` 48 passed. After finding 7, the last change in their code: `backend/tests/component/core/ownership` 132 passed, `backend/tests/component/core/diff` 364 passed, `backend/tests/component/templates` 39 passed, `backend/tests/unit/core` 1315 passed.

For the user documentation task (IFC-3630):

- `docs/docs/branches/rebase.mdx`, row "Attribute owner or source conflict": the advice to resolve in favor of the branch is wrong for a list of owners, because the rebase stops until both branches hold the same list. The row does not name the conflicts of node owners, relationship owners, given owners and node sources.
- `docs/docs/branches/resolve-conflicts.mdx`, first bullet of "How to resolve conflicts": the same point for a rebase. It does not say that a merge can apply either side of an owner list conflict.
- `docs/docs/objects/metadata.mdx`, list under "Metadata": it says that an owner can be a repository, and it describes one owner only. It does not describe node owners, "no owner", inheritance and node sources.

### Third review, 2026-11-18

An independent review gave 4 findings to fix and 5 items to fix or record, on commit `71bb828757`. Each fix has a test that failed before the fix, except the structure changes (items 8 and 9).

| # | Finding | Result | Commit before the squash | Test |
|---|---|---|---|---|
| 1 | A write on the global branch (branch-agnostic holder) only ended the removed owner edge. A branch made before the write read the old and the new owner, and the single `owner` read NULL. | Real, fixed: the write also adds a `deleted` edge on the global branch, as the node delete does. It covers every holder kind. | `ba6064af3a` | `test_global_owner_writes.py` (13 cases), one merge test, one rebase test |
| 2 | m085 did not hide a global repository owner from a branch made before the upgrade. | Real, fixed with a third query, same pattern as finding 1. A second run adds nothing. | `f28d9540b8` | `test_close_repository_owner_edges.py::test_branch_made_before_the_upgrade_reads_no_global_repository_owner_after_the_upgrade` |
| 3 | The patch `delete-duplicated-edges` merged two correct owner edges to the same peer and lost the time of a removal. | Real, fixed: the patch reads only the 4 edge types it was made for (`IS_PART_OF`, `HAS_ATTRIBUTE`, `IS_RELATED`, `IS_RESERVED`). `develop` does not have the problem, because there the owner edges start at an `Attribute` or `Relationship` vertex. | `d4c1addc02` | `test_patches.py::test_edge_deduplication_plan_keeps_owner_added_again` (4 cases) |
| 4 | `UpdateAttributeValuesQuery` had a change that is not about owners. | Reverted. The change came from the work on migration 087 (pull request 3). No test of this pull request needs it: the migrations package passed after the revert. | `7bd0d144b3` | the migrations package |
| 5 | Each node delete ran the owner close query, with a lock and holder reads, also for a node with no owner. | Fixed (decision of the maintainer). The lock stays: the node delete locks the node only on the default and the global branch. An `EXISTS` check after the lock skips the holder reads. A cascade delete of 550 nodes went from +12.9% to about +6% compared with the base. A plain delete is within the noise between runs. | `d1076f1dfa` | `test_storage.py::test_node_delete_closes_the_source_edges_of_a_node_without_owner`, and the race test of the extra finding |
| Extra | Found by the race test of item 5: an owner write checked that the node is active before it took the lock, so it could write on a node that an open transaction deleted. | Real, fixed: the lock comes first. A write on such a node now fails and writes nothing, for every holder kind. | `df18e2207b` | `test_owner_sets.py::test_owner_write_and_node_delete_in_open_transactions_leave_no_open_owner_edge` (12 cases) |
| 6 | The owner diff read all node IDs of the previous diff in one query. | Fixed (decision of the maintainer): batches of `query_size_limit`. | `fdb5844683` | `test_ownership_merge.py::test_owner_diff_of_more_nodes_than_the_query_size_limit_reads_the_nodes_in_batches` |
| 7 | `verify_graph` reported a correct `deleted` owner or source edge to an owner that the default branch deleted before the branch started. | Real, fixed in the check. | `710c90a450` | `test_storage.py::test_branch_removes_an_owner_that_the_default_branch_deleted_before_the_start_of_the_branch` (2 cases) |
| 8 | `OwnerReference` and `OwnershipResolver.resolve_fields` had no caller and no test. | Moved to pull request 2. | `47ea980e82` | none |
| 9 | `core/ownership/` imported `core/diff/`, and `store_owner_states` was in the GraphQL layer. | Done: the reserved field names are in `core/ownership/fields.py`, and `store_owner_states` is in `core/ownership/writer.py`. No change of behavior. | `c69978e283`, `ee6ae9d90b` | the existing tests |
| Docs | Knowledge index, conflict rule for any owner or source list, edge patterns, T149 list, T144, 3 new limits. | Done. | `499b86b694` | none |

Not changed, as the review asked: the merge row order in `bulk_merge.py` (the claim was refuted before), the customer docs (IFC-3630), and the changelog.

Limits found in this round and written in `dev/knowledge/backend/ownership.md`:

- A branch made before the upgrade can read two owners on a branch-agnostic attribute, when an earlier release changed its owner on the global branch after the start of the branch.
- The clear of the source of a branch-agnostic attribute leaves the old source readable on a branch made before the clear. `develop` has the same behavior.
- The attribute rename migration takes the node lock but does not check that the node is still active. A later round
  removed this limit: the migration now takes the lock before it reads the sets, and then checks that the node is active.

Runs after the last code change of this round, each package in its own pytest session, with testcontainers and without the `INFRAHUB_*` variables of the shell: on commit `499b86b694` (before the squash), 2026-11-18: `backend/tests/component/core/ownership` 160 passed; `backend/tests/component/core/diff/merge` 97 passed; `backend/tests/component/core/merge` 47 passed; `backend/tests/component/core/migrations` 349 passed, 2 skipped; `backend/tests/component/templates` 39 passed. Earlier in this round: `backend/tests/component/core/diff` 367 passed, `backend/tests/component/database` 19 passed, `backend/tests/component/patch` 14 passed, `backend/tests/component/core/agnostic_retirement` 27 passed, the node delete tests 134 passed, `backend/tests/unit/core` 1315 passed. `invoke lint` and `docs.validate` pass.

## 6. Autonomous decisions

- **Spec directory on the feature branch.** The commit that adds the spec directory is on the feature branch, at the request of the maintainer, so that the diff of this pull request holds the code, the tests, the ticks of the tasks and this report.
- **Final state of the source branch.** The chunks took the final state of each file, not the steps of the first implementation. Some files came whole in an early chunk, and the later chunk checked them and added the tests.
- **Code with no caller before pull request 2.** `OwnerInputParser`, `OwnershipResolver.resolve` and `resolve_target_ownership` are in this pull request with their tests. Their callers are in the GraphQL layer. `OwnerReference` and `OwnershipResolver.resolve_fields` had no caller and no test in this pull request. On 2026-11-18, at the request of the maintainer, they moved to pull request 2, with the `fields` option of the parent read that only `resolve_fields` used. `resolve_field_ownership` stays, with its unit test.
- **Lock of the mutation.** The `node_ownership` lock (T021) stays in pull request 2. The database lock that keeps one owner set for each key is in this pull request.
- **Behavior change.** An owner that is not an account or an account group is refused (T065). This is in this pull request. The consolidated changelog must name it.
- **No changelog fragment in this pull request.** The run first added 3 fragments (the report command, the refusal of owners that are not accounts or account groups, the attribute owner in the diff). The maintainer asked to remove them: the changelog is one consolidated set of fragments, written when all pull requests are in the feature branch.
- **Evidence table.** One line is one test file, not one test, because the run added more than 400 tests.
- **Review finding 5 uses option B.** The maintainer chose option B: the migration hides the set with a `deleted` edge on its branch, as the attribute removal does. The global edges stay open, so a branch with the old schema still reads the owners of the field.
  - Rename on the default branch: the new set of a branch-agnostic profile or template gets its edges on the global branch. A later write of owners can then replace them. A branch with the old schema reads the old set, and also the new set under a name that its schema does not have.
  - Rename on another branch: the new set gets its edges on that branch, as before. The default branch reads the old owners until the merge. The merge runs the migration on the default branch, which reuses the set.
  - Not built: the retirement of branch-agnostic data does not read `OwnerSet` vertices, so the global edges of a hidden set never close. The change is not small: it touches the shared retention predicate and the 3 retirement queries. `dev/knowledge/backend/ownership.md` names this limit.
  - Known limit: after a rename on another branch, a write of owners on that branch cannot replace the owners that a branch-agnostic profile gives to the attribute. `dev/knowledge/backend/ownership.md` names this limit.
  - Found, not changed: `AttributeRenameQuery` puts the edges of a renamed branch-agnostic attribute on the branch of the migration, and a second run on the default branch creates the attribute again. `verify_graph` reports `attribute_edge_branch` and `duplicate_attributes`. This is not about owners, so the 4 new tests check only `GraphCheck.DUPLICATE_OWNER_SETS`.
- **Squash of the history.** At the request of the maintainer, the commits of the run and of the three review rounds were squashed into a few commits on 2026-11-18. The final content did not change. The commit SHAs in sections 2 and 5 name the commits before the squash.
- **Tests not run on the VM.** `component/git` and `component/test_lock.py` cannot run in the virtual environment of the VM. `component/git/writeback/test_repository_conversion.py` is one of them, and this pull request changes `repository_conversion.py` (one parameter of pull request 3 is not there).

## 7. Suggested next steps

1. Decide if the retirement of branch-agnostic data must also close the global edges of a hidden `OwnerSet` (review finding 5), and if `AttributeRenameQuery` needs a fix for a branch-agnostic attribute.
2. Run `/pre-ci` before the pull request leaves the draft state. CI runs the `component/git` tests that the VM cannot run.
3. Done on 2026-11-18: `OwnerReference` and `OwnershipResolver.resolve_fields` moved to pull request 2.
4. Get the decision of the engineering review on the depth limit of the parent walk (T003, PD-3). The code uses the provisional value.
5. A person reviews the owner merge queries (work that the storage decision names).
6. Start pull request 2 (IFC-3627) on a branch from the feature branch after this pull request merges into it.
