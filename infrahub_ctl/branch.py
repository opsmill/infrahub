import sys
from asyncio import run as aiorun

import typer
from rich.console import Console
from rich.table import Table

import infrahub_ctl.config as config
from infrahub_client import GraphQLError, InfrahubClient
from infrahub_ctl.utils import calculate_time_diff

app = typer.Typer()


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
    config_file: str = typer.Argument("infrahubctl.toml", envvar="INFRAHUBCTL_CONFIG"),
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
    config_file: str = typer.Option("infrahubctl.toml", envvar="INFRAHUBCTL_CONFIG"),
):
    """Create a new branch."""
    config.load_and_exit(config_file_name=config_file)
    aiorun(_create(branch_name=branch_name, description=description, data_only=data_only))
