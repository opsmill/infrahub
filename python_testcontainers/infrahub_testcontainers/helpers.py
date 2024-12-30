import os
import subprocess  # noqa: S404
from pathlib import Path

import pytest

from infrahub_testcontainers import __version__ as infrahub_version

from .container import PROJECT_ENV_VARIABLES, InfrahubDockerCompose


class TestInfrahubDocker:
    @pytest.fixture(scope="class")
    def infrahub_version(self) -> str:
        return infrahub_version

    def execute_ctl_run(self, address: str, script: str) -> str:
        env = os.environ.copy()
        env["INFRAHUB_ADDRESS"] = address
        env["INFRAHUB_API_TOKEN"] = PROJECT_ENV_VARIABLES["INFRAHUB_TESTING_INITIAL_ADMIN_TOKEN"]
        env["INFRAHUB_MAX_CONCURRENT_EXECUTION"] = "1"
        result = subprocess.run(  # noqa: S602
            f"infrahubctl run {script}", shell=True, capture_output=True, text=True, env=env, check=False
        )
        return result.stdout

    @pytest.fixture(scope="class")
    def tmp_directory(self, tmpdir_factory: pytest.TempdirFactory) -> Path:
        directory = Path(str(tmpdir_factory.getbasetemp().strpath))
        return directory

    @pytest.fixture(scope="class")
    def remote_repos_dir(self, tmp_directory: Path) -> Path:
        directory = tmp_directory / PROJECT_ENV_VARIABLES["INFRAHUB_TESTING_LOCAL_REMOTE_GIT_DIRECTORY"]
        directory.mkdir(exist_ok=True)

        return directory

    @pytest.fixture(scope="class")
    def default_branch(self) -> str:
        return "main"

    @pytest.fixture(scope="class")
    def infrahub_compose(self, tmp_directory: Path, infrahub_version: str) -> InfrahubDockerCompose:
        return InfrahubDockerCompose.init(directory=tmp_directory, version=infrahub_version)

    @pytest.fixture(scope="class")
    def infrahub_app(self, request: pytest.FixtureRequest, infrahub_compose: InfrahubDockerCompose) -> dict[str, int]:
        def cleanup() -> None:
            infrahub_compose.stop()

        request.addfinalizer(cleanup)

        infrahub_compose.start()

        return infrahub_compose.get_services_port()

    @pytest.fixture(scope="class")
    def infrahub_port(self, infrahub_app: dict[str, int]) -> int:
        return infrahub_app["server"]

    @pytest.fixture(scope="class")
    def task_manager_port(self, infrahub_app: dict[str, int]) -> int:
        return infrahub_app["task-manager"]
