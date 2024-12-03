from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import patch

import pytest
from infrahub_sdk.exceptions import GraphQLError

from infrahub.core.initialization import create_branch
from infrahub.core.manager import NodeManager
from infrahub.core.merge import BranchMerger
from infrahub.core.node import Node
from infrahub.services.adapters.cache.redis import RedisCache
from tests.constants import TestKind
from tests.helpers.schema import CAR_SCHEMA, load_schema
from tests.helpers.test_app import TestInfrahubApp

if TYPE_CHECKING:
    from infrahub_sdk import InfrahubClient

    from infrahub.core.branch.models import Branch
    from infrahub.database import InfrahubDatabase
    from tests.adapters.message_bus import BusSimulator


BRANCH_MERGE = """
mutation($branch: String!) {
    BranchMerge(data: { name: $branch }) {
        ok
    }
}
"""


class BrokenBranchMerger:
    def __init__(self, *args, **kwargs) -> None:
        self.real_merger = BranchMerger(*args, **kwargs)

    async def merge(self, at=None) -> None:
        await self.real_merger.merge(at=at)
        raise ValueError("This is broken on purpose")

    async def rollback(self) -> None:
        await self.real_merger.rollback()


class TestBranchMergeRollback(TestInfrahubApp):
    @pytest.fixture(scope="class")
    async def initial_dataset(
        self,
        db: InfrahubDatabase,
        initialize_registry: None,
        bus_simulator: BusSimulator,
        prefect_test_fixture: None,
    ) -> dict[str, Node]:
        await load_schema(db, schema=CAR_SCHEMA)

        bus_simulator.service.cache = RedisCache()

        john = await Node.init(schema=TestKind.PERSON, db=db)
        await john.new(db=db, name="John", height=175, description="The famous Joe Doe")
        await john.save(db=db)
        kara = await Node.init(schema=TestKind.PERSON, db=db)
        await kara.new(db=db, name="Kara Thrace", height=165, description="Starbuck")
        await kara.save(db=db)
        murphy = await Node.init(schema=TestKind.PERSON, db=db)
        await murphy.new(db=db, name="Alex Murphy", height=185, description="Robocop")
        await murphy.save(db=db)
        omnicorp = await Node.init(schema=TestKind.MANUFACTURER, db=db)
        await omnicorp.new(db=db, name="Omnicorp", customers=[murphy])
        await omnicorp.save(db=db)
        cyberdyne = await Node.init(schema=TestKind.MANUFACTURER, db=db)
        await cyberdyne.new(db=db, name="Cyberdyne")
        await cyberdyne.save(db=db)

        t_800 = await Node.init(schema=TestKind.CAR, db=db)
        await t_800.new(
            db=db,
            name="Cyberdyne systems model 101",
            color="Chrome",
            description="killing machine with secret heart of gold",
            owner=john,
            manufacturer=cyberdyne,
        )
        await t_800.save(db=db)
        ed_209 = await Node.init(schema=TestKind.CAR, db=db)
        await ed_209.new(
            db=db,
            name="ED-209",
            color="Chrome",
            description="still working on doing stairs",
            owner=murphy,
            manufacturer=omnicorp,
        )
        await ed_209.save(db=db)

        return {
            "john": john,
            "kara": kara,
            "murphy": murphy,
            "omnicorp": omnicorp,
            "cyberdyne": cyberdyne,
            "t_800": t_800,
            "ed_209": ed_209,
        }

    @pytest.fixture(scope="class")
    async def branch1(self, db: InfrahubDatabase) -> Branch:
        return await create_branch(db=db, branch_name="branch1")

    @pytest.fixture(scope="class")
    async def branch1_data(
        self, db: InfrahubDatabase, initial_dataset: dict[str, Node], branch1: Branch
    ) -> dict[str, Node]:
        kara_branch = await NodeManager.get_one(db=db, branch=branch1, id=initial_dataset["kara"].id)
        await kara_branch.delete(db=db)

        sarah = await Node.init(schema=TestKind.PERSON, db=db, branch=branch1)
        await sarah.new(db=db, name="Sarah", height=161, description="no fate")
        await sarah.save(db=db)

        t_800_branch = await NodeManager.get_one(db=db, branch=branch1, id=initial_dataset["t_800"].id)
        await t_800_branch.owner.update(db=db, data=sarah)
        await t_800_branch.save(db=db)

        ocp_branch = await NodeManager.get_one(db=db, branch=branch1, id=initial_dataset["omnicorp"].id)
        ocp_branch.name.value = "Omni Consumer Products"
        await ocp_branch.save(db=db)

        return {"sarah": sarah}

    async def test_merge_branch_rollback(
        self,
        db: InfrahubDatabase,
        client: InfrahubClient,
        initial_dataset: dict[str, Node],
        branch1: Branch,
        branch1_data: dict[str, Node],
    ) -> None:
        with patch("infrahub.core.branch.tasks.BranchMerger", new=BrokenBranchMerger):
            with pytest.raises(GraphQLError) as exc:
                await client.execute_graphql(query=BRANCH_MERGE, variables={"branch": branch1.name})

            assert exc
            assert f"Failed to merge branch '{branch1.name}'" in exc.value.message

        # check that the changes on the branch have all been rolled back
        kara_main = await NodeManager.get_one(db=db, id=initial_dataset["kara"].id)
        assert kara_main.id

        sarah = await NodeManager.get_one(db=db, id=branch1_data["sarah"].id)
        assert sarah is None

        t_800_main = await NodeManager.get_one(db=db, id=initial_dataset["t_800"].id)
        owner_peer = await t_800_main.owner.get_peer(db=db)
        assert owner_peer.id == initial_dataset["john"].id

        ocp_main = await NodeManager.get_one(db=db, id=initial_dataset["omnicorp"].id)
        assert ocp_main.name.value == "Omnicorp"
