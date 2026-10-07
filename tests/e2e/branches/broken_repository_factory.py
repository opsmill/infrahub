from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from collections.abc import Awaitable


@dataclass(frozen=True)
class BrokenRepository:
    branch: str
    repository_name: str
    failed_task_id: str


class BrokenRepositoryFactory(Protocol):
    def __call__(self, *, sync_with_git: bool) -> Awaitable[BrokenRepository]: ...
