from infrahub.core.constants.database import DatabaseEdgeType
from infrahub.core.diff.enricher.labels import DiffLabelsEnricher
from infrahub.core.initialization import create_branch
from infrahub.core.manager import NodeManager
from infrahub.database import InfrahubDatabase

from .factories import (
    EnrichedAttributeFactory,
    EnrichedConflictFactory,
    EnrichedNodeFactory,
    EnrichedPropertyFactory,
    EnrichedRelationshipElementFactory,
    EnrichedRelationshipGroupFactory,
    EnrichedRootFactory,
)


async def test_labels_added(
    db: InfrahubDatabase, default_branch, car_yaris_main, person_jane_main, person_alfred_main, person_john_main
):
    branch = await create_branch(db=db, branch_name="branch")
    alfred_branch = await NodeManager.get_one(db=db, branch=branch, id=person_alfred_main.get_id())
    await alfred_branch.delete(db=db)

    diff_attribute_owner_prop = EnrichedPropertyFactory.build(
        property_type=DatabaseEdgeType.HAS_OWNER, previous_value=None, new_value=person_john_main.id
    )
    diff_attribute_source_conflict = EnrichedConflictFactory.build(
        base_branch_value=person_john_main.id, diff_branch_value=person_alfred_main.id
    )
    diff_attribute_source_prop = EnrichedPropertyFactory.build(
        property_type=DatabaseEdgeType.HAS_SOURCE,
        previous_value=person_john_main.id,
        new_value=None,
        conflict=diff_attribute_source_conflict,
    )
    diff_attribute_value_conflict = EnrichedConflictFactory.build(
        base_branch_value=person_john_main.id, diff_branch_value=person_jane_main.id
    )
    diff_attribute_value_prop = EnrichedPropertyFactory.build(
        property_type=DatabaseEdgeType.HAS_VALUE,
        previous_value=person_john_main.id,
        new_value=person_jane_main.id,
        conflict=diff_attribute_value_conflict,
    )
    diff_attribute = EnrichedAttributeFactory.build(
        properties={diff_attribute_owner_prop, diff_attribute_source_prop, diff_attribute_value_prop}
    )
    diff_element_is_protected_conflict = EnrichedConflictFactory.build(
        base_branch_value=car_yaris_main.id, diff_branch_value=person_jane_main.id
    )
    diff_element_protected_prop = EnrichedPropertyFactory.build(
        property_type=DatabaseEdgeType.IS_PROTECTED,
        previous_value=person_john_main.id,
        new_value=person_jane_main.id,
        conflict=diff_element_is_protected_conflict,
    )
    diff_element_is_related_conflict = EnrichedConflictFactory.build(
        base_branch_value=car_yaris_main.id, diff_branch_value=person_jane_main.id
    )
    diff_element_related_prop = EnrichedPropertyFactory.build(
        property_type=DatabaseEdgeType.IS_RELATED,
        previous_value=person_john_main.id,
        new_value=person_jane_main.id,
        conflict=diff_element_is_related_conflict,
    )
    diff_element_conflict = EnrichedConflictFactory.build(
        base_branch_value=person_alfred_main.id, diff_branch_value=person_jane_main.id
    )
    diff_rel_element = EnrichedRelationshipElementFactory.build(
        peer_id=person_jane_main.id,
        conflict=diff_element_conflict,
        properties={diff_element_protected_prop, diff_element_related_prop},
    )
    diff_rel = EnrichedRelationshipGroupFactory.build(name="owner", nodes=set(), relationships={diff_rel_element})
    diff_node = EnrichedNodeFactory.build(
        uuid=car_yaris_main.get_id(),
        kind=car_yaris_main.get_kind(),
        relationships={diff_rel},
        attributes={diff_attribute},
    )
    deleted_diff_node = EnrichedNodeFactory.build(
        uuid=person_alfred_main.get_id(), kind=person_alfred_main.get_kind(), relationships=set(), attributes=set()
    )

    diff_root = EnrichedRootFactory.build(
        base_branch_name=default_branch.name, diff_branch_name=branch.name, nodes={diff_node, deleted_diff_node}
    )
    labels_enricher = DiffLabelsEnricher(db=db)

    await labels_enricher.enrich(enriched_diff_root=diff_root, calculated_diffs=None)

    nodes_by_id = {n.uuid: n for n in diff_root.nodes}
    updated_node = nodes_by_id[car_yaris_main.get_id()]
    assert updated_node.label == "yaris #444444"
    diff_attribute = updated_node.attributes.pop()
    properties_by_type = {p.property_type: p for p in diff_attribute.properties}
    owner_prop = properties_by_type[DatabaseEdgeType.HAS_OWNER]
    assert owner_prop.previous_label is None
    assert owner_prop.new_label == "John"
    source_prop = properties_by_type[DatabaseEdgeType.HAS_SOURCE]
    assert source_prop.previous_label == "John"
    assert source_prop.new_label is None
    source_prop_conflict = source_prop.conflict
    assert source_prop_conflict.base_branch_label == "John"
    assert source_prop_conflict.diff_branch_label == "Alfred"
    value_prop = properties_by_type[DatabaseEdgeType.HAS_VALUE]
    assert value_prop.previous_label is None
    assert value_prop.new_label is None
    value_prop_conflict = value_prop.conflict
    assert value_prop_conflict.base_branch_label is None
    assert value_prop_conflict.diff_branch_label is None

    updated_rel = updated_node.relationships.pop()
    assert updated_rel.label == "Commander of Car"
    updated_element = updated_rel.relationships.pop()
    assert updated_element.peer_label == "Jane"
    element_conflict = updated_element.conflict
    assert element_conflict.base_branch_label == "Alfred"
    assert element_conflict.diff_branch_label == "Jane"
    properties_by_type = {p.property_type: p for p in updated_element.properties}
    protected_prop = properties_by_type[DatabaseEdgeType.IS_PROTECTED]
    assert protected_prop.previous_label is None
    assert protected_prop.new_label is None
    protected_prop_conflict = protected_prop.conflict
    assert protected_prop_conflict.base_branch_label is None
    assert protected_prop_conflict.diff_branch_label is None
    related_prop = properties_by_type[DatabaseEdgeType.IS_RELATED]
    assert related_prop.previous_label == "John"
    assert related_prop.new_label == "Jane"
    related_prop_conflict = related_prop.conflict
    assert related_prop_conflict.base_branch_label == "yaris #444444"
    assert related_prop_conflict.diff_branch_label == "Jane"

    deleted_node = nodes_by_id[person_alfred_main.get_id()]
    assert deleted_node.label == await person_alfred_main.render_display_label(db=db)


async def test_labels_skipped(db: InfrahubDatabase, default_branch, car_person_schema):
    branch = await create_branch(db=db, branch_name="branch")
    diff_rel_element = EnrichedRelationshipElementFactory.build(peer_id="not-a-real-one", peer_label=None)
    diff_rel = EnrichedRelationshipGroupFactory.build(
        name="cars", nodes=set(), label="", relationships={diff_rel_element}
    )
    diff_node = EnrichedNodeFactory.build(relationships={diff_rel}, kind="TestPerson", label="")
    diff_root = EnrichedRootFactory.build(
        base_branch_name=default_branch.name, diff_branch_name=branch.name, nodes={diff_node}
    )
    labels_enricher = DiffLabelsEnricher(db=db)

    await labels_enricher.enrich(enriched_diff_root=diff_root, calculated_diffs=None)

    updated_node = diff_root.nodes.pop()
    assert not updated_node.label
    updated_rel = updated_node.relationships.pop()
    assert updated_rel.label == "Cars"
    updated_element = updated_rel.relationships.pop()
    assert updated_element.peer_label is None
