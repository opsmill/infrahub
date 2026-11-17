from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from infrahub.core import registry
from infrahub.core.constants import RepositoryInternalStatus, RepositorySyncStatus
from infrahub.core.initialization import create_branch
from infrahub.core.manager import NodeManager
from infrahub.core.node import Node
from infrahub.core.protocols import CoreReadOnlyRepository
from infrahub.git.sync_status import RepositoryBranchSyncStatus, RepositoryBranchSyncStatusReader

if TYPE_CHECKING:
    from collections.abc import Generator

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
    await repository.new(
        db=db,
        name=name,
        location=f"https://example.com/{name}.git",
        ref="stable",
        internal_status=RepositoryInternalStatus.ACTIVE.value,
    )
    await repository.save(db=db)
    return repository


async def _set_on_branch(
    db: InfrahubDatabase, repository_id: str, branch_name: str, sync_status: RepositorySyncStatus, ref: str
) -> None:
    repository = await NodeManager.get_one(
        db=db, id=repository_id, kind=CoreReadOnlyRepository, branch=branch_name, raise_on_error=True
    )
    repository.ref.value = ref
    repository.sync_status.value = sync_status.value
    await repository.save(db=db)


async def test_the_tracked_ref_on_the_branch_is_read_only_for_a_repository_whose_ref_is_missing(
    db: InfrahubDatabase, repository_branch_status_branches: RepositoryBranchStatusBranches
) -> None:
    ref_missing = await _create_read_only_repository(db=db, name="reader-ref-missing")
    import_failed = await _create_read_only_repository(db=db, name="reader-import-failed")
    branch = await create_branch(branch_name="reader-tracked-ref", db=db)
    await _set_on_branch(
        db=db,
        repository_id=ref_missing.id,
        branch_name=branch.name,
        sync_status=RepositorySyncStatus.ERROR_REF_MISSING,
        ref="v1.0",
    )
    await _set_on_branch(
        db=db,
        repository_id=import_failed.id,
        branch_name=branch.name,
        sync_status=RepositorySyncStatus.ERROR_IMPORT,
        ref="v2.0",
    )
    reader = RepositoryBranchSyncStatusReader(db=db)

    statuses = await reader.list_statuses_on_branch(branch=branch)
    tracked_ref = await reader.get_tracked_ref(repository_id=ref_missing.id, branch=branch)

    assert sorted(
        (status for status in statuses if status.repository_name.startswith("reader-")),
        key=lambda status: status.repository_name,
    ) == [
        RepositoryBranchSyncStatus(
            repository_name="reader-import-failed",
            internal_status=RepositoryInternalStatus.ACTIVE,
            sync_status=RepositorySyncStatus.ERROR_IMPORT,
            tracked_ref=None,
        ),
        RepositoryBranchSyncStatus(
            repository_name="reader-ref-missing",
            internal_status=RepositoryInternalStatus.ACTIVE,
            sync_status=RepositorySyncStatus.ERROR_REF_MISSING,
            tracked_ref="v1.0",
        ),
    ]
    assert tracked_ref == "v1.0"
