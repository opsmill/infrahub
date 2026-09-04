# Data Model: Git Repository Commit Visibility

**Feature**: IFC-3101 | **Branch**: `pog-repo-commit-visibility-ifc-3101`

No graph schema change. No new node kind, attribute, relationship or migration. Everything below is
an in-memory value object, a wire message, a cache key, an enum or a configuration setting.

## Existing graph data this feature reads (never writes)

| Kind | Attribute | Branch support | Role |
| --- | --- | --- | --- |
| `CoreGenericRepository` | `commit` (Text, optional) | LOCAL on `CoreRepository`, AWARE on `CoreReadOnlyRepository` | The imported commit for the request branch |
| `CoreRepository` | `default_branch` (Text) | AGNOSTIC | Remote branch the Infrahub default branch maps to; other Infrahub branches map to the same-named remote branch via `InfrahubRepositoryBase._get_mapped_remote_branch` |
| `CoreReadOnlyRepository` | `ref` (Text) | AWARE | Branch or tag whose history the log describes; may differ per Infrahub branch |
| `Branch` (registry) | `sync_with_git` | n/a | Selects the drift list's row set for the read-write kind; a branch with `sync_with_git = false` is excluded rather than shown as drifted |

Source of the per-branch values: `RepositoryBranchValuesQuery` (below). The existing
`infrahub.git.utils::get_repositories_commit_per_branch` is not the drift resolver's source and is
not modified by this feature. It is still used, unchanged, for one purpose: the read-only refs-check
cycle calls it to enumerate the repositories to check.

### Per-branch resolution this feature must reproduce

For each branch in the row set, the value is the first of: the branch's own active edge; the origin
branch's edge active at `branched_from` (branches are isolated by default); the global-branch edge.
Resolved by `ORDER BY branch_level DESC, from DESC, status ASC LIMIT 1` plus an active-status check.

Consequence to preserve, not to fix: `commit` is `LOCAL` on a branch-`AGNOSTIC` node, so its creation
edge lands on the global branch and a branch that never imported inherits its origin branch's
fork-point value rather than null. A rebase advances `branched_from`, so an untouched branch's
inherited value follows its origin branch forward with no git activity on that branch. The origin
branch is usually the default branch but is not necessarily it, which is why `source_branch` names it
per row rather than being assumed.

### Row set

| Repository kind | Branches included |
| --- | --- |
| `CoreRepository` | branches with `sync_with_git` true |
| `CoreReadOnlyRepository` | every branch |

`MERGED` and `DELETING` branches and the global branch are excluded from both. Matches the sibling
card's row set so the drift column lines up with its rows.

## Enums (`infrahub.core.constants`, `InfrahubStringEnum`; exposed with `graphene.Enum.from_enum`)

### `RepositoryGitCondition`

| Member | Value | Meaning |
| --- | --- | --- |
| `IN_SYNC` | `in_sync` | remote head equals the imported commit |
| `BEHIND` | `behind` | imported commit is an ancestor of the head; `pending_count` is set |
| `REWRITTEN` | `rewritten` | imported commit is not an ancestor of the head (rebase, force-push, moved tag); no pending count |
| `ORPHANED` | `orphaned` | the imported commit's object is not present at all, so it cannot be placed in any history. A stronger form of `REWRITTEN`: there, the commit exists and has been left behind; here, the clone cannot resolve the hash. Decided before any ancestry call, because `Repo.is_ancestor` on an unresolvable hash raises rather than returning `False`. No pending count, and the imported marker has nowhere to sit |
| `NO_REMOTE` | `no_remote` | the branch or ref has no counterpart on the remote |
| `NOT_TRACKED` | `not_tracked` | nothing imported on this Infrahub branch, and nothing inherited from its origin. Read-write branches not synchronised with Git are excluded from the row set instead of carrying this condition |
| `UNAVAILABLE` | `unavailable` | no git-derived answer; see `RepositoryGitUnavailable` |

### `RepositoryCommitState`

