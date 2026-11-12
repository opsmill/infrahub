# Research: Branch-Agnostic Reads That Return the Right Branch's Data

Findings from reading `release-1.12` (`4d7611830`) and the earlier branch-agnostic code at `7015435c4` (local branch `branch-agnostic-source`). Every decision below either applies a decision from the brief or fills a gap the brief leaves to the plan. Code is cited as `module::symbol`.

## R1. One shared branch window module

**Finding.** Four copies of the branch window logic exist, not three:

| Copy | Windows it builds | Fork time capped at read time | Default branch in the list | How it picks the latest edge |
|---|---|---|---|---|
| `core/query/subquery.py::build_branch_windows_query`, `render_window_filter` and `render_outranks` at `7015435c4` | Every branch except `-global-` and `DELETING` | Yes, `min(branched_from, $windows_at)` | Yes, with a NULL origin | `NOT EXISTS` of an edge in the same window that outranks it |
| `core/query/resource_manager.py::LIVE_BRANCHES_QUERY` and the number pool fragments built on it | Every branch except `-global-`, `DELETING` and the default branch | No: `fork_at = branched_from`. `INHERITED_OPEN_VALUES_QUERY` can treat a branch created after `$at` as inheriting a value | No | No ranking: an edge is visible unless the branch wrote its own edge (the "hiding" edge) |
| `core/query/agnostic_retention.py::UNRETAINED_AGNOSTIC_FIELD_PREDICATE` | Same as the first copy | Yes, at `$at` | Yes, with a NULL origin | `ORDER BY branch_level DESC, from DESC, status ASC LIMIT 1` per window |
| `core/query/branch_agnostic_retirement.py` (the collect inside the query that retires fields of a deleted branch) | Same as the first copy | Yes | Yes | Uses `UNRETAINED_AGNOSTIC_FIELD_EVALUATION` |

`agnostic_retention.py` imports nothing and writes `"DELETING"` as a string literal. Importing `BranchStatus` from `infrahub.core.branch.enums` runs `core/branch/__init__.py`, which imports `core/branch/models.py`, which imports `infrahub.core.query`. That cycle is latent today.

**Decision.** Add a leaf module `backend/infrahub/core/query/branch_windows.py`. It imports only `infrahub.core.constants` (and `Timestamp` under `TYPE_CHECKING`), and it keeps the `"DELETING"` literal. It holds:

- the Cypher that collects the live branch windows, parameterised by the time parameter name and the variables to carry through the aggregation (retention carries `agnostic_candidates`);
- `render_window_filter(edge, window)`, which tests whether an edge is visible in one window;
- `render_outranks(edge)`, which tests whether the competing edge `r` outranks `edge`.

`subquery.py`, `ipam.py`, `resource_manager.py`, `agnostic_retention.py` and `branch_agnostic_retirement.py` import from it.

**Rationale.** FR-013 asks for one definition of a window. `dev/knowledge/backend/query-pattern.md` ("Keep Cypher readable inline") allows a shared Cypher fragment only when it has a substantial body and several consumers. Here there are five consumers, and one copy computes a different window. A leaf module avoids the import cycle.

**Number pools.** The number pool fragments keep their "hiding edge" rule, which is correct on `release-1.12` and covered by its tests. PR 3 replaces only the window collection with the shared one. The fragments read `origin_at` instead of `fork_at`, and read `deleting_branches` from the shared clause, which emits it when called with `include_deleting=True`. Two differences need care:

- The shared list includes the default branch with a NULL origin. A comparison `window.origin_name = hv.branch` is never true for NULL, so the fragments skip that entry, but every fragment must be checked.
- The shared list caps the fork time at the read time. This changes the result only for a read in the past of a branch created after that time. PR 3 adds a test that pins the current results of `test_number_pool_query.py` and the audit's number pool tests, including the values `NumberPoolGetAllocated` reports per branch, plus one test of a read at a time before a branch was created.

**Alternatives considered.**

- Keep the copies and fix the number pool cap in place. Rejected because FR-013 requires one definition.
- Rewrite the number pool queries onto the ranking form. Rejected because they are correct on `release-1.12`, and the brief only asks to move them onto the helpers.

## R2. Global permissions read the default branch (PR 1)

**Finding.** `core/account.py::fetch_permissions` builds `AccountGlobalPermissionQuery(branch=branch, branch_agnostic=True)`. `fetch_role_permissions` builds `AccountRoleGlobalPermissionQuery` in the same way. Without `branch_agnostic`, `Branch.get_query_filter_path` on the default branch reads `-global-` plus `main`. The object permission queries already read the request branch. `auth/auth.py::fetch_account_groups_and_roles` and `auth/auth_groups/service.py::AutoCreatedGroupsService._add_member` load the group on the default branch, then call `get_peers(branch_agnostic=True)`.

