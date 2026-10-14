"""Start repository activity runs for tests that drive the git flows and the syncer."""

from __future__ import annotations

from contextlib import asynccontextmanager
from typing import TYPE_CHECKING

from infrahub.git.activity.factory import build_repository_activity
from infrahub.git.activity.models import RepositoryActivityOperation
from tests.adapters.cache import MemoryCache

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

    from infrahub.git.activity.recorder import ActivityRun
    from infrahub.services.adapters.cache import InfrahubCache


@asynccontextmanager
async def activity_run(
    repository_id: str = "repository",
    operation: RepositoryActivityOperation = RepositoryActivityOperation.SYNC,
    cache: InfrahubCache | None = None,
) -> AsyncIterator[ActivityRun]:
    """Track a run in the process-wide table, so a subflow given its id finds it."""
    async with build_repository_activity(cache=cache or MemoryCache()).track(
        repository_id=repository_id, operation=operation
    ) as run:
        yield run
