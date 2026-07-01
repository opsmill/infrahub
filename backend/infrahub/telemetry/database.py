import logging

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

log = logging.getLogger(__name__)


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


@task(name="telemetry-gather-db", task_run_name="Gather Database Information", cache_policy=NONE)
async def gather_database_information(db: InfrahubDatabase) -> TelemetryDatabaseData:
    """Gather database node and relationship counts for the telemetry payload.

    ``node_count`` carries three semantically distinct, strictly nesting node metrics —
    ``user`` ⊆ ``corenode`` ⊆ ``total`` — defined at the namespace level so they can never
    collapse into synonyms:

    - ``total`` — raw vertex count of the whole graph, including attributes, values, and
      internal bookkeeping nodes across all branches and history.
    - ``corenode`` — all managed nodes (the ``CoreNode`` generic), spanning the ``Core``,
      ``Builtin``, and user-defined namespaces. The ``Core`` management namespace is always
      non-empty, so ``corenode`` always exceeds the customer-facing subset. Counted through
      the branch/temporal-correct count path on the default branch, not a raw label tally.
    - ``user`` — the customer-facing subset: concrete nodes living in user-defined (non-restricted)
      namespaces, so it excludes the ``Core`` management namespace, the pipeline validators and
      checks, and by default ``Builtin`` kinds. Generics, profiles, and templates are not counted,
      and group-generic kinds are skipped so that ``user`` stays a subset of ``corenode`` (groups
      do not carry the ``CoreNode`` label). Counted through the same branch/temporal-correct count
      path on the default branch.

    ``corenode`` and ``user`` are each isolated: if either source raises, only that one key is set
    to ``None`` while ``total`` and the per-graph-label keys are still populated and the payload
    still ships.
    """
    async with db.start_session(read_only=True) as dbs:
        server_info = []
        system_info = None
        database_type = db.db_type.value

        if db.db_type == DatabaseType.NEO4J:
            server_info = await get_server_info(db=dbs)
            system_info = await get_system_info(db=dbs)

            # server_info is only available on Neo4j Enterprise
            #  so if it's not empty, we can assume the database is of type Enterprise
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

        # Managed-node count via the branch/temporal-correct count path on the default branch.
        # Isolated in its own try/except so a failure nulls only this key, leaving the raw
        # "total" and the per-graph-label counts intact.
        try:
            data.node_count["corenode"] = await NodeManager.count(
                db=dbs,
                schema=InfrahubKind.NODE,
                branch=registry.get_branch_from_registry(),
            )
        except Exception as exc:
            log.warning("Telemetry metric collection failed; reporting null for this field: %s", exc)
            data.node_count["corenode"] = None

        # Customer-facing node count: concrete nodes in user-defined (non-restricted) namespaces,
        # counted branch/temporal-correctly on the default branch. Group-generic kinds are skipped
        # because groups do not carry the CoreNode label, keeping user a subset of corenode.
        # Isolated in its own try/except so a failure nulls only this key.
        try:
            default_branch = registry.get_branch_from_registry()
            schema_branch = registry.schema.get_schema_branch(name=default_branch.name)
            user_namespaces = [
                namespace.name for namespace in schema_branch.get_namespaces() if namespace.user_editable
            ]
            user_total = 0
            for node_schema in schema_branch.get_schemas_for_namespaces(namespaces=user_namespaces):
                if isinstance(node_schema, NodeSchema) and InfrahubKind.GENERICGROUP not in node_schema.inherit_from:
                    user_total += await NodeManager.count(db=dbs, schema=node_schema.kind, branch=default_branch)
            data.node_count["user"] = user_total
        except Exception as exc:
            log.warning("Telemetry metric collection failed; reporting null for this field: %s", exc)
            data.node_count["user"] = None

        return data