**Decision.**

- In both `fetch_*` functions, resolve the default branch with `registry.get_branch(db=db, branch=registry.default_branch)` and run the global query on it without `branch_agnostic`.
- In the two auth callers, remove `branch_agnostic=True`. The group is already loaded on the default branch.
- The signature of `fetch_permissions` keeps its `branch` argument, because the object permission query uses it.

**Base branch.** `core/account.py` and `auth/auth_groups/service.py` are the same on `stable` and on `release-1.12`. `auth/auth.py` differs only far below the function. The PR is written on `stable` and merged into `release-1.12` through the regular merge. Tests that use `SUPER_ADMIN_PERMISSION` (from `permissions/globals.py`) exist only on `release-1.12`, so the PR 1 tests must not depend on it.

**The merge test.** `graphql/mutations/branch.py::BranchMerge.mutate` takes the branch from `data.name`, and `MergeBranchPermissionChecker` checks `MERGE_BRANCH` against the permissions loaded for the request branch. The new test sends `BranchMerge(name: "B")` to `/graphql/B`, from an account that added itself to an administrator group on B. With the fix, the permissions loaded for B come from the default branch, so the checker refuses the merge. The test goes in `backend/tests/component/api/` and sends the `BranchMerge` over HTTP to `/graphql/B`, so it runs the same permission loading as a real request. A second test sends a mutation that changes an account to `/graphql/B`, from an account that holds `super_admin` only through a membership added on B, and expects it to be refused.

**Alternatives considered.**

- Read the request branch. Rejected in review: it keeps the escalation through the merge mutation.
- Apply the window rule. Rejected in the audit: it keeps the grant by design.

## R3. Callers that read only `-global-` data (PR 2)

**Finding.** Every caller the brief lists still passes `branch_agnostic=True`. Two files make more calls than the brief lists:

- `pools/schema_number_pool_synchronizer.py` makes 3 calls (`get_one` when it renames the scope, `query` in `_sync_existing_pools_with_schema`, and `get_one` inside the lock).
- `pools/schema_number_pool_upserter.py` makes 3 calls (`query` after it takes the lock, `get_one` inside the transaction, and `get_one` behind the cache).

All six read `CoreNumberPool`, which is branch-agnostic.

The search also found callers the brief does not list:

| Caller | What it reads | Classification |
|---|---|---|
| `pools/number_pool_repository.py` (3 calls) | `CoreNumberPool` | Probably `-global-` only. To verify. |
| `pools/number_pool_lookup.py` | `CoreNumberPoolRange` by pool | Depends on the branch support of `CoreNumberPoolRange`. To verify. |
| `pools/scoped_number_pool_reader.py` (2 calls) | `CoreNumberPool` | Probably `-global-` only. To verify. |
| `pools/number_pool_usage_nodes.py::PeerSummaryReader.read` | Branch-aware nodes that use pool numbers | Needs an answer across branches (group 1). Not `-global-` only. |
| `graphql/queries/resource_manager.py` (`pool.resources.get_peers(branch_agnostic=True)`) | A branch-agnostic relationship to branch-aware prefixes | Group 2 (PR 6). |
| `core/migrations/graph/m080_number_pool_ranges/migration.py` | Number pool data | To verify. |

**Decision.** PR 2 removes the flag from every call the brief lists, including all calls in the synchronizer and the upserter. The new callers are classified by a task in PR 2. A caller is changed in PR 2 only when its kind and every relationship it follows are verified as branch-agnostic. `PeerSummaryReader.read` and the resource manager read are left as they are and recorded for PRs 3 and 6. `PeerSummaryReader.read` calls `get_many(branch_agnostic=True)`, so PR 6 changes what it returns: each node's display label then comes from its chosen branch. PR 6 checks its output in a test. A migration that has already shipped is not edited, because a shipped migration must not change behavior; the brief lists `m062`, and PR 2 applies the brief's decision there only after confirming that `GetGlobalPermissionAttributesQuery` ignores the flag. The audit says it does, so the change is a no-op.

**Rationale.** The brief limits group 4 to callers whose results cannot change. Adding a caller without verifying it would break that guarantee.

## R4. IP pool free values and allocation (PR 3)

**Finding.**

