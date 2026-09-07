# Data Model: Honour the Configured Repository Default Branch

No graph schema, migration, GraphQL schema or REST change. Every entity below is an in-process
object or an internal message model. Locations are cited as `module::symbol`; field shapes are the
target state after implementation.

## Graph entities (unchanged)

| Kind | Attribute | Shape | Note |
|---|---|---|---|
| `CoreRepository` | `default_branch` | Text, mandatory, default `main` | The trunk. Meaning clarified by the already-landed description: the remote branch Infrahub maps onto its own default branch. |
| `CoreRepository` | `internal_status` | Text, `active` / `inactive` / `staging`, branch-scoped | `ACTIVE` on the default branch, `STAGING` on the branch the repository was created in. |
| `CoreReadOnlyRepository` | `ref` | Text, mandatory, default `main` | The single ref a read-only repository tracks. No trunk. |

## Per-flow repository object

### `backend/infrahub/git/base.py::InfrahubRepositoryBase` (shared base)

Fields after the change:

| Field | Type | Change |
|---|---|---|
| `id` | `UUID` | unchanged |
| `name` | `str` | unchanged |
| `type` | `str \| None` | unchanged |
| `location` | `str \| None` | unchanged |
| `has_origin` | `bool` | unchanged |
| `client` | `InfrahubClient \| None` | unchanged |
| `cache_repo` | `Repo \| None` | unchanged |
| `is_read_only` | `bool` | unchanged |
| `reinitialized` | `bool` | unchanged |
| `infrahub_branch_name` | `str \| None` | shape unchanged, but the factories now **populate** it with the branch they read the node on, so it is no longer `None` on the `get_initialized_repo` path. See the note below the read-write factories |
| `default_branch_name` | | **removed** |
| `default_branch` (property) | | **removed** |
| `internal_status` | | **removed** (moves to the read-write class) |

Abstract hooks added to the base (each kind must implement all three):

| Hook | Read-write implementation | Read-only implementation |
|---|---|---|
| `_get_mapped_remote_branch(branch_name) -> str` | Infrahub default branch name maps to `self.default_branch`; every other name is returned as is | identity |
| `_get_mapped_target_branch(branch_name) -> str` | `self.default_branch` maps to the Infrahub default branch name; every other name is returned as is | identity |
| `_resolve_worktree_identifier(branch_name) -> str` | `self.default_branch` maps to the on-disk identifier `main` when it differs from the Infrahub default; every other name is returned as is | identity |

Signature changes on the base:

| Method | Before | After |
|---|---|---|
| `create_locally` | `checkout_ref: str \| None = None, infrahub_branch_name: str \| None = None, update_commit_value: bool = True` | `checkout_ref: str, infrahub_branch_name: str \| None = None, update_commit_value: bool = True`. Records the commit against `infrahub_branch_name` when given, otherwise against the Infrahub default branch. |
| `_raise_enriched_error` | `branch_name or self.default_branch` | passes `branch_name` through, `None` allowed |
| `_raise_enriched_error_static` | `branch_name: str \| None` | unchanged signature; the two messages that name a branch omit it when `None` |
| `check_connectivity` | `(name, url) -> None` classmethod, runs `ls-remote --tags` | **removed from the class**; replaced by the module-level `remote_refs.list_remote_refs(name, url) -> RemoteRefs` (see below). Connectivity failure still raises through the static classifier, which stays on the base |
| `validate_remote_branch` | `(branch_name: str) -> bool` on the base | **moves to `InfrahubRepository`** and returns `BranchSkipReason \| None` (see below), so the caller records a skipped branch from the decision rather than re-testing the predicate |

### `backend/infrahub/git/repository.py::InfrahubRepository` (read-write)

| Field | Type | Change |
|---|---|---|
| `default_branch` | `str` | **new, required**. The trunk. No default. |
| `internal_status` | `RepositoryInternalStatus` | **new here, required**. Was a defaulted `str` on the base. |

Validation rule: omitting either field raises `pydantic.ValidationError` at construction (FR-002,
FR-005). There is no other path to an instance.

Factories (the single resolution point, D1):

