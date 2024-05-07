import asyncio
from dataclasses import dataclass
from typing import Any, Awaitable, Callable, Dict, List, Optional, Tuple

from infrahub_sdk.batch import BatchTask, InfrahubBatch
from rich.progress import Progress

from infrahub.core.node import Node
from infrahub.database import InfrahubDatabase


@dataclass
class CallbackTask:
    name: str
    task: Callable[[Any], Awaitable[Any]]
    args: Tuple[Any, ...]
    kwargs: Dict[str, Any]


class DataGeneratorBatch(InfrahubBatch):
    def __init__(
        self,
        callbacks: Optional[List[CallbackTask]] = None,
        callback_frequency: int = 10,
        semaphore: Optional[asyncio.Semaphore] = None,
        max_concurrent_execution: int = 5,
        return_exceptions: bool = False,
    ):
        super().__init__(
            semaphore=semaphore, max_concurrent_execution=max_concurrent_execution, return_exceptions=return_exceptions
        )
        self.callbacks: List[CallbackTask] = callbacks or []
        self.callback_frequency = callback_frequency

    def add(self, *args: Any, **kwargs: Any) -> None:
        super().add(*args, **kwargs)

        if len(self._tasks) % self.callback_frequency == 0:
            for callback in self.callbacks:
                self._tasks.append(BatchTask(task=callback.task, args=callback.args, kwargs=callback.kwargs))


class DataGenerator:
    def __init__(self, db: InfrahubDatabase, concurrent_execution: int = 2, progress: Optional[Progress] = None):
        self.db = db
        self.concurrent_execution = concurrent_execution
        self.progress = progress
        self.callbacks: List[CallbackTask] = []

    def add_callback(self, *args: Any, callback_name: str, **kwargs: Any) -> None:
        self.callbacks.append(CallbackTask(name=callback_name, task=self.execute_db_task, args=args, kwargs=kwargs))

    async def execute_db_task(self, task: Callable[[Any], Awaitable[Any]], **kwargs: Any) -> Any:
        async with self.db.start_session() as dbs:
            return await task(db=dbs, **kwargs)

    async def save_obj(self, obj: Node) -> Node:
        async with self.db.start_session() as dbs:
            async with dbs.start_transaction() as dbt:
                await obj.save(db=dbt)

        return obj

    def create_batch(self) -> DataGeneratorBatch:
        return DataGeneratorBatch(
            max_concurrent_execution=self.concurrent_execution, return_exceptions=True, callbacks=self.callbacks
        )
