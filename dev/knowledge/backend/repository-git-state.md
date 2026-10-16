# Repository git-state read

> Part of: `dev/knowledge/backend/` | Related: [Git Sync](git-sync.md), [Git Integration](git-integration.md), [Message Bus](message-bus.md)

How the API server answers a repository's commit log (`InfrahubRepositoryCommits`) and its per-branch
drift (`InfrahubRepositoryBranchDrift`) when it holds no clone and must never build a repository
object. Read this before changing either resolver, the reader in `backend/infrahub/git/state/`, the
read-only refs check in `backend/infrahub/git/refs_check/`, or any of the cache keys listed below.
The frontend side is in [Repository Commits tab](../frontend/repository-commits.md).

## The path of one read

1. The resolver in `backend/infrahub/graphql/queries/repository_git_state.py` loads the repository,
   checks view permission and resolves the git ref the request branch reads. For a read-write
   repository it maps the branch name through `get_mapped_remote_branch` and
   `remote_branch_is_imported` in `backend/infrahub/git/branch_mapping.py` (see
   [Git Sync](git-sync.md#branch-import-and-mapping)). For a read-only repository it uses `ref`.
2. It builds a reader with `build_repository_git_state_reader` and calls `commits` or
   `branch_heads`.
3. `BusRepositoryGitStateReader` sends an RPC on the message bus (`git.commit_log.get` or
   `git.branch_heads.get`). `commit_log_wire.py` and `branch_heads_wire.py` convert between the
   domain values in `models.py` and the message classes, in both directions.
4. Whichever worker takes the message runs the handler in
   `backend/infrahub/message_bus/operations/git/commit_log.py` or `branch_heads.py`, which builds a
   `RepositoryLogReader` (`git/state/log_reader.py`) and reads that worker's own clone.
5. The worker classifies what it measured with the pure functions in `git/state/classification.py`
   and replies. The API server only maps the result onto the GraphQL types.

The resolver sends no worker request when the answer does not need one:

- When the ref resolves to none, the answer is `condition: NOT_TRACKED` with no edges.
- When the query selects none of the git-derived fields (`COMMIT_GIT_FIELDS`, `DRIFT_GIT_FIELDS` and
  `DRIFT_ROW_GIT_FIELDS` in the resolver module), the answer carries only the graph values and
  `checked_at`, which comes from the cache.

Storage is per worker (see [Git Integration](git-integration.md#storage-is-per-worker-not-shared)),
so two requests for the same repository can be answered from two different clones, with two
different fetch times.

## The reader protocol and its implementations

`RepositoryGitStateReader` in `git/state/reader.py` is a `Protocol` with two methods, `commits` and
`branch_heads`. No implementation clones, fetches or takes a repository lock. The implementations
are:

- `BusRepositoryGitStateReader` (`git/state/bus_reader.py`): the production implementation. It
  waits for the reply for `broker.rpc_timeout` seconds, and raises `WorkerTimeoutError` when no worker
  answers and `RPCError` when the worker failed or replied with something unusable.
- `UnavailableRepositoryGitStateReader` (`git/state/reader.py`): answers `UNAVAILABLE` with the reason
  `NOT_IMPLEMENTED`. The factory never returns it; only tests inject it, to drive the unavailable
  state.
- `RecordingRepositoryGitStateReader` (`backend/tests/helpers/repository_git_state.py`): records
  every request in order and replays queued results, so a test can assert that no request was made
  or exactly which request was made.
- `FailingRepositoryGitStateReader` (same module): raises a given exception on every call, to test
  what a resolver does when the read fails, such as a worker timeout.

`RepositoryLogReader` on the worker has the same two methods with the same signatures, but it is not
one of the implementations above: it runs behind the bus, inside the handler, and the factory never
returns it.

## The factory is the only wiring point

`build_repository_git_state_reader` in `git/state/factory.py` is the only place that picks an
implementation or reads a setting. Call it; never construct a reader in a resolver.

- It returns `config.OVERRIDE.repository_git_state_reader` when that is set. Tests set it through a
  save-and-restore fixture to inject a double, with no patching.
- Otherwise it returns `BusRepositoryGitStateReader` with the message bus of the active service and
  `config.SETTINGS.broker.rpc_timeout`.

## Why the read never clones, fetches or locks

An import holds the repository lock for as long as it runs. A read that took the lock would queue
behind it, and a commit log request would wait for the length of an import. The read uses git's own
object store instead, which is consistent for concurrent reads.

- `RepositoryLogReader` opens the `main` clone through `_LocalCopy`, a repository subclass whose
  branch-mapping, checkout and commit-value methods raise `NotImplementedError`. The read can only
  validate the directory layout and open the clone.
- The blocking git calls run in a thread (`asyncio.to_thread`), and the clone is closed after each
  read. A `GitCommandError` becomes a `RepositoryError` whose message carries no path and no git
  output.
- The remote head is read from `origin/<ref>` only, never from a bare name, because a bare name also
  matches the local branch and would keep reporting a branch the remote has deleted. A read-only
  repository also accepts `refs/tags/<ref>` and a commit hash.

### A worker with no clone starts a warm-up

When the answering worker has no valid clone, the read answers `UNAVAILABLE` with the reason
`NOT_CLONED` and starts at most one warm-up across all workers while the warm-up claim lasts:

- It claims the warm-up key (see below) with a set-if-absent write. The worker whose write succeeds
  submits the `git-repository-warm-up` flow and returns its run id as `warm_up_task_id`. A worker
  whose write fails answers that a warm-up is already in progress.
- If submitting the flow fails, the claim is deleted, so that no worker keeps reporting a warm-up
  that never started.
- A clone that exists but fails validation while a warm-up claim is held is treated as a clone in
  progress, not as a broken one.
- A read-write repository with nothing imported on the requested branch starts no warm-up. Its next
  sync creates the clone together with its first import, and the message says so.

The warm-up itself (`RepositoryWarmUp.warm_up` in `git/state/warm_up.py`) is the only step on this
path that clones, and it runs as a flow, outside the read. It clones on its own worker, broadcasts
`RefreshGitClone` so every other worker clones too, and then fetches a copy that has no fetch time
yet, so that later reads report one. No local branch is moved.

## The two freshness values

The commit log and the drift answer carry two different times. They answer different questions and
come from different places.

- `fetched_at`: when the answering worker's clone last fetched from its remote. `read_fetched_at` in
  `git/state/log_reader.py` returns the modification time of `FETCH_HEAD` in that clone. A missing or
  unreadable file means the time is not known. An empty `FETCH_HEAD` also means not known, because a
  failed fetch still writes the file but leaves it empty. The value belongs to one worker's clone, so
  it can differ between two requests.
- `checked_at`: when the last read-only refs check that took the claim ended, whether it succeeded or
  failed, including a check refused for an invalid ref that listed nothing. `_resolve_checked_at` in
  the resolver module reads it from the cache on the API server, with no worker request. It is set
  for read-only repositories only. A read-write repository returns null, because its sync fetches
  the remote, so its `fetched_at` already answers the question.

`ReadOnlyRepositoryRefsChecker._record_check_time` writes the check time in a `finally` block, after
every check that took the claim, whether the check succeeded or failed, and after the claim is
released. A check skipped because another run holds the claim writes nothing.

`checked_at` is best effort when written and when read, because the cache is not durable storage:

- A failed write is logged and does not change the outcome of the check.
- On read, an unreachable cache, a flushed cache, an expired key and a value that does not parse all
  return null rather than failing the query.

## Cache keys

Every key is built by a function in `git/state/cache_keys.py`, because the API server and the
workers read and write them from different processes. Every key starts with `git:`.

| Function | Key | Written by | Expires | When the value is lost |
| --- | --- | --- | --- | --- |
| `warm_up_key` | `git:warmup:<repository id>` | `RepositoryLogReader`, set-if-absent, value is the worker identity | `WARM_UP_TTL` (one minute) | The next read can start another warm-up |
| `refs_check_due_key` | `git:refs_check:due:<repository id>` | `RefsCheckScheduler.select_due`, set-if-absent; `retry_soon` shortens it after a failed check | The configured check interval, or the retry delay after a failure | The repository is checked on the next cycle |
| `refs_check_running_key` | `git:refs_check:running:<repository id>` | `ReadOnlyRepositoryRefsChecker.check`, set-if-absent, value is the run id; renewed before convergence | `REFS_CHECK_CLAIM_TTL_SECONDS` | A second check of the same repository can run at the same time |
| `refs_check_last_key` | `git:refs_check:last:<repository id>` | `ReadOnlyRepositoryRefsChecker._record_check_time` | 30 days | `checked_at` reads as null until the next check |
| `refs_check_listed_key` | `git:refs_check:listed:<repository id>:<ref>` | `ReadOnlyRepositoryRefsChecker._record_listed`, once every broadcast has been sent | 30 days | The next check broadcasts that ref once more |

The interval is `git.read_only_refs_check_interval_mins`. The retry delay is
`REFS_CHECK_RETRY_SECONDS` in `git/refs_check/constants.py`, shortened to the interval when the
interval is shorter. `retry_soon` writes nothing for a repository that has no due key, so a failed
check that a user started by hand does not delay the scheduled checks.

The last listed head per ref is shared by all workers and written only by the check. The check
compares each remote head with it to decide whether the other workers have to be told about the ref,
so the decision does not depend on which worker ran the check. Whether the running worker itself has
to fetch is decided separately, against its own clone.

## Failures by query

- Commit log: a worker timeout fails the field with the `WORKER_TIMEOUT` GraphQL error, which carries
  `retry_after_seconds`. The commit log has nothing to show without a worker answer, so a timeout is
  an error and not an `unavailable` state.
- Drift: the rows come from the graph, so a worker timeout keeps every row with a null remote head and
  sets `unavailable.reason` to `TIMEOUT`. A row with a tracked ref gets the condition `UNAVAILABLE`,
  and a row without one keeps `NOT_TRACKED`.
- In both queries, a `NOT_CLONED` answer is an `unavailable` state with the worker's message, and an
  `RPCError` fails the field.
