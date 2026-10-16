from neo4j.exceptions import Neo4jError
from prefect import task
from prefect.cache_policies import NONE

from infrahub.core import registry, utils
from infrahub.core.constants import InfrahubKind
from infrahub.core.graph.schema import GRAPH_SCHEMA
from infrahub.core.manager import NodeManager
from infrahub.core.query import QueryType
from infrahub.core.schema import NodeSchema
from infrahub.database import DatabaseType, InfrahubDatabase

from .models import TelemetryDatabaseData, TelemetryDatabaseServerData, TelemetryDatabaseSystemInfoData
from .queries import CountNodesByKindsQuery
from .utils import safe_metric

# The Neo4j setting for how many CPUs its parallel query engine uses; the default, 0, means all of them, so no cap.
DB_WORKER_LIMIT_SETTING = "server.cypher.parallel.worker_limit"
# The Neo4j settings that size its memory; left unset, Neo4j sizes it from the memory it can see.
DB_HEAP_MAX_SETTING = "server.memory.heap.max_size"
DB_PAGECACHE_SETTING = "server.memory.pagecache.size"


async def get_server_info(db: InfrahubDatabase) -> list[TelemetryDatabaseServerData]:
    data: list[TelemetryDatabaseServerData] = []

    try:
        results = await db.execute_query(query="SHOW SERVERS YIELD *", name="get_server_info", type=QueryType.READ)
    except Neo4jError:
        return []

    for result in results:
        data.append(
            TelemetryDatabaseServerData(
                name=result["name"],
                version=result["version"],
            )
        )

    return data


def _worker_limit_from_value(value: object) -> int | None:
    """Turn the raw setting value into a number of CPUs, or ``None`` when no cap is set.

    Only a positive whole number is a cap. ``0`` (the default), a missing value or
    anything that is not a positive number means no cap.
    """
    if not isinstance(value, (str, int)):
        return None
    try:
        limit = int(value)
    except ValueError:
        return None
    return limit if limit > 0 else None


async def _read_settings(db: InfrahubDatabase, setting_names: list[str], query_name: str) -> dict[str, object]:
    query = """
    SHOW SETTINGS YIELD name, value
    WHERE name IN $setting_names
    RETURN name, value
    """
    results = await db.execute_query(
        query=query,
        params={"setting_names": setting_names},
        name=query_name,
        type=QueryType.READ,
    )
    return {result["name"]: result["value"] for result in results}


async def get_processor_assigned(db: InfrahubDatabase) -> int | None:
    """Read how many CPUs the database's parallel query engine is set to use, or ``None`` when no cap is set."""
    settings = await _read_settings(db=db, setting_names=[DB_WORKER_LIMIT_SETTING], query_name="get_processor_assigned")
    return _worker_limit_from_value(settings.get(DB_WORKER_LIMIT_SETTING))


async def get_setting_text(db: InfrahubDatabase, setting_name: str) -> str | None:
    """Read a database setting's value as the database reports it, or ``None`` when it is unset."""
    settings = await _read_settings(db=db, setting_names=[setting_name], query_name="get_setting_text")
    value = settings.get(setting_name)
    return value if isinstance(value, str) else None


async def get_system_info(db: InfrahubDatabase) -> TelemetryDatabaseSystemInfoData:
    query = """
    CALL dbms.queryJmx("java.lang:type=OperatingSystem")
    YIELD attributes
    RETURN
        attributes.AvailableProcessors as processor_available,
        attributes.TotalMemorySize as memory_total,
        attributes.FreeMemorySize as memory_available
    """
    results = await db.execute_query(query=query, name="get_system_info", type=QueryType.READ)

    return TelemetryDatabaseSystemInfoData(
        memory_total=results[0]["memory_total"]["value"],
        memory_available=results[0]["memory_available"]["value"],
        processor_available=results[0]["processor_available"]["value"],
        processor_assigned=await safe_metric(get_processor_assigned(db=db)),
        memory_heap_max_size=await safe_metric(get_setting_text(db=db, setting_name=DB_HEAP_MAX_SETTING)),
        memory_pagecache_size=await safe_metric(get_setting_text(db=db, setting_name=DB_PAGECACHE_SETTING)),
    )


async def count_corenode(db: InfrahubDatabase) -> int:
    """Count managed (CoreNode) nodes on the default branch."""
    return await NodeManager.count(db=db, schema=InfrahubKind.NODE)


async def count_user_nodes(db: InfrahubDatabase) -> int:
    """Count concrete nodes in user-editable namespaces, excluding group-generic kinds."""
    default_branch = registry.get_branch_from_registry()
    schema_branch = db.schema.get_schema_branch(name=default_branch.name)
    user_namespaces = [namespace.name for namespace in schema_branch.get_namespaces() if namespace.user_editable]
    schemas = [
        node_schema
        for node_schema in schema_branch.get_schemas_for_namespaces(namespaces=user_namespaces)
        if isinstance(node_schema, NodeSchema) and InfrahubKind.GENERICGROUP not in node_schema.inherit_from
    ]
    if not schemas:
        return 0
    query = await CountNodesByKindsQuery.init(db=db, branch=default_branch, schemas=schemas)
    await query.execute(db=db)
    return sum(item.count for item in query.get_data())


@task(name="telemetry-gather-db", task_run_name="Gather Database Information", cache_policy=NONE)
async def gather_database_information(db: InfrahubDatabase) -> TelemetryDatabaseData:
    """Gather node/relationship counts and database server/system info."""
    async with db.start_session(read_only=True) as dbs:
        server_info = []
        system_info = None
        database_type = db.db_type.value

        if db.db_type == DatabaseType.NEO4J:
            server_info = await get_server_info(db=dbs)
            system_info = await get_system_info(db=dbs)

            # server_info is populated only on Neo4j Enterprise, so a non-empty result implies it.
            if len(server_info) == 0:
                database_type = f"{database_type}-community"
            else:
                database_type = f"{database_type}-enterprise"

        data = TelemetryDatabaseData(
            database_type=database_type,
            relationship_count={
                "total": await utils.count_relationships(db=dbs),
            },
            node_count={
                "total": await utils.count_nodes(db=dbs),
            },
            servers=server_info,
            system_info=system_info,
        )

        for name in GRAPH_SCHEMA["relationships"]:
            data.relationship_count[name] = await utils.count_relationships(db=dbs, label=name)

        for name in GRAPH_SCHEMA["nodes"]:
            data.node_count[name] = await utils.count_nodes(db=dbs, label=name)

        # corenode/user each degrade to None independently through the shared metric helper.
        data.node_count["corenode"] = await safe_metric(count_corenode(db=dbs))
        data.node_count["user"] = await safe_metric(count_user_nodes(db=dbs))

        return data
