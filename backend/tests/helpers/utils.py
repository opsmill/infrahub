from testcontainers.core.container import DockerContainer
from testcontainers.core.waiting_utils import wait_for_logs

from tests.helpers.constants import PORT_BOLT_NEO4J, PORT_HTTP_NEO4J


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
        .with_exposed_ports(PORT_HTTP_NEO4J)
    )

    container.start()
    wait_for_logs(container, "Started.")  # wait_container_is_ready does not seem to be enough
    return container
