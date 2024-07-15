from asyncio import run as aiorun
from pathlib import Path

import typer
from rich.console import Console

from infrahub_sdk.ctl.client import initialize_client
from infrahub_sdk.transfer.exceptions import TransferError
from infrahub_sdk.transfer.importer.json import LineDelimitedJSONImporter
from infrahub_sdk.transfer.schema_sorter import InfrahubSchemaTopologicalSorter

from .parameters import CONFIG_PARAM


def local_directory():
    # We use a function here to avoid failure when generating the documentation due to directory name
    return Path().resolve()


def load(
    directory: Path = typer.Option(local_directory, help="Directory path of exported data"),
    continue_on_error: bool = typer.Option(
        False, help="Allow exceptions during loading and display them when complete"
    ),
    quiet: bool = typer.Option(False, help="No console output"),
    _: str = CONFIG_PARAM,
    branch: str = typer.Option("main", help="Branch from which to export"),
    concurrent: int = typer.Option(
        4,
        help="Maximum number of requests to execute at the same time.",
        envvar="INFRAHUBCTL_CONCURRENT_EXECUTION",
    ),
    timeout: int = typer.Option(60, help="Timeout in sec", envvar="INFRAHUBCTL_TIMEOUT"),
) -> None:
    """Import nodes and their relationships into the database."""
    console = Console()

    client = aiorun(
        initialize_client(branch=branch, timeout=timeout, max_concurrent_execution=concurrent, retry_on_failure=True)
    )
    importer = LineDelimitedJSONImporter(
        client,
        InfrahubSchemaTopologicalSorter(),
        continue_on_error=continue_on_error,
        console=Console() if not quiet else None,
    )
    try:
        aiorun(importer.import_data(import_directory=directory, branch=branch))
    except TransferError as exc:
        console.print(f"[red]{exc}")
        raise typer.Exit(1)
