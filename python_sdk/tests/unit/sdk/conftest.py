import re
import sys
from dataclasses import dataclass
from inspect import Parameter
from io import StringIO
from typing import AsyncGenerator, Mapping, Optional

import pytest
import ujson
from pytest_httpx import HTTPXMock

from infrahub_sdk import Config, InfrahubClient, InfrahubClientSync
from infrahub_sdk.schema import BranchSupportType, NodeSchema
from infrahub_sdk.utils import get_fixtures_dir

# pylint: disable=redefined-outer-name,unused-argument


@dataclass
class BothClients:
    sync: InfrahubClientSync
    standard: InfrahubClient
    stdout: Optional[StringIO] = None


@pytest.fixture
async def client() -> InfrahubClient:
    return InfrahubClient(config=Config(address="http://mock", insert_tracker=True, pagination_size=3))


@pytest.fixture
async def clients() -> BothClients:
    both = BothClients(
        standard=InfrahubClient(config=Config(address="http://mock", insert_tracker=True, pagination_size=3)),
        sync=InfrahubClientSync(config=Config(address="http://mock", insert_tracker=True, pagination_size=3)),
    )
    return both


@pytest.fixture
async def echo_clients(clients: BothClients) -> AsyncGenerator[BothClients, None]:
    clients.standard.config.echo_graphql_queries = True
    clients.sync.config.echo_graphql_queries = True
    clients.stdout = StringIO()
    backup_stdout = sys.stdout
    sys.stdout = clients.stdout

    yield clients

    sys.stdout = backup_stdout

    clients.standard.config.echo_graphql_queries = False
    clients.sync.config.echo_graphql_queries = False


@pytest.fixture
def replace_async_return_annotation():
    """Allows for comparison between sync and async return annotations."""

    def replace_annotation(annotation: str) -> str:
        replacements = {
            "InfrahubClient": "InfrahubClientSync",
            "InfrahubNode": "InfrahubNodeSync",
            "list[InfrahubNode]": "list[InfrahubNodeSync]",
            "Optional[InfrahubNode]": "Optional[InfrahubNodeSync]",
        }
        return replacements.get(annotation) or annotation

    return replace_annotation


@pytest.fixture
def replace_async_parameter_annotations(replace_async_return_annotation):
    """Allows for comparison between sync and async parameter annotations."""

    def replace_annotations(parameters: Mapping[str, Parameter]) -> tuple[str, str]:
        parameter_tuples = []
        for name, parameter in parameters.items():
            parameter_tuples.append((name, replace_async_return_annotation(parameter.annotation)))

        return parameter_tuples

    return replace_annotations


@pytest.fixture
def replace_sync_return_annotation() -> str:
    """Allows for comparison between sync and async return annotations."""

    def replace_annotation(annotation: str) -> str:
        replacements = {
            "InfrahubClientSync": "InfrahubClient",
            "InfrahubNodeSync": "InfrahubNode",
            "list[InfrahubNodeSync]": "list[InfrahubNode]",
            "Optional[InfrahubNodeSync]": "Optional[InfrahubNode]",
        }
        return replacements.get(annotation) or annotation

    return replace_annotation


@pytest.fixture
def replace_sync_parameter_annotations(replace_sync_return_annotation):
    """Allows for comparison between sync and async parameter annotations."""

    def replace_annotations(parameters: Mapping[str, Parameter]) -> tuple[str, str]:
        parameter_tuples = []
        for name, parameter in parameters.items():
            parameter_tuples.append((name, replace_sync_return_annotation(parameter.annotation)))

        return parameter_tuples

    return replace_annotations


@pytest.fixture
async def location_schema() -> NodeSchema:
    data = {
        "name": "Location",
        "namespace": "Builtin",
        "default_filter": "name__value",
        "attributes": [
            {"name": "name", "kind": "String", "unique": True},
            {"name": "description", "kind": "String", "optional": True},
            {"name": "type", "kind": "String"},
        ],
        "relationships": [
            {
                "name": "tags",
                "peer": "BuiltinTag",
                "optional": True,
                "cardinality": "many",
            },
            {
                "name": "primary_tag",
                "peer": "BuiltinTag",
                "optional": True,
                "cardinality": "one",
            },
            {
                "name": "member_of_groups",
                "peer": "CoreGroup",
                "optional": True,
                "cardinality": "many",
                "kind": "Group",
            },
        ],
    }
    return NodeSchema(**data)  # type: ignore


@pytest.fixture
async def schema_with_hfid() -> dict[str, NodeSchema]:
    data = {
        "location": {
            "name": "Location",
            "namespace": "Builtin",
            "default_filter": "name__value",
            "human_friendly_id": ["name__value"],
            "attributes": [
                {"name": "name", "kind": "String", "unique": True},
                {"name": "description", "kind": "String", "optional": True},
                {"name": "type", "kind": "String"},
            ],
            "relationships": [
                {
                    "name": "tags",
                    "peer": "BuiltinTag",
                    "optional": True,
                    "cardinality": "many",
                },
                {
                    "name": "primary_tag",
                    "peer": "BuiltinTag",
                    "optional": True,
                    "cardinality": "one",
                },
                {
                    "name": "member_of_groups",
                    "peer": "CoreGroup",
                    "optional": True,
                    "cardinality": "many",
                    "kind": "Group",
                },
            ],
        },
        "rack": {
            "name": "Rack",
            "namespace": "Builtin",
            "default_filter": "facility_id__value",
            "human_friendly_id": ["facility_id__value", "location__name__value"],
            "attributes": [
                {"name": "facility_id", "kind": "String", "unique": True},
                {"name": "description", "kind": "String", "optional": True},
            ],
            "relationships": [
                {"name": "location", "peer": "BuiltinLocation", "cardinality": "one"},
                {
                    "name": "tags",
                    "peer": "BuiltinTag",
                    "optional": True,
                    "cardinality": "many",
                },
                {
                    "name": "member_of_groups",
                    "peer": "CoreGroup",
                    "optional": True,
                    "cardinality": "many",
                    "kind": "Group",
                },
            ],
        },
    }
    return {k: NodeSchema(**v) for k, v in data.items()}  # type: ignore


@pytest.fixture
async def std_group_schema() -> NodeSchema:
    data = {
        "name": "StandardGroup",
        "namespace": "Core",
        "default_filter": "name__value",
        "attributes": [
            {"name": "name", "kind": "String", "unique": True},
            {"name": "description", "kind": "String", "optional": True},
        ],
    }
    return NodeSchema(**data)  # type: ignore


@pytest.fixture
async def location_data01_no_pagination():
    data = {
        "__typename": "BuiltinLocation",
        "id": "llllllll-llll-llll-llll-llllllllllll",
        "display_label": "dfw1",
        "name": {
            "is_protected": True,
            "is_visible": True,
            "owner": None,
            "source": None,
            "value": "DFW",
        },
        "description": {
            "is_protected": False,
            "is_visible": True,
            "owner": None,
            "source": None,
            "value": None,
        },
        "type": {
            "is_protected": True,
            "is_visible": True,
            "owner": None,
            "source": None,
            "value": "SITE",
        },
        "primary_tag": {
            "id": "rrrrrrrr-rrrr-rrrr-rrrr-rrrrrrrrrrrr",
            "display_label": "red",
            "__typename": "RelatedTag",
            "_relation__is_protected": True,
            "_relation__is_visible": True,
            "_relation__owner": None,
            "_relation__source": None,
        },
        "tags": [
            {
                "id": "bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb",
                "display_label": "blue",
                "__typename": "RelatedTag",
                "_relation__is_protected": True,
                "_relation__is_visible": True,
                "_relation__owner": None,
                "_relation__source": None,
            }
        ],
    }

    return data


