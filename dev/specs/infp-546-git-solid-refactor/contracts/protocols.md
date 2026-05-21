# Contract: Repository Protocols (Story 3, FR-006)

**Path**: `backend/infrahub/git/protocols.py`, re-exported via `infrahub.git.repository`.

Two structural `typing.Protocol` types. The exact method set is finalized by an FR-020 audit (grep all callers of `InfrahubRepository` / `InfrahubReadOnlyRepository` in the backend, list every method invoked) before the protocol PR opens. The lists below are the working surface from research.md.

## `ReadOnlyRepositoryProtocol`

```python
from typing import Protocol

class ReadOnlyRepositoryProtocol(Protocol):
    name: str
    id: str
    default_branch: str

    def get_commit_value(self, branch_name: str, remote: bool = False) -> str: ...
    def get_commit_worktree(self, commit: str) -> Worktree: ...
    def get_worktree(self, identifier: str) -> Worktree: ...
    def find_files(
        self,
        extension: list[str] | str,
        branch_name: str | None = None,
        commit: str | None = None,
        directory: str | None = None,
        recursive: bool = True,
    ) -> list[Path]: ...
    async def get_file_content(self, commit: str, file_path: str) -> str: ...
    async def get_repository_config(self, branch_name: str, commit: str) -> InfrahubRepositoryConfig | None: ...
```

### Required of every consumer

A function that today receives `InfrahubReadOnlyRepository | InfrahubRepository` and only invokes read-side methods MAY be migrated to type its parameter as `ReadOnlyRepositoryProtocol`. Story 3's acceptance requires at least one such consumer migration; further migrations are follow-up PRs of the same shape.

### Required of every implementation

`InfrahubRepository` and `InfrahubReadOnlyRepository` satisfy this protocol structurally. No new method is added to either class to make them satisfy it — the protocol is derived from existing behavior.

## `RepositoryProtocol`

```python
class RepositoryProtocol(ReadOnlyRepositoryProtocol, Protocol):
    async def pull(self, branch_name: str) -> bool: ...
    async def push(self, branch_name: str) -> bool: ...
    async def merge(
        self, source_branch: str, dest_branch: str, push_remote: bool = True,
    ) -> str | Literal[False]: ...    # post-Story-2 signature
    async def rebase(
        self, branch_name: str, source_branch: str = "main", push_remote: bool = True,
    ) -> bool: ...
    async def sync(self) -> None: ...
    async def create_branch_in_git(self, branch_name: str, push_origin: bool = True) -> bool: ...
    async def delete_branch_in_git(self, branch_name: str) -> None: ...
    async def update_commit_value(self, branch_name: str, commit: str) -> bool: ...
```

### Notes

- `merge`'s declared return type is `str | Literal[False]` AFTER Story 2 ships. Before then, the protocol carries the same misleading `-> bool` as the runtime; Story 2 and the protocol PR may land in either order, with the later PR aligning to whichever is current.
- `InfrahubReadOnlyRepository` inherits write methods from the integrator/base and therefore also satisfies this protocol at runtime. Consumers that need a *strict* read-only type use `ReadOnlyRepositoryProtocol`; the protocol type is the constraint, not the runtime class.

## Backwards-compatible re-exports

```python
# infrahub/git/repository.py — appended after Story 3 PR
from infrahub.git.protocols import ReadOnlyRepositoryProtocol, RepositoryProtocol  # noqa: F401  re-export

__all__ = [
    "InfrahubReadOnlyRepository",
    "InfrahubRepository",
    "ReadOnlyRepositoryProtocol",
    "RepositoryProtocol",
    "get_initialized_repo",
]
```

## Verification

- `mypy backend/infrahub/git/` clean against both protocols (within the bounds of existing per-module suppressions; no new suppression added — FR-018).
- A unit test under `backend/tests/unit/git/test_protocols.py` constructs each concrete class and assigns it to a variable typed as each protocol; if the structural match fails, mypy errors. (Runtime `isinstance` is not used — protocols are not `runtime_checkable` here.)
- The Story 3 PR migrates at least one existing consumer to depend on the protocol; the diff shows the type annotation change and a passing test.