- The four queries `IPPrefixSubnetFetchFree`, `IPv6PrefixSubnetFetchFree`, `IPPrefixIPAddressFetchFree` and `IPv6PrefixIPAddressFetchFree` in `core/query/ipam.py` share no base class.
- Each one ranks the namespace `IS_PART_OF` edge with `ORDER BY branch_level DESC, from DESC LIMIT 1`, with no status tiebreak. When no row is left, the following `collect()` still returns one row with an empty list.
- Each one checks the allocated children with `all(r IN relationships(path) WHERE <filter> AND r.status = "active")`. This is a test of each edge, not of the latest edge, and it never checks the child's own `IS_PART_OF` edge. With `branch_agnostic=True` the filter accepts edges on `DELETING` branches and on every other branch.
- `CoreIPPrefixPool.get_next` and `CoreIPAddressPool.get_next` read `resources` and `ip_namespace` through the relationship manager on the pool's own branch, then build `IPAMResourceAllocator(branch_agnostic=True)`.
- `get_peer` returns `None` only when the pool has no `ip_namespace` link. Because `ip_namespace` is a branch-agnostic relationship, `get_peer` reads it across branches, so it returns a namespace that exists on any branch and never detects a namespace missing on the allocating branch. When it returns `None`, the free-value query falls back to the default namespace and `get_resource` then fails with an `AttributeError`.
- When there are no resources, the prefix pool raises `IndexError("No more resources available")` and the address pool raises `PoolExhaustedError`.

**Decision.**

- Rewrite the four queries in the flat window form of `NodeGetByHFIDQuery._build_branch_agnostic_query`:
  - The windows collection opens the query.
  - The namespace check becomes `any(window IN branch_windows WHERE <IS_PART_OF visible and active> AND NOT EXISTS {<an edge outranks it>})`. A missing namespace yields no rows, not an empty list.
  - Each allocated child is kept when, in some window, its `IS_PART_OF`, both `IS_RELATED` edges of `ip_namespace`, its `HAS_ATTRIBUTE` and its `HAS_VALUE` are all the latest edges and active.
- Bound the candidate edges with `r.from <= $windows_at AND (r.to IS NULL OR r.to > <oldest origin_at among the windows>)`, as the audit proposed. This keeps the number of historical rows proportional to the open branches.
- Keep the IPv4 and IPv6 bodies separate. Only the window predicate moves into `branch_windows.py`, to stay close to "three similar lines over a premature abstraction".
- **Allocation on branch X.** `get_next` and `get_resource` read the namespace id with `ip_namespace.get_peer_id()`, then load the namespace with `NodeManager.get_one(id=…, branch=X)` without `branch_agnostic`. They read `resources` with a normal read on X: the peer ids of the link, then `NodeManager.get_many(ids=…, branch=X)`. Neither read is branch-agnostic:
  - If the namespace does not exist on X, raise `ResourceNotFoundError` with a message naming the pool, the namespace and X.
  - Resources that do not exist on X are skipped. If none remain, raise `PoolExhaustedError` with a message naming the pool and X.
  - The prefix pool's `IndexError` becomes the same `PoolExhaustedError`. This is a user-visible change of error type, so it needs a changelog fragment.
- **Pool links (FR-011).** A link from a pool to a namespace or resource that exists on at least one live branch stays valid. PR 3 changes nothing in how links are added, so this needs no new code there. PR 6 makes adding a link follow FR-031.

**Rationale for the error classes.** A namespace that does not exist on the branch is a referenced resource that cannot be found, so `ResourceNotFoundError` (404) fits. A pool with no usable resource on the branch cannot allocate, which is what `PoolExhaustedError` (409) already means for the address pool. Adding new exception classes was considered and rejected (constitution VII).

## R5. Delete check across every live branch (PR 4)

**Finding.**

- `NodeDeleteValidator` builds a dependency index from the schema of the request branch: cascades and required relationships.
- It runs one `RelationshipGetByIdentifierQuery` on the request branch. That query has no branch-agnostic path, and it is not filtered to the ids being deleted.
- The error is a `ValidationError` with the message `Cannot delete {kind} '{id}'. It is linked to mandatory relationship {rel} on node {peer_kind} '{peer_id}'`.

**Decision.**

- For a branch-agnostic node, `NodeDeleteValidator` runs `RelationshipGetByIdentifierQuery` once in window mode. The query opens with the windows collection and returns one row per window in which the link is the latest and active, and both ends exist. Each row also carries the window name.
- The validator then runs its existing walk once per window name, starting from the same delete set, with the same index:
  - A required peer left behind in any window raises the error, with `on branch '{name}'` added to the message.
  - A peer reached through a cascade in some window but not in the request branch's window also raises it, with the same branch suffix. Removed after the review of PR 4, at the user's request: only a required relationship blocks the delete.

  Changed during the review of PR 4: only the request branch's window runs the full walk. In every other window, only the branch-agnostic nodes of that walk's delete set count as deleted, because a cascade removes a branch-aware node on the request branch only. A branch-aware cascade target that keeps a required relationship to a deleted node on another branch therefore blocks the delete. Errors are grouped per blocking link and list every branch where it blocks (see `contracts/user-visible-behavior.md`).
