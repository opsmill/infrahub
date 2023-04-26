import inspect

import pytest

from infrahub_client.node import (
    InfrahubNode,
    InfrahubNodeSync,
    RelatedNodeBase,
    RelationshipManagerBase,
)

# pylint: disable=no-member

async_node_methods = [method for method in dir(InfrahubNode) if not method.startswith("_")]
sync_node_methods = [method for method in dir(InfrahubNodeSync) if not method.startswith("_")]

client_types = ["standard", "sync"]


async def test_method_sanity():
    """Validate that there is at least one public method and that both clients look the same."""
    assert async_node_methods
    assert async_node_methods == sync_node_methods


@pytest.mark.parametrize("method", async_node_methods)
async def test_validate_method_signature(method):
    async_method = getattr(InfrahubNode, method)
    sync_method = getattr(InfrahubNodeSync, method)
    async_sig = inspect.signature(async_method)
    sync_sig = inspect.signature(sync_method)
    assert async_sig.parameters == sync_sig.parameters
    assert async_sig.return_annotation == sync_sig.return_annotation


@pytest.mark.parametrize("client_type", client_types)
async def test_init_node_no_data(client, location_schema, client_type):
    if client_type == "standard":
        node = InfrahubNode(client=client, schema=location_schema)
    else:
        node = InfrahubNodeSync(client=client, schema=location_schema)
    assert sorted(node._attributes) == ["description", "name", "type"]

    assert hasattr(node, "name")
    assert hasattr(node, "description")
    assert hasattr(node, "type")


@pytest.mark.parametrize("client_type", client_types)
async def test_init_node_data(client, location_schema, client_type):
    data = {"name": {"value": "JFK1"}, "description": {"value": "JFK Airport"}, "type": {"value": "SITE"}}
    if client_type == "standard":
        node = InfrahubNode(client=client, schema=location_schema, data=data)
    else:
        node = InfrahubNodeSync(client=client, schema=location_schema, data=data)

    assert node.name.value == "JFK1"
    assert node.name.is_protected is None
    assert node.description.value == "JFK Airport"
    assert node.type.value == "SITE"


@pytest.mark.parametrize("client_type", client_types)
async def test_init_node_data_with_relationships(client, location_schema, client_type):
    data = {
        "name": {"value": "JFK1"},
        "description": {"value": "JFK Airport"},
        "type": {"value": "SITE"},
        "primary_tag": "pppppppp",
        "tags": [{"id": "aaaaaa"}, {"id": "bbbb"}],
    }
    if client_type == "standard":
        node = InfrahubNode(client=client, schema=location_schema, data=data)
    else:
        node = InfrahubNodeSync(client=client, schema=location_schema, data=data)

    assert node.name.value == "JFK1"
    assert node.name.is_protected is None
    assert node.description.value == "JFK Airport"
    assert node.type.value == "SITE"

    assert isinstance(node.tags, RelationshipManagerBase)
    assert len(node.tags.peers) == 2
    assert isinstance(node.tags.peers[0], RelatedNodeBase)
    assert isinstance(node.primary_tag, RelatedNodeBase)
    assert node.primary_tag.id == "pppppppp"


@pytest.mark.parametrize("client_type", client_types)
async def test_query_data_no_filters(client, location_schema, client_type):
    if client_type == "standard":
        node = InfrahubNode(client=client, schema=location_schema)
    else:
        node = InfrahubNodeSync(client=client, schema=location_schema)

    assert node.generate_query_data() == {
        "location": {
            "id": None,
            "display_label": None,
            "name": {
                "is_protected": None,
                "is_visible": None,
                "owner": {"__typename": None, "display_label": None, "id": None},
                "source": {"__typename": None, "display_label": None, "id": None},
                "value": None,
            },
            "description": {
                "is_protected": None,
                "is_visible": None,
                "owner": {"__typename": None, "display_label": None, "id": None},
                "source": {"__typename": None, "display_label": None, "id": None},
                "value": None,
            },
            "type": {
                "is_protected": None,
                "is_visible": None,
                "owner": {"__typename": None, "display_label": None, "id": None},
                "source": {"__typename": None, "display_label": None, "id": None},
                "value": None,
            },
            "primary_tag": {
                "id": None,
                "display_label": None,
                "__typename": None,
                "_relation__is_protected": None,
                "_relation__is_visible": None,
                "_relation__owner": {
                    "__typename": None,
                    "display_label": None,
                    "id": None,
                },
                "_relation__source": {
                    "__typename": None,
                    "display_label": None,
                    "id": None,
                },
            },
            "tags": {
                "id": None,
                "display_label": None,
                "__typename": None,
                "_relation__is_protected": None,
                "_relation__is_visible": None,
                "_relation__owner": {
                    "id": None,
                    "__typename": None,
                    "display_label": None,
                },
                "_relation__source": {
                    "id": None,
                    "__typename": None,
                    "display_label": None,
                },
            },
        },
    }


