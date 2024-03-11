from __future__ import annotations

from typing import TYPE_CHECKING, Any, Optional, Type

from typing_extensions import Self

from infrahub.core import registry
from infrahub.core.constants import Severity
from infrahub.core.task import Task, TaskConclusion
from infrahub.core.task_log import TaskLog
from infrahub.log import get_logger

if TYPE_CHECKING:
    from types import TracebackType

    from structlog.stdlib import BoundLogger

    from infrahub.core.node import Node
    from infrahub.database import InfrahubDatabase

    from . import GraphqlContext


class GraphQLTaskReport:
    def __init__(self, title: str, db: InfrahubDatabase, account: Node, logger: Optional[BoundLogger] = None) -> None:
        self.account = account
        self.db = db
        self.task = Task(title=title, conclusion=TaskConclusion.UNKNOWN, related_node=account)
        self.log: BoundLogger = logger or get_logger()

    @property
    def task_id(self) -> str:
        if self.task and self.task.uuid:
            return str(self.task.uuid)
        raise ValueError("Task hasn't been initialized")

    @classmethod
    async def init(cls, title: str, context: GraphqlContext, logger: Optional[BoundLogger] = None) -> Self:
        if not context.db or not context.account_session:
            raise ValueError("db and account_session must be provided to initialize a GraphQLTaskReport")
        account = await registry.manager.get_one(id=context.account_session.account_id, db=context.db)
        if not account:
            raise ValueError(f"Unable to find the account associated with {context.account_session.account_id}")

        return cls(title=title, account=account, db=context.db, logger=logger)

    async def __aenter__(self) -> Self:
        await self.task.save(db=self.db)
        return self

    async def __aexit__(
        self,
        exc_type: Optional[Type[BaseException]],
        exc_value: Optional[BaseException],
        traceback: Optional[TracebackType],
    ) -> None:
        if exc_type is None:
            self.task.conclusion = TaskConclusion.SUCCESS
        else:
            self.task.conclusion = TaskConclusion.FAILURE
        await self.task.save(db=self.db)

    async def add_log(self, message: str, severity: Severity = Severity.INFO) -> None:
        tlog = TaskLog(message=message, severity=severity, task_id=self.task_id)
        await tlog.save(db=self.db)

    async def info(self, message: str, *args: Any, **kwargs: Any) -> None:
        self.log.info(message, *args, **kwargs)
        await self.add_log(message=message, severity=Severity.INFO)

    async def warning(self, message: str, *args: Any, **kwargs: Any) -> None:
        self.log.warning(message, *args, **kwargs)
        await self.add_log(message=message, severity=Severity.WARNING)

    async def error(self, message: str, *args: Any, **kwargs: Any) -> None:
        self.log.error(message, *args, **kwargs)
        await self.add_log(message=message, severity=Severity.ERROR)
