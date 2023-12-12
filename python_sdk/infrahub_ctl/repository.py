from pathlib import Path

import typer
import yaml

try:
    from pydantic import v1 as pydantic  # type: ignore[attr-defined]
except ImportError:
    import pydantic  # type: ignore[no-redef]

from rich.console import Console

from infrahub_ctl.exceptions import FileNotValidError
from infrahub_sdk.schema import InfrahubRepositoryConfig


def get_repository_config(repo_config_file: Path) -> InfrahubRepositoryConfig:
    console = Console()
    try:
        config_file_data = load_repository_config_file(repo_config_file)
    except FileNotFoundError as exc:
        console.print(f"[red]{exc}")
        raise typer.Exit(1) from exc
    except FileNotValidError as exc:
        console.print(f"[red]{exc}")
        raise typer.Exit(1) from exc

    try:
        data = InfrahubRepositoryConfig(**config_file_data)
    except pydantic.ValidationError as exc:
        console.print(f"[red]Repository config file not valid, found {len(exc.errors())} error(s)")
        for error in exc.errors():
            loc_str = [str(item) for item in error["loc"]]
            console.print(f"  {'/'.join(loc_str)} | {error['msg']} ({error['type']})")
        raise typer.Exit(1) from exc

    return data


def load_repository_config_file(repo_config_file: Path) -> dict:
    if not repo_config_file.is_file():
        raise FileNotFoundError(repo_config_file)

    try:
        yaml_data = repo_config_file.read_text()
        data = yaml.safe_load(yaml_data)
    except yaml.YAMLError as exc:
        raise FileNotValidError(name=str(repo_config_file)) from exc

    return data
