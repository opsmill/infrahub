from __future__ import annotations

from typing import TYPE_CHECKING, Optional

from infrahub_sdk.task_report import TaskLogs, TaskReport

from infrahub.core.constants import RepositoryOperationalStatus

if TYPE_CHECKING:
    from infrahub.exceptions import RepositoryError


class GitReport(TaskReport):
    async def update(
        self, title: Optional[str] = None, conclusion: Optional[str] = None, logs: Optional[TaskLogs] = None
    ) -> None:
        await super().update(title=title, conclusion=conclusion, logs=logs)
        status = RepositoryOperationalStatus.ERROR if self.has_failures else RepositoryOperationalStatus.ONLINE
        await self.client.execute_graphql(
            query=UPDATE_STATUS, variables={"repo_id": self.related_node, "status": status.value}
        )

    async def set_status(self, previous_status: str, error: RepositoryError | None = None) -> None:
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
