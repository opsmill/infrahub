from asyncio import run as aiorun
from datetime import datetime, timezone
from pathlib import Path
from typing import List

import typer
from rich.console import Console

# pylint: disable=import-outside-toplevel
import infrahub_ctl.config as config
from infrahub_ctl.client import initialize_client
from infrahub_sdk.transfer.export.json import LineDelimitedJSONExporter

from .command import do_export
from .constants import ILLEGAL_NAMESPACES


def directory_name_with_timestamp():
    right_now = datetime.now(timezone.utc).astimezone()
    timestamp = right_now.strftime("%Y%m%d-%H%M%S")
    return f"infrahubexport-{timestamp}"


def export(
    namespace: List[str] = typer.Option([], help="Namespace(s) to export"),
    directory: Path = typer.Option(directory_name_with_timestamp, help="Directory path to store export."),
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
    namespace = [ns.lower() for ns in namespace]
    console = Console()
    if set(namespace) & ILLEGAL_NAMESPACES:
        console.print(f"[red]namespaces cannot include {ILLEGAL_NAMESPACES}")
        raise typer.Exit(1)
    if not config.SETTINGS:
        config.load_and_exit(config_file=config_file)
    client = aiorun(initialize_client(timeout=timeout, max_concurrent_execution=concurrent, retry_on_failure=True))
    exporter = LineDelimitedJSONExporter(destination_directory=directory)
    exported = aiorun(
        do_export(
            exporter,
            client,
            namespaces=namespace,
            branch=branch,
        )
    )

    console.print(exported)
