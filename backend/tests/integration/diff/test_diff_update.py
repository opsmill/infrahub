from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

import pytest

from infrahub.core import registry
from infrahub.core.constants import BranchConflictKeep, DiffAction, InfrahubKind, ProposedChangeState
from infrahub.core.constants.database import DatabaseEdgeType
from infrahub.core.diff.model.path import BranchTrackingId, ConflictSelection, EnrichedDiffRoot
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
PROPOSED_CHANGE_NAME = "branch1-pc"
DIFF_UPDATE_QUERY = """
mutation DiffUpdate($branch_name: String!, $wait_for_completion: Boolean) {
    DiffUpdate(data: { branch: $branch_name, wait_for_completion: $wait_for_completion }) {
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

PROPOSED_CHANGE_CREATE = """
mutation ProposedChange(
  $name: String!,
  $source_branch: String!,
  $destination_branch: String!,
	) {
  CoreProposedChangeCreate(
    data: {
      name: {value: $name},
      source_branch: {value: $source_branch},
      destination_branch: {value: $destination_branch}
    }
  ) {
    object {
      id
    }
  }
}
"""

PROPOSED_CHANGE_UPDATE = """
mutation UpdateProposedChange(
    $proposed_change_id: String!,
    $state: String
  ) {
  CoreProposedChangeUpdate(data:
    {
      id: $proposed_change_id,
      state: {value: $state}
    }
  ) {
    ok
  }
}
"""


@dataclass
class TrackedConflict:
    conflict_id: str
    keep_branch: BranchConflictKeep
    conflict_selection: ConflictSelection
    expected_value: Any
    node_id: str


class TestDiffUpdateConflict(TestInfrahubApp):
    @classmethod
    def setup_class(cls) -> None:
        cls._tracked_items: dict[str, TrackedConflict] = {}

    def track_item(self, name: str, data: TrackedConflict) -> None:
        self._tracked_items[name] = data

    def retrieve_item(self, name: str) -> TrackedConflict:
        return self._tracked_items[name]

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
        kara = await Node.init(schema=TestKind.PERSON, db=db)
        await kara.new(db=db, name="Kara Thrace", height=165, description="Starbuck")
        await kara.save(db=db)
        koenigsegg = await Node.init(schema=TestKind.MANUFACTURER, db=db)
        await koenigsegg.new(db=db, name="Koenigsegg", customers=[john])
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

        return {
            "john": john,
            "kara": kara,
            "koenigsegg": koenigsegg,
            "people": people,
            "jesko": jesko,
        }

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
    async def get_branch_diff(db: InfrahubDatabase, branch: Branch) -> EnrichedDiffRoot:
        # Validate if the diff has been updated properly
        component_registry = get_component_registry()
        diff_repo = await component_registry.get_component(DiffRepository, db=db, branch=branch)

        return await diff_repo.get_one(
            tracking_id=BranchTrackingId(name=BRANCH_NAME),
            diff_branch_name=BRANCH_NAME,
        )

    async def _get_proposed_change_and_data_validator(self, db) -> tuple[Node, Node]:
        pcs = await NodeManager.query(db=db, schema=InfrahubKind.PROPOSEDCHANGE, filters={"source_branch": BRANCH_NAME})
        assert len(pcs) == 1
        pc = pcs[0]
        validators = await pc.validations.get_peers(db=db)
        data_validator = None
        for v in validators.values():
            if v.get_kind() == InfrahubKind.DATAVALIDATOR:
                data_validator = v

        assert data_validator
        return (pc, data_validator)

    async def test_diff_first_update(
        self, db: InfrahubDatabase, initial_dataset, create_diff, client: InfrahubClient
    ) -> None:
        """Validate if the diff is properly created the first time"""

        result = await client.execute_graphql(query=DIFF_UPDATE_QUERY, variables={"branch_name": BRANCH_NAME})
        assert result["DiffUpdate"]["ok"]

        # Validate if the diff has been updated properly
        diff_branch = registry.get_branch_from_registry(branch=BRANCH_NAME)
        diff = await self.get_branch_diff(db=db, branch=diff_branch)

        assert len(diff.nodes) == 2

    async def test_diff_second_update(
        self, db: InfrahubDatabase, initial_dataset, create_diff, client: InfrahubClient
    ) -> None:
        """Validate if the diff is properly updated the second time"""

        branch1 = registry.get_branch_from_registry(branch=BRANCH_NAME)

        bob = await Node.init(schema=TestKind.PERSON, db=db, branch=branch1.name)
        await bob.new(db=db, name="Bob", height=123, description="The less famous Bob")
        await bob.save(db=db)

        result = await client.execute_graphql(query=DIFF_UPDATE_QUERY, variables={"branch_name": BRANCH_NAME})
        assert result["DiffUpdate"]["ok"]

        # Validate if the diff has been updated properly
        diff_branch = registry.get_branch_from_registry(branch=BRANCH_NAME)
        diff = await self.get_branch_diff(db=db, branch=diff_branch)

        assert len(diff.nodes) == 3

    async def test_diff_add_attribute_value_conflict(
        self, db: InfrahubDatabase, initial_dataset, default_branch, client: InfrahubClient
    ) -> None:
        john_main = await NodeManager.get_one_by_id_or_default_filter(
            db=db, id="John", kind=TestKind.PERSON, branch=default_branch
        )
        john_main.age.value = 402
        await john_main.save(db=db)
        changes_done_time = Timestamp()

        result = await client.execute_graphql(
            query=DIFF_UPDATE_QUERY, variables={"branch_name": BRANCH_NAME, "wait_for_completion": True}
        )
        assert result["DiffUpdate"]["ok"]

        diff_branch = registry.get_branch_from_registry(branch=BRANCH_NAME)
        diff = await self.get_branch_diff(db=db, branch=diff_branch)

        assert diff.to_time > changes_done_time
        assert len(diff.nodes) == 3
        nodes_by_id = {n.uuid: n for n in diff.nodes}
        john_node = nodes_by_id[john_main.get_id()]
        assert len(john_node.attributes) == 1
        age_attribute = john_node.attributes.pop()
        assert age_attribute.name == "age"
        properties_by_type = {p.property_type: p for p in age_attribute.properties}
        value_property = properties_by_type[DatabaseEdgeType.HAS_VALUE]
        assert value_property.conflict
        conflict = value_property.conflict
        assert conflict.base_branch_action is DiffAction.ADDED
        assert conflict.base_branch_value == "402"
        assert conflict.diff_branch_action is DiffAction.ADDED
        assert conflict.diff_branch_value == "26"
        self.track_item(
            "attribute_value",
            TrackedConflict(
                conflict_id=conflict.uuid,
                keep_branch=BranchConflictKeep.SOURCE,
                conflict_selection=ConflictSelection.DIFF_BRANCH,
                expected_value=26,
                node_id=john_node.uuid,
            ),
        )

    async def test_diff_add_node_conflict(
        self, db: InfrahubDatabase, initial_dataset, default_branch, client: InfrahubClient
    ) -> None:
        kara_id = initial_dataset["kara"].get_id()
        kara_main = await NodeManager.get_one(db=db, id=kara_id, kind=TestKind.PERSON, branch=default_branch)
        await kara_main.delete(db=db)
        kara_branch = await NodeManager.get_one(db=db, id=kara_id, kind=TestKind.PERSON, branch=BRANCH_NAME)
        kara_branch.height.value += 1
        await kara_branch.save(db=db)
        changes_done_time = Timestamp()

        result = await client.execute_graphql(
            query=DIFF_UPDATE_QUERY, variables={"branch_name": BRANCH_NAME, "wait_for_completion": True}
        )
        assert result["DiffUpdate"]["ok"]

        diff_branch = registry.get_branch_from_registry(branch=BRANCH_NAME)
        diff = await self.get_branch_diff(db=db, branch=diff_branch)

        assert diff.to_time > changes_done_time
        assert len(diff.nodes) == 4
        nodes_by_id = {n.uuid: n for n in diff.nodes}
        kara_node = nodes_by_id[kara_id]
        assert kara_node.action is DiffAction.UPDATED
        assert kara_node.conflict.base_branch_action is DiffAction.REMOVED
        assert kara_node.conflict.base_branch_value is None
        assert kara_node.conflict.diff_branch_action is DiffAction.UPDATED
        assert kara_node.conflict.diff_branch_value is None
        self.track_item(
            "node_removed",
            TrackedConflict(
                conflict_id=kara_node.conflict.uuid,
                keep_branch=BranchConflictKeep.SOURCE,
                conflict_selection=ConflictSelection.DIFF_BRANCH,
                expected_value=None,
                node_id=kara_node.uuid,
            ),
        )
        assert len(kara_node.attributes) == 1
        height_attribute = kara_node.attributes.pop()
        assert height_attribute.name == "height"
        properties_by_type = {p.property_type: p for p in height_attribute.properties}
        value_property = properties_by_type[DatabaseEdgeType.HAS_VALUE]
        assert value_property.conflict
        attr_conflict = value_property.conflict
        assert attr_conflict.base_branch_action is DiffAction.REMOVED
        assert attr_conflict.base_branch_value is None
        assert attr_conflict.diff_branch_action is DiffAction.UPDATED
        assert attr_conflict.diff_branch_value == str(kara_branch.height.value)
        self.track_item(
            "node_removed_attribute_value",
            TrackedConflict(
                conflict_id=attr_conflict.uuid,
                keep_branch=BranchConflictKeep.TARGET,
                conflict_selection=ConflictSelection.BASE_BRANCH,
                expected_value=None,
                node_id=kara_node.uuid,
            ),
        )

    async def test_diff_resolve_attribute_value_conflict(
        self, db: InfrahubDatabase, initial_dataset, default_branch, client: InfrahubClient
    ) -> None:
        john_main = await NodeManager.get_one_by_id_or_default_filter(
            db=db, id="John", kind=TestKind.PERSON, branch=default_branch
        )
        attribute_value_conflict = self.retrieve_item("attribute_value")

        result = await client.execute_graphql(
            query=CONFLICT_SELECTION_QUERY,
            variables={
                "conflict_id": attribute_value_conflict.conflict_id,
                "selected_branch": attribute_value_conflict.conflict_selection.name,
            },
        )
        assert result["ResolveDiffConflict"]["ok"]

        diff_branch = registry.get_branch_from_registry(branch=BRANCH_NAME)
        diff = await self.get_branch_diff(db=db, branch=diff_branch)
        assert len(diff.nodes) == 4
        nodes_by_id = {n.uuid: n for n in diff.nodes}
        john_node = nodes_by_id[john_main.get_id()]
        assert len(john_node.attributes) == 1
        age_attribute = john_node.attributes.pop()
        properties_by_type = {p.property_type: p for p in age_attribute.properties}
        value_property = properties_by_type[DatabaseEdgeType.HAS_VALUE]
        assert value_property.conflict
        conflict = value_property.conflict
        assert conflict.uuid == attribute_value_conflict.conflict_id
        assert conflict.base_branch_action is DiffAction.ADDED
        assert conflict.base_branch_value == "402"
        assert conflict.diff_branch_action is DiffAction.ADDED
        assert conflict.diff_branch_value == "26"
        assert conflict.selected_branch is attribute_value_conflict.conflict_selection

    async def test_create_proposed_change_data_checks_created(
        self, db: InfrahubDatabase, initial_dataset, default_branch, client: InfrahubClient
    ) -> None:
        result = await client.execute_graphql(
            query=PROPOSED_CHANGE_CREATE,
            variables={
                "name": PROPOSED_CHANGE_NAME,
                "source_branch": BRANCH_NAME,
                "destination_branch": default_branch.name,
            },
        )
        assert result["CoreProposedChangeCreate"]["object"]["id"]
        attribute_value_conflict = self.retrieve_item("attribute_value")
        node_removed_conflict = self.retrieve_item("node_removed")
        node_removed_attribute_value_conflict = self.retrieve_item("node_removed_attribute_value")

        _, data_validator = await self._get_proposed_change_and_data_validator(db=db)
        core_data_checks = await data_validator.checks.get_peers(db=db)
        assert set(core_data_checks.keys()) == {
            attribute_value_conflict.conflict_id,
            node_removed_conflict.conflict_id,
            node_removed_attribute_value_conflict.conflict_id,
        }
        attr_value_data_check = core_data_checks[attribute_value_conflict.conflict_id]
        node_removed_data_check = core_data_checks[node_removed_conflict.conflict_id]
        node_removed_attr_value_data_check = core_data_checks[node_removed_attribute_value_conflict.conflict_id]
        assert attr_value_data_check.keep_branch.value.value == attribute_value_conflict.keep_branch.value
        assert node_removed_attr_value_data_check.keep_branch.value is None
        assert node_removed_data_check.keep_branch.value is None

    async def test_diff_resolve_node_removed_conflicts(
        self, db: InfrahubDatabase, initial_dataset, default_branch, client: InfrahubClient
    ) -> None:
        attribute_value_conflict = self.retrieve_item("attribute_value")
        node_removed_conflict = self.retrieve_item("node_removed")
        node_removed_attribute_value_conflict = self.retrieve_item("node_removed_attribute_value")
        result = await client.execute_graphql(
            query=CONFLICT_SELECTION_QUERY,
            variables={
                "conflict_id": node_removed_conflict.conflict_id,
                "selected_branch": node_removed_conflict.conflict_selection.name,
            },
        )
        assert result["ResolveDiffConflict"]["ok"]
        result = await client.execute_graphql(
            query=CONFLICT_SELECTION_QUERY,
            variables={
                "conflict_id": node_removed_attribute_value_conflict.conflict_id,
                "selected_branch": node_removed_attribute_value_conflict.conflict_selection.name,
            },
        )
        assert result["ResolveDiffConflict"]["ok"]

        diff_branch = registry.get_branch_from_registry(branch=BRANCH_NAME)
        kara_main = initial_dataset["kara"]
        kara_branch = await NodeManager.get_one(db=db, branch=diff_branch, id=kara_main.get_id())
        diff = await self.get_branch_diff(db=db, branch=diff_branch)

        # check EnrichedDiff
        assert len(diff.nodes) == 4
        nodes_by_id = {n.uuid: n for n in diff.nodes}
        kara_node = nodes_by_id[kara_main.get_id()]
        assert kara_node.action is DiffAction.UPDATED
        assert kara_node.conflict.uuid == node_removed_conflict.conflict_id
        assert kara_node.conflict.base_branch_action is DiffAction.REMOVED
        assert kara_node.conflict.base_branch_value is None
        assert kara_node.conflict.diff_branch_action is DiffAction.UPDATED
        assert kara_node.conflict.diff_branch_value is None
        assert kara_node.conflict.selected_branch == node_removed_conflict.conflict_selection
        assert len(kara_node.attributes) == 1
        height_attribute = kara_node.attributes.pop()
        assert height_attribute.name == "height"
        properties_by_type = {p.property_type: p for p in height_attribute.properties}
        value_property = properties_by_type[DatabaseEdgeType.HAS_VALUE]
        assert value_property.conflict
        attr_conflict = value_property.conflict
        assert attr_conflict.uuid == node_removed_attribute_value_conflict.conflict_id
        assert attr_conflict.base_branch_action is DiffAction.REMOVED
        assert attr_conflict.base_branch_value is None
        assert attr_conflict.diff_branch_action is DiffAction.UPDATED
        assert attr_conflict.diff_branch_value == str(kara_branch.height.value)
        assert attr_conflict.selected_branch == node_removed_attribute_value_conflict.conflict_selection
        # check CoreDataChecks
        _, data_validator = await self._get_proposed_change_and_data_validator(db=db)
        core_data_checks = await data_validator.checks.get_peers(db=db)
        assert set(core_data_checks.keys()) == {
            attribute_value_conflict.conflict_id,
            node_removed_conflict.conflict_id,
            node_removed_attribute_value_conflict.conflict_id,
        }
        attr_value_data_check = core_data_checks[attribute_value_conflict.conflict_id]
        node_removed_data_check = core_data_checks[node_removed_conflict.conflict_id]
        node_removed_attr_value_data_check = core_data_checks[node_removed_attribute_value_conflict.conflict_id]
        assert attr_value_data_check.keep_branch.value.value == attribute_value_conflict.keep_branch.value
        assert node_removed_data_check.keep_branch.value.value == node_removed_conflict.keep_branch.value
        assert (
            node_removed_attr_value_data_check.keep_branch.value.value
            == node_removed_attribute_value_conflict.keep_branch.value
        )

    async def test_merge_proposed_change(
        self, db: InfrahubDatabase, initial_dataset, default_branch, client: InfrahubClient
    ) -> None:
        pc, _ = await self._get_proposed_change_and_data_validator(db=db)
        result = await client.execute_graphql(
            query=PROPOSED_CHANGE_UPDATE,
            variables={
                "proposed_change_id": pc.get_id(),
                "state": ProposedChangeState.MERGED.value,
            },
        )
        assert result["CoreProposedChangeUpdate"]["ok"]

        attribute_value_conflict = self.retrieve_item("attribute_value")
        john_id = initial_dataset["john"].get_id()
        john_main = await NodeManager.get_one(db=db, branch=default_branch, id=john_id)
        assert john_main.age.value == attribute_value_conflict.expected_value
        # TODO: node deleted on main is not un-deleted during conflict resolution
        # node_removed_attribute_value_conflict = self.retrieve_item("node_removed_attribute_value")
        # kara_id = initial_dataset["kara"].get_id()
        # kara_main = await NodeManager.get_one(db=db, branch=default_branch, id=kara_id)
        # assert kara_main.height.value == node_removed_attribute_value_conflict.expected_value
