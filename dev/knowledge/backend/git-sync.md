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
- The reverse mapping — from an Infrahub branch name to the remote git branch — is the pure
  function `get_mapped_remote_branch` in `backend/infrahub/git/branch_mapping.py`. Any git
  operation that names a remote ref (`pull`, `push`) must route the branch name through it: when
  the repository's default branch differs from Infrahub's, the remote has no branch named after
  the Infrahub default, and the raw name fails with "couldn't find remote ref".
  `InfrahubRepositoryBase._get_mapped_remote_branch` is the instance-method wrapper that supplies
  the repository's own `default_branch` and `registry.default_branch`; code that has no repository
  object — the API server, which must never build one — calls the function directly. The function
  takes all three inputs as required parameters, so no caller can fall back to Infrahub's default
  branch by omitting the repository's trunk.
- `git.import_sync_branch_names` (settings) is a list of names or regex patterns selecting which
  other remote branches are imported during sync; branches created in Infrahub with
  `sync_with_git` are imported regardless. **The list is empty by default, and an empty list
  filters nothing** — every remote branch is then imported, `sync_with_git` or not. So
  `sync_with_git` alone never answers "does Infrahub import this branch"; the predicate that does
  is `remote_branch_is_imported` in `backend/infrahub/git/branch_mapping.py`, and both trunks are
  always imported.

## Git error surfacing

`git merge` writes conflict output to **stdout**, not stderr. GitPython's `GitCommandError.stderr`
is therefore empty on a merge conflict, and the `RepositoryError` raised from the merge path
carries only its default message. Keep that in mind when asserting on error messages
(`pytest.raises(match=...)`) or when tempted to include `exc.stderr` in user-facing output for
merge failures.