- A branch-aware node keeps today's single-branch query and walk.
- In window mode the query starts from the ids in the delete set and is run again for each level of cascade, instead of reading every link of the indexed identifiers. The PR reports the database hits of deleting a `CoreAccountGroup` with 50 live branches and 10,000 group memberships elsewhere in the database.

**Rationale.** One query keeps the cost at one read of the candidate links times the number of windows, and the walk in Python is unchanged. Example in the brief: P reaches G1 on B only through `main`'s edge from before B was created. Only a window read finds it.

## R6. Peer existence check (PR 5)

**Finding.**

- None of the target queries checks the peer's `IS_PART_OF` edge today.
- `RelationshipGetPeerQuery` (and therefore its count) and `build_subquery_filter` / `build_subquery_order` know the relationship schema and can look up the peer schema.
- `NodeListGetRelationshipsQuery`, `GetAllPeersIds` and `RelationshipGetByIdentifierQuery` receive only identifier strings. In `build_subquery_order` every path element except the tail is unnamed.
- No helper reports whether a generic has a branch-agnostic implementation. `core/relationship/model.py::_use_global_branch` handles node schemas only.

**Decision.**

- Add `needs_peer_existence_check(relationship_schema, peer_schema, schema_branch) -> bool`. It returns true when the relationship is not branch-agnostic and the peer schema is a branch-agnostic node, or a generic one of whose `used_by` node schemas is branch-agnostic. It returns false for every branch-agnostic relationship (spec Clarifications, 2026-10-30): the retirement check already closes the `-global-` link once no live branch holds both ends, and the peer is returned on every branch until then, including a branch that deleted it. It lives with the relationship schema helpers in `core/schema/` and has unit tests.
- Render the check only when the helper returns true:
  - For a normal read: `EXISTS { MATCH (peer)-[p:IS_PART_OF]->(:Root) WHERE <request branch filter on p> }` and the latest such edge is `active`, ranked as every other `IS_PART_OF` read.
  - For a branch-agnostic read: in the same window that passes the link.
- Queries that only know identifier strings receive, from their caller, the set of identifiers that need the check:
  - `NodeManager` computes it for `NodeListGetRelationshipsQuery`.
  - The object conversion code computes it for `GetAllPeersIds`.
  - The delete validator computes it for `RelationshipGetByIdentifierQuery`.
- In `build_subquery_order`, keep the peer element named so the check can refer to it.
- `GetAllPeersIds` also gets the missing filter on `e2` and the status check on `e1`, because it is a read of current peers (FR-040).
- **Other reads of `IS_RELATED`.** Once PR 5 stops writing branch `deleted` edges, any query that reads a relationship to a branch-agnostic kind without the check could start returning a deleted peer. A query that reads a branch-agnostic relationship starts returning, on branch B, a peer deleted only on B. That is the intended result, but it needs PR 6 to build the peer from the chosen branch. R13 therefore places FR-023 and the removal of shape 2 in PR 6. Before the write change, PR 5 lists every query under `backend/infrahub/` that reads `IS_RELATED` (`rg -l IS_RELATED backend/infrahub`). For each, it records whether the query can read such a relationship, and either adds the check or states why the result cannot change. Known cases to check: `core/query/relationship.py::RelationshipCountPerNodeQuery` (used by `core/relationship/constraints/count.py`), the targeted uniqueness validation query, `core/query/dependent_nodes.py::DependentNodesQuery`, and the relationship count validator in `core/validators/relationship/count.py`. The list goes in the PR description. This goes beyond the reads the brief names, because the brief's own rule is that a read must not regress when the edges are removed.

**Rationale.** FR-018 and FR-020. The check uses the same definition of a live peer as `UNRETAINED_AGNOSTIC_FIELD_PREDICATE` (FR-019): the latest `IS_PART_OF` edge is `active` in the window.

**Dependency on PR #11220.** PR #11220 changes `build_subquery_filter` (it adds `branch_agnostic` and the latest-value ranking) and one line of `RelationshipGetPeerQuery.query_init`. It does not touch `build_subquery_order`, `NodeListGetRelationshipsQuery`, `GetAllPeersIds` or `RelationshipGetByIdentifierQuery`. PR 5 starts after PR #11220 reaches `release-1.12`, as decided.

