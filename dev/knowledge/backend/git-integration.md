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
| `registry.default_branch` | Infrahub's own default branch. | `INFRAHUB_INITIAL_DEFAULT_BRANCH`, set once at initialization (`config.py:801-804`) |
| `CoreRepository.default_branch` | The branch on the **remote** that Infrahub treats as this repository's trunk. | Schema attribute, mandatory, defaults to `main` (`core/schema/definitions/core/repository.py:41-47`) |

`CoreRepository.default_branch` makes no claim about the remote's own default branch. Nothing in the
codebase reads `origin/HEAD`: `get_branches_from_remote` skips the HEAD ref outright
(`git/base.py:513-530`), and there is no symbolic-ref anywhere in the module. A repository whose
remote default is `stable` but whose `default_branch` is `develop` is a valid, working configuration
that simply means "treat `develop` as this repository's trunk".

`CoreReadOnlyRepository` has no equivalent. It tracks a single `ref` instead
(`core/schema/definitions/core/repository.py:78-85`), and the branch-mapping helpers are never used
on it.

## Resolving the trunk on the repository object

`InfrahubRepositoryBase` holds an optional `default_branch_name` (`git/base.py:158`) exposed through:

```python
# git/base.py:190-192
@property
def default_branch(self) -> str:
    return self.default_branch_name or registry.default_branch
```

The fallback is silent. When `default_branch_name` is unset, the object treats **Infrahub's** default
branch as the remote's trunk, with no log line, no error, and no status change.

Only `resolve_checkout_ref` loads the value from the graph (`git/repository.py:87-94` for read-write,
`:384-398` for read-only), and `init()` calls it **only** inside the failure branch:

```python
# git/integrator.py:246-256 (abridged)
try:
    self.validate_local_directories()
except RepositoryInvalidFileSystemError:
    await self.create_locally(checkout_ref=await self.resolve_checkout_ref(), ...)
```

The practical consequence, and the shape of most reported non-`main` bugs:

- **Worker has no local clone (cold path):** validation raises, `resolve_checkout_ref()` runs, the
  trunk is resolved correctly.
- **Worker already has a local clone (warm path):** validation passes, `resolve_checkout_ref()` never
  runs, and the object falls back to Infrahub's default branch.

So a repository behaves correctly on a worker's first touch and incorrectly on every subsequent one.

### Which construction paths resolve it today

| Path | Passes the trunk? |
|---|---|
| Periodic sync (`git/tasks.py:284,298,345`) | Yes, explicitly from the node |
| Merge (`core/merge/repository_merge_dispatcher.py:82` → `git/tasks.py:734-736`) | Yes, explicitly via `GitRepositoryMerge.default_branch` |
| `get_initialized_repo` (`git/repository.py:469-497`) | **No.** Constructs with id, name, commit, client only |

`get_initialized_repo` is the factory used by roughly sixteen call sites, including artifacts,
transforms, generators, computed attributes, proposed-change diffs and checks, and the message-bus
git operations. It is TTLCached for 30s keyed on repository id, name, kind and commit.

> **Volatile section.** The fallback and the unresolved factory are a known defect (IFC-2870). The
> planned fix makes the trunk a required field resolved once inside `_get_initialized_repo`, removing
> the `or registry.default_branch` fallback entirely. Update this section when that lands.

## Storage is per worker, not shared

Each task worker keeps its own clones. In the development stack `task-worker` runs with `replicas: 2`
and `INFRAHUB_GIT_REPOSITORIES_DIRECTORY: /opt/infrahub/git` with **no volume mounted at that path**
(`development/docker-compose.yml:229-252`), so replicas share nothing. Any reasoning about "the
repository's local state" has to be per worker.

Layout under `directory_root` (`get_repositories_directory() / str(repository.id)`):

- `main`: the primary clone.
- `branch`: worktrees for branches.
- `commit`: worktrees for individual commits.
- `temp`: worktrees for commits pending validation.