@pytest.fixture
async def location_data02_no_pagination():
    data = {
        "__typename": "BuiltinLocation",
        "id": "llllllll-llll-llll-llll-llllllllllll",
        "display_label": "dfw1",
        "name": {
            "is_protected": True,
            "is_visible": True,
            "owner": None,
            "source": {
                "__typename": "Account",
                "display_label": "CRM",
                "id": "cccccccc-cccc-cccc-cccc-cccccccccccc",
            },
            "value": "dfw1",
        },
        "description": {
            "is_protected": False,
            "is_visible": True,
            "owner": None,
            "source": None,
            "value": None,
        },
        "type": {
            "is_protected": True,
            "is_visible": True,
            "owner": None,
            "source": {
                "__typename": "Account",
                "display_label": "CRM",
                "id": "cccccccc-cccc-cccc-cccc-cccccccccccc",
            },
            "value": "SITE",
        },
        "primary_tag": {
            "id": "rrrrrrrr-rrrr-rrrr-rrrr-rrrrrrrrrrrr",
            "display_label": "red",
            "__typename": "RelatedTag",
            "_relation__is_protected": True,
            "_relation__is_visible": True,
            "_relation__owner": None,
            "_relation__source": {
                "__typename": "Account",
                "display_label": "CRM",
                "id": "cccccccc-cccc-cccc-cccc-cccccccccccc",
            },
        },
        "tags": [
            {
                "id": "bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb",
                "display_label": "blue",
                "__typename": "RelatedTag",
                "_relation__is_protected": True,
                "_relation__is_visible": True,
                "_relation__owner": None,
                "_relation__source": {
                    "__typename": "Account",
                    "display_label": "CRM",
                    "id": "cccccccc-cccc-cccc-cccc-cccccccccccc",
                },
            }
        ],
    }

    return data


@pytest.fixture
async def location_data01():
    data = {
        "node": {
            "__typename": "BuiltinLocation",
            "id": "llllllll-llll-llll-llll-llllllllllll",
            "display_label": "dfw1",
            "name": {
                "is_protected": True,
                "is_visible": True,
                "owner": None,
                "source": None,
                "value": "DFW",
            },
            "description": {
                "is_protected": False,
                "is_visible": True,
                "owner": None,
                "source": None,
                "value": None,
            },
            "type": {
                "is_protected": True,
                "is_visible": True,
                "owner": None,
                "source": None,
                "value": "SITE",
            },
            "primary_tag": {
                "properties": {
                    "is_protected": True,
                    "is_visible": True,
                    "owner": None,
                    "source": None,
                },
                "node": {
                    "id": "rrrrrrrr-rrrr-rrrr-rrrr-rrrrrrrrrrrr",
                    "display_label": "red",
                    "__typename": "BuiltinTag",
                },
            },
            "tags": {
                "count": 1,
                "edges": [
                    {
                        "properties": {
                            "is_protected": True,
                            "is_visible": True,
                            "owner": None,
                            "source": None,
                        },
                        "node": {
                            "id": "bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb",
                            "display_label": "blue",
                            "__typename": "BuiltinTag",
                        },
                    }
                ],
            },
        }
    }

    return data


@pytest.fixture
async def location_data02():
    data = {
        "node": {
            "__typename": "BuiltinLocation",
            "id": "llllllll-llll-llll-llll-llllllllllll",
            "display_label": "dfw1",
            "name": {
                "is_protected": True,
                "is_visible": True,
                "owner": None,
                "source": {
                    "__typename": "Account",
                    "display_label": "CRM",
                    "id": "cccccccc-cccc-cccc-cccc-cccccccccccc",
                },
                "value": "dfw1",
            },
            "description": {
                "is_protected": False,
                "is_visible": True,
                "owner": None,
                "source": None,
                "value": None,
            },
            "type": {
                "is_protected": True,
                "is_visible": True,
                "owner": None,
                "source": {
                    "__typename": "Account",
                    "display_label": "CRM",
                    "id": "cccccccc-cccc-cccc-cccc-cccccccccccc",
                },
                "value": "SITE",
            },
            "primary_tag": {
                "properties": {
                    "is_protected": True,
                    "is_visible": True,
                    "owner": None,
                    "source": {
                        "__typename": "Account",
                        "display_label": "CRM",
                        "id": "cccccccc-cccc-cccc-cccc-cccccccccccc",
                    },
                },
                "node": {
                    "id": "rrrrrrrr-rrrr-rrrr-rrrr-rrrrrrrrrrrr",
                    "display_label": "red",
                    "__typename": "BuiltinTag",
                },
            },
            "tags": {
                "count": 1,
                "edges": [
                    {
                        "properties": {
                            "is_protected": True,
                            "is_visible": True,
                            "owner": None,
                            "source": {
                                "__typename": "Account",
                                "display_label": "CRM",
                                "id": "cccccccc-cccc-cccc-cccc-cccccccccccc",
                            },
                        },
                        "node": {
                            "id": "bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb",
                            "display_label": "blue",
                            "__typename": "BuiltinTag",
                        },
                    }
                ],
            },
        }
    }

    return data


@pytest.fixture
async def tag_schema() -> NodeSchema:
    data = {
        "name": "Tag",
        "namespace": "Builtin",
        "default_filter": "name__value",
        "attributes": [
            {"name": "name", "kind": "String", "unique": True},
            {"name": "description", "kind": "String", "optional": True},
        ],
    }
    return NodeSchema(**data)  # type: ignore


@pytest.fixture
async def tag_blue_data_no_pagination():
    data = {
        "__typename": "BuiltinTag",
        "id": "bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb",
        "display_label": "blue",
        "name": {
            "is_protected": False,
            "is_visible": True,
            "owner": None,
            "source": {
                "__typename": "Account",
                "display_label": "CRM",
                "id": "cccccccc-cccc-cccc-cccc-cccccccccccc",
            },
            "value": "blue",
        },
        "description": {
            "is_protected": False,
            "is_visible": True,
            "owner": None,
            "source": None,
            "value": None,
        },
    }
    return data


@pytest.fixture
async def tag_red_data_no_pagination():
    data = {
        "__typename": "BuiltinTag",
        "id": "rrrrrrrr-rrrr-rrrr-rrrr-rrrrrrrrrrrr",
        "display_label": "red",
        "name": {
            "is_protected": False,
            "is_visible": True,
            "owner": None,
            "source": {
                "__typename": "Account",
                "display_label": "CRM",
                "id": "cccccccc-cccc-cccc-cccc-cccccccccccc",
            },
            "value": "red",
        },
        "description": {
            "is_protected": False,
            "is_visible": True,
            "owner": None,
            "source": None,
            "value": None,
        },
    }
    return data


@pytest.fixture
async def tag_green_data_no_pagination():
    data = {
        "__typename": "BuiltinTag",
        "id": "gggggggg-gggg-gggg-gggg-gggggggggggg",
        "display_label": "green",
        "name": {
            "is_protected": False,
            "is_visible": True,
            "owner": None,
            "source": {
                "__typename": "Account",
                "display_label": "CRM",
                "id": "cccccccc-cccc-cccc-cccc-cccccccccccc",
            },
            "value": "green",
        },
        "description": {
            "is_protected": False,
            "is_visible": True,
            "owner": None,
            "source": None,
            "value": None,
        },
    }
    return data


@pytest.fixture
async def tag_blue_data():
    data = {
        "node": {
            "__typename": "BuiltinTag",
            "id": "bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb",
            "display_label": "blue",
            "name": {
                "is_protected": False,
                "is_visible": True,
                "owner": None,
                "source": {
                    "__typename": "Account",
                    "display_label": "CRM",
                    "id": "cccccccc-cccc-cccc-cccc-cccccccccccc",
                },
                "value": "blue",
            },
            "description": {
                "is_protected": False,
                "is_visible": True,
                "owner": None,
                "source": None,
                "value": None,
            },
        }
    }
    return data


