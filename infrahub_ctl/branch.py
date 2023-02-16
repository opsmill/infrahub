import sys
from asyncio import run as aiorun
from datetime import datetime
from typing import Optional

import typer
from rich.console import Console
from rich.table import Table

import infrahub_ctl.config as config
from infrahub_client import GraphQLError, InfrahubClient
from infrahub_ctl.utils import calculate_time_diff

app = typer.Typer()


DEFAULT_CONFIG_FILE = "infrahubctl.toml"
ENVVAR_CONFIG_FILE = "INFRAHUBCTL_CONFIG"


async def _list():
    client = await InfrahubClient.init(address=config.SETTINGS.server_address)

    console = Console()

    try:
        branches = await client.get_list_branches()
    except GraphQLError as exc:
        for error in exc.errors:
            console.print(f"[red]{error}")
        sys.exit(1)

    table = Table(title=f"List of all branches")

    table.add_column("Name", justify="right", style="cyan", no_wrap=True)
    table.add_column("Description")
    table.add_column("Origin Branch")
    table.add_column("Branched From")
    table.add_column("Is Data Only")
    table.add_column("Is Default")

    # identify the default branch and always print it first
    default_branch = [branch for branch in branches.values() if branch.is_default][0]
    table.add_row(
        default_branch.name,
        default_branch.description or " - ",
        default_branch.origin_branch,
        f"{default_branch.branched_from} ({calculate_time_diff(default_branch.branched_from)})",
        "[green]True" if default_branch.is_data_only else "[#FF7F50]False",
        "[green]True" if default_branch.is_default else "[#FF7F50]False",
    )

    for branch in branches.values():
        if branch.is_default:
            continue

        table.add_row(
            branch.name,
            branch.description or " - ",
            branch.origin_branch,
            f"{branch.branched_from} ({calculate_time_diff(branch.branched_from)})",
            "[green]True" if branch.is_data_only else "[#FF7F50]False",
            "[green]True" if branch.is_default else "[#FF7F50]False",
        )

    console.print(table)


@app.command()
def list(
    config_file: str = typer.Option(DEFAULT_CONFIG_FILE, envvar=ENVVAR_CONFIG_FILE),
):
    """List all existing branches."""
    config.load_and_exit(config_file_name=config_file)
    aiorun(_list())


async def _create(branch_name: str, description: str, data_only: bool):
    console = Console()

    client = await InfrahubClient.init(address=config.SETTINGS.server_address)

    try:
        branch = await client.create_branch(branch_name=branch_name, description=description, data_only=data_only)
    except GraphQLError as exc:
        for error in exc.errors:
            console.print(f"[red]{error['message']}")
        sys.exit(1)

    console.print(f"Branch '{branch_name}' created successfully ({branch.id}).")


@app.command()
def create(
    branch_name: str,
    description: str = typer.Argument(""),
    data_only: bool = True,
    config_file: str = typer.Option(DEFAULT_CONFIG_FILE, envvar=ENVVAR_CONFIG_FILE),
):
    """Create a new branch."""
    config.load_and_exit(config_file_name=config_file)
    aiorun(_create(branch_name=branch_name, description=description, data_only=data_only))


@app.command()
def rebase(
    branch_name: str,
    config_file: str = typer.Option(DEFAULT_CONFIG_FILE, envvar=ENVVAR_CONFIG_FILE),
):
    """Rebase a Branch with main (NOT IMPLEMENTED YET)."""
    config.load_and_exit(config_file_name=config_file)
    # aiorun(_rebase(branch_name=branch_name))


@app.command()
def merge(
    branch_name: str,
    config_file: str = typer.Option(DEFAULT_CONFIG_FILE, envvar=ENVVAR_CONFIG_FILE),
):
    """Merge a Branch with main (NOT IMPLEMENTED YET)."""
    config.load_and_exit(config_file_name=config_file)
    # aiorun(_merge(branch_name=branch_name))


@app.command()
def validate(
    branch_name: str,
    config_file: str = typer.Option(DEFAULT_CONFIG_FILE, envvar=ENVVAR_CONFIG_FILE),
):
    """Validate if a branch has some conflict and is passing all the tests (NOT IMPLEMENTED YET)."""
    config.load_and_exit(config_file_name=config_file)
    # aiorun(_validate(branch_name=branch_name))


async def _diff(branch_name: str, diff_from: str, diff_to: str, branch_only: str):
    Console()

    client = await InfrahubClient.init(address=config.SETTINGS.server_address)

    response = await client.get_branch_diff(branch_name=branch_name, branch_only=branch_only)

    print(response)


# ? pendulum.now()
@app.command()
def diff(
    branch_name: str,
    diff_from: Optional[datetime] = typer.Option(
        None, "--from", help="Start Time used to calculate the Diff, Default: from the start of the branch"
    ),
    diff_to: Optional[datetime] = typer.Option(None, "--to", help="End Time used to calculate the Diff, Default: now"),
    branch_only: bool = True,
    config_file: str = typer.Option(DEFAULT_CONFIG_FILE, envvar=ENVVAR_CONFIG_FILE),
):
    """Show the differences between a Branch and main."""
    config.load_and_exit(config_file_name=config_file)
    aiorun(_diff(branch_name=branch_name, diff_from=diff_from, diff_to=diff_to, branch_only=branch_only))
