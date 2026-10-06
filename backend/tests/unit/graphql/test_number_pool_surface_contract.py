from __future__ import annotations

from pathlib import Path

import pytest
from graphql import (
    DocumentNode,
    InputObjectTypeDefinitionNode,
    ObjectTypeDefinitionNode,
    TypeDefinitionNode,
    parse,
    print_ast,
    print_schema,
)

from infrahub.core.schema import SchemaRoot, core_models, internal_schema
from infrahub.core.schema.schema_branch import SchemaBranch
from infrahub.graphql.manager import GraphQLSchemaManager
from infrahub.graphql.schema_sort import sort_schema_ast

EXPECTED_SDL_PATH = Path(__file__).parent / "snapshots" / "number_pool_surface.graphql"

SURFACE_TYPES = (
    "NumberPoolAllocation",
    "NumberPoolAllocations",
    "NumberPoolDivision",
    "NumberPoolDivisionEntry",
    "NumberPoolDivisionEntryInput",
    "NumberPoolDivisions",
    "NumberPoolHolder",
    "NumberPoolProvenance",
    "NumberPoolRangeRef",
    "NumberPoolRangeUtilization",
    "NumberPoolUtilization",
    "NumberPoolUtilizationFigures",
)
SURFACE_ROOT_FIELDS = (
    "InfrahubNumberPoolAllocations",
    "InfrahubNumberPoolDivisions",
    "InfrahubNumberPoolUtilization",
)
NUMBER_POOL_INPUTS = ("CoreNumberPoolCreateInput", "CoreNumberPoolUpdateInput", "CoreNumberPoolUpsertInput")
SCOPE_FIELD = "allocation_scope"


@pytest.fixture(scope="module")
def sorted_core_sdl() -> DocumentNode:
    schema_branch = SchemaBranch(cache={}, name="default")
    schema_branch.load_schema(schema=SchemaRoot(**internal_schema).merge(schema=SchemaRoot(**core_models)))
    schema_branch.process()
    graphql_schema = GraphQLSchemaManager(schema=schema_branch).generate()
    return sort_schema_ast(parse(print_schema(graphql_schema)))


def _surface_sdl(document: DocumentNode) -> str:
    definitions: dict[str, TypeDefinitionNode] = {
        definition.name.value: definition
        for definition in document.definitions
        if isinstance(definition, TypeDefinitionNode)
    }
    selected: list[TypeDefinitionNode] = [definitions[name] for name in SURFACE_TYPES]

    query = definitions["Query"]
    assert isinstance(query, ObjectTypeDefinitionNode)
    root_fields = tuple(field for field in query.fields or () if field.name.value in SURFACE_ROOT_FIELDS)
    selected.append(ObjectTypeDefinitionNode(name=query.name, fields=root_fields, interfaces=(), directives=()))

    for name in NUMBER_POOL_INPUTS:
        pool_input = definitions[name]
        assert isinstance(pool_input, InputObjectTypeDefinitionNode)
        scope_fields = tuple(field for field in pool_input.fields or () if field.name.value == SCOPE_FIELD)
        selected.append(InputObjectTypeDefinitionNode(name=pool_input.name, fields=scope_fields, directives=()))

    return print_ast(DocumentNode(definitions=tuple(selected))) + "\n"


def test_number_pool_surface_sdl_matches_the_published_contract(sorted_core_sdl: DocumentNode) -> None:
    """Any rename, retype, removal or description change of the published surface must update the snapshot."""
    assert _surface_sdl(sorted_core_sdl) == EXPECTED_SDL_PATH.read_text()
