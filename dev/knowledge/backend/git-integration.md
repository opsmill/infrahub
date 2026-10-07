# Git Integration

> Part of: `dev/knowledge/backend/` | Related: [Git Sync](git-sync.md), [Architecture](architecture.md)

How Infrahub models an external git repository, where the repository object comes from, and which
branch each operation actually targets. Read this before changing anything in `backend/infrahub/git/`:
the branch a given call site operates on is decided in three different places, and the most common
class of bug is an operation silently targeting the wrong one.

Branch import and mapping rules are covered in [Git Sync](git-sync.md) and are not repeated here.

## Two things are called "default branch"

These are independent and must never be substituted for one another.

| Term | Meaning | Source |
|---|---|---|
| `registry.default_branch` | Infrahub's own default branch. | `INFRAHUB_INITIAL_DEFAULT_BRANCH`, set once at initialization (`config.py::InitialSettings.default_branch`) |
| `CoreRepository.default_branch` | The branch on the **remote** that Infrahub treats as this repository's trunk. | Schema attribute, mandatory, defaults to `main` (the `default_branch` attribute on `CoreRepository` in `core/schema/definitions/core/repository.py`) |

`CoreRepository.default_branch` makes no claim about the remote's own default branch. Nothing in the
codebase reads `origin/HEAD`: `InfrahubRepositoryBase.get_branches_from_remote` skips the HEAD ref
outright, and there is no symbolic-ref anywhere in the module. A repository whose remote default is
`stable` but whose `default_branch` is `develop` is a valid, working configuration that simply means
"treat `develop` as this repository's trunk".

`CoreReadOnlyRepository` has no equivalent. It tracks a single `ref` attribute instead, and the
branch-mapping helpers are never used on it.

## Resolving the trunk on the repository object

