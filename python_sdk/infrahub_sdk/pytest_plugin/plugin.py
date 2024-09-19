import os
from pathlib import Path
from typing import Optional, Union

from pytest import Collector, Config, Item, Parser, Session
from pytest import exit as exit_test

from infrahub_sdk import InfrahubClientSync
from infrahub_sdk.utils import is_valid_url

from .loader import InfrahubYamlFile
from .utils import load_repository_config


def pytest_addoption(parser: Parser) -> None:
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
        default=os.getenv("INFRAHUB_API_TOKEN"),
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

    client_config = {
        "address": session.config.option.infrahub_address,
        "default_branch": session.config.option.infrahub_branch,
    }
    if hasattr(session.config.option, "infrahub_key"):
        client_config["api_token"] = session.config.option.infrahub_key
    elif hasattr(session.config.option, "infrahub_username") and hasattr(session.config.option, "infrahub_password"):
        client_config.pop("api_token")
        client_config["username"] = session.config.option.infrahub_username
        client_config["password"] = session.config.option.infrahub_password

    infrahub_client = InfrahubClientSync(config=client_config)
    session.infrahub_client = infrahub_client  # type: ignore[attr-defined]


def pytest_collect_file(parent: Union[Collector, Item], file_path: Path) -> Optional[InfrahubYamlFile]:
    if file_path.suffix in [".yml", ".yaml"] and file_path.name.startswith("test_"):
        return InfrahubYamlFile.from_parent(parent, path=file_path)
    return None


def pytest_configure(config: Config) -> None:
    config.addinivalue_line("markers", "infrahub: Infrahub test")
    config.addinivalue_line("markers", "infrahub_smoke: Smoke test for an Infrahub resource")
    config.addinivalue_line("markers", "infrahub_unit: Unit test for an Infrahub resource, works without dependencies")
    config.addinivalue_line(
        "markers",
        "infrahub_integraton: Integation test for an Infrahub resource, depends on an Infrahub running instance",
    )
    config.addinivalue_line("markers", "infrahub_check: Test related to an Infrahub Check")
    config.addinivalue_line("markers", "infrahub_graphql_query: Test related to an Infrahub GraphQL query")
    config.addinivalue_line("markers", "infrahub_jinja2_transform: Test related to an Infrahub Jinja2 Transform")
    config.addinivalue_line("markers", "infrahub_python_transform: Test related to an Infrahub Python Transform")
