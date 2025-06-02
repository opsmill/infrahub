import os
import subprocess  # noqa: S404
import uuid
import warnings
from pathlib import Path

import pytest
from prefect.client.orchestration import PrefectClient

from infrahub_testcontainers import __version__ as infrahub_version

from .container import PROJECT_ENV_VARIABLES, InfrahubDockerCompose


class TestInfrahubDocker:
    @pytest.fixture(scope="class")
    def infrahub_version(self) -> str:
        return os.getenv("INFRAHUB_TESTING_IMAGE_VER") or infrahub_version

    @staticmethod
    def execute_ctl_run(address: str, script: str) -> str:
        env = os.environ.copy()
        env["INFRAHUB_ADDRESS"] = address
        env["INFRAHUB_API_TOKEN"] = PROJECT_ENV_VARIABLES["INFRAHUB_TESTING_INITIAL_ADMIN_TOKEN"]
        env["INFRAHUB_MAX_CONCURRENT_EXECUTION"] = "1"
        result = subprocess.run(  # noqa: S602
            f"infrahubctl run {script}", shell=True, capture_output=True, text=True, env=env, check=False
        )
        return result.stdout

    @staticmethod
    def execute_command(command: str, address: str, concurrent_execution: int = 10) -> subprocess.CompletedProcess[str]:
        env = os.environ.copy()
        env["INFRAHUB_ADDRESS"] = address
        env["INFRAHUB_API_TOKEN"] = PROJECT_ENV_VARIABLES["INFRAHUB_TESTING_INITIAL_ADMIN_TOKEN"]
        env["INFRAHUB_MAX_CONCURRENT_EXECUTION"] = f"{concurrent_execution}"
        result = subprocess.run(  # noqa: S602
            command, shell=True, capture_output=True, text=True, env=env, check=False
        )
        return result

    @pytest.fixture(scope="class")
    def tmp_directory(self, tmpdir_factory: pytest.TempdirFactory) -> Path:
        name = f"{self.__class__.__name__.lower()}_{uuid.uuid4().hex}"
        return Path(str(tmpdir_factory.mktemp(name)))

    @pytest.fixture(scope="class")
    def remote_repos_dir(self, tmp_directory: Path) -> Path:
        directory = tmp_directory / PROJECT_ENV_VARIABLES["INFRAHUB_TESTING_LOCAL_REMOTE_GIT_DIRECTORY"]
        directory.mkdir(exist_ok=True)

        return directory

    @pytest.fixture(scope="class")
    def remote_backups_dir(self, tmp_directory: Path) -> Path:
        directory = tmp_directory / PROJECT_ENV_VARIABLES["INFRAHUB_TESTING_LOCAL_DB_BACKUP_DIRECTORY"]
        directory.mkdir(exist_ok=True)

        return directory

    @pytest.fixture(scope="class")
    def default_branch(self) -> str:
        return "main"

    @pytest.fixture(scope="class")
    def deployment_type(self, request: pytest.FixtureRequest) -> str | None:
        return request.config.getoption(name="infrahub_deployment_type", default=None)

    @pytest.fixture(scope="class")
    def infrahub_compose(
        self,
        tmp_directory: Path,
        remote_repos_dir: Path,  # initialize repository before running docker compose to fix permissions issues # noqa: ARG002
        remote_backups_dir: Path,  # noqa: ARG002
        infrahub_version: str,
        deployment_type: str | None,
    ) -> InfrahubDockerCompose:
        return InfrahubDockerCompose.init(
            directory=tmp_directory, version=infrahub_version, deployment_type=deployment_type
        )

    @pytest.fixture(scope="class")
    def infrahub_app(self, request: pytest.FixtureRequest, infrahub_compose: InfrahubDockerCompose) -> dict[str, int]:
        tests_failed_before_class = request.session.testsfailed

        def cleanup() -> None:
            tests_failed_during_class = request.session.testsfailed - tests_failed_before_class
            if tests_failed_during_class > 0:
                stdout, stderr = infrahub_compose.get_logs("infrahub-server", "task-worker")
                warnings.warn(f"Container logs:\nStdout:\n{stdout}\nStderr:\n{stderr}", stacklevel=2)
            infrahub_compose.stop()

        request.addfinalizer(cleanup)

        try:
            infrahub_compose.start()
        except Exception as exc:
            stdout, stderr = infrahub_compose.get_logs()
            raise Exception(f"Failed to start docker compose:\nStdout:\n{stdout}\nStderr:\n{stderr}") from exc

        return infrahub_compose.get_services_port()

    @pytest.fixture(scope="class")
    def infrahub_port(self, infrahub_app: dict[str, int]) -> int:
        return infrahub_app["server"]

    @pytest.fixture(scope="class")
    def task_manager_port(self, infrahub_app: dict[str, int]) -> int:
        return infrahub_app["task-manager"]

    @pytest.fixture(scope="class")
    def prefect_client(self, task_manager_port: int) -> PrefectClient:
        return PrefectClient(api=f"http://localhost:{task_manager_port}/api/")