@pytest.mark.parametrize("client_type", client_types)
async def test_create_input_data(client, location_schema, client_type):
    data = {"name": {"value": "JFK1"}, "description": {"value": "JFK Airport"}, "type": {"value": "SITE"}}

    if client_type == "standard":
        node = InfrahubNode(client=client, schema=location_schema, data=data)
    else:
        node = InfrahubNodeSync(client=client, schema=location_schema, data=data)
    assert node._generate_input_data() == {
        "data": {
            "name": {"value": "JFK1"},
            "description": {"value": "JFK Airport"},
            "type": {"value": "SITE"},
        }
    }


@pytest.mark.parametrize("client_type", client_types)
async def test_create_input_data__with_relationships_01(client, location_schema, client_type):
    data = {
        "name": {"value": "JFK1"},
        "description": {"value": "JFK Airport"},
        "type": {"value": "SITE"},
        "primary_tag": "pppppppp",
        "tags": [{"id": "aaaaaa"}, {"id": "bbbb"}],
    }
    if client_type == "standard":
        node = InfrahubNode(client=client, schema=location_schema, data=data)
    else:
        node = InfrahubNodeSync(client=client, schema=location_schema, data=data)
    assert node._generate_input_data() == {
        "data": {
            "name": {"value": "JFK1"},
            "description": {"value": "JFK Airport"},
            "type": {"value": "SITE"},
            "tags": [{"id": "aaaaaa"}, {"id": "bbbb"}],
            "primary_tag": {"id": "pppppppp"},
        }
    }


@pytest.mark.parametrize("client_type", client_types)
async def test_create_input_data_with_relationships_02(clients, rfile_schema, client_type):
    data = {
        "name": {"value": "rfile01", "is_protected": True, "source": "ffffffff", "owner": "ffffffff"},
        "template_path": {"value": "mytemplate.j2"},
        "query": {"id": "qqqqqqqq", "source": "ffffffff", "owner": "ffffffff"},
        "template_repository": {"id": "rrrrrrrr", "source": "ffffffff", "owner": "ffffffff"},
        "tags": [{"id": "t1t1t1t1"}, "t2t2t2t2"],
    }
    if client_type == "standard":
        node = InfrahubNode(client=clients.standard, schema=rfile_schema, data=data)
    else:
        node = InfrahubNodeSync(client=clients.sync, schema=rfile_schema, data=data)

    assert node._generate_input_data() == {
        "data": {
            "name": {
                "is_protected": True,
                "owner": "ffffffff",
                "source": "ffffffff",
                "value": "rfile01",
            },
            "query": {
                "_relation__owner": "ffffffff",
                "_relation__source": "ffffffff",
                "id": "qqqqqqqq",
            },
            "tags": [{"id": "t1t1t1t1"}, {"id": "t2t2t2t2"}],
            "template_path": {"value": "mytemplate.j2"},
            "template_repository": {
                "_relation__owner": "ffffffff",
                "_relation__source": "ffffffff",
                "id": "rrrrrrrr",
            },
        }
    }


@pytest.mark.parametrize("client_type", client_types)
async def test_create_input_data_with_relationships_03(clients, rfile_schema, client_type):
    data = {
        "id": "aaaaaaaaaaaaaa",
        "name": {"value": "rfile01", "is_protected": True, "source": "ffffffff"},
        "template_path": {"value": "mytemplate.j2"},
        "query": {"id": "qqqqqqqq", "source": "ffffffff", "owner": "ffffffff", "is_protected": True},
        "template_repository": {"id": "rrrrrrrr", "source": "ffffffff", "owner": "ffffffff"},
        "tags": [{"id": "t1t1t1t1"}, "t2t2t2t2"],
    }
    if client_type == "standard":
        node = InfrahubNode(client=clients.standard, schema=rfile_schema, data=data)
    else:
        node = InfrahubNodeSync(client=clients.sync, schema=rfile_schema, data=data)

    assert node._generate_input_data() == {
        "data": {
            "name": {
                "is_protected": True,
                "source": "ffffffff",
                "value": "rfile01",
            },
            "query": {
                "_relation__is_protected": True,
                "_relation__owner": "ffffffff",
                "_relation__source": "ffffffff",
                "id": "qqqqqqqq",
            },
            "tags": [{"id": "t1t1t1t1"}, {"id": "t2t2t2t2"}],
            "template_path": {"value": "mytemplate.j2"},
            "template_repository": {
                "_relation__owner": "ffffffff",
                "_relation__source": "ffffffff",
                "id": "rrrrrrrr",
            },
        }
    }


# @pytest.mark.parametrize("client_type", client_types)
# async def test_update_input_data__with_relationships_01(client, location_schema, client_type):
#     data = {
#         "name": {"value": "JFK1"},
#         "description": {"value": "JFK Airport"},
#         "type": {"value": "SITE"},
#         "primary_tag": "pppppppp",
#         "tags": [{"id": "aaaaaa"}, {"id": "bbbb"}],
#     }
#     if client_type == "standard":
#         node = InfrahubNode(client=client, schema=location_schema, data=data)
#     else:
#         node = InfrahubNodeSync(client=client, schema=location_schema, data=data)
#     assert node._generate_input_data() == {
#         "data": {
#             "name": {"value": "JFK1"},
#             "description": {"value": "JFK Airport"},
#             "type": {"value": "SITE"},
#             "tags": [{"id": "aaaaaa"}, {"id": "bbbb"}],
#             "primary_tag": {"id": "pppppppp"},
#         }
#     }
