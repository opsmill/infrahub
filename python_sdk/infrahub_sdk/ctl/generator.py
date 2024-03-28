from pathlib import Path
from typing import List, Optional

from rich.console import Console

from infrahub_sdk.ctl import config
from infrahub_sdk.ctl.repository import get_repository_config
from infrahub_sdk.schema import InfrahubRepositoryConfig


async def run(
    generator_name: str,
    path: str,
    debug: bool,
    list_available: bool,
    branch: Optional[str] = None,
    variables: Optional[List[str]] = None,
):  # pylint: disable=unused-argument
    repository_config = get_repository_config(Path(config.INFRAHUB_REPO_CONFIG_FILE))

    if list_available:
        list_generators(repository_config=repository_config)
        return

    matched = [generator for generator in repository_config.generator_definitions if generator.name == generator_name]

    console = Console()

    if not matched:
        console.print(f"[red]Unable to find requested generator: {generator_name}")
        list_generators(repository_config=repository_config)
        return


def list_generators(repository_config: InfrahubRepositoryConfig) -> None:
    console = Console()
    console.print(f"Generators defined in repository: {len(repository_config.generator_definitions)}")

    for generator in repository_config.generator_definitions:
        console.print(f"{generator.name} ({generator.file_path}::{generator.class_name}) Target: {generator.targets}")
