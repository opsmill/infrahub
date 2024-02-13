import inspect
import ipaddress
from typing import TYPE_CHECKING

import pytest
from pytest_httpx import HTTPXMock

from infrahub_sdk.exceptions import NodeNotFound
from infrahub_sdk.node import (
    SAFE_VALUE,
    InfrahubNode,
    InfrahubNodeBase,
    InfrahubNodeSync,
    RelatedNodeBase,
    RelationshipManagerBase,
)

if TYPE_CHECKING:
    from infrahub_sdk.client import InfrahubClient, InfrahubClientSync
    from infrahub_sdk.schema import GenericSchema

# pylint: disable=no-member,too-many-lines
# type: ignore[attr-defined]

async_node_methods = [method for method in dir(InfrahubNode) if not method.startswith("_")]
sync_node_methods = [method for method in dir(InfrahubNodeSync) if not method.startswith("_")]

client_types = ["standard", "sync"]

SAFE_GRAPHQL_VALUES = [
    pytest.param("", id="allow-empty"),
    pytest.param("user1", id="allow-normal"),
    pytest.param("User Lastname", id="allow-space"),
    pytest.param("020a1c39-6071-4bf8-9336-ffb7a001e665", id="allow-uuid"),
    pytest.param("user.lastname", id="allow-dots"),
    pytest.param("/opt/repos/backbone-links", id="allow-filepaths"),
    pytest.param("https://github.com/opsmill/infrahub-demo-edge", id="allow-urls"),
]

UNSAFE_GRAPHQL_VALUES = [
    pytest.param('No "quote"', id="disallow-quotes"),
    pytest.param("Line \n break", id="disallow-linebreaks"),
]


async def test_method_sanity():
    """Validate that there is at least one public method and that both clients look the same."""
    assert async_node_methods
    assert async_node_methods == sync_node_methods


@pytest.mark.parametrize("value", SAFE_GRAPHQL_VALUES)
def test_validate_graphql_value(value: str) -> None:
    """All these values are safe and should not be converted"""
    assert SAFE_VALUE.match(value)


@pytest.mark.parametrize("value", UNSAFE_GRAPHQL_VALUES)
def test_identify_unsafe_graphql_value(value: str) -> None:
    """All these values are safe and should not be converted"""
    assert not SAFE_VALUE.match(value)


@pytest.mark.parametrize("method", async_node_methods)
async def test_validate_method_signature(method):
    EXCLUDE_PARAMETERS = ["client"]
    async_method = getattr(InfrahubNode, method)
    sync_method = getattr(InfrahubNodeSync, method)
    async_sig = inspect.signature(async_method)
    sync_sig = inspect.signature(sync_method)

    # Extract names of parameters and exclude some from the comparaison like client
    async_params_name = async_sig.parameters.keys()
    sync_params_name = sync_sig.parameters.keys()
    async_params = {key: value for key, value in async_sig.parameters.items() if key not in EXCLUDE_PARAMETERS}
    sync_params = {key: value for key, value in sync_sig.parameters.items() if key not in EXCLUDE_PARAMETERS}

    assert async_params_name == sync_params_name
    assert async_params == sync_params
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
async def test_init_node_data_user(client, location_schema, client_type):
    data = {
        "name": {"value": "JFK1"},
        "description": {"value": "JFK Airport"},
        "type": {"value": "SITE"},
    }
    if client_type == "standard":
        node = InfrahubNode(client=client, schema=location_schema, data=data)
    else:
        node = InfrahubNodeSync(client=client, schema=location_schema, data=data)

    assert node.name.value == "JFK1"
    assert node.name.is_protected is None
    assert node.description.value == "JFK Airport"
    assert node.type.value == "SITE"


@pytest.mark.parametrize("client_type", client_types)
async def test_init_node_data_user_with_relationships(client, location_schema, client_type):
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
async def test_init_node_data_graphql(client, location_schema, location_data01, client_type):
    if client_type == "standard":
        node = InfrahubNode(client=client, schema=location_schema, data=location_data01)
    else:
        node = InfrahubNodeSync(client=client, schema=location_schema, data=location_data01)

    assert node.name.value == "DFW"
    assert node.name.is_protected is True
    assert node.description.value is None
    assert node.type.value == "SITE"

    assert isinstance(node.tags, RelationshipManagerBase)
    assert len(node.tags.peers) == 1
    assert isinstance(node.tags.peers[0], RelatedNodeBase)
    assert isinstance(node.primary_tag, RelatedNodeBase)
    assert node.primary_tag.id == "rrrrrrrr-rrrr-rrrr-rrrr-rrrrrrrrrrrr"
    assert node.primary_tag.typename == "BuiltinTag"


