from __future__ import annotations

from typing import TYPE_CHECKING, Any

from infrahub_sdk.convert_object_type import ConversionFieldInput, ConversionFieldValue

from infrahub.core.node import Node
from infrahub.core.registry import registry
from infrahub.core.schema import SchemaRoot
from infrahub.graphql.initialization import prepare_graphql_params
from tests.helpers.graphql import graphql

if TYPE_CHECKING:
    from infrahub.core.branch import Branch
    from infrahub.database import InfrahubDatabase


async def test_convert_object_type_with_profile_error(
    db: InfrahubDatabase, schemas_conversion: dict[str, Any], default_branch: Branch
) -> None:
    """Test that converting an object type with a profile returns the appropriate error message."""

    schema = SchemaRoot(**schemas_conversion)
    registry.schema.register_schema(schema=schema, branch=default_branch.name)

    person1_profile = await Node.init(db=db, schema="ProfileTestconvPerson1")
    await person1_profile.new(db=db, profile_name="person1-profile", profile_priority=10, height=175)
    await person1_profile.save(db=db)

    default_branch.update_schema_hash()
    gql_params = await prepare_graphql_params(db=db, branch=default_branch)

    create_person_mutation = f"""
    mutation {{
        TestconvPerson1Create(data: {{
            name: {{value: "John"}},
            profiles: [{{id: "{person1_profile.id}"}}]
        }}) {{
            ok
            object {{
                id
            }}
        }}
    }}
    """

    create_result = await graphql(
        schema=gql_params.schema,
        source=create_person_mutation,
        context_value=gql_params.context,
        root_value=None,
        variable_values={},
    )

    assert create_result.errors is None
    assert create_result.data
    assert create_result.data["TestconvPerson1Create"]["ok"] is True
    person1_node_id = create_result.data["TestconvPerson1Create"]["object"]["id"]

    mapping = {
        "name": ConversionFieldInput(source_field="name"),
        "age": ConversionFieldInput(data=ConversionFieldValue(attribute_value=30)),
    }
    mapping_dict = {field_name: model.model_dump(mode="json") for field_name, model in mapping.items()}

    result = await graphql(
        schema=gql_params.schema,
        source=CONVERT_OBJECT_TYPE_MUTATION,
        context_value=gql_params.context,
        root_value=None,
        variable_values={
            "node_id": person1_node_id,
            "target_kind": "TestconvPerson2",
            "fields_mapping": mapping_dict,
        },
    )

    assert result.errors
    assert (
        "The attribute 'height' is from a profile, converting objects that use profiles is not yet supported."
        in str(result.errors)
    )


CONVERT_OBJECT_TYPE_MUTATION = """
mutation ConvertObjectType(
    $node_id: String!
    $target_kind: String!
    $fields_mapping: GenericScalar!
) {
    ConvertObjectType(data: {
        node_id: $node_id,
        target_kind: $target_kind,
        fields_mapping: $fields_mapping
    }) {
        ok
        node
    }
}
"""
