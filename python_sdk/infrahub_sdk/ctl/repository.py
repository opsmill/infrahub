from pathlib import Path

import typer
import yaml
from pydantic import ValidationError
from rich.console import Console

from infrahub_sdk.async_typer import AsyncTyper
from infrahub_sdk.ctl.client import initialize_client
from infrahub_sdk.ctl.exceptions import FileNotValidError
from infrahub_sdk.ctl.utils import init_logging
from infrahub_sdk.graphql import Mutation
from infrahub_sdk.schema import InfrahubRepositoryConfig

from .parameters import CONFIG_PARAM

app = AsyncTyper()
console = Console()


def get_repository_config(repo_config_file: Path) -> InfrahubRepositoryConfig:
    try:
        config_file_data = load_repository_config_file(repo_config_file)
    except FileNotFoundError as exc:
        console.print(f"[red]File not found {exc}")
        raise typer.Exit(1) from exc
    except FileNotValidError as exc:
        console.print(f"[red]{exc.message}")
        raise typer.Exit(1) from exc

    try:
        data = InfrahubRepositoryConfig(**config_file_data)
    except ValidationError as exc:
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


@app.callback()
def callback() -> None:
    """
    Manage the repositories in a remote Infrahub instance.

    List, create, delete ..
    """


@app.command()
async def add(
    name: str,
    location: str,
    description: str = "",
    username: str = "",
    password: str = "",
    commit: str = "",
    read_only: bool = False,
    debug: bool = False,
    branch: str = typer.Option("main", help="Branch on which to add the repository."),
    _: str = CONFIG_PARAM,
) -> None:
    """Add a new repository."""

    init_logging(debug=debug)

    input_data = {
        "data": {
            "name": {"value": name},
            "location": {"value": location},
            "description": {"value": description},
            "commit": {"value": commit},
        },
    }

    client = await initialize_client()

    if username:
        credential = await client.create(kind="CorePasswordCredential", name=name, username=username, password=password)
        await credential.save()
        input_data["data"]["credential"] = {"id": credential.id}

    query = Mutation(
        mutation="CoreReadOnlyRepositoryCreate" if read_only else "CoreRepositoryCreate",
        input_data=input_data,
        query={"ok": None},
    )

    await client.execute_graphql(query=query.render(), branch_name=branch, tracker="mutation-repository-create")
