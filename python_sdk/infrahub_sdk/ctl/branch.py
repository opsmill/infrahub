import logging
import sys
from typing import Optional

import typer
from rich.console import Console
from rich.table import Table

from infrahub_sdk import Error, GraphQLError
from infrahub_sdk.async_typer import AsyncTyper
from infrahub_sdk.ctl.client import initialize_client
from infrahub_sdk.ctl.utils import (
    calculate_time_diff,
    print_graphql_errors,
)

from .parameters import CONFIG_PARAM

app = AsyncTyper()


DEFAULT_CONFIG_FILE = "infrahubctl.toml"
ENVVAR_CONFIG_FILE = "INFRAHUBCTL_CONFIG"


@app.callback()
def callback() -> None:
    """
    Manage the branches in a remote Infrahub instance.

    List, create, merge, rebase ..
    """


@app.command("list")
async def list_branch(
    _: str = CONFIG_PARAM,
) -> None:
    """List all existing branches."""

    logging.getLogger("infrahub_sdk").setLevel(logging.CRITICAL)

    client = await initialize_client()

    console = Console()

    try:
        branches = await client.branch.all()
    except GraphQLError as exc:
        print_graphql_errors(console, exc.errors)
        sys.exit(1)
    except Error as exc:
        console.print(f"[red]{exc.message}")
        sys.exit(1)

    table = Table(title="List of all branches")

    table.add_column("Name", justify="right", style="cyan", no_wrap=True)
    table.add_column("Description")
    table.add_column("Origin Branch")
    table.add_column("Branched From")
    table.add_column("Sync with Git")
    table.add_column("Is Isolated")
    table.add_column("Has Schema Changes")
    table.add_column("Is Default")

    # identify the default branch and always print it first
    default_branch = [branch for branch in branches.values() if branch.is_default][0]
    table.add_row(
        default_branch.name,
        default_branch.description or " - ",
        default_branch.origin_branch,
        f"{default_branch.branched_from} ({calculate_time_diff(default_branch.branched_from)})",
        "[green]True" if default_branch.sync_with_git else "[#FF7F50]False",
        "[green]True" if default_branch.is_isolated else "[#FF7F50]False",
        "[green]True" if default_branch.has_schema_changes else "[#FF7F50]False",
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
            "[green]True" if branch.sync_with_git else "[#FF7F50]False",
            "[green]True" if default_branch.is_isolated else "[#FF7F50]False",
            "[green]True" if default_branch.has_schema_changes else "[#FF7F50]False",
            "[green]True" if branch.is_default else "[#FF7F50]False",
        )

    console.print(table)


@app.command()
async def create(
    branch_name: str = typer.Argument(..., help="Name of the branch to create"),
    description: Optional[str] = typer.Option("", help="Description of the branch"),
    sync_with_git: bool = typer.Option(
        False, help="Extend the branch to Git and have Infrahub create the branch in connected repositories."
    ),
    isolated: bool = typer.Option(False, help="Set the branch to isolated mode"),
    _: str = CONFIG_PARAM,
) -> None:
    """Create a new branch."""

    logging.getLogger("infrahub_sdk").setLevel(logging.CRITICAL)

    console = Console()

    client = await initialize_client()

    try:
        branch = await client.branch.create(
            branch_name=branch_name, description=description, sync_with_git=sync_with_git, is_isolated=isolated
        )
    except GraphQLError as exc:
        print_graphql_errors(console, exc.errors)
        sys.exit(1)
    except Error as exc:
        console.print(f"[red]{exc.message}")
        sys.exit(1)

    console.print(f"Branch {branch_name!r} created successfully ({branch.id}).")


@app.command()
async def delete(
    branch_name: str,
    _: str = CONFIG_PARAM,
) -> None:
    """Delete a branch."""

    logging.getLogger("infrahub_sdk").setLevel(logging.CRITICAL)

    console = Console()

    client = await initialize_client()

    try:
        await client.branch.delete(branch_name=branch_name)
    except GraphQLError as exc:
        print_graphql_errors(console, exc.errors)
        sys.exit(1)
    except Error as exc:
        console.print(f"[red]{exc.message}")
        sys.exit(1)

    console.print(f"Branch '{branch_name}' deleted successfully.")


@app.command()
async def rebase(
    branch_name: str,
    _: str = CONFIG_PARAM,
) -> None:
    """Rebase a Branch with main."""

    logging.getLogger("infrahub_sdk").setLevel(logging.CRITICAL)

    console = Console()

    client = await initialize_client()

    try:
        await client.branch.rebase(branch_name=branch_name)
    except GraphQLError as exc:
        print_graphql_errors(console, exc.errors)
        sys.exit(1)
    except Error as exc:
        console.print(f"[red]{exc.message}")
        sys.exit(1)

    console.print(f"Branch '{branch_name}' rebased successfully.")


@app.command()
async def merge(
    branch_name: str,
    _: str = CONFIG_PARAM,
) -> None:
    """Merge a Branch with main."""

    logging.getLogger("infrahub_sdk").setLevel(logging.CRITICAL)

    console = Console()

    client = await initialize_client()

    try:
        await client.branch.merge(branch_name=branch_name)
    except GraphQLError as exc:
        print_graphql_errors(console, exc.errors)
        sys.exit(1)
    except Error as exc:
        console.print(f"[red]{exc.message}")
        sys.exit(1)

    console.print(f"Branch '{branch_name}' merged successfully.")


@app.command()
async def validate(
    branch_name: str,
    _: str = CONFIG_PARAM,
) -> None:
    """Validate if a branch has some conflict and is passing all the tests (NOT IMPLEMENTED YET)."""

    console = Console()

    client = await initialize_client()

    try:
        await client.branch.validate(branch_name=branch_name)
    except GraphQLError as exc:
        print_graphql_errors(console, exc.errors)
        sys.exit(1)
    except Error as exc:
        console.print(f"[red]{exc.message}")
        sys.exit(1)

    console.print(f"Branch '{branch_name}' is valid.")
