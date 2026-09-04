# Message Bus Contract: worker reads and convergence

**Feature**: IFC-3101

Two new request/reply pairs and one changed adapter method. Message classes follow
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
   and on success `submit_workflow(GIT_REPOSITORY_WARM_UP)`; put the task id in `warm_up_task_id`.
2. Otherwise resolve the head for `git_ref` on the main clone with no fetch; `None` means `NO_REMOTE`.
3. Compute facts (`is_ancestor`, `rev-list --count` for the pending count when requested), classify,
   page with `iter_commits(head, max_count=limit, skip=offset)`, classify each commit, read
   `FETCH_HEAD` mtime. No total-count pass exists.
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

`timeout=None` means `config.SETTINGS.broker.rpc_timeout`. Expiry raises
`infrahub.exceptions::WorkerTimeoutError(operation=<routing key>, timeout_seconds=...)`, catalogued
as `WORKER_TIMEOUT`. Implemented in `rabbitmq.py`, `nats.py` (both wrap the reply future) and
`local.py` (`BusSimulator.rpc` accepts and ignores it). Existing callers (`infrahub.api.file::get_file`,
`ValidateRepositoryConnectivity`) inherit the default bound; that is the intended shared-path change
and lands in its own pull request.

## Reused unchanged: `refresh.git.fetch`

`RefreshGitFetch` broadcast to every worker (`broadcasted_event_bindings = ["refresh.git.*"]`),
handled by `infrahub.message_bus.operations.git.repository::fetch`, which clones if missing, fetches
and resets to the pinned `commit` with `update_commit_value=False`. Both the warm-up flow and the
read-only refs check send it with `commit` pinned to the imported commit, so convergence can never
move the pin (FR-016, FR-017).
