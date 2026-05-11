from infrahub.core.schema import AttributeSchema, NodeSchema, SchemaAttributePath


def test_parse_schema_path_misroutes_double_underscore_attribute() -> None:
    """An attribute named 'name__asc' is unreachable via parse_schema_path.

    parse_schema_path("name__asc__value") splits on __ producing ["name", "asc", "value"].
    It matches the 'name' attribute (not 'name__asc') and treats 'asc' as a property,
    which fails because 'asc' is not a valid attribute property.
    The 'name__asc' attribute can never be correctly resolved.
    """
    node_schema = NodeSchema(
        name="TestUnderscore",
        namespace="Test",
        attributes=[
            AttributeSchema(name="name", kind="Text"),
            AttributeSchema(name="name__asc", kind="Text"),
        ],
    )

    # Attempting to reference the name__asc attribute with its value property
    # should resolve to SchemaAttributePath with attribute_schema pointing at
    # the name__asc attribute and attribute_property_name="value".
    schema_path = node_schema.parse_schema_path(path="name__asc__value")

    name_asc_attr = node_schema.get_attribute(name="name__asc")
    assert schema_path == SchemaAttributePath(
        attribute_schema=name_asc_attr,
        attribute_property_name="value",
    )