@pytest.mark.parametrize("client_type", client_types)
async def test_query_data_no_filters(clients, location_schema, client_type):
    if client_type == "standard":
        client: InfrahubClient = getattr(clients, client_type)  # type: ignore[annotation-unchecked]
        node = InfrahubNode(client=client, schema=location_schema)
        data = await node.generate_query_data()
    else:
        client: InfrahubClientSync = getattr(clients, client_type)  # type: ignore[annotation-unchecked]
        node = InfrahubNodeSync(client=client, schema=location_schema)
        data = node.generate_query_data()

    assert data == {
        "BuiltinLocation": {
            "@filters": {},
            "count": None,
            "edges": {
                "node": {
                    "__typename": None,
                    "id": None,
                    "display_label": None,
                    "name": {
                        "is_protected": None,
                        "is_visible": None,
                        "owner": {
                            "__typename": None,
                            "display_label": None,
                            "id": None,
                        },
                        "source": {
                            "__typename": None,
                            "display_label": None,
                            "id": None,
                        },
                        "value": None,
                    },
                    "description": {
                        "is_protected": None,
                        "is_visible": None,
                        "owner": {
                            "__typename": None,
                            "display_label": None,
                            "id": None,
                        },
                        "source": {
                            "__typename": None,
                            "display_label": None,
                            "id": None,
                        },
                        "value": None,
                    },
                    "type": {
                        "is_protected": None,
                        "is_visible": None,
                        "owner": {
                            "__typename": None,
                            "display_label": None,
                            "id": None,
                        },
                        "source": {
                            "__typename": None,
                            "display_label": None,
                            "id": None,
                        },
                        "value": None,
                    },
                    "primary_tag": {
                        "properties": {
                            "is_protected": None,
                            "is_visible": None,
                            "owner": {
                                "__typename": None,
                                "display_label": None,
                                "id": None,
                            },
                            "source": {
                                "__typename": None,
                                "display_label": None,
                                "id": None,
                            },
                        },
                        "node": {
                            "id": None,
                            "display_label": None,
                            "__typename": None,
                        },
                    },
                },
            },
        },
    }


@pytest.mark.parametrize("client_type", client_types)
async def test_query_data_node(clients, location_schema, client_type):
    if client_type == "standard":
        client: InfrahubClient = getattr(clients, client_type)  # type: ignore[annotation-unchecked]
        node = InfrahubNode(client=client, schema=location_schema)
        data = await node.generate_query_data_node()

    else:
        client: InfrahubClientSync = getattr(clients, client_type)  # type: ignore[annotation-unchecked]
        node = InfrahubNodeSync(client=client, schema=location_schema)
        data = node.generate_query_data_node()

    assert data == {
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
            "properties": {
                "is_protected": None,
                "is_visible": None,
                "owner": {
                    "__typename": None,
                    "display_label": None,
                    "id": None,
                },
                "source": {
                    "__typename": None,
                    "display_label": None,
                    "id": None,
                },
            },
            "node": {
                "id": None,
                "display_label": None,
                "__typename": None,
            },
        },
    }


@pytest.mark.parametrize("client_type", client_types)
async def test_query_data_with_prefetch_relationships(clients, mock_schema_query_02, client_type):
    if client_type == "standard":
        client: InfrahubClient = getattr(clients, client_type)  # type: ignore[annotation-unchecked]
        location_schema: GenericSchema = await client.schema.get(kind="BuiltinLocation")  # type: ignore[annotation-unchecked]
        node = InfrahubNode(client=client, schema=location_schema)
        data = await node.generate_query_data(prefetch_relationships=True)

    else:
        client: InfrahubClientSync = getattr(clients, client_type)  # type: ignore[annotation-unchecked]
        location_schema: GenericSchema = client.schema.get(kind="BuiltinLocation")  # type: ignore[annotation-unchecked]
        node = InfrahubNodeSync(client=client, schema=location_schema)
        data = node.generate_query_data(prefetch_relationships=True)

    assert data == {
        "BuiltinLocation": {
            "@filters": {},
            "count": None,
            "edges": {
                "node": {
                    "__typename": None,
                    "id": None,
                    "display_label": None,
                    "name": {
                        "is_protected": None,
                        "is_visible": None,
                        "owner": {
                            "__typename": None,
                            "display_label": None,
                            "id": None,
                        },
                        "source": {
                            "__typename": None,
                            "display_label": None,
                            "id": None,
                        },
                        "value": None,
                    },
                    "description": {
                        "is_protected": None,
                        "is_visible": None,
                        "owner": {
                            "__typename": None,
                            "display_label": None,
                            "id": None,
                        },
                        "source": {
                            "__typename": None,
                            "display_label": None,
                            "id": None,
                        },
                        "value": None,
                    },
                    "type": {
                        "is_protected": None,
                        "is_visible": None,
                        "owner": {
                            "__typename": None,
                            "display_label": None,
                            "id": None,
                        },
                        "source": {
                            "__typename": None,
                            "display_label": None,
                            "id": None,
                        },
                        "value": None,
                    },
                    "primary_tag": {
                        "properties": {
                            "is_protected": None,
                            "is_visible": None,
                            "owner": {
                                "__typename": None,
                                "display_label": None,
                                "id": None,
                            },
                            "source": {
                                "__typename": None,
                                "display_label": None,
                                "id": None,
                            },
                        },
                        "node": {
                            "id": None,
                            "display_label": None,
                            "__typename": None,
                            "description": {
                                "is_protected": None,
                                "is_visible": None,
                                "owner": {
                                    "__typename": None,
                                    "display_label": None,
                                    "id": None,
                                },
                                "source": {
                                    "__typename": None,
                                    "display_label": None,
                                    "id": None,
                                },
                                "value": None,
                            },
                            "name": {
                                "is_protected": None,
                                "is_visible": None,
                                "owner": {
                                    "__typename": None,
                                    "display_label": None,
                                    "id": None,
                                },
                                "source": {
                                    "__typename": None,
                                    "display_label": None,
                                    "id": None,
                                },
                                "value": None,
                            },
                        },
                    },
                },
            },
        },
    }


