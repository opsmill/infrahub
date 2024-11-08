from typing import Optional, Tuple

from infrahub import config
from infrahub.core import registry
from infrahub.core.branch import Branch
from infrahub.core.graph.index import node_indexes, rel_indexes
from infrahub.core.initialization import create_default_branch, create_global_branch, create_root_node
from infrahub.core.schema.manager import SchemaManager
from infrahub.database import InfrahubDatabaseMode, QueryConfig, get_db
from tests.helpers.constants import PORT_BOLT_NEO4J
from tests.helpers.query_benchmark.db_query_profiler import InfrahubDatabaseProfiler
from tests.helpers.utils import start_neo4j_container


async def start_db_and_create_default_branch(
    neo4j_image: str, load_indexes: bool, queries_names_to_config: Optional[dict[str, QueryConfig]] = None
) -> Tuple[InfrahubDatabaseProfiler, Branch]:
    # Start database and create db profiler
    neo4j_container = start_neo4j_container(neo4j_image)
    config.SETTINGS.database.port = int(neo4j_container.get_exposed_port(PORT_BOLT_NEO4J))
    db = InfrahubDatabaseProfiler(
        mode=InfrahubDatabaseMode.DRIVER, driver=await get_db(), queries_names_to_config=queries_names_to_config
    )

    # Create default branch
    await create_root_node(db=db)
    default_branch = await create_default_branch(db=db)
    await create_global_branch(db=db)
    registry.schema = SchemaManager()

    # Initialize indexes if needed
    if load_indexes:
        db.manager.index.init(nodes=node_indexes, rels=rel_indexes)
        await db.manager.index.add()

    return db, default_branch
