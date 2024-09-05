from copy import deepcopy
from uuid import uuid4

from infrahub.core.constants import DiffAction, RelationshipCardinality
from infrahub.core.constants.database import DatabaseEdgeType
from infrahub.core.diff.enricher.cardinality_one import DiffCardinalityOneEnricher
from infrahub.core.diff.model.path import EnrichedDiffProperty
from infrahub.core.initialization import create_branch
from infrahub.core.timestamp import Timestamp
from infrahub.database import InfrahubDatabase

from .factories import (
    EnrichedNodeFactory,
    EnrichedPropertyFactory,
    EnrichedRelationshipElementFactory,
    EnrichedRelationshipGroupFactory,
    EnrichedRootFactory,
)


class TestDiffCardinalityOneEnricher:
    async def test_no_cardinality_one_relationships(self, db: InfrahubDatabase, car_person_schema):
        branch = await create_branch(db=db, branch_name="branch")
        enricher = DiffCardinalityOneEnricher(db=db)
        diff_relationship = EnrichedRelationshipGroupFactory.build(
            name="cars",
            nodes=set(),
            cardinality=RelationshipCardinality.MANY,
            relationships={EnrichedRelationshipElementFactory.build() for _ in range(3)},
        )
        diff_node = EnrichedNodeFactory.build(kind="TestPerson", relationships={diff_relationship})
        diff_root = EnrichedRootFactory.build(diff_branch_name=branch.name, nodes={diff_node})
        diff_root_copy = deepcopy(diff_root)

        await enricher.enrich(enriched_diff_root=diff_root, calculated_diffs=None)

        assert diff_root == diff_root_copy

    async def test_cardinality_one_relationship_update(self, db: InfrahubDatabase, car_person_schema):
        branch = await create_branch(db=db, branch_name="branch")
        enricher = DiffCardinalityOneEnricher(db=db)
        peer_id_1 = str(uuid4())
        peer_id_2 = str(uuid4())
        has_owner_prop_1 = EnrichedPropertyFactory.build(
            property_type=DatabaseEdgeType.HAS_OWNER, action=DiffAction.REMOVED, conflict=None
        )
        is_related_prop_1 = EnrichedPropertyFactory.build(
            property_type=DatabaseEdgeType.IS_RELATED,
            action=DiffAction.REMOVED,
            conflict=None,
            previous_value=peer_id_1,
            new_value=None,
        )
        diff_rel_element_1 = EnrichedRelationshipElementFactory.build(
            properties={has_owner_prop_1, is_related_prop_1}, peer_id=peer_id_1
        )
        has_source_prop_2 = EnrichedPropertyFactory.build(
            property_type=DatabaseEdgeType.HAS_SOURCE, action=DiffAction.REMOVED, conflict=None
        )
        is_related_prop_2 = EnrichedPropertyFactory.build(
            property_type=DatabaseEdgeType.IS_RELATED,
            action=DiffAction.ADDED,
            conflict=None,
            previous_value=None,
            new_value=peer_id_2,
            changed_at=is_related_prop_1.changed_at.add_delta(minutes=2),
        )
        diff_rel_element_2 = EnrichedRelationshipElementFactory.build(
            properties={has_source_prop_2, is_related_prop_2},
            peer_id=peer_id_2,
            changed_at=diff_rel_element_1.changed_at.add_delta(minutes=2),
        )

        diff_relationship = EnrichedRelationshipGroupFactory.build(
            name="owner",
            nodes=set(),
            cardinality=RelationshipCardinality.ONE,
            relationships={diff_rel_element_1, diff_rel_element_2},
        )
        diff_node = EnrichedNodeFactory.build(kind="TestCar", relationships={diff_relationship})
        diff_root = EnrichedRootFactory.build(diff_branch_name=branch.name, nodes={diff_node})

        await enricher.enrich(enriched_diff_root=diff_root, calculated_diffs=None)

        assert len(diff_root.nodes) == 1
        diff_node = diff_root.nodes.pop()
        assert len(diff_node.relationships) == 1
        diff_rel = diff_node.relationships.pop()
        assert len(diff_rel.relationships) == 1
        diff_rel_element = diff_rel.relationships.pop()
        assert diff_rel_element.changed_at == diff_rel_element_2.changed_at
        assert diff_rel_element.action == diff_rel_element_2.action
        assert diff_rel_element.peer_id == peer_id_2
        assert diff_rel_element.peer_label == diff_rel_element_2.peer_label
        assert diff_rel_element.conflict is None
        diff_properties = diff_rel_element.properties
        assert len(diff_properties) == 3
        assert has_owner_prop_1 in diff_properties
        assert has_source_prop_2 in diff_properties
        assert (
            EnrichedDiffProperty(
                property_type=DatabaseEdgeType.IS_RELATED,
                changed_at=is_related_prop_2.changed_at,
                previous_value=peer_id_1,
                new_value=peer_id_2,
                action=DiffAction.UPDATED,
                conflict=None,
            )
            in diff_properties
        )

    async def test_cardinality_one_relationship_simulataneous_update(self, db: InfrahubDatabase, car_person_schema):
        branch = await create_branch(db=db, branch_name="branch")
        enricher = DiffCardinalityOneEnricher(db=db)
        peer_id_1 = str(uuid4())
        peer_id_2 = str(uuid4())
        owner_1 = str(uuid4())
        owner_2 = str(uuid4())
        timestamp = Timestamp()
        has_owner_prop_1 = EnrichedPropertyFactory.build(
            property_type=DatabaseEdgeType.HAS_OWNER,
            action=DiffAction.REMOVED,
            previous_value=owner_1,
            new_value=None,
            conflict=None,
            changed_at=timestamp,
        )
        is_related_prop_1 = EnrichedPropertyFactory.build(
            property_type=DatabaseEdgeType.IS_RELATED,
            action=DiffAction.REMOVED,
            conflict=None,
            previous_value=peer_id_1,
            new_value=None,
            changed_at=timestamp,
        )
        diff_rel_element_1 = EnrichedRelationshipElementFactory.build(
            properties={has_owner_prop_1, is_related_prop_1},
            peer_id=peer_id_1,
            action=DiffAction.REMOVED,
            changed_at=timestamp,
        )
        has_owner_prop_2 = EnrichedPropertyFactory.build(
            property_type=DatabaseEdgeType.HAS_OWNER,
            action=DiffAction.ADDED,
            conflict=None,
            previous_value=None,
            new_value=owner_2,
            changed_at=timestamp,
        )
        is_related_prop_2 = EnrichedPropertyFactory.build(
            property_type=DatabaseEdgeType.IS_RELATED,
            action=DiffAction.ADDED,
            conflict=None,
            previous_value=None,
            new_value=peer_id_2,
            changed_at=timestamp,
        )
        diff_rel_element_2 = EnrichedRelationshipElementFactory.build(
            properties={has_owner_prop_2, is_related_prop_2},
            peer_id=peer_id_2,
            action=DiffAction.ADDED,
            changed_at=timestamp,
        )

        diff_relationship = EnrichedRelationshipGroupFactory.build(
            name="owner",
            nodes=set(),
            cardinality=RelationshipCardinality.ONE,
            relationships={diff_rel_element_1, diff_rel_element_2},
        )
        diff_node = EnrichedNodeFactory.build(kind="TestCar", relationships={diff_relationship})
        diff_root = EnrichedRootFactory.build(diff_branch_name=branch.name, nodes={diff_node})

        await enricher.enrich(enriched_diff_root=diff_root, calculated_diffs=None)

        assert len(diff_root.nodes) == 1
        diff_node = diff_root.nodes.pop()
        assert len(diff_node.relationships) == 1
        diff_rel = diff_node.relationships.pop()
        assert len(diff_rel.relationships) == 1
        diff_rel_element = diff_rel.relationships.pop()
        assert diff_rel_element.changed_at == diff_rel_element_2.changed_at
        assert diff_rel_element.action == DiffAction.UPDATED
        assert diff_rel_element.peer_id == peer_id_2
        assert diff_rel_element.peer_label == diff_rel_element_2.peer_label
        assert diff_rel_element.conflict is None
        diff_properties = diff_rel_element.properties
        assert len(diff_properties) == 2
        assert (
            EnrichedDiffProperty(
                property_type=DatabaseEdgeType.HAS_OWNER,
                changed_at=timestamp,
                previous_value=owner_1,
                new_value=owner_2,
                action=DiffAction.UPDATED,
                conflict=None,
            )
            in diff_properties
        )
        assert (
            EnrichedDiffProperty(
                property_type=DatabaseEdgeType.IS_RELATED,
                changed_at=timestamp,
                previous_value=peer_id_1,
                new_value=peer_id_2,
                action=DiffAction.UPDATED,
                conflict=None,
            )
            in diff_properties
        )

    async def test_cardinality_one_relationship_reverted_update(self, db: InfrahubDatabase, car_person_schema):
        branch = await create_branch(db=db, branch_name="branch")
        enricher = DiffCardinalityOneEnricher(db=db)
        peer_id = str(uuid4())
        has_owner_prop_1 = EnrichedPropertyFactory.build(
            property_type=DatabaseEdgeType.HAS_OWNER, action=DiffAction.REMOVED, conflict=None
        )
        is_related_prop_1 = EnrichedPropertyFactory.build(
            property_type=DatabaseEdgeType.IS_RELATED,
            action=DiffAction.REMOVED,
            conflict=None,
            previous_value=peer_id,
            new_value=None,
        )
        diff_rel_element_1 = EnrichedRelationshipElementFactory.build(
            properties={has_owner_prop_1, is_related_prop_1}, peer_id=peer_id
        )
        has_source_prop_2 = EnrichedPropertyFactory.build(
            property_type=DatabaseEdgeType.HAS_SOURCE, action=DiffAction.REMOVED, conflict=None
        )
        is_related_prop_2 = EnrichedPropertyFactory.build(
            property_type=DatabaseEdgeType.IS_RELATED,
            action=DiffAction.ADDED,
            conflict=None,
            previous_value=None,
            new_value=peer_id,
            changed_at=is_related_prop_1.changed_at.add_delta(minutes=2),
        )
        diff_rel_element_2 = EnrichedRelationshipElementFactory.build(
            properties={has_source_prop_2, is_related_prop_2},
            peer_id=peer_id,
            changed_at=diff_rel_element_1.changed_at.add_delta(minutes=2),
        )

        diff_relationship = EnrichedRelationshipGroupFactory.build(
            name="owner",
            nodes=set(),
            cardinality=RelationshipCardinality.ONE,
            relationships={diff_rel_element_1, diff_rel_element_2},
        )
        diff_node = EnrichedNodeFactory.build(kind="TestCar", relationships={diff_relationship})
        diff_root = EnrichedRootFactory.build(diff_branch_name=branch.name, nodes={diff_node})

        await enricher.enrich(enriched_diff_root=diff_root, calculated_diffs=None)

        assert len(diff_root.nodes) == 1
        diff_node = diff_root.nodes.pop()
        assert len(diff_node.relationships) == 1
        diff_rel = diff_node.relationships.pop()
        assert len(diff_rel.relationships) == 1
        diff_rel_element = diff_rel.relationships.pop()
        assert diff_rel_element.changed_at == diff_rel_element_2.changed_at
        assert diff_rel_element.action == diff_rel_element_2.action
        assert diff_rel_element.peer_id == peer_id
        assert diff_rel_element.peer_label == diff_rel_element_2.peer_label
        assert diff_rel_element.conflict is None
        diff_properties = diff_rel_element.properties
        assert len(diff_properties) == 2
        assert has_owner_prop_1 in diff_properties
        assert has_source_prop_2 in diff_properties
