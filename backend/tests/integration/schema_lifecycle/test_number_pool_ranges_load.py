from __future__ import annotations

from typing import TYPE_CHECKING, Any

import pytest

from infrahub.core import registry
from infrahub.core.manager import NodeManager
from infrahub.core.protocols import CoreNumberPool
from infrahub.core.schema import NUMBER_POOL_SHORTHAND_DEPRECATION
from infrahub.core.schema.attribute_parameters import NumberPoolParameters, NumberPoolRangeParameters
from infrahub.pools.number_pool_repository import NumberPoolRepository
from infrahub.pools.schema_number_pool_synchronizer import SchemaNumberPoolSynchronizer
from infrahub.pools.schema_number_pool_upserter import SchemaNumberPoolUpserter
from tests.helpers.test_app import TestInfrahubApp

if TYPE_CHECKING:
    from infrahub_sdk.client import InfrahubClient

    from infrahub.core.branch.models import Branch
    from infrahub.database import InfrahubDatabase


KIND = "TestingSlot"
RANGED_ATTRIBUTE = "ranged_number"
BARE_ATTRIBUTE = "bare_number"


class TestLoadNumberPoolRanges(TestInfrahubApp):
    @pytest.fixture(scope="class")
    def schema_slot(self) -> dict[str, Any]:
        return {
            "version": "1.0",
            "nodes": [
                {
                    "name": "Slot",
                    "namespace": "Testing",
                    "attributes": [
                        {"name": "name", "kind": "Text"},
                        {
                            "name": RANGED_ATTRIBUTE,
                            "kind": "NumberPool",
                            "optional": False,
                            "read_only": True,
                            "parameters": {
                                "ranges": [{"start": 1, "end": 100}, {"start": 200, "end": 300, "weight": 10}]
                            },
                        },
                        {"name": BARE_ATTRIBUTE, "kind": "NumberPool", "optional": False, "read_only": True},
                    ],
                }
            ],
        }

    @staticmethod
    async def _pool_ranges(db: InfrahubDatabase, attribute: str) -> tuple[tuple[int | None, int | None], list[tuple]]:
        pools = await NodeManager.query(
            db=db,
            schema=CoreNumberPool,
            filters={"node__value": KIND, "node_attribute__value": attribute},
            branch_agnostic=True,
        )
        assert len(pools) == 1
        pool = pools[0]
        ranges = await NumberPoolRepository(db=db).get_ranges(pool_id=pool.get_id())
        shorthand = (pool.get_attribute("start_range").value, pool.get_attribute("end_range").value)
        return shorthand, [(item.start.value, item.end.value, item.allocation_weight.value) for item in ranges]

    async def test_check_reports_no_shorthand_deprecation(
        self, client: InfrahubClient, default_branch: Branch, schema_slot: dict[str, Any]
    ) -> None:
        success, response = await client.schema.check(schemas=[schema_slot], branch=default_branch.name)

        assert success, response
        assert response["warnings"] == []

    async def test_load_materialises_the_declared_ranges(
        self, db: InfrahubDatabase, client: InfrahubClient, default_branch: Branch, schema_slot: dict[str, Any]
    ) -> None:
        response = await client.schema.load(schemas=[schema_slot], branch=default_branch.name)

        assert not response.errors
        assert NUMBER_POOL_SHORTHAND_DEPRECATION not in {warning.message for warning in response.warnings}

        schema_branch = await registry.schema.load_schema_from_db(db=db, branch=default_branch)
        node_schema = schema_branch.get_node(name=KIND, duplicate=False)
        ranged = node_schema.get_attribute(RANGED_ATTRIBUTE).parameters
        assert isinstance(ranged, NumberPoolParameters)
        assert (ranged.start_range, ranged.end_range) == (None, None)
        assert ranged.ranges == [
            NumberPoolRangeParameters(start=1, end=100),
            NumberPoolRangeParameters(start=200, end=300, weight=10),
        ]
        bare = node_schema.get_attribute(BARE_ATTRIBUTE).parameters
        assert isinstance(bare, NumberPoolParameters)
        assert (bare.start_range, bare.end_range, bare.ranges) == (None, None, [])

        upserter = SchemaNumberPoolUpserter(
            db=db, schema_manager=registry.schema, range_store_factory=NumberPoolRepository
        )
        await SchemaNumberPoolSynchronizer(
            db=db, schema_manager=registry.schema, upserter=upserter, range_store_factory=NumberPoolRepository
        ).run()

        assert await self._pool_ranges(db=db, attribute=RANGED_ATTRIBUTE) == (
            (None, None),
            [(1, 100, None), (200, 300, 10)],
        )
        assert await self._pool_ranges(db=db, attribute=BARE_ATTRIBUTE) == ((None, None), [])
