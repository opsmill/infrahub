import asyncio
from dataclasses import dataclass
from typing import Any, Awaitable, Dict, Generator, List, Optional

from infrahub_client.node import InfrahubNode


@dataclass
class BatchTask:
    task: Awaitable
    args: Optional[List[Any]] = None
    kwargs: Optional[Dict[str, Any]] = None
    node: Optional[InfrahubNode] = None


async def execute_batch_task_in_pool(task: BatchTask, semaphore) -> tuple[InfrahubNode, Any]:
    async with semaphore:
        return task.node, await task.task(*task.args, **task.kwargs)


class InfrahubBatch:
    def __init__(self, semaphore: Optional[asyncio.Semaphore] = None, max_concurrent_execution: int = 5):
        self._tasks: List[BatchTask] = []
        self.semaphore: asyncio.Semaphore = semaphore

        if not self.semaphore:
            self.semaphore = asyncio.Semaphore(value=max_concurrent_execution)

    def add(self, *args, task: Awaitable, node: Optional[InfrahubNode] = None, **kwargs):
        self._tasks.append(BatchTask(task=task, node=node, args=args, kwargs=kwargs))

    async def execute(self) -> Generator[None, None, tuple[Optional[InfrahubNode], Any]]:
        results: List[tuple[InfrahubNode, Any]] = []
        tasks = []

        for batch_task in self._tasks:
            tasks.append(asyncio.create_task(execute_batch_task_in_pool(task=batch_task, semaphore=self.semaphore)))

        for completed_task in asyncio.as_completed(tasks):
            yield await completed_task
