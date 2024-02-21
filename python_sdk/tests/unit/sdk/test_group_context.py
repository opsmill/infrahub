import inspect

import pytest

from infrahub_sdk.query_groups import InfrahubGroupContext, InfrahubGroupContextBase, InfrahubGroupContextSync

async_methods = [method for method in dir(InfrahubGroupContext) if not method.startswith("_")]
sync_methods = [method for method in dir(InfrahubGroupContextSync) if not method.startswith("_")]

client_types = ["standard", "sync"]


async def test_method_sanity():
    """Validate that there is at least one public method and that both clients look the same."""
    assert async_methods
    assert async_methods == sync_methods


@pytest.mark.parametrize("method", async_methods)
async def test_validate_method_signature(method, replace_sync_return_annotation, replace_async_return_annotation):
    async_method = getattr(InfrahubGroupContext, method)
    sync_method = getattr(InfrahubGroupContextSync, method)
    async_sig = inspect.signature(async_method)
    sync_sig = inspect.signature(sync_method)
    assert async_sig.parameters == sync_sig.parameters
    assert async_sig.return_annotation == replace_sync_return_annotation(sync_sig.return_annotation)
    assert replace_async_return_annotation(async_sig.return_annotation) == sync_sig.return_annotation


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
