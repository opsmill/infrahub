# Git Sync

> Part of: `dev/knowledge/backend/` | Related: [Architecture](architecture.md)

How Infrahub maps and imports branches from external git repositories, how the sync flow reads the
per-branch state of each repository, and how git errors surface. Read this before reasoning about
which remote branches get imported, how many queries a sync run costs, or why a git failure carries
(or lacks) a message - the logic is split across several methods and is easy to mis-trace.

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

## Per-branch repository read

`get_repositories_commit_per_branch` in `backend/infrahub/git/utils.py` builds the per-repository,
per-branch view the sync flow and the Python computed-attribute trigger gather both read. It issues
two kinds of query:

- One `NodeManager.query` on the default branch reads the repository nodes. Every field on the node
  therefore holds the default branch's value, `commit` and `internal_status` included: the
  branch-agnostic `location` and `default_branch`, which no branch can hold its own value for, and
  the branch-aware `ref`, whose per-branch value is deliberately not read. The node is handed to
  callers as `RepositoryData.repository` and is never rewritten with a per-branch value, so
  `repository.commit.value` is the default branch's commit, not the commit of whichever branch the
  caller is working on.
- One `RepositoryBranchAttributesQuery` (`backend/infrahub/core/query/repository.py`) per chunk of
  `REPOSITORY_BRANCH_READ_CHUNK_SIZE` branch names resolves `commit` and `internal_status` for every
  repository on every branch in that chunk. Those two are the only attributes resolved per branch,
  and the per-branch values live only in `RepositoryData.branches` and `RepositoryData.branch_info`.

`REPOSITORY_BRANCH_READ_CHUNK_SIZE` is 100 and is defined in `backend/infrahub/git/constants.py`. It
is not a setting, so for N non-global branches the read costs `1 + ceil(N / 100)` queries rather than
one query per branch. When no repository exists the function returns after the node query, so the
cost is a single query.

The `RepositoryBranchAttributesReader` that runs those queries is constructed once at the top of
`get_repositories_commit_per_branch`, before the chunk loop, and reused for every chunk.

The global branch (`-global-`) is filtered out of the branch names before the chunk loop, so it is
never a key of `RepositoryData.branches` or `RepositoryData.branch_info`. Callers that index those
dictionaries by branch name must skip it themselves rather than expect an entry.

`RepositoryData.branches` is typed `dict[str, str | None]`: a branch whose `commit` does not resolve
is present with a value of `None`. A branch whose `internal_status` does not resolve is logged as a
warning and recorded as `inactive`, the conservative choice. A failing chunk raises rather than
being caught, so the read never returns a `RepositoryData` that silently omits branches.

## Git error surfacing

`git merge` writes conflict output to **stdout**, not stderr. GitPython's `GitCommandError.stderr`
is therefore empty on a merge conflict, and the `RepositoryError` raised from the merge path
carries only its default message. Keep that in mind when asserting on error messages
(`pytest.raises(match=...)`) or when tempted to include `exc.stderr` in user-facing output for
merge failures.
