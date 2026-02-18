import contextlib
from typing import Any
from unittest.mock import AsyncMock
from uuid import uuid4

from infrahub.core import registry
from infrahub.core.branch import Branch
from infrahub.core.constants import DiffAction, InfrahubKind
from infrahub.core.constants.database import DatabaseEdgeType
from infrahub.core.diff.calculator import DiffCalculator
from infrahub.core.diff.combiner import DiffCombiner
from infrahub.core.diff.coordinator import DiffCoordinator
from infrahub.core.diff.model.field_specifiers_map import NodeFieldSpecifierMap
from infrahub.core.diff.model.path import BranchTrackingId, EnrichedDiffRootMetadata, NameTrackingId
from infrahub.core.diff.repository.repository import DiffRepository
from infrahub.core.initialization import create_branch
from infrahub.core.manager import NodeManager
from infrahub.core.node import Node
from infrahub.core.schema.schema_branch import SchemaBranch
from infrahub.core.timestamp import Timestamp
from infrahub.database import InfrahubDatabase
from infrahub.dependencies.registry import get_component_registry
from infrahub.exceptions import SchemaNotFoundError
from infrahub.proposed_change.constants import ProposedChangeState


class TestDiffCoordinator:
    async def get_wrapped_diff_coordinator(
        self,
        db: InfrahubDatabase,
        branch: Branch,
    ) -> DiffCoordinator:
        component_registry = get_component_registry()
        diff_coordinator = await component_registry.get_component(DiffCoordinator, db=db, branch=branch)
        real_repository = await component_registry.get_component(DiffRepository, db=db, branch=branch)
        real_calculator = await component_registry.get_component(DiffCalculator, db=db, branch=branch)
        real_combiner = await component_registry.get_component(DiffCombiner, db=db, branch=branch)
        diff_coordinator.diff_repo = AsyncMock(wraps=real_repository)
        diff_coordinator.diff_calculator = AsyncMock(wraps=real_calculator)
        diff_coordinator.diff_combiner = AsyncMock(wraps=real_combiner)
        return diff_coordinator

    def reset_mocks(self, reset_it: Any) -> None:
        for attr_name in dir(reset_it):
            attr = getattr(reset_it, attr_name)
            if isinstance(attr, AsyncMock):
                attr.reset_mock()

    async def test_node_deleted_after_branching(
        self, db: InfrahubDatabase, default_branch: Branch, person_john_main: Node
    ) -> None:
        branch = await create_branch(db=db, branch_name="branch")
        person_main = await NodeManager.get_one(db=db, branch=default_branch, id=person_john_main.id)
        await person_main.delete(db=db)
        person_branch = await NodeManager.get_one(db=db, branch=branch, id=person_john_main.id)
        await person_branch.delete(db=db)

        component_registry = get_component_registry()
        diff_coordinator = await component_registry.get_component(DiffCoordinator, db=db, branch=branch)
        diff_repository = await component_registry.get_component(DiffRepository, db=db, branch=branch)
        diff_metadata = await diff_coordinator.update_branch_diff(base_branch=default_branch, diff_branch=branch)
        diff = await diff_repository.get_one(
            diff_branch_name=diff_metadata.diff_branch_name, diff_id=diff_metadata.uuid
        )

        assert diff.base_branch_name == default_branch.name
        assert diff.diff_branch_name == branch.name
        nodes_by_id = {n.uuid: n for n in diff.nodes}
        assert set(nodes_by_id.keys()) == {person_john_main.id}
        node_diff = nodes_by_id[person_john_main.id]
        assert node_diff.action is DiffAction.REMOVED
        assert len(node_diff.relationships) == 0
        attributes_by_name = {a.name: a for a in node_diff.attributes}
        assert set(attributes_by_name.keys()) == {"name", "height", "human_friendly_id", "display_label"}
        for attr_diff in node_diff.attributes:
            assert attr_diff.action is DiffAction.REMOVED
            properties_by_type = {p.property_type: p for p in attr_diff.properties}
            assert set(properties_by_type.keys()) == {
                DatabaseEdgeType.HAS_VALUE,
                DatabaseEdgeType.IS_PROTECTED,
            }
            for prop_diff in attr_diff.properties:
                assert prop_diff.action is DiffAction.REMOVED
                assert prop_diff.conflict is None
                assert prop_diff.new_value is None

    async def test_node_added_diff_updated_node_removed(
        self, db: InfrahubDatabase, default_branch: Branch, person_john_main: Node
    ) -> None:
        main_person_2 = await Node.init(db=db, schema="TestPerson", branch=default_branch)
        await main_person_2.new(db=db, name="Rex", height=190)
        await main_person_2.save(db=db)
        branch = await create_branch(db=db, branch_name="branch")
        # new person
        branch_person_1 = await Node.init(db=db, schema="TestPerson", branch=branch)
        await branch_person_1.new(db=db, name="Ray", height=180)
        await branch_person_1.save(db=db)
        # updated person
        branch_person_2 = await NodeManager.get_one(db=db, branch=branch, id=main_person_2.id)
        branch_person_2.height.value += 1
        await branch_person_2.save(db=db)
        # updated person
        branch_john = await NodeManager.get_one(db=db, branch=branch, id=person_john_main.id)
        branch_john.height.value += 1
        await branch_john.save(db=db)

        component_registry = get_component_registry()
        diff_coordinator = await component_registry.get_component(DiffCoordinator, db=db, branch=branch)
        diff_repository = await component_registry.get_component(DiffRepository, db=db, branch=branch)
        diff_metadata = await diff_coordinator.update_branch_diff(base_branch=default_branch, diff_branch=branch)
        diff = await diff_repository.get_one(
            diff_branch_name=diff_metadata.diff_branch_name, diff_id=diff_metadata.uuid
        )

        assert diff.base_branch_name == default_branch.name
        assert diff.diff_branch_name == branch.name
        nodes_by_id = {n.uuid: n for n in diff.nodes}
        assert set(nodes_by_id.keys()) == {branch_person_1.id, main_person_2.id, person_john_main.id}
        branch_node_diff_1 = nodes_by_id[branch_person_1.id]
        assert branch_node_diff_1.action is DiffAction.ADDED
        branch_node_diff_2 = nodes_by_id[main_person_2.id]
        assert branch_node_diff_2.action is DiffAction.UPDATED
        branch_john_diff = nodes_by_id[person_john_main.id]
        assert branch_john_diff.action is DiffAction.UPDATED

        # delete on branch to remove from diff
        fresh_branch_person_1 = await NodeManager.get_one(db=db, branch=branch, id=branch_person_1.id)
        await fresh_branch_person_1.delete(db=db)
        # update on main, validate not removed from diff
        fresh_main_person_2 = await NodeManager.get_one(db=db, branch=default_branch, id=main_person_2.id)
        fresh_main_person_2.height.value += 1
        await fresh_main_person_2.save(db=db)

        diff_metadata = await diff_coordinator.update_branch_diff(base_branch=default_branch, diff_branch=branch)
        diff = await diff_repository.get_one(
            diff_branch_name=diff_metadata.diff_branch_name, diff_id=diff_metadata.uuid
        )
        assert diff.base_branch_name == default_branch.name
        assert diff.diff_branch_name == branch.name
        nodes_by_id = {n.uuid: n for n in diff.nodes}
        assert set(nodes_by_id.keys()) == {person_john_main.id, fresh_main_person_2.id}
        branch_node_diff_2 = nodes_by_id[main_person_2.id]
        assert branch_node_diff_2.action is DiffAction.UPDATED
        branch_john_diff = nodes_by_id[person_john_main.id]
        assert branch_john_diff.action is DiffAction.UPDATED

    async def test_overlapping_diffs(
        self, db: InfrahubDatabase, default_branch: Branch, person_john_main: Node
    ) -> None:
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
            base_branch=default_branch,
            diff_branch=branch,
            from_time=t1,
            to_time=t3,
            name=str(uuid4()),
        )

        full_diff = await diff_coordinator.update_branch_diff(base_branch=default_branch, diff_branch=branch)

        # check that only one branch-tracking diff exists for this branch
        tracking_diff = await diff_repository.get_one(
            diff_branch_name=branch.name, tracking_id=BranchTrackingId(name=branch.name)
        )
        assert tracking_diff.uuid == full_diff.uuid
        # test that arbitrary diff still exists
        retrieved_arbitrary_diff = await diff_repository.get_one(
            diff_branch_name=branch.name, diff_id=arbitrary_diff.uuid
        )
        assert retrieved_arbitrary_diff.uuid == arbitrary_diff.uuid

        # validate content of the diff
        assert tracking_diff.base_branch_name == default_branch.name
        assert tracking_diff.diff_branch_name == branch.name
        assert tracking_diff.from_time < t0
        assert tracking_diff.to_time > t3
        assert len(tracking_diff.nodes) == 1
        diff_node = tracking_diff.nodes.pop()
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

    async def test_no_changes_skips_expensive_operations(
        self, db: InfrahubDatabase, default_branch: Branch, person_john_main: Node
    ) -> None:
        branch = await create_branch(db=db, branch_name="branch")
        wrapped_diff_coordinator = await self.get_wrapped_diff_coordinator(db=db, branch=branch)
        component_registry = get_component_registry()
        diff_repository = await component_registry.get_component(DiffRepository, db=db, branch=branch)

        person_john_branch = await NodeManager.get_one(db=db, branch=branch, id=person_john_main.id)
        person_john_branch.height.value += 1
        await person_john_branch.save(db=db)

        # calculate this diff in the middle of change timeframe
        diff_with_data = await wrapped_diff_coordinator.update_branch_diff(
            base_branch=default_branch, diff_branch=branch
        )
        self.reset_mocks(wrapped_diff_coordinator)

        # get the whole diff with no-change time periods before and after the calculated diff
        no_changes_diff_metadata = await wrapped_diff_coordinator.update_branch_diff(
            base_branch=default_branch, diff_branch=branch
        )
        assert type(no_changes_diff_metadata) is EnrichedDiffRootMetadata
        assert no_changes_diff_metadata.uuid == diff_with_data.uuid
        assert no_changes_diff_metadata.from_time == Timestamp(branch.get_branched_from())
        assert no_changes_diff_metadata.from_time == diff_with_data.from_time
        assert no_changes_diff_metadata.to_time > diff_with_data.to_time
        wrapped_diff_coordinator.diff_calculator.calculate_diff.assert_not_awaited()
        wrapped_diff_coordinator.diff_repo.get_one.assert_not_awaited()
        wrapped_diff_coordinator.diff_repo.hydrate_diff_pair.assert_not_awaited()

        # verify that to_time was updated on the database
        no_changes_diff = await diff_repository.get_one(
            diff_branch_name=no_changes_diff_metadata.diff_branch_name, diff_id=no_changes_diff_metadata.uuid
        )
        assert no_changes_diff.from_time == no_changes_diff_metadata.from_time == diff_with_data.from_time
        assert no_changes_diff.to_time == no_changes_diff_metadata.to_time

    async def test_unrelated_changes_skip_some_expensive_operations(
        self, db: InfrahubDatabase, default_branch: Branch, person_john_main: Node
    ) -> None:
        branch = await create_branch(db=db, branch_name="branch")
        wrapped_diff_coordinator = await self.get_wrapped_diff_coordinator(db=db, branch=branch)
        component_registry = get_component_registry()
        diff_repository = await component_registry.get_component(DiffRepository, db=db, branch=branch)

        # unrelated change on main before
        john_main = await NodeManager.get_one(db=db, id=person_john_main.id)
        john_main.name.value = "Before John"
        await john_main.save(db=db)

        # change on branch for the diff
        person_john_branch = await NodeManager.get_one(db=db, branch=branch, id=person_john_main.id)
        person_john_branch.height.value += 1
        await person_john_branch.save(db=db)

        # calculate this diff in the middle of change timeframe
        diff_with_data = await wrapped_diff_coordinator.update_branch_diff(
            base_branch=default_branch, diff_branch=branch
        )
        self.reset_mocks(wrapped_diff_coordinator)

        # unrelated change on main after
        john_main = await NodeManager.get_one(db=db, id=person_john_main.id)
        john_main.name.value = "After John"
        await john_main.save(db=db)

        # get the whole diff with no-change time periods before and after the calculated diff
        no_changes_diff_metadata = await wrapped_diff_coordinator.update_branch_diff(
            base_branch=default_branch, diff_branch=branch
        )
        assert type(no_changes_diff_metadata) is EnrichedDiffRootMetadata
        assert no_changes_diff_metadata.uuid == diff_with_data.uuid
        assert no_changes_diff_metadata.from_time == Timestamp(branch.get_branched_from())
        assert no_changes_diff_metadata.from_time == diff_with_data.from_time
        assert no_changes_diff_metadata.to_time > diff_with_data.to_time

        expected_previous_node_specifiers = NodeFieldSpecifierMap()
        expected_previous_node_specifiers.add_entry(
            node_uuid=person_john_main.id, kind=person_john_main.get_kind(), field_name="height"
        )
        wrapped_diff_coordinator.diff_calculator.calculate_diff.assert_awaited_once_with(
            base_branch=default_branch,
            diff_branch=branch,
            from_time=diff_with_data.to_time,
            to_time=no_changes_diff_metadata.to_time,
            include_unchanged=True,
            previous_node_specifiers=expected_previous_node_specifiers,
        )
        wrapped_diff_coordinator.diff_repo.get_one.assert_not_awaited()
        wrapped_diff_coordinator.diff_repo.save.assert_awaited_once()
        wrapped_diff_coordinator.diff_repo.hydrate_diff_pair.assert_not_awaited()

        # verify that to_time was updated on the database
        no_changes_diff = await diff_repository.get_one(
            diff_branch_name=no_changes_diff_metadata.diff_branch_name, diff_id=no_changes_diff_metadata.uuid
        )
        assert no_changes_diff.from_time == no_changes_diff_metadata.from_time == diff_with_data.from_time
        assert no_changes_diff.to_time == no_changes_diff_metadata.to_time

    async def test_diff_on_default_branch_only(
        self,
        db: InfrahubDatabase,
        default_branch: Branch,
        person_john_main: Node,
        person_jane_main: Node,
        person_alfred_main: Node,
        car_camry_main: Node,
        car_accord_main: Node,
    ) -> None:
        branch = await create_branch(db=db, branch_name="branch1")

        updated_person = await NodeManager.get_one(db=db, id=person_john_main.id)
        updated_person.height.value = 200
        await updated_person.save(db=db)

        new_person = await Node.init(db=db, schema="TestPerson", branch=default_branch)
        await new_person.new(db=db, name="Jeff", height=170)
        await new_person.save(db=db)

        deleted_person = await NodeManager.get_one(db=db, id=person_alfred_main.id)
        await deleted_person.delete(db=db)

        updated_car = await NodeManager.get_one(db=db, id=car_accord_main.id)
        await updated_car.owner.update(db=db, data=new_person)
        await updated_car.save(db=db)

        from_time = Timestamp(branch.get_branched_from())
        to_time = Timestamp()
        name = str(uuid4())
        diff_coordinator = await self.get_wrapped_diff_coordinator(db=db, branch=default_branch)
        component_registry = get_component_registry()
        diff_repository = await component_registry.get_component(DiffRepository, db=db, branch=default_branch)
        main_diff_metadata = await diff_coordinator.create_or_update_arbitrary_timeframe_diff(
            base_branch=default_branch, diff_branch=default_branch, from_time=from_time, to_time=to_time, name=name
        )
        main_diff = await diff_repository.get_one(diff_branch_name=default_branch.name, diff_id=main_diff_metadata.uuid)

        assert main_diff.base_branch_name == default_branch.name
        assert main_diff.diff_branch_name == default_branch.name
        assert main_diff.from_time == from_time
        assert main_diff.to_time == to_time
        assert main_diff.tracking_id == NameTrackingId(name=name)
        assert len(main_diff.nodes) == 4
        nodes_by_id = {n.uuid: n for n in main_diff.nodes}
        assert set(nodes_by_id.keys()) == {updated_person.id, new_person.id, deleted_person.id, updated_car.id}
        new_person_diff = nodes_by_id[new_person.id]
        assert new_person_diff.action is DiffAction.ADDED
        deleted_person_diff = nodes_by_id[deleted_person.id]
        assert deleted_person_diff.action is DiffAction.REMOVED
        updated_car_diff = nodes_by_id[updated_car.id]
        assert updated_car_diff.action is DiffAction.UPDATED
        assert updated_car_diff.attributes == set()
        rel_diffs = {(r.name, r.action) for r in updated_car_diff.relationships}
        assert rel_diffs == {("owner", DiffAction.UPDATED)}
        updated_person_diff = nodes_by_id[updated_person.id]
        rel_diffs = {(r.name, r.action) for r in updated_person_diff.relationships}
        assert rel_diffs == {("cars", DiffAction.UPDATED)}
        attr_diffs = {(a.name, a.action) for a in updated_person_diff.attributes}
        assert attr_diffs == {("height", DiffAction.UPDATED)}

    async def test_schema_deleted_on_source_and_target_branches(
        self,
        db: InfrahubDatabase,
        register_internal_models_schema,
        default_branch: Branch,
        person_john_main,
    ) -> None:
        branch = await create_branch(db=db, branch_name="branch1")
        component_registry = get_component_registry()
        diff_coordinator = await component_registry.get_component(DiffCoordinator, db=db, branch=branch)
        diff_repository = await component_registry.get_component(DiffRepository, db=db, branch=branch)

        # delete john on the default branch
        john_main = await NodeManager.get_one(db=db, id=person_john_main.id)
        await john_main.delete(db=db)

        # delete john on the branch
        john_branch = await NodeManager.get_one(db=db, id=person_john_main.id, branch=branch)
        await john_branch.delete(db=db)

        # delete the schema on the default branch
        main_schema_branch = registry.schema.get_schema_branch(name=default_branch.name)
        main_schema_branch.delete(name="TestPerson")

        # delete the schema on the branch, it might not exist b/c it was just deleted above
        branch_schema_branch = registry.schema.get_schema_branch(name=default_branch.name)
        with contextlib.suppress(SchemaNotFoundError):
            branch_schema_branch.delete(name="TestPerson")

        # calculate the diff
        diff_metadata = await diff_coordinator.update_branch_diff(base_branch=default_branch, diff_branch=branch)
        enriched_diff = await diff_repository.get_one(diff_branch_name=branch.name, diff_id=diff_metadata.uuid)

        assert len(enriched_diff.nodes) == 1
        nodes_by_id = {n.uuid: n for n in enriched_diff.nodes}
        assert set(nodes_by_id.keys()) == {person_john_main.id}
        john_diff = nodes_by_id[person_john_main.id]
        assert john_diff.action is DiffAction.REMOVED

    async def test_proposed_change_linked_during_update_branch_diff(
        self, db: InfrahubDatabase, default_branch: Branch, person_john_main: Node
    ) -> None:
        """Test that proposed_change_id is correctly linked to diffs during update_branch_diff."""
        branch = await create_branch(db=db, branch_name="branch")

        # Create a node that will act as the proposed change
        proposed_change_id = str(uuid4())
        await db.execute_query(query="CREATE (pc:Node {uuid: $uuid})", params={"uuid": proposed_change_id})

        # Make a change on the branch
        person_john_branch = await NodeManager.get_one(db=db, branch=branch, id=person_john_main.id)
        person_john_branch.height.value += 1
        await person_john_branch.save(db=db)

        component_registry = get_component_registry()
        diff_coordinator = await component_registry.get_component(DiffCoordinator, db=db, branch=branch)
        diff_repository = await component_registry.get_component(DiffRepository, db=db, branch=branch)

        # Update branch diff with proposed_change_id
        diff_metadata = await diff_coordinator.update_branch_diff(
            base_branch=default_branch, diff_branch=branch, proposed_change_id=proposed_change_id
        )

        # Verify the diff is linked to the proposed change
        assert diff_metadata.proposed_change_id == proposed_change_id

        # Verify via repository retrieval - need to query both branch names since
        retrieved_metadata = await diff_repository.get_roots_metadata(
            diff_branch_names=[branch.name, default_branch.name],
            proposed_change_id=proposed_change_id,
        )
        assert len(retrieved_metadata) == 2  # base and diff branch roots
        for metadata in retrieved_metadata:
            assert metadata.proposed_change_id == proposed_change_id

        # make another change on the branch
        person_john_branch = await NodeManager.get_one(db=db, branch=branch, id=person_john_main.id)
        person_john_branch.height.value += 1
        await person_john_branch.save(db=db)

        # update the diff w/ no proposed_change_id
        diff_metadata = await diff_coordinator.update_branch_diff(base_branch=default_branch, diff_branch=branch)

        # make sure the proposed_change_id sticks
        assert diff_metadata.proposed_change_id == proposed_change_id
        retrieved_metadata = await diff_repository.get_roots_metadata(
            diff_branch_names=[branch.name, default_branch.name],
            proposed_change_id=proposed_change_id,
        )
        assert len(retrieved_metadata) == 2  # base and diff branch roots
        for metadata in retrieved_metadata:
            assert metadata.proposed_change_id == proposed_change_id

    async def test_proposed_change_preserved_during_incremental_diff_update(
        self, db: InfrahubDatabase, default_branch: Branch, person_john_main: Node
    ) -> None:
        """Test that proposed_change_id is preserved when updating an existing diff incrementally."""
        branch = await create_branch(db=db, branch_name="branch")

        # Create a node that will act as the proposed change
        proposed_change_id = str(uuid4())
        await db.execute_query(query="CREATE (pc:Node {uuid: $uuid})", params={"uuid": proposed_change_id})

        # Make initial change on the branch
        person_john_branch = await NodeManager.get_one(db=db, branch=branch, id=person_john_main.id)
        person_john_branch.height.value += 1
        await person_john_branch.save(db=db)

        component_registry = get_component_registry()
        diff_coordinator = await component_registry.get_component(DiffCoordinator, db=db, branch=branch)
        diff_repository = await component_registry.get_component(DiffRepository, db=db, branch=branch)

        # First update with proposed_change_id
        first_diff_metadata = await diff_coordinator.update_branch_diff(
            base_branch=default_branch, diff_branch=branch, proposed_change_id=proposed_change_id
        )
        assert first_diff_metadata.proposed_change_id == proposed_change_id

        # Make another change on the branch
        person_john_branch = await NodeManager.get_one(db=db, branch=branch, id=person_john_main.id)
        person_john_branch.height.value += 1
        await person_john_branch.save(db=db)

        # Update again with the same proposed_change_id
        second_diff_metadata = await diff_coordinator.update_branch_diff(
            base_branch=default_branch, diff_branch=branch, proposed_change_id=proposed_change_id
        )

        # Verify proposed_change_id is still linked
        assert second_diff_metadata.proposed_change_id == proposed_change_id

        # The diff should have been updated in place (same uuid) or recreated with the link
        retrieved_metadata = await diff_repository.get_roots_metadata(
            diff_branch_names=[branch.name, default_branch.name],
            proposed_change_id=proposed_change_id,
        )
        assert len(retrieved_metadata) == 2
        for metadata in retrieved_metadata:
            assert metadata.proposed_change_id == proposed_change_id

    async def test_open_proposed_change_discovered_when_not_provided(
        self,
        db: InfrahubDatabase,
        register_core_models_schema: SchemaBranch,
        default_branch: Branch,
        person_john_main: Node,
    ) -> None:
        """When update_branch_diff is called without proposed_change_id but an OPEN
        CoreProposedChange exists for the branch, the diff should be linked to it."""
        branch = await create_branch(db=db, branch_name="branch")

        # Create a real OPEN CoreProposedChange for this branch
        proposed_change = await Node.init(db=db, schema=InfrahubKind.PROPOSEDCHANGE, branch=default_branch)
        await proposed_change.new(
            db=db,
            name="test-pc",
            source_branch=branch.name,
            destination_branch=default_branch.name,
        )
        await proposed_change.save(db=db)

        # Make a change on the branch so the diff has content
        person_john_branch = await NodeManager.get_one(db=db, branch=branch, id=person_john_main.id)
        person_john_branch.height.value += 1
        await person_john_branch.save(db=db)

        component_registry = get_component_registry()
        diff_coordinator = await component_registry.get_component(DiffCoordinator, db=db, branch=branch)
        diff_repository = await component_registry.get_component(DiffRepository, db=db, branch=branch)

        # Update branch diff WITHOUT providing proposed_change_id
        diff_metadata = await diff_coordinator.update_branch_diff(base_branch=default_branch, diff_branch=branch)

        # The diff should have discovered and linked the open proposed change
        assert diff_metadata.proposed_change_id == proposed_change.id

        # Verify both diff roots are linked via the repository
        retrieved_metadata = await diff_repository.get_roots_metadata(
            diff_branch_names=[branch.name, default_branch.name],
            proposed_change_id=proposed_change.id,
        )
        assert len(retrieved_metadata) == 2
        for metadata in retrieved_metadata:
            assert metadata.proposed_change_id == proposed_change.id

    async def test_non_open_proposed_changes_not_discovered(
        self,
        db: InfrahubDatabase,
        register_core_models_schema: SchemaBranch,
        default_branch: Branch,
        person_john_main: Node,
    ) -> None:
        """Diffs should not be linked to CLOSED, CANCELED, or MERGED proposed changes."""
        branch = await create_branch(db=db, branch_name="branch")

        # Create proposed changes in non-open states for this branch
        for state in (ProposedChangeState.CLOSED, ProposedChangeState.CANCELED, ProposedChangeState.MERGED):
            pc = await Node.init(db=db, schema=InfrahubKind.PROPOSEDCHANGE, branch=default_branch)
            await pc.new(
                db=db,
                name=f"pc-{state.value}",
                source_branch=branch.name,
                destination_branch=default_branch.name,
                state=state.value,
            )
            await pc.save(db=db)

        # Make a change on the branch so the diff has content
        person_john_branch = await NodeManager.get_one(db=db, branch=branch, id=person_john_main.id)
        person_john_branch.height.value += 1
        await person_john_branch.save(db=db)

        component_registry = get_component_registry()
        diff_coordinator = await component_registry.get_component(DiffCoordinator, db=db, branch=branch)

        # Update branch diff WITHOUT providing proposed_change_id
        diff_metadata = await diff_coordinator.update_branch_diff(base_branch=default_branch, diff_branch=branch)

        # The diff should NOT be linked to any of the non-open proposed changes
        assert diff_metadata.proposed_change_id is None
