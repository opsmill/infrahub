from __future__ import annotations

from typing import TYPE_CHECKING

import httpx
import pytest
from infrahub_sdk import Config, InfrahubClient

from infrahub.core import registry
from infrahub.core.constants import RepositorySyncStatus
from infrahub.core.initialization import create_branch
from infrahub.core.manager import NodeManager
from infrahub.core.node import Node
from infrahub.core.protocols import CoreReadOnlyRepository
from infrahub.core.repository_branch_status.factory import build_repository_branch_attributes_source
from infrahub.git.refs_check.ref_missing import BranchRefState, GraphRefMissingStatusStore

if TYPE_CHECKING:
    from collections.abc import Generator

    from infrahub_sdk.types import HTTPMethod

    from infrahub.database import InfrahubDatabase
    from tests.component.conftest import RepositoryBranchStatusBranches


@pytest.fixture(autouse=True)
def branch_registry_restored(
    repository_branch_status_branches: RepositoryBranchStatusBranches,
) -> Generator[None, None, None]:
    original = dict(registry.branch)
    yield
    registry.branch.clear()
    registry.branch.update(original)


async def _create_read_only_repository(db: InfrahubDatabase, name: str) -> CoreReadOnlyRepository:
    repository = await Node.init(db=db, schema=CoreReadOnlyRepository)
    await repository.new(db=db, name=name, location=f"https://example.com/{name}.git", ref="stable")
    await repository.save(db=db)
    return repository


async def _set_on_branch(
    db: InfrahubDatabase,
    repository_id: str,
    branch_name: str,
    sync_status: RepositorySyncStatus,
    ref: str | None = None,
) -> None:
    repository = await NodeManager.get_one(
        db=db, id=repository_id, kind=CoreReadOnlyRepository, branch=branch_name, raise_on_error=True
    )
    if ref is not None:
        repository.ref.value = ref
    repository.sync_status.value = sync_status.value
    await repository.save(db=db)


class RecordingRequester:
    """Answers every SDK call as a successful mutation and keeps the URL and payload of each one."""

    def __init__(self) -> None:
        self.calls: list[tuple[str, dict | None]] = []

    async def __call__(
        self,
        url: str,
        method: HTTPMethod,
        headers: dict,
        timeout: int,  # noqa: ASYNC109
        payload: dict | None = None,
    ) -> httpx.Response:
        self.calls.append((url, payload))
        return httpx.Response(
            status_code=200,
            json={"data": {"CoreGenericRepositoryUpdate": {"ok": True}}},
            request=httpx.Request(method="POST", url=url),
        )


def _store(db: InfrahubDatabase, requester: RecordingRequester | None = None) -> GraphRefMissingStatusStore:
    return GraphRefMissingStatusStore(
        db=db,
        client=InfrahubClient(config=Config(address="http://mock", requester=requester or RecordingRequester())),
        build_attributes_source=build_repository_branch_attributes_source,
        find_branch=registry.get_branch_from_registry,
    )


async def test_a_mark_writes_the_ref_missing_status_of_the_repository_on_that_branch_only(
    db: InfrahubDatabase, repository_branch_status_branches: RepositoryBranchStatusBranches
) -> None:
    requester = RecordingRequester()

    await _store(db=db, requester=requester).mark(repository_id="repository-id", branch_name="feature")

    assert [(url, payload["variables"] if payload else None) for url, payload in requester.calls] == [
        ("http://mock/graphql/feature", {"repo_id": "repository-id", "status": "error-ref-missing"})
    ]
    payload = requester.calls[0][1]
    assert payload is not None
    assert "CoreGenericRepositoryUpdate(data: { id: $repo_id, sync_status: { value: $status } })" in payload["query"]


async def test_only_a_branch_that_set_its_ref_holds_its_own_and_only_a_written_status_is_reported(
    db: InfrahubDatabase, repository_branch_status_branches: RepositoryBranchStatusBranches
) -> None:
    default_branch_name = repository_branch_status_branches.default_branch.name
    repository = await _create_read_only_repository(db=db, name="ref-missing-store")
    own = await create_branch(branch_name="ref-missing-store-own", db=db)
    inherits = await create_branch(branch_name="ref-missing-store-inherits", db=db)
    await _set_on_branch(
        db=db,
        repository_id=repository.id,
        branch_name=own.name,
        ref="release",
        sync_status=RepositorySyncStatus.ERROR_IMPORT,
    )
    await _set_on_branch(
        db=db,
        repository_id=repository.id,
        branch_name=default_branch_name,
        sync_status=RepositorySyncStatus.ERROR_REF_MISSING,
    )

    states = await _store(db=db).read(
        repository_id=repository.id,
        branch_names=[default_branch_name, own.name, inherits.name, "ref-missing-store-unknown"],
    )

    assert states == {
        default_branch_name: BranchRefState(
            ref="stable", holds_own_ref=True, written_sync_status=RepositorySyncStatus.ERROR_REF_MISSING
        ),
        own.name: BranchRefState(
            ref="release", holds_own_ref=True, written_sync_status=RepositorySyncStatus.ERROR_IMPORT
        ),
        inherits.name: BranchRefState(ref="stable", holds_own_ref=False, written_sync_status=None),
    }
