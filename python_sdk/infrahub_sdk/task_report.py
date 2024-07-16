from __future__ import annotations

from typing import TYPE_CHECKING, Any, Final, Optional, Protocol, TypedDict, Union, runtime_checkable

from typing_extensions import Self

from infrahub_sdk.uuidt import generate_uuid

if TYPE_CHECKING:
    from types import TracebackType

    from infrahub_sdk.client import InfrahubClient


class Log(TypedDict):
    message: str
    severity: str


TaskLogs = Union[list[Log], Log]


class TaskReport:
    def __init__(
        self,
        client: InfrahubClient,
        logger: InfrahubLogger,
        related_node: str,
        title: str,
        task_id: Optional[str] = None,
        created_by: Optional[str] = None,
        create_with_context: bool = True,
    ):
        self.client = client
        self.title = title
        self.task_id: Final = task_id or generate_uuid()
        self.related_node: Final = related_node
        self.created_by: Final = created_by
        self.has_failures: bool = False
        self.finalized: bool = False
        self.created: bool = False
        self.create_with_context = create_with_context
        self.log = logger

    async def __aenter__(self) -> Self:
        if self.create_with_context:
            await self.create()
        return self

    async def __aexit__(
        self,
        exc_type: Optional[type[BaseException]],
        exc_value: Optional[BaseException],
        traceback: Optional[TracebackType],
    ) -> None:
        if exc_type:
            self.finalized = True
            await self.update(conclusion="FAILURE", logs={"message": str(exc_value), "severity": "ERROR"})

        if self.finalized or not self.created:
            return

        conclusion = "FAILURE" if self.has_failures else "SUCCESS"
        await self.update(conclusion=conclusion)

    async def create(
        self, title: Optional[str] = None, conclusion: str = "UNKNOWN", logs: Optional[TaskLogs] = None
    ) -> None:
        variables: dict[str, Any] = {
            "related_node": self.related_node,
            "task_id": self.task_id,
            "title": title or self.title,
            "conclusion": conclusion,
        }
        if self.created_by:
            variables["created_by"] = self.created_by
        if logs:
            variables["logs"] = logs

        await self.client.execute_graphql(
            query=CREATE_TASK,
            variables=variables,
        )
        self.created = True

    async def info(self, event: str, *args: Any, **kw: Any) -> None:
        self.log.info(event, *args, **kw)
        await self.update(logs={"severity": "INFO", "message": event})

    async def warning(self, event: str, *args: Any, **kw: Any) -> None:
        self.log.warning(event, *args, **kw)
        await self.update(logs={"severity": "WARNING", "message": event})

    async def error(self, event: str, *args: Any, **kw: Any) -> None:
        self.log.error(event, *args, **kw)
        self.has_failures = True
        await self.update(logs={"severity": "ERROR", "message": event})

    async def critical(self, event: str, *args: Any, **kw: Any) -> None:
        self.log.critical(event, *args, **kw)
        self.has_failures = True
        await self.update(logs={"severity": "CRITICAL", "message": event})

    async def exception(self, event: str, *args: Any, **kw: Any) -> None:
        self.log.critical(event, *args, **kw)
        self.has_failures = True
        await self.update(logs={"severity": "CRITICAL", "message": event})

    async def finalise(
        self, title: Optional[str] = None, conclusion: str = "SUCCESS", logs: Optional[TaskLogs] = None
    ) -> None:
        self.finalized = True
        await self.update(title=title, conclusion=conclusion, logs=logs)

    async def update(
        self, title: Optional[str] = None, conclusion: Optional[str] = None, logs: Optional[TaskLogs] = None
    ) -> None:
        if not self.created:
            await self.create()
        variables: dict[str, Any] = {"task_id": self.task_id}
        if conclusion:
            variables["conclusion"] = conclusion
        if title:
            variables["title"] = title
        if logs:
            variables["logs"] = logs
        await self.client.execute_graphql(query=UPDATE_TASK, variables=variables)


class InfrahubLogger(Protocol):
    def debug(self, event: Optional[str] = None, *args: Any, **kw: Any) -> Any:
        """Send a debug event"""

    def info(self, event: Optional[str] = None, *args: Any, **kw: Any) -> Any:
        """Send an info event"""

    def warning(self, event: Optional[str] = None, *args: Any, **kw: Any) -> Any:
        """Send a warning event"""

    def error(self, event: Optional[str] = None, *args: Any, **kw: Any) -> Any:
        """Send an error event."""

    def critical(self, event: Optional[str] = None, *args: Any, **kw: Any) -> Any:
        """Send a critical event."""

    def exception(self, event: Optional[str] = None, *args: Any, **kw: Any) -> Any:
        """Send an exception event."""


@runtime_checkable
class InfrahubTaskReportLogger(Protocol):
    async def info(self, event: Optional[str] = None, *args: Any, **kw: Any) -> Any:
        """Send an info event"""

    async def warning(self, event: Optional[str] = None, *args: Any, **kw: Any) -> Any:
        """Send a warning event"""

    async def error(self, event: Optional[str] = None, *args: Any, **kw: Any) -> Any:
        """Send an error event."""

    async def critical(self, event: Optional[str] = None, *args: Any, **kw: Any) -> Any:
        """Send a critical event."""

    async def exception(self, event: Optional[str] = None, *args: Any, **kw: Any) -> Any:
        """Send an exception event."""


CREATE_TASK = """
mutation CreateTask(
    $conclusion: TaskConclusion!,
    $title: String!,
    $task_id: UUID,
    $related_node: String!,
    $created_by: String,
    $logs: [RelatedTaskLogCreateInput]
    ) {
    InfrahubTaskCreate(
        data: {
            id: $task_id,
            title: $title,
            related_node: $related_node,
            conclusion: $conclusion,
            created_by: $created_by,
            logs: $logs
        }
    ) {
        ok
    }
}
"""

UPDATE_TASK = """
mutation UpdateTask(
    $conclusion: TaskConclusion,
    $title: String,
    $task_id: UUID!,
    $logs: [RelatedTaskLogCreateInput]
    ) {
    InfrahubTaskUpdate(
        data: {
            id: $task_id,
            title: $title,
            conclusion: $conclusion,
            logs: $logs
        }
    ) {
        ok
    }
}
"""