@pytest.mark.parametrize("client_type", client_types)
async def test_query_data_node_with_prefetch_relationships(clients, mock_schema_query_02, client_type):
    if client_type == "standard":
        client: InfrahubClient = getattr(clients, client_type)  # type: ignore[annotation-unchecked]
        location_schema: GenericSchema = await client.schema.get(kind="BuiltinLocation")  # type: ignore[annotation-unchecked]
        node = InfrahubNode(client=client, schema=location_schema)
        data = await node.generate_query_data_node(prefetch_relationships=True)

    else:
        client: InfrahubClientSync = getattr(clients, client_type)  # type: ignore[annotation-unchecked]
        location_schema: GenericSchema = client.schema.get(kind="BuiltinLocation")  # type: ignore[annotation-unchecked]
        node = InfrahubNodeSync(client=client, schema=location_schema)
        data = node.generate_query_data_node(prefetch_relationships=True)

    assert data == {
        "description": {
            "is_protected": None,
            "is_visible": None,
            "owner": {"__typename": None, "display_label": None, "id": None},
            "source": {"__typename": None, "display_label": None, "id": None},
            "value": None,
        },
        "name": {
            "is_protected": None,
            "is_visible": None,
            "owner": {"__typename": None, "display_label": None, "id": None},
            "source": {"__typename": None, "display_label": None, "id": None},
            "value": None,
        },
        "primary_tag": {
            "node": {
                "__typename": None,
                "description": {
                    "is_protected": None,
                    "is_visible": None,
                    "owner": {"__typename": None, "display_label": None, "id": None},
                    "source": {"__typename": None, "display_label": None, "id": None},
                    "value": None,
                },
                "display_label": None,
                "id": None,
                "name": {
                    "is_protected": None,
                    "is_visible": None,
                    "owner": {"__typename": None, "display_label": None, "id": None},
                    "source": {"__typename": None, "display_label": None, "id": None},
                    "value": None,
                },
            },
            "properties": {
                "is_protected": None,
                "is_visible": None,
                "owner": {"__typename": None, "display_label": None, "id": None},
                "source": {"__typename": None, "display_label": None, "id": None},
            },
        },
        "type": {
            "is_protected": None,
            "is_visible": None,
            "owner": {"__typename": None, "display_label": None, "id": None},
            "source": {"__typename": None, "display_label": None, "id": None},
            "value": None,
        },
    }


@pytest.mark.parametrize("client_type", client_types)
async def test_query_data_generic(clients, mock_schema_query_02, client_type):  # pylint: disable=unused-argument
    if client_type == "standard":
        client: InfrahubClient = getattr(clients, client_type)  # type: ignore[annotation-unchecked]
        corenode_schema: GenericSchema = await client.schema.get(kind="CoreNode")  # type: ignore[annotation-unchecked]
        node = InfrahubNode(client=client, schema=corenode_schema)
        data = await node.generate_query_data(fragment=False)

    else:
        client: InfrahubClientSync = getattr(clients, client_type)  # type: ignore[annotation-unchecked]
        corenode_schema: GenericSchema = client.schema.get(kind="CoreNode")  # type: ignore[annotation-unchecked]
        node = InfrahubNodeSync(client=client, schema=corenode_schema)
        data = node.generate_query_data(fragment=False)

    assert data == {
        "CoreNode": {
            "@filters": {},
            "count": None,
            "edges": {
                "node": {
                    "__typename": None,
                    "id": None,
                    "display_label": None,
                },
            },
        },
    }


