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
  reads it, so status writes land on the branch the operation ran on.
- **The read-only kind has no default branch at all.** It tracks a single `ref`, and the three
  branch-mapping hooks below are the identity on it.

Three abstract hooks on `InfrahubRepositoryBase` keep the base class from needing a default branch of
its own: `_get_mapped_remote_branch`, `_get_mapped_target_branch` and `_resolve_worktree_identifier`.
The read-write kind implements the mapping described below; the read-only kind returns its input.

> **Merge-order note.** `dev/knowledge/backend/git-integration.md` exists on `develop` and documents
> the previous shape — an optional default-branch field with a silent fallback, and a table of which
> construction paths resolve it. Both are gone. Reconcile the two pages when these branches meet.

## Branch import and mapping

- A repository's own `default_branch` is mapped onto Infrahub's default branch by
  `_get_mapped_target_branch` on `InfrahubRepository`: when a commit lands on the
  repository's default branch, it is recorded against Infrahub's default branch, whatever either
  is named.
- Because of that mapping, when the repository's default branch differs from Infrahub's, a remote
  branch literally named like Infrahub's default branch cannot be imported — it would collide with
  the mapped default. The skip happens in `validate_remote_branch` (which logs
  "Ignoring import of mismatched default branch" and returns `False`), *not* in
  `_get_mapped_target_branch`. Both of those live on `InfrahubRepository` rather than the shared
  base, because only a read-write repository has a default branch to collide with.
- The reverse mapping — from an Infrahub branch name to the remote git branch — is
  `_get_mapped_remote_branch`. Any git operation that names a remote ref (`pull`, `push`) must
  route the branch name through it: when the repository's default branch differs from Infrahub's,
  the remote has no branch named after the Infrahub default, and the raw name fails with
  "couldn't find remote ref".
- `git.import_sync_branch_names` (settings) is a list of names or regex patterns selecting which
  other remote branches are imported during sync; branches created in Infrahub with
  `sync_with_git` are imported regardless.

## Git error surfacing

`git merge` writes conflict output to **stdout**, not stderr. GitPython's `GitCommandError.stderr`
is therefore empty on a merge conflict, and the `RepositoryError` raised from the merge path
carries only its default message. Keep that in mind when asserting on error messages
(`pytest.raises(match=...)`) or when tempted to include `exc.stderr` in user-facing output for
merge failures.
