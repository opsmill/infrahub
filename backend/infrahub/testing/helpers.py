from pathlib import Path

import pytest
from infrahub_sdk import Config, InfrahubClient, InfrahubClientSync
from prefect.client.orchestration import PrefectClient

from .container import InfrahubDockerCompose


class TestInfrahub:
    @pytest.fixture(scope="class")
    def tmp_directory(self, tmpdir_factory: pytest.TempdirFactory) -> Path:
        directory = Path(str(tmpdir_factory.getbasetemp().strpath))
        return directory

    @pytest.fixture(scope="class")
    def default_branch(self) -> str:
        return "main"

    @pytest.fixture(scope="class")
    def infrahub_compose(self, tmp_directory: Path) -> InfrahubDockerCompose:
        return InfrahubDockerCompose.init(directory=tmp_directory)

    @pytest.fixture(scope="class")
    def infrahub_app(self, request: pytest.FixtureRequest, infrahub_compose: InfrahubDockerCompose) -> dict[str, int]:
        def cleanup() -> None:
            infrahub_compose.stop()

        infrahub_compose.start()
        request.addfinalizer(cleanup)

        return infrahub_compose.get_services_port()

    @pytest.fixture(scope="class")
    def infrahub_port(self, infrahub_app: dict[str, int]) -> int:
        return infrahub_app["server"]

    @pytest.fixture(scope="class")
    def infrahub_client(self, infrahub_port: int) -> InfrahubClient:
        return InfrahubClient(config=Config(address=f"http://localhost:{infrahub_port}"))

    @pytest.fixture(scope="class")
    def infrahub_client_sync(self, infrahub_port: int) -> InfrahubClientSync:
        return InfrahubClientSync(config=Config(address=f"http://localhost:{infrahub_port}"))

    @pytest.fixture(scope="class")
    def task_manager_port(self, infrahub_app: dict[str, int]) -> int:
        return infrahub_app["task-manager"]

    @pytest.fixture(scope="class")
    def prefect_client(self, task_manager_port: int) -> PrefectClient:
        prefect_server = f"http://localhost:{task_manager_port}/api"
        return PrefectClient(api=prefect_server)


class TestInfrahubDev(TestInfrahub):
    @pytest.fixture(scope="class")
    def infrahub_compose(self, tmp_directory: Path) -> InfrahubDockerCompose:
        return InfrahubDockerCompose.init(directory=tmp_directory, version="local")
