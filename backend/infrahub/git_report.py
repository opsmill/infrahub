from __future__ import annotations

from typing import Optional

from infrahub_sdk.task_report import TaskLogs, TaskReport

from infrahub.core.constants import RepositoryStatus


class GitReport(TaskReport):
    async def create(
        self, title: Optional[str] = None, conclusion: str = "UNKNOWN", logs: Optional[TaskLogs] = None
    ) -> None:
        await super().create(title=title, conclusion=conclusion, logs=logs)

        await self.client.execute_graphql(
            query=UPDATE_STATUS, variables={"repo_id": self.related_node, "status": RepositoryStatus.SYNCING.value}
        )

    async def update(
        self, title: Optional[str] = None, conclusion: Optional[str] = None, logs: Optional[TaskLogs] = None
    ) -> None:
        await super().update(title=title, conclusion=conclusion, logs=logs)
        status = RepositoryStatus.ERROR if self.has_failures else RepositoryStatus.INSYNC
        await self.client.execute_graphql(
            query=UPDATE_STATUS, variables={"repo_id": self.related_node, "status": status.value}
        )


UPDATE_STATUS = """
mutation UpdateRepositoryStatus(
    $repo_id: UUID,
    $status: String!,
    ) {
    CoreGenericRepositoryUpdate(
        data: {
            id: $repo_id,
            status: { value: $status },
        }
    ) {
        ok
    }
}
"""
