from asyncio import run as aiorun
from pathlib import Path

import typer
import yaml
from pydantic import ValidationError
from rich.console import Console
from ujson import JSONDecodeError

import infrahub_ctl.config as config
from infrahub_client import InfrahubClient

app = typer.Typer()

DEFAULT_CONFIG_FILE = "infrahubctl.toml"
ENVVAR_CONFIG_FILE = "INFRAHUBCTL_CONFIG"


@app.callback()
def callback() -> None:
    """
    Helper to validate the format of various files.
    """


async def _schema(schema: Path) -> None:
    console = Console()

    try:
        schema_data = yaml.safe_load(schema.read_text())
    except JSONDecodeError as exc:
        console.print("[red]Invalid JSON file")
        raise typer.Exit(2) from exc

    client = await InfrahubClient.init(address=config.SETTINGS.server_address, insert_tracker=True)

    try:
        client.schema.validate(schema_data)
    except ValidationError as exc:
        console.print(f"[red]Schema not valid, found '{len(exc.errors())}' error(s)")
        for error in exc.errors():
            loc_str = [str(item) for item in error["loc"]]
            console.print(f"  '{'/'.join(loc_str)}' | {error['msg']} ({error['type']})")
        raise typer.Exit(2)

    console.print("[green]Schema is valid !!")


@app.command(name="schema")
def validate_schema(
    schema: Path, config_file: Path = typer.Option(DEFAULT_CONFIG_FILE, envvar=ENVVAR_CONFIG_FILE)
) -> None:
    """Validate the format of a schema file either in JSON or YAML"""
    config.load_and_exit(config_file=config_file)
    aiorun(_schema(schema=schema))
