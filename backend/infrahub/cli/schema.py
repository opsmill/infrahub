from __future__ import annotations

from pathlib import Path  # noqa: TC003

import typer
from graphql import parse, print_ast, print_schema
from infrahub_sdk.async_typer import AsyncTyper

from infrahub import config
from infrahub.core.schema import SchemaRoot, core_models, internal_schema
from infrahub.core.schema.schema_branch import SchemaBranch
from infrahub.graphql.manager import GraphQLSchemaManager
from infrahub.graphql.schema_sort import sort_schema_ast

app = AsyncTyper()


@app.command(name="export-graphql-schema")
async def export_graphql_schema(
    ctx: typer.Context,  # noqa: ARG001
    config_file: str = typer.Option("infrahub.toml", envvar="INFRAHUB_CONFIG"),  # noqa: ARG001
    out: Path = typer.Option("schema.graphql"),  # noqa: B008
) -> None:
    """Export the GraphQL schema to a file."""

    config.load_and_exit()

    schema = SchemaRoot(**internal_schema)
    full_schema = schema.merge(schema=SchemaRoot(**core_models))

    schema_branch = SchemaBranch(cache={}, name="default")
    schema_branch.load_schema(schema=full_schema)

    schema_branch.process()

    gqlm = GraphQLSchemaManager(schema=schema_branch)
    gql_schema = gqlm.generate(
        include_query=True,
        include_mutation=True,
        include_subscription=True,
        include_types=True,
    )

    schema_str = print_schema(gql_schema)
    schema_ast = parse(schema_str)
    sorted_schema_ast = sort_schema_ast(schema_ast)
    sorted_schema_str = print_ast(sorted_schema_ast)

    out.write_text(sorted_schema_str)
