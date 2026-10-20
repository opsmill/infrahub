"""Build the repository activity recorder that the git flows use."""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from typing import TYPE_CHECKING

from infrahub.git.state.cache_keys import (
    ACTIVITY_LAST_RUN_TTL_SECONDS,
    ACTIVITY_RUN_RENEW_SECONDS,
    ACTIVITY_RUN_TTL_SECONDS,
)
from infrahub.worker import WORKER_IDENTITY

from .recorder import ActiveRuns, RepositoryActivity

if TYPE_CHECKING:
    from infrahub.services.adapters.cache import InfrahubCache

ACTIVE_RUNS = ActiveRuns()
"""One table per process, so every recorder built in it resolves the runs the others started."""


def _now() -> datetime:
    return datetime.now(tz=UTC)


def build_repository_activity(cache: InfrahubCache) -> RepositoryActivity:
    return RepositoryActivity(
        cache=cache,
        active_runs=ACTIVE_RUNS,
        worker_id=WORKER_IDENTITY,
        now=_now,
        sleep=asyncio.sleep,
        run_ttl_seconds=ACTIVITY_RUN_TTL_SECONDS,
        renew_interval_seconds=ACTIVITY_RUN_RENEW_SECONDS,
        last_run_ttl_seconds=ACTIVITY_LAST_RUN_TTL_SECONDS,
    )
