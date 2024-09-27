import random
from uuid import uuid4

from infrahub.core.branch import Branch
from infrahub.core.constants import DiffAction, RelationshipCardinality
from infrahub.core.constants.database import DatabaseEdgeType
from infrahub.core.diff.conflicts_enricher import ConflictsEnricher
from infrahub.core.diff.model.path import EnrichedDiffConflict, EnrichedDiffRoot
from infrahub.core.initialization import create_branch
from infrahub.core.timestamp import Timestamp
from infrahub.database import InfrahubDatabase

from .factories import (
    EnrichedAttributeFactory,
    EnrichedNodeFactory,
    EnrichedPropertyFactory,
    EnrichedRelationshipElementFactory,
    EnrichedRelationshipGroupFactory,
    EnrichedRootFactory,
)


class TestConflictsEnricher:
    def setup_method(self):
        self.base_branch = Branch(name="main")
        self.diff_branch = Branch(name="branch")
        self.from_time = Timestamp("2024-07-28T13:45:22Z")
        self.to_time = Timestamp()

    def _set_conflicts_to_none(self, enriched_diff: EnrichedDiffRoot):
        for node in enriched_diff.nodes:
            node.conflict = None
            for attribute in node.attributes:
                for attr_prop in attribute.properties:
                    attr_prop.conflict = None
            for relationship in node.relationships:
                for element in relationship.relationships:
                    element.conflict = None
                    for element_prop in element.properties:
                        element_prop.conflict = None

    async def __call_system_under_test(self, db: InfrahubDatabase, base_enriched_diff, branch_enriched_diff) -> None:
        conflicts_enricher = ConflictsEnricher()
        return await conflicts_enricher.add_conflicts_to_branch_diff(
            base_diff_root=base_enriched_diff, branch_diff_root=branch_enriched_diff
        )

    async def test_no_conflicts(self, db: InfrahubDatabase):
        base_root = EnrichedRootFactory.build(nodes=[])
        branch_root = EnrichedRootFactory.build(nodes=[])
        for diff_root in (base_root, branch_root):
            properties = {
                EnrichedPropertyFactory.build(property_type=property_type)
                for property_type in random.sample(list(DatabaseEdgeType), 3)
            }
            attribute = EnrichedAttributeFactory.build(properties=properties)
            diff_root.nodes = {EnrichedNodeFactory.build(attributes={attribute}, relationships=set())}
        self._set_conflicts_to_none(base_root)
        self._set_conflicts_to_none(branch_root)

        await self.__call_system_under_test(db=db, base_enriched_diff=base_root, branch_enriched_diff=branch_root)

        for node in branch_root.nodes:
            assert node.conflict is None
            for attribute in node.attributes:
                for attr_prop in attribute.properties:
                    assert attr_prop.conflict is None
            for relationship in node.relationships:
                for element in relationship.relationships:
                    assert element.conflict is None
                    for element_prop in element.properties:
                        assert element_prop.conflict is None

    async def test_one_node_conflict(self, db: InfrahubDatabase):
        node_uuid = str(uuid4())
        node_kind = "SomethingSmelly"
        base_conflict_node = EnrichedNodeFactory.build(
            uuid=node_uuid, kind=node_kind, action=DiffAction.UPDATED, relationships=set()
        )
        base_nodes = {base_conflict_node, EnrichedNodeFactory.build(relationships=set())}
        branch_conflict_node = EnrichedNodeFactory.build(
            uuid=node_uuid, kind=node_kind, action=DiffAction.REMOVED, relationships=set()
        )
        branch_nodes = {branch_conflict_node, EnrichedNodeFactory.build(relationships=set())}
        base_root = EnrichedRootFactory.build(nodes=base_nodes)
        branch_root = EnrichedRootFactory.build(nodes=branch_nodes)
        self._set_conflicts_to_none(base_root)
        self._set_conflicts_to_none(branch_root)

        await self.__call_system_under_test(db=db, base_enriched_diff=base_root, branch_enriched_diff=branch_root)

        for node in branch_root.nodes:
            if node.uuid == node_uuid:
                assert node.conflict
                assert node.conflict == EnrichedDiffConflict(
                    uuid=node.conflict.uuid,
                    base_branch_action=DiffAction.UPDATED,
                    base_branch_value=None,
                    base_branch_changed_at=base_conflict_node.changed_at,
                    diff_branch_action=DiffAction.REMOVED,
                    diff_branch_value=None,
                    diff_branch_changed_at=branch_conflict_node.changed_at,
                    selected_branch=None,
                )
            else:
                assert node.conflict is None

    async def test_one_attribute_conflict(self, db: InfrahubDatabase):
        property_type = DatabaseEdgeType.HAS_OWNER
        attribute_name = "smell"
        node_uuid = str(uuid4())
        node_kind = "SomethingSmelly"
        base_conflict_property = EnrichedPropertyFactory.build(
            property_type=property_type, action=DiffAction.UPDATED, new_value="potato salad"
        )
        base_properties = {
            base_conflict_property,
            EnrichedPropertyFactory.build(property_type=DatabaseEdgeType.HAS_SOURCE),
        }
        base_attributes = {
            EnrichedAttributeFactory.build(),
            EnrichedAttributeFactory.build(properties=base_properties, name=attribute_name),
        }
        base_nodes = {
            EnrichedNodeFactory.build(
                uuid=node_uuid,
                kind=node_kind,
                action=DiffAction.UPDATED,
                attributes=base_attributes,
                relationships=set(),
            ),
            EnrichedNodeFactory.build(relationships=set()),
        }
        base_root = EnrichedRootFactory.build(nodes=base_nodes)
        branch_conflict_property = EnrichedPropertyFactory.build(
            property_type=property_type, action=DiffAction.UPDATED, new_value="ham sandwich"
        )
        branch_properties = {
            branch_conflict_property,
            EnrichedPropertyFactory.build(property_type=DatabaseEdgeType.IS_VISIBLE),
        }
        branch_attributes = {
            EnrichedAttributeFactory.build(),
            EnrichedAttributeFactory.build(properties=branch_properties, name=attribute_name),
        }
        branch_nodes = {
            EnrichedNodeFactory.build(
                uuid=node_uuid,
                kind=node_kind,
                action=DiffAction.UPDATED,
                attributes=branch_attributes,
                relationships=set(),
            ),
            EnrichedNodeFactory.build(relationships=set()),
        }
        branch_root = EnrichedRootFactory.build(nodes=branch_nodes)
        self._set_conflicts_to_none(base_root)
        self._set_conflicts_to_none(branch_root)

        await self.__call_system_under_test(db=db, base_enriched_diff=base_root, branch_enriched_diff=branch_root)

        for node in branch_root.nodes:
            assert node.conflict is None
            for attribute in node.attributes:
                for prop in attribute.properties:
                    if (
                        node.uuid == node_uuid
                        and attribute.name == attribute_name
                        and prop.property_type == property_type
                    ):
                        assert prop.conflict
                        assert prop.conflict == EnrichedDiffConflict(
                            uuid=prop.conflict.uuid,
                            base_branch_action=DiffAction.UPDATED,
                            base_branch_value=base_conflict_property.new_value,
                            base_branch_changed_at=base_conflict_property.changed_at,
                            diff_branch_action=DiffAction.UPDATED,
                            diff_branch_value=branch_conflict_property.new_value,
                            diff_branch_changed_at=branch_conflict_property.changed_at,
                            selected_branch=None,
                        )
                    else:
                        assert prop.conflict is None

    async def test_cardinality_one_conflicts(self, db: InfrahubDatabase, car_person_schema):
        branch = await create_branch(db=db, branch_name="branch")
        property_type = DatabaseEdgeType.IS_RELATED
        relationship_name = "owner"
        node_uuid = str(uuid4())
        node_kind = "TestCar"
        previous_peer_id = str(uuid4())
        new_base_peer_id = str(uuid4())
        base_conflict_property = EnrichedPropertyFactory.build(
            property_type=property_type,
            previous_value=previous_peer_id,
            new_value=new_base_peer_id,
            action=DiffAction.UPDATED,
        )
        base_properties = {
            base_conflict_property,
            EnrichedPropertyFactory.build(property_type=DatabaseEdgeType.IS_VISIBLE),
        }
        base_relationships = {
            EnrichedRelationshipGroupFactory.build(
                name=relationship_name,
                relationships={
                    EnrichedRelationshipElementFactory.build(
                        peer_id=new_base_peer_id, properties=base_properties, action=DiffAction.UPDATED
                    )
                },
                cardinality=RelationshipCardinality.ONE,
            )
        }
        base_nodes = {
            EnrichedNodeFactory.build(
                uuid=node_uuid,
                kind=node_kind,
                action=DiffAction.UPDATED,
                relationships=base_relationships,
            ),
            EnrichedNodeFactory.build(relationships=set()),
        }
        base_root = EnrichedRootFactory.build(nodes=base_nodes)
        branch_conflict_property = EnrichedPropertyFactory.build(
            property_type=property_type, previous_value=previous_peer_id, new_value=None, action=DiffAction.REMOVED
        )
        branch_properties = {
            branch_conflict_property,
            EnrichedPropertyFactory.build(property_type=DatabaseEdgeType.HAS_OWNER),
        }
        branch_relationships = {
            EnrichedRelationshipGroupFactory.build(
                name=relationship_name,
                relationships={
                    EnrichedRelationshipElementFactory.build(
                        peer_id=previous_peer_id, properties=branch_properties, action=DiffAction.REMOVED
                    )
                },
                cardinality=RelationshipCardinality.ONE,
            )
        }
        branch_nodes = {
            EnrichedNodeFactory.build(
                uuid=node_uuid,
                kind=node_kind,
                action=DiffAction.UPDATED,
                relationships=branch_relationships,
            ),
            EnrichedNodeFactory.build(relationships=set()),
        }
        branch_root = EnrichedRootFactory.build(nodes=branch_nodes, diff_branch_name=branch.name)
        self._set_conflicts_to_none(base_root)
        self._set_conflicts_to_none(branch_root)

        await self.__call_system_under_test(db=db, base_enriched_diff=base_root, branch_enriched_diff=branch_root)

        for node in branch_root.nodes:
            assert node.conflict is None
            for attribute in node.attributes:
                for prop in attribute.properties:
                    assert prop.conflict is None
            for rel in node.relationships:
                for rel_element in rel.relationships:
                    if (
                        node.uuid == node_uuid
                        and rel.name == relationship_name
                        and rel_element.peer_id == previous_peer_id
                    ):
                        assert rel_element.conflict
                        assert rel_element.conflict == EnrichedDiffConflict(
                            uuid=rel_element.conflict.uuid,
                            base_branch_action=DiffAction.UPDATED,
                            base_branch_value=new_base_peer_id,
                            base_branch_changed_at=base_conflict_property.changed_at,
                            diff_branch_action=DiffAction.REMOVED,
                            diff_branch_value=None,
                            diff_branch_changed_at=branch_conflict_property.changed_at,
                            selected_branch=None,
                        )

    async def test_cardinality_many_conflicts(self, db: InfrahubDatabase, car_person_schema):
        branch = await create_branch(db=db, branch_name="branch")
        peer_id_1 = str(uuid4())
        peer_id_2 = str(uuid4())
        conflict_property_type_1 = DatabaseEdgeType.HAS_SOURCE
        conflict_property_type_2 = DatabaseEdgeType.HAS_OWNER
        previous_property_value_1 = str(uuid4())
        base_property_value_1 = str(uuid4())
        branch_property_value_1 = str(uuid4())
        previous_property_value_2 = str(uuid4())
        base_property_value_2 = str(uuid4())
        branch_property_value_2 = str(uuid4())
        relationship_name = "cars"
        node_uuid = str(uuid4())
        node_kind = "TestPerson"
        base_conflict_property_1 = EnrichedPropertyFactory.build(
            property_type=conflict_property_type_1,
            previous_value=previous_property_value_1,
            new_value=base_property_value_1,
            action=DiffAction.ADDED,
        )
        base_properties_1 = {
            base_conflict_property_1,
            EnrichedPropertyFactory.build(property_type=DatabaseEdgeType.IS_VISIBLE),
        }
        base_conflict_property_2 = EnrichedPropertyFactory.build(
            property_type=conflict_property_type_2,
            previous_value=previous_property_value_2,
            new_value=base_property_value_2,
            action=DiffAction.UPDATED,
        )
        base_properties_2 = {
            base_conflict_property_2,
            EnrichedPropertyFactory.build(property_type=DatabaseEdgeType.IS_PROTECTED),
        }
        base_relationships = {
            EnrichedRelationshipGroupFactory.build(
                name=relationship_name,
                relationships={
                    EnrichedRelationshipElementFactory.build(peer_id=peer_id_1, properties=base_properties_1),
                    EnrichedRelationshipElementFactory.build(peer_id=peer_id_2, properties=base_properties_2),
                },
                cardinality=RelationshipCardinality.MANY,
            )
        }
        base_nodes = {
            EnrichedNodeFactory.build(
                uuid=node_uuid,
                kind=node_kind,
                action=DiffAction.UPDATED,
                relationships=base_relationships,
            ),
            EnrichedNodeFactory.build(),
        }
        base_root = EnrichedRootFactory.build(nodes=base_nodes)
        branch_conflict_property_1 = EnrichedPropertyFactory.build(
            property_type=conflict_property_type_1,
            previous_value=previous_property_value_1,
            new_value=branch_property_value_1,
            action=DiffAction.UPDATED,
        )
        branch_properties_1 = {
            branch_conflict_property_1,
            EnrichedPropertyFactory.build(property_type=DatabaseEdgeType.IS_PART_OF),
        }
        branch_conflict_property_2 = EnrichedPropertyFactory.build(
            property_type=conflict_property_type_2,
            previous_value=previous_property_value_2,
            new_value=branch_property_value_2,
            action=DiffAction.REMOVED,
        )
        branch_properties_2 = {
            branch_conflict_property_2,
            EnrichedPropertyFactory.build(property_type=DatabaseEdgeType.HAS_ATTRIBUTE),
        }
        branch_relationships = {
            EnrichedRelationshipGroupFactory.build(
                name=relationship_name,
                relationships={
                    EnrichedRelationshipElementFactory.build(peer_id=peer_id_1, properties=branch_properties_1),
                    EnrichedRelationshipElementFactory.build(peer_id=peer_id_2, properties=branch_properties_2),
                },
                cardinality=RelationshipCardinality.MANY,
            )
        }
        branch_nodes = {
            EnrichedNodeFactory.build(
                uuid=node_uuid,
                kind=node_kind,
                action=DiffAction.UPDATED,
                relationships=branch_relationships,
            ),
            EnrichedNodeFactory.build(),
        }
        branch_root = EnrichedRootFactory.build(nodes=branch_nodes, diff_branch_name=branch.name)
        self._set_conflicts_to_none(base_root)
        self._set_conflicts_to_none(branch_root)

        await self.__call_system_under_test(db=db, base_enriched_diff=base_root, branch_enriched_diff=branch_root)

        for node in branch_root.nodes:
            assert node.conflict is None
            for attribute in node.attributes:
                for attr_prop in attribute.properties:
                    assert attr_prop.conflict is None
            for relationship in node.relationships:
                for element in relationship.relationships:
                    assert element.conflict is None
                    for element_prop in element.properties:
                        if (
                            node.uuid == node_uuid
                            and relationship.name == relationship_name
                            and element.peer_id == peer_id_1
                            and element_prop.property_type == conflict_property_type_1
                        ):
                            assert element_prop.conflict
                            assert element_prop.conflict == EnrichedDiffConflict(
                                uuid=element_prop.conflict.uuid,
                                base_branch_action=DiffAction.ADDED,
                                base_branch_value=base_property_value_1,
                                base_branch_changed_at=base_conflict_property_1.changed_at,
                                diff_branch_action=DiffAction.UPDATED,
                                diff_branch_value=branch_property_value_1,
                                diff_branch_changed_at=branch_conflict_property_1.changed_at,
                                selected_branch=None,
                            )
                        elif (
                            node.uuid == node_uuid
                            and relationship.name == relationship_name
                            and element.peer_id == peer_id_2
                            and element_prop.property_type == conflict_property_type_2
                        ):
                            assert element_prop.conflict
                            assert element_prop.conflict == EnrichedDiffConflict(
                                uuid=element_prop.conflict.uuid,
                                base_branch_action=DiffAction.UPDATED,
                                base_branch_value=base_property_value_2,
                                base_branch_changed_at=base_conflict_property_2.changed_at,
                                diff_branch_action=DiffAction.REMOVED,
                                diff_branch_value=branch_property_value_2,
                                diff_branch_changed_at=branch_conflict_property_2.changed_at,
                                selected_branch=None,
                            )
                        else:
                            assert element_prop.conflict is None
