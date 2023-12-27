from asyncio import run as aiorun
from pathlib import Path

import typer
from rich.console import Console

from infrahub_ctl import config
from infrahub_ctl.client import initialize_client
from infrahub_sdk.transfer.exceptions import TransferError
from infrahub_sdk.transfer.importer.json import LineDelimitedJSONImporter
from infrahub_sdk.transfer.schema_sorter import InfrahubSchemaTopologicalSorter


def load(
    directory: Path = typer.Argument(default=None, help="Directory path of exported data."),
    continue_on_error: bool = typer.Option(
        False, help="Allow exceptions during loading and display them when complete"
    ),
    quiet: bool = typer.Option(False, help="No console output"),
    config_file: str = typer.Option("infrahubctl.toml", envvar="INFRAHUBCTL_CONFIG"),
    branch: str = typer.Option("main", help="Branch from which to export"),
    concurrent: int = typer.Option(
        4,
        help="Maximum number of requests to execute at the same time.",
        envvar="INFRAHUBCTL_CONCURRENT_EXECUTION",
    ),
    timeout: int = typer.Option(60, help="Timeout in sec", envvar="INFRAHUBCTL_TIMEOUT"),
) -> None:
    """Import node(s)."""
    console = Console()
    if not config.SETTINGS:
        config.load_and_exit(config_file=config_file)
    client = aiorun(initialize_client(timeout=timeout, max_concurrent_execution=concurrent, retry_on_failure=True))
    importer = LineDelimitedJSONImporter(
        client,
        InfrahubSchemaTopologicalSorter(),
        continue_on_error=continue_on_error,
        console=Console() if not quiet else None,
    )
    try:
        aiorun(
            importer.import_data(
                import_directory=directory,
                branch=branch,
            )
        )
    except TransferError as exc:
        console.print(f"[red]{exc}")
        raise typer.Exit(1)
