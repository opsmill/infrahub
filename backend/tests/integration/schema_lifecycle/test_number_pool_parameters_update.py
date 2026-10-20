from __future__ import annotations

from copy import deepcopy
from typing import TYPE_CHECKING, Any

import pytest

from infrahub.core import registry
from infrahub.core.manager import NodeManager
from infrahub.core.node import Node
from infrahub.core.protocols import CoreNumberPool
from infrahub.core.schema import SchemaRoot
from infrahub.core.schema.attribute_parameters import NumberPoolParameters
from infrahub.pools.number_pool_repository import NumberPoolRepository
from tests.helpers.number_pool import run_schema_updated_workflow
from tests.helpers.schema import load_schema as load_schema_root
from tests.helpers.test_app import TestInfrahubApp

if TYPE_CHECKING:
    from infrahub_sdk.client import InfrahubClient

    from infrahub.core.branch.models import Branch
    from infrahub.core.schema.node_schema import NodeSchema
    from infrahub.database import InfrahubDatabase
    from infrahub.services import InfrahubServices


KIND = "TestingThing"


class TestUpdateNumberPoolParameters(TestInfrahubApp):
    @pytest.fixture(scope="class")
    def schema_thing(self) -> dict[str, Any]:
        return {
            "name": "Thing",
            "namespace": "Testing",
            "include_in_menu": True,
            "label": "Thing",
            "attributes": [
                {"name": "name", "kind": "Text"},
                {
                    "name": "assigned_number",
                    "kind": "NumberPool",
                    "optional": False,
                    "read_only": True,
                    "parameters": {"start_range": 50, "end_range": 1200},
                },
            ],
        }

    @pytest.fixture(scope="class")
    def schema_thing_excluding_held_value(self, schema_thing: dict[str, Any]) -> dict[str, Any]:
        return self._thing_with_pool_parameters(schema_thing, parameters={"start_range": 100, "end_range": 200})

    @pytest.fixture(scope="class")
    def schema_thing_ranges_excluding_held_value(self, schema_thing: dict[str, Any]) -> dict[str, Any]:
        return self._thing_with_pool_parameters(
            schema_thing, parameters={"ranges": [{"start": 10, "end": 20}, {"start": 100, "end": 200}]}
        )

    @staticmethod
    def _thing_with_pool_parameters(schema_thing: dict[str, Any], parameters: dict[str, Any]) -> dict[str, Any]:
        thing = deepcopy(schema_thing)
        for attribute in thing["attributes"]:
            if attribute["name"] == "assigned_number":
                attribute["parameters"] = parameters
        return thing

    @pytest.fixture(scope="class")
    async def load_schema_thing(
        self, db: InfrahubDatabase, default_branch: Branch, schema_thing: dict[str, Any]
    ) -> None:
        schema_root = SchemaRoot(version="1.0", nodes=[schema_thing])
        await load_schema_root(db=db, branch_name=default_branch.name, schema=schema_root, update_db=True)

    @pytest.fixture(scope="class")
    async def thing_holding_a_number(
        self, db: InfrahubDatabase, default_branch: Branch, service: InfrahubServices, load_schema_thing: None
    ) -> Node:
        await run_schema_updated_workflow(service=service, branch=default_branch)
        thing = await Node.init(db=db, schema=KIND, branch=default_branch)
        await thing.new(db=db, name="holder")
        await thing.save(db=db)
        return thing

    @staticmethod
    async def _pool_ranges(db: InfrahubDatabase) -> tuple[str, list[tuple[int, int, int | None]]]:
        pools = await NodeManager.query(
            db=db,
            schema=CoreNumberPool,
            filters={"node__value": KIND, "node_attribute__value": "assigned_number"},
            branch_agnostic=True,
        )
        assert len(pools) == 1
        pool = pools[0]
        ranges = await NumberPoolRepository(db=db).get_ranges(pool_id=pool.get_id())
        return pool.get_id(), [(item.start.value, item.end.value, item.allocation_weight.value) for item in ranges]

    def _validate_schema_numberpool_parameters(self, schema: NodeSchema, start_range: int, end_range: int) -> None:
        number_attr = schema.get_attribute("assigned_number")
        assert isinstance(number_attr.parameters, NumberPoolParameters)
        assert number_attr.parameters.start_range == start_range
        assert number_attr.parameters.end_range == end_range
        assert number_attr.parameters.ranges == []

    async def test_step01_range_excluding_a_held_value_is_refused(
        self,
        db: InfrahubDatabase,
        client: InfrahubClient,
        default_branch: Branch,
        thing_holding_a_number: Node,
        schema_thing_excluding_held_value: dict[str, Any],
    ) -> None:
        assert thing_holding_a_number.get_attribute("assigned_number").value == 50

        response = await client.schema.load(
            schemas=[{"version": "1.0", "nodes": [schema_thing_excluding_held_value]}],
            branch=default_branch.name,
        )

        errors = str(response.errors)
        assert KIND in errors
        assert "assigned_number=50" in errors
        schema_branch = await registry.schema.load_schema_from_db(db=db, branch=default_branch)
        self._validate_schema_numberpool_parameters(
            schema=schema_branch.get_node(name=KIND, duplicate=False), start_range=50, end_range=1200
        )
        assert (await self._pool_ranges(db=db))[1] == [(50, 1200, None)]

    async def test_step02_ranges_excluding_a_held_value_are_refused(
        self,
        db: InfrahubDatabase,
        client: InfrahubClient,
        default_branch: Branch,
        thing_holding_a_number: Node,
        schema_thing_ranges_excluding_held_value: dict[str, Any],
    ) -> None:
        response = await client.schema.load(
            schemas=[{"version": "1.0", "nodes": [schema_thing_ranges_excluding_held_value]}],
            branch=default_branch.name,
        )

        errors = str(response.errors)
        assert KIND in errors
        assert "assigned_number=50" in errors
        schema_branch = await registry.schema.load_schema_from_db(db=db, branch=default_branch)
        self._validate_schema_numberpool_parameters(
            schema=schema_branch.get_node(name=KIND, duplicate=False), start_range=50, end_range=1200
        )
        assert (await self._pool_ranges(db=db))[1] == [(50, 1200, None)]
