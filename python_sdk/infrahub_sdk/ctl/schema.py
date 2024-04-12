import asyncio
import time
from pathlib import Path
from typing import Dict, List

import typer
import yaml

try:
    from pydantic import v1 as pydantic  # type: ignore[attr-defined]
except ImportError:
    import pydantic  # type: ignore[no-redef]

from rich.console import Console

from infrahub_sdk import InfrahubClient
from infrahub_sdk.async_typer import AsyncTyper
from infrahub_sdk.ctl.client import initialize_client
from infrahub_sdk.ctl.exceptions import FileNotValidError
from infrahub_sdk.ctl.utils import init_logging
from infrahub_sdk.queries import SCHEMA_HASH_SYNC_STATUS
from infrahub_sdk.utils import find_files
from infrahub_sdk.yaml import SchemaFile

from .parameters import CONFIG_PARAM

app = AsyncTyper()


@app.callback()
def callback() -> None:
    """
    Manage the schema in a remote Infrahub instance.
    """


def load_schemas_from_disk(schemas: List[Path]) -> List[SchemaFile]:
    schemas_data: List[SchemaFile] = []
    for schema in schemas:
        if schema.is_file():
            schema_file = SchemaFile(location=schema)
            schema_file.load_content()
            schemas_data.append(schema_file)
        elif schema.is_dir():
            files = find_files(extension=["yaml", "yml", "json"], directory=schema, recursive=True)
            for item in files:
                schema_file = SchemaFile(location=item)
                schema_file.load_content()
                schemas_data.append(schema_file)
        else:
            raise FileNotValidError(name=schema, message=f"Schema path: {schema} does not exist!")

    return schemas_data


def load_schemas_from_disk_and_exit(schemas: List[Path], console: Console):
    has_error = False
    try:
        schemas_data = load_schemas_from_disk(schemas=schemas)
    except FileNotValidError as exc:
        console.print(f"[red]{exc.message}")
        raise typer.Exit(2) from exc

    for schema_file in schemas_data:
        if schema_file.valid and schema_file.content:
            continue
        console.print(f"[red]{schema_file.error_message} ({schema_file.location})")
        has_error = True

    if has_error:
        raise typer.Exit(2)

    return schemas_data


def validate_schema_content_and_exit(client: InfrahubClient, console: Console, schemas: List[SchemaFile]) -> None:
    has_error: bool = False
    for schema_file in schemas:
        try:
            client.schema.validate(data=schema_file.content)
        except pydantic.ValidationError as exc:
            console.print(f"[red]Schema not valid, found '{len(exc.errors())}' error(s) in {schema_file.location}")
            has_error = True
            for error in exc.errors():
                loc_str = [str(item) for item in error["loc"]]
                console.print(f"  '{'/'.join(loc_str)}' | {error['msg']} ({error['type']})")

    if has_error:
        raise typer.Exit(2)


def display_schema_load_errors(console: Console, response: Dict):
    console.print("[red]Unable to load the schema:")
    if "detail" in response:
        for error in response.get("detail"):
            loc_str = [str(item) for item in error["loc"][1:]]
            console.print(f"  '{'/'.join(loc_str)}' | {error['msg']} ({error['type']})")
    elif "error" in response:
        console.print(f"  {response.get('error')}")
    elif "errors" in response:
        for error in response.get("errors"):
            console.print(f"  {error.get('message')}")
    else:
        console.print(f"  '{response}'")


@app.command()
async def load(
    schemas: List[Path],
    debug: bool = False,
    branch: str = typer.Option("main", help="Branch on which to load the schema."),
    wait: int = typer.Option(0, help="Time in seconds to wait until the schema has converged across all workers"),
    _: str = CONFIG_PARAM,
) -> None:
    """Load one or multiple schema files into Infrahub."""

    init_logging(debug=debug)

    console = Console()

    schemas_data = load_schemas_from_disk_and_exit(console=console, schemas=schemas)
    schema_definition = "schema" if len(schemas_data) == 1 else "schemas"
    client = await initialize_client()
    validate_schema_content_and_exit(console=console, client=client, schemas=schemas_data)

    start_time = time.time()
    response = await client.schema.load(schemas=[item.content for item in schemas_data], branch=branch)
    loading_time = time.time() - start_time

    if response.errors:
        display_schema_load_errors(console=console, response=response.errors)
        raise typer.Exit(1)

    if response.schema_updated:
        for schema_file in schemas_data:
            console.print(f"[green] schema '{schema_file.location}' loaded successfully")
    else:
        console.print("[green] The schema in Infrahub was is already up to date, no changes were required")

    console.print(f"[green] {len(schemas_data)} {schema_definition} processed in {loading_time:.3f} seconds.")

    if response.schema_updated and wait:
        waited = 0
        continue_waiting = True
        while continue_waiting:
            status = await client.execute_graphql(query=SCHEMA_HASH_SYNC_STATUS, branch_name=branch)
            if status["InfrahubStatus"]["summary"]["schema_hash_synced"]:
                console.print("[green] Schema updated on all workers.")
                continue_waiting = False
            else:
                if waited >= wait:
                    console.print("[red] Schema is still not in sync after the specified waiting time")
                    raise typer.Exit(1)
                console.print("[yellow] Waiting for schema to sync across all workers")
                waited += 1
                await asyncio.sleep(delay=1)


@app.command()
async def check(
    schemas: List[Path],
    debug: bool = False,
    branch: str = typer.Option("main", help="Branch on which to check the schema."),
    _: str = CONFIG_PARAM,
) -> None:
    """Check if schema files are valid and what would be the impact of loading them with Infrahub."""

    init_logging(debug=debug)

    console = Console()

    schemas_data = load_schemas_from_disk_and_exit(console=console, schemas=schemas)
    client = await initialize_client()
    validate_schema_content_and_exit(console=console, client=client, schemas=schemas_data)

    success, response = await client.schema.check(schemas=[item.content for item in schemas_data], branch=branch)

    if not success:
        display_schema_load_errors(console=console, response=response)
    else:
        for schema_file in schemas_data:
            console.print(f"[green] schema '{schema_file.location}' is Valid!")
        if response == {"diff": {"added": {}, "changed": {}, "removed": {}}}:
            print("No diff")
        else:
            print(yaml.safe_dump(data=response, indent=4))
