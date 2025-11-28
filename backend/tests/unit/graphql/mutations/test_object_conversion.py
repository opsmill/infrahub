from __future__ import annotations

from typing import TYPE_CHECKING, Any

from infrahub_sdk.convert_object_type import ConversionFieldInput, ConversionFieldValue

from infrahub.core.node import Node
from infrahub.core.registry import registry
from infrahub.core.schema import SchemaRoot
from infrahub.graphql.initialization import prepare_graphql_params
from infrahub.graphql.mutations.convert_object_type import _filter_none_values_from_data
from tests.helpers.graphql import graphql

if TYPE_CHECKING:
    from infrahub.core.branch import Branch
    from infrahub.database import InfrahubDatabase


class TestFilterNoneValuesFromData:
    """Tests for the _filter_none_values_from_data helper function."""

    def test_source_field_unchanged(self) -> None:
        """Test that source_field input is unchanged."""
        input_dict = {"source_field": "name"}
        result = _filter_none_values_from_data(input_dict)
        assert result == {"source_field": "name"}

    def test_use_default_value_unchanged(self) -> None:
        """Test that use_default_value input is unchanged."""
        input_dict = {"use_default_value": True}
        result = _filter_none_values_from_data(input_dict)
        assert result == {"use_default_value": True}

    def test_data_with_valid_value_unchanged(self) -> None:
        """Test that data with a valid attribute_value is unchanged."""
        input_dict = {"data": {"attribute_value": "test"}}
        result = _filter_none_values_from_data(input_dict)
        assert result == {"data": {"attribute_value": "test"}}

    def test_data_with_none_attribute_value_filtered(self) -> None:
        """Test that data with null attribute_value is filtered out.

        This is the key bug fix case - UI sends {"data": {"attribute_value": null}}
        which would cause a validation error.
        """
        input_dict = {"data": {"attribute_value": None}}
        result = _filter_none_values_from_data(input_dict)
        assert result is None

    def test_data_with_valid_peer_id_unchanged(self) -> None:
        """Test that data with a valid peer_id is unchanged."""
        input_dict = {"data": {"peer_id": "123"}}
        result = _filter_none_values_from_data(input_dict)
        assert result == {"data": {"peer_id": "123"}}

    def test_data_with_valid_peers_ids_unchanged(self) -> None:
        """Test that data with a valid peers_ids is unchanged."""
        input_dict = {"data": {"peers_ids": ["123", "456"]}}
        result = _filter_none_values_from_data(input_dict)
        assert result == {"data": {"peers_ids": ["123", "456"]}}

    def test_data_with_empty_peers_ids_unchanged(self) -> None:
        """Test that data with an empty peers_ids list is unchanged."""
        input_dict = {"data": {"peers_ids": []}}
        result = _filter_none_values_from_data(input_dict)
        assert result == {"data": {"peers_ids": []}}

    def test_data_with_multiple_none_values_filtered(self) -> None:
        """Test that all None values in data are filtered."""
        input_dict = {"data": {"attribute_value": None, "peer_id": None}}
        result = _filter_none_values_from_data(input_dict)
        assert result is None

    def test_data_with_mixed_none_and_value_keeps_value(self) -> None:
        """Test that non-None values are kept when there are also None values."""
        input_dict = {"data": {"attribute_value": None, "peer_id": "123"}}
        result = _filter_none_values_from_data(input_dict)
        assert result == {"data": {"peer_id": "123"}}

    def test_non_dict_input_unchanged(self) -> None:
        """Test that non-dict input is returned unchanged."""
        input_val = "not a dict"
        result = _filter_none_values_from_data(input_val)  # type: ignore
        assert result == "not a dict"

    def test_empty_dict_returns_none(self) -> None:
        """Test that an empty dict returns None."""
        result = _filter_none_values_from_data({})
        assert result is None


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
