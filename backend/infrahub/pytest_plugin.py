from pathlib import Path
from typing import Optional, Union

from infrahub_sdk.client import InfrahubClient
from infrahub_sdk.pytest_plugin.loader import InfrahubYamlFile
from infrahub_sdk.pytest_plugin.utils import load_repository_config
from pytest import Collector, Config, Item, Session

TEST_FILE_PREFIX = "test_"
TEST_FILE_SUFFIXES = [".yml", ".yaml"]


class InfrahubBackendPlugin:
    def __init__(self, directory: str, client: InfrahubClient, *args, **kwargs):
        self.directory = Path(directory)
        self.client = client

    def pytest_configure(self, config: Config) -> None:
        config.addinivalue_line("markers", "infrahub_check(name: str): Test related to a Check for Infrahub")
        config.addinivalue_line(
            "markers", "infrahub_graphql_query(name: str): Test related to a GraphQL query for Infrahub"
        )
        config.addinivalue_line(
            "markers", "infrahub_jinja2_transform(name: str): Test related to a Jinja2 Transform for Infrahub"
        )
        config.addinivalue_line(
            "markers", "infrahub_python_transform(name: str): Test related to a Python Transform for Infrahub"
        )
        config.addinivalue_line(
            "markers", "infrahub_unit: Unit test for Infrahub, should work without any dependencies"
        )
        config.addinivalue_line(
            "markers", "infrahub_integraton: Integation test with Infrahub, must be run against an instance"
        )

    def pytest_sessionstart(self, session: Session) -> None:
        session.infrahub_config_path = self.directory / ".infrahub.yml"  # type: ignore[attr-defined]
        print(f"*** Using Infrahub configuration {session.infrahub_config_path}")

        if session.infrahub_config_path.is_file():  # type: ignore[attr-defined]
            session.infrahub_repo_config = load_repository_config(repo_config_file=session.infrahub_config_path)  # type: ignore[attr-defined]
        else:
            print(f"*** {session.infrahub_config_path} is not a file")

    def pytest_sessionfinish(self, session: Session):
        print("*** test run reporting finishing")
        # TODO: store a relevant value in the database

    def pytest_collect_file(self, parent: Union[Collector, Item], file_path: Path) -> Optional[InfrahubYamlFile]:
        if file_path.suffix in TEST_FILE_SUFFIXES and file_path.name.startswith(TEST_FILE_PREFIX):
            return InfrahubYamlFile.from_parent(parent, path=file_path)
        return None
