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
from .utils import safe_metric


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
    )


async def count_corenode(db: InfrahubDatabase) -> int:
    """Count managed nodes visible on the default branch at gather time.

    Uses the branch-safe count path so the total matches what the product reports for the
    default branch, rather than a raw vertex/label tally.
    """
    return await NodeManager.count(db=db, schema=InfrahubKind.NODE, branch=registry.get_branch_from_registry())


async def count_user_nodes(db: InfrahubDatabase) -> int:
    """Count concrete nodes in user-editable namespaces.

    Group-generic kinds are excluded because they do not carry the ``CoreNode`` label, which
    would otherwise let ``user`` exceed ``corenode``.
    """
    default_branch = registry.get_branch_from_registry()
    schema_branch = db.schema.get_schema_branch(name=default_branch.name)
    user_namespaces = [namespace.name for namespace in schema_branch.get_namespaces() if namespace.user_editable]
    total = 0
    for node_schema in schema_branch.get_schemas_for_namespaces(namespaces=user_namespaces):
        if isinstance(node_schema, NodeSchema) and InfrahubKind.GENERICGROUP not in node_schema.inherit_from:
            total += await NodeManager.count(db=db, schema=node_schema.kind, branch=default_branch)
    return total


@task(name="telemetry-gather-db", task_run_name="Gather Database Information", cache_policy=NONE)
async def gather_database_information(db: InfrahubDatabase) -> TelemetryDatabaseData:
    """Gather node/relationship counts and database server/system info.

    ``node_count`` holds three strictly nesting metrics, ``user`` ⊆ ``corenode`` ⊆ ``total``;
    ``corenode`` and ``user`` degrade to ``None`` independently, leaving ``total`` and the
    per-graph-label counts intact.
    """
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
