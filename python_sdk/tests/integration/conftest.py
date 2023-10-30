import asyncio
import json
import os
from typing import Any, Dict, Optional

import httpx
import pytest
from fastapi.testclient import TestClient

import infrahub.config as config
from infrahub.core.initialization import first_time_initialization, initialization
from infrahub.core.node import Node
from infrahub.core.utils import delete_all_nodes
from infrahub.database import InfrahubDatabase, get_db
from infrahub.lock import initialize_lock
from infrahub_client.schema import NodeSchema
from infrahub_client.types import HTTPMethod
from infrahub_client.utils import str_to_bool

BUILD_NAME = os.environ.get("INFRAHUB_BUILD_NAME", "infrahub")
TEST_IN_DOCKER = str_to_bool(os.environ.get("INFRAHUB_TEST_IN_DOCKER", "false"))


# pylint: disable=redefined-outer-name
class InfrahubTestClient(TestClient):
    def _request(
        self, url: str, method: HTTPMethod, headers: Dict[str, Any], timeout: int, payload: Optional[Dict] = None
    ) -> httpx.Response:
        content = None
        if payload:
            content = str(json.dumps(payload)).encode("UTF-8")
        with self as client:
            return client.request(method=method.value, url=url, headers=headers, timeout=timeout, content=content)

    async def async_request(
        self, url: str, method: HTTPMethod, headers: Dict[str, Any], timeout: int, payload: Optional[Dict] = None
    ) -> httpx.Response:
        return self._request(url=url, method=method, headers=headers, timeout=timeout, payload=payload)

    def sync_request(
        self, url: str, method: HTTPMethod, headers: Dict[str, Any], timeout: int, payload: Optional[Dict] = None
    ) -> httpx.Response:
        return self._request(url=url, method=method, headers=headers, timeout=timeout, payload=payload)


@pytest.fixture(scope="session")
def event_loop():
    """Overrides pytest default function scoped event loop"""
    policy = asyncio.get_event_loop_policy()
    loop = policy.new_event_loop()
    yield loop
    loop.close()


@pytest.fixture(scope="session", autouse=True)
def execute_before_any_test(worker_id, tmpdir_factory):
    config.load_and_exit()
    initialize_lock()

    if TEST_IN_DOCKER:
        try:
            db_id = int(worker_id[2]) + 1
        except (ValueError, IndexError):
            db_id = 1
        config.SETTINGS.database.address = f"{BUILD_NAME}-database-{db_id}"
        config.SETTINGS.storage.settings = {"directory": "/opt/infrahub/storage"}
    else:
        storage_dir = tmpdir_factory.mktemp("storage")
        config.SETTINGS.storage.settings = {"directory": str(storage_dir)}

    config.SETTINGS.broker.enable = False
    config.SETTINGS.cache.enable = False
    config.SETTINGS.miscellaneous.start_background_runner = False
    config.SETTINGS.security.secret_key = "4e26b3d9-b84f-42c9-a03f-fee3ada3b2fa"
    config.SETTINGS.main.internal_address = "http://mock"


@pytest.fixture(scope="module")
async def db() -> InfrahubDatabase:
    driver = InfrahubDatabase(driver=await get_db(retry=1))

    yield driver

    await driver.close()


@pytest.fixture(scope="module")
async def init_db_base(db: InfrahubDatabase):
    await delete_all_nodes(db=db)
    await first_time_initialization(db=db)
    await initialization(db=db)


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
            {"name": "tags", "peer": "BuiltinTag", "optional": True, "cardinality": "many"},
            {"name": "primary_tag", "peer": "BultinTag", "optional": True, "cardinality": "one"},
        ],
    }
    return NodeSchema(**data)  # type: ignore


@pytest.fixture
async def location_cdg(db: InfrahubDatabase, tag_blue: Node, tag_red: Node) -> Node:
    obj = await Node.init(schema="BuiltinLocation", db=db)
    await obj.new(db=db, name="cdg01", type="SITE", tags=[tag_blue, tag_red])
    await obj.save(db=db)
    return obj


@pytest.fixture
async def tag_blue(db: InfrahubDatabase) -> Node:
    obj = await Node.init(schema="BuiltinTag", db=db)
    await obj.new(db=db, name="Blue")
    await obj.save(db=db)
    return obj


@pytest.fixture
async def tag_red(db: InfrahubDatabase) -> Node:
    obj = await Node.init(schema="BuiltinTag", db=db)
    await obj.new(db=db, name="Red")
    await obj.save(db=db)
    return obj


@pytest.fixture
async def tag_green(db: InfrahubDatabase) -> Node:
    obj = await Node.init(schema="BuiltinTag", db=db)
    await obj.new(db=db, name="Green")
    await obj.save(db=db)
    return obj


