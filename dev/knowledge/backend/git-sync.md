# Git Sync

> Part of: `dev/knowledge/backend/` | Related: [Architecture](architecture.md)

How Infrahub maps and imports branches from external git repositories, and how git errors surface.
Read this before reasoning about which remote branches get imported or why a git failure carries
(or lacks) a message — the logic is split across several methods and is easy to mis-trace.

## The repository object and where its default branch comes from

The per-flow repository object is built by `InfrahubRepository.init` / `.new`, and those are the only
two places that read a read-write repository's configuration from the graph. They call
`resolve_graph_settings` (`backend/infrahub/git/graph_settings.py`), which performs one SDK read of
the repository node and returns its default branch, internal status and location.

- **The default branch is a required constructor field.** `InfrahubRepository` declares
  `default_branch: str` and `internal_status: RepositoryInternalStatus` with no defaults, so an
  object cannot exist without them. There is no fallback to Infrahub's default branch anywhere.
- **Every construction resolves it**, not only the one that clones. The object is therefore correct
  whether or not the worker already had a local copy — the distinction that used to decide whether
  the graph was read at all.
- **The read happens on a named Infrahub branch.** `get_initialized_repo` and both factories take a
  required `infrahub_branch_name`, which is also added to the factory's 30-second cache key. The
  branch matters because `internal_status` is branch-scoped and a repository created inside a branch
  exists only there until its proposed change merges.
- **The factories set `infrahub_branch_name` on the instance** from that parameter, so the branch the
  node was read on and the branch the object reports are one value. `_update_operational_status`
  reads it, so status writes name the branch the operation ran on. That attribute is
  `BranchSupportType.AGNOSTIC`, though, so its value is shared across branches and the named branch
  has no observable effect on what an operator sees.
- **The read-only kind has no default branch at all.** It tracks a single `ref`, and the three
  branch-mapping hooks below are the identity on it.

Three abstract hooks on `InfrahubRepositoryBase` keep the base class from needing a default branch of
its own: `_get_mapped_remote_branch`, `_get_mapped_target_branch` and `_resolve_worktree_identifier`.
The read-write kind implements the mapping described below; the read-only kind returns its input.

## Branch import and mapping

- A repository's own `default_branch` is mapped onto Infrahub's default branch by
  `_get_mapped_target_branch` on `InfrahubRepository`: when a commit lands on the
  repository's default branch, it is recorded against Infrahub's default branch, whatever either
  is named.
- Because of that mapping, when the repository's default branch differs from Infrahub's, a remote
  branch literally named like Infrahub's default branch cannot be imported — it would collide with
  the mapped default. The skip is decided in `InfrahubRepository.validate_remote_branch`, *not* in
  `_get_mapped_target_branch`. It returns `False` for this case and for a name Infrahub cannot
  store as a branch, and `True` for a branch to import. The collision test itself is one method,
  `_collides_with_infrahub_default_branch`, which `validate_remote_branch` and the skip record both
  call, so nothing re-derives it.
- The sync never creates the colliding branch locally, so it usually shows up as new on every sync
  and is skipped again, logging "Ignoring import of mismatched default branch" to the process log
  each time. A clone whose remote HEAD is the colliding branch does hold it as a local branch, and
  the local/remote comparison does not list it until it moves. So `collect_pending_imports` decides
  the skip from the remote alone: whenever the remote has the colliding branch, it is recorded in
  `CollectedImports.skipped_branches`, whether or not the comparison listed it.
- It is also recorded in `advanced_skipped_branches` when its remote head moved during this run's
  fetch. Its remote-tracking ref is read before the fetch and compared after it. A branch absent from
  that earlier read counts as moved, because it was pushed after this clone's last fetch. A worker
  with no clone makes one before the read, so its first sync does not see the branch as new.
- `RepositorySyncer.sync` returns a `SyncReport` of the skipped, imported and advanced branches. When
  a branch fails, it raises `RepositoryBranchesFailedError` carrying the same report, so a caller can
  still report the skipped branches before re-raising.
- The operator-facing record of the skip is a warning in the flow run's log, emitted through
  Prefect's run logger. The add flow writes it whenever its first sync skips a branch. The
  per-repository sync flow writes it only when the run imported a branch or saw a skipped branch
  advance (`SyncReport.reports_skipped_branches`).
- That sync flow's run is linked to the repository node when it imports a branch (the import tags the
  run itself), when it writes the warning, or when it fails while the repository is online. A
  successful run where nothing moved adds nothing to the repository's task history. Every tag update
  is rebuilt from the tags the run started with, so a later `add_tags` call must repeat the branches
  the imports tagged, or it drops them.
- The reverse mapping — from an Infrahub branch name to the remote git branch — is
  `_get_mapped_remote_branch`. Any git operation that names a remote ref (`pull`, `push`) must
  route the branch name through it: when the repository's default branch differs from Infrahub's,
  the remote has no branch named after the Infrahub default, and the raw name fails with
  "couldn't find remote ref".
- `git.import_sync_branch_names` (settings) is a list of names or regex patterns selecting which
  other remote branches are imported during sync; branches created in Infrahub with
  `sync_with_git` are imported regardless.

### A push to the skipped branch can go unreported

The advance check compares against the remote-tracking refs, and those move on every fetch, not only
the sync's own. After each successful sync the initiating worker broadcasts `RefreshGitFetch`, and every other
worker fetches on receipt (see [Git Integration](git-integration.md#how-the-workers-converge)). So a
push to the skipped branch is absorbed by whichever fetch runs first: when that is a broadcast fetch
on a worker whose next sync then finds nothing moved, the push is never reported. A single worker
ignores its own broadcasts, so there only the rarer fetches outside the sync can absorb a push: the
one a repository makes when its location changed, or when a pinned commit is missing from the clone.
More than one worker can also each report the same
push, at most once per worker. Reporting it reliably needs a baseline that only the sync writes, such
as a worker-local ref updated after each comparison.

## Git error surfacing

`git merge` writes conflict output to **stdout**, not stderr. GitPython's `GitCommandError.stderr`
is therefore empty on a merge conflict, and the `RepositoryError` raised from the merge path
carries only its default message. Keep that in mind when asserting on error messages
(`pytest.raises(match=...)`) or when tempted to include `exc.stderr` in user-facing output for
merge failures.