## R7. Delete writes (PRs 5 and 6)

**Finding.** `RelationshipDeleteAllQuery`, called only from `Node.delete`:

- matches every relationship with any active `IS_RELATED` edge in the view;
- for each edge type, picks the latest edge per `(rl, n)` by `from` only, with no `branch_level` and no status tiebreak;
- always writes a `deleted` edge on `$branch`;
- sets `to` on the old edge only when it is on `$branch`;
- does not look at the relationship's branch support.

For a branch-agnostic node, `$branch` is `-global-` and the filter is time-only.

**Decision.**

- Rank by `branch_level DESC, from DESC, status ASC` everywhere in the query (FR-022).
- Split by the deleted node's branch support:
  - **Branch-aware node (PR 6, R13):** process only links whose `Relationship` vertex has `branch_support = "aware"`. Branch-agnostic relationships get no branch edge (FR-023). `RetireNodeAgnosticFieldsQuery` already runs after the delete and closes their `-global-` edges once no live branch holds both ends.
  - **Branch-agnostic node:** process only links with `branch_support = "aware"`, and for each link and each edge type:
    - on the default branch: when the default branch's latest edge is `active`, close it as decided for open question 2;
    - on each user branch whose own latest edge for the link is `active` (an edge with `branch = <that branch>`): write a `deleted` edge on that branch with `from = $at`;
    - write nothing on `-global-`.
  - The links of a branch-agnostic node on branch-agnostic relationships are on `-global-`, so they keep today's handling: close on `-global-`.
- Both cases read the user branches from the live windows, so a branch whose status is `DELETING` gets nothing.

**Open question 2, evidence.** For a user delete on the same branch, every edge type already gets both `to` on the old edge and a new `deleted` edge: `IS_PART_OF` in `NodeDeleteQuery`, attributes in `AttributeDeleteQuery`, links in `RelationshipDeleteAllQuery`. The diff depends on the `deleted` edge: `core/diff/query_parser.py::TrackedStatusUpdates.get_action_and_timestamp` reports `REMOVED` only when the latest status is `deleted`. Only merge writes on `HAS_ATTRIBUTE` and `IS_RELATED` set `to` alone. `dev/knowledge/backend/database-schema.md` ("Soft Deletes") does not describe user deletes correctly.

**Recommendation for open question 2.** On the default branch, set `to` on the active edge and write a `deleted` edge with the same `from`, as every other user delete does. The PR 5 documentation task then corrects "Soft Deletes" to describe what user deletes and merges each write. This is not applied: the brief says to stop and ask, so the PR 5 task that decides it is a gate.

## R8. The graph migration (PR 6)

**Finding.**

- `GRAPH_VERSION` is 82, and the latest migration is `m082_heal_missing_number_pool_rows`.
- Migrations are discovered automatically (`core/migrations/graph/discovery.py`), so a new `m083_*` package needs no registry edit.
- `m081` is the pattern for edge rewrites: `ArbitraryMigration`, ordered `CountedMigrationQuery` steps, `CALL {…} IN TRANSACTIONS OF $batch_size ROWS`, counts from `stats`, `validate_migration` with a leftover count, and a test for resuming.
- `m078` already uses `UNRETAINED_AGNOSTIC_FIELD_PREDICATE`.

**Decision.** Add `m083_separate_global_and_branch_link_edges` (name to confirm at implementation), an `ArbitraryMigration` with `minimum_version = 82` and three steps. It ships in PR 6, the last PR that changes the delete writes, and reaches `release-1.12` together with PR 5 through the feature branch of R13. Shape 1 links have `branch_support = "aware"` and shape 2 links have `branch_support = "agnostic"`, so steps 1 and 2 never touch the same link and need no order between them:

1. **Shape 1:** a `-global-` `deleted` edge of type `IS_RELATED`, `IS_PROTECTED`, `HAS_OWNER` or `HAS_SOURCE` on a link whose `Relationship` vertex has `branch_support = "aware"`. Write what the new delete writes, with the original `from`, then remove the `-global-` edge.
2. **Shape 2:** a `deleted` edge on the default branch or on a user branch, on a link whose `Relationship` vertex has `branch_support = "agnostic"`. Deleting a branch-aware node on any branch, the default branch included, writes these edges today, and a merge may have written some (open question 1). Remove them. The brief names only the edges written on a branch; the edges written on the default branch are included because the brief's rule forbids a default-branch edge next to a `-global-` edge too, and because leaving them would leave the most common mixed pair in existing databases.
3. **Count and log** the pairs that hold both a `-global-` edge and a branch edge of the same type and match neither shape.

