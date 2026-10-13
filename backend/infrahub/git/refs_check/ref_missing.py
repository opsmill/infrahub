"""Reading and writing the sync status that tells a user a tracked ref is gone from the remote."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import TYPE_CHECKING, Protocol

from infrahub.core.constants import InfrahubKind, RepositorySyncStatus
from infrahub.core.timestamp import Timestamp
from infrahub.exceptions import BranchNotFoundError, RepositoryError
from infrahub.log import get_run_logger

from ..constants import UPDATE_SYNC_STATUS_MUTATION
from ..sync_status import is_written_on_branch

if TYPE_CHECKING:
    from collections.abc import Mapping

    from infrahub_sdk.client import InfrahubClient

    from infrahub.core.branch import Branch
    from infrahub.core.repository_branch_status.interface import RepositoryBranchAttributesSource
    from infrahub.database import InfrahubDatabase

    from ..models import GitRepositoryImportObjects
    from .gateway import RepositoryRefsGateway

AttributesSourceFactory = Callable[["InfrahubDatabase"], "RepositoryBranchAttributesSource"]

BranchFinder = Callable[[str], "Branch"]
"""Returns the branch of a name, raising BranchNotFoundError for one that does not exist."""

log = get_run_logger()


@dataclass(frozen=True)
class BranchRefState:
    """What decides whether a branch tracking a missing ref is marked."""

    ref: str
    """The ref the repository tracks on the branch when it was read."""

    holds_own_ref: bool
    """Whether the branch set `ref` itself rather than inheriting it from the branch it was created from."""

    written_sync_status: RepositorySyncStatus | None
    """The sync status written on the branch itself, or None when the branch only inherits one."""


class RefMissingStatusStore(Protocol):
    async def read(self, *, repository_id: str, branch_names: list[str]) -> Mapping[str, BranchRefState]:
        """Return the state of each branch, leaving out a branch that no longer exists or resolves no `ref`."""
        ...

    async def mark(self, *, repository_id: str, branch_name: str) -> None:
        """Set the sync status of the repository on the branch to the tracked-ref-missing value."""
        ...


class GraphRefMissingStatusStore:
    """Reads from the graph in a read-only session of its own, and writes through the API.

    The status written on a branch is read the way the merge guard reads it, so the two never disagree on
    whether a branch is marked.
    """

    def __init__(
        self,
        *,
        db: InfrahubDatabase,
        client: InfrahubClient,
        build_attributes_source: AttributesSourceFactory,
        find_branch: BranchFinder,
    ) -> None:
        self._db = db
        self._client = client
        self._build_attributes_source = build_attributes_source
        self._find_branch = find_branch

    async def read(self, *, repository_id: str, branch_names: list[str]) -> Mapping[str, BranchRefState]:
        async with self._db.start_session(read_only=True) as db:
            attributes = await self._build_attributes_source(db).read(
                repository_ids=[repository_id], branch_names=branch_names, attribute_names=("ref", "sync_status")
            )

        states = {}
        for branch_name in branch_names:
            ref = attributes.get(repository_id=repository_id, branch_name=branch_name, attribute_name="ref")
            if ref is None or not ref.value:
                continue
            try:
                branch = self._find_branch(branch_name)
            except BranchNotFoundError:
                continue
            sync_status = attributes.get(
                repository_id=repository_id, branch_name=branch_name, attribute_name="sync_status"
            )
            written_sync_status = None
            if (
                sync_status is not None
                and sync_status.value
                and is_written_on_branch(
                    updated_at=Timestamp(sync_status.updated_at) if sync_status.updated_at else None, branch=branch
                )
            ):
                written_sync_status = RepositorySyncStatus(sync_status.value)
            states[branch_name] = BranchRefState(
                ref=ref.value, holds_own_ref=ref.own_value, written_sync_status=written_sync_status
            )
        return states

    async def mark(self, *, repository_id: str, branch_name: str) -> None:
        await self._client.execute_graphql(
            branch_name=branch_name,
            query=UPDATE_SYNC_STATUS_MUTATION,
            variables={"repo_id": repository_id, "status": RepositorySyncStatus.ERROR_REF_MISSING.value},
            tracker="mutation-repository-mark-ref-missing",
        )


@dataclass(frozen=True)
class _ImportedRepository:
    repository_id: str
    repository_name: str
    location: str


class RefMissingImportGate:
    """Decides the sync status an import of a read-only repository leaves on a branch.

    An import of the commit Infrahub already runs never looks the ref up, so it would otherwise clear the
    mark, and with it the refused merge, while the ref is still gone. Only a branch that carries the mark
    is looked at, so a branch the refs check would not mark is never marked here either.
    """

    def __init__(self, *, store: RefMissingStatusStore, gateway: RepositoryRefsGateway) -> None:
        self._store = store
        self._gateway = gateway

    async def status_after_import(
        self, *, model: GitRepositoryImportObjects, location: str | None
    ) -> RepositorySyncStatus:
        """Return the status the import described by `model` leaves on its branch once its objects are imported."""
        if model.repository_kind != InfrahubKind.READONLYREPOSITORY:
            return RepositorySyncStatus.IN_SYNC

        branch_name = model.infrahub_branch_name
        states = await self._store.read(repository_id=model.repository_id, branch_names=[branch_name])
        state = states.get(branch_name)
        if state is None or state.written_sync_status != RepositorySyncStatus.ERROR_REF_MISSING:
            return RepositorySyncStatus.IN_SYNC

        reason = await self._reason_to_keep_mark(model=model, location=location, ref=state.ref)
        if reason is None:
            return RepositorySyncStatus.IN_SYNC
        log.info(
            "Keeping the missing ref status of repository %s on branch %s: %s",
            model.repository_name,
            branch_name,
            reason,
        )
        return RepositorySyncStatus.ERROR_REF_MISSING

    async def _reason_to_keep_mark(
        self, *, model: GitRepositoryImportObjects, location: str | None, ref: str
    ) -> str | None:
        """Return why the remote cannot be shown to carry `ref`, or None when it carries it."""
        if not location:
            return "the repository has no location to list"

        repository = _ImportedRepository(
            repository_id=model.repository_id, repository_name=model.repository_name, location=location
        )
        try:
            heads = await self._gateway.read_heads(repository, (ref,))
        # Clearing the mark needs the ref seen on the remote, which a failed listing cannot show.
        except RepositoryError as exc:
            return f"the remote could not be listed: {exc.message}"

        if all(head.remote_head is None and not head.pinned_commit for head in heads):
            return f"ref {ref} is still missing from the remote"
        return None
