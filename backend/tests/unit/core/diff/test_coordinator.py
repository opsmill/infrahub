
from infrahub.core.branch import Branch
from infrahub.core.constants import DiffAction
from infrahub.core.constants.database import DatabaseEdgeType
from infrahub.core.diff.coordinator import DiffCoordinator
from infrahub.core.initialization import create_branch
from infrahub.core.manager import NodeManager
from infrahub.core.node import Node
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
        diff = await diff_coordinator.update_branch_diff(base_branch=default_branch, diff_branch=branch)

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
