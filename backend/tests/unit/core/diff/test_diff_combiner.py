from dataclasses import replace
from datetime import UTC
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest
from pendulum.datetime import DateTime

from infrahub.core import registry
from infrahub.core.constants import DiffAction, RelationshipCardinality
from infrahub.core.constants.database import DatabaseEdgeType
from infrahub.core.diff.combiner import DiffCombiner
from infrahub.core.diff.model.path import (
    ConflictSelection,
    EnrichedDiffAttribute,
    EnrichedDiffNode,
    EnrichedDiffProperty,
    EnrichedDiffRelationship,
    EnrichedDiffSingleRelationship,
)
from infrahub.core.schema.node_schema import NodeSchema
from infrahub.core.schema_manager import SchemaManager
from infrahub.core.timestamp import Timestamp

from .factories import (
    EnrichedAttributeFactory,
    EnrichedConflictFactory,
    EnrichedNodeFactory,
    EnrichedPropertyFactory,
    EnrichedRelationshipElementFactory,
    EnrichedRelationshipGroupFactory,
    EnrichedRootFactory,
)


class TestDiffCombiner:
    def setup_method(self):
        self.diff_from_1 = Timestamp(DateTime(2024, 3, 5, 7, 9, 11, tzinfo=UTC))
        self.diff_to_1 = Timestamp(DateTime(2024, 3, 5, 9, 11, 13, tzinfo=UTC))
        self.diff_from_2 = Timestamp(DateTime(2024, 3, 5, 7, 9, 14, tzinfo=UTC))
        self.diff_to_2 = Timestamp(DateTime(2024, 3, 5, 11, 13, 15, tzinfo=UTC))
        self.base_branch = "main"
        self.diff_branch = "branch"
        self.diff_root_1 = EnrichedRootFactory.build(
            base_branch_name=self.base_branch,
            diff_branch_name=self.diff_branch,
            from_time=self.diff_from_1,
            to_time=self.diff_to_1,
        )
        self.diff_root_2 = EnrichedRootFactory.build(
            base_branch_name=self.base_branch,
            diff_branch_name=self.diff_branch,
            from_time=self.diff_from_2,
            to_time=self.diff_to_2,
        )
        self.expected_combined = EnrichedRootFactory.build(
            base_branch_name=self.base_branch,
            diff_branch_name=self.diff_branch,
            from_time=self.diff_from_1,
            to_time=self.diff_to_2,
            nodes=set(),
            num_added=0,
            num_updated=0,
            num_removed=0,
            num_conflicts=0,
            contains_conflict=False,
        )
        self.schema_manager = AsyncMock(spec=SchemaManager)
        registry.schema = self.schema_manager
        self.combiner = DiffCombiner()

    @pytest.fixture
    def with_schema_manager(self, car_person_schema_unregistered):
        for node_schema in car_person_schema_unregistered.nodes:
            if node_schema.kind == "TestCar":
                car_schema = node_schema
            elif node_schema.kind == "TestPerson":
                person_schema = node_schema

        def mock_get_node_schema(name, *args, **kwargs):
            if name == "TestCar":
                return car_schema
            if name == "TestPerson":
                return person_schema
            return MagicMock(spec=NodeSchema)

        self.schema_manager.get_node_schema.side_effect = mock_get_node_schema

    async def __call_system_under_test(self, diff_1, diff_2):
        return await self.combiner.combine(earlier_diff=diff_1, later_diff=diff_2)

    @pytest.mark.parametrize(
        "action_1,action_2",
        [
            (DiffAction.ADDED, DiffAction.REMOVED),
            (DiffAction.REMOVED, DiffAction.ADDED),
            # unchanged in both diffs and no child nodes will be removed
            (DiffAction.UNCHANGED, DiffAction.UNCHANGED),
        ],
    )
    async def test_add_and_remove_node_cancel_one_another(self, action_1, action_2):
        diff_node_1 = EnrichedNodeFactory.build(action=action_1, attributes=set(), relationships=set())
        diff_node_2 = EnrichedNodeFactory.build(
            uuid=diff_node_1.uuid, kind=diff_node_1.kind, action=action_2, attributes=set(), relationships=set()
        )
        self.diff_root_1.nodes = {diff_node_1}
        self.diff_root_2.nodes = {diff_node_2}

        combined = await self.__call_system_under_test(self.diff_root_1, self.diff_root_2)

        self.expected_combined.uuid = combined.uuid
        assert combined == self.expected_combined

    @pytest.mark.parametrize(
        "action_1,action_2,expected_action",
        [
            (DiffAction.ADDED, DiffAction.UPDATED, DiffAction.ADDED),
            (DiffAction.ADDED, DiffAction.UNCHANGED, DiffAction.ADDED),
            (DiffAction.UPDATED, DiffAction.REMOVED, DiffAction.REMOVED),
            (DiffAction.UPDATED, DiffAction.UNCHANGED, DiffAction.UPDATED),
            (DiffAction.UPDATED, DiffAction.UPDATED, DiffAction.UPDATED),
            (DiffAction.UNCHANGED, DiffAction.REMOVED, DiffAction.REMOVED),
            (DiffAction.UNCHANGED, DiffAction.UPDATED, DiffAction.UPDATED),
        ],
    )
    async def test_node_action_addition(self, action_1, action_2, expected_action):
        node_1_conflict = EnrichedConflictFactory.build()
        node_2_conflict = replace(node_1_conflict, selected_branch=ConflictSelection.DIFF_BRANCH)
        diff_node_1 = EnrichedNodeFactory.build(
            action=action_1, attributes=set(), relationships=set(), conflict=node_1_conflict
        )
        diff_node_2 = EnrichedNodeFactory.build(
            uuid=diff_node_1.uuid,
            kind=diff_node_1.kind,
            action=action_2,
            attributes=set(),
            relationships=set(),
            conflict=node_2_conflict,
            changed_at=Timestamp(),
        )
        self.diff_root_1.nodes = {diff_node_1}
        self.diff_root_2.nodes = {diff_node_2}

        combined = await self.__call_system_under_test(self.diff_root_1, self.diff_root_2)

        self.expected_combined.uuid = combined.uuid
        self.expected_combined.nodes = {
            EnrichedDiffNode(
                uuid=diff_node_2.uuid,
                kind=diff_node_2.kind,
                label=diff_node_2.label,
                changed_at=diff_node_2.changed_at,
                action=expected_action,
                path_identifier=diff_node_2.path_identifier,
                attributes=set(),
                relationships=set(),
                conflict=node_2_conflict,
            )
        }
        assert combined == self.expected_combined

    async def test_stale_parent_node_removed(self):
        parent_node_1 = EnrichedNodeFactory.build(action=DiffAction.UNCHANGED, attributes=set(), relationships=set())
        relationship_1 = EnrichedRelationshipGroupFactory.build(
            name="smells",
            label="Olfactory essences",
            action=DiffAction.UPDATED,
            relationships=set(),
            nodes={parent_node_1},
        )
        child_node_1 = EnrichedNodeFactory.build(action=DiffAction.ADDED, relationships={relationship_1})
        self.diff_root_1.nodes = {parent_node_1, child_node_1}
        parent_node_2 = EnrichedNodeFactory.build(action=DiffAction.UNCHANGED, attributes=set(), relationships=set())
        relationship_2 = EnrichedRelationshipGroupFactory.build(
            name=relationship_1.name,
            label=relationship_1.label,
            action=DiffAction.UPDATED,
            relationships=set(),
            nodes={parent_node_2},
            changed_at=Timestamp(),
        )
        child_node_2 = EnrichedNodeFactory.build(
            uuid=child_node_1.uuid,
            kind=child_node_1.kind,
            action=DiffAction.UPDATED,
            relationships={relationship_2},
            changed_at=Timestamp(),
        )
        self.diff_root_2.nodes = {parent_node_2, child_node_2}

        combined = await self.__call_system_under_test(self.diff_root_1, self.diff_root_2)

        self.expected_combined.uuid = combined.uuid
        expected_parent_node = replace(parent_node_2)
        expected_rel = replace(relationship_2, nodes={expected_parent_node})
        expected_child_node = replace(
            child_node_2,
            action=DiffAction.ADDED,
            relationships={expected_rel},
            attributes=child_node_1.attributes | child_node_2.attributes,
            conflict=None,
        )
        self.expected_combined.nodes = {expected_parent_node, expected_child_node}
        assert combined == self.expected_combined

    async def test_attributes_combined(self):
        added_attr_name = "width"
        added_attr_owner_property_1 = EnrichedPropertyFactory.build(
            property_type=DatabaseEdgeType.HAS_OWNER,
            action=DiffAction.ADDED,
            previous_value=None,
            new_value=str(uuid4()),
        )
        added_attr_owner_property_2 = EnrichedPropertyFactory.build(
            property_type=DatabaseEdgeType.HAS_OWNER,
            action=DiffAction.UPDATED,
            previous_value=added_attr_owner_property_1.new_value,
            new_value=str(uuid4()),
        )
        earlier_only_property = EnrichedPropertyFactory.build(property_type=DatabaseEdgeType.HAS_VALUE)
        added_attribute_1 = EnrichedAttributeFactory.build(
            name=added_attr_name,
            action=DiffAction.ADDED,
            properties={added_attr_owner_property_1, earlier_only_property},
        )
        later_only_property = EnrichedPropertyFactory.build(property_type=DatabaseEdgeType.HAS_SOURCE)
        added_attribute_2 = EnrichedAttributeFactory.build(
            name=added_attr_name, action=DiffAction.ADDED, properties={added_attr_owner_property_2, later_only_property}
        )
        attr_earlier_only = EnrichedAttributeFactory.build()
        attr_later_only = EnrichedAttributeFactory.build()
        earlier_node_1 = EnrichedNodeFactory.build(
            action=DiffAction.ADDED, attributes={added_attribute_1, attr_earlier_only}, relationships=set()
        )
        later_node_1 = EnrichedNodeFactory.build(
            uuid=earlier_node_1.uuid,
            kind=earlier_node_1.kind,
            action=DiffAction.UPDATED,
            attributes={added_attribute_2, attr_later_only},
            relationships=set(),
            changed_at=Timestamp(),
        )
        updated_attr_name = "length"
        updated_attr_value_property_1 = EnrichedPropertyFactory.build(
            property_type=DatabaseEdgeType.HAS_VALUE,
            action=DiffAction.UPDATED,
            previous_value=str(uuid4()),
            new_value=str(uuid4()),
        )
        updated_attr_value_property_2 = EnrichedPropertyFactory.build(
            property_type=DatabaseEdgeType.HAS_VALUE,
            action=DiffAction.UPDATED,
            previous_value=updated_attr_value_property_1.new_value,
            new_value=str(uuid4()),
        )
        updated_attribute_1 = EnrichedAttributeFactory.build(
            name=updated_attr_name,
            action=DiffAction.UPDATED,
            properties={updated_attr_value_property_1},
        )
        updated_attribute_2 = EnrichedAttributeFactory.build(
            name=updated_attr_name, action=DiffAction.UPDATED, properties={updated_attr_value_property_2}
        )
        earlier_node_2 = EnrichedNodeFactory.build(
            action=DiffAction.UPDATED, attributes={updated_attribute_1}, relationships=set()
        )
        later_node_2 = EnrichedNodeFactory.build(
            uuid=earlier_node_2.uuid,
            kind=earlier_node_2.kind,
            action=DiffAction.UPDATED,
            attributes={updated_attribute_2},
            relationships=set(),
            changed_at=Timestamp(),
        )

        self.diff_root_1.nodes = {earlier_node_1, earlier_node_2}
        self.diff_root_2.nodes = {later_node_1, later_node_2}

        expected_added_combined_property = EnrichedDiffProperty(
            property_type=added_attr_owner_property_2.property_type,
            changed_at=added_attr_owner_property_2.changed_at,
            previous_value=added_attr_owner_property_1.previous_value,
            new_value=added_attr_owner_property_2.new_value,
            path_identifier=added_attr_owner_property_2.path_identifier,
            action=DiffAction.ADDED,
        )
        expected_updated_combined_property = EnrichedDiffProperty(
            property_type=updated_attr_value_property_2.property_type,
            changed_at=updated_attr_value_property_2.changed_at,
            previous_value=updated_attr_value_property_1.previous_value,
            new_value=updated_attr_value_property_2.new_value,
            path_identifier=updated_attr_value_property_2.path_identifier,
            action=DiffAction.UPDATED,
        )
        expected_added_combined_attr = EnrichedDiffAttribute(
            name=added_attr_name,
            changed_at=added_attribute_2.changed_at,
            action=DiffAction.ADDED,
            path_identifier=added_attribute_2.path_identifier,
            properties={earlier_only_property, later_only_property, expected_added_combined_property},
        )
        expected_updated_combined_attr = EnrichedDiffAttribute(
            name=updated_attr_name,
            changed_at=updated_attribute_2.changed_at,
            action=DiffAction.UPDATED,
            path_identifier=updated_attribute_2.path_identifier,
            properties={expected_updated_combined_property},
        )
        expected_nodes = {
            EnrichedDiffNode(
                uuid=later_node_1.uuid,
                kind=later_node_1.kind,
                label=later_node_1.label,
                changed_at=later_node_1.changed_at,
                action=DiffAction.ADDED,
                path_identifier=later_node_1.path_identifier,
                attributes={attr_earlier_only, attr_later_only, expected_added_combined_attr},
            ),
            EnrichedDiffNode(
                uuid=later_node_2.uuid,
                kind=later_node_2.kind,
                label=later_node_2.label,
                changed_at=later_node_2.changed_at,
                action=DiffAction.UPDATED,
                path_identifier=later_node_2.path_identifier,
                attributes={expected_updated_combined_attr},
            ),
        }
        self.expected_combined.nodes = expected_nodes

        combined = await self.__call_system_under_test(self.diff_root_1, self.diff_root_2)

        self.expected_combined.uuid = combined.uuid
        assert combined == self.expected_combined

    async def test_relationship_one_combined(self, with_schema_manager):
        relationship_name = "owner"
        old_peer_id = str(uuid4())
        intermediate_peer_id = str(uuid4())
        new_peer_id = str(uuid4())
        early_only_property = EnrichedPropertyFactory.build(
            property_type=DatabaseEdgeType.HAS_OWNER, action=DiffAction.UPDATED
        )
        early_peer_conflict = EnrichedConflictFactory.build(selected_branch=ConflictSelection.BASE_BRANCH)
        early_peer_property = EnrichedPropertyFactory.build(
            property_type=DatabaseEdgeType.IS_RELATED,
            action=DiffAction.UPDATED,
            previous_value=old_peer_id,
            new_value=intermediate_peer_id,
            conflict=early_peer_conflict,
        )
        later_peer_conflict = replace(early_peer_conflict, uuid=str(uuid4()), selected_branch=None)
        later_peer_property = EnrichedPropertyFactory.build(
            property_type=DatabaseEdgeType.IS_RELATED,
            action=DiffAction.UPDATED,
            previous_value=intermediate_peer_id,
            new_value=new_peer_id,
            conflict=later_peer_conflict,
        )
        later_only_property = EnrichedPropertyFactory.build(
            property_type=DatabaseEdgeType.HAS_SOURCE, action=DiffAction.UPDATED
        )
        early_element = EnrichedRelationshipElementFactory.build(
            action=DiffAction.UPDATED,
            peer_id=intermediate_peer_id,
            properties={early_only_property, early_peer_property},
        )
        later_element = EnrichedRelationshipElementFactory.build(
            action=DiffAction.UPDATED,
            peer_id=new_peer_id,
            changed_at=early_element.changed_at.add_delta(minutes=1),
            properties={later_only_property, later_peer_property},
            conflict=EnrichedConflictFactory.build(),
        )
        early_relationship = EnrichedRelationshipGroupFactory.build(
            name=relationship_name,
            action=DiffAction.ADDED,
            relationships={early_element},
            nodes=set(),
            cardinality=RelationshipCardinality.ONE,
        )
        later_relationship = EnrichedRelationshipGroupFactory.build(
            name=relationship_name,
            action=DiffAction.UPDATED,
            cardinality=RelationshipCardinality.ONE,
            relationships={later_element},
            nodes=set(),
            changed_at=Timestamp(),
        )
        early_node = EnrichedNodeFactory.build(
            kind="TestCar", action=DiffAction.UPDATED, relationships={early_relationship}
        )
        later_node = EnrichedNodeFactory.build(
            uuid=early_node.uuid,
            kind="TestCar",
            action=DiffAction.UPDATED,
            relationships={later_relationship},
            changed_at=Timestamp(),
        )
        self.diff_root_1.nodes = {early_node}
        self.diff_root_2.nodes = {later_node}

        expected_peer_property = EnrichedDiffProperty(
            property_type=DatabaseEdgeType.IS_RELATED,
            changed_at=later_peer_property.changed_at,
            previous_value=old_peer_id,
            new_value=new_peer_id,
            path_identifier=later_peer_property.path_identifier,
            action=DiffAction.UPDATED,
            conflict=replace(
                later_peer_conflict, uuid=early_peer_conflict.uuid, selected_branch=early_peer_conflict.selected_branch
            ),
        )
        expected_relationship_element = EnrichedDiffSingleRelationship(
            changed_at=later_element.changed_at,
            action=DiffAction.UPDATED,
            peer_id=new_peer_id,
            peer_label=later_element.peer_label,
            path_identifier=later_element.path_identifier,
            properties={early_only_property, later_only_property, expected_peer_property},
            conflict=later_element.conflict,
        )
        expected_relationship = EnrichedDiffRelationship(
            name=relationship_name,
            label=later_relationship.label,
            cardinality=RelationshipCardinality.ONE,
            changed_at=later_relationship.changed_at,
            action=DiffAction.ADDED,
            path_identifier=later_relationship.path_identifier,
            relationships={expected_relationship_element},
        )
        expected_node = EnrichedDiffNode(
            uuid=later_node.uuid,
            kind="TestCar",
            label=later_node.label,
            changed_at=later_node.changed_at,
            action=DiffAction.UPDATED,
            path_identifier=later_node.path_identifier,
            relationships={expected_relationship},
            attributes=(early_node.attributes | later_node.attributes),
        )
        self.expected_combined.nodes = {expected_node}

        combined = await self.__call_system_under_test(self.diff_root_1, self.diff_root_2)

        self.expected_combined.uuid = combined.uuid

        assert combined == self.expected_combined

    async def test_relationship_many_combined(self, with_schema_manager):
        rel_prop_types = [DatabaseEdgeType.HAS_OWNER, DatabaseEdgeType.HAS_SOURCE, DatabaseEdgeType.IS_RELATED]
        relationship_name = "cars"
        removed_element_peer_id = str(uuid4())
        added_element_peer_id = str(uuid4())
        updated_element_peer_id = str(uuid4())
        canceled_element_peer_id = str(uuid4())

        removed_props_1 = set()
        removed_props_2 = set()
        expected_removed_props = set()
        for rpt in rel_prop_types:
            r1 = EnrichedPropertyFactory.build(action=DiffAction.UPDATED, property_type=rpt)
            r2 = EnrichedPropertyFactory.build(action=DiffAction.REMOVED, property_type=rpt, new_value=None)
            removed_props_1.add(r1)
            removed_props_2.add(r2)
            expected_removed_props.add(
                EnrichedDiffProperty(
                    property_type=rpt,
                    changed_at=r2.changed_at,
                    previous_value=r1.previous_value,
                    new_value=None,
                    path_identifier=r2.path_identifier,
                    action=DiffAction.REMOVED,
                )
            )
        removed_element_1 = EnrichedRelationshipElementFactory.build(
            action=DiffAction.UPDATED, peer_id=removed_element_peer_id, properties=removed_props_1
        )
        removed_element_2 = EnrichedRelationshipElementFactory.build(
            action=DiffAction.REMOVED, peer_id=removed_element_peer_id, properties=removed_props_2
        )

        added_props_1 = set()
        added_props_2 = set()
        expected_added_props = set()
        for rpt in rel_prop_types:
            a1 = EnrichedPropertyFactory.build(action=DiffAction.ADDED, previous_value=None, property_type=rpt)
            a2 = EnrichedPropertyFactory.build(action=DiffAction.UPDATED, property_type=rpt)
            added_props_1.add(a1)
            added_props_2.add(a2)
            expected_added_props.add(
                EnrichedDiffProperty(
                    property_type=rpt,
                    changed_at=a2.changed_at,
                    previous_value=None,
                    new_value=a2.new_value,
                    path_identifier=a2.path_identifier,
                    action=DiffAction.ADDED,
                )
            )
        added_element_1 = EnrichedRelationshipElementFactory.build(
            action=DiffAction.ADDED, peer_id=added_element_peer_id, properties=added_props_1
        )
        added_element_2 = EnrichedRelationshipElementFactory.build(
            action=DiffAction.UPDATED, peer_id=added_element_peer_id, properties=added_props_2
        )
        updated_property_1 = EnrichedPropertyFactory.build(
            property_type=DatabaseEdgeType.HAS_OWNER, action=DiffAction.UPDATED
        )
        updated_element_1 = EnrichedRelationshipElementFactory.build(
            action=DiffAction.UPDATED, peer_id=updated_element_peer_id, properties={updated_property_1}
        )
        updated_property_2 = EnrichedPropertyFactory.build(
            property_type=DatabaseEdgeType.HAS_OWNER, action=DiffAction.UPDATED
        )
        updated_element_2 = EnrichedRelationshipElementFactory.build(
            action=DiffAction.UPDATED, peer_id=updated_element_peer_id, properties={updated_property_2}
        )
        canceled_element_1 = EnrichedRelationshipElementFactory.build(
            action=DiffAction.ADDED,
            peer_id=canceled_element_peer_id,
        )
        canceled_element_2 = EnrichedRelationshipElementFactory.build(
            action=DiffAction.REMOVED,
            peer_id=canceled_element_peer_id,
        )
        relationship_group_1 = EnrichedRelationshipGroupFactory.build(
            name=relationship_name,
            action=DiffAction.UPDATED,
            cardinality=RelationshipCardinality.MANY,
            relationships={added_element_1, removed_element_1, updated_element_1, canceled_element_1},
            nodes=set(),
        )
        relationship_group_2 = EnrichedRelationshipGroupFactory.build(
            name=relationship_name,
            action=DiffAction.UPDATED,
            cardinality=RelationshipCardinality.MANY,
            relationships={added_element_2, removed_element_2, updated_element_2, canceled_element_2},
            changed_at=Timestamp(),
            nodes=set(),
        )
        node_1 = EnrichedNodeFactory.build(
            kind="TestPerson", action=DiffAction.UPDATED, relationships={relationship_group_1}
        )
        node_2 = EnrichedNodeFactory.build(
            uuid=node_1.uuid,
            kind=node_1.kind,
            action=DiffAction.UPDATED,
            relationships={relationship_group_2},
            changed_at=Timestamp(),
        )
        self.diff_root_1.nodes = {node_1}
        self.diff_root_2.nodes = {node_2}

        expected_removed_element = EnrichedDiffSingleRelationship(
            changed_at=removed_element_2.changed_at,
            action=DiffAction.REMOVED,
            peer_id=removed_element_peer_id,
            peer_label=removed_element_2.peer_label,
            path_identifier=removed_element_2.path_identifier,
            properties=expected_removed_props,
        )
        expected_added_element = EnrichedDiffSingleRelationship(
            changed_at=added_element_2.changed_at,
            action=DiffAction.ADDED,
            peer_id=added_element_peer_id,
            peer_label=added_element_2.peer_label,
            path_identifier=added_element_2.path_identifier,
            properties=expected_added_props,
        )
        expected_updated_element = EnrichedDiffSingleRelationship(
            changed_at=updated_element_2.changed_at,
            action=DiffAction.UPDATED,
            peer_id=updated_element_peer_id,
            peer_label=updated_element_2.peer_label,
            path_identifier=updated_element_2.path_identifier,
            properties={
                EnrichedDiffProperty(
                    property_type=DatabaseEdgeType.HAS_OWNER,
                    changed_at=updated_property_2.changed_at,
                    previous_value=updated_property_1.previous_value,
                    new_value=updated_property_2.new_value,
                    path_identifier=updated_property_2.path_identifier,
                    action=DiffAction.UPDATED,
                )
            },
        )
        expected_relationship = EnrichedDiffRelationship(
            name=relationship_name,
            label=relationship_group_2.label,
            cardinality=RelationshipCardinality.MANY,
            changed_at=relationship_group_2.changed_at,
            action=DiffAction.UPDATED,
            path_identifier=relationship_group_2.path_identifier,
            relationships={expected_added_element, expected_removed_element, expected_updated_element},
        )
        expected_node = EnrichedDiffNode(
            uuid=node_1.uuid,
            kind="TestPerson",
            label=node_2.label,
            changed_at=node_2.changed_at,
            action=DiffAction.UPDATED,
            path_identifier=node_2.path_identifier,
            relationships={expected_relationship},
            attributes=(node_1.attributes | node_2.attributes),
        )
        self.expected_combined.nodes = {expected_node}

        combined = await self.__call_system_under_test(self.diff_root_1, self.diff_root_2)

        self.expected_combined.uuid = combined.uuid

        assert combined == self.expected_combined

    async def test_relationship_with_only_nodes(self, with_schema_manager):
        relationship_name = "owner"
        early_parent_node = EnrichedNodeFactory.build(
            action=DiffAction.UNCHANGED, relationships=set(), attributes=set()
        )
        early_relationship = EnrichedRelationshipGroupFactory.build(
            name=relationship_name,
            action=DiffAction.ADDED,
            cardinality=RelationshipCardinality.MANY,
            relationships=set(),
            nodes={early_parent_node},
        )
        later_parent_node = EnrichedNodeFactory.build(
            action=DiffAction.UNCHANGED, relationships=set(), attributes=set()
        )
        later_relationship = EnrichedRelationshipGroupFactory.build(
            name=relationship_name,
            action=DiffAction.UPDATED,
            cardinality=RelationshipCardinality.MANY,
            relationships=set(),
            nodes={later_parent_node},
            changed_at=Timestamp(),
        )
        early_node = EnrichedNodeFactory.build(
            kind="TestCar", action=DiffAction.UPDATED, relationships={early_relationship}
        )
        later_node = EnrichedNodeFactory.build(
            uuid=early_node.uuid,
            kind="TestCar",
            action=DiffAction.UPDATED,
            relationships={later_relationship},
            changed_at=Timestamp(),
        )
        self.diff_root_1.nodes = {early_node, early_parent_node}
        self.diff_root_2.nodes = {later_node, later_parent_node}

        expected_relationship = EnrichedDiffRelationship(
            name=relationship_name,
            label=later_relationship.label,
            cardinality=RelationshipCardinality.MANY,
            changed_at=later_relationship.changed_at,
            action=DiffAction.ADDED,
            path_identifier=later_relationship.path_identifier,
            relationships=set(),
            nodes={later_parent_node},
        )
        expected_node = EnrichedDiffNode(
            uuid=later_node.uuid,
            kind="TestCar",
            label=later_node.label,
            changed_at=later_node.changed_at,
            action=DiffAction.UPDATED,
            path_identifier=later_node.path_identifier,
            relationships={expected_relationship},
            attributes=(early_node.attributes | later_node.attributes),
        )
        self.expected_combined.nodes = {expected_node, later_parent_node}

        combined = await self.__call_system_under_test(self.diff_root_1, self.diff_root_2)

        self.expected_combined.uuid = combined.uuid

        assert combined == self.expected_combined

    async def test_early_conflict_removed(self):
        node_uuid = str(uuid4())
        early_conflict = EnrichedConflictFactory.build()
        later_conflict = None
        early_node = EnrichedNodeFactory.build(uuid=node_uuid, action=DiffAction.UPDATED, conflict=early_conflict)
        later_node = EnrichedNodeFactory.build(uuid=node_uuid, action=DiffAction.UPDATED, conflict=later_conflict)
        self.diff_root_1.nodes = {early_node}
        self.diff_root_2.nodes = {later_node}

        combined = await self.__call_system_under_test(self.diff_root_1, self.diff_root_2)

        combined_node = combined.nodes.pop()
        assert combined_node.uuid == node_uuid
        assert combined_node.conflict is None

    async def test_later_conflict_added(self):
        node_uuid = str(uuid4())
        early_conflict = None
        later_conflict = EnrichedConflictFactory.build()
        early_node = EnrichedNodeFactory.build(uuid=node_uuid, action=DiffAction.UPDATED, conflict=early_conflict)
        later_node = EnrichedNodeFactory.build(uuid=node_uuid, action=DiffAction.UPDATED, conflict=later_conflict)
        self.diff_root_1.nodes = {early_node}
        self.diff_root_2.nodes = {later_node}

        combined = await self.__call_system_under_test(self.diff_root_1, self.diff_root_2)

        combined_node = combined.nodes.pop()
        assert combined_node.uuid == node_uuid
        assert combined_node.conflict == later_conflict

    @pytest.mark.parametrize(
        "early_values,later_values,selections",
        [
            (("abc", "def"), ("abc", "def"), (None, None, None)),
            (
                ("abc", "def"),
                ("abc", "def"),
                (None, ConflictSelection.BASE_BRANCH, ConflictSelection.BASE_BRANCH),
            ),
            (
                ("abc", "def"),
                ("abc", "def"),
                (ConflictSelection.DIFF_BRANCH, None, ConflictSelection.DIFF_BRANCH),
            ),
            (
                ("abc", "def"),
                ("abc", "def"),
                (ConflictSelection.DIFF_BRANCH, ConflictSelection.BASE_BRANCH, ConflictSelection.BASE_BRANCH),
            ),
            (("abc", "def"), ("abc", "xyz"), (None, None, None)),
            (("abc", "def"), ("abc", "xyz"), (ConflictSelection.DIFF_BRANCH, None, None)),
            (
                ("abc", "def"),
                ("abc", "xyz"),
                (None, ConflictSelection.BASE_BRANCH, ConflictSelection.BASE_BRANCH),
            ),
            (
                ("abc", "def"),
                ("abc", "xyz"),
                (ConflictSelection.DIFF_BRANCH, ConflictSelection.BASE_BRANCH, ConflictSelection.BASE_BRANCH),
            ),
            (
                ("abc", "def"),
                ("abc", "xyz"),
                (ConflictSelection.DIFF_BRANCH, ConflictSelection.DIFF_BRANCH, ConflictSelection.DIFF_BRANCH),
            ),
        ],
    )
    async def test_conflict_value_and_selection_update(self, early_values, later_values, selections):
        node_uuid = str(uuid4())
        early_conflict_uuid = str(uuid4())
        early_base_value, early_diff_value = early_values
        later_base_value, later_diff_value = later_values
        early_selection, later_selection, expected_selection = selections
        early_conflict = EnrichedConflictFactory.build(
            uuid=early_conflict_uuid,
            base_branch_value=early_base_value,
            diff_branch_value=early_diff_value,
            selected_branch=early_selection,
        )
        later_conflict = EnrichedConflictFactory.build(
            uuid=str(uuid4()),
            base_branch_value=later_base_value,
            diff_branch_value=later_diff_value,
            selected_branch=later_selection,
        )
        early_node = EnrichedNodeFactory.build(uuid=node_uuid, action=DiffAction.UPDATED, conflict=early_conflict)
        later_node = EnrichedNodeFactory.build(uuid=node_uuid, action=DiffAction.UPDATED, conflict=later_conflict)
        self.diff_root_1.nodes = {early_node}
        self.diff_root_2.nodes = {later_node}

        combined = await self.__call_system_under_test(self.diff_root_1, self.diff_root_2)

        combined_node = combined.nodes.pop()
        assert combined_node.uuid == node_uuid
        assert combined_node.conflict == replace(
            later_conflict, uuid=early_conflict_uuid, selected_branch=expected_selection
        )

    async def test_unchanged_parents_correctly_updated(self):
        child_node_uuid = str(uuid4())
        relationship_name = "related-things"
        parent_node_1 = EnrichedNodeFactory.build(action=DiffAction.UNCHANGED, attributes=set(), relationships=set())
        parent_node_2 = EnrichedNodeFactory.build(
            action=DiffAction.UNCHANGED, attributes=set(), relationships=set(), changed_at=Timestamp()
        )
        parent_rel_1 = EnrichedRelationshipGroupFactory.build(
            name=relationship_name,
            relationships=set(),
            nodes={parent_node_1},
            action=DiffAction.UNCHANGED,
            cardinality=RelationshipCardinality.ONE,
        )
        parent_rel_2 = EnrichedRelationshipGroupFactory.build(
            name=relationship_name,
            cardinality=RelationshipCardinality.ONE,
            relationships=set(),
            nodes={parent_node_2},
            action=DiffAction.UNCHANGED,
            changed_at=Timestamp(),
        )
        child_node_1 = EnrichedNodeFactory.build(
            uuid=child_node_uuid, kind="ThisKind", action=DiffAction.UPDATED, relationships={parent_rel_1}
        )
        child_node_2 = EnrichedNodeFactory.build(
            uuid=child_node_uuid,
            kind="ThisKind",
            action=DiffAction.UPDATED,
            relationships={parent_rel_2},
            changed_at=Timestamp(),
        )
        self.diff_root_1.nodes = {parent_node_1, child_node_1}
        self.diff_root_2.nodes = {parent_node_2, child_node_2}

        combined = await self.__call_system_under_test(self.diff_root_1, self.diff_root_2)

        expected_parent_node = replace(parent_node_2)
        expected_relationship = EnrichedDiffRelationship(
            name=relationship_name,
            label=parent_rel_2.label,
            changed_at=parent_rel_2.changed_at,
            cardinality=RelationshipCardinality.ONE,
            path_identifier=parent_rel_2.path_identifier,
            action=DiffAction.UNCHANGED,
            relationships=set(),
            nodes={expected_parent_node},
        )
        expected_child_node = EnrichedDiffNode(
            uuid=child_node_uuid,
            kind=child_node_2.kind,
            label=child_node_2.label,
            changed_at=child_node_2.changed_at,
            action=DiffAction.UPDATED,
            path_identifier=child_node_2.path_identifier,
            attributes=child_node_1.attributes | child_node_2.attributes,
            relationships={expected_relationship},
        )
        self.expected_combined.uuid = combined.uuid
        self.expected_combined.nodes = {expected_parent_node, expected_child_node}
        assert combined == self.expected_combined

    async def test_updated_parents_correctly_updated(self):
        child_node_uuid = str(uuid4())
        relationship_name = "related-things"
        parent_node_1 = EnrichedNodeFactory.build(
            action=DiffAction.UPDATED,
            relationships=set(),
            attributes={EnrichedAttributeFactory.build() for _ in range(2)},
        )
        parent_node_2 = EnrichedNodeFactory.build(
            action=DiffAction.UNCHANGED, attributes=set(), relationships=set(), changed_at=Timestamp()
        )
        child_element_1 = EnrichedRelationshipElementFactory.build()
        child_rel_1 = EnrichedRelationshipGroupFactory.build(
            name=relationship_name,
            relationships={child_element_1},
            nodes={parent_node_1},
            cardinality=RelationshipCardinality.ONE,
            action=DiffAction.UPDATED,
            num_added=0,
            num_updated=0,
            num_removed=0,
            num_conflicts=0,
            contains_conflict=False,
        )
        child_rel_2 = EnrichedRelationshipGroupFactory.build(
            name=relationship_name,
            relationships=set(),
            nodes={parent_node_2},
            cardinality=RelationshipCardinality.ONE,
            action=DiffAction.UNCHANGED,
            changed_at=Timestamp(),
        )
        child_node_1 = EnrichedNodeFactory.build(
            uuid=child_node_uuid, action=DiffAction.UPDATED, relationships={child_rel_1}
        )
        child_node_2 = EnrichedNodeFactory.build(
            uuid=child_node_uuid, action=DiffAction.UPDATED, relationships={child_rel_2}, changed_at=Timestamp()
        )
        self.diff_root_1.nodes = {parent_node_1, child_node_1}
        self.diff_root_2.nodes = {parent_node_2, child_node_2}

        combined = await self.__call_system_under_test(self.diff_root_1, self.diff_root_2)

        expected_parent_1 = replace(parent_node_1)
        expected_parent_2 = replace(parent_node_2)
        expected_child_rel = EnrichedDiffRelationship(
            name=relationship_name,
            label=child_rel_2.label,
            changed_at=child_rel_2.changed_at,
            cardinality=RelationshipCardinality.ONE,
            path_identifier=child_rel_2.path_identifier,
            action=DiffAction.UPDATED,
            relationships={child_element_1},
            nodes={expected_parent_2},
        )
        expected_child_node = EnrichedDiffNode(
            uuid=child_node_uuid,
            kind=child_node_2.kind,
            label=child_node_2.label,
            changed_at=child_node_2.changed_at,
            action=DiffAction.UPDATED,
            path_identifier=child_node_2.path_identifier,
            attributes=child_node_1.attributes | child_node_2.attributes,
            relationships={expected_child_rel},
        )
        self.expected_combined.uuid = combined.uuid
        self.expected_combined.nodes = {expected_parent_1, expected_parent_2, expected_child_node}
        assert combined == self.expected_combined
