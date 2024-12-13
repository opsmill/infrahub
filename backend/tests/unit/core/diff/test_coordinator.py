from infrahub.core.branch import Branch
from infrahub.core.constants import DiffAction
from infrahub.core.constants.database import DatabaseEdgeType
from infrahub.core.diff.coordinator import DiffCoordinator
from infrahub.core.diff.model.path import BranchTrackingId
from infrahub.core.diff.repository.repository import DiffRepository
from infrahub.core.initialization import create_branch
from infrahub.core.manager import NodeManager
from infrahub.core.node import Node
from infrahub.core.timestamp import Timestamp
from infrahub.database import InfrahubDatabase
from infrahub.dependencies.registry import get_component_registry


class TestDiffCoordinator:
    async def test_node_deleted_after_branching(
        self, db: InfrahubDatabase, default_branch: Branch, person_john_main: Node
    ):
        branch = await create_branch(db=db, branch_name="branch")
        person_main = await NodeManager.get_one(db=db, branch=default_branch, id=person_john_main.id)
        await person_main.delete(db=db)
        person_branch = await NodeManager.get_one(db=db, branch=branch, id=person_john_main.id)
        await person_branch.delete(db=db)

        component_registry = get_component_registry()
        diff_coordinator = await component_registry.get_component(DiffCoordinator, db=db, branch=branch)
        diff = await diff_coordinator.update_branch_diff_and_return(base_branch=default_branch, diff_branch=branch)

        assert diff.base_branch_name == default_branch.name
        assert diff.diff_branch_name == branch.name
        nodes_by_id = {n.uuid: n for n in diff.nodes}
        assert set(nodes_by_id.keys()) == {person_john_main.id}
        node_diff = nodes_by_id[person_john_main.id]
        assert node_diff.action is DiffAction.REMOVED
        assert len(node_diff.relationships) == 0
        attributes_by_name = {a.name: a for a in node_diff.attributes}
        assert set(attributes_by_name.keys()) == {"name", "height"}
        for attr_diff in node_diff.attributes:
            assert attr_diff.action is DiffAction.REMOVED
            properties_by_type = {p.property_type: p for p in attr_diff.properties}
            assert set(properties_by_type.keys()) == {
                DatabaseEdgeType.HAS_VALUE,
                DatabaseEdgeType.IS_VISIBLE,
                DatabaseEdgeType.IS_PROTECTED,
            }
            for prop_diff in attr_diff.properties:
                assert prop_diff.action is DiffAction.REMOVED
                assert prop_diff.conflict is None
                assert prop_diff.new_value is None

    async def test_overlapping_diffs(self, db: InfrahubDatabase, default_branch: Branch, person_john_main: Node):
        branch = await create_branch(db=db, branch_name="branch")
        component_registry = get_component_registry()
        diff_coordinator = await component_registry.get_component(DiffCoordinator, db=db, branch=branch)
        diff_repository = await component_registry.get_component(DiffRepository, db=db, branch=branch)
        original_height = person_john_main.height.value
        person_john_branch = await NodeManager.get_one(db=db, branch=branch, id=person_john_main.id)

        # t0
        t0 = Timestamp()
        person_john_branch.height.value = 1
        await person_john_branch.save(db=db)
        # t1
        t1 = Timestamp()
        person_john_branch.height.value = 2
        await person_john_branch.save(db=db)
        # t2
        # diff from t0 - t2
        await diff_coordinator.update_branch_diff(base_branch=default_branch, diff_branch=branch)
        person_john_branch.height.value = 3
        await person_john_branch.save(db=db)
        # t3
        t3 = Timestamp()
        # overlapping diff from t1 to t3
        arbitrary_diff = await diff_coordinator.create_or_update_arbitrary_timeframe_diff(
            base_branch=default_branch, diff_branch=branch, from_time=t1, to_time=t3
        )

        full_diff = await diff_coordinator.update_branch_diff(base_branch=default_branch, diff_branch=branch)

        # check that only one branch-tracking diff exists for this branch
        tracking_diff = await diff_repository.get_one(
            diff_branch_name=branch.name, tracking_id=BranchTrackingId(name=branch.name)
        )
        assert tracking_diff == full_diff
        # test that arbitrary diff still exists
        retrieved_arbitrary_diff = await diff_repository.get_one(
            diff_branch_name=branch.name, diff_id=arbitrary_diff.uuid
        )
        assert retrieved_arbitrary_diff == arbitrary_diff

        # validate content of the diff
        assert full_diff.base_branch_name == default_branch.name
        assert full_diff.diff_branch_name == branch.name
        assert full_diff.from_time < t0
        assert full_diff.to_time > t3
        assert len(full_diff.nodes) == 1
        diff_node = full_diff.nodes.pop()
        assert diff_node.uuid == person_john_main.id
        assert diff_node.action is DiffAction.UPDATED
        assert not diff_node.relationships
        assert len(diff_node.attributes) == 1
        diff_attribute = diff_node.attributes.pop()
        assert diff_attribute.name == "height"
        assert diff_attribute.action is DiffAction.UPDATED
        assert len(diff_attribute.properties) == 1
        diff_property = diff_attribute.properties.pop()
        assert diff_property.property_type is DatabaseEdgeType.HAS_VALUE
        assert diff_property.action is DiffAction.UPDATED
        assert diff_property.previous_value == str(original_height)
        assert diff_property.new_value == "3"