@pytest.fixture
async def tag_red_data():
    data = {
        "node": {
            "__typename": "BuiltinTag",
            "id": "rrrrrrrr-rrrr-rrrr-rrrr-rrrrrrrrrrrr",
            "display_label": "red",
            "name": {
                "is_protected": False,
                "is_visible": True,
                "owner": None,
                "source": {
                    "__typename": "Account",
                    "display_label": "CRM",
                    "id": "cccccccc-cccc-cccc-cccc-cccccccccccc",
                },
                "value": "red",
            },
            "description": {
                "is_protected": False,
                "is_visible": True,
                "owner": None,
                "source": None,
                "value": None,
            },
        }
    }
    return data


@pytest.fixture
async def tag_green_data():
    data = {
        "node": {
            "__typename": "BuiltinTag",
            "id": "gggggggg-gggg-gggg-gggg-gggggggggggg",
            "display_label": "green",
            "name": {
                "is_protected": False,
                "is_visible": True,
                "owner": None,
                "source": {
                    "__typename": "Account",
                    "display_label": "CRM",
                    "id": "cccccccc-cccc-cccc-cccc-cccccccccccc",
                },
                "value": "green",
            },
            "description": {
                "is_protected": False,
                "is_visible": True,
                "owner": None,
                "source": None,
                "value": None,
            },
        }
    }
    return data


@pytest.fixture
async def rfile_schema() -> NodeSchema:
    data = {
        "name": "TransformJinja2",
        "namespace": "Core",
        "default_filter": "name__value",
        "display_label": ["label__value"],
        "branch": BranchSupportType.AWARE.value,
        "attributes": [
            {"name": "name", "kind": "String", "unique": True},
            {"name": "description", "kind": "String", "optional": True},
            {"name": "template_path", "kind": "String"},
        ],
        "relationships": [
            {
                "name": "repository",
                "peer": "CoreRepository",
                "kind": "Attribute",
                "identifier": "jinja2__repository",
                "cardinality": "one",
                "optional": False,
            },
            {
                "name": "query",
                "peer": "CoreGraphQLQuery",
                "kind": "Attribute",
                "cardinality": "one",
                "optional": False,
            },
            {
                "name": "tags",
                "peer": "BuiltinTag",
                "optional": True,
                "cardinality": "many",
            },
        ],
    }
    return NodeSchema(**data)  # type: ignore


@pytest.fixture
async def ipaddress_schema() -> NodeSchema:
    data = {
        "name": "IPAddress",
        "namespace": "Infra",
        "default_filter": "address__value",
        "display_labels": ["address_value"],
        "order_by": ["address_value"],
        "attributes": [
            {"name": "address", "kind": "IPHost"},
        ],
        "relationships": [
            {
                "name": "interface",
                "peer": "InfraInterfaceL3",
                "optional": True,
                "cardinality": "one",
                "kind": "Parent",
            }
        ],
    }
    return NodeSchema(**data)  # type: ignore


@pytest.fixture
async def ipnetwork_schema() -> NodeSchema:
    data = {
        "name": "IPNetwork",
        "namespace": "Infra",
        "default_filter": "network__value",
        "display_labels": ["network_value"],
        "order_by": ["network_value"],
        "attributes": [
            {"name": "network", "kind": "IPNetwork"},
        ],
        "relationships": [
            {
                "name": "site",
                "peer": "BuiltinLocation",
                "optional": True,
                "cardinality": "one",
                "kind": "Parent",
            }
        ],
    }
    return NodeSchema(**data)  # type: ignore


@pytest.fixture
async def ipam_ipprefix_schema() -> NodeSchema:
    data = {
        "name": "IPNetwork",
        "namespace": "Ipam",
        "default_filter": "prefix__value",
        "display_labels": ["prefix_value"],
        "order_by": ["prefix_value"],
        "inherit_from": ["BuiltinIPAddress"],
    }
    return NodeSchema(**data)  # type: ignore


@pytest.fixture
async def simple_device_schema() -> NodeSchema:
    data = {
        "name": "Device",
        "namespace": "Infra",
        "label": "Device",
        "default_filter": "name__value",
        "order_by": ["name__value"],
        "display_labels": ["name__value"],
        "attributes": [{"name": "name", "kind": "Text", "unique": True}],
        "relationships": [
            {
                "name": "primary_address",
                "peer": "IpamIPAddress",
                "label": "Primary IP Address",
                "optional": True,
                "cardinality": "one",
                "kind": "Attribute",
            }
        ],
    }
    return NodeSchema(**data)  # type: ignore


@pytest.fixture
async def ipam_ipprefix_data():
    data = {
        "node": {
            "__typename": "IpamIPPrefix",
            "id": "llllllll-llll-llll-llll-llllllllllll",
            "display_label": "192.0.2.0/24",
            "prefix": {
                "is_protected": True,
                "is_visible": True,
                "owner": None,
                "source": {
                    "__typename": "Account",
                    "display_label": "CRM",
                    "id": "cccccccc-cccc-cccc-cccc-cccccccccccc",
                },
                "value": "192.0.2.0/24",
            },
            "description": {
                "is_protected": False,
                "is_visible": True,
                "owner": None,
                "source": None,
                "value": None,
            },
            "member_type": {
                "is_protected": True,
                "is_visible": True,
                "owner": None,
                "source": {
                    "__typename": "Account",
                    "display_label": "CRM",
                    "id": "cccccccc-cccc-cccc-cccc-cccccccccccc",
                },
                "value": "address",
            },
            "is_pool": {
                "is_protected": True,
                "is_visible": True,
                "owner": None,
                "source": {
                    "__typename": "Account",
                    "display_label": "CRM",
                    "id": "cccccccc-cccc-cccc-cccc-cccccccccccc",
                },
                "value": False,
            },
            "ip_namespace": {
                "properties": {
                    "is_protected": True,
                    "is_visible": True,
                    "owner": None,
                    "source": {
                        "__typename": "Account",
                        "display_label": "CRM",
                        "id": "cccccccc-cccc-cccc-cccc-cccccccccccc",
                    },
                },
                "node": {
                    "id": "rrrrrrrr-rrrr-rrrr-rrrr-rrrrrrrrrrrr",
                    "display_label": "default",
                    "__typename": "IpamNamespace",
                },
            },
        }
    }

    return data


@pytest.fixture
async def ipaddress_pool_schema() -> NodeSchema:
    data = {
        "name": "IPAddressPool",
        "namespace": "Core",
        "description": "A pool of IP address resources",
        "label": "IP Address Pool",
        "default_filter": "name__value",
        "order_by": ["name__value"],
        "display_labels": ["name__value"],
        "include_in_menu": False,
        "branch": BranchSupportType.AGNOSTIC.value,
        "inherit_from": ["CoreResourcePool"],
        "attributes": [
            {
                "name": "default_address_type",
                "kind": "Text",
                "optional": False,
                "description": "The object type to create when reserving a resource in the pool",
            },
            {
                "name": "default_prefix_length",
                "kind": "Number",
                "optional": True,
            },
        ],
        "relationships": [
            {
                "name": "resources",
                "peer": "BuiltinIPPrefix",
                "kind": "Attribute",
                "identifier": "ipaddresspool__resource",
                "cardinality": "many",
                "optional": False,
                "order_weight": 4000,
            },
            {
                "name": "ip_namespace",
                "peer": "BuiltinIPNamespace",
                "kind": "Attribute",
                "identifier": "ipaddresspool__ipnamespace",
                "cardinality": "one",
                "optional": False,
                "order_weight": 5000,
            },
        ],
    }
    return NodeSchema(**data)  # type: ignore


