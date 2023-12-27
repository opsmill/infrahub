from asyncio import run as aiorun
from datetime import datetime, timezone
from pathlib import Path
from typing import List

import typer
from rich.console import Console

from infrahub_ctl import config
from infrahub_ctl.client import initialize_client
from infrahub_sdk.transfer.exceptions import TransferError
from infrahub_sdk.transfer.exporter.json import LineDelimitedJSONExporter


def directory_name_with_timestamp():
    right_now = datetime.now(timezone.utc).astimezone()
    timestamp = right_now.strftime("%Y%m%d-%H%M%S")
    return f"infrahubexport-{timestamp}"


def dump(
    namespace: List[str] = typer.Option([], help="Namespace(s) to export"),
    directory: Path = typer.Option(directory_name_with_timestamp, help="Directory path to store export."),
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
    """Export node(s)."""
    console = Console()
    if not config.SETTINGS:
        config.load_and_exit(config_file=config_file)
    client = aiorun(initialize_client(timeout=timeout, max_concurrent_execution=concurrent, retry_on_failure=True))
    exporter = LineDelimitedJSONExporter(client, console=Console() if not quiet else None)
    try:
        aiorun(
            exporter.export(
                export_directory=directory,
                namespaces=namespace,
                branch=branch,
            )
        )
    except TransferError as exc:
        console.print(f"[red]{exc}")
        raise typer.Exit(1)
