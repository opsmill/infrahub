# Contract: Connect-time trunk validation

Covers FR-007 and FR-010. The only operator-facing surface is the error message returned by the
existing create mutation; no GraphQL type, field or argument changes.

## Message bus

```python
class GitRepositoryConnectivity(InfrahubMessage):
    repository_name: str
    repository_location: str
    default_branch: str | None = None   # new
```

| Sender | `default_branch` |
|---|---|
| `repositories/create_repository.py::RepositoryFinalizer.post_create`, read-write kind | `obj.default_branch.value` |
| same, read-only kind | `None` |
| `graphql/mutations/repository.py::ValidateRepositoryConnectivity` (existing repository) | `None` |

`None` means "connectivity only", which is today's behaviour. The response model is unchanged.
`docs/docs/reference/message-bus-events.mdx` is regenerated.

## Worker-side listing

`backend/infrahub/git/remote_refs.py`, a new module holding the dataclass, the listing and the check
below as three module-level symbols:

```python
@dataclass(frozen=True)
class RemoteRefs:
    default_branch: str | None
    branches: frozenset[str]

def list_remote_refs(name: str, url: str) -> RemoteRefs
```

None of the three touches repository instance state, and the `connectivity` flow that uses them holds
no repository object, so putting the listing on `InfrahubRepositoryBase` would have used the class as
a namespace and forced the flow to name a concrete repository kind to reach it. The base class also
does not need three more symbols. `check_connectivity`'s current placement on the base is the shape
being replaced, not one to preserve; the static error classifier it delegates to stays where it is.

- Runs `git ls-remote --symref <url> HEAD refs/heads/*` from a neutral working directory, exactly
  as the current connectivity check does, so a `.git` pointer in the process cwd is never picked up.
- Parses the output line by line: a `ref: refs/heads/<name>\tHEAD` line sets `default_branch`; a
  `<sha>\trefs/heads/<name>` line adds `<name>` to `branches`; every other line (the `HEAD` object
  line) is ignored.
- Any `GitCommandError` is passed to the existing static classifier with no branch name, so
  connection, credential and TLS failures raise the same typed errors as today. Nothing is parsed
  when the command fails.
- An empty repository produces `RemoteRefs(default_branch=None, branches=frozenset())` and no error.
  Verified: an empty bare remote returns no output at all and exit status 0, under protocol v0 and v2
  alike, because `ls-remote` never requests the `unborn` ls-refs capability that would advertise an
  unborn `HEAD`. No special casing is needed.

Unit tests pin the parser against captured output for three shapes: a populated remote whose default
branch is not `main`, an empty remote, and a remote with branches but a detached `HEAD`.

## Pure check

```python
def ensure_branch_exists(refs: RemoteRefs, branch_name: str, repository_name: str) -> None
```

Raises `RepositoryInvalidBranchError(identifier=repository_name, branch_name=branch_name, location=..., message=...)`
when `branch_name not in refs.branches`. Messages, verbatim:

| Condition | Message |
|---|---|
| trunk absent, remote has a default branch | `Branch 'main' does not exist on the remote repository demo; the remote's default branch is 'stable'.` |
| trunk absent, remote has no default branch | `Branch 'main' does not exist on the remote repository demo; the remote is empty or has no default branch.` |
| trunk present | no error, regardless of whether it is the remote's default branch |

The second message covers both an empty remote and a detached `HEAD` without claiming to distinguish
them, because the listing does not.

The third row is FR-010: a trunk that exists but differs from the remote's default is a supported
configuration and produces no error, warning or log line.

## Flow

`message_bus/operations/git/repository.py::connectivity`:

1. `refs = list_remote_refs(name=..., url=...)`; a `RepositoryError` here is
   mapped exactly as today (`ERROR_CONNECTION`, `ERROR_CRED`, else `ERROR`).
2. If `message.default_branch` is set, `ensure_branch_exists(refs, message.default_branch, message.repository_name)`;
   `RepositoryInvalidBranchError` is mapped to `success=False`, `message=exc.message`,
   `operational_status=ERROR`.
3. Reply as today.

## Mutation outcome

`post_create` is unchanged in shape: on `success is False` it deletes the just-created node and
raises `ValidationError(response.data.message)`. The operator receives the message above as a
GraphQL error, and a subsequent query for the repository returns nothing. A retry with a corrected
trunk follows the normal create path.

FR-007 is therefore worded as "no repository remains after a rejected request" rather than "no
repository is created": the node is created and then deleted, exactly as it is for a connectivity
failure today. The observable outcome is the same, and the create-then-delete window is pre-existing
behaviour this feature does not change.

## Out of contract

- Editing `default_branch` on an existing repository is not validated (spec US3 scenario 5). The
  "Check connectivity" action passes `default_branch=None` and stays a reachability check; an
  on-demand configuration-validation action belongs with the manual repository controls (INFP-672).
- A read-only repository's tracked `ref` is not validated. A `ref` may name a branch, a tag or a raw
  commit SHA, and a SHA cannot be confirmed from a reference listing, so a check modelled on this one
  would falsely reject valid SHA-pinned repositories. Deferred to its own design.
- The conversion path that calls `post_create(delete_on_connectivity_failure=False)` performs
  neither check, as today.
