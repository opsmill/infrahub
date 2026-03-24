from infrahub.core.diff.enricher.hierarchy import DiffHierarchyEnricher
from infrahub.core.diff.model.path import DiffAction, NodeIdentifier
from infrahub.core.diff.parent_node_adder import DiffParentNodeAdder
from infrahub.core.initialization import create_branch
from infrahub.core.node import Node
from infrahub.database import InfrahubDatabase

from .factories import EnrichedNodeFactory, EnrichedRelationshipGroupFactory, EnrichedRootFactory
from .get_one_node import get_one_diff_node


async def test_node_no_parent_no_rel(db: InfrahubDatabase, default_branch, person_jane_main, car_yaris_main) -> None:
    branch = await create_branch(db=db, branch_name="branch")
    diff_node = EnrichedNodeFactory.build(
        identifier=NodeIdentifier(
            uuid=car_yaris_main.get_id(),
            kind=car_yaris_main.get_kind(),
            db_id=car_yaris_main.db_id,
        ),
        relationships=set(),
    )
    diff_root = EnrichedRootFactory.build(
        base_branch_name=default_branch.name, diff_branch_name=branch.name, nodes={diff_node}
    )
    enricher = DiffHierarchyEnricher(db=db, parent_adder=DiffParentNodeAdder())
    await enricher.enrich(enriched_diff_root=diff_root, calculated_diffs=None)

    assert len(diff_root.nodes) == 2

    jane_node = get_one_diff_node(diff_root=diff_root, node_uuid=person_jane_main.get_id())
    yaris_node = get_one_diff_node(diff_root=diff_root, node_uuid=car_yaris_main.get_id())

    assert len(yaris_node.relationships) == 1
    yaris_rel = yaris_node.relationships.pop()
    assert yaris_rel.action == DiffAction.UNCHANGED
    assert yaris_rel.name == "owner"
    assert len(yaris_rel.nodes) == 1

    assert jane_node.action == DiffAction.UNCHANGED
    assert len(jane_node.relationships) == 0


async def test_node_no_parent_rel(db: InfrahubDatabase, default_branch, person_jane_main, car_yaris_main) -> None:
    branch = await create_branch(db=db, branch_name="branch")
    diff_rel = EnrichedRelationshipGroupFactory.build(name="owner", action=DiffAction.UPDATED, nodes=set())
    diff_node = EnrichedNodeFactory.build(
        identifier=NodeIdentifier(
            uuid=car_yaris_main.get_id(),
            kind=car_yaris_main.get_kind(),
            db_id=car_yaris_main.db_id,
        ),
        relationships={diff_rel},
    )
    diff_root = EnrichedRootFactory.build(
        base_branch_name=default_branch.name, diff_branch_name=branch.name, nodes={diff_node}
    )
    enricher = DiffHierarchyEnricher(db=db, parent_adder=DiffParentNodeAdder())
    await enricher.enrich(enriched_diff_root=diff_root, calculated_diffs=None)

    assert len(diff_root.nodes) == 2

    jane_node = get_one_diff_node(diff_root=diff_root, node_uuid=person_jane_main.get_id())
    yaris_node = get_one_diff_node(diff_root=diff_root, node_uuid=car_yaris_main.get_id())

    assert len(yaris_node.relationships) == 1
    yaris_rel = yaris_node.relationships.pop()
    assert yaris_rel.name == "owner"
    assert yaris_rel.action == DiffAction.UPDATED
    assert len(yaris_rel.nodes) == 1

    assert jane_node.action == DiffAction.UNCHANGED
    assert len(jane_node.relationships) == 0