- `InfrahubRepository.init(id, name, client, infrahub_branch_name, commit=None, location=None)`
  and `InfrahubRepository.new(id, name, client, infrahub_branch_name, location=None, update_commit_value=True)`
  read the node once via the resolver below, then construct with `default_branch`, `internal_status`
  and `location` (a caller-supplied `location` wins over the node's).
- Both factories also set `infrahub_branch_name` on the instance from their parameter, so the branch
  the node was read on and the branch the object reports are one value. This changes which branch
  `_update_operational_status` writes on for every `get_initialized_repo` caller; see
  `contracts/repository-object.md`.
- `InfrahubRepository.resolve_checkout_ref()` returns `self.default_branch` without a graph read.

### `backend/infrahub/git/repository.py::InfrahubReadOnlyRepository` (read-only)

| Field | Type | Change |
|---|---|---|
| `ref` | `str \| None` | unchanged |
| `is_read_only` | `bool = True` | unchanged |

No trunk, no staging status. `resolve_checkout_ref()` keeps reading `ref` from the node when the
field is unset; the dead fallback to a trunk is removed and the method raises if the node has no ref.

### `backend/infrahub/git/graph_settings.py::RepositoryGraphSettings` (new module)

Frozen dataclass returned by the resolver. One instance per construction; never stored.

| Field | Type | Source |
|---|---|---|
| `default_branch` | `str` | `CoreRepository.default_branch.value` on the operation's Infrahub branch |
| `internal_status` | `RepositoryInternalStatus` | `CoreRepository.internal_status.value` on the same branch |
| `location` | `str` | `CoreRepository.location.value` |

Resolver, a module-level function in the same module rather than a method on the repository model
(`.agents/rules/backend-component-design.md`, "Persistence lives in Repository/Query classes, not on
models"):
`resolve_graph_settings(client, repository_id, repository_name, infrahub_branch_name) -> RepositoryGraphSettings`.
One SDK `get` by id on the given branch, `raise_when_missing=True`. `repository_name` is what the
wrapped `RepositoryError(identifier=...)` needs. The SDK's exceptions
(`NodeNotFoundError`, `BranchNotFoundError`, `GraphQLError`, `ServerNotReachableError`) are caught and
re-raised as `RepositoryError(identifier=repository_name, message=...) from exc`, because the callers that
isolate a single repository's failure catch `RepositoryError` and `CommitNotFoundError` only. See
`contracts/repository-object.md` for the full contract.

### `backend/infrahub/git/repository.py::get_initialized_repo` (factory task)

| Parameter | Before | After |
|---|---|---|
| `client`, `repository_id`, `name`, `repository_kind`, `commit` | present | unchanged |
| `infrahub_branch_name` | absent | **new, required** `str` |

Cache key of `_get_initialized_repo` gains `infrahub_branch_name`.

## Remote reference listing (connect-time validation, D5)

### `backend/infrahub/git/remote_refs.py::RemoteRefs` (new module)

Frozen dataclass produced from one `git ls-remote --symref <url> HEAD refs/heads/*` invocation. The
dataclass, the listing function and the pure check below are three module-level symbols; none of them
touches repository instance state, and the connect path that uses them holds no repository object.

| Field | Type | Meaning |
|---|---|---|
| `default_branch` | `str \| None` | The branch `HEAD` points at, from the `ref: refs/heads/<name>\tHEAD` line. `None` when the remote has no `HEAD` (empty repository) or `HEAD` is detached. |
| `branches` | `frozenset[str]` | Short names of every `refs/heads/*` entry. |

Pure check: `ensure_branch_exists(refs: RemoteRefs, branch_name: str, repository_name: str, location: str) -> None`

`location` is the remote URL, required because `RepositoryInvalidBranchError.__init__` takes it as a
required positional parameter. `RemoteRefs` holds no URL by design, so the caller supplies it from
`message.repository_location`.
raises `RepositoryInvalidBranchError` when `branch_name not in refs.branches`.

## Synchronisation report (task-log warning, D6)

### `backend/infrahub/git/models.py::CollectedImports`

| Field | Type | Change |
|---|---|---|
| `imports` | `list[PendingObjectImport]` | unchanged |
| `failed_imports` | `list[FailedImport]` | unchanged |
| `skipped_branches` | `list[str]` | **new**, default empty. Remote branches not imported because their name collides with the Infrahub default branch while the trunk differs. |
| `advanced_skipped_branches` | `list[str]` | **new**, default empty. The subset of `skipped_branches` whose remote head moved during this run's fetch. Derived by listing the remote heads immediately before `fetch` and comparing after it. A branch with no head in the pre-fetch listing is omitted, so a cold clone reports nothing on this basis. |

### `backend/infrahub/git/repository.py::BranchSkipReason` (new)

Enum returned by `validate_remote_branch` in place of a bare `bool`, so the reason a branch was
skipped is available to the caller without re-deriving the predicate. `None` means "import it".

| Member | Meaning |
|---|---|
| `DEFAULT_BRANCH_COLLISION` | The branch name equals Infrahub's default branch while the trunk differs. Recorded in `skipped_branches`. |
| `INVALID_BRANCH_NAME` | `Branch(name=...)` failed pydantic validation. Skipped, not recorded as a collision. |

`validate_remote_branch` moves from `InfrahubRepositoryBase` to `InfrahubRepository` with this
change; it is reached only through `collect_pending_imports` on the read-write class.

### `backend/infrahub/git/sync.py::SyncReport` (new)

Frozen dataclass returned by `RepositorySyncer.sync` (previously returned `None`), and attached to
`RepositoryBranchesFailedError` so it is available on the failure path too — see
`contracts/sync-task-log.md` for why the warning must survive a partial import failure.

| Field | Type | Meaning |
|---|---|---|
| `skipped_branches` | `tuple[str, ...]` | Copied from `CollectedImports.skipped_branches` for the run. Empty when nothing was skipped. |
| `imported_branches` | `tuple[str, ...]` | Infrahub branch name of every import the run applied successfully. Empty when the run changed nothing, which is the case on every cycle whose only new remote branch is the permanently-skipped colliding one. |
| `advanced_skipped_branches` | `tuple[str, ...]` | Copied from `CollectedImports.advanced_skipped_branches` for the run. Non-empty when a skipped branch received a commit since this worker's previous fetch. |

`imported_branches` and `advanced_skipped_branches` are the two stateless signals that separate a
cycle worth reporting from one where nothing moved. Both empty means no warning and no node link.

## Message models

### `backend/infrahub/message_bus/messages/git_repository_connectivity.py::GitRepositoryConnectivity`

| Field | Type | Change |
|---|---|---|
| `repository_name` | `str` | unchanged |
| `repository_location` | `str` | unchanged |
| `default_branch` | `str \| None = None` | **new**. Set by the create path for the read-write kind. `None` for read-only repositories and for the standalone connectivity check on an existing repository, in which case no trunk validation is performed. |

Response model unchanged: `message`, `success`, `operational_status`.

### `backend/infrahub/message_bus/messages/git_file_get.py::GitFileGet`

| Field | Type | Change |
|---|---|---|
| `branch_name` | `str` | **new, required**. The Infrahub branch the file request is scoped to; forwarded to the factory. |

### `backend/infrahub/git/models.py`

| Model | Field | Change |
|---|---|---|
| `GitRepositoryAdd` | `default_branch_name` | **removed** (FR-003) |
| `GitRepositoryMerge` | `default_branch` | **removed** (FR-003) |

### Flow parameters

`backend/infrahub/git/tasks.py::sync_git_repo_with_origin_and_tag_on_failure` loses
`internal_status` and `default_branch_name`; it keeps `client`, `repository_id`, `repository_name`,
`repository_location`, `operational_status`, `staging_branch` and `infrahub_branch` (now required,
because it is the branch the factory reads the node on). The repository construction moves inside the
flow's existing `try`, so a failing node read is tagged with the repository node.

`GitRepositoryAdd.internal_status` is **not** removed: it is flow control for the staging early
return at `git/tasks.py:100`, not a carrier of the object's field. See
`contracts/repository-object.md`.

## State transitions

None. The feature adds no status values and keeps no state across synchronisation runs. The one
lifecycle that changes is the repository object's: the trunk moves from "resolved on the cold-clone
path only" to "resolved at every construction".