The `main` directory name is literal and unrelated to any branch name. `_resolve_worktree_identifier`
maps a non-Infrahub-default trunk onto that same `main` identifier (`git/base.py:927-931`).

## How the workers converge

There is no primary worker and no shared filesystem. Convergence is a broadcast, and every
git-state mutation is serialized by a per-repository distributed lock taken as
`lock.registry.get(name=<repository name>, namespace="repository")`.

After mutating git state, the initiating worker resolves a concrete SHA and sends
`RefreshGitFetch` carrying it (six emission sites in `git/tasks.py`, covering repository add
read-write and read-only, periodic sync, branch create, read-only pull, and merge). Every other
worker takes the same repository lock, fetches, and then either hard-resets onto the pinned SHA or,
when no SHA was supplied, pulls (`message_bus/operations/git/repository.py:45-76`). A worker ignores
its own broadcast by comparing `meta.initiator_id` against `WORKER_IDENTITY`.

Pinning a SHA rather than a branch name is deliberate: the remote may advance between the
initiating worker's operation and a receiving worker's fetch, and a pull would land that worker
somewhere else. The handler passes `update_commit_value=False`, so a broadcast never writes to
the graph - the initiating worker owns that write.

`reset_to_commit` (`git/base.py:988-1023`) is the primitive behind the pinned path. It hard-resets
the branch worktree and intentionally discards local divergence, on the principle that a worktree
is a disposable mirror of the remote. It does not contact the remote; the caller must have fetched
the commit first.

## Sync triggers, and what does not wait for what

| Trigger | Entry point | Notes |
|---|---|---|
| Periodic sync | `git.tasks.sync_remote_repositories` | Cron `* * * * *`, `concurrency_limit=1`, `CANCEL_NEW` (`workflows/catalogue.py:177-185`). Pull direction only; it never pushes. |
| Add repository | `git.tasks.add_git_repository` / `..._read_only` | Clone, import, broadcast. |
| Create branch | `git.tasks.create_branch` | Create in git, push, broadcast. |
| Proposed-change merge | `core/merge/repository_merge_dispatcher.py` → `git.tasks.merge_git_repository` | Merge and push, read-write repositories only. |
| Read-only pull | `git.tasks.pull_read_only` | On-demand fetch latest. |

The merge trigger is **not ordered against post-merge regeneration**. `PostMergeDispatcher.run_follow_ups`
submits the repository merge (`core/merge/post_merge.py:76-77`) and then `BRANCH_MERGE_POST_PROCESS`
(`:106-114`); both go through `submit_workflow`, which is `run_deployment(..., timeout=0)` and returns
immediately (`services/adapters/workflow/worker.py:113-119`). `post_process_branch_merge` dispatches
regeneration without waiting on the repository merge (`core/branch/tasks.py:543-552`), and artifact
generation reads the destination branch's commit from the graph at the moment it runs
(`git/tasks.py:616`). Nothing guarantees which of the two flows the scheduler reaches first.

> **Volatile section.** Closing this ordering gap is INFP-670 scope: the intended fix is a persisted
> writeback state, recorded before the merge workflow is submitted, that holds regeneration for
> repository-owned definitions until that repository's commit on the destination branch is final.
> Update this section when that lands.

## Pushing back to the remote

`push` sends the worktree HEAD rather than a bare branch name:

```python
# git/repository.py:300-305
remote_branch = self._get_mapped_remote_branch(branch_name=branch_name)
push_infos = repo.remotes.origin.push(refspec=f"HEAD:refs/heads/{remote_branch}")
```

A bare refspec would have no local source on a worker whose clone never checked out a local branch
named after the remote one, which is the case whenever the trunk is not Infrahub's default. This is
the fix for IFC-2740; a bare refspec fails with `src refspec <branch> does not match any` and the
merge still reports success.

### The writeback direction has no reconciliation

