import logging
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, Generator, List, Optional

import typer
from rich.console import Console
from rich.console import group as rich_group
from rich.panel import Panel
from rich.table import Table

from infrahub_sdk import Error, GraphQLError
from infrahub_sdk.async_typer import AsyncTyper
from infrahub_sdk.ctl import config
from infrahub_sdk.ctl.client import initialize_client
from infrahub_sdk.ctl.utils import (
    calculate_time_diff,
    print_graphql_errors,
    render_action_rich,
)

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
    config_file: Path = typer.Option(DEFAULT_CONFIG_FILE, envvar=ENVVAR_CONFIG_FILE),
) -> None:
    """List all existing branches."""

    logging.getLogger("infrahub_sdk").setLevel(logging.CRITICAL)

    if not config.SETTINGS:
        config.load_and_exit(config_file=config_file)

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
async def create(
    branch_name: str,
    description: str = typer.Argument(""),
    data_only: bool = True,
    config_file: Path = typer.Option(DEFAULT_CONFIG_FILE, envvar=ENVVAR_CONFIG_FILE),
) -> None:
    """Create a new branch."""

    logging.getLogger("infrahub_sdk").setLevel(logging.CRITICAL)

    if not config.SETTINGS:
        config.load_and_exit(config_file=config_file)

    console = Console()

    client = await initialize_client()

    try:
        branch = await client.branch.create(branch_name=branch_name, description=description, data_only=data_only)
    except GraphQLError as exc:
        print_graphql_errors(console, exc.errors)
        sys.exit(1)
    except Error as exc:
        console.print(f"[red]{exc.message}")
        sys.exit(1)

    console.print(f"Branch '{branch_name}' created successfully ({branch.id}).")


@app.command()
async def delete(
    branch_name: str,
    config_file: Path = typer.Option(DEFAULT_CONFIG_FILE, envvar=ENVVAR_CONFIG_FILE),
) -> None:
    """Delete a branch."""

    logging.getLogger("infrahub_sdk").setLevel(logging.CRITICAL)

    if not config.SETTINGS:
        config.load_and_exit(config_file=config_file)

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
    config_file: Path = typer.Option(DEFAULT_CONFIG_FILE, envvar=ENVVAR_CONFIG_FILE),
) -> None:
    """Rebase a Branch with main."""

    logging.getLogger("infrahub_sdk").setLevel(logging.CRITICAL)

    if not config.SETTINGS:
        config.load_and_exit(config_file=config_file)

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
    config_file: Path = typer.Option(DEFAULT_CONFIG_FILE, envvar=ENVVAR_CONFIG_FILE),
) -> None:
    """Merge a Branch with main."""

    logging.getLogger("infrahub_sdk").setLevel(logging.CRITICAL)

    if not config.SETTINGS:
        config.load_and_exit(config_file=config_file)

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
    config_file: Path = typer.Option(DEFAULT_CONFIG_FILE, envvar=ENVVAR_CONFIG_FILE),
) -> None:
    """Validate if a branch has some conflict and is passing all the tests (NOT IMPLEMENTED YET)."""

    if not config.SETTINGS:
        config.load_and_exit(config_file=config_file)

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


@rich_group()
def node_panel_generator(nodes: List[Dict]) -> Generator:
    for node in nodes:
        lines = []

        for attr in node["attributes"]:
            attr_header = "{:10}{:10}  {:<20}".format(
                "",
                render_action_rich(attr["action"]),
                attr["name"],
            )
            lines.append(attr_header)

            for prop in attr["properties"]:
                clean_prop_name = prop["type"].replace("HAS_", "").replace("IS_", "").lower()

                property_string = "{:>20}[magenta]{:>20}[blue]{:>4}[magenta]{:20}[green]{:>20}[/green]{:>20}".format(
                    clean_prop_name,
                    f"{prop['value']['previous']}",
                    " >> ",
                    f"{prop['value']['new']}",
                    f"{prop['changed_at']}",
                    f"({calculate_time_diff(prop['changed_at'])})",
                )

            lines.append(property_string)

        for rel in node["relationships"]:
            rel_header = "{:10}{:10}  {:<20} Node {:>20}{:>20} {:>20}".format(
                "",
                render_action_rich(rel["action"]),
                rel["name"],
                rel["peer"]["kind"],
                rel["peer"]["display_label"],
                rel["peer"]["id"],
            )

            lines.append(rel_header)

            for prop in rel["properties"]:
                clean_prop_name = prop["type"].replace("HAS_", "").replace("IS_", "").lower()

                property_string = "{:>20}[magenta]{:>20}[blue]{:>4}[magenta]{:20}[green]{:>20}[/green]{:>20}".format(
                    clean_prop_name,
                    f"{prop['value']['previous']}",
                    " >> ",
                    f"{prop['value']['new']}",
                    f"{prop['changed_at']}",
                    f"({calculate_time_diff(prop['changed_at'])})",
                )

            lines.append(property_string)

        yield Panel(
            "\n".join(lines),
            title=f"Node {node['kind']} {node['display_label']} ({node['id']})",
            title_align="left",
        )


@app.command()
async def diff(
    branch_name: str,
    time_from: Optional[datetime] = typer.Option(
        None,
        "--from",
        help="Start Time used to calculate the Diff, Default: from the start of the branch",
    ),
    time_to: Optional[datetime] = typer.Option(None, "--to", help="End Time used to calculate the Diff, Default: now"),
    branch_only: bool = True,
    config_file: Path = typer.Option(DEFAULT_CONFIG_FILE, envvar=ENVVAR_CONFIG_FILE),
) -> None:
    """Show the differences between a Branch and main."""
    if not config.SETTINGS:
        config.load_and_exit(config_file=config_file)

    logging.getLogger("infrahub_sdk").setLevel(logging.CRITICAL)

    console = Console()

    client = await initialize_client()

    try:
        response = await client.branch.diff_data(
            branch_name=branch_name,
            branch_only=branch_only,
            time_from=time_from,
            time_to=time_to,
        )
    except Error as exc:
        console.print(f"[red]{exc.message}")
        sys.exit(1)

    for branch, nodes in response.json().items():
        console.print(
            Panel(
                node_panel_generator(nodes),
                title=f"Branch: [green]{branch}",
                title_align="left",
            )
        )
