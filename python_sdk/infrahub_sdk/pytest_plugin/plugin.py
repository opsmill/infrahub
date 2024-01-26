from pathlib import Path
from typing import Optional, Union

from pytest import Collector, Config, Item, Parser, Session
from pytest import exit as exit_test

from infrahub_sdk import InfrahubClientSync
from infrahub_sdk.utils import is_valid_url

from .loader import InfrahubYamlFile
from .utils import load_repository_config


def pytest_addoption(parser: Parser) -> None:
    """Add options to control ansible."""
    group = parser.getgroup("pytest-infrahub")
    group.addoption(
        "--infrahub-repo-config",
        action="store",
        dest="infrahub_repo_config",
        default=".infrahub.yml",
        metavar="INFRAHUB_REPO_CONFIG_FILE",
        help="Infrahub configuration file for the repository (default: %(default)s)",
    )
    group.addoption(
        "--infrahub-address",
        action="store",
        dest="infrahub_address",
        default="http://localhost:8000",
        metavar="INFRAHUB_TESTS_ADDRESS",
        help="Address of the Infrahub instance for live testing (default: %(default)s)",
    )
    group.addoption(
        "--infrahub-key",
        action="store",
        dest="infrahub_key",
        metavar="INFRAHUB_TESTS_API_KEY",
        help="Key to use when querying the Infrahub instance for live testing",
    )
    group.addoption(
        "--infrahub-username",
        action="store",
        dest="infrahub_username",
        metavar="INFRAHUB_TESTS_USERNAME",
        help="Username to use when authenticating on the Infrahub instance for live testing",
    )
    group.addoption(
        "--infrahub-password",
        action="store",
        dest="infrahub_password",
        metavar="INFRAHUB_TESTS_PASSWORD",
        help="Password to use when authenticating on the Infrahub instance for live testing",
    )
    group.addoption(
        "--infrahub-branch",
        action="store",
        dest="infrahub_branch",
        default="main",
        metavar="INFRAHUB_TESTS_BRANCH",
        help="Branch to use when running integration tests with an Infrahub instance (default: %(default)s)",
    )


def pytest_sessionstart(session: Session) -> None:
    session.infrahub_config_path = Path(session.config.option.infrahub_repo_config)  # type: ignore[attr-defined]

    if session.infrahub_config_path.is_file():  # type: ignore[attr-defined]
        session.infrahub_repo_config = load_repository_config(repo_config_file=session.infrahub_config_path)  # type: ignore[attr-defined]

    if not is_valid_url(session.config.option.infrahub_address):
        exit_test("Infrahub test instance address is not a valid URL", returncode=1)

    client_config = None
    if hasattr(session.config.option, "infrahub_key"):
        client_config = {"api_token": session.config.option.infrahub_key}
    elif hasattr(session.config.option, "infrahub_username") and hasattr(session.config.option, "infrahub_password"):
        client_config = {
            "username": session.config.option.infrahub_username,
            "password": session.config.option.infrahub_password,
        }

    infrahub_client = InfrahubClientSync(address=session.config.option.infrahub_address, config=client_config)
    infrahub_client.login()
    session.infrahub_client = infrahub_client  # type: ignore[attr-defined]


def pytest_collect_file(parent: Union[Collector, Item], file_path: Path) -> Optional[InfrahubYamlFile]:
    if file_path.suffix in [".yml", ".yaml"] and file_path.name.startswith("test_"):
        return InfrahubYamlFile.from_parent(parent, path=file_path)
    return None


def pytest_configure(config: Config) -> None:
    config.addinivalue_line(
        "markers", "infrahub_graphql_query(name: str): Test related to a GraphQL query for Infrahub"
    )
    config.addinivalue_line(
        "markers", "infrahub_jinja2_transform(name: str): Test related to a Jinja2 Transform for Infrahub"
    )
    config.addinivalue_line(
        "markers", "infrahub_python_transform(name: str): Test related to a Python Transform for Infrahub"
    )
    config.addinivalue_line("markers", "infrahub_unit: Unit test for Infrahub, should work without any dependencies")
    config.addinivalue_line(
        "markers", "infrahub_integraton: Integation test with Infrahub, must be run against an instance"
    )
