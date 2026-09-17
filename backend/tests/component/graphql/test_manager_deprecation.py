from typing import Any

from infrahub.core import registry
from infrahub.core.branch import Branch
from infrahub.core.schema import SchemaRoot
from infrahub.core.schema.schema_branch import SchemaBranch
from infrahub.database import InfrahubDatabase
from infrahub.graphql.manager import GraphQLSchemaManager

DEPRECATED_ATTR_MESSAGE = "old_name is deprecated, use name instead"
DEPRECATED_REL_MESSAGE = "old_owner is deprecated, use owner instead"
DEPRECATED_REL_MANY_MESSAGE = "old_crew is deprecated, use crew instead"

DEPRECATED_INPUT_FIELDS = {
    "old_name": DEPRECATED_ATTR_MESSAGE,
    "old_owner": DEPRECATED_REL_MESSAGE,
    "old_crew": DEPRECATED_REL_MANY_MESSAGE,
}


def _deprecated_fields(graphql_type: Any) -> dict[str, str]:
    """Return every field of a generated type that carries a deprecation reason, by field name."""
    return {
        name: field.deprecation_reason
        for name, field in graphql_type._meta.fields.items()
        if getattr(field, "deprecation_reason", None)
    }


DEPRECATION_SCHEMA = SchemaRoot(
    generics=[
        {
            "name": "Vessel",
            "namespace": "Testing",
            "attributes": [
                {"name": "name", "kind": "Text"},
                {"name": "old_name", "kind": "Text", "optional": True, "deprecation": DEPRECATED_ATTR_MESSAGE},
            ],
        }
    ],
    nodes=[
        {
            "name": "Owner",
            "namespace": "Testing",
            "attributes": [{"name": "name", "kind": "Text"}],
        },
        {
            "name": "Boat",
            "namespace": "Testing",
            "inherit_from": ["TestingVessel"],
            "attributes": [{"name": "length", "kind": "Number", "optional": True}],
            "relationships": [
                {
                    "name": "old_owner",
                    "peer": "TestingOwner",
                    "identifier": "boat__owner",
                    "cardinality": "one",
                    "optional": True,
                    "kind": "Attribute",
                    "deprecation": DEPRECATED_REL_MESSAGE,
                },
                {
                    "name": "old_crew",
                    "peer": "TestingOwner",
                    "identifier": "boat__crew",
                    "cardinality": "many",
                    "optional": True,
                    "kind": "Attribute",
                    "deprecation": DEPRECATED_REL_MANY_MESSAGE,
                },
            ],
        },
    ],
)


async def test_deprecation_reaches_every_generated_surface(
    db: InfrahubDatabase, default_branch: Branch, reset_graphql_schema_between_tests: None
) -> None:
    schema_branch = registry.schema.get_schema_branch(name=default_branch.name)
    schema_branch.load_schema(schema=DEPRECATION_SCHEMA)
    schema_branch.process()
    gqlm = GraphQLSchemaManager(schema=schema_branch)

    generic_schema = schema_branch.get(name="TestingVessel", duplicate=False)
    node_schema = schema_branch.get(name="TestingBoat", duplicate=False)

    interface = gqlm.generate_interface_object(schema=generic_schema, populate_cache=True).reference
    assert _deprecated_fields(interface) == {"old_name": DEPRECATED_ATTR_MESSAGE}

    node_type = gqlm.generate_graphql_object(schema=node_schema).reference
    assert _deprecated_fields(node_type) == {"old_name": DEPRECATED_ATTR_MESSAGE}

    create_input = gqlm.generate_graphql_mutation_create_input(schema=node_schema)
    assert _deprecated_fields(create_input) == DEPRECATED_INPUT_FIELDS

    update_input = gqlm.generate_graphql_mutation_update_input(schema=node_schema)
    assert _deprecated_fields(update_input) == DEPRECATED_INPUT_FIELDS

    upsert_input = gqlm.generate_graphql_mutation_upsert_input(schema=node_schema)
    assert _deprecated_fields(upsert_input) == DEPRECATED_INPUT_FIELDS


async def test_deprecated_relationship_field_on_node_type(
    db: InfrahubDatabase,
    default_branch: Branch,
    register_core_models_schema: SchemaBranch,
    reset_graphql_schema_between_tests: None,
) -> None:
    schema_branch = register_core_models_schema
    schema_branch.load_schema(schema=DEPRECATION_SCHEMA)
    schema_branch.process()
    gqlm = GraphQLSchemaManager(schema=schema_branch)
    gqlm.generate_object_types()

    node_type = gqlm.get_type(name="TestingBoat")
    assert _deprecated_fields(node_type) == {
        "old_name": DEPRECATED_ATTR_MESSAGE,
        "old_owner": DEPRECATED_REL_MESSAGE,
        "old_crew": DEPRECATED_REL_MANY_MESSAGE,
    }
