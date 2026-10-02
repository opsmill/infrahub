# Message Bus Contract: worker reads and convergence

**Feature**: IFC-3101

Two new request/reply pairs, one new broadcast and one changed adapter method. Message classes follow
`infrahub.message_bus.messages.git_file_get`; registration goes in
`infrahub.message_bus.messages::MESSAGE_MAP`, `RESPONSE_MAP`, `PRIORITY_MAP` and the handler in
`infrahub.message_bus.operations::COMMAND_MAP`. Both routing keys match the existing
`git.*.*` worker binding, so they land in the shared `{namespace}.rpcs` queue and one worker answers.

## `git.commit_log.get`

| Direction | Class | Fields |
| --- | --- | --- |
| request | `GitCommitLogGet` | `repository_id`, `repository_name`, `repository_kind`, `location`, `infrahub_branch_name`, `git_ref`, `imported_commit`, `limit`, `offset`, `include_pending_count` |
| reply | `GitCommitLogGetResponse` with `GitCommitLogGetResponseData` | see `data-model.md` |

Handler `infrahub.message_bus.operations.git.commit_log::get` unpacks the message, delegates to
`infrahub.git.state.log_reader`, and replies. It is intentionally shallow and holds no git call of its
own. The reader performs, in order:

1. Build the repository object for `repository_kind` without `init` and call
   `validate_local_directories()`. On `RepositoryInvalidFileSystemError`: reply
   `unavailable_reason = NOT_CLONED`, attempt `cache.set("git:warmup:<id>", not_exists=True, expires=60)`,
   and on success `submit_workflow(GIT_REPOSITORY_WARM_UP)`; put the task id in `warm_up_task_id`. If
   the submission raises, delete the key before re-raising, or every worker reports a warm-up in
   progress that never started. A read-write repository with nothing imported claims and submits
   nothing: the warm-up would not clone it, so the reply says its next sync creates the copy instead.
   Any other validation failure (`RepositoryError`) propagates, unless a
   warm-up claim is held: a copy still being cloned fails validation the same way a broken one does,
   so the read answers `NOT_CLONED` with the warm-up already in progress.
2. Otherwise resolve the head for `git_ref` on the main clone with no fetch: `origin/<ref>` for the
   read-write kind, `origin/<ref>` then `refs/tags/<ref>` for the read-only kind. A bare ref is only
   accepted as a commit hash (the resolved commit's hash starts with it), never as a name, which
   would match the local branch the clone checked out after the remote deleted it. No head means
   `REF_MISSING` for the read-only kind, whose ref is configured; otherwise `NO_REMOTE` when a commit is
   imported and `NOT_TRACKED` when none is.
3. Compute facts (`is_ancestor` of imported against head), classify, and under `BEHIND` walk
   `rev-list imported..head` once: its membership places every listed commit as pending or history, and
   its length is the pending count when requested. Page with `iter_commits(start, max_count=limit,
   skip=offset)`, where `start` is the head, or the imported commit under `REF_MISSING`. Read the
   `FETCH_HEAD` mtime. No total-count pass exists. A `GitCommandError` is logged on the worker and
   raised as a `RepositoryError` whose message carries no path or git output. The `Repo` is closed
   when the read ends.
4. Never take the repository lock: the read is against git's own consistent object store and must not
   queue behind an import. Never call `get_initialized_repo`, `get_commit_value`, `fetch` or `pull`.

## `git.branch_heads.get`

| Direction | Class | Fields |
| --- | --- | --- |
| request | `GitBranchHeadsGet` | `repository_id`, `repository_name`, `repository_kind`, `location`, `branches: [{branch_name, git_ref, tracked_commit}]` |
| reply | `GitBranchHeadsGetResponse` with `GitBranchHeadsGetResponseData` | see `data-model.md` |

Handler `infrahub.message_bus.operations.git.branch_heads::get` is shallow in the same way. Step 1
above is the same code, reached through the same reader rather than written a second time; the reader
then makes one pass over `get_branches_from_remote()` plus tag refs to resolve every row's head and
classifies each row, with no pending count. Exactly one message regardless of branch count (FR-004).

## Changed: `InfrahubMessageBus.rpc`

```python
async def rpc(self, message: InfrahubMessage, response_class: type[ResponseClass], timeout: float | None = None) -> ResponseClass
```

`timeout=None` means the adapter's own injected `BrokerSettings.rpc_timeout`, never a module-global
`config.SETTINGS` read, so a bus constructed with explicit settings honours them. Expiry raises
`infrahub.exceptions::WorkerTimeoutError(operation=<routing key>, timeout_seconds=...)`, catalogued
as `WORKER_TIMEOUT`. Implemented in `rabbitmq.py`, `nats.py` (both wrap the reply future) and
`local.py` (`BusSimulator.rpc` accepts and ignores it). Three existing callers inherit the default
bound, which is the intended shared-path change and lands in its own pull request:
`infrahub.api.file::get_file` and `ValidateRepositoryConnectivity` need nothing beyond the bound,
while `InfrahubRepositoryCreate` needs the timeout routed into the delete-and-raise path its
connectivity check already has for a failure verdict (T099), or a slow remote leaves an uncloned
repository behind a 504.

Whether a timeout reaches the client as an error is a resolver decision, not an adapter one:
`InfrahubRepositoryCommits` lets it propagate, `InfrahubRepositoryBranchDrift` catches it and reports
`UNAVAILABLE / TIMEOUT` on the column while still returning its graph-resolved rows.

## Reused unchanged: `refresh.git.fetch`

`RefreshGitFetch` broadcast to every worker (`broadcasted_event_bindings = ["refresh.git.*"]`),
handled by `infrahub.message_bus.operations.git.repository::fetch`, which clones if missing, fetches
and resets to the pinned `commit` with `update_commit_value=False`. Both the warm-up flow and the
read-only refs check send it with `commit` pinned to the imported commit, so convergence can never
move the pin (FR-016, FR-017). The warm-up reads that commit through the client only once it holds the
repository lock, and resets its own fresh copy to it as well, since a copy left at the remote head
leaves that worker's sync nothing to import: the sync compares local branches with the remote, not
with the graph. When a read-only branch has nothing imported it sends `refresh.git.clone` instead,
since an unpinned fetch pulls the wrong remote branch for a read-only repository. A read-write
repository with nothing imported is not warmed up at all; its sync creates and imports the copy.

## New: `refresh.git.clone`

| Direction | Class | Fields |
| --- | --- | --- |
| broadcast | `RefreshGitClone` | `repository_id`, `repository_name`, `repository_kind`, `infrahub_branch_name` |

Matches the existing `refresh.git.*` broadcast binding, so every worker receives it with no topology
change. Handler `infrahub.message_bus.operations.git.repository::clone` calls `get_initialized_repo`,
which clones a missing copy (checking out the configured `ref` for the read-only kind) and leaves an
existing one untouched. It exists because the warm-up runs on whichever worker the workflow engine
picks, which need not be the worker that reported `NOT_CLONED`, so the broadcast is what reaches that
worker when there is no commit to pin.
