# Git Sync

> Part of: `dev/knowledge/backend/` | Related: [Architecture](architecture.md)

How Infrahub maps and imports branches from external git repositories, and how git and import errors surface.
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

## Rewritten history

`InfrahubRepository.collect_pending_imports` compares each branch twice. Keep the two comparisons
apart, because they drive different outcomes:

- **The commit the graph records against the remote head** says what happened to the branch:
  unchanged, fast-forward, rewrite, re-target or gone from the remote (`git/divergence/`). The commits
  are read once per cycle by `get_repositories_commit_per_branch` and passed down through the sync
  flows.
- **This worker's worktree head against the remote head** says whether the clone moves. The sync
  moves a worktree by a hard reset onto the remote head it classified, so a worktree behind the
  remote fast-forwards and the commit imported is the one classified. A worktree that does not lead
  to the remote head, because the remote was rewritten or rewound, loses the commits it held, and
  that includes a worktree ahead of the remote. Such a commit is rare: `InfrahubRepository.merge`
  pushes before it records the commit, and resets the destination worktree when either step fails.
  Only a failed reset, which `merge` logs as needing manual reconciliation, leaves an unpushed merge
  commit there, and the sync reset then discards it
  ([Git Integration](git-integration.md#the-writeback-direction-has-no-reconciliation)). A worktree
  already on the remote head stays there. When the graph records another commit, the sync resets the
  worktree onto the same commit, which records it, and imports the branch again: a pull would move
  nothing, so it would record nothing.

A worker whose graph already holds the remote head can still hold the discarded history on disk. It
resets and logs the reconciliation, and its classification stays unchanged.

The sync considers the branches whose local head differs from the remote, and also the local
branches whose graph commit differs from the remote head. Only branches that can still record a
commit take part in the second comparison. A branch that needs a rebase, is being merged, failed a
merge, is merged or is being deleted rejects the commit, and so does a branch Infrahub no longer
lists, so it would be selected again on every cycle. `git/branch_status.py::accepts_commit_write`
holds that rule for both comparisons. A commit write the graph still refuses, because the status
changed after the listing, fails that branch alone. It classifies a branch new to this
worker too, because the graph can hold a commit that another worker imported and the remote has
since discarded. A new branch that git cannot classify is still created, but a branch this worker
holds fails before its worktree moves. Each reset or lineage break logs one line with the branch,
the discarded commit and the commit that replaced it. The add flow passes no graph commits, so it
classifies nothing.

## Cloning and the repository lock

Creating the local copy deletes whatever is already at the repository directory before cloning
into it. The creation primitive does not take the repository lock itself, so every caller that
reaches it holds that lock; `initialize_local()`, which clones only when it finds no usable copy,
also re-checks once the lock is held and clones only if the copy is still absent or unusable. Two flows
on the same worker can otherwise ask for the same repository at the same time — a periodic sync
and a refresh request, say — and the second clone wipes the directory the first one just built,
invalidating the git objects already opened against it and leaving the sync unable to resolve a
commit.

The re-check treats a copy that fails validation like an absent one. The copy was absent before
the lock was taken, so a copy that is present but broken once the lock is held was left by a
concurrent clone that failed part-way (the clone succeeded but the checkout did not, say), and
cloning over it is the only way back to a usable copy. A `Repo` already opened on that broken copy
is closed first: once the directory is replaced it would keep reading the deleted object store.
The check before the lock still raises on a broken copy rather than replacing it.

The lock is reentrant per context, so a caller that already holds it for a wider critical section
pays nothing extra.

## Import failures

A branch import is built by `build_import_plan` and applied by `apply_import_plan`. Each runs inside
the same boundary, `_import_failure_boundary` on the integrator; the apply step does not run when the
build step fails, so a failure is handled once. Every import goes through these two
methods: the add and sync flows, the scheduled sync of a new clone, the import-objects flow, and the
read-only flows through `import_objects_from_files`.

- **What the boundary does.** On any failure it sets the branch to `ERROR_IMPORT`, logs the failure
  once to the flow run's log, and raises `RepositoryImportError`
  (`backend/infrahub/git/import_errors.py`). `RepositoryConnectionError` and
  `RepositoryCredentialsError` also set the branch being imported to `ERROR_IMPORT`, but they are not
  logged or converted: they pass through unchanged and still stop the repository's sync.
  A failed `ERROR_IMPORT` write is logged and does not replace the import failure. The boundary
  ends after the last import step: setting the branch to `IN_SYNC` and sending `CommitUpdatedEvent`
  run outside it, so their failure cannot mark a fully imported branch as `ERROR_IMPORT`.
- **Expected and unrecognised failures.** `describe_import_error` is the single function that maps an
  exception to a readable message. A failure it recognises is logged at error level without a
  traceback. A failure it does not recognise is logged once with its traceback, which is the signal
  that the function needs a new entry. Both become `RepositoryImportError`. To make a new error
  type expected, add a `case` to that function and nothing else. The SDK `Error` base class is
  deliberately not mapped, because it also covers connection errors.
- **One log entry per failure.** The error entry carries `repository`, `branch`, `step` (`import`)
  and `reason` as log record fields for log shippers and alert rules. `raise_if_branches_failed`
  logs its warning with the same fields only for branches that failed before the import (step
  `collection`), so each failure appears once in the task log.
- **Naming the `.infrahub.yml` entry.** The mapping function only receives the exception, so the
  loops over `.infrahub.yml` entries, in the build and in the apply step, wrap their body in
  `import_entry(label)`. That context manager adds the entry's name and file as an exception note,
  and the message is prefixed with the notes, for example
  `GraphQL query 'backbone_service' (queries/backbone.gql): Violates uniqueness constraint 'name'`.
  Schema files have no label, because their validation errors already name the file. The build
  loops that import Python modules (checks, Python transforms, generators) also pass the worktree
  directory to `import_entry`, so a syntax error names its file relative to the repository root.
  The file can be a helper module, not the entry's own file.
  Do not log inside an import step and then re-raise: the boundary logs, and a second entry
  duplicates the failure.
- **No Prefect traceback.** The import steps are plain methods, not `@task`s. An exception leaving a
  task is logged by Prefect with its traceback before the boundary can convert it. When
  `RepositoryImportError` or `RepositoryBranchesFailedError` leaves a flow, Prefect also writes a
  record with the traceback. Both types are registered with `@suppress_traceback_in_logs`, so the
  filter on the Prefect run loggers drops that record (see [Webhooks](webhooks.md) for the
  mechanism). The filter matches the exact type, so each class is registered on its own. Prefect's
  `Finished in state Failed(...)` entry has no traceback and stays.
- **A failure stays on its branch.** Containment does not rely on the boundary converting every
  failure. `import_branch` (`backend/infrahub/git/sync.py`) builds and applies one branch under the
  repository lock and returns any failure instead of raising it, including one raised outside the
  boundary such as a lock error, which it logs once with its traceback. Only
  `RepositoryConnectionError` and `RepositoryCredentialsError` are re-raised, so only the branch
  being imported is set to `ERROR_IMPORT`: recording them on every remaining branch would leave
  those statuses in place until a new commit or a manual re-import. `RepositorySyncer.sync` records
  a failed branch and continues with the next one. `RepositoryAdder.add` returns a failed
  default-branch import. For an active repository, `add_git_repository` still syncs the other
  branches and sends `RefreshGitFetch` before it fails with that error; for a repository that is
  not active, it syncs no other branch and fails with that error at once.
  `bootstrap_local_repository` returns the repository when the default-branch import fails, so the
  scheduled sync continues with its other branches; it returns `None` when the clone fails or when
  that import raises a connection or credential error.
- **Calling an import step directly.** The steps write to the run logger, which Prefect provides only
  inside a flow or task run. A test that calls one directly wraps the call in a flow
  (`tests/helpers/flow.py::call_in_flow`).

## Git error surfacing

`git merge` writes conflict output to **stdout**, not stderr. GitPython's `GitCommandError.stderr`
is therefore empty on a merge conflict, and the `RepositoryError` raised from the merge path
carries only its default message. Keep that in mind when asserting on error messages
(`pytest.raises(match=...)`) or when tempted to include `exc.stderr` in user-facing output for
merge failures.