Every construction of a read-write repository object reads the trunk from the repository node, on
the Infrahub branch the operation runs on, whether or not the worker already has a clone. There is
no fallback to Infrahub's default branch. The lifecycle (the resolver, the required fields, which
branch the node is read on) is in
[Git Sync](git-sync.md#the-repository-object-and-where-its-default-branch-comes-from).

`get_initialized_repo` is the factory most flows construct through: artifacts, transforms,
generators, computed attributes, proposed-change diffs and checks, and the message-bus git
operations. It is TTLCached for 30s keyed on repository id, name, kind, commit and the Infrahub
branch.

## Storage is per worker, not shared

Each task worker keeps its own clones. In the development stack the `task-worker` service runs with
`replicas: 2` and `INFRAHUB_GIT_REPOSITORIES_DIRECTORY: /opt/infrahub/git` with **no volume mounted
at that path** (`development/docker-compose.yml`), so replicas share nothing. Any reasoning about
"the repository's local state" has to be per worker.

Layout under `directory_root` (`get_repositories_directory() / str(repository.id)`):

- `main`: the primary clone.
- `branches`: worktrees for branches.
- `commits`: worktrees for individual commits.
- `temp`: worktrees for commits pending validation.

The `main` directory name is literal and unrelated to any branch name.
`InfrahubRepository._resolve_worktree_identifier` maps a non-Infrahub-default trunk onto that same
`main` identifier.

## How the workers converge

There is no primary worker and no shared filesystem. Convergence is a broadcast, and every
git-state mutation is serialized by a per-repository distributed lock taken as
`lock.registry.get(name=<repository name>, namespace="repository")`.

After mutating git state, the initiating worker resolves a concrete SHA and sends
`RefreshGitFetch` carrying it (six emission sites in `git/tasks.py`, covering repository add
read-write and read-only, periodic sync, branch create, read-only pull, and merge). Every other
worker takes the same repository lock, fetches, and then either hard-resets onto the pinned SHA or,
when no SHA was supplied, pulls (`git/convergence.py::WorktreeConverger`, which the `fetch` handler
in `message_bus/operations/git/repository.py` builds). A worker ignores its own broadcast by
comparing `meta.initiator_id` against `WORKER_IDENTITY`. A worker that lacks the branch creates its
worktree in its own clone only and never pushes it, so a branch deleted on the remote after the sync
does not come back.

The periodic sync sends one message per repository per cycle. Its `branches` list starts with the
trunk, on every cycle, and then names every other branch the cycle advanced, each with its pinned
commit. The trunk is listed at its local head even when its import failed; any other branch whose
import failed is not listed. The receiving worker resets each entry inside one lock hold and after
one fetch, and a branch it cannot reset is logged and skipped. The single-branch fields repeat the
first entry, so a worker on older code still converges the trunk. The message is sent even when a
branch of the cycle failed. Listing the trunk on an idle cycle is what brings back a worker that
missed an earlier message. When the cycle cannot read the trunk's commit, the trunk entry carries no
commit, and every worker pulls the trunk instead of resetting it.

Pinning a SHA rather than a branch name is deliberate: the remote may advance between the
initiating worker's operation and a receiving worker's fetch, and a pull would land that worker
somewhere else. The handler passes `update_commit_value=False`, so a broadcast never writes to
the graph - the initiating worker owns that write.

`InfrahubRepositoryBase.reset_to_commit` is the primitive behind the pinned path. It hard-resets
the branch worktree and intentionally discards local divergence, on the principle that a worktree
is a disposable mirror of the remote. It does not contact the remote; the caller must have fetched
the commit first.

### No path runs `git pull`

Each path that moves a branch worktree from the remote compares it with the remote head by ancestry
first, and resets a worktree that does not lead to that head:

- The periodic sync resets in its collector. `compare_local_remote` compares heads by equality only,
  and the collector then classifies each branch by ancestry.
  [Git Sync](git-sync.md#rewritten-history) describes how.
- `InfrahubRepositoryBase.pull` fetches the branch and hard-resets onto the remote head when the
  worktree does not lead to it. Otherwise it fast-forwards with `git merge --ff-only`, whatever the
  pull settings of the clone. It writes no rewrite record and emits no event.

`pull` runs only for a message entry that pins no commit, as [above](#how-the-workers-converge).

## Sync triggers, and what does not wait for what

| Trigger | Entry point | Notes |
|---|---|---|
| Periodic sync | `git.tasks.sync_remote_repositories` | Cron `* * * * *`, `concurrency_limit=1`, `CANCEL_NEW` (`workflows/catalogue.py::GIT_REPOSITORIES_SYNC`). Pull direction only; it never pushes. |
| Add repository | `git.tasks.add_git_repository` / `..._read_only` | Clone, import, broadcast. |
| Create branch | `git.tasks.create_branch` | Create in git, push, broadcast. |
| Proposed-change merge | `core/merge/repository_merge_dispatcher.py` → `git.tasks.merge_git_repository` | Merge and push, read-write repositories only. |
| Read-only pull | `git.tasks.pull_read_only` | On-demand fetch latest. |

The merge trigger is **not ordered against post-merge regeneration**.
`PostMergeDispatcher.run_follow_ups` submits the repository merge and then `BRANCH_MERGE_POST_PROCESS`;
both go through `submit_workflow` (`services/adapters/workflow/worker.py`), which is
`run_deployment(..., timeout=0)` and returns immediately. `post_process_branch_merge`
(`core/branch/tasks.py`) dispatches regeneration without waiting on the repository merge, and artifact
generation reads the destination branch's commit from the graph node at the moment it runs. Nothing
guarantees which of the two flows the scheduler reaches first.

> **Volatile section.** The intended fix for this ordering gap is a persisted writeback state,
> recorded before the merge workflow is submitted, that holds regeneration for repository-owned
> definitions until that repository's commit on the destination branch is final. It is specified in
> `dev/specs/ifc-3220-writeback-failure-handling/`. Update this section when that lands.

## Pushing back to the remote

`InfrahubRepository.push` sends the worktree HEAD rather than a bare branch name:

```python
# git/repository.py::InfrahubRepository.push
remote_branch = self._get_mapped_remote_branch(branch_name=branch_name)
push_infos = repo.remotes.origin.push(refspec=f"HEAD:refs/heads/{remote_branch}")
```

A bare refspec would have no local source on a worker whose clone never checked out a local branch
named after the remote one, which is the case whenever the trunk is not Infrahub's default. Before
`push` sent the worktree HEAD, that bare refspec failed with `src refspec <branch> does not match any`
while the merge still reported success; sending HEAD is what closed that gap.

### The writeback direction has no reconciliation

The pull direction has the once-a-minute loop. The push direction has nothing equivalent.

`InfrahubRepository.merge` merges into the destination worktree, pushes, and only then creates the
commit worktree and writes the new commit to the graph. A rejected push therefore records nothing.
After a rejected push, and after a failure to record a pushed commit, `merge` tries to reset the
destination worktree to its pre-merge commit. The reset is best-effort: it never raises, so the
original failure propagates unmasked.

- When the reset succeeds, a re-run of the merge re-derives it instead of finding nothing to merge.
  After a failed record, the reset leaves the worktree behind the remote, and the periodic sync then
  resets the worktree onto the pushed commit and records it.
- When the reset fails, `merge` logs the failure and says that manual reconciliation may be
  required. The worktree can stay on a merge commit that the graph does not record, and a re-run can
  then find nothing to merge, until the next sync resets the worktree onto the remote head.

What remains is that nothing ever re-pushes. `push()` is reachable only from branch creation and
`merge()`, the periodic sync only reads from the remote, and `merge_git_repository` has no retry. A rejected push
stays undelivered until a later merge into the same destination, and nothing on the repository
records that it failed: the only trace is the failed flow run.

With `git.use_explicit_merge_commit` at its default of `False` the merge fast-forwards where it can
and the resulting SHA is the source commit, which the remote already has. When the destination has
diverged, or when that setting is enabled, git creates a real merge commit whose SHA embeds a
timestamp and is therefore not reproducible. A reset that succeeds discards it, so a later attempt
re-derives the merge from `(source_branch, source_commit, dest_branch)` on any worker.

> **Volatile section.** A delivery queue with retry and abandon actions is specified in
> `dev/specs/ifc-3220-writeback-failure-handling/`. Update this section when that lands.

Per-ref push rejections do **not** flow through the error classifier below. GitPython reports them on
`push_info.summary`, not by raising `GitCommandError`, so `push()` inspects `push_info.flags` and
raises `RepositoryError` itself. Anything that needs to distinguish a non-fast-forward rejection from
a per-ref permissions denial has to parse that summary.

A push that fails at the **transport** level (a 403 on the receive-pack advertisement, an expired
token, a refused connection, a TLS failure) is different: GitPython finds no porcelain status line to
parse and re-raises `GitCommandError`. `push()` catches that and routes it through the same enriched
classifier a fetch uses, so it is converted to the typed error and recorded on `operational_status`.

### Two checks keep a merge on the commits the graph imported

A merge does not move a worktree from the remote: it builds on the local destination and merges the
local source ref. Two checks keep it on the commits the graph imported. Only the first one holds a
merge after a plain push and keeps the branch open:

- Before the graph merge, `merge_branch` reads the remote heads of the source branch and of the trunk
  with `git ls-remote` and compares them with the commits the graph records
  (`git/merge_readiness.py::RemoteHeadsMergeCheck`). While one differs, it refuses the merge with
  `RepositoryNotSynchronizedError`, so the branch stays open and the user merges again after the next
  cycle. It compares for equality, so a plain push to the source branch, or to the trunk of a
  repository the branch changed, holds the merge too, not only a rewrite, until the next cycle imports
  the new head. A remote that refuses the credentials blocks the merge, with
  `RepositoryCredentialsRefusedError`, when the repository needs a Git merge: that Git merge would
  fail the same way after the graph merge. Any other failure to read a remote, and a remote not read
  before the total deadline of the check (`REMOTE_HEADS_DEADLINE_SECONDS`), logs a warning and does
  not block the merge. For a
  repository whose source branch records the commit its trunk records, the check reads the source
  branch only, and the dispatcher runs no Git merge for it: there is nothing to push.
- In the Git merge, `InfrahubRepository.prepare_branches_for_merge` fetches the heads of the remote
  branches, with no tags because a tag moved on the remote would fail the fetch, then compares the
  local source ref and the local trunk worktree with their remote heads. A fetch that fails says how
  to finish the merge in Git. The source graph commit comes in
  the merge model (`GitRepositoryMerge`), read when the merge was dispatched, because the source
  branch can be deleted before the Git merge runs. `merge_git_repository` reads the destination graph
  commit under the repository lock, because an earlier Git merge can move the trunk after the
  dispatch. Each branch is compared with its graph commit, also when the clone holds the remote head:
  - A graph commit equal to the remote head: a clone behind, ahead (the remote was rewound) or
    diverged moves onto that head, because only this clone is stale.
  - Ahead or diverged, with a graph commit that differs: the merge is refused, because the rewrite is
    not recorded yet.
  - A trunk on or behind its remote head, with a graph commit that differs: the merge is refused. On
    an older trunk the remote would reject the push. On a head the graph never imported, the record
    of the merge commit would hide that head from the next cycle. A plain push to the trunk that
    lands between the two checks ends here.
  - A source on or behind its remote head, with a graph commit that differs: the source moves onto
    the graph commit when the remote history holds it, forward or back, so the merge holds what the
    graph merged. The commits after it stay on the source branch and do not reach the trunk, and a
    warning says so, because the branch is merged in Infrahub already and a refusal cannot help.
  - Known risk: a source whose graph commit is missing, or no longer in the remote history, is merged
    as it is, and can differ from what the graph merged.

  A refusal raises `RepositoryDivergentHistoryError`. It comes after the graph merge: the branch is
  merged in Infrahub and not in Git, nothing runs the Git merge again, and the message tells the user
  to finish the merge in Git.

> **Volatile section.** A rewrite of the trunk emits no signal yet, and nothing recovers a Git merge
> the guard refused: the user finishes it in Git. The delivery queue specified in
> `dev/specs/ifc-3220-writeback-failure-handling/` does not recover it either. After a rewrite of the
> source or of the trunk, it only marks such a delivery as one it cannot replay. After a plain push
> to the trunk between the two checks, it specifies no recovery at all. Update this section when
> either lands.

## Repository state and branch support

Repository nodes are `BranchSupportType.AGNOSTIC` at the node level (`CoreRepository`,
`CoreReadOnlyRepository`, and `CoreGenericRepository` in
`core/schema/definitions/core/repository.py`), with the operational attributes overridden
individually:

| Attribute | Branch support | Consequence |
|---|---|---|
| `CoreRepository.commit`, `sync_status`, `internal_status` | LOCAL | Per-branch value, never diffed, never merged |
| `operational_status` | AGNOSTIC | One value shared by every branch |
| `name`, `description`, `location` | AGNOSTIC | One value shared by every branch |
| `CoreReadOnlyRepository.commit` and `.ref` | AWARE | Per-branch value that **does** reach diffs and merges |

`CoreReadOnlyRepository` sets `commit` to AWARE and adds an AWARE `ref` of its own. Reasoning that
per-branch repository state is invisible holds for `CoreRepository` and not for the read-only kind.

LOCAL is what makes per-branch repository state invisible to users. The diff query
(`core/query/diff.py`) selects only `node.branch_support IN [$branch_aware, $branch_agnostic]`, and
the bulk merge (`core/diff/query/bulk_merge.py`) touches only `branch_support = "aware"`. So a LOCAL
attribute never appears in a branch diff or a proposed change, and can never produce a merge
conflict. That is why nobody has ever had to resolve a conflict on `sync_status`.

`sync_status` still never diffs or conflicts, but it is no longer invisible on a proposed change:
the repository validator fails the pipeline when the source branch recorded `error-import`.

Reading a LOCAL value on a branch does not tell you whether the branch wrote it. Branches are
isolated, so a branch that never imported a repository reads the value its base branch held at
`branched_from`, frozen there: a branch created while the default
branch was in `error-import` keeps reading `error-import` after the default branch recovers, until
it is rebased. The import check therefore only counts a value the source branch wrote
(`git/sync_status.py::RepositoryBranchSyncStatusReader`), recognised by the attribute's `updated_at`
being at or after `branched_from`; an inherited value is older and passes.

The comparison must be `>=`, not `>`. A rebase (`RebaseBranchQuery`) sets `from` on every live edge
of the branch to the rebase time and moves `branched_from` to that same time, so a value the branch
wrote before the rebase ends up with `updated_at == branched_from`.

AGNOSTIC buys conflict-freedom but **not** invisibility: agnostic nodes do reach the diff, forced
to `DiffAction.UPDATED` because a globally-stored node has no created/deleted distinction on a branch
(`core/diff/query_parser.py`). New per-branch operational state belongs on the repository node as a
LOCAL attribute, not on a related node.

## Staging repositories

A repository being validated inside a proposed change carries `internal_status` of `staging`
(`InfrahubRepository.internal_status`, a required field read from the node). The staging branch is resolved per sync
from `RepositoryData.get_staging_branch` (`git/models.py`), which scans `branch_info` for the entry
whose `internal_status` is `staging`. `InfrahubRepository.collect_pending_imports` pairs that branch
with the repository's trunk: it advances the trunk worktree and imports its commit into the staging branch.

## Deleting a repository is destructive

`CoreRepository` cascades on delete to **transformations, queries, checks, generators and repository
groups** (five relationships on `CoreGenericRepository` with
`on_delete=RelationshipDeleteBehavior.CASCADE`). It also inherits `LineageOwner` and `LineageSource`,
so every node it created references it. Removing and re-adding a repository is not a cheap
reconfiguration step and should not be proposed as a remedy for a misconfigured attribute.

## How git errors are classified

`InfrahubRepositoryBase._raise_enriched_error_static` maps `GitCommandError.stderr` to typed
exceptions: `RepositoryConnectionError` (unreachable host, gateway 5xx, TLS verification failure),
`RepositoryCredentialsError`, `RepositoryPermissionError` (authenticated but not authorized to push -
a 403 on the receive-pack advertisement, "Write access to repository not granted", "Permission to ...
denied"), `RepositoryInvalidBranchError`, or a generic `RepositoryError`. `RepositoryPermissionError`
maps to the same `ERROR_CRED` operational status as a credential failure; the distinction is carried
in the message.

It matches on **stderr text, not exit status**, because git exits 128 for virtually every fatal
error and an HTTP failure surfaces only as text from the libcurl remote helper. The matched
substrings are stable user-facing git and curl strings, but they are still strings: a wording change
upstream silently reclassifies an error to the generic fallthrough.

One gap to know about: **per-ref push rejections bypass it** (see above); they arrive on
`push_info.summary`. Transport-level push failures do reach it, because those raise `GitCommandError`.

A diverged history gets a message of its own, never a conflict. The merge guard raises
`RepositoryDivergentHistoryError` itself. The classifier has no entry for git's "Need to specify how
to reconcile divergent branches", because only `git pull` writes that text and no path runs it. Only
"you have unmerged files", which is a conflict git observed, is reported as one.

## Known limitations

- **Editing `default_branch` after creation is not reconciled.** The attribute is freely editable and
  the periodic sync picks up the new value on the next cycle, but nothing re-clones, re-validates, or
  reconciles branches already imported under the old mapping. The commit recorded against Infrahub's
  default branch changes to the new trunk's history, and a previously imported branch of that name is
  left orphaned. `get_initialized_repo` is also cached for 30s, so an edit is served stale for up to
  that long; this is consistent with the lack of reconciliation rather than a separate bug. The sync
  is never told that the tracking target changed, so it never classifies a branch as re-targeted. When
  the old trunk commit is not an ancestor of the new trunk, it classifies the edit as a rewrite and
  logs the trunk as reconciled.
- **A skipped branch is re-evaluated every cycle.** A remote branch named like Infrahub's default, on
  a repository whose trunk is something else, is never created locally by the sync, so every sync
  usually skips it again and the process log repeats once a minute. The exception is a clone whose
  remote HEAD is that branch: the clone holds it locally, so it is not re-evaluated, and nothing is
  logged, until it moves. The operator-facing warning is gated separately, and a
  push to that branch can go unreported when more than one worker runs; both are covered in
  [Git Sync](git-sync.md#branch-import-and-mapping).
- **`CommitUpdatedEvent` is emitted but has no subscribers.** It is sent from
  `InfrahubRepositoryIntegrator.apply_import_plan` and no `EventTrigger` anywhere lists
  `infrahub.repository.update_commit` in its events set. It is not a working signal; wiring anything
  to it means introducing the first consumer. The merge path does not emit it at all, and the
  `RefreshGitFetch` handler explicitly suppresses the commit write that would.
- **Remote branch deletion is not gated on writeback state.** `git.tasks.git_branch_delete` deletes
  the remote branch gated only on `origin_has_branch`, and `BRANCH_DELETE` is submitted concurrently
  with the repository merge (`core/merge/post_merge.py`). With `delete_branch_after_merge` enabled, a
  rejected push plus a successful branch delete can leave the remote holding neither the source commit
  nor the merged content.
