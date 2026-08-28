"""Live check that the enrichment gate applies on the merge/diff changelog path.

The merge path builds changelogs from the enriched diff, not from loaded Node objects, so its
cost profile is the inverse of the mutation path: the peer display label is already carried by
the diff (free), while the node HFID is absent from the diff and must be loaded (one DB read
per changed node).
"""

import pytest

from infrahub.core.branch import Branch
from infrahub.core.changelog.diff import DiffChangelogCollector
from infrahub.core.changelog.models import RelationshipCardinalityOneChangelog
from infrahub.core.diff.coordinator import DiffCoordinator
from infrahub.core.diff.merger.merger import DiffMerger
from infrahub.core.diff.repository.repository import DiffRepository
from infrahub.core.initialization import create_branch
from infrahub.core.manager import NodeManager
from infrahub.core.node import Node
from infrahub.core.schema.schema_branch import SchemaBranch
from infrahub.core.timestamp import Timestamp
from infrahub.database import InfrahubDatabase
from infrahub.dependencies.registry import get_component_registry

ENV = "INFRAHUB_EXPERIMENTAL_WEBHOOK_ENRICHMENT"


async def test_merge_path_enrichment_gate(
    db: InfrahubDatabase,
    default_branch: Branch,
    register_simplified_proposed_change_schema: SchemaBranch,
    car_person_schema: None,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    owner = await Node.init(db=db, schema="TestPerson", branch=default_branch)
    await owner.new(db=db, name="John", height=180)
    await owner.save(db=db)

    branch = await create_branch(db=db, branch_name="merge_enrich")
    car = await Node.init(db=db, schema="TestCar", branch=branch)
    await car.new(db=db, name="Volvo", nbr_seats=5, is_electric=False, owner={"id": owner.id})
    await car.save(db=db)

    at = Timestamp()
    registry = get_component_registry()
    coordinator = await registry.get_component(DiffCoordinator, db=db, branch=branch)
    merger = await registry.get_component(DiffMerger, db=db, branch=branch)
    await coordinator.update_branch_diff(base_branch=default_branch, diff_branch=branch)
    await merger.merge_graph(at=at)
    diff = await (await registry.get_component(DiffRepository, db=db, branch=branch)).get_one(diff_branch_name=branch.name)

    collector = DiffChangelogCollector(diff=diff, db=db, branch=branch)

    def car_owner_rel(changelogs) -> RelationshipCardinalityOneChangelog:
        car_log = next(cl for _, cl in changelogs if cl.node_id == car.id)
        rel = car_log.relationships["owner"]
        assert isinstance(rel, RelationshipCardinalityOneChangelog)
        return rel, car_log

    # OFF: no hfid, peer label left empty.
    monkeypatch.setenv(ENV, "off")
    off_rel, off_car = car_owner_rel(await collector.collect_changelogs())
    assert off_car.hfid is None
    assert off_rel.peer_display_label is None

    # Enriched: node hfid resolved via a load; peer label taken from the diff (no per-peer load).
    monkeypatch.setenv(ENV, "local_hfid_peers_label")
    on_rel, on_car = car_owner_rel(await collector.collect_changelogs())

    expected_hfid = await (await NodeManager.get_one(db=db, id=car.id, kind="TestCar", branch=branch)).get_hfid(db=db)
    assert on_car.hfid == expected_hfid
    assert on_car.hfid

    owner_label = await owner.get_display_label(db=db)
    assert on_rel.peer_id == owner.id
    assert on_rel.peer_display_label == owner_label
    assert on_rel.peer_display_label != "n/a"
