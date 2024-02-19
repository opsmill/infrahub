import pytest

from infrahub_sdk.query_groups import InfrahubGroupContextBase

client_types = ["standard", "sync"]


def test_set_properties():
    context = InfrahubGroupContextBase()
    context.set_properties(identifier="MYID")
    assert context.identifier == "MYID"

    context = InfrahubGroupContextBase()
    context.set_properties(identifier="MYID", params={"one": 1, "two": "two"}, delete_unused_nodes=True)
    assert context.identifier == "MYID"
    assert context.params == {"one": 1, "two": "two"}
    assert context.delete_unused_nodes is True


def test_get_params_as_str():
    context = InfrahubGroupContextBase()
    context.set_properties(identifier="MYID", params={"one": 1, "two": "two"})
    assert context._get_params_as_str() == "one: 1, two: two"

    context = InfrahubGroupContextBase()
    context.set_properties(identifier="MYID")
    with pytest.raises(ValueError):
        assert not context._get_params_as_str()


def test_generate_group_name():
    context = InfrahubGroupContextBase()
    context.set_properties(identifier="MYID")
    assert context._generate_group_name() == "MYID"

    context = InfrahubGroupContextBase()
    context.set_properties(identifier="MYID", params={"one": 1, "two": "two"})
    assert context._generate_group_name() == "MYID-d0566319e45e619bacd039299850c612"

    context = InfrahubGroupContextBase()
    context.set_properties(identifier="MYID", params={"one": 1, "two": "two"})
    assert context._generate_group_name(suffix="xxx") == "MYID-xxx-d0566319e45e619bacd039299850c612"


def test_generate_group_description(std_group_schema):
    context = InfrahubGroupContextBase()
    context.set_properties(identifier="MYID")
    assert not context._generate_group_description(schema=std_group_schema)

    context = InfrahubGroupContextBase()
    context.set_properties(identifier="MYID", params={"one": 1, "two": "two"})
    assert context._generate_group_description(schema=std_group_schema) == "one: 1, two: two"

    assert std_group_schema.attributes[1].name == "description"
    std_group_schema.attributes[1].max_length = 20
    context = InfrahubGroupContextBase()
    context.set_properties(identifier="MYID", params={"one": "xxxxxxxxxxx", "two": "yyyyyyyyyyy"})
    assert context._generate_group_description(schema=std_group_schema) == "one: xxxxxxxxxx..."
