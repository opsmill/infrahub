from unittest.mock import patch

from infrahub.core import registry
from infrahub.core.branch import Branch
from infrahub.core.constants import DiffAction
from infrahub.core.constants.database import DatabaseEdgeType
from infrahub.core.diff.enricher.labels import DiffLabelsEnricher
from infrahub.core.diff.payload_builder import get_display_labels
from infrahub.core.initialization import create_branch
from infrahub.core.manager import NodeManager
from infrahub.core.node import Node
from infrahub.core.schema.schema_branch import SchemaBranch
from infrahub.database import InfrahubDatabase
from tests.constants import TestKind
from tests.helpers.diff_factories import (
    EnrichedAttributeFactory,
    EnrichedConflictFactory,
    EnrichedNodeFactory,
    EnrichedPropertyFactory,
    EnrichedRelationshipElementFactory,
    EnrichedRelationshipGroupFactory,
    EnrichedRootFactory,
)
from tests.helpers.schema import CAR_SCHEMA


async def test_labels_added(
    db: InfrahubDatabase,
    default_branch: Branch,
    car_yaris_main: Node,
    person_jane_main: Node,
    person_alfred_main: Node,
    person_john_main: Node,
) -> None:
    branch = await create_branch(db=db, branch_name="branch")
    yaris_label_main = await car_yaris_main.get_display_label(db=db)
    yaris_branch = await NodeManager.get_one(db=db, branch=branch, id=car_yaris_main.get_id())
    yaris_branch.color.value = "purple"
    await yaris_branch.save(db=db)
    yaris_label_branch = await yaris_branch.get_display_label(db=db)
    alfred_branch = await NodeManager.get_one(db=db, branch=branch, id=person_alfred_main.get_id())
    await alfred_branch.delete(db=db)

    diff_attribute_owner_prop = EnrichedPropertyFactory.build(
        property_type=DatabaseEdgeType.HAS_OWNER, previous_value=car_yaris_main.id, new_value=person_john_main.id
    )
    diff_attribute_source_conflict = EnrichedConflictFactory.build(
        base_branch_value=person_alfred_main.id, diff_branch_value=person_john_main.id
    )
    diff_attribute_source_prop = EnrichedPropertyFactory.build(
        property_type=DatabaseEdgeType.HAS_SOURCE,
        previous_value=person_john_main.id,
        new_value=car_yaris_main.id,
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
        action=DiffAction.UPDATED,
        uuid=car_yaris_main.get_id(),
        kind=car_yaris_main.get_kind(),
        relationships={diff_rel},
        attributes={diff_attribute},
    )
    deleted_diff_node = EnrichedNodeFactory.build(
        action=DiffAction.REMOVED,
        uuid=person_alfred_main.get_id(),
        kind=person_alfred_main.get_kind(),
        relationships=set(),
        attributes=set(),
    )

    diff_root = EnrichedRootFactory.build(
        base_branch_name=default_branch.name, diff_branch_name=branch.name, nodes={diff_node, deleted_diff_node}
    )
    labels_enricher = DiffLabelsEnricher(db=db)

    with patch("infrahub.core.diff.enricher.labels.get_display_labels", wraps=get_display_labels) as computed_labels:
        await labels_enricher.enrich(enriched_diff_root=diff_root, calculated_diffs=None)

    # every node in this diff has a stored display label, so none is computed through a node object
    computed_labels.assert_not_called()
    nodes_by_id = {n.uuid: n for n in diff_root.nodes}
    updated_node = nodes_by_id[car_yaris_main.get_id()]
    assert updated_node.label == yaris_label_branch
    diff_attribute = updated_node.attributes.pop()
    properties_by_type = {p.property_type: p for p in diff_attribute.properties}
    owner_prop = properties_by_type[DatabaseEdgeType.HAS_OWNER]
    assert owner_prop.previous_label == yaris_label_main
    assert owner_prop.new_label == "John"
    source_prop = properties_by_type[DatabaseEdgeType.HAS_SOURCE]
    assert source_prop.previous_label == "John"
    assert source_prop.new_label == yaris_label_branch
    source_prop_conflict = source_prop.conflict
    assert source_prop_conflict.base_branch_label == "Alfred"
    assert source_prop_conflict.diff_branch_label == "John"
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
    assert related_prop_conflict.base_branch_label == yaris_label_main
    assert related_prop_conflict.diff_branch_label == "Jane"

    deleted_node = nodes_by_id[person_alfred_main.get_id()]
    assert deleted_node.label == await person_alfred_main.get_display_label(db=db)


async def test_labels_skipped(db: InfrahubDatabase, default_branch: Branch, car_person_schema: SchemaBranch) -> None:
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