| Member | Value | Meaning |
| --- | --- | --- |
| `HEAD` | `head` | the remote head, when it differs from the imported commit |
| `IMPORTED` | `imported` | the commit Infrahub has imported |
| `PENDING` | `pending` | ancestor of the head, not an ancestor of the imported commit; only under `BEHIND` |
| `HISTORY` | `history` | ancestor of the imported commit; already imported content |
| `UNRELATED` | `unrelated` | cannot be related to the imported commit (`REWRITTEN`, `ORPHANED`, `NOT_TRACKED`) |

No `RepositoryCommitState` member is needed for the orphaned case: an unresolvable commit cannot
appear in the log at all, so there is no row to label. The condition carries the answer, and
`imported_commit` still reports the hash the graph holds so a user can see which commit went missing.

Precedence when one commit qualifies for several states: `IMPORTED` over `HEAD` (when head equals
imported, `condition` is `IN_SYNC` and the top-level `remote_head` and `imported_commit` carry the
same hash so both markers can be drawn), then `HEAD`, then `PENDING` / `HISTORY` / `UNRELATED`.

### `RepositoryGitUnavailableReason`

| Member | Value | Meaning |
| --- | --- | --- |
| `NOT_CLONED` | `not_cloned` | the answering worker has no local copy; a warm-up was triggered |
| `NOT_IMPLEMENTED` | `not_implemented` | Phase A placeholder while the worker read path is not wired; removed in Phase B |

## Value objects (frozen dataclasses)

### `infrahub.core.query.repository` (new module, one database query)

```text
RepositoryBranchValuesQuery(Query)
  params in: repository_id: str
             branch_scopes: list[BranchScope]     one per branch in the row set
             attribute_names: set[str]            {"commit"} or {"commit", "ref"}

BranchScope                    the per-branch scope unwound in Cypher
  branch_name: str             the row identity
  branch_names: list[str]      global + origin + self, as the edge filter accepts
  time_base: str               origin branch read time (branched_from when isolated)
  time_tip: str                query time

RepositoryBranchValue          one returned row, from get_data()
  branch_name: str
  attribute_name: str
  value: str | None
  source_branch: str           branch whose edge supplied the value; differs from
                               branch_name when the value is inherited
```

`source_branch` is not exposed through GraphQL in this slice. It is what makes the inheritance
assertions readable in tests, and it is how support tells "this branch imported this commit" from
"this branch inherited it".

### `infrahub.git.state` (new subpackage: `models.py` for the dataclasses, `classification.py` for the pure functions, no I/O in either)

```text
CommitEntry
  hash: str            full SHA
  short_hash: str      first 7 characters
  summary: str         first line of the message
  message: str         full message
  author_name: str
  authored_at: datetime (tz-aware)
  committed_at: datetime (tz-aware)
  state: RepositoryCommitState

GitStateFacts                  what the worker measured on the clone
  head: str | None
  imported: str | None
  imported_resolvable: bool | None   whether the imported hash names an object the clone holds.
                                     Measured BEFORE any ancestry call, because is_ancestor on an
                                     unresolvable hash raises rather than returning False
  imported_is_ancestor_of_head: bool | None
  pending_count: int | None
  tracked: bool                False when nothing is imported or inherited on this branch

classify(facts: GitStateFacts) -> RepositoryGitCondition
classify_commit(hash, is_ancestor_of_imported: bool | None, facts, condition) -> RepositoryCommitState
```

### `infrahub.message_bus.messages.git_commit_log_get`

```text
GitCommitLogGet(InfrahubMessage)              routing key git.commit_log.get, priority 4
  repository_id: str
  repository_name: str
  repository_kind: str                        CoreRepository | CoreReadOnlyRepository
  location: str
  infrahub_branch_name: str
  git_ref: str                                remote branch name or read-only ref
  imported_commit: str | None
  limit: int                                  1..100
  offset: int                                 >= 0
  include_pending_count: bool

GitCommitLogGetResponseData
  condition: RepositoryGitCondition
  remote_head: str | None
  imported_commit: str | None
  pending_count: int | None
  fetched_at: datetime | None
  unavailable_reason: RepositoryGitUnavailableReason | None
  warm_up_task_id: str | None
  commits: list[CommitEntry]
  error_message: str | None
  http_code: int | None                       same convention as GitFileGetResponseData

GitCommitLogGetResponse(InfrahubResponse)     routing key git.commit_log.get
```

