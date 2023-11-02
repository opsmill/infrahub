import pytest

from infrahub_sdk import InfrahubNode, NodeStore

client_types = ["standard", "sync"]


@pytest.mark.parametrize("client_type", client_types)
def test_node_store_set(client_type, clients, location_schema):
    client = getattr(clients, client_type)
    data = {
        "name": {"value": "JFK1"},
        "description": {"value": "JFK Airport"},
        "type": {"value": "SITE"},
    }
    node = InfrahubNode(client=client, schema=location_schema, data=data)

    store = NodeStore()

    store.set(key="mykey", node=node)

    assert store._store["BuiltinLocation"]["mykey"]


@pytest.mark.parametrize("client_type", client_types)
def test_node_store_get(client_type, clients, location_schema):
    client = getattr(clients, client_type)
    data = {
        "id": "54f3108c-1f21-44c4-93cf-ec5737587b48",
        "name": {"value": "JFK1"},
        "description": {"value": "JFK Airport"},
        "type": {"value": "SITE"},
    }
    node = InfrahubNode(client=client, schema=location_schema, data=data)

    store = NodeStore()

    store.set(key="mykey", node=node)
    assert store.get(kind="BuiltinLocation", key="mykey").id == node.id
    assert store.get(key="mykey").id == node.id

    assert store.get(kind="BuiltinLocation", key="anotherkey", raise_when_missing=False) is None
    assert store.get(key="anotherkey", raise_when_missing=False) is None
