import logging
from asyncio import run as aiorun
from pathlib import Path

import typer
import yaml
from pydantic import ValidationError
from rich.console import Console
from rich.logging import RichHandler

import infrahub_ctl.config as config
from infrahub_ctl.client import initialize_client

app = typer.Typer()


@app.callback()
def callback() -> None:
    """
    Manage the schema in a remote Infrahub instance.
    """


async def _load(schema: Path, branch: str, log: logging.Logger) -> None:  # pylint: disable=unused-argument
    console = Console()

    try:
        schema_data = yaml.safe_load(schema.read_text())
    except yaml.YAMLError as exc:
        console.print("[red]Invalid JSON file")
        raise typer.Exit(2) from exc

    client = await initialize_client()

    try:
        client.schema.validate(schema_data)
    except ValidationError as exc:
        console.print(f"[red]Schema not valid, found '{len(exc.errors())}' error(s)")
        for error in exc.errors():
            loc_str = [str(item) for item in error["loc"]]
            console.print(f"  '{'/'.join(loc_str)}' | {error['msg']} ({error['type']})")
        raise typer.Exit(2)

    _, errors = await client.schema.load(schema=schema_data, branch=branch)

    if errors:
        console.print("[red]Unable to load the schema:")
        if "detail" in errors:
            for error in errors.get("detail"):
                loc_str = [str(item) for item in error["loc"][1:]]
                console.print(f"  '{'/'.join(loc_str)}' | {error['msg']} ({error['type']})")
        elif "error" in errors:
            console.print(f"  '{errors.get('error')}'")
        else:
            console.print(f"  '{errors}'")
    else:
        console.print("[green]Schema loaded successfully!")


@app.command()
def load(
    schema: Path,
    debug: bool = False,
    branch: str = typer.Option("main", help="Branch on which to load the schema."),
    config_file: str = typer.Option("infrahubctl.toml", envvar="INFRAHUBCTL_CONFIG"),
) -> None:
    """Load a schema file into Infrahub."""
    if not config.SETTINGS:
        config.load_and_exit(config_file=config_file)

    logging.getLogger("infrahub_client").setLevel(logging.CRITICAL)
    logging.getLogger("httpx").setLevel(logging.ERROR)
    logging.getLogger("httpcore").setLevel(logging.ERROR)

    log_level = "DEBUG" if debug else "INFO"
    FORMAT = "%(message)s"
    logging.basicConfig(level=log_level, format=FORMAT, datefmt="[%X]", handlers=[RichHandler()])
    log = logging.getLogger("infrahubctl")

    aiorun(_load(schema=schema, branch=branch, log=log))


@app.command()
def migrate() -> None:
    """Migrate the schema to the latest version. (Not Implemented Yet)"""
    print("Not implemented yet.")
