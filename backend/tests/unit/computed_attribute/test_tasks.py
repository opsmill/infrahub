from infrahub.computed_attribute.models import ComputedAttrJinja2GraphQLResponse


async def test_computed_attribute_jinja2_parameters_serialization():
    obj = ComputedAttrJinja2GraphQLResponse(
        node_id="12345", computed_attribute_value="value", variables={"name__value": 1234}
    )

    assert obj.model_dump() == {
        "computed_attribute_value": "value",
        "node_id": "12345",
        "variables": {"name__value": 1234},
    }
