from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import uuid4

from infrahub.core.changelog.models import NodeChangelog
from infrahub.core.node import Node
from infrahub.graphql.mutations.relationship import _enrich_source_changelog

if TYPE_CHECKING:
    from infrahub.core.branch import Branch
    from infrahub.core.schema.schema_branch import SchemaBranch
    from infrahub.database import InfrahubDatabase


async def test_enrich_source_changelog_applies_the_nodes_current_labels(
    db: InfrahubDatabase, default_branch: Branch, animal_person_schema: SchemaBranch
) -> None:
    """Enrichment reads the node's labels from the database, overwriting whatever the changelog held."""
    person_schema = animal_person_schema.get(name="TestPerson")
    dog_schema = animal_person_schema.get(name="TestDog")

    owner = await Node.init(db=db, schema=person_schema, branch=default_branch)
    await owner.new(db=db, name="Jack")
    await owner.save(db=db)
    dog = await Node.init(db=db, schema=dog_schema, branch=default_branch)
    await dog.new(db=db, name="Rocky", breed="Labrador", owner=owner)
    await dog.save(db=db)

    current_hfid = await dog.get_hfid(db=db)
    current_label = await dog.get_display_label(db=db)
    assert current_hfid == ["Jack", "Rocky"]

    changelog = NodeChangelog(node_id=dog.id, node_kind="TestDog", display_label="stale", hfid=["stale"])
    await _enrich_source_changelog(node_changelog=changelog, source_id=dog.id, db=db, branch=default_branch)

    assert changelog.hfid == current_hfid
    assert changelog.display_label == current_label


async def test_enrich_source_changelog_leaves_changelog_when_node_cannot_be_read(
    db: InfrahubDatabase, default_branch: Branch
) -> None:
    """Enrichment is best-effort: an unreadable node leaves the changelog untouched, never raising."""
    changelog = NodeChangelog(node_id="n1", node_kind="TestDog", display_label="kept", hfid=["kept"])

    await _enrich_source_changelog(node_changelog=changelog, source_id=str(uuid4()), db=db, branch=default_branch)

    assert changelog.hfid == ["kept"]
    assert changelog.display_label == "kept"
