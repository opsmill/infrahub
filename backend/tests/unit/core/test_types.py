import pytest
from graphene.types.field import Field

from infrahub.core import attribute
from infrahub.graphql import types
from infrahub.types import ATTRIBUTE_TYPES


@pytest.mark.parametrize(
    "test_case",
    [pytest.param(attribute_name, id=attribute_name) for attribute_name in ATTRIBUTE_TYPES.keys()],
)
def test_attribute_types_allowed_property_path(test_case: str) -> None:
    """Validates that the get_allowed_property_in_path() method returns the correct fields for all types

    This ensures that we can use the entries properly when evaluating the schema path for instance with the
    computed attributes
    """
    attribute_type = ATTRIBUTE_TYPES[test_case]

    graphql_query_type = getattr(types, attribute_type.graphql_query)
    include_binary_address = test_case in ["IPHost", "IPNetwork"]
    path_list = _get_path_field_list(
        include_binary_address=include_binary_address, fields=graphql_query_type._meta.fields
    )
    infrahub_type: attribute.BaseAttribute = getattr(attribute, attribute_type.infrahub)
    assert path_list == infrahub_type.get_allowed_property_in_path()


def _get_path_field_list(include_binary_address: bool, fields: dict[str, Field]) -> list[str]:
    """Return list of valid property paths for the specified type"""
    excluded_fields = [
        "id",
        "is_default",
        "is_from_profile",
        "is_inherited",
        "is_protected",
        "owner",
        "source",
        "permissions",
        "updated_at",
        "updated_by",
    ]
    included = ["binary_address"] if include_binary_address else []
    for name in fields.keys():
        if name not in excluded_fields:
            included.append(name)

    return sorted(included)
