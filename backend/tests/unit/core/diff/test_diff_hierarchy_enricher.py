from infrahub.core.diff.enricher.hierarchy import DiffHierarchyEnricher
from infrahub.core.diff.model.path import DiffAction
from infrahub.core.initialization import create_branch
from infrahub.database import InfrahubDatabase

from .factories import EnrichedNodeFactory, EnrichedRelationshipGroupFactory, EnrichedRootFactory


async def test_node_no_parent_no_rel(db: InfrahubDatabase, default_branch, person_jane_main, car_yaris_main):
    branch = await create_branch(db=db, branch_name="branch")
    diff_node = EnrichedNodeFactory.build(
        uuid=car_yaris_main.get_id(), kind=car_yaris_main.get_kind(), relationships=set()
    )
    diff_root = EnrichedRootFactory.build(
        base_branch_name=default_branch.name, diff_branch_name=branch.name, nodes={diff_node}
    )
    enricher = DiffHierarchyEnricher(db=db)
    await enricher.enrich(enriched_diff_root=diff_root, calculated_diffs=None)

    assert len(diff_root.nodes) == 2

    jane_node = diff_root.get_node(node_uuid=person_jane_main.get_id())
    yaris_node = diff_root.get_node(node_uuid=car_yaris_main.get_id())

    assert len(yaris_node.relationships) == 0

    assert jane_node.action == DiffAction.UNCHANGED
    assert len(jane_node.relationships) == 1
    jane_rel = jane_node.relationships.pop()
    assert jane_rel.action == DiffAction.UNCHANGED
    assert jane_rel.name == "cars"
    assert len(jane_rel.nodes) == 1


async def test_node_no_parent_rel(db: InfrahubDatabase, default_branch, person_jane_main, car_yaris_main):
    branch = await create_branch(db=db, branch_name="branch")
    diff_rel = EnrichedRelationshipGroupFactory.build(name="owner", action=DiffAction.UPDATED, nodes=set())
    diff_node = EnrichedNodeFactory.build(
        uuid=car_yaris_main.get_id(), kind=car_yaris_main.get_kind(), relationships={diff_rel}
    )
    diff_root = EnrichedRootFactory.build(
        base_branch_name=default_branch.name, diff_branch_name=branch.name, nodes={diff_node}
    )
    enricher = DiffHierarchyEnricher(db=db)
    await enricher.enrich(enriched_diff_root=diff_root, calculated_diffs=None)

    assert len(diff_root.nodes) == 2

    jane_node = diff_root.get_node(node_uuid=person_jane_main.get_id())
    yaris_node = diff_root.get_node(node_uuid=car_yaris_main.get_id())

    assert len(yaris_node.relationships) == 1
    yaris_rel = yaris_node.relationships.pop()
    assert yaris_rel.name == "owner"
    assert yaris_rel.action == DiffAction.UPDATED
    assert len(yaris_rel.nodes) == 0

    assert jane_node.action == DiffAction.UNCHANGED
    assert len(jane_node.relationships) == 1
    jane_rel = jane_node.relationships.pop()
    assert jane_rel.action == DiffAction.UNCHANGED
    assert jane_rel.name == "cars"
    assert len(jane_rel.nodes) == 1


async def test_node_hierarchy(db: InfrahubDatabase, default_branch, hierarchical_location_data):
    branch = await create_branch(db=db, branch_name="branch")

    rack1 = hierarchical_location_data["paris-r1"]
    site1 = hierarchical_location_data["paris"]

    diff_node = EnrichedNodeFactory.build(uuid=rack1.get_id(), kind=rack1.get_kind(), relationships=set())
    diff_root = EnrichedRootFactory.build(
        base_branch_name=default_branch.name, diff_branch_name=branch.name, nodes={diff_node}
    )
    enricher = DiffHierarchyEnricher(db=db)
    await enricher.enrich(enriched_diff_root=diff_root, calculated_diffs=None)

    assert len(diff_root.nodes) == 3

    rack1_node = diff_root.get_node(node_uuid=rack1.get_id())
    site1_node = diff_root.get_node(node_uuid=site1.get_id())

    assert len(rack1_node.relationships) == 0

    assert site1_node.action == DiffAction.UNCHANGED
    assert len(site1_node.relationships) == 1
    site1_rel = site1_node.relationships.pop()
    assert site1_rel.action == DiffAction.UNCHANGED
    assert site1_rel.name == "children"
    assert len(site1_rel.nodes) == 1