### `infrahub.message_bus.messages.git_branch_heads_get`

```text
GitBranchHeadsGet(InfrahubMessage)            routing key git.branch_heads.get, priority 4
  repository_id, repository_name, repository_kind, location
  branches: list[BranchRefInput]
    BranchRefInput: branch_name: str, git_ref: str, tracked_commit: str | None

`sync_with_git` is deliberately absent: the row set already excludes read-write branches that are not
synchronised with Git (above), so the flag would reach the worker with nothing to decide.

GitBranchHeadsGetResponseData
  fetched_at: datetime | None
  unavailable_reason: RepositoryGitUnavailableReason | None
  warm_up_task_id: str | None
  branches: list[BranchDriftRow]
    BranchDriftRow: branch_name, git_ref, tracked_commit, remote_head: str | None, condition
  error_message, http_code

GitBranchHeadsGetResponse(InfrahubResponse)   routing key git.branch_heads.get
```

### `infrahub.git.models` additions (Pydantic, workflow parameters)

```text
GitRepositoryWarmUp
  repository_id, repository_name, repository_kind, location, infrahub_branch_name, imported_commit

GitReadOnlyRepositoryCheckRefs
  repository_id, repository_name, location
  refs: list[TrackedRef]   TrackedRef: infrahub_branch_name, infrahub_branch_id, ref, commit
```

## Reader seam (`infrahub.git.state`, not the resolver module)

The protocol lives in the git domain beside its production implementation, after
`git/fingerprint/blob_resolver.py` and `task_manager/flow_run/`. The resolver reaches it through a
factory and `InfrahubServices` is not touched. It returns the frozen dataclasses above, never a
message-bus `*ResponseData` model: registering a message pair before its handler breaks
`test_message_command_overlap`, so the wire models do not exist yet in the phase the protocol ships.

```text
RepositoryGitStateReader (Protocol)              git/state/reader.py
  async commits(request: CommitLogRequest) -> CommitLogResult
  async branch_heads(request: BranchHeadsRequest) -> BranchDriftResult

UnavailableRepositoryGitStateReader              git/state/reader.py
                                 Answers UNAVAILABLE / NOT_IMPLEMENTED. The placeholder until the
                                 worker read lands. No sample-data implementation.
BusRepositoryGitStateReader                      git/state/bus_reader.py
                                 Wraps message_bus.rpc(..., timeout=...) and maps the reply onto the
                                 dataclasses. The only module in the read path knowing a routing key.
Recording / Failing doubles                      backend/tests/helpers/repository_git_state.py

build_repository_git_state_reader(...)           git/state/factory.py
                                 The only place an implementation is chosen or a setting is read.
```

## Cache keys (`service.cache`, `set(..., not_exists=True)`)

Every key is built by `infrahub.git.state.cache_keys`, which owns the prefix and the four formats. The
API resolver and the worker flows write and read these keys from different processes, so nothing else
makes them agree on the string. Prefix constant plus builder functions, after
`infrahub.webhook.constants::CACHE_KEY_PREFIX` and `task_manager/flow_run/cache_key.py`. TTLs come
from `infrahub.message_bus.types::KVTTL` where a member fits and from a computed value where none
does (noted per row).