@pytest.fixture
async def ipprefix_pool_schema() -> NodeSchema:
    data = {
        "name": "IPPrefixPool",
        "namespace": "Core",
        "description": "A pool of IP prefix resources",
        "label": "IP Prefix Pool",
        "include_in_menu": False,
        "branch": BranchSupportType.AGNOSTIC.value,
        "inherit_from": ["CoreResourcePool"],
        "attributes": [
            {
                "name": "default_prefix_length",
                "kind": "Number",
                "description": "The default prefix length as an integer for prefixes allocated from this pool.",
                "optional": True,
                "order_weight": 5000,
            },
            {
                "name": "default_member_type",
                "kind": "Text",
                "enum": ["prefix", "address"],
                "default_value": "prefix",
                "optional": True,
                "order_weight": 3000,
            },
            {
                "name": "default_prefix_type",
                "kind": "Text",
                "optional": True,
                "order_weight": 4000,
            },
        ],
        "relationships": [
            {
                "name": "resources",
                "peer": "BuiltinIPPrefix",
                "kind": "Attribute",
                "identifier": "prefixpool__resource",
                "cardinality": "many",
                "branch": BranchSupportType.AGNOSTIC.value,
                "optional": False,
                "order_weight": 6000,
            },
            {
                "name": "ip_namespace",
                "peer": "BuiltinIPNamespace",
                "kind": "Attribute",
                "identifier": "prefixpool__ipnamespace",
                "cardinality": "one",
                "branch": BranchSupportType.AGNOSTIC.value,
                "optional": False,
                "order_weight": 7000,
            },
        ],
    }
    return NodeSchema(**data)  # type: ignore


@pytest.fixture
async def address_schema() -> NodeSchema:
    data = {
        "name": "Address",
        "namespace": "Infra",
        "default_filter": "network__value",
        "display_labels": ["network_value"],
        "order_by": ["network_value"],
        "attributes": [
            {"name": "street_number", "kind": "String", "optional": True},
            {"name": "street_name", "kind": "String", "optional": True},
            {"name": "postal_code", "kind": "String", "optional": True},
            {"name": "computed_address", "kind": "String", "optional": True, "read_only": True},
        ],
        "relationships": [],
    }
    return NodeSchema(**data)  # type: ignore


@pytest.fixture
async def address_data():
    data = {
        "node": {
            "__typename": "Address",
            "id": "d5994b18-b25e-4261-9e63-17c2844a0b45",
            "display_label": "test_address",
            "street_number": {
                "is_protected": False,
                "is_visible": True,
                "owner": None,
                "source": None,
                "value": "1234",
            },
            "street_name": {
                "is_protected": False,
                "is_visible": True,
                "owner": None,
                "source": None,
                "value": "Fake Street",
            },
            "postal_code": {
                "is_protected": False,
                "is_visible": True,
                "owner": None,
                "source": None,
                "value": "123ABC",
            },
            "computed_address": {
                "is_protected": False,
                "is_visible": True,
                "owner": None,
                "source": None,
                "value": "1234 Fake Street 123ABC",
            },
        }
    }
    return data


@pytest.fixture
async def device_schema() -> NodeSchema:
    data = {
        "name": "Device",
        "namespace": "Infra",
        "label": "Device",
        "default_filter": "name__value",
        "inherit_from": ["CoreArtifactTarget"],
        "order_by": ["name__value"],
        "display_labels": ["name__value"],
        "attributes": [
            {"name": "name", "kind": "Text", "unique": True},
            {"name": "description", "kind": "Text", "optional": True},
            {"name": "type", "kind": "Text"},
        ],
        "relationships": [
            {"name": "site", "peer": "BuiltinLocation", "optional": False, "cardinality": "one", "kind": "Attribute"},
            {"name": "status", "peer": "BuiltinStatus", "optional": False, "cardinality": "one", "kind": "Attribute"},
            {"name": "role", "peer": "BuiltinRole", "optional": False, "cardinality": "one", "kind": "Attribute"},
            {
                "name": "interfaces",
                "peer": "InfraInterface",
                "identifier": "device__interface",
                "optional": True,
                "cardinality": "many",
                "kind": "Component",
            },
            {
                "name": "asn",
                "peer": "InfraAutonomousSystem",
                "optional": True,
                "cardinality": "one",
                "kind": "Attribute",
            },
            {"name": "tags", "peer": "BuiltinTag", "optional": True, "cardinality": "many", "kind": "Attribute"},
            {
                "name": "primary_address",
                "peer": "InfraIPAddress",
                "label": "Primary IP Address",
                "optional": True,
                "cardinality": "one",
                "kind": "Attribute",
            },
            {"name": "platform", "peer": "InfraPlatform", "optional": True, "cardinality": "one", "kind": "Attribute"},
            {"name": "artifacts", "peer": "CoreArtifact", "optional": True, "cardinality": "many", "kind": "Generic"},
        ],
    }
    return NodeSchema(**data)  # type: ignore


@pytest.fixture
async def device_data():
    data = {
        "node": {
            "id": "1799f647-203c-cd41-3409-c51d55097213",
            "display_label": "atl1-edge1",
            "__typename": "InfraDevice",
            "name": {
                "value": "atl1-edge1",
                "is_visible": True,
                "is_protected": True,
                "source": {
                    "id": "1799f644-d5eb-8e37-3403-c512518ae06a",
                    "display_label": "Pop-Builder",
                    "__typename": "CoreAccount",
                },
                "owner": None,
            },
            "description": {"value": None, "is_visible": True, "is_protected": False, "source": None, "owner": None},
            "type": {
                "value": "7280R3",
                "is_visible": True,
                "is_protected": False,
                "source": {
                    "id": "1799f644-d5eb-8e37-3403-c512518ae06a",
                    "display_label": "Pop-Builder",
                    "__typename": "CoreAccount",
                },
                "owner": None,
            },
            "site": {
                "node": {
                    "id": "1799f646-fa2c-29d0-3406-c5101365ec3a",
                    "display_label": "atl1",
                    "__typename": "BuiltinLocation",
                },
                "properties": {
                    "is_visible": True,
                    "is_protected": True,
                    "source": {
                        "id": "1799f644-d5eb-8e37-3403-c512518ae06a",
                        "display_label": "Pop-Builder",
                        "__typename": "CoreAccount",
                    },
                    "owner": None,
                },
            },
            "status": {
                "node": {
                    "id": "1799f646-c1b3-2ed5-3406-c5102132e63b",
                    "display_label": "Active",
                    "__typename": "BuiltinStatus",
                },
                "properties": {
                    "is_visible": True,
                    "is_protected": None,
                    "source": None,
                    "owner": {
                        "id": "1799f645-a5c5-e0ac-3403-c512c9cff168",
                        "display_label": "Operation Team",
                        "__typename": "CoreAccount",
                    },
                },
            },
            "role": {
                "node": {
                    "id": "1799f646-c1af-2bd0-3407-c51069f6bdae",
                    "display_label": "Edge",
                    "__typename": "BuiltinRole",
                },
                "properties": {
                    "is_visible": True,
                    "is_protected": True,
                    "source": {
                        "id": "1799f644-d5eb-8e37-3403-c512518ae06a",
                        "display_label": "Pop-Builder",
                        "__typename": "CoreAccount",
                    },
                    "owner": {
                        "id": "1799f645-b916-a9e8-3407-c51370cacbd0",
                        "display_label": "Engineering Team",
                        "__typename": "CoreAccount",
                    },
                },
            },
            "asn": {
                "node": {
                    "id": "1799f646-6d88-e77f-340d-c51ca48eb24e",
                    "display_label": "AS64496 64496",
                    "__typename": "InfraAutonomousSystem",
                },
                "properties": {
                    "is_visible": True,
                    "is_protected": True,
                    "source": {
                        "id": "1799f644-d5eb-8e37-3403-c512518ae06a",
                        "display_label": "Pop-Builder",
                        "__typename": "CoreAccount",
                    },
                    "owner": {
                        "id": "1799f645-b916-a9e8-3407-c51370cacbd0",
                        "display_label": "Engineering Team",
                        "__typename": "CoreAccount",
                    },
                },
            },
            "tags": {
                "count": 2,
                "edges": [
                    {
                        "node": {
                            "id": "1799f646-c1b4-c4eb-340f-c51512957ddc",
                            "display_label": "green",
                            "__typename": "BuiltinTag",
                        },
                        "properties": {"is_visible": True, "is_protected": None, "source": None, "owner": None},
                    },
                    {
                        "node": {
                            "id": "1799f646-c1b5-123b-3408-c51ed097b328",
                            "display_label": "red",
                            "__typename": "BuiltinTag",
                        },
                        "properties": {"is_visible": True, "is_protected": None, "source": None, "owner": None},
                    },
                ],
            },
            "primary_address": {
                "node": {
                    "id": "1799f647-7d80-0a4b-340f-c511da489224",
                    "display_label": "172.20.20.20/24",
                    "__typename": "InfraIPAddress",
                },
                "properties": {"is_visible": True, "is_protected": None, "source": None, "owner": None},
            },
            "platform": {
                "node": {
                    "id": "1799f645-e041-134d-3406-c515c08b15fc",
                    "display_label": "Arista EOS",
                    "__typename": "InfraPlatform",
                },
                "properties": {
                    "is_visible": True,
                    "is_protected": True,
                    "source": {
                        "id": "1799f644-d5eb-8e37-3403-c512518ae06a",
                        "display_label": "Pop-Builder",
                        "__typename": "CoreAccount",
                    },
                    "owner": None,
                },
            },
        }
    }
    return data


