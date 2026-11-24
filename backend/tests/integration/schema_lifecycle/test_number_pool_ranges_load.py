from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

import pytest

from infrahub.core.manager import NodeManager
from infrahub.core.protocols import CoreNumberPool
from infrahub.core.schema import NUMBER_POOL_SHORTHAND_DEPRECATION
from infrahub.pools.number_pool_repository import NumberPoolRepository
from tests.helpers.number_pool import StoredRange, run_schema_updated_workflow
from tests.helpers.test_app import TestInfrahubApp

if TYPE_CHECKING:
    from infrahub_sdk.client import InfrahubClient

    from infrahub.core.branch.models import Branch
    from infrahub.database import InfrahubDatabase
    from infrahub.services import InfrahubServices


KIND = "TestingSlot"
RANGED_ATTRIBUTE = "ranged_number"
BARE_ATTRIBUTE = "bare_number"


@dataclass(frozen=True)
class StoredPool:
    start_range: int | None = None
    end_range: int | None = None
    ranges: list[StoredRange] = field(default_factory=list)


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
    async def _stored_pool(db: InfrahubDatabase, attribute: str) -> StoredPool:
        pools = await NodeManager.query(
            db=db,
            schema=CoreNumberPool,
            filters={"node__value": KIND, "node_attribute__value": attribute},
            branch_agnostic=True,
        )
        assert len(pools) == 1
        pool = pools[0]
        ranges = await NumberPoolRepository(db=db).get_ranges(pool_id=pool.get_id())
        return StoredPool(
            start_range=pool.start_range.value,
            end_range=pool.end_range.value,
            ranges=[
                StoredRange(start=item.start.value, end=item.end.value, weight=item.allocation_weight.value)
                for item in ranges
            ],
        )

    async def test_load_materialises_the_declared_ranges(
        self,
        db: InfrahubDatabase,
        client: InfrahubClient,
        default_branch: Branch,
        service: InfrahubServices,
        schema_slot: dict[str, Any],
    ) -> None:
        response = await client.schema.load(schemas=[schema_slot], branch=default_branch.name)

        assert not response.errors
        assert NUMBER_POOL_SHORTHAND_DEPRECATION not in {warning.message for warning in response.warnings}

        await run_schema_updated_workflow(service=service, branch=default_branch)

        assert await self._stored_pool(db=db, attribute=RANGED_ATTRIBUTE) == StoredPool(
            ranges=[StoredRange(start=1, end=100), StoredRange(start=200, end=300, weight=10)]
        )
        assert await self._stored_pool(db=db, attribute=BARE_ATTRIBUTE) == StoredPool(
            ranges=[StoredRange(start=None, end=None)]
        )