async def test_node_hierarchy(db: InfrahubDatabase, default_branch, hierarchical_location_schema) -> None:
    branch = await create_branch(db=db, branch_name="branch")

    # we need hierarchies where the
    region_a = await Node.init(db=db, branch=branch, schema="LocationRegion")
    await region_a.new(db=db, name="a")
    await region_a.save(db=db)
    site_b = await Node.init(db=db, branch=branch, schema="LocationSite")
    await site_b.new(db=db, name="b", parent=region_a)
    await site_b.save(db=db)
    rack_c = await Node.init(db=db, branch=branch, schema="LocationRack")
    await rack_c.new(db=db, name="c", parent=site_b)
    await rack_c.save(db=db)
    region_z = await Node.init(db=db, branch=branch, schema="LocationRegion")
    await region_z.new(db=db, name="z")
    await region_z.save(db=db)
    site_y = await Node.init(db=db, branch=branch, schema="LocationSite")
    await site_y.new(db=db, name="y", parent=region_z)
    await site_y.save(db=db)
    rack_x = await Node.init(db=db, branch=branch, schema="LocationRack")
    await rack_x.new(db=db, name="x", parent=site_y)
    await rack_x.save(db=db)

    diff_node1 = EnrichedNodeFactory.build(
        identifier=NodeIdentifier(
            uuid=rack_c.get_id(),
            kind=rack_c.get_kind(),
            db_id=rack_c.db_id,
        ),
        relationships=set(),
    )
    diff_node2 = EnrichedNodeFactory.build(
        identifier=NodeIdentifier(
            uuid=rack_x.get_id(),
            kind=rack_x.get_kind(),
            db_id=rack_x.db_id,
        ),
        relationships=set(),
    )
    diff_root = EnrichedRootFactory.build(
        base_branch_name=default_branch.name, diff_branch_name=branch.name, nodes={diff_node1, diff_node2}
    )
    enricher = DiffHierarchyEnricher(db=db, parent_adder=DiffParentNodeAdder())
    await enricher.enrich(enriched_diff_root=diff_root, calculated_diffs=None)

    assert len(diff_root.nodes) == 6

    rack_c_node = get_one_diff_node(diff_root=diff_root, node_uuid=rack_c.get_id())
    site_b_node = get_one_diff_node(diff_root=diff_root, node_uuid=site_b.get_id())
    region_a_node = get_one_diff_node(diff_root=diff_root, node_uuid=region_a.get_id())

    assert len(rack_c_node.relationships) == 1
    rack_c_rel = rack_c_node.relationships.pop()
    assert rack_c_rel.name == "parent"
    assert rack_c_rel.action is DiffAction.UNCHANGED
    assert len(rack_c_rel.nodes) == 1
    rack_c_parent_node = rack_c_rel.nodes.pop()
    assert rack_c_parent_node.uuid == site_b.id

    assert site_b_node.action == DiffAction.UNCHANGED
    assert len(site_b_node.relationships) == 1
    site_b_rel = site_b_node.relationships.pop()
    assert site_b_rel.action == DiffAction.UNCHANGED
    assert site_b_rel.name == "parent"
    assert len(site_b_rel.nodes) == 1
    site_b_parent_node = site_b_rel.nodes.pop()
    assert site_b_parent_node.uuid == region_a.id

    assert region_a_node.action == DiffAction.UNCHANGED
    assert len(region_a_node.relationships) == 0

    rack_x_node = get_one_diff_node(diff_root=diff_root, node_uuid=rack_x.get_id())
    site_y_node = get_one_diff_node(diff_root=diff_root, node_uuid=site_y.get_id())
    region_z_node = get_one_diff_node(diff_root=diff_root, node_uuid=region_z.get_id())

    assert len(rack_x_node.relationships) == 1
    rack_x_rel = rack_x_node.relationships.pop()
    assert rack_x_rel.name == "parent"
    assert rack_x_rel.action is DiffAction.UNCHANGED
    assert len(rack_x_rel.nodes) == 1
    rack_x_parent_node = rack_x_rel.nodes.pop()
    assert rack_x_parent_node.uuid == site_y.id

    assert site_y_node.action == DiffAction.UNCHANGED
    assert len(site_y_node.relationships) == 1
    site_y_rel = site_y_node.relationships.pop()
    assert site_y_rel.action == DiffAction.UNCHANGED
    assert site_y_rel.name == "parent"
    assert len(site_y_rel.nodes) == 1
    site_y_parent_node = site_y_rel.nodes.pop()
    assert site_y_parent_node.uuid == region_z.id

    assert region_z_node.action == DiffAction.UNCHANGED
    assert len(region_z_node.relationships) == 0