@pytest.mark.parametrize("client_type", client_types)
async def test_query_data_generic_fragment(clients, mock_schema_query_02, client_type):  # pylint: disable=unused-argument
    if client_type == "standard":
        client: InfrahubClient = getattr(clients, client_type)  # type: ignore[annotation-unchecked]
        corenode_schema: GenericSchema = await client.schema.get(kind="CoreNode")  # type: ignore[annotation-unchecked]
        node = InfrahubNode(client=client, schema=corenode_schema)
        data = await node.generate_query_data(fragment=True)

    else:
        client: InfrahubClientSync = getattr(clients, client_type)  # type: ignore[annotation-unchecked]
        corenode_schema: GenericSchema = client.schema.get(kind="CoreNode")  # type: ignore[annotation-unchecked]
        node = InfrahubNodeSync(client=client, schema=corenode_schema)
        data = node.generate_query_data(fragment=True)

    assert data == {
        "CoreNode": {
            "@filters": {},
            "count": None,
            "edges": {
                "node": {
                    "__typename": None,
                    "...on BuiltinLocation": {
                        "description": {
                            "@alias": "__alias__BuiltinLocation__description",
                            "is_protected": None,
                            "is_visible": None,
                            "owner": {
                                "__typename": None,
                                "display_label": None,
                                "id": None,
                            },
                            "source": {
                                "__typename": None,
                                "display_label": None,
                                "id": None,
                            },
                            "value": None,
                        },
                        "name": {
                            "@alias": "__alias__BuiltinLocation__name",
                            "is_protected": None,
                            "is_visible": None,
                            "owner": {
                                "__typename": None,
                                "display_label": None,
                                "id": None,
                            },
                            "source": {
                                "__typename": None,
                                "display_label": None,
                                "id": None,
                            },
                            "value": None,
                        },
                        "primary_tag": {
                            "@alias": "__alias__BuiltinLocation__primary_tag",
                            "node": {
                                "__typename": None,
                                "display_label": None,
                                "id": None,
                            },
                            "properties": {
                                "is_protected": None,
                                "is_visible": None,
                                "owner": {
                                    "__typename": None,
                                    "display_label": None,
                                    "id": None,
                                },
                                "source": {
                                    "__typename": None,
                                    "display_label": None,
                                    "id": None,
                                },
                            },
                        },
                        "type": {
                            "@alias": "__alias__BuiltinLocation__type",
                            "is_protected": None,
                            "is_visible": None,
                            "owner": {
                                "__typename": None,
                                "display_label": None,
                                "id": None,
                            },
                            "source": {
                                "__typename": None,
                                "display_label": None,
                                "id": None,
                            },
                            "value": None,
                        },
                    },
                    "...on BuiltinTag": {
                        "description": {
                            "@alias": "__alias__BuiltinTag__description",
                            "is_protected": None,
                            "is_visible": None,
                            "owner": {
                                "__typename": None,
                                "display_label": None,
                                "id": None,
                            },
                            "source": {
                                "__typename": None,
                                "display_label": None,
                                "id": None,
                            },
                            "value": None,
                        },
                        "name": {
                            "@alias": "__alias__BuiltinTag__name",
                            "is_protected": None,
                            "is_visible": None,
                            "owner": {
                                "__typename": None,
                                "display_label": None,
                                "id": None,
                            },
                            "source": {
                                "__typename": None,
                                "display_label": None,
                                "id": None,
                            },
                            "value": None,
                        },
                    },
                    "display_label": None,
                    "id": None,
                },
            },
        },
    }


@pytest.mark.parametrize("client_type", client_types)
async def test_query_data_include(client, location_schema, client_type):
    if client_type == "standard":
        node = InfrahubNode(client=client, schema=location_schema)
        data = await node.generate_query_data(include=["tags"])
    else:
        node = InfrahubNodeSync(client=client, schema=location_schema)
        data = node.generate_query_data(include=["tags"])

    assert data == {
        "BuiltinLocation": {
            "@filters": {},
            "count": None,
            "edges": {
                "node": {
                    "__typename": None,
                    "id": None,
                    "display_label": None,
                    "name": {
                        "is_protected": None,
                        "is_visible": None,
                        "owner": {
                            "__typename": None,
                            "display_label": None,
                            "id": None,
                        },
                        "source": {
                            "__typename": None,
                            "display_label": None,
                            "id": None,
                        },
                        "value": None,
                    },
                    "description": {
                        "is_protected": None,
                        "is_visible": None,
                        "owner": {
                            "__typename": None,
                            "display_label": None,
                            "id": None,
                        },
                        "source": {
                            "__typename": None,
                            "display_label": None,
                            "id": None,
                        },
                        "value": None,
                    },
                    "type": {
                        "is_protected": None,
                        "is_visible": None,
                        "owner": {
                            "__typename": None,
                            "display_label": None,
                            "id": None,
                        },
                        "source": {
                            "__typename": None,
                            "display_label": None,
                            "id": None,
                        },
                        "value": None,
                    },
                    "primary_tag": {
                        "properties": {
                            "is_protected": None,
                            "is_visible": None,
                            "owner": {
                                "__typename": None,
                                "display_label": None,
                                "id": None,
                            },
                            "source": {
                                "__typename": None,
                                "display_label": None,
                                "id": None,
                            },
                        },
                        "node": {
                            "id": None,
                            "display_label": None,
                            "__typename": None,
                        },
                    },
                    "tags": {
                        "count": None,
                        "edges": {
                            "properties": {
                                "is_protected": None,
                                "is_visible": None,
                                "owner": {
                                    "__typename": None,
                                    "display_label": None,
                                    "id": None,
                                },
                                "source": {
                                    "__typename": None,
                                    "display_label": None,
                                    "id": None,
                                },
                            },
                            "node": {
                                "id": None,
                                "display_label": None,
                                "__typename": None,
                            },
                        },
                    },
                },
            },
        },
    }


