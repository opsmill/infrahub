from __future__ import annotations

import importlib
import json
import logging
from pathlib import Path  # noqa: TC003
from typing import TYPE_CHECKING

import typer
from graphql import parse, print_ast, print_schema
from infrahub_sdk.async_typer import AsyncTyper
from rich.logging import RichHandler

from infrahub import config
from infrahub.api.schema import SchemaLoadAPI
from infrahub.core.initialization import (
    first_time_initialization,
    initialization,
)
from infrahub.core.schema import SchemaRoot, core_models, internal_schema
from infrahub.core.schema.schema_branch import SchemaBranch
from infrahub.core.utils import delete_all_nodes
from infrahub.graphql.manager import GraphQLSchemaManager
from infrahub.graphql.schema_sort import sort_schema_ast
from infrahub.log import get_logger
from infrahub.server import app as server_app

if TYPE_CHECKING:
    from infrahub.cli.context import CliContext

app = AsyncTyper()


@app.command(name="export-graphql-schema")
async def export_graphql_schema(
    ctx: typer.Context,  # noqa: ARG001
    config_file: str = typer.Option("infrahub.toml", envvar="INFRAHUB_CONFIG"),
    out: Path = typer.Option("schema.graphql"),  # noqa: B008
) -> None:
    """Export the Core GraphQL schema to a file."""

    config.load_and_exit(config_file_name=config_file)

    schema = SchemaRoot(**internal_schema)
    full_schema = schema.merge(schema=SchemaRoot(**core_models))

    schema_branch = SchemaBranch(cache={}, name="default")
    schema_branch.load_schema(schema=full_schema)

    schema_branch.process()

    gqlm = GraphQLSchemaManager(schema=schema_branch)
    gql_schema = gqlm.generate()

    schema_str = print_schema(gql_schema)
    schema_ast = parse(schema_str)
    sorted_schema_ast = sort_schema_ast(schema_ast)
    sorted_schema_str = print_ast(sorted_schema_ast)

    out.write_text(sorted_schema_str)


@app.command(name="export-json-schema")
async def export_json_schema(
    ctx: typer.Context,  # noqa: ARG001
    out: Path = typer.Option("openapi.json"),  # noqa: B008
) -> None:
    """Export the REST API OpenAPI schema to a file."""
    openapi_dict = server_app.openapi()
    openapi_dict["info"]["version"] = "latest"
    content = json.dumps(openapi_dict, indent=4)
    out.write_text(content)


@app.command(name="export-node-schema")
async def export_node_schema(
    ctx: typer.Context,  # noqa: ARG001
    config_file: str = typer.Option("infrahub.toml", envvar="INFRAHUB_CONFIG"),
    out: Path = typer.Option("develop.json"),  # noqa: B008
) -> None:
    """Export the repository configuration to a file."""
    config.load_and_exit(config_file_name=config_file)
    schema = SchemaLoadAPI.model_json_schema()
    schema["title"] = "InfrahubSchema"
    content = json.dumps(schema, indent=4)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(content)


@app.command(name="db-init")
async def database_init(
    ctx: typer.Context,
    config_file: str = typer.Option(
        "infrahub.toml", envvar="INFRAHUB_CONFIG", help="Location of the configuration file to use for Infrahub"
    ),
) -> None:
    """Erase the content of the database and initialize it with the core schema."""

    log = get_logger()

    # --------------------------------------------------
    # CLEANUP
    #  - For now we delete everything in the database
    #   TODO, if possible try to implement this in an idempotent way
    # --------------------------------------------------

    logging.getLogger("neo4j").setLevel(logging.ERROR)
    config.load_and_exit(config_file_name=config_file)

    context: CliContext = ctx.obj
    dbdriver = await context.init_db(retry=1)
    async with dbdriver.start_transaction() as db:
        log.info("Delete All Nodes")
        await delete_all_nodes(db=db)
        await first_time_initialization(db=db)

    await dbdriver.close()


@app.command(name="load-test-data")
async def load_test_data(
    ctx: typer.Context,
    config_file: str = typer.Option(
        "infrahub.toml", envvar="INFRAHUB_CONFIG", help="Location of the configuration file to use for Infrahub"
    ),
    dataset: str = "dataset01",
) -> None:
    """Load test data into the database from the `test_data` directory."""

    logging.getLogger("neo4j").setLevel(logging.ERROR)
    config.load_and_exit(config_file_name=config_file)

    context: CliContext = ctx.obj
    dbdriver = await context.init_db(retry=1)

    async with dbdriver.start_session() as db:
        await initialization(db=db)

        log_level = "DEBUG"

        FORMAT = "%(message)s"
        logging.basicConfig(level=log_level, format=FORMAT, datefmt="[%X]", handlers=[RichHandler()])
        logging.getLogger("infrahub")

        dataset_module = importlib.import_module(f"infrahub.test_data.{dataset}")
        await dataset_module.load_data(db=db)

    await dbdriver.close()
