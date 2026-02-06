from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from infrahub_sdk.graphql import Query

from infrahub.core.constants import HashableModelState
from infrahub.core.manager import NodeManager
from infrahub.core.node import Node
from infrahub.core.protocols import CoreNumberPool
from infrahub.core.registry import registry
from infrahub.core.schema import AttributeSchema, NodeSchema, SchemaRoot
from infrahub.core.schema.attribute_parameters import NumberPoolParameters
from infrahub.exceptions import NodeNotFoundError
from infrahub.graphql.registry import registry as graphql_registry
from infrahub.pools.registration import get_branches_with_schema_number_pool
from infrahub.pools.schema_number_pool_synchronizer import SchemaNumberPoolSynchronizer
from infrahub.pools.schema_number_pool_upserter import SchemaNumberPoolUpserter
from infrahub.services.adapters.cache.redis import RedisCache
from infrahub.workers.dependencies import build_cache
from tests.helpers.schema.snow import SNOW_INCIDENT, SNOW_REQUEST, SNOW_TASK
from tests.helpers.test_app import TestInfrahubApp

if TYPE_CHECKING:
    from pathlib import Path

    from fast_depends import Provider
    from infrahub_sdk import InfrahubClient

    from infrahub.core.branch import Branch
    from infrahub.database import InfrahubDatabase
    from tests.adapters.message_bus import BusSimulator

node_schema_definition = NodeSchema(
    name="NumberAttribute",
    namespace="Test",
    attributes=[
        AttributeSchema(name="name", kind="Text", unique=True),
        AttributeSchema(
            name="assigned_number",
            kind="NumberPool",
            optional=False,
            unique=True,
            read_only=True,
            parameters=NumberPoolParameters(start_range=10, end_range=25),
        ),
    ],
)

number_pool_allocation_query = Query(
    query={
        "InfrahubResourcePoolAllocated": {"@filters": {"pool_id": "$pool_id", "resource_id": "$pool_id"}, "count": None}
    },
    variables={"pool_id": str},
)