@pytest.mark.parametrize("client_type", client_types)
async def test_query_data_exclude(client, location_schema, client_type):
    if client_type == "standard":
        node = InfrahubNode(client=client, schema=location_schema)
        data = await node.generate_query_data(exclude=["description", "primary_tag"])
    else:
        node = InfrahubNodeSync(client=client, schema=location_schema)
        data = node.generate_query_data(exclude=["description", "primary_tag"])

    assert data == {
        "BuiltinLocation": {
            "@filters": {},
            "count": None,
            "edges": {
                "node": {
                    "__typename": None,
                    "id": None,
                    "display_label": None,
                    "name": {
                        "is_protected": None,
                        "is_visible": None,
                        "owner": {
                            "__typename": None,
                            "display_label": None,
                            "id": None,
                        },
                        "source": {
                            "__typename": None,
                            "display_label": None,
                            "id": None,
                        },
                        "value": None,
                    },
                    "type": {
                        "is_protected": None,
                        "is_visible": None,
                        "owner": {
                            "__typename": None,
                            "display_label": None,
                            "id": None,
                        },
                        "source": {
                            "__typename": None,
                            "display_label": None,
                            "id": None,
                        },
                        "value": None,
                    },
                },
            },
        },
    }


@pytest.mark.parametrize("client_type", client_types)
async def test_create_input_data(client, location_schema, client_type):
    data = {
        "name": {"value": "JFK1"},
        "description": {"value": "JFK Airport"},
        "type": {"value": "SITE"},
    }

    if client_type == "standard":
        node = InfrahubNode(client=client, schema=location_schema, data=data)
        node_id = node.id
    else:
        node = InfrahubNodeSync(client=client, schema=location_schema, data=data)
        node_id = node.id
    assert node._generate_input_data()["data"] == {
        "data": {
            "id": f"{node_id}",
            "name": {"value": "JFK1"},
            "description": {"value": "JFK Airport"},
            "type": {"value": "SITE"},
            # "primary_tag": None,
            "tags": [],
            "member_of_groups": [],
        }
    }


@pytest.mark.parametrize("client_type", client_types)
async def test_create_input_data__with_relationships_02(client, location_schema, client_type):
    """Validate input data with variables that needs replacements"""
    data = {
        "name": {"value": "JFK1"},
        "description": {"value": "JFK\n Airport"},
        "type": {"value": "SITE"},
        "primary_tag": "pppppppp",
        "tags": [{"id": "aaaaaa"}, {"id": "bbbb"}],
    }
    if client_type == "standard":
        node = InfrahubNode(client=client, schema=location_schema, data=data)
        node_id = node.id
    else:
        node = InfrahubNodeSync(client=client, schema=location_schema, data=data)
        node_id = node.id

    input_data = node._generate_input_data()
    assert len(input_data["variables"].keys()) == 1
    key = list(input_data["variables"].keys())[0]
    value = input_data["variables"][key]

    expected = {
        "data": {
            "id": f"{node_id}",
            "name": {"value": "JFK1"},
            "description": {"value": f"${key}"},
            "type": {"value": "SITE"},
            "tags": [{"id": "aaaaaa"}, {"id": "bbbb"}],
            "primary_tag": {"id": "pppppppp"},
            "member_of_groups": [],
        }
    }
    assert input_data["data"] == expected
    assert value == "JFK\n Airport"


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
        node_id = node.id
    else:
        node = InfrahubNodeSync(client=client, schema=location_schema, data=data)
        node_id = node.id
    assert node._generate_input_data()["data"] == {
        "data": {
            "id": f"{node_id}",
            "name": {"value": "JFK1"},
            "description": {"value": "JFK Airport"},
            "type": {"value": "SITE"},
            "tags": [{"id": "aaaaaa"}, {"id": "bbbb"}],
            "primary_tag": {"id": "pppppppp"},
            "member_of_groups": [],
        }
    }