@pytest.fixture
async def artifact_definition_schema() -> NodeSchema:
    data = {
        "name": "ArtifactDefinition",
        "namespace": "Core",
        "label": "Artifact Definition",
        "default_filter": "name__value",
        "inherit_from": [],
        "display_labels": ["name__value"],
        "attributes": [
            {"name": "name", "kind": "Text", "unique": True},
            {"name": "artifact_name", "kind": "Text"},
        ],
    }
    return NodeSchema(**data)  # type: ignore


@pytest.fixture
async def artifact_definition_data():
    data = {
        "node": {
            "id": "1799fd6e-cc5d-219f-3371-c514ed70bf23",
            "display_label": "Startup Config for Edge devices",
            "__typename": "CoreArtifactDefinition",
            "name": {
                "value": "Startup Config for Edge devices",
                "is_visible": True,
                "is_protected": True,
                "source": {
                    "id": "1799fd6b-f0a9-9d23-304d-c51b05d142c5",
                    "display_label": "infrahub-demo-edge",
                    "__typename": "CoreRepository",
                },
                "owner": None,
            },
            "artifact_name": {
                "value": "startup-config",
                "is_visible": True,
                "is_protected": True,
                "source": {
                    "id": "1799fd6b-f0a9-9d23-304d-c51b05d142c5",
                    "display_label": "infrahub-demo-edge",
                    "__typename": "CoreRepository",
                },
                "owner": None,
            },
        }
    }
    return data


@pytest.fixture
async def mock_branches_list_query(httpx_mock: HTTPXMock) -> HTTPXMock:
    response = {
        "data": {
            "Branch": [
                {
                    "id": "eca306cf-662e-4e03-8180-2b788b191d3c",
                    "name": "main",
                    "sync_with_git": True,
                    "is_default": True,
                    "origin_branch": "main",
                    "branched_from": "2023-02-17T09:30:17.811719Z",
                    "has_schema_changes": False,
                },
                {
                    "id": "7d9f817a-b958-4e76-8528-8afd0c689ada",
                    "name": "cr1234",
                    "sync_with_git": False,
                    "is_default": False,
                    "origin_branch": "main",
                    "branched_from": "2023-02-17T09:30:17.811719Z",
                    "has_schema_changes": True,
                },
            ]
        }
    }

    httpx_mock.add_response(
        method="POST",
        json=response,
        match_headers={"X-Infrahub-Tracker": "query-branch-all"},
    )
    return httpx_mock


@pytest.fixture
async def mock_repositories_query_no_pagination(httpx_mock: HTTPXMock) -> HTTPXMock:
    response1 = {
        "data": {
            "repository": [
                {
                    "__typename": "CoreRepository",
                    "id": "9486cfce-87db-479d-ad73-07d80ba96a0f",
                    "name": {"value": "infrahub-demo-edge"},
                    "location": {"value": "git@github.com:dgarros/infrahub-demo-edge.git"},
                    "commit": {"value": "aaaaaaaaaaaaaaaaaaaa"},
                }
            ]
        }
    }
    response2 = {
        "data": {
            "repository": [
                {
                    "__typename": "CoreRepository",
                    "id": "9486cfce-87db-479d-ad73-07d80ba96a0f",
                    "name": {"value": "infrahub-demo-edge"},
                    "location": {"value": "git@github.com:dgarros/infrahub-demo-edge.git"},
                    "commit": {"value": "bbbbbbbbbbbbbbbbbbbb"},
                }
            ]
        }
    }

    httpx_mock.add_response(method="POST", url="http://mock/graphql/main", json=response1)
    httpx_mock.add_response(method="POST", url="http://mock/graphql/cr1234", json=response2)
    return httpx_mock


@pytest.fixture
async def mock_query_repository_all_01_no_pagination(
    httpx_mock: HTTPXMock, client: InfrahubClient, mock_schema_query_01
) -> HTTPXMock:
    response = {
        "data": {
            "repository": [
                {
                    "__typename": "CoreRepository",
                    "id": "9486cfce-87db-479d-ad73-07d80ba96a0f",
                    "name": {"value": "infrahub-demo-edge"},
                    "location": {"value": "git@github.com:opsmill/infrahub-demo-edge.git"},
                    "commit": {"value": "aaaaaaaaaaaaaaaaaaaa"},
                },
                {
                    "__typename": "CoreRepository",
                    "id": "bfae43e8-5ebb-456c-a946-bf64e930710a",
                    "name": {"value": "infrahub-demo-core"},
                    "location": {"value": "git@github.com:opsmill/infrahub-demo-core.git"},
                    "commit": {"value": "bbbbbbbbbbbbbbbbbbbb"},
                },
            ]
        }
    }

    httpx_mock.add_response(
        method="POST",
        json=response,
        match_headers={"X-Infrahub-Tracker": "query-repository-all"},
    )
    return httpx_mock


