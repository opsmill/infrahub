"""Start repository activity runs, and read back the records they leave, for tests that drive the git flows."""

from __future__ import annotations

import json
from contextlib import asynccontextmanager
from typing import TYPE_CHECKING, Any

from infrahub.git.activity.factory import build_repository_activity
from infrahub.git.activity.models import RepositoryActivityOperation
from tests.adapters.cache import MemoryCache

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

    from infrahub.git.activity.recorder import ActivityRun
    from infrahub.services.adapters.cache import InfrahubCache
    from tests.adapters.cache import RecordingCache


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


def _run_record_values(cache: RecordingCache, repository_id: str) -> list[dict[str, Any]]:
    prefix = f"git:activity:run:{repository_id}:"
    return [json.loads(call.value) for call in cache.set_calls if call.key.startswith(prefix)]


def run_record_writes(cache: RecordingCache, repository_id: str) -> list[tuple[str | None, str | None]]:
    """Return the phase and branch of every run record the cache was given for the repository, in order."""
    return [(record["phase"], record["branch_name"]) for record in _run_record_values(cache, repository_id)]


def run_record_operations(cache: RecordingCache, repository_id: str) -> set[str]:
    return {record["operation"] for record in _run_record_values(cache, repository_id)}


def stored_run_keys(cache: RecordingCache, repository_id: str) -> list[str]:
    return [key for key in cache.storage if key.startswith(f"git:activity:run:{repository_id}:")]


def last_run_branches(cache: RecordingCache, repository_id: str, operation: str) -> list[dict[str, str]]:
    """Return the branches of the last run of one operation, failing when no last run is stored."""
    return json.loads(cache.storage[f"git:activity:last:{repository_id}:{operation}"])["branches"]