`validate_migration` fails when any pair of shape 1 or shape 2 is left. The test follows the `m081` layout: it builds each shape through the old write path, reads at several timestamps before and after, and runs the migration twice.

**Open question 1, evidence.** The merge does not copy a branch `deleted` edge on a branch-agnostic relationship to the default branch:

- `core/diff/query/bulk_merge.py::BulkMergeRelationshipEdgesQuery` and `BulkMergeRelationshipPropertyEdgesQuery` require `branch_support = "aware"`.
- `BulkMergeNodeExistenceQuery` closes only edges on the target branch.
- `DiffNodePathsQuery` can report the path under a deleted node, but no merge query writes it.

Merge code from before 1.10 may have written such copies, so the check also counts, on a copy of a real database or in a dry run of the migration, default-branch `deleted` edges on branch-agnostic links that have a user-branch `deleted` edge with an earlier `from`. The result is reported before shape 2 is written, whatever it shows.

No test asserts this. A PR 6 task adds a test that merges a branch with such an edge and checks the default branch's edges. If the test shows a copy, implementation stops and asks before shape 2 is written.

**Hard delete.** Steps 1 and 2 remove edges, which constitution principle II allows only for branch deletion. The plan records the exception under Complexity Tracking, as the brief decided.

## R9. Branch-agnostic reads of peers and values (PR 6)

**Finding.**

- `NodeManager.get_many` runs `NodeListGetInfoQuery`, then `NodeListGetAttributeQuery`, builds each node on `node.branch` (the branch of the winning `IS_PART_OF` edge, or `-global-` for a branch-agnostic node), then runs `NodeListGetRelationshipsQuery`.
- Its extra `get_many` for missing peers does not pass `branch_agnostic`.
- `NodeListGetAttributeQuery` ranks each attribute separately across branches.
- `NodeListGetRelationshipsQuery` ranks by `from` only.
- `NodeGetListQuery` on the default branch matches every live `IS_PART_OF` edge without ranking, so a merged node appears twice.
- The `WHEN $is_branch_agnostic` arms in `RelationshipGetPeerQuery`'s metadata subqueries are never reached.
- The branch-agnostic filter accepts edges of deleted branches, so `registry.get_branch(node.branch)` can receive a branch that no longer exists.

**Decision.**

1. `NodeListGetInfoQuery`, in branch-agnostic mode, opens with the windows collection. For each node it chooses the first window, in the order of FR-029, in which the node's latest `IS_PART_OF` edge is `active`:
   - The order is computed in Cypher with a sort key: 0 for the request branch, 1 for the default branch, then 2 followed by the name.
   - The query returns the chosen window `{name, origin_name, origin_at}` with each row.
   - A branch-agnostic node always chooses the request branch.
2. `get_many` builds each node object on the chosen branch, and passes a `node_windows` map (node id to window) to `NodeListGetAttributeQuery`, `NodeListGetRelationshipsQuery` and the missing-peer `get_many`.
3. In those queries, when `node_windows` is given, `WITH n, $node_windows[n.uuid] AS window` follows the node match. Every ranked `CALL` takes `window` into scope and uses `render_window_filter(edge="r", window="window")` in place of the branch filter. The ranking `ORDER BY r.branch_level DESC, r.from DESC LIMIT 1` stays, because it is correct inside one window. The `created_at` and `updated_at` subqueries use the same window.
4. `RelationshipGetPeerQuery`, in branch-agnostic mode: the main peer match keeps a peer when in some window the link edges and the peer's `IS_PART_OF` are the latest and active. Ordering then reads inside the peer's chosen window, which the query chooses as in point 1. The unreachable `$is_branch_agnostic` arms are removed.
5. `NodeGetListQuery`, in branch-agnostic mode, uses the window check on `IS_PART_OF` for the top-level match on every branch, and returns each node once.
6. `RelationshipManager.save` reads current peers with the same branch-agnostic `RelationshipGetPeerQuery`, so a peer deleted on another branch is still found and its `-global-` link is closed when replaced.
7. `Relationship._get_peer` in branch-agnostic mode uses `get_one_by_id_or_default_filter`, which reaches `get_many`. The window rule makes it find a peer that exists on any live branch, and `NodeNotFoundError` is raised only when none does.

**Open question 3, evidence.** No caller found saves a branch-aware node obtained through a branch-agnostic read. Callers that save a node read branch-agnostically all read branch-agnostic kinds:

- `core/integrity/object_conflict/conflict_recorder.py::ObjectConflictValidatorRecorder.get_validator` (`CoreValidator`);
- the number pool synchronizer and upserter (`CoreNumberPool`, which PR 2 moves off the branch-agnostic read anyway).

