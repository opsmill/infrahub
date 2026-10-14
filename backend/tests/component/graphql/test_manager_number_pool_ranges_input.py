from typing import Any

from infrahub.core import registry
from infrahub.core.branch import Branch
from infrahub.core.constants import InfrahubKind
from infrahub.core.schema import SchemaRoot
from infrahub.core.schema.schema_branch import SchemaBranch
from infrahub.database import InfrahubDatabase
from infrahub.graphql.manager import GraphQLSchemaManager

RANGE_HOLDER_SCHEMA = SchemaRoot(
    nodes=[
        {
            "name": "RangeHolder",
            "namespace": "Testing",
            "attributes": [{"name": "name", "kind": "Text"}],
            "relationships": [
                {
                    "name": "ranges",
                    "peer": InfrahubKind.NUMBERPOOLRANGE,
                    "identifier": "rangeholder__range",
                    "cardinality": "many",
                    "optional": True,
                    "kind": "Component",
                },
            ],
        },
    ],
)


def _ranges_input_types(gqlm: GraphQLSchemaManager, kind: str) -> dict[str, str]:
    schema = registry.schema.get(name=kind, duplicate=False)
    inputs: dict[str, Any] = {
        "create": gqlm.generate_graphql_mutation_create_input(schema=schema),
        "update": gqlm.generate_graphql_mutation_update_input(schema=schema),
        "upsert": gqlm.generate_graphql_mutation_upsert_input(schema=schema),
    }
    return {name: str(input_type._meta.fields["ranges"].type) for name, input_type in inputs.items()}


async def test_only_the_number_pool_writes_its_ranges_by_value(
    db: InfrahubDatabase,
    default_branch: Branch,
    register_core_models_schema: SchemaBranch,
    reset_graphql_schema_between_tests: None,
) -> None:
    schema_branch = registry.schema.get_schema_branch(name=default_branch.name)
    schema_branch.load_schema(schema=RANGE_HOLDER_SCHEMA)
    schema_branch.process()
    gqlm = GraphQLSchemaManager(schema=schema_branch)

    assert _ranges_input_types(gqlm=gqlm, kind=InfrahubKind.NUMBERPOOL) == {
        "create": "[NumberPoolRangeInput!]",
        "update": "[NumberPoolRangeInput!]",
        "upsert": "[NumberPoolRangeInput!]",
    }
    assert _ranges_input_types(gqlm=gqlm, kind="TestingRangeHolder") == {
        "create": "[RelatedNodeInput]",
        "update": "[RelatedNodeInput]",
        "upsert": "[RelatedNodeInput]",
    }