class TestAttributeNumberPoolLifecycle(TestInfrahubApp):
    async def _post_schema_load_updates(self, db: InfrahubDatabase) -> None:
        upserter = SchemaNumberPoolUpserter(db=db, schema_manager=registry.schema)
        snps = SchemaNumberPoolSynchronizer(db=db, schema_manager=registry.schema, upserter=upserter)
        await snps.run()
        graphql_registry.clear_cache()

    @pytest.fixture(scope="class")
    def initial_schema(self) -> SchemaRoot:
        schema = SchemaRoot(
            version="1.0",
            generics=[SNOW_TASK],
            nodes=[node_schema_definition, SNOW_INCIDENT, SNOW_REQUEST],
        )
        return schema

    @pytest.fixture(scope="class")
    async def initial_dataset(
        self,
        db: InfrahubDatabase,
        initialize_registry: None,
        git_repos_source_dir_module_scope: Path,
        client: InfrahubClient,
        bus_simulator: BusSimulator,
        prefect_test_fixture: None,
        dependency_provider: Provider,
        initial_schema: SchemaRoot,
    ) -> None:
        with dependency_provider.scope(build_cache, RedisCache):
            schema_load_response = await client.schema.load(
                schemas=[initial_schema.model_dump()], wait_until_converged=True
            )
            assert not schema_load_response.errors
        await self._post_schema_load_updates(db)

    async def test_numberpool_assignment_direct_node(
        self, db: InfrahubDatabase, initial_dataset: None, client: InfrahubClient, default_branch: Branch
    ) -> None:
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

        incident_1 = await Node.init(db=db, schema="TestNumberAttribute")
        await incident_1.new(db=db, name="The first thing")
        await incident_1.save(db=db)

        initial_branches = get_branches_with_schema_number_pool(
            kind="TestNumberAttribute", attribute_name="assigned_number"
        )

        assert initial_branches == ["main"]
        node_schema_definition.state = HashableModelState.ABSENT
        schema = SchemaRoot(version="1.0", nodes=[node_schema_definition])
        schema_load_response = await client.schema.load(schemas=[schema.model_dump()], wait_until_converged=True)
        assert not schema_load_response.errors
        await self._post_schema_load_updates(db)

        after_purge = get_branches_with_schema_number_pool(kind="TestNumberAttribute", attribute_name="assigned_number")
        assert after_purge == []

        with pytest.raises(NodeNotFoundError):
            await NodeManager.find_object(
                db=db,
                kind=CoreNumberPool,
                id=number_pool_id,
            )

    async def test_numberpool_assignment_from_generic(
        self, db: InfrahubDatabase, initial_dataset: None, client: InfrahubClient, default_branch: Branch
    ) -> None:
        await self._post_schema_load_updates(db)

        test_schema = registry.schema.get_node_schema(name="SnowIncident")
        test_attribute = test_schema.get_attribute(name="number")
        assert isinstance(test_attribute.parameters, NumberPoolParameters)
        number_pool_id = test_attribute.parameters.number_pool_id

        number_pool_pre = await NodeManager.find_object(
            db=db,
            kind=CoreNumberPool,
            id=number_pool_id,
        )
        assert number_pool_pre.start_range.value == 1

        incident_1 = await Node.init(db=db, schema="SnowIncident")
        await incident_1.new(db=db, title="The very first incident")
        await incident_1.save(db=db)

        initial_branches = get_branches_with_schema_number_pool(kind="SnowTask", attribute_name="number")

        assert initial_branches == ["main"]
        snow_task = SNOW_TASK.duplicate()
        snow_task.state = HashableModelState.ABSENT
        snow_request = SNOW_REQUEST.duplicate()
        snow_request.state = HashableModelState.ABSENT
        snow_incident = SNOW_INCIDENT.duplicate()
        snow_incident.state = HashableModelState.ABSENT
        schema = SchemaRoot(version="1.0", generics=[snow_task], nodes=[snow_request, snow_incident])
        schema_load_response = await client.schema.load(schemas=[schema.model_dump()], wait_until_converged=True)
        assert not schema_load_response.errors
        await self._post_schema_load_updates(db)

        after_purge = get_branches_with_schema_number_pool(kind="SnowTask", attribute_name="number")
        assert after_purge == []

        with pytest.raises(NodeNotFoundError):
            await NodeManager.find_object(
                db=db,
                kind=CoreNumberPool,
                id=number_pool_id,
            )

    async def test_numberpool_existing_nodes(
        self,
        db: InfrahubDatabase,
        client: InfrahubClient,
        redis: dict[int, int] | None,
        default_branch: Branch,
        initial_schema: SchemaRoot,
    ) -> None:
        schema_load_response = await client.schema.load(
            schemas=[initial_schema.model_dump()], wait_until_converged=True
        )
        assert not schema_load_response.errors
        await self._post_schema_load_updates(db)

        # Create incidents to ensure there are some data into the database
        for idx in range(1, 6):
            incident = await Node.init(db=db, schema=SNOW_INCIDENT.kind)
            await incident.new(db=db, title=f"Incident #{idx}")
            await incident.save(db=db)

        pools_before = await client.all(kind="CoreNumberPool", branch=default_branch.name)
        assert len(pools_before) == 1
        expected_pool_names = {("SnowTask", "number")}
        number_pool_details = {(pool.node.value, pool.node_attribute.value) for pool in pools_before}
        assert number_pool_details == expected_pool_names

        # Add a new attribute to the existing schema with a large pool
        new_schema = initial_schema.duplicate()
        incident_schema = new_schema.get(name=SNOW_INCIDENT.kind)
        incident_schema.attributes.append(
            AttributeSchema(
                name="new_number",
                kind="NumberPool",
                optional=False,
                read_only=True,
                parameters=NumberPoolParameters(start_range=10, end_range=30),
            ),
        )

        schema_load_response = await client.schema.load(schemas=[new_schema.model_dump()], wait_until_converged=True)
        assert not schema_load_response.errors
        await self._post_schema_load_updates(db)

        # Validate that the new pool has been created
        pools_after = await client.all(kind="CoreNumberPool", branch=default_branch.name)
        assert len(pools_after) == 2
        expected_pool_names.add(("SnowIncident", "new_number"))
        number_pool_details = {(pool.node.value, pool.node_attribute.value) for pool in pools_after}
        assert number_pool_details == expected_pool_names

        # Validate that the existing incidents have been updated with the new number
        incidents = await registry.manager.query(db=db, branch=default_branch, schema=incident_schema)
        assert incidents[0].new_number.value == 10

        incident10 = await client.create(kind=SNOW_INCIDENT.kind, title="Incident #10", branch=default_branch.name)
        await incident10.save()

        # Ensure the calculated allocation is correct for both pools
        number_pool = [pool for pool in pools_after if pool.node_attribute.value == "number"][0]
        number_allocation = await client.execute_graphql(
            query=number_pool_allocation_query.render(), variables={"pool_id": number_pool.id}
        )
        assert number_allocation["InfrahubResourcePoolAllocated"]["count"] == 6

        new_number_pool = [pool for pool in pools_after if pool.node_attribute.value == "new_number"][0]
        new_number_allocation = await client.execute_graphql(
            query=number_pool_allocation_query.render(), variables={"pool_id": new_number_pool.id}
        )
        assert new_number_allocation["InfrahubResourcePoolAllocated"]["count"] == 6

        # Add a new attribute to the existing schema with a large pool
        new_schema2 = initial_schema.duplicate()
        incident_schema = new_schema2.get(name=SNOW_INCIDENT.kind)
        incident_schema.attributes.append(
            AttributeSchema(
                name="new_number2",
                kind="NumberPool",
                optional=False,
                read_only=True,
                parameters=NumberPoolParameters(start_range=2, end_range=4),
            ),
        )

        schema_load_response = await client.schema.load(schemas=[new_schema2.model_dump()], wait_until_converged=True)
        assert schema_load_response.errors
        assert len(schema_load_response.errors["errors"]) == 1
        assert schema_load_response.errors["errors"][0]["message"] == (
            "The size of the NumberPool is smaller than the number of existing nodes 3 < 6."
        )
