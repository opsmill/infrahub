from __future__ import annotations

from typing import TYPE_CHECKING

from infrahub_sdk.exceptions import Error as SdkError
from infrahub_sdk.protocols import CoreGenericRepository

from infrahub.exceptions import RepositoryError

if TYPE_CHECKING:
    from infrahub_sdk.client import InfrahubClient

    from infrahub.git.divergence.models import RewriteRecord


class SdkRepositoryRecordStore:
    """Holds the rewrite record on the repository node, through the SDK node API."""

    def __init__(self, client: InfrahubClient) -> None:
        self.client = client

    async def get_rewrite_count(self, repository_id: str, infrahub_branch_name: str) -> int | None:
        """Return the rewrite count the repository reads on the branch, None when it reads none.

        Raises:
            RepositoryError: When the API cannot answer, or holds no such repository on the branch.

        """
        repository = await self._get_repository(repository_id=repository_id, infrahub_branch_name=infrahub_branch_name)
        return repository.rewrite_count.value

    async def write_record(self, repository_id: str, infrahub_branch_name: str, record: RewriteRecord) -> None:
        """Write the four values of the record on the branch, in one mutation.

        Raises:
            RepositoryError: When the API rejects the write or cannot be reached.

        """
        repository = await self._get_repository(repository_id=repository_id, infrahub_branch_name=infrahub_branch_name)
        repository.last_rewrite_previous_commit.value = record.previous_commit
        repository.last_rewrite_commit.value = record.commit
        repository.last_rewrite_at.value = record.rewritten_at.isoformat()
        repository.rewrite_count.value = record.rewrite_count
        try:
            await repository.save()
        except SdkError as exc:
            raise self._access_failed(
                repository_id=repository_id, infrahub_branch_name=infrahub_branch_name, exc=exc
            ) from exc

    async def _get_repository(self, repository_id: str, infrahub_branch_name: str) -> CoreGenericRepository:
        try:
            return await self.client.get(kind=CoreGenericRepository, id=repository_id, branch=infrahub_branch_name)
        except SdkError as exc:
            raise self._access_failed(
                repository_id=repository_id, infrahub_branch_name=infrahub_branch_name, exc=exc
            ) from exc

    def _access_failed(self, repository_id: str, infrahub_branch_name: str, exc: SdkError) -> RepositoryError:
        return RepositoryError(
            identifier=repository_id,
            message=f"Unable to access the rewrite record of repository {repository_id} on branch "
            f"{infrahub_branch_name}: {exc}",
        )
