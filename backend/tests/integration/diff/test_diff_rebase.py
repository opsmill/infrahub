from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from infrahub import config, lock
from infrahub.core.constants import DiffAction, InfrahubKind
from infrahub.core.constants.database import DatabaseEdgeType
from infrahub.core.diff.model.path import BranchTrackingId
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
        jesko_id = initial_dataset["jesko"].id
        cyberdyne_id = initial_dataset["cyberdyne"].id
        jesko_branch_1 = await NodeManager.get_one(db=db, id=jesko_id, branch=branch_1)
        await jesko_branch_1.manufacturer.update(db=db, data=cyberdyne_id)
        await jesko_branch_1.save(db=db)

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
        jesko_id = initial_dataset["jesko"].id
        omnicorp_id = initial_dataset["omnicorp"].id
        jesko_branch_2 = await NodeManager.get_one(db=db, id=jesko_id, branch=branch_2)
        await jesko_branch_2.manufacturer.update(db=db, data=omnicorp_id)
        await jesko_branch_2.save(db=db)

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
        jesko_id = initial_dataset["jesko"].id
        koenigsegg_id = initial_dataset["koenigsegg"].id
        cyberdyne_id = initial_dataset["cyberdyne"].id
        omnicorp_id = initial_dataset["omnicorp"].id

        branch_1_diff = await diff_repository.get_one(
            diff_branch_name=branch_1.name, tracking_id=BranchTrackingId(name=branch_1.name)
        )
        branch_2_diff = await diff_repository.get_one(
            diff_branch_name=branch_2.name, tracking_id=BranchTrackingId(name=branch_2.name)
        )
        for new_desc_value, new_peer_id, branch_diff in [
            ("branch-1-description", cyberdyne_id, branch_1_diff),
            ("branch-2-description", omnicorp_id, branch_2_diff),
        ]:
            assert len(branch_diff.nodes) == 4
            nodes_by_id = {n.uuid: n for n in branch_diff.nodes}
            assert set(nodes_by_id.keys()) == {kara_id, jesko_id, koenigsegg_id, new_peer_id}
            kara_node = nodes_by_id[kara_id]
            assert len(kara_node.attributes) == 1
            description_attr = kara_node.attributes.pop()
            assert description_attr.name == "description"
            assert len(description_attr.properties) == 1
            value_prop = description_attr.properties.pop()
            assert value_prop.action is DiffAction.UPDATED
            assert value_prop.property_type is DatabaseEdgeType.HAS_VALUE
            assert value_prop.previous_value == "Starbuck"
            assert value_prop.new_value == new_desc_value
            assert value_prop.conflict is None
            jesko_node = nodes_by_id[jesko_id]
            assert len(jesko_node.relationships) == 1
            manufacturer_rel = jesko_node.relationships.pop()
            assert manufacturer_rel.name == "manufacturer"
            assert len(manufacturer_rel.relationships) == 1
            manufacturer_element = manufacturer_rel.relationships.pop()
            assert manufacturer_element.peer_id == new_peer_id
            assert manufacturer_element.action is DiffAction.UPDATED
            assert manufacturer_element.conflict is None
            assert len(manufacturer_element.properties) == 1
            related_prop = manufacturer_element.properties.pop()
            assert related_prop.property_type is DatabaseEdgeType.IS_RELATED
            assert related_prop.action is DiffAction.UPDATED
            assert related_prop.previous_value == koenigsegg_id
            assert related_prop.new_value == new_peer_id
            assert related_prop.conflict is None
            for manufacturer_id, expected_action in (
                (koenigsegg_id, DiffAction.REMOVED),
                (new_peer_id, DiffAction.ADDED),
            ):
                manufacturer_node = nodes_by_id[manufacturer_id]
                assert len(manufacturer_node.relationships) == 1
                cars_rel = manufacturer_node.relationships.pop()
                assert cars_rel.name == "cars"
                assert cars_rel.action is DiffAction.UPDATED
                assert len(cars_rel.relationships) == 1
                cars_element = cars_rel.relationships.pop()
                assert cars_element.peer_id == jesko_id
                assert cars_element.action is expected_action
                assert cars_element.conflict is None
                properties_by_type = {p.property_type: p for p in cars_element.properties}
                assert set(properties_by_type.keys()) == {
                    DatabaseEdgeType.IS_RELATED,
                    DatabaseEdgeType.IS_PROTECTED,
                    DatabaseEdgeType.IS_VISIBLE,
                }
                for property_type, check_value in (
                    (DatabaseEdgeType.IS_RELATED, jesko_id),
                    (DatabaseEdgeType.IS_PROTECTED, "False"),
                    (DatabaseEdgeType.IS_VISIBLE, "True"),
                ):
                    prop_diff = properties_by_type[property_type]
                    assert prop_diff.action is expected_action
                    assert prop_diff.previous_value == (check_value if expected_action is DiffAction.REMOVED else None)
                    assert prop_diff.new_value == (check_value if expected_action is DiffAction.ADDED else None)
                    assert prop_diff.conflict is None

    async def test_merge_causes_diff_update(
        self,
        db: InfrahubDatabase,
        client: InfrahubClient,
        initial_dataset,
        add_branch_1_changes,
        branch_1: Branch,
        branch_2: Branch,
        diff_repository: DiffRepository,
    ):
        kara_id = initial_dataset["kara"].id
        jesko_id = initial_dataset["jesko"].id
        koenigsegg_id = initial_dataset["koenigsegg"].id
        cyberdyne_id = initial_dataset["cyberdyne"].id
        omnicorp_id = initial_dataset["omnicorp"].id
        before_merge = Timestamp()

        result = await client.execute_graphql(query=BRANCH_MERGE, variables={"branch": branch_1.name})
        assert result["BranchMerge"]["ok"]

        branch_2_diff = await diff_repository.get_one(
            diff_branch_name=branch_2.name, tracking_id=BranchTrackingId(name=branch_2.name)
        )

        assert len(branch_2_diff.nodes) == 4
        assert branch_2_diff.to_time > before_merge
        nodes_by_id = {n.uuid: n for n in branch_2_diff.nodes}
        kara_node = nodes_by_id[kara_id]
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
        jesko_node = nodes_by_id[jesko_id]
        assert len(jesko_node.relationships) == 1
        manufacturer_rel = jesko_node.relationships.pop()
        assert manufacturer_rel.name == "manufacturer"
        assert len(manufacturer_rel.relationships) == 1
        manufacturer_element = manufacturer_rel.relationships.pop()
        assert manufacturer_element.peer_id == omnicorp_id
        assert manufacturer_element.action is DiffAction.UPDATED
        assert manufacturer_element.conflict
        assert manufacturer_element.conflict.base_branch_action is DiffAction.UPDATED
        assert manufacturer_element.conflict.base_branch_value == cyberdyne_id
        assert manufacturer_element.conflict.diff_branch_action is DiffAction.UPDATED
        assert manufacturer_element.conflict.diff_branch_value == omnicorp_id
        assert len(manufacturer_element.properties) == 1
        related_prop = manufacturer_element.properties.pop()
        assert related_prop.property_type is DatabaseEdgeType.IS_RELATED
        assert related_prop.action is DiffAction.UPDATED
        assert related_prop.previous_value == koenigsegg_id
        assert related_prop.new_value == omnicorp_id
        assert related_prop.conflict is None
        for manufacturer_id, expected_action in ((koenigsegg_id, DiffAction.REMOVED), (omnicorp_id, DiffAction.ADDED)):
            manufacturer_node = nodes_by_id[manufacturer_id]
            assert len(manufacturer_node.relationships) == 1
            cars_rel = manufacturer_node.relationships.pop()
            assert cars_rel.name == "cars"
            assert cars_rel.action is DiffAction.UPDATED
            assert len(cars_rel.relationships) == 1
            cars_element = cars_rel.relationships.pop()
            assert cars_element.peer_id == jesko_id
            assert cars_element.action is expected_action
            assert cars_element.conflict is None
            properties_by_type = {p.property_type: p for p in cars_element.properties}
            assert set(properties_by_type.keys()) == {
                DatabaseEdgeType.IS_RELATED,
                DatabaseEdgeType.IS_PROTECTED,
                DatabaseEdgeType.IS_VISIBLE,
            }
            for property_type, check_value in (
                (DatabaseEdgeType.IS_RELATED, jesko_id),
                (DatabaseEdgeType.IS_PROTECTED, "False"),
                (DatabaseEdgeType.IS_VISIBLE, "True"),
            ):
                prop_diff = properties_by_type[property_type]
                assert prop_diff.action is expected_action
                assert prop_diff.previous_value == (check_value if expected_action is DiffAction.REMOVED else None)
                assert prop_diff.new_value == (check_value if expected_action is DiffAction.ADDED else None)
                assert prop_diff.conflict is None

    async def test_resolve_conflict(
        self,
        db: InfrahubDatabase,
        branch_2: Branch,
        initial_dataset,
    ):
        kara_id = initial_dataset["kara"].id
        jesko_id = initial_dataset["jesko"].id
        cyberdyne_id = initial_dataset["cyberdyne"].id

        kara_main = await NodeManager.get_one(db=db, id=kara_id)
        kara_main.description.value = "branch-2-description"
        await kara_main.save(db=db)

        jesko_branch = await NodeManager.get_one(db=db, branch=branch_2, id=jesko_id)
        await jesko_branch.manufacturer.update(db=db, data=cyberdyne_id)
        await jesko_branch.save(db=db)

    async def test_rebase_causes_diff_recalculation(
        self,
        db: InfrahubDatabase,
        client: InfrahubClient,
        initial_dataset,
        branch_2: Branch,
        diff_repository: DiffRepository,
    ):
        jesko_id = initial_dataset["jesko"].id
        koenigsegg_id = initial_dataset["koenigsegg"].id
        cyberdyne_id = initial_dataset["cyberdyne"].id
        before_rebase = Timestamp()

        result = await client.execute_graphql(query=BRANCH_REBASE, variables={"branch": branch_2.name})
        assert result["BranchRebase"]["ok"]

        branch_2_diff = await diff_repository.get_one(
            diff_branch_name=branch_2.name, tracking_id=BranchTrackingId(name=branch_2.name)
        )

        assert len(branch_2_diff.nodes) == 3
        assert branch_2_diff.to_time > before_rebase
        nodes_by_id = {n.uuid: n for n in branch_2_diff.nodes}
        assert set(nodes_by_id.keys()) == {jesko_id, cyberdyne_id, koenigsegg_id}
        jesko_node = nodes_by_id[jesko_id]
        assert len(jesko_node.relationships) == 1
        manufacturer_rel = jesko_node.relationships.pop()
        assert manufacturer_rel.name == "manufacturer"
        assert len(manufacturer_rel.relationships) == 1
        manufacturer_element = manufacturer_rel.relationships.pop()
        assert manufacturer_element.peer_id == cyberdyne_id
        assert manufacturer_element.action is DiffAction.UPDATED
        assert manufacturer_element.conflict is None
        assert len(manufacturer_element.properties) == 1
        related_prop = manufacturer_element.properties.pop()
        assert related_prop.property_type is DatabaseEdgeType.IS_RELATED
        assert related_prop.action is DiffAction.UPDATED
        assert related_prop.previous_value == koenigsegg_id
        assert related_prop.new_value == cyberdyne_id
        assert related_prop.conflict is None
        for manufacturer_id, expected_action in ((koenigsegg_id, DiffAction.REMOVED), (cyberdyne_id, DiffAction.ADDED)):
            manufacturer_node = nodes_by_id[manufacturer_id]
            assert len(manufacturer_node.relationships) == 1
            cars_rel = manufacturer_node.relationships.pop()
            assert cars_rel.name == "cars"
            assert cars_rel.action is DiffAction.UPDATED
            assert len(cars_rel.relationships) == 1
            cars_element = cars_rel.relationships.pop()
            assert cars_element.peer_id == jesko_id
            assert cars_element.action is expected_action
            assert cars_element.conflict is None
            properties_by_type = {p.property_type: p for p in cars_element.properties}
            assert set(properties_by_type.keys()) == {
                DatabaseEdgeType.IS_RELATED,
                DatabaseEdgeType.IS_PROTECTED,
                DatabaseEdgeType.IS_VISIBLE,
            }
            for property_type, check_value in (
                (DatabaseEdgeType.IS_RELATED, jesko_id),
                (DatabaseEdgeType.IS_PROTECTED, "False"),
                (DatabaseEdgeType.IS_VISIBLE, "True"),
            ):
                prop_diff = properties_by_type[property_type]
                assert prop_diff.action is expected_action
                assert prop_diff.previous_value == (check_value if expected_action is DiffAction.REMOVED else None)
                assert prop_diff.new_value == (check_value if expected_action is DiffAction.ADDED else None)
                assert prop_diff.conflict is None
