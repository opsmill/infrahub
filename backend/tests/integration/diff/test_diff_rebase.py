from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from infrahub import config, lock
from infrahub.core.constants import DiffAction, InfrahubKind
from infrahub.core.constants.database import DatabaseEdgeType
from infrahub.core.diff.model.path import BranchTrackingId, ConflictSelection
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


DIFF_UPDATE_QUERY = """
mutation DiffUpdate($branch_name: String!, $wait_for_completion: Boolean) {
    DiffUpdate(data: { branch: $branch_name, wait_for_completion: $wait_for_completion }) {
        ok
    }
}
"""

BRANCH_MERGE = """
mutation($branch: String!) {
    BranchMerge(data: { name: $branch }) {
        ok
    }
}
"""

CONFLICT_SELECTION_QUERY = """
mutation ResolveDiffConflict($conflict_id: String!, $selected_branch: ConflictSelection!) {
    ResolveDiffConflict(data: { conflict_id: $conflict_id, selected_branch: $selected_branch }) {
        ok
    }
}
"""

BRANCH_REBASE = """
mutation($branch: String!) {
    BranchRebase(data: { name: $branch }) {
        ok
    }
}
"""


class TestDiffRebase(TestInfrahubApp):
    @pytest.fixture(scope="class", autouse=True)
    def configure_settings(self):
        config.SETTINGS.broker.enable = True
        config.SETTINGS.cache.enable = False

    @pytest.fixture(scope="class", autouse=True)
    def initialize_lock(self):
        lock.initialize_lock(local_only=True)

    @pytest.fixture(scope="class")
    async def initial_dataset(
        self,
        db: InfrahubDatabase,
        default_branch,
        client: InfrahubClient,
        bus_simulator: BusSimulator,
    ) -> dict[str, Node]:
        await load_schema(db, schema=CAR_SCHEMA)
        john = await Node.init(schema=TestKind.PERSON, db=db)
        await john.new(db=db, name="John", height=175, description="The famous Joe Doe")
        await john.save(db=db)
        kara = await Node.init(schema=TestKind.PERSON, db=db)
        await kara.new(db=db, name="Kara Thrace", height=165, description="Starbuck")
        await kara.save(db=db)
        murphy = await Node.init(schema=TestKind.PERSON, db=db)
        await murphy.new(db=db, name="Alex Murphy", height=185, description="Robocop")
        await murphy.save(db=db)
        koenigsegg = await Node.init(schema=TestKind.MANUFACTURER, db=db)
        await koenigsegg.new(db=db, name="Koenigsegg", customers=[john])
        await koenigsegg.save(db=db)
        omnicorp = await Node.init(schema=TestKind.MANUFACTURER, db=db)
        await omnicorp.new(db=db, name="Omnicorp", customers=[murphy])
        await omnicorp.save(db=db)
        cyberdyne = await Node.init(schema=TestKind.MANUFACTURER, db=db)
        await cyberdyne.new(db=db, name="Cyberdyne")
        await cyberdyne.save(db=db)
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
            owner=john,
            manufacturer=omnicorp,
        )
        await ed_209.save(db=db)

        bus_simulator.service.cache = RedisCache()

        return {
            "john": john,
            "kara": kara,
            "murphy": murphy,
            "koenigsegg": koenigsegg,
            "omnicorp": omnicorp,
            "cyberdyne": cyberdyne,
            "people": people,
            "jesko": jesko,
            "t_800": t_800,
            "ed_209": ed_209,
        }

    @pytest.fixture(scope="class")
    async def branch_1(self, db: InfrahubDatabase) -> Branch:
        return await create_branch(branch_name="branch_1", db=db)

    @pytest.fixture(scope="class")
    async def branch_2(self, db: InfrahubDatabase) -> Branch:
        return await create_branch(branch_name="branch_2", db=db)

    @pytest.fixture(scope="class")
    async def diff_repository(self, db: InfrahubDatabase, default_branch: Branch) -> DiffRepository:
        component_registry = get_component_registry()
        return await component_registry.get_component(DiffRepository, db=db, branch=default_branch)

    @pytest.fixture(scope="class")
    async def add_branch_1_changes(
        self, db: InfrahubDatabase, client: InfrahubClient, default_branch: Branch, initial_dataset, branch_1: Branch
    ):
        kara_id = initial_dataset["kara"].id
        kara_branch_1 = await NodeManager.get_one(db=db, id=kara_id, branch=branch_1)
        kara_branch_1.description.value = "branch-1-description"
        await kara_branch_1.save(db=db)

        result = await client.execute_graphql(query=DIFF_UPDATE_QUERY, variables={"branch_name": branch_1.name})
        assert result["DiffUpdate"]["ok"]

    @pytest.fixture(scope="class")
    async def add_branch_2_changes(
        self, db: InfrahubDatabase, client: InfrahubClient, default_branch: Branch, initial_dataset, branch_2: Branch
    ):
        kara_id = initial_dataset["kara"].id
        kara_branch_2 = await NodeManager.get_one(db=db, id=kara_id, branch=branch_2)
        kara_branch_2.description.value = "branch-2-description"
        await kara_branch_2.save(db=db)

        result = await client.execute_graphql(query=DIFF_UPDATE_QUERY, variables={"branch_name": branch_2.name})
        assert result["DiffUpdate"]["ok"]

    async def test_no_conflicts_before_merge(
        self,
        db: InfrahubDatabase,
        initial_dataset,
        add_branch_1_changes,
        add_branch_2_changes,
        branch_1: Branch,
        branch_2: Branch,
        diff_repository: DiffRepository,
    ):
        kara_id = initial_dataset["kara"].id

        branch_1_diff = await diff_repository.get_one(
            diff_branch_name=branch_1.name, tracking_id=BranchTrackingId(name=branch_1.name)
        )
        branch_2_diff = await diff_repository.get_one(
            diff_branch_name=branch_2.name, tracking_id=BranchTrackingId(name=branch_2.name)
        )
        for new_value, branch_diff in [
            ("branch-1-description", branch_1_diff),
            ("branch-2-description", branch_2_diff),
        ]:
            assert len(branch_diff.nodes) == 1
            kara_node = branch_diff.nodes.pop()
            assert kara_node.uuid == kara_id
            assert len(kara_node.attributes) == 1
            description_attr = kara_node.attributes.pop()
            assert description_attr.name == "description"
            assert len(description_attr.properties) == 1
            value_prop = description_attr.properties.pop()
            assert value_prop.property_type is DatabaseEdgeType.HAS_VALUE
            assert value_prop.previous_value == "Starbuck"
            assert value_prop.new_value == new_value
            assert value_prop.conflict is None

    async def test_merge_causes_diff_update(
        self,
        db: InfrahubDatabase,
        client: InfrahubClient,
        initial_dataset,
        add_branch_1_changes,
        branch_1: Branch,
        branch_2: Branch,
        diff_repository,
    ):
        kara_id = initial_dataset["kara"].id
        before_merge = Timestamp()
        result = await client.execute_graphql(query=BRANCH_MERGE, variables={"branch": branch_1.name})
        assert result["BranchMerge"]["ok"]

        branch_2_diff = await diff_repository.get_one(
            diff_branch_name=branch_2.name, tracking_id=BranchTrackingId(name=branch_2.name)
        )

        assert len(branch_2_diff.nodes) == 1
        assert branch_2_diff.to_time > before_merge
        kara_node = branch_2_diff.nodes.pop()
        assert kara_node.uuid == kara_id
        assert len(kara_node.attributes) == 1
        description_attr = kara_node.attributes.pop()
        assert description_attr.name == "description"
        assert len(description_attr.properties) == 1
        value_prop = description_attr.properties.pop()
        assert value_prop.property_type is DatabaseEdgeType.HAS_VALUE
        assert value_prop.previous_value == "Starbuck"
        assert value_prop.new_value == "branch-2-description"
        assert value_prop.conflict
        assert value_prop.conflict.base_branch_action is DiffAction.UPDATED
        assert value_prop.conflict.base_branch_value == "branch-1-description"
        assert value_prop.conflict.diff_branch_action is DiffAction.UPDATED
        assert value_prop.conflict.diff_branch_value == "branch-2-description"

    async def test_resolve_conflict(self, client: InfrahubClient, branch_2: Branch, diff_repository: DiffRepository):
        branch_2_diff = await diff_repository.get_one(
            diff_branch_name=branch_2.name, tracking_id=BranchTrackingId(name=branch_2.name)
        )
        conflict = branch_2_diff.get_all_conflicts()[0]

        result = await client.execute_graphql(
            query=CONFLICT_SELECTION_QUERY,
            variables={"conflict_id": conflict.uuid, "selected_branch": ConflictSelection.DIFF_BRANCH.name},
        )
        assert result["ResolveDiffConflict"]["ok"]

        branch_2_diff = await diff_repository.get_one(
            diff_branch_name=branch_2.name, tracking_id=BranchTrackingId(name=branch_2.name)
        )
        conflict = branch_2_diff.get_all_conflicts()[0]
        assert conflict.selected_branch is ConflictSelection.DIFF_BRANCH

    async def test_rebase_causes_diff_recalculation(
        self,
        db: InfrahubDatabase,
        client: InfrahubClient,
        initial_dataset,
        branch_2: Branch,
        diff_repository: DiffRepository,
    ):
        kara_id = initial_dataset["kara"].id
        before_rebase = Timestamp()
        result = await client.execute_graphql(query=BRANCH_REBASE, variables={"branch": branch_2.name})
        assert result["BranchRebase"]["ok"]

        branch_2_diff = await diff_repository.get_one(
            diff_branch_name=branch_2.name, tracking_id=BranchTrackingId(name=branch_2.name)
        )

        assert len(branch_2_diff.nodes) == 1
        assert branch_2_diff.to_time > before_rebase
        kara_node = branch_2_diff.nodes.pop()
        assert kara_node.uuid == kara_id
        assert len(kara_node.attributes) == 1
        description_attr = kara_node.attributes.pop()
        assert description_attr.name == "description"
        assert len(description_attr.properties) == 1
        value_prop = description_attr.properties.pop()
        assert value_prop.property_type is DatabaseEdgeType.HAS_VALUE
        assert value_prop.previous_value == "Starbuck"
        assert value_prop.new_value == "branch-2-description"
        assert value_prop.conflict
        assert value_prop.conflict.base_branch_action is DiffAction.UPDATED
        assert value_prop.conflict.base_branch_value == "branch-1-description"
        assert value_prop.conflict.diff_branch_action is DiffAction.UPDATED
        assert value_prop.conflict.diff_branch_value == "branch-2-description"
        assert value_prop.conflict.selected_branch is ConflictSelection.DIFF_BRANCH
