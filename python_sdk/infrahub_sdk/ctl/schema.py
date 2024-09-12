import asyncio
import time
from pathlib import Path
from typing import Any, Optional

import typer
import yaml
from pydantic import ValidationError
from rich.console import Console

from infrahub_sdk import InfrahubClient
from infrahub_sdk.async_typer import AsyncTyper
from infrahub_sdk.ctl.client import initialize_client
from infrahub_sdk.ctl.exceptions import FileNotValidError
from infrahub_sdk.ctl.utils import catch_exception, init_logging
from infrahub_sdk.queries import SCHEMA_HASH_SYNC_STATUS
from infrahub_sdk.utils import find_files
from infrahub_sdk.yaml import SchemaFile

from .parameters import CONFIG_PARAM

app = AsyncTyper()
console = Console()


@app.callback()
def callback() -> None:
    """
    Manage the schema in a remote Infrahub instance.
    """


def load_schemas_from_disk(schemas: list[Path]) -> list[SchemaFile]:
    schemas_data: list[SchemaFile] = []
    for schema in schemas:
        if schema.is_file():
            schema_file = SchemaFile(location=schema)
            schema_file.load_content()
            schemas_data.append(schema_file)
        elif schema.is_dir():
            files = find_files(extension=["yaml", "yml", "json"], directory=schema)
            for item in files:
                schema_file = SchemaFile(location=item)
                schema_file.load_content()
                schemas_data.append(schema_file)
        else:
            raise FileNotValidError(name=schema, message=f"Schema path: {schema} does not exist!")

    return schemas_data


def load_schemas_from_disk_and_exit(schemas: list[Path]) -> list[SchemaFile]:
    has_error = False
    try:
        schemas_data = load_schemas_from_disk(schemas=schemas)
    except FileNotValidError as exc:
        console.print(f"[red]{exc.message}")
        raise typer.Exit(1) from exc

    for schema_file in schemas_data:
        if schema_file.valid and schema_file.content:
            continue
        console.print(f"[red]{schema_file.error_message} ({schema_file.location})")
        has_error = True

    if has_error:
        raise typer.Exit(1)

    return schemas_data


def validate_schema_content_and_exit(client: InfrahubClient, schemas: list[SchemaFile]) -> None:
    has_error: bool = False
    for schema_file in schemas:
        try:
            client.schema.validate(data=schema_file.content)
        except ValidationError as exc:
            console.print(f"[red]Schema not valid, found '{len(exc.errors())}' error(s) in {schema_file.location}")
            has_error = True
            for error in exc.errors():
                loc_str = [str(item) for item in error["loc"]]
                console.print(f"  '{'/'.join(loc_str)}' | {error['msg']} ({error['type']})")

    if has_error:
        raise typer.Exit(1)


def display_schema_load_errors(response: dict[str, Any], schemas_data: list[dict]) -> None:
    console.print("[red]Unable to load the schema:")
    if "detail" not in response:
        handle_non_detail_errors(response=response)
        return

    for error in response["detail"]:
        loc_path = error.get("loc", [])
        if not valid_error_path(loc_path=loc_path):
            continue

        # if the len of the path is equal to 6, the error is at the root of the object
        # if the len of the path is higher than 6, the error is in an attribute or a relationships
        schema_index = int(loc_path[2])
        node_index = int(loc_path[4])
        node = get_node(schemas_data=schemas_data, schema_index=schema_index, node_index=node_index)

        if not node:
            console.print("Node data not found.")
            continue

        if len(loc_path) == 6:
            loc_type = loc_path[-1]
            input_str = error.get("input", None)
            error_message = f"{loc_type} ({input_str}) | {error['msg']} ({error['type']})"
            console.print(f"  Node: {node.get('namespace', None)}{node.get('name', None)} | {error_message}")

        elif len(loc_path) > 6:
            loc_type = loc_path[5]
            input_label = node[loc_type][loc_path[6]].get("name", None)
            input_str = error.get("input", None)
            error_message = f"{loc_type[:-1].title()}: {input_label} ({input_str}) | {error['msg']} ({error['type']})"
            console.print(f"  Node: {node.get('namespace', None)}{node.get('name', None)} | {error_message}")


def handle_non_detail_errors(response: dict[str, Any]) -> None:
    if "error" in response:
        console.print(f"  {response.get('error')}")
    elif "errors" in response:
        for error in response.get("errors"):
            console.print(f"  {error.get('message')}")
    else:
        console.print(f"  '{response}'")


def valid_error_path(loc_path: list[Any]) -> bool:
    return len(loc_path) >= 6 and loc_path[0] == "body" and loc_path[1] == "schemas"


def get_node(schemas_data: list[dict], schema_index: int, node_index: int) -> Optional[dict]:
    if schema_index < len(schemas_data) and node_index < len(schemas_data[schema_index].content["nodes"]):
        return schemas_data[schema_index].content["nodes"][node_index]
    return None


@app.command()
@catch_exception(console=console)
async def load(
    schemas: list[Path],
    debug: bool = False,
    branch: str = typer.Option("main", help="Branch on which to load the schema."),
    wait: int = typer.Option(0, help="Time in seconds to wait until the schema has converged across all workers"),
    _: str = CONFIG_PARAM,
) -> None:
    """Load one or multiple schema files into Infrahub."""

    init_logging(debug=debug)

    schemas_data = load_schemas_from_disk_and_exit(schemas=schemas)
    schema_definition = "schema" if len(schemas_data) == 1 else "schemas"
    client = await initialize_client()
    validate_schema_content_and_exit(client=client, schemas=schemas_data)

    start_time = time.time()
    response = await client.schema.load(schemas=[item.content for item in schemas_data], branch=branch)
    loading_time = time.time() - start_time

    if response.errors:
        display_schema_load_errors(response=response.errors, schemas_data=schemas_data)
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
@catch_exception(console=console)
async def check(
    schemas: list[Path],
    debug: bool = False,
    branch: str = typer.Option("main", help="Branch on which to check the schema."),
    _: str = CONFIG_PARAM,
) -> None:
    """Check if schema files are valid and what would be the impact of loading them with Infrahub."""

    init_logging(debug=debug)

    schemas_data = load_schemas_from_disk_and_exit(schemas=schemas)
    client = await initialize_client()
    validate_schema_content_and_exit(client=client, schemas=schemas_data)

    success, response = await client.schema.check(schemas=[item.content for item in schemas_data], branch=branch)

    if not success:
        display_schema_load_errors(response=response, schemas_data=schemas_data)
    else:
        for schema_file in schemas_data:
            console.print(f"[green] schema '{schema_file.location}' is Valid!")
        if response == {"diff": {"added": {}, "changed": {}, "removed": {}}}:
            print("No diff")
        else:
            print(yaml.safe_dump(data=response, indent=4))
