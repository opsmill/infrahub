from infrahub.database import DatabaseType, InfrahubDatabase

PREPARE_FOR_REPLANNING_TIMEOUT_SECONDS = 60


async def refresh_planner_statistics(db: InfrahubDatabase) -> None:
    """Resample every index and drop the cached plans, so the next queries are planned against the current graph.

    A test empties the graph and fills it again faster than Neo4j resamples its indexes in the
    background, and a plan made from statistics that still describe the empty graph can scan a whole
    relationship index once per row of a large read.
    """
    if db.db_type != DatabaseType.NEO4J:
        return
    await db.execute_query(
        query="CALL db.prepareForReplanning($timeout_seconds)",
        params={"timeout_seconds": PREPARE_FOR_REPLANNING_TIMEOUT_SECONDS},
        name="refresh_planner_statistics",
    )
