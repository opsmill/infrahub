from typing import Optional, Tuple

from testcontainers.core.container import DockerContainer
from testcontainers.core.waiting_utils import wait_for_logs

from infrahub import config
from infrahub.core import registry
from infrahub.core.branch import Branch
from infrahub.core.initialization import create_default_branch, create_global_branch, create_root_node
from infrahub.core.schema.manager import SchemaManager
from infrahub.database import InfrahubDatabaseMode, QueryConfig, get_db
from infrahub.lock import initialize_lock
from tests.helpers.constants import PORT_BOLT_NEO4J
from tests.helpers.query_benchmark.db_query_profiler import InfrahubDatabaseProfiler


def get_exposed_port(container: DockerContainer, port: int) -> int:
    """
    Use this method instead of DockerContainer.get_exposed_port as it is decorated with wait_container_is_ready
    which we do not want to use as it does not perform a real healthcheck. DockerContainer.get_exposed_port
    also introduces extra "Waiting for container" logs as we might call it multiple times for containers exposing
    multiple ports such as rabbitmq.
    """

    return int(container.get_docker_client().port(container.get_wrapped_container().id, port))


def start_neo4j_container(neo4j_image: str) -> DockerContainer:
    container = (
        DockerContainer(image=neo4j_image)
        .with_env("NEO4J_AUTH", "neo4j/admin")
        .with_env("NEO4J_ACCEPT_LICENSE_AGREEMENT", "yes")
        .with_env("NEO4J_dbms_security_procedures_unrestricted", "apoc.*")
        .with_env("NEO4J_dbms_security_auth__minimum__password__length", "4")
        .with_exposed_ports(PORT_BOLT_NEO4J)
    )

    container.start()
    wait_for_logs(container, "Started.")  # wait_container_is_ready does not seem to be enough
    return container


async def start_db_and_create_default_branch(
    neo4j_image: str, queries_names_to_config: Optional[dict[str, QueryConfig]] = None
) -> Tuple[InfrahubDatabaseProfiler, Branch]:
    neo4j_container = start_neo4j_container(neo4j_image)
    config.SETTINGS.database.port = int(neo4j_container.get_exposed_port(PORT_BOLT_NEO4J))
    db = InfrahubDatabaseProfiler(
        mode=InfrahubDatabaseMode.DRIVER, driver=await get_db(), queries_names_to_config=queries_names_to_config
    )
    initialize_lock()

    # Create default branch
    await create_root_node(db=db)
    default_branch = await create_default_branch(db=db)
    await create_global_branch(db=db)
    registry.schema = SchemaManager()

    return db, default_branch
