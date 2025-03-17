from __future__ import annotations

from typing import TYPE_CHECKING, Any

from typing_extensions import Self

from infrahub.core import registry
from infrahub.core.constants import Severity, TaskConclusion
from infrahub.log import get_logger

from .task import Task
from .task_log import TaskLog

if TYPE_CHECKING:
    from types import TracebackType

    from structlog.stdlib import BoundLogger

    from infrahub.core.protocols import CoreGenericAccount
    from infrahub.database import InfrahubDatabase
    from infrahub.graphql.initialization import GraphqlContext
    from infrahub.services.protocols import InfrahubLogger


class UserTask:
    def __init__(
        self,
        title: str,
        db: InfrahubDatabase,
        account: CoreGenericAccount | None = None,
        account_id: str | None = None,
        logger: BoundLogger | InfrahubLogger | None = None,
    ) -> None:
        if not account and not account_id:
            raise ValueError("Either account or account_id must be provided to initialize UserTask")

        self._account = account
        if account_id:
            self.account_id = account_id
        if not account_id and account:
            self.account_id = account.id

        self.title = title
        self._task: Task | None
        self.log: BoundLogger | InfrahubLogger = logger or get_logger()
        self.db = db

    @property
    def task(self) -> Task:
        if self._task:
            return self._task
        raise ValueError("Task hasn't been initialized")

    @property
    def account(self) -> CoreGenericAccount:
        if self._account:
            return self._account
        raise ValueError("Account hasn't been initialized")

    @property
    def task_id(self) -> str:
        if self.task.uuid:
            return str(self.task.uuid)
        raise ValueError("Task hasn't been initialized")

    async def fetch_account(self) -> bool:
        if self._account:
            return False

        account: CoreGenericAccount | None = await registry.manager.get_one(id=self.account_id, db=self.db)
        if not account:
            raise ValueError(f"Unable to find the account associated with {self.account_id}")
        self._account = account
        return True

    async def create_task(self) -> None:
        await self.fetch_account()
        self._task = Task(title=self.title, conclusion=TaskConclusion.UNKNOWN, related_node=self.account)
        await self._task.save(db=self.db)

    @classmethod
    def from_graphql_context(
        cls, title: str, graphql_context: GraphqlContext, logger: BoundLogger | InfrahubLogger | None = None
    ) -> Self:
        if not graphql_context.db or not graphql_context.account_session:
            raise ValueError("db and account_session must be provided to initialize a GraphQLTaskReport")

        if not logger and graphql_context.service and graphql_context.service.log:
            logger = graphql_context.service.log
        return cls(
            title=title, account_id=graphql_context.account_session.account_id, db=graphql_context.db, logger=logger
        )

    async def __aenter__(self) -> Self:
        await self.create_task()
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        if exc_type:
            await self.error(message=str(exc_value))
            self.task.conclusion = TaskConclusion.FAILURE
        else:
            self.task.conclusion = TaskConclusion.SUCCESS
        await self.task.save(db=self.db)

    async def add_log(
        self, message: str, severity: Severity = Severity.INFO, db: InfrahubDatabase | None = None
    ) -> None:
        tlog = TaskLog(message=message, severity=severity, task_id=self.task_id)
        await tlog.save(db=db or self.db)

    async def info(self, message: str, db: InfrahubDatabase | None = None, **kwargs: Any) -> None:
        if self.log:
            self.log.info(message, **kwargs)
        await self.add_log(message=message, severity=Severity.INFO, db=db)

    async def warning(self, message: str, db: InfrahubDatabase | None = None, **kwargs: Any) -> None:
        if self.log:
            self.log.warning(message, **kwargs)
        await self.add_log(message=message, severity=Severity.WARNING, db=db)

    async def error(self, message: str, db: InfrahubDatabase | None = None, **kwargs: Any) -> None:
        if self.log:
            self.log.error(message, **kwargs)
        await self.add_log(message=message, severity=Severity.ERROR, db=db)
