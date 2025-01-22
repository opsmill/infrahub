import os
import subprocess  # noqa: S404
from pathlib import Path
from typing import Optional

import pytest
from packaging.version import InvalidVersion, Version

from .container import ENV_VAR_DEFAULT_VALUES, InfrahubDockerCompose

DEFAULT_INFRAHUB_SERVER_VERSION = "latest"


class TestInfrahubDocker:
    @staticmethod
    def infrahub_version() -> str:
        """Required (for now) to define the version of infrahub to use.
        This fixture is meant to be overriden by subclasses."""

        # Note that when this method is not overriden, it might also return an image tag, like "local" or "latest".

        return os.getenv("INFRAHUB_TESTING_IMAGE_TAG", DEFAULT_INFRAHUB_SERVER_VERSION)

    def check_skip(self, min_infrahub_version: Optional[str], max_infrahub_version: Optional[str]) -> None:
        """
        Check if a test should be skipped depending on infrahub version. This method is meant to be called
        at the start of any test that should be skipped depending on infrahub version.
        """

        # Ideally, we would use `skipIf` or a fixture instead of calling a method to skip a test. The fact
        # we support both `infrahub_version` as a convenient way to declare version and `INFRAHUB_TESTING_IMAGE_TAG`
        # for internal development purposes (CI) makes it trickier to do.

        infrahub_version = self.infrahub_version()

        try:
            version = Version(infrahub_version)
        except InvalidVersion:
            # We would typically end up here for development purpose while running a CI test against
            # unreleased versions of infrahub, like `stable` or `develop` branch.
            # For now, we consider this means we are testing against the most recent version of infrahub,
            # so we skip if the test should not be ran against a maximum version.
            if max_infrahub_version is None:
                pytest.skip(
                    f"A local version is used ({infrahub_version}) while a maximum version is specified ({max_infrahub_version}"
                )
            return

        if min_infrahub_version is not None and version <= Version(min_infrahub_version):
            pytest.skip(f"Infrahub version should be higher than {min_infrahub_version}, found {infrahub_version}")

        if max_infrahub_version is not None and version <= Version(max_infrahub_version):
            pytest.skip(f"Infrahub version should be less than {max_infrahub_version}, found {infrahub_version}")

    def execute_ctl_run(self, address: str, script: str) -> str:
        env = os.environ.copy()
        env["INFRAHUB_ADDRESS"] = address
        env["INFRAHUB_API_TOKEN"] = ENV_VAR_DEFAULT_VALUES["INFRAHUB_TESTING_INITIAL_ADMIN_TOKEN"]
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
        directory = tmp_directory / ENV_VAR_DEFAULT_VALUES["INFRAHUB_TESTING_LOCAL_REMOTE_GIT_DIRECTORY"]
        directory.mkdir(exist_ok=True)

        return directory

    @pytest.fixture(scope="class")
    def default_branch(self) -> str:
        return "main"

    @pytest.fixture(scope="class")
    def infrahub_compose(self, tmp_directory: Path) -> InfrahubDockerCompose:
        return InfrahubDockerCompose.init(directory=tmp_directory, image_tag=self.infrahub_version())

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
