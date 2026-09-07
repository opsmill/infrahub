# Contract: Per-flow repository object

Internal Python contract between the Git module and every flow that constructs a repository object.
Symbols in `backend/infrahub/git/base.py` and `backend/infrahub/git/repository.py`.

## Construction

```python
class InfrahubRepository(InfrahubRepositoryIntegrator):
    default_branch: str                          # required, no default
    internal_status: RepositoryInternalStatus    # required, no default

class InfrahubReadOnlyRepository(InfrahubRepositoryIntegrator):
    ref: str | None = None
    is_read_only: bool = True
```

- `InfrahubRepository(...)` without `default_branch` or without `internal_status` raises
  `pydantic.ValidationError`. This is the enforcement for FR-002 and FR-005; there is no bypass.
- `InfrahubReadOnlyRepository` declares no trunk field and no code path reads one. The base model
  config ignores unknown keyword arguments, so a stray `default_branch=` passed to the read-only
  kind is dropped rather than rejected; the unit test for the read-only kind asserts the attribute
  does not exist on the instance.

## Factories

```python
# backend/infrahub/git/graph_settings.py — module level, not a method on the model
async def resolve_graph_settings(
    *, client: InfrahubClient, repository_id: str, repository_name: str, infrahub_branch_name: str
) -> RepositoryGraphSettings

@classmethod
async def InfrahubRepository.init(cls, *, id, name, client, infrahub_branch_name, commit=None, location=None) -> Self
@classmethod
async def InfrahubRepository.new(cls, *, id, name, client, infrahub_branch_name, location=None, update_commit_value=True) -> Self
```

- Both factories call `resolve_graph_settings` exactly once and construct with its values. They are
  the only production code that reads `CoreRepository.default_branch`.
- `infrahub_branch_name` is the Infrahub branch the operation runs on. The node is read on that
  branch, which is what makes a repository in staging resolvable.

### The resolver is a module, not a method on the repository class

`InfrahubRepository` is a pydantic model, and `.agents/rules/backend-component-design.md` keeps
database access off models for new code. `resolve_graph_settings` and `RepositoryGraphSettings`
therefore live in `backend/infrahub/git/graph_settings.py`, and the factories import them. FR-003's
single resolution point is unaffected by where the function lives; what changes is that the resolver
and its `RepositoryError` wrapping can be tested with a stub client and no repository object.

`repository_name` is a parameter because the wrapped error needs an identifier; a classmethod on the
class would not have had one either, since the failure happens before an instance exists.

### The factories set `infrahub_branch_name` on the instance

The base already declares `infrahub_branch_name: str | None` (`git/base.py:175`). The factories
construct with the value they read the node on, so the object never holds one branch in the field
while having been resolved against another. Without this the parameter shadows the field and the
object carries two answers to question (b) below.

**One behavioural consequence, intended and pinned by a test.** `_update_operational_status` sends
`branch_name=self.infrahub_branch_name or registry.default_branch` (`git/base.py:247`). Today
`_get_initialized_repo` omits the field (`git/repository.py:477`, `:480`), so every downstream flow
writes `operational_status` on the platform default branch no matter where it runs; afterwards those
writes land on the branch the operation ran on, which is the branch whose node it read. The read-only
write-back reads the same field (`git/repository.py:441-442`, `:460`). `operational_status` is
branch-scoped, so this moves an operator-visible value; research.md D7 carries the unit row that
asserts which branch the mutation names.

If that move is unwanted for an unrelated reason, the correction is for `_update_operational_status`
to name `registry.default_branch` outright — not to leave the field unset, which only relocates the
ambiguity.

### `location` keeps a caller-supplied override

Of the three values the resolver reads, `default_branch` and `internal_status` become required with
no fallback while `location` keeps a caller-wins override. This is deliberate and narrow: `location`
is the only one a caller can legitimately know better than the node does, and two paths rely on it —
tests that point a repository at a `file://` path on disk, and `RepositoryAdder.add`, which holds the
location from the add model. Neither has an equivalent for the trunk, which is why the trunk gets no
override. If neither caller survives implementation, drop the parameter rather than keep it unused.

### Error contract

`resolve_graph_settings` catches the SDK's base `Error` and re-raises
`RepositoryError(identifier=repository_name, message=...) from exc`. The factories add no fallback and
no retry.

This wrapping is required, not cosmetic. The SDK raises `NodeNotFoundError`, `BranchNotFoundError`,
`GraphQLError` and `ServerNotReachableError`, none of which derive from
`infrahub.exceptions.RepositoryError`, while every caller that isolates a single repository's failure
(`git/tasks.py::bootstrap_local_repository`, `sync_repository_from_origin`,
`sync_git_repo_with_origin_and_tag_on_failure`) catches `RepositoryError` and `CommitNotFoundError`
only. Unwrapped, a single misconfigured or deleted repository would abort the whole periodic sync
cycle for every repository. The cause is preserved with `from exc` so the original SDK error stays in
the traceback.

```python
@task(name="Fetch repository commit", cache_policy=NONE)
async def get_initialized_repo(
    client: InfrahubClient,
    repository_id: str,
    name: str,
    repository_kind: str,
    infrahub_branch_name: str,
    commit: str | None = None,
) -> InfrahubReadOnlyRepository | InfrahubRepository
```

Every caller passes the branch it operates on. Five need the branch named explicitly rather than
taken from a model field; see research.md D4 for the table and the reasons. In short: the
branch-deleted refresh flow and both git branch-lifecycle tasks (`git_branch_create`,
`git_branch_delete`) pass `registry.default_branch` explicitly, the file-fetch message gains a
`branch_name` field, and `merge_git_repository` — a **direct** `InfrahubRepository.init` caller, not a
`get_initialized_repo` one — passes `model.destination_branch`.

