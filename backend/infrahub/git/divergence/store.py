from __future__ import annotations

from typing import TYPE_CHECKING, Any

from infrahub_sdk.exceptions import Error as SdkError

from infrahub.exceptions import RepositoryError

if TYPE_CHECKING:
    from infrahub_sdk.client import InfrahubClient

    from infrahub.git.divergence.models import RewriteRecord

REWRITE_COUNT_QUERY = """
query RepositoryRewriteCount($repository_id: ID!) {
    CoreGenericRepository(ids: [$repository_id]) {
        edges {
            node {
                rewrite_count {
                    value
                }
            }
        }
    }
}
"""

# The generic mutation serves both repository kinds, and it sends only the four fields it names.
REWRITE_RECORD_MUTATION = """
mutation RecordRepositoryRewrite(
    $repository_id: String!,
    $previous_commit: String!,
    $commit: String!,
    $rewritten_at: String!,
    $rewrite_count: BigInt!,
) {
    CoreGenericRepositoryUpdate(
        data: {
            id: $repository_id,
            last_rewrite_previous_commit: { value: $previous_commit },
            last_rewrite_commit: { value: $commit },
            last_rewrite_at: { value: $rewritten_at },
            rewrite_count: { value: $rewrite_count },
        }
    ) {
        ok
    }
}
"""


class SdkRepositoryRecordStore:
    """Holds the rewrite record on the repository node, through the Infrahub API."""

    def __init__(self, client: InfrahubClient) -> None:
        self.client = client

    async def get_rewrite_count(self, repository_id: str, infrahub_branch_name: str) -> int | None:
        """Return the rewrite count the repository reads on the branch, None when it reads none.

        Raises:
            RepositoryError: When the API cannot answer, or holds no such repository on the branch.

        """
        response = await self._execute(
            repository_id=repository_id,
            infrahub_branch_name=infrahub_branch_name,
            query=REWRITE_COUNT_QUERY,
            variables={"repository_id": repository_id},
            tracker="query-repository-rewrite-count",
        )
        edges = response["CoreGenericRepository"]["edges"]
        if not edges:
            raise RepositoryError(
                identifier=repository_id,
                message=f"Infrahub holds no repository {repository_id} on branch {infrahub_branch_name}",
            )
        count = edges[0]["node"]["rewrite_count"]["value"]
        return None if count is None else int(count)

    async def write_record(self, repository_id: str, infrahub_branch_name: str, record: RewriteRecord) -> None:
        """Write the four values of the record on the branch, in one mutation.

        Raises:
            RepositoryError: When the API rejects the write or cannot be reached.

        """
        await self._execute(
            repository_id=repository_id,
            infrahub_branch_name=infrahub_branch_name,
            query=REWRITE_RECORD_MUTATION,
            variables={
                "repository_id": repository_id,
                "previous_commit": record.previous_commit,
                "commit": record.commit,
                "rewritten_at": record.rewritten_at.isoformat(),
                "rewrite_count": record.rewrite_count,
            },
            tracker="mutation-repository-rewrite-record",
        )

    async def _execute(
        self,
        repository_id: str,
        infrahub_branch_name: str,
        query: str,
        variables: dict[str, Any],
        tracker: str,
    ) -> dict[str, Any]:
        try:
            return await self.client.execute_graphql(
                query=query, variables=variables, branch_name=infrahub_branch_name, tracker=tracker
            )
        except SdkError as exc:
            raise RepositoryError(
                identifier=repository_id,
                message=f"Unable to access the rewrite record of repository {repository_id} on branch "
                f"{infrahub_branch_name}: {exc}",
            ) from exc