@pytest.fixture
async def mock_repositories_query(httpx_mock: HTTPXMock) -> HTTPXMock:
    response1 = {
        "data": {
            "CoreGenericRepository": {
                "count": 2,
                "edges": [
                    {
                        "node": {
                            "__typename": "CoreRepository",
                            "id": "9486cfce-87db-479d-ad73-07d80ba96a0f",
                            "name": {"value": "infrahub-demo-edge"},
                            "location": {"value": "git@github.com:dgarros/infrahub-demo-edge.git"},
                            "commit": {"value": "aaaaaaaaaaaaaaaaaaaa"},
                            "internal_status": {"value": "active"},
                        }
                    },
                    {
                        "node": {
                            "__typename": "CoreReadOnlyRepository",
                            "id": "aeff0feb-6a49-406e-b395-de7b7856026d",
                            "name": {"value": "infrahub-demo-edge-read-only"},
                            "location": {"value": "git@github.com:dgarros/infrahub-demo-edge-read-only.git"},
                            "commit": {"value": "cccccccccccccccccccc"},
                            "internal_status": {"value": "active"},
                        }
                    },
                ],
            }
        }
    }
    response2 = {
        "data": {
            "CoreGenericRepository": {
                "count": 1,
                "edges": [
                    {
                        "node": {
                            "__typename": "CoreRepository",
                            "id": "9486cfce-87db-479d-ad73-07d80ba96a0f",
                            "name": {"value": "infrahub-demo-edge"},
                            "location": {"value": "git@github.com:dgarros/infrahub-demo-edge.git"},
                            "commit": {"value": "bbbbbbbbbbbbbbbbbbbb"},
                            "internal_status": {"value": "active"},
                        }
                    },
                    {
                        "node": {
                            "__typename": "CoreReadOnlyRepository",
                            "id": "aeff0feb-6a49-406e-b395-de7b7856026d",
                            "name": {"value": "infrahub-demo-edge-read-only"},
                            "location": {"value": "git@github.com:dgarros/infrahub-demo-edge-read-only.git"},
                            "commit": {"value": "dddddddddddddddddddd"},
                            "internal_status": {"value": "active"},
                        }
                    },
                ],
            }
        }
    }

    httpx_mock.add_response(method="POST", url="http://mock/graphql/main", json=response1)
    httpx_mock.add_response(method="POST", url="http://mock/graphql/cr1234", json=response2)
    return httpx_mock


@pytest.fixture
async def mock_query_repository_page1_1(
    httpx_mock: HTTPXMock, client: InfrahubClient, mock_schema_query_01
) -> HTTPXMock:
    response = {
        "data": {
            "CoreRepository": {
                "count": 2,
                "edges": [
                    {
                        "node": {
                            "__typename": "CoreRepository",
                            "id": "9486cfce-87db-479d-ad73-07d80ba96a0f",
                            "name": {"value": "infrahub-demo-edge"},
                            "location": {"value": "git@github.com:opsmill/infrahub-demo-edge.git"},
                            "commit": {"value": "aaaaaaaaaaaaaaaaaaaa"},
                        },
                    },
                    {
                        "node": {
                            "__typename": "CoreRepository",
                            "id": "bfae43e8-5ebb-456c-a946-bf64e930710a",
                            "name": {"value": "infrahub-demo-core"},
                            "location": {"value": "git@github.com:opsmill/infrahub-demo-core.git"},
                            "commit": {"value": "bbbbbbbbbbbbbbbbbbbb"},
                        }
                    },
                ],
            }
        }
    }

    httpx_mock.add_response(
        method="POST",
        json=response,
        match_headers={"X-Infrahub-Tracker": "query-corerepository-page1"},
    )
    return httpx_mock


@pytest.fixture
async def mock_query_corenode_page1_1(httpx_mock: HTTPXMock, client: InfrahubClient, mock_schema_query_02) -> HTTPXMock:
    response = {
        "data": {
            "CoreNode": {
                "count": 2,
                "edges": [
                    {
                        "node": {
                            "__typename": "BuiltinTag",
                            "id": "179068dd-210a-8278-7532-18f23abfdd04",
                            "display_label": "RED",
                        }
                    },
                    {
                        "node": {
                            "__typename": "BuiltinLocation",
                            "id": "179068dd-21e7-f5e0-7531-18f2477f33dc",
                            "display_label": "MyLocation",
                        }
                    },
                ],
            }
        }
    }

    httpx_mock.add_response(
        method="POST",
        json=response,
        match_headers={"X-Infrahub-Tracker": "query-corenode-page1"},
    )
    return httpx_mock


@pytest.fixture
async def mock_query_repository_page1_empty(
    httpx_mock: HTTPXMock, client: InfrahubClient, mock_schema_query_01
) -> HTTPXMock:
    response: dict = {"data": {"CoreRepository": {"edges": []}}}

    httpx_mock.add_response(
        method="POST",
        json=response,
        match_headers={"X-Infrahub-Tracker": "query-corerepository-page1"},
    )
    return httpx_mock


@pytest.fixture
async def mock_query_repository_page1_2(
    httpx_mock: HTTPXMock, client: InfrahubClient, mock_schema_query_01
) -> HTTPXMock:
    response = {
        "data": {
            "CoreRepository": {
                "count": 5,
                "edges": [
                    {
                        "node": {
                            "__typename": "CoreRepository",
                            "id": "9486cfce-87db-479d-ad73-07d80ba96a0f",
                            "name": {"value": "infrahub-demo-edge"},
                            "location": {"value": "git@github.com:opsmill/infrahub-demo-edge.git"},
                            "commit": {"value": "aaaaaaaaaaaaaaaaaaaa"},
                        },
                    },
                    {
                        "node": {
                            "__typename": "CoreRepository",
                            "id": "bfae43e8-5ebb-456c-a946-bf64e930710a",
                            "name": {"value": "infrahub-demo-core"},
                            "location": {"value": "git@github.com:opsmill/infrahub-demo-core.git"},
                            "commit": {"value": "bbbbbbbbbbbbbbbbbbbb"},
                        }
                    },
                    {
                        "node": {
                            "__typename": "CoreRepository",
                            "id": "cccccccc-5ebb-456c-a946-bf64e930710a",
                            "name": {"value": "infrahub-demo-core"},
                            "location": {"value": "git@github.com:opsmill/infrahub-demo-core.git"},
                            "commit": {"value": "ccccccccccccccccccccccccccccccc"},
                        }
                    },
                ],
            }
        }
    }

    httpx_mock.add_response(
        method="POST",
        json=response,
        match_headers={"X-Infrahub-Tracker": "query-corerepository-page1"},
    )
    return httpx_mock


@pytest.fixture
async def mock_query_repository_page2_2(
    httpx_mock: HTTPXMock, client: InfrahubClient, mock_schema_query_01
) -> HTTPXMock:
    response = {
        "data": {
            "CoreRepository": {
                "count": 5,
                "edges": [
                    {
                        "node": {
                            "__typename": "CoreRepository",
                            "id": "dddddddd-87db-479d-ad73-07d80ba96a0f",
                            "name": {"value": "infrahub-demo-edge"},
                            "location": {"value": "git@github.com:opsmill/infrahub-demo-edge.git"},
                            "commit": {"value": "dddddddddddddddddddd"},
                        },
                    },
                    {
                        "node": {
                            "__typename": "CoreRepository",
                            "id": "eeeeeeee-5ebb-456c-a946-bf64e930710a",
                            "name": {"value": "infrahub-demo-core"},
                            "location": {"value": "git@github.com:opsmill/infrahub-demo-core.git"},
                            "commit": {"value": "eeeeeeeeeeeeeeeeeeeeee"},
                        }
                    },
                ],
            }
        }
    }

    httpx_mock.add_response(
        method="POST",
        json=response,
        match_headers={"X-Infrahub-Tracker": "query-corerepository-page2"},
    )
    return httpx_mock


@pytest.fixture
async def mock_schema_query_01(httpx_mock: HTTPXMock) -> HTTPXMock:
    response_text = (get_fixtures_dir() / "schema_01.json").read_text(encoding="UTF-8")

    httpx_mock.add_response(
        method="GET",
        url="http://mock/api/schema?branch=main",
        json=ujson.loads(response_text),
    )
    return httpx_mock


@pytest.fixture
async def mock_schema_query_02(httpx_mock: HTTPXMock) -> HTTPXMock:
    response_text = (get_fixtures_dir() / "schema_02.json").read_text(encoding="UTF-8")
    httpx_mock.add_response(
        method="GET", url=re.compile(r"^http://mock/api/schema\?branch=(main|cr1234)"), json=ujson.loads(response_text)
    )
    return httpx_mock


