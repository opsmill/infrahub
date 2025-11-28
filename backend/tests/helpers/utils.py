import time
from pathlib import Path

import httpx
import pytest
from testcontainers.core.container import DockerContainer
from testcontainers.core.waiting_utils import wait_for_logs

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

    prefect_base = Path(Path(__file__).parent.resolve() / "./../../infrahub/prefect_server")
    container = (
        DockerContainer(image="prefecthq/prefect:3.5.0-python3.13")
        .with_command("uvicorn --host 0.0.0.0 --port 4200 --factory prefect_server.app:create_infrahub_prefect")
        .with_exposed_ports(PORT_PREFECT)
        .with_volume_mapping(host=str(prefect_base), container="/opt/prefect/prefect_server", mode="ro")
        .with_env(key="PREFECT_SERVER_SERVICES_EVENT_PERSISTER_FLUSH_INTERVAL", value="1")
    )

    def cleanup() -> None:
        container.stop()

    container.start()

    mapped_port = get_exposed_port(container, PORT_PREFECT)
    # As our entrypoint doesn't print out any logs on startup we can't "wait for logs"
    wait_for_prefect(port=mapped_port)
    request.addfinalizer(cleanup)

    return {PORT_PREFECT: mapped_port}


url = "http://localhost:52879/api/admin/version"  # Replace with your target URL


def wait_for_prefect(port: int) -> None:
    for _ in range(120):
        try:
            response = httpx.get(f"http://localhost:{port}/api/admin/version", timeout=1)
            if response.status_code == 200:
                return
        except httpx.HTTPError:
            time.sleep(1)

    pytest.fail(reason="Prefect didn't start in an orderly fashion")
