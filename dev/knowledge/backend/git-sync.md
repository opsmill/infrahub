# Git Sync

> Part of: `dev/knowledge/backend/` | Related: [Architecture](architecture.md)

How Infrahub maps and imports branches from external git repositories, and how git errors surface.
Read this before reasoning about which remote branches get imported or why a git failure carries
(or lacks) a message — the logic is split across several methods and is easy to mis-trace.

## Branch import and mapping

- A repository's own `default_branch` is mapped onto Infrahub's default branch by
  `_get_mapped_target_branch` in `backend/infrahub/git/base.py`: when a commit lands on the
  repository's default branch, it is recorded against Infrahub's default branch, whatever either
  is named.
- Because of that mapping, when the repository's default branch differs from Infrahub's, a remote
  branch literally named like Infrahub's default branch cannot be imported — it would collide with
  the mapped default. The skip happens in `validate_remote_branch` (which logs
  "Ignoring import of mismatched default branch" and returns `False`), *not* in
  `_get_mapped_target_branch`.
- The reverse mapping — from an Infrahub branch name to the remote git branch — is
  `_get_mapped_remote_branch`. Any git operation that names a remote ref (`pull`, `push`) must
  route the branch name through it: when the repository's default branch differs from Infrahub's,
  the remote has no branch named after the Infrahub default, and the raw name fails with
  "couldn't find remote ref".
- `git.import_sync_branch_names` (settings) is a list of names or regex patterns selecting which
  other remote branches are imported during sync; branches created in Infrahub with
  `sync_with_git` are imported regardless.

## Cloning and the repository lock

Creating the local copy deletes whatever is already at the repository directory before cloning
into it. The creation primitive does not take the repository lock itself, so every caller that
reaches it holds that lock; `init()`, which clones only when it finds no usable copy, also
re-checks once the lock is held and clones only if the copy is still absent or unusable. Two flows
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

## Git error surfacing

`git merge` writes conflict output to **stdout**, not stderr. GitPython's `GitCommandError.stderr`
is therefore empty on a merge conflict, and the `RepositoryError` raised from the merge path
carries only its default message. Keep that in mind when asserting on error messages
(`pytest.raises(match=...)`) or when tempted to include `exc.stderr` in user-facing output for
merge failures.
