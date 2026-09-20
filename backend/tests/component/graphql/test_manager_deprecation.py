from typing import Any

from infrahub.core import registry
from infrahub.core.branch import Branch
from infrahub.core.constants.schema import PARENT_CHILD_IDENTIFIER
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


DEPRECATED_HIERARCHY_PARENT_MESSAGE = "parent is deprecated, use region instead"
DEPRECATED_HIERARCHY_CHILDREN_MESSAGE = "children is deprecated, use sites instead"

HIERARCHY_DEPRECATION_SCHEMA = SchemaRoot(
    generics=[
        {
            "name": "Place",
            "namespace": "Testing",
            "hierarchical": True,
            "attributes": [{"name": "name", "kind": "Text"}],
        }
    ],
    nodes=[
        {
            "name": "Region",
            "namespace": "Testing",
            "hierarchy": "TestingPlace",
            "attributes": [{"name": "name", "kind": "Text"}],
            "relationships": [
                {
                    "name": "parent",
                    "peer": "TestingPlace",
                    "identifier": PARENT_CHILD_IDENTIFIER,
                    "kind": "Hierarchy",
                    "cardinality": "one",
                    "direction": "outbound",
                    "optional": True,
                    "deprecation": DEPRECATED_HIERARCHY_PARENT_MESSAGE,
                },
                {
                    "name": "children",
                    "peer": "TestingPlace",
                    "identifier": PARENT_CHILD_IDENTIFIER,
                    "kind": "Hierarchy",
                    "cardinality": "many",
                    "direction": "inbound",
                    "optional": True,
                    "deprecation": DEPRECATED_HIERARCHY_CHILDREN_MESSAGE,
                },
            ],
        }
    ],
)


async def test_deprecated_hierarchy_relationships_on_node_type(
    db: InfrahubDatabase,
    default_branch: Branch,
    register_core_models_schema: SchemaBranch,
    reset_graphql_schema_between_tests: None,
) -> None:
    """The hierarchy fields are rebuilt away from the relationship loop and carry the reason all the same."""
    schema_branch = register_core_models_schema
    schema_branch.load_schema(schema=HIERARCHY_DEPRECATION_SCHEMA)
    schema_branch.process()
    gqlm = GraphQLSchemaManager(schema=schema_branch)
    gqlm.generate_object_types()

    node_type = gqlm.get_type(name="TestingRegion")
    assert _deprecated_fields(node_type) == {
        "parent": DEPRECATED_HIERARCHY_PARENT_MESSAGE,
        "children": DEPRECATED_HIERARCHY_CHILDREN_MESSAGE,
    }


DEPRECATED_GENERIC_HIERARCHY_PARENT_MESSAGE = "parent is deprecated, use zone instead"
DEPRECATED_GENERIC_HIERARCHY_CHILDREN_MESSAGE = "children is deprecated, use spots instead"

GENERIC_HIERARCHY_DEPRECATION_SCHEMA = SchemaRoot(
    generics=[
        {
            "name": "Spot",
            "namespace": "Testing",
            "hierarchical": True,
            "attributes": [{"name": "name", "kind": "Text"}],
            "relationships": [
                {
                    "name": "parent",
                    "peer": "TestingSpot",
                    "identifier": PARENT_CHILD_IDENTIFIER,
                    "kind": "Hierarchy",
                    "cardinality": "one",
                    "direction": "outbound",
                    "optional": True,
                    "deprecation": DEPRECATED_GENERIC_HIERARCHY_PARENT_MESSAGE,
                },
                {
                    "name": "children",
                    "peer": "TestingSpot",
                    "identifier": PARENT_CHILD_IDENTIFIER,
                    "kind": "Hierarchy",
                    "cardinality": "many",
                    "direction": "inbound",
                    "optional": True,
                    "deprecation": DEPRECATED_GENERIC_HIERARCHY_CHILDREN_MESSAGE,
                },
            ],
        }
    ],
    nodes=[
        {
            "name": "Zone",
            "namespace": "Testing",
            "hierarchy": "TestingSpot",
            "inherit_from": ["TestingSpot"],
            "attributes": [{"name": "name", "kind": "Text"}],
        }
    ],
)