Under decision 1 these nodes would be built on the request branch instead of `-global-`. `Node.save` writes a branch-agnostic node on `-global-` through `get_branch_based_on_support_type()`, so the writes should not change. This is not verified by a test. A PR 6 task checks it and is a gate.

## R10. Measuring cost

**Decision.** Each PR that changes a query adds or extends a benchmark under `backend/tests/benchmark/` that runs Neo4j `PROFILE` and sums database hits, following `test_node_list_filter.py` at `7015435c4`. The paths come from the brief:

- reads of branch-aware relationships between branch-aware kinds;
- a list of `CoreTransformPython` with `repository`;
- `CoreStandardGroup.members` with 5,000 members, because the peer existence check applies to every relationship whose peer is the `CoreNode` generic, which has branch-agnostic implementations;
- deleting a branch-agnostic node with 50 live branches;
- branch-agnostic reads with many live branches;
- IP pool allocation with many live branches and past allocations.

The PR description reports before and after. The plan sets no fixed limits. If a path becomes significantly slower, the approach changes.

## R11. Test fixtures

**Decision.**

- Reuse `backend/tests/helpers/schema/agnostic_retirement.py`. It holds `AgnosticretireWidget` and `AgnosticretireGadget` (branch-aware, with the branch-agnostic cardinality-one relationship `gadget`) and `AgnosticretireBeacon` (a branch-agnostic kind). It has not changed since `7015435c4`.
- Reuse `backend/tests/component/conftest.py::branch_aware_node_with_agnostic_attrs_schema` for a cardinality-many branch-agnostic relationship.
- Move each audit test into `backend/tests/component/` next to the code it covers, and drop its debug output and unused fixtures.
- Bring `TestBranchAgnosticLookupByHFID`, `TestBranchAgnosticPeerFilter` and `test_branch_agnostic_filter_through_the_parent_relationship` from `7015435c4`'s `test_reads_by_value_on_branch.py` in PR 6. Bring `BranchDataset` and `_update` with them.
- Keep PR #11220's tests `test_branch_agnostic_lookup_by_hfid_finds_the_default_branch_value` and `test_branch_agnostic_filter_finds_the_default_branch_value`. They must still pass after PR 6.

The existing branch-agnostic query tests whose expected results change are listed in tasks.md for the PR that changes them.

## R12. Bringing in the code at `7015435c4`

**Finding.** `release-1.12` has none of the branch-agnostic code written at `7015435c4`:

- the window helpers;
- the window form of `build_subquery_filter`, used by `NodeGetListQuery` filters and by `RelationshipGetPeerQuery` peer filters;
- `NodeGetByHFIDQuery._build_branch_agnostic_query`;
- the benchmark `backend/tests/benchmark/test_node_list_filter.py`.

`Relationship._get_peer` uses `get_one_by_hfid` when a peer is given by HFID, so FR-031 depends on the HFID lookup. The rewrite of `build_subquery_filter` (`48789ecad`) costs 8% more database hits on the default branch than PR #11220's query, and the brief says the single-branch path must not get slower.

**Decision.**

| Piece | PR | How |
|---|---|---|
| Window helpers | PR 3 | Into `core/query/branch_windows.py` (R1), not into `subquery.py` |
| Window form of `build_subquery_filter`, `branch_windows` passed through `NodeGetListQuery` and `RelationshipGetPeerQuery` | PR 6 | Used only when `branch_agnostic` is true. A read on one branch keeps PR #11220's query unchanged (FR-039). |
| `NodeGetByHFIDQuery._build_branch_agnostic_query` (flat form from `7015435c4`) | PR 6 | As written at `7015435c4`, on top of PR #11220's version |
| Benchmark `test_node_list_filter.py` | PR 3 | Brought in first, so every later PR can report against it |

Each piece is re-applied by hand on its PR's base, not cherry-picked. The three commits conflict with `release-1.12` at `15502a8b6`.

**Alternatives considered.** Bring down the cost of the rewrite on the default branch so one query serves both paths. Rejected for this work: the brief allows either option, and keeping PR #11220's single-branch query leaves the most-used path untouched.

## R13. Order of PRs 5 and 6

**Finding.** Two changes make a read on branch B return a branch-aware peer that B deleted, when the relationship is branch-agnostic (spec Clarifications, 2026-10-30):

- FR-023: deleting a branch-aware node on B no longer writes a branch `deleted` edge on its branch-agnostic links;
- step 2 of R8: the migration removes the existing edges of that kind (shape 2).

