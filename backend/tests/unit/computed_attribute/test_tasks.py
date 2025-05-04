from infrahub_sdk.template import Jinja2Template

from infrahub.computed_attribute.models import ComputedAttrJinja2GraphQLResponse
from infrahub.computed_attribute.tasks import computed_attribute_jinja2_update_value


async def test_computed_attribute_jinja2_update_value():
    parameters = {
        "branch_name": "main",
        "obj": ComputedAttrJinja2GraphQLResponse(
            node_id="12345", computed_attribute_value="value", variables={"name__value": 1234}
        ),
        "node_kind": "TestingTag",
        "attribute_name": "name",
        "template": Jinja2Template(template="Value is {{ name__value }}"),
    }

    clean_parameters = computed_attribute_jinja2_update_value.serialize_parameters(parameters)
    assert clean_parameters == {
        "attribute_name": "name",
        "branch_name": "main",
        "node_kind": "TestingTag",
        "obj": {
            "computed_attribute_value": "value",
            "node_id": "12345",
            "variables": {"name__value": 1234},
        },
        "template": {
            "filters": None,
            "template": "Value is {{ name__value }}",
            "template_directory": None,
        },
    }