The pull direction has the once-a-minute loop. The push direction has nothing equivalent, and three
properties compound:

- `merge()` writes the new commit to the graph **before** pushing (`git/repository.py:347` then
  `:349`), so a rejected push leaves the graph naming a commit the remote never received.
- Nothing ever re-pushes. `push()` is reachable only from branch creation and `merge()`; the periodic
  sync only pulls.
- Re-running the merge no-ops. `merge()` returns `False` when `commit_after == commit_before`
  (`git/repository.py:343-344`) computed from local git state, and `merge_git_repository` ignores the
  return value, so once the local merge has happened a re-triggered merge never reaches `push()`.

A merge commit created this way also exists on exactly one worker's disk: the `RefreshGitFetch`
broadcast is sent after `merge()` returns, so a failed push aborts the flow before any other worker
hears about it. With `git.use_explicit_merge_commit` at its default of `False` the merge
fast-forwards where it can and the resulting SHA is the source commit, which the remote already has.
When the destination has diverged, or when that setting is enabled, git creates a real merge commit
whose SHA embeds a timestamp and is therefore not reproducible.

> **Volatile section.** INFP-670 reorders this so the push precedes the graph write and the
> destination worktree is reset on failure, which makes the discarded merge commit harmless and lets
> any worker re-derive the merge from `(source_branch, source_commit, dest_branch)`. Update this
> section when that lands.

Push rejections do **not** flow through the error classifier below. GitPython reports them on
`push_info.summary`, not by raising `GitCommandError`, so `push()` inspects `push_info.flags` and
raises `RepositoryError` itself (`git/repository.py:306-311`). Anything that needs to distinguish a
non-fast-forward rejection from a permissions denial has to parse that summary.

## Repository state and branch support

Repository nodes are `BranchSupportType.AGNOSTIC` at the node level
(`core/schema/definitions/core/repository.py:32,69,107`), with the operational attributes overridden
individually:

| Attribute | Branch support | Consequence |
|---|---|---|
| `commit`, `sync_status`, `internal_status` | LOCAL | Per-branch value, never diffed, never merged |
| `operational_status` | AGNOSTIC | One value shared by every branch |
| `name`, `description`, `location` | AGNOSTIC | One value shared by every branch |

LOCAL is what makes per-branch repository state invisible to users. The diff query selects only
`node.branch_support IN [$branch_aware, $branch_agnostic]` (`core/query/diff.py:360`), and the bulk
merge touches only `branch_support = "aware"` (`core/diff/query/bulk_merge.py:68,186,326,731,861`).
So a LOCAL attribute never appears in a branch diff or a proposed change, and can never produce a
merge conflict. That is why nobody has ever had to resolve a conflict on `sync_status`.

AGNOSTIC buys conflict-freedom but **not** invisibility: agnostic nodes do reach the diff, forced
to `DiffAction.UPDATED` because a globally-stored node has no created/deleted distinction on a branch
(`core/diff/query_parser.py:552-565`). New per-branch operational state belongs on the repository node
as a LOCAL attribute, not on a related node.

## Staging repositories

A repository being validated inside a proposed change carries `internal_status` of `staging`
(`git/base.py:173`, default `active`). The staging branch is resolved per sync from
`RepositoryData.get_staging_branch()` (`git/models.py:269`), which scans `branch_info` for the entry
whose `internal_status` is `staging`. `_collect_staging_imports` (`git/repository.py:260-284`) pairs
that branch with the repository's trunk, so staging inherits whatever the object resolved: it is
correct exactly when the trunk is correct, and wrong in the same cases.

## Deleting a repository is destructive

`CoreRepository` cascades on delete to **transformations, queries, checks, generators and repository
groups** (`core/schema/definitions/core/repository.py:277-315`, five relationships with
`on_delete=RelationshipDeleteBehavior.CASCADE`). It also inherits `LineageOwner` and `LineageSource`,
so every node it created references it. Removing and re-adding a repository is not a cheap
reconfiguration step and should not be proposed as a remedy for a misconfigured attribute.