Today that edge hides the peer on B. Once it is gone, the `-global-` link is the only edge, so reads on B return the peer: GraphQL resolvers, counts, filters through the relationship and peer id lists. The intended result is the peer built from its chosen branch (FR-029, FR-030). Only PR 6 builds peers that way. Before PR 6, `NodeManager.get_many` builds the peer on B, where it does not exist, so the read drops the peer or fails. That is worse than today.

The other write changes of PR 5 do not have this dependency:

- FR-021 and shape 1 concern branch-aware links to a branch-agnostic node. The peer existence check of PR 5 already filters a deleted branch-agnostic peer, whatever edges the link holds.
- FR-022 (ranking) does not change which peers a read returns.

PR 6's reads work with or without shape 2 edges. In B's window the branch edge hides the link, but the default branch's window still holds the link and the peer, so a branch-agnostic read returns the peer either way. FR-026 therefore holds for the shape 2 removal in PR 6.

**Decision.**

- PRs 5 and 6 merge into a feature branch, `branch-agnostic-links-ifc-3508`, created from `release-1.12` once PR 3 and PR #11220 are in it. The feature branch merges into `release-1.12` once both PRs are in it, so no release holds PR 5 without PR 6. Each PR is still reviewed on its own.
- PR 5 keeps the peer existence check, FR-021, FR-022, FR-040 and open question 2.
- PR 6 takes FR-023 and open question 1. FR-023 lands after the read changes (T091 to T095), so every commit on the feature branch passes its tests.
- One migration, `m083`, converts shape 1 and removes shape 2 (R8). It ships in PR 6, after both write changes.
- PR 6 lists every caller that reads the peers of a branch-agnostic relationship and then loads a peer on the request branch, and checks that each one handles a peer that does not exist there.

**Rationale.** The migration's two shapes do not need two phases. They touch different links, so one migration can run every step. A split was needed only if PR 5 reached a release without PR 6: deletes would then still write shape 2 edges, and removing them would change reads on a branch before PR 6 can build the peer. The feature branch removes that case, so one migration and one upgrade step are enough.

**Alternatives considered.**

- Merge PR 5 into `release-1.12` on its own, with two migrations: `m083` for shape 1 in PR 5 and `m084` for shape 2 in PR 6. Rejected: it adds a second one-way migration and upgrade step only to release PR 5 earlier.
- Keep FR-023 and shape 2 in PR 5, and bring PR 6's chosen-branch reads into PR 5. Rejected: that moves most of PR 6 into PR 5.
- Keep them in PR 5 with a temporary check that hides the peer on B, removed in PR 6. Rejected: the check is written only to be removed, and it contradicts the clarified rule while it exists.
- Merge PRs 5 and 6 into one PR. Rejected: both are large, and the feature branch gives the same release result with two reviews.

## R14. Reading `-global-` edges on a user branch (PR 5)

**Finding.**

- For a user branch, `core/branch/models.py::Branch.get_branches_and_times_to_query_global` returns two groups:
  - `-global-` and the origin branch, read at `min(branched_from, at)`;
  - `-global-` and the branch itself, read at `at`.
- `get_query_filter_path` (84 calls under `backend/infrahub/`) and `get_query_filter_relationships` accept an edge that is visible in either group.
- A `-global-` edge created before `branched_from` and closed after it, by setting only its `to`, is still visible in the first group. A read on that branch therefore returns it, while the default branch and every branch created after the close do not.
- When a newer `-global-` edge replaces the closed one, as for an updated branch-agnostic attribute, queries that rank edges pick the newer edge, so the wrong edge is returned only when nothing replaces it.
- The branch window rule (data-model.md, "Branch window") reads `-global-` at `at` only, so window-based reads, including the delete check of PR 4, do not return the closed edge.
- Found while testing the PR 4 delete check: updating a declared branch-agnostic relationship on a branch closed its `-global-` edge this way. No committed test covers it yet.

**Decision.**

- Remove `-global-` from the origin group. A user branch reads the origin branch at `min(branched_from, at)`, and `-global-` with the branch itself at `at`. The default branch is unchanged.
- The query text does not change, only the branch lists passed as parameters, so reads on one branch should cost the same (FR-039, SC-004). PR 5 measures it.
- Before the change, list:
  - every write that closes a `-global-` edge by setting only its `to`;
  - every query that builds its own branch filter with `-global-` instead of calling these helpers.
- `get_branches_and_times_for_range`, used by the diff, does not include `-global-` and does not change.

**Rationale.** FR-043. The `-global-` part of the origin group adds nothing a correct read needs:
- an edge still open is visible in the second group;
- an edge closed before `branched_from` is visible in neither;
- for a read time before `branched_from`, both groups use the same time.

Its only effect is to return an edge closed after the branch was created.