async def test_labels_computed_when_not_stored(
    db: InfrahubDatabase,
    default_branch: Branch,
    car_yaris_main: Node,
    person_jane_main: Node,
    person_john_main: Node,
) -> None:
    branch = await create_branch(db=db, branch_name="branch")
    # A node created before display labels were stored has no display_label attribute at all
    await db.execute_query(
        query="""
        MATCH (n:Node {uuid: $uuid})-[:HAS_ATTRIBUTE]->(attr:Attribute {name: "display_label"})
        DETACH DELETE attr
        """,
        params={"uuid": person_john_main.get_id()},
    )
    diff_rel_element = EnrichedRelationshipElementFactory.build(
        peer_id=person_jane_main.get_id(), action=DiffAction.UPDATED, conflict=None, properties=set()
    )
    diff_rel = EnrichedRelationshipGroupFactory.build(name="owner", nodes=set(), relationships={diff_rel_element})
    car_diff_node = EnrichedNodeFactory.build(
        action=DiffAction.UPDATED,
        uuid=car_yaris_main.get_id(),
        kind=car_yaris_main.get_kind(),
        relationships={diff_rel},
        attributes=set(),
    )
    john_diff_node = EnrichedNodeFactory.build(
        action=DiffAction.UPDATED,
        uuid=person_john_main.get_id(),
        kind=person_john_main.get_kind(),
        relationships=set(),
        attributes=set(),
    )
    diff_root = EnrichedRootFactory.build(
        base_branch_name=default_branch.name, diff_branch_name=branch.name, nodes={car_diff_node, john_diff_node}
    )
    labels_enricher = DiffLabelsEnricher(db=db)

    with patch("infrahub.core.diff.enricher.labels.get_display_labels", wraps=get_display_labels) as computed_labels:
        await labels_enricher.enrich(enriched_diff_root=diff_root, calculated_diffs=None)

    # only the node without a stored label goes through a node object
    computed_labels.assert_called_once()
    assert computed_labels.call_args.kwargs["nodes"] == {branch.name: {"TestPerson": [person_john_main.get_id()]}}
    nodes_by_id = {n.uuid: n for n in diff_root.nodes}
    assert nodes_by_id[car_yaris_main.get_id()].label == await car_yaris_main.get_display_label(db=db)
    assert nodes_by_id[person_john_main.get_id()].label == "John"
    updated_element = nodes_by_id[car_yaris_main.get_id()].relationships.pop().relationships.pop()
    assert updated_element.peer_label == "Jane"


async def test_peer_label_computed_for_kind_without_template(
    db: InfrahubDatabase,
    default_branch: Branch,
    register_core_models_schema: SchemaBranch,
    car_yaris_main: Node,
) -> None:
    """A kind without a display_label template stores the NULL sentinel; its label is its representation."""
    registry.schema.register_schema(schema=CAR_SCHEMA, branch=default_branch.name)
    branch = await create_branch(db=db, branch_name="branch")
    manufacturer = await Node.init(db=db, schema=TestKind.MANUFACTURER, branch=default_branch)
    await manufacturer.new(db=db, name="Omnicorp")
    await manufacturer.save(db=db)
    manufacturer_label = await manufacturer.get_display_label(db=db)
    assert manufacturer_label == f"{TestKind.MANUFACTURER}(ID: {manufacturer.get_id()})"
    diff_rel_element = EnrichedRelationshipElementFactory.build(
        peer_id=manufacturer.get_id(), action=DiffAction.REMOVED, conflict=None, properties=set()
    )
    diff_rel = EnrichedRelationshipGroupFactory.build(
        name="manufacturer", nodes=set(), relationships={diff_rel_element}
    )
    diff_node = EnrichedNodeFactory.build(
        action=DiffAction.REMOVED,
        uuid=car_yaris_main.get_id(),
        kind=car_yaris_main.get_kind(),
        relationships={diff_rel},
        attributes=set(),
    )
    diff_root = EnrichedRootFactory.build(
        base_branch_name=default_branch.name, diff_branch_name=branch.name, nodes={diff_node}
    )
    labels_enricher = DiffLabelsEnricher(db=db)

    with patch("infrahub.core.diff.enricher.labels.get_display_labels", wraps=get_display_labels) as computed_labels:
        await labels_enricher.enrich(enriched_diff_root=diff_root, calculated_diffs=None)

    computed_labels.assert_called_once()
    assert computed_labels.call_args.kwargs["nodes"] == {
        default_branch.name: {TestKind.MANUFACTURER: [manufacturer.get_id()]}
    }
    updated_element = diff_root.nodes.pop().relationships.pop().relationships.pop()
    assert updated_element.peer_label == manufacturer_label