## How git errors are classified

`_raise_enriched_error_static` (`git/base.py:1155-1199`) maps `GitCommandError.stderr` to typed
exceptions: `RepositoryConnectionError` (unreachable host, gateway 5xx, TLS verification failure),
`RepositoryCredentialsError`, `RepositoryInvalidBranchError`, or a generic `RepositoryError`.

It matches on **stderr text, not exit status**, because git exits 128 for virtually every fatal
error and an HTTP failure surfaces only as text from the libcurl remote helper. The matched
substrings are stable user-facing git and curl strings, but they are still strings: a wording change
upstream silently reclassifies an error to the generic fallthrough.

Two gaps to know about:

- **Push rejections bypass it entirely** (see above); they arrive on `push_info.summary`.
- **Divergence is misreported as conflict.** The workers configure no `pull.rebase` or `pull.ff`
  (`workers/infrahub_async.py:238-244`), so a branch whose remote history was rewritten fails
  `git pull` with "Need to specify how to reconcile divergent branches", which the classifier maps to
  "there are conflicts that must be resolved" (`git/base.py:1195-1199`). There is no conflict. A
  user acting on that message will look for a merge conflict that does not exist.

`compare_local_remote` cannot tell the two situations apart in the first place: it compares only
`remote_branches[b].commit != local_branches[b].commit` (`git/base.py:872-879`), so a fast-forward
and a rewritten history are indistinguishable and both are reported as "New commit detected".

> **Volatile section.** INFP-670 adds divergence detection here, and reconciles a rewritten branch by
> hard-resetting to the remote and broadcasting, rather than failing. Update this section when that
> lands.

## Known limitations

- **Editing `default_branch` after creation is not reconciled.** The attribute is freely editable and
  the periodic sync picks up the new value on the next cycle, but nothing re-clones, re-validates, or
  reconciles branches already imported under the old mapping. The commit recorded against Infrahub's
  default branch changes to the new trunk's history, and a previously imported branch of that name is
  left orphaned. `_get_initialized_repo` is also cached for 30s, so an edit is served stale for
  up to that long; this is consistent with the lack of reconciliation rather than a separate bug.
- **A skipped branch is re-reported every cycle.** When `validate_remote_branch` rejects a branch it
  is never created locally, so `compare_local_remote()` classifies it as new again on the next cycle.
  A remote branch named like Infrahub's default, on a repository whose trunk is something else, logs
  "Ignoring import of mismatched default branch" once a minute for the life of the repository
  (`git/base.py:890-895`, called from `git/repository.py:178,211`).
- **A branch left ahead of its remote is re-reported every cycle too.** After a failed push the local
  branch sits ahead of `origin/`, so `compare_local_remote` flags it as updated, `pull()` returns
  `True` with no change, and "An update was detected but the commit remained the same after `pull()`"
  is logged once a minute (`git/repository.py:232-237`).
- **`CommitUpdatedEvent` is emitted but has no subscribers.** It is sent from `apply_import_plan`
  (`git/integrator.py:431`) and no `EventTrigger` anywhere lists `infrahub.repository.update_commit`
  in its events set. It is not a working signal; wiring anything to it means introducing the first
  consumer. The merge path does not emit it at all, and the `RefreshGitFetch` handler explicitly
  suppresses the commit write that would.
- **Remote branch deletion is not gated on writeback state.** `git_branch_delete`
  (`git/tasks.py:465-485`) deletes the remote branch gated only on `origin_has_branch`, and
  `BRANCH_DELETE` is submitted concurrently with the repository merge (`core/merge/post_merge.py:99-104`).
  With `delete_branch_after_merge` enabled, a rejected push plus a successful branch delete can
  leave the remote holding neither the source commit nor the merged content.
