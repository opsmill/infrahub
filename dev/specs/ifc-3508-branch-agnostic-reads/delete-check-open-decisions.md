# Delete check: open decisions on cascade targets and merged branches

Deleting a branch-agnostic node removes it from every branch at once. The delete check of user story 4 refuses the delete when another live branch holds a node with a required relationship to it. Two consequences of that rule need a decision before the PR is opened:

- Users cannot delete a repository while any other branch holds the nodes that the repository's import created.
- A stale link on a merged branch blocks a delete until someone deletes that branch, because a merged branch is read-only.

Decided on 2026-11-13:

- Decision 1: option B2, as a general rule taken from the schema. On each other live branch, a link does not block the delete when it is the peer side of a relationship on which the deleted node has `on_delete: cascade`. Each branch's own schema decides whether the relationship cascades. See FR-014, FR-017 and the Clarifications session of 2026-11-13 in [spec.md](spec.md).
- Decision 2: deferred to its own Jira issue. Option C of decision 1, and what a merge does with a node left without its required peer, are deferred too. See "Deferred follow-ups" in [spec.md](spec.md).

The rest of this brief is the input to that discussion, kept as it was.

## How the delete check works now

The code is on branch `agnostic-delete-check-ifc-3508` at commit `9272f01fb`, which is not pushed. Nothing below has been run as a test since commit `ec178f999`.

- `backend/infrahub/core/node/delete_validator.py::NodeDeleteValidator.get_ids_to_delete` runs the check.
- Query 1, `backend/infrahub/core/query/node_delete.py::NodeDeleteCascadeQuery`:
  - follows the cascade in the request branch's window;
  - returns the delete set, whether each node is branch-agnostic, and the required peers outside the delete set on the request branch.
- Query 2, `NodeDeleteOtherBranchesQuery` in the same module, runs only when the delete set holds a branch-agnostic node. In every other live branch's window, it reads the links of a required relationship to those branch-agnostic nodes. Each branch's own schema decides which relationships are required.
- A live branch is any branch except `-global-` and branches being deleted. `NodeDeleteValidator._get_links_on_other_branches` builds the list from the worker's branch registry, and the query reads the windows with `backend/infrahub/core/query/branch_windows.py::build_branch_windows_query`.
- Branch-aware nodes of the delete set are deleted on the request branch only. This is FR-016 in [spec.md](spec.md). So on every other branch, they count as peers that remain.

## Decision 1: a node that the cascade deletes on the request branch blocks the delete on other branches

### What happens

A branch-agnostic node A cascades to a branch-aware node C, and C has a required relationship back to A. The delete removes A on every branch but removes C only on the request branch. On every other branch where C exists, C keeps a required link to a node that no longer exists, so query 2 refuses the delete.

The test `backend/tests/component/core/test_node_manager_delete_agnostic.py::test_delete_refused_when_a_cascade_target_with_a_required_link_back_stays_on_another_branch` asserts this refusal.

### Example: deleting a repository

The facts below come from the core schema definitions in `backend/infrahub/core/schema/definitions/core/` and from `backend/infrahub/git/base.py`. The refusal itself has not been reproduced by a test. `test_delete_repository_repository_group_cascade` creates no branch.

- `CoreRepository`, `CoreReadOnlyRepository` and their generic `CoreGenericRepository` are branch-agnostic.
- A repository cascades to the nodes its import creates. The kinds reached are listed in `backend/tests/unit/core/node/test_delete_validator.py::test_repository_cascade_reaches_exactly_expected_kinds`.
- These cascade targets are branch-aware and have a required `repository` relationship:
  - `CoreCheckDefinition`;
  - `CoreTransformPython` and `CoreTransformJinja2`, through the generic `CoreTransformation`;
  - `CoreGeneratorDefinition`.
- `CoreRepositoryGroup` also has a required `repository` relationship, but it is branch-local. How the check treats a branch-local node on another branch has not been checked.
- A branch created after an import holds the imported nodes, because a branch reads the default branch's data up to the time it branched.
- Git sync creates an Infrahub branch for a git branch with `sync_with_git=True` and imports that git branch's objects on it. So some imported nodes exist on one Infrahub branch only.
- Deleting a repository has no flow of its own. It runs the generic node delete.

So, unless the rule changes, a repository delete is refused whenever another live branch holds one of these nodes.

### Options

| Option | Rule on other branches | Repository delete | What remains on other branches | Size of the change |
|---|---|---|---|---|
| A. Keep the refusal | A node with a required link to a deleted branch-agnostic node blocks, even when the cascade deletes it on the request branch | Refused until the user deletes the imported nodes on every branch, or deletes the branches | Nothing is left without its peer | None |
| B. Ignore nodes of the delete set | A node that the cascade deletes on the request branch does not block | Still refused when a branch holds an imported node that exists only there, because query 1 builds the delete set in the request branch's window | Those nodes keep a required link to a deleted node, as on `stable` | Small: query 2 excludes the delete set's ids instead of only the branch-agnostic ids |
| B2. Ignore cascade targets by schema | A link through a relationship on which the branch-agnostic node cascades never blocks, whether or not the node is in the delete set | Allowed | Same as B, also for nodes that exist on one branch only | Small: drop those relationships from the required relationships that query 2 checks |
| C. Cascade on every branch | On each live branch, delete the cascade targets that exist there, continue the cascade on that branch, and check the required peers of the larger delete set there | Allowed | Nothing is left without its peer | Large; see below |

