import sys
from asyncio import run as aiorun
from pathlib import Path
from typing import List, Optional

import typer
import yaml

try:
    from pydantic import v1 as pydantic  # type: ignore[attr-defined]
except ImportError:
    import pydantic  # type: ignore[no-redef]

from rich.console import Console
from ujson import JSONDecodeError

from infrahub_sdk.ctl import config
from infrahub_sdk.ctl.client import initialize_client, initialize_client_sync
from infrahub_sdk.ctl.exceptions import QueryNotFoundError
from infrahub_sdk.ctl.utils import find_graphql_query, parse_cli_vars
from infrahub_sdk.exceptions import GraphQLError
from infrahub_sdk.utils import get_branch

app = typer.Typer()


@app.callback()
def callback() -> None:
    """
    Helper to validate the format of various files.
    """


async def _schema(schema: Path) -> None:
    console = Console()

    try:
        schema_data = yaml.safe_load(schema.read_text())
    except JSONDecodeError as exc:
        console.print("[red]Invalid JSON file")
        raise typer.Exit(2) from exc

    client = await initialize_client()

    try:
        client.schema.validate(schema_data)
    except pydantic.ValidationError as exc:
        console.print(f"[red]Schema not valid, found '{len(exc.errors())}' error(s)")
        for error in exc.errors():
            loc_str = [str(item) for item in error["loc"]]
            console.print(f"  '{'/'.join(loc_str)}' | {error['msg']} ({error['type']})")
        raise typer.Exit(2)

    console.print("[green]Schema is valid !!")


@app.command(name="schema")
def validate_schema(
    schema: Path,
    config_file: Path = typer.Option(config.DEFAULT_CONFIG_FILE, envvar=config.ENVVAR_CONFIG_FILE),
) -> None:
    """Validate the format of a schema file either in JSON or YAML"""

    if not config.SETTINGS:
        config.load_and_exit(config_file=config_file)

    aiorun(_schema(schema=schema))


@app.command(name="graphql-query")
def validate_graphql(
    query: str,
    variables: Optional[List[str]] = typer.Argument(
        None, help="Variables to pass along with the query. Format key=value key=value."
    ),
    debug: bool = typer.Option(False, help="Display more troubleshooting information."),
    branch: str = typer.Option(None, help="Branch on which to validate the GraphQL Query."),
    config_file: Path = typer.Option(config.DEFAULT_CONFIG_FILE, envvar=config.ENVVAR_CONFIG_FILE),
) -> None:
    """Validate the format of a GraphQL Query stored locally by executing it on a remote GraphQL endpoint"""

    if not config.SETTINGS:
        config.load_and_exit(config_file=config_file)

    console = Console()

    branch = get_branch(branch)

    try:
        query_str = find_graphql_query(query)
    except QueryNotFoundError:
        console.print(f"[red]Unable to find the GraphQL Query : {query}")
        sys.exit(1)

    console.print(f"[purple]Query '{query}' will be validated on branch '{branch}'.")

    variables_dict = parse_cli_vars(variables)

    client = initialize_client_sync()
    try:
        response = client.execute_graphql(
            query=query_str,
            branch_name=branch,
            variables=variables_dict,
            raise_for_error=False,
        )
    except GraphQLError as exc:
        console.print(f"[red]{len(exc.errors)} error(s) occured while executing the query")
        for error in exc.errors:
            if isinstance(error, dict) and "message" in error and "locations" in error:
                console.print(f"[yellow] - Message: {error['message']}")
                console.print(f"[yellow]   Location: {error['locations']}")
            elif isinstance(error, str) and "Branch:" in error:
                console.print(f"[yellow] - {error}")
                console.print("[yellow]   you can specify a different branch with --branch")
        sys.exit(1)

    console.print("[green] Query executed successfully.")

    if debug:
        console.print("-" * 40)
        console.print(f"Response for GraphQL Query {query}")
        console.print(response)
        console.print("-" * 40)