@pytest.fixture
async def mock_rest_api_artifact_definition_generate(httpx_mock: HTTPXMock) -> HTTPXMock:
    httpx_mock.add_response(method="POST", url=re.compile(r"^http://mock/api/artifact/generate/.*"))
    return httpx_mock


@pytest.fixture
async def mock_rest_api_artifact_fetch(httpx_mock: HTTPXMock) -> HTTPXMock:
    schema_response = (get_fixtures_dir() / "schema_03.json").read_text(encoding="UTF-8")

    httpx_mock.add_response(
        method="GET",
        url="http://mock/api/schema?branch=main",
        json=ujson.loads(schema_response),
    )

    graphql_response = {
        "data": {
            "CoreArtifact": {
                "edges": [
                    {
                        "id": "1799fd71-488b-84e8-3378-c5181c5ee9af",
                        "display_label": "Startup Config for Edge devices",
                        "__typename": "CoreArtifact",
                        "name": {
                            "value": "Startup Config for Edge devices",
                            "is_visible": True,
                            "is_protected": False,
                            "source": None,
                            "owner": None,
                        },
                        "status": {
                            "value": "Ready",
                            "is_visible": True,
                            "is_protected": False,
                            "source": None,
                            "owner": None,
                        },
                        "content_type": {
                            "value": "text/plain",
                            "is_visible": True,
                            "is_protected": False,
                            "source": None,
                            "owner": None,
                        },
                        "checksum": {
                            "value": "58d949c1a1c0fcd06e79bc032be8373a",
                            "is_visible": True,
                            "is_protected": False,
                            "source": None,
                            "owner": None,
                        },
                        "storage_id": {
                            "value": "1799fd71-950c-5a85-3041-c515082800ff",
                            "is_visible": True,
                            "is_protected": False,
                            "source": None,
                            "owner": None,
                        },
                        "parameters": {
                            "value": None,
                            "is_visible": True,
                            "is_protected": False,
                            "source": None,
                            "owner": None,
                        },
                        "object": {
                            "node": {
                                "id": "1799f647-203c-cd41-3409-c51d55097213",
                                "display_label": "atl1-edge1",
                                "__typename": "InfraDevice",
                            },
                            "properties": {"is_visible": True, "is_protected": None, "source": None, "owner": None},
                        },
                        "definition": {
                            "node": {
                                "id": "1799fd6e-cc5d-219f-3371-c514ed70bf23",
                                "display_label": "Startup Config for Edge devices",
                                "__typename": "CoreArtifactDefinition",
                            },
                            "properties": {"is_visible": True, "is_protected": None, "source": None, "owner": None},
                        },
                    },
                ]
            }
        }
    }

    httpx_mock.add_response(method="POST", url="http://mock/graphql/main", json=graphql_response)

    artifact_content = """!device startup config
ip name-server 1.1.1.1
"""

    httpx_mock.add_response(method="GET", url=re.compile(r"^http://mock/api/storage/object/.*"), text=artifact_content)
    return httpx_mock


@pytest.fixture
async def mock_rest_api_artifact_generate(httpx_mock: HTTPXMock) -> HTTPXMock:
    schema_response = (get_fixtures_dir() / "schema_04.json").read_text(encoding="UTF-8")

    httpx_mock.add_response(
        method="GET",
        url="http://mock/api/schema?branch=main",
        json=ujson.loads(schema_response),
    )

    artifact_graphql_response = {
        "data": {
            "CoreArtifact": {
                "edges": [
                    {
                        "id": "1799fd71-488b-84e8-3378-c5181c5ee9af",
                        "display_label": "Startup Config for Edge devices",
                        "__typename": "CoreArtifact",
                        "name": {
                            "value": "Startup Config for Edge devices",
                            "is_visible": True,
                            "is_protected": False,
                            "source": None,
                            "owner": None,
                        },
                        "status": {
                            "value": "Ready",
                            "is_visible": True,
                            "is_protected": False,
                            "source": None,
                            "owner": None,
                        },
                        "content_type": {
                            "value": "text/plain",
                            "is_visible": True,
                            "is_protected": False,
                            "source": None,
                            "owner": None,
                        },
                        "checksum": {
                            "value": "58d949c1a1c0fcd06e79bc032be8373a",
                            "is_visible": True,
                            "is_protected": False,
                            "source": None,
                            "owner": None,
                        },
                        "storage_id": {
                            "value": "1799fd71-950c-5a85-3041-c515082800ff",
                            "is_visible": True,
                            "is_protected": False,
                            "source": None,
                            "owner": None,
                        },
                        "parameters": {
                            "value": None,
                            "is_visible": True,
                            "is_protected": False,
                            "source": None,
                            "owner": None,
                        },
                        "object": {
                            "node": {
                                "id": "1799f647-203c-cd41-3409-c51d55097213",
                                "display_label": "atl1-edge1",
                                "__typename": "InfraDevice",
                            },
                            "properties": {"is_visible": True, "is_protected": None, "source": None, "owner": None},
                        },
                        "definition": {
                            "node": {
                                "id": "1799fd6e-cc5d-219f-3371-c514ed70bf23",
                                "display_label": "Startup Config for Edge devices",
                                "__typename": "CoreArtifactDefinition",
                            },
                            "properties": {"is_visible": True, "is_protected": None, "source": None, "owner": None},
                        },
                    },
                ]
            },
        }
    }
    httpx_mock.add_response(method="POST", url="http://mock/graphql/main", json=artifact_graphql_response)

    artifact_definition_graphql_response = {
        "data": {
            "CoreArtifactDefinition": {
                "count": 1,
                "edges": [
                    {
                        "node": {
                            "id": "1799fd6e-cc5d-219f-3371-c514ed70bf23",
                            "display_label": "Startup Config for Edge devices",
                            "__typename": "CoreArtifactDefinition",
                            "name": {
                                "value": "Startup Config for Edge devices",
                                "is_visible": True,
                                "is_protected": True,
                                "source": {
                                    "id": "1799fd6b-f0a9-9d23-304d-c51b05d142c5",
                                    "display_label": "infrahub-demo-edge",
                                    "__typename": "CoreRepository",
                                },
                                "owner": None,
                            },
                            "artifact_name": {
                                "value": "startup-config",
                                "is_visible": True,
                                "is_protected": True,
                                "source": {
                                    "id": "1799fd6b-f0a9-9d23-304d-c51b05d142c5",
                                    "display_label": "infrahub-demo-edge",
                                    "__typename": "CoreRepository",
                                },
                                "owner": None,
                            },
                            "description": {
                                "value": None,
                                "is_visible": True,
                                "is_protected": False,
                                "source": None,
                                "owner": None,
                            },
                            "parameters": {
                                "value": {"device": "name__value"},
                                "is_visible": True,
                                "is_protected": True,
                                "source": {
                                    "id": "1799fd6b-f0a9-9d23-304d-c51b05d142c5",
                                    "display_label": "infrahub-demo-edge",
                                    "__typename": "CoreRepository",
                                },
                                "owner": None,
                            },
                            "content_type": {
                                "value": "text/plain",
                                "is_visible": True,
                                "is_protected": True,
                                "source": {
                                    "id": "1799fd6b-f0a9-9d23-304d-c51b05d142c5",
                                    "display_label": "infrahub-demo-edge",
                                    "__typename": "CoreRepository",
                                },
                                "owner": None,
                            },
                            "targets": {
                                "node": {
                                    "id": "1799f645-e03b-0bae-3400-c51c3f21895c",
                                    "display_label": "edge_router",
                                    "__typename": "CoreStandardGroup",
                                },
                                "properties": {
                                    "is_visible": True,
                                    "is_protected": True,
                                    "source": {
                                        "id": "1799fd6b-f0a9-9d23-304d-c51b05d142c5",
                                        "display_label": "infrahub-demo-edge",
                                        "__typename": "CoreRepository",
                                    },
                                    "owner": None,
                                },
                            },
                            "transformation": {
                                "node": {
                                    "id": "1799fd6e-791b-c12c-337d-c51ec00bba63",
                                    "display_label": "device_startup",
                                    "__typename": "CoreRFile",
                                },
                                "properties": {
                                    "is_visible": True,
                                    "is_protected": True,
                                    "source": {
                                        "id": "1799fd6b-f0a9-9d23-304d-c51b05d142c5",
                                        "display_label": "infrahub-demo-edge",
                                        "__typename": "CoreRepository",
                                    },
                                    "owner": None,
                                },
                            },
                        }
                    }
                ],
            }
        }
    }
    httpx_mock.add_response(method="POST", url="http://mock/graphql/main", json=artifact_definition_graphql_response)
    httpx_mock.add_response(method="POST", url=re.compile(r"^http://mock/api/artifact/generate/.*"))