async def test_deprecated_hierarchy_relationships_on_generic_interface(
    db: InfrahubDatabase,
    default_branch: Branch,
    register_core_models_schema: SchemaBranch,
    reset_graphql_schema_between_tests: None,
) -> None:
    """A hierarchical generic carries its own parent and children deprecation on the interface."""
    schema_branch = register_core_models_schema
    schema_branch.load_schema(schema=GENERIC_HIERARCHY_DEPRECATION_SCHEMA)
    schema_branch.process()
    gqlm = GraphQLSchemaManager(schema=schema_branch)
    gqlm.generate_object_types()

    interface = gqlm.get_type(name="TestingSpot")
    assert _deprecated_fields(interface) == {
        "parent": DEPRECATED_GENERIC_HIERARCHY_PARENT_MESSAGE,
        "children": DEPRECATED_GENERIC_HIERARCHY_CHILDREN_MESSAGE,
    }


DEPRECATED_INHERITED_REL_MESSAGE = "old_pilot is deprecated, use pilot instead"
DEPRECATED_INHERITED_REL_MANY_MESSAGE = "old_fleet is deprecated, use fleet instead"

DEPRECATED_INHERITED_FIELDS = {
    "old_pilot": DEPRECATED_INHERITED_REL_MESSAGE,
    "old_fleet": DEPRECATED_INHERITED_REL_MANY_MESSAGE,
}

INHERITED_RELATIONSHIP_DEPRECATION_SCHEMA = SchemaRoot(
    generics=[
        {
            "name": "Aircraft",
            "namespace": "Testing",
            "attributes": [{"name": "name", "kind": "Text"}],
            "relationships": [
                {
                    "name": "old_pilot",
                    "peer": "TestingCrew",
                    "identifier": "aircraft__pilot",
                    "cardinality": "one",
                    "optional": True,
                    "kind": "Attribute",
                    "deprecation": DEPRECATED_INHERITED_REL_MESSAGE,
                },
                {
                    "name": "old_fleet",
                    "peer": "TestingCrew",
                    "identifier": "aircraft__fleet",
                    "cardinality": "many",
                    "optional": True,
                    "kind": "Attribute",
                    "deprecation": DEPRECATED_INHERITED_REL_MANY_MESSAGE,
                },
            ],
        }
    ],
    nodes=[
        {
            "name": "Crew",
            "namespace": "Testing",
            "attributes": [{"name": "name", "kind": "Text"}],
        },
        {
            "name": "Plane",
            "namespace": "Testing",
            "inherit_from": ["TestingAircraft"],
            "attributes": [{"name": "wings", "kind": "Number", "optional": True}],
        },
    ],
)


async def test_deprecated_relationship_declared_on_a_generic(
    db: InfrahubDatabase,
    default_branch: Branch,
    register_core_models_schema: SchemaBranch,
    reset_graphql_schema_between_tests: None,
) -> None:
    """A relationship deprecated on a generic carries the reason on the interface and on each heir."""
    schema_branch = register_core_models_schema
    schema_branch.load_schema(schema=INHERITED_RELATIONSHIP_DEPRECATION_SCHEMA)
    schema_branch.process()
    gqlm = GraphQLSchemaManager(schema=schema_branch)
    gqlm.generate_object_types()

    assert _deprecated_fields(gqlm.get_type(name="TestingAircraft")) == DEPRECATED_INHERITED_FIELDS
    assert _deprecated_fields(gqlm.get_type(name="TestingPlane")) == DEPRECATED_INHERITED_FIELDS

    node_schema = schema_branch.get(name="TestingPlane", duplicate=False)
    for input_type in (
        gqlm.generate_graphql_mutation_create_input(schema=node_schema),
        gqlm.generate_graphql_mutation_update_input(schema=node_schema),
        gqlm.generate_graphql_mutation_upsert_input(schema=node_schema),
    ):
        assert _deprecated_fields(input_type) == DEPRECATED_INHERITED_FIELDS
