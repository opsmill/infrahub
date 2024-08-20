from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from infrahub.core import registry
from infrahub.core.constants import InfrahubKind
from infrahub.core.diff.repository.repository import DiffRepository
from infrahub.core.initialization import create_branch
from infrahub.core.manager import NodeManager
from infrahub.core.node import Node
from infrahub.core.timestamp import Timestamp
from infrahub.dependencies.registry import get_component_registry
from infrahub.services.adapters.cache.redis import RedisCache
from tests.constants import TestKind
from tests.helpers.schema import CAR_SCHEMA, load_schema
from tests.helpers.test_app import TestInfrahubApp

if TYPE_CHECKING:
    from infrahub_sdk import InfrahubClient

    from infrahub.core.branch import Branch
    from infrahub.database import InfrahubDatabase
    from tests.adapters.message_bus import BusSimulator

BRANCH_NAME = "branch1"

DIFF_UPDATE_QUERY = """
mutation DiffUpdate($branch_name: String!) {
    DiffUpdate(data: { branch: $branch_name }) {
        ok
    }
}
"""


class TestDiffUpdateConflict(TestInfrahubApp):
    @pytest.fixture(scope="class")
    async def initial_dataset(
        self,
        db: InfrahubDatabase,
        default_branch,
        client: InfrahubClient,
        bus_simulator: BusSimulator,
    ) -> None:
        await load_schema(db, schema=CAR_SCHEMA)
        john = await Node.init(schema=TestKind.PERSON, db=db)
        await john.new(db=db, name="John", height=175, description="The famous Joe Doe")
        await john.save(db=db)
        koenigsegg = await Node.init(schema=TestKind.MANUFACTURER, db=db)
        await koenigsegg.new(db=db, name="Koenigsegg")
        await koenigsegg.save(db=db)
        people = await Node.init(schema=InfrahubKind.STANDARDGROUP, db=db)
        await people.new(db=db, name="people", members=[john])
        await people.save(db=db)

        jesko = await Node.init(schema=TestKind.CAR, db=db)
        await jesko.new(
            db=db,
            name="Jesko",
            color="Red",
            description="A limited production mid-engine sports car",
            owner=john,
            manufacturer=koenigsegg,
        )
        await jesko.save(db=db)

        bus_simulator.service.cache = RedisCache()

    @pytest.fixture(scope="class")
    async def create_diff(self, db: InfrahubDatabase, initial_dataset, client: InfrahubClient) -> None:
        branch1 = await create_branch(db=db, branch_name=BRANCH_NAME)

        richard = await Node.init(schema=TestKind.PERSON, db=db, branch=branch1.name)
        await richard.new(db=db, name="Richard", height=180, description="The less famous Richard Doe")
        await richard.save(db=db)

        john = await NodeManager.get_one_by_id_or_default_filter(
            db=db, id="John", kind=TestKind.PERSON, branch=branch1.name
        )
        john.age.value = 26  # type: ignore[attr-defined]
        await john.save(db=db)

    @staticmethod
    async def get_diffs(db: InfrahubDatabase, branch: Branch):
        # Validate if the diff has been updated properly
        component_registry = get_component_registry()
        diff_repo = await component_registry.get_component(DiffRepository, db=db, branch=branch)

        from_timestamp = Timestamp(branch.get_created_at())
        to_timestamp = Timestamp()

        return await diff_repo.get(
            base_branch_name=registry.default_branch,
            diff_branch_names=[BRANCH_NAME],
            from_time=from_timestamp,
            to_time=to_timestamp,
        )

    async def test_diff_first_update(
        self, db: InfrahubDatabase, initial_dataset, create_diff, client: InfrahubClient
    ) -> None:
        """Validate if the diff is properly created the first time"""

        result = await client.execute_graphql(query=DIFF_UPDATE_QUERY, variables={"branch_name": BRANCH_NAME})
        assert result["DiffUpdate"]["ok"]

        # Validate if the diff has been updated properly
        diff_branch = registry.get_branch_from_registry(branch=BRANCH_NAME)
        diffs = await self.get_diffs(db=db, branch=diff_branch)

        assert len(diffs) == 1
        assert len(diffs[0].nodes) == 2

    async def test_diff_second_update(
        self, db: InfrahubDatabase, initial_dataset, create_diff, client: InfrahubClient
    ) -> None:
        """Validate if the diff is properly updated the second time"""

        branch1 = registry.get_branch_from_registry(branch=BRANCH_NAME)

        bob = await Node.init(schema=TestKind.PERSON, db=db, branch=branch1.name)
        await bob.new(db=db, name="Bob", height=123, description="The less famous Bob")
        await bob.save(db=db)

        # Validate if the diff has been updated properly
        diff_branch = registry.get_branch_from_registry(branch=BRANCH_NAME)
        diffs = await self.get_diffs(db=db, branch=diff_branch)

        assert len(diffs) == 1
        assert len(diffs[0].nodes) == 2  # FIXME should be 3 here
