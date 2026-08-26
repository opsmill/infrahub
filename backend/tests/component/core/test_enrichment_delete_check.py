"""Point-2 check: what does peer enrichment carry on a cascade delete?

When a node is deleted, its Component children are cascade-deleted first, then the secondary
(peer) changelogs are generated. This verifies whether the peer label resolved at that point is
real or the "n/a" placeholder -- i.e. whether enriching peers on delete events is meaningful.
"""

from typing import AsyncGenerator

from infrahub.core import registry
from infrahub.core.branch import Branch
from infrahub.core.changelog.models import RelationshipChangelogGetter
from infrahub.core.constants import RelationshipDeleteBehavior
from infrahub.core.manager import NodeManager
from infrahub.core.node import Node
from infrahub.database import InfrahubDatabase

import pytest

ENV = "INFRAHUB_EXPERIMENTAL_WEBHOOK_ENRICHMENT"


async def test_delete_cascade_peer_labels(
    db: AsyncGenerator[InfrahubDatabase, None],
    default_branch: Branch,
    car_accord_main: Node,
    car_prius_main: Node,
    person_john_main: Node,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv(ENV, "full")

    schema_branch = registry.schema.get_schema_branch(name=default_branch.name)
    person_schema = schema_branch.get(name="TestPerson", duplicate=False)
    person_schema.get_relationship("cars").on_delete = RelationshipDeleteBehavior.CASCADE

    car_ids = {car_accord_main.id, car_prius_main.id}

    # Faithful delete path: cascades the person AND its cars, in that order.
    deleted = await NodeManager.delete(db=db, branch=default_branch, nodes=[person_john_main])
    assert car_ids <= {d.id for d in deleted}, "cars should have cascade-deleted"

    # Secondary (peer) changelogs, exactly as the event generator builds them.
    secondaries = await RelationshipChangelogGetter(db=db, branch=default_branch).get_changelogs(
        primary_changelog=person_john_main.node_changelog
    )
    car_secondaries = [s for s in secondaries if s.node_id in car_ids]
    assert car_secondaries, "expected a secondary changelog per cascaded car peer"

    for s in car_secondaries:
        print(f"[peer {s.node_id}] display_label={s.display_label!r} hfid={s.hfid!r}", flush=True)

    # The cascaded peers are gone when their label is loaded -> placeholder, not a real label.
    assert all(s.display_label == "n/a" for s in car_secondaries)
    assert all(s.hfid is None for s in car_secondaries)

    # Contrast: each cascaded car still carries its real identity via its OWN delete changelog.
    for d in deleted:
        if d.id in car_ids:
            print(f"[own changelog {d.id}] display_label={d.node_changelog.display_label!r}", flush=True)
            assert d.node_changelog.display_label and d.node_changelog.display_label != "n/a"
