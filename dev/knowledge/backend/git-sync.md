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
- `git.import_sync_branch_names` (settings) is a list of names or regex patterns selecting which
  other remote branches are imported during sync; branches created in Infrahub with
  `sync_with_git` are imported regardless.

## Git error surfacing

`git merge` writes conflict output to **stdout**, not stderr. GitPython's `GitCommandError.stderr`
is therefore empty on a merge conflict, and the `RepositoryError` raised from the merge path
carries only its default message. Keep that in mind when asserting on error messages
(`pytest.raises(match=...)`) or when tempted to include `exc.stderr` in user-facing output for
merge failures.
