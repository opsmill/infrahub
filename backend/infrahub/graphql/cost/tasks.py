from __future__ import annotations

import time

from prefect import flow
from prefect.logging import get_run_logger

from infrahub import config
from infrahub.core.registry import registry
from infrahub.core.timestamp import Timestamp
from infrahub.graphql.cost.collector import StatisticsCollector
from infrahub.graphql.cost.statistics_store import StatisticsStore
from infrahub.workers.dependencies import get_cache, get_database


@flow(name="graphql-cost-statistics-refresh", flow_run_name="Refresh GraphQL query cost statistics")
async def refresh_query_cost_statistics() -> None:
    """Read the spread of peers of every relationship on the default branch and publish it as a new version."""
    log = get_run_logger()
    started = time.monotonic()
    at = Timestamp()

    default_branch = registry.get_branch_from_registry()
    schema_branch = registry.schema.get_schema_branch(name=default_branch.name)
    schema_hash = schema_branch.get_hash()
    database = await get_database()
    store = StatisticsStore(cache=await get_cache())

    async with database.start_session(read_only=True) as db:
        collector = StatisticsCollector(
            db=db,
            branch=default_branch,
            schema_branch=schema_branch,
            chunk_size=config.SETTINGS.database.query_size_limit,
        )
        collected = await collector.collect(at=at)

    pointer = await store.publish(
        kinds=collected.kinds, branch=default_branch.name, computed_at=at.to_datetime(), schema_hash=schema_hash
    )
    log.info(
        f"Published version {pointer.version} of the GraphQL query cost statistics in "
        f"{time.monotonic() - started:.1f} seconds: {len(collected.kinds)} kinds, "
        f"{collected.side_count} relationship sides, {collected.query_count} database queries"
    )
