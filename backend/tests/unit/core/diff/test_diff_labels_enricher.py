from infrahub.core.diff.enricher.labels import DiffLabelsEnricher
from infrahub.core.initialization import create_branch
from infrahub.database import InfrahubDatabase

from .factories import EnrichedNodeFactory, EnrichedRelationshipGroupFactory, EnrichedRootFactory


async def test_labels_added(db: InfrahubDatabase, default_branch, car_yaris_main):
    branch = await create_branch(db=db, branch_name="branch")
    diff_rel = EnrichedRelationshipGroupFactory.build(name="owner", nodes=set())
    diff_node = EnrichedNodeFactory.build(
        uuid=car_yaris_main.get_id(), kind=car_yaris_main.get_kind(), relationships={diff_rel}
    )
    diff_root = EnrichedRootFactory.build(
        base_branch_name=default_branch.name, diff_branch_name=branch.name, nodes={diff_node}
    )
    labels_enricher = DiffLabelsEnricher(db=db)

    await labels_enricher.enrich(enriched_diff_root=diff_root, calculated_diffs=None)

    updated_node = diff_root.nodes.pop()
    assert updated_node.label == "yaris #444444"
    updated_rel = updated_node.relationships.pop()
    assert updated_rel.label == "Commander of Car"


async def test_labels_skipped(db: InfrahubDatabase, default_branch, car_person_schema):
    branch = await create_branch(db=db, branch_name="branch")
    diff_rel = EnrichedRelationshipGroupFactory.build(name="cars", nodes=set(), label="")
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