`git_branch_delete` matters most: its fan-out runs after the Infrahub branch has been deleted, so
reading the node on that branch would raise `BranchNotFoundError` and break every `delete_from_git`
cleanup.

`merge_git_repository` matters next: it is the merge write-back path (spec US1 scenario 5), its model
carries two candidate branches, and it is easy to miss because it does not go through
`get_initialized_repo`. The merge lands on the destination branch, and the flow takes its staging
decision from `model.internal_status` rather than from the object, so the object's status never needs
to resolve `STAGING`.

## The three questions

| Question | Answered by | Never answered by |
|---|---|---|
| Which remote branch is the trunk | `InfrahubRepository.default_branch` | `registry.default_branch` |
| Which Infrahub branch a commit is recorded against | an explicit `infrahub_branch_name`, or `registry.default_branch` when none was named | the trunk |
| Which branch name appears in an error message | the `branch_name` the failing operation was given, or nothing | a fallback of either kind |

Worked example of the middle row. `webhook/models.py::TransformWebhook.compute_payload` computes the
Infrahub branch it runs a transform on. It reads `context.branch or registry.default_branch`, and
passes that value both to the factory and to `get_commit_value`. It must never read
`repo.default_branch`: that is the trunk, and using it here would name an Infrahub branch that need
not exist. The expression looks harmless today only because the removed fallback happened to resolve
to the platform default.

## Abstract hooks on the base

```python
@abstractmethod
def _get_mapped_remote_branch(self, branch_name: str) -> str: ...
@abstractmethod
def _get_mapped_target_branch(self, branch_name: str) -> str: ...
@abstractmethod
def _resolve_worktree_identifier(self, branch_name: str) -> str: ...
```

Read-write semantics (unchanged from today, now reading the required field):

| Input | `_get_mapped_remote_branch` | `_get_mapped_target_branch` | `_resolve_worktree_identifier` |
|---|---|---|---|
| Infrahub default name, trunk differs | trunk | same name | same name |
| trunk name, trunk differs from Infrahub default | same name | Infrahub default name | `main` |
| any other name, or trunk equals Infrahub default | same name | same name | same name |

Read-only semantics: all three return their input. This matches what the read-only kind computed
before, because its trunk always equalled the platform default.

## Error path

```python
async def _raise_enriched_error(self, error: GitCommandError, branch_name: str | None = None) -> NoReturn
```

- `branch_name` is forwarded as given. `fetch()` passes none.
- With `branch_name=None` the classifier still raises the same exception types as today for the
  same stderr patterns. The two messages that name a branch read
  "The requested branch isn't a valid branch for the repository X at Y." and
  "Unable to pull repository X, there are conflicts that must be resolved." when no branch was
  given, and keep their current wording when one was.
- Operational status side effects are unchanged.

## `create_locally`

```python
async def create_locally(self, checkout_ref: str, infrahub_branch_name: str | None = None, update_commit_value: bool = True) -> bool
```

- `checkout_ref` is required. The read-write kind passes `self.default_branch`; the read-only kind
  passes its resolved `ref`.
- The commit is recorded against `infrahub_branch_name` when given, otherwise against the Infrahub
  default branch.

## Removed carriers (FR-003)

| Symbol | Change |
|---|---|
| `git/models.py::GitRepositoryAdd.default_branch_name` | removed |
| `git/models.py::GitRepositoryMerge.default_branch` | removed |
| `git/tasks.py::sync_git_repo_with_origin_and_tag_on_failure(default_branch_name=, internal_status=)` | parameters removed |
| `git/tasks.py::bootstrap_local_repository` | stops forwarding `default_branch_name` and `internal_status` |
| `repositories/create_repository.py::RepositoryFinalizer.post_create` | stops setting `default_branch_name` on the add model |
| `core/merge/repository_merge_dispatcher.py::RepositoryMergeDispatcher.merge_core_repositories` | stops setting `default_branch` on the merge model |
| `git/tasks.py::merge_git_repository` | stops passing `default_branch_name=model.default_branch` to `InfrahubRepository.init` and passes `infrahub_branch_name=model.destination_branch` instead (research.md D4) |

After the change, `grep -rn "default_branch_name" backend/infrahub/` returns nothing, and
`grep -rn "default_branch" backend/infrahub/git/models.py` returns nothing.

### Deliberately kept: `GitRepositoryAdd.internal_status`

`GitRepositoryAdd.internal_status` stays on the model. It is **flow control**, not a carrier of the
object's field: `add_git_repository` reads it at `git/tasks.py:100` to decide whether to synchronise
at all, and returns early for a repository added in staging — before any repository object would be
asked for its status.

So after this change the staging status legitimately exists in two places: the message field (does
this flow sync?) and the object field (resolved from the graph, on the branch the operation runs on).
Both derive from the same node, so they agree. This is recorded because FR-003's logic, applied
mechanically to FR-005, reads like an instruction to delete this field too — which would remove the
staging early return and make the add flow synchronise a repository that exists only on its branch.
It is not a carrier FR-003 or FR-005 targets.

### Construction sites must sit inside their flow's error handling

`sync_git_repo_with_origin_and_tag_on_failure` constructs the repository at `git/tasks.py:225`,
outside the `try` at `:235`. Because construction now performs a graph read that raises
`RepositoryError` under the error contract above, the construction moves **inside** the `try`, so a
node-read failure is tagged with the repository node like any other sync failure. Without the move
the sync cycle still survives (`sync_repository_from_origin` isolates it at `git/tasks.py:338`), but
the run is never linked to the repository, so the failure is absent from the Tasks tab that SC-005
promises. Apply the same check to any other call site that constructs outside its handler.