@pytest.mark.parametrize("client_type", client_types)
async def test_create_input_data_with_relationships_02(clients, rfile_schema, client_type):
    data = {
        "name": {
            "value": "rfile01",
            "is_protected": True,
            "source": "ffffffff",
            "owner": "ffffffff",
        },
        "template_path": {"value": "mytemplate.j2"},
        "query": {"id": "qqqqqqqq", "source": "ffffffff", "owner": "ffffffff"},
        "repository": {"id": "rrrrrrrr", "source": "ffffffff", "owner": "ffffffff"},
        "tags": [{"id": "t1t1t1t1"}, "t2t2t2t2"],
    }
    if client_type == "standard":
        node = InfrahubNode(client=clients.standard, schema=rfile_schema, data=data)
        node_id = node.id
    else:
        node = InfrahubNodeSync(client=clients.sync, schema=rfile_schema, data=data)
        node_id = node.id

    assert node._generate_input_data()["data"] == {
        "data": {
            "id": f"{node_id}",
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
            "repository": {
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
        "query": {
            "id": "qqqqqqqq",
            "source": "ffffffff",
            "owner": "ffffffff",
            "is_protected": True,
        },
        "repository": {"id": "rrrrrrrr", "source": "ffffffff", "owner": "ffffffff"},
        "tags": [{"id": "t1t1t1t1"}, "t2t2t2t2"],
    }
    if client_type == "standard":
        node = InfrahubNode(client=clients.standard, schema=rfile_schema, data=data)
    else:
        node = InfrahubNodeSync(client=clients.sync, schema=rfile_schema, data=data)

    assert node._generate_input_data()["data"] == {
        "data": {
            "id": "aaaaaaaaaaaaaa",
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
            "repository": {
                "_relation__owner": "ffffffff",
                "_relation__source": "ffffffff",
                "id": "rrrrrrrr",
            },
        }
    }


@pytest.mark.parametrize("client_type", client_types)
async def test_create_input_data_with_relationships_03_for_update(clients, rfile_schema, client_type):
    data = {
        "id": "aaaaaaaaaaaaaa",
        "name": {"value": "rfile01", "is_protected": True, "source": "ffffffff"},
        "template_path": {"value": "mytemplate.j2"},
        "query": {
            "id": "qqqqqqqq",
            "source": "ffffffff",
            "owner": "ffffffff",
            "is_protected": True,
        },
        "repository": {"id": "rrrrrrrr", "source": "ffffffff", "owner": "ffffffff"},
        "tags": [{"id": "t1t1t1t1"}, "t2t2t2t2"],
    }
    if client_type == "standard":
        node = InfrahubNode(client=clients.standard, schema=rfile_schema, data=data)
    else:
        node = InfrahubNodeSync(client=clients.sync, schema=rfile_schema, data=data)

    node.template_path.value = "my-changed-template.j2"
    assert node._generate_input_data(exclude_unmodified=True)["data"] == {
        "data": {
            "id": "aaaaaaaaaaaaaa",
            "query": {
                "id": "qqqqqqqq",
                "_relation__is_protected": True,
                "_relation__owner": "ffffffff",
                "_relation__source": "ffffffff",
            },
            "tags": [{"id": "t1t1t1t1"}, {"id": "t2t2t2t2"}],
            "template_path": {"value": "my-changed-template.j2"},
            "repository": {
                "id": "rrrrrrrr",
                "_relation__owner": "ffffffff",
                "_relation__source": "ffffffff",
            },
        }
    }


@pytest.mark.parametrize("client_type", client_types)
async def test_create_input_data_with_IPHost_attribute(client, ipaddress_schema, client_type):
    data = {
        "id": "aaaaaaaaaaaaaa",
        "address": {
            "value": ipaddress.ip_interface("1.1.1.1/24"),
            "is_protected": True,
        },
    }
    if client_type == "standard":
        ip_address = InfrahubNode(client=client, schema=ipaddress_schema, data=data)
        node_id = ip_address.id
    else:
        ip_address = InfrahubNodeSync(client=client, schema=ipaddress_schema, data=data)
        node_id = ip_address.id

    assert ip_address._generate_input_data()["data"] == {
        "data": {
            "id": f"{node_id}",
            "address": {
                "value": "1.1.1.1/24",
                "is_protected": True,
            },
        }
    }


@pytest.mark.parametrize("client_type", client_types)
async def test_create_input_data_with_IPNetwork_attribute(client, ipnetwork_schema, client_type):
    data = {
        "id": "aaaaaaaaaaaaaa",
        "network": {
            "value": ipaddress.ip_network("1.1.1.0/24"),
            "is_protected": True,
        },
    }
    if client_type == "standard":
        ip_network = InfrahubNode(client=client, schema=ipnetwork_schema, data=data)
        node_id = ip_network.id
    else:
        ip_network = InfrahubNodeSync(client=client, schema=ipnetwork_schema, data=data)
        node_id = ip_network.id

    assert ip_network._generate_input_data()["data"] == {
        "data": {
            "id": f"{node_id}",
            "network": {
                "value": "1.1.1.0/24",
                "is_protected": True,
            },
        }
    }


@pytest.mark.parametrize("client_type", client_types)
async def test_update_input_data__with_relationships_01(
    client,
    location_schema,
    location_data01,
    tag_schema,
    tag_blue_data,
    tag_green_data,
    client_type,
):
    if client_type == "standard":
        location = InfrahubNode(client=client, schema=location_schema, data=location_data01)
        tag_green = InfrahubNode(client=client, schema=tag_schema, data=tag_green_data)
        tag_blue = InfrahubNode(client=client, schema=tag_schema, data=tag_blue_data)

    else:
        location = InfrahubNodeSync(client=client, schema=location_schema, data=location_data01)
        tag_green = InfrahubNodeSync(client=client, schema=tag_schema, data=tag_green_data)
        tag_blue = InfrahubNode(client=client, schema=tag_schema, data=tag_blue_data)

    location.primary_tag = tag_green_data
    location.tags.add(tag_green)
    location.tags.remove(tag_blue)

    assert location._generate_input_data()["data"] == {
        "data": {
            "id": "llllllll-llll-llll-llll-llllllllllll",
            "name": {"is_protected": True, "is_visible": True, "value": "DFW"},
            "primary_tag": {"id": "gggggggg-gggg-gggg-gggg-gggggggggggg"},
            "tags": [{"id": "gggggggg-gggg-gggg-gggg-gggggggggggg"}],
            "type": {"is_protected": True, "is_visible": True, "value": "SITE"},
            "member_of_groups": [],
        },
    }


@pytest.mark.parametrize("client_type", client_types)
async def test_update_input_data_with_relationships_02(client, location_schema, location_data02, client_type):
    if client_type == "standard":
        location = InfrahubNode(client=client, schema=location_schema, data=location_data02)

    else:
        location = InfrahubNodeSync(client=client, schema=location_schema, data=location_data02)

    assert location._generate_input_data()["data"] == {
        "data": {
            "id": "llllllll-llll-llll-llll-llllllllllll",
            "name": {
                "is_protected": True,
                "is_visible": True,
                "source": "cccccccc-cccc-cccc-cccc-cccccccccccc",
                "value": "dfw1",
            },
            "primary_tag": {
                "_relation__is_protected": True,
                "_relation__is_visible": True,
                "_relation__source": "cccccccc-cccc-cccc-cccc-cccccccccccc",
                "id": "rrrrrrrr-rrrr-rrrr-rrrr-rrrrrrrrrrrr",
            },
            "tags": [
                {
                    "_relation__is_protected": True,
                    "_relation__is_visible": True,
                    "_relation__source": "cccccccc-cccc-cccc-cccc-cccccccccccc",
                    "id": "bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb",
                },
            ],
            "type": {
                "is_protected": True,
                "is_visible": True,
                "source": "cccccccc-cccc-cccc-cccc-cccccccccccc",
                "value": "SITE",
            },
            "member_of_groups": [],
        },
    }


@pytest.mark.parametrize("client_type", client_types)
async def test_update_input_data_empty_relationship(
    client, location_schema, location_data01, tag_schema, tag_blue_data, client_type
):
    if client_type == "standard":
        location = InfrahubNode(client=client, schema=location_schema, data=location_data01)
        tag_blue = InfrahubNode(client=client, schema=tag_schema, data=tag_blue_data)

    else:
        location = InfrahubNodeSync(client=client, schema=location_schema, data=location_data01)
        tag_blue = InfrahubNode(client=client, schema=tag_schema, data=tag_blue_data)

    location.tags.remove(tag_blue)
    location.primary_tag = None

    assert location._generate_input_data()["data"] == {
        "data": {
            "id": "llllllll-llll-llll-llll-llllllllllll",
            "name": {"is_protected": True, "is_visible": True, "value": "DFW"},
            # "primary_tag": None,
            "tags": [],
            "type": {"is_protected": True, "is_visible": True, "value": "SITE"},
            "member_of_groups": [],
        },
    }


@pytest.mark.parametrize("client_type", client_types)
async def test_node_get_relationship_from_store(
    client,
    location_schema,
    location_data01,
    tag_schema,
    tag_red_data,
    tag_blue_data,
    client_type,
):
    if client_type == "standard":
        node = InfrahubNode(client=client, schema=location_schema, data=location_data01)
        tag_red = InfrahubNode(client=client, schema=tag_schema, data=tag_red_data)
        tag_blue = InfrahubNode(client=client, schema=tag_schema, data=tag_blue_data)

    else:
        node = InfrahubNodeSync(client=client, schema=location_schema, data=location_data01)
        tag_red = InfrahubNodeSync(client=client, schema=tag_schema, data=tag_red_data)
        tag_blue = InfrahubNodeSync(client=client, schema=tag_schema, data=tag_blue_data)

    client.store.set(key=tag_red.id, node=tag_red)
    client.store.set(key=tag_blue.id, node=tag_blue)

    assert node.primary_tag.peer == tag_red
    assert node.primary_tag.get() == tag_red

    assert node.tags[0].peer == tag_blue
    assert [tag.peer for tag in node.tags] == [tag_blue]


@pytest.mark.parametrize("client_type", client_types)
async def test_node_get_relationship_not_in_store(client, location_schema, location_data01, client_type):
    if client_type == "standard":
        node = InfrahubNode(client=client, schema=location_schema, data=location_data01)

    else:
        node = InfrahubNodeSync(client=client, schema=location_schema, data=location_data01)

    with pytest.raises(NodeNotFound):
        node.primary_tag.peer  # pylint: disable=pointless-statement

    with pytest.raises(NodeNotFound):
        node.tags[0].peer  # pylint: disable=pointless-statement


@pytest.mark.parametrize("client_type", client_types)
async def test_node_fetch_relationship(
    httpx_mock: HTTPXMock,
    mock_schema_query_01,
    clients,
    location_schema,
    location_data01,
    tag_schema,
    tag_red_data,
    tag_blue_data,
    client_type,
):  # pylint: disable=unused-argument
    response1 = {
        "data": {
            "BuiltinTag": {
                "count": 1,
                "edges": [
                    tag_red_data,
                ],
            }
        }
    }

    httpx_mock.add_response(
        method="POST",
        json=response1,
        match_headers={"X-Infrahub-Tracker": "query-builtintag-page1"},
    )

    response2 = {
        "data": {
            "BuiltinTag": {
                "count": 1,
                "edges": [
                    tag_blue_data,
                ],
            }
        }
    }

    httpx_mock.add_response(
        method="POST",
        json=response2,
        match_headers={"X-Infrahub-Tracker": "query-builtintag-page1"},
    )

    if client_type == "standard":
        node = InfrahubNode(client=clients.standard, schema=location_schema, data=location_data01)
        await node.primary_tag.fetch()  # type: ignore[attr-defined]
        await node.tags.fetch()  # type: ignore[attr-defined]
    else:
        node = InfrahubNodeSync(client=clients.sync, schema=location_schema, data=location_data01)  # type: ignore[assignment]
        node.primary_tag.fetch()  # type: ignore[attr-defined]
        node.tags.fetch()  # type: ignore[attr-defined]

    assert isinstance(node.primary_tag.peer, InfrahubNodeBase)  # type: ignore[attr-defined]
    assert isinstance(node.tags[0].peer, InfrahubNodeBase)  # type: ignore[attr-defined]


@pytest.mark.parametrize("client_type", client_types)
async def test_node_IPHost_deserialization(client, ipaddress_schema, client_type):
    data = {
        "id": "aaaaaaaaaaaaaa",
        "address": {
            "value": "1.1.1.1/24",
            "is_protected": True,
        },
    }
    if client_type == "standard":
        ip_address = InfrahubNode(client=client, schema=ipaddress_schema, data=data)
    else:
        ip_address = InfrahubNodeSync(client=client, schema=ipaddress_schema, data=data)

    assert ip_address.address.value == ipaddress.ip_interface("1.1.1.1/24")


@pytest.mark.parametrize("client_type", client_types)
async def test_node_IPNetwork_deserialization(client, ipnetwork_schema, client_type):
    data = {
        "id": "aaaaaaaaaaaaaa",
        "network": {
            "value": "1.1.1.0/24",
            "is_protected": True,
        },
    }
    if client_type == "standard":
        ip_network = InfrahubNode(client=client, schema=ipnetwork_schema, data=data)
    else:
        ip_network = InfrahubNodeSync(client=client, schema=ipnetwork_schema, data=data)

    assert ip_network.network.value == ipaddress.ip_network("1.1.1.0/24")


@pytest.mark.parametrize("client_type", client_types)
async def test_node_extract(client, location_schema, location_data01, client_type):
    if client_type == "standard":
        node = InfrahubNode(client=client, schema=location_schema, data=location_data01)
    else:
        node = InfrahubNodeSync(client=client, schema=location_schema, data=location_data01)

    params = {
        "identifier": "id",
        "name": "name__value",
        "description": "description__value",
    }

    assert node.extract(params=params) == {
        "description": None,
        "identifier": "llllllll-llll-llll-llll-llllllllllll",
        "name": "DFW",
    }


@pytest.mark.parametrize("client_type", client_types)
async def test_read_only_attr(
    client,
    address_schema,
    address_data,
    client_type,
):
    if client_type == "standard":
        address = InfrahubNode(client=client, schema=address_schema, data=address_data)
    else:
        address = InfrahubNodeSync(client=client, schema=address_schema, data=address_data)

    assert address._generate_input_data()["data"] == {
        "data": {
            "id": "d5994b18-b25e-4261-9e63-17c2844a0b45",
            "street_number": {"is_protected": False, "is_visible": True, "value": "1234"},
            "street_name": {"is_protected": False, "is_visible": True, "value": "Fake Street"},
            "postal_code": {"is_protected": False, "is_visible": True, "value": "123ABC"},
        },
    }
    assert address.computed_address.value == "1234 Fake Street 123ABC"
