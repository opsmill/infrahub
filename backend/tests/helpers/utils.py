from contextlib import contextmanager
from typing import Generator

import pytest
from testcontainers.core.container import DockerContainer
from testcontainers.core.waiting_utils import wait_for_logs

from infrahub.services import InfrahubServices, services
from tests.helpers.constants import INFRAHUB_USE_TEST_CONTAINERS, PORT_BOLT_NEO4J, PORT_HTTP_NEO4J, PORT_PREFECT


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


def start_prefect_server_container(
    request: pytest.FixtureRequest,
) -> dict[int, int] | None:
    if not INFRAHUB_USE_TEST_CONTAINERS:
        return None

    container = (
        DockerContainer(image="prefecthq/prefect:3.0.11-python3.12")
        .with_command("prefect server start --host 0.0.0.0 --ui")
        .with_exposed_ports(PORT_PREFECT)
    )

    def cleanup() -> None:
        container.stop()

    container.start()
    wait_for_logs(container, "Configure Prefect to communicate with the server")
    request.addfinalizer(cleanup)

    return {PORT_PREFECT: get_exposed_port(container, PORT_PREFECT)}


@contextmanager
def init_global_service(service: InfrahubServices) -> Generator:
    """
    `service` needs to be accessed through a global variable within prefect tasks, this utility
    helps for restoring original `service` values so tests do no have side effects.
    """

    original = services.service
    services.service = service
    try:
        yield service
    finally:
        services.service = original
