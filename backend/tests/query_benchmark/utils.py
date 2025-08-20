from infrahub import config
from infrahub.core import registry
from infrahub.core.branch import Branch
from infrahub.core.initialization import add_indexes, create_default_branch, create_global_branch, create_root_node
from infrahub.core.schema.manager import SchemaManager
from infrahub.database import InfrahubDatabaseMode, QueryConfig, get_db
from tests.helpers.constants import PORT_BOLT_NEO4J
from tests.helpers.query_benchmark.db_query_profiler import InfrahubDatabaseProfiler
from tests.helpers.utils import start_neo4j_container


async def start_db_and_create_default_branch(
    neo4j_image: str, load_indexes: bool, queries_names_to_config: dict[str, QueryConfig] | None = None
) -> tuple[InfrahubDatabaseProfiler, Branch]:
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
        await add_indexes(db=db)

    return db, default_branch
