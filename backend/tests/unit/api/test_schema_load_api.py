import pytest

from infrahub.api.schema import SchemaLoadAPI
from infrahub.core.constants import RelationshipDeleteBehavior


@pytest.fixture
def simple_schema():
    return {
        "version": "0.9",
        "nodes": [
            {
                "name": "Criticality",
                "namespace": "Builtin",
                "default_filter": "name__value",
                "attributes": [
                    {"name": "name", "kind": "Text", "unique": True},
                    {"name": "level", "kind": "Number"},
                ],
                "relationships": [
                    {
                        "name": "tags",
                        "peer": "BuiltinTag",
                        "label": "Tags",
                        "optional": True,
                        "kind": "Component",
                        "cardinality": "many",
                    },
                ],
            },
            {
                "name": "Tag",
                "namespace": "Builtin",
                "label": "Tag",
                "default_filter": "name__value",
                "attributes": [
                    {"name": "name", "kind": "Text", "label": "Name", "unique": True},
                ],
                "relationships": [
                    {
                        "name": "criticalities",
                        "peer": "BuiltinCriticality",
                        "label": "Criticalities",
                        "optional": True,
                        "cardinality": "many",
                    },
                ],
            },
        ],
    }


def _get_schema_by_name(schema: SchemaLoadAPI, schema_kind):
    for node_schema in schema.nodes + schema.generics:
        if node_schema.kind == schema_kind:
            return node_schema
    raise ValueError(f"Schema {schema_kind} not found")


async def test_component_on_delete_set_to_default(simple_schema):
    schema = SchemaLoadAPI(**simple_schema)

    criticality_schema = _get_schema_by_name(schema, "BuiltinCriticality")
    tags_relationship = criticality_schema.get_relationship("tags")
    assert tags_relationship.on_delete == RelationshipDeleteBehavior.CASCADE


async def test_component_on_delete_can_be_overridden(simple_schema):
    simple_schema["nodes"][0]["relationships"][0]["on_delete"] = RelationshipDeleteBehavior.NO_ACTION.value

    schema = SchemaLoadAPI(**simple_schema)

    criticality_schema = _get_schema_by_name(schema, "BuiltinCriticality")
    tags_relationship = criticality_schema.get_relationship("tags")
    assert tags_relationship.on_delete == RelationshipDeleteBehavior.NO_ACTION


async def test_component_on_delete_defaults_to_no_action_for_generic_relationships(simple_schema):
    schema = SchemaLoadAPI(**simple_schema)

    tag_schema = _get_schema_by_name(schema, "BuiltinTag")
    criticalities_relationship = tag_schema.get_relationship("criticalities")
    assert criticalities_relationship.on_delete == RelationshipDeleteBehavior.NO_ACTION
