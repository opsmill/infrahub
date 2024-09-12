from __future__ import annotations

from typing import TYPE_CHECKING

from infrahub_sdk_internal.task_report import TaskReport

from infrahub.core.constants import RepositoryOperationalStatus

if TYPE_CHECKING:
    from infrahub.exceptions import RepositoryError


class GitReport(TaskReport):
    async def set_status(self, previous_status: str, error: RepositoryError | None = None) -> None:
        """Sets the operational status for the repository."""
        if error:
            status = RepositoryOperationalStatus.ERROR
        else:
            status = RepositoryOperationalStatus.ONLINE

        if previous_status != status.value:
            # Avoid setting status each time as it happens every 10 seconds by default. Instead we update the status if
            # the status value has changed
            await self.client.execute_graphql(
                query=UPDATE_STATUS,
                variables={"repo_id": self.related_node, "status": status.value},
                tracker="mutation-repository-update-operational-status",
            )
            if error:
                await self.error(str(error))
            else:
                await self.info("Successfully connected to repository.")


UPDATE_STATUS = """
mutation UpdateRepositoryStatus(
    $repo_id: String!,
    $status: String!,
    ) {
    CoreGenericRepositoryUpdate(
        data: {
            id: $repo_id,
            operational_status: { value: $status },
        }
    ) {
        ok
    }
}
"""
