from __future__ import annotations

from typing import TYPE_CHECKING, Any

import pytest

from infrahub.auth import AccountSession, AuthType
from infrahub.context import InfrahubContext
from infrahub.core.manager import NodeManager
from infrahub.core.node import Node
from infrahub.core.protocols import CoreNumberPool
from infrahub.core.registry import registry
from infrahub.core.schema.attribute_parameters import NumberPoolParameters
from infrahub.exceptions import NodeNotFoundError
from infrahub.pools.registration import get_branches_with_schema_number_pool
from infrahub.pools.tasks import validate_schema_number_pools
from infrahub.services import InfrahubServices
from infrahub.services.adapters.cache.redis import RedisCache
from infrahub.workers.dependencies import build_cache
from tests.helpers.test_app import TestInfrahubApp

if TYPE_CHECKING:
    from pathlib import Path

    from infrahub_sdk import InfrahubClient

    from infrahub.database import InfrahubDatabase
    from tests.adapters.message_bus import BusSimulator

node_schema_definition: dict[str, Any] = {
    "name": "NumberAttribute",
    "namespace": "Test",
    "attributes": [
        {"name": "name", "kind": "Text", "unique": True},
        {
            "name": "assigned_number",
            "kind": "NumberPool",
            "optional": False,
            "unique": True,
            "read_only": True,
            "parameters": {"start_range": 10, "end_range": 25},
        },
    ],
}


class TestMutationGenerator(TestInfrahubApp):
    @pytest.fixture(scope="class")
    async def initial_dataset(
        self,
        db: InfrahubDatabase,
        initialize_registry: None,
        git_repos_source_dir_module_scope: Path,
        client: InfrahubClient,
        bus_simulator: BusSimulator,
        prefect_test_fixture,
        dependency_provider,
    ) -> None:
        with dependency_provider.scope(build_cache, RedisCache):
            schema = {"version": "1.0", "nodes": [node_schema_definition]}
            schema_load_response = await client.schema.load(schemas=[schema], wait_until_converged=True)
            assert not schema_load_response.errors

    async def test_numberpool_assignment(
        self, db: InfrahubDatabase, initial_dataset: None, client: InfrahubClient, default_branch
    ) -> None:
        assert True

        incident_1 = await Node.init(db=db, schema="TestNumberAttribute")
        await incident_1.new(db=db, name="The first thing")
        await incident_1.save(db=db)

        test_schema = registry.schema.get_node_schema(name="TestNumberAttribute")
        test_attribute = test_schema.get_attribute(name="assigned_number")
        assert isinstance(test_attribute.parameters, NumberPoolParameters)
        number_pool_id = test_attribute.parameters.number_pool_id

        number_pool_pre = await NodeManager.find_object(
            db=db,
            kind=CoreNumberPool,
            id=number_pool_id,
        )
        assert number_pool_pre.start_range.value == 10

        initial_branches = get_branches_with_schema_number_pool(
            kind="TestNumberAttribute", attribute_name="assigned_number"
        )

        assert initial_branches == ["main"]
        node_schema_definition["state"] = "absent"
        schema = {"version": "1.0", "nodes": [node_schema_definition]}
        schema_load_response = await client.schema.load(schemas=[schema], wait_until_converged=True)
        assert not schema_load_response.errors

        after_purge = get_branches_with_schema_number_pool(kind="TestNumberAttribute", attribute_name="assigned_number")
        assert after_purge == []

        service = await InfrahubServices.new(database=db)
        context = InfrahubContext.init(
            branch=default_branch,
            account=AccountSession(auth_type=AuthType.NONE, authenticated=False, account_id=""),
        )

        await validate_schema_number_pools(branch_name=registry.default_branch, context=context, service=service)

        with pytest.raises(NodeNotFoundError):
            await NodeManager.find_object(
                db=db,
                kind=CoreNumberPool,
                id=number_pool_id,
            )