| Key | Value | TTL | Purpose |
| --- | --- | --- | --- |
| `git:warmup:<repository_id>` | worker identity | `KVTTL.ONE_MINUTE` | collapse concurrent warm-up triggers (FR-013) |
| `git:refs_check:due:<repository_id>` | ISO timestamp | `read_only_refs_check_interval_mins * 60` | due check for the cron refs check (FR-015). Deleted on failure so the next tick retries; left to expire on success (FR-026) |
| `git:refs_check:running:<repository_id>` | flow-run id of the running check | per-run ceiling: the per-repository timeout plus a margin, from one constant | one check per repository in flight, across the scheduled and on-demand paths; deleted in a `finally` (FR-025). The value is the flow-run id because the mutation has to report the in-flight run, and the ceiling must exceed the per-repository timeout or a slow check's key expires while it is still running and a second check starts. The worker identity is deliberately not the value: the mutation returns this to the caller, and worker identity stays out of payloads (Principle VI, the same reason `answered_by` was dropped) |
| `git:refs_check:last:<repository_id>` | ISO timestamp | 30 days | when the remote was last checked, successfully or not. Written unconditionally at the end of every check, read by the resolver to fill `checked_at` (FR-007). Distinct from the due key, whose absence means "due" rather than "never checked". Bounded so a deleted repository's key does not linger; `checked_at` is therefore best-effort and reads null after a cache flush |

An API resolver reading a key a worker flow wrote is an established pattern here, not a new one:
`infrahub.core.merge.write_blocker` does exactly that through the same shared cache.

### Where the two freshness values come from

`fetched_at` is measured on the answering worker (the `FETCH_HEAD` mtime) and travels back in the RPC
reply. `checked_at` is read by the API resolver from `git:refs_check:last:<id>` and never travels
through the worker, because a refs listing touches no file the worker could stamp. It is null for
read-write repositories, where the every-minute sync fetches and `fetched_at` already means what a
user would read it to mean, and null for a read-only repository whose remote has never been checked.

## Error catalogue addition

| Code | HTTP | Exception | Payload |
| --- | --- | --- | --- |
| `WORKER_TIMEOUT` | 504 | `infrahub.exceptions::WorkerTimeoutError` | `WorkerTimeoutData(operation: str, timeout_seconds: int, retry_after_seconds: int)` |

Stability `evolving`. Registered in `infrahub.errors.catalogue::CATALOGUE`, built in
`infrahub.graphql.error_formatter::_build_payload`.

## Configuration

| Class | Field | Type | Default | Constraint |
| --- | --- | --- | --- | --- |
| `BrokerSettings` | `rpc_timeout` | int (seconds) | 30 | `ge=1` |
| `GitSettings` | `read_only_refs_check_interval_mins` | int | 15 | `ge=1` |

## Workflow definitions (`infrahub.workflows.catalogue`)

| Constant | Flow | Type | Schedule / concurrency |
| --- | --- | --- | --- |
| `GIT_REPOSITORY_WARM_UP` | `infrahub.git.tasks::warm_up_git_repository` | INTERNAL | on demand |
| `GIT_READ_ONLY_REPOSITORIES_CHECK_REFS` | `infrahub.git.tasks::check_read_only_repositories_refs` | INTERNAL | `* * * * *`, limit 1, `CANCEL_NEW` |
| `GIT_READ_ONLY_REPOSITORY_CHECK_REFS` | `infrahub.git.tasks::check_read_only_repository_refs` | USER | on demand (mutation) |

## State transitions of `condition` for one repository branch

```text
UNAVAILABLE(NOT_CLONED) --warm-up completes, next read--> IN_SYNC | BEHIND | REWRITTEN | ORPHANED | NO_REMOTE | NOT_TRACKED
IN_SYNC   --push to remote, fetch seen-->  BEHIND
BEHIND    --import runs-->                 IN_SYNC
BEHIND    --force-push / rebase-->         REWRITTEN
REWRITTEN --import of the new head-->      IN_SYNC
REWRITTEN --old commit collected upstream and locally--> ORPHANED
ORPHANED  --import of the new head-->      IN_SYNC
NOT_TRACKED --first import-->              IN_SYNC
```

The read-only refs check can move a branch from `IN_SYNC` to `BEHIND` or `REWRITTEN`; it can never
move it to `IN_SYNC`, because it never writes the tracked commit (FR-016).
