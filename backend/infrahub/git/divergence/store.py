from __future__ import annotations

from typing import TYPE_CHECKING

from infrahub_sdk.exceptions import Error as SdkError
from infrahub_sdk.protocols import CoreGenericRepository

from infrahub.exceptions import RepositoryError
from infrahub.git.divergence.gateway import readable_commit

if TYPE_CHECKING:
    from collections.abc import Callable

    from infrahub_sdk.client import InfrahubClient

    from infrahub.git.divergence.models import RewriteRecord


class SdkRepositoryReader:
    """Reads the repository node on one Infrahub branch, through the SDK node API."""

    def __init__(self, client: InfrahubClient) -> None:
        self.client = client

    async def get_repository(self, repository_id: str, infrahub_branch_name: str) -> CoreGenericRepository:
        """Return the repository node as the branch reads it.

        Raises:
            RepositoryError: When the API cannot answer, or holds no such repository on the branch.

        """
        try:
            return await self.client.get(kind=CoreGenericRepository, id=repository_id, branch=infrahub_branch_name)
        except SdkError as exc:
            raise RepositoryError(
                identifier=repository_id,
                message=f"Unable to read repository {repository_id} on branch {infrahub_branch_name}: {exc}",
            ) from exc

    async def get_commit(self, repository_id: str, infrahub_branch_name: str) -> str | None:
        """Return the commit the branch records, None when it records no full commit id.

        Raises:
            RepositoryError: When the API cannot answer, or holds no such repository on the branch.

        """
        repository = await self.get_repository(repository_id=repository_id, infrahub_branch_name=infrahub_branch_name)
        return readable_commit(repository.commit.value)


class SdkRepositoryRecordStore:
    """Holds the rewrite record on the repository node, through the SDK node API."""

    def __init__(self, client: InfrahubClient) -> None:
        self.reader = SdkRepositoryReader(client=client)

    async def write_record(
        self, repository_id: str, infrahub_branch_name: str, build_record: Callable[[int | None], RewriteRecord]
    ) -> None:
        """Read the repository node on the branch once, and save the record built from its count in one mutation.

        Raises:
            RepositoryError: When the API cannot answer, holds no such repository on the branch, or rejects
                the write.

        """
        repository = await self.reader.get_repository(
            repository_id=repository_id, infrahub_branch_name=infrahub_branch_name
        )
        record = build_record(repository.rewrite_count.value)
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

    def _access_failed(self, repository_id: str, infrahub_branch_name: str, exc: SdkError) -> RepositoryError:
        return RepositoryError(
            identifier=repository_id,
            message=f"Unable to access the rewrite record of repository {repository_id} on branch "
            f"{infrahub_branch_name}: {exc}",
        )
