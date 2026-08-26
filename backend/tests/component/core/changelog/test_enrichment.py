"""Live verification of the webhook payload enrichment prototype gate.

Runs the real Node.save() / RelationshipChangelogGetter path against a live database at
each enrichment level and checks what lands in the changelog that feeds the webhook payload.
"""

import pytest

from infrahub.core.branch import Branch
from infrahub.core.changelog.models import (
    RelationshipCardinalityManyChangelog,
    RelationshipChangelogGetter,
)
from infrahub.core.node import Node
from infrahub.core.schema.schema_branch import SchemaBranch
from infrahub.database import InfrahubDatabase

ENV_VAR = "INFRAHUB_EXPERIMENTAL_WEBHOOK_ENRICHMENT"


async def _create_person_and_dog(db: InfrahubDatabase, branch: Branch, schema: SchemaBranch) -> tuple[Node, Node]:
    person = await Node.init(db=db, schema=schema.get(name="TestPerson"), branch=branch)
    await person.new(db=db, name={"value": "Jack", "is_protected": True})
    await person.save(db=db)

    dog = await Node.init(db=db, schema=schema.get(name="TestDog"), branch=branch)
    await dog.new(db=db, name={"value": "Rocky", "owner": person.id}, breed="Labrador", owner=person)
    await dog.save(db=db)
    return person, dog


async def test_off_leaves_changelog_unenriched(
    db: InfrahubDatabase,
    default_branch: Branch,
    animal_person_schema: SchemaBranch,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv(ENV_VAR, raising=False)

    person1, dog1 = await _create_person_and_dog(db, default_branch, animal_person_schema)

    assert dog1.node_changelog.hfid is None

    secondaries = await RelationshipChangelogGetter(db=db, branch=default_branch).get_changelogs(
        primary_changelog=dog1.node_changelog
    )
    person_sec = secondaries[0]
    assert person_sec.node_id == person1.id
    assert person_sec.display_label == "n/a"
    assert person_sec.hfid is None

    animals = person_sec.relationships["animals"]
    assert isinstance(animals, RelationshipCardinalityManyChangelog)
    assert animals.peers[0].peer_display_label is None
    assert animals.peers[0].peer_hfid is None


async def test_primary_adds_hfid_but_not_peer_labels(
    db: InfrahubDatabase,
    default_branch: Branch,
    animal_person_schema: SchemaBranch,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv(ENV_VAR, "primary")

    person1, dog1 = await _create_person_and_dog(db, default_branch, animal_person_schema)

    # Primary node carries its own materialized hfid.
    assert dog1.node_changelog.hfid == await dog1.get_hfid(db=db)
    assert dog1.node_changelog.hfid

    # Peers stay unenriched at this level.
    secondaries = await RelationshipChangelogGetter(db=db, branch=default_branch).get_changelogs(
        primary_changelog=dog1.node_changelog
    )
    person_sec = secondaries[0]
    assert person_sec.display_label == "n/a"
    assert person_sec.hfid is None
    assert person_sec.relationships["animals"].peers[0].peer_display_label is None


async def test_full_enriches_primary_and_peers(
    db: InfrahubDatabase,
    default_branch: Branch,
    animal_person_schema: SchemaBranch,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv(ENV_VAR, "full")

    person1, dog1 = await _create_person_and_dog(db, default_branch, animal_person_schema)

    # Primary node hfid, as at the `primary` level.
    assert dog1.node_changelog.hfid == await dog1.get_hfid(db=db)
    assert dog1.node_changelog.hfid

    secondaries = await RelationshipChangelogGetter(db=db, branch=default_branch).get_changelogs(
        primary_changelog=dog1.node_changelog
    )
    person_sec = secondaries[0]
    assert person_sec.node_id == person1.id

    # The peer node's real label/hfid are resolved from the database, not the "n/a" placeholder.
    assert person_sec.display_label != "n/a"
    assert person_sec.display_label == await person1.get_display_label(db=db)
    assert person_sec.hfid == await person1.get_hfid(db=db)

    # The relationship entry pointing back to the primary carries the primary's label/hfid.
    animals = person_sec.relationships["animals"]
    assert isinstance(animals, RelationshipCardinalityManyChangelog)
    assert animals.peers[0].peer_display_label == dog1.node_changelog.display_label
    assert animals.peers[0].peer_hfid == dog1.node_changelog.hfid
