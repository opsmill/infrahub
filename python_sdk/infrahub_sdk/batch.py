import asyncio
from dataclasses import dataclass
from typing import Any, AsyncGenerator, Awaitable, Callable, Dict, List, Optional, Tuple

from infrahub_sdk.node import InfrahubNode


@dataclass
class BatchTask:
    task: Callable[[Any], Awaitable[Any]]
    args: Tuple[Any, ...]
    kwargs: Dict[str, Any]
    node: Optional[InfrahubNode] = None


async def execute_batch_task_in_pool(
    task: BatchTask, semaphore: asyncio.Semaphore
) -> Tuple[Optional[InfrahubNode], Any]:
    async with semaphore:
        return (task.node, await task.task(*task.args, **task.kwargs))


class InfrahubBatch:
    def __init__(
        self,
        semaphore: Optional[asyncio.Semaphore] = None,
        max_concurrent_execution: int = 5,
        return_exceptions: bool = False,
    ):
        self._tasks: List[BatchTask] = []
        self.semaphore = semaphore or asyncio.Semaphore(value=max_concurrent_execution)
        self.return_exceptions = return_exceptions

    @property
    def num_tasks(self) -> int:
        return len(self._tasks)

    def add(
        self, *args: Any, task: Callable[[Any], Awaitable[Any]], node: Optional[InfrahubNode] = None, **kwargs: Any
    ) -> None:
        self._tasks.append(BatchTask(task=task, node=node, args=args, kwargs=kwargs))

    async def execute(self) -> AsyncGenerator:
        tasks = []

        for batch_task in self._tasks:
            tasks.append(asyncio.create_task(execute_batch_task_in_pool(task=batch_task, semaphore=self.semaphore)))

        for completed_task in asyncio.as_completed(tasks):
            try:
                yield await completed_task
            except Exception as exc:
                if self.return_exceptions:
                    yield exc
                else:
                    raise exc