@pytest.fixture
async def first_account(db: InfrahubDatabase) -> Node:
    obj = await Node.init(db=db, schema="CoreAccount")
    await obj.new(db=db, name="First Account", type="Git", password="TestPassword123")
    await obj.save(db=db)
    return obj


@pytest.fixture
async def second_account(db: InfrahubDatabase) -> Node:
    obj = await Node.init(db=db, schema="CoreAccount")
    await obj.new(db=db, name="Second Account", type="Git", password="TestPassword123")
    await obj.save(db=db)
    return obj


@pytest.fixture
async def repo01(db: InfrahubDatabase) -> Node:
    obj = await Node.init(db=db, schema="CoreRepository")
    await obj.new(db=db, name="repo01", location="https://github.com/my/repo.git")
    await obj.save(db=db)
    return obj


@pytest.fixture
async def repo99(db: InfrahubDatabase) -> Node:
    obj = await Node.init(db=db, schema="CoreRepository")
    await obj.new(db=db, name="repo99", location="https://github.com/my/repo99.git")
    await obj.save(db=db)
    return obj


@pytest.fixture
async def gqlquery01(db: InfrahubDatabase) -> Node:
    obj = await Node.init(db=db, schema="CoreGraphQLQuery")
    await obj.new(db=db, name="query01", query="query { device { name { value }}}")
    await obj.save(db=db)
    return obj


@pytest.fixture
async def gqlquery02(db: InfrahubDatabase, repo01: Node, tag_blue: Node, tag_red: Node) -> Node:
    obj = await Node.init(db=db, schema="CoreGraphQLQuery")
    await obj.new(
        db=db,
        name="query02",
        query="query { CoreRepository { edges { node { name { value }}}}}",
        repository=repo01,
        tags=[tag_blue, tag_red],
    )
    await obj.save(db=db)
    return obj


@pytest.fixture
async def gqlquery03(db: InfrahubDatabase, repo01: Node, tag_blue: Node, tag_red: Node) -> Node:
    obj = await Node.init(db=db, schema="CoreGraphQLQuery")
    await obj.new(
        db=db,
        name="query03",
        query="query { CoreRepository { edges { node { name { value }}}}}",
        repository=repo01,
        tags=[tag_blue, tag_red],
    )
    await obj.save(db=db)
    return obj


@pytest.fixture
async def schema_extension_01() -> Dict[str, Any]:
    return {
        "version": "1.0",
        "nodes": [
            {
                "name": "Rack",
                "namespace": "Infra",
                "description": "A Rack represents a physical two- or four-post equipment rack in which devices can be installed.",
                "label": "Rack",
                "default_filter": "name__value",
                "display_labels": ["name__value"],
                "attributes": [
                    {"name": "name", "kind": "Text"},
                    {"name": "description", "kind": "Text", "optional": True},
                ],
                "relationships": [
                    {
                        "name": "location",
                        "peer": "BuiltinLocation",
                        "optional": False,
                        "cardinality": "one",
                        "kind": "Attribute",
                    },
                    {
                        "name": "tags",
                        "peer": "BuiltinTag",
                        "optional": True,
                        "cardinality": "many",
                        "kind": "Attribute",
                    },
                ],
            }
        ],
        "extensions": {
            "nodes": [
                {
                    "kind": "BuiltinLocation",
                    "relationships": [
                        {
                            "name": "racks",
                            "peer": "InfraRack",
                            "optional": True,
                            "cardinality": "many",
                            "kind": "Generic",
                        }
                    ],
                }
            ]
        },
    }


@pytest.fixture
async def schema_extension_02() -> Dict[str, Any]:
    return {
        "version": "1.0",
        "nodes": [
            {
                "name": "Contract",
                "namespace": "Procurement",
                "description": "Generic Contract",
                "label": "Contract",
                "display_labels": ["contract_ref__value"],
                "order_by": ["contract_ref__value"],
                "attributes": [
                    {"name": "contract_ref", "label": "Contract Reference", "kind": "Text", "unique": True},
                    {"name": "description", "kind": "Text", "optional": True},
                ],
                "relationships": [
                    {
                        "name": "Organization",
                        "peer": "CoreOrganization",
                        "optional": False,
                        "cardinality": "one",
                        "kind": "Attribute",
                    }
                ],
            }
        ],
        "extensions": {
            "nodes": [
                {
                    "kind": "CoreOrganization",
                    "relationships": [
                        {
                            "name": "contract",
                            "peer": "ProcurementContract",
                            "optional": True,
                            "cardinality": "many",
                            "kind": "Component",
                        }
                    ],
                }
            ]
        },
    }
