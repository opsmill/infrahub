import os
import shutil
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
    def remote_backups_dir(self, tmp_directory: Path) -> Path:
        directory = tmp_directory / PROJECT_ENV_VARIABLES["INFRAHUB_TESTING_LOCAL_DB_BACKUP_DIRECTORY"]
        directory.mkdir(exist_ok=True)

        return directory

    @pytest.fixture(scope="class")
    def default_branch(self) -> str:
        return "main"

    @pytest.fixture(scope="class")
    def infrahub_compose(
        self,
        tmp_directory: Path,
        remote_repos_dir: Path,  # initialize repository before running docker compose to fix permissions issues # noqa: ARG002
        remote_backups_dir: Path,  # noqa: ARG002
        infrahub_version: str,
    ) -> InfrahubDockerCompose:
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

    def backup_database(self, request: pytest.FixtureRequest, dest_dir: Path | None = None) -> None:
        assert "enterprise" in os.environ.get("NEO4J_DOCKER_IMAGE", "")

        backup_dir: Path = request.getfixturevalue("remote_backups_dir")
        infrahub_compose: InfrahubDockerCompose = request.getfixturevalue("infrahub_compose")

        infrahub_compose.exec_in_container(
            command=[
                "neo4j-admin",
                "database",
                "backup",
                "--to-path",
                os.environ.get(
                    "INFRAHUB_TESTING_INTERNAL_DB_BACKUP_DIRECTORY",
                    PROJECT_ENV_VARIABLES["INFRAHUB_TESTING_INTERNAL_DB_BACKUP_DIRECTORY"],
                ),
            ],
            service_name="database",
        )

        if dest_dir:
            shutil.copytree(
                str(backup_dir),
                str(dest_dir),
            )

    def restore_database(self, request: pytest.FixtureRequest, backup_file: Path) -> None:
        assert "enterprise" in os.environ.get("NEO4J_DOCKER_IMAGE", "")

        backup_dir: Path = request.getfixturevalue("remote_backups_dir")
        infrahub_compose: InfrahubDockerCompose = request.getfixturevalue("infrahub_compose")

        shutil.copy(
            str(backup_file),
            str(backup_dir / backup_file.name),
        )

        infrahub_compose.exec_in_container(
            command=["cypher-shell", "-u", "neo4j", "-p", "admin", "STOP DATABASE neo4j;"],
            service_name="database",
        )

        infrahub_compose.exec_in_container(
            command=[
                "neo4j-admin",
                "database",
                "restore",
                "--overwrite-destination",
                "--from-path",
                str(
                    Path(
                        os.environ.get(
                            "INFRAHUB_TESTING_INTERNAL_DB_BACKUP_DIRECTORY",
                            PROJECT_ENV_VARIABLES["INFRAHUB_TESTING_INTERNAL_DB_BACKUP_DIRECTORY"],
                        )
                    )
                    / backup_file.name
                ),
            ],
            service_name="database",
        )

        infrahub_compose.exec_in_container(
            command=["cypher-shell", "-d", "system", "-u", "neo4j", "-p", "admin", "START DATABASE neo4j;"],
            service_name="database",
        )

        infrahub_compose.stop(down=False)
        infrahub_compose.start()
