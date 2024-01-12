from pathlib import Path
from typing import Optional, Union

from pytest import Collector, Config, Item, Parser, Session

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


def pytest_sessionstart(session: Session) -> None:
    config_path = Path(session.config.option.infrahub_repo_config)

    if config_path.is_file():
        session.infrahub_repo_config = load_repository_config(repo_config_file=config_path)  # type: ignore[attr-defined]


def pytest_collect_file(parent: Union[Collector, Item], file_path: Path) -> Optional[InfrahubYamlFile]:
    if file_path.suffix in [".yml", ".yaml"] and file_path.name.startswith("test_"):
        return InfrahubYamlFile.from_parent(parent, path=file_path)
    return None


def pytest_configure(config: Config) -> None:
    config.addinivalue_line(
        "markers", "infrahub_python_transform(name: str): Test related to a Python Transform for Infrahub"
    )
    config.addinivalue_line("markers", "infrahub_rfile(name: str): Test related to a RFile for Infrahub")
    config.addinivalue_line("markers", "infrahub_check(name: str): Test related to a User defined Check for Infrahub")
    config.addinivalue_line("markers", "infrahub_unit: Unit test for Infrahub, should work without any dependencies")
    config.addinivalue_line("markers", "infrahub_integraton: Integation test Infrahub")
