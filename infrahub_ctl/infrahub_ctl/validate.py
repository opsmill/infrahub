from asyncio import run as aiorun
from pathlib import Path

import typer
import ujson
from rich.console import Console

import infrahub_ctl.config as config
from infrahub_client import InfrahubClient

app = typer.Typer()

DEFAULT_CONFIG_FILE = "infrahubctl.toml"
ENVVAR_CONFIG_FILE = "INFRAHUBCTL_CONFIG"


@app.command(name="config")
def valid_config():
    pass


async def _schema(schema: Path):
    schema_data = ujson.loads(schema.read_text())

    client = await InfrahubClient.init(address=config.SETTINGS.server_address)
    Console()

    client.schema.validate(schema_data)


@app.command(name="schema")
def validate_schema(schema: Path, config_file: Path = typer.Option(DEFAULT_CONFIG_FILE, envvar=ENVVAR_CONFIG_FILE)):
    config.load_and_exit(config_file=config_file)
    aiorun(_schema(schema=schema))
