import logging
import sys
from asyncio import run as aiorun
from datetime import datetime
from typing import Optional

import typer
from rich.console import Console
from rich.table import Table

import infrahub_ctl.config as config
from infrahub_client import GraphQLError, InfrahubClient, ServerNotReacheableError
from infrahub_ctl.utils import calculate_time_diff, render_action_rich

app = typer.Typer()


DEFAULT_CONFIG_FILE = "infrahubctl.toml"
ENVVAR_CONFIG_FILE = "INFRAHUBCTL_CONFIG"


async def _list():
    client = await InfrahubClient.init(address=config.SETTINGS.server_address)

    console = Console()

    try:
        branches = await client.get_list_branches()
    except ServerNotReacheableError as exc:
        console.print(f"[red]{exc.message}")
        sys.exit(1)
    except GraphQLError as exc:
        for error in exc.errors:
            console.print(f"[red]{error}")
        sys.exit(1)

    table = Table(title="List of all branches")

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


@app.command("list")
def list_branch(
    config_file: str = typer.Option(DEFAULT_CONFIG_FILE, envvar=ENVVAR_CONFIG_FILE),
):
    """List all existing branches."""

    logging.getLogger("infrahub_client").setLevel(logging.CRITICAL)

    config.load_and_exit(config_file_name=config_file)
    aiorun(_list())


async def _create(branch_name: str, description: str, data_only: bool):
    console = Console()

    client = await InfrahubClient.init(address=config.SETTINGS.server_address)

    try:
        branch = await client.create_branch(branch_name=branch_name, description=description, data_only=data_only)
    except ServerNotReacheableError as exc:
        console.print(f"[red]{exc.message}")
        sys.exit(1)
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

    logging.getLogger("infrahub_client").setLevel(logging.CRITICAL)

    config.load_and_exit(config_file_name=config_file)
    aiorun(_create(branch_name=branch_name, description=description, data_only=data_only))


async def _rebase(branch_name: str):
    console = Console()

    client = await InfrahubClient.init(address=config.SETTINGS.server_address)

    try:
        await client.branch_rebase(branch_name=branch_name)
    except ServerNotReacheableError as exc:
        console.print(f"[red]{exc.message}")
        sys.exit(1)
    except GraphQLError as exc:
        for error in exc.errors:
            console.print(f"[red]{error['message']}")
        sys.exit(1)

    console.print(f"Branch '{branch_name}' rebased successfully.")


@app.command()
def rebase(
    branch_name: str,
    config_file: str = typer.Option(DEFAULT_CONFIG_FILE, envvar=ENVVAR_CONFIG_FILE),
):
    """Rebase a Branch with main."""

    logging.getLogger("infrahub_client").setLevel(logging.CRITICAL)

    config.load_and_exit(config_file_name=config_file)
    aiorun(_rebase(branch_name=branch_name))


async def _merge(branch_name: str):
    console = Console()

    client = await InfrahubClient.init(address=config.SETTINGS.server_address)

    try:
        await client.branch_merge(branch_name=branch_name)
    except ServerNotReacheableError as exc:
        console.print(f"[red]{exc.message}")
        sys.exit(1)
    except GraphQLError as exc:
        for error in exc.errors:
            console.print(f"[red]{error['message']}")
        sys.exit(1)

    console.print(f"Branch '{branch_name}' merged successfully.")


@app.command()
def merge(
    branch_name: str,
    config_file: str = typer.Option(DEFAULT_CONFIG_FILE, envvar=ENVVAR_CONFIG_FILE),
):
    """Merge a Branch with main (NOT IMPLEMENTED YET)."""

    logging.getLogger("infrahub_client").setLevel(logging.CRITICAL)

    config.load_and_exit(config_file_name=config_file)
    aiorun(_merge(branch_name=branch_name))


async def _validate(branch_name: str):
    console = Console()

    client = await InfrahubClient.init(address=config.SETTINGS.server_address)

    try:
        await client.branch_validate(branch_name=branch_name)
    except ServerNotReacheableError as exc:
        console.print(f"[red]{exc.message}")
        sys.exit(1)
    except GraphQLError as exc:
        for error in exc.errors:
            console.print(f"[red]{error['message']}")
        sys.exit(1)

    console.print(f"Branch '{branch_name}' is valid.")


@app.command()
def validate(
    branch_name: str,
    config_file: str = typer.Option(DEFAULT_CONFIG_FILE, envvar=ENVVAR_CONFIG_FILE),
):
    """Validate if a branch has some conflict and is passing all the tests (NOT IMPLEMENTED YET)."""
    config.load_and_exit(config_file_name=config_file)
    aiorun(_validate(branch_name=branch_name))


async def _diff(branch_name: str, diff_from: str, diff_to: str, branch_only: str):
    console = Console()

    client = await InfrahubClient.init(address=config.SETTINGS.server_address)

    try:
        response = await client.get_branch_diff(
            branch_name=branch_name, branch_only=branch_only, diff_from=diff_from, diff_to=diff_to
        )
    except ServerNotReacheableError as exc:
        console.print(f"[red]{exc.message}")
        sys.exit(1)
    except GraphQLError as exc:
        for error in exc.errors:
            console.print(f"[red]{error['message']}")
        sys.exit(1)

    attr_padding = " " * 2

    for node in response["diff"]["nodes"]:
        console.print(f"Node {node['kind']} '{node['id']}'")
        for attr in node["attributes"]:
            console.print(f"{attr_padding}{attr['name']} {render_action_rich(attr['action'])} ")

            grid = Table.grid(expand=True)
            grid.add_column(justify="right")
            grid.add_column(justify="right")
            grid.add_column(justify="center", width=4)
            grid.add_column(justify="left")
            grid.add_column()
            # grid.add_column(justify="right")

            for prop in attr["properties"]:
                clean_prop_name = prop["type"].replace("HAS_", "").replace("IS_", "").lower()
                grid.add_row(
                    clean_prop_name,
                    f"[magenta]{prop['value']['previous']}",
                    "[blue] >> ",
                    f"[magenta]{prop['value']['new']}",
                    f"[green]{prop['changed_at']}[/green] ({calculate_time_diff(prop['changed_at'])})",
                )

            console.print(grid)


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

    logging.getLogger("infrahub_client").setLevel(logging.CRITICAL)

    aiorun(_diff(branch_name=branch_name, diff_from=diff_from or "", diff_to=diff_to or "", branch_only=branch_only))