What option C involves:

- It contradicts FR-016, which allows the cascade to write only on the request branch.
- It needs a cascade and a required-peer check for each branch, then a delete written on each branch.
- Every branch it writes to gets deletes that its user did not make. These deletes appear in that branch's diff, events and changelog.
- Whether the user needs permission to write on each of those branches is not decided.
- A merged branch is read-only (see decision 2), so option C cannot write there.
- FR-021 (user story 5) already writes `deleted` edges on user branches for links to a deleted branch-agnostic node, so option C extends work that is already planned.

What options B and B2 leave behind:

- A node on another branch with a required relationship that has no peer.
- FR-018 (user story 5) makes a read return a peer only if the peer exists in the read's view, so reads hide the missing peer.
- Editing that node on that branch would fail validation until the user sets the relationship again. This has not been checked.
- Merging a branch that created such a node writes it to the default branch with a link to the deleted node. What merge validation does then has not been checked.

### Questions for the discussion

- Is it acceptable that a repository cannot be deleted while branches exist (option A)? If not, should the repository delete get its own flow instead of a general rule?
- Which is worse for users: a delete that is refused, or nodes left on other branches with a required relationship that has no peer?
- Should option C ship with user story 5, which already writes on user branches, and should option B2 cover the gap until then?
- Does the answer depend on the relationship kind, for example a component relationship compared with a plain relationship that has `on_delete: cascade`?

## Decision 2: a merged branch blocks a delete for good

### What happens

Query 2 counts every branch that is not being deleted, including merged branches. Example:

1. Member M requires team T1 on the default branch.
2. Branch C is created, so C inherits the link from M to T1.
3. On the default branch, M moves to team T2.
4. Branch C is merged and kept.

Deleting T1 is now refused "on branch C". Nobody can edit C to remove the link, so only deleting C lets the delete through.

### What each branch status allows

Sources: `backend/infrahub/core/branch/enums.py::BranchStatus`, `backend/infrahub/permissions/resolver.py`, `backend/infrahub/branch/status_checker.py::BranchStatusChecker.check_merge_status` and `backend/infrahub/graphql/mutations/branch.py`.

| Status | Writes | Rebase or merge | Delete the branch |
|---|---|---|---|
| `MERGED` | Refused | Both refused | Allowed |
| `MERGE_FAILED` | Not checked | An administrator's recovery can still merge the branch's data into the default branch | Refused until an administrator recovers the branch |
| `MERGING` | Not checked | Both refused while the merge runs | Not checked |
| `NEED_REBASE` | Refused by the permission check | Rebase allowed | Allowed |

`TERMINAL_BRANCH_STATUSES` contains `MERGED` and `DELETING`.

### Options

| Option | Rule | Consequence | Size of the change |
|---|---|---|---|
| A. Keep | Every branch that is not being deleted counts | A stale link on a merged branch blocks the delete until someone deletes the branch | None |
| B. Skip merged branches in the delete check only | Branches with status `MERGED` are not checked. All other statuses still count, because their data can still change or reach the default branch | Reading the merged branch shows the link without its peer; FR-018 hides the peer on reads. The branch's changes were already merged, so the default branch is not affected | One condition in `NodeDeleteValidator._get_links_on_other_branches`: a merged branch gets no required relationships, so query 2 checks nothing there |
| C. Remove merged branches from the shared definition of a live branch | Merged branches stop counting for every check that reads live branch windows | Also changes the pool allocation of user story 3 and the peer reads that use live branches | Larger, and outside this PR |

### Questions for the discussion

- Should a merged branch that is kept still protect its data from deletes, or is it only a record?
- Should `MERGE_FAILED` count? Its data can still be merged by recovery.

## How the two decisions interact

- Option C of decision 1 cannot write on a merged branch, so it needs option B or C of decision 2.
- With options B or B2 of decision 1, a merged branch can still block through a peer that is not a cascade target, as in the example of decision 2.

## Spec items each option changes

- Decision 1, option B, B2 or C: the last sentence of FR-014 in [spec.md](spec.md), which says that a peer the cascade removes on another branch but not on the request branch blocks the delete when its relationship to the node is required, and the test named above. User story 4 scenario 3 covers only the optional case. Option C also changes FR-016.
- Decision 2, option B: the definition of "Live branch" in the Terms section of [spec.md](spec.md), or an exception to it in FR-014.
