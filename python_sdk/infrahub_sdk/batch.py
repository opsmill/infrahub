import asyncio
from dataclasses import dataclass
from typing import Any, AsyncGenerator, Awaitable, Callable, Dict, List, Optional, Tuple

from infrahub_sdk.node import InfrahubNode


@dataclass
class BatchTask:
    task: Callable[[Any], Awaitable[Any]]
    args: Tuple[Any, ...]
    kwargs: Dict[str, Any]
    identifier: Optional[str] = None
    node: Optional[InfrahubNode] = None


async def execute_batch_task_in_pool(
    task: BatchTask,
    semaphore: asyncio.Semaphore,
    return_exceptions: bool = False,
) -> Tuple[BatchTask, Any]:
    async with semaphore:
        try:
            result = await task.task(*task.args, **task.kwargs)
        except Exception as exc:  # pylint: disable=broad-exception-caught
            if return_exceptions:
                return (task, exc)
            raise exc

        return (task, result)


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
        self,
        *args: Any,
        identifier: Optional[str] = None,
        task: Callable[[Any], Awaitable[Any]],
        node: Optional[InfrahubNode] = None,
        **kwargs: Any,
    ) -> None:
        self._tasks.append(BatchTask(identifier=identifier, task=task, node=node, args=args, kwargs=kwargs))

    async def execute(self) -> AsyncGenerator:
        tasks = []

        for batch_task in self._tasks:
            tasks.append(
                asyncio.create_task(
                    execute_batch_task_in_pool(
                        task=batch_task, semaphore=self.semaphore, return_exceptions=self.return_exceptions
                    )
                )
            )

        for completed_task in asyncio.as_completed(tasks):
            batch_task, result = await completed_task
            if isinstance(result, Exception) and not self.return_exceptions:
                raise result
            yield batch_task, result