@pytest.fixture
async def mock_query_mutation_schema_dropdown_add(httpx_mock: HTTPXMock) -> None:
    response = {"data": {"SchemaDropdownAdd": {"ok": True}}}
    httpx_mock.add_response(method="POST", url="http://mock/graphql", json=response)


@pytest.fixture
async def mock_query_mutation_schema_dropdown_remove(httpx_mock: HTTPXMock) -> None:
    response = {"data": {"SchemaDropdownRemove": {"ok": True}}}
    httpx_mock.add_response(method="POST", url="http://mock/graphql", json=response)


@pytest.fixture
async def mock_query_mutation_schema_enum_add(httpx_mock: HTTPXMock) -> None:
    response = {"data": {"SchemaEnumAdd": {"ok": True}}}
    httpx_mock.add_response(method="POST", url="http://mock/graphql", json=response)


@pytest.fixture
async def mock_query_mutation_schema_enum_remove(httpx_mock: HTTPXMock) -> None:
    response = {"data": {"SchemaEnumRemove": {"ok": True}}}
    httpx_mock.add_response(method="POST", url="http://mock/graphql", json=response)


@pytest.fixture
async def mock_query_mutation_location_create_failed(httpx_mock: HTTPXMock) -> HTTPXMock:
    response1 = {
        "data": {"BuiltinLocationCreate": {"ok": True, "object": {"id": "17aec828-9814-ce00-3f20-1a053670f1c8"}}}
    }
    response2 = {
        "data": {"BuiltinLocationCreate": None},
        "errors": [
            {
                "message": "An object already exist with this value: name: JFK1 at name",
                "locations": [{"line": 2, "column": 5}],
                "path": ["BuiltinLocationCreate"],
            }
        ],
    }
    url_regex = re.compile(r"http://mock/graphql/main")
    httpx_mock.add_response(method="POST", url=url_regex, json=response1)
    httpx_mock.add_response(method="POST", url=url_regex, json=response2)
    return httpx_mock


@pytest.fixture
def query_01() -> str:
    """Simple query with one document"""
    query = """
    query {
        TestPerson {
            edges {
                node {
                    name {
                        value
                    }
                    cars {
                        edges {
                            node {
                                name {
                                    value
                                }
                            }
                        }
                    }
                }
            }
        }
    }
    """
    return query


@pytest.fixture
def query_02() -> str:
    query = """
    query {
        TestPerson {
            edges {
                node {
                    name {
                        value
                    }

                    cars {
                        edges {
                            node {
                                name {
                                    value
                                }
                                ... on TestElectricCar {
                                    nbr_engine {
                                        value
                                    }
                                    member_of_groups {
                                        edges {
                                            node {
                                                id
                                            }
                                        }
                                    }
                                }
                                ... on TestGazCar {
                                    mpg {
                                        value
                                        is_protected
                                    }
                                }
                            }
                        }
                    }
                }
            }
        }
    }
    """
    return query


@pytest.fixture
def query_03() -> str:
    """Advanced Query with 2 documents"""
    query = """
    query FirstQuery {
        TestPerson {
            edges {
                node {
                    name {
                        value
                    }
                    cars {
                        edges {
                            node {
                                name {
                                    value
                                }
                            }
                        }
                    }
                }
            }
        }
    }
    mutation FirstMutation {
        TestPersonCreate(
            data: {
                name: { value: "person1"}
            }
        ){
            ok
            object {
                id
            }
        }
    }
    """
    return query


@pytest.fixture
def query_04() -> str:
    """Simple query with variables"""
    query = """
    query ($person: String!){
        TestPerson(name__value: $person) {
            edges {
                node {
                    name {
                        value
                    }
                }
            }
        }
    }
    """
    return query


@pytest.fixture
def query_05() -> str:
    query = """
    query MyQuery {
        CoreRepository {
            edges {
                node {
                    name {
                        value
                    }
                    tags {
                        edges {
                            node {
                                id
                            }
                        }
                    }
                }
            }
        }
    }
    mutation MyMutation($myvar: String) {
        CoreRepositoryCreate (data: {
            name: { value: $myvar},
            location: { value: "location1"},
        }) {
            ok
        }
    }
    """

    return query


@pytest.fixture
def query_06() -> str:
    """Simple query with variables"""
    query = """
    query (
        $str1: String,
        $str2: String = "default2",
        $str3: String!
        $int1: Int,
        $int2: Int = 12,
        $int3: Int!
        $bool1: Boolean,
        $bool2: Boolean = true,
        $bool3: Boolean!
    ){
        TestPerson(name__value: $person) {
            edges {
                node {
                    name {
                        value
                    }
                }
            }
        }
    }
    """
    return query


@pytest.fixture
def bad_query_01() -> str:
    query = """
    query {
        TestPerson {
            edges {
                node {
                    name {
                        value
                    }
                    cars {
                        edges {
                            node {
                                name {
                                    value
                                }
                            }
                        }
                    }
                }
            }
    """
    return query


@pytest.fixture
def query_introspection() -> str:
    query = """
        query IntrospectionQuery {
            __schema {
                queryType {
                    name
                }
                mutationType {
                    name
                }
                subscriptionType {
                    name
                }
                types {
                    ...FullType
                }
                directives {
                    name
                    description
                    locations
                    args {
                        ...InputValue
                    }
                }
            }
        }

        fragment FullType on __Type {
            kind
            name
            description
            fields(includeDeprecated: true) {
                name
                description
                args {
                    ...InputValue
                }
                type {
                    ...TypeRef
                }
                isDeprecated
                deprecationReason
            }
            inputFields {
                ...InputValue
            }
            interfaces {
                ...TypeRef
            }
            enumValues(includeDeprecated: true) {
                name
                description
                isDeprecated
                deprecationReason
            }
            possibleTypes {
                ...TypeRef
            }
        }

        fragment InputValue on __InputValue {
            name
            description
            type {
                ...TypeRef
            }
                defaultValue
            }

            fragment TypeRef on __Type {
            kind
            name
            ofType {
                kind
                name
                ofType {
                    kind
                    name
                    ofType {
                        kind
                        name
                        ofType {
                            kind
                            name
                            ofType {
                                kind
                                name
                                ofType {
                                    kind
                                    name
                                    ofType {
                                        kind
                                        name
                                    }
                                }
                            }
                        }
                    }
                }
            }
        }
    """
    return query


@pytest.fixture
async def mock_schema_query_ipam(httpx_mock: HTTPXMock) -> HTTPXMock:
    response_text = (get_fixtures_dir() / "schema_ipam.json").read_text(encoding="UTF-8")

    httpx_mock.add_response(method="GET", url="http://mock/api/schema?branch=main", json=ujson.loads(response_text))
    return httpx_mock
