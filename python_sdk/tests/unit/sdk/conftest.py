import os
from dataclasses import dataclass
from pathlib import Path

import pytest
import ujson
from pytest_httpx import HTTPXMock

from infrahub_sdk import InfrahubClient, InfrahubClientSync
from infrahub_sdk.schema import BranchSupportType, NodeSchema
from infrahub_sdk.utils import get_fixtures_dir

# pylint: disable=redefined-outer-name,unused-argument


@dataclass
class BothClients:
    sync: InfrahubClientSync
    standard: InfrahubClient


@pytest.fixture
async def client() -> InfrahubClient:
    return await InfrahubClient.init(address="http://mock", insert_tracker=True, pagination_size=3)


@pytest.fixture
async def clients() -> BothClients:
    both = BothClients(
        standard=await InfrahubClient.init(address="http://mock", insert_tracker=True, pagination_size=3),
        sync=InfrahubClientSync.init(address="http://mock", insert_tracker=True, pagination_size=3),
    )
    return both


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
        "name": "RFile",
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
                "identifier": "rfile__repository",
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
async def mock_branches_list_query(httpx_mock: HTTPXMock) -> HTTPXMock:
    response = {
        "data": {
            "Branch": [
                {
                    "id": "eca306cf-662e-4e03-8180-2b788b191d3c",
                    "name": "main",
                    "is_data_only": False,
                    "is_default": True,
                    "origin_branch": "main",
                    "branched_from": "2023-02-17T09:30:17.811719Z",
                },
                {
                    "id": "7d9f817a-b958-4e76-8528-8afd0c689ada",
                    "name": "cr1234",
                    "is_data_only": True,
                    "is_default": False,
                    "origin_branch": "main",
                    "branched_from": "2023-02-17T09:30:17.811719Z",
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
            "CoreRepository": {
                "count": 1,
                "edges": [
                    {
                        "node": {
                            "__typename": "CoreRepository",
                            "id": "9486cfce-87db-479d-ad73-07d80ba96a0f",
                            "name": {"value": "infrahub-demo-edge"},
                            "location": {"value": "git@github.com:dgarros/infrahub-demo-edge.git"},
                            "commit": {"value": "aaaaaaaaaaaaaaaaaaaa"},
                        }
                    }
                ],
            }
        }
    }
    response2 = {
        "data": {
            "CoreRepository": {
                "count": 1,
                "edges": [
                    {
                        "node": {
                            "__typename": "CoreRepository",
                            "id": "9486cfce-87db-479d-ad73-07d80ba96a0f",
                            "name": {"value": "infrahub-demo-edge"},
                            "location": {"value": "git@github.com:dgarros/infrahub-demo-edge.git"},
                            "commit": {"value": "bbbbbbbbbbbbbbbbbbbb"},
                        }
                    }
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
    response_text = Path(os.path.join(get_fixtures_dir(), "schema_01.json")).read_text(encoding="UTF-8")

    httpx_mock.add_response(
        method="GET",
        url="http://mock/api/schema/?branch=main",
        json=ujson.loads(response_text),
    )
    return httpx_mock


@pytest.fixture
async def mock_schema_query_02(httpx_mock: HTTPXMock) -> HTTPXMock:
    response_text = Path(os.path.join(get_fixtures_dir(), "schema_02.json")).read_text(encoding="UTF-8")

    httpx_mock.add_response(
        method="GET",
        url="http://mock/api/schema/?branch=main",
        json=ujson.loads(response_text),
    )
    return httpx_mock
